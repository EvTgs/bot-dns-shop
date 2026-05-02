from app.deepseek_settings import DeepSeekSettings
from app.windows_menu import ask_deepseek_settings, ask_section_filters_run, build_parser_command, parse_menu_choice


def test_parse_menu_choice_accepts_known_options() -> None:
    assert parse_menu_choice("1") == "fetch_default_200"
    assert parse_menu_choice(" 2 ") == "inspect_section_filters"
    assert parse_menu_choice("3") == "fetch_custom"
    assert parse_menu_choice("4") == "fetch_url"
    assert parse_menu_choice("5") == "configure_deepseek"
    assert parse_menu_choice("6") == "run_telegram_bot"
    assert parse_menu_choice("7") == "export_category_snapshots"
    assert parse_menu_choice("8") == "compact_snapshot_file"
    assert parse_menu_choice("0") == "exit"


def test_parse_menu_choice_rejects_unknown_option() -> None:
    assert parse_menu_choice("9") is None
    assert parse_menu_choice("abc") is None


def test_build_parser_command_uses_current_python_and_parser_script() -> None:
    command = build_parser_command(
        query="клавиатура",
        category="17a8950d16404e77",
        limit=200,
        stock="now",
        price="10000-20000",
    )

    assert command[:3] == [command[0], "-m", "app.dns_search_parser"]
    assert command[-12:-2] == [
        "--query",
        "клавиатура",
        "--category",
        "17a8950d16404e77",
        "--stock",
        "now",
        "--price",
        "10000-20000",
        "--limit",
        "200",
    ]
    assert command[-2] == "--output"
    assert command[-1].endswith("artifacts\\dns_products.json")


def test_build_parser_command_accepts_dns_url() -> None:
    command = build_parser_command(
        query="",
        category="",
        limit=10,
        url="https://www.dns-shop.ru/search/?q=смартфон&stock=now",
    )

    assert "--url" in command
    assert "https://www.dns-shop.ru/search/?q=смартфон&stock=now" in command


def test_build_parser_command_accepts_section_filters_inspection() -> None:
    command = build_parser_command(
        query="",
        category="",
        limit=10,
        inspect_section_filters="https://www.dns-shop.ru/search/?q=планшет&category=17a8a05316404e77",
    )

    assert command[:3] == [command[0], "-m", "app.dns_search_parser"]
    assert command[-4:-1] == [
        "--inspect-section-filters",
        "https://www.dns-shop.ru/search/?q=планшет&category=17a8a05316404e77",
        "--inspect-section-output",
    ]
    assert command[-1].endswith("artifacts\\dns_section_filters.json")


def test_ask_section_filters_run_reads_url(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "https://www.dns-shop.ru/search/?q=планшет&category=cat")

    assert ask_section_filters_run() == "https://www.dns-shop.ru/search/?q=планшет&category=cat"


def test_ask_deepseek_settings_updates_values(monkeypatch) -> None:
    answers = iter(["deepseek-chat", "https://api.deepseek.com", "/chat/completions"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    settings = ask_deepseek_settings(
        DeepSeekSettings(
            model="deepseek-v4-flash",
            base_url="https://old.example",
            endpoint_path="/old",
        )
    )

    assert settings == DeepSeekSettings(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        endpoint_path="/chat/completions",
    )
