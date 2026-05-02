import json
import asyncio
import time
from pathlib import Path
from unittest.mock import patch

from app.dns_search_parser import (
    DnsFilterSelectionError,
    Product,
    COOKIES_TTL_SECONDS,
    DEFAULT_CONCURRENCY,
    BLOCKED_AFTER_BOOTSTRAP,
    build_category_resolution_url,
    build_compare_url,
    build_search_filters_endpoint_url,
    build_search_filters_extended_endpoint_url,
    build_search_filters_headers,
    build_section_filters_url,
    build_dns_url_from_section_filters,
    build_characteristics_actual_url,
    build_product_buy_payload,
    build_result_payload,
    build_search_page_url,
    characteristics_page_needs_expansion,
    browser_resolve_url,
    classify_query_params,
    collect_products_by_url,
    collect_products_from_url_async,
    cookies_cache_is_fresh,
    expand_all_characteristics,
    compare_specs_from_table,
    extract_compare_table,
    fetch_pages_batch_async,
    fetch_compare_characteristics_for_products,
    fetch_characteristics_for_urls,
    fetch_characteristics_via_ajax,
    extract_prices,
    extract_product_uuid,
    invalidate_cookies_cache,
    inspect_dns_url_params,
    inspect_dns_section_filters,
    prewarm_dns_cookies,
    current_process_cookies,
    load_cookies_cache,
    map_dns_filter_block,
    extract_extended_filters,
    build_selected_price_value,
    resolve_selected_value_ids,
    find_filter_block,
    http_resolve_url,
    parse_characteristics,
    parse_compare_table,
    parse_characteristics_urls,
    format_progress,
    get_or_create_cookies,
    normalize_dns_url,
    parse_cards,
    postprocess_products,
    product_characteristics_url,
    resolve_category_if_missing,
    save_cookies_cache,
    to_httpx_cookies,
)


HTML = """
<html><body>
  <div class="catalog-product" data-code="0124851">
    <a class="catalog-product__name ui-link" href="/product/id/keyboard/"> Keyboard  A </a>
    <span id="as-buy-1" class="catalog-product__buy product-buy"></span>
  </div>
  <div class="catalog-product" data-code="999">
    <a class="catalog-product__name ui-link" href="/product/id/missing-buy/">Broken</a>
  </div>
</body></html>
"""


def test_parse_cards_extracts_name_link_code_and_buy_container() -> None:
    cards = parse_cards(HTML)

    assert len(cards) == 1
    assert cards[0].name == "Keyboard A"
    assert cards[0].code == "0124851"
    assert cards[0].buy_container_id == "as-buy-1"
    assert cards[0].url == "https://www.dns-shop.ru/product/id/keyboard/"


def test_inspect_dns_section_filters_retries_with_browser_on_blocked_bootstrap() -> None:
    calls = []

    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    responses = [
        RuntimeError(BLOCKED_AFTER_BOOTSTRAP),
        {"data": {"filters": [{"id": "price", "name": "Цена", "type": "range-checkbox", "values": []}]}},
        {"data": {"groups": []}},
    ]

    def fake_fetch_search_filters_payload(*args, **kwargs):
        calls.append(kwargs.get("endpoint_url") or args[1])
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch("app.dns_search_parser.get_or_create_cookies", return_value=to_httpx_cookies([])), patch(
        "app.dns_search_parser.recover_dns_cookies", return_value=to_httpx_cookies([])
    ), patch("app.dns_search_parser.make_client", return_value=DummyClient()), patch(
        "app.dns_search_parser.fetch_search_filters_payload", side_effect=fake_fetch_search_filters_payload
    ):
        report = inspect_dns_section_filters("https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&category=17a8a01d16404e77")

    assert report["count"] == 1
    assert len(calls) == 3


def test_parse_cards_moves_bracket_specs_out_of_product_name() -> None:
    html = """
    <html><body>
      <div class="catalog-product" data-code="0124851">
        <a class="catalog-product__name ui-link" href="/product/id/monitor/">
          27" Монитор Samsung ViewFinity S6 S60UD S27D604UAI черный [2560x1440@100 Гц, IPS, LED, 1000:1, 350 Кд/м², DisplayPort 1.4, HDMI 2.0, USB Type-C, USB х3 шт]
        </a>
        <span id="as-buy-1" class="catalog-product__buy product-buy"></span>
      </div>
    </body></html>
    """

    cards = parse_cards(html)

    assert len(cards) == 1
    assert cards[0].name == '27" Монитор Samsung ViewFinity S6 S60UD S27D604UAI черный'
    assert "[" not in cards[0].name
    assert cards[0].specs == [
        {"name": "Разрешение и частота", "value": "2560x1440@100 Гц"},
        {"name": "Тип матрицы", "value": "IPS"},
        {"name": "Подсветка", "value": "LED"},
        {"name": "Контрастность", "value": "1000:1"},
        {"name": "Яркость", "value": "350 Кд/м²"},
        {"name": "Интерфейсы", "value": "DisplayPort 1.4, HDMI 2.0, USB Type-C"},
        {"name": "USB", "value": "USB х3 шт"},
    ]


def test_build_product_buy_payload_uses_dns_ajax_state_shape() -> None:
    cards = parse_cards(HTML)

    payload = json.loads(build_product_buy_payload(cards))

    assert payload == {
        "type": "product-buy",
        "containers": [{"id": "as-buy-1", "data": {"id": "0124851"}}],
    }


def test_extract_prices_maps_container_id_to_current_price() -> None:
    response = {
        "data": {
            "states": [
                {"id": "as-buy-1", "data": {"price": {"current": 850}}},
                {"id": "as-buy-2", "data": {"price": {}}},
            ]
        }
    }

    assert extract_prices(response) == {"as-buy-1": 850}


def test_format_progress_shows_current_page_and_count() -> None:
    assert format_progress(3, 54, 200) == "Страница 3: собрано 54/200"


