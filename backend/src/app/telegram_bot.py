from __future__ import annotations

import asyncio
import atexit
import logging
import os
import re
from pathlib import Path
from time import monotonic

from .app_logging import LOG_FILE, configure_logging
from .ai_orchestrator import NormalizedSearchRequest, ProductAnalysisOrchestrator, extract_normalize_constraints
from .bot_memory import append_turn, load_chat_context, load_chat_memory, reset_chat_memory, save_chat_context
from .dns_search_parser import BLOCKED_AFTER_BOOTSTRAP, BLOCKED_REQUIRES_BROWSER, Product, prewarm_dns_cookies
from .project_paths import MEMORY_FILE, TELEGRAM_BOT_LOCK_FILE, ensure_runtime_directories
from .telegram_lock import acquire_bot_lock as acquire_runtime_bot_lock
from .telegram_lock import pid_is_running
from .telegram_lock import release_bot_lock as release_runtime_bot_lock
from .telegram_stages import TelegramStageReporter, looks_like_raw_json_chunk, render_stage_message
from .telegram.tech_answer import build_tech_answer as build_telegram_tech_answer
from .telegram_text import (
    build_live_message,
    escape_markdown_v2,
    is_message_cant_be_edited_error,
    is_message_not_modified_error,
    is_network_error_text,
    parse_bullet_line,
    parse_heading_line,
    is_timed_out_error,
    render_markdown_v2,
    sanitize_error,
    sanitize_telegram_answer,
    trim_telegram_text,
)


START_TEXT = (
    "DNS AI bot готов. Пришли DNS URL или запрос вроде: "
    "найди смартфон 15000-30000. /reset сбрасывает память."
)
TELEGRAM_PARSE_MODE = "MarkdownV2"
STREAM_EDIT_SECONDS = 1.2
STREAM_EDIT_CHARS = 350
TELEGRAM_CONNECT_TIMEOUT = 20.0
TELEGRAM_READ_TIMEOUT = 30.0
TELEGRAM_WRITE_TIMEOUT = 30.0
TELEGRAM_POOL_TIMEOUT = 10.0
TELEGRAM_MEDIA_WRITE_TIMEOUT = 60.0
TELEGRAM_BOOTSTRAP_RETRIES = 3
TELEGRAM_POLL_TIMEOUT_SECONDS = 30
_telegram_product_limit_raw = os.getenv("TELEGRAM_ORCHESTRATOR_PRODUCT_LIMIT", "").strip()
TELEGRAM_ORCHESTRATOR_PRODUCT_LIMIT = int(_telegram_product_limit_raw) if _telegram_product_limit_raw else None
logger = logging.getLogger("dns_bot.telegram")
LOCK_FILE_PATH = TELEGRAM_BOT_LOCK_FILE
NETWORK_ERROR_LOG_INTERVAL_SECONDS = 60.0
BOARD_RESET_TEXT = "Сброс"
BOARD_LOGIN_TEXT = "Логин"
BOARD_AI_TEXT = "/ai"
BOARD_TECH_TEXT = "/tech"
LOCK_FILE_HANDLE = None


def acquire_bot_lock() -> None:
    acquire_runtime_bot_lock(LOCK_FILE_PATH)


def release_bot_lock() -> None:
    release_runtime_bot_lock(LOCK_FILE_PATH)


