"""模型配置读写 — config/models.csv（问题 13：模型管理）。

支持 load / append / update / delete，带文件锁。
"""

from __future__ import annotations

import csv
from pathlib import Path

FIELDS = (
    "model_id",
    "model_name",
    "provider",
    "use_case",
    "priority",
    "enabled",
    "api_endpoint",
    "api_key_env",
    "remark",
)


def _lock(path: Path):
    import fcntl
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with lock_path.open("w") as fd:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)

    return _ctx


def load_models_file(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{k: (row.get(k) or "").strip() for k in FIELDS} for row in csv.DictReader(f)]


def _save(path: Path, rows: list[dict]) -> None:
    with _lock(path)(), path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: str(r.get(k) or "") for k in FIELDS})


def append_model(path: Path, payload: dict) -> dict:
    rows = load_models_file(path)
    model_id = str(payload.get("model_id") or "").strip()
    if model_id and any(r.get("model_id") == model_id for r in rows):
        raise ValueError(f"model_id already exists: {model_id}")
    if not model_id:
        seq = 1
        existing = {int(r["model_id"]) for r in rows if r.get("model_id", "").isdigit()}
        while seq in existing:
            seq += 1
        model_id = str(seq)
    row = {k: str(payload.get(k) or "").strip() for k in FIELDS}
    row["model_id"] = model_id
    row.setdefault("enabled", "true")
    rows.append(row)
    _save(path, rows)
    return row


def update_model(path: Path, model_id: str, payload: dict) -> dict | None:
    rows = load_models_file(path)
    target = None
    for r in rows:
        if r.get("model_id") == model_id:
            for k in FIELDS:
                if k in payload and payload[k] is not None:
                    r[k] = str(payload[k]).strip()
            target = r
            break
    if target is None:
        return None
    _save(path, rows)
    return target


def delete_model(path: Path, model_id: str) -> bool:
    rows = load_models_file(path)
    kept = [r for r in rows if r.get("model_id") != model_id]
    if len(kept) == len(rows):
        return False
    _save(path, kept)
    return True
