from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .ai_orchestrator import (
    SHORTLIST_LIMIT,
    NormalizedSearchRequest,
    ProductAnalysisOrchestrator,
    build_analysis_payload,
    build_constraint_candidate_packets,
    build_normalize_query_messages,
    build_preselected_filters_and_coverage,
    build_shortlist_payload,
    build_comparison_summary,
    build_normalized_request_search_url,
    build_dns_url_from_section_filters,
    classify_query_params,
    deduplicate_filter_list,
    ensure_teacher_checked_analysis_answer,
    filter_selection_to_filters,
    normalized_search_request_from_text,
    normalized_request_payload,
    postprocess_products,
    problematic_constraint_packets,
    rank_products_for_request,
    shortlist_to_urls,
)
from .dns_search_parser import Product
from .project_paths import ARTIFACTS_DIR, ensure_runtime_directories


MANUAL_STAGE_ORDER = (
    "normalize",
    "category_resolve",
    "filters_map",
    "filters_select",
    "parser",
    "shortlist",
    "details",
    "final_analysis",
)
STAGE_LABELS = {
    "normalize": "Normalize",
    "category_resolve": "Category resolve",
    "filters_map": "Filters map",
    "filters_select": "Filters select",
    "parser": "Parser",
    "shortlist": "Shortlist",
    "details": "Details",
    "final_analysis": "Final analysis",
}
MANUAL_RESPONSE_END_MARKER = "END"


@dataclass
class ManualSessionState:
    question: str
    session_dir: Path
    history: list[dict[str, str]] = field(default_factory=list)
    normalized_request: NormalizedSearchRequest | None = None
    normalize_raw_answer: str = ""
    requested_url: str = ""
    section_url: str = ""
    filters_map: dict[str, object] = field(default_factory=dict)
    preselected_filters: list[dict[str, object]] = field(default_factory=list)
    coverage: list[dict[str, object]] = field(default_factory=list)
    candidate_packets: list[dict[str, object]] = field(default_factory=list)
    selected_filters: list[dict[str, object]] = field(default_factory=list)
    merged_filters: list[dict[str, object]] = field(default_factory=list)
    built_url: str = ""
    parsed_products: list[Product] = field(default_factory=list)
    processed_products: list[Product] = field(default_factory=list)
    resolved_url: str = ""
    stats: dict[str, int] = field(default_factory=dict)
    shortlist_raw_answer: str = ""
    shortlisted_products: list[Product] = field(default_factory=list)
    enriched_products: list[Product] = field(default_factory=list)
    comparison_summary: dict[str, object] = field(default_factory=dict)
    final_analysis_raw_answer: str = ""
    final_answer: str = ""


def build_manual_response_template(step_name: str) -> str:
    if step_name == "normalize":
        return (
            "Верни только один JSON-объект.\n"
            "Формат:\n"
            '{\n'
            '  "product_type": "",\n'
            '  "query": "",\n'
            '  "price_min": null,\n'
            '  "price_max": null,\n'
            '  "brand": "",\n'
            '  "ranking_policy": "",\n'
            '  "price_band_hint": "",\n'
            '  "constraints": [],\n'
            '  "soft_wishes": []\n'
            '}\n'
            "Пример:\n"
            '{\n'
            '  "product_type": "laptop",\n'
            '  "query": "ноутбук",\n'
            '  "price_min": 125000,\n'
            '  "price_max": 262500,\n'
            '  "brand": "",\n'
            '  "ranking_policy": "performance",\n'
            '  "price_band_hint": "top",\n'
            '  "constraints": [\n'
            '    {"key":"gpu","op":"==","value":"rtx 4080","unit":"","source_text":"RTX 4080"},\n'
            '    {"key":"ram","op":"==","value":32,"unit":"gb","source_text":"32 ГБ ОЗУ"},\n'
            '    {"key":"refresh_rate","op":"==","value":240,"unit":"hz","source_text":"240 Гц"}\n'
            '  ],\n'
            '  "soft_wishes": ["lightweight", "good_battery"]\n'
            '}'
        )
    if step_name == "filters_select":
        return (
            "Верни только JSON.\n"
            '{\n  "filters": [\n    {"id": "f[44]", "values": [{"id": "1qx"}]}\n  ]\n}'
        )
    if step_name == "shortlist":
        return (
            "Верни только JSON.\n"
            '{\n  "selected_urls": [\n    "https://www.dns-shop.ru/product/.../"\n  ]\n}'
        )
    if step_name == "final_analysis":
        return (
            "Верни только финальный текст.\n"
            "Структура:\n"
            "Лучший вариант\n<текст>\n\n"
            "Почему он подходит\n<текст>\n\n"
            "Что сильнее у альтернатив\n<текст>\n\n"
            "Компромиссы и проверки\n<текст>"
        )
    return "Для этого шага ручной ответ не нужен."


