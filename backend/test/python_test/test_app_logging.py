from __future__ import annotations

import logging
from pathlib import Path

from app.app_logging import RedactingFilter, configure_logging


def test_redacting_filter_masks_telegram_token_and_api_key() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='HTTP Request: POST https://api.telegram.org/bot123456:SECRET/getMe "HTTP/1.1 200 OK" key=sk-secret123',
        args=(),
        exc_info=None,
    )

    assert RedactingFilter().filter(record) is True
    assert "bot123456:SECRET" not in record.msg
    assert "sk-secret123" not in record.msg
    assert "bot<redacted>" in record.msg
    assert "sk-***" in record.msg


def test_redacting_filter_masks_sensitive_args() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP Request: %s %s",
        args=("POST", "https://api.telegram.org/bot123456:SECRET/getUpdates"),
        exc_info=None,
    )

    RedactingFilter().filter(record)

    assert record.args == ("POST", "https://api.telegram.org/bot<redacted>/getUpdates")


def test_configure_logging_adds_redaction_to_existing_handlers(tmp_path: Path, monkeypatch) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    handler = logging.StreamHandler()
    root.handlers = [handler]
    try:
        monkeypatch.setattr("app.app_logging.LOG_FILE", tmp_path / "telegram_bot.log")
        monkeypatch.setattr("app.app_logging.ensure_runtime_directories", lambda: None)
        configure_logging()
        assert any(isinstance(item, RedactingFilter) for item in handler.filters)
        assert any(isinstance(item, RedactingFilter) for item in logging.getLogger("httpx").filters)
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
    finally:
        for existing in list(root.handlers):
            if existing not in original_handlers:
                existing.close()
        root.handlers = original_handlers
        root.setLevel(original_level)
        logging.getLogger("httpx").filters.clear()
        logging.getLogger("httpcore").filters.clear()
        logging.getLogger("httpx").setLevel(logging.NOTSET)
        logging.getLogger("httpcore").setLevel(logging.NOTSET)
