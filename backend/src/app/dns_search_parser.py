from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, quote, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from .dns_parser_url import (
    build_query_string,
    build_search_filters_endpoint_url,
    build_search_filters_extended_endpoint_url,
    build_search_page_url,
    build_search_params,
    build_section_filters_url,
    classify_query_params,
    inspect_dns_url_params,
    is_url,
    known_query_params,
    normalize_dns_url,
    upsert_param,
)
from .project_paths import COOKIES_FILE, ARTIFACTS_DIR, PROJECT_ROOT, artifact_path, ensure_runtime_directories, resolve_project_path


BASE_URL = "https://www.dns-shop.ru"
SEARCH_PATH = "/search/"
DEFAULT_CATEGORY = "17a8950d16404e77"
DEFAULT_QUERY = "клавиатура"
DEFAULT_LIMIT = 200
PAGE_SIZE_GUESS = 18
REQUEST_TIMEOUT = 30.0
COOKIES_TTL_SECONDS = 20 * 60
DEFAULT_CONCURRENCY = 3
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_COMPARE_CITY_ID = "128"
COOKIES_CACHE_PATH = COOKIES_FILE
BLOCKED_AFTER_BOOTSTRAP = "DNS still returns qauth/403 after browser cookie bootstrap."
BLOCKED_REQUIRES_BROWSER = "DNS returned qauth/403; browser cookie bootstrap is required."
PRODUCT_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
BROWSER_BOOTSTRAP_LOCK = threading.Lock()
PROCESS_COOKIES: httpx.Cookies | None = None
CHROME_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)
logger = logging.getLogger("dns_bot.parser")


@dataclass(frozen=True)
class Product:
    name: str
    price: int | None
    url: str
    code: str
    specs: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class ParsedCard:
    name: str
    url: str
    code: str
    buy_container_id: str
    specs: list[dict[str, str]]


class DnsFilterSelectionError(ValueError):
    def __init__(self, details: dict[str, object]) -> None:
        self.details = details
        super().__init__(json.dumps(details, ensure_ascii=False))


def browser_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }


def build_search_filters_headers(section_url: str) -> dict[str, str]:
    return {
        "Accept": "*/*",
        "Referer": section_url,
        "X-Requested-With": "XMLHttpRequest",
    }


def inspect_dns_section_filters(
    url: str,
    client_factory=None,
) -> dict[str, object]:
    section_url = build_section_filters_url(url)
    params = known_query_params(section_url)
    query = params.get("q", "")
    category = params.get("category", "")
    cookies = get_or_create_cookies(query, category, reason="section_filters")
    factory = client_factory or (lambda: make_client(cookies))
    try:
        with factory() as client:
            base_payload = fetch_search_filters_payload(
                client,
                build_search_filters_endpoint_url(section_url),
                section_url,
            )
            extended_payload = fetch_search_filters_payload(
                client,
                build_search_filters_extended_endpoint_url(section_url),
                section_url,
            )
    except RuntimeError as exc:
        if BLOCKED_AFTER_BOOTSTRAP not in str(exc):
            raise
        cookies = recover_dns_cookies(query, category, reason="section_filters")
        with make_client(cookies) as client:
            base_payload = fetch_search_filters_payload(
                client,
                build_search_filters_endpoint_url(section_url),
                section_url,
            )
            extended_payload = fetch_search_filters_payload(
                client,
                build_search_filters_extended_endpoint_url(section_url),
                section_url,
            )
    filters = merge_dns_filters(
        extract_base_filters(base_payload),
        extract_extended_filters(extended_payload),
    )
    return {
        "url": url,
        "section_url": section_url,
        "query": query,
        "category": category,
        "count": len(filters),
        "filters": filters,
    }


def fetch_search_filters_payload(client: httpx.Client, endpoint_url: str, section_url: str) -> dict[str, object]:
    response = client.get(endpoint_url, headers=build_search_filters_headers(section_url))
    if response_is_blocked(response):
        raise RuntimeError(BLOCKED_AFTER_BOOTSTRAP)
    response.raise_for_status()
    persist_client_cookies(client)
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def extract_base_filters(payload: dict[str, object]) -> list[dict[str, object]]:
    filters: list[dict[str, object]] = []
    blocks = payload.get("data", {}).get("filters", [])
    for block in blocks:
        if isinstance(block, dict):
            filters.append(map_dns_filter_block(block, "base"))
    return filters


def extract_extended_filters(payload: dict[str, object]) -> list[dict[str, object]]:
    filters: list[dict[str, object]] = []
    groups = payload.get("data", {}).get("groups", [])
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_name = str(group.get("title", "")).strip() or "extended"
        for block in group.get("blocks", []):
            if isinstance(block, dict):
                filters.append(map_dns_filter_block(block, group_name))
    return filters


