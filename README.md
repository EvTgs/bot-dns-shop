# DNSpars v1 Telegram Bot

Telegram-бот и DNS parser для подбора техники в DNS Shop.

Проект делает полный `/tech` цикл:

```text
запрос пользователя
-> нормализация через DeepSeek
-> определение категории DNS
-> загрузка карты фильтров раздела
-> безопасный подбор фильтров
-> сбор DNS URL
-> парсинг выдачи
-> shortlist
-> сбор характеристик
-> compare-link или прямая ссылка на товар
-> финальный ответ пользователю
```

## Текущее состояние

- Основной код: `backend/src/app`
- Runtime-файлы: `database/runtime`
- Тесты: `backend/test/python_test`
- Документация текущей версии: `docs-this-version`
- Основной запуск Windows: `единый_запуск.bat`

Последний проверенный smoke:

```powershell
py -m pytest backend/test/python_test -q
```

Ожидаемый результат:

```text
271 passed
```

## Быстрый Запуск

### 1. Установить зависимости

```powershell
Set-Location C:\1all_project\Dns_project\DNSpars_v1_tgbot
py -m pip install -r requirements.txt
```

### 2. Настроить `.env`

Скопируйте значения из `.env.example` в `.env` и заполните ключи:

```text
TELEGRAM_BOT_TOKEN=...
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_FALLBACK_MODEL=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_ENDPOINT_PATH=/chat/completions
```

`.env` не коммитится.

### 3. Запустить меню

```powershell
.\единый_запуск.bat
```

Меню:

```text
1. Получить 200 клавиатур
2. Тест карты фильтров раздела
3. Свой поиск
4. Свой URL DNS
5. Настройки DeepSeek
6. Запуск Telegram-бота
7. Экспорт смартфоны/планшеты/ноутбуки
8. Компактный локальный дамп
0. Выход
```

Для запуска Telegram-бота выберите пункт `6`.

## Прямые Команды

Если нужно запустить без меню:

```powershell
$env:PYTHONPATH="C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\src"
py -m app.telegram_bot
```

Парсер по запросу:

```powershell
$env:PYTHONPATH="C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\src"
py -m app.dns_search_parser --query "клавиатура" --category 17a8950d16404e77 --limit 200 --output database\runtime\artifacts\dns_products.json
```

Парсер по готовому DNS URL:

```powershell
$env:PYTHONPATH="C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\src"
py -m app.dns_search_parser --url "https://www.dns-shop.ru/search/?q=клавиатура&category=17a8950d16404e77&price=0-3000" --limit 50 --output database\runtime\artifacts\dns_products.json
```

Ручной AI-runner без Telegram:

```powershell
$env:PYTHONPATH="C:\1all_project\Dns_project\DNSpars_v1_tgbot\backend\src"
py -m app.manual_ai_runner
```

## Telegram Команды

- `/start` - приветствие
- `/reset` - сброс памяти чата
- `/ai <текст>` - простой режим LLM
- `/tech <запрос>` - полный техноцикл DNS

Пример:

```text
/tech магнитная клавиатура до 3к лучше 75-80 процентов
```

Во время `/tech` бот редактирует одно Telegram-сообщение по стадиям:

```text
Определяю раздел DNS
Загружаю карту фильтров DNS
Сопоставляю требования с реальными фильтрами
Собираю DNS-ссылку
Начинаю парс DNS
Отбираю лучшие варианты
Добираю характеристики
Финализация
```

DeepSeek stream используется только на финальной генерации ответа.

## Структура Backend

```text
backend/src/app/
  ai_orchestrator.py          общий Tech pipeline, пока ещё главный крупный файл
  dns_search_parser.py        DNS parser facade
  deepseek_client.py          DeepSeek API client
  telegram_bot.py             Telegram runtime
  telegram_stages.py          stage-сообщения Telegram
  telegram_text.py            MarkdownV2 и ограничения текста
  bot_memory.py               память чата
  windows_menu.py             Windows CLI menu
  normalization/
    price.py                  price parsing, budget buckets, normalize_price_pair
  parser/
    models.py                 Product, ParsedCard, DnsFilterSelectionError
  telegram/
    tech_answer.py            финальная сборка /tech ответа, compare/direct-link
  prompts/
    *.txt                     системные промты
```

## Важные Улучшения

Сейчас уже исправлено:

- `price=0-N` сохраняется как hard constraint при сборке DNS URL
- `2к` в запросах про монитор понимается как `1440p`, а не как `2000 ₽`
- если найден один товар, бот добавляет прямую ссылку на товар, а не пустой compare-link
- `stream=True` используется только для финального ответа
- structured JSON-этапы DeepSeek идут через non-stream `chat`
- browser fallback закрывает Chrome/Edge через `finally`
- `allow_browser=False` больше не запускает compare browser loader
- DeepSeek malformed JSON и empty content обрабатываются как API error
- stream не ретраится после уже выданных чанков, чтобы не дублировать текст

## Тесты

Полный прогон:

```powershell
py -m pytest backend/test/python_test -q
```

Ключевые тесты:

```powershell
py -m pytest backend/test/python_test/test_bot_scenarios.py -q
py -m pytest backend/test/python_test/test_telegram_bot.py -q
py -m pytest backend/test/python_test/test_ai_orchestrator.py -q
py -m pytest backend/test/python_test/test_dns_search_parser.py -q
py -m pytest backend/test/python_test/test_deepseek_client.py -q
```

`test_bot_scenarios.py` содержит быстрые сценарии:

- магнитная клавиатура до 3к, 75-80%, магнитные свитчи
- игровой монитор 27 дюймов, 2к/1440p, до 35 тысяч

## Runtime И Логи

Основные файлы:

```text
database/runtime/logs/telegram_bot.log
database/runtime/bot_memory.json
database/runtime/cookies.json
database/runtime/deepseek_settings.json
database/runtime/telegram_bot.lock
database/runtime/artifacts/
```

Runtime-папка игнорируется Git.

## Документация И Canvas

- `docs-this-version/README.md` - дополнительные заметки версии
- `docs-this-version/compare_link.canvas` - схема compare-link
- `backend/test/snapshots/ai_stage_monitors_27_1440p_35k/` - трасса monitor pipeline
- `backend/test/snapshots/ai_stage_monitors_raw_27_1440p_35k/` - raw-трасса monitor pipeline

## Известные Слабые Места

Главные технические долги:

- `ai_orchestrator.py` всё ещё слишком большой
- `dns_search_parser.py` пока совмещает HTTP, cookies, browser, catalog, details и CLI
- нет полноценного per-chat job manager для очереди, отмены и busy-state
- `_last_filter_trace` и `_last_shortlist_decision` нужно вынести в request context
- `relax/retry` при нулевой выдаче ещё надо привести ближе к Tech_canvas
- Telegram buttons `/ai` и `/tech` пока работают скорее как подсказки, а не как полноценные режимы

План дальнейшего разделения:

```text
pipeline/      порядок этапов и request context
filters/       DNS filter map, preselect, coverage, safe selection
ranking/       scoring, shortlist, comparison summary
parser/        HTTP, cookies, browser, catalog, prices, details, compare
telegram/      delivery, commands, keyboards, streaming
memory/        atomic writes, context, corruption recovery
```

## GitHub

Репозиторий:

```text
https://github.com/EvTgs/bot-dns-shop
```
