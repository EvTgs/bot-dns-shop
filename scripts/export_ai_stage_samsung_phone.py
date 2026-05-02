from __future__ import annotations

import asyncio
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

from app.ai_orchestrator import (
    ProductAnalysisOrchestrator,
    build_analysis_messages,
    build_comparison_summary,
    build_constraint_candidate_packets,
    build_filter_selection_messages,
    build_no_products_analysis_answer,
    build_normalize_query_messages,
    build_preselected_filters_and_coverage,
    build_router_messages,
    build_shortlist_messages,
    coverage_requires_patch,
    ensure_teacher_checked_analysis_answer,
    filter_selection_to_filters,
    merge_selected_filters,
    normalized_search_request_from_text,
    normalize_price_pair,
    parse_intent_route,
    problematic_constraint_packets,
    rank_products_for_request,
    sanitize_selected_filters,
    shortlist_to_urls,
)
from app.deepseek_client import DeepSeekClient
from app.dns_search_parser import (
    Product,
    build_dns_url_from_section_filters,
    classify_query_params,
    collect_products_by_url,
    fetch_characteristics_for_urls,
    inspect_dns_section_filters,
    normalize_dns_url,
    postprocess_products,
)

QUESTION = os.getenv(
    "AI_STAGE_QUESTION",
    (
        "Найди смартфон с AMOLED-экраном от 120 Гц, памятью от 256 ГБ, "
        "оперативной памятью от 12 ГБ, поддержкой 5G, NFC, защитой не ниже IP68, "
        "быстрой зарядкой, хорошей камерой и хорошей автономностью, не старше 2024 года, "
        "бюджет до 80 000 рублей"
    ),
)
OUT_DIR = Path(os.getenv("AI_STAGE_OUT_DIR", str(PROJECT_ROOT / "backend" / "test" / "snapshots" / "ai_stage")))


def dump_md(path: Path, title: str, content: object) -> None:
    if isinstance(content, str):
        body = content
    else:
        body = json.dumps(serialize_for_json(content), ensure_ascii=False, indent=2)
    path.write_text(f"# {title}\n\n```text\n{body}\n```\n", encoding="utf-8")


def serialize_for_json(value: object) -> object:
    if is_dataclass(value):
        return {key: serialize_for_json(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): serialize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_for_json(item) for item in value]
    return value


def dump_stage(name: str, prompt_content: object, output_content: object) -> None:
    dump_md(
        OUT_DIR / f"{name}.md",
        name,
        {
            "technical_prompt_and_input": prompt_content,
            "output": output_content,
        },
    )


def brief(products: list[Product], limit: int = 10) -> list[dict[str, object]]:
    return [{"name": p.name, "price": p.price, "url": p.url, "code": p.code} for p in products[:limit]]


def product_payload(product: Product) -> dict[str, object]:
    return {
        "name": product.name,
        "price": product.price,
        "url": product.url,
        "code": product.code,
        "specs": product.specs or [],
    }