def test_format_progress_supports_unlimited_mode() -> None:
    assert format_progress(3, 54, None) == "Страница 3: собрано 54"


def test_normalize_dns_url_accepts_full_url_without_category() -> None:
    url = normalize_dns_url("https://www.dns-shop.ru/search/?q=смартфон")

    assert url == "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD"


def test_normalize_dns_url_accepts_plain_query_and_flags() -> None:
    url = normalize_dns_url(
        "смартфон",
        category="17a8a01d16404e77",
        stock="now-out_of_stock",
        price="10000-20000",
    )

    assert url == (
        "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&category=17a8a01d16404e77"
        "&stock=now-out_of_stock&price=10000-20000"
    )


def test_normalize_dns_url_keeps_unknown_params() -> None:
    url = normalize_dns_url("https://www.dns-shop.ru/search/?q=смартфон&brand=abc123&f=some_hash")

    assert url == "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&brand=abc123&f=some_hash"


def test_build_search_page_url_keeps_flags_and_unknown_params() -> None:
    url = build_search_page_url(
        "https://www.dns-shop.ru/search/?q=смартфон&category=cat&stock=now&brand=abc", 2
    )

    assert url == (
        "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD"
        "&category=cat&stock=now&brand=abc&p=2"
    )


def test_classify_query_params_splits_known_and_unknown() -> None:
    result = classify_query_params(
        "https://www.dns-shop.ru/search/?q=смартфон&category=cat&stock=now&price=1-2&brand=abc"
    )

    assert result == {
        "known": {"q": "смартфон", "category": "cat", "stock": "now", "price": "1-2"},
        "unknown": {"brand": "abc"},
    }


def test_build_category_resolution_url_uses_only_base_query() -> None:
    url = build_category_resolution_url(
        "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD"
        "&stock=now-out_of_stock&price=15001-30000&brand=abc123"
    )

    assert url == "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD"


def test_resolve_category_if_missing_does_not_call_resolver_when_category_exists() -> None:
    calls = []
    url = "https://www.dns-shop.ru/search/?q=смартфон&category=cat"

    assert resolve_category_if_missing(url, lambda value: calls.append(value) or value) == url
    assert calls == []


def test_resolve_category_if_missing_uses_loaded_url_category() -> None:
    url = "https://www.dns-shop.ru/search/?q=смартфон"
    resolved = "https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77"

    assert resolve_category_if_missing(url, lambda value: resolved) == (
        "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&category=17a8a01d16404e77"
    )


def test_resolve_category_if_missing_preserves_existing_flags() -> None:
    url = (
        "https://www.dns-shop.ru/search/?q=смартфон&stock=now-out_of_stock"
        "&price=10000-20000&brand=abc123"
    )
    resolved = "https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77"

    assert resolve_category_if_missing(url, lambda value: resolved) == (
        "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD&stock=now-out_of_stock"
        "&price=10000-20000&brand=abc123&category=17a8a01d16404e77"
    )


def test_browser_resolve_url_uses_browser_page_url_and_saves_cookies() -> None:
    saved = {}
    fake_cookies = object()
    url = "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82%D1%84%D0%BE%D0%BD"
    resolved = f"{url}&category=17a8a01d16404e77"

    with patch("app.dns_search_parser.load_url_in_browser", return_value=(fake_cookies, resolved)) as loader:
        with patch("app.dns_search_parser.save_cookies_cache") as saver:
            result = browser_resolve_url(url)
            saved["args"] = saver.call_args[0]

    assert result == resolved
    loader.assert_called_once_with(url, wait_for_category=True)
    assert saved["args"][0] is fake_cookies


def test_http_resolve_url_persists_updated_client_cookies() -> None:
    class FakeResponse:
        status_code = 200
        url = "https://www.dns-shop.ru/search/?q=телевизор&category=cat"
        text = ""

        def raise_for_status(self) -> None:
            return None

    fake_cookies = to_httpx_cookies([{"name": "foo", "value": "bar", "domain": "www.dns-shop.ru", "path": "/"}])

    class FakeClient:
        def __init__(self) -> None:
            self.cookies = fake_cookies

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str):
            return FakeResponse()

    with patch("app.dns_search_parser.make_client", return_value=FakeClient()):
        with patch("app.dns_search_parser.save_cookies_cache") as saver:
            result = http_resolve_url("https://www.dns-shop.ru/search/?q=телевизор")

    assert result == "https://www.dns-shop.ru/search/?q=телевизор&category=cat"
    saver.assert_called_once()


def test_collect_products_by_url_uses_cached_cookies_on_first_request() -> None:
    fake_cookies = to_httpx_cookies([{"name": "foo", "value": "bar", "domain": "www.dns-shop.ru", "path": "/"}])
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "<html></html>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, cookies):
            self.cookies = cookies

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_make_client(cookies=None):
        captured["cookies"] = cookies
        return FakeClient(cookies)

    with patch("app.dns_search_parser.resolve_category_if_missing", return_value="https://www.dns-shop.ru/search/?q=телевизор&category=cat"):
        with patch("app.dns_search_parser.get_or_create_cookies", return_value=fake_cookies):
            with patch("app.dns_search_parser.make_client", side_effect=fake_make_client):
                with patch("app.dns_search_parser.fetch_search_page_by_url", return_value=FakeResponse()):
                    with patch("app.dns_search_parser.collect_products_from_url_async", return_value=[]):
                        collect_products_by_url("телевизор", 10, allow_browser=True)

    assert captured["cookies"] is fake_cookies