def build_manual_filters_payload(
    question: str,
    history: list[dict[str, str]],
    section_url: str,
    normalized_request: NormalizedSearchRequest,
    preselected_filters: list[dict[str, object]],
    coverage: list[dict[str, object]],
    candidate_packets: list[dict[str, object]],
) -> str:
    payload = {
        "task": "filters_patch",
        "question": question,
        "url": section_url,
        "request": normalized_request_payload(normalized_request),
        "history": history,
        "preselected_filters": preselected_filters,
        "coverage": coverage,
        "candidate_packets": problematic_constraint_packets(candidate_packets, coverage),
    }
    return json.dumps(payload, ensure_ascii=False)


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9а-яА-Я_-]+", "_", value.strip())
    return cleaned.strip("_")[:48] or "manual"


def build_session_dir(question: str) -> Path:
    ensure_runtime_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = ARTIFACTS_DIR / "manual_ai_sessions" / f"{stamp}_{sanitize_filename(question)}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def products_to_dicts(products: list[Product]) -> list[dict[str, object]]:
    return [asdict(product) for product in products]


def stage_prefix(step_name: str) -> str:
    return f"{MANUAL_STAGE_ORDER.index(step_name) + 1:02d}_{step_name}"


def save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def is_stage_completed(state: ManualSessionState, step_name: str) -> bool:
    return {
        "normalize": state.normalized_request is not None,
        "category_resolve": bool(state.section_url),
        "filters_map": bool(state.filters_map),
        "filters_select": bool(state.built_url),
        "parser": bool(state.resolved_url),
        "shortlist": bool(state.shortlisted_products),
        "details": bool(state.enriched_products),
        "final_analysis": bool(state.final_answer),
    }[step_name]


def current_stage_index(state: ManualSessionState) -> int:
    for index, step_name in enumerate(MANUAL_STAGE_ORDER):
        if not is_stage_completed(state, step_name):
            return index
    return len(MANUAL_STAGE_ORDER)


def available_stage_names(state: ManualSessionState) -> tuple[str, ...]:
    next_index = current_stage_index(state)
    limit = min(next_index + 1, len(MANUAL_STAGE_ORDER))
    return MANUAL_STAGE_ORDER[:limit]


def clear_state_from(state: ManualSessionState, step_name: str) -> None:
    stage_index = MANUAL_STAGE_ORDER.index(step_name)
    if stage_index <= 0:
        state.normalized_request = None
        state.normalize_raw_answer = ""
        state.requested_url = ""
    if stage_index <= 1:
        state.section_url = ""
    if stage_index <= 2:
        state.filters_map = {}
        state.preselected_filters = []
        state.coverage = []
        state.candidate_packets = []
    if stage_index <= 3:
        state.selected_filters = []
        state.merged_filters = []
        state.built_url = ""
    if stage_index <= 4:
        state.parsed_products = []
        state.processed_products = []
        state.resolved_url = ""
        state.stats = {}
    if stage_index <= 5:
        state.shortlist_raw_answer = ""
        state.shortlisted_products = []
    if stage_index <= 6:
        state.enriched_products = []
        state.comparison_summary = {}
    if stage_index <= 7:
        state.final_analysis_raw_answer = ""
        state.final_answer = ""


def read_multiline_response() -> str:
    print(f"Вставьте ответ. Завершение отдельной строкой {MANUAL_RESPONSE_END_MARKER}.")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == MANUAL_RESPONSE_END_MARKER:
            break
        lines.append(line)
    return "\n".join(lines).strip()


