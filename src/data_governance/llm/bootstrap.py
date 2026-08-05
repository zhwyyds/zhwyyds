from __future__ import annotations

import json
import os
from pathlib import Path

from data_governance.paths import repo_root


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        if key not in os.environ or not (os.environ.get(key) or "").strip():
            os.environ[key] = value


def load_secrets_json(path: Path) -> bool:
    """Merge config/secrets.json into os.environ; never override existing vars."""
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    for key, value in data.items():
        if not isinstance(key, str) or key.startswith("_"):
            continue
        if not isinstance(value, str):
            continue
        secret = value.strip()
        if not secret:
            continue
        if key not in os.environ or not (os.environ.get(key) or "").strip():
            os.environ[key] = secret
    return True


def bootstrap_llm_env(base_dir: Path | None = None) -> dict[str, bool]:
    """Load `.env` and `config/secrets.json` under project root (once per process is enough)."""
    base = (base_dir or repo_root()).resolve()
    dotenv_ok = (base / ".env").is_file()
    _load_dotenv(base / ".env")
    secrets_path = base / "config" / "secrets.json"
    secrets_ok = load_secrets_json(secrets_path)
    return {"dotenv": dotenv_ok, "secrets_json": secrets_ok, "secrets_path": str(secrets_path)}