class TelegramBotRuntime:
    def __init__(self, orchestrator=None, memory_path: Path | str = MEMORY_FILE) -> None:
        self.orchestrator = orchestrator
        self.memory_path = Path(memory_path)
        self._last_network_error_log_at = 0.0

    async def start(self, update, _context) -> None:
        await update.message.reply_text(
            render_markdown_v2(START_TEXT),
            parse_mode=TELEGRAM_PARSE_MODE,
            reply_markup=self.build_command_keyboard(),
        )

    async def reset(self, update, _context) -> None:
        reset_chat_memory(update.effective_chat.id, path=self.memory_path)
        await update.message.reply_text(
            render_markdown_v2("Память сброшена."),
            parse_mode=TELEGRAM_PARSE_MODE,
            reply_markup=self.build_command_keyboard(),
        )

    async def handle_message(self, update, _context) -> None:
        await self.run_query_update(update, update.message.text or "", tech_mode=False)

    async def ai(self, update, _context) -> None:
        await self.run_query_update(update, self.extract_command_query(update.message.text or "", "ai"), tech_mode=False)

    async def tech(self, update, _context) -> None:
        await self.run_query_update(update, self.extract_command_query(update.message.text or "", "tech"), tech_mode=True)

    async def run_query_update(self, update, user_text: str, tech_mode: bool) -> None:
        chat_id = update.effective_chat.id
        stream_partial_answer = tech_mode
        if await self.handle_board_command(update, user_text):
            return
        if not str(user_text).strip():
            usage = "Использование: /tech <запрос>" if tech_mode else "Использование: /ai <запрос>"
            await update.message.reply_text(
                render_markdown_v2(usage),
                parse_mode=TELEGRAM_PARSE_MODE,
                reply_markup=self.build_command_keyboard(),
            )
            return
        logger.info("telegram_message chat_id=%s text=%s", chat_id, trim_telegram_text(user_text))
        initial_text = render_stage_message("start") if tech_mode else "Обработка данных..."
        sent = await update.message.reply_text(
            render_markdown_v2(initial_text),
            parse_mode=TELEGRAM_PARSE_MODE,
        )
        state: dict[str, object] = {"last_text": initial_text}
        buffer: list[str] = []
        stop_event: asyncio.Event | None = None
        flush_task = None
        stage_reporter = TelegramStageReporter(
            sent,
            state,
            self.safe_edit_text,
        ) if tech_mode else None
        if stream_partial_answer:
            stop_event = asyncio.Event()
            flush_task = asyncio.create_task(self.flush_stream_updates(sent, buffer, stop_event, state))

        def on_chunk(chunk: str) -> None:
            if stage_reporter is not None and not stage_reporter.finalization_started:
                return
            if looks_like_raw_json_chunk(chunk):
                return
            buffer.append(chunk)

        try:
            result = await self.get_orchestrator().handle_message(
                user_text,
                history=load_chat_memory(chat_id, path=self.memory_path),
                on_text_chunk=on_chunk if stream_partial_answer else None,
                on_stage=stage_reporter.on_stage if stage_reporter is not None else None,
                memory_context=load_chat_context(chat_id, path=self.memory_path),
            )
        except Exception as exc:
            if stage_reporter is not None:
                await stage_reporter.flush()
            if stop_event is not None:
                stop_event.set()
            if flush_task is not None:
                await self.finish_flush(flush_task)
            error_text = format_user_error(exc)
            await self.deliver_error(sent, update, error_text, state)
            if is_known_user_error(exc):
                logger.warning("telegram_user_error chat_id=%s error=%s", chat_id, sanitize_error(exc))
            else:
                logger.exception("telegram_message_error chat_id=%s", chat_id)
            return

        if stage_reporter is not None:
            await stage_reporter.flush()
        if stop_event is not None:
            stop_event.set()
        if flush_task is not None:
            await self.finish_flush(flush_task)
        final_answer = sanitize_telegram_answer(
            self.build_tech_answer(result, user_text) if tech_mode else (result.answer or "Ответ пуст.")
        )
        final_message = build_live_message(final_answer)
        delivery_status = await self.safe_edit_text(sent, final_message, state)
        if delivery_status in {"timed_out", "failed"}:
            await self.send_fallback_text(update, final_message)
        append_turn(chat_id, "user", user_text, path=self.memory_path)
        append_turn(chat_id, "assistant", final_answer, path=self.memory_path)
        if hasattr(result, "context_payload") and isinstance(result.context_payload, dict):
            self.save_context(chat_id, result.context_payload)
        logger.info(
            "telegram_message_done chat_id=%s images=%s products=%s delivery=%s",
            chat_id,
            0,
            result.products_count,
            delivery_status,
        )

    async def deliver_error(self, sent_message, update, text: str, state: dict[str, object]) -> None:
        status = await self.safe_edit_text(sent_message, text, state)
        if status in {"timed_out", "failed"}:
            await self.send_fallback_text(update, text)

    async def send_fallback_text(self, update, text: str) -> None:
        try:
            await update.message.reply_text(
                render_markdown_v2(trim_telegram_text(sanitize_telegram_answer(text))),
                parse_mode=TELEGRAM_PARSE_MODE,
                reply_markup=self.build_command_keyboard(),
            )
            logger.warning("telegram_delivery_fallback_send")
        except Exception as exc:
            logger.error("telegram_delivery_fallback_failed error=%s", sanitize_error(exc))

    def build_command_keyboard(self):
        from telegram import KeyboardButton, ReplyKeyboardMarkup

        return ReplyKeyboardMarkup(
            [
                [KeyboardButton(BOARD_RESET_TEXT), KeyboardButton(BOARD_LOGIN_TEXT)],
                [KeyboardButton(BOARD_AI_TEXT), KeyboardButton(BOARD_TECH_TEXT)],
            ],
            resize_keyboard=True,
            is_persistent=True,
        )

    async def handle_board_command(self, update, text: str) -> bool:
        normalized = " ".join(str(text).split()).strip().casefold()
        if normalized == BOARD_RESET_TEXT.casefold():
            await self.reset(update, None)
            return True
        if normalized == BOARD_LOGIN_TEXT.casefold():
            await update.message.reply_text(
                render_markdown_v2("Функция ещё не подключена."),
                parse_mode=TELEGRAM_PARSE_MODE,
                reply_markup=self.build_command_keyboard(),
            )
            return True
        return False

    @staticmethod
    def extract_command_query(text: str, command: str) -> str:
        pattern = rf"^/{re.escape(command)}(?:@[A-Za-z0-9_]+)?\s*"
        return re.sub(pattern, "", text.strip(), flags=re.IGNORECASE).strip()

    @staticmethod
    def build_tech_answer(result, user_text: str | None = None) -> str:
        return build_telegram_tech_answer(result, user_text)

    def load_context(self, chat_id: int) -> dict[str, object]:
        return load_chat_context(chat_id, path=self.memory_path) or {}

    def save_context(self, chat_id: int, context: dict[str, object]) -> None:
        save_chat_context(chat_id, context, path=self.memory_path)

    def get_orchestrator(self):
        if self.orchestrator is None:
            ensure_runtime_directories()
            self.orchestrator = ProductAnalysisOrchestrator(
                product_limit=TELEGRAM_ORCHESTRATOR_PRODUCT_LIMIT,
            )
        return self.orchestrator

    def prime_startup(self) -> None:
        prewarm_dns_cookies(reason="telegram_startup")
        orchestrator = self.get_orchestrator()
        if hasattr(orchestrator, "prime_static_category_fast_path"):
            orchestrator.prime_static_category_fast_path()

    async def aclose(self) -> None:
        orchestrator = self.orchestrator
        if orchestrator is None:
            return
        if hasattr(orchestrator, "aclose"):
            await orchestrator.aclose()

    async def handle_error(self, update, context) -> None:
        error = getattr(context, "error", None)
        chat_id = getattr(getattr(update, "effective_chat", None), "id", None)
        error_text = sanitize_error(error) if isinstance(error, Exception) else str(error)
        if error is not None and is_network_error_text(error_text):
            if not self.should_log_network_error():
                return
            logger.warning("telegram_network_error chat_id=%s error=%s", chat_id, error_text)
            return
        logger.error("telegram_unhandled_error chat_id=%s error=%s", chat_id, error_text)

    def should_log_network_error(self) -> bool:
        now = monotonic()
        if now - self._last_network_error_log_at < NETWORK_ERROR_LOG_INTERVAL_SECONDS:
            return False
        self._last_network_error_log_at = now
        return True

    async def finish_flush(self, flush_task: asyncio.Task[None]) -> None:
        try:
            await flush_task
        except asyncio.CancelledError:
            return

    async def flush_stream_updates(
        self,
        sent_message,
        buffer: list[str],
        stop_event: asyncio.Event,
        state: dict[str, object],
    ) -> None:
        last_buffer = ""
        while not stop_event.is_set():
            current_text = "".join(buffer)
            should_flush = current_text and current_text != last_buffer
            if should_flush and len(current_text) >= STREAM_EDIT_CHARS:
                delivery_status = await self.safe_edit_text(sent_message, build_live_message(sanitize_telegram_answer(current_text)), state)
                if delivery_status == "updated":
                    logger.info("telegram_stream_edit chars=%s", len(trim_telegram_text(current_text)))
                last_buffer = current_text
            await asyncio.sleep(STREAM_EDIT_SECONDS)
        current_text = "".join(buffer)
        if current_text and current_text != last_buffer:
            await self.safe_edit_text(sent_message, build_live_message(sanitize_telegram_answer(current_text)), state)

    async def safe_edit_text(self, sent_message, text: str, state: dict[str, object]) -> str:
        trimmed = trim_telegram_text(text)
        if state.get("edit_disabled"):
            return "failed"
        if trimmed == state.get("last_text", ""):
            return "skipped"
        try:
            await sent_message.edit_text(render_markdown_v2(trimmed), parse_mode=TELEGRAM_PARSE_MODE)
        except Exception as exc:
            if is_message_not_modified_error(exc):
                return "skipped"
            if is_message_cant_be_edited_error(exc):
                state["edit_disabled"] = True
                logger.warning("telegram_delivery_edit_disabled error=%s", sanitize_error(exc))
                return "failed"
            if is_timed_out_error(exc):
                logger.warning("telegram_delivery_edit_timeout error=%s", sanitize_error(exc))
                return "timed_out"
            logger.error("telegram_delivery_edit_failed error=%s", sanitize_error(exc))
            return "failed"
        state["last_text"] = trimmed
        return "updated"


