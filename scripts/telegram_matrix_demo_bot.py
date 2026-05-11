from __future__ import annotations

import asyncio
import math
import os
import sys
from pathlib import Path

from telegram.error import RetryAfter

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_SRC_DIR = ROOT_DIR / "backend" / "src"
if str(BACKEND_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC_DIR))

from app.telegram_matrix import build_progressive_reveal_frames


AUTO_BUTTON_TEXT = "Авто 6с"
MATRIX_FRAME_SECONDS = 0.08
MAX_DEMO_SECONDS = 6.0
MAX_DEMO_EDITS = 12

CARD_TEST_MESSAGE = """🔍 Найдено: RTX 4070 (2 варианта)

1. MSI GeForce RTX 4070 Ventus 3X
💰 Цена: 62 999 ₽
📦 Наличие: В наличии
⭐ Оценка: 8.7 / 10

✔️ Плюсы:
– хорошее охлаждение
– тихая работа

❌ Минусы:
– высокая цена

—————————————

2. Palit RTX 4070 Dual
💰 Цена: 59 990 ₽
📦 Наличие: Мало на складе
⭐ Оценка: 8.2 / 10

✔️ Плюсы:
– дешевле конкурентов
– компактная

❌ Минусы:
– проще охлаждение

—————————————

📊 Итог:
Лучший выбор: MSI Ventus 3X (баланс производительности и шума)
Бюджетный вариант: Palit Dual"""


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


async def start(update, _context) -> None:
    await update.message.reply_text(
        "Тестовый бот карточки готов. Нажми кнопку для авто-раскрытия.",
        reply_markup=build_keyboard(),
    )


async def test_command(update, _context) -> None:
    await update.message.reply_text(
        "Нажми кнопку `Авто 6с` для теста карточки.",
        reply_markup=build_keyboard(),
    )


async def handle_message(update, _context) -> None:
    normalized = " ".join((update.message.text or "").split()).strip().casefold()
    if normalized == AUTO_BUTTON_TEXT.casefold():
        await run_card_demo(update)
        return
    await update.message.reply_text(
        "Используй кнопку `Авто 6с` или команду /test.",
        reply_markup=build_keyboard(),
    )


async def run_card_demo(update) -> None:
    await update.message.reply_text(
        "Показываю карточку. Режим: Авто 6с.",
        reply_markup=build_keyboard(),
    )
    sent = await update.message.reply_text("▓")
    effective_reveal_size = budget_reveal_size(
        CARD_TEST_MESSAGE,
        reveal_size=5,
        unit="char",
        max_seconds=MAX_DEMO_SECONDS,
        frame_seconds=MATRIX_FRAME_SECONDS,
    )
    frames = build_progressive_reveal_frames(
        CARD_TEST_MESSAGE,
        reveal_size=effective_reveal_size,
        unit="char",
    )
    frame_delay = compute_frame_delay(len(frames), MAX_DEMO_SECONDS)
    for frame in frames:
        try:
            await sent.edit_text(frame)
        except RetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.5)
            continue
        except Exception:
            await update.message.reply_text(CARD_TEST_MESSAGE, reply_markup=build_keyboard())
            return
        await asyncio.sleep(frame_delay)


def build_keyboard():
    from telegram import KeyboardButton, ReplyKeyboardMarkup

    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(AUTO_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def budget_reveal_size(text: str, reveal_size: int, unit: str, max_seconds: float, frame_seconds: float) -> int:
    final_text = text.strip("\n")
    if not final_text:
        return max(1, reveal_size)
    max_frames = max(2, min(int(max_seconds / frame_seconds), MAX_DEMO_EDITS))
    if unit == "word":
        total_units = count_words(final_text)
    else:
        total_units = count_nonspace_chars(final_text)
    if total_units <= 0:
        return max(1, reveal_size)
    max_reveal_steps = max(1, max_frames - 1)
    required_size = math.ceil(total_units / max_reveal_steps)
    return max(1, max(reveal_size, required_size))


def count_nonspace_chars(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def count_words(text: str) -> int:
    return sum(1 for part in text.split() if part)


def compute_frame_delay(frame_count: int, max_seconds: float) -> float:
    if frame_count <= 1:
        return max_seconds
    return max(max_seconds / max(1, frame_count - 1), MATRIX_FRAME_SECONDS)


def main() -> int:
    load_dotenv_if_available()
    token = os.getenv("TELEGRAM_MATRIX_TEST_BOT_TOKEN", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_MATRIX_TEST_BOT_TOKEN is not configured.")
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
