import asyncio
import logging
from pathlib import Path

from app.dns_search_parser import BLOCKED_AFTER_BOOTSTRAP
from app.telegram_bot import (
    START_TEXT,
    TelegramBotRuntime,
    acquire_bot_lock,
    build_live_message,
    escape_markdown_v2,
    format_user_error,
    is_message_not_modified_error,
    is_message_cant_be_edited_error,
    is_timed_out_error,
    pid_is_running,
    release_bot_lock,
    render_markdown_v2,
    sanitize_telegram_answer,
)
from app.telegram_stages import render_stage_message


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.replies: list[str] = []
        self.reply_markups = []
        self.photos: list[str] = []
        self.documents: list[str] = []
        self.sent_messages: list[FakeSentMessage] = []
        self.timeout_photo = False
        self.photo_markup = []
        self.deleted_messages: list[int] = []
        self.next_message_id = 100

    async def reply_text(self, text: str, **kwargs):
        self.replies.append(text)
        self.reply_markups.append(kwargs.get("reply_markup"))
        sent = FakeSentMessage(message_id=self.next_message_id)
        self.next_message_id += 1
        self.sent_messages.append(sent)
        return sent

    async def reply_photo(self, photo, **kwargs):
        if self.timeout_photo:
            raise RuntimeError("Timed out")
        self.photos.append(getattr(photo, "name", "photo"))
        self.photo_markup.append(kwargs.get("reply_markup"))
        sent = FakeSentMessage(message_id=self.next_message_id)
        self.next_message_id += 1
        return sent

    async def reply_document(self, document):
        self.documents.append(getattr(document, "name", "document"))


class FakeSentMessage:
    def __init__(self, message_id: int = 1) -> None:
        self.edits: list[str] = []
        self.fail_on_duplicate = False
        self.timeout_on_edit = False
        self.message_id = message_id
        self.deleted = False
        self.reply_markup = None
        self.reply_markup_edits = []

    async def edit_text(self, text: str, **kwargs) -> None:
        if self.fail_on_duplicate and self.edits and self.edits[-1] == text:
            raise RuntimeError(
                "Message is not modified: specified new message content and reply markup are exactly the same"
            )
        if self.timeout_on_edit:
            raise RuntimeError("Timed out")
        self.edits.append(text)
        self.reply_markup = kwargs.get("reply_markup")

    async def edit_reply_markup(self, reply_markup=None) -> None:
        self.reply_markup = reply_markup
        self.reply_markup_edits.append(reply_markup)

    async def delete(self) -> None:
        self.deleted = True


class FakeCallbackMessage(FakeMessage):
    def __init__(self, text: str = "", message_id: int = 999) -> None:
        super().__init__(text)
        self.message_id = message_id
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class FakeCallbackQuery:
    def __init__(self, data: str, message: FakeCallbackMessage) -> None:
        self.data = data
        self.message = message
        self.answers: list[str | None] = []

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)


class FakeCallbackUpdate:
    def __init__(self, data: str, chat_id: int = 1, message_id: int = 999) -> None:
        self.effective_chat = type("Chat", (), {"id": chat_id})()
        self.message = None
        self.callback_query = FakeCallbackQuery(data, FakeCallbackMessage(message_id=message_id))


class FakeErrorContext:
    def __init__(self, error) -> None:
        self.error = error


class FakeUpdate:
    def __init__(self, text: str, chat_id: int = 1) -> None:
        self.effective_chat = type("Chat", (), {"id": chat_id})()
        self.message = FakeMessage(text)


def test_start_replies_with_instruction() -> None:
    asyncio.run(run_start_replies_with_instruction())


async def run_start_replies_with_instruction() -> None:
    runtime = TelegramBotRuntime(orchestrator=None)
    update = FakeUpdate("/start")

    await runtime.start(update, None)

    assert update.message.replies == [render_markdown_v2(START_TEXT)]
    assert update.message.reply_markups[0] is not None


def test_reset_clears_memory(tmp_path) -> None:
    asyncio.run(run_reset_clears_memory(tmp_path))


async def run_reset_clears_memory(tmp_path) -> None:
    runtime = TelegramBotRuntime(orchestrator=None, memory_path=tmp_path / "memory.json")
    update = FakeUpdate("/reset")

    await runtime.reset(update, None)

    assert update.message.replies == [render_markdown_v2("Память сброшена.")]
    assert update.message.reply_markups[0] is not None