def is_known_user_error(exc: Exception) -> bool:
    text = str(exc)
    return text in {BLOCKED_AFTER_BOOTSTRAP, BLOCKED_REQUIRES_BROWSER}


def format_user_error(exc: Exception) -> str:
    text = sanitize_error(exc)
    if text == BLOCKED_AFTER_BOOTSTRAP:
        return (
            "Ошибка: DNS сейчас не отдаёт выдачу после обычной загрузки страницы. "
            "Если запрос был без category, откройте поиск в браузере, дождитесь URL с category "
            "и пришлите уже готовую ссылку DNS."
        )
    if text == BLOCKED_REQUIRES_BROWSER:
        return (
            "Ошибка: DNS запросил дополнительную проверку страницы. "
            "Откройте поиск в браузере, дождитесь полной загрузки и пришлите готовую ссылку DNS с category."
        )
    return f"Ошибка: {text}"


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def main() -> int:
    configure_logging()
    load_dotenv_if_available()
    logger.info("telegram_bot_start log_file=%s", LOG_FILE)
    acquire_bot_lock()
    atexit.register(release_bot_lock)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    from telegram.request import HTTPXRequest

    runtime = TelegramBotRuntime()
    request = HTTPXRequest(
        connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
        read_timeout=TELEGRAM_READ_TIMEOUT,
        write_timeout=TELEGRAM_WRITE_TIMEOUT,
        pool_timeout=TELEGRAM_POOL_TIMEOUT,
        media_write_timeout=TELEGRAM_MEDIA_WRITE_TIMEOUT,
    )
    async def post_shutdown(_application) -> None:
        await runtime.aclose()

    application = (
        Application.builder()
        .token(token)
        .request(request)
        .get_updates_request(request)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", runtime.start))
    application.add_handler(CommandHandler("reset", runtime.reset))
    application.add_handler(CommandHandler("ai", runtime.ai))
    application.add_handler(CommandHandler("tech", runtime.tech))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, runtime.handle_message))
    application.add_error_handler(runtime.handle_error)
    logger.info("telegram_bot_polling_start")
    application.run_polling(timeout=TELEGRAM_POLL_TIMEOUT_SECONDS, bootstrap_retries=TELEGRAM_BOOTSTRAP_RETRIES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
