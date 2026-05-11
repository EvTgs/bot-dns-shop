from __future__ import annotations

import asyncio
import json
import shutil
import sys
from datetime import datetime
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
    build_filter_selection_messages,
    build_normalize_query_messages,
    build_normalized_search_request_from_fallback,
    build_preselected_filters_and_coverage,
    build_constraint_candidate_packets,
    build_router_messages,
    build_shortlist_messages,
    coverage_requires_patch,
    ensure_request_price_filter,
    ensure_complete_analysis_answer,
    filter_selection_to_filters,
    merge_selected_filters,
    normalized_search_request_from_text,
    normalize_price_pair,
    parse_intent_route,
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

QUESTION = "Найди хороший монитор для программиста 27 дюймов, 1440p, IPS, с регулировкой высоты, до 35000 рублей"
TRACE_DIR = PROJECT_ROOT / "backend" / "test" / "artifacts" / "dns_traces" / "monitor_27_1440p_height_35k"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stage_payload(stage: str, payload: dict[str, object], valid: bool = True, reason: str | None = None) -> dict[str, object]:
    return {"stage": stage, "valid": valid, "reason": reason, **payload}


def products_brief(products: list[Product], limit: int = 5) -> list[dict[str, object]]:
    return [
        {"name": product.name, "price": product.price, "url": product.url, "code": product.code}
        for product in products[:limit]
    ]


