from __future__ import annotations

import re
from pathlib import Path

from data_governance.io.catalog import MetricRecord, load_catalog
from data_governance.io.metrics_csv import upsert_metric
from data_governance.pipeline.metric_review import MetricReviewPipeline
from data_governance.schemas.metrics import MetricInput, MetricReviewRequest


def _parse_root_ids(raw: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,]", raw or "") if p.strip()]


def metric_to_input(m: MetricRecord) -> MetricInput:
    return MetricInput(
        metric_id=m.metric_id,
        metric_cn=m.metric_cn,
        metric_en=m.metric_en,
        caliber_desc=m.caliber_desc,
        root_ids=_parse_root_ids(m.root_ids),
        unit=m.unit,
        frequency=m.frequency,
    )


def run_metric_review_for_id(base_dir: Path, metric_id: str) -> dict:
    catalog = load_catalog(base_dir)
    record = next((m for m in catalog.metrics if m.metric_id == metric_id), None)
    if record is None:
        raise KeyError(metric_id)
    request = MetricReviewRequest(domain=record.domain_code, metrics=[metric_to_input(record)])
    doc = MetricReviewPipeline(base_dir=base_dir, use_mock=None).run(request)
    item = doc.items[0] if doc.items else None
    if item and item.final_decision.approved:
        upsert_metric(
            base_dir,
            metric_id,
            {
                "review_status": item.final_decision.review_status,
                "source_model": "model_majority",
            },
        )
    return doc.model_dump(mode="json")


def load_metric_review_for_metric(base_dir: Path, metric_id: str) -> dict | None:
    reviews_dir = base_dir / "reviews" / "metric_reviews"
    if not reviews_dir.is_dir():
        return None
    import json

    mid = metric_id.strip()
    for path in sorted(reviews_dir.glob("*_metric_review_*.json"), reverse=True):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for item in doc.get("items") or []:
            if item.get("metric_id") == mid:
                return {
                    "review_type": "metric_review",
                    "review_id": doc.get("review_id"),
                    "domain": doc.get("domain"),
                    "created_at": doc.get("created_at"),
                    "models_used": doc.get("models_used"),
                    "source_file": path.name,
                    "item": item,
                }
    return None


def load_latest_metric_review(base_dir: Path, domain: str) -> dict | None:
    reviews_dir = base_dir / "reviews" / "metric_reviews"
    if not reviews_dir.is_dir():
        return None
    files = sorted(reviews_dir.glob(f"{domain.lower()}_metric_review_*.json"), reverse=True)
    if not files:
        return None
    import json

    data = json.loads(files[0].read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


REVISION_FIELDS = ("metric_cn", "metric_en", "caliber_desc", "unit", "frequency", "root_ids")


def merge_revision_suggestions(model_reviews: list[dict]) -> dict | None:
    """合并各模型的修订建议：每个字段取第一个非空值（live 单模型即其自身）。"""
    merged: dict = {}
    for mr in model_reviews:
        rev = mr.get("revision") or {}
        if not isinstance(rev, dict):
            continue
        for f in REVISION_FIELDS:
            v = rev.get(f)
            if v is not None and v != "" and v != [] and f not in merged:
                merged[f] = v
        if rev.get("summary") and "summary" not in merged:
            merged["summary"] = rev["summary"]
    return merged or None


def apply_metric_revision(
    base_dir: Path,
    metric_id: str,
    review_id: str,
    fields: list[str],
    *,
    checked_by: str = "system",
) -> dict:
    """把指定评审的 AI 修订建议（勾选字段）应用到指标定义。

    fields 为空列表表示应用全部建议字段。
    """
    import json as _json

    catalog = load_catalog(base_dir)
    record = next((m for m in catalog.metrics if m.metric_id == metric_id), None)
    if record is None:
        raise KeyError(metric_id)

    reviews_dir = base_dir / "reviews" / "metric_reviews"
    doc: dict | None = None
    for path in sorted(reviews_dir.glob("*_metric_review_*.json"), reverse=True):
        try:
            candidate = _json.loads(path.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError):
            continue
        if isinstance(candidate, dict) and candidate.get("review_id") == review_id:
            doc = candidate
            break
    if doc is None:
        raise ValueError(f"review not found: {review_id}")

    item = next((it for it in doc.get("items") or [] if it.get("metric_id") == metric_id), None)
    if item is None:
        raise ValueError(f"review {review_id} 无 {metric_id} 的评审条目")

    suggestions = merge_revision_suggestions(item.get("model_reviews") or [])
    if not suggestions:
        raise ValueError(f"review {review_id} 无 AI 修订建议")

    apply_keys = list(fields) if fields else [f for f in REVISION_FIELDS if f in suggestions]
    bad = [f for f in apply_keys if f not in REVISION_FIELDS]
    if bad:
        raise ValueError(f"不允许的修订字段: {bad}")
    if not apply_keys:
        raise ValueError("无可应用的修订字段")

    payload: dict = {}
    for f in apply_keys:
        if f in suggestions:
            payload[f] = suggestions[f]
    if not payload:
        raise ValueError("无可应用的修订字段")

    from data_governance.io.metrics_csv import upsert_metric

    upsert_metric(base_dir, metric_id, payload)
    return {
        "metric_id": metric_id,
        "review_id": review_id,
        "applied_fields": list(payload.keys()),
        "applied": {k: v for k, v in payload.items()},
        "checked_by": checked_by,
        "note": "建议重跑评分/评审以反映最新定义",
    }
