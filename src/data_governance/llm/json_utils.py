from __future__ import annotations

import json
import re


def extract_json_payload(text: str) -> str:
    """Strip markdown fences and surrounding prose; return JSON array/object substring."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty model response")
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    start_arr = raw.find("[")
    start_obj = raw.find("{")
    if start_arr >= 0 and (start_obj < 0 or start_arr < start_obj):
        end = raw.rfind("]")
        if end > start_arr:
            return raw[start_arr : end + 1]
    if start_obj >= 0:
        end = raw.rfind("}")
        if end > start_obj:
            return raw[start_obj : end + 1]
    return raw


def parse_json_array(text: str) -> list:
    payload = extract_json_payload(text)
    data = json.loads(payload)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise ValueError("expected JSON array from model")
