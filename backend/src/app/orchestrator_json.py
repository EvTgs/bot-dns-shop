from __future__ import annotations

import json


def extract_json_object(value: str) -> str:
    start = value.find("{")
    end = value.rfind("}")
    if start == -1 or end == -1 or end < start:
        return value
    return value[start : end + 1]


def parse_llm_json_payload(value: str) -> dict[str, object] | None:
    try:
        payload = json.loads(extract_json_object(value))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def should_retry_router_response(raw_value: str) -> bool:
    lowered = raw_value.casefold()
    repeated_noise = lowered.count("response_style") >= 8
    return len(raw_value) > 500 and repeated_noise
