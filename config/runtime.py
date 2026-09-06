"""Runtime configuration loaded from the project .env file.

Secrets are intentionally kept out of Python modules and are never included in
the string representation of :class:`RuntimeConfig`.
"""

from __future__ import annotations

import os
import json
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:  # Keep the launcher usable before optional dependencies are installed.
    def dotenv_values(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        result = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip().strip("'\"")
        return result

    def load_dotenv(path: Path, override: bool = False) -> None:
        for key, value in dotenv_values(path).items():
            if override or key not in os.environ:
                os.environ[key] = value


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
SSID_PATTERN = re.compile(r'^42\["auth",\s*\{.*\}\]$', re.DOTALL)


@dataclass(frozen=True)
class RuntimeConfig:
    """Application configuration with canonical environment variable names."""

    platform_url: str = "https://po-fxo.com/"
    demo_ssid: str | None = None
    demo_uid: int | None = None
    real_ssid: str | None = None
    real_uid: int | None = None
    default_symbol: str = "EURUSD_otc"
    default_period: int = 60
    default_amount: float = 1.0
    default_duration: int = 60

    @property
    def demo_enabled(self) -> bool:
        return bool(self.demo_ssid)

    @property
    def real_enabled(self) -> bool:
        return bool(self.real_ssid)


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def is_valid_ssid(ssid: str | None) -> bool:
    """Return whether ``ssid`` is a valid Socket.IO auth payload."""
    if not ssid or not SSID_PATTERN.fullmatch(ssid.strip()):
        return False
    try:
        payload = json.loads(ssid.strip()[2:])
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, list) or len(payload) < 2 or payload[0] != "auth":
        return False
    auth = payload[1]
    if not isinstance(auth, dict) or not auth.get("session"):
        return False
    try:
        return int(auth.get("uid", 0)) > 0
    except (TypeError, ValueError):
        return False


def ssid_uid(ssid: str | None) -> int | None:
    """Extract the numeric UID from a validated SSID."""
    if not is_valid_ssid(ssid):
        return None
    payload = json.loads(ssid.strip()[2:])
    return int(payload[1]["uid"])


def ssid_is_demo(ssid: str | None) -> bool | None:
    """Extract the account mode declared by the SSID auth payload."""
    if not is_valid_ssid(ssid):
        return None
    payload = json.loads(ssid.strip()[2:])
    value = payload[1].get("isDemo")
    return bool(value) if value is not None else None


def load_runtime_config(env_path: Path = ENV_PATH) -> RuntimeConfig:
    """Load configuration, accepting old names only for persisted projects."""
    load_dotenv(env_path, override=False)
    values = dotenv_values(env_path) if env_path.exists() else {}

    def value(*names: str, default: str | None = None) -> str | None:
        for name in names:
            current = os.getenv(name)
            if current is None:
                current = values.get(name)
            if current is not None and str(current).strip():
                return str(current).strip()
        return default

    return RuntimeConfig(
        platform_url=value("PO_PLATFORM_URL", "PO_AUTH_URL", default="https://po-fxo.com/") or "https://po-fxo.com/",
        demo_ssid=_clean(value("POCKET_OPTION_DEMO_SSID", "POCKET_OPTION_SSID", "PO_SESSION_SSID")),
        demo_uid=int(value("POCKET_OPTION_DEMO_UID", "POCKET_OPTION_UID", default="0") or 0) or None,
        real_ssid=_clean(value("POCKET_OPTION_REAL_SSID")),
        real_uid=int(value("POCKET_OPTION_REAL_UID", default="0") or 0) or None,
        default_symbol=value("PO_TRADE_DEFAULT_SYMBOL", "DEFAULT_SYMBOL", default="EURUSD_otc") or "EURUSD_otc",
        default_period=int(value("PO_TRADE_DEFAULT_PERIOD", "DEFAULT_PERIOD", default="60") or 60),
        default_amount=float(value("PO_TRADE_DEFAULT_AMOUNT", "DEFAULT_AMOUNT", default="1.0") or 1.0),
        default_duration=int(value("PO_TRADE_DEFAULT_DURATION", "DEFAULT_DURATION", default="60") or 60),
    )


def save_runtime_config(config: RuntimeConfig, env_path: Path = ENV_PATH) -> None:
    """Atomically write canonical settings while preserving unrelated variables."""
    existing = dict(dotenv_values(env_path)) if env_path.exists() else {}
    existing.update(
        {
            "PO_PLATFORM_URL": config.platform_url,
            "POCKET_OPTION_DEMO_SSID": config.demo_ssid or "",
            "POCKET_OPTION_DEMO_UID": str(config.demo_uid or ssid_uid(config.demo_ssid) or ""),
            "POCKET_OPTION_REAL_SSID": config.real_ssid or "",
            "POCKET_OPTION_REAL_UID": str(config.real_uid or ssid_uid(config.real_ssid) or ""),
            "PO_TRADE_DEFAULT_SYMBOL": config.default_symbol,
            "PO_TRADE_DEFAULT_PERIOD": str(config.default_period),
            "PO_TRADE_DEFAULT_AMOUNT": str(config.default_amount),
            "PO_TRADE_DEFAULT_DURATION": str(config.default_duration),
        }
    )

    env_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f"{env_path.name}.", dir=env_path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("# Pocket Option Robot configuration\n")
            for key, value in existing.items():
                if value is not None:
                    stream.write(f"{key}={value}\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, env_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def config_with_account(config: RuntimeConfig, *, is_demo: bool, ssid: str) -> RuntimeConfig:
    """Return a copy with one account credential replaced after validation."""
    if not is_valid_ssid(ssid):
        raise ValueError('SSID должен иметь формат 42["auth",{...}] и содержать положительный UID')
    declared_mode = ssid_is_demo(ssid)
    if declared_mode is not None and declared_mode != is_demo:
        expected = "demo" if is_demo else "real"
        actual = "demo" if declared_mode else "real"
        raise ValueError(f"SSID предназначен для {actual}-счёта, выбран режим {expected}")
    return replace(config, demo_ssid=ssid if is_demo else config.demo_ssid,
                   real_ssid=ssid if not is_demo else config.real_ssid)


__all__ = [
    "ENV_PATH",
    "PROJECT_ROOT",
    "RuntimeConfig",
    "config_with_account",
    "is_valid_ssid",
    "ssid_uid",
    "ssid_is_demo",
    "load_runtime_config",
    "save_runtime_config",
]
