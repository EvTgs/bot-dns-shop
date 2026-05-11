from app.ai_orchestrator import build_normalized_search_request_from_fallback
from app.dns_search_parser import build_dns_url_from_section_filters


def test_keyboard_bot_keeps_budget_without_price_filter_block() -> None:
    request = build_normalized_search_request_from_fallback("магнитная клавиатура до 3к лучше 75-80 процентов")
    url = build_dns_url_from_section_filters(
        "https://www.dns-shop.ru/search/?q=клавиатура&category=17a8950d16404e77",
        [{"id": "price", "min": request.price_min or 0, "max": request.price_max}],
        [],
    )

    assert request.price_max == 3000
    assert "price=0-3000" in url


def test_monitor_bot_understands_2k_as_1440p_not_budget() -> None:
    request = build_normalized_search_request_from_fallback("игровой монитор 27 дюймов 2к до 35 тысяч")

    assert request.product_type == "monitor"
    assert request.price_max == 35000
    assert "1440p" in request.wishes
    assert "27_inch" in request.wishes
