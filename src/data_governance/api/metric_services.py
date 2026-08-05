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