def test_collect_products_by_url_skips_category_resolve_when_category_already_present() -> None:
    class FakeResponse:
        status_code = 200
        text = "<html></html>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, cookies):
            self.cookies = cookies

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    source_url = "https://www.dns-shop.ru/search/?q=%D1%82%D0%B5%D0%BB%D0%B5%D0%B2%D0%B8%D0%B7%D0%BE%D1%80&category=cat&price=1-2"
    with patch("app.dns_search_parser.resolve_category_if_missing", return_value=source_url) as resolver:
        with patch("app.dns_search_parser.get_or_create_cookies", return_value=None):
            with patch("app.dns_search_parser.make_client", side_effect=lambda cookies=None: FakeClient(cookies)):
                with patch("app.dns_search_parser.fetch_search_page_by_url", return_value=FakeResponse()):
                    with patch("app.dns_search_parser.collect_products_from_url_async", return_value=[]):
                        collect_products_by_url(
                            source_url,
                            10,
                            allow_browser=True,
                        )

    resolver.assert_not_called()


def test_postprocess_products_dedupes_and_filters_keyboard_noise() -> None:
    products = [
        Product("Клавиатура A", 100, "https://example/a", "1"),
        Product("Клавиатура duplicate", 100, "https://example/a-copy", "1"),
        Product("Цифровой блок 8BitDo", 100, "https://example/b", "2"),
        Product("Клавиатура B", 200, "https://example/c", ""),
    ]

    processed, stats = postprocess_products(products, query="клавиатура")

    assert [product.name for product in processed] == ["Клавиатура A", "Клавиатура B"]
    assert stats == {
        "raw_count": 4,
        "dedup_count": 3,
        "filtered_count": 2,
        "skipped_duplicates": 1,
        "skipped_noise": 1,
    }


def test_product_characteristics_url_from_product_url() -> None:
    url = "https://www.dns-shop.ru/product/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/"

    assert product_characteristics_url(url) == (
        "https://www.dns-shop.ru/product/characteristics/7ffd0cf6a89cd21a/"
        "667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/"
    )


def test_parse_characteristics_extracts_specs() -> None:
    html = """
    <div class="product-characteristics__spec">
      <div class="product-characteristics__spec-title">Объем памяти</div>
      <div class="product-characteristics__spec-value">256 ГБ</div>
    </div>
    """

    assert parse_characteristics(html) == [{"name": "Объем памяти", "value": "256 ГБ"}]


def test_extract_compare_table_and_specs_map_rows_by_product_order() -> None:
    html = """
    <html><body>
      <div class="products-slider">
        <div class="products-slider__item">
          <a class="products-slider__product-name">Phone A</a>
          <span class="products-slider__score-points">4.8</span>
        </div>
        <div class="products-slider__item">
          <a class="products-slider__product-name">Phone B</a>
          <span class="products-slider__score-points">4.7</span>
        </div>
      </div>
      <div class="compare-table">
        <section>
          <article class="group-table">
            <div class="group-table__header">Экран</div>
            <div class="group-table__option-wrapper">
              <div class="group-table__option-name">Диагональ</div>
              <div class="group-table__data">
                <div class="group-table__product-value">6.1"</div>
                <div class="group-table__product-value">6.7"</div>
              </div>
            </div>
            <div class="group-table__option-wrapper">
              <div class="group-table__option-name">Частота</div>
              <div class="group-table__data">
                <div class="group-table__product-value">120 Гц</div>
                <div class="group-table__product-value">60 Гц</div>
              </div>
            </div>
          </article>
        </section>
      </div>
    </body></html>
    """

    parsed = parse_compare_table(html)
    specs_by_index = compare_specs_from_table(parsed, 2)

    assert parsed["products"] == [
        {"index": 0, "name": "Phone A", "score": "4.8"},
        {"index": 1, "name": "Phone B", "score": "4.7"},
    ]
    assert parsed["groups"] == [
        {
            "name": "Экран",
            "rows": [
                {"label": "Диагональ", "values": ['6.1"', '6.7"']},
                {"label": "Частота", "values": ["120 Гц", "60 Гц"]},
            ],
        }
    ]
    assert specs_by_index == [
        [{"name": "Диагональ", "value": '6.1"'}, {"name": "Частота", "value": "120 Гц"}],
        [{"name": "Диагональ", "value": '6.7"'}, {"name": "Частота", "value": "60 Гц"}],
    ]


def test_fetch_compare_characteristics_for_products_uses_compare_link_once() -> None:
    compare_url = build_compare_url("128", ["111", "222"])
    products = [
        Product("Phone A", 10000, "https://www.dns-shop.ru/product/111/phone-a/", "111"),
        Product("Phone B", 20000, "https://www.dns-shop.ru/product/222/phone-b/", "222"),
    ]

    def loader(url: str) -> str:
        assert url == compare_url
        return """
        <html><body>
          <div class="compare-table">
            <section>
              <article class="group-table">
                <div class="group-table__header">Память</div>
                <div class="group-table__option-wrapper">
                  <div class="group-table__option-name">ОЗУ</div>
                  <div class="group-table__data">
                    <div class="group-table__product-value">8 ГБ</div>
                    <div class="group-table__product-value">12 ГБ</div>
                  </div>
                </div>
              </article>
            </section>
          </div>
        </body></html>
        """

    items = fetch_compare_characteristics_for_products(products, allow_browser=True, browser_loader=loader)

    assert items == [
        {
            "url": "https://www.dns-shop.ru/product/111/phone-a/",
            "characteristics_url": compare_url,
            "compare_url": compare_url,
            "specs": [{"name": "ОЗУ", "value": "8 ГБ"}],
        },
        {
            "url": "https://www.dns-shop.ru/product/222/phone-b/",
            "characteristics_url": compare_url,
            "compare_url": compare_url,
            "specs": [{"name": "ОЗУ", "value": "12 ГБ"}],
        },
    ]


def test_parse_characteristics_urls_accepts_lines_and_commas() -> None:
    raw = "https://example/a/, https://example/b/\nhttps://example/c/"

    assert parse_characteristics_urls(raw) == ["https://example/a/", "https://example/b/", "https://example/c/"]


def test_inspect_dns_url_params_returns_known_and_unknown_maps() -> None:
    report = inspect_dns_url_params(
        "https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77&stock=now&price=10000-20000&brand=abc123"
    )

    assert report == {
        "url": "https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77&stock=now&price=10000-20000&brand=abc123",
        "known_params": {
            "q": "смартфон",
            "category": "17a8a01d16404e77",
            "stock": "now",
            "price": "10000-20000",
        },
        "unknown_params": {"brand": "abc123"},
    }


