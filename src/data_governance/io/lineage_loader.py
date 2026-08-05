from __future__ import annotations

import json
from pathlib import Path


def load_domain_lineage(base_dir: Path, domain: str) -> dict | None:
    path = base_dir / "lineage" / f"{domain.lower()}_lineage.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_lineage_domains(base_dir: Path) -> list[str]:
    lineage_dir = base_dir / "lineage"
    if not lineage_dir.is_dir():
        return []
    out: list[str] = []
    for p in sorted(lineage_dir.glob("*_lineage.json")):
        name = p.stem.replace("_lineage", "")
        if name:
            out.append(name)
    return out
