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
    RevisionApplyRequest,
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
            synonyms=body.synonyms,
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

    @app.post("/api/roots/generate")
    def roots_generate(body: dict) -> dict:
        """词根 AI 生成（问题 7）：多模型生成词根定义，返回评审结果（不写库）。"""
        from data_governance.pipeline.root_generation import RootGenerationPipeline
        from data_governance.schemas.roots import RootGenerationRequest, TermInput

        domain = str((body or {}).get("domain") or "sale").strip().lower()
        terms_raw = (body or {}).get("terms") or []
        if not terms_raw:
            raise HTTPException(400, "terms 必填（至少一个中文词根）")
        terms = []
        for t in terms_raw:
            cn = str((t or {}).get("cn_term") or "").strip()
            if not cn:
                raise HTTPException(400, "cn_term 不能为空")
            terms.append(
                TermInput(cn_term=cn, context=str((t or {}).get("context") or "").strip())
            )

        # 词根语义归并（G3）：术语命中已有词根（含同义词）→ 直接复用，跳过 LLM，禁止自创
        from data_governance.io.catalog import load_catalog
        from data_governance.roots.dictionary import (
            build_root_dictionary,
            dictionary_to_prompt_text,
            find_root_for_term,
        )

        catalog = load_catalog(base)
        reuse_items: list[dict] = []
        pending_terms: list[TermInput] = []
        for t in terms:
            hit = find_root_for_term(catalog.roots, t.cn_term, domain=domain)
            if hit is not None:
                reuse_items.append(
                    {
                        "cn_term": t.cn_term,
                        "context": t.context,
                        "model_results": [],
                        "comparison": {
                            "root_en_consistent": True,
                            "root_abbr_consistent": True,
                            "root_type_consistent": True,
                            "conflict_fields": [],
                        },
                        "final_decision": {
                            "root_en": hit.root_en,
                            "root_abbr": hit.root_abbr,
                            "root_type": hit.root_type,
                            "description": f"已复用已有词根 {hit.root_id}（{hit.root_cn}），未新建",
                            "decision_reason": f"语义命中已有词根 {hit.root_id}（含同义词），强制复用",
                            "decision_type": "model_consensus",
                            "review_status": "approved",
                        },
                        "auto_approved": True,
                        "reused_root_id": hit.root_id,
                    }
                )
            else:
                pending_terms.append(t)

        root_text = dictionary_to_prompt_text(build_root_dictionary(catalog.roots, domain=domain))
        if pending_terms:
            req = RootGenerationRequest(domain=domain, terms=pending_terms)
            doc = RootGenerationPipeline(
                base_dir=base, use_mock=None, root_dictionary_text=root_text
            ).run(req, write_roots=False)
            payload = doc.model_dump(mode="json")
            payload["items"] = payload["items"] + reuse_items
            return payload
        if reuse_items:
            return {
                "review_id": f"RR_{domain.upper()}_001",
                "domain": domain,
                "review_type": "root_generation",
                "created_at": __import__("data_governance.io.reviews", fromlist=["now_iso_cn"]).now_iso_cn(),
                "models_used": [],
                "items": reuse_items,
            }
        return {"review_id": f"RR_{domain.upper()}_001", "domain": domain, "items": []}

    @app.post("/api/roots/generate/commit")
    def roots_generate_commit(body: dict) -> dict:
        """把已生成的词根评审结果确认入库（勾选 cn_terms；空=全部 auto_approved）。"""
        import json as _json

        from data_governance.io.roots_csv import append_root_row, make_root_csv_row
        from data_governance.schemas.roots import ReviewStatus, SourceModel

        review_id = str((body or {}).get("review_id") or "").strip()
        if not review_id:
            raise HTTPException(400, "review_id 必填")
        cn_terms = [(t or "").strip() for t in (body or {}).get("cn_terms") or []]
        cn_terms = [t for t in cn_terms if t]

        reviews_dir = base / "reviews" / "root_reviews"
        doc: dict | None = None
        for path in sorted(reviews_dir.glob("*_root_review_*.json"), reverse=True):
            try:
                candidate = _json.loads(path.read_text(encoding="utf-8"))
            except (_json.JSONDecodeError, OSError):
                continue
            if isinstance(candidate, dict) and candidate.get("review_id") == review_id:
                doc = candidate
                break
        if doc is None:
            raise HTTPException(404, f"review not found: {review_id}")

        domain = str(doc.get("domain") or "sale").lower()
        created: list[str] = []
        skipped: list[str] = []
        for item in doc.get("items") or []:
            cn = str(item.get("cn_term") or "").strip()
            if item.get("reused_root_id"):
                skipped.append(f"{cn}(已复用 {item['reused_root_id']}，无需入库)")
                continue
            if not item.get("auto_approved"):
                skipped.append(f"{cn}(未自动通过)")
                continue
            if cn_terms and cn not in cn_terms:
                skipped.append(f"{cn}(未勾选)")
                continue
            fd = item.get("final_decision") or {}
            if not (fd.get("root_en") or "").strip():
                skipped.append(f"{cn}(无英文名)")
                continue
            try:
                row = make_root_csv_row(
                    domain=domain,
                    root_cn=cn,
                    root_en=str(fd["root_en"]).strip(),
                    root_abbr=str(fd.get("root_abbr") or "").strip() or str(fd["root_en"]).strip(),
                    root_type=str(fd.get("root_type") or "noun").strip() or "noun",
                    description=str(fd.get("description") or "").strip(),
                    source_model=SourceModel("model_consensus"),
                    review_status=ReviewStatus.approved,
                    roots_dir=base / "roots",
                )
                append_root_row(base / "roots" / f"{domain}_roots.csv", row)
                created.append(cn)
            except ValueError as exc:
                skipped.append(f"{cn}({exc})")
        return {"review_id": review_id, "domain": domain, "created": created, "skipped": skipped}

    # ── 指标 CRUD ────────────────────────────────────────────────

    @app.get("/api/metrics")
    def list_metrics(domain: str | None = Query(default=None)) -> list[dict]:
        return metric_svc.list_metrics(domain)

    @app.post("/api/metrics/suggest")
    def metric_suggest(body: dict) -> dict:
        """AI 辅助生成指标定义：mock（相似指标复用+词根提示）/ live（LLM 生成）——问题 2 修复。"""
        from data_governance.caliber.draft import parse_response
        from data_governance.config_loader import load_models
        from data_governance.llm.env import resolve_use_mock

        metric_cn = str((body or {}).get("metric_cn") or "").strip()
        domain = str((body or {}).get("domain_code") or "").strip().lower()
        desc = str((body or {}).get("caliber_desc") or "").strip()
        if not metric_cn:
            raise HTTPException(400, "metric_cn 必填")
        catalog = load_catalog(base)

        if resolve_use_mock(None):
            same = next((m for m in catalog.metrics if m.metric_cn == metric_cn), None)
            if same is not None:
                return {
                    "source": "similar_metric",
                    "metric_cn": metric_cn,
                    "metric_en": same.metric_en,
                    "metric_abbr": same.metric_abbr,
                    "caliber_desc": same.caliber_desc,
                    "unit": same.unit,
                    "frequency": same.frequency,
                    "dimensions": same.dimensions,
                    "scenario": same.scenario,
                    "formula": same.formula,
                    "data_sources": same.data_sources,
                    "suggestions": ["已复用同名指标的既有定义，请核查后确认"],
                    "suggested_roots": [],
                }
            hits = [r.root_en for r in catalog.roots if r.domain_code == domain and r.root_cn and r.root_cn in metric_cn]
            return {
                "source": "rule_hint",
                "metric_cn": metric_cn,
                "metric_en": "_".join(hits),
                "metric_abbr": "",
                "caliber_desc": desc,
                "unit": "",
                "frequency": "月",
                "dimensions": "",
                "scenario": "",
                "formula": "",
                "data_sources": "",
                "suggestions": ["mock 模式给出词根组合提示；配置 ≥2 个 LLM Key 后可生成完整定义"],
                "suggested_roots": [],
            }

        # live：单模型生成指标定义
        models = load_models("metric_review", config_path=base / "config" / "models.csv")
        from data_governance.llm.factory import build_live_clients

        clients = build_live_clients(models)
        from data_governance.roots.dictionary import build_root_dictionary, dictionary_to_prompt_text

        entries = build_root_dictionary(catalog.roots, domain=domain)
        root_text = dictionary_to_prompt_text(entries)
        prompt = (
            "你是数据治理平台的指标定义专家。根据中文指标名生成指标定义，只输出 JSON：\n"
            f'{{"metric_cn":"{metric_cn}","metric_en":"snake_case 英文名","metric_abbr":"缩写",'
            f'"caliber_desc":"业务定义(含统计周期与边界)","unit":"单位","frequency":"月/日/周",'
            f'"dimensions":"常用维度","scenario":"适用场景","formula":"计算公式",'
            f'"formula_cn":"公式中文说明","data_sources":"来源表","tech_caliber":"技术口径",'
            f'"suggestions":["需人工确认的点"],'
            f'"suggested_roots":[{{"root_cn":"中文词根","root_en":"词根英文","root_abbr":"缩写",'
            f'"root_type":"noun/verb/adj/unit/time","description":"说明"}}]}}\n\n'
            f"参考词根库（该域的既有标准词根，含同义词）：\n{root_text}\n\n"
            "词根强制复用规则（必须遵守）：\n"
            "1. metric_en 必须由词根库中的词根组合而成（使用 root_en 原词）\n"
            "2. 术语语义若已被词根库覆盖（包括其同义词），必须复用对应词根，禁止自创新词根\n"
            "3. 例如词根库已有 rent（同义词：租金/租赁/出租），则「租赁收入」必须用 rent，不能写 lease\n"
            "4. suggested_roots 只列出 metric_en 用到的词根中【词根库缺失】的部分（供同步新建），"
            "词根库已有的绝不要列；无缺失则为空数组 []\n"
            f"\n中文名：{metric_cn}\n域：{domain}"
        )
        from data_governance.llm.parallel import run_models_parallel_prompt

        raws = run_models_parallel_prompt(clients, prompt, cache_base_dir=base)
        merged: dict = {}
        for _mname, raw in raws:
            try:
                data = parse_response(raw)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for key in (
                "metric_en", "metric_abbr", "caliber_desc", "unit", "frequency",
                "dimensions", "scenario", "formula", "formula_cn", "data_sources",
                "tech_caliber", "suggestions", "suggested_roots",
            ):
                v = data.get(key)
                if v not in (None, "") and key not in merged:
                    merged[key] = v
        if not merged.get("metric_en"):
            raise HTTPException(500, "模型未返回有效的指标定义，请重试或检查 Key 余额")
        merged.setdefault("metric_cn", metric_cn)
        merged.setdefault("frequency", "月")
        merged.setdefault("suggestions", [])
        merged.setdefault("source", "llm_multi" if len(raws) > 1 else "llm")

        # 同步补词根（G5）：suggested_roots 过滤掉词根库已有的，仅返回缺失的
        from data_governance.roots.dictionary import find_root_for_term

        missing_roots: list[dict] = []
        for sr in merged.get("suggested_roots") or []:
            if not isinstance(sr, dict):
                continue
            en = str(sr.get("root_en") or "").strip().lower()
            cn = str(sr.get("root_cn") or "").strip()
            if not en or not cn:
                continue
            if find_root_for_term(catalog.roots, en) is not None:
                continue
            if find_root_for_term(catalog.roots, cn) is not None:
                continue
            missing_roots.append(
                {
                    "root_cn": cn,
                    "root_en": en,
                    "root_abbr": str(sr.get("root_abbr") or "").strip() or en,
                    "root_type": str(sr.get("root_type") or "noun").strip() or "noun",
                    "description": str(sr.get("description") or "").strip(),
                }
            )
        merged["suggested_roots"] = missing_roots
        return merged

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

    @app.post("/api/metrics/{metric_id}/review/{review_id}/apply-revision")
    def review_apply_revision(metric_id: str, review_id: str, body: RevisionApplyRequest) -> dict:
        """把评审的 AI 修订建议（勾选字段）应用到指标定义。"""
        from data_governance.api.metric_services import apply_metric_revision

        try:
            return apply_metric_revision(
                base,
                metric_id,
                review_id,
                body.fields,
                checked_by=body.checked_by or "system",
            )
        except KeyError:
            raise HTTPException(404, f"metric not found: {metric_id}") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
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

    @app.post("/api/caliber/backfill")
    def caliber_backfill(body: dict | None = None) -> dict:
        """存量一键补全：对未起草口径的指标批量起草（IT2-6）。"""
        from data_governance.caliber.review import backfill_calibers

        domain = ((body or {}).get("domain") or "") if body else ""
        dry_run = bool((body or {}).get("dry_run", False)) if body else False
        return backfill_calibers(base, domain or None, dry_run=dry_run)

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

    @app.get("/api/roots/export")
    def export_roots(domain: str | None = Query(default=None)) -> PlainTextResponse:
        """词根导出 CSV（问题 6）。"""
        from data_governance.io.roots_csv import ROOT_CSV_HEADER

        catalog = load_catalog(base)
        rows = [r for r in catalog.roots if not domain or r.domain_code == domain]
        import io as _io

        buf = _io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=ROOT_CSV_HEADER)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: getattr(r, k, "") for k in ROOT_CSV_HEADER})
        return PlainTextResponse(
            content=buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="roots_export.csv"'},
        )

    @app.post("/api/roots/import")
    def import_roots(body: dict) -> dict:
        """词根导入：CSV 文本 → 校验 → 批量入库（问题 6）。"""
        import io as _io

        from data_governance.io.roots_csv import append_root_row, make_root_csv_row

        csv_text = str((body or {}).get("csv") or "")
        if not csv_text.strip():
            raise HTTPException(400, "csv 内容为空")
        rows = list(csv.DictReader(_io.StringIO(csv_text)))
        created, skipped = 0, 0
        errors: list[str] = []
        for row in rows:
            domain = str(row.get("domain_code") or "").strip().lower()
            root_cn = str(row.get("root_cn") or "").strip()
            root_en = str(row.get("root_en") or "").strip()
            if not domain or not root_cn or not root_en:
                skipped += 1
                continue
            if any(r.domain_code == domain and r.root_en == root_en for r in load_catalog(base).roots):
                skipped += 1
                continue
            try:
                from data_governance.schemas.roots import ReviewStatus, RootType, SourceModel

                record = make_root_csv_row(
                    domain=domain,
                    root_cn=root_cn,
                    root_en=root_en,
                    root_abbr=str(row.get("root_abbr") or "").strip() or root_en,
                    root_type=RootType(str(row.get("root_type") or "noun").strip() or "noun"),
                    description=str(row.get("description") or "").strip(),
                    source_model=SourceModel.manual,
                    review_status=ReviewStatus.pending,
                    roots_dir=base / "roots",
                )
                append_root_row(base / "roots" / f"{domain}_roots.csv", record)
                created += 1
            except Exception as exc:
                errors.append(f"{root_cn}: {exc}")
        return {"created": created, "skipped": skipped, "errors": errors}

    @app.post("/api/metrics/import")
    def import_metrics(body: dict) -> dict:
        """指标导入：CSV 文本 → 校验 → 批量入库（问题 3）。"""
        import io as _io

        from data_governance.io.metrics_csv import batch_create_metrics

        csv_text = str((body or {}).get("csv") or "")
        if not csv_text.strip():
            raise HTTPException(400, "csv 内容为空")
        rows = list(csv.DictReader(_io.StringIO(csv_text)))
        payloads = []
        for row in rows:
            mid = str(row.get("metric_id") or "").strip()
            cn = str(row.get("metric_cn") or "").strip()
            if not mid or not cn:
                continue
            payloads.append({k: v for k, v in row.items() if v is not None})
        created, skipped = batch_create_metrics(base, payloads)
        return {"created": len(created), "skipped": len(skipped), "payload_rows": len(payloads)}

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