def test_build_section_filters_url_keeps_only_query_and_category() -> None:
    value = build_section_filters_url(
        "https://www.dns-shop.ru/search/?q=планшет&category=17a8a05316404e77&f[1bm]=cn9&price=10000-20000"
    )

    assert value == (
        "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82"
        "&category=17a8a05316404e77"
    )

def test_build_search_filters_extended_endpoint_url_uses_query_and_category() -> None:
    value = build_search_filters_extended_endpoint_url(
        "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82&category=17a8a05316404e77"
    )

    assert value == (
        "https://www.dns-shop.ru/catalog/search/filters-extended/?category=17a8a05316404e77"
        "&q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82"
    )


def test_build_search_filters_endpoint_url_uses_query_and_category() -> None:
    value = build_search_filters_endpoint_url(
        "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82&category=17a8a05316404e77"
    )

    assert value == (
        "https://www.dns-shop.ru/catalog/search/filters/?category=17a8a05316404e77"
        "&q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82"
    )


def test_build_search_filters_headers_uses_section_url_as_referer() -> None:
    section_url = "https://www.dns-shop.ru/search/?q=%D0%BF%D0%BB%D0%B0%D0%BD%D1%88%D0%B5%D1%82&category=17a8a05316404e77"

    assert build_search_filters_headers(section_url) == {
        "Accept": "*/*",
        "Referer": section_url,
        "X-Requested-With": "XMLHttpRequest",
    }


def test_map_dns_filter_block_keeps_all_values_including_zero_count() -> None:
    block = {
        "id": "f[1bm]",
        "label": "Тип клавиатуры",
        "type": "checkbox",
        "isSpec": True,
        "selected": ["cn9"],
        "default": [],
        "variants": [
            {"id": "cn9", "label": "магнитная", "count": 168},
            {"id": "79w", "label": "механическая", "count": 0},
        ],
    }

    result = map_dns_filter_block(block, "left")

    assert result == {
        "group": "left",
        "id": "f[1bm]",
        "name": "Тип клавиатуры",
        "type": "checkbox",
        "is_spec": True,
        "values": [
            {"id": "cn9", "name": "магнитная", "count": 168},
            {"id": "79w", "name": "механическая", "count": 0},
        ],
        "selected": ["cn9"],
        "default": [],
    }


def test_inspect_dns_section_filters_returns_structured_filter_map() -> None:
    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self.status_code = 200
            self._payload = payload
            self.text = json.dumps(payload, ensure_ascii=False)

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeClient:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str, headers: dict[str, str]):
            self.urls.append(url)
            self.headers = headers
            if "/filters-extended/" in url:
                return FakeResponse(
                    {
                        "result": True,
                        "data": {
                            "groups": [
                                {
                                    "title": "Основные",
                                    "blocks": [
                                        {
                                            "id": "stock",
                                            "label": "Наличие",
                                            "type": "checkbox",
                                            "variants": [
                                                {"id": "now", "label": "В наличии", "count": None},
                                                {"id": "out_of_stock", "label": "Отсутствующие в продаже", "count": 0},
                                            ],
                                            "selected": [],
                                            "default": ["now", "out_of_stock"],
                                        },
                                        {
                                            "id": "f[1bm]",
                                            "label": "Тип клавиатуры",
                                            "type": "checkbox",
                                            "isSpec": True,
                                            "variants": [
                                                {"id": "cn9", "label": "магнитная", "count": 168},
                                                {"id": "79w", "label": "механическая", "count": 0},
                                            ],
                                            "selected": [],
                                            "default": [],
                                        },
                                    ],
                                }
                            ]
                        },
                    }
                )
            return FakeResponse(
                {
                    "data": {
                        "filters": [
                            {
                                "id": "f[2d]",
                                "label": "Разрешение экрана",
                                "type": "checkbox",
                                "isSpec": True,
                                "variants": [{"id": "1080", "label": "1920x1080", "count": 12}],
                                "selected": [],
                                "default": [],
                            }
                        ]
                    }
                }
            )

    fake_client = FakeClient()

    with patch("app.dns_search_parser.get_or_create_cookies", return_value=None):
        result = inspect_dns_section_filters(
            "https://www.dns-shop.ru/search/?q=клавиатура&category=17a8950d16404e77",
            client_factory=lambda: fake_client,
        )

    assert fake_client.urls == [
        "https://www.dns-shop.ru/catalog/search/filters/?category=17a8950d16404e77"
        "&q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0",
        "https://www.dns-shop.ru/catalog/search/filters-extended/?category=17a8950d16404e77"
        "&q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0",
    ]
    assert result == {
        "url": "https://www.dns-shop.ru/search/?q=клавиатура&category=17a8950d16404e77",
        "section_url": "https://www.dns-shop.ru/search/?q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0&category=17a8950d16404e77",
        "query": "клавиатура",
        "category": "17a8950d16404e77",
        "count": 3,
        "filters": [
            {
                "group": "base",
                "id": "f[2d]",
                "name": "Разрешение экрана",
                "type": "checkbox",
                "is_spec": True,
                "values": [{"id": "1080", "name": "1920x1080", "count": 12}],
                "selected": [],
                "default": [],
            },
            {
                "group": "Основные",
                "id": "stock",
                "name": "Наличие",
                "type": "checkbox",
                "is_spec": False,
                "values": [
                    {"id": "now", "name": "В наличии", "count": None},
                    {"id": "out_of_stock", "name": "Отсутствующие в продаже", "count": 0},
                ],
                "selected": [],
                "default": ["now", "out_of_stock"],
            },
            {
                "group": "Основные",
                "id": "f[1bm]",
                "name": "Тип клавиатуры",
                "type": "checkbox",
                "is_spec": True,
                "values": [
                    {"id": "cn9", "name": "магнитная", "count": 168},
                    {"id": "79w", "name": "механическая", "count": 0},
                ],
                "selected": [],
                "default": [],
            },
        ],
    }


