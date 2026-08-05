from __future__ import annotations

import json
import re
from typing import Any

from data_governance.schemas.roots import RootType


class RootResponseParseError(ValueError):
    pass


_JSON_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    block = _JSON_BLOCK.search(text)
    if block:
        return block.group(1).strip()
    return text


def parse_root_generation_response(raw: str) -> list[dict[str, Any]]:
    text = _extract_json_text(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RootResponseParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise RootResponseParseError("expected JSON array")
    return data


def row_to_model_fields(row: dict[str, Any]) -> dict[str, Any]:
    try:
        root_type = RootType(str(row["root_type"]))
    except (KeyError, ValueError) as exc:
        raise RootResponseParseError("missing or invalid root_type") from exc
    for key in ("cn_term", "root_en", "root_abbr"):
        if key not in row or not str(row[key]).strip():
            raise RootResponseParseError(f"missing or empty {key}")
    return {
        "cn_term": str(row["cn_term"]).strip(),
        "root_en": str(row["root_en"]).strip(),
        "root_abbr": str(row["root_abbr"]).strip(),
        "root_type": root_type,
        "description": str(row.get("description") or "").strip(),
    }
