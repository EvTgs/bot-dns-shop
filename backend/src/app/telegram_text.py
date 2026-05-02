from __future__ import annotations


def sanitize_error(exc: Exception) -> str:
    return " ".join(str(exc).replace("sk-", "sk-***").split())


def trim_telegram_text(value: str) -> str:
    if len(value) <= 3900:
        return value
    return value[:3897].rstrip() + "..."


def is_message_not_modified_error(exc: Exception) -> bool:
    return "message is not modified" in str(exc).lower()


def is_message_cant_be_edited_error(exc: Exception) -> bool:
    return "message can't be edited" in str(exc).lower()


def is_timed_out_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "timed out" in text or "timeout" in text


def is_network_error_text(value: str) -> bool:
    lowered = value.lower()
    return "readerror" in lowered or "networkerror" in lowered or "httpx.readerror" in lowered


def build_live_message(answer_text: str) -> str:
    answer_block = trim_telegram_text(answer_text.strip())
    return answer_block or "Обработка данных..."


def sanitize_telegram_answer(value: str) -> str:
    cleaned = value.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
    cleaned = cleaned.replace("**", "").replace("__", "").replace("`", "").replace("*", "")
    lines = [line.lstrip("# ").rstrip() for line in cleaned.splitlines()]
    return "\n".join(lines).strip()


def render_markdown_v2(value: str) -> str:
    lines = [line.rstrip() for line in value.splitlines()]
    rendered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            rendered.append("")
            continue
        heading = parse_heading_line(stripped)
        if heading is not None:
            rendered.append(f"*{escape_markdown_v2(heading)}*")
            continue
        bullet = parse_bullet_line(stripped)
        if bullet is not None:
            rendered.append(f"• {escape_markdown_v2(bullet)}")
            continue
        rendered.append(escape_markdown_v2(stripped))
    return "\n".join(rendered)


def parse_heading_line(value: str) -> str | None:
    headings = (
        "Лучший вариант",
        "Почему он подходит",
        "Что сильнее у альтернатив",
        "Компромиссы и проверки",
        "Лидер анализа",
        "Альтернатива",
        "Критическое резюме",
        "Ближайшие аналоги",
    )
    for heading in headings:
        if value.startswith(heading):
            return heading
    return None


def parse_bullet_line(value: str) -> str | None:
    for prefix in ("• ", "- ", "— "):
        if value.startswith(prefix):
            return value[len(prefix):].strip()
    return None


def escape_markdown_v2(value: str) -> str:
    escaped = []
    special_chars = set("_*[]()~`>#+-=|{}.!")
    for char in value:
        if char in special_chars:
            escaped.append("\\")
        escaped.append(char)
    return "".join(escaped)