def test_extract_extended_filters_preserves_group_and_values() -> None:
    ext_payload = {
        "data": {
            "groups": [
                {
                    "title": "Основные",
                    "blocks": [
                        {
                            "id": "f[1bm]",
                            "label": "Тип клавиатуры",
                            "type": "checkbox",
                            "variants": [
                                {"id": "cn9", "label": "магнитная", "count": 10},
                                {"id": "79w", "label": "механическая", "count": 0},
                            ],
                        },
                        {
                            "id": "f[2d]",
                            "label": "Разрешение экрана",
                            "type": "checkbox",
                            "variants": [{"id": "1080", "label": "1920x1080", "count": 1}],
                        },
                    ],
                }
            ]
        }
    }

    merged = extract_extended_filters(ext_payload)

    assert [item["id"] for item in merged] == ["f[1bm]", "f[2d]"]
    assert merged[0]["values"] == [
        {"id": "cn9", "name": "магнитная", "count": 10},
        {"id": "79w", "name": "механическая", "count": 0},
    ]


def test_find_filter_block_supports_lookup_by_name_and_id() -> None:
    filters = [
        {"id": "stock", "name": "Наличие"},
        {"id": "f[1bm]", "name": "Тип клавиатуры"},
    ]

    assert find_filter_block(filters, {"name": "Тип клавиатуры"}) == {"id": "f[1bm]", "name": "Тип клавиатуры"}
    assert find_filter_block(filters, {"id": "stock"}) == {"id": "stock", "name": "Наличие"}


def test_resolve_selected_value_ids_supports_names_and_ids() -> None:
    block = {
        "values": [
            {"id": "cn9", "name": "магнитная"},
            {"id": "79w", "name": "механическая"},
        ]
    }

    result, missing = resolve_selected_value_ids(
        block,
        {"values": [{"name": "магнитная"}, {"id": "79w"}]},
    )

    assert result == ["cn9", "79w"]
    assert missing == []


def test_build_selected_price_value_builds_dns_range() -> None:
    assert build_selected_price_value({"min": 10000, "max": 20000}) == "10000-20000"
    assert build_selected_price_value({"min": "", "max": ""}) == ""


def test_build_dns_url_from_section_filters_builds_checkbox_stock_price_and_toggle() -> None:
    available_filters = [
        {
            "id": "stock",
            "name": "Наличие",
            "type": "checkbox",
            "values": [
                {"id": "now", "name": "В наличии"},
                {"id": "out_of_stock", "name": "Отсутствующие в продаже"},
            ],
        },
        {
            "id": "price",
            "name": "Цена",
            "type": "range-checkbox",
            "values": [],
        },
        {
            "id": "rating",
            "name": "Рейтинг 4 и выше",
            "type": "toggle",
            "values": [],
        },
        {
            "id": "f[1bm]",
            "name": "Тип клавиатуры",
            "type": "checkbox",
            "values": [
                {"id": "cn9", "name": "магнитная"},
                {"id": "79w", "name": "механическая"},
            ],
        },
        {
            "id": "f[1h3]",
            "name": "Подсветка клавиш",
            "type": "checkbox",
            "values": [
                {"id": "21", "name": "есть"},
                {"id": "22", "name": "нет"},
            ],
        },
    ]
    selected_filters = [
        {"name": "Тип клавиатуры", "values": [{"name": "магнитная"}, {"name": "механическая"}]},
        {"name": "Подсветка клавиш", "values": [{"name": "есть"}]},
        {"name": "Наличие", "values": [{"id": "now"}, {"id": "out_of_stock"}]},
        {"name": "Цена", "min": 10000, "max": 20000},
        {"name": "Рейтинг 4 и выше", "enabled": True},
    ]

    result = build_dns_url_from_section_filters(
        "https://www.dns-shop.ru/search/?q=клавиатура&category=17a8950d16404e77",
        selected_filters,
        available_filters,
    )

    assert result == (
        "https://www.dns-shop.ru/search/?q=%D0%BA%D0%BB%D0%B0%D0%B2%D0%B8%D0%B0%D1%82%D1%83%D1%80%D0%B0"
        "&category=17a8950d16404e77&stock=now-out_of_stock&price=10000-20000"
        "&f%5B1bm%5D=cn9-79w&f%5B1h3%5D=21&rating=1"
    )


def test_build_dns_url_from_section_filters_fails_for_unknown_filter() -> None:
    available_filters = [{"id": "stock", "name": "Наличие", "type": "checkbox", "values": []}]

    try:
        build_dns_url_from_section_filters(
            "https://www.dns-shop.ru/search/?q=клавиатура&category=17a8950d16404e77",
            [{"name": "Несуществующий фильтр", "values": [{"id": "x"}]}],
            available_filters,
        )
    except DnsFilterSelectionError as exc:
        assert exc.details["missing_filter_ids"] == ["Несуществующий фильтр"]
        assert exc.details["missing_value_ids"] == []
    else:
        raise AssertionError("Expected DnsFilterSelectionError")


def test_build_result_payload_uses_new_json_shape() -> None:
    products = [Product("Клавиатура A", 100, "https://example/a", "1", [{"name": "Тип", "value": "мембранная"}])]
    processed, stats = postprocess_products(products, query="клавиатура")

    payload = build_result_payload(
        mode="browser-cookies+httpx",
        url="https://www.dns-shop.ru/search/?q=клавиатура&brand=abc",
        resolved_url="https://www.dns-shop.ru/search/?q=клавиатура&category=cat&brand=abc",
        products=processed,
        stats=stats,
    )

    assert payload == {
        "mode": "browser-cookies+httpx",
        "url": "https://www.dns-shop.ru/search/?q=клавиатура&brand=abc",
        "resolved_url": "https://www.dns-shop.ru/search/?q=клавиатура&category=cat&brand=abc",
        "filters": {
            "category": "cat",
            "stock": "",
            "price": "",
            "unknown": {"brand": "abc"},
        },
        "stats": stats,
        "count": 1,
        "products": [
            {
                "name": "Клавиатура A",
                "price": 100,
                "url": "https://example/a",
                "code": "1",
                "specs": [{"name": "Тип", "value": "мембранная"}],
            }
        ],
    }


