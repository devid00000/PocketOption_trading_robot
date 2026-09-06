"""Project-relative paths used by persistence layers."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROBOTS_DIR = PROJECT_ROOT / "robots"
STRATEGIES_DIR = PROJECT_ROOT / "strategies" / "configs"
STORAGE_DIR = PROJECT_ROOT / "storage"
LOGS_DIR = PROJECT_ROOT / "logs"
EXPORTS_DIR = PROJECT_ROOT / "exports"
TRADES_DB = STORAGE_DIR / "trades.db"


def ensure_project_dirs() -> None:
    for path in (ROBOTS_DIR, STRATEGIES_DIR, STORAGE_DIR, LOGS_DIR, EXPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


__all__ = [
    "PROJECT_ROOT", "ROBOTS_DIR", "STRATEGIES_DIR", "STORAGE_DIR",
    "LOGS_DIR", "EXPORTS_DIR", "TRADES_DB", "ensure_project_dirs",
]