def product_to_payload(product: Product) -> dict[str, object]:
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
    if TRACE_DIR.exists():
        shutil.rmtree(TRACE_DIR)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    client = DeepSeekClient.from_env()
    stages: list[dict[str, object]] = []
    try:
        request_stage = stage_payload("request", {"question": QUESTION})
        write_json(TRACE_DIR / "00_request.json", request_stage)
        stages.append(request_stage)

        router_messages = build_router_messages(QUESTION, [], None)
        router_answer = await client.chat(router_messages)
        route = parse_intent_route(router_answer, has_products=False)
        router_stage = stage_payload(
            "router",
            {"ai_input": {"messages": router_messages}, "ai_output_raw": router_answer, "parsed": route.__dict__},
            valid=route.mode == "product_search",
            reason=None if route.mode == "product_search" else "router did not select product_search",
        )
        write_json(TRACE_DIR / "01_router.json", router_stage)
        stages.append(router_stage)

        normalize_messages = build_normalize_query_messages(QUESTION)
        normalize_answer = await client.chat(normalize_messages)
        normalized_request = normalized_search_request_from_text(normalize_answer, fallback=QUESTION)
        normalize_stage = stage_payload(
            "normalize",
            {"ai_input": {"messages": normalize_messages}, "ai_output_raw": normalize_answer, "parsed": normalized_request.__dict__},
            valid=normalized_request.query == "монитор" and normalized_request.price_max is not None,
            reason=None if normalized_request.query == "монитор" else "normalize query is not monitor",
        )
        write_json(TRACE_DIR / "02_normalize.json", normalize_stage)
        stages.append(normalize_stage)

        orchestrator = ProductAnalysisOrchestrator(chat=client.chat, stream_chat=client.stream_chat)
        await asyncio.to_thread(orchestrator.prime_static_category_fast_path, ("monitor",))
        local_hint = build_normalized_search_request_from_fallback(QUESTION)
        section_url = orchestrator.build_static_category_section_url(normalized_request) or orchestrator.build_static_category_section_url(local_hint)
        source = "category_static"
        if not section_url:
            requested_url = normalize_dns_url(normalized_request.query, price=normalize_price_pair(normalized_request.price_min, normalized_request.price_max))
            section_url = await asyncio.to_thread(ProductAnalysisOrchestrator.default_section_url_resolver, requested_url)
            source = "category_resolve"
        category_stage = stage_payload(
            "category_resolve",
            {"source": source, "section_url": section_url},
            valid="category=" in section_url,
            reason=None if "category=" in section_url else "section_url has no category",
        )
        write_json(TRACE_DIR / "03_category_resolve.json", category_stage)
        stages.append(category_stage)

        filters_map = await asyncio.to_thread(inspect_dns_section_filters, section_url)
        filters_stage = stage_payload(
            "filters_map",
            {"requested": {"section_url": section_url}, "received": filters_map},
            valid=bool(filters_map.get("filters")),
            reason=None if filters_map.get("filters") else "empty filters_map",
        )
        write_json(TRACE_DIR / "04_filters_map.json", filters_stage)
        stages.append(filters_stage)

        preselected_filters, coverage = build_preselected_filters_and_coverage(normalized_request, filters_map)
        candidate_packets = build_constraint_candidate_packets(normalized_request, filters_map)
        if not coverage_requires_patch(coverage):
            selected_filters = []
            filters_ai_stage = stage_payload(
                "filters_ai",
                {
                    "skipped": True,
                    "reason_detail": "preselected_hard_wishes_covered",
                    "preselected_filters": preselected_filters,
                    "coverage": coverage,
                    "candidate_packets": candidate_packets,
                },
            )
        else:
            filter_messages = build_filter_selection_messages(
                QUESTION,
                [],
                section_url,
                normalized_request,
                preselected_filters,
                coverage,
                candidate_packets,
            )
            filter_answer = await client.chat(filter_messages)
            selected_filters = filter_selection_to_filters(filter_answer)
            filters_ai_stage = stage_payload(
                "filters_ai",
                {
                    "skipped": False,
                    "ai_input": {"messages": filter_messages},
                    "ai_output_raw": filter_answer,
                    "preselected_filters": preselected_filters,
                    "coverage": coverage,
                    "candidate_packets": candidate_packets,
                    "selected_filters": selected_filters,
                },
            )
        write_json(TRACE_DIR / "05_filters_ai.json", filters_ai_stage)
        stages.append(filters_ai_stage)

        selected_filters = merge_selected_filters(preselected_filters, selected_filters)
        selected_filters = sanitize_selected_filters(selected_filters, normalized_request, preselected_filters)
        selected_filters = ensure_request_price_filter(selected_filters, normalized_request)
        built_url = build_dns_url_from_section_filters(section_url, selected_filters, filters_map.get("filters", []))
        built_stage = stage_payload(
            "built_url",
            {"section_url": section_url, "selected_filters": selected_filters, "built_url": built_url},
            valid=all(token in built_url for token in ("fr%5B1q%5D", "f%5B1v%5D", "f%5B2v%5D", "f%5B9x%5D")),
            reason=None if all(token in built_url for token in ("fr%5B1q%5D", "f%5B1v%5D", "f%5B2v%5D", "f%5B9x%5D")) else "built_url lacks expected hard filters",
        )
        write_json(TRACE_DIR / "06_built_url.json", built_stage)
        stages.append(built_stage)

        products, mode, requested_url, resolved_url = await asyncio.to_thread(
            lambda: collect_products_by_url(built_url, limit=100, allow_browser=True)
        )
        parser_stage = stage_payload(
            "parser",
            {"mode": mode, "requested_url": requested_url, "resolved_url": resolved_url, "products_count": len(products), "sample": products_brief(products)},
            valid=bool(products),
            reason=None if products else "parser returned no products",
        )
        write_json(TRACE_DIR / "07_parser.json", parser_stage)
        stages.append(parser_stage)

        query = classify_query_params(resolved_url)["known"].get("q", built_url)
        processed, stats = postprocess_products(products, query=query)
        ranked = rank_products_for_request(processed, normalized_request)
        shortlist_messages = build_shortlist_messages(QUESTION, [], ranked, resolved_url, normalized_request)
        shortlist_answer = await client.chat(shortlist_messages)
        selected_urls = shortlist_to_urls(shortlist_answer, ranked)
        shortlisted = [product for product in ranked if product.url in selected_urls][:5] or ranked[:5]
        shortlist_stage = stage_payload(
            "shortlist",
            {"ai_input": {"messages": shortlist_messages}, "ai_output_raw": shortlist_answer, "ranked_candidates_sent": min(len(ranked), 20), "shortlist": products_brief(shortlisted, limit=5)},
            valid=bool(shortlisted) and len(json.loads(shortlist_messages[-1]["content"]).get("products", [])) <= 20,
            reason=None if shortlisted else "empty shortlist",
        )
        write_json(TRACE_DIR / "08_shortlist.json", shortlist_stage)
        stages.append(shortlist_stage)

        details = await asyncio.to_thread(fetch_characteristics_for_urls, [product.url for product in shortlisted], True)
        specs_by_url = {str(item.get("url", "")): item.get("specs", []) for item in details if isinstance(item, dict)}
        enriched = [
            Product(product.name, product.price, product.url, product.code, specs_by_url.get(product.url, product.specs or []))
            for product in shortlisted
        ]
        details_stage = stage_payload(
            "details",
            {"products": [product_to_payload(product) for product in enriched]},
            valid=all(product.specs for product in enriched),
            reason=None if all(product.specs for product in enriched) else "some products have no specs",
        )
        write_json(TRACE_DIR / "09_details.json", details_stage)
        stages.append(details_stage)

        comparison = build_comparison_summary(enriched, normalized_request)
        analysis_messages = build_analysis_messages(QUESTION, [], enriched, resolved_url, stats, normalized_request, comparison)
        raw_answer = await client.chat(analysis_messages)
        final_answer = ensure_complete_analysis_answer(raw_answer.strip(), enriched)
        banned = ("Гарантия продавца", "Страна-производитель", "Срок эксплуатации")
        analysis_stage = stage_payload(
            "analysis",
            {"ai_input": {"messages": analysis_messages}, "ai_output_raw": raw_answer, "final_answer": final_answer, "comparison": comparison},
            valid=all(token not in final_answer for token in banned) and "Лидер анализа" in final_answer,
            reason=None if all(token not in final_answer for token in banned) and "Лидер анализа" in final_answer else "analysis contains banned spec fields or lacks leader section",
        )
        write_json(TRACE_DIR / "10_analysis.json", analysis_stage)
        stages.append(analysis_stage)

        (TRACE_DIR / "99_full_request_and_answer.md").write_text(
            f"# Full Request\n\n{QUESTION}\n\n# Full Answer\n\n{final_answer}\n",
            encoding="utf-8",
        )
        files = sorted(path.name for path in TRACE_DIR.iterdir() if path.is_file() and path.name != "trace_index.json")
        failed_stage = next((stage for stage in stages if not stage.get("valid")), None)
        index_payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "question": QUESTION,
            "resolved_url": resolved_url,
            "built_url": built_url,
            "valid": failed_stage is None,
            "failed_stage": failed_stage.get("stage") if failed_stage else None,
            "failed_reason": failed_stage.get("reason") if failed_stage else None,
            "files": files,
            "stages": [{"stage": stage.get("stage"), "valid": stage.get("valid"), "reason": stage.get("reason")} for stage in stages],
        }
        write_json(TRACE_DIR / "trace_index.json", index_payload)
        print(json.dumps(index_payload, ensure_ascii=False, indent=2))
        return 0 if failed_stage is None else 1
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
