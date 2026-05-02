from __future__ import annotations

import subprocess
import sys

from .deepseek_settings import DeepSeekSettings, describe_deepseek_settings, load_deepseek_settings, save_deepseek_settings
from .project_paths import PROJECT_ROOT, artifact_path, ensure_runtime_directories


DEFAULT_CATEGORY = "17a8950d16404e77"
DEFAULT_LIMIT = 200
DEFAULT_QUERY = "клавиатура"
MENU_ACTIONS = {
    "1": "fetch_default_200",
    "2": "inspect_section_filters",
    "3": "fetch_custom",
    "4": "fetch_url",
    "5": "configure_deepseek",
    "6": "run_telegram_bot",
    "7": "export_category_snapshots",
    "8": "compact_snapshot_file",
    "0": "exit",
}


def parse_menu_choice(raw_choice: str) -> str | None:
    return MENU_ACTIONS.get(raw_choice.strip())


def build_parser_command(
    query: str,
    category: str,
    limit: int,
    stock: str = "",
    price: str = "",
    url: str = "",
    inspect_section_filters: str = "",
) -> list[str]:
    ensure_runtime_directories()
    command = [
        sys.executable,
        "-m",
        "app.dns_search_parser",
    ]
    if inspect_section_filters:
        command.extend(
            [
                "--inspect-section-filters",
                inspect_section_filters,
                "--inspect-section-output",
                str(artifact_path("dns_section_filters.json")),
            ]
        )
    elif url:
        command.extend(["--url", url])
    else:
        command.extend(["--query", query])
        if category:
            command.extend(["--category", category])
        if stock:
            command.extend(["--stock", stock])
        if price:
            command.extend(["--price", price])
    if inspect_section_filters:
        return command
    command.extend(["--limit", str(limit), "--output", str(artifact_path("dns_products.json"))])
    return command