def test_fetch_characteristics_for_urls_uses_browser_loader_when_http_is_blocked() -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int, url: str):
            self.text = text
            self.status_code = status_code
            self.url = url

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str):
            return FakeResponse("qauth", 403, url)

    items = fetch_characteristics_for_urls(
        ["https://www.dns-shop.ru/product/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/"],
        allow_browser=True,
        client_factory=lambda: FakeClient(),
        browser_loader=lambda url: """
        <div class=\"product-characteristics__spec\">
          <div class=\"product-characteristics__spec-title\">Экран</div>
          <div class=\"product-characteristics__spec-value\">6.67</div>
        </div>
        """,
    )

    assert items == [
        {
            "url": "https://www.dns-shop.ru/product/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/",
            "characteristics_url": "https://www.dns-shop.ru/product/characteristics/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/",
            "specs": [{"name": "Экран", "value": "6.67"}],
        }
    ]


def test_fetch_characteristics_for_urls_uses_browser_loader_when_page_is_collapsed() -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int, url: str):
            self.text = text
            self.status_code = status_code
            self.url = url

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str):
            return FakeResponse(
                '<div class="product-characteristics product-characteristics_collapsed"><button class="product-characteristics__expand">Развернуть все</button></div>',
                200,
                url,
            )

    items = fetch_characteristics_for_urls(
        ["https://www.dns-shop.ru/product/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/"],
        allow_browser=True,
        client_factory=lambda: FakeClient(),
        browser_loader=lambda url: """
        <div class=\"product-characteristics__spec\">
          <div class=\"product-characteristics__spec-title\">Экран</div>
          <div class=\"product-characteristics__spec-value\">6.67</div>
        </div>
        """,
    )

    assert items == [
        {
            "url": "https://www.dns-shop.ru/product/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/",
            "characteristics_url": "https://www.dns-shop.ru/product/characteristics/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/",
            "specs": [{"name": "Экран", "value": "6.67"}],
        }
    ]


def test_fetch_characteristics_for_urls_async_limits_browser_fallback_to_one(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200, url: str = "https://example") -> None:
            self.text = text
            self.status_code = status_code
            self.url = url

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.cookies = to_httpx_cookies([{"name": "foo", "value": "bar", "domain": "www.dns-shop.ru", "path": "/"}])

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):
            class PostResponse:
                text = "qauth"
                status_code = 403

                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return {"result": False}

            return PostResponse()

    active = {"value": 0, "max": 0}

    async def fake_get(_client, _url):
        return FakeResponse("qauth", 403, "https://example/specs")

    def fake_browser_loader(_url: str) -> str:
        active["value"] += 1
        active["max"] = max(active["max"], active["value"])
        time.sleep(0.02)
        active["value"] -= 1
        return """
        <div class=\"product-characteristics__spec\">
          <div class=\"product-characteristics__spec-title\">Экран</div>
          <div class=\"product-characteristics__spec-value\">6.67</div>
        </div>
        """

    monkeypatch.setattr("app.dns_search_parser.make_async_client", lambda cookies=None: FakeAsyncClient())
    monkeypatch.setattr("app.dns_search_parser.async_get_with_retry", fake_get)
    monkeypatch.setattr("app.dns_search_parser.load_page_html_with_browser", fake_browser_loader)

    items = fetch_characteristics_for_urls(
        [
            "https://www.dns-shop.ru/product/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/",
            "https://www.dns-shop.ru/product/8ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-belyj/",
        ],
        allow_browser=True,
    )

    assert len(items) == 2
    assert active["max"] == 1


