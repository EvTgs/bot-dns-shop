from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_SRC_DIR = PROJECT_DIR / "backend" / "src"
if str(BACKEND_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC_DIR))

from app.ai_orchestrator import ProductAnalysisOrchestrator
from app.deepseek_client import DeepSeekClient

ARTIFACTS_DIR = PROJECT_DIR / "backend" / "test" / "artifacts" / "live_chat_compare"
DEFAULT_CHAT_ID = 2122344909
DIRECT_CHAT_SYSTEM_PROMPT = (
    "Ты обычный ассистент в Telegram. "
    "Отвечай естественно, кратко и по делу. "
    "Строго следуй последнему ограничению пользователя по формату. "
    "Не выдумывай функции, которых не просили."
)
TEST_SCENARIOS = [
    {
        "id": "chat_identity",
        "turns": [
            "Кто ты в этом боте и чем реально можешь помочь?",
            "Ответь короче, одним абзацем, без списка и без официоза.",
        ],
    },
    {
        "id": "chat_limits",
        "turns": [
            "Если я попрошу подобрать технику, что ты сделаешь по шагам?",
            "Теперь ответь без шагов, только суть в 2 предложениях.",
        ],
    },
]


@dataclass
class TurnResult:
    prompt: str
    bot_answer: str
    direct_answer: str


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PROJECT_DIR / ".env")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def compare_answers(bot_answer: str, direct_answer: str) -> dict[str, object]:
    return {
        "bot_len": len(bot_answer),
        "direct_len": len(direct_answer),
        "bot_has_list": any(token in bot_answer for token in ("1.", "2.", "-", "•")),
        "direct_has_list": any(token in direct_answer for token in ("1.", "2.", "-", "•")),
        "bot_mentions_dns": "dns" in bot_answer.casefold(),
        "direct_mentions_dns": "dns" in direct_answer.casefold(),
    }


def build_direct_messages(prompt: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": DIRECT_CHAT_SYSTEM_PROMPT}]
    messages.extend(history[-8:])
    messages.append({"role": "user", "content": prompt})
    return messages


async def run_scenario(
    orchestrator: ProductAnalysisOrchestrator,
    direct_client: DeepSeekClient,
    turns: list[str],
) -> list[TurnResult]:
    bot_history: list[dict[str, str]] = []
    direct_history: list[dict[str, str]] = []
    results: list[TurnResult] = []
    for prompt in turns:
        bot_result = await orchestrator.handle_message(
            prompt,
            history=bot_history,
            on_text_chunk=None,
            on_stage=lambda _stage: None,
            memory_context={},
        )
        direct_answer = await direct_client.chat(build_direct_messages(prompt, direct_history))
        bot_answer = bot_result.answer.strip()
        direct_answer = direct_answer.strip()
        results.append(TurnResult(prompt=prompt, bot_answer=bot_answer, direct_answer=direct_answer))
        bot_history.append({"role": "user", "content": prompt})
        bot_history.append({"role": "assistant", "content": bot_answer})
        direct_history.append({"role": "user", "content": prompt})
        direct_history.append({"role": "assistant", "content": direct_answer})
    return results


def render_markdown_report(title: str, scenario_id: str, turns: list[TurnResult]) -> str:
    lines = [f"# {title}", "", f"scenario: `{scenario_id}`", ""]
    for index, turn in enumerate(turns, start=1):
        metrics = compare_answers(turn.bot_answer, turn.direct_answer)
        lines.extend(
            [
                f"## Turn {index}",
                "",
                f"Prompt: {turn.prompt}",
                "",
                "### Bot",
                turn.bot_answer,
                "",
                "### Direct",
                turn.direct_answer,
                "",
                "### Metrics",
                json.dumps(metrics, ensure_ascii=False, indent=2),
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


async def send_telegram_message(text: str, chat_id: int) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(endpoint, json={"chat_id": chat_id, "text": text})


async def main() -> int:
    load_dotenv_if_available()
    chat_id = int(os.getenv("DNS_COMPARE_CHAT_ID", str(DEFAULT_CHAT_ID)))
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = ensure_dir(ARTIFACTS_DIR / run_id)
    orchestrator = ProductAnalysisOrchestrator()
    direct_client = DeepSeekClient.from_env(max_tokens=900, temperature=0.2)
    summary_lines = [f"Сравнительный live chat run: {run_id}"]
    try:
        for scenario in TEST_SCENARIOS:
            turns = await run_scenario(orchestrator, direct_client, scenario["turns"])
            report = render_markdown_report("Live Chat Compare", scenario["id"], turns)
            (output_dir / f"{scenario['id']}.md").write_text(report, encoding="utf-8")
            payload = {
                "scenario": scenario["id"],
                "turns": [asdict(item) for item in turns],
            }
            (output_dir / f"{scenario['id']}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            summary_lines.append(f"{scenario['id']}: {len(turns)} turns")
        await send_telegram_message("\n".join(summary_lines), chat_id)
    finally:
        await direct_client.aclose()
        close_method = getattr(orchestrator, "aclose", None)
        if callable(close_method):
            await close_method()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
