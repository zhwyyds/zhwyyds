from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from data_governance.io.catalog import MetricRecord, load_catalog

METRIC_CSV_FIELDS = [
    "metric_id",
    "metric_cn",
    "metric_en",
    "domain_code",
    "root_ids",
    "metric_type",
    "data_type",
    "caliber_desc",
    "unit",
    "frequency",
    "owner",
    "source_model",
    "review_status",
    "category_l1",
    "category_l2",
    "value_type",
    "dimensions",
    "scenario",
    "reports",
    "formula",
    "analysis_methods",
    "alert_rules",
    "precision",
    "data_sources",
    "tech_caliber",
    "tree_node_id",
    "created_at",
    "updated_at",
    "formula_cn",
    "source_table",
    "version",
    "version_history",
    "offline_reason",
    "offline_note",
    "objection_status",
    "objection_note",
    # ── 口径助手结构化字段（口径字段标准与迁移方案.md，IT2-4） ──
    "caliber_business",
    "caliber_formula",
    "caliber_period",
    "caliber_granularity",
    "caliber_boundary",
    "caliber_source",
    "caliber_owner",
    "caliber_status",
    "caliber_ai_by",
    "caliber_checked_by",
    "caliber_checked_at",
    "caliber_reject_reason",
]

_METRIC_ID = re.compile(r"^M_([A-Z]+)_")


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """文件锁上下文管理器，防止多人并发写入丢失数据。"""
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def metrics_csv_path(metrics_dir: Path, domain: str) -> Path:
    return metrics_dir / f"{domain.lower()}_metrics.csv"


def infer_domain_from_metric_id(metric_id: str) -> str:
    m = _METRIC_ID.match(metric_id.strip())
    if not m:
        raise ValueError(f"invalid metric_id: {metric_id}")
    return m.group(1).lower()


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [{k: (row.get(k) or "").strip() for k in METRIC_CSV_FIELDS} for row in reader]


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with _file_lock(path), path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=METRIC_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in METRIC_CSV_FIELDS})


def find_metric_file(metrics_dir: Path, metric_id: str) -> Path | None:
    mid = metric_id.strip()
    for path in sorted(metrics_dir.glob("*_metrics.csv")):
        for row in _read_rows(path):
            if row.get("metric_id") == mid:
                return path
    return None


def row_to_record(row: dict[str, str]) -> MetricRecord:
    """委托给 MetricRecord.from_row，消除重复映射逻辑。"""
    return MetricRecord.from_row(row)


def record_to_row(rec: MetricRecord) -> dict[str, str]:
    return {k: str(rec.__dict__.get(k, "") or "") for k in METRIC_CSV_FIELDS}


def merge_payload(existing: dict[str, str], payload: dict) -> dict[str, str]:
    out = dict(existing)
    for key in METRIC_CSV_FIELDS:
        if key in payload and payload[key] is not None:
            out[key] = str(payload[key]).strip()
    out["updated_at"] = date.today().isoformat()
    if not out.get("created_at"):
        out["created_at"] = out["updated_at"]
    return out


def upsert_metric(base_dir: Path, metric_id: str, payload: dict) -> MetricRecord:
    metrics_dir = base_dir / "metrics"
    path = find_metric_file(metrics_dir, metric_id)
    if path is None:
        raise KeyError(metric_id)
    rows = _read_rows(path)
    found = False
    updated_row: dict[str, str] = {}
    for i, row in enumerate(rows):
        if row.get("metric_id") == metric_id:
            rows[i] = merge_payload(row, payload)
            updated_row = rows[i]
            found = True
            break
    if not found:
        raise KeyError(metric_id)
    _write_rows(path, rows)
    return row_to_record(updated_row)


def next_metric_id(existing_ids: list[str], domain: str) -> str:
    """为指定域生成下一个 M_{DOMAIN}_{seq} 指标 ID。"""
    domain_upper = domain.upper()
    prefix = f"M_{domain_upper}_"
    max_seq = 0
    for mid in existing_ids:
        if mid.startswith(prefix):
            tail = mid[len(prefix) :]
            if tail.isdigit():
                max_seq = max(max_seq, int(tail))
    return f"{prefix}{max_seq + 1:03d}"