async def main() -> int:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    client = DeepSeekClient.from_env()
    try:
        router_messages = build_router_messages(QUESTION, [], None)
        router_raw = await client.chat(router_messages)
        router_parsed = parse_intent_route(router_raw, has_products=False)
        dump_stage("01_router", router_messages, {"raw": router_raw, "parsed": router_parsed.__dict__})

        normalize_messages = build_normalize_query_messages(QUESTION)
        normalize_raw = await client.chat(normalize_messages)
        normalized = normalized_search_request_from_text(normalize_raw, fallback=QUESTION)
        dump_stage("02_normalize", normalize_messages, {"raw": normalize_raw, "parsed": normalized.__dict__})

        orchestrator = ProductAnalysisOrchestrator(chat=client.chat, stream_chat=client.stream_chat)
        await asyncio.to_thread(
            orchestrator.prime_static_category_fast_path,
            tuple(item for item in (normalized.product_type,) if item and item != "unknown"),
        )
        section_url = orchestrator.build_static_category_section_url(normalized)
        source = "category_static"
        if not section_url:
            requested_url = normalize_dns_url(
                normalized.query,
                price=normalize_price_pair(normalized.price_min, normalized.price_max),
            )
            section_url = await asyncio.to_thread(
                ProductAnalysisOrchestrator.default_section_url_resolver,
                requested_url,
            )
            source = "category_resolve"
        dump_stage(
            "03_filters_map_fetch",
            {"query": normalized.query, "price_min": normalized.price_min, "price_max": normalized.price_max},
            {"source": source, "section_url": section_url},
        )

        filters_map = await asyncio.to_thread(inspect_dns_section_filters, section_url)
        candidate_packets = build_constraint_candidate_packets(normalized, filters_map)
        dump_stage(
            "04_candidate_packets",
            {"section_url": section_url},
            {
                "filters_count": len(filters_map.get("filters", [])),
                "candidate_packets": candidate_packets,
            },
        )

        preselected_filters, coverage = build_preselected_filters_and_coverage(normalized, filters_map)
        problematic_packets = problematic_constraint_packets(candidate_packets, coverage)
        dump_stage(
            "05_preselect_and_coverage",
            {"section_url": section_url, "normalized": normalized.__dict__},
            {
                "preselected_filters": preselected_filters,
                "coverage": coverage,
                "coverage_requires_patch": coverage_requires_patch(coverage),
                "candidate_packets": candidate_packets,
            },
        )
        if coverage_requires_patch(coverage):
            filters_messages = build_filter_selection_messages(
                QUESTION,
                [],
                section_url,
                normalized,
                preselected_filters,
                coverage,
                problematic_packets,
            )
            filters_raw = await client.chat(filters_messages)
            selected_filters = filter_selection_to_filters(filters_raw)
            filters_prompt = filters_messages
            filters_output = {
                "skipped": False,
                "raw": filters_raw,
                "preselected_filters": preselected_filters,
                "coverage": coverage,
                "candidate_packets": problematic_packets,
                "selected_filters": selected_filters,
            }
        else:
            selected_filters = []
            filters_prompt = "SKIPPED (preselected_hard_wishes_covered)"
            filters_output = {
                "skipped": True,
                "reason": "preselected_hard_wishes_covered",
                "preselected_filters": preselected_filters,
                "coverage": coverage,
                "candidate_packets": problematic_packets,
            }
        dump_stage("06_filters_patch", filters_prompt, filters_output)

        merged_filters = merge_selected_filters(preselected_filters, selected_filters)
        merged_filters = sanitize_selected_filters(merged_filters, normalized, preselected_filters)
        built_url = build_dns_url_from_section_filters(section_url, merged_filters, filters_map.get("filters", []))
        dump_stage(
            "07_built_url",
            {"section_url": section_url, "merged_filters": merged_filters},
            {"built_url": built_url},
        )

        products, mode, requested_url, resolved_url = await asyncio.to_thread(
            lambda: collect_products_by_url(built_url, limit=100, allow_browser=True)
        )
        dump_stage(
            "08_parser",
            {"url": built_url, "limit": 100},
            {
                "mode": mode,
                "requested_url": requested_url,
                "resolved_url": resolved_url,
                "products_count": len(products),
                "products_sample": brief(products, 20),
            },
        )

        query = classify_query_params(resolved_url)["known"].get("q", built_url)
        processed_products, stats = postprocess_products(products, query=query)
        if not processed_products:
            no_match_answer = build_no_products_analysis_answer(normalized, resolved_url)
            dump_stage("09_shortlist_ai", "SKIPPED (no products after parser)", {"selected_urls": [], "shortlist": []})
            dump_stage("10_details", "SKIPPED (no products after parser)", {"products": [], "comparison_summary": {}})
            dump_stage("11_final_ai", "SKIPPED (no products after parser/details)", {"final": no_match_answer})
            dump_md(
                OUT_DIR / "99_full_trace.md",
                "99 full trace",
                {
                    "question": QUESTION,
                    "router": router_parsed.__dict__,
                    "normalize": normalized.__dict__,
                    "section_url": section_url,
                    "filters_map": {"filters_count": len(filters_map.get("filters", []))},
                    "preselected_filters": preselected_filters,
                    "coverage": coverage,
                    "selected_filters": selected_filters,
                    "built_url": built_url,
                    "parser": {
                        "mode": mode,
                        "requested_url": requested_url,
                        "resolved_url": resolved_url,
                        "products_count": len(products),
                    },
                    "answer": no_match_answer,
                },
            )
            return 0

        ranked_products = rank_products_for_request(processed_products, normalized)
        shortlist_messages = build_shortlist_messages(QUESTION, [], ranked_products, resolved_url, normalized)
        shortlist_raw = await client.chat(shortlist_messages)
        shortlist_urls = shortlist_to_urls(shortlist_raw, ranked_products)
        shortlisted = [product for product in ranked_products if product.url in shortlist_urls][:5] or ranked_products[:5]
        dump_stage(
            "09_shortlist_ai",
            shortlist_messages,
            {"raw": shortlist_raw, "selected_urls": shortlist_urls, "shortlist": brief(shortlisted, 10)},
        )

        details = await asyncio.to_thread(fetch_characteristics_for_urls, [product.url for product in shortlisted], True)
        specs_by_url = {
            str(item.get("url", "")): item.get("specs", [])
            for item in details
            if isinstance(item, dict)
        }
        enriched = [
            Product(product.name, product.price, product.url, product.code, specs_by_url.get(product.url, product.specs or []))
            for product in shortlisted
        ]
        comparison_summary = build_comparison_summary(enriched, normalized)
        dump_stage(
            "10_details",
            {"urls": [product.url for product in shortlisted]},
            {
                "products": [product_payload(product) for product in enriched],
                "comparison_summary": comparison_summary,
            },
        )

        analysis_messages = build_analysis_messages(
            QUESTION,
            [],
            enriched,
            resolved_url,
            stats,
            normalized,
            comparison_summary,
        )
        analysis_raw = await client.chat(analysis_messages)
        analysis_final = ensure_teacher_checked_analysis_answer(
            analysis_raw.strip(),
            enriched,
            comparison_summary,
        )
        dump_stage("11_final_ai", analysis_messages, {"raw": analysis_raw, "final": analysis_final})
        dump_md(
            OUT_DIR / "99_full_trace.md",
            "99 full trace",
            {
                "question": QUESTION,
                "router": router_parsed.__dict__,
                "normalize": normalized.__dict__,
                "section_url": section_url,
                "filters_map": {"filters_count": len(filters_map.get("filters", []))},
                "preselected_filters": preselected_filters,
                "coverage": coverage,
                "selected_filters": merged_filters,
                "built_url": built_url,
                "parser": {
                    "mode": mode,
                    "requested_url": requested_url,
                    "resolved_url": resolved_url,
                    "products_count": len(products),
                },
                "shortlist": {
                    "selected_urls": shortlist_urls,
                    "shortlisted": brief(shortlisted, 10),
                },
                "comparison_summary": comparison_summary,
                "answer": analysis_final,
            },
        )
        return 0
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
