from __future__ import annotations

import json
import re
from typing import Any

_JSON_BLOCK = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class MetricResponseParseError(ValueError):
    pass


def _extract_json_text(raw: str) -> str:
    text = raw.strip()
    block = _JSON_BLOCK.search(text)
    if block:
        return block.group(1).strip()
    return text


def parse_metric_review_response(raw: str) -> list[dict[str, Any]]:
    text = _extract_json_text(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MetricResponseParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise MetricResponseParseError("expected JSON array")
    return data


def row_to_metric_review_fields(row: dict[str, Any]) -> dict[str, Any]:
    if "metric_id" not in row or not str(row["metric_id"]).strip():
        raise MetricResponseParseError("missing metric_id")
    for score_key in ("naming_score", "caliber_score"):
        if score_key not in row:
            raise MetricResponseParseError(f"missing {score_key}")
        try:
            score = int(row[score_key])
        except (TypeError, ValueError) as exc:
            raise MetricResponseParseError(f"invalid {score_key}") from exc
        if score < 1 or score > 5:
            raise MetricResponseParseError(f"{score_key} out of range 1-5")
    if "root_match" not in row:
        raise MetricResponseParseError("missing root_match")
    return {
        "metric_id": str(row["metric_id"]).strip(),
        "naming_score": int(row["naming_score"]),
        "naming_issues": row.get("naming_issues") or [],
        "caliber_score": int(row["caliber_score"]),
        "caliber_issues": row.get("caliber_issues") or [],
        "conflict_risks": row.get("conflict_risks") or [],
        "root_match": bool(row["root_match"]),
        "suggestions": str(row.get("suggestions") or "").strip(),
    }
