import asyncio
import json
import logging
import time
from pathlib import Path

from app.orchestrator_finalization import extract_request_facts_for_entry
from app.ai_orchestrator import (
    analysis_product_payload,
    build_analysis_messages,
    build_constraint_candidate_packets,
    build_no_products_analysis_answer,
    build_comparison_summary,
    build_filter_selection_messages,
    build_preselected_filters,
    build_preselected_filters_and_coverage,
    constraints_from_payload,
    build_product_score_entry,
    enforce_chat_answer_constraints,
    extract_chat_format_constraints,
    build_teacher_corrected_analysis_answer,
    is_obvious_bot_meta_question,
    is_format_followup_for_chat,
    build_normalize_client,
    build_shortlist_messages,
    build_normalized_search_request_from_fallback,
    build_normalized_request_search_url,
    ProductAnalysisOrchestrator,
    ensure_teacher_checked_analysis_answer,
    extract_price_hint,
    extract_dns_url,
    ensure_complete_analysis_answer,
    NormalizedSearchRequest,
    parse_analysis_sections,
    extract_soft_wishes_from_text,
    rank_products_for_request,
    score_product_for_request,
    extract_hard_wishes_from_text,
    infer_product_type_and_query,
    normalized_search_request_from_text,
    select_shortlist_candidates,
    unresolved_request_wishes,
)
from app.dns_search_parser import Product, build_dns_url_from_section_filters


def test_extract_dns_url_finds_dns_search_url() -> None:
    text = "посмотри https://www.dns-shop.ru/search/?q=test&brand=abc"

    assert extract_dns_url(text) == "https://www.dns-shop.ru/search/?q=test&brand=abc"


def test_build_shortlist_messages_uses_json_payload() -> None:
    request = NormalizedSearchRequest(
        product_type="monitor",
        query="монитор",
        price_min=17500,
        price_max=36750,
        wishes=("ips", "1440p"),
        soft_wishes=("good_camera",),
    )
    messages = build_shortlist_messages(
        "Найди монитор",
        history=[],
        products=[Product("LG 27BA65QB-B", 31999, "https://example/lg", "1", specs=[{"name": "Тип матрицы", "value": "IPS"}])],
        resolved_url="https://dns.example/search",
        normalized_request=request,
    )

    assert messages[-1]["content"].startswith("{")
    assert '"task": "shortlist"' in messages[-1]["content"]
    assert '"products":' in messages[-1]["content"]
    assert "LG 27BA65QB-B" in messages[-1]["content"]
    assert "P1|" not in messages[-1]["content"]


def test_build_shortlist_messages_limits_payload_to_score_ranked_candidates() -> None:
    request = NormalizedSearchRequest(product_type="monitor", query="монитор", wishes=("ips",))
    products = [
        Product(f"Monitor {index}", 10000 + index, f"https://example/{index}", str(index), specs=[])
        for index in range(25)
    ]

    messages = build_shortlist_messages("Найди монитор IPS", [], products, "https://dns.example/search", request)
    payload = json.loads(messages[-1]["content"])

    assert len(payload["products"]) == 20


def test_shortlist_products_falls_back_when_no_hard_signals_and_llm_returns_no_match() -> None:
    asyncio.run(run_shortlist_products_falls_back_when_no_hard_signals_and_llm_returns_no_match())


async def run_shortlist_products_falls_back_when_no_hard_signals_and_llm_returns_no_match() -> None:
    products = [
        Product("Alpha 1", 10000, "https://example/a1", "1", specs=[]),
        Product("Alpha 2", 11000, "https://example/a2", "2", specs=[]),
        Product("Alpha 3", 12000, "https://example/a3", "3", specs=[]),
    ]
    request = NormalizedSearchRequest(product_type="smartphone", query="смартфон", soft_wishes=("good_camera",))

    async def fake_collect_complete_answer(messages, chat=None):
        return '{"selected_codes":[],"no_match":true,"reason":"нет подходящих товаров"}'

    orchestrator = ProductAnalysisOrchestrator(parser=lambda *_: ([], "", "", ""), chat=lambda *_: "", product_limit=10)
    orchestrator.collect_complete_answer = fake_collect_complete_answer  # type: ignore[method-assign]

    shortlisted = await orchestrator.shortlist_products("найти смартфон", [], products, "https://example/search", request)

    assert {product.url for product in shortlisted} == {product.url for product in products}
    assert orchestrator._last_shortlist_decision["no_match"] is False


def test_select_shortlist_candidates_covers_price_segments_without_budget() -> None:
    request = NormalizedSearchRequest(product_type="smartphone", query="смартфон", wishes=("matrix_type_amoled",))
    products = [
        Product(f"Budget {index}", 15000 + index, f"https://example/b{index}", f"b{index}", specs=[])
        for index in range(7)
    ] + [
        Product(f"Mid {index}", 35000 + index, f"https://example/m{index}", f"m{index}", specs=[])
        for index in range(7)
    ] + [
        Product(f"Premium {index}", 75000 + index, f"https://example/p{index}", f"p{index}", specs=[])
        for index in range(7)
    ]

    selected = select_shortlist_candidates(products, request, limit=9)
    selected_names = [product.name for product in selected]

    assert any(name.startswith("Budget") for name in selected_names)
    assert any(name.startswith("Mid") for name in selected_names)
    assert any(name.startswith("Premium") for name in selected_names)


def test_build_filter_selection_messages_uses_json_payload() -> None:
    request = NormalizedSearchRequest(
        product_type="monitor",
        query="монитор",
        price_min=17500,
        price_max=36750,
        wishes=("ips",),
        soft_wishes=("good_camera",),
    )
    messages = build_filter_selection_messages(
        question="Найди монитор IPS",
        history=[],
        section_url="https://dns.example/search?q=монитор&category=cat",
        normalized_request=request,
        preselected_filters=[{"id": "price", "name": "Цена", "min": 17500, "max": 36750}],
        coverage=[
            {"constraint_key": "matrix_type", "status": "uncovered", "confidence": 0.0, "reason": "need patch"},
        ],
        candidate_packets=[
            {
                "constraint": {"key": "matrix_type", "op": "==", "value": "ips", "unit": "", "source_text": "IPS"},
                "candidate_filters": [
                    {
                        "id": "f[2v]",
                        "name": "Тип матрицы",
                        "group": "Экран",
                        "type": "checkbox",
                        "values": [{"id": "1uq", "name": "IPS"}],
                        "total_values_count": 2,
                    }
                ],
            }
        ],
    )

    assert messages[-1]["content"].startswith("{")
    assert '"task": "filters_patch"' in messages[-1]["content"]
    assert '"preselected_filters":' in messages[-1]["content"]
    assert '"coverage":' in messages[-1]["content"]
    assert '"candidate_packets":' in messages[-1]["content"]
    assert '"Тип матрицы"' in messages[-1]["content"]
    assert "F1|" not in messages[-1]["content"]


def test_parse_analysis_sections_accepts_common_heading_variants() -> None:
    answer = (
        "**ЛИДЕР АНАЛИЗА:** LG 27BA65QB-B — лучший по эргономике.\n\n"
        "Альтернатива: ASUS ProArt — сильнее для цвета.\n\n"
        "**Критическое резюме**\nSamsung уступает по USB-C."
    )

    sections = parse_analysis_sections(answer)

    assert sections["Лидер анализа"].startswith("LG 27BA65QB-B")
    assert sections["Альтернатива"].startswith("ASUS ProArt")
    assert sections["Критическое резюме"].startswith("Samsung")
    assert sections["Лучший вариант"].startswith("LG 27BA65QB-B")
    assert sections["Что сильнее у альтернатив"].startswith("ASUS ProArt")
    assert sections["Компромиссы и проверки"].startswith("Samsung")


def test_ensure_complete_analysis_answer_keeps_non_empty_raw_answer_when_sections_are_unknown() -> None:
    raw_answer = "Модель LG лучше по USB-C и эргономике. ASUS альтернативен для цвета."
    products = [
        Product(
            "LG 27BA65QB-B",
            31999,
            "https://example/lg",
            "1",
            specs=[{"name": "Гарантия продавца / производителя", "value": "24 мес."}],
        )
    ]

    assert ensure_complete_analysis_answer(raw_answer, products) == raw_answer


def test_ensure_complete_analysis_answer_keeps_partial_raw_answer_without_specs_fallback() -> None:
    raw_answer = "Лидер анализа\nLG лучше по эргономике."
    products = [
        Product(
            "LG 27BA65QB-B",
            31999,
            "https://example/lg",
            "1",
            specs=[{"name": "Гарантия продавца / производителя", "value": "24 мес."}],
        )
    ]

    assert ensure_complete_analysis_answer(raw_answer, products) == raw_answer


def test_extract_chat_format_constraints_reads_explicit_user_requirements() -> None:
    constraints = extract_chat_format_constraints("Ответь короче, одним абзацем, без списка и в 2 предложениях.")

    assert constraints == {
        "no_list": True,
        "one_paragraph": True,
        "max_sentences": 2,
    }


def test_enforce_chat_answer_constraints_flattens_list_and_sentence_count() -> None:
    answer = "1. Первый пункт.\n2. Второй пункт.\n3. Третий пункт."
    constraints = {
        "no_list": True,
        "one_paragraph": True,
        "max_sentences": 2,
    }

    result = enforce_chat_answer_constraints(answer, constraints)

    assert result == "Первый пункт. Второй пункт."


def test_is_obvious_bot_meta_question_accepts_process_question_about_bot_behavior() -> None:
    assert is_obvious_bot_meta_question("Если я попрошу подобрать технику, что ты сделаешь по шагам?") is True


def test_is_format_followup_for_chat_detects_rephrase_request_without_memory_products() -> None:
    assert is_format_followup_for_chat(
        "Теперь ответь без шагов, только суть в 2 предложениях.",
        history=[
            {"role": "user", "content": "Если я попрошу подобрать технику, что ты сделаешь по шагам?"},
            {"role": "assistant", "content": "Сначала уточню задачу и бюджет, потом предложу варианты."},
        ],
        memory_context={},
    ) is True


def test_build_preselected_filters_uses_structured_monitor_matching() -> None:
    request = normalized_search_request_from_text(
        '[ {монитор}, {17500:36750}, {}, {"size":"27 inch","resolution":"1440p","panel":"ips","height_adjustment":"yes"}, {} ]',
        fallback="Найди монитор 27 дюймов, 1440p, IPS, с регулировкой высоты",
    )
    result = build_preselected_filters(
        request,
        {
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {
                    "id": "fr[1q]",
                    "name": "Диагональ экрана (дюйм)",
                    "type": "range-radio",
                    "values": [{"id": "small", "name": "23 - 25.99"}, {"id": "target", "name": "26 - 29.99"}],
                },
                {
                    "id": "f[1v]",
                    "name": "Максимальное разрешение",
                    "type": "checkbox",
                    "values": [{"id": "71", "name": "1920x1080"}, {"id": "76", "name": "2560x1440"}],
                },
                {
                    "id": "f[2v]",
                    "name": "Тип матрицы",
                    "type": "checkbox",
                    "values": [{"id": "1uq", "name": "IPS"}, {"id": "b2i", "name": "VA"}],
                },
                {
                    "id": "f[9x]",
                    "name": "Регулировка по высоте",
                    "type": "checkbox",
                    "values": [{"id": "21", "name": "есть"}, {"id": "22", "name": "нет"}],
                },
                {
                    "id": "f[2b]",
                    "name": "Максимальная частота обновления экрана (Гц)",
                    "type": "checkbox",
                    "values": [{"id": "19xc", "name": "270 Гц"}, {"id": "sp", "name": "144 Гц"}],
                },
            ]
        },
    )

    assert {item["id"] for item in result} == {"price", "fr[1q]", "f[1v]", "f[2v]", "f[9x]"}
    assert next(item for item in result if item["id"] == "price") == {"id": "price", "min": 17500, "max": 36750}
    assert next(item for item in result if item["id"] == "fr[1q]")["values"] == [{"id": "target", "name": "26 - 29.99"}]
    assert next(item for item in result if item["id"] == "f[1v]")["values"] == [{"id": "76", "name": "2560x1440"}]
    assert next(item for item in result if item["id"] == "f[2v]")["values"] == [{"id": "1uq", "name": "IPS"}]
    assert next(item for item in result if item["id"] == "f[9x]")["values"] == [{"id": "21", "name": "есть"}]


def test_build_normalized_search_request_from_fallback_keeps_value_prompt_signals() -> None:
    request = build_normalized_search_request_from_fallback(
        "найти самый мощьный смартфон по цена/качество, ценой от средней до 100к, лучше с хорошей камерой"
    )

    assert request.product_type == "smartphone"
    assert request.ranking_policy == "value"
    assert request.price_band_hint == "mid_to_max"
    assert request.price_max == 100000
    assert "good_camera" in request.soft_wishes
    assert "good_performance" in request.soft_wishes


def test_build_normalized_search_request_from_fallback_keeps_display_prompt_signals() -> None:
    request = build_normalized_search_request_from_fallback(
        "ноутбук с самым большим и ярким экраном"
    )

    assert request.product_type == "laptop"
    assert request.ranking_policy == "display"
    assert "bright_screen" in request.soft_wishes
    assert any(constraint.key == "screen_size" for constraint in request.constraints)


def test_normalized_search_request_from_text_recovers_missing_structured_product_type_from_prompt() -> None:
    request = normalized_search_request_from_text(
        '{"product_type":"","query":"самый большой и яркий экран","price_min":null,"price_max":null,"constraints":[],"soft_wishes":["bright_screen"],"ranking_policy":"display"}',
        fallback="ноутбук с самым большим и ярким экраном",
    )

    assert request.product_type == "laptop"
    assert request.query == "ноутбук"
    assert request.ranking_policy == "display"
    assert "bright_screen" in request.soft_wishes
    assert any(constraint.key == "screen_size" for constraint in request.constraints)


def test_build_teacher_corrected_analysis_answer_uses_screen_facts_for_display_request() -> None:
    products = [
        Product(
            '18" Ноутбук ASUS Vivobook 18 M1807HA-S8091 синий',
            94999,
            "https://example/asus18",
            "asus18",
            specs=[
                {"name": "Диагональ экрана", "value": '18"'},
                {"name": "Яркость", "value": "500 Кд/м²"},
                {"name": "Тип матрицы", "value": "IPS"},
                {"name": "Объем оперативной памяти", "value": "16 ГБ"},
            ],
        ),
        Product(
            '17.3" Ноутбук Acer Aspire Lite AL17-31P-C4FR серебристый',
            34499,
            "https://example/acer17",
            "acer17",
            specs=[
                {"name": "Диагональ экрана", "value": '17.3"'},
                {"name": "Яркость", "value": "300 Кд/м²"},
                {"name": "Тип матрицы", "value": "IPS"},
                {"name": "Объем оперативной памяти", "value": "16 ГБ"},
            ],
        ),
    ]
    comparison_summary = {
        "leader": {
            "name": products[0].name,
            "url": products[0].url,
            "code": products[0].code,
            "price": products[0].price,
            "match_status": "exact",
            "details_confirmed_all_hard_wishes": True,
            "brand_mismatch": False,
            "matched_hard_wishes": ["screen_size"],
            "missing_hard_wishes": [],
            "contradicted_hard_wishes": [],
        },
        "competitors": [
            {
                "name": products[1].name,
                "url": products[1].url,
                "code": products[1].code,
                "price": products[1].price,
                "match_status": "exact",
                "details_confirmed_all_hard_wishes": True,
                "brand_mismatch": False,
            }
        ],
        "request_profile": {
            "ranking_policy": "display",
            "price_band_hint": "",
            "soft_wishes": ["bright_screen"],
            "price_min": None,
            "price_max": None,
        },
    }

    answer = build_teacher_corrected_analysis_answer(products, comparison_summary)

    assert 'диагональ 18"' in answer
    assert "яркость 500 Кд/м²" in answer
    assert "ОЗУ" not in answer


def test_build_teacher_corrected_analysis_answer_prefers_camera_facts_for_value_request() -> None:
    product = Product(
        '6.7" Смартфон HUAWEI nova 15 512 ГБ черный',
        35799,
        "https://example/huawei-nova-15",
        "huawei-nova-15",
        specs=[
            {"name": "Тип оперативной памяти", "value": "-"},
            {"name": "Объем оперативной памяти", "value": "12 ГБ"},
            {"name": "Объем встроенной памяти", "value": "512 ГБ"},
            {"name": "Количество мегапикселей основной камеры", "value": "50+12+1.5 Мп"},
            {"name": "Яркость", "value": "5000 Кд/м²"},
            {"name": "Емкость аккумулятора", "value": "6000 мА*ч"},
        ],
    )
    comparison_summary = {
        "leader": {
            "name": product.name,
            "url": product.url,
            "code": product.code,
            "price": product.price,
            "match_status": "exact",
            "details_confirmed_all_hard_wishes": True,
            "brand_mismatch": False,
            "matched_hard_wishes": [],
            "missing_hard_wishes": [],
            "contradicted_hard_wishes": [],
        },
        "competitors": [],
        "request_profile": {
            "ranking_policy": "value",
            "price_band_hint": "mid_to_max",
            "soft_wishes": ["good_camera"],
            "price_min": None,
            "price_max": 100000,
        },
    }

    answer = build_teacher_corrected_analysis_answer([product], comparison_summary)

    assert "камера 50+12+1.5 Мп" in answer
    assert "ОЗУ -" not in answer


def test_build_teacher_corrected_analysis_answer_ignores_non_screen_specs_for_display_request() -> None:
    product = Product(
        '18" Ноутбук ASUS Vivobook 18 M1807HA-S8091 синий',
        94999,
        "https://example/asus18",
        "asus18",
        specs=[
            {"name": "Максимальное количество подключаемых мониторов", "value": "3 шт"},
            {"name": "Базовая частота производительных ядер", "value": "3.8 ГГц"},
            {"name": "Диагональ экрана", "value": '18"'},
            {"name": "Яркость", "value": "300 Кд/м²"},
            {"name": "Частота обновления экрана", "value": "144 Гц"},
        ],
    )
    comparison_summary = {
        "leader": {
            "name": product.name,
            "url": product.url,
            "code": product.code,
            "price": product.price,
            "match_status": "partial",
            "details_confirmed_all_hard_wishes": True,
            "brand_mismatch": False,
            "matched_hard_wishes": [],
            "missing_hard_wishes": [],
            "contradicted_hard_wishes": [],
        },
        "competitors": [],
        "request_profile": {
            "ranking_policy": "display",
            "price_band_hint": "",
            "soft_wishes": ["bright_screen"],
            "price_min": None,
            "price_max": None,
        },
    }

    answer = build_teacher_corrected_analysis_answer([product], comparison_summary)

    assert "яркость 300 Кд/м²" in answer
    assert 'диагональ 18"' in answer
    assert "подключаемых мониторов" not in answer
    assert "3.8 ГГц" not in answer


def test_build_preselected_filters_uses_structured_laptop_matching() -> None:
    request = normalized_search_request_from_text(
        '[ {ноутбук}, {125000:262500}, {}, {"gpu":"rtx 4080","ram":"32 gb","refresh_rate":"240 hz","weight_max":"2.5 kg","screen_finish":"matte","year":"2024"}, {} ]',
        fallback="Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, до 250 000 рублей, 2024 года выпуска",
    )

    result = build_preselected_filters(
        request,
        {
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "f[48j]", "name": "Год релиза", "type": "checkbox", "values": [{"id": "h9dq", "name": "2024"}]},
                {"id": "f[2b]", "name": "Максимальная частота обновления экрана (Гц)", "type": "checkbox", "values": [{"id": "b3o", "name": "240 Гц"}]},
                {"id": "f[2c]", "name": "Покрытие экрана", "type": "checkbox", "values": [{"id": "apl", "name": "антибликовое"}, {"id": "ss", "name": "матовое"}]},
                {"id": "f[44]", "name": "Объем оперативной памяти (ГБ)", "type": "checkbox", "values": [{"id": "1qx", "name": "32 ГБ"}]},
                {"id": "f[1go]", "name": "Модель дискретной видеокарты", "type": "checkbox", "values": [{"id": "eig9", "name": "GeForce RTX 4080 для ноутбуков"}]},
                {"id": "fr[8o]", "name": "Вес (кг)", "type": "range-radio", "values": [{"id": "c31d", "name": "2.091 - 2.49"}]},
            ]
        },
    )

    assert {item["id"] for item in result} == {"price", "f[48j]", "f[2b]", "f[2c]", "f[44]", "f[1go]", "fr[8o]"}
    assert next(item for item in result if item["id"] == "f[2c]")["values"] == [{"id": "ss", "name": "матовое"}]


