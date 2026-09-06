"""Standalone realtime candlestick window for API debugging."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QComboBox, QGraphicsRectItem, QHBoxLayout, QLabel, QMainWindow,
    QVBoxLayout, QWidget,
)

from config.runtime import load_runtime_config
from ui.app import RobotWorker


TIMEFRAMES = [("S5", 5), ("S10", 10), ("S15", 15), ("S30", 30),
              ("M1", 60), ("M5", 300), ("M15", 900), ("H1", 3600)]


def price_decimals(symbol: str) -> int:
    """Return the usual forex display precision for an asset symbol."""
    return 3 if "JPY" in str(symbol).upper() else 5


class PriceAxis(pg.AxisItem):
    """Price axis with symbol-dependent decimal formatting."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.decimals = 5

    def set_decimals(self, decimals: int) -> None:
        self.decimals = decimals
        self.picture = None
        self.update()

    def tickStrings(self, values, scale, spacing):
        return [f"{value:.{self.decimals}f}" for value in values]


class CandlestickItem(pg.GraphicsObject):
    """Candlestick renderer using live floating-point Qt geometry."""

    def __init__(self):
        super().__init__()
        self._candles: list[dict] = []
        self._period = 5
        self._bounds = (0.0, 0.0, 0.0, 0.0)

    def set_candles(self, candles: list[dict], period: int) -> None:
        half_width = max(float(period) * 0.32, 0.5)
        normalized = []
        for index, candle in enumerate(candles):
            open_price = float(candle.get("open", 0))
            high = float(candle.get("high", open_price))
            low = float(candle.get("low", open_price))
            close = float(candle.get("close", open_price))
            if min(open_price, high, low, close) <= 0:
                continue
            normalized.append({
                "timestamp": float(candle.get("timestamp", candle.get("time", 0))),
                "x": float(index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
            })

        if normalized:
            low = min(candle["low"] for candle in normalized)
            high = max(candle["high"] for candle in normalized)
            padding = max((high - low) * 0.05, 1e-8)
            bounds = (
                low - padding,
                high + padding,
                -0.5,
                max(float(len(normalized)) - 0.5, 0.5),
            )
        else:
            bounds = (0.0, 0.0, 0.0, 0.0)

        if self._bounds != bounds:
            self.prepareGeometryChange()
        self._candles = normalized
        self._period = period
        self._bounds = bounds
        self.update()

    def paint(self, painter, option, widget=None):
        half_width = max(float(self._period) * 0.32, 0.5)
        for candle in self._candles:
            x = candle["x"]
            open_price = candle["open"]
            high = candle["high"]
            low = candle["low"]
            close = candle["close"]
            is_closed = bool(candle.get("is_closed", True))
            color = QColor("#2ecc71" if close >= open_price else "#e74c3c")
            painter.setPen(QPen(color, 1))
            painter.drawLine(pg.QtCore.QLineF(x, low, x, high))
            painter.setBrush(QBrush(color))
            painter.drawRect(pg.QtCore.QRectF(
                x - 0.35,
                min(open_price, close),
                0.7,
                max(abs(close - open_price), 1e-8),
            ))

    def boundingRect(self):
        low, high, start, end = self._bounds
        return pg.QtCore.QRectF(start, low, max(end - start, 1.0), max(high - low, 1e-8))


class DebugChartWindow(QMainWindow):
    """Debug chart using one worker-owned asyncio client."""

    def __init__(self, ssid: str, parent=None, auto_start: bool = True):
        super().__init__(parent)
        self.ssid = ssid
        self.worker: RobotWorker | None = None
        self.current_symbol = load_runtime_config().default_symbol
        # Five seconds makes the first realtime candle visible quickly.
        self.current_period = 5
        self.decimals = price_decimals(self.current_symbol)
        self.candles: list[dict] = []
        self.wick_item = None
        self.body_items = []
        self._init_ui()
        if auto_start:
            self.start()

    def _init_ui(self) -> None:
        self.setWindowTitle("DebugChartWindow - Pocket Option")
        self.resize(1200, 750)
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        controls = QHBoxLayout()
        self.asset_combo = QComboBox()
        self.asset_combo.addItem(self.current_symbol)
        self.asset_combo.currentTextChanged.connect(self._change_subscription)
        controls.addWidget(QLabel("Актив:"))
        controls.addWidget(self.asset_combo, 2)

        self.period_combo = QComboBox()
        for title, seconds in TIMEFRAMES:
            self.period_combo.addItem(title, seconds)
        index = self.period_combo.findData(self.current_period)
        self.period_combo.setCurrentIndex(index if index >= 0 else 0)
        self.period_combo.currentIndexChanged.connect(self._change_subscription)
        controls.addWidget(QLabel("Таймфрейм:"))
        controls.addWidget(self.period_combo)

        self.status_label = QLabel("Подключение...")
        controls.addWidget(self.status_label, 2)
        layout.addLayout(controls)

        self.price_axis = PriceAxis(orientation="left")
        self.price_axis.set_decimals(self.decimals)
        self.plot = pg.PlotWidget(
            background="#101820",
            axisItems={"left": self.price_axis},
        )
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel("left", "Цена")
        self.plot.setLabel("bottom", "Время")
        layout.addWidget(self.plot, 1)

        self.info_label = QLabel("Свечей: 0 | Последнее обновление: -")
        layout.addWidget(self.info_label)

        self.price_label = QLabel("Последняя цена: -")
        layout.addWidget(self.price_label)

    def _start_worker(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.worker = RobotWorker(self.ssid)
        self.worker.connected_signal.connect(self._on_connected)
        self.worker.disconnected_signal.connect(lambda: self.status_label.setText("Отключено"))
        self.worker.candle_signal.connect(self._on_candles)
        self.worker.assets_signal.connect(self._on_assets)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def start(self) -> None:
        """Start the API worker after the window has been constructed."""
        self._start_worker()

    def _on_connected(self, data: dict) -> None:
        self.status_label.setText(f"Подключено. Загружаю валютные активы и подписываюсь на {self.current_symbol} S5...")
        self._run(self.worker.load_assets_and_subscribe(self.current_symbol, self.current_period))

    def _on_assets(self, assets: list) -> None:
        symbols = []
        for asset in assets:
            if isinstance(asset, dict):
                symbol = asset.get("symbol")
                is_currency = asset.get("asset_type") == "currency"
            else:
                symbol = asset
                is_currency = self._is_currency(symbol)
            if symbol and is_currency and symbol not in symbols:
                symbols.append(symbol)
        if not symbols:
            return
        current = self.current_symbol if self.current_symbol in symbols else symbols[0]
        self.asset_combo.blockSignals(True)
        self.asset_combo.clear()
        self.asset_combo.addItems(symbols)
        self.asset_combo.setCurrentText(current)
        self.asset_combo.blockSignals(False)
        self.current_symbol = current
        self._set_price_precision(current)

    def _set_price_precision(self, symbol: str) -> None:
        self.decimals = price_decimals(symbol)
        self.price_axis.set_decimals(self.decimals)

    @staticmethod
    def _is_currency(symbol: str) -> bool:
        """Keep forex symbols only, including OTC currency pairs."""
        return bool(re.fullmatch(r"[A-Z]{6}(?:_otc)?", str(symbol)))

    def _on_candles(self, symbol: str, period: int, candles: list) -> None:
        if symbol != self.current_symbol or period != self.current_period:
            return
        self.candles = candles[-50:]
        self._render_candles()
        low = min(float(c["low"]) for c in self.candles)
        high = max(float(c["high"]) for c in self.candles)
        start = -0.5
        end = max(len(self.candles) - 0.5, 0.5)
        self.plot.setRange(
            xRange=(start, end),
            yRange=(low, high),
            padding=0.05,
        )
        self.info_label.setText(
            f"Свечей: {len(self.candles)} | Последнее обновление: "
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        )
        self.price_label.setText(
            f"Последняя цена: {float(self.candles[-1]['close']):.{self.decimals}f}"
        )

    def _render_candles(self) -> None:
        """Render bodies as scene rectangles and wicks as a line item."""
        if self.wick_item is not None:
            self.plot.removeItem(self.wick_item)
        for item in self.body_items:
            self.plot.removeItem(item)
        self.body_items = []

        wick_x, wick_y = [], []
        if not self.candles:
            self.wick_item = None
            return
        for index, candle in enumerate(self.candles):
            open_price = float(candle["open"])
            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])
            wick_x.extend([index, index, float("nan")])
            wick_y.extend([low, high, float("nan")])

            is_closed = bool(candle.get("is_closed", True))
            color = QColor("#2ecc71" if close >= open_price else "#e74c3c")
            body_height = abs(close - open_price)
            if body_height == 0:
                # A doji is represented by its wick; do not invent OHLC size.
                continue
            body = QGraphicsRectItem(
                index - 0.35,
                (open_price + close) / 2 - body_height / 2,
                0.7,
                body_height,
            )
            pen = QPen(color, 1)
            pen.setCosmetic(True)
            body.setPen(QPen(Qt.NoPen) if is_closed else pen)
            body.setBrush(QBrush(color if is_closed else QColor(0, 0, 0, 0)))
            self.plot.addItem(body)
            self.body_items.append(body)

        self.wick_item = self.plot.plot(
            wick_x,
            wick_y,
            connect="finite",
            pen=pg.mkPen("#d7dee7", width=1),
        )

    def _change_subscription(self) -> None:
        self.current_symbol = self.asset_combo.currentText()
        self._set_price_precision(self.current_symbol)
        self.current_period = int(self.period_combo.currentData())
        if not self.worker or not self.worker.engine:
            return
        self.candles = []
        self._render_candles()
        self._replace_subscription()

    def _subscribe(self) -> None:
        if self.worker and self.worker.engine:
            self._run(self.worker.subscribe(self.current_symbol, self.current_period))

    def _replace_subscription(self) -> None:
        if self.worker and self.worker.engine:
            self._run(self.worker.replace_subscription(self.current_symbol, self.current_period))

    def _run(self, coroutine) -> None:
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, self.worker._loop)
            future.add_done_callback(self._operation_finished)
        except Exception as exc:
            self._on_error(str(exc))

    def _operation_finished(self, future) -> None:
        try:
            future.result()
        except Exception as exc:
            self._on_error(f"{type(exc).__name__}: {exc}")

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f"Ошибка: {message}")

    def closeEvent(self, event) -> None:
        if self.worker:
            self.worker.stop()
            self.worker.wait(5000)
            self.worker = None
        event.accept()


__all__ = ["DebugChartWindow", "CandlestickItem", "TIMEFRAMES"]
