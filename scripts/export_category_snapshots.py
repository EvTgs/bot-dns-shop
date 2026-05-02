from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC_DIR = PROJECT_ROOT / "backend" / "src"
if str(BACKEND_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC_DIR))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from app.ai_orchestrator import STATIC_CATEGORY_ID_BY_PRODUCT_TYPE
from app.dns_parser_url import normalize_dns_url
from app.dns_search_parser import collect_products_by_url, inspect_dns_section_filters

DEFAULT_EXPORT_DIR = PROJECT_ROOT / "backend" / "test" / "snapshots" / "ai_total"
CATEGORY_SOURCES: tuple[tuple[str, str], ...] = (
    ("smartphone", "смартфон"),
    ("tablet", "планшет"),
    ("laptop", "ноутбук"),
)


def serialize(value: object) -> object:
    if is_dataclass(value):
        return {key: serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    return value


def write_md(path: Path, title: str, payload: object) -> None:
    body = json.dumps(serialize(payload), ensure_ascii=False, indent=2)
    path.write_text(f"# {title}\n\n```json\n{body}\n```\n", encoding="utf-8")


def category_section_url(product_type: str, query: str) -> str:
    category_id = STATIC_CATEGORY_ID_BY_PRODUCT_TYPE.get(product_type, "")
    if not category_id:
        raise RuntimeError(f"Missing static category id for {product_type}.")
    return normalize_dns_url(query, category=category_id)


def export_category_snapshots(out_dir: Path, categories: list[str] | None = None) -> dict[str, object]:
    selected = categories or [name for name, _query in CATEGORY_SOURCES]
    out_dir.mkdir(parents=True, exist_ok=True)
    for child in list(out_dir.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    exported: list[dict[str, object]] = []
    for product_type, query in CATEGORY_SOURCES:
        if product_type not in selected:
            continue
        section_url = category_section_url(product_type, query)
        filters_map = inspect_dns_section_filters(section_url)
        products, mode, requested_url, resolved_url = collect_products_by_url(
            section_url,
            limit=None,
            allow_browser=True,
        )
        filters_path = out_dir / f"01_{product_type}_filters.md"
        devices_path = out_dir / f"01_{product_type}_devices.md"
        write_md(
            filters_path,
            f"{product_type} filters",
            {
                "product_type": product_type,
                "query": query,
                "section_url": section_url,
                "filters_count": len(filters_map.get("filters", [])),
                "filters_map": filters_map,
            },
        )
        write_md(
            devices_path,
            f"{product_type} devices",
            {
                "product_type": product_type,
                "query": query,
                "section_url": section_url,
                "requested_url": requested_url,
                "resolved_url": resolved_url,
                "mode": mode,
                "products_count": len(products),
                "products": products,
            },
        )
        exported.append(
            {
                "product_type": product_type,
                "query": query,
                "filters_file": str(filters_path),
                "devices_file": str(devices_path),
                "products_count": len(products),
                "filters_count": len(filters_map.get("filters", [])),
            }
        )
    return {"out_dir": str(out_dir), "categories": selected, "files_written": len(exported) * 2, "exports": exported}


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")
    out_dir = Path(os.getenv("CATEGORY_EXPORT_OUT_DIR", str(DEFAULT_EXPORT_DIR)))
    result = export_category_snapshots(out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