def test_build_preselected_filters_supports_new_laptop_wish_aliases() -> None:
    request = normalized_search_request_from_text(
        '[ {ноутбук}, {125000:262500}, {}, {"gpu":"rtx 4080","ram":"32 gb","refresh_rate":"240 hz","weight_max":"2.5 kg","screen_finish":"matte","year":"2024"}, {} ]',
        fallback="Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, до 250 000 рублей, 2024 года выпуска",
    )

    result = build_preselected_filters(
        request,
        {
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "f[48j]", "name": "Год релиза", "type": "checkbox", "values": [{"id": "h9dq", "name": "2024"}]},
                {"id": "f[2b]", "name": "Максимальная частота обновления экрана (Гц)", "type": "checkbox", "values": [{"id": "b3o", "name": "240 Гц"}]},
                {"id": "f[2c]", "name": "Покрытие экрана", "type": "checkbox", "values": [{"id": "ss", "name": "матовое"}]},
                {"id": "f[44]", "name": "Объем оперативной памяти (ГБ)", "type": "checkbox", "values": [{"id": "1qx", "name": "32 ГБ"}]},
                {"id": "f[1go]", "name": "Модель дискретной видеокарты", "type": "checkbox", "values": [{"id": "eig9", "name": "GeForce RTX 4080 для ноутбуков"}]},
                {"id": "fr[8o]", "name": "Вес (кг)", "type": "range-radio", "values": [{"id": "c31d", "name": "2.091 - 2.49"}]},
            ]
        },
    )

    assert {item["id"] for item in result} == {"price", "f[48j]", "f[2b]", "f[2c]", "f[44]", "f[1go]", "fr[8o]"}


def test_unresolved_request_wishes_respects_preselected_filter_values() -> None:
    request = normalized_search_request_from_text(
        '[ {ноутбук}, {125000:262500}, {}, {"gpu":"rtx 4080","year":"2024"}, {} ]',
        fallback="Ноутбук RTX 4080 2024 года",
    )

    unresolved = unresolved_request_wishes(
        request,
        [
            {"id": "f[48j]", "name": "Год релиза", "values": [{"id": "h9dq", "name": "2024"}]},
            {"id": "f[1go]", "name": "Модель дискретной видеокарты", "values": [{"id": "eig9", "name": "GeForce RTX 4080 для ноутбуков"}]},
        ],
    )

    assert unresolved == ()


def test_build_product_score_entry_matches_laptop_specs_for_hard_wishes() -> None:
    request = normalized_search_request_from_text(
        '[ {ноутбук}, {125000:262500}, {}, {"gpu":"rtx 4080","ram":"32 gb","refresh_rate":"240 hz","weight_max":"2.5 kg","screen_finish":"matte","year":"2024"}, {} ]',
        fallback="Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, до 250 000 рублей, 2024 года выпуска",
    )
    product = Product(
        '17.3" Ноутбук ARDOR Gaming ELEMENT L17-I9ND400 черный',
        218999,
        "https://example/ardor",
        "1",
        specs=[
            {"name": "Год релиза", "value": "2024"},
            {"name": "Покрытие экрана", "value": "матовое"},
            {"name": "Максимальная частота обновления экрана", "value": "240 Гц"},
            {"name": "Объем оперативной памяти", "value": "32 ГБ"},
            {"name": "Модель дискретной видеокарты", "value": "GeForce RTX 4080 для ноутбуков"},
            {"name": "Вес", "value": "3.29 кг"},
        ],
    )

    entry = build_product_score_entry(product, request)

    assert set(entry["matched_hard_wishes"]) == {"rtx_4080", "32gb_ram", "240hz_screen", "matte_screen", "2024_year"}
    assert entry["contradicted_hard_wishes"] == ["weight_up_to_2.5_kg"]
    assert entry["missing_hard_wishes"] == []
    assert entry["match_status"] == "rejected"


def test_orchestrator_skips_filters_ai_when_preselect_covers_hard_wishes(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_skips_filters_ai_when_preselect_covers_hard_wishes(tmp_path))


async def run_orchestrator_skips_filters_ai_when_preselect_covers_hard_wishes(tmp_path: Path) -> None:
    calls = {"chat_payloads": []}

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        return ([Product("27 Monitor IPS", 10000, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "монитор",
            "category": "cat",
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "fr[1q]", "name": "Диагональ экрана (дюйм)", "type": "range-radio", "values": [{"id": "target", "name": "26 - 29.99"}]},
                {"id": "f[1v]", "name": "Максимальное разрешение", "type": "checkbox", "values": [{"id": "76", "name": "2560x1440"}]},
                {"id": "f[2v]", "name": "Тип матрицы", "type": "checkbox", "values": [{"id": "1uq", "name": "IPS"}]},
                {"id": "f[9x]", "name": "Регулировка по высоте", "type": "checkbox", "values": [{"id": "21", "name": "есть"}]},
            ],
        }

    async def chat(messages):
        content = messages[-1]["content"]
        calls["chat_payloads"].append(content)
        if "normalize_query" in content:
            return '[ {монитор}, {17500:36750}, {}, {"size":"27 inch","resolution":"1440p","panel":"ips","height_adjustment":"yes"}, {} ]'
        if "shortlist" in content:
            return json.dumps({"selected_urls": ["https://example/a"]}, ensure_ascii=False)
        if "analysis" in content:
            return "Лидер анализа\nLG\n\nАльтернатива\nНет\n\nКритическое резюме\nНет"
        return '{"mode":"product_search","response_style":"structured","reason":"new"}'

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        chat=chat,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=cat",
    )

    await orchestrator.handle_message(
        "Найди монитор 27 дюймов 1440p IPS с регулировкой высоты до 35000",
        history=[],
        on_text_chunk=lambda chunk: None,
    )

    assert not any('"task": "filters_patch"' in payload for payload in calls["chat_payloads"])
    assert "fr%5B1q%5D=target" in calls["input"]
    assert "f%5B1v%5D=76" in calls["input"]
    assert "f%5B2v%5D=1uq" in calls["input"]
    assert "f%5B9x%5D=21" in calls["input"]


def test_build_analysis_messages_uses_json_payload() -> None:
    request = NormalizedSearchRequest(
        product_type="monitor",
        query="монитор",
        price_min=17500,
        price_max=36750,
        wishes=("ips", "1440p"),
    )
    messages = build_analysis_messages(
        question="Найди монитор",
        history=[],
        products=[Product("LG 27BA65QB-B", 31999, "https://example/lg", "1", specs=[{"name": "Тип матрицы", "value": "IPS"}])],
        resolved_url="https://dns.example/search",
        stats={"total": 1},
        normalized_request=request,
        comparison_summary=build_comparison_summary([Product("LG 27BA65QB-B", 31999, "https://example/lg", "1", specs=[{"name": "Тип матрицы", "value": "IPS"}])], request),
    )

    assert messages[-1]["content"].startswith("{")
    assert '"task": "analysis"' in messages[-1]["content"]
    assert '"comparison":' in messages[-1]["content"]
    assert '"products":' in messages[-1]["content"]
    assert "LEADER|" not in messages[-1]["content"]


def test_build_normalize_client_uses_same_runtime_config(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.deepseek_client.load_deepseek_settings",
        lambda: __import__("app.deepseek_settings", fromlist=["DeepSeekSettings"]).DeepSeekSettings(
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            endpoint_path="/chat/completions",
        ),
    )

    client = build_normalize_client()

    assert client.model == "deepseek-chat"
    assert client.endpoint.endswith("/chat/completions")


def test_orchestrator_uses_dns_url_and_keeps_unknown_params(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_uses_dns_url_and_keeps_unknown_params(tmp_path))


async def run_orchestrator_uses_dns_url_and_keeps_unknown_params(tmp_path: Path) -> None:
    calls = {}
    stages: list[str] = []
    resolver_calls = []

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        calls["limit"] = limit
        return (
            [Product("Смартфон A", 15000, "https://example/a", "1")],
            "httpx",
            input_value,
            input_value,
        )

    def fetch_specs(urls):
        calls["specs_urls"] = urls
        return [
            {
                "url": "https://example/a",
                "characteristics_url": "https://example/specs-a",
                "specs": [{"name": "Память", "value": "256 ГБ"}],
            }
        ]

    async def stream(messages):
        if "intent_route" in messages[-1]["content"]:
            yield '{"mode":"product_search","response_style":"structured","reason":"dns_url"}'
            return
        if "shortlist" in messages[-1]["content"]:
            yield '{"selected_urls":["https://example/a"],"reasons":["цена и релевантность"]}'
            return
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_url_resolver=lambda requested_url: resolver_calls.append(requested_url) or "https://www.dns-shop.ru/search/?q=test&brand=abc&category=cat",
    )

    result = await orchestrator.handle_message(
        "https://www.dns-shop.ru/search/?q=test&brand=abc",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=stages.append,
    )

    assert calls["input"] == "https://www.dns-shop.ru/search/?q=test&brand=abc"
    assert resolver_calls == ["https://www.dns-shop.ru/search/?q=test&brand=abc"]
    assert calls["limit"] is None
    assert calls["specs_urls"] == ["https://example/a"]
    assert stages == [
        "remember_mode",
        "find_x",
        "cycle_code_1_start",
        "category_resolve_start",
        "category_resolve_done",
        "parser_start",
        "parser_done",
        "shortlist_start",
        "shortlist_done",
        "bot3_characteristics",
        "details_start",
        "details_done",
        "analysis_start",
        "analysis_done",
        "compare_link_start",
        "render_done",
    ]
    assert result.answer.startswith("Лучший вариант")
    assert "Смартфон A" in result.answer
    assert "память 256 ГБ" in result.answer
    assert result.products_count == 1
    assert result.image_paths == []


def test_orchestrator_uses_text_query_when_no_url(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_uses_text_query_when_no_url(tmp_path))


async def run_orchestrator_uses_text_query_when_no_url(tmp_path: Path) -> None:
    calls = {}
    stages: list[str] = []

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        calls["limit"] = limit
        return (
            [
                Product("Клавиатура A", 1000, "https://example/a", "1"),
                Product("Клавиатура B", 1800, "https://example/b", "2"),
            ],
            "httpx",
            input_value,
            input_value,
        )

    def fetch_specs(urls):
        calls["specs_urls"] = urls
        return [
            {
                "url": "https://example/b",
                "characteristics_url": "https://example/specs-b",
                "specs": [{"name": "Тип", "value": "механическая"}],
            }
        ]

    def inspect_filters(section_url: str):
        calls["section_url"] = section_url
        return {
            "section_url": section_url,
            "query": "клавиатура",
            "category": "17a8950d16404e77",
            "count": 3,
            "filters": [
                {
                    "id": "price",
                    "name": "Цена",
                    "type": "range-checkbox",
                    "values": [],
                },
                {
                    "id": "f[1bm]",
                    "name": "Тип клавиатуры",
                    "type": "checkbox",
                    "values": [{"id": "mech", "name": "механическая", "count": 5}],
                },
                {
                    "id": "stock",
                    "name": "Наличие",
                    "type": "checkbox",
                    "values": [{"id": "now", "name": "В наличии", "count": None}],
                },
            ],
        }

    async def stream(messages):
        if "intent_route" in messages[-1]["content"]:
            yield '{"mode":"product_search","response_style":"structured","reason":"new_search"}'
            return
        if "normalize_query" in messages[-1]["content"]:
            yield "[ {клавиатура}, {0:2000}, {}, {}, {} ]"
            return
        if "filters_patch" in messages[-1]["content"]:
            yield '{"filters":[{"name":"Цена","min":0,"max":2000},{"name":"Тип клавиатуры","values":[{"name":"механическая"}]},{"name":"Наличие","values":[{"id":"now"}]}]}'
            return
        if "shortlist" in messages[-1]["content"]:
            yield '{"selected_urls":["https://example/b"],"reasons":["лучше по запросу"]}'
            return
        yield "Подходит"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0&category=17a8950d16404e77",
    )

    await orchestrator.handle_message(
        "найди клавиатуру до 2000",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=stages.append,
    )

    assert calls["input"] == (
        "https://www.dns-shop.ru/search/?q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0"
        "%D1%82%D1%83%D1%80%D0%B0&category=17a8950d16404e77&price=0-2000"
    )
    assert calls["limit"] is None
    assert calls["specs_urls"] == ["https://example/b"]
    assert calls["section_url"] == "https://www.dns-shop.ru/search/?q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0&category=17a8950d16404e77"
    assert stages == [
        "remember_mode",
        "find_x",
        "cycle_code_1_start",
        "bot1_category_brand",
        "bot2_price",
        "bot4_wishes",
        "wait_bot3_notimeout",
        "json_build_start",
        "category_resolve_start",
        "category_resolve_done",
        "filters_map_start",
        "filters_map_done",
        "filters_ai_start",
        "filters_ai_done",
        "create_link_start",
        "built_url_done",
        "parser_start",
        "parser_done",
        "shortlist_start",
        "shortlist_done",
        "bot3_characteristics",
        "details_start",
        "details_done",
        "analysis_start",
        "analysis_done",
        "compare_link_start",
        "render_done",
    ]


def test_orchestrator_falls_back_to_analog_search_when_exact_search_is_empty(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_falls_back_to_analog_search_when_exact_search_is_empty(tmp_path))


async def run_orchestrator_falls_back_to_analog_search_when_exact_search_is_empty(tmp_path: Path) -> None:
    calls = {"parser_inputs": []}

    async def normalize_search_request(_text: str) -> NormalizedSearchRequest:
        return NormalizedSearchRequest(
            product_type="refrigerator",
            query="холодильник side-by-side",
            price_min=75000,
            price_max=157500,
            wishes=("side_by_side",),
        )

    def parser(input_value: str, limit: int | None):
        calls["parser_inputs"].append(input_value)
        if len(calls["parser_inputs"]) == 1:
            return ([], "httpx", input_value, input_value)
        return (
            [Product("Холодильник B", 99999, "https://example/b", "2")],
            "httpx",
            input_value,
            input_value,
        )

    def inspect_filters(_section_url: str):
        return {
            "section_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=cat",
            "query": "холодильник",
            "category": "cat",
            "count": 2,
            "filters": [
                {
                    "id": "price",
                    "name": "Цена",
                    "type": "range-checkbox",
                    "values": [],
                },
                {
                    "id": "type",
                    "name": "Тип",
                    "type": "checkbox",
                    "values": [{"id": "side", "name": "Side by Side", "count": 4}],
                },
            ],
        }

    async def chat(messages):
        payload = messages[-1]["content"]
        if '"task": "filters_patch"' in payload:
            return '{"filters":[{"name":"Тип","values":[{"name":"Side by Side"}]}]}'
        if '"task": "shortlist"' in payload:
            return '{"selected_urls":["https://example/b"],"reasons":["аналог по категории"]}'
        return "Лидер анализа\nХолодильник B"

    async def stream(_messages):
        yield "Лидер анализа\nХолодильник B"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        chat=chat,
        stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [{"url": urls[0], "specs": [{"name": "Объем", "value": "700 л"}]}],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=cat",
    )
    orchestrator.normalize_search_request = normalize_search_request  # type: ignore[method-assign]

    result = await orchestrator.handle_message(
        "Найди холодильник Side-by-Side, с лёдогенератором, инверторным компрессором, объёмом от 600 литров, до 150 000 рублей",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert len(calls["parser_inputs"]) >= 1
    assert "type=side" in calls["parser_inputs"][0].lower()
    if len(calls["parser_inputs"]) > 1:
        assert calls["parser_inputs"][0] != calls["parser_inputs"][1]
        assert "price=0-150000" in calls["parser_inputs"][1].lower()
    assert result.products_count == 1
    assert "Холодильник B" in result.answer


def test_orchestrator_times_out_slow_analog_search(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_times_out_slow_analog_search(tmp_path))


async def run_orchestrator_times_out_slow_analog_search(tmp_path: Path) -> None:
    calls = {"parser_inputs": []}

    async def normalize_search_request(_text: str) -> NormalizedSearchRequest:
        return NormalizedSearchRequest(
            product_type="refrigerator",
            query="холодильник side-by-side",
            price_min=75000,
            price_max=157500,
            wishes=("side_by_side",),
        )

    def parser(input_value: str, limit: int | None):
        calls["parser_inputs"].append(input_value)
        if len(calls["parser_inputs"]) == 1:
            return ([], "httpx", input_value, input_value)
        time.sleep(0.2)
        return ([], "httpx", input_value, input_value)

    def inspect_filters(_section_url: str):
        return {
            "section_url": "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=cat",
            "query": "холодильник",
            "category": "cat",
            "count": 2,
            "filters": [
                {
                    "id": "price",
                    "name": "Цена",
                    "type": "range-checkbox",
                    "values": [],
                },
                {
                    "id": "type",
                    "name": "Тип",
                    "type": "checkbox",
                    "values": [{"id": "side", "name": "Side by Side", "count": 4}],
                },
            ],
        }

    async def chat(messages):
        payload = messages[-1]["content"]
        if '"task": "filters_patch"' in payload:
            return '{"filters":[{"name":"Тип","values":[{"name":"Side by Side"}]}]}'
        if '"task": "shortlist"' in payload:
            return '{"selected_urls":[],"no_match":true,"reason":"нет подходящих товаров"}'
        return "Лидер анализа\nХолодильник B"

    async def stream(_messages):
        yield "Лидер анализа\nХолодильник B"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        chat=chat,
        stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D1%85%D0%BE%D0%BB%D0%BE%D0%B4%D0%B8%D0%BB%D1%8C%D0%BD%D0%B8%D0%BA&category=cat",
    )
    orchestrator.normalize_search_request = normalize_search_request  # type: ignore[method-assign]
    orchestrator.analog_search_timeout_seconds = 0.01

    started = time.monotonic()
    result = await orchestrator.handle_message(
        "Найди холодильник Side-by-Side, с лёдогенератором, инверторным компрессором, объёмом от 600 литров, до 150 000 рублей",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )
    elapsed = time.monotonic() - started

    assert len(calls["parser_inputs"]) >= 1
    assert elapsed < 1.0
    assert result.products_count == 0


def test_orchestrator_keeps_russian_dns_query_when_llm_returns_english_query(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_keeps_russian_dns_query_when_llm_returns_english_query(tmp_path))


