from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

FENCE_RE = re.compile(r"(?P<prefix>```(?:json)?\s*\n)(?P<body>.*?)(?P<suffix>\n```)", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> tuple[str, str | None, str | None]:
    match = FENCE_RE.search(text)
    if not match:
        return text.strip(), None, None
    prefix = text[: match.start("body")]
    suffix = text[match.end("body") :]
    return match.group("body").strip(), prefix, suffix


def remove_url_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            key: remove_url_keys(value)
            for key, value in obj.items()
            if key != "url" and not key.endswith("_url")
        }
    if isinstance(obj, list):
        return [remove_url_keys(item) for item in obj]
    return obj


def compact_specs(specs: Any, mode: str) -> Any:
    if mode == "keep" or not isinstance(specs, list):
        return specs
    parts: list[str] = []
    for item in specs:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            value = item.get("value")
            if value is None:
                continue
            value = str(value).strip()
            if not value:
                continue
            if mode == "named_join" and name:
                parts.append(f"{name}: {value}")
            else:
                parts.append(value)
        elif item is not None:
            value = str(item).strip()
            if value:
                parts.append(value)
    if mode in {"join", "named_join"}:
        return "; ".join(parts)
    return parts


def transform_products(obj: Any, specs_mode: str) -> Any:
    if isinstance(obj, dict):
        new_obj: dict[str, Any] = {}
        for key, value in obj.items():
            if key == "specs":
                new_obj[key] = compact_specs(value, specs_mode)
            else:
                new_obj[key] = transform_products(value, specs_mode)
        return new_obj
    if isinstance(obj, list):
        return [transform_products(item, specs_mode) for item in obj]
    return obj


def rename_product_keys(obj: Any, enabled: bool) -> Any:
    if not enabled:
        return obj
    key_map = {"name": "n", "price": "p", "code": "c", "specs": "s"}
    if isinstance(obj, dict):
        is_product = {"name", "price", "code"}.issubset(obj.keys())
        result: dict[str, Any] = {}
        for key, value in obj.items():
            new_key = key_map.get(key, key) if is_product else key
            result[new_key] = rename_product_keys(value, enabled)
        return result
    if isinstance(obj, list):
        return [rename_product_keys(item, enabled) for item in obj]
    return obj


def dumps_json(obj: Any, pretty: bool) -> str:
    if pretty:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def compact_snapshot_file(
    input_path: Path,
    output_path: Path,
    *,
    specs_mode: str = "join",
    pretty: bool = False,
    short_keys: bool = False,
    raw_json: bool = False,
) -> dict[str, object]:
    text = input_path.read_text(encoding="utf-8")
    json_text, md_prefix, md_suffix = extract_json(text)
    data = json.loads(json_text)
    data = remove_url_keys(data)
    data = transform_products(data, specs_mode)
    data = rename_product_keys(data, short_keys)
    out_json = dumps_json(data, pretty=pretty)
    if md_prefix is not None and md_suffix is not None and not raw_json:
        output_text = md_prefix + out_json + md_suffix
    else:
        output_text = out_json + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output_text, encoding="utf-8")
    before = input_path.stat().st_size
    after = output_path.stat().st_size
    return {
        "input": str(input_path),
        "output": str(output_path),
        "before": before,
        "after": after,
        "saved": before - after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact DNS snapshot JSON/Markdown for local LLM input")
    parser.add_argument("input", type=Path, help="Input .md or .json file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output file")
    parser.add_argument(
        "--specs",
        choices=["join", "values", "named_join", "keep"],
        default="join",
        help="How to compact specs. Default: join",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    parser.add_argument("--short-keys", action="store_true", help="Rename product keys name/price/code/specs to n/p/c/s.")
    parser.add_argument("--raw-json", action="store_true", help="Write raw JSON even if input was Markdown.")
    args = parser.parse_args()
    result = compact_snapshot_file(
        args.input,
        args.output,
        specs_mode=args.specs,
        pretty=args.pretty,
        short_keys=args.short_keys,
        raw_json=args.raw_json,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
