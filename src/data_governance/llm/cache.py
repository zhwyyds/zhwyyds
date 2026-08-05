from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

DEFAULT_TTL_SEC = 7 * 24 * 3600


def _cache_dir(base_dir: Path) -> Path:
    return base_dir / ".cache" / "llm"


def _entry_path(base_dir: Path, model_name: str, prompt: str) -> Path:
    digest = hashlib.sha256(f"{model_name}\0{prompt}".encode()).hexdigest()
    return _cache_dir(base_dir) / f"{digest}.json"


def get_cached_response(
    base_dir: Path,
    model_name: str,
    prompt: str,
    *,
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> str | None:
    path = _entry_path(base_dir, model_name, prompt)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        created = float(data.get("created_at", 0))
        if time.time() - created > ttl_sec:
            return None
        text = data.get("text")
        return text if isinstance(text, str) else None
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None


def set_cached_response(base_dir: Path, model_name: str, prompt: str, text: str) -> None:
    path = _entry_path(base_dir, model_name, prompt)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"model": model_name, "created_at": time.time(), "text": text}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
