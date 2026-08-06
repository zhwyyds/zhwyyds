"""血缘数据落盘 — lineage/{domain}_lineage.json（IT2-3）。"""

from __future__ import annotations

import json
from pathlib import Path

from data_governance.io.file_lock import file_lock


def lineage_path(base_dir: Path, domain: str) -> Path:
    return base_dir / "lineage" / f"{domain.lower()}_lineage.json"


def save_lineage(base_dir: Path, domain: str, data: dict) -> Path:
    """写入血缘 JSON（含文件锁），返回写入路径。"""
    path = lineage_path(base_dir, domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return path