async def run_orchestrator_keeps_russian_dns_query_when_llm_returns_english_query(tmp_path: Path) -> None:
    calls = {"parser_inputs": [], "filters_urls": []}

    async def normalize_search_request(_text: str) -> NormalizedSearchRequest:
        return NormalizedSearchRequest(
            product_type="gamingchair",
            query="GamingChair",
            wishes=("mid_range",),
        )

    def parser(input_value: str, limit: int | None):
        calls["parser_inputs"].append(input_value)
        return (
            [Product("Игровое кресло X", 19999, "https://example/chair", "1")],
            "httpx",
            input_value,
            input_value,
        )

    def inspect_filters(section_url: str):
        calls["filters_urls"].append(section_url)
        assert "category=" in section_url
        return {
            "section_url": section_url,
            "query": "игровое кресло",
            "category": "cat",
            "count": 1,
            "filters": [],
        }

    async def chat(messages):
        payload = messages[-1]["content"]
        if '"task": "shortlist"' in payload:
            return '{"selected_urls":["https://example/chair"],"reasons":["подходит"]}'
        return "Лидер анализа\nИгровое кресло X"

    async def stream(_messages):
        yield "Лидер анализа\nИгровое кресло X"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        chat=chat,
        stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [{"url": urls[0], "specs": [{"name": "Рама", "value": "металл"}]}],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%B8%D0%B3%D1%80%D0%BE%D0%B2%D0%BE%D0%B5%20%D0%BA%D1%80%D0%B5%D1%81%D0%BB%D0%BE&category=cat",
    )
    orchestrator.normalize_search_request = normalize_search_request  # type: ignore[method-assign]

    result = await orchestrator.handle_message(
        "Игровое кресло средней цены",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert calls["filters_urls"]
    assert "GamingChair" not in calls["parser_inputs"][0]
    assert "q=%d0%b8%d0%b3%d1%80%d0%be%d0%b2%d0%be%d0%b5" in calls["parser_inputs"][0].lower()
    assert result.products_count == 1


def test_normalized_search_request_from_text_parses_compact_line() -> None:
    plan = normalized_search_request_from_text(
        '[ {видеокарта}, {20000:30000}, {samsung}, {"panel":"oled","nfc":"yes"}, {good_camera} ]',
        fallback="найди видеокарту самсунг 20-30к",
    )

    assert plan.query == "видеокарта"
    assert plan.price_min == 20000
    assert plan.price_max == 30000
    assert plan.brand == "samsung"
    assert set(plan.wishes) == {"matrix_type_oled", "nfc"}
    assert plan.soft_wishes == ("good_camera",)


def test_normalized_search_request_from_text_adds_soft_wishes_from_raw_text() -> None:
    plan = normalized_search_request_from_text(
        '[ {смартфон}, {0:25000}, {}, {"nfc":"yes"}, {} ]',
        fallback="Найди смартфон с хорошей камерой и NFC",
    )

    assert plan.wishes == ("nfc",)
    assert plan.soft_wishes == ("good_camera",)


def test_normalized_search_request_from_text_supports_stable_prompt_fields() -> None:
    plan = normalized_search_request_from_text(
        '[ {робот-пылесос}, {0:30000}, {xiaomi}, {"cleaning_mode":"wet","mapping":true}, {reliable} ]',
        fallback="Ищу робот-пылесос Xiaomi до 30000 с влажной уборкой и построением карты",
    )

    assert plan.query == "робот-пылесос"
    assert plan.product_type == "robotvacuum"
    assert plan.price_min == 0
    assert plan.price_max == 30000
    assert plan.brand == "xiaomi"
    assert set(plan.wishes) == {"wet_cleaning", "mapping"}
    assert plan.soft_wishes == ("reliable",)


def test_infer_product_type_and_query_supports_additional_home_appliances() -> None:
    assert infer_product_type_and_query("Найди электрогриль для дома")[0] == "electricgrill"
    assert infer_product_type_and_query("Найди лазерное МФУ для дома")[0] == "mfp"
    assert infer_product_type_and_query("Найди велотренажер для дома")[0] == "exercisebike"
    assert infer_product_type_and_query("Найди велотренажер для дома")[1] == "велотренажер"
    assert infer_product_type_and_query("Найди наушники с шумоподавлением")[0] == "headphones"
    assert infer_product_type_and_query("Найди жесткий диск для ПК")[0] == "hdd"
    assert infer_product_type_and_query("Найди пылесос с влажной уборкой")[0] == "robotvacuum"


def test_extract_hard_wishes_from_text_recognizes_additional_home_appliances() -> None:
    wishes = extract_hard_wishes_from_text(
        "Найди электрогриль со съемными панелями, антипригарным покрытием, регулировкой температуры, поддоном для жира и раскрытием на 180 градусов"
    )
    assert {
        "power_from_1800_w",
        "removable_panels",
        "nonstick_coating",
        "temperature_control",
        "grease_tray",
        "opens_180",
    } & set(wishes)

    robot_wishes = extract_hard_wishes_from_text(
        "Найди робот-пылесос с лидаром, влажной уборкой, построением карты, управлением со смартфона и аккумулятором от 4000 мА·ч"
    )
    assert {"lidar_navigation", "wet_cleaning", "mapping", "smartphone_control", "battery_capacity_from_4000_mah"} <= set(robot_wishes)

    printer_wishes = extract_hard_wishes_from_text(
        "Найди лазерное МФУ с Wi-Fi, двусторонней печатью, сканером, черно-белой печатью и скоростью от 20 стр/мин"
    )
    assert {"device_type_mfp", "print_technology_laser", "wifi", "duplex_print", "scanner", "print_speed_from_20_ppm"} & set(printer_wishes)

    bike_wishes = extract_hard_wishes_from_text(
        "Найди велотренажер с магнитной системой нагрузки, весом пользователя от 120 кг, дисплеем, пульсом и не меньше 8 уровней нагрузки"
    )
    assert {"resistance_system_magnetic", "max_user_weight_from_120_kg", "display", "pulse_measurement", "resistance_levels_from_8"} & set(bike_wishes)

    coffee_wishes = extract_hard_wishes_from_text(
        "Найди автоматическую кофемашину с капучинатором, давлением от 15 бар, встроенной кофемолкой, регулировкой крепости, регулировкой объема порции и самоочисткой"
    )
    assert {"machine_type_automatic", "cappuccinator", "pressure_from_15_bar", "built_in_grinder", "strength_adjustment", "portion_volume_adjustment", "self_cleaning"} & set(coffee_wishes)


def test_extract_hard_wishes_from_text_recovers_explicit_laptop_constraints() -> None:
    wishes = extract_hard_wishes_from_text(
        "Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, 2024 года выпуска"
    )

    assert wishes == (
        "rtx_4080",
        "32gb_ram",
        "240hz_screen",
        "weight_up_to_2.5_kg",
        "matte_screen",
        "2024_year",
    )


def test_extract_soft_wishes_from_text_does_not_treat_freezer_chamber_as_camera() -> None:
    soft_wishes = extract_soft_wishes_from_text(
        "Найди холодильник с морозильной камерой снизу, No Frost и тихой работой"
    )

    assert "good_camera" not in soft_wishes


def test_extract_hard_wishes_from_text_recognizes_refrigerator_constraints() -> None:
    wishes = extract_hard_wishes_from_text(
        "Найди холодильник No Frost с морозильной камерой снизу и инверторным компрессором"
    )

    assert "cooling_system_no_frost" in wishes
    assert "freezer_position_bottom" in wishes
    assert "inverter_compressor" in wishes


def test_extract_hard_wishes_from_text_recognizes_sewing_machine_constraints() -> None:
    wishes = extract_hard_wishes_from_text(
        "Найди швейную машину с горизонтальным челноком, автоматическим выполнением петли, не меньше 30 швейных операций, регулировкой скорости и подсветкой рабочей зоны"
    )

    assert wishes == (
        "sewing_operations_from_30",
        "shuttle_type_horizontal",
        "buttonhole_automatic",
        "speed_control",
        "work_area_light",
    )


def test_constraints_from_payload_supports_sewing_machine_keys() -> None:
    constraints = constraints_from_payload(
        {
            "sewing_operations_min": 30,
            "shuttle_type": "horizontal",
            "buttonhole": "automatic",
            "speed_control": True,
            "work_area_light": True,
        }
    )

    assert [constraint.key for constraint in constraints] == [
        "sewing_operations",
        "shuttle_type",
        "buttonhole",
        "speed_control",
        "work_area_light",
    ]
    assert [constraint.op for constraint in constraints] == [">=", "==", "==", "==", "=="]


def test_normalized_search_request_from_text_prefers_sewing_machine_category() -> None:
    plan = normalized_search_request_from_text(
        '{"product_type":"washingmachine","query":"швейная машина","price_min":0,"price_max":25000,"constraints":[{"key":"sewing_operations","op":">=","value":30,"unit":"","source_text":"не меньше 30 швейных операций"},{"key":"shuttle_type","op":"==","value":"horizontal","unit":"","source_text":"горизонтальным челноком"},{"key":"buttonhole","op":"==","value":"automatic","unit":"","source_text":"автоматическим выполнением петли"},{"key":"speed_control","op":"==","value":"true","unit":"","source_text":"регулировкой скорости"},{"key":"work_area_light","op":"==","value":"true","unit":"","source_text":"подсветкой рабочей зоны"}],"soft_wishes":["reliable","quality_build"]}',
        fallback="Найди швейную машину для дома с горизонтальным челноком, автоматическим выполнением петли, не меньше 30 швейных операций, регулировкой скорости, подсветкой рабочей зоны, возможностью шить плотные ткани, надежной сборкой и простым управлением, бюджет до 25 000 рублей",
    )

    assert plan.product_type == "sewingmachine"
    assert plan.query == "швейная машина"
    assert set(plan.wishes) == {
        "sewing_operations_from_30",
        "shuttle_type_horizontal",
        "buttonhole_automatic",
        "speed_control",
        "work_area_light",
    }


def test_build_preselected_filters_selects_sewing_machine_filters() -> None:
    request = NormalizedSearchRequest(
        product_type="sewingmachine",
        query="швейная машина",
        price_max=25000,
        wishes=(
            "sewing_operations_from_30",
            "shuttle_type_horizontal",
            "buttonhole_automatic",
            "speed_control",
            "work_area_light",
        ),
    )

    result = build_preselected_filters(
        request,
        {
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {
                    "id": "f[uw]",
                    "name": "Тип челнока",
                    "type": "checkbox",
                    "values": [
                        {"id": "vertical_rotary", "name": "Вертикальный вращающийся"},
                        {"id": "vertical_oscillating", "name": "Вертикальный качающийся"},
                        {"id": "horizontal", "name": "Горизонтальный"},
                    ],
                },
                {
                    "id": "f[uy]",
                    "name": "Выполнение петли",
                    "type": "checkbox",
                    "values": [
                        {"id": "automatic", "name": "Автомат"},
                        {"id": "semi", "name": "Полуавтомат"},
                        {"id": "none", "name": "Нет"},
                    ],
                },
                {
                    "id": "f[1w0]",
                    "name": "Максимальная скорость шитья (ст/мин)",
                    "type": "checkbox",
                    "values": [
                        {"id": "300", "name": "300 ст/мин"},
                        {"id": "450", "name": "450 ст/мин"},
                    ],
                },
                {
                    "id": "f[9ns]",
                    "name": "Регулировка скорости шитья без педали",
                    "type": "checkbox",
                    "values": [
                        {"id": "continuous", "name": "Бесступенчатая"},
                        {"id": "step", "name": "Ступенчатая"},
                        {"id": "none", "name": "Нет"},
                    ],
                },
                {
                    "id": "f[6jx]",
                    "name": "Источник подсветки",
                    "type": "checkbox",
                    "values": [
                        {"id": "led", "name": "LED"},
                        {"id": "lightbulb", "name": "Лампа накаливания"},
                        {"id": "none", "name": "Нет"},
                    ],
                },
                {
                    "id": "fr[ux]",
                    "name": "Количество швейных операций",
                    "type": "range-radio",
                    "values": [
                        {"id": "25_49", "name": "25 - 49"},
                        {"id": "50_99", "name": "50 - 99"},
                        {"id": "100_199", "name": "100 - 199"},
                    ],
                    "range": {"min": 1, "max": 478},
                },
            ],
        },
    )

    by_id = {item["id"]: item for item in result}
    assert by_id["f[uw]"]["values"][0]["id"] == "horizontal"
    assert by_id["f[uy]"]["values"][0]["id"] == "automatic"
    assert by_id["f[6jx]"]["values"][0]["id"] == "led"
    assert by_id["fr[ux]"]["min"] == 30
    assert by_id["fr[ux]"]["max"] == 478


def test_constraints_from_payload_supports_refrigerator_keys() -> None:
    constraints = constraints_from_payload(
        {
            "freezer_position": "bottom",
            "compressor_type": "inverter",
        }
    )

    assert [constraint.key for constraint in constraints] == ["freezer_position", "inverter_compressor"]
    assert [constraint.value for constraint in constraints] == ["bottom", "true"]


def test_build_preselected_filters_selects_both_no_frost_filters_for_refrigerator() -> None:
    request = NormalizedSearchRequest(
        product_type="refrigerator",
        query="холодильник",
        wishes=("cooling_system_no_frost", "freezer_position_bottom", "inverter_compressor"),
    )

    result = build_preselected_filters(
        request,
        {
            "filters": [
                {
                    "id": "freezer_nofrost",
                    "name": "Размораживание морозильной камеры / НТО",
                    "type": "checkbox",
                    "values": [
                        {"id": "freezer_yes", "name": "No Frost"},
                        {"id": "freezer_no", "name": "Капельная"},
                    ],
                },
                {
                    "id": "fridge_nofrost",
                    "name": "Размораживание холодильной камеры",
                    "type": "checkbox",
                    "values": [
                        {"id": "fridge_yes", "name": "No Frost"},
                        {"id": "fridge_no", "name": "Капельная"},
                    ],
                },
                {
                    "id": "freezer_position",
                    "name": "Расположение морозильной камеры / НТО",
                    "type": "checkbox",
                    "values": [
                        {"id": "bottom", "name": "Снизу"},
                        {"id": "top", "name": "Сверху"},
                    ],
                },
                {
                    "id": "compressor",
                    "name": "Инверторный компрессор",
                    "type": "checkbox",
                    "values": [
                        {"id": "yes", "name": "Есть"},
                        {"id": "no", "name": "Нет"},
                    ],
                },
            ]
        },
    )

    selected_ids = [item["id"] for item in result]
    assert "freezer_nofrost" in selected_ids
    assert "fridge_nofrost" in selected_ids
    assert "freezer_position" in selected_ids
    assert "compressor" in selected_ids


def test_build_product_score_entry_matches_refrigerator_hard_wishes() -> None:
    product = Product(
        name="Холодильник DEXP B4-35AMA белый",
        price=25999,
        url="https://example.test/fridge",
        code="fridge-1",
        specs=[
            {"name": "Размораживание морозильной камеры / НТО", "value": "No Frost"},
            {"name": "Размораживание холодильной камеры", "value": "No Frost"},
            {"name": "Инверторный компрессор", "value": "есть"},
            {"name": "Расположение морозильной камеры / НТО", "value": "снизу"},
            {"name": "Ширина", "value": "59.5 см"},
            {"name": "Полезный объем холодильной камеры", "value": "223 л"},
            {"name": "Общий объем", "value": "346 л"},
            {"name": "Класс энергопотребления", "value": "A+"},
            {"name": "Высота", "value": "186 см"},
            {"name": "Глубина", "value": "67 см"},
            {"name": "Гарантия", "value": "12 мес."},
            {"name": "Ящики", "value": "3 шт"},
        ],
    )
    request = NormalizedSearchRequest(
        product_type="refrigerator",
        query="холодильник",
        price_max=70000,
        wishes=("cooling_system_no_frost", "freezer_position_bottom", "inverter_compressor"),
    )

    entry = build_product_score_entry(product, request)

    assert entry["match_status"] == "exact"
    assert set(entry["matched_hard_wishes"]) == {
        "cooling_system_no_frost",
        "freezer_position_bottom",
        "inverter_compressor",
    }


def test_build_normalized_search_request_from_fallback_supports_macbook_iphone_and_gaming_monitor() -> None:
    macbook = build_normalized_search_request_from_fallback(
        "лёгкий макбук чуть дешевле 120000, 16 ГБ, SSD 512 ГБ, для программирования"
    )
    iphone = build_normalized_search_request_from_fallback(
        "айфон до 90000 с хорошей камерой"
    )
    gaming_monitor = build_normalized_search_request_from_fallback(
        "Хочу игровой монитор 27 дюймов от 20 до 35к, 144 Гц или выше, желательно с тонкими рамками"
    )

    assert macbook.query == "ноутбук"
    assert macbook.product_type == "laptop"
    assert macbook.brand == "apple"
    assert macbook.price_min == 96000
    assert macbook.price_max == 120000
    assert set(macbook.wishes) == {"16gb_ram", "ssd_from_512_gb"}
    assert set(macbook.soft_wishes) == {"lightweight", "for_programmer"}

    assert iphone.query == "смартфон"
    assert iphone.product_type == "smartphone"
    assert iphone.brand == "apple"
    assert iphone.price_min == 0
    assert iphone.price_max == 90000
    assert iphone.soft_wishes == ("good_camera",)

    assert gaming_monitor.query == "монитор"
    assert gaming_monitor.product_type == "monitor"
    assert gaming_monitor.price_min == 20000
    assert gaming_monitor.price_max == 35000
    assert set(gaming_monitor.wishes) == {"27_inch", "144hz_display"}
    assert set(gaming_monitor.soft_wishes) == {"for_gaming", "thin_bezel"}


def test_build_normalized_search_request_from_fallback_without_price_keeps_none() -> None:
    plan = build_normalized_search_request_from_fallback("телефон самсунг, 2024 года выпуска, с амолед экраном")

    assert plan.product_type == "smartphone"
    assert plan.price_min is None
    assert plan.price_max is None
    assert "price=0-0" not in build_normalized_request_search_url(plan)


def test_normalized_search_request_from_text_recovers_missing_hard_wishes_from_raw_text() -> None:
    plan = normalized_search_request_from_text(
        "[ {ноутбук}, {0:250000}, {}, {}, {} ]",
        fallback="Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, до 250 000 рублей, 2024 года выпуска",
    )

    assert plan.wishes == (
        "rtx_4080",
        "32gb_ram",
        "240hz_screen",
        "weight_up_to_2.5_kg",
        "matte_screen",
        "2024_year",
    )
    assert plan.price_min == 0
    assert plan.price_max == 250000


def test_normalized_search_request_from_text_merges_llm_and_raw_hard_wishes() -> None:
    plan = normalized_search_request_from_text(
        '[ {ноутбук}, {0:250000}, {}, {"gpu":"rtx 4080"}, {} ]',
        fallback="Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, до 250 000 рублей, 2024 года выпуска",
    )

    assert plan.wishes == (
        "rtx_4080",
        "32gb_ram",
        "240hz_screen",
        "weight_up_to_2.5_kg",
        "matte_screen",
        "2024_year",
    )


def test_normalized_search_request_from_text_preserves_laptop_range_wishes() -> None:
    text = (
        "Найди игровой ноутбук с видеокартой RTX 4070 или выше, оперативной памятью от 32 ГБ, "
        "экраном с частотой от 165 Гц, весом до 2.3 кг, с матовым покрытием, "
        "не старше 2024 года, бюджет до 200 000 рублей"
    )
    plan = normalized_search_request_from_text(
        '["игровой ноутбук", {"min":0,"max":200000}, {}, {"ram":"32 gb","refresh_rate":"165 hz","gpu":"rtx 4070","weight":"2.3 kg","coating":"matte","year":"2024"}, {"for_gaming","lightweight"}]',
        fallback=text,
    )

    assert set(plan.wishes) == {
        "rtx_4070_or_higher",
        "32gb_ram",
        "refresh_rate_from_165hz",
        "weight_up_to_2.3_kg",
        "matte_screen",
        "year_from_2024",
    }
    assert set(plan.soft_wishes) == {"for_gaming", "lightweight"}
    assert (plan.price_min, plan.price_max) == (0, 200000)

    raw_dict_style = normalized_search_request_from_text(
        '["игровой ноутбук",{"min":0,"max":200000},"",{"gpu_min":"rtx 4070"},{"for_gaming":true}]',
        fallback=text,
    )
    assert raw_dict_style.soft_wishes == ("for_gaming",)


def test_normalized_search_request_from_text_distinguishes_exact_year_from_year_floor() -> None:
    exact = normalized_search_request_from_text(
        '[ {смартфон}, {0:80000}, {samsung}, {"matrix_type":"amoled","year":"2024"}, {good_camera} ]',
        fallback="телефон самсунг, 2024 года выпуска, с амолед экраном",
    )
    floor = normalized_search_request_from_text(
        '[ {смартфон}, {0:80000}, {samsung}, {"matrix_type":"amoled","year_min":"2024"}, {good_camera} ]',
        fallback="телефон самсунг, не старше 2024 года, с амолед экраном",
    )

    assert "2024_year" in exact.wishes
    assert "year_from_2024" not in exact.wishes
    assert "year_from_2024" in floor.wishes
    assert "2024_year" not in floor.wishes


def test_normalized_search_request_from_text_deduplicates_year_constraints() -> None:
    plan = normalized_search_request_from_text(
        '[ {смартфон}, {0:80000}, {samsung}, {"year":"2024"}, {good_camera} ]',
        fallback="телефон самсунг, 2024 года выпуска, с амолед экраном",
    )

    year_constraints = [constraint for constraint in plan.constraints if constraint.key == "year"]

    assert len(year_constraints) == 1
    assert year_constraints[0].op == "=="
    assert year_constraints[0].value == "2024"
    assert year_constraints[0].source_text in {"2024", "2024_year"}