def test_handle_message_reply_keyboard_commands(tmp_path) -> None:
    asyncio.run(run_handle_message_reply_keyboard_commands(tmp_path))


async def run_handle_message_reply_keyboard_commands(tmp_path) -> None:
    runtime = TelegramBotRuntime(orchestrator=None, memory_path=tmp_path / "memory.json")

    login_update = FakeUpdate("Логин", chat_id=5)
    await runtime.handle_message(login_update, None)
    assert login_update.message.replies == [render_markdown_v2("Функция ещё не подключена.")]
    assert login_update.message.reply_markups[0] is not None

    reset_update = FakeUpdate("Сброс", chat_id=5)
    await runtime.handle_message(reset_update, None)
    assert reset_update.message.replies == [render_markdown_v2("Память сброшена.")]
    assert reset_update.message.reply_markups[0] is not None


def test_ai_command_requires_query(tmp_path) -> None:
    asyncio.run(run_ai_command_requires_query(tmp_path))


async def run_ai_command_requires_query(tmp_path) -> None:
    runtime = TelegramBotRuntime(orchestrator=None, memory_path=tmp_path / "memory.json")
    update = FakeUpdate("/ai", chat_id=5)

    await runtime.ai(update, None)

    assert update.message.replies == [render_markdown_v2("Использование: /ai <запрос>")]


def test_tech_command_returns_structured_dump_without_images(tmp_path) -> None:
    asyncio.run(run_tech_command_returns_structured_dump_without_images(tmp_path))


async def run_tech_command_returns_structured_dump_without_images(tmp_path) -> None:
    image_path = tmp_path / "telegram_table_01.png"
    image_path.write_bytes(b"fake-image")

    class FakeOrchestrator:
        async def handle_message(self, text, history, on_text_chunk, on_stage=None, memory_context=None):
            return type(
                "Result",
                (),
                {
                    "answer": "Лидер анализа\nТовар A",
                    "image_paths": [image_path],
                    "products_count": 2,
                    "resolved_url": "https://example/search",
                    "products": [
                        {"name": "Tecno CAMON 50", "code": "5660709"},
                        {"name": "Samsung Galaxy A56", "code": "5620468"},
                    ],
                    "context_payload": {
                        "normalized_request": {"product_type": "smartphone", "intent_signals": [{"key": "matrix_type"}]},
                        "stats": {"total_products": 2},
                        "filters_llm": {"filters_count": 10, "groups": [{"name": "Экран", "filters": [{"id": "f[1]"}]}]},
                        "comparison_summary": {"top_pick": {"name": "A", "code": "5660709"}, "fit_policy": {"full_match_allowed": False}},
                        "products": [
                            {"name": "Tecno CAMON 50", "code": "5660709"},
                            {"name": "Samsung Galaxy A56", "code": "5620468"},
                        ],
                    },
                },
            )()

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    update = FakeUpdate("/tech смартфон samsung", chat_id=9)

    await runtime.tech(update, None)

    assert update.message.photos == []
    tech_text = update.message.sent_messages[0].edits[-1]
    assert "Лидер анализа" in tech_text
    assert "Таблица сравнения DNS" in tech_text
    assert "https://www\\.dns\\-shop\\.ru/compare/?cityId\\=128&ids\\=5660709%2C5620468" in tech_text
    assert "normalized_request" not in tech_text
    assert "filters_llm" not in tech_text


def test_tech_command_edits_one_message_by_stages_and_streams_final_only(tmp_path) -> None:
    asyncio.run(run_tech_command_edits_one_message_by_stages_and_streams_final_only(tmp_path))


def test_build_tech_answer_uses_direct_product_link_when_compare_has_one_item() -> None:
    result = type(
        "Result",
        (),
        {
            "answer": "Лучший вариант\nVGN A75",
            "context_payload": {
                "products": [
                    {
                        "name": "Клавиатура проводная VGN A75 Gradient Pink",
                        "code": "5617581",
                        "url": "https://www.dns-shop.ru/product/1d0007bdedb2d0a4/klaviatura-provodnaa-vgn-a75-gradient-pink/",
                    }
                ]
            },
        },
    )()

    text = TelegramBotRuntime.build_tech_answer(result, "магнитная клавиатура до 3к")

    assert "Таблица сравнения DNS" not in text
    assert "Ссылка на товар DNS" in text
    assert "https://www.dns-shop.ru/product/1d0007bdedb2d0a4/klaviatura-provodnaa-vgn-a75-gradient-pink/" in text


