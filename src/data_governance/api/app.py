"""FastAPI 应用 — 数据治理平台 API。

重构要点：
- Pydantic 请求模型替代 dict=Body()
- CORS 收敛（配置化，不再 allow_origins=["*"]）
- API Key 认证（可选，环境变量控制）
- Service 层分离业务逻辑
- 类型注解完整
"""

from __future__ import annotations

import csv
import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from data_governance.acceptance.engine import run_acceptance
from data_governance.acceptance.report import render_markdown
from data_governance.acceptance.serialize import acceptance_report_to_dict
from data_governance.api.metric_services import (
    load_latest_metric_review,
    load_metric_review_for_metric,
    run_metric_review_for_id,
)
from data_governance.api.middleware import setup_auth, setup_cors
from data_governance.api.schemas import (
    HealthResponse,
    MetricCreateRequest,
    MetricUpdateRequest,
    StatsResponse,
)
from data_governance.config_loader import load_domains
from data_governance.io.catalog import load_catalog
from data_governance.io.lineage_loader import list_lineage_domains, load_domain_lineage
from data_governance.io.metric_tree import load_metric_tree
from data_governance.llm.bootstrap import bootstrap_llm_env
from data_governance.paths import repo_root
from data_governance.release.registry import ReleaseRegistry
from data_governance.release.service import publish_domain
from data_governance.schemas.roots import RootCreateRequest
from data_governance.scoring.store import (
    load_score,
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

    @app.get("/api/roots")
    def list_roots(domain: str | None = Query(default=None)) -> list[dict]:
        catalog = load_catalog(base)
        rows = catalog.roots
        if domain:
            rows = [r for r in rows if r.domain_code == domain]
        return [asdict(r) for r in rows]

    @app.post("/api/roots")
    def create_root(body: RootCreateRequest) -> dict:
        """手工创建词根，自动分配 R_{DOMAIN}_{seq} ID（IT2-2）。"""
        from data_governance.io.roots_csv import (
            append_root_row,
            make_root_csv_row,
            roots_csv_path,
        )

        domain = body.domain_code.strip().lower()
        domains = load_domains(base / "config" / "domains.csv")
        if domain not in {d.domain_code for d in domains}:
            raise HTTPException(400, f"unknown domain: {domain}")

        path = roots_csv_path(base / "roots", domain)
        existing = load_catalog(base).roots
        if any(r.domain_code == domain and r.root_en == body.root_en for r in existing):
            raise HTTPException(400, f"root_en already exists in domain {domain}: {body.root_en}")

        row = make_root_csv_row(
            domain=domain,
            root_cn=body.root_cn,
            root_en=body.root_en,
            root_abbr=body.root_abbr or body.root_en,
            root_type=body.root_type,
            description=body.description,
            source_model=body.source_model,
            review_status=body.review_status,
            roots_dir=base / "roots",
        )
        append_root_row(path, row)
        return row.model_dump()

    @app.put("/api/roots/{root_id}")
    def update_root(root_id: str, body: dict) -> dict:
        """更新词根字段（IT2-2）。"""
        from data_governance.io.roots_csv import roots_csv_path, update_root_row

        catalog = load_catalog(base)
        target = next((r for r in catalog.roots if r.root_id == root_id), None)
        if target is None:
            raise HTTPException(404, f"root not found: {root_id}")
        path = roots_csv_path(base / "roots", target.domain_code)
        updated = update_root_row(path, root_id, body)
        if updated is None:
            raise HTTPException(404, f"root not found: {root_id}")
        return updated

    # ── 指标 CRUD ────────────────────────────────────────────────

    @app.get("/api/metrics")
    def list_metrics(domain: str | None = Query(default=None)) -> list[dict]:
        return metric_svc.list_metrics(domain)

    @app.get("/api/metrics/stats", response_model=StatsResponse)
    def metrics_statistics() -> StatsResponse:
        stats = metric_svc.get_stats()
        return StatsResponse(**stats)

    @app.put("/api/metrics/{metric_id}")
    def update_metric(
        metric_id: str,
        body: MetricUpdateRequest,
    ) -> dict:
        payload = body.model_dump(exclude_unset=True, exclude_none=True)
        try:
            return metric_svc.update(metric_id, payload)
        except KeyError:
            raise HTTPException(404, f"metric not found: {metric_id}") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/metrics")
    def add_metric(body: MetricCreateRequest) -> dict:
        payload = body.model_dump(exclude_unset=True, exclude_none=True)
        try:
            return metric_svc.create(payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/metrics/batch-generate")
    def metrics_batch_generate(body: dict) -> dict:
        """批量生成派生指标：原子指标 × 修饰词组合，dry_run 可预览不落盘。"""
        atomic_ids = [str(x).strip() for x in (body or {}).get("atomic_ids", []) if str(x).strip()]
        modifier_ids = [str(x).strip() for x in (body or {}).get("modifier_ids", []) if str(x).strip()]
        dry_run = bool((body or {}).get("dry_run", False))
        if not atomic_ids or not modifier_ids:
            raise HTTPException(400, "atomic_ids 与 modifier_ids 必填")
        from data_governance.generate import generate_derived_metrics

        result = generate_derived_metrics(base, atomic_ids, modifier_ids, dry_run=dry_run)
        return {
            "dry_run": dry_run,
            "generated": [
                {"metric_id": m.metric_id, "metric_cn": m.metric_cn, "metric_en": m.metric_en}
                for m in result.generated
            ],
            "existing": result.existing,
            "invalid_atomics": result.invalid_atomics,
            "invalid_modifiers": result.invalid_modifiers,
        }

    # ── 指标评审 ────────────────────────────────────────────────

    @app.post("/api/metrics/{metric_id}/review")
    def review_metric(metric_id: str) -> dict:
        try:
            return run_metric_review_for_id(base, metric_id)
        except KeyError:
            raise HTTPException(404, f"metric not found: {metric_id}") from None
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc

    @app.get("/api/metrics/export")
    def export_metrics() -> PlainTextResponse:
        text = metric_svc.export_csv()
        return PlainTextResponse(
            content=text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="metrics_export.csv"'},
        )

    @app.get("/api/metric-reviews/latest")
    def latest_metric_review(domain: str = Query(default="sale")) -> dict:
        doc = load_latest_metric_review(base, domain)
        if doc is None:
            raise HTTPException(404, "no metric review found for domain")
        return doc

    @app.get("/api/metrics/{metric_id}/review/latest")
    def metric_review_latest(metric_id: str) -> dict:
        doc = load_metric_review_for_metric(base, metric_id)
        if doc is None:
            raise HTTPException(404, f"no review found for metric {metric_id}")
        return doc

    # ── 指标评分（六维度明细 + 多模型评审） ────────────────────

    @app.get("/api/metrics/{metric_id}/score")
    def metric_score(metric_id: str) -> dict:
        """指标评分明细：六维度逐检查项打分 + 多模型评审明细。"""
        cached = load_score(base, metric_id)
        if cached is not None:
            return cached.to_dict()
        catalog = load_catalog(base)
        metric = next((m for m in catalog.metrics if m.metric_id == metric_id), None)
        if metric is None:
            raise HTTPException(404, f"metric not found: {metric_id}")
        from data_governance.scoring.engine import score_metric

        review_detail = load_metric_review_for_metric(base, metric_id)
        return score_metric(metric, catalog, base, model_review_detail=review_detail).to_dict()

    @app.post("/api/metrics/{metric_id}/score/refresh")
    def metric_score_refresh(metric_id: str) -> dict:
        """重新评分并落盘（scores/{id}.json + _summary.csv）。"""
        try:
            result = score_and_persist(base, metric_id, trigger="manual")
        except KeyError:
            raise HTTPException(404, f"metric not found: {metric_id}") from None
        return result.to_dict()

    # ── 口径助手：起草 ──────────────────────────────────────────

    @app.post("/api/metrics/{metric_id}/caliber/draft")
    def caliber_draft_endpoint(metric_id: str) -> dict:
        """多模型起草口径并落库（status=pending），返回推荐版 + 模型差异（IT2-4）。"""
        from data_governance.caliber.draft import draft_caliber, persist_draft

        catalog = load_catalog(base)
        metric = next((m for m in catalog.metrics if m.metric_id == metric_id), None)
        if metric is None:
            raise HTTPException(404, f"metric not found: {metric_id}")
        try:
            result = draft_caliber(metric, base_dir=base)
            persist_draft(base, metric_id, result)
        except Exception as exc:
            raise HTTPException(500, f"caliber draft failed: {exc}") from exc
        return {
            "metric_id": metric_id,
            "status": "pending",
            "caliber": result.draft,
            "diff_summary": result.diff_summary,
            "high_risk": result.high_risk,
            "ai_by": result.ai_by,
        }

    # ── 口径助手：核查流 ────────────────────────────────────────

    @app.get("/api/caliber/pending")
    def caliber_pending(domain: str | None = Query(default=None)) -> list[dict]:
        """待核查口径队列（status ∈ pending/rejected）。"""
        from data_governance.caliber.review import pending_queue

        return pending_queue(base, domain)

    @app.post("/api/metrics/{metric_id}/caliber/approve")
    def caliber_approve(metric_id: str, body: dict | None = None) -> dict:
        """批准口径草稿，触发重新评分（IT2-5）。"""
        from data_governance.caliber.review import approve_caliber

        checked_by = (body or {}).get("checked_by", "system") if body else "system"
        try:
            return approve_caliber(base, metric_id, checked_by=checked_by)
        except KeyError:
            raise HTTPException(404, f"metric not found: {metric_id}") from None

    @app.post("/api/metrics/{metric_id}/caliber/reject")
    def caliber_reject(metric_id: str, body: dict | None = None) -> dict:
        """打回口径草稿，附原因（IT2-5）。"""
        from data_governance.caliber.review import reject_caliber

        reason = ((body or {}).get("reason") or "") if body else ""
        if not reason.strip():
            raise HTTPException(400, "reason 必填")
        checked_by = (body or {}).get("checked_by", "system") if body else "system"
        try:
            return reject_caliber(base, metric_id, reason, checked_by=checked_by)
        except KeyError:
            raise HTTPException(404, f"metric not found: {metric_id}") from None

    @app.put("/api/metrics/{metric_id}/caliber")
    def caliber_update(metric_id: str, body: dict) -> dict:
        """人工修改口径，改后 status=edited 并重评分（IT2-5）。"""
        from data_governance.caliber.review import update_caliber

        checked_by = (body or {}).get("checked_by", "system") if body else "system"
        try:
            return update_caliber(base, metric_id, body or {}, checked_by=checked_by)
        except KeyError:
            raise HTTPException(404, f"metric not found: {metric_id}") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

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

    # ── 修饰规则 & 指标树 ────────────────────────────────────────

    @app.get("/api/modifier-rules")
    def modifier_rules() -> list[dict]:
        path = base / "config" / "modifier_rules.csv"
        if not path.is_file():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    @app.get("/api/metric-tree")
    def get_metric_tree() -> dict:
        nodes_path = base / "config" / "metric_tree.csv"
        nodes = load_metric_tree(nodes_path)
        catalog = load_catalog(base)
        domain_map = {d.domain_code: d.domain_name_cn for d in load_domains(base / "config" / "domains.csv")}
        metrics_by_node: dict[str, list[dict]] = {}
        unassigned: list[dict] = []
        for m in catalog.metrics:
            payload = asdict(m)
            nid = (m.tree_node_id or "").strip()
            if nid:
                metrics_by_node.setdefault(nid, []).append(payload)
            else:
                unassigned.append(payload)
        return {
            "nodes": [asdict(n) for n in nodes],
            "metrics_by_node": metrics_by_node,
            "unassigned_metrics": unassigned,
            "domain_names": domain_map,
        }

    # ── 验收 ────────────────────────────────────────────────────

    @app.get("/api/acceptance")
    def get_acceptance(refresh: bool = Query(default=False)) -> dict:
        if not refresh:
            scoring = base / "scoring"
            if scoring.is_dir():
                reports = sorted(scoring.glob("acceptance_report_*.md"), reverse=True)
                if reports:
                    return {
                        "source": "cached_markdown",
                        "markdown_path": str(reports[0]),
                        "markdown": reports[0].read_text(encoding="utf-8"),
                    }
        report = run_acceptance(base)
        payload = acceptance_report_to_dict(report)
        payload["source"] = "live"
        payload["markdown"] = render_markdown(report)
        return payload

    @app.post("/api/acceptance/run")
    def run_acceptance_endpoint() -> dict:
        from datetime import date

        report = run_acceptance(base)
        out = base / "scoring" / f"acceptance_report_{date.today().isoformat()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(report), encoding="utf-8")
        payload = acceptance_report_to_dict(report)
        payload["markdown_path"] = str(out)
        return payload

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