def batch_create_metrics(base_dir: Path, payloads: list[dict]) -> tuple[list[MetricRecord], list[str]]:
    """批量创建指标：同一文件一次读、一次写（避免 N 次全量写盘）。

    返回 (created_records, skipped_ids)；metric_id 已存在则跳过。
    """
    metrics_dir = base_dir / "metrics"
    by_domain: dict[str, list[dict]] = {}
    for p in payloads:
        domain = str(p.get("domain_code") or "").strip().lower()
        if not domain:
            mid = str(p.get("metric_id") or "")
            domain = infer_domain_from_metric_id(mid) if mid else "base"
        by_domain.setdefault(domain, []).append(p)

    created: list[MetricRecord] = []
    skipped: list[str] = []
    today = date.today().isoformat()
    for domain, items in by_domain.items():
        path = metrics_csv_path(metrics_dir, domain)
        rows = _read_rows(path)
        existing_ids = {r.get("metric_id") for r in rows}
        new_rows: list[dict[str, str]] = []
        for p in items:
            mid = str(p.get("metric_id") or "").strip()
            if not mid:
                mid = next_metric_id(
                    [r.get("metric_id") or "" for r in rows] + [n["metric_id"] for n in new_rows],
                    domain,
                )
            if mid in existing_ids:
                skipped.append(mid)
                continue
            row = {k: "" for k in METRIC_CSV_FIELDS}
            row.update({k: str(v).strip() for k, v in p.items() if v is not None})
            row["metric_id"] = mid
            row["domain_code"] = domain
            row.setdefault("review_status", "pending")
            row.setdefault("source_model", "manual")
            row["created_at"] = today
            row["updated_at"] = today
            new_rows.append(row)
            existing_ids.add(mid)
        if new_rows:
            _write_rows(path, rows + new_rows)
            created.extend(row_to_record(r) for r in new_rows)
    return created, skipped


def create_metric(base_dir: Path, payload: dict) -> MetricRecord:
    metrics_dir = base_dir / "metrics"
    metric_id = str(payload.get("metric_id") or "").strip()
    domain = str(payload.get("domain_code") or "").strip().lower()
    if not metric_id:
        raise ValueError("metric_id required")
    if not domain:
        domain = infer_domain_from_metric_id(metric_id)
    path = metrics_csv_path(metrics_dir, domain)
    rows = _read_rows(path)
    if any(r.get("metric_id") == metric_id for r in rows):
        raise ValueError(f"metric_id already exists: {metric_id}")
    today = date.today().isoformat()
    row = {k: "" for k in METRIC_CSV_FIELDS}
    row.update({k: str(v).strip() for k, v in payload.items() if v is not None})
    row["metric_id"] = metric_id
    row["domain_code"] = domain
    row.setdefault("review_status", "pending")
    row.setdefault("source_model", "manual")
    row["created_at"] = today
    row["updated_at"] = today
    rows.append(row)
    _write_rows(path, rows)
    return row_to_record(row)


def metric_stats(metrics: list[MetricRecord]) -> dict[str, int]:
    pending = sum(1 for m in metrics if m.review_status not in ("approved", "offline"))
    approved = sum(1 for m in metrics if m.review_status == "approved")
    offline = sum(1 for m in metrics if m.review_status == "offline")
    return {
        "total": len(metrics),
        "pending_review": pending,
        "published": approved,
        "offline": offline,
    }


def export_metrics_csv(base_dir: Path) -> str:
    catalog = load_catalog(base_dir)
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=METRIC_CSV_FIELDS)
    writer.writeheader()
    for m in catalog.metrics:
        writer.writerow({k: record_to_row(m).get(k, "") for k in METRIC_CSV_FIELDS})
    return buf.getvalue()
