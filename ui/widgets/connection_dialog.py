"""Connection settings dialog and Playwright-based SSID capture."""

from __future__ import annotations

import asyncio
import json
import re
import traceback
from urllib.parse import unquote

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)

from config.runtime import (
    RuntimeConfig,
    config_with_account,
    is_valid_ssid,
    load_runtime_config,
    save_runtime_config,
    ssid_uid,
)


def _auth_payload(value: str) -> str | None:
    """Extract a valid Socket.IO auth message from a WebSocket frame."""
    if not isinstance(value, str):
        return None
    match = re.search(r"42\s*", value)
    if not match:
        return None

    try:
        decoder = json.JSONDecoder()
        payload, _ = decoder.raw_decode(value[match.end():])
    except (TypeError, ValueError):
        return None

    if not isinstance(payload, list) or len(payload) < 2 or payload[0] != "auth":
        return None
    candidate = "42" + json.dumps(payload, separators=(",", ":"))
    return candidate if is_valid_ssid(candidate) else None


def _candidate_from_value(value: str | None) -> str | None:
    """Find a complete SSID in a frame, request body, cookie, or storage value."""
    if not value:
        return None
    value = unquote(str(value)).strip()
    direct = _auth_payload(value)
    if direct:
        return direct
    if value.startswith("42[") and is_valid_ssid(value):
        return value
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    if isinstance(decoded, dict):
        if "session" in decoded and "uid" in decoded:
            payload = ["auth", decoded]
            candidate = "42" + json.dumps(payload, separators=(",", ":"))
            return candidate if is_valid_ssid(candidate) else None
        for nested in decoded.values():
            candidate = _candidate_from_value(nested if isinstance(nested, str) else json.dumps(nested))
            if candidate:
                return candidate
    return None


