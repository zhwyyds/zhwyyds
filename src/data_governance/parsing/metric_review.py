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


def _coerce_str_list(value: Any) -> list[str]:
    """把模型返回的 issues/risks 字段规整为字符串数组。

    live 模型常把数组写成一句话（str）而非 JSON 数组，这里做容错：
    str → 按换行/分号/顿号拆成列表；list → 元素规整为 str。
    """
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):  # 形如 '["a","b"]' 的字符串
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except json.JSONDecodeError:
                pass
        parts = re.split(r"[\n;；、]", text)
        return [p.strip().lstrip("-•* ").strip() for p in parts if p.strip()]
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


def _coerce_bool(value: Any) -> bool:
    """把模型返回的 root_match 规整为 bool（容错 '是/否/1/0/true/false'）。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in ("true", "yes", "y", "是", "对", "1", "ok", "通过")


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
        "naming_issues": _coerce_str_list(row.get("naming_issues")),
        "caliber_score": int(row["caliber_score"]),
        "caliber_issues": _coerce_str_list(row.get("caliber_issues")),
        "conflict_risks": _coerce_str_list(row.get("conflict_risks")),
        "root_match": _coerce_bool(row["root_match"]),
        "suggestions": str(row.get("suggestions") or "").strip(),
    }