async def run_tech_command_edits_one_message_by_stages_and_streams_final_only(tmp_path) -> None:
    class FakeOrchestrator:
        async def handle_message(self, text, history, on_text_chunk, on_stage=None, memory_context=None):
            if on_text_chunk is not None:
                on_text_chunk('{"selected_codes":["raw-json-before-final"]}')
            if on_stage:
                on_stage("parser_start")
                on_stage("analysis_start")
            if on_text_chunk is not None:
                on_text_chunk("Финальный поток. ")
                on_text_chunk('{"filters":["hidden-json-during-final"]}')
                on_text_chunk("Человеческий текст.")
            if on_stage:
                on_stage("render_done")
            return type(
                "Result",
                (),
                {
                    "answer": "Финальный поток. Человеческий текст.",
                    "image_paths": [],
                    "products_count": 1,
                    "context_payload": {
                        "products": [
                            {"name": "Товар A", "code": "111"},
                            {"name": "Товар B", "code": "222"},
                        ],
                    },
                },
            )()

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    update = FakeUpdate("/tech ноутбук", chat_id=91)

    await runtime.tech(update, None)

    sent = update.message.sent_messages[0]
    assert update.message.replies[0] == render_markdown_v2(render_stage_message("start"))
    assert len(update.message.sent_messages) == 1
    assert any("Начинаю парс DNS" in edit for edit in sent.edits)
    assert all("raw\\-json\\-before\\-final" not in edit for edit in sent.edits)
    assert all("hidden\\-json\\-during\\-final" not in edit for edit in sent.edits)
    assert "Финальный поток" in sent.edits[-1]
    assert "Таблица сравнения DNS" in sent.edits[-1]


def test_message_streams_answer_batches_without_media_delivery(tmp_path) -> None:
    asyncio.run(run_message_streams_answer_batches_without_media_delivery(tmp_path))


async def run_message_streams_answer_batches_without_media_delivery(tmp_path) -> None:
    image_path = tmp_path / "telegram_table_01.png"
    image_path.write_bytes(b"fake-image")
    image_path_2 = tmp_path / "telegram_table_02.png"
    image_path_2.write_bytes(b"fake-image-2")

    class FakeOrchestrator:
        async def handle_message(self, text, history, on_text_chunk, on_stage=None, memory_context=None):
            if on_stage:
                on_stage("parser_start")
                on_stage("shortlist_start")
                on_stage("details_start")
                on_stage("analysis_start")
            if on_text_chunk is not None:
                on_text_chunk("Первая часть. ")
                on_text_chunk("Вторая часть.")
            if on_stage:
                on_stage("render_done")
            return type(
                "Result",
                (),
                {
                    "answer": "Первая часть. Вторая часть.",
                    "image_paths": [image_path, image_path_2],
                    "products_count": 1,
                    "context_payload": {"products": [{"name": "A"}], "stats": {}, "resolved_url": "https://example"},
                },
            )()

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    update = FakeUpdate("найди смартфон")

    await runtime.handle_message(update, None)

    assert update.message.replies[0] == render_markdown_v2("Обработка данных...")
    assert update.message.documents == []
    assert update.message.photos == []
    saved_context = runtime.load_context(1)
    assert "table_actions" not in saved_context


def test_handle_message_does_not_stream_raw_json_chunks(tmp_path) -> None:
    asyncio.run(run_handle_message_does_not_stream_raw_json_chunks(tmp_path))


