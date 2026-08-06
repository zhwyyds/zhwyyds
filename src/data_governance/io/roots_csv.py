from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path

from data_governance.io.file_lock import file_lock
from data_governance.schemas.roots import RootCsvRow, SourceModel

ROOT_CSV_HEADER = [
    "root_id",
    "root_cn",
    "root_en",
    "root_abbr",
    "domain_code",
    "root_type",
    "description",
    "synonyms",
    "source_model",
    "review_status",
    "created_at",
    "updated_at",
]

_ROOT_ID = re.compile(r"^R_([A-Z]+)_(\d+)$")


def roots_csv_path(roots_dir: Path, domain: str) -> Path:
    return roots_dir / f"{domain}_roots.csv"


def _next_root_id(existing_ids: list[str], domain: str) -> str:
    domain_upper = domain.upper()
    max_seq = 0
    prefix = f"R_{domain_upper}_"
    for rid in existing_ids:
        m = _ROOT_ID.match(rid)
        if m and m.group(1) == domain_upper:
            max_seq = max(max_seq, int(m.group(2)))
    return f"{prefix}{max_seq + 1:03d}"


def read_existing_root_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    ids: list[str] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = (row.get("root_id") or "").strip()
            if rid:
                ids.append(rid)
    return ids


def update_root_row(path: Path, root_id: str, payload: dict) -> dict | None:
    """按 root_id 更新词根字段（payload 内键需属于表头），返回更新后的行；未找到返回 None。"""
    with file_lock(path), path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        fieldnames = list(reader.fieldnames or ROOT_CSV_HEADER)
        # 兼容旧文件缺列：payload 中的新列（如 synonyms）自动追加表头并为已有行补空值
        for k in payload:
            if k not in fieldnames and k in ROOT_CSV_HEADER:
                fieldnames.append(k)
                for row in rows:
                    row.setdefault(k, "")

    target: dict | None = None
    for row in rows:
        if (row.get("root_id") or "").strip() == root_id:
            for k, v in payload.items():
                if k in fieldnames and v is not None:
                    row[k] = str(v).strip()
            row["updated_at"] = date.today().isoformat()
            target = row
            break
    if target is None:
        return None

    with file_lock(path), path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def append_root_row(path: Path, row: RootCsvRow) -> None:
    write_header = not path.is_file() or path.stat().st_size == 0
    with file_lock(path), path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ROOT_CSV_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "root_id": row.root_id,
                "root_cn": row.root_cn,
                "root_en": row.root_en,
                "root_abbr": row.root_abbr,
                "domain_code": row.domain_code,
                "root_type": row.root_type.value,
                "description": row.description,
                "synonyms": row.synonyms,
                "source_model": row.source_model.value,
                "review_status": row.review_status.value,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )


def make_root_csv_row(
    *,
    domain: str,
    root_cn: str,
    root_en: str,
    root_abbr: str,
    root_type,
    description: str,
    source_model: SourceModel,
    review_status,
    roots_dir: Path,
    on_date: date | None = None,
    synonyms: str = "",
) -> RootCsvRow:
    d = (on_date or date.today()).isoformat()
    csv_path = roots_csv_path(roots_dir, domain)
    root_id = _next_root_id(read_existing_root_ids(csv_path), domain)
    return RootCsvRow(
        root_id=root_id,
        root_cn=root_cn,
        root_en=root_en,
        root_abbr=root_abbr,
        domain_code=domain,
        root_type=root_type,
        description=description,
        synonyms=synonyms,
        source_model=source_model,
        review_status=review_status,
        created_at=d,
        updated_at=d,
    )
