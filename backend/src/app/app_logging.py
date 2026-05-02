from __future__ import annotations

import logging
import re
from .project_paths import LOGS_DIR, ensure_runtime_directories


LOG_DIR = LOGS_DIR
LOG_FILE = LOG_DIR / "telegram_bot.log"
TELEGRAM_BOT_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)[^/\s\"]+")
API_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-]+")


def redact_sensitive_text(value: str) -> str:
    redacted = TELEGRAM_BOT_URL_RE.sub(r"\1<redacted>", value)
    return API_KEY_RE.sub("sk-***", redacted)


def sanitize_log_args(value: object) -> object:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, tuple):
        return tuple(sanitize_log_args(item) for item in value)
    if isinstance(value, list):
        return [sanitize_log_args(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_log_args(item) for key, item in value.items()}
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            record.args = sanitize_log_args(record.args)
        return True


def ensure_redacting_filter(logger: logging.Logger) -> None:
    if any(isinstance(existing, RedactingFilter) for existing in logger.filters):
        return
    logger.addFilter(RedactingFilter())


def configure_logging() -> None:
    ensure_runtime_directories()
    root_logger = logging.getLogger()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers = list(root_logger.handlers)
    if not handlers:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        stream_handler = logging.StreamHandler()
        handlers = [file_handler, stream_handler]
        logging.basicConfig(level=logging.INFO, handlers=handlers)
    for handler in handlers:
        handler.setFormatter(formatter)
        if not any(isinstance(existing, RedactingFilter) for existing in handler.filters):
            handler.addFilter(RedactingFilter())
    if not any(isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == str(LOG_FILE) for handler in handlers):
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(RedactingFilter())
        root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
    ensure_redacting_filter(root_logger)
    httpx_logger = logging.getLogger("httpx")
    httpcore_logger = logging.getLogger("httpcore")
    ensure_redacting_filter(httpx_logger)
    ensure_redacting_filter(httpcore_logger)
    httpx_logger.setLevel(logging.WARNING)
    httpcore_logger.setLevel(logging.WARNING)
