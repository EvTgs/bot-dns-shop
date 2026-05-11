import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import telegram_matrix_demo_bot as demo


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.replies: list[str] = []
        self.reply_markups = []
        self.sent_messages: list[FakeSentMessage] = []
        self.next_message_id = 1

    async def reply_text(self, text: str, **kwargs):
        self.replies.append(text)
        self.reply_markups.append(kwargs.get("reply_markup"))
        sent = FakeSentMessage(message_id=self.next_message_id)
        self.next_message_id += 1
        self.sent_messages.append(sent)
        return sent


class FakeSentMessage:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id
        self.edits: list[str] = []

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edits.append(text)


class FakeUpdate:
    def __init__(self, text: str) -> None:
        self.message = FakeMessage(text)


def test_start_sends_auto_keyboard() -> None:
    asyncio.run(run_start_sends_auto_keyboard())


async def run_start_sends_auto_keyboard() -> None:
    update = FakeUpdate("/start")

    await demo.start(update, None)

    assert update.message.replies
    assert "авто-раскрытия" in update.message.replies[0]
    markup = update.message.reply_markups[0]
    labels = [[button.text for button in row] for row in markup.keyboard]
    assert labels == [[demo.AUTO_BUTTON_TEXT]]


def test_handle_message_routes_auto_mode() -> None:
    asyncio.run(run_handle_message_routes_auto_mode())


async def run_handle_message_routes_auto_mode() -> None:
    update = FakeUpdate(demo.AUTO_BUTTON_TEXT)

    await demo.handle_message(update, None)

    assert update.message.replies
    assert update.message.replies[0] == "Показываю карточку. Режим: Авто 6с."
    assert update.message.replies[1] == "▓"
    assert len(update.message.sent_messages) == 2
    assert update.message.sent_messages[1].edits
    assert update.message.sent_messages[1].edits[-1] == demo.CARD_TEST_MESSAGE


def test_budget_reveal_size_caps_duration() -> None:
    effective = demo.budget_reveal_size(
        demo.CARD_TEST_MESSAGE,
        reveal_size=5,
        unit="char",
        max_seconds=demo.MAX_DEMO_SECONDS,
        frame_seconds=demo.MATRIX_FRAME_SECONDS,
    )

    assert effective >= 5
    assert effective > 5


def test_compute_frame_delay_scales_to_budget() -> None:
    delay = demo.compute_frame_delay(8, demo.MAX_DEMO_SECONDS)

    assert delay >= demo.MATRIX_FRAME_SECONDS
    assert delay <= demo.MAX_DEMO_SECONDS
