#!/usr/bin/env python3
"""
График котировок в реальном времени с агрегацией тиков в свечи.
Использует subscribe_symbol_timed() для получения данных.
"""

import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import pyqtgraph as pg
    from pyqtgraph import PlotWidget, DateAxisItem
    from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QFont
except ImportError:
    print("PyQtGraph или PySide6 не установлены!")
    print("Установка: pip install pyqtgraph PySide6")
    sys.exit(1)

from core.robot_engine import RobotEngine
from config.runtime import load_runtime_config

DEMO_SSID = load_runtime_config().demo_ssid


class CandleAggregator:
    """Агрегатор тиков в свечи с фильтрацией дубликатов."""
    
    def __init__(self, period: int = 15):
        self.period = period
        self.current_candle = None
        self.seen_timestamps = set()
        self.max_timestamps = 5000
        
    def add_tick(self, tick_data: dict) -> dict:
        timestamp = tick_data['timestamp']
        price = float(tick_data.get('close', 0))
        
        ts_key = (timestamp, price)
        if ts_key in self.seen_timestamps:
            return None
        
        self.seen_timestamps.add(ts_key)
        if len(self.seen_timestamps) > self.max_timestamps:
            to_remove = list(self.seen_timestamps)[:500]
            for ts in to_remove:
                self.seen_timestamps.discard(ts)
        
        candle_start = (timestamp // self.period) * self.period
        
        if self.current_candle is None or self.current_candle['start'] != candle_start:
            completed = self.current_candle
            
            self.current_candle = {
                'start': candle_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'timestamp': candle_start + self.period,
                'volume': 1
            }
            
            return completed
        else:
            self.current_candle['high'] = max(self.current_candle['high'], price)
            self.current_candle['low'] = min(self.current_candle['low'], price)
            self.current_candle['close'] = price
            self.current_candle['volume'] += 1
            
            return None


class RealtimeChart(QMainWindow):
    """Окно с графиком японских свечей в реальном времени."""

    def __init__(self, ssid: str, symbol: str = "EURUSD_otc", period: int = 15):
        super().__init__()

        self.ssid = ssid
        self.symbol = symbol
        self.candle_period = period

        self.engine: RobotEngine = None
        self.aggregator = CandleAggregator(period=self.candle_period)

        self.candles = []
        self.tick_count = 0
        self.last_price = 0.0

        self._init_ui()
        self._init_timer()

    def _init_ui(self):
        self.setWindowTitle(f"{self.symbol} - Chart ({self.candle_period}s)")
        self.setMinimumSize(1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        header_layout = QHBoxLayout()
        
        self.lbl_title = QLabel(f"{self.symbol} ({self.candle_period}s)")
        self.lbl_title.setFont(QFont("Arial", 18, QFont.Bold))
        header_layout.addWidget(self.lbl_title)
        
        header_layout.addStretch()
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setFont(QFont("Arial", 12))
        self.btn_connect.clicked.connect(self._toggle_connection)
        header_layout.addWidget(self.btn_connect)
        
        layout.addLayout(header_layout)

        self.plot = PlotWidget()
        self.plot.setBackground('#1a1a2e')
        self.plot.setTitle(f"{self.symbol} - Real-time", color='#00d9ff', size='14pt')
        self.plot.setLabel('left', 'Price', color='#eee')
        self.plot.setLabel('bottom', 'Time', color='#eee')
        self.plot.showGrid(x=True, y=True, alpha=0.2)

        date_axis = DateAxisItem(orientation='bottom')
        self.plot.setAxisItems({'bottom': date_axis})

        layout.addWidget(self.plot)

        stats_layout = QHBoxLayout()
        
        self.lbl_price = QLabel("Price: $0.00000")
        self.lbl_price.setFont(QFont("Arial", 16, QFont.Bold))
        stats_layout.addWidget(self.lbl_price)
        
        stats_layout.addSpacing(20)
        
        self.lbl_change = QLabel("Change: 0.00000")
        self.lbl_change.setFont(QFont("Arial", 14))
        stats_layout.addWidget(self.lbl_change)
        
        stats_layout.addSpacing(20)
        
        self.lbl_status = QLabel("Disconnected")
        self.lbl_status.setFont(QFont("Arial", 12))
        stats_layout.addWidget(self.lbl_status)
        
        stats_layout.addSpacing(20)
        
        self.lbl_stats = QLabel("Ticks: 0 | Candles: 0")
        self.lbl_stats.setFont(QFont("Arial", 11))
        stats_layout.addWidget(self.lbl_stats)
        
        layout.addLayout(stats_layout)

        self.lbl_current_candle = QLabel("Current: O:0.00000 H:0.00000 L:0.00000 C:0.00000")
        self.lbl_current_candle.setFont(QFont("Arial", 11))
        layout.addWidget(self.lbl_current_candle)

    def _init_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_chart)
        self.update_timer.start(1000)

    def _toggle_connection(self):
        if self.engine:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        print(f"Connecting to {self.symbol}...")

        if not DEMO_SSID:
            print("Demo SSID не задан. Заполните POCKET_OPTION_DEMO_SSID в .env.")
            return
        self.engine = RobotEngine(ssid=DEMO_SSID)
        self.aggregator = CandleAggregator(period=self.candle_period)

        self.engine.on_candle(self._on_candle)
        self.engine.on_connected(self._on_connected)
        self.engine.on_disconnected(self._on_disconnected)

        import threading
        
        def connect_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self.engine.connect())
                loop.run_until_complete(
                    self.engine.subscribe(self.symbol, 5)
                )
                print(f"Subscribed to {self.symbol}")
                loop.run_forever()
            except Exception as e:
                print(f"Connection error: {e}")
            finally:
                loop.close()

        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
        
        self.btn_connect.setText("Disconnect")

    def _disconnect(self):
        if self.engine:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.engine.disconnect())
            loop.close()
            self.engine = None
        
        self.btn_connect.setText("Connect")
        self.lbl_status.setText("Disconnected")

    def _on_connected(self):
        self.lbl_status.setText("Connected")
        print("Connected")

    def _on_disconnected(self):
        self.lbl_status.setText("Disconnected")
        print("Disconnected")

    def _on_candle(self, symbol: str, period: int, candles: list):
        if symbol != self.symbol:
            return

        for candle_data in candles:
            self.tick_count += 1
            
            candle_dict = candle_data.to_dict() if hasattr(candle_data, 'to_dict') else candle_data
            
            completed_candle = self.aggregator.add_tick(candle_dict)
            
            if completed_candle:
                self.candles.append((
                    completed_candle['timestamp'],
                    completed_candle['open'],
                    completed_candle['high'],
                    completed_candle['low'],
                    completed_candle['close']
                ))
                
                if len(self.candles) > 100:
                    self.candles = self.candles[-100:]
                
                print(f"Candle #{len(self.candles)}: O:{completed_candle['open']:.5f} "
                      f"H:{completed_candle['high']:.5f} L:{completed_candle['low']:.5f} "
                      f"C:{completed_candle['close']:.5f}")
            
            current_price = float(candle_dict.get('close', 0))
            self.last_price = current_price
            
            self._update_price_label(current_price)
            
            if self.aggregator.current_candle:
                cc = self.aggregator.current_candle
                self.lbl_current_candle.setText(
                    f"Current: O:{cc['open']:.5f} H:{cc['high']:.5f} L:{cc['low']:.5f} C:{cc['close']:.5f} V:{cc['volume']}"
                )
            
            self.lbl_stats.setText(f"Ticks: {self.tick_count} | Candles: {len(self.candles)}")

    def _update_price_label(self, price: float):
        if self.last_price > 0:
            change = price - self.last_price
            if change > 0:
                self.lbl_price.setText(f"Price: ${price:.5f} UP")
                self.lbl_change.setText(f"Change: {change:+.5f}")
            elif change < 0:
                self.lbl_price.setText(f"Price: ${price:.5f} DOWN")
                self.lbl_change.setText(f"Change: {change:+.5f}")
            else:
                self.lbl_price.setText(f"Price: ${price:.5f} =")
                self.lbl_change.setText(f"Change: {change:+.5f}")

    def _update_chart(self):
        if not self.candles:
            return

        self.plot.clear()
        
        timestamps = [c[0] for c in self.candles]
        highs = [c[2] for c in self.candles]
        lows = [c[3] for c in self.candles]
        opens = [c[1] for c in self.candles]
        closes = [c[4] for c in self.candles]
        
        bull_color = pg.mkColor('#00ff88')
        bear_color = pg.mkColor('#ff4757')
        
        for i, (ts, o, h, l, c) in enumerate(self.candles):
            color = bull_color if c >= o else bear_color
            bar_width = self.candle_period * 0.4
            
            self.plot.plot(
                x=[ts, ts],
                y=[l, h],
                pen=pg.mkPen(color, width=1)
            )
            
            if abs(c - o) > 0.00001:
                half_w = bar_width / 2
                
                self.plot.plot(
                    x=[ts - half_w, ts - half_w],
                    y=[min(o, c), max(o, c)],
                    pen=pg.mkPen(color, width=2)
                )
                self.plot.plot(
                    x=[ts + half_w, ts + half_w],
                    y=[min(o, c), max(o, c)],
                    pen=pg.mkPen(color, width=2)
                )
                self.plot.plot(
                    x=[ts - half_w, ts + half_w],
                    y=[max(o, c), max(o, c)],
                    pen=pg.mkPen(color, width=2)
                )
                self.plot.plot(
                    x=[ts - half_w, ts + half_w],
                    y=[min(o, c), min(o, c)],
                    pen=pg.mkPen(color, width=2)
                )
            else:
                half_w = bar_width / 2
                self.plot.plot(
                    x=[ts - half_w, ts + half_w],
                    y=[o, o],
                    pen=pg.mkPen(color, width=3)
                )
        
        spread = max(highs) - min(lows) if highs and lows else 0
        change = closes[-1] - closes[0] if closes else 0
        direction = "UP" if change > 0 else "DOWN" if change < 0 else "="
        
        self.plot.setTitle(
            f"{self.symbol} ({self.candle_period}s) - {len(self.candles)} candles | "
            f"Spread: {spread:.5f} ({change:+.5f}) {direction} | Ticks: {self.tick_count}",
            color='#00d9ff', size='14pt'
        )
        
        if len(self.candles) > 0:
            padding = (max(highs) - min(lows)) * 0.2 if max(highs) != min(lows) else 0.0005
            self.plot.setYRange(min(lows) - padding, max(highs) + padding)

    def closeEvent(self, event):
        self._disconnect()
        event.accept()


def main():
    print("=" * 80)
    print("Real-time chart (15-second candles)")
    print("=" * 80)

    app = QApplication(sys.argv)

    window = RealtimeChart(ssid=DEMO_SSID or "", symbol="EURUSD_otc", period=15)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
