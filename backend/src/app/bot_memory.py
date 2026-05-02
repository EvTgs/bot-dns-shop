from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from .project_paths import MEMORY_FILE, ensure_runtime_directories


MEMORY_PATH = MEMORY_FILE
MAX_HISTORY_TURNS = 8
_MEMORY_LOCKS: dict[Path, threading.RLock] = {}
_MEMORY_LOCKS_GUARD = threading.Lock()


def load_chat_memory(chat_id: int, path: Path = MEMORY_PATH) -> list[dict[str, str]]:
    payload = read_memory_payload(path)
    history = get_chat_state(payload, chat_id).get("history", [])
    if not isinstance(history, list):
        return []
    return [turn for turn in history if is_valid_turn(turn)]


def load_chat_context(chat_id: int, path: Path = MEMORY_PATH) -> dict[str, object] | None:
    payload = read_memory_payload(path)
    context = get_chat_state(payload, chat_id).get("context")
    return context if isinstance(context, dict) else None


def append_turn(chat_id: int, role: str, content: str, path: Path = MEMORY_PATH) -> None:
    def mutate(payload: dict[str, object]) -> None:
        state = get_chat_state(payload, chat_id)
        history = state.get("history", [])
        if not isinstance(history, list):
            history = []
        history.append({"role": role, "content": content})
        state["history"] = history[-MAX_HISTORY_TURNS:]
        payload[str(chat_id)] = state

    mutate_memory_payload(path, mutate)


def save_chat_context(chat_id: int, context: dict[str, object], path: Path = MEMORY_PATH) -> None:
    def mutate(payload: dict[str, object]) -> None:
        state = get_chat_state(payload, chat_id)
        state["context"] = context
        payload[str(chat_id)] = state

    mutate_memory_payload(path, mutate)


def reset_chat_memory(chat_id: int, path: Path = MEMORY_PATH) -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload.pop(str(chat_id), None)

    mutate_memory_payload(path, mutate)


def read_memory_payload(path: Path) -> dict[str, object]:
    with memory_lock_for(path):
        return read_memory_payload_unlocked(path)


def read_memory_payload_unlocked(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_memory_payload(path: Path, payload: dict[str, object]) -> None:
    with memory_lock_for(path):
        write_memory_payload_unlocked(path, payload)


def write_memory_payload_unlocked(path: Path, payload: dict[str, object]) -> None:
    ensure_runtime_directories()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = build_temp_memory_path(path)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        temp_path.write_text(serialized, encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def mutate_memory_payload(path: Path, mutator: Callable[[dict[str, object]], None]) -> None:
    with memory_lock_for(path):
        payload = read_memory_payload_unlocked(path)
        mutator(payload)
        write_memory_payload_unlocked(path, payload)


def memory_lock_for(path: Path) -> threading.RLock:
    normalized = path.resolve()
    with _MEMORY_LOCKS_GUARD:
        lock = _MEMORY_LOCKS.get(normalized)
        if lock is None:
            lock = threading.RLock()
            _MEMORY_LOCKS[normalized] = lock
        return lock


def build_temp_memory_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.{threading.get_ident()}.tmp")


def is_valid_turn(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return isinstance(value.get("role"), str) and isinstance(value.get("content"), str)


def get_chat_state(payload: dict[str, object], chat_id: int) -> dict[str, object]:
    raw = payload.get(str(chat_id), {})
    if isinstance(raw, list):
        return {"history": raw, "context": None}
    return raw if isinstance(raw, dict) else {"history": [], "context": None}
