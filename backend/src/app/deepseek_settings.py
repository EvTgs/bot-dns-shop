from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .project_paths import runtime_path


DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_ENDPOINT_PATH = "/chat/completions"
DEEPSEEK_SETTINGS_FILE = runtime_path("deepseek_settings.json")


@dataclass(frozen=True)
class DeepSeekSettings:
    model: str = DEFAULT_DEEPSEEK_MODEL
    fallback_model: str = ""
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    endpoint_path: str = DEFAULT_DEEPSEEK_ENDPOINT_PATH


def normalize_endpoint_path(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return DEFAULT_DEEPSEEK_ENDPOINT_PATH
    return cleaned if cleaned.startswith("/") else f"/{cleaned}"


def build_default_deepseek_settings() -> DeepSeekSettings:
    return DeepSeekSettings(
        model=os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL).strip() or DEFAULT_DEEPSEEK_MODEL,
        fallback_model=os.getenv("DEEPSEEK_FALLBACK_MODEL", "").strip(),
        base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL).strip() or DEFAULT_DEEPSEEK_BASE_URL,
        endpoint_path=normalize_endpoint_path(os.getenv("DEEPSEEK_ENDPOINT_PATH", DEFAULT_DEEPSEEK_ENDPOINT_PATH)),
    )


def load_deepseek_settings(path: Path | None = None) -> DeepSeekSettings:
    settings_path = path or DEEPSEEK_SETTINGS_FILE
    defaults = build_default_deepseek_settings()
    if not settings_path.exists():
        return defaults
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(payload, dict):
        return defaults
    return DeepSeekSettings(
        model=str(payload.get("model", defaults.model)).strip() or defaults.model,
        fallback_model=str(payload.get("fallback_model", defaults.fallback_model)).strip(),
        base_url=str(payload.get("base_url", defaults.base_url)).strip() or defaults.base_url,
        endpoint_path=normalize_endpoint_path(str(payload.get("endpoint_path", defaults.endpoint_path))),
    )


def save_deepseek_settings(settings: DeepSeekSettings, path: Path | None = None) -> Path:
    settings_path = path or DEEPSEEK_SETTINGS_FILE
    settings_path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return settings_path


def describe_deepseek_settings(settings: DeepSeekSettings) -> str:
    fallback_part = f" fallback_model={settings.fallback_model}" if settings.fallback_model else ""
    return f"model={settings.model}{fallback_part} base_url={settings.base_url} endpoint_path={settings.endpoint_path}"
