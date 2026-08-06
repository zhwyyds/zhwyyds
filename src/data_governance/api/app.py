"""FastAPI 应用 — 数据治理平台 API。

重构要点：
- Pydantic 请求模型替代 dict=Body()
- CORS 收敛（配置化，不再 allow_origins=["*"]）
- API Key 认证（可选，环境变量控制）
- Service 层分离业务逻辑
- 类型注解完整
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from data_governance.api.middleware import setup_auth, setup_cors
from data_governance.api.schemas import (
    HealthResponse,
)
from data_governance.config_loader import load_domains
from data_governance.io.catalog import load_catalog
from data_governance.io.lineage_loader import list_lineage_domains, load_domain_lineage
from data_governance.llm.bootstrap import bootstrap_llm_env
from data_governance.paths import repo_root
from data_governance.release.registry import ReleaseRegistry
from data_governance.release.service import publish_domain
from data_governance.scoring.store import (
    load_summary,
    score_and_persist,
)
from data_governance.services import MetricService


def resolve_base_dir(explicit: Path | None = None) -> Path:
    """解析项目根目录：优先参数 > 环境变量 > 自动探测。"""
    if explicit is not None:
        return explicit.resolve()
    env = os.environ.get("DATA_GOV_BASE_DIR")
    if env:
        return Path(env).resolve()
    return repo_root()


def create_app(base_dir: Path | None = None) -> FastAPI:
    """创建 FastAPI 应用实例。"""
    base = resolve_base_dir(base_dir)
    bootstrap_llm_env(base)

    app = FastAPI(
        title="Data Governance API",
        version="0.2.0",
        description="数据治理平台 — 词根驱动的指标管理体系",
    )

    # 安全中间件
    setup_cors(app)
    setup_auth(app)

    # Service 层
    metric_svc = MetricService(base)
    from data_governance.services.ai_service import AiService

    ai_svc = AiService(base)

    # 按域拆分路由（R3）
    from data_governance.api.routes_metrics import register as register_metrics
    from data_governance.api.routes_roots import register as register_roots

    register_roots(app, base, ai_svc)
    register_metrics(app, base, metric_svc, ai_svc)

    # ── 基础端点 ──────────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", base_dir=str(base))

    @app.get("/api/meta")
    def meta() -> dict:
        links = {
            "domains": "/api/domains",
            "roots": "/api/roots",
            "metrics": "/api/metrics",
            "metric_tree": "/api/metric-tree",
            "acceptance": "/api/acceptance",
            "llm_status": "/api/llm/status",
        }
        ui_dir = base / "ui-prototype"
        if (ui_dir / "index.html").is_file():
            links["ui"] = "/ui/"
            links["metric_spec_template"] = "/ui/metric-spec-template.html"
        return {"base_dir": str(base), "links": links}

    @app.get("/api/llm/status")
    def llm_status() -> dict:
        from data_governance.llm.env import llm_mode_from_env, provider_api_key, resolve_use_mock

        loaded = bootstrap_llm_env(base)
        return {
            "mode": llm_mode_from_env(),
            "use_mock": resolve_use_mock(None),
            "providers_configured": {
                "OpenAI": bool(provider_api_key("OpenAI")),
                "Anthropic": bool(provider_api_key("Anthropic")),
                "Qwen": bool(provider_api_key("Qwen")),
                "ZhipuAI": bool(provider_api_key("ZhipuAI")),
                "DeepSeek": bool(provider_api_key("DeepSeek")),
            },
            "dotenv_present": loaded["dotenv"],
            "secrets_file_present": loaded["secrets_json"],
            "secrets_path": loaded["secrets_path"],
            "secrets_template": "config/secrets.example.json",
            "env_template": ".env.example",
        }

    # ── 域 & 词根 ────────────────────────────────────────────────

    @app.get("/api/domains")
    def list_domains() -> list[dict]:
        path = base / "config" / "domains.csv"
        if not path.is_file():
            raise HTTPException(404, "domains.csv not found")
        return [asdict(d) for d in load_domains(path)]

    @app.post("/api/scores/refresh")
    def scores_refresh() -> dict:
        """全量重评分所有指标。"""
        catalog = load_catalog(base)
        done = 0
        for m in catalog.metrics:
            score_and_persist(base, m.metric_id, trigger="batch")
            done += 1
        return {"scored": done, "summary": load_summary(base)}

    @app.get("/api/scores/summary")
    def scores_summary() -> list[dict]:
        """评分汇总（scores/_summary.csv）。"""
        return load_summary(base)

    # ── 版本发布控制 ────────────────────────────────────────────

    @app.post("/api/domains/{domain}/publish")
    def publish_domain_endpoint(domain: str, body: dict | None = None) -> dict:
        """按域批量发布 approved 指标，自动分配版本号（发布控制）。"""
        note = (body or {}).get("note", "") if body else ""
        released_by = (body or {}).get("released_by", "system") if body else "system"
        try:
            record = publish_domain(base, domain, note=note, released_by=released_by)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return record.to_dict()

    @app.get("/api/domains/{domain}/releases")
    def domain_releases(domain: str) -> list[dict]:
        """某主题域的发布历史。"""
        return [r.to_dict() for r in ReleaseRegistry(base).list_releases(domain)]

    @app.post("/api/domains/{domain}/revert")
    def revert_domain_release(domain: str, body: dict | None = None) -> dict:
        """撤销指定版本发布：指标回退上一版本，registry 标记 revoked（IT3-1）。"""
        from data_governance.release.service import revert_release

        version = int((body or {}).get("version", 0) or 0) if body else 0
        if version <= 0:
            raise HTTPException(400, "version 必填且为正整数")
        note = ((body or {}).get("note") or "") if body else ""
        try:
            return revert_release(base, domain, version, note=note)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/domains/{domain}/version-diff")
    def domain_version_diff(
        domain: str,
        from_version: str = Query(default="v1", alias="from"),
        to_version: str = Query(default="v2", alias="to"),
    ) -> dict:
        """对比两个发布版本的指标差异（IT3-1）。"""
        from data_governance.release.service import version_diff

        return version_diff(base, domain, from_version, to_version)

    @app.get("/api/releases/overview")
    def releases_overview() -> list[dict]:
        """跨域发布总览（IT3-1）。"""
        from data_governance.release.service import release_overview

        return release_overview(base)

    # ── 域级治理看板 ────────────────────────────────────────────

    @app.get("/api/dashboard/domains")
    def domains_dashboard() -> list[dict]:
        """每域治理红绿灯：词根/指标/评分/血缘/口径/发布（IT3-2）。"""
        from data_governance.dashboard import domain_dashboard

        return domain_dashboard(base)

    # ── 血缘 ────────────────────────────────────────────────────

    @app.get("/api/lineage")
    def get_lineage(domain: str = Query(default="sale")) -> dict:
        payload = load_domain_lineage(base, domain)
        if payload is None:
            raise HTTPException(404, f"lineage not found for domain {domain}")
        return payload

    @app.get("/api/lineage/domains")
    def lineage_domains() -> dict:
        return {"domains": list_lineage_domains(base)}

    @app.post("/api/lineage/upload")
    def upload_lineage(body: dict) -> dict:
        """上传血缘 JSON：校验结构后写入 lineage/{domain}_lineage.json（IT2-3）。"""
        from data_governance.io.lineage_store import save_lineage
        from data_governance.validation import validate_lineage_data

        issues = validate_lineage_data(body)
        errors = [i.message for i in issues if i.severity == "error"]
        if errors:
            raise HTTPException(400, "lineage 数据校验失败: " + "; ".join(errors))

        domain = str((body or {}).get("domain") or "").strip().lower()
        if not domain:
            raise HTTPException(400, "缺少 domain 字段")
        lineages = body.get("lineages") or []
        path = save_lineage(base, domain, body)
        return {"domain": domain, "lineages": len(lineages), "written_to": path.name}

    # ── 修饰规则 & 指标树 & 配置管理 ────────────────────────────

    @app.get("/api/modifier-rules")
    def modifier_rules() -> list[dict]:
        from data_governance.io.modifier_rules import load_modifiers_file

        return load_modifiers_file(base / "config" / "modifier_rules.csv")

    @app.post("/api/modifier-rules")
    def create_modifier(body: dict) -> dict:
        """新增修饰词（问题 11）。"""
        from data_governance.io.modifier_rules import append_modifier

        try:
            return append_modifier(base / "config" / "modifier_rules.csv", body or {})
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.put("/api/modifier-rules/{modifier_id}")
    def update_modifier_endpoint(modifier_id: str, body: dict) -> dict:
        from data_governance.io.modifier_rules import update_modifier

        updated = update_modifier(base / "config" / "modifier_rules.csv", modifier_id, body or {})
        if updated is None:
            raise HTTPException(404, f"modifier not found: {modifier_id}")
        return updated

    @app.delete("/api/modifier-rules/{modifier_id}")
    def delete_modifier_endpoint(modifier_id: str) -> dict:
        from data_governance.io.modifier_rules import delete_modifier

        if not delete_modifier(base / "config" / "modifier_rules.csv", modifier_id):
            raise HTTPException(404, f"modifier not found: {modifier_id}")
        return {"deleted": modifier_id}

    # ── 模型配置管理（问题 13） ─────────────────────────────────

    @app.get("/api/models")
    def list_models() -> list[dict]:
        from data_governance.io.models_store import load_models_file

        return load_models_file(base / "config" / "models.csv")

    @app.post("/api/models")
    def create_model(body: dict) -> dict:
        from data_governance.io.models_store import append_model

        try:
            return append_model(base / "config" / "models.csv", body or {})
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.put("/api/models/{model_id}")
    def update_model_endpoint(model_id: str, body: dict) -> dict:
        from data_governance.io.models_store import update_model

        updated = update_model(base / "config" / "models.csv", model_id, body or {})
        if updated is None:
            raise HTTPException(404, f"model not found: {model_id}")
        return updated

    @app.delete("/api/models/{model_id}")
    def delete_model_endpoint(model_id: str) -> dict:
        from data_governance.io.models_store import delete_model

        if not delete_model(base / "config" / "models.csv", model_id):
            raise HTTPException(404, f"model not found: {model_id}")
        return {"deleted": model_id}

    # ── 导入导出（问题 3/6） ────────────────────────────────────

    @app.get("/api/prompts/{prompt_type}")
    def get_prompt(prompt_type: str) -> dict:
        """查看 AI 提示词模板（评审/词根/口径），便于审查与调优（用户需求）。"""
        if prompt_type == "metric_review":
            from data_governance.prompts.metric_review import METRIC_REVIEW_TEMPLATE

            return {
                "type": "metric_review",
                "name": "指标评审提示词",
                "location": "src/data_governance/prompts/metric_review.py",
                "template": METRIC_REVIEW_TEMPLATE,
            }
        if prompt_type == "root_generation":
            from data_governance.prompts.root_generation import ROOT_GENERATION_TEMPLATE

            return {
                "type": "root_generation",
                "name": "词根生成提示词",
                "location": "src/data_governance/prompts/root_generation.py",
                "template": ROOT_GENERATION_TEMPLATE,
            }
        if prompt_type == "caliber_draft":
            return {
                "type": "caliber_draft",
                "name": "口径起草提示词（动态构建）",
                "location": "src/data_governance/caliber/draft.py build_prompt()",
                "template": (
                    "（口径起草提示词为动态函数，基于单个指标构建。)\n"
                    "核心要求：输入含糊指标定义，输出结构化 JSON：\n"
                    "caliber_business / caliber_formula / caliber_period / "
                    "caliber_granularity / caliber_boundary / caliber_source / suggestions\n"
                    "详见 build_prompt() 源码或调用口径起草接口查看完整内容。"
                ),
            }
        raise HTTPException(404, f"unknown prompt type: {prompt_type}")

    # ── 静态资源 / UI ───────────────────────────────────────────

    ui_dir = base / "ui-prototype"
    if ui_dir.is_dir() and (ui_dir / "index.html").is_file():
        js_dir = ui_dir / "js"
        css_dir = ui_dir / "css"
        if js_dir.is_dir():
            app.mount("/js", StaticFiles(directory=str(js_dir.resolve())), name="ui-js")
        if css_dir.is_dir():
            app.mount("/css", StaticFiles(directory=str(css_dir.resolve())), name="ui-css")
        app.mount("/ui", StaticFiles(directory=str(ui_dir.resolve()), html=True), name="ui")

        @app.get("/")
        def root_page() -> FileResponse:
            return FileResponse(ui_dir / "index.html")
    else:

        @app.get("/")
        def root_index() -> JSONResponse:
            return JSONResponse({"message": "Data Governance API", "docs": "/docs", "meta": "/api/meta"})

    return app