def test_build_preselected_filters_expands_laptop_minimum_ranges() -> None:
    request = NormalizedSearchRequest(
        product_type="laptop",
        query="ноутбук",
        price_min=0,
        price_max=200000,
        wishes=(
            "rtx_4070_or_higher",
            "32gb_ram",
            "refresh_rate_from_165hz",
            "weight_up_to_2.3_kg",
            "matte_screen",
            "year_from_2024",
        ),
    )

    result = build_preselected_filters(
        request,
        {
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {
                    "id": "gpu",
                    "name": "Модель дискретной видеокарты",
                    "type": "checkbox",
                    "values": [
                        {"id": "4060", "name": "GeForce RTX 4060 для ноутбуков"},
                        {"id": "4070", "name": "GeForce RTX 4070 для ноутбуков"},
                        {"id": "4080", "name": "GeForce RTX 4080 для ноутбуков"},
                        {"id": "4090", "name": "GeForce RTX 4090 для ноутбуков"},
                        {"id": "5050", "name": "GeForce RTX 5050 для ноутбуков"},
                        {"id": "5060", "name": "GeForce RTX 5060 для ноутбуков"},
                        {"id": "5070", "name": "GeForce RTX 5070 для ноутбуков"},
                        {"id": "rx6800", "name": "Radeon RX 6800M"},
                    ],
                },
                {
                    "id": "year",
                    "name": "Год релиза",
                    "type": "checkbox",
                    "values": [
                        {"id": "2023", "name": "2023"},
                        {"id": "2024", "name": "2024"},
                        {"id": "2025", "name": "2025"},
                        {"id": "2026", "name": "2026"},
                    ],
                },
                {
                    "id": "hz",
                    "name": "Частота обновления экрана",
                    "type": "checkbox",
                    "values": [
                        {"id": "144", "name": "144 Гц"},
                        {"id": "165", "name": "165 Гц"},
                        {"id": "180", "name": "180 Гц"},
                        {"id": "240", "name": "240 Гц"},
                    ],
                },
                {
                    "id": "weight",
                    "name": "Вес",
                    "type": "range-radio",
                    "values": [
                        {"id": "w19", "name": "1.50-1.99 кг"},
                        {"id": "w23", "name": "2.00-2.30 кг"},
                        {"id": "w24", "name": "2.31-2.49 кг"},
                    ],
                    "range": {"min": 0.85, "max": 3.9},
                },
                {"id": "ram", "name": "Объем оперативной памяти (ГБ)", "type": "checkbox", "values": [{"id": "32", "name": "32 ГБ"}]},
                {"id": "finish", "name": "Покрытие экрана", "type": "checkbox", "values": [{"id": "matte", "name": "матовое"}]},
            ],
        },
    )

    by_id = {item["id"]: item for item in result}
    assert [value["id"] for value in by_id["gpu"]["values"]] == ["4070", "4080", "4090"]
    assert [value["id"] for value in by_id["year"]["values"]] == ["2024", "2025", "2026"]
    assert [value["id"] for value in by_id["hz"]["values"]] == ["165", "180", "240"]
    assert by_id["weight"]["min"] == 0.85
    assert by_id["weight"]["max"] == 2.3


def test_normalized_search_request_from_text_keeps_smartphone_minimum_constraints() -> None:
    text = "Найди смартфон с AMOLED-экраном от 120 Гц, памятью от 256 ГБ, оперативной памятью от 12 ГБ, поддержкой 5G, NFC, защитой не ниже IP68, быстрой зарядкой, хорошей камерой и хорошей автономностью, не старше 2024 года, бюджет до 80 000 рублей"
    plan = normalized_search_request_from_text(
        '["смартфон",{"min":0,"max":80000},"",{"storage_min":"256 gb","ram_min":"12 gb","refresh_rate_min":"120 hz","matrix_type":"amoled","network":"5g","nfc":true,"protection":"ip68","fast_charge":true,"year_min":"2024"},{"good_camera":true,"good_battery":true}]',
        fallback=text,
    )

    assert set(plan.wishes) == {
        "storage_from_256_gb",
        "12gb_ram",
        "refresh_rate_from_120hz",
        "matrix_type_amoled",
        "network_5g",
        "nfc",
        "waterproof_ip68",
        "fast_charge",
        "year_from_2024",
    }
    assert "amoled_display" not in plan.wishes


def test_normalized_search_request_from_text_drops_hallucinated_soft_performance() -> None:
    plan = normalized_search_request_from_text(
        '["смартфон",{"min":0,"max":80000},"",{"storage_min":"256 gb","ram_min":"12 gb","refresh_rate_min":"120 hz","matrix_type":"amoled","network":"5g","nfc":true,"protection":"ip68","fast_charge":true,"year_min":"2024"},{"good_camera":true,"good_performance":true}]',
        fallback="Найди смартфон с AMOLED-экраном от 120 Гц, памятью от 256 ГБ, оперативной памятью от 12 ГБ, поддержкой 5G, NFC, защитой не ниже IP68, быстрой зарядкой, хорошей камерой и хорошей автономностью, не старше 2024 года, бюджет до 80 000 рублей",
    )

    assert "good_camera" in plan.soft_wishes
    assert "good_battery" in plan.soft_wishes
    assert "good_performance" not in plan.soft_wishes


def test_build_preselected_filters_handles_smartphone_minimum_ranges_without_model_fallback() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        price_min=0,
        price_max=80000,
        wishes=("storage_from_256_gb", "12gb_ram", "refresh_rate_from_120hz", "network_5g"),
    )

    result = build_preselected_filters(
        request,
        {
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {
                    "id": "ram",
                    "name": "Объем оперативной памяти (ГБ)",
                    "type": "checkbox",
                    "values": [
                        {"id": "8", "name": "8 ГБ"},
                        {"id": "12", "name": "12 ГБ"},
                        {"id": "16", "name": "16 ГБ"},
                    ],
                },
                {
                    "id": "virtual_ram",
                    "name": "Виртуальное расширение ОЗУ (Б)",
                    "type": "checkbox",
                    "values": [
                        {"id": "1000000000", "name": "1000000000 Б"},
                        {"id": "2000000000", "name": "2000000000 Б"},
                    ],
                },
                {
                    "id": "thickness",
                    "name": "Толщина (мм)",
                    "type": "range-radio",
                    "values": [
                        {"id": "thin", "name": "7.91 - 8.9"},
                        {"id": "thick", "name": "12.91 и более"},
                    ],
                    "range": {"min": 4.1, "max": 66.7},
                },
                {
                    "id": "storage",
                    "name": "Объем встроенной памяти (ГБ)",
                    "type": "checkbox",
                    "values": [
                        {"id": "128", "name": "128 ГБ"},
                        {"id": "256", "name": "256 ГБ"},
                        {"id": "512", "name": "512 ГБ"},
                    ],
                },
                {
                    "id": "hz",
                    "name": "Частота обновления экрана (Гц)",
                    "type": "checkbox",
                    "values": [
                        {"id": "120", "name": "120 Гц"},
                        {"id": "144", "name": "144 Гц"},
                        {"id": "165", "name": "165 Гц"},
                    ],
                },
                {
                    "id": "model",
                    "name": "Модель",
                    "type": "checkbox",
                    "values": [
                        {"id": "a", "name": "Samsung Galaxy A56 5G"},
                        {"id": "b", "name": "Xiaomi 14T 5G"},
                    ],
                },
            ]
        },
    )

    by_id = {item["id"]: item for item in result}
    assert [value["id"] for value in by_id["ram"]["values"]] == ["12", "16"]
    assert [value["id"] for value in by_id["storage"]["values"]] == ["256", "512"]
    assert [value["id"] for value in by_id["hz"]["values"]] == ["120", "144", "165"]
    assert "model" not in by_id
    assert "virtual_ram" not in by_id
    assert "thickness" not in by_id


def test_build_preselected_filters_expands_smartphone_numeric_ranges_and_includes_super_amoled() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        price_min=0,
        price_max=80000,
        wishes=("12gb_ram", "storage_from_256_gb", "matrix_type_amoled"),
    )

    result = build_preselected_filters(
        request,
        {
            "filters": [
                {
                    "id": "ram",
                    "name": "Объем оперативной памяти (ГБ)",
                    "type": "checkbox",
                    "values": [
                        {"id": "8", "name": "8 ГБ"},
                        {"id": "12", "name": "12 ГБ"},
                        {"id": "16", "name": "16 ГБ"},
                        {"id": "24", "name": "24 ГБ"},
                    ],
                },
                {
                    "id": "storage",
                    "name": "Объем встроенной памяти (ГБ)",
                    "type": "checkbox",
                    "values": [
                        {"id": "128", "name": "128 ГБ"},
                        {"id": "256", "name": "256 ГБ"},
                        {"id": "512", "name": "512 ГБ"},
                        {"id": "1024", "name": "1024 ГБ"},
                        {"id": "2048", "name": "2048 ГБ"},
                    ],
                },
                {
                    "id": "matrix",
                    "name": "Тип матрицы (подробно)",
                    "type": "checkbox",
                    "values": [
                        {"id": "amoled", "name": "AMOLED"},
                        {"id": "super", "name": "Super AMOLED"},
                        {"id": "dynamic", "name": "Dynamic AMOLED 2X"},
                        {"id": "oled", "name": "OLED"},
                    ],
                },
            ]
        },
    )

    by_id = {item["id"]: item for item in result}
    assert [value["id"] for value in by_id["ram"]["values"]] == ["12", "16", "24"]
    assert [value["id"] for value in by_id["storage"]["values"]] == ["256", "512", "1024", "2048"]
    assert [value["id"] for value in by_id["matrix"]["values"]] == ["amoled", "super", "dynamic"]


def test_build_preselected_filters_marks_broad_amoled_family_as_covered() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        wishes=("matrix_type_amoled",),
    )

    _, coverage = build_preselected_filters_and_coverage(
        request,
        {
            "filters": [
                {
                    "id": "matrix",
                    "name": "Тип матрицы (подробно)",
                    "type": "checkbox",
                    "values": [
                        {"id": "amoled", "name": "AMOLED"},
                        {"id": "crystal", "name": "CrystalRes AMOLED"},
                        {"id": "dynamic", "name": "Dynamic AMOLED"},
                        {"id": "dynamic2x", "name": "Dynamic AMOLED 2X"},
                        {"id": "flex", "name": "Flexible AMOLED"},
                        {"id": "fluid", "name": "Fluid AMOLED"},
                        {"id": "lead", "name": "LEAD AMOLED"},
                        {"id": "rigid", "name": "Rigid AMOLED"},
                        {"id": "super", "name": "Super AMOLED"},
                        {"id": "superplus", "name": "Super AMOLED Plus"},
                        {"id": "swift", "name": "Swift AMOLED"},
                    ],
                }
            ]
        },
    )

    assert coverage[0]["status"] == "covered"
    assert coverage[0]["confidence"] >= 0.9
    assert coverage[0]["reason"] == "Selected broad AMOLED subtype set."


def test_build_constraint_candidate_packets_preserves_full_amoled_family() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        wishes=("matrix_type_amoled",),
    )

    packets = build_constraint_candidate_packets(
        request,
        {
            "filters": [
                {
                    "id": "matrix",
                    "name": "Тип матрицы (подробно)",
                    "type": "checkbox",
                    "values": [
                        {"id": "amoled", "name": "AMOLED"},
                        {"id": "crystal", "name": "CrystalRes AMOLED"},
                        {"id": "dynamic", "name": "Dynamic AMOLED"},
                        {"id": "dynamic2x", "name": "Dynamic AMOLED 2X"},
                        {"id": "flex", "name": "Flexible AMOLED"},
                        {"id": "fluid", "name": "Fluid AMOLED"},
                        {"id": "super", "name": "Super AMOLED"},
                        {"id": "superplus", "name": "Super AMOLED Plus"},
                        {"id": "oled", "name": "OLED"},
                    ],
                }
            ]
        },
    )

    values = packets[0]["candidate_filters"][0]["values"]
    assert [value["id"] for value in values] == [
        "amoled",
        "crystal",
        "dynamic",
        "dynamic2x",
        "flex",
        "fluid",
        "super",
        "superplus",
    ]
    assert all("numeric" not in value and "unit" not in value for value in values)


def test_build_constraint_candidate_packets_filters_matrix_noise() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        wishes=("matrix_type_amoled",),
    )

    packets = build_constraint_candidate_packets(
        request,
        {
            "filters": [
                {
                    "id": "matrix",
                    "name": "Тип матрицы (подробно)",
                    "group": "Экран",
                    "type": "checkbox",
                    "values": [
                        {"id": "amoled", "name": "AMOLED"},
                        {"id": "oled", "name": "OLED"},
                    ],
                },
                {
                    "id": "refresh",
                    "name": "Частота обновления экрана (Гц)",
                    "group": "Экран",
                    "type": "checkbox",
                    "values": [{"id": "120", "name": "120 Гц"}],
                },
                {
                    "id": "colors",
                    "name": "Количество цветов экрана",
                    "group": "Экран",
                    "type": "checkbox",
                    "values": [{"id": "16m", "name": "16.7 млн"}],
                },
            ]
        },
    )

    candidate_names = [candidate["name"] for candidate in packets[0]["candidate_filters"]]
    assert candidate_names == ["Тип матрицы (подробно)"]


def test_build_constraint_candidate_packets_prefers_screen_refresh_rate_over_cpu_frequency() -> None:
    request = NormalizedSearchRequest(
        product_type="monitor",
        query="монитор",
        wishes=("refresh_rate_from_120hz",),
    )

    packets = build_constraint_candidate_packets(
        request,
        {
            "filters": [
                {
                    "id": "cpu",
                    "name": "Максимальная частота процессора (ГГц)",
                    "group": "Операционная система и процессор",
                    "type": "range-radio",
                    "values": [
                        {"id": "cpu-1", "name": "2.5 ГГц"},
                        {"id": "cpu-2", "name": "3.0 ГГц"},
                    ],
                },
                {
                    "id": "screen",
                    "name": "Частота обновления экрана (Гц)",
                    "group": "Экран",
                    "type": "range-radio",
                    "values": [
                        {"id": "screen-120", "name": "120 Гц"},
                        {"id": "screen-144", "name": "144 Гц"},
                    ],
                },
            ]
        },
    )

    candidate_ids = [candidate["id"] for candidate in packets[0]["candidate_filters"]]
    assert "screen" in candidate_ids
    assert "cpu" not in candidate_ids


def test_build_dns_url_from_section_filters_supports_numeric_weight_range() -> None:
    url = build_dns_url_from_section_filters(
        "https://www.dns-shop.ru/search/?q=%D0%BD%D0%BE%D1%83%D1%82%D0%B1%D1%83%D0%BA&category=17a892f816404e77",
        [{"id": "fr[8o]", "name": "Вес (кг)", "min": 0.85, "max": 2.3}],
        [
            {
                "id": "fr[8o]",
                "name": "Вес (кг)",
                "type": "range-radio",
                "values": [],
                "range": {"min": 0.85, "max": 3.9},
            }
        ],
    )

    assert "fr%5B8o%5D=0.85-2.3" in url


def test_score_product_penalizes_price_above_budget() -> None:
    request = NormalizedSearchRequest(
        product_type="laptop",
        query="ноутбук",
        price_max=200000,
        wishes=("rtx_4070_or_higher", "32gb_ram"),
    )
    within_budget = Product(
        name="Ноутбук RTX 4070 32 ГБ",
        price=199999,
        url="https://example.test/ok",
        code="ok",
        specs=[
            {"name": "Модель дискретной видеокарты", "value": "GeForce RTX 4070"},
            {"name": "Объем оперативной памяти", "value": "32 ГБ"},
        ],
    )
    above_budget = Product(
        name="Ноутбук RTX 4070 32 ГБ",
        price=204999,
        url="https://example.test/over",
        code="over",
        specs=within_budget.specs,
    )

    assert score_product_for_request(within_budget, request) > score_product_for_request(above_budget, request)
    over_budget_entry = build_product_score_entry(above_budget, request)
    assert "price_max" in over_budget_entry["contradicted_hard_wishes"]


def test_rtx_4070_or_higher_does_not_auto_accept_newer_lower_tier_gpu_names() -> None:
    request = NormalizedSearchRequest(
        product_type="laptop",
        query="ноутбук",
        wishes=("rtx_4070_or_higher",),
    )
    rtx_4070 = Product(
        name="Ноутбук RTX 4070",
        price=180000,
        url="https://example.test/4070",
        code="4070",
        specs=[{"name": "Модель дискретной видеокарты", "value": "GeForce RTX 4070 для ноутбуков"}],
    )
    rtx_5060 = Product(
        name="Ноутбук RTX 5060",
        price=170000,
        url="https://example.test/5060",
        code="5060",
        specs=[{"name": "Модель дискретной видеокарты", "value": "GeForce RTX 5060 для ноутбуков"}],
    )

    assert score_product_for_request(rtx_4070, request) > score_product_for_request(rtx_5060, request)
    assert "rtx_4070_or_higher" in build_product_score_entry(rtx_5060, request)["contradicted_hard_wishes"]


def test_extract_price_hint_uses_budget_semantics_for_do() -> None:
    assert extract_price_hint("Найди монитор до 35000 рублей") == (0, 35000)


def test_extract_price_hint_ignores_keyboard_percent_layout() -> None:
    assert extract_price_hint("магнитная клавиатура до 3к лучше 75-80 процентов") == (0, 3000)