class SSIDCaptureThread(QThread):
    """Open the platform in a visible browser and capture its auth frame."""

    captured = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._cancelled = False

    def run(self) -> None:
        try:
            asyncio.run(self._capture())
        except Exception as exc:
            details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            self.failed.emit(details.strip())

    async def _capture(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright не установлен. Установите зависимости проекта.") from exc

        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch(headless=False)
            except Exception as exc:
                raise RuntimeError(
                    "Не удалось запустить Chromium Playwright. Выполните: "
                    "playwright install chromium"
                ) from exc

            context = await browser.new_context()
            page = await context.new_page()
            found = asyncio.Event()
            captured: list[str] = []
            websocket_count = 0
            frame_count = 0

            def accept(value: str | bytes | None, source: str) -> None:
                try:
                    if captured:
                        return
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", errors="ignore")
                    ssid = _candidate_from_value(value)
                    if ssid:
                        captured.append(ssid)
                        self.status.emit(f"SSID перехвачен ({source}), проверяю UID...")
                        found.set()
                except Exception as exc:
                    self.status.emit(f"Ошибка разбора {source}: {type(exc).__name__}")

            def on_websocket(websocket) -> None:
                nonlocal websocket_count
                websocket_count += 1
                self.status.emit(f"WebSocket обнаружен: {websocket_count}. Ожидаю auth...")

                def on_frame(frame: str | bytes) -> None:
                    nonlocal frame_count
                    frame_count += 1
                    accept(frame, "WebSocket")

                websocket.on("framereceived", on_frame)
                websocket.on("framesent", on_frame)

            page.on("websocket", on_websocket)

            def on_request(request) -> None:
                # Some builds send the auth payload through an HTTP bootstrap
                # request instead of exposing it as a Playwright WS frame.
                try:
                    accept(request.post_data, "сетевой запрос")
                except Exception as exc:
                    self.status.emit(f"Ошибка чтения сетевого запроса: {type(exc).__name__}")

            page.on("request", on_request)
            self.status.emit("Открываю страницу. Войдите в аккаунт в браузере...")
            try:
                # The platform can keep loading analytics/socket resources forever.
                # `commit` is enough: WebSocket frames are observed independently.
                await page.goto(self.url, wait_until="commit", timeout=30_000)
            except Exception as exc:
                # A navigation timeout does not mean that the page is unusable.
                # Keep the context alive so the user can finish login and the
                # WebSocket auth frame can still be captured.
                self.status.emit(
                    f"Страница загружена не полностью ({type(exc).__name__}). "
                    "Ожидаю auth-сообщение после входа..."
                )

            async def inspect_browser_state() -> None:
                while not found.is_set():
                    try:
                        for cookie in await context.cookies():
                            if cookie.get("name", "").lower() in {"ssid", "session", "po_session"}:
                                accept(cookie.get("value"), f"cookie {cookie['name']}")
                    except Exception as exc:
                        self.status.emit(f"Ошибка чтения cookies: {type(exc).__name__}")
                    try:
                        storage = await page.evaluate("""() => {
                            const result = {};
                            for (let i = 0; i < localStorage.length; i++) {
                                const key = localStorage.key(i);
                                result[key] = localStorage.getItem(key);
                            }
                            return result;
                        }""")
                        for key, value in (storage or {}).items():
                            accept(value, f"localStorage {key}")
                    except Exception:
                        pass
                    await asyncio.sleep(1)

            inspector = asyncio.create_task(inspect_browser_state())
            capture_error: Exception | None = None
            try:
                await asyncio.wait_for(found.wait(), timeout=300)
            except asyncio.TimeoutError as exc:
                capture_error = RuntimeError(
                    "Auth SSID не перехвачен за 5 минут. Обнаружено "
                    f"WebSocket: {websocket_count}, frames: {frame_count}. "
                    "Убедитесь, что вход выполнен и открыт именно торговый терминал. "
                    "Если платформа не передаёт UID в браузерный payload, вставьте полный SSID вручную."
                )
            finally:
                inspector.cancel()
                await asyncio.gather(inspector, return_exceptions=True)
                # Cleanup errors must not hide the actual capture result.
                try:
                    await context.close()
                except Exception as exc:
                    self.status.emit(f"Предупреждение закрытия контекста: {type(exc).__name__}")
                try:
                    await browser.close()
                except Exception as exc:
                    self.status.emit(f"Предупреждение закрытия браузера: {type(exc).__name__}")

            if capture_error:
                raise capture_error

            self.captured.emit(captured[0])

    def cancel(self) -> None:
        self._cancelled = True


class ConnectionDialog(QDialog):
    """Edit account credentials and capture a complete SSID automatically."""

    def __init__(self, parent=None, config: RuntimeConfig | None = None):
        super().__init__(parent)
        self.config = config or load_runtime_config()
        self.selected_is_demo = True
        self.capture_thread: SSIDCaptureThread | None = None
        self.setWindowTitle("Параметры подключения")
        self.setMinimumWidth(620)
        self._init_ui()
        self._load_config()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.account_combo = QComboBox()
        self.account_combo.addItem("Демо-счёт", True)
        self.account_combo.addItem("Реальный счёт", False)
        self.account_combo.currentIndexChanged.connect(self._update_fields)
        form.addRow("Счёт:", self.account_combo)

        self.url_edit = QLineEdit()
        form.addRow("URL платформы:", self.url_edit)

        self.ssid_edit = QLineEdit()
        self.ssid_edit.setEchoMode(QLineEdit.Password)
        self.ssid_edit.setPlaceholderText('42["auth",{"session":"...","uid":123,...}]')
        form.addRow("SSID:", self.ssid_edit)

        self.uid_edit = QLineEdit()
        self.uid_edit.setReadOnly(True)
        form.addRow("UID:", self.uid_edit)
        layout.addLayout(form)

        self.status_label = QLabel("SSID не задан")
        layout.addWidget(self.status_label)

        self.capture_button = QPushButton("Открыть браузер и перехватить SSID")
        self.capture_button.clicked.connect(self._capture_ssid)
        layout.addWidget(self.capture_button)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_config(self) -> None:
        self.url_edit.setText(self.config.platform_url)
        self._update_fields()

    def _update_fields(self) -> None:
        is_demo = bool(self.account_combo.currentData())
        self.selected_is_demo = is_demo
        ssid = self.config.demo_ssid if is_demo else self.config.real_ssid
        uid = self.config.demo_uid if is_demo else self.config.real_uid
        self.ssid_edit.setText(ssid or "")
        self.uid_edit.setText(str(uid or ssid_uid(ssid) or ""))
        self.status_label.setText("SSID задан и валиден" if is_valid_ssid(ssid) else "SSID не задан или имеет неверный формат")

    def _capture_ssid(self) -> None:
        if self.capture_thread and self.capture_thread.isRunning():
            return
        self.capture_button.setEnabled(False)
        self.status_label.setText("Запуск браузера...")
        self.capture_thread = SSIDCaptureThread(self.url_edit.text().strip(), self)
        self.capture_thread.status.connect(self.status_label.setText)
        self.capture_thread.captured.connect(self._on_captured)
        self.capture_thread.failed.connect(self._on_capture_failed)
        self.capture_thread.finished.connect(lambda: self.capture_button.setEnabled(True))
        self.capture_thread.start()

    def _on_captured(self, ssid: str) -> None:
        self.ssid_edit.setText(ssid)
        self.uid_edit.setText(str(ssid_uid(ssid) or ""))
        self.status_label.setText("SSID перехвачен и валиден")

    def _on_capture_failed(self, message: str) -> None:
        self.status_label.setText("Перехват не выполнен")
        QMessageBox.critical(self, "Ошибка перехвата", message)

    def _save(self) -> None:
        ssid = self.ssid_edit.text().strip()
        if not is_valid_ssid(ssid):
            QMessageBox.warning(self, "Неверный SSID", 'Введите полный SSID формата 42["auth",{...}] с положительным UID.')
            return
        try:
            is_demo = bool(self.account_combo.currentData())
            self.selected_is_demo = is_demo
            updated = config_with_account(self.config, is_demo=is_demo, ssid=ssid)
            updated = RuntimeConfig(
                platform_url=self.url_edit.text().strip() or self.config.platform_url,
                demo_ssid=updated.demo_ssid,
                demo_uid=ssid_uid(updated.demo_ssid),
                real_ssid=updated.real_ssid,
                real_uid=ssid_uid(updated.real_ssid),
                default_symbol=self.config.default_symbol,
                default_period=self.config.default_period,
                default_amount=self.config.default_amount,
                default_duration=self.config.default_duration,
            )
            save_runtime_config(updated)
            self.config = updated
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def closeEvent(self, event) -> None:
        if self.capture_thread and self.capture_thread.isRunning():
            self.capture_thread.requestInterruption()
            self.capture_thread.wait(1000)
        super().closeEvent(event)


__all__ = ["ConnectionDialog", "SSIDCaptureThread"]
