from __future__ import annotations

import re


PRICE_RANGE_RE = re.compile(
    r"(?:(?P<approx>около|примерно|приблизительно)\s+)?(?:от\s+|между\s+)?(?P<first>\d{1,3}(?:\s\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<first_suffix>к|k|тыс(?:\.|яч(?:а|и|)?)?)?\s*(?:-|–|—|до|и)\s*(?P<second>\d{1,3}(?:\s\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<second_suffix>к|k|тыс(?:\.|яч(?:а|и|)?)?)?",
    re.IGNORECASE,
)
PRICE_SINGLE_RE = re.compile(
    r"\b(?P<kind>не\s+дороже|не\s+выше|не\s+дешевле|не\s+ниже|чуть\s+дешевле|чуть\s+дороже|сильно\s+дешевле|сильно\s+дороже|до|от|около|примерно|приблизительно|за|>=|<=)\s+(?:за\s+)?(?P<value>\d{1,3}(?:\s\d{3})+|\d+(?:[.,]\d+)?)\s*(?P<suffix>к|k|тыс(?:\.|яч(?:а|и|)?)?)?\b",
    re.IGNORECASE,
)
PRICE_CURRENCY_HINT_RE = re.compile(r"(руб|р\b|₽|тыс|тысяч|тысячи|к\b|k\b)", re.IGNORECASE)
PRICE_FORBIDDEN_SUFFIX_RE = re.compile(r"^\s*(?:%|процент\w*|кг|г|гр|гц|hz|дюйм|дюйма|дюймов|inch|in|см|мм|mah|мah|tb|gb|гб)\b", re.IGNORECASE)
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
PRICE_BUCKET_TEXT_RE = re.compile(
    r"\b(?:средней цены|средняя цена|средней стоимости|средняя стоимость|среднего ценового сегмента|средний ценовой сегмент|"
    r"среднего бюджета|средний бюджет|дешев(?:ый|ая|ое|ые)?|недорог(?:ой|ая|ое|ие)?|бюджетн(?:ый|ая|ое|ые)?)\b",
    re.IGNORECASE,
)

DEFAULT_PRICE_BUCKET_RANGES: dict[str, tuple[int, int]] = {
    "budget": (8000, 20000),
    "mid": (15000, 30000),
    "premium": (30000, 60000),
}
PRICE_BUCKET_RANGES_BY_PRODUCT_TYPE: dict[str, dict[str, tuple[int, int]]] = {
    "gamingchair": {"budget": (7000, 14000), "mid": (14000, 28000), "premium": (28000, 60000)},
    "monitor": {"budget": (12000, 20000), "mid": (20000, 35000), "premium": (35000, 60000)},
    "smartphone": {"budget": (10000, 20000), "mid": (20000, 40000), "premium": (40000, 80000)},
    "laptop": {"budget": (35000, 55000), "mid": (55000, 90000), "premium": (90000, 160000)},
    "refrigerator": {"budget": (25000, 40000), "mid": (40000, 65000), "premium": (65000, 120000)},
    "washingmachine": {"budget": (20000, 35000), "mid": (35000, 60000), "premium": (60000, 100000)},
    "tablet": {"budget": (10000, 20000), "mid": (20000, 35000), "premium": (35000, 70000)},
}
PRICE_BUCKET_HINT_PATTERNS: dict[str, re.Pattern[str]] = {
    "budget": re.compile(r"\b(?:дешев(?:ый|ая|ое|ые)?|недорог(?:ой|ая|ое|ие)?|бюджетн(?:ый|ая|ое|ые)?)\b", re.IGNORECASE),
    "mid": re.compile(r"\b(?:средней цены|средняя цена|средней стоимости|средняя стоимость|среднего ценового сегмента|средний ценовой сегмент|среднего бюджета|средний бюджет)\b", re.IGNORECASE),
    "premium": re.compile(r"\b(?:дорог(?:ой|ая|ое|ие)?|премиум|топов(?:ый|ая|ое|ые)?)\b", re.IGNORECASE),
}


