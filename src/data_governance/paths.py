from __future__ import annotations

from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    """Locate repository root (directory containing config/domains.csv)."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "config" / "domains.csv").is_file():
            return candidate
    raise FileNotFoundError("Could not find repo root (config/domains.csv)")
