from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from data_governance.paths import repo_root


@dataclass(frozen=True)
class Domain:
    domain_code: str
    domain_name_cn: str
    domain_name_en: str
    description: str
    owner: str


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    model_name: str
    provider: str
    use_case: str
    priority: int
    enabled: bool
    api_endpoint: str
    api_key_env: str
    remark: str


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def load_domains(config_path: Path | None = None) -> list[Domain]:
    path = config_path or (repo_root() / "config" / "domains.csv")
    if not path.is_file():
        raise FileNotFoundError(f"domains config not found: {path}")
    rows: list[Domain] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"domain_code", "domain_name_cn", "domain_name_en", "description", "owner"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"domains.csv missing columns; need {sorted(required)}")
        for row in reader:
            code = (row.get("domain_code") or "").strip()
            if not code:
                continue
            rows.append(
                Domain(
                    domain_code=code,
                    domain_name_cn=(row.get("domain_name_cn") or "").strip(),
                    domain_name_en=(row.get("domain_name_en") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    owner=(row.get("owner") or "").strip(),
                )
            )
    if not rows:
        raise ValueError("domains.csv has no data rows")
    return rows


def load_models(
    use_case: str | None = None,
    *,
    config_path: Path | None = None,
    min_enabled: int = 1,
) -> list[ModelConfig]:
    path = config_path or (repo_root() / "config" / "models.csv")
    if not path.is_file():
        raise FileNotFoundError(f"models config not found: {path}")
    rows: list[ModelConfig] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {
            "model_id",
            "model_name",
            "provider",
            "use_case",
            "priority",
            "enabled",
            "api_endpoint",
            "remark",
        }
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"models.csv missing columns; need {sorted(required)}")
        for row in reader:
            uc = (row.get("use_case") or "").strip()
            if use_case and uc != use_case:
                continue
            enabled = _parse_bool(row.get("enabled") or "")
            if not enabled:
                continue
            try:
                priority = int((row.get("priority") or "0").strip())
            except ValueError as exc:
                raise ValueError(f"invalid priority for model {row.get('model_id')}") from exc
            rows.append(
                ModelConfig(
                    model_id=(row.get("model_id") or "").strip(),
                    model_name=(row.get("model_name") or "").strip(),
                    provider=(row.get("provider") or "").strip(),
                    use_case=uc,
                    priority=priority,
                    enabled=enabled,
                    api_endpoint=(row.get("api_endpoint") or "").strip(),
                    api_key_env=(row.get("api_key_env") or "").strip()
                    if reader.fieldnames and "api_key_env" in reader.fieldnames
                    else "",
                    remark=(row.get("remark") or "").strip(),
                )
            )
    rows.sort(key=lambda m: m.priority)
    if use_case and len(rows) < min_enabled:
        raise ValueError(f"need at least {min_enabled} enabled models for use_case={use_case!r}, got {len(rows)}")
    return rows
