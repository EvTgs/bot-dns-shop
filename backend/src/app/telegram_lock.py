from __future__ import annotations

import atexit
import ctypes
import json
import os
from pathlib import Path

from .project_paths import ensure_runtime_directories


_LOCK_FILE_HANDLE = None


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    process_handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not process_handle:
        return False
    ctypes.windll.kernel32.CloseHandle(process_handle)
    return True


def get_process_image_path(pid: int) -> str:
    if pid <= 0:
        return ""
    process_handle = ctypes.windll.kernel32.OpenProcess(0x1000 | 0x0400, False, pid)
    if not process_handle:
        return ""
    try:
        buffer_length = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(buffer_length.value)
        result = ctypes.windll.kernel32.QueryFullProcessImageNameW(
            process_handle,
            0,
            buffer,
            ctypes.byref(buffer_length),
        )
        if not result:
            return ""
        return buffer.value[: buffer_length.value]
    finally:
        ctypes.windll.kernel32.CloseHandle(process_handle)


def process_looks_like_python(pid: int) -> bool:
    image_path = get_process_image_path(pid)
    if not image_path:
        return False
    normalized = image_path.casefold()
    return normalized.endswith("python.exe") or normalized.endswith("py.exe") or "python" in normalized


def parse_lock_payload(raw_value: str) -> tuple[int, str]:
    stripped = raw_value.strip()
    if not stripped:
        return 0, ""
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            return int(stripped), ""
        except ValueError:
            return 0, ""
    if not isinstance(payload, dict):
        return 0, ""
    pid = payload.get("pid")
    image_path = payload.get("image_path")
    return (pid if isinstance(pid, int) else 0), str(image_path or "").strip()


def build_lock_payload() -> str:
    return json.dumps(
        {
            "pid": os.getpid(),
            "image_path": get_process_image_path(os.getpid()),
        },
        ensure_ascii=False,
    )


def running_process_matches_lock(pid: int, image_path: str) -> bool:
    if not pid_is_running(pid):
        return False
    running_image_path = get_process_image_path(pid)
    if image_path:
        return bool(running_image_path) and running_image_path.casefold() == image_path.casefold()
    return process_looks_like_python(pid)


def release_bot_lock(lock_file_path: Path) -> None:
    global _LOCK_FILE_HANDLE
    if _LOCK_FILE_HANDLE is None:
        return
    try:
        _LOCK_FILE_HANDLE.close()
    finally:
        _LOCK_FILE_HANDLE = None
        try:
            lock_file_path.unlink()
        except FileNotFoundError:
            return


def acquire_bot_lock(lock_file_path: Path) -> None:
    global _LOCK_FILE_HANDLE
    ensure_runtime_directories()
    if _LOCK_FILE_HANDLE is not None:
        return
    if lock_file_path.exists():
        existing_pid, existing_image_path = parse_lock_payload(lock_file_path.read_text(encoding="utf-8"))
        if running_process_matches_lock(existing_pid, existing_image_path):
            raise RuntimeError(f"Telegram bot is already running with pid={existing_pid}.")
        lock_file_path.unlink(missing_ok=True)
    try:
        handle = lock_file_path.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError("Telegram bot is already running.")
    handle.write(build_lock_payload())
    handle.flush()
    _LOCK_FILE_HANDLE = handle
    atexit.register(lambda: release_bot_lock(lock_file_path))
