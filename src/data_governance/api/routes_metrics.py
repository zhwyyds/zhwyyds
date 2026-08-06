"""指标路由模块（R3 拆分）。

从 app.py 拆出：指标 CRUD / AI 生成 / 评审修订 / 评分 / 口径核查 / 验收 / 指标树。
register(app, base, metric_svc, ai_svc) 由 create_app 装配。
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from fastapi import HTTPException, Query
from fastapi.responses import PlainTextResponse

from data_governance.acceptance.engine import run_acceptance
from data_governance.acceptance.report import render_markdown
from data_governance.acceptance.serialize import acceptance_report_to_dict
from data_governance.api.metric_services import (
    load_latest_metric_review,
    load_metric_review_for_metric,
    run_metric_review_for_id,
)
from data_governance.api.schemas import MetricCreateRequest, MetricUpdateRequest, RevisionApplyRequest, StatsResponse
from data_governance.config_loader import load_domains
from data_governance.io.catalog import load_catalog
from data_governance.io.metric_tree import load_metric_tree
from data_governance.scoring.store import load_score, score_and_persist
from data_governance.services import MetricService
from data_governance.services.ai_service import AiService


def register(app, base: Path, metric_svc: MetricService, ai_svc: AiService) -> None:
    """注册指标路由（闭包风格，与拆分前行为一致）。"""

    @app.get("/api/metrics")
    def list_metrics(domain: str | None = Query(default=None)) -> list[dict]:
        return metric_svc.list_metrics(domain)

    @app.post("/api/metrics/suggest")
    def metric_suggest(body: dict) -> dict:
        """AI 辅助生成指标定义（逻辑已下沉 AiService.suggest_metric）。"""
        return ai_svc.suggest_metric(body)

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