def extract_price_hint(text: str, product_type: str | None = None) -> tuple[int, int] | None:
    """Extract a user budget range from Russian free-form text."""

    best_match: tuple[int, int] | None = None
    best_end = -1
    range_spans: list[tuple[int, int]] = []
    for match in PRICE_RANGE_RE.finditer(text):
        first_suffix = match.group("first_suffix") or match.group("second_suffix")
        second_suffix = match.group("second_suffix") or match.group("first_suffix")
        if not is_valid_price_match(text, match.start(), match.end(), match.group("first"), first_suffix):
            continue
        if not is_valid_price_match(text, match.start(), match.end(), match.group("second"), second_suffix):
            continue
        first = parse_price_value(match.group("first"), first_suffix)
        second = parse_price_value(match.group("second"), second_suffix)
        low = min(first, second)
        high = max(first, second)
        best_match = (int(round(low * 0.9)), int(round(high * 1.1))) if match.group("approx") else (low, high)
        best_end = match.end()
        range_spans.append((match.start(), match.end()))
    for match in PRICE_SINGLE_RE.finditer(text):
        if any(match.start() >= start and match.end() <= end for start, end in range_spans):
            continue
        if not is_valid_price_match(text, match.start(), match.end(), match.group("value"), match.group("suffix")):
            continue
        target = parse_price_value(match.group("value"), match.group("suffix"))
        kind = str(match.group("kind") or "").casefold()
        if kind in {"до", "не дороже", "не выше", "<="}:
            candidate = (0, target)
        elif kind in {"от", "не дешевле", "не ниже", ">="}:
            candidate = (target, 999999)
        elif kind == "чуть дешевле":
            candidate = (int(round(target * 0.8)), target)
        elif kind == "чуть дороже":
            candidate = (target, int(round(target * 1.2)))
        elif kind == "сильно дешевле":
            candidate = (0, int(round(target * 0.7)))
        elif kind == "сильно дороже":
            candidate = (int(round(target * 1.3)), 999999)
        elif kind in {"около", "примерно", "приблизительно"}:
            candidate = (int(round(target * 0.8)), int(round(target * 1.2)))
        else:
            delta = max(1, int(round(target * 0.05)))
            candidate = (max(0, target - delta), target + delta)
        if match.end() >= best_end:
            best_match = candidate
            best_end = match.end()
    if best_match is not None:
        return best_match
    bucket_hint = extract_price_bucket_hint(text)
    if bucket_hint is None:
        return None
    return resolve_price_bucket_range(product_type or "", bucket_hint)


def is_valid_price_match(text: str, start: int, end: int, value: str, suffix: str | None) -> bool:
    """Return True when a number is likely a price, not a percent, weight, or spec."""

    cleaned_value = value.replace(" ", "")
    if ("," in cleaned_value or "." in cleaned_value) and not suffix:
        return False
    trailing = text[end : end + 12]
    if PRICE_FORBIDDEN_SUFFIX_RE.search(trailing):
        return False
    if suffix:
        return True
    if PRICE_CURRENCY_HINT_RE.search(text[max(0, start - 8) : min(len(text), end + 12)]):
        return True
    try:
        numeric_value = parse_price_value(value, suffix)
    except ValueError:
        return False
    return numeric_value >= 1000


def parse_price_value(value: str, suffix: str | None) -> int:
    """Parse compact price values like 35к or 45 тысяч."""

    amount = float(value.replace(" ", "").replace(",", "."))
    if suffix:
        normalized_suffix = normalize_price_token(suffix)
        if normalized_suffix.startswith("к") or normalized_suffix.startswith("k") or normalized_suffix.startswith("тыс"):
            return int(amount * 1000)
    return int(amount)


def normalize_price_pair(price_min: int | None, price_max: int | None) -> str:
    """Format a DNS price range query value."""

    if price_min is None and price_max is None:
        return ""
    if price_min is None:
        price_min = 0
    if price_max is None:
        return ""
    if price_min == 0 and price_max == 0:
        return ""
    return f"{price_min}-{price_max}"


def extract_price_bucket_hint(text: str) -> str | None:
    """Extract budget/mid/premium price bucket words."""

    lowered = text.casefold()
    for bucket, pattern in PRICE_BUCKET_HINT_PATTERNS.items():
        if pattern.search(lowered):
            return bucket
    return None


def resolve_price_bucket_range(product_type: str, bucket: str) -> tuple[int, int]:
    """Resolve a semantic price bucket into a concrete range."""

    ranges = PRICE_BUCKET_RANGES_BY_PRODUCT_TYPE.get(normalize_price_token(product_type), DEFAULT_PRICE_BUCKET_RANGES)
    return ranges.get(bucket, DEFAULT_PRICE_BUCKET_RANGES["mid"])


def normalize_price_token(value: str) -> str:
    """Normalize tokens used by price parsing without importing orchestrator helpers."""

    return re.sub(r"[^0-9a-zа-яё]+", "_", value.casefold()).strip("_")
