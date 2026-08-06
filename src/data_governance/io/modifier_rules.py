"""修饰词库读写 — config/modifier_rules.csv（问题 11：修饰词管理）。

支持 load / append / update / delete，带文件锁防并发。
"""

from __future__ import annotations

import csv
from pathlib import Path

from data_governance.io.file_lock import file_lock

FIELDS = (
    "modifier_id",
    "modifier_cn",
    "modifier_en",
    "modifier_abbr",
    "modifier_type",
    "time_scope",
    "description",
    "example_metric",
    "sort_order",
)


def load_modifiers_file(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{k: (row.get(k) or "").strip() for k in FIELDS} for row in csv.DictReader(f)]


def _save(path: Path, rows: list[dict]) -> None:
    with file_lock(path), path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: str(r.get(k) or "") for k in FIELDS})


def append_modifier(path: Path, payload: dict) -> dict:
    rows = load_modifiers_file(path)
    mid = str(payload.get("modifier_id") or "").strip()
    if not mid:
        # 自动分配：T 系列 + 序号
        seq = 1
        existing = {r.get("modifier_id") for r in rows}
        while f"T{seq:03d}" in existing:
            seq += 1
        mid = f"T{seq:03d}"
    if any(r.get("modifier_id") == mid for r in rows):
        raise ValueError(f"modifier_id already exists: {mid}")
    row = {k: str(payload.get(k) or "").strip() for k in FIELDS}
    row["modifier_id"] = mid
    rows.append(row)
    _save(path, rows)
    return row


def update_modifier(path: Path, modifier_id: str, payload: dict) -> dict | None:
    rows = load_modifiers_file(path)
    target = None
    for r in rows:
        if r.get("modifier_id") == modifier_id:
            for k in FIELDS:
                if k in payload and payload[k] is not None:
                    r[k] = str(payload[k]).strip()
            target = r
            break
    if target is None:
        return None
    _save(path, rows)
    return target


def delete_modifier(path: Path, modifier_id: str) -> bool:
    rows = load_modifiers_file(path)
    kept = [r for r in rows if r.get("modifier_id") != modifier_id]
    if len(kept) == len(rows):
        return False
    _save(path, kept)
    return True