async def run_handle_message_does_not_stream_raw_json_chunks(tmp_path) -> None:
    class FakeOrchestrator:
        async def handle_message(self, text, history, on_text_chunk, on_stage=None, memory_context=None):
            if on_text_chunk is not None:
                on_text_chunk('{"selected_codes":["123"]}')
            return type(
                "Result",
                (),
                {
                    "answer": "Готовый человеческий ответ.",
                    "image_paths": [],
                    "products_count": 0,
                    "context_payload": {"products": [], "stats": {}, "resolved_url": "https://example"},
                },
            )()

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    update = FakeUpdate("найди смартфон", chat_id=11)

    await runtime.handle_message(update, None)

    sent = update.message.sent_messages[0]
    assert sent.edits
    assert all("selected\\_codes" not in text for text in sent.edits)
    assert sent.edits[-1] == render_markdown_v2(build_live_message("Готовый человеческий ответ."))


def test_handle_message_uses_fallback_after_edit_timeout(tmp_path) -> None:
    asyncio.run(run_handle_message_uses_fallback_after_edit_timeout(tmp_path))


async def run_handle_message_uses_fallback_after_edit_timeout(tmp_path) -> None:
    image_path = tmp_path / "telegram_table_01.png"
    image_path.write_bytes(b"fake-image")

    class FakeOrchestrator:
        async def handle_message(self, text, history, on_text_chunk, on_stage=None, memory_context=None):
            if on_stage:
                on_stage("analysis_start")
                on_stage("render_done")
            if on_text_chunk is not None:
                on_text_chunk("Готовый ответ")
            return type("Result", (), {"answer": "Готовый ответ", "image_paths": [image_path], "products_count": 1})()

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    update = FakeUpdate("найди смартфон")
    sent = FakeSentMessage()
    sent.timeout_on_edit = True

    async def reply_text(text: str, **kwargs):
        update.message.replies.append(text)
        return sent if len(update.message.replies) == 1 else FakeSentMessage()

    update.message.reply_text = reply_text
    await runtime.handle_message(update, None)

    assert len(update.message.replies) >= 2
    assert any("Готовый ответ" in reply for reply in update.message.replies)
    assert update.message.replies[-1] == render_markdown_v2("Готовый ответ")
    assert update.message.photos == []


def test_handle_message_direct_followup_does_not_send_images(tmp_path) -> None:
    asyncio.run(run_handle_message_direct_followup_does_not_send_images(tmp_path))


async def run_handle_message_direct_followup_does_not_send_images(tmp_path) -> None:
    class FakeOrchestrator:
        async def handle_message(self, text, history, on_text_chunk, on_stage=None, memory_context=None):
            if on_text_chunk is not None:
                on_text_chunk("Самый надежный вариант — SSD Samsung.")
            return type(
                "Result",
                (),
                {
                    "answer": "Самый надежный вариант — SSD Samsung.",
                    "image_paths": [],
                    "products_count": 3,
                    "context_payload": memory_context or {},
                },
            )()

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    update = FakeUpdate("а какой надежнее")

    await runtime.handle_message(update, None)

    assert update.message.photos == []
    assert update.message.documents == []


def test_prime_startup_prewarm_cookies_and_orchestrator(tmp_path, monkeypatch) -> None:
    calls = {"prewarm": 0, "orchestrator": 0}

    def fake_prewarm(reason="startup"):
        calls["prewarm"] += 1
        return object()

    class FakeOrchestrator:
        pass

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    monkeypatch.setattr("app.telegram_bot.prewarm_dns_cookies", fake_prewarm)

    runtime.prime_startup()

    assert calls["prewarm"] == 1


def test_handle_message_returns_friendly_dns_block_error(tmp_path) -> None:
    asyncio.run(run_handle_message_returns_friendly_dns_block_error(tmp_path))


async def run_handle_message_returns_friendly_dns_block_error(tmp_path) -> None:
    class FakeOrchestrator:
        async def handle_message(self, text, history, on_text_chunk, on_stage=None, memory_context=None):
            raise RuntimeError(BLOCKED_AFTER_BOOTSTRAP)

    runtime = TelegramBotRuntime(orchestrator=FakeOrchestrator(), memory_path=tmp_path / "memory.json")
    update = FakeUpdate("найди смартфон от 22000 до 24000")

    await runtime.handle_message(update, None)

    expected = render_markdown_v2(
        "Ошибка: DNS сейчас не отдаёт выдачу после обычной загрузки страницы. "
        "Если запрос был без category, откройте поиск в браузере, дождитесь URL с category "
        "и пришлите уже готовую ссылку DNS."
    )
    assert update.message.replies[0] == render_markdown_v2("Обработка данных...")
    assert update.message.sent_messages[0].edits[-1] == expected


