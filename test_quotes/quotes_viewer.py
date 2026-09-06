"""
Тестовый проект для получения котировок Pocket Option через BinaryOptionsToolsV2.
Отображение графика японских свечей с помощью PyQtGraph.
"""

import sys
import asyncio
from datetime import datetime
from pathlib import Path

# Добавляем корень проекта в path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pyqtgraph as pg
from pyqtgraph import PlotWidget, DateAxisItem
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QComboBox, QSpinBox, QHBoxLayout
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont

try:
    from BinaryOptionsToolsV2 import PocketOptionAsync
except ImportError:
    print("❌ BinaryOptionsToolsV2 не установлена!")
    print("Установка: pip install \"https://github.com/ChipaDevTeam/BinaryOptionsTools-v2/releases/download/v0.2.9/binaryoptionstoolsv2-0.2.9-cp39-abi3-manylinux_2_28_x86_64.whl\"")
    sys.exit(1)


# ==============================================================================
# КОНФИГУРАЦИЯ
# ==============================================================================

from config.runtime import load_runtime_config

DEMO_SSID = load_runtime_config().demo_ssid


# ==============================================================================
# ГЛАВНОЕ ОКНО
# ==============================================================================

class QuotesViewer(QMainWindow):
    """Окно для просмотра котировок в реальном времени."""

    def __init__(self, ssid: str):
        super().__init__()
        
        self.ssid = ssid
        self.client: PocketOptionAsync = None
        self.candles = []  # Список свечей [(timestamp, open, high, low, close), ...]
        self.current_price = 0.0
        
        self._init_ui()
        self._init_timers()

    def _init_ui(self):
        """Инициализация интерфейса."""
        self.setWindowTitle("📊 Pocket Option Quotes Viewer")
        self.setMinimumSize(1000, 700)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Заголовок
        header = self._create_header()
        layout.addWidget(header)
        
        # График
        self.plot = PlotWidget()
        self.plot.setBackground('w')
        self.plot.setTitle("Японские свечи", color='k', size='16pt')
        self.plot.setLabel('left', 'Цена', color='k')
        self.plot.setLabel('bottom', 'Время', color='k')
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        
        # Используем DateAxisItem для оси X
        date_axis = DateAxisItem(orientation='bottom')
        self.plot.setAxisItems({'bottom': date_axis})
        
        layout.addWidget(self.plot)
        
        # Текущая цена
        self.lbl_price = QLabel("Текущая цена: $0.00000")
        self.lbl_price.setFont(QFont("Arial", 18, QFont.Bold))
        self.lbl_price.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_price)
        
        # Статус
        self.lbl_status = QLabel("⚪ Отключено")
        self.lbl_status.setFont(QFont("Arial", 12))
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

    def _create_header(self) -> QWidget:
        """Создание панели управления."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 10)
        
        # Актив
        layout.addWidget(QLabel("Актив:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems([
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
            "BTCUSD_otc", "ETHUSD_otc"
        ])
        layout.addWidget(self.symbol_combo)
        
        # Период
        layout.addWidget(QLabel("Период:"))
        self.period_spin = QSpinBox()
        self.period_spin.setRange(5, 3600)
        self.period_spin.setValue(60)
        self.period_spin.setSuffix(" сек")
        layout.addWidget(self.period_spin)
        
        # Кнопки
        self.btn_connect = QPushButton("🔌 Подключить")
        self.btn_connect.clicked.connect(self._toggle_connection)
        layout.addWidget(self.btn_connect)
        
        self.btn_update = QPushButton("🔄 Обновить")
        self.btn_update.clicked.connect(self._update_candles)
        self.btn_update.setEnabled(False)
        layout.addWidget(self.btn_update)
        
        layout.addStretch()
        
        return widget

    def _init_timers(self):
        """Инициализация таймеров."""
        # Таймер обновления цены (каждую секунду)
        self.price_timer = QTimer()
        self.price_timer.timeout.connect(self._update_price)
        
        # Таймер обновления свечей (каждые 5 секунд)
        self.candle_timer = QTimer()
        self.candle_timer.timeout.connect(self._update_candles)

    # ==========================================================================
    # ПОДКЛЮЧЕНИЕ
    # ==========================================================================

    async def _connect(self):
        """Подключение к Pocket Option."""
        self.lbl_status.setText("🔄 Подключение...")
        self.lbl_status.setStyleSheet("color: orange;")
        
        try:
            self.client = PocketOptionAsync(ssid=self.ssid)
            await self.client.__aenter__()
            
            self.lbl_status.setText("🟢 Подключено")
            self.lbl_status.setStyleSheet("color: green;")
            
            self.btn_connect.setText("⏹️ Отключить")
            self.btn_update.setEnabled(True)
            
            # Загружаем начальные свечи
            await self._load_candles()
            
            # Запускаем таймеры
            self.price_timer.start(1000)  # 1 секунда
            self.candle_timer.start(5000)  # 5 секунд
            
        except Exception as e:
            self.lbl_status.setText(f"❌ Ошибка: {e}")
            self.lbl_status.setStyleSheet("color: red;")

    async def _disconnect(self):
        """Отключение."""
        self.price_timer.stop()
        self.candle_timer.stop()
        
        if self.client:
            await self.client.__aexit__(None, None, None)
        
        self.lbl_status.setText("⚪ Отключено")
        self.lbl_status.setStyleSheet("color: gray;")
        
        self.btn_connect.setText("🔌 Подключить")
        self.btn_update.setEnabled(False)

    def _toggle_connection(self):
        """Переключение подключения."""
        if self.client:
            asyncio.get_event_loop().run_until_complete(self._disconnect())
        else:
            asyncio.get_event_loop().run_until_complete(self._connect())

    # ==========================================================================
    # ПОЛУЧЕНИЕ ДАННЫХ
    # ==========================================================================

    async def _load_candles(self):
        """Загрузка исторических свечей."""
        symbol = self.symbol_combo.currentText()
        period = self.period_spin.value()
        
        print(f"📡 Загрузка свечей {symbol} ({period}s)...")
        
        try:
            # Получаем свечи через BinaryOptionsToolsV2
            candles = await self.client.get_candles(symbol, period=period, offset=0)
            
            if candles:
                self.candles = []
                for candle in candles:
                    timestamp = candle.get("timestamp", 0)
                    open_price = float(candle.get("open", 0))
                    high = float(candle.get("high", 0))
                    low = float(candle.get("low", 0))
                    close = float(candle.get("close", 0))
                    self.candles.append((timestamp, open_price, high, low, close))
                
                print(f"✅ Получено {len(self.candles)} свечей")
                self._plot_candles()
            else:
                print("⚠️ Свечи не получены")
                
        except Exception as e:
            print(f"❌ Ошибка загрузки свечей: {e}")

    async def _update_candles_data(self):
        """Обновление данных свечей."""
        symbol = self.symbol_combo.currentText()
        period = self.period_spin.value()
        
        try:
            # Получаем последние свечи
            candles = await self.client.get_candles(symbol, period=period, offset=0)
            
            if candles:
                old_count = len(self.candles)
                self.candles = []
                
                for candle in candles:
                    timestamp = candle.get("timestamp", 0)
                    open_price = float(candle.get("open", 0))
                    high = float(candle.get("high", 0))
                    low = float(candle.get("low", 0))
                    close = float(candle.get("close", 0))
                    self.candles.append((timestamp, open_price, high, low, close))
                
                new_count = len(self.candles)
                print(f"📊 Обновление: {old_count} → {new_count} свечей")
                self._plot_candles()
                
        except Exception as e:
            print(f"❌ Ошибка обновления свечей: {e}")

    async def _update_price_data(self):
        """Обновление текущей цены."""
        symbol = self.symbol_combo.currentText()
        
        try:
            # Получаем последнюю цену из последней свечи
            if self.candles:
                last_candle = self.candles[-1]
                self.current_price = last_candle[4]  # close price
                
                # Обновляем метку
                self.lbl_price.setText(f"Текущая цена: ${self.current_price:.5f}")
                
                # Обновляем цвет в зависимости от движения
                if len(self.candles) > 1:
                    prev_close = self.candles[-2][4]
                    if self.current_price > prev_close:
                        self.lbl_price.setStyleSheet("color: green;")
                    elif self.current_price < prev_close:
                        self.lbl_price.setStyleSheet("color: red;")
                    else:
                        self.lbl_price.setStyleSheet("color: black;")
                        
        except Exception as e:
            print(f"❌ Ошибка обновления цены: {e}")

    # ==========================================================================
    # ОТРИСОВКА
    # ==========================================================================

    def _plot_candles(self):
        """Отрисовка графика свечей."""
        self.plot.clear()
        
        if not self.candles:
            return
        
        # Преобразуем данные для PyQtGraph
        timestamps = [c[0] for c in self.candles]
        opens = [c[1] for c in self.candles]
        highs = [c[2] for c in self.candles]
        lows = [c[3] for c in self.candles]
        closes = [c[4] for c in self.candles]
        
        # Рисуем свечи
        self.plot.plotCandlestick(
            x=timestamps,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            pen='k',
            w=0.8
        )
        
        # Обновляем заголовок
        symbol = self.symbol_combo.currentText()
        period = self.period_spin.value()
        self.plot.setTitle(f"{symbol} ({period}s)", color='k', size='16pt')

    def _update_candles(self):
        """Обновление свечей (вызывается таймером)."""
        if self.client:
            asyncio.get_event_loop().run_until_complete(self._update_candles_data())

    def _update_price(self):
        """Обновление цены (вызывается таймером)."""
        if self.client:
            asyncio.get_event_loop().run_until_complete(self._update_price_data())

    def closeEvent(self, event):
        """Закрытие окна."""
        if self.client:
            asyncio.get_event_loop().run_until_complete(self._disconnect())
        event.accept()


# ==============================================================================
# ЗАПУСК
# ==============================================================================

def main():
    """Запуск приложения."""
    print("=" * 70)
    print("📊 Pocket Option Quotes Viewer")
    print("=" * 70)
    
    app = QApplication(sys.argv)
    
    if not DEMO_SSID:
        print("POCKET_OPTION_DEMO_SSID не задан в .env")
        sys.exit(1)
    window = QuotesViewer(ssid=DEMO_SSID)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