def run_parser(
    query: str,
    category: str,
    limit: int,
    stock: str = "",
    price: str = "",
    url: str = "",
    inspect_section_filters: str = "",
) -> int:
    command = build_parser_command(query, category, limit, stock, price, url, inspect_section_filters)
    if inspect_section_filters:
        print("Запуск карты фильтров раздела.", flush=True)
        print(f"Результат: {artifact_path('dns_section_filters.json')}", flush=True)
    else:
        print("Запуск парсера. Прогресс будет выводиться по страницам.", flush=True)
        print(f"Результат: {artifact_path('dns_products.json')}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def run_telegram_bot() -> int:
    ensure_runtime_directories()
    command = [sys.executable, "-m", "app.telegram_bot"]
    print("Запуск Telegram-бота.", flush=True)
    print(f"Логи: {PROJECT_ROOT / 'database' / 'runtime' / 'logs' / 'telegram_bot.log'}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def export_category_snapshots() -> int:
    ensure_runtime_directories()
    script_path = PROJECT_ROOT / "scripts" / "export_category_snapshots.py"
    command = [sys.executable, str(script_path)]
    print("Экспорт категорий смартфоны/планшеты/ноутбуки.", flush=True)
    print(f"Результат: {PROJECT_ROOT / 'backend' / 'test' / 'snapshots' / 'ai_total'}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def ask_compact_snapshot_run() -> tuple[str, str, str, str, bool, bool]:
    input_path = input("Входной файл (.md/.json): ").strip()
    output_path = input("Выходной файл: ").strip()
    specs_mode = input("specs [join/values/named_join/keep] (join): ").strip() or "join"
    short_keys = (input("short-keys [y/N]: ").strip().lower() == "y")
    raw_json = (input("raw-json [y/N]: ").strip().lower() == "y")
    pretty = (input("pretty [y/N]: ").strip().lower() == "y")
    return input_path, output_path, specs_mode, pretty, short_keys, raw_json


def compact_snapshot_file() -> int:
    ensure_runtime_directories()
    script_path = PROJECT_ROOT / "scripts" / "compact_dns_snapshot.py"
    input_path, output_path, specs_mode, pretty, short_keys, raw_json = ask_compact_snapshot_run()
    command = [
        sys.executable,
        str(script_path),
        input_path,
        "--output",
        output_path,
        "--specs",
        specs_mode,
    ]
    if pretty:
        command.append("--pretty")
    if short_keys:
        command.append("--short-keys")
    if raw_json:
        command.append("--raw-json")
    print("Компактный локальный дамп.", flush=True)
    print(f"Результат: {output_path}", flush=True)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def ask_custom_run() -> tuple[str, str, str, str, int]:
    query = input(f"Поиск [{DEFAULT_QUERY}]: ").strip() or DEFAULT_QUERY
    category = input("Категория (можно пусто): ").strip()
    print("stock: now=сейчас, today=сегодня, tomorrow=завтра, later=позже, out_of_stock=нет в наличии")
    print("пример stock: now-out_of_stock")
    stock = input("stock (можно пусто): ").strip()
    print("пример price: 10000-20000")
    price = input("price (можно пусто): ").strip()
    raw_limit = input(f"Сколько товаров [{DEFAULT_LIMIT}]: ").strip()
    limit = parse_positive_int(raw_limit, DEFAULT_LIMIT)
    return query, category, stock, price, limit


def ask_url_run() -> tuple[str, int]:
    url = input("URL DNS: ").strip()
    raw_limit = input(f"Сколько товаров [{DEFAULT_LIMIT}]: ").strip()
    return url, parse_positive_int(raw_limit, DEFAULT_LIMIT)


def ask_section_filters_run() -> str:
    return input("URL раздела DNS (с q и category): ").strip()


def ask_deepseek_settings(current: DeepSeekSettings) -> DeepSeekSettings:
    print("Текущие настройки DeepSeek:")
    print(describe_deepseek_settings(current))
    model = input(f"Model [{current.model}]: ").strip() or current.model
    base_url = input(f"Base URL [{current.base_url}]: ").strip() or current.base_url
    endpoint_path = input(f"Endpoint path [{current.endpoint_path}]: ").strip() or current.endpoint_path
    return DeepSeekSettings(model=model, base_url=base_url, endpoint_path=endpoint_path)


def parse_positive_int(raw_value: str, default: int) -> int:
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def print_menu() -> None:
    print("")
    print("DNS parser")
    print("1. Получить 200 клавиатур")
    print("2. Тест карты фильтров раздела")
    print("3. Свой поиск")
    print("4. Свой URL DNS")
    print("5. Настройки DeepSeek")
    print("6. Запуск Telegram-бота")
    print("7. Экспорт смартфоны/планшеты/ноутбуки")
    print("8. Компактный локальный дамп")
    print("0. Выход", flush=True)


def main() -> int:
    while True:
        print_menu()
        action = parse_menu_choice(input("Выбор: "))
        if action == "exit":
            return 0
        if action == "fetch_default_200":
            run_parser(DEFAULT_QUERY, DEFAULT_CATEGORY, DEFAULT_LIMIT)
            input("Готово. Enter для продолжения...")
            continue
        if action == "inspect_section_filters":
            url = ask_section_filters_run()
            run_parser("", "", DEFAULT_LIMIT, inspect_section_filters=url)
            input("Готово. Enter для продолжения...")
            continue
        if action == "fetch_custom":
            query, category, stock, price, limit = ask_custom_run()
            run_parser(query, category, limit, stock, price)
            input("Готово. Enter для продолжения...")
            continue
        if action == "fetch_url":
            url, limit = ask_url_run()
            run_parser("", "", limit, url=url)
            input("Готово. Enter для продолжения...")
            continue
        if action == "configure_deepseek":
            settings = ask_deepseek_settings(load_deepseek_settings())
            saved_path = save_deepseek_settings(settings)
            print(f"Сохранено: {saved_path}", flush=True)
            input("Готово. Enter для продолжения...")
            continue
        if action == "run_telegram_bot":
            run_telegram_bot()
            input("Готово. Enter для продолжения...")
            continue
        if action == "export_category_snapshots":
            export_category_snapshots()
            input("Готово. Enter для продолжения...")
            continue
        if action == "compact_snapshot_file":
            compact_snapshot_file()
            input("Готово. Enter для продолжения...")
            continue
        print("Неизвестный пункт меню.")


if __name__ == "__main__":
    raise SystemExit(main())