def test_format_user_error_maps_dns_block_message() -> None:
    value = format_user_error(RuntimeError(BLOCKED_AFTER_BOOTSTRAP))

    assert "DNS сейчас не отдаёт выдачу" in value
    assert "category" in value


def test_safe_edit_text_ignores_message_not_modified() -> None:
    asyncio.run(run_safe_edit_text_ignores_message_not_modified())


async def run_safe_edit_text_ignores_message_not_modified() -> None:
    runtime = TelegramBotRuntime()
    sent = FakeSentMessage()
    state = {"last_text": ""}

    status = await runtime.safe_edit_text(sent, "Ответ", state)
    sent.fail_on_duplicate = True
    duplicate_status = await runtime.safe_edit_text(sent, "Ответ", state)

    assert status == "updated"
    assert duplicate_status == "skipped"
    assert sent.edits == ["Ответ"]


def test_build_live_message_keeps_statuses_separate_from_answer() -> None:
    value = build_live_message("Финальный текст")

    assert value == "Финальный текст"


def test_sanitize_telegram_answer_removes_markdown_markers() -> None:
    value = sanitize_telegram_answer("Лучший — **HONOR Pad X8a**.\n# Заголовок\n`код`")

    assert "**" not in value
    assert "`" not in value
    assert "HONOR Pad X8a" in value
    assert "Заголовок" in value


def test_render_markdown_v2_formats_headings_and_bullets() -> None:
    value = render_markdown_v2("Лидер анализа\n• Товар 1\nЦена 10.000!")

    assert value.startswith("*Лидер анализа*")
    assert "• Товар 1" in value
    assert "10\\.000\\!" in value


def test_escape_markdown_v2_escapes_telegram_special_chars() -> None:
    assert escape_markdown_v2("Цена 10.000!") == "Цена 10\\.000\\!"


def test_error_detectors() -> None:
    assert is_message_not_modified_error(RuntimeError("Message is not modified")) is True
    assert is_message_not_modified_error(RuntimeError("other error")) is False
    assert is_message_cant_be_edited_error(RuntimeError("Message can't be edited")) is True
    assert is_message_cant_be_edited_error(RuntimeError("other error")) is False
    assert is_timed_out_error(RuntimeError("Timed out")) is True
    assert is_timed_out_error(RuntimeError("broken pipe")) is False


def test_safe_edit_text_disables_retries_after_non_editable_error() -> None:
    asyncio.run(run_safe_edit_text_disables_retries_after_non_editable_error())


async def run_safe_edit_text_disables_retries_after_non_editable_error() -> None:
    runtime = TelegramBotRuntime()
    state = {"last_text": ""}

    class NotEditableMessage(FakeSentMessage):
        async def edit_text(self, text: str, **kwargs) -> None:
            raise RuntimeError("Message can't be edited")

    sent = NotEditableMessage()

    first = await runtime.safe_edit_text(sent, "Ответ", state)
    second = await runtime.safe_edit_text(sent, "Ответ 2", state)

    assert first == "failed"
    assert second == "failed"
    assert state["edit_disabled"] is True


def test_pid_is_running_accepts_current_process() -> None:
    import os

    assert pid_is_running(os.getpid()) is True


def test_acquire_bot_lock_blocks_second_instance(tmp_path, monkeypatch) -> None:
    import app.telegram_lock as telegram_lock

    lock_path = tmp_path / "telegram_bot.lock"
    monkeypatch.setattr("app.telegram_bot.LOCK_FILE_PATH", lock_path)
    monkeypatch.setattr("app.telegram_bot.ensure_runtime_directories", lambda: None)
    monkeypatch.setattr("app.telegram_lock.ensure_runtime_directories", lambda: None)
    monkeypatch.setattr("app.telegram_lock._LOCK_FILE_HANDLE", None)

    acquire_bot_lock()
    original_handle = telegram_lock._LOCK_FILE_HANDLE
    try:
        monkeypatch.setattr("app.telegram_lock._LOCK_FILE_HANDLE", None)
        try:
            acquire_bot_lock()
        except RuntimeError as exc:
            assert "already running" in str(exc)
        else:
            raise AssertionError("Second acquire_bot_lock() must fail")
    finally:
        telegram_lock._LOCK_FILE_HANDLE = original_handle
        release_bot_lock()
    assert not lock_path.exists()


