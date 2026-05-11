from __future__ import annotations

from ..telegram_text import trim_telegram_text


def build_tech_answer(result: object, user_text: str | None = None) -> str:
    """Build the final user-facing /tech answer with DNS compare or product links."""

    payload = result.context_payload if isinstance(getattr(result, "context_payload", None), dict) else {}
    comparison = payload.get("comparison_summary", {}) if isinstance(payload.get("comparison_summary"), dict) else {}
    products = payload.get("products", [])
    codes = extract_codes(products)
    if not codes:
        codes = extract_codes(comparison.get("other_candidates", []))
    if not codes:
        top_pick = comparison.get("top_pick", comparison.get("leader", {}))
        price_pick = comparison.get("price_pick", comparison.get("price_leader", {}))
        for item in (top_pick, price_pick):
            if isinstance(item, dict):
                code = str(item.get("code", "")).strip()
                if code and code not in codes:
                    codes.append(code)
    compare_url = compare_url_from_codes(codes)
    lines = [format_final_answer(getattr(result, "answer", ""))]
    if compare_url:
        lines.extend(["", "Таблица сравнения DNS", compare_url])
    elif direct_url := first_product_url(products):
        lines.extend(["", "Ссылка на товар DNS", direct_url])
    elif user_text:
        lines.extend(["", "Таблица сравнения DNS", "Не удалось собрать compare-ссылку по текущему набору товаров."])
    return trim_telegram_text("\n".join(lines))


def extract_codes(items: object) -> list[str]:
    """Return unique DNS product codes from product-like dictionaries."""

    codes: list[str] = []
    if not isinstance(items, list):
        return codes
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def compare_url_from_codes(codes: list[str]) -> str:
    """Build a DNS compare URL for two to five product codes."""

    normalized = [code for code in codes if code]
    if len(normalized) < 2:
        return ""
    joined = "%2C".join(normalized[:5])
    return f"https://www.dns-shop.ru/compare/?cityId=128&ids={joined}"


def first_product_url(items: object) -> str:
    """Return the first direct DNS product URL from product-like dictionaries."""

    if not isinstance(items, list):
        return ""
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if url:
            return url
    return ""


def format_final_answer(text: str) -> str:
    """Normalize empty final model answers for Telegram output."""

    cleaned = str(text or "").strip()
    return cleaned if cleaned else "Ответ пуст."