class ManualAiRunner:
    def __init__(self, question: str) -> None:
        self.state = ManualSessionState(question=question, session_dir=build_session_dir(question))
        self.orchestrator = ProductAnalysisOrchestrator(chat=self._unused_chat)

    async def _unused_chat(self, _messages: list[dict[str, str]]) -> str:
        return ""

    def run(self) -> int:
        save_text(self.state.session_dir / "question.txt", self.state.question)
        while True:
            if current_stage_index(self.state) >= len(MANUAL_STAGE_ORDER):
                self.print_final_summary()
                return 0
            try:
                step_name = self.select_stage()
            except ValueError as exc:
                print(f"[manual_ai] error={exc}")
                continue
            if step_name is None:
                return 0
            clear_state_from(self.state, step_name)
            self.run_stage(step_name)

    def select_stage(self) -> str | None:
        print()
        print(f"[manual_ai] session={self.state.session_dir}")
        print(f"[manual_ai] question={self.state.question}")
        available = available_stage_names(self.state)
        for index, step_name in enumerate(available, start=1):
            marker = "done" if is_stage_completed(self.state, step_name) else "next"
            print(f"{index}. {STAGE_LABELS[step_name]} [{marker}]")
        print("0. Exit")
        choice = input("Выберите шаг: ").strip()
        if choice == "0":
            return None
        if not choice.isdigit():
            raise ValueError("Нужен номер шага.")
        index = int(choice) - 1
        if index < 0 or index >= len(available):
            raise ValueError("Шаг вне диапазона.")
        return available[index]

    def run_stage(self, step_name: str) -> None:
        handlers = {
            "normalize": self.run_normalize,
            "category_resolve": self.run_category_resolve,
            "filters_map": self.run_filters_map,
            "filters_select": self.run_filters_select,
            "parser": self.run_parser,
            "shortlist": self.run_shortlist,
            "details": self.run_details,
            "final_analysis": self.run_final_analysis,
        }
        handlers[step_name]()

    def run_normalize(self) -> None:
        prefix = stage_prefix("normalize")
        messages = build_normalize_query_messages(self.state.question)
        save_json(self.state.session_dir / f"{prefix}_request.json", {"messages": messages})
        save_text(self.state.session_dir / f"{prefix}_response_template.txt", build_manual_response_template("normalize"))
        print(f"[normalize] request={self.state.session_dir / f'{prefix}_request.json'}")
        print(build_manual_response_template("normalize"))
        answer = read_multiline_response()
        self.state.normalize_raw_answer = answer
        self.state.normalized_request = normalized_search_request_from_text(answer, fallback=self.state.question)
        self.state.requested_url = build_normalized_request_search_url(self.state.normalized_request)
        save_text(self.state.session_dir / f"{prefix}_response.txt", answer)
        save_json(self.state.session_dir / f"{prefix}_parsed.json", normalized_request_payload(self.state.normalized_request))

    def run_category_resolve(self) -> None:
        prefix = stage_prefix("category_resolve")
        section_url = self.orchestrator.section_url_resolver(self.state.requested_url)
        self.state.section_url = section_url
        save_json(
            self.state.session_dir / f"{prefix}_result.json",
            {"requested_url": self.state.requested_url, "section_url": self.state.section_url},
        )
        print(f"[category_resolve] section_url={self.state.section_url}")

    def run_filters_map(self) -> None:
        prefix = stage_prefix("filters_map")
        self.state.filters_map = self.orchestrator.section_filters_inspector(self.state.section_url)
        self.state.preselected_filters, self.state.coverage = build_preselected_filters_and_coverage(
            self.state.normalized_request,
            self.state.filters_map,
        )
        self.state.candidate_packets = build_constraint_candidate_packets(
            self.state.normalized_request,
            self.state.filters_map,
        )
        save_json(self.state.session_dir / f"{prefix}_full_filters_map.json", self.state.filters_map)
        save_json(self.state.session_dir / f"{prefix}_preselected_filters.json", self.state.preselected_filters)
        save_json(self.state.session_dir / f"{prefix}_coverage.json", self.state.coverage)
        save_json(
            self.state.session_dir / f"{prefix}_candidate_packets.json",
            problematic_constraint_packets(self.state.candidate_packets, self.state.coverage),
        )
        print(f"[filters_map] filters={len(self.state.filters_map.get('filters', []))}")

    def run_filters_select(self) -> None:
        prefix = stage_prefix("filters_select")
        payload = build_manual_filters_payload(
            question=self.state.question,
            history=self.state.history,
            section_url=self.state.section_url,
            normalized_request=self.state.normalized_request,
            preselected_filters=self.state.preselected_filters,
            coverage=self.state.coverage,
            candidate_packets=self.state.candidate_packets,
        )
        save_text(self.state.session_dir / f"{prefix}_request.json", payload)
        save_text(self.state.session_dir / f"{prefix}_response_template.txt", build_manual_response_template("filters_select"))
        print(f"[filters_select] request={self.state.session_dir / f'{prefix}_request.json'}")
        print(build_manual_response_template("filters_select"))
        answer = read_multiline_response()
        self.state.selected_filters = filter_selection_to_filters(answer)
        self.state.merged_filters = deduplicate_filter_list(self.state.preselected_filters + self.state.selected_filters)
        self.state.built_url = build_dns_url_from_section_filters(self.state.section_url, self.state.merged_filters, self.state.filters_map)
        save_text(self.state.session_dir / f"{prefix}_response.txt", answer)
        save_json(self.state.session_dir / f"{prefix}_selected_filters.json", self.state.selected_filters)
        save_json(self.state.session_dir / f"{prefix}_merged_filters.json", self.state.merged_filters)
        save_text(self.state.session_dir / f"{prefix}_built_url.txt", self.state.built_url)

    def run_parser(self) -> None:
        prefix = stage_prefix("parser")
        products, _mode, _requested_url, resolved_url = self.orchestrator.parser(self.state.built_url, self.orchestrator.product_limit)
        query = classify_query_params(resolved_url)["known"].get("q", self.state.built_url)
        processed, stats = postprocess_products(products, query=query)
        self.state.parsed_products = products
        self.state.processed_products = processed
        self.state.resolved_url = resolved_url
        self.state.stats = stats
        save_json(
            self.state.session_dir / f"{prefix}_result.json",
            {
                "resolved_url": self.state.resolved_url,
                "stats": self.state.stats,
                "parsed_products": products_to_dicts(self.state.parsed_products),
                "processed_products": products_to_dicts(self.state.processed_products),
            },
        )
        print(f"[parser] products={len(self.state.processed_products)}")

    def run_shortlist(self) -> None:
        prefix = stage_prefix("shortlist")
        ranked_products = rank_products_for_request(self.state.processed_products, self.state.normalized_request)
        payload = build_shortlist_payload(
            question=self.state.question,
            resolved_url=self.state.resolved_url,
            normalized_request=self.state.normalized_request,
            products=ranked_products,
            history=self.state.history,
        )
        save_text(self.state.session_dir / f"{prefix}_request.json", payload)
        save_text(self.state.session_dir / f"{prefix}_response_template.txt", build_manual_response_template("shortlist"))
        print(f"[shortlist] request={self.state.session_dir / f'{prefix}_request.json'}")
        print(build_manual_response_template("shortlist"))
        answer = read_multiline_response()
        selected_urls = shortlist_to_urls(answer, ranked_products)
        shortlisted = [product for product in ranked_products if product.url in selected_urls][:SHORTLIST_LIMIT]
        self.state.shortlist_raw_answer = answer
        self.state.shortlisted_products = shortlisted or ranked_products[:SHORTLIST_LIMIT]
        save_text(self.state.session_dir / f"{prefix}_response.txt", answer)
        save_json(self.state.session_dir / f"{prefix}_selected_products.json", products_to_dicts(self.state.shortlisted_products))

    def run_details(self) -> None:
        prefix = stage_prefix("details")
        self.state.enriched_products = self.orchestrator.attach_characteristics(
            self.state.processed_products,
            self.state.shortlisted_products,
        )
        self.state.comparison_summary = build_comparison_summary(
            self.state.enriched_products,
            self.state.normalized_request,
            coverage=self.state.coverage,
        )
        save_json(
            self.state.session_dir / f"{prefix}_result.json",
            {
                "enriched_products": products_to_dicts(self.state.enriched_products),
                "comparison_summary": self.state.comparison_summary,
            },
        )
        print(f"[details] enriched={len(self.state.enriched_products)}")

    def run_final_analysis(self) -> None:
        prefix = stage_prefix("final_analysis")
        payload = build_analysis_payload(
            question=self.state.question,
            resolved_url=self.state.resolved_url,
            stats=self.state.stats,
            normalized_request=self.state.normalized_request,
            products=self.state.enriched_products,
            comparison_summary=self.state.comparison_summary,
        )
        save_text(self.state.session_dir / f"{prefix}_request.json", payload)
        save_text(self.state.session_dir / f"{prefix}_response_template.txt", build_manual_response_template("final_analysis"))
        print(f"[final_analysis] request={self.state.session_dir / f'{prefix}_request.json'}")
        print(build_manual_response_template("final_analysis"))
        answer = read_multiline_response()
        self.state.final_analysis_raw_answer = answer
        self.state.final_answer = ensure_teacher_checked_analysis_answer(
            answer.strip(),
            self.state.enriched_products,
            self.state.comparison_summary,
        )
        save_text(self.state.session_dir / f"{prefix}_response.txt", answer)
        save_text(self.state.session_dir / f"{prefix}_final_output.txt", self.state.final_answer)
        print(self.state.final_answer)

    def print_final_summary(self) -> None:
        final_output = self.state.session_dir / f"{stage_prefix('final_analysis')}_final_output.txt"
        print()
        print("[manual_ai] done")
        print(f"[manual_ai] session_dir={self.state.session_dir}")
        print(f"[manual_ai] final_output={final_output}")


def prompt_question() -> str:
    question = input("Введите запрос: ").strip()
    if not question:
        raise ValueError("Пустой запрос.")
    return question


def main() -> int:
    try:
        question = prompt_question()
    except ValueError as exc:
        print(f"[manual_ai] error={exc}")
        return 1
    runner = ManualAiRunner(question)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