def test_acquire_bot_lock_ignores_stale_non_python_pid(tmp_path, monkeypatch) -> None:
    import app.telegram_lock as telegram_lock

    lock_path = tmp_path / "telegram_bot.lock"
    lock_path.write_text("5580", encoding="utf-8")
    monkeypatch.setattr("app.telegram_bot.LOCK_FILE_PATH", lock_path)
    monkeypatch.setattr("app.telegram_bot.ensure_runtime_directories", lambda: None)
    monkeypatch.setattr("app.telegram_lock.ensure_runtime_directories", lambda: None)
    monkeypatch.setattr("app.telegram_lock._LOCK_FILE_HANDLE", None)
    monkeypatch.setattr("app.telegram_lock.pid_is_running", lambda pid: pid == 5580)
    monkeypatch.setattr("app.telegram_lock.get_process_image_path", lambda pid: "C:\\Users\\Zver\\AppData\\Local\\Chromium\\Application\\chrome.exe")

    acquire_bot_lock()
    try:
        assert lock_path.exists()
        assert lock_path.read_text(encoding="utf-8").strip() != "5580"
    finally:
        telegram_lock._LOCK_FILE_HANDLE = telegram_lock._LOCK_FILE_HANDLE
        release_bot_lock()
    assert not lock_path.exists()


def test_handle_error_downgrades_read_error_to_warning(tmp_path, monkeypatch) -> None:
    asyncio.run(run_handle_error_downgrades_read_error_to_warning(tmp_path, monkeypatch))


async def run_handle_error_downgrades_read_error_to_warning(tmp_path, monkeypatch) -> None:
    runtime = TelegramBotRuntime(memory_path=tmp_path / "memory.json")
    update = FakeUpdate("test", chat_id=77)
    warnings: list[str] = []
    errors: list[str] = []

    monkeypatch.setattr("app.telegram_bot.logger.warning", lambda message, *args: warnings.append(message % args))
    monkeypatch.setattr("app.telegram_bot.logger.error", lambda message, *args: errors.append(message % args))

    await runtime.handle_error(update, FakeErrorContext(RuntimeError("httpx.ReadError: boom")))

    assert warnings == ["telegram_network_error chat_id=77 error=httpx.ReadError: boom"]
    assert errors == []


def test_handle_error_logs_non_network_as_error(tmp_path, monkeypatch) -> None:
    asyncio.run(run_handle_error_logs_non_network_as_error(tmp_path, monkeypatch))


async def run_handle_error_logs_non_network_as_error(tmp_path, monkeypatch) -> None:
    runtime = TelegramBotRuntime(memory_path=tmp_path / "memory.json")
    update = FakeUpdate("test", chat_id=88)
    warnings: list[str] = []
    errors: list[str] = []

    monkeypatch.setattr("app.telegram_bot.logger.warning", lambda message, *args: warnings.append(message % args))
    monkeypatch.setattr("app.telegram_bot.logger.error", lambda message, *args: errors.append(message % args))

    await runtime.handle_error(update, FakeErrorContext(RuntimeError("boom")))

    assert warnings == []
    assert errors == ["telegram_unhandled_error chat_id=88 error=boom"]


def test_handle_error_rate_limits_repeated_network_errors(tmp_path, monkeypatch) -> None:
    asyncio.run(run_handle_error_rate_limits_repeated_network_errors(tmp_path, monkeypatch))


async def run_handle_error_rate_limits_repeated_network_errors(tmp_path, monkeypatch) -> None:
    runtime = TelegramBotRuntime(memory_path=tmp_path / "memory.json")
    update = FakeUpdate("test", chat_id=99)
    warnings: list[str] = []

    monkeypatch.setattr("app.telegram_bot.logger.warning", lambda message, *args: warnings.append(message % args))

    await runtime.handle_error(update, FakeErrorContext(RuntimeError("httpx.ReadError: boom")))
    await runtime.handle_error(update, FakeErrorContext(RuntimeError("httpx.ReadError: boom")))

    assert warnings == ["telegram_network_error chat_id=99 error=httpx.ReadError: boom"]
