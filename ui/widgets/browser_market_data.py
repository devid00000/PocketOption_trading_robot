"""Persistent Playwright market-data capture for chart diagnostics."""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import traceback
from typing import Any

from PySide6.QtCore import QThread, Signal

from config.runtime import is_valid_ssid
from ui.widgets.connection_dialog import _auth_payload


def _as_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _parse_frame(value: str | bytes) -> Any:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    value = value.strip()
    if value.startswith("42"):
        try:
            return json.loads(value[2:])
        except (TypeError, ValueError):
            return None
    for marker in ("[", "{"):
        position = value.find(marker)
        if position >= 0:
            try:
                return json.JSONDecoder().raw_decode(value[position:])[0]
            except (TypeError, ValueError):
                continue
    return None


def _extract_quotes(payload: Any) -> list[dict]:
    """Extract quote-like records from an arbitrary Socket.IO payload."""
    quotes: list[dict] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            symbol = node.get("symbol") or node.get("asset") or node.get("active")
            timestamp = node.get("timestamp") or node.get("time") or node.get("date")
            price = node.get("price") or node.get("rate") or node.get("value")
            if symbol and timestamp is not None:
                parsed_price = price
                if parsed_price is None:
                    parsed_price = node.get("close")
                parsed_price = _as_number(parsed_price)
                try:
                    parsed_timestamp = int(float(timestamp))
                except (TypeError, ValueError):
                    parsed_timestamp = 0
                if parsed_price and parsed_timestamp > 0:
                    quotes.append({
                        "symbol": str(symbol),
                        "timestamp": parsed_timestamp,
                        "price": parsed_price,
                    })
            for child in node.values():
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(payload)
    return quotes


class BrowserMarketDataThread(QThread):
    """Keep a visible browser alive and emit parsed quote candidates."""

    authenticated = Signal(str)
    tick = Signal(dict)
    status = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, profile_dir: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.profile_dir = profile_dir
        self._stop_event = threading.Event()
        self._seen_auth: set[str] = set()
        self._frame_count = 0
        self._quote_count = 0

    def run(self) -> None:
        try:
            asyncio.run(self._run_browser())
        except Exception as exc:
            details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            self.failed.emit(details.strip())

    async def _run_browser(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright не установлен") from exc

        async with async_playwright() as playwright:
            try:
                context = await playwright.chromium.launch_persistent_context(
                    self.profile_dir,
                    headless=False,
                )
            except Exception as exc:
                raise RuntimeError(
                    "Не удалось запустить Chromium. Выполните: "
                    "./.venv/bin/python -m playwright install chromium"
                ) from exc

            page = context.pages[0] if context.pages else await context.new_page()

            def process_frame(frame: str | bytes) -> None:
                self._frame_count += 1
                auth = _auth_payload(
                    frame.decode("utf-8", errors="ignore") if isinstance(frame, bytes) else frame
                )
                if auth and auth not in self._seen_auth:
                    self._seen_auth.add(auth)
                    self.authenticated.emit(auth)

                payload = _parse_frame(frame)
                for quote in _extract_quotes(payload):
                    self._quote_count += 1
                    self.tick.emit(quote)

            def on_websocket(websocket) -> None:
                self.status.emit(f"Браузерный WebSocket: {websocket.url}")
                websocket.on("framesent", process_frame)
                websocket.on("framereceived", process_frame)

            page.on("websocket", on_websocket)
            self.status.emit("Открываю persistent browser. Войдите в Pocket Option...")
            try:
                await page.goto(self.url, wait_until="commit", timeout=30_000)
            except Exception as exc:
                self.status.emit(
                    f"Навигация не завершилась ({type(exc).__name__}), "
                    "браузер оставлен открытым"
                )

            self.status.emit("Браузер открыт. Ожидаю frames и котировки...")
            while not self._stop_event.is_set():
                await asyncio.sleep(0.5)

            self.status.emit(
                f"Браузер остановлен: frames={self._frame_count}, "
                f"quote candidates={self._quote_count}"
            )
            await context.close()

    def stop(self) -> None:
        self._stop_event.set()


__all__ = ["BrowserMarketDataThread"]