def test_fetch_characteristics_via_ajax_uses_uuid_and_csrf_from_html() -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200, url: str = "https://example") -> None:
            self.text = text
            self.status_code = status_code
            self.url = url

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return json.loads(self.text)

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str]]] = []

        def post(self, url: str, headers: dict[str, str]):
            self.calls.append((url, headers))
            return FakeResponse(
                json.dumps(
                    {
                        "result": True,
                        "html": """
                        <div class=\"product-characteristics__spec\">
                          <div class=\"product-characteristics__spec-title\">Bluetooth</div>
                          <div class=\"product-characteristics__spec-value\">5.3</div>
                        </div>
                        """,
                    }
                )
            )

    html = """
    <meta name="csrf-token" content="csrf-token-value">
    <script>
      const productId = "da6aaf30-b8d4-11ed-90a8-00155d8ed20b";
    </script>
    """
    client = FakeClient()

    specs = fetch_characteristics_via_ajax(
        client,
        "https://www.dns-shop.ru/product/characteristics/da6aaf30b8d4ed20/test/",
        html,
    )

    assert specs == [{"name": "Bluetooth", "value": "5.3"}]
    assert client.calls == [
        (
            build_characteristics_actual_url("da6aaf30-b8d4-11ed-90a8-00155d8ed20b"),
            {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://www.dns-shop.ru/product/characteristics/da6aaf30b8d4ed20/test/",
                "X-CSRF-Token": "csrf-token-value",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
    ]


def test_expand_all_characteristics_clicks_expand_button_once() -> None:
    class FakeLocator:
        def __init__(self, present: bool) -> None:
            self.present = present
            self.clicked = 0

        def count(self) -> int:
            return 1 if self.present else 0

        @property
        def first(self):
            return self

        def click(self) -> None:
            self.clicked += 1

    class FakePage:
        def __init__(self, present: bool) -> None:
            self.loc = FakeLocator(present)
            self.waited = 0

        def locator(self, _selector: str):
            return self.loc

        def wait_for_timeout(self, value: int) -> None:
            self.waited = value

    page = FakePage(True)
    expand_all_characteristics(page)

    assert page.loc.clicked == 1
    assert page.waited == 1200


def test_characteristics_page_needs_expansion_detects_collapsed_block() -> None:
    html = '<div class="product-characteristics product-characteristics_collapsed"><button class="product-characteristics__expand">Развернуть все</button></div>'

    assert characteristics_page_needs_expansion(html) is True
    assert characteristics_page_needs_expansion("<div>plain</div>") is False


def test_extract_product_uuid_returns_last_uuid() -> None:
    html = """
    <div>17a8a58c-1640-11e5-a679-00259074e77d</div>
    <div>da6aaf30-b8d4-11ed-90a8-00155d8ed20b</div>
    """

    assert extract_product_uuid(html) == "da6aaf30-b8d4-11ed-90a8-00155d8ed20b"


def test_cookies_cache_roundtrip_and_ttl(tmp_path: Path) -> None:
    cache_path = tmp_path / "cookies.json"
    cookies = to_httpx_cookies(
        [{"name": "PHPSESSID", "value": "abc", "domain": "www.dns-shop.ru", "path": "/"}]
    )

    save_cookies_cache(cookies, cache_path)

    assert cookies_cache_is_fresh(cache_path, COOKIES_TTL_SECONDS)
    restored = load_cookies_cache(cache_path, COOKIES_TTL_SECONDS)
    assert restored is not None
    assert restored.get("PHPSESSID") == "abc"


def test_cookies_cache_expires_and_invalidates(tmp_path: Path) -> None:
    cache_path = tmp_path / "cookies.json"
    cache_path.write_text(
        json.dumps({"created_at": time.time() - (COOKIES_TTL_SECONDS + 5), "cookies": []}),
        encoding="utf-8",
    )

    assert load_cookies_cache(cache_path, COOKIES_TTL_SECONDS) is None
    invalidate_cookies_cache(cache_path)
    assert not cache_path.exists()


def test_cookies_cache_handles_broken_json(tmp_path: Path) -> None:
    cache_path = tmp_path / "cookies.json"
    cache_path.write_text("{broken", encoding="utf-8")

    assert cookies_cache_is_fresh(cache_path, COOKIES_TTL_SECONDS) is False
    assert load_cookies_cache(cache_path, COOKIES_TTL_SECONDS) is None


def test_cookies_cache_handles_invalid_created_at(tmp_path: Path) -> None:
    cache_path = tmp_path / "cookies.json"
    cache_path.write_text(
        json.dumps({"created_at": "bad-value", "cookies": []}),
        encoding="utf-8",
    )

    assert cookies_cache_is_fresh(cache_path, COOKIES_TTL_SECONDS) is False
    assert load_cookies_cache(cache_path, COOKIES_TTL_SECONDS) is None


def test_fetch_pages_batch_async_keeps_order_and_retries() -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    class FakeClient:
        def __init__(self) -> None:
            self.calls: dict[int, int] = {}

        async def get(self, url: str):
            page = 1
            if "p=" in url:
                page = int(url.split("p=")[1])
            self.calls[page] = self.calls.get(page, 0) + 1
            if page == 2 and self.calls[page] == 1:
                raise httpx.ReadTimeout("timeout")
            return FakeResponse(f"<html>page-{page}</html>")

    import httpx

    client = FakeClient()
    pages = asyncio.run(
        fetch_pages_batch_async(
            client=client,
            normalized_url="https://www.dns-shop.ru/search/?q=смартфон&category=cat",
            pages=[3, 2],
            concurrency=DEFAULT_CONCURRENCY,
        )
    )

    assert [page for page, _ in pages] == [2, 3]
    assert client.calls[2] == 2
    assert pages[0][1].text == "<html>page-2</html>"


def test_collect_products_from_url_async_persists_cookies_after_pages_and_prices(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.cookies = to_httpx_cookies([{"name": "foo", "value": "bar", "domain": "www.dns-shop.ru", "path": "/"}])

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    calls = {"persist": 0}

    def make_card(prefix: str, index: int):
        return type(
            "Card",
            (),
            {
                "name": f"{prefix}-{index}",
                "url": f"https://example/{prefix}/{index}",
                "code": f"{prefix}-{index}",
                "buy_container_id": f"buy-{prefix}-{index}",
            },
        )()

    page_cards = {
        "page-1": [make_card("p1", index) for index in range(18)],
        "page-2": [make_card("p2", index) for index in range(5)],
    }

    async def fake_prices(*_args, **_kwargs):
        return {}

    async def fake_batch(_client, _normalized_url, pages, _concurrency):
        return [(page, FakeResponse(f"<html>page-{page}</html>")) for page in pages]

    monkeypatch.setattr("app.dns_search_parser.make_async_client", lambda cookies=None: FakeAsyncClient())
    monkeypatch.setattr(
        "app.dns_search_parser.parse_cards",
        lambda html: page_cards.get(html.replace("<html>", "").replace("</html>", ""), []),
    )
    monkeypatch.setattr("app.dns_search_parser.fetch_prices_async", fake_prices)
    monkeypatch.setattr("app.dns_search_parser.fetch_pages_batch_async", fake_batch)
    monkeypatch.setattr("app.dns_search_parser.has_catalog_pagination", lambda _html: True)
    monkeypatch.setattr("app.dns_search_parser.persist_client_cookies", lambda client: calls.__setitem__("persist", calls["persist"] + 1))

    first_response = FakeResponse("<html>page-1</html>")
    products = asyncio.run(
        collect_products_from_url_async("https://www.dns-shop.ru/search/?q=test", None, first_response, None)
    )

    assert len(products) == 23
    assert calls["persist"] >= 2


def test_collect_products_from_url_async_without_limit_collects_until_short_page(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):
            class PostResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return {"result": True, "data": {"states": []}}

            return PostResponse()

    def make_card(prefix: str, index: int):
        return type(
            "Card",
            (),
            {
                "name": f"{prefix}-{index}",
                "url": f"https://example/{prefix}/{index}",
                "code": f"{prefix}-{index}",
                "buy_container_id": f"buy-{prefix}-{index}",
            },
        )()

    page_cards = {
        "page-1": [make_card("p1", index) for index in range(18)],
        "page-2": [make_card("p2", index) for index in range(18)],
        "page-3": [make_card("p3", index) for index in range(5)],
    }

    monkeypatch.setattr("app.dns_search_parser.make_async_client", lambda cookies=None: FakeAsyncClient())
    monkeypatch.setattr(
        "app.dns_search_parser.parse_cards",
        lambda html: page_cards.get(html.replace("<html>", "").replace("</html>", ""), []),
    )
    monkeypatch.setattr("app.dns_search_parser.fetch_prices_async", lambda *args, **kwargs: asyncio.sleep(0, result={}))
    monkeypatch.setattr("app.dns_search_parser.has_catalog_pagination", lambda _html: True)

    async def fake_batch(_client, _normalized_url, pages, _concurrency):
        return [(page, FakeResponse(f"<html>page-{page}</html>")) for page in pages]

    monkeypatch.setattr("app.dns_search_parser.fetch_pages_batch_async", fake_batch)

    first_response = FakeResponse("<html>page-1</html>")
    products = asyncio.run(
        collect_products_from_url_async("https://www.dns-shop.ru/search/?q=test", None, first_response, None)
    )

    assert len(products) == 41


def test_collect_products_from_url_async_with_limit_still_respects_limit(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):
            class PostResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return {"result": True, "data": {"states": []}}

            return PostResponse()

    def make_card(index: int):
        return type(
            "Card",
            (),
            {
                "name": f"P{index}",
                "url": f"https://example/{index}",
                "code": str(index),
                "buy_container_id": f"buy-{index}",
            },
        )()

    page_cards = {
        "page-1": [make_card(index) for index in range(18)],
        "page-2": [make_card(index) for index in range(18, 36)],
    }

    monkeypatch.setattr("app.dns_search_parser.make_async_client", lambda cookies=None: FakeAsyncClient())
    monkeypatch.setattr(
        "app.dns_search_parser.parse_cards",
        lambda html: page_cards.get(html.replace("<html>", "").replace("</html>", ""), []),
    )
    monkeypatch.setattr("app.dns_search_parser.fetch_prices_async", lambda *args, **kwargs: asyncio.sleep(0, result={}))
    monkeypatch.setattr("app.dns_search_parser.has_catalog_pagination", lambda _html: True)

    async def fake_batch(_client, _normalized_url, pages, _concurrency):
        return [(page, FakeResponse(f"<html>page-{page}</html>")) for page in pages]

    monkeypatch.setattr("app.dns_search_parser.fetch_pages_batch_async", fake_batch)

    first_response = FakeResponse("<html>page-1</html>")
    products = asyncio.run(
        collect_products_from_url_async("https://www.dns-shop.ru/search/?q=test", 20, first_response, None)
    )

    assert len(products) == 20


def test_collect_products_from_url_async_small_first_page_skips_extra_pages(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    cards = [
        type(
            "Card",
            (),
            {
                "name": f"P{index}",
                "url": f"https://example/{index}",
                "code": str(index),
                "buy_container_id": f"buy-{index}",
            },
        )()
        for index in range(5)
    ]
    calls = {"batch": 0}

    monkeypatch.setattr("app.dns_search_parser.make_async_client", lambda cookies=None: FakeAsyncClient())
    monkeypatch.setattr("app.dns_search_parser.parse_cards", lambda _html: cards)
    monkeypatch.setattr("app.dns_search_parser.fetch_prices_async", lambda *args, **kwargs: asyncio.sleep(0, result={}))

    async def fake_batch(*_args, **_kwargs):
        calls["batch"] += 1
        return []

    monkeypatch.setattr("app.dns_search_parser.fetch_pages_batch_async", fake_batch)

    products = asyncio.run(
        collect_products_from_url_async("https://www.dns-shop.ru/search/?q=test", None, FakeResponse("<html></html>"), None)
    )

    assert len(products) == 5
    assert calls["batch"] == 0


def test_collect_products_from_url_async_ambiguous_full_page_probes_second_page_before_batch(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def make_card(prefix: str, index: int):
        return type(
            "Card",
            (),
            {
                "name": f"{prefix}-{index}",
                "url": f"https://example/{prefix}/{index}",
                "code": f"{prefix}-{index}",
                "buy_container_id": f"buy-{prefix}-{index}",
            },
        )()

    page_cards = {
        "page-1": [make_card("p1", index) for index in range(18)],
        "page-2": [],
    }
    calls = {"probe": 0, "batch": 0}

    monkeypatch.setattr("app.dns_search_parser.make_async_client", lambda cookies=None: FakeAsyncClient())
    monkeypatch.setattr(
        "app.dns_search_parser.parse_cards",
        lambda html: page_cards.get(html.replace("<html>", "").replace("</html>", ""), []),
    )
    monkeypatch.setattr("app.dns_search_parser.fetch_prices_async", lambda *args, **kwargs: asyncio.sleep(0, result={}))

    async def fake_retry(_client, url, attempts=3):
        calls["probe"] += 1
        assert "p=2" in url
        return FakeResponse("<html>page-2</html>")

    async def fake_batch(*_args, **_kwargs):
        calls["batch"] += 1
        return []

    monkeypatch.setattr("app.dns_search_parser.async_get_with_retry", fake_retry)
    monkeypatch.setattr("app.dns_search_parser.fetch_pages_batch_async", fake_batch)

    products = asyncio.run(
        collect_products_from_url_async("https://www.dns-shop.ru/search/?q=test", None, FakeResponse("<html>page-1</html>"), None)
    )

    assert len(products) == 18
    assert calls["probe"] == 1
    assert calls["batch"] == 0
