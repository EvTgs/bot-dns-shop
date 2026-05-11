# DNS search parser

Парсер поисковой выдачи DNS Shop, инструмент карты фильтров раздела и Telegram-бот с DeepSeek.

## Структура

- `app/` — Python-код проекта
- `tests/` — тесты
- `runtime/` — изменяемые файлы запуска
  - `runtime/cookies.json`
  - `runtime/bot_memory.json`
  - `runtime/logs/telegram_bot.log`
  - `runtime/telegram_reports/`
  - `runtime/telegram_reports_test/`
- `artifacts/` — JSON-результаты и примеры входных файлов
- `scripts/` — реальные `.cmd` entrypoint-ы
- `run_*.cmd` в корне — совместимые обёртки для запуска
- `win-git/` — журнал изменений

## Запуск

Меню Windows:

```powershell
run_dns_menu.cmd
```

Telegram-бот:

```powershell
run_telegram_bot.cmd
```

Карта фильтров раздела:

```powershell
run_dns_section_filters.cmd
```

Прямой CLI:

```powershell
py -m app.dns_search_parser --query "клавиатура" --category 17a8950d16404e77 --limit 200 --output artifacts\dns_products.json
```

По готовому URL DNS:

```powershell
py -m app.dns_search_parser --url "https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77&stock=now-out_of_stock&price=10000-20000" --limit 50 --output artifacts\dns_products.json
```

Диагностика параметров URL:

```powershell
py -m app.dns_search_parser --inspect-url "https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77&stock=now-out_of_stock&price=10000-20000&brand=abc123"
```

Характеристики по списку ссылок:

```powershell
py -m app.dns_search_parser --characteristics-urls "https://www.dns-shop.ru/product/7ffd0cf6a89cd21a/667-smartfon-xiaomi-redmi-note-14-256-gb-cernyj/"
```

## Telegram bot

Локальные ключи читаются из `.env`:

```text
TELEGRAM_BOT_TOKEN=...
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_ENDPOINT_PATH=/chat/completions
```

Runtime-переключатель без правки `.env`:

- `run_dns_menu.cmd`
- пункт `5. Настройки DeepSeek`
- сохраняет `runtime/deepseek_settings.json`

Команды:

- `/start`
- `/reset`
- любой текстовый запрос

Поддерживается цепочка:

- текстовый запрос или DNS URL
- category resolve
- полная карта фильтров категории
- AI selection фильтров
- готовый DNS URL
- shortlist
- характеристики shortlist
- compare-link из `code`
- финальный AI-ответ

## Отдельный compare-контур

Сравнение товаров живет в отдельном канвасе и не смешивается с shortlist:

- [`docs-this-version/compare_link.canvas`](compare_link.canvas) - мост от shortlist к compare-link и финальному ответу;
- [`DNS_compare_link_research/docs-this-version/compare_link.canvas`](../../DNS_compare_link_research/docs-this-version/compare_link.canvas) - отдельный исследовательский канвас по сборке и проверке compare-ссылки.

## Где смотреть файлы

Runtime:

- `runtime/logs/telegram_bot.log`
- `runtime/cookies.json`
- `runtime/bot_memory.json`
- `runtime/telegram_reports/telegram_table.png`
- `runtime/telegram_reports/telegram_price_chart.png`

Artifacts:

- `artifacts/dns_products.json`
- `artifacts/dns_filters_report.json`
- `artifacts/dns_characteristics.json`
- `artifacts/dns_section_filters.json`
- `artifacts/dns_built_section_url.json`

## Поддерживаемые флаги DNS

- `category=17a8a01d16404e77`
- `stock=now-out_of_stock`
- `stock=now-today-tomorrow-later-out_of_stock`
- `price=10000-20000`
- `f[...]` фильтры категории, включая multi-select через `-`

Неизвестные query-параметры сохраняются и передаются дальше без интерпретации.

## Примеры ссылок

Смартфоны без category:

```text
https://www.dns-shop.ru/search/?q=смартфон
```

Смартфоны с category:

```text
https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77
```

Смартфоны с наличием:

```text
https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77&stock=now-out_of_stock
```

Смартфоны с наличием и ценой:

```text
https://www.dns-shop.ru/search/?q=смартфон&category=17a8a01d16404e77&stock=now-out_of_stock&price=10000-20000
```