def merge_dns_filters(
    base_filters: list[dict[str, object]],
    extended_filters: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for filter_block in base_filters:
        filter_id = str(filter_block.get("id", "")).strip()
        if not filter_id:
            continue
        order.append(filter_id)
        merged[filter_id] = filter_block
    for filter_block in extended_filters:
        filter_id = str(filter_block.get("id", "")).strip()
        if not filter_id:
            continue
        if filter_id not in order:
            order.append(filter_id)
        merged[filter_id] = filter_block
    return [merged[filter_id] for filter_id in order]


def build_dns_url_from_section_filters(
    section_url: str,
    selected_filters: list[dict[str, object]],
    available_filters: list[dict[str, object]],
) -> str:
    normalized_url = build_section_filters_url(section_url)
    query_params = parse_qsl(urlparse(normalized_url).query, keep_blank_values=True)
    extra_params: list[tuple[str, str]] = []
    stock_value = ""
    price_value = ""
    missing_filter_ids: list[str] = []
    missing_value_ids: list[str] = []
    for selected_filter in selected_filters:
        if not isinstance(selected_filter, dict):
            continue
        filter_block = find_filter_block(available_filters, selected_filter)
        if filter_block is None:
            missing_filter_ids.append(str(selected_filter.get("id", "") or selected_filter.get("name", "")).strip())
            continue
        block_id = str(filter_block.get("id", ""))
        block_type = str(filter_block.get("type", ""))
        if block_id == "price":
            range_value = build_selected_price_value(selected_filter)
            if range_value:
                price_value = range_value
            continue
        if block_type in {"range-checkbox", "range-radio"} and ("min" in selected_filter or "max" in selected_filter):
            range_value = build_selected_numeric_range_value(selected_filter)
            if range_value:
                extra_params.append((block_id, range_value))
            continue
        if block_id == "stock":
            selected_ids, unresolved_values = resolve_selected_value_ids(filter_block, selected_filter)
            missing_value_ids.extend(unresolved_values)
            if selected_ids:
                stock_value = "-".join(selected_ids)
            continue
        if block_type == "toggle":
            if selected_filter.get("enabled") is True:
                extra_params.append((block_id, "1"))
            continue
        selected_ids, unresolved_values = resolve_selected_value_ids(filter_block, selected_filter)
        missing_value_ids.extend(unresolved_values)
        if selected_ids:
            extra_params.append((block_id, "-".join(selected_ids)))
    missing_filter_ids = [item for item in missing_filter_ids if item]
    missing_value_ids = [item for item in missing_value_ids if item]
    if missing_filter_ids or missing_value_ids:
        raise DnsFilterSelectionError(
            {
                "section_url": section_url,
                "selected_filters": selected_filters,
                "missing_filter_ids": missing_filter_ids,
                "missing_value_ids": missing_value_ids,
            }
        )
    for current_key, _current_value in query_params[:]:
        if current_key == "stock":
            query_params = [(key, value) for key, value in query_params if key != "stock"]
        if current_key == "price":
            query_params = [(key, value) for key, value in query_params if key != "price"]
    query_params = [(key, value) for key, value in query_params if key not in {param[0] for param in extra_params}]
    query_params = upsert_param(query_params, "stock", stock_value)
    query_params = upsert_param(query_params, "price", price_value)
    query_params.extend(extra_params)
    parsed = urlparse(normalized_url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", build_query_string(query_params), ""))


def find_filter_block(
    available_filters: list[dict[str, object]],
    selected_filter: dict[str, object],
) -> dict[str, object] | None:
    selected_id = str(selected_filter.get("id", "")).strip()
    selected_name = str(selected_filter.get("name", "")).strip()
    for filter_block in available_filters:
        if selected_id and str(filter_block.get("id", "")) == selected_id:
            return filter_block
        if selected_name and str(filter_block.get("name", "")) == selected_name:
            return filter_block
    return None


def resolve_selected_value_ids(
    filter_block: dict[str, object],
    selected_filter: dict[str, object],
) -> tuple[list[str], list[str]]:
    raw_values = selected_filter.get("values", [])
    if not isinstance(raw_values, list):
        return [], []
    by_id = {
        str(item.get("id", "")): str(item.get("id", ""))
        for item in filter_block.get("values", [])
        if isinstance(item, dict)
    }
    by_name = {
        str(item.get("name", "")): str(item.get("id", ""))
        for item in filter_block.get("values", [])
        if isinstance(item, dict)
    }
    result: list[str] = []
    unresolved: list[str] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, dict):
            continue
        value_id = str(raw_value.get("id", "")).strip()
        value_name = str(raw_value.get("name", "")).strip()
        resolved_id = by_id.get(value_id) or by_name.get(value_name)
        if not resolved_id:
            unresolved.append(value_id or value_name)
            continue
        if resolved_id in result:
            continue
        result.append(resolved_id)
    return result, unresolved


def build_selected_price_value(selected_filter: dict[str, object]) -> str:
    min_value = selected_filter.get("min")
    max_value = selected_filter.get("max")
    if min_value in {None, ""} and max_value in {None, ""}:
        return ""
    min_price = coerce_price(min_value)
    max_price = coerce_price(max_value)
    return normalize_price_range(min_price, max_price)


def build_selected_numeric_range_value(selected_filter: dict[str, object]) -> str:
    min_value = coerce_numeric_range_number(selected_filter.get("min"))
    max_value = coerce_numeric_range_number(selected_filter.get("max"))
    if min_value is None and max_value is None:
        return ""
    if min_value is None:
        min_value = 0.0
    if max_value is None:
        return ""
    if min_value > max_value:
        min_value, max_value = max_value, min_value
    return f"{format_numeric_range_component(min_value)}-{format_numeric_range_component(max_value)}"


def normalize_price_range(low: object, high: object) -> str:
    low_value = coerce_price(low)
    high_value = coerce_price(high)
    if low_value is None and high_value is None:
        return ""
    if low_value is None:
        low_value = 0
    if high_value is None:
        return ""
    if low_value > high_value:
        low_value, high_value = high_value, low_value
    return f"{low_value}-{high_value}"


def coerce_price(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(str(value).replace(" ", "").replace(",", ".")))
    except ValueError:
        return None
    return number if number >= 0 else None


def coerce_numeric_range_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return number if number >= 0 else None


def format_numeric_range_component(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text


def map_dns_filter_block(block: dict[str, object], group: str) -> dict[str, object]:
    values = []
    for variant in block.get("variants", []):
        if not isinstance(variant, dict):
            continue
        values.append(
            {
                "id": str(variant.get("id", "")),
                "name": str(variant.get("label", "")),
                "count": variant.get("count"),
            }
        )
    result = {
        "group": group,
        "id": str(block.get("id", "")),
        "name": str(block.get("label", "")),
        "type": str(block.get("type", "")),
        "is_spec": bool(block.get("isSpec", False)),
        "values": values,
    }
    if "selected" in block:
        selected = block.get("selected", [])
        result["selected"] = [str(item) for item in selected] if isinstance(selected, list) else []
    if "default" in block:
        default = block.get("default", [])
        result["default"] = [str(item) for item in default] if isinstance(default, list) else []
    if "min" in block or "max" in block:
        result["range"] = {
            "min": block.get("min"),
            "max": block.get("max"),
            "min_selected": block.get("minSelected"),
            "max_selected": block.get("maxSelected"),
        }
    return result


def build_category_resolution_url(url: str) -> str:
    params = known_query_params(url)
    query = params.get("q", "")
    if not query:
        return url
    return normalize_dns_url(query)


def resolve_category_if_missing(
    url: str,
    browser_resolver,
    http_resolver=None,
) -> str:
    params = known_query_params(url)
    if params.get("category"):
        return url
    resolved_url = ""
    if http_resolver is not None:
        try:
            resolved_url = http_resolver(url)
        except RuntimeError:
            resolved_url = ""
    if not resolved_url:
        resolved_url = browser_resolver(url)
    resolved_category = known_query_params(resolved_url).get("category")
    if resolved_category:
        return normalize_dns_url(url, category=resolved_category)
    print(json.dumps({"warning": "category_not_resolved", "url": url}, ensure_ascii=False), file=sys.stderr)
    return url


def build_result_payload(
    mode: str,
    url: str,
    resolved_url: str,
    products: list[Product],
    stats: dict[str, int],
) -> dict[str, object]:
    params = classify_query_params(resolved_url)
    return {
        "mode": mode,
        "url": url,
        "resolved_url": resolved_url,
        "filters": {
            "category": params["known"].get("category", ""),
            "stock": params["known"].get("stock", ""),
            "price": params["known"].get("price", ""),
            "unknown": params["unknown"],
        },
        "stats": stats,
        "count": len(products),
        "products": [asdict(product) for product in products],
    }


def parse_cards(html: str) -> list[ParsedCard]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[ParsedCard] = []
    for card in soup.select(".catalog-product"):
        name_link = card.select_one(".catalog-product__name[href]")
        buy_node = card.select_one(".catalog-product__buy[id]")
        code = card.get("data-code", "").strip()
        if not name_link or not buy_node or not code:
            continue
        normalized_name, inline_specs = split_card_name_and_specs(normalize_space(name_link.get_text(" ", strip=True)))
        cards.append(
            ParsedCard(
                name=normalized_name,
                url=urljoin(BASE_URL, name_link["href"]),
                code=code,
                buy_container_id=buy_node["id"],
                specs=inline_specs,
            )
        )
    return cards


def split_card_name_and_specs(raw_name: str) -> tuple[str, list[dict[str, str]]]:
    match = re.search(r"\[(.+)\]\s*$", raw_name)
    if match is None:
        return raw_name, []
    base_name = normalize_space(raw_name[: match.start()].strip())
    return base_name, parse_inline_card_specs(match.group(1))


def parse_inline_card_specs(raw_specs: str) -> list[dict[str, str]]:
    tokens = [normalize_space(token) for token in raw_specs.split(",") if normalize_space(token)]
    if not tokens:
        return []
    specs: list[dict[str, str]] = []
    interfaces: list[str] = []
    extras: list[str] = []
    usb_tokens: list[str] = []
    for token in tokens:
        lowered = token.casefold()
        if ("x" in lowered and "@" in lowered) or ("х" in lowered and "@" in lowered):
            specs.append({"name": "Разрешение и частота", "value": token})
            continue
        if lowered in {"ips", "va", "tn", "oled", "amoled", "qled", "mini led", "micro led"}:
            specs.append({"name": "Тип матрицы", "value": token})
            continue
        if lowered == "led":
            specs.append({"name": "Подсветка", "value": token})
            continue
        if re.fullmatch(r"\d+\s*:\s*\d+", token):
            specs.append({"name": "Контрастность", "value": token})
            continue
        if "кд/" in lowered or "cd/" in lowered:
            specs.append({"name": "Яркость", "value": token})
            continue
        if "°/" in token:
            specs.append({"name": "Углы обзора", "value": token})
            continue
        if re.match(r"^usb\s+[xх]\d+", lowered):
            usb_tokens.append(token)
            continue
        if lowered.startswith(("displayport", "hdmi", "usb type-c", "usb-c", "dvi", "vga", "thunderbolt", "mini displayport")):
            interfaces.append(token)
            continue
        extras.append(token)
    if interfaces:
        specs.append({"name": "Интерфейсы", "value": ", ".join(interfaces)})
    if usb_tokens:
        specs.append({"name": "USB", "value": ", ".join(usb_tokens)})
    if extras:
        specs.append({"name": "Дополнительно", "value": ", ".join(extras)})
    return specs


def has_catalog_pagination(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    pagination = soup.select_one(
        ".pagination-widget, .pagination-widget__pages, .pagination, .pager, [data-role='pagination']"
    )
    if pagination is None:
        return False
    return bool(
        pagination.select(
            "a[href*='p=2'], a[data-page-number='2'], [data-page='2'], .pagination-widget__page"
        )
    )


def classify_first_page_scope(
    html: str,
    card_count: int,
    collected_count: int,
    limit: int | None,
) -> str:
    if card_count < PAGE_SIZE_GUESS:
        return "small"
    if limit is not None and collected_count >= limit:
        return "small"
    if has_catalog_pagination(html):
        return "large"
    return "ambiguous"


def product_characteristics_url(product_url: str) -> str:
    parsed = urlparse(product_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3 or parts[0] != "product":
        raise ValueError(f"Unsupported DNS product URL: {product_url}")
    product_id = parts[1]
    slug = parts[2]
    return urlunparse(
        (
            parsed.scheme or "https",
            parsed.netloc or "www.dns-shop.ru",
            f"/product/characteristics/{product_id}/{slug}/",
            "",
            "",
            "",
        )
    )


def build_compare_url(city_id: str, product_ids: list[str]) -> str:
    joined = quote(",".join(product_ids), safe="")
    return f"https://www.dns-shop.ru/compare/?cityId={city_id}&ids={joined}"


def parse_characteristics_urls(raw_value: str) -> list[str]:
    chunks = re.split(r"[\s,]+", raw_value.strip())
    return [chunk for chunk in chunks if chunk.startswith(("http://", "https://"))]


def parse_characteristics(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    specs: list[dict[str, str]] = []
    for row in soup.select(".product-characteristics__spec"):
        name_node = row.select_one(".product-characteristics__spec-title")
        value_node = row.select_one(".product-characteristics__spec-value")
        if not name_node or not value_node:
            continue
        name = normalize_space(name_node.get_text(" ", strip=True))
        value = normalize_space(value_node.get_text(" ", strip=True))
        if name and value:
            specs.append({"name": name, "value": value})
    if specs:
        return specs
    return parse_characteristics_table_fallback(soup)


def parse_compare_table(html: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    products: list[dict[str, object]] = []
    for index, card in enumerate(soup.select(".products-slider__item")):
        name_node = card.select_one(".products-slider__product-name, .base-ui-link")
        score_node = card.select_one(".products-slider__score-points")
        name = normalize_space(name_node.get_text(" ", strip=True)) if name_node else ""
        if not name:
            continue
        product_payload: dict[str, object] = {"index": index, "name": name}
        if score_node:
            score = normalize_space(score_node.get_text(" ", strip=True))
            if score:
                product_payload["score"] = score
        products.append(product_payload)

    groups: list[dict[str, object]] = []
    for group in soup.select(".compare-table > section article.group-table"):
        group_name_node = group.select_one(".group-table__header, .group-table__title")
        group_name = normalize_space(group_name_node.get_text(" ", strip=True)) if group_name_node else ""
        rows: list[dict[str, object]] = []
        for row in group.select(".group-table__option-wrapper"):
            label_node = row.select_one(".group-table__option-name, .group-table__option")
            label = normalize_space(label_node.get_text(" ", strip=True)) if label_node else ""
            values = [
                normalize_space(cell.get_text(" ", strip=True))
                for cell in row.select(".group-table__data .group-table__product-value")
            ]
            values = [value for value in values if value]
            if label and values:
                rows.append({"label": label, "values": values})
        if group_name and rows:
            groups.append({"name": group_name, "rows": rows})
    return {"products": products, "groups": groups}


def load_compare_page_html_with_browser(url: str) -> str:
    chrome_path = find_installed_browser()
    if not chrome_path:
        raise RuntimeError("Chrome/Edge was not found; install Playwright browsers or Chrome.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright package is required for browser page loading.") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chrome_path,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(locale="ru-RU", viewport={"width": 1600, "height": 1200})
        page = context.new_page()
        block_heavy_resources(page)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_selector(".compare-table", timeout=45000)
        except Exception:
            page.wait_for_timeout(8000)
        page.wait_for_timeout(1200)
        html = page.content()
        browser.close()
    return html


def extract_compare_table(compare_url: str, browser_loader=None) -> dict[str, object]:
    loader = browser_loader or load_compare_page_html_with_browser
    return parse_compare_table(loader(compare_url))


def compare_specs_from_table(parsed: dict[str, object], product_count: int) -> list[list[dict[str, str]]]:
    groups = parsed.get("groups") or []
    specs_by_index: list[list[dict[str, str]]] = [[] for _ in range(max(product_count, 0))]
    seen_by_index: list[set[tuple[str, str]]] = [set() for _ in range(max(product_count, 0))]
    for group in groups:
        if not isinstance(group, dict):
            continue
        for row in group.get("rows") or []:
            if not isinstance(row, dict):
                continue
            label = normalize_space(str(row.get("label", "")))
            values = row.get("values") or []
            if not label or not isinstance(values, list):
                continue
            for index, value in enumerate(values[:product_count]):
                if not isinstance(value, str):
                    continue
                normalized_value = normalize_space(value)
                if not normalized_value:
                    continue
                signature = (label, normalized_value)
                if signature in seen_by_index[index]:
                    continue
                seen_by_index[index].add(signature)
                specs_by_index[index].append({"name": label, "value": normalized_value})
    return specs_by_index


def parse_characteristics_table_fallback(soup: BeautifulSoup) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        name = normalize_space(cells[0].get_text(" ", strip=True))
        value = normalize_space(cells[1].get_text(" ", strip=True))
        if name and value:
            specs.append({"name": name, "value": value})
    return specs


def characteristics_page_needs_expansion(html: str) -> bool:
    lowered = html.lower()
    return "product-characteristics_collapsed" in lowered


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_csrf_token(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.select_one('meta[name="csrf-token"][content]')
    return meta["content"] if meta else ""


def extract_product_uuid(html: str) -> str:
    matches = PRODUCT_UUID_RE.findall(html)
    return matches[-1] if matches else ""


def build_characteristics_actual_url(product_uuid: str) -> str:
    return f"/catalog/product/get-product-characteristics-actual/?id={product_uuid}"


def build_product_buy_payload(cards: Iterable[ParsedCard]) -> str:
    containers = [
        {"id": card.buy_container_id, "data": {"id": card.code}}
        for card in cards
        if card.buy_container_id and card.code
    ]
    return json.dumps(
        {"type": "product-buy", "containers": containers},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def extract_prices(response_json: dict) -> dict[str, int]:
    prices: dict[str, int] = {}
    states = response_json.get("data", {}).get("states", [])
    if not isinstance(states, list):
        return prices
    for state in states:
        container_id = state.get("id")
        price = state.get("data", {}).get("price", {}).get("current")
        if isinstance(container_id, str) and isinstance(price, int):
            prices[container_id] = price
    return prices


def make_client(cookies: httpx.Cookies | None = None) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers=browser_headers(),
        cookies=cookies,
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT,
    )


def make_async_client(cookies: httpx.Cookies | None = None) -> httpx.AsyncClient:
    try:
        return httpx.AsyncClient(
            base_url=BASE_URL,
            headers=browser_headers(),
            cookies=cookies,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            http2=True,
        )
    except ImportError:
        return httpx.AsyncClient(
            base_url=BASE_URL,
            headers=browser_headers(),
            cookies=cookies,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        )


def cookies_cache_is_fresh(cache_path: Path, ttl_seconds: int) -> bool:
    return load_cookies_cache_payload(cache_path, ttl_seconds) is not None


def read_cookies_cache_payload(cache_path: Path) -> dict[str, object] | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def parse_cookies_cache_created_at(payload: dict[str, object]) -> float:
    try:
        return float(payload.get("created_at", 0))
    except (TypeError, ValueError):
        return 0.0


def load_cookies_cache_payload(cache_path: Path, ttl_seconds: int) -> dict[str, object] | None:
    payload = read_cookies_cache_payload(cache_path)
    if payload is None:
        return None
    created_at = parse_cookies_cache_created_at(payload)
    if created_at <= 0 or (time.time() - created_at) > ttl_seconds:
        return None
    return payload


def load_cookies_cache(cache_path: Path, ttl_seconds: int) -> httpx.Cookies | None:
    payload = load_cookies_cache_payload(cache_path, ttl_seconds)
    if payload is None:
        return None
    return to_httpx_cookies(payload.get("cookies", []))


def save_cookies_cache(cookies: httpx.Cookies, cache_path: Path) -> None:
    ensure_runtime_directories()
    serialized = []
    for cookie in cookies.jar:
        serialized.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
            }
        )
    cache_path.write_text(
        json.dumps({"created_at": time.time(), "cookies": serialized}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def invalidate_cookies_cache(cache_path: Path) -> None:
    if cache_path.exists():
        cache_path.unlink()


def response_is_blocked(response: httpx.Response) -> bool:
    text = response.text.lower()
    return response.status_code in {401, 403, 429} or "qauth" in text or "/__qrator/" in text or "qrator" in text


def set_process_cookies(cookies: httpx.Cookies) -> httpx.Cookies:
    global PROCESS_COOKIES
    PROCESS_COOKIES = cookies
    return cookies


def current_process_cookies() -> httpx.Cookies | None:
    return PROCESS_COOKIES


def persist_client_cookies(client: httpx.Client | httpx.AsyncClient) -> None:
    cookies = getattr(client, "cookies", None)
    if not isinstance(cookies, httpx.Cookies):
        return
    set_process_cookies(cookies)
    save_cookies_cache(cookies, COOKIES_CACHE_PATH)


def prewarm_dns_cookies(
    query: str = DEFAULT_QUERY,
    category: str = DEFAULT_CATEGORY,
    reason: str = "startup",
    force: bool = False,
) -> httpx.Cookies:
    logger.info(
        "dns_cookie_bootstrap_start reason=%s query=%s category=%s",
        reason,
        query,
        category,
    )
    cached = None if force else current_process_cookies()
    if cached is not None:
        logger.info("dns_cookie_bootstrap_done source=process_cache reason=%s", reason)
        return cached
    cached = None if force else load_cookies_cache(COOKIES_CACHE_PATH, COOKIES_TTL_SECONDS)
    if cached is not None:
        set_process_cookies(cached)
        logger.info("dns_cookie_bootstrap_done source=file_cache reason=%s", reason)
        return cached
    cookies = bootstrap_cookies(query, category)
    save_cookies_cache(cookies, COOKIES_CACHE_PATH)
    set_process_cookies(cookies)
    logger.info("dns_cookie_bootstrap_done source=browser reason=%s", reason)
    return cookies


def recover_dns_cookies(query: str, category: str, reason: str) -> httpx.Cookies:
    logger.info(
        "dns_cookie_bootstrap_recovery reason=%s query=%s category=%s",
        reason,
        query,
        category,
    )
    return prewarm_dns_cookies(query=query, category=category, reason=reason, force=True)


def fetch_search_page_by_url(client: httpx.Client, normalized_url: str, page: int) -> httpx.Response:
    return client.get(build_search_page_url(normalized_url, page))


async def async_get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    attempts: int = DEFAULT_RETRY_ATTEMPTS,
) -> httpx.Response:
    delay = 0.5
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(url)
            return response
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(delay)
            delay *= 2
    if last_error:
        raise last_error
    raise RuntimeError("async_get_with_retry failed without error")


async def fetch_pages_batch_async(
    client: httpx.AsyncClient,
    normalized_url: str,
    pages: list[int],
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[tuple[int, httpx.Response]]:
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(page: int) -> tuple[int, httpx.Response]:
        async with semaphore:
            response = await async_get_with_retry(client, build_search_page_url(normalized_url, page))
            return page, response

    results = await asyncio.gather(*(fetch_one(page) for page in pages))
    return sorted(results, key=lambda item: item[0])


def format_progress(page: int, collected: int, limit: int | None) -> str:
    if limit is None:
        return f"Страница {page}: собрано {collected}"
    return f"Страница {page}: собрано {collected}/{limit}"


def print_progress(page: int, collected: int, limit: int | None) -> None:
    if os.getenv("DNS_PARSER_PROGRESS", "0").strip() != "1":
        return
    print(format_progress(page, collected, limit), file=sys.stderr, flush=True)


async def fetch_prices_async(
    client: httpx.AsyncClient,
    cards: list[ParsedCard],
    csrf_token: str,
    referer_url: str,
) -> dict[str, int]:
    if not cards:
        return {}
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": referer_url,
        "X-Requested-With": "XMLHttpRequest",
    }
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    response = await client.post(
        "/ajax-state/product-buy/",
        data={"data": build_product_buy_payload(cards)},
        headers=headers,
    )
    persist_client_cookies(client)
    response.raise_for_status()
    data = response.json()
    if data.get("result") is not True:
        return {}
    return extract_prices(data)


def browser_resolve_url(url: str) -> str:
    params = known_query_params(url)
    query = params.get("q", "")
    if not query:
        return url
    cookies, resolved_url = load_url_in_browser(url, wait_for_category=True)
    save_cookies_cache(cookies, COOKIES_CACHE_PATH)
    set_process_cookies(cookies)
    return resolved_url or url


def http_resolve_url(url: str, cookies: httpx.Cookies | None = None) -> str:
    with make_client(cookies) as client:
        response = client.get(url)
        if response_is_blocked(response):
            raise RuntimeError(BLOCKED_AFTER_BOOTSTRAP)
        response.raise_for_status()
        persist_client_cookies(client)
        return str(response.url)


def collect_products_by_url(
    input_value: str,
    limit: int | None,
    category: str = "",
    stock: str = "",
    price: str = "",
    allow_browser: bool = True,
) -> tuple[list[Product], str, str, str]:
    requested_url = normalize_dns_url(input_value, category=category, stock=stock, price=price)
    requested_params = known_query_params(requested_url)
    requested_category = requested_params.get("category", "")
    if requested_category:
        resolved_url = requested_url
    else:
        resolution_url = build_category_resolution_url(requested_url)
        resolved_url = resolve_category_if_missing(
            resolution_url,
            browser_resolver=browser_resolve_url if allow_browser else (lambda value: value),
        )
        resolved_params = known_query_params(resolved_url)
        resolved_category = resolved_params.get("category", "")
        if resolved_category:
            resolved_url = normalize_dns_url(requested_url, category=resolved_category)
        else:
            resolved_url = requested_url
    params = known_query_params(resolved_url)
    with make_client(get_or_create_cookies(params.get("q", ""), params.get("category", ""), reason="url_search")) as client:
        first = fetch_search_page_by_url(client, resolved_url, 1)
        if response_is_blocked(first):
            if not allow_browser:
                raise RuntimeError(BLOCKED_REQUIRES_BROWSER)
            cookies = recover_dns_cookies(params.get("q", ""), params.get("category", ""), reason="url_blocked")
            return (
                collect_products_by_url_with_cookies(resolved_url, limit, cookies),
                "browser-cookies+httpx",
                requested_url,
                resolved_url,
            )
        persist_client_cookies(client)
        return asyncio.run(collect_products_from_url_async(resolved_url, limit, first, client.cookies)), "httpx", requested_url, resolved_url


def collect_products_by_url_with_cookies(
    normalized_url: str,
    limit: int | None,
    cookies: httpx.Cookies,
) -> list[Product]:
    with make_client(cookies) as client:
        first = fetch_search_page_by_url(client, normalized_url, 1)
        if response_is_blocked(first):
            raise RuntimeError(BLOCKED_AFTER_BOOTSTRAP)
        return asyncio.run(collect_products_from_url_async(normalized_url, limit, first, client.cookies))


async def collect_products_from_url_async(
    normalized_url: str,
    limit: int | None,
    first_response: httpx.Response,
    cookies: httpx.Cookies | None,
) -> list[Product]:
    products: list[Product] = []
    async with make_async_client(cookies) as async_client:
        first_cards = parse_cards(first_response.text)
        if not first_cards:
            return []
        first_prices = await fetch_prices_async(
            async_client,
            first_cards,
            extract_csrf_token(first_response.text),
            build_search_page_url(normalized_url, 1),
        )
        products.extend(build_products(first_cards, first_prices))
        persist_client_cookies(async_client)
        print_progress(1, min(len(products), limit) if limit is not None else len(products), limit)
        first_page_scope = classify_first_page_scope(first_response.text, len(first_cards), len(products), limit)
        if first_page_scope == "small":
            return products[:limit] if limit is not None else products
        next_page = 2
        if first_page_scope == "ambiguous":
            probe_response = await async_get_with_retry(async_client, build_search_page_url(normalized_url, 2))
            if response_is_blocked(probe_response):
                raise RuntimeError("DNS returned qauth/403 on page 2.")
            probe_response.raise_for_status()
            persist_client_cookies(async_client)
            probe_cards = parse_cards(probe_response.text)
            if not probe_cards:
                return products[:limit] if limit is not None else products
            probe_prices = await fetch_prices_async(
                async_client,
                probe_cards,
                extract_csrf_token(probe_response.text),
                build_search_page_url(normalized_url, 2),
            )
            products.extend(build_products(probe_cards, probe_prices))
            print_progress(2, min(len(products), limit) if limit is not None else len(products), limit)
            if len(probe_cards) < PAGE_SIZE_GUESS or (limit is not None and len(products) >= limit):
                return products[:limit] if limit is not None else products
            next_page = 3
        while True:
            if limit is not None:
                remaining = limit - len(products)
                if remaining <= 0:
                    break
                pages_needed = max(1, (remaining + PAGE_SIZE_GUESS - 1) // PAGE_SIZE_GUESS)
                batch_size = min(DEFAULT_CONCURRENCY, pages_needed)
            else:
                batch_size = DEFAULT_CONCURRENCY
            pages = list(range(next_page, next_page + batch_size))
            page_responses = await fetch_pages_batch_async(async_client, normalized_url, pages, DEFAULT_CONCURRENCY)
            if not page_responses:
                break
            should_stop = False
            for page, response in page_responses:
                if response_is_blocked(response):
                    raise RuntimeError(f"DNS returned qauth/403 on page {page}.")
                response.raise_for_status()
                persist_client_cookies(async_client)
                cards = parse_cards(response.text)
                if not cards:
                    should_stop = True
                    break
                prices = await fetch_prices_async(
                    async_client,
                    cards,
                    extract_csrf_token(response.text),
                    build_search_page_url(normalized_url, page),
                )
                products.extend(build_products(cards, prices))
                print_progress(page, min(len(products), limit) if limit is not None else len(products), limit)
                if len(cards) < PAGE_SIZE_GUESS:
                    should_stop = True
                    break
                if limit is not None and len(products) >= limit:
                    should_stop = True
                    break
            if should_stop:
                break
            next_page += batch_size
    return products[:limit] if limit is not None else products


def build_products(cards: list[ParsedCard], prices: dict[str, int]) -> list[Product]:
    return [
        Product(
            name=card.name,
            price=prices.get(card.buy_container_id),
            url=card.url,
            code=card.code,
            specs=getattr(card, "specs", []),
        )
        for card in cards
    ]


def postprocess_products(
    products: list[Product],
    query: str | None = None,
    exclude_noise: bool = True,
) -> tuple[list[Product], dict[str, int]]:
    deduped: list[Product] = []
    seen: set[str] = set()
    skipped_duplicates = 0
    for product in products:
        key = product.code or product.url
        if key in seen:
            skipped_duplicates += 1
            continue
        seen.add(key)
        deduped.append(product)
    filtered = []
    skipped_noise = 0
    for product in deduped:
        if exclude_noise and is_noise_product(product, query):
            skipped_noise += 1
            continue
        filtered.append(product)
    stats = {
        "raw_count": len(products),
        "dedup_count": len(deduped),
        "filtered_count": len(filtered),
        "skipped_duplicates": skipped_duplicates,
        "skipped_noise": skipped_noise,
    }
    return filtered, stats


def is_noise_product(product: Product, query: str | None) -> bool:
    if not query or "клавиатура" not in query.lower():
        return False
    lowered = product.name.lower()
    return "цифровой блок" in lowered or "numpad" in lowered


def fetch_characteristics_for_urls(
    urls: list[str],
    allow_browser: bool,
    client_factory=make_client,
    browser_loader=None,
) -> list[dict[str, object]]:
    if client_factory is not make_client or browser_loader is not None:
        items: list[dict[str, object]] = []
        with client_factory() as client:
            for source_url in urls:
                characteristics_url = product_characteristics_url(source_url)
                response = client.get(characteristics_url)
                if response_is_blocked(response):
                    if not allow_browser:
                        raise RuntimeError("DNS returned qauth/403 while fetching characteristics.")
                    loader = browser_loader or load_page_html_with_browser
                    items.append(
                        {
                            "url": source_url,
                            "characteristics_url": characteristics_url,
                            "specs": parse_characteristics(loader(characteristics_url)),
                        }
                    )
                    continue
                response.raise_for_status()
                ajax_specs = fetch_characteristics_via_ajax(client, characteristics_url, response.text)
                if ajax_specs is not None:
                    items.append(
                        {
                            "url": source_url,
                            "characteristics_url": characteristics_url,
                            "specs": ajax_specs,
                        }
                    )
                    continue
                if allow_browser and characteristics_page_needs_expansion(response.text):
                    loader = browser_loader or load_page_html_with_browser
                    items.append(
                        {
                            "url": source_url,
                            "characteristics_url": characteristics_url,
                            "specs": parse_characteristics(loader(characteristics_url)),
                        }
                    )
                    continue
                items.append(
                    {
                        "url": source_url,
                        "characteristics_url": str(response.url),
                        "specs": parse_characteristics(response.text),
                    }
                )
        return items
    return asyncio.run(fetch_characteristics_for_urls_async(urls, allow_browser))


def fetch_compare_characteristics_for_products(
    products: list[object],
    allow_browser: bool,
    city_id: str = DEFAULT_COMPARE_CITY_ID,
    browser_loader=None,
) -> list[dict[str, object]]:
    if not products:
        return []
    product_ids: list[str] = []
    source_urls: list[str] = []
    for product in products:
        source_url = normalize_space(str(getattr(product, "url", "")) or str(product))
        product_id = normalize_space(str(getattr(product, "code", "")))
        if not source_url or not product_id:
            continue
        source_urls.append(source_url)
        product_ids.append(product_id)
    if not source_urls:
        return []
    compare_url = build_compare_url(city_id, product_ids)
    if allow_browser:
        html = (browser_loader or load_compare_page_html_with_browser)(compare_url)
    else:
        html = load_compare_page_html_with_browser(compare_url)
    parsed = parse_compare_table(html)
    specs_by_index = compare_specs_from_table(parsed, len(source_urls))
    items: list[dict[str, object]] = []
    for index, source_url in enumerate(source_urls):
        items.append(
            {
                "url": source_url,
                "characteristics_url": compare_url,
                "compare_url": compare_url,
                "specs": specs_by_index[index] if index < len(specs_by_index) else [],
            }
        )
    return items


async def fetch_characteristics_for_urls_async(
    urls: list[str],
    allow_browser: bool,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[dict[str, object]]:
    semaphore = asyncio.Semaphore(concurrency)
    browser_semaphore = asyncio.Semaphore(1)

    async def fetch_browser_specs(characteristics_url: str) -> list[dict[str, str]]:
        async with browser_semaphore:
            return parse_characteristics(await asyncio.to_thread(load_page_html_with_browser, characteristics_url))

    async def fetch_one(async_client: httpx.AsyncClient, source_url: str) -> tuple[str, str, str, list[dict[str, str]] | None]:
        characteristics_url = product_characteristics_url(source_url)
        async with semaphore:
            response = await async_get_with_retry(async_client, characteristics_url)
        persist_client_cookies(async_client)
        if response_is_blocked(response):
            if not allow_browser:
                raise RuntimeError("DNS returned qauth/403 while fetching characteristics.")
            return source_url, characteristics_url, "browser", None
        response.raise_for_status()
        ajax_specs = await fetch_characteristics_via_ajax_async(async_client, characteristics_url, response.text)
        if ajax_specs is not None:
            return source_url, characteristics_url, "ready", ajax_specs
        if allow_browser and characteristics_page_needs_expansion(response.text):
            return source_url, characteristics_url, "browser", None
        return source_url, str(response.url), "ready", parse_characteristics(response.text)

    async with make_async_client(current_process_cookies() or load_cookies_cache(COOKIES_CACHE_PATH, COOKIES_TTL_SECONDS)) as async_client:
        raw_results = await asyncio.gather(*(fetch_one(async_client, source_url) for source_url in urls))
    results: list[dict[str, object]] = []
    for source_url, characteristics_url, mode, specs in raw_results:
        if mode == "browser":
            specs = await fetch_browser_specs(characteristics_url)
        results.append(
            {
                "url": source_url,
                "characteristics_url": characteristics_url,
                "specs": specs or [],
            }
        )
    return results


def save_json(path: str, payload: object) -> None:
    output_path = resolve_output_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_file(path: str) -> object:
    candidate = resolve_project_path(path)
    if not candidate.exists():
        artifact_candidate = ARTIFACTS_DIR / path
        if artifact_candidate.exists():
            candidate = artifact_candidate
    return json.loads(candidate.read_text(encoding="utf-8"))


def resolve_output_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if candidate.parent != Path("."):
        return PROJECT_ROOT / candidate
    return artifact_path(candidate.name)


def get_or_create_cookies(query: str, category: str, reason: str) -> httpx.Cookies:
    cached = current_process_cookies()
    if cached is not None:
        return cached
    cached = load_cookies_cache(COOKIES_CACHE_PATH, COOKIES_TTL_SECONDS)
    if cached is not None:
        set_process_cookies(cached)
        return cached
    return prewarm_dns_cookies(query=query, category=category, reason=reason)


def fetch_characteristics_via_ajax(
    client: httpx.Client,
    characteristics_url: str,
    html: str,
) -> list[dict[str, str]] | None:
    if not hasattr(client, "post"):
        return None
    csrf_token = extract_csrf_token(html)
    product_uuid = extract_product_uuid(html)
    if not csrf_token or not product_uuid:
        return None
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": characteristics_url,
        "X-CSRF-Token": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
    }
    response = client.post(build_characteristics_actual_url(product_uuid), headers=headers)
    if response_is_blocked(response):
        return None
    persist_client_cookies(client)
    response.raise_for_status()
    data = response.json()
    if data.get("result") is not True:
        return None
    actual_html = str(data.get("html", ""))
    return parse_characteristics(actual_html) if actual_html else None


async def fetch_characteristics_via_ajax_async(
    client: httpx.AsyncClient,
    characteristics_url: str,
    html: str,
) -> list[dict[str, str]] | None:
    csrf_token = extract_csrf_token(html)
    product_uuid = extract_product_uuid(html)
    if not csrf_token or not product_uuid:
        return None
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": characteristics_url,
        "X-CSRF-Token": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
    }
    response = await client.post(build_characteristics_actual_url(product_uuid), headers=headers)
    if response_is_blocked(response):
        return None
    persist_client_cookies(client)
    response.raise_for_status()
    data = response.json()
    if data.get("result") is not True:
        return None
    actual_html = str(data.get("html", ""))
    return parse_characteristics(actual_html) if actual_html else None


def bootstrap_cookies(query: str, category: str) -> httpx.Cookies:
    target_url = httpx.URL(BASE_URL + SEARCH_PATH).copy_merge_params(
        build_search_params(query, category, 1)
    )
    cookies, _resolved_url = load_url_in_browser(str(target_url), wait_for_category=False)
    return cookies


def load_url_in_browser(url: str, wait_for_category: bool) -> tuple[httpx.Cookies, str]:
    chrome_path = find_installed_browser()
    if not chrome_path:
        raise RuntimeError("Chrome/Edge was not found; install Playwright browsers or Chrome.")
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright package is required for browser cookie bootstrap.") from exc

    with BROWSER_BOOTSTRAP_LOCK:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=chrome_path,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(locale="ru-RU", viewport={"width": 1365, "height": 900})
            page = context.new_page()
            block_heavy_resources(page)
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if wait_for_category:
                try:
                    page.wait_for_url("**category=**", timeout=15000)
                except PlaywrightTimeoutError:
                    pass
            page.wait_for_selector("body", timeout=45000)
            cookies = to_httpx_cookies(context.cookies(BASE_URL))
            resolved_url = page.url
            browser.close()
    return cookies, resolved_url


def load_page_html_with_browser(url: str) -> str:
    chrome_path = find_installed_browser()
    if not chrome_path:
        raise RuntimeError("Chrome/Edge was not found; install Playwright browsers or Chrome.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright package is required for browser page loading.") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=chrome_path,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(locale="ru-RU", viewport={"width": 1365, "height": 900})
        page = context.new_page()
        block_heavy_resources(page)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("body", timeout=45000)
        expand_all_characteristics(page)
        html = page.content()
        browser.close()
    return html


def expand_all_characteristics(page: object) -> None:
    expand_button = page.locator(".product-characteristics__expand")
    if expand_button.count() == 0:
        return
    expand_button.first.click()
    page.wait_for_timeout(1200)


def block_heavy_resources(page: object) -> None:
    def route_request(route: object) -> None:
        resource_type = route.request.resource_type
        if resource_type in {"image", "media", "font"}:
            route.abort()
            return
        route.continue_()

    page.route("**/*", route_request)


def to_httpx_cookies(playwright_cookies: list[dict]) -> httpx.Cookies:
    cookies = httpx.Cookies()
    for cookie in playwright_cookies:
        domain = str(cookie.get("domain", "")).lstrip(".")
        cookies.set(cookie["name"], cookie["value"], domain=domain, path=cookie.get("path", "/"))
    return cookies


def find_installed_browser() -> str:
    for browser_path in CHROME_PATHS:
        if Path(browser_path).exists():
            return browser_path
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight DNS search parser.")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--category", default="")
    parser.add_argument("--stock", default="")
    parser.add_argument("--price", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", default="")
    parser.add_argument("--inspect-url", default="")
    parser.add_argument("--inspect-output", default=str(artifact_path("dns_filters_report.json")))
    parser.add_argument("--inspect-section-filters", default="")
    parser.add_argument("--inspect-section-output", default=str(artifact_path("dns_section_filters.json")))
    parser.add_argument("--build-section-url", default="")
    parser.add_argument("--build-section-input", default="")
    parser.add_argument("--build-section-output", default=str(artifact_path("dns_built_section_url.json")))
    parser.add_argument("--characteristics-urls", default="")
    parser.add_argument("--characteristics-output", default=str(artifact_path("dns_characteristics.json")))
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> int:
    ensure_runtime_directories()
    args = parse_args()
    try:
        if args.inspect_url:
            report = inspect_dns_url_params(args.inspect_url)
            save_json(args.inspect_output, report)
            print(json.dumps({"output": args.inspect_output}, ensure_ascii=False))
            return 0
        if args.inspect_section_filters:
            report = inspect_dns_section_filters(args.inspect_section_filters)
            save_json(args.inspect_section_output, report)
            print(json.dumps({"output": args.inspect_section_output, "count": report["count"]}, ensure_ascii=False))
            return 0
        if args.build_section_url:
            section_map = inspect_dns_section_filters(args.build_section_url)
            selected_filters = load_json_file(args.build_section_input) if args.build_section_input else []
            built_url = build_dns_url_from_section_filters(
                args.build_section_url,
                selected_filters if isinstance(selected_filters, list) else [],
                section_map["filters"] if isinstance(section_map.get("filters"), list) else [],
            )
            payload = {"url": built_url, "count": len(selected_filters) if isinstance(selected_filters, list) else 0}
            save_json(args.build_section_output, payload)
            print(json.dumps({"output": args.build_section_output, "url": built_url}, ensure_ascii=False))
            return 0
        if args.characteristics_urls:
            urls = parse_characteristics_urls(args.characteristics_urls)
            payload = {
                "count": len(urls),
                "items": fetch_characteristics_for_urls(urls, allow_browser=not args.no_browser),
            }
            save_json(args.characteristics_output, payload)
            print(json.dumps({"output": args.characteristics_output, "count": len(urls)}, ensure_ascii=False))
            return 0
        products, mode, requested_url, resolved_url = collect_products_by_url(
            input_value=args.url or args.query,
            limit=args.limit,
            category=args.category,
            stock=args.stock,
            price=args.price,
            allow_browser=not args.no_browser,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    products, stats = postprocess_products(products, query=known_query_params(resolved_url).get("q", ""))
    payload = build_result_payload(mode, requested_url, resolved_url, products, stats)
    output = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = resolve_output_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(json.dumps({"mode": mode, "count": len(products), "output": str(output_path)}, ensure_ascii=False))
        return 0
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
