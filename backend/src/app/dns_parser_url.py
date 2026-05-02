from __future__ import annotations

from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse


BASE_URL = "https://www.dns-shop.ru"
SEARCH_PATH = "/search/"


def build_search_params(query: str, category: str, page: int) -> dict[str, str]:
    params = {"q": query, "category": category}
    if page > 1:
        params["p"] = str(page)
    return params


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "www."))


def upsert_param(params: list[tuple[str, str]], key: str, value: str | None) -> list[tuple[str, str]]:
    if value is None or value == "":
        return params
    result = [(current_key, current_value) for current_key, current_value in params if current_key != key]
    result.append((key, value))
    return result


def build_query_string(params: list[tuple[str, str]]) -> str:
    return urlencode(params, doseq=True, quote_via=quote, safe="-_")


def normalize_dns_url(
    input_url_or_query: str,
    category: str | None = None,
    stock: str | None = None,
    price: str | None = None,
    extra_params: dict[str, str] | None = None,
) -> str:
    url = input_url_or_query.strip()
    if not is_url(url):
        url = f"{BASE_URL}{SEARCH_PATH}?{build_query_string([('q', url)])}"
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    params = parse_qsl(parsed.query, keep_blank_values=True)
    params = upsert_param(params, "category", category)
    params = upsert_param(params, "stock", stock)
    params = upsert_param(params, "price", price)
    for key, value in (extra_params or {}).items():
        params = upsert_param(params, key, value)
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc or "www.dns-shop.ru",
            parsed.path or SEARCH_PATH,
            "",
            build_query_string(params),
            "",
        )
    )


def build_search_page_url(normalized_url: str, page: int) -> str:
    parsed = urlparse(normalized_url)
    params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "p"]
    if page > 1:
        params.append(("p", str(page)))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", build_query_string(params), ""))


def classify_query_params(url: str) -> dict[str, dict[str, str]]:
    known_names = {"q", "category", "stock", "price"}
    known: dict[str, str] = {}
    unknown: dict[str, str] = {}
    for key, value in parse_qsl(urlparse(url).query, keep_blank_values=True):
        target = known if key in known_names else unknown
        target[key] = value
    return {"known": known, "unknown": unknown}


def known_query_params(url: str) -> dict[str, str]:
    return classify_query_params(url)["known"]


def inspect_dns_url_params(url: str) -> dict[str, object]:
    params = classify_query_params(url)
    known = {
        "q": params["known"].get("q", ""),
        "category": params["known"].get("category", ""),
        "stock": params["known"].get("stock", ""),
        "price": params["known"].get("price", ""),
    }
    return {"url": url, "known_params": known, "unknown_params": params["unknown"]}


def build_section_filters_url(url: str) -> str:
    params = known_query_params(url)
    query = params.get("q", "")
    category = params.get("category", "")
    if not query or not category:
        raise ValueError("Section URL must contain both q and category.")
    return normalize_dns_url(query, category=category)


def build_search_filters_extended_endpoint_url(section_url: str) -> str:
    params = known_query_params(section_url)
    query = params.get("q", "")
    category = params.get("category", "")
    return f"{BASE_URL}/catalog/search/filters-extended/?category={quote(category)}&q={quote(query)}"


def build_search_filters_endpoint_url(section_url: str) -> str:
    params = known_query_params(section_url)
    query = params.get("q", "")
    category = params.get("category", "")
    return f"{BASE_URL}/catalog/search/filters/?category={quote(category)}&q={quote(query)}"