def test_keyboard_request_builds_price_magnetic_and_format_filters() -> None:
    request = build_normalized_search_request_from_fallback("магнитная клавиатура до 3к лучше 75-80 процентов")
    filters_map = {
        "filters": [
            {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
            {
                "id": "f[1bm]",
                "name": "Тип клавиатуры",
                "type": "checkbox",
                "values": [{"id": "cn9", "name": "магнитная", "count": 171}],
            },
            {
                "id": "f[7rj]",
                "name": "Формат клавиатуры",
                "type": "checkbox",
                "values": [
                    {"id": "699q", "name": "75%", "count": 443},
                    {"id": "atlu", "name": "TKL (80%)", "count": 399},
                ],
            },
        ]
    }

    selected, coverage = build_preselected_filters_and_coverage(request, filters_map)
    url = build_dns_url_from_section_filters(
        "https://www.dns-shop.ru/search/?q=клавиатура&category=17a8950d16404e77",
        selected,
        filters_map["filters"],
    )

    assert request.price_max == 3000
    assert "keyboard_type_magnetic" in request.wishes
    assert "keyboard_format_75_80" in request.wishes
    assert {"constraint_key": "keyboard_type", "status": "covered", "confidence": 0.96, "selected_filter_ids": ["f[1bm]"], "selected_values": ["магнитная"], "reason": ""} in coverage
    assert {"constraint_key": "keyboard_format", "status": "covered", "confidence": 0.96, "selected_filter_ids": ["f[7rj]"], "selected_values": ["75%", "TKL (80%)"], "reason": ""} in coverage
    assert "price=0-3000" in url
    assert "f%5B1bm%5D=cn9" in url
    assert "f%5B7rj%5D=699q-atlu" in url


def test_keyboard_ranking_prefers_needed_match_inside_budget_not_cheapest() -> None:
    request = build_normalized_search_request_from_fallback("магнитная клавиатура до 3к лучше 75-80 процентов")
    cheap = Product(
        "Клавиатура проводная Basic 75 Magnetic",
        99,
        "https://example/cheap",
        "1",
        specs=[
            {"name": "Тип клавиатуры", "value": "магнитная"},
            {"name": "Формат клавиатуры", "value": "75%"},
        ],
    )
    better = Product(
        "Клавиатура проводная VGN A75",
        2999,
        "https://example/better",
        "2",
        specs=[
            {"name": "Тип клавиатуры", "value": "магнитная"},
            {"name": "Формат клавиатуры", "value": "75%"},
        ],
    )

    assert rank_products_for_request([cheap, better], request)[0] == better


def test_extract_price_hint_ignores_weight_and_keeps_real_budget() -> None:
    assert extract_price_hint("Подбери лёгкий ноутбук до 1.5 кг для работы, до 80 000 рублей") == (0, 80000)


def test_extract_price_hint_inherits_thousands_suffix_for_range() -> None:
    assert extract_price_hint("найди видеокарту 20-30к") == (20000, 30000)


def test_extract_price_hint_supports_approx_thousands_words() -> None:
    assert extract_price_hint("Подбери смартфон Samsung примерно за 45 тысяч") == (36000, 54000)


def test_extract_price_hint_supports_not_more_than() -> None:
    assert extract_price_hint("Нужен холодильник не дороже 120000 рублей") == (0, 120000)


def test_extract_price_hint_supports_not_less_than() -> None:
    assert extract_price_hint("Нужна стиральная машина Bosch не дешевле 50к") == (50000, 999999)


def test_extract_price_hint_uses_mid_range_semantics_for_category_words() -> None:
    assert extract_price_hint("Игровое кресло средней цены", product_type="gamingchair") == (14000, 28000)


def test_normalized_search_request_from_text_overrides_llm_price_with_local_budget_semantics() -> None:
    plan = normalized_search_request_from_text(
        '[ {монитор}, {33250:36750}, {}, {"size":"27 inch","resolution":"1440p","panel":"ips","height_adjustment":"yes"}, {} ]',
        fallback="Найди хороший монитор для программиста 27 дюймов, 1440p, IPS, с регулировкой высоты, до 35000 рублей",
    )

    assert plan.query == "монитор"
    assert plan.price_min == 0
    assert plan.price_max == 35000


def test_normalized_search_request_from_text_cleans_mid_price_words_from_query() -> None:
    plan = normalized_search_request_from_text(
        "[ {игровое кресло}, {}, {}, {}, {} ]",
        fallback="Игровое кресло средней цены",
    )

    assert plan.query.casefold() == "игровое кресло"
    assert plan.price_min == 14000
    assert plan.price_max == 28000


def test_build_normalized_search_request_from_fallback_handles_common_category_prompts() -> None:
    cases = [
        (
            "Найди стиральную машину с загрузкой от 8 кг, сушкой, инверторным мотором, управлением со смартфона, до 60 000 рублей",
            "стиральная машина",
            "washingmachine",
            (0, 60000),
        ),
        (
            "Подбери робот-пылесос с функцией влажной уборки, навигацией по карте, объёмом пылесборника от 400 мл, временем работы от 120 минут, до 30 000 рублей",
            "робот-пылесос",
            "robotvacuum",
            (0, 30000),
        ),
        (
            "Найди кофемашину с автокапучинатором, отдельным контейнером для молока, регулировкой температуры и помолом \"под ключ\", до 80 000 рублей",
            "кофемашина",
            "coffee_machine",
            (0, 80000),
        ),
        (
            "Подбери кондиционер (сплит-систему) для комнаты 25 м², с инвертором, функцией очистки воздуха, управлением с телефона, энергокласс A+, до 50 000 рублей",
            "кондиционер",
            "airconditioner",
            (0, 50000),
        ),
        (
            "Найди игровую приставку с дисководом, поддержкой 4K, объёмом встроенной памяти от 1 ТБ, двумя геймпадами, до 60 000 рублей",
            "игровая приставка",
            "gameconsole",
            (0, 60000),
        ),
    ]

    for text, expected_query, expected_product_type, expected_price in cases:
        plan = build_normalized_search_request_from_fallback(text)
        assert plan.query.casefold() == expected_query
        assert plan.product_type == expected_product_type
        assert (plan.price_min, plan.price_max) == expected_price
        assert plan.soft_wishes == ()


def test_build_normalized_search_request_from_fallback_handles_new_query_matrix() -> None:
    cases = [
        (
            "Найди ноутбук Lenovo до 85к, с 16 ГБ ОЗУ, SSD на 512 ГБ, чтобы был легкий и с хорошей батареей",
            "ноутбук",
            "laptop",
            (0, 85000),
            "lenovo",
            {"16gb_ram", "ssd_from_512_gb"},
            {"lightweight", "good_battery"},
        ),
        (
            "Подбери смартфон Samsung примерно за 45 тысяч, с хорошей камерой, 256 гб памяти и чтобы не тормозил",
            "смартфон",
            "smartphone",
            (36000, 54000),
            "samsung",
            {"256gb_storage"},
            {"good_camera", "good_performance"},
        ),
        (
            "Хочу игровой монитор 27 дюймов от 20 до 35к, 144 Гц или выше, желательно с тонкими рамками",
            "монитор",
            "monitor",
            (20000, 35000),
            "",
            {"27_inch", "144hz_display"},
            {"thin_bezel", "for_gaming"},
        ),
        (
            "Нужен холодильник side-by-side не дороже 120000 рублей, серебристый, вместительный и тихий",
            "холодильник",
            "refrigerator",
            (0, 120000),
            "",
            {"side_by_side"},
            {"spacious", "quiet"},
        ),
        (
            "Ищу робот-пылесос Xiaomi около 30к, с влажной уборкой, лидаром, но можно чуть дороже если реально хороший",
            "робот-пылесос",
            "robotvacuum",
            (24000, 36000),
            "xiaomi",
            {"wet_cleaning", "lidar_navigation"},
            set(),
        ),
        (
            "Подбери кресло для работы до 25000, не хлам, с поддержкой спины, желательно не слишком тяжелое",
            "кресло",
            "chair",
            (0, 25000),
            "",
            set(),
            {"back_support", "lightweight", "quality_build"},
        ),
        (
            "Найди телевизор LG или Samsung от 70 до 100 тысяч, 55 дюймов, 4K, чтобы картинка была хорошая",
            "телевизор",
            "tv",
            (70000, 100000),
            "",
            {"55_inch", "4k"},
            {"good_image_quality"},
        ),
        (
            "Хочу планшет Apple примерно 80-100к, с 256 ГБ памяти, легкий, для рисования",
            "планшет",
            "tablet",
            (72000, 110000),
            "apple",
            {"256gb_storage"},
            {"lightweight", "for_drawing"},
        ),
        (
            "Нужна стиральная машина Bosch не дешевле 50к, с сушкой, тихая и надежная",
            "стиральная машина",
            "washingmachine",
            (50000, 999999),
            "bosch",
            {"dryer"},
            {"quiet", "reliable"},
        ),
        (
            "Подбери видеокарту RTX 4070, желательно до 70000, но можно чуть дороже если выгодно",
            "видеокарта",
            "graphicscard",
            (0, 70000),
            "",
            {"rtx_4070"},
            set(),
        ),
    ]

    for text, expected_query, expected_product_type, expected_price, expected_brand, expected_hard, expected_soft in cases:
        plan = build_normalized_search_request_from_fallback(text)
        assert plan.query.casefold() == expected_query
        assert plan.product_type == expected_product_type
        assert (plan.price_min, plan.price_max) == expected_price
        assert plan.brand == expected_brand
        assert expected_hard.issubset(set(plan.wishes))
        assert expected_soft.issubset(set(plan.soft_wishes))


def test_orchestrator_uses_non_stream_chat_for_structured_steps(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_uses_non_stream_chat_for_structured_steps(tmp_path))


async def run_orchestrator_uses_non_stream_chat_for_structured_steps(tmp_path: Path) -> None:
    calls = {"chat_payloads": [], "stream_payloads": []}

    def parser(input_value: str, limit: int | None):
        return ([Product("Ноутбук A", 100000, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(_section_url: str):
        return {
            "section_url": "https://www.dns-shop.ru/search/?q=%D0%BD%D0%BE%D1%83%D1%82%D0%B1%D1%83%D0%BA&category=cat",
            "query": "ноутбук",
            "category": "cat",
            "count": 3,
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "f[gpu]", "name": "Видеокарта", "type": "checkbox", "values": [{"id": "rtx4060", "name": "RTX 4060", "count": 1}]},
                {"id": "f[ram]", "name": "ОЗУ", "type": "checkbox", "values": [{"id": "16gb", "name": "16 ГБ", "count": 1}]},
            ],
        }

    def fetch_specs(_urls):
        return [{"url": "https://example/a", "specs": [{"name": "GPU", "value": "RTX 4060"}]}]

    async def chat(messages):
        payload = messages[-1]["content"]
        calls["chat_payloads"].append(payload)
        if "normalize_query" in payload:
            return '[ {ноутбук}, {95000:105000}, {}, {"gpu":"rtx 4060","ram":"16 gb"}, {} ]'
        if "filters_patch" in payload:
            return '{"filters":[{"name":"Видеокарта","values":[{"name":"RTX 4060"}]},{"name":"ОЗУ","values":[{"name":"16 ГБ"}]}]}'
        if "shortlist" in payload:
            return '{"selected_urls":["https://example/a"],"reasons":["подходит"]}'
        return ""

    async def stream(messages):
        payload = messages[-1]["content"]
        calls["stream_payloads"].append(payload)
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        chat=chat,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BD%D0%BE%D1%83%D1%82%D0%B1%D1%83%D0%BA&category=cat",
    )

    result = await orchestrator.handle_message(
        "Найди игровой ноутбук RTX 4060 16 ГБ",
        history=[],
        on_text_chunk=lambda _chunk: None,
        on_stage=lambda _stage: None,
    )

    assert result.products_count == 1
    assert any("normalize_query" in payload for payload in calls["chat_payloads"])
    assert any("shortlist" in payload for payload in calls["chat_payloads"])
    assert calls["stream_payloads"]
    assert not any("normalize_query" in payload for payload in calls["stream_payloads"])
    assert not any("shortlist" in payload for payload in calls["stream_payloads"])


def test_orchestrator_parallelizes_normalize_and_category_resolve(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_parallelizes_normalize_and_category_resolve(tmp_path))


async def run_orchestrator_parallelizes_normalize_and_category_resolve(tmp_path: Path) -> None:
    markers = {"chat_overlap": False, "resolver_overlap": False}
    chat_started = asyncio.Event()
    resolver_started = asyncio.Event()

    def parser(input_value: str, limit: int | None):
        return ([Product("Телевизор A", 25000, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(_section_url: str):
        return {
            "section_url": "https://www.dns-shop.ru/search/?q=%D1%82%D0%B5%D0%BB%D0%B5%D0%B2%D0%B8%D0%B7%D0%BE%D1%80&category=cat",
            "query": "телевизор",
            "category": "cat",
            "count": 1,
            "filters": [{"id": "price", "name": "Цена", "type": "range-checkbox", "values": []}],
        }

    def fetch_specs(_urls):
        return [{"url": "https://example/a", "specs": [{"name": "Диагональ", "value": "43"}]}]

    async def chat(messages):
        payload = messages[-1]["content"]
        if "normalize_query" in payload:
            chat_started.set()
            await asyncio.sleep(0.05)
            markers["chat_overlap"] = resolver_started.is_set()
            return "[ {телевизор}, {19000:31500}, {}, {}, {} ]"
        if "filters_patch" in payload:
            return '{"filters":[]}'
        if "shortlist" in payload:
            return '{"selected_urls":["https://example/a"],"reasons":["подходит"]}'
        return ""

    async def stream(_messages):
        yield "Ответ"

    def section_url_resolver(_requested_url: str) -> str:
        resolver_started.set()
        time.sleep(0.05)
        markers["resolver_overlap"] = chat_started.is_set()
        return "https://www.dns-shop.ru/search/?q=%D1%82%D0%B5%D0%BB%D0%B5%D0%B2%D0%B8%D0%B7%D0%BE%D1%80&category=cat"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        chat=chat,
        stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_filters_inspector=inspect_filters,
        section_url_resolver=section_url_resolver,
    )

    result = await orchestrator.handle_message(
        "подбери телевизор mini ips за 20к-30к",
        history=[],
        on_text_chunk=lambda _chunk: None,
        on_stage=lambda _stage: None,
    )

    assert result.products_count == 1
    assert markers["chat_overlap"] is True
    assert markers["resolver_overlap"] is True


def test_orchestrator_uses_startup_validated_static_category_without_resolver(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_uses_startup_validated_static_category_without_resolver(tmp_path))


async def run_orchestrator_uses_startup_validated_static_category_without_resolver(tmp_path: Path) -> None:
    calls = {"resolver": 0, "filters": []}

    def parser(input_value: str, limit: int | None):
        calls["parser_input"] = input_value
        return ([Product("27 Monitor", 10000, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(section_url: str):
        calls["filters"].append(section_url)
        return {
            "section_url": section_url,
            "query": "монитор",
            "category": "17a8943716404e77",
            "filters": [{"id": "price", "name": "Цена", "type": "range-checkbox", "values": []}],
        }

    async def chat(messages):
        content = messages[-1]["content"]
        if "normalize_query" in content:
            return "[ {монитор}, {0:35000}, {}, {}, {} ]"
        if "filters_patch" in content:
            return '{"filters":[]}'
        if "shortlist" in content:
            return '{"selected_urls":["https://example/a"]}'
        if "analysis" in content:
            return "Лидер анализа\nLG\n\nАльтернатива\nНет\n\nКритическое резюме\nНет"
        return '{"mode":"product_search","response_style":"structured","reason":"new"}'

    def resolver(requested_url: str) -> str:
        calls["resolver"] += 1
        return requested_url

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        chat=chat,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=resolver,
    )
    orchestrator.prime_static_category_fast_path(product_types=("monitor",))

    await orchestrator.handle_message(
        "Найди монитор до 35000 рублей",
        history=[],
        on_text_chunk=lambda chunk: None,
    )

    assert calls["resolver"] == 0
    assert "category=17a8943716404e77" in calls["parser_input"]
    assert calls["filters"].count("https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=17a8943716404e77") == 1
    assert calls["filters"].count("https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=17a8943716404e77&price=0-35000") == 1


def test_orchestrator_lazy_validates_static_category_for_exercisebike(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_lazy_validates_static_category_for_exercisebike(tmp_path))


async def run_orchestrator_lazy_validates_static_category_for_exercisebike(tmp_path: Path) -> None:
    calls = {"filters": []}

    def inspect_filters(section_url: str):
        calls["filters"].append(section_url)
        return {
            "section_url": section_url,
            "query": "велотренажер",
            "category": "17a8d9c316404e77",
            "filters": [{"id": "price", "name": "Цена", "type": "range-checkbox", "values": []}],
        }

    orchestrator = ProductAnalysisOrchestrator(
        chat=lambda _messages: '{"mode":"product_search","response_style":"structured","reason":"new"}',
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
    )
    request = NormalizedSearchRequest(
        product_type="exercisebike",
        query="велотренажер",
        price_min=0,
        price_max=30000,
    )

    section_url = orchestrator.build_static_category_section_url(request)

    assert section_url == "https://www.dns-shop.ru/search/?q=%D0%B2%D0%B5%D0%BB%D0%BE%D1%82%D1%80%D0%B5%D0%BD%D0%B0%D0%B6%D0%B5%D1%80&category=17a8d9c316404e77&price=0-30000"
    assert calls["filters"] == ["https://www.dns-shop.ru/search/?q=%D0%B2%D0%B5%D0%BB%D0%BE%D1%82%D1%80%D0%B5%D0%BD%D0%B0%D0%B6%D0%B5%D1%80&category=17a8d9c316404e77"]


def test_orchestrator_does_not_repeat_category_resolve_when_only_price_changes(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_does_not_repeat_category_resolve_when_only_price_changes(tmp_path))


async def run_orchestrator_does_not_repeat_category_resolve_when_only_price_changes(tmp_path: Path) -> None:
    calls = {"resolver": 0}

    def parser(input_value: str, limit: int | None):
        return ([Product("Ноутбук A", 130000, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(_section_url: str):
        return {
            "section_url": "https://www.dns-shop.ru/search/?q=%D0%BD%D0%BE%D1%83%D1%82%D0%B1%D1%83%D0%BA&category=cat",
            "query": "ноутбук",
            "category": "cat",
            "count": 1,
            "filters": [{"id": "price", "name": "Цена", "type": "range-checkbox", "values": []}],
        }

    def fetch_specs(_urls):
        return [{"url": "https://example/a", "specs": [{"name": "ОЗУ", "value": "16 ГБ"}]}]

    async def chat(messages):
        payload = messages[-1]["content"]
        if "normalize_query" in payload:
            return "[ {ноутбук}, {123500:136500}, {}, {}, {} ]"
        if "filters_patch" in payload:
            return '{"filters":[]}'
        if "shortlist" in payload:
            return '{"selected_urls":["https://example/a"],"reasons":["подходит"]}'
        return ""

    async def stream(_messages):
        yield "Ответ"

    def section_url_resolver(_requested_url: str) -> str:
        calls["resolver"] += 1
        return "https://www.dns-shop.ru/search/?q=%D0%BD%D0%BE%D1%83%D1%82%D0%B1%D1%83%D0%BA&category=cat"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        chat=chat,
        stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_filters_inspector=inspect_filters,
        section_url_resolver=section_url_resolver,
    )

    result = await orchestrator.handle_message(
        "Найди игровой ноутбук до 130 000 рублей",
        history=[],
        on_text_chunk=lambda _chunk: None,
        on_stage=lambda _stage: None,
    )

    assert result.products_count == 1
    assert calls["resolver"] == 1


def test_orchestrator_injects_price_filter_from_query_plan_hint(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_injects_price_filter_from_query_plan_hint(tmp_path))


async def run_orchestrator_injects_price_filter_from_query_plan_hint(tmp_path: Path) -> None:
    calls = {}

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        return ([Product("GPU A", 19999, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "видеокарта",
            "category": "gpu-cat",
            "count": 1,
            "filters": [{"id": "price", "name": "Цена", "type": "range-checkbox", "values": []}],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "normalize_query" in content:
            yield "[ {видеокарта}, {19000:21000}, {}, {}, {} ]"
            return
        if "filters_patch" in content:
            yield '{"filters":[]}'
            return
        if "shortlist" in content:
            yield '{"selected_urls":["https://example/a"],"reasons":["релевантность"]}'
            return
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%B2%D0%B8%D0%B4%D0%B5%D0%BE%D0%BA%D0%B0%D1%80%D1%82%D0%B0&category=gpu-cat",
    )

    await orchestrator.handle_message(
        "найди лучшую видеокарту до 20к",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert "price=0-20000" in calls["input"]


def test_orchestrator_drops_ai_brand_filter_when_brand_not_requested(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_drops_ai_brand_filter_when_brand_not_requested(tmp_path))


async def run_orchestrator_drops_ai_brand_filter_when_brand_not_requested(tmp_path: Path) -> None:
    calls = {}

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        return ([Product("Monitor A", 34999, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "монитор",
            "category": "monitor-cat",
            "count": 3,
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "brand", "name": "Бренд", "type": "checkbox", "values": [{"id": "philips", "name": "Philips", "count": 4}]},
                {"id": "f[ips]", "name": "Тип матрицы", "type": "checkbox", "values": [{"id": "ips", "name": "IPS", "count": 10}]},
            ],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "normalize_query" in content:
            yield '[ {монитор}, {33250:36750}, {}, {"panel":"ips"}, {} ]'
            return
        if "filters_patch" in content:
            yield '{"filters":[{"name":"Бренд","values":[{"name":"Philips"}]},{"id":"f[ips]","values":[{"id":"ips"}]}]}'
            return
        if "shortlist" in content:
            yield '{"selected_urls":["https://example/a"],"reasons":["релевантность"]}'
            return
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=monitor-cat",
    )

    await orchestrator.handle_message(
        "Найди монитор IPS до 35000 рублей",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert "brand=philips" not in calls["input"]
    assert "price=0-35000" in calls["input"]
    assert "f%5Bips%5D=ips" in calls["input"]


def test_orchestrator_keeps_only_user_requested_ai_mapped_filters(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_keeps_only_user_requested_ai_mapped_filters(tmp_path))


async def run_orchestrator_keeps_only_user_requested_ai_mapped_filters(tmp_path: Path) -> None:
    calls = {}

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        return ([Product("Phone A", 24999, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "смартфон",
            "category": "phone-cat",
            "count": 4,
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "brand", "name": "Бренд", "type": "checkbox", "values": [{"id": "philips", "name": "Philips", "count": 2}]},
                {"id": "f[nfc]", "name": "NFC", "type": "checkbox", "values": [{"id": "21", "name": "есть", "count": 10}]},
                {"id": "f[amoled]", "name": "Тип матрицы", "type": "checkbox", "values": [{"id": "amoled", "name": "AMOLED", "count": 7}]},
            ],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "normalize_query" in content:
            yield '[ {смартфон}, {17500:26250}, {}, {"panel":"amoled","nfc":"yes"}, {} ]'
            return
        if "filters_patch" in content:
            yield '{"filters":[{"id":"brand","values":[{"id":"philips"}]},{"id":"f[amoled]","values":[{"id":"amoled"}]},{"id":"f[nfc]","values":[{"id":"21"}]}]}'
            return
        if "shortlist" in content:
            yield '{"selected_urls":["https://example/a"],"reasons":["релевантность"]}'
            return
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&category=phone-cat",
    )

    await orchestrator.handle_message(
        "Найди смартфон до 25000 с AMOLED и NFC",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert "brand=philips" not in calls["input"]
    assert "f%5Bamoled%5D=amoled" in calls["input"]
    assert "f%5Bnfc%5D=21" in calls["input"]


def test_orchestrator_drops_ambiguous_good_camera_filter(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_drops_ambiguous_good_camera_filter(tmp_path))


async def run_orchestrator_drops_ambiguous_good_camera_filter(tmp_path: Path) -> None:
    calls = {"payloads": []}

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        return ([Product("Phone A", 24999, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "смартфон",
            "category": "phone-cat",
            "count": 3,
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "f[camera]", "name": "Основная камера", "type": "checkbox", "values": [{"id": "50mp", "name": "50 Мп", "count": 4}]},
                {"id": "f[nfc]", "name": "NFC", "type": "checkbox", "values": [{"id": "21", "name": "есть", "count": 10}]},
            ],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        calls["payloads"].append(content)
        if "normalize_query" in content:
            yield '[ {смартфон}, {17500:26250}, {}, {"nfc":"yes"}, {good_camera} ]'
            return
        if "filters_patch" in content:
            yield '{"filters":[{"id":"f[camera]","values":[{"id":"50mp"}]},{"id":"f[nfc]","values":[{"id":"21"}]}]}'
            return
        if "shortlist" in content:
            yield '{"selected_urls":["https://example/a"],"reasons":["релевантность"]}'
            return
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&category=phone-cat",
    )

    await orchestrator.handle_message(
        "Найди смартфон до 25000 с хорошей камерой и NFC",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert "f%5Bcamera%5D=50mp" not in calls["input"]
    assert "f%5Bnfc%5D=21" in calls["input"]
    assert any('"soft_wishes": ["good_camera"]' in payload for payload in calls["payloads"])


def test_orchestrator_fails_fast_on_unknown_filter_selection(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_fails_fast_on_unknown_filter_selection(tmp_path))


async def run_orchestrator_fails_fast_on_unknown_filter_selection(tmp_path: Path) -> None:
    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "клавиатура",
            "category": "17a8950d16404e77",
            "count": 1,
            "filters": [
                {
                    "id": "stock",
                    "name": "Наличие",
                    "type": "checkbox",
                    "values": [{"id": "now", "name": "В наличии", "count": None}],
                }
            ],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "normalize_query" in content:
            yield "[ {клавиатура}, {}, {}, {}, {} ]"
            return
        if "filters_patch" in content:
            yield '{"filters":[{"name":"Несуществующий фильтр","values":[{"id":"x"}]}]}'
            return
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=lambda input_value, limit: ([], "httpx", input_value, input_value),
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0&category=17a8950d16404e77",
    )

    result = await orchestrator.handle_message(
        "найди клавиатуру",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert result.products_count == 0


def test_wish_matching_does_not_confuse_ips_with_philips(tmp_path: Path) -> None:
    asyncio.run(run_wish_matching_does_not_confuse_ips_with_philips(tmp_path))


async def run_wish_matching_does_not_confuse_ips_with_philips(tmp_path: Path) -> None:
    calls = {}

    def parser(input_value: str, limit: int | None):
        calls["input"] = input_value
        return ([Product("Monitor A", 30000, "https://example/a", "1")], "httpx", input_value, input_value)

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "монитор",
            "category": "monitor-cat",
            "count": 2,
            "filters": [
                {"id": "price", "name": "Цена", "type": "range-checkbox", "values": []},
                {"id": "brand", "name": "Бренд", "type": "checkbox", "values": [{"id": "philips", "name": "Philips", "count": 4}]},
                {"id": "f[ips]", "name": "Тип матрицы", "type": "checkbox", "values": [{"id": "ips", "name": "IPS", "count": 10}]},
            ],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "normalize_query" in content:
            yield '[ {монитор}, {17500:36750}, {}, {"panel":"ips"}, {} ]'
            return
        if "filters_patch" in content:
            yield '{"filters":[]}'
            return
        if "shortlist" in content:
            yield '{"selected_urls":["https://example/a"],"reasons":["релевантность"]}'
            return
        yield "Ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=lambda urls: [],
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BC%D0%BE%D0%BD%D0%B8%D1%82%D0%BE%D1%80&category=monitor-cat",
    )

    await orchestrator.handle_message(
        "Найди монитор IPS до 35000 рублей",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert "brand=philips" not in calls["input"]
    assert "f%5Bips%5D=ips" in calls["input"]


def test_soft_wishes_influence_local_ranking() -> None:
    request = normalized_search_request_from_text(
        "[ {смартфон}, {17500:26250}, {}, {}, {good_camera} ]",
        fallback="Найди смартфон с хорошей камерой",
    )
    products = [
        Product(
            "Phone B",
            24000,
            "https://example/b",
            "2",
            specs=[{"name": "Аккумулятор", "value": "5000 мАч"}],
        ),
        Product(
            "Phone A",
            25000,
            "https://example/a",
            "1",
            specs=[{"name": "Камера", "value": "50 Мп"}],
        ),
    ]

    ranked = rank_products_for_request(products, request)

    assert [product.url for product in ranked] == ["https://example/a", "https://example/b"]


def test_score_aware_rank_penalizes_hard_wish_contradictions() -> None:
    request = normalized_search_request_from_text(
        '[ {монитор}, {17500:36750}, {}, {"size":"27 inch","resolution":"1440p","panel":"ips","height_adjustment":"yes"}, {} ]',
        fallback="Найди монитор 27 дюймов, 1440p, IPS, с регулировкой высоты",
    )
    products = [
        Product(
            "31.5\" Монитор ARDOR GAMING",
            29999,
            "https://example/bad",
            "2",
            specs=[
                {"name": "Диагональ экрана (дюйм)", "value": '31.5"'},
                {"name": "Максимальное разрешение", "value": "2560x1440"},
                {"name": "Тип матрицы", "value": "IPS"},
                {"name": "Регулировка по высоте", "value": "есть"},
            ],
        ),
        Product(
            "27\" Монитор LG",
            31999,
            "https://example/good",
            "1",
            specs=[
                {"name": "Диагональ экрана (дюйм)", "value": '27"'},
                {"name": "Максимальное разрешение", "value": "2560x1440"},
                {"name": "Тип матрицы", "value": "IPS"},
                {"name": "Регулировка по высоте", "value": "есть"},
            ],
        ),
    ]

    ranked = rank_products_for_request(products, request)

    assert ranked[0].url == "https://example/good"


def test_rank_products_for_request_prefers_cheaper_item_on_equal_score() -> None:
    request = NormalizedSearchRequest(
        product_type="laptop",
        query="ноутбук",
        price_max=200000,
        wishes=("rtx_4070_or_higher", "32gb_ram", "weight_up_to_2.3_kg"),
    )
    products = [
        Product(
            '17.3" Ноутбук MSI Katana',
            197999,
            "https://example/msi",
            "1",
            specs=[
                {"name": "Модель дискретной видеокарты", "value": "GeForce RTX 4070 для ноутбуков"},
                {"name": "Объем оперативной памяти", "value": "32 ГБ"},
                {"name": "Вес", "value": "2.7 кг"},
            ],
        ),
        Product(
            '16" Ноутбук Machenike Star 16 Moon',
            169999,
            "https://example/machenike",
            "2",
            specs=[
                {"name": "Модель дискретной видеокарты", "value": "GeForce RTX 4070 для ноутбуков"},
                {"name": "Объем оперативной памяти", "value": "32 ГБ"},
                {"name": "Вес", "value": "2.7 кг"},
            ],
        ),
    ]

    ranked = rank_products_for_request(products, request)

    assert ranked[0].url == "https://example/machenike"


def test_build_comparison_summary_exposes_score_and_gap() -> None:
    request = normalized_search_request_from_text(
        '[ {монитор}, {17500:36750}, {}, {"size":"27 inch","resolution":"1440p","panel":"ips","height_adjustment":"yes"}, {} ]',
        fallback="Найди монитор для программиста 27 дюймов, 1440p, IPS и регулировкой высоты",
    )
    products = [
        Product(
            "ASUS ProArt PA278CGV",
            31999,
            "https://example/asus",
            "1",
            [
                {"name": "Диагональ экрана (дюйм)", "value": '27"'},
                {"name": "Максимальное разрешение", "value": "2560x1440"},
                {"name": "Тип матрицы", "value": "IPS"},
                {"name": "Регулировка по высоте", "value": "есть"},
                {"name": "USB-C", "value": "есть"},
            ],
        ),
        Product(
            "Samsung ViewFinity S6",
            29999,
            "https://example/samsung",
            "2",
            [
                {"name": "Диагональ экрана (дюйм)", "value": '27"'},
                {"name": "Максимальное разрешение", "value": "1920x1080"},
                {"name": "Тип матрицы", "value": "IPS"},
                {"name": "Регулировка по высоте", "value": "нет"},
            ],
        ),
    ]

    summary = build_comparison_summary(products, request)

    assert summary["leader"]["name"] == "ASUS ProArt PA278CGV"
    assert summary["leader"]["score"] >= summary["competitors"][0]["score"]
    assert summary["competitors"][0]["score_gap_to_leader"] == summary["leader"]["score"] - summary["competitors"][0]["score"]
    assert summary["leader"]["matched_hard_wishes"] == ["27_inch", "1440p", "ips", "height_adjustable"]
    assert summary["leader"]["match_status"] == "exact"
    assert summary["competitors"][0]["missing_hard_wishes"] == []
    assert summary["competitors"][0]["contradicted_hard_wishes"] == ["1440p", "height_adjustable"]
    assert summary["competitors"][0]["match_status"] == "rejected"
    assert "teacher_contract" not in summary


def test_build_comparison_summary_exposes_price_and_segment_leaders() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        price_min=0,
        price_max=80000,
        soft_wishes=("good_camera", "good_battery"),
    )
    products = [
        Product(
            "Camera Phone",
            60000,
            "https://example/camera",
            "1",
            specs=[{"name": "Камера", "value": "50 Мп"}],
        ),
        Product(
            "Battery Phone",
            70000,
            "https://example/battery",
            "2",
            specs=[{"name": "Аккумулятор", "value": "5000 мАч"}],
        ),
        Product(
            "Cheapest Phone",
            50000,
            "https://example/cheap",
            "3",
            specs=[{"name": "NFC", "value": "есть"}],
        ),
    ]

    summary = build_comparison_summary(products, request)

    assert summary["price_leader"]["name"] == "Cheapest Phone"
    assert summary["segment_leaders"]["price_leader"]["name"] == "Cheapest Phone"
    assert summary["segment_leaders"]["value_leader"]["name"] in {"Camera Phone", "Battery Phone", "Cheapest Phone"}
    assert "soft_wish_leaders" not in summary


def test_build_comparison_summary_prefers_stronger_battery_signal_over_cheaper_candidate() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        price_min=0,
        price_max=80000,
        soft_wishes=("good_battery",),
    )
    products = [
        Product(
            "Cheaper Phone",
            45000,
            "https://example/cheap",
            "1",
            specs=[{"name": "Аккумулятор", "value": "5000 мАч"}],
        ),
        Product(
            "Battery Monster",
            55000,
            "https://example/battery",
            "2",
            specs=[{"name": "Аккумулятор", "value": "7000 мАч"}],
        ),
    ]

    summary = build_comparison_summary(products, request)

    assert summary["segment_leaders"]["value_leader"]["name"] == "Battery Monster"
    assert summary["leader"]["name"] == "Battery Monster"
    assert "soft_wish_leaders" not in summary


def test_build_comparison_summary_finds_soft_wish_leader_outside_top_five() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        soft_wishes=("good_battery",),
    )
    products = [
        Product("Alpha 1", 10000, "https://example/a1", "1", specs=[{"name": "Экран", "value": "AMOLED"}]),
        Product("Alpha 2", 11000, "https://example/a2", "2", specs=[{"name": "Экран", "value": "AMOLED"}]),
        Product("Alpha 3", 12000, "https://example/a3", "3", specs=[{"name": "Экран", "value": "AMOLED"}]),
        Product("Alpha 4", 13000, "https://example/a4", "4", specs=[{"name": "Экран", "value": "AMOLED"}]),
        Product("Alpha 5", 14000, "https://example/a5", "5", specs=[{"name": "Экран", "value": "AMOLED"}]),
        Product(
            "Vivo iQOO 15",
            90000,
            "https://example/vivo",
            "6",
            specs=[{"name": "Аккумулятор", "value": "7000 мАч"}],
        ),
    ]

    summary = build_comparison_summary(products, request)

    assert summary["segment_leaders"]["value_leader"]["name"] == "Vivo iQOO 15"
    assert summary["leader"]["name"] == "Vivo iQOO 15"
    assert "soft_wish_leaders" not in summary


def test_build_comparison_summary_exposes_segment_leaders_without_budget() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        soft_wishes=("good_camera", "good_battery"),
    )
    products = [
        Product(
            "Samsung M15",
            24999,
            "https://example/m15",
            "1",
            specs=[
                {"name": "Камера", "value": "50 Мп"},
                {"name": "Аккумулятор", "value": "6000 мАч"},
            ],
        ),
        Product(
            "Samsung A55",
            49999,
            "https://example/a55",
            "2",
            specs=[
                {"name": "Камера", "value": "50 Мп"},
                {"name": "Аккумулятор", "value": "5000 мАч"},
            ],
        ),
        Product(
            "Samsung S24",
            89999,
            "https://example/s24",
            "3",
            specs=[
                {"name": "Камера", "value": "200 Мп"},
                {"name": "Аккумулятор", "value": "5000 мАч"},
            ],
        ),
    ]

    summary = build_comparison_summary(products, request)

    assert summary["segment_leaders"]["price_leader"]["name"] == "Samsung M15"
    assert summary["segment_leaders"]["value_leader"]["name"] == "Samsung A55"
    assert summary["segment_leaders"]["spec_leader"]["name"] == "Samsung S24"
    assert summary["budget_defined"] is False


def test_build_comparison_summary_prefers_value_leader_for_budgeted_non_exact_match() -> None:
    request = NormalizedSearchRequest(
        product_type="headphones",
        price_max=5000,
        query="наушники",
        wishes=("wifi",),
    )
    products = [
        Product("Budget Buds", 850, "https://example/budget", "1", specs=[]),
        Product("Value Buds", 1250, "https://example/value", "2", specs=[]),
        Product("Feature Buds", 2200, "https://example/feature", "3", specs=[]),
    ]

    summary = build_comparison_summary(products, request)

    assert summary["price_leader"]["name"] == "Budget Buds"
    assert summary["leader"]["name"] == "Value Buds"


def test_build_comparison_summary_prefers_value_segment_when_budget_defined_and_no_hard_signals() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        price_min=0,
        price_max=100000,
        soft_wishes=("good_camera",),
    )
    products = [
        Product("Budget Phone", 14000, "https://example/budget", "1", specs=[]),
        Product("Value Phone", 49999, "https://example/value", "2", specs=[]),
        Product("Spec Phone", 89999, "https://example/spec", "3", specs=[]),
    ]

    summary = build_comparison_summary(products, request)

    assert summary["price_leader"]["name"] == "Budget Phone"
    assert summary["segment_leaders"]["value_leader"]["name"] == "Value Phone"
    assert summary["leader"]["name"] == "Value Phone"


def test_build_teacher_corrected_analysis_answer_uses_segment_leaders_without_budget() -> None:
    comparison_summary = {
        "leader": {
            "name": "Samsung A55",
            "price": 49999,
            "score": 10,
            "match_status": "exact",
            "missing_hard_wishes": [],
            "contradicted_hard_wishes": [],
            "matched_hard_wishes": [],
        },
        "competitors": [],
        "segment_leaders": {
            "price_leader": {
                "name": "Samsung M15",
                "price": 24999,
                "score": 7,
                "match_status": "exact",
                "missing_hard_wishes": [],
                "contradicted_hard_wishes": [],
                "matched_hard_wishes": [],
            },
            "value_leader": {
                "name": "Samsung A55",
                "price": 49999,
                "score": 10,
                "match_status": "exact",
                "missing_hard_wishes": [],
                "contradicted_hard_wishes": [],
                "matched_hard_wishes": [],
            },
            "spec_leader": {
                "name": "Samsung S24",
                "price": 89999,
                "score": 14,
                "match_status": "exact",
                "missing_hard_wishes": [],
                "contradicted_hard_wishes": [],
                "matched_hard_wishes": [],
            },
        },
        "budget_defined": False,
    }

    answer = build_teacher_corrected_analysis_answer([Product("Samsung A55", 49999, "https://example/a55", "1")], comparison_summary)

    assert answer.startswith("Лучший вариант")
    assert "Samsung A55" in answer
    assert "Samsung S24" in answer or "Samsung M15" in answer
    assert "сегментный ориентир" not in answer


def test_build_teacher_corrected_analysis_answer_uses_segment_leaders_for_budgeted_soft_only_request() -> None:
    comparison_summary = {
        "leader": {
            "name": "Xiaomi Redmi 14C",
            "price": 7499,
            "score": 12,
            "missing_hard_wishes": [],
            "contradicted_hard_wishes": [],
        },
        "competitors": [],
        "budget_defined": True,
        "segment_leaders": {
            "price_leader": {"name": "Xiaomi Redmi 14C", "price": 7499, "score": 12, "match_status": "partial"},
            "value_leader": {"name": "HUAWEI nova Y63", "price": 8599, "score": 18, "match_status": "partial"},
            "spec_leader": {"name": "Honor X8b", "price": 16999, "score": 22, "match_status": "partial"},
        },
    }

    answer = build_teacher_corrected_analysis_answer(
        [Product("Xiaomi Redmi 14C", 7499, "https://example/redmi", "1", specs=[])],
        comparison_summary,
    )

    assert "HUAWEI nova Y63" in answer
    assert "Honor X8b" in answer or "Xiaomi Redmi 14C" in answer
    assert "Лучший вариант" in answer
    assert "соответствует фильтрам выдачи" not in answer


def test_ensure_teacher_checked_analysis_answer_rewrites_false_full_match_claim() -> None:
    request = normalized_search_request_from_text(
        '[ {ноутбук}, {125000:262500}, {}, {"gpu":"rtx 4080","ram":"32 gb","refresh_rate":"240 hz","weight_max":"2.5 kg","screen_finish":"matte","year":"2024"}, {} ]',
        fallback="Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, до 250 000 рублей, 2024 года выпуска",
    )
    product = Product(
        '17.3" Ноутбук ARDOR Gaming ELEMENT L17-I9ND400 черный',
        218999,
        "https://example/ardor",
        "1",
        specs=[
            {"name": "Год релиза", "value": "2024"},
            {"name": "Покрытие экрана", "value": "матовое"},
            {"name": "Максимальная частота обновления экрана", "value": "240 Гц"},
            {"name": "Объем оперативной памяти", "value": "32 ГБ"},
            {"name": "Модель дискретной видеокарты", "value": "GeForce RTX 4080 для ноутбуков"},
            {"name": "Вес", "value": "3.29 кг"},
        ],
    )
    summary = build_comparison_summary([product], request)
    raw_answer = (
        "Лидер анализа\n"
        '17.3" Ноутбук ARDOR Gaming ELEMENT L17-I9ND400 черный — 218 999 руб. '
        "Полностью соответствует всем требованиям.\n\n"
        "Альтернатива\nВ рамках текущей выборки альтернатив нет.\n\n"
        "Критическое резюме\nЯвно неудачных позиций в текущей выборке не выявлено."
    )

    checked = ensure_teacher_checked_analysis_answer(raw_answer, [product], summary)

    assert "Полностью соответствует" not in checked
    assert "противоречит карточке" in checked
    assert "вес до 2.5 кг" in checked


def test_boolean_preselect_requires_semantic_filter_name() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        constraints=constraints_from_payload({"wifi": True}),
        wishes=("wifi",),
    )
    filters_map = {
        "filters": [
            {
                "id": "f-bad",
                "name": "Отображение информации",
                "group": "Экран",
                "type": "checkbox",
                "values": [{"id": "1", "name": "LED"}],
            }
        ]
    }

    preselected, coverage = build_preselected_filters_and_coverage(request, filters_map)

    assert preselected == []
    assert coverage[0]["status"] in {"uncovered", "unverifiable"}


def test_constraints_from_payload_canonicalizes_wifi_network_to_wifi() -> None:
    request = constraints_from_payload({"network": "wifi"})

    assert request
    assert request[0].key == "wifi"
    assert request[0].value == "true"


def test_boolean_preselect_rejects_proxy_scanner_filter_name() -> None:
    request = NormalizedSearchRequest(
        product_type="mfp",
        query="мфу",
        constraints=constraints_from_payload({"scanner": True}),
        wishes=("scanner",),
    )
    filters_map = {
        "filters": [
            {
                "id": "f-scan",
                "name": "Устройство автоподачи",
                "group": "Подача документов",
                "type": "checkbox",
                "values": [{"id": "1", "name": "есть"}],
            }
        ]
    }

    preselected, coverage = build_preselected_filters_and_coverage(request, filters_map)

    assert preselected == []
    assert coverage[0]["status"] in {"uncovered", "unverifiable"}


def test_boolean_preselect_rejects_proxy_grinder_filter_name() -> None:
    request = NormalizedSearchRequest(
        product_type="coffee_machine",
        query="кофемашина",
        constraints=constraints_from_payload({"built_in_grinder": True}),
        wishes=("built_in_grinder",),
    )
    filters_map = {
        "filters": [
            {
                "id": "f-grind",
                "name": "Регулировка степени помола",
                "group": "Кофемолка",
                "type": "checkbox",
                "values": [{"id": "1", "name": "есть"}],
            }
        ]
    }

    preselected, coverage = build_preselected_filters_and_coverage(request, filters_map)

    assert preselected == []
    assert coverage[0]["status"] in {"uncovered", "unverifiable"}


def test_ensure_teacher_checked_analysis_answer_uses_filter_language_when_full_match_is_not_allowed() -> None:
    product = Product(
        "Example Smartphone",
        49999,
        "https://example/phone",
        "1",
        specs=[{"name": "Камера", "value": "50 Мп"}],
    )
    summary = {
        "leader": {
            "name": "Example Smartphone",
            "price": 49999,
            "score": 18,
            "match_status": "exact",
            "matched_hard_wishes": ["nfc"],
            "missing_hard_wishes": [],
            "contradicted_hard_wishes": [],
            "details_confirmed_all_hard_wishes": False,
        },
        "competitors": [],
        "all_candidates_rejected": False,
    }

    checked = ensure_teacher_checked_analysis_answer(
        "Лидер анализа\nExample Smartphone — 49 999 руб. Полностью соответствует всем жёстким требованиям.\n\n"
        "Альтернатива\nНет.\n\n"
        "Критическое резюме\nНет.",
        [product],
        summary,
    )

    assert "Полностью соответствует" not in checked
    assert "по карточке подтверждены основные сигналы запроса" in checked.casefold()


def test_no_products_answer_does_not_mention_brand_when_brand_not_requested() -> None:
    request = NormalizedSearchRequest(
        product_type="headphones",
        query="наушники",
        price_min=0,
        price_max=5000,
        constraints=constraints_from_payload({"wifi": True}),
        wishes=("wifi",),
        source_hard_wishes_count=1,
    )

    answer = build_no_products_analysis_answer(request, "https://example/no-match")

    assert "бренд" not in answer.casefold()
    assert "wi-fi" in answer.casefold() or "wifi" in answer.casefold()


def test_build_teacher_corrected_analysis_answer_marks_partial_or_rejected_match() -> None:
    request = normalized_search_request_from_text(
        '[ {ноутбук}, {125000:262500}, {}, {"gpu":"rtx 4080","ram":"32 gb","refresh_rate":"240 hz","weight_max":"2.5 kg","screen_finish":"matte","year":"2024"}, {} ]',
        fallback="Найди игровой ноутбук с RTX 4080, 32 ГБ ОЗУ, экраном 240 Гц, весом до 2.5 кг, с матовым покрытием экрана, до 250 000 рублей, 2024 года выпуска",
    )
    product = Product(
        '17.3" Ноутбук ARDOR Gaming ELEMENT L17-I9ND400 черный',
        218999,
        "https://example/ardor",
        "1",
        specs=[
            {"name": "Год релиза", "value": "2024"},
            {"name": "Покрытие экрана", "value": "матовое"},
            {"name": "Максимальная частота обновления экрана", "value": "240 Гц"},
            {"name": "Объем оперативной памяти", "value": "32 ГБ"},
            {"name": "Модель дискретной видеокарты", "value": "GeForce RTX 4080 для ноутбуков"},
            {"name": "Вес", "value": "3.29 кг"},
        ],
    )
    summary = build_comparison_summary([product], request)

    corrected = build_teacher_corrected_analysis_answer([product], summary)

    assert "не точное совпадение" in corrected
    assert "противоречит карточке" in corrected


def test_teacher_checked_answer_renames_leader_when_all_candidates_rejected() -> None:
    request = NormalizedSearchRequest(
        product_type="laptop",
        query="ноутбук",
        price_max=200000,
        wishes=("weight_up_to_2.3_kg",),
    )
    products = [
        Product(
            '17.3" Ноутбук MSI Katana',
            197999,
            "https://example/msi",
            "1",
            specs=[{"name": "Вес", "value": "2.7 кг"}],
        ),
        Product(
            '16" Ноутбук ASUS ROG',
            185999,
            "https://example/asus",
            "2",
            specs=[{"name": "Вес", "value": "2.5 кг"}],
        ),
    ]
    summary = build_comparison_summary(products, request)
    raw_answer = (
        "Лидер анализа\n"
        '17.3" Ноутбук MSI Katana — 197 999 руб. Лучший вариант.\n\n'
        "Альтернатива\nASUS ROG.\n\n"
        "Критическое резюме\nОба не идеальны."
    )

    checked = ensure_teacher_checked_analysis_answer(raw_answer, products, summary)

    assert "Лидер анализа" not in checked
    assert checked.startswith("Лучший вариант")
    assert "точного совпадения нет" in checked.casefold()


def test_teacher_checked_answer_strips_markdown_formatting() -> None:
    checked = ensure_teacher_checked_analysis_answer(
        "**Ближайшие аналоги**\n\n1. **Первый вариант**\n2. Второй вариант",
        [],
        {},
    )

    assert "**" not in checked
    assert "1." not in checked
    assert checked.startswith("Лучший вариант")


def test_teacher_checked_answer_preserves_decimal_screen_sizes() -> None:
    checked = ensure_teacher_checked_analysis_answer(
        'Лидер анализа\n6.57" Смартфон realme 15T 256 ГБ серый\n\n1. Второй вариант',
        [],
        {},
    )

    assert '6.57" Смартфон realme 15T 256 ГБ серый' in checked
    assert '\n1. Второй вариант' not in checked
    assert checked.startswith("Лучший вариант")


def test_build_no_products_analysis_answer_is_short_and_user_facing() -> None:
    answer = build_no_products_analysis_answer(
        NormalizedSearchRequest(
            product_type="laptop",
            query="ноутбук",
            price_min=0,
            price_max=200000,
            wishes=(
                "rtx_4070_or_higher",
                "32gb_ram",
                "refresh_rate_from_165hz",
                "matte_screen",
                "year_from_2024",
                "weight_up_to_2.3_kg",
            ),
        ),
        "https://www.dns-shop.ru/search/?q=%D0%BD%D0%BE%D1%83%D1%82%D0%B1%D1%83%D0%BA&category=17a892f816404e77",
    )

    assert "По заданным фильтрам товаров не найдено." in answer
    assert "Точного совпадения нет: одновременно не нашлось модели с" in answer
    assert "RTX 4070 или выше" in answer
    assert "32 ГБ ОЗУ" in answer
    assert "экран от 165 Гц" in answer
    assert "матовое покрытие" in answer
    assert "2024 год выпуска или новее" in answer
    assert "вес до 2.3 кг" in answer
    assert "бюджетом до 200 000 ₽" in answer
    assert "вес" in answer
    assert "бюджет" in answer
    assert "объём ОЗУ" in answer
    assert "https://www.dns-shop.ru" not in answer
    assert "в DNS нет подходящих моделей" not in answer
    assert "обычно стоят дороже" not in answer


def test_build_no_products_analysis_answer_uses_request_specific_relaxations() -> None:
    answer = build_no_products_analysis_answer(
        NormalizedSearchRequest(
            product_type="smartphone",
            query="смартфон",
            price_min=0,
            price_max=80000,
            wishes=("storage_from_256_gb", "12gb_ram", "refresh_rate_from_120hz", "matrix_type_amoled", "network_5g"),
        ),
        "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD",
    )

    assert "вес" not in answer
    assert "бюджет" in answer
    assert "объём памяти" in answer
    assert "объём ОЗУ" in answer


def test_normalized_search_request_uses_short_product_query() -> None:
    plan = normalized_search_request_from_text(
        '{"product_type":"smartphone","query":"Найди смартфон с AMOLED-экраном от 120 Гц и памятью от 256 ГБ","price_min":0,"price_max":80000,"brand":"","constraints":[{"key":"matrix_type","op":"==","value":"amoled","unit":"","source_text":"AMOLED-экраном"}],"soft_wishes":["good_camera","good_battery"]}',
        fallback="Найди смартфон с AMOLED-экраном от 120 Гц, памятью от 256 ГБ, оперативной памятью от 12 ГБ, поддержкой 5G, NFC, защитой не ниже IP68, быстрой зарядкой, хорошей камерой и хорошей автономностью, не старше 2024 года, бюджет до 80 000 рублей",
    )

    assert plan.query == "смартфон"
    assert "120 Гц" not in plan.query
    assert "256 ГБ" not in plan.query


def test_normalized_search_request_keeps_ranking_policy_and_price_band_hint() -> None:
    plan = normalized_search_request_from_text(
        '{"product_type":"smartphone","query":"найти самый мощный смартфон по цена/качество","price_min":null,"price_max":100000,"brand":"","constraints":[],"soft_wishes":["good_camera"],"ranking_policy":"value","price_band_hint":"mid_to_max"}',
        fallback="найти самый мощьный смартфон по цена/качество, ценой от средней до 100к, лучше с хорошей камерой",
    )

    assert plan.query == "смартфон"
    assert plan.price_min is None
    assert plan.price_max == 100000
    assert plan.soft_wishes == ("good_camera",)
    assert plan.ranking_policy == "value"
    assert plan.price_band_hint == "mid_to_max"


def test_rank_products_for_request_avoids_ultrabudget_for_mid_to_max_value_search() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        price_max=100000,
        soft_wishes=("good_camera",),
        ranking_policy="value",
        price_band_hint="mid_to_max",
    )
    cheap = Product(
        "Tecno SPARK 20",
        6199,
        "https://example/cheap",
        "1",
        specs=[
            {"name": "Камера", "value": "108 Мп"},
            {"name": "AnTuTu", "value": "380000"},
        ],
    )
    mid = Product(
        "Xiaomi 14T",
        54999,
        "https://example/mid",
        "2",
        specs=[
            {"name": "Камера", "value": "50 Мп"},
            {"name": "AnTuTu", "value": "1450000"},
        ],
    )
    top = Product(
        "iQOO Neo 10",
        99999,
        "https://example/top",
        "3",
        specs=[
            {"name": "Камера", "value": "50 Мп"},
            {"name": "AnTuTu", "value": "1650000"},
        ],
    )

    ranked = rank_products_for_request([cheap, mid, top], request)

    assert ranked[0].name == "Xiaomi 14T"


def test_build_teacher_corrected_analysis_answer_uses_exact_leader_language_without_full_match_claim() -> None:
    leader = {
        "name": "Xiaomi 15",
        "price": 49999,
        "score": 48,
        "match_status": "exact",
        "missing_hard_wishes": [],
        "contradicted_hard_wishes": [],
    }
    comparison_summary = {
        "leader": leader,
        "competitors": [],
    }
    product = Product("Xiaomi 15", 49999, "https://example/xiaomi", "1", specs=[])

    answer = build_teacher_corrected_analysis_answer([product], comparison_summary)

    assert "безальтернативный лидер" not in answer.casefold()
    assert "по карточке подтверждены основные сигналы запроса" in answer.casefold()
    assert "по автономности сильнее Vivo iQOO 15" not in answer
    assert "Лидер анализа" not in answer
    assert "Альтернатива" not in answer
    assert "Критическое резюме" not in answer
    assert answer.startswith("Лучший вариант")


def test_build_teacher_corrected_analysis_answer_uses_nearest_matches_for_partial_no_hit_leader() -> None:
    leader = {
        "name": "DEXP B4-35AMA",
        "price": 25999,
        "score": 2,
        "match_status": "partial",
        "matched_hard_wishes": [],
        "missing_hard_wishes": ["cooling_system_no_frost", "width_up_to_60_cm"],
        "contradicted_hard_wishes": [],
    }
    comparison_summary = {
        "leader": leader,
        "competitors": [],
    }
    product = Product("DEXP B4-35AMA", 25999, "https://example/dexp", "1", specs=[])

    answer = build_teacher_corrected_analysis_answer([product], comparison_summary)

    assert answer.startswith("Лучший вариант")
    assert "Точного совпадения нет." in answer
    assert "Лидер анализа" not in answer


def test_build_teacher_corrected_analysis_answer_hides_internal_segment_labels() -> None:
    comparison_summary = {
        "segment_leaders": {
            "price_leader": {"name": "Model A", "price": 29999, "score": 21},
            "value_leader": {"name": "Model B", "price": 35999, "score": 25},
            "spec_leader": {"name": "Model C", "price": 41999, "score": 29},
        },
        "use_segment_leaders": True,
    }

    answer = build_teacher_corrected_analysis_answer([], comparison_summary)

    assert "spec_leader" not in answer
    assert "value_leader" not in answer
    assert "price_leader" not in answer
    assert "Лидер анализа" not in answer
    assert "fit_score" not in answer


def test_build_teacher_corrected_analysis_answer_gives_concrete_value_leader_reasoning() -> None:
    request = NormalizedSearchRequest(
        product_type="smartphone",
        query="смартфон",
        price_max=100000,
        soft_wishes=("good_camera",),
        ranking_policy="value",
        price_band_hint="mid_to_max",
    )
    products = [
        Product(
            '6.77" Смартфон Vivo V50 512 ГБ фиолетовый',
            36299,
            "https://example/vivo-v50",
            "1",
            specs=[
                {"name": "Встроенная память", "value": "512 ГБ"},
                {"name": "Основная камера", "value": "50 МП"},
                {"name": "Процессор", "value": "Snapdragon 7 Gen 3"},
            ],
        ),
        Product(
            '6.8" Смартфон realme 15 Pro 256 ГБ зеленый',
            36999,
            "https://example/realme-15-pro",
            "2",
            specs=[
                {"name": "Встроенная память", "value": "256 ГБ"},
                {"name": "Основная камера", "value": "50 МП"},
                {"name": "Процессор", "value": "Snapdragon 7+ Gen 3"},
            ],
        ),
        Product(
            '6.67" Смартфон POCO X7 Pro 512 ГБ желтый',
            37999,
            "https://example/poco-x7-pro",
            "3",
            specs=[
                {"name": "Встроенная память", "value": "512 ГБ"},
                {"name": "Основная камера", "value": "50 МП"},
                {"name": "Процессор", "value": "Dimensity 8400 Ultra"},
            ],
        ),
    ]

    summary = build_comparison_summary(products, request)

    answer = build_teacher_corrected_analysis_answer(products, summary)

    assert answer.startswith("Лучший вариант")
    assert str(summary["leader"]["name"]) in answer
    assert "средн" in answer.casefold()
    assert "хорош" in answer.casefold() and "камер" in answer.casefold()
    assert "realme 15 Pro" in answer or "POCO X7 Pro" in answer
    assert "сегментный ориентир" not in answer.casefold()


def test_extract_request_facts_for_entry_prefers_concrete_camera_specs_for_value_request() -> None:
    product = Product(
        '6.7" Смартфон HONOR 200 512 ГБ черный',
        36999,
        "https://example/honor-200",
        "honor-200",
        specs=[
            {"name": "Количество мегапикселей основной камеры", "value": "200+12+50 Мп"},
            {"name": "Количество мегапикселей фронтальной камеры", "value": "50 Мп"},
            {"name": "Модель сенсора основной камеры", "value": "Samsung ISOCELL HP3"},
            {"name": "Количество основных (тыловых) камер", "value": "3"},
            {"name": "Апертура основной камеры", "value": "f/1.9, f/2.2, f/2.4"},
            {"name": "Угол обзора объектива", "value": "112°"},
            {"name": "Объем встроенной памяти", "value": "512 ГБ"},
        ],
    )

    facts = extract_request_facts_for_entry(
        {"name": product.name, "url": product.url, "code": product.code, "price": product.price},
        [product],
        {"ranking_policy": "value", "soft_wishes": ["good_camera"]},
    )

    assert "основная камера 200+12+50 Мп" in facts
    assert "сенсор основной камеры Samsung ISOCELL HP3" in facts
    assert all("камера 3" != fact for fact in facts)
    assert all("апертура" not in fact.casefold() for fact in facts)
    assert all("112°" not in fact for fact in facts)


def test_build_teacher_corrected_analysis_answer_display_alternative_does_not_claim_lower_price_when_it_is_higher() -> None:
    request = NormalizedSearchRequest(
        product_type="laptop",
        query="ноутбук",
        soft_wishes=("bright_screen",),
        ranking_policy="display",
    )
    products = [
        Product(
            '18" Ноутбук ASUS Vivobook 18 M1807HA-S8091 синий',
            94999,
            "https://example/asus18",
            "asus18",
            specs=[
                {"name": "Диагональ экрана", "value": '18"'},
                {"name": "Яркость", "value": "300 Кд/м²"},
            ],
        ),
        Product(
            '16" Ноутбук ASUS Vivobook S M5606WA-MX019W черный',
            154999,
            "https://example/asus16",
            "asus16",
            specs=[
                {"name": "Диагональ экрана", "value": '16"'},
                {"name": "Яркость", "value": "600 Кд/м²"},
            ],
        ),
    ]
    summary = {
        "leader": {"name": products[0].name, "price": products[0].price, "url": products[0].url, "code": products[0].code, "match_status": "partial"},
        "competitors": [{"name": products[1].name, "price": products[1].price, "url": products[1].url, "code": products[1].code}],
        "request_profile": {
            "ranking_policy": request.ranking_policy,
            "soft_wishes": list(request.soft_wishes),
        },
    }

    answer = build_teacher_corrected_analysis_answer(products, summary)

    assert "более низкой ценой" not in answer
    assert "в сторону цены" not in answer
    assert "яркость 600 Кд/м²" in answer


def test_ensure_teacher_checked_analysis_answer_rewrites_inner_leader_heading_for_nearest_matches() -> None:
    comparison_summary = {
        "leader": {
            "name": "DEXP B4-35AMA",
            "price": 25999,
            "score": 2,
            "match_status": "partial",
            "matched_hard_wishes": [],
            "missing_hard_wishes": ["cooling_system_no_frost"],
            "contradicted_hard_wishes": [],
        },
        "competitors": [],
    }
    raw_answer = (
        "Ближайшие аналоги\n\n"
        "Лидер анализа — DEXP B4-35AMA, 25 999 руб. Точного совпадения нет.\n\n"
        "Альтернатива\nНет.\n\n"
        "Критическое резюме\nНет."
    )

    corrected = ensure_teacher_checked_analysis_answer(raw_answer, [Product("DEXP", 1, "https://example/dexp", "1", specs=[])], comparison_summary)

    assert corrected.startswith("Лучший вариант")
    assert "Лидер анализа —" not in corrected


def test_ensure_teacher_checked_analysis_answer_rewrites_raw_structured_json() -> None:
    comparison_summary = {
        "leader": {
            "name": "Samsung Galaxy A55",
            "price": 49999,
            "score": 42,
            "match_status": "exact",
            "matched_hard_wishes": ["brand", "matrix_type"],
            "missing_hard_wishes": [],
            "contradicted_hard_wishes": [],
        },
        "competitors": [],
    }
    raw_answer = '{"selected_codes":["123"],"reason":"raw"}'

    checked = ensure_teacher_checked_analysis_answer(
        raw_answer,
        [Product("Samsung Galaxy A55", 49999, "https://example/a55", "1", specs=[])],
        comparison_summary,
    )

    assert checked
    assert "selected_codes" not in checked
    assert checked.startswith("Лучший вариант")


def test_analysis_product_payload_hides_raw_specs_and_keeps_highlights() -> None:
    request = normalized_search_request_from_text(
        '[ {монитор}, {17500:36750}, {}, {"panel":"ips","height_adjustment":"yes"}, {} ]',
        fallback="Найди монитор для программиста с IPS и регулировкой высоты",
    )
    product = Product(
        "ASUS ProArt PA278CGV",
        31999,
        "https://example/a",
        "1",
        specs=[
            {"name": "Диагональ", "value": '27"'},
            {"name": "Матрица", "value": "IPS"},
        ],
    )

    payload = analysis_product_payload(product, request)

    assert "specs" not in payload
    assert "key_specs" not in payload
    assert payload["highlights"]
    assert "verified_facts" in payload


def test_analysis_product_payload_includes_compact_verified_facts_for_monitor_interfaces() -> None:
    request = normalized_search_request_from_text(
        '[ {монитор}, {17500:36750}, {}, {"size":"27 inch","resolution":"1440p","panel":"ips","height_adjustment":"yes"}, {} ]',
        fallback="Найди монитор для программиста 27 дюймов 1440p IPS с регулировкой высоты",
    )
    product = Product(
        "ASUS ProArt PA278CGV",
        31999,
        "https://example/asus",
        "1",
        specs=[
            {"name": "Диагональ экрана (дюйм)", "value": '27"'},
            {"name": "Максимальное разрешение", "value": "2560x1440"},
            {"name": "Тип матрицы", "value": "IPS"},
            {"name": "Регулировка по высоте", "value": "есть"},
            {"name": "USB-концентратор", "value": "есть"},
            {"name": "Поддержка USB Power Delivery", "value": "есть"},
            {"name": "Мощность зарядки USB Power Delivery", "value": "90 Вт"},
            {"name": "Тип, версия и количество видеоразъемов", "value": "DisplayPort 1.4, HDMI 2.0 x2, USB Type-C"},
        ],
    )

    payload = analysis_product_payload(product, request)

    assert payload["verified_facts"]["usb_type_c"] is True
    assert payload["verified_facts"]["usb_hub"] is True
    assert payload["verified_facts"]["usb_power_delivery"] is True
    assert payload["verified_facts"]["usb_power_delivery_watts"] == 90
    assert payload["verified_facts"]["height_adjustable"] is True


def test_analysis_product_payload_does_not_emit_useless_negative_highlights() -> None:
    request = normalized_search_request_from_text(
        '[ {монитор}, {17500:36750}, {}, {"size":"27 inch","resolution":"1440p","panel":"ips","height_adjustment":"yes"}, {} ]',
        fallback="Найди монитор 27 дюймов 1440p IPS с регулировкой высоты",
    )
    product = Product(
        "27\" Монитор LG",
        31999,
        "https://example/lg",
        "1",
        specs=[
            {"name": "Тип матрицы", "value": "IPS"},
            {"name": "Регулировка по высоте", "value": "нет"},
            {"name": "Категория", "value": "монитор"},
        ],
    )

    payload = analysis_product_payload(product, request)

    assert "важный признак: нет" not in payload["highlights"]
    assert "важный признак: монитор" not in payload["highlights"]


def test_orchestrator_logs_human_ai_chain_for_product_search(tmp_path: Path, caplog) -> None:
    asyncio.run(run_orchestrator_logs_human_ai_chain_for_product_search(tmp_path, caplog))


async def run_orchestrator_logs_human_ai_chain_for_product_search(tmp_path: Path, caplog) -> None:
    def parser(input_value: str, limit: int | None):
        return (
            [Product("Клавиатура A", 1000, "https://example/a", "1")],
            "httpx",
            input_value,
            input_value,
        )

    def fetch_specs(urls):
        return [
            {
                "url": "https://example/a",
                "characteristics_url": "https://example/specs-a",
                "specs": [{"name": "Тип", "value": "механическая"}],
            }
        ]

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "клавиатура",
            "category": "17a8950d16404e77",
            "count": 1,
            "filters": [
                {
                    "id": "f[1bm]",
                    "name": "Тип клавиатуры",
                    "type": "checkbox",
                    "values": [{"id": "mech", "name": "механическая", "count": 5}],
                }
            ],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "intent_route" in content:
            yield '{"mode":"product_search","response_style":"structured","reason":"new_search"}'
            return
        if "normalize_query" in content:
            yield '[ {клавиатура}, {}, {}, {"keyboard_type":"mechanical"}, {} ]'
            return
        if "filters_patch" in content:
            yield '{"filters":[{"name":"Тип клавиатуры","values":[{"name":"механическая"}]}]}'
            return
        if "shortlist" in content:
            yield '{"selected_urls":["https://example/a"],"reasons":["лучше по запросу"]}'
            return
        yield "Подходит"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0&category=17a8950d16404e77",
    )

    caplog.set_level(logging.INFO, logger="dns_bot.orchestrator")
    await orchestrator.handle_message(
        "найди магнитную клавиатуру",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    steps = [
        record.message.split("step=", 1)[1].split()[0]
        for record in caplog.records
        if "ai_chain_step step=" in record.message
    ]
    assert steps == [
        "category_and_filters",
        "request",
        "category_and_filters",
        "category_and_filters",
        "filters_ai",
        "built_url",
        "list",
        "shortlist_ai",
        "details",
        "final_ai",
        "output",
    ]


def test_orchestrator_shortlists_full_list_but_fetches_specs_only_for_selected(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_shortlists_full_list_but_fetches_specs_only_for_selected(tmp_path))


async def run_orchestrator_shortlists_full_list_but_fetches_specs_only_for_selected(tmp_path: Path) -> None:
    calls = {}
    stages: list[str] = []
    products = [
        Product(f"Смартфон {index}", 10000 + index, f"https://example/{index}", str(index))
        for index in range(120)
    ]

    def parser(input_value: str, limit: int | None):
        calls["limit"] = limit
        return (products, "httpx", input_value, input_value)

    def fetch_specs(urls):
        calls["specs_urls"] = urls
        return [{"url": url, "characteristics_url": f"{url}/specs", "specs": [{"name": "Память", "value": "256"}]} for url in urls]

    def inspect_filters(section_url: str):
        calls["section_url"] = section_url
        return {
            "section_url": section_url,
            "query": "смартфон",
            "category": "cat",
            "count": 1,
            "filters": [],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "intent_route" in content:
            yield '{"mode":"product_search","response_style":"structured","reason":"new_search"}'
            return
        if "filters_patch" in content:
            yield '{"filters":[]}'
            return
        if "shortlist" in content:
            selected = [f"https://example/{index}" for index in range(5)]
            yield json.dumps({"selected_urls": selected, "reasons": ["релевантность"]}, ensure_ascii=False)
            return
        if "normalize_query" in content:
            yield "[ {смартфон}, {}, {}, {}, {} ]"
            return
        yield "Финальный ответ"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&category=cat",
    )

    result = await orchestrator.handle_message(
        "найди смартфон",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=stages.append,
    )

    assert calls["limit"] is None
    assert calls["section_url"] == "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&category=cat"
    assert set(calls["specs_urls"]) == {f"https://example/{index}" for index in range(5)}
    assert len(calls["specs_urls"]) == 5


def test_attach_characteristics_reuses_existing_detailed_specs() -> None:
    calls = {"count": 0}

    def fetch_specs(_urls):
        calls["count"] += 1
        return []

    orchestrator = ProductAnalysisOrchestrator(
        stream_chat=lambda _messages: (_ for _ in ()),
        normalize_stream_chat=lambda _messages: (_ for _ in ()),
        characteristics_fetcher=fetch_specs,
    )
    selected = [
        Product(
            "LG 27BA65QB-B",
            31999,
            "https://example/lg",
            "1",
            specs=[
                {"name": "Гарантия продавца / производителя", "value": "24 мес."},
                {"name": "Модель", "value": "LG 27BA65QB-B"},
                {"name": "Диагональ экрана (дюйм)", "value": '27"'},
                {"name": "Максимальное разрешение", "value": "2560x1440"},
                {"name": "Тип матрицы", "value": "IPS"},
                {"name": "Регулировка по высоте", "value": "есть"},
                {"name": "Регулировка наклона", "value": "есть"},
                {"name": "Поворот на 90° (портретный режим)", "value": "есть"},
                {"name": "Размер VESA", "value": "100 x 100"},
                {"name": "Яркость", "value": "350 Кд/м²"},
                {"name": "Контрастность", "value": "1000:1"},
                {"name": "Видеоразъемы", "value": "HDMI, DisplayPort, USB Type-C"},
            ],
        )
    ]

    enriched = orchestrator.attach_characteristics(selected, selected)

    assert calls["count"] == 0
    assert enriched[0].specs == selected[0].specs


def test_attach_characteristics_fetches_full_specs_for_summary_cards() -> None:
    calls = {"count": 0}

    def fetch_specs(_urls):
        calls["count"] += 1
        return [{"url": "https://example/lg", "specs": [{"name": "Регулировка по высоте", "value": "есть"}]}]

    orchestrator = ProductAnalysisOrchestrator(
        stream_chat=lambda _messages: (_ for _ in ()),
        normalize_stream_chat=lambda _messages: (_ for _ in ()),
        characteristics_fetcher=fetch_specs,
    )
    selected = [
        Product(
            "LG 27BA65QB-B",
            31999,
            "https://example/lg",
            "1",
            specs=[{"name": "Тип матрицы", "value": "IPS"}],
        )
    ]

    enriched = orchestrator.attach_characteristics(selected, selected)

    assert calls["count"] == 1
    assert enriched[0].specs == [{"name": "Регулировка по высоте", "value": "есть"}]


def test_orchestrator_reuses_memory_context_for_direct_follow_up(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_reuses_memory_context_for_direct_follow_up(tmp_path))


async def run_orchestrator_reuses_memory_context_for_direct_follow_up(tmp_path: Path) -> None:
    calls = {"parser": 0, "specs": 0}

    def parser(input_value: str, limit: int | None):
        calls["parser"] += 1
        return ([], "httpx", input_value, input_value)

    def fetch_specs(urls):
        calls["specs"] += 1
        return []

    async def stream(messages):
        if "intent_route" in messages[-1]["content"]:
            yield '{"mode":"product_followup","response_style":"direct","reason":"memory_question"}'
            return
        yield "HONOR Pad X8a надежнее за счет более высокой частоты процессора."

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
    )

    result = await orchestrator.handle_message(
        "а какой по мощности лучший",
        history=[{"role": "user", "content": "Планшет от 10к до 12к"}],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
        memory_context={
            "resolved_url": "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82",
            "stats": {"filtered_count": 2},
            "products": [
                {
                    "name": "HONOR Pad X8a",
                    "price": 11499,
                    "url": "https://example/a",
                    "code": "1",
                    "specs": [{"name": "Процессор", "value": "8 ядер, 2.4 ГГц"}],
                },
                {
                    "name": "Samsung Galaxy Tab A11",
                    "price": 10999,
                    "url": "https://example/b",
                    "code": "2",
                    "specs": [{"name": "Процессор", "value": "8 ядер, 2.2 ГГц"}],
                },
            ],
        },
    )

    assert calls["parser"] == 0
    assert calls["specs"] == 0
    assert "Лидер анализа" not in result.answer
    assert "HONOR Pad X8a" in result.answer
    assert result.image_paths == []
    assert result.products_count == 2


def test_orchestrator_handles_general_chat_without_parser(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_handles_general_chat_without_parser(tmp_path))


async def run_orchestrator_handles_general_chat_without_parser(tmp_path: Path) -> None:
    calls = {"parser": 0}

    def parser(input_value: str, limit: int | None):
        calls["parser"] += 1
        return ([], "httpx", input_value, input_value)

    async def stream(messages):
        if "intent_route" in messages[-1]["content"]:
            yield '{"mode":"general_chat","response_style":"direct","reason":"small_talk"}'
            return
        yield "Меня зовут DNS AI bot."

    async def chat(messages):
        content = messages[-1]["content"]
        if '"draft_answer"' in content:
            return "Я помощник в этом боте."
        return "Меня зовут DNS AI bot."

    orchestrator = ProductAnalysisOrchestrator(parser=parser, stream_chat=stream, chat=chat, report_dir=tmp_path)

    result = await orchestrator.handle_message(
        "как тебя зовут",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert calls["parser"] == 0
    assert result.answer == "Я помощник в этом боте."
    assert result.image_paths == []
    assert result.products_count == 0


def test_orchestrator_uses_structured_follow_up_with_memory(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_uses_structured_follow_up_with_memory(tmp_path))


async def run_orchestrator_uses_structured_follow_up_with_memory(tmp_path: Path) -> None:
    calls = {"parser": 0}

    def parser(input_value: str, limit: int | None):
        calls["parser"] += 1
        return ([], "httpx", input_value, input_value)

    async def stream(messages):
        if "intent_route" in messages[-1]["content"]:
            yield '{"mode":"product_followup","response_style":"structured","reason":"summary"}'
            return
        yield "Лидер анализа\nSSD A\n\nАльтернатива\nSSD B\n\nКритическое резюме\n• SSD C"

    orchestrator = ProductAnalysisOrchestrator(parser=parser, stream_chat=stream, report_dir=tmp_path)

    result = await orchestrator.handle_message(
        "сделай итог по этим SSD",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
        memory_context={
            "resolved_url": "https://www.dns-shop.ru/search/?q=ssd",
            "stats": {"filtered_count": 3},
            "products": [
                {"name": "SSD A", "price": 10000, "url": "https://example/a", "code": "1", "specs": []},
                {"name": "SSD B", "price": 11000, "url": "https://example/b", "code": "2", "specs": []},
                {"name": "SSD C", "price": 12000, "url": "https://example/c", "code": "3", "specs": []},
            ],
        },
    )

    assert calls["parser"] == 0
    assert result.answer.startswith("Лучший вариант")
    assert "Лидер анализа" not in result.answer
    assert result.image_paths == []
    assert result.context_payload["resolved_url"] == "https://www.dns-shop.ru/search/?q=ssd"


def test_orchestrator_applies_teacher_pack_to_direct_followup(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_applies_teacher_pack_to_direct_followup(tmp_path))


async def run_orchestrator_applies_teacher_pack_to_direct_followup(tmp_path: Path) -> None:
    async def stream(messages):
        if "intent_route" in messages[-1]["content"]:
            yield '{"mode":"product_followup","response_style":"direct","reason":"format_followup"}'
            return
        yield "1. SSD A лучше.\n2. SSD B дешевле.\n3. SSD C слабее."

    async def chat(messages):
        content = messages[-1]["content"]
        if '"draft_answer"' in content:
            return "SSD A лучше, SSD B дешевле, SSD C слабее."
        return "1. SSD A лучше.\n2. SSD B дешевле.\n3. SSD C слабее."

    orchestrator = ProductAnalysisOrchestrator(stream_chat=stream, chat=chat, report_dir=tmp_path)
    result = await orchestrator.handle_message(
        "Ответь без списка, одним абзацем и в 2 предложениях.",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
        memory_context={
            "resolved_url": "https://www.dns-shop.ru/search/?q=ssd",
            "stats": {"filtered_count": 3},
            "products": [
                {"name": "SSD A", "price": 10000, "url": "https://example/a", "code": "1", "specs": []},
                {"name": "SSD B", "price": 11000, "url": "https://example/b", "code": "2", "specs": []},
                {"name": "SSD C", "price": 12000, "url": "https://example/c", "code": "3", "specs": []},
            ],
        },
    )

    assert result.answer == "SSD A лучше, SSD B дешевле, SSD C слабее."


def test_orchestrator_fills_empty_sections_from_shortlist(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_fills_empty_sections_from_shortlist(tmp_path))


async def run_orchestrator_fills_empty_sections_from_shortlist(tmp_path: Path) -> None:
    def parser(input_value: str, limit: int | None):
        return (
            [
                Product("HONOR Pad X8a", 11499, "https://example/a", "1"),
                Product("Samsung Galaxy Tab A11", 10999, "https://example/b", "2"),
                Product("Xiaomi Redmi Pad 2", 13499, "https://example/c", "3"),
            ],
            "httpx",
            input_value,
            input_value,
        )

    def fetch_specs(urls):
        return [
            {"url": "https://example/a", "characteristics_url": "https://example/specs-a", "specs": [{"name": "Процессор", "value": "8 ядер, 2.4 ГГц"}]},
            {"url": "https://example/b", "characteristics_url": "https://example/specs-b", "specs": [{"name": "Процессор", "value": "8 ядер, 2.2 ГГц"}]},
            {"url": "https://example/c", "characteristics_url": "https://example/specs-c", "specs": [{"name": "ОЗУ", "value": "4 ГБ"}]},
        ]

    def inspect_filters(section_url: str):
        return {
            "section_url": section_url,
            "query": "планшет",
            "category": "cat",
            "count": 1,
            "filters": [{"id": "price", "name": "Цена", "type": "range-checkbox", "values": []}],
        }

    async def stream(messages):
        content = messages[-1]["content"]
        if "intent_route" in content:
            yield '{"mode":"product_search","response_style":"structured","reason":"new_search"}'
            return
        if "query_plan" in content:
            yield '{"query":"планшет"}'
            return
        if "filters_patch" in content:
            yield '{"filters":[{"name":"Цена","min":10000,"max":12000}]}'
            return
        if "shortlist" in content:
            yield '{"selected_urls":["https://example/a","https://example/b","https://example/c"],"reasons":["релевантность"]}'
            return
        yield "Лидер анализа\n\nАльтернатива\n\nКритическое резюме"

    orchestrator = ProductAnalysisOrchestrator(
        parser=parser,
        stream_chat=stream,
        normalize_stream_chat=stream,
        report_dir=tmp_path,
        characteristics_fetcher=fetch_specs,
        section_filters_inspector=inspect_filters,
        section_url_resolver=lambda requested_url: "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82&category=cat",
    )

    result = await orchestrator.handle_message(
        "найди планшет от 10000 до 12000",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
    )

    assert result.answer.startswith("Лучший вариант")
    assert "Почему он подходит" in result.answer
    assert "Что сильнее у альтернатив" in result.answer
    assert "Компромиссы и проверки" in result.answer
    assert "Лидер анализа" not in result.answer


def test_orchestrator_followup_does_not_load_filters_again(tmp_path: Path) -> None:
    asyncio.run(run_orchestrator_followup_does_not_load_filters_again(tmp_path))


async def run_orchestrator_followup_does_not_load_filters_again(tmp_path: Path) -> None:
    calls = {"filters": 0}

    def inspect_filters(_section_url: str):
        calls["filters"] += 1
        return {}

    async def stream(messages):
        if "intent_route" in messages[-1]["content"]:
            yield '{"mode":"product_followup","response_style":"direct","reason":"memory_question"}'
            return
        yield "Лучший по экрану — планшет A."

    orchestrator = ProductAnalysisOrchestrator(
        stream_chat=stream,
        report_dir=tmp_path,
        section_filters_inspector=inspect_filters,
    )

    await orchestrator.handle_message(
        "какой лучше по экрану",
        history=[],
        on_text_chunk=lambda chunk: None,
        on_stage=lambda stage: None,
        memory_context={
            "resolved_url": "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82&category=cat",
            "section_url": "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82&category=cat",
            "filters_map_summary": {"count": 5, "filters": []},
            "stats": {},
            "products": [
                {"name": "планшет A", "price": 10000, "url": "https://example/a", "code": "1", "specs": []},
            ],
        },
    )

    assert calls["filters"] == 0
