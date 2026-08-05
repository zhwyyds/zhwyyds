"""血缘数据落盘 — lineage/{domain}_lineage.json（IT2-3）。"""

from __future__ import annotations

import json
from pathlib import Path


def lineage_path(base_dir: Path, domain: str) -> Path:
    return base_dir / "lineage" / f"{domain.lower()}_lineage.json"


def save_lineage(base_dir: Path, domain: str, data: dict) -> Path:
    """写入血缘 JSON（含文件锁），返回写入路径。"""
    path = lineage_path(base_dir, domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    import fcntl

    with lock_path.open("w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    return path
