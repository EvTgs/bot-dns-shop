from __future__ import annotations

from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt_text(filename: str, fallback: str) -> str:
    path = PROMPTS_DIR / filename
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback
    return value or fallback


NORMALIZE_QUERY_SYSTEM_PROMPT = load_prompt_text(
    "normalize_query_system.txt",
    "Нормализуй товарный запрос в массив [ {query_rus}, {price}, {brand_en}, {hard_wishes}, {subjective_wishes} ].",
)
ROUTER_SYSTEM_PROMPT = load_prompt_text(
    "router_system.txt",
    "Верни только JSON с mode, response_style, reason.",
)
GENERAL_CHAT_SYSTEM_PROMPT = load_prompt_text(
    "general_chat_system.txt",
    "Отвечай кратко и по делу.",
)
FOLLOWUP_DIRECT_SYSTEM_PROMPT = load_prompt_text(
    "followup_direct_system.txt",
    "Отвечай только по переданным товарам.",
)
CHAT_TEACHER_SYSTEM_PROMPT = load_prompt_text(
    "chat_teacher_system.txt",
    "Отредактируй draft_answer по формату user_request без новых фактов.",
)
FILTER_SELECTION_SYSTEM_PROMPT = load_prompt_text(
    "filter_selection_system.txt",
    "Верни JSON с filters для DNS-карты.",
)
FINAL_ANALYSIS_SYSTEM_PROMPT = load_prompt_text(
    "final_analysis_system.txt",
    "Сформируй итоговый аналитический ответ по переданным данным.",
)
