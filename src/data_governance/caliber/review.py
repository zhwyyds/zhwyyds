"""口径核查流 — pending/approved/edited/rejected 状态机（IT2-5）。

状态流转："" →(draft)→ pending →(approve)→ approved
                                   →(update)→ edited（视为 approved 等效）
                                   →(reject, 附 reason)→ rejected →(重 draft)→ pending
批准/修改后触发重新评分（口径变化影响评分）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from data_governance.caliber.draft import CALIBER_FIELDS
from data_governance.io.catalog import load_catalog
from data_governance.io.metrics_csv import upsert_metric

APPROVED_STATES = ("approved", "edited")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def pending_queue(base_dir: Path, domain: str | None = None) -> list[dict]:
    """待核查队列：status ∈ {pending, rejected}（含打回原因）。"""
    catalog = load_catalog(base_dir)
    out: list[dict] = []
    for m in catalog.metrics:
        if m.caliber_status not in ("pending", "rejected"):
            continue
        if domain and m.domain_code != domain:
            continue
        out.append(
            {
                "metric_id": m.metric_id,
                "metric_cn": m.metric_cn,
                "metric_en": m.metric_en,
                "domain_code": m.domain_code,
                "caliber_status": m.caliber_status,
                "caliber_reject_reason": m.caliber_reject_reason,
                "caliber_ai_by": m.caliber_ai_by,
                "caliber": {f: getattr(m, f) for f in CALIBER_FIELDS},
            }
        )
    return out


def _set_status(base_dir: Path, metric_id: str, status: str, extra: dict | None = None) -> None:
    payload = {
        "caliber_status": status,
        "caliber_checked_by": (extra or {}).get("checked_by", "system"),
        "caliber_checked_at": _now_iso(),
    }
    payload.update({k: v for k, v in (extra or {}).items() if k not in ("checked_by",)})
    upsert_metric(base_dir, metric_id, payload)


def approve_caliber(base_dir: Path, metric_id: str, *, checked_by: str = "system") -> dict:
    """批准草稿：status=approved + 触发重新评分。"""
    catalog = load_catalog(base_dir)
    m = next((x for x in catalog.metrics if x.metric_id == metric_id), None)
    if m is None:
        raise KeyError(metric_id)
    _set_status(base_dir, metric_id, "approved", {"checked_by": checked_by})
    from data_governance.scoring.store import score_and_persist

    score_and_persist(base_dir, metric_id, trigger="caliber_approved")
    return {"metric_id": metric_id, "status": "approved", "checked_by": checked_by}


def reject_caliber(base_dir: Path, metric_id: str, reason: str, *, checked_by: str = "system") -> dict:
    """打回草稿：status=rejected + 记录原因。"""
    catalog = load_catalog(base_dir)
    m = next((x for x in catalog.metrics if x.metric_id == metric_id), None)
    if m is None:
        raise KeyError(metric_id)
    if not reason.strip():
        raise ValueError("reject reason 必填")
    _set_status(base_dir, metric_id, "rejected", {"checked_by": checked_by, "caliber_reject_reason": reason})
    return {"metric_id": metric_id, "status": "rejected", "reason": reason}


def update_caliber(base_dir: Path, metric_id: str, fields: dict, *, checked_by: str = "system") -> dict:
    """人工修改口径：仅允许 CALIBER_FIELDS 字段，改后 status=edited（视为 approved）并重评分。"""
    catalog = load_catalog(base_dir)
    m = next((x for x in catalog.metrics if x.metric_id == metric_id), None)
    if m is None:
        raise KeyError(metric_id)
    payload = {k: str(v).strip() for k, v in fields.items() if k in CALIBER_FIELDS and v is not None}
    if not payload:
        raise ValueError("无可更新的口径字段")
    payload["caliber_status"] = "edited"
    payload["caliber_checked_by"] = checked_by
    payload["caliber_checked_at"] = _now_iso()
    upsert_metric(base_dir, metric_id, payload)
    from data_governance.scoring.store import score_and_persist

    score_and_persist(base_dir, metric_id, trigger="caliber_edited")
    return {"metric_id": metric_id, "status": "edited", "updated": list(payload.keys())}
