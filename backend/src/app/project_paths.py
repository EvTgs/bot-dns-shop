from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
BACKEND_SRC_DIR = APP_DIR.parent
BACKEND_DIR = BACKEND_SRC_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATABASE_DIR = PROJECT_ROOT / "database"
RUNTIME_DIR = DATABASE_DIR / "runtime"
ARTIFACTS_DIR = PROJECT_ROOT / "backend" / "test" / "artifacts"
SNAPSHOTS_DIR = PROJECT_ROOT / "backend" / "test" / "snapshots"
DOCS_DIR = PROJECT_ROOT / "docs-this-version"
LOGS_DIR = RUNTIME_DIR / "logs"
MEMORY_FILE = RUNTIME_DIR / "bot_memory.json"
COOKIES_FILE = RUNTIME_DIR / "cookies.json"
TELEGRAM_BOT_LOCK_FILE = RUNTIME_DIR / "telegram_bot.lock"


def ensure_runtime_directories() -> None:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def artifact_path(filename: str) -> Path:
    ensure_runtime_directories()
    return ARTIFACTS_DIR / filename


def runtime_path(filename: str) -> Path:
    ensure_runtime_directories()
    return RUNTIME_DIR / filename


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
