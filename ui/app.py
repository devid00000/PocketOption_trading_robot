#!/usr/bin/env python3
"""
Pocket Option Robot v2.0 — GUI в стиле расширения.
Интеграция с RobotEngine (BinaryOptionsToolsV2).
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QScrollArea, QFrame,
    QGridLayout, QSizePolicy, QMessageBox, QFileDialog, QMenu, QDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QCursor

from utils.logger import Logger
from core.robot_engine import RobotEngine
from core.models import RobotManager, RobotConfig
from core.strategy_models import StrategyConfig
from strategies.converter import StrategyConverter
from ui.widgets.trading_tab import TradingTab
from ui.widgets.robot_dialog import RobotDialog
from ui.widgets.strategy_builder import StrategyBuilderDialog
from config.runtime import load_runtime_config, ssid_is_demo
from ui.widgets.connection_dialog import ConnectionDialog


logger = Logger("GUI")

DEMO_SSID = load_runtime_config().demo_ssid


# ==============================================================================
# WORKER ДЛЯ АСИНХРОННЫХ ОПЕРАЦИЙ
# ==============================================================================

class RobotWorker(QThread):
    """Worker поток для работы с RobotEngine."""

    # Сигналы
    connected_signal = Signal(dict)
    disconnected_signal = Signal()
    candle_signal = Signal(str, int, list)
    balance_signal = Signal(float, bool)  # balance, is_demo
    assets_signal = Signal(list)
    trade_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, ssid: str):
        super().__init__()
        self.ssid = ssid
        self.engine: Optional[RobotEngine] = None
        self._running = False
        self._stop_requested = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def run(self):
        """Запуск event loop в отдельном потоке."""
        self._stop_requested = False
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_loop())
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()
            self._loop = None

    async def _main_loop(self):
        """Основной асинхронный цикл."""
        try:
            self.engine = RobotEngine(ssid=self.ssid)

            # Регистрация callbacks
            self.engine.on_connected(self._on_connected)
            self.engine.on_disconnected(self._on_disconnected)
            self.engine.on_candle(self._on_candle)
            self.engine.on_balance(self._on_balance)
            self.engine.on_trade(self._on_trade)

            # Подключение
            await self.engine.connect()

            if self._stop_requested:
                return
            self._running = True
            while self._running:
                await asyncio.sleep(0.1)

        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            if self.engine:
                try:
                    await self.engine.disconnect()
                except Exception as exc:
                    self.error_signal.emit(f"Ошибка отключения: {exc}")
                finally:
                    self._running = False

    async def _on_connected(self):
        balance = self.engine.get_balance()
        self.connected_signal.emit({
            "balance": balance.current,
            "is_demo": balance.is_demo
        })

    async def _on_disconnected(self):
        self.disconnected_signal.emit()

    async def _on_candle(self, symbol: str, period: int, candles: list):
        candle_data = [c.to_dict() for c in candles]
        self.candle_signal.emit(symbol, period, candle_data)

    async def _on_balance(self, balance):
        self.balance_signal.emit(balance.current, balance.is_demo)

    async def _on_trade(self, deal):
        self.trade_signal.emit(deal.to_dict())

    def stop(self):
        """Остановка worker."""
        # Do not stop the event loop while run_until_complete() is active.
        # Let _main_loop exit normally and disconnect the API client first.
        self._stop_requested = True
        self._running = False

    async def subscribe(self, symbol: str, period: int):
        """Подписка на свечи."""
        if self.engine:
            await self.engine.subscribe(symbol, period)

    async def replace_subscription(self, symbol: str, period: int):
        """Replace the current market-data stream in the worker loop."""
        if self.engine:
            await self.engine.replace_subscription(symbol, period)

    async def trade(self, symbol: str, amount: float, duration: int, direction: str):
        """Открытие сделки."""
        if self.engine:
            await self.engine.buy(symbol, amount, duration, direction)

    async def refresh_balance(self):
        """Request an immediate balance update in the worker event loop."""
        if self.engine:
            await self.engine.refresh_balance()

    async def load_active_assets(self):
        """Load API assets and emit them to the Qt thread."""
        if self.engine:
            self.assets_signal.emit(await self.engine.get_active_assets())

    async def load_assets_and_subscribe(self, symbol: str, period: int):
        """Load assets and subscribe sequentially on the API event loop."""
        if not self.engine:
            return
        self.assets_signal.emit(await self.engine.get_active_assets())
        await self.engine.replace_subscription(symbol, period)

    def submit(self, coroutine):
        """Schedule a coroutine on the worker-owned event loop."""
        if not self._loop or self._loop.is_closed():
            raise RuntimeError("Рабочий event loop не запущен")
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def get_candles(self, symbol: str, period: int, count: int = 100) -> List:
        """Получение свечей."""
        if self.engine:
            return self.engine.get_candles(symbol, period, count)
        return []

    def get_balance(self) -> float:
        """Получение баланса."""
        if self.engine:
            return self.engine.get_balance().current
        return 0.0


class Sidebar(QFrame):
    """Боковая панель навигации."""

    page_changed = Signal(int)
    open_developer_panel = Signal()  # Сигнал для открытия панели разработчика

    def __init__(self):
        super().__init__()
        self._init_ui()
    
    def _init_ui(self):
        """Инициализация интерфейса."""
        self.setFixedWidth(200)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a252f;
                border-right: 2px solid #34495e;
            }
            QPushButton {
                background-color: transparent;
                color: #ecf0f1;
                text-align: left;
                padding: 15px 20px;
                font-size: 14px;
                border: none;
                border-radius: 5px;
                margin: 5px 10px;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
            QPushButton:checked {
                background-color: #3498db;
                font-weight: bold;
            }
            QPushButton#logoBtn {
                font-size: 18px;
                font-weight: bold;
                padding: 20px;
                border-bottom: 2px solid #34495e;
                margin-bottom: 20px;
            }
            QPushButton#logoBtn:hover {
                background-color: transparent;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Логотип
        self.btn_logo = QPushButton("📊 PO Robot")
        self.btn_logo.setObjectName("logoBtn")
        self.btn_logo.setCheckable(False)
        layout.addWidget(self.btn_logo)
        
        # Кнопки навигации
        self.btn_strategies = QPushButton("🎓 Стратегии")
        self.btn_strategies.setCheckable(True)
        self.btn_strategies.setChecked(True)
        self.btn_strategies.clicked.connect(lambda: self.page_changed.emit(0))
        layout.addWidget(self.btn_strategies)
        
        self.btn_trading = QPushButton("📈 Торговля")
        self.btn_trading.setCheckable(True)
        self.btn_trading.clicked.connect(lambda: self.page_changed.emit(1))
        layout.addWidget(self.btn_trading)
        
        self.btn_history = QPushButton("📜 История")
        self.btn_history.setCheckable(True)
        self.btn_history.clicked.connect(lambda: self.page_changed.emit(2))
        layout.addWidget(self.btn_history)
        
        self.btn_settings = QPushButton("⚙️ Настройки")
        self.btn_settings.setCheckable(True)
        self.btn_settings.clicked.connect(lambda: self.page_changed.emit(3))
        layout.addWidget(self.btn_settings)

        # Кнопка для разработчика
        self.btn_developer = QPushButton("🔧 Для разработчика")
        self.btn_developer.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                font-weight: bold;
                padding: 15px;
                margin: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #9b59b6;
            }
        """)
        self.btn_developer.clicked.connect(lambda: self.open_developer_panel.emit())
        layout.addWidget(self.btn_developer)

        layout.addStretch()

        # Кнопка подключения
        self.btn_connect = QPushButton("🔌 Подключить")
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 15px;
                margin: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.btn_connect.clicked.connect(self._on_connect)
        layout.addWidget(self.btn_connect)
    
    def _on_connect(self):
        """Кнопка подключения."""
        self.page_changed.emit(3)  # Переход на вкладку настроек


class StrategiesPage(QFrame):
    """Страница "Стратегии" — сетка роботов."""
    
    robot_clicked = Signal(str)  # Название робота
    create_robot = Signal()
    
    def __init__(self):
        super().__init__()
        self._init_ui()
    
    def _init_ui(self):
        """Инициализация интерфейса."""
        self.setStyleSheet("""
            QFrame {
                background-color: #1a252f;
            }
            QLabel#title {
                color: #ecf0f1;
                font-size: 24px;
                font-weight: bold;
                padding: 20px;
            }
            QPushButton#createBtn {
                background-color: #3498db;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 10px 30px;
                border-radius: 5px;
            }
            QPushButton#createBtn:hover {
                background-color: #2980b9;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Заголовок
        title_layout = QHBoxLayout()
        title = QLabel("🎓 Стратегии")
        title.setObjectName("title")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        self.btn_create = QPushButton("+ Создать")
        self.btn_create.setObjectName("createBtn")
        self.btn_create.clicked.connect(lambda: self.create_robot.emit())
        title_layout.addWidget(self.btn_create)
        
        layout.addLayout(title_layout)
        
        # Скролл для сетки
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #2c3e50;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        
        # Контейнер для сетки
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(20)
        self.grid_layout.setContentsMargins(20, 20, 20, 20)
        
        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)
        
        # Словарь для хранения кнопок роботов
        self.robot_buttons = {}
    
    def load_robots(self, robots: list):
        """Загрузка роботов в сетку."""
        # Очищаем сетку
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.robot_buttons.clear()
        
        # Создаём кнопки для каждого робота
        for i, robot in enumerate(robots):
            row = i // 5
            col = i % 5
            
            btn = self._create_robot_button(robot)
            self.grid_layout.addWidget(btn, row, col)
            self.robot_buttons[robot.name] = btn
    
    def _create_robot_button(self, robot: RobotConfig) -> QPushButton:
        """Создание кнопки робота."""
        btn = QPushButton()
        btn.setFixedSize(150, 180)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        
        # Статус
        status_color = "#e74c3c"  # Красный (остановлен)
        status_text = "Выкл"
        
        if robot.total_trades > 0:
            if robot.win_rate >= 60:
                status_color = "#2ecc71"  # Зелёный
                status_text = "Вкл"
            elif robot.win_rate >= 40:
                status_color = "#f39c12"  # Жёлтый
                status_text = "Пауза"
        
        # Иконка и текст
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2c3e50;
                border: 2px solid {status_color};
                border-radius: 10px;
                color: #ecf0f1;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #34495e;
                border: 2px solid #3498db;
            }}
        """)
        
        # Текст кнопки
        btn.setText(f"🤖\n\n{robot.name}\n\n"
                   f"💰 ${robot.amount:.2f}\n"
                   f"📊 {robot.total_trades} сделок\n"
                   f"📈 Win: {robot.win_rate:.0f}%\n"
                   f"● {status_text}")
        
        # Контекстное меню
        btn.setContextMenuPolicy(Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda pos, r=robot.name: self._show_context_menu(pos, r)
        )
        
        # Клик
        btn.clicked.connect(lambda: self.robot_clicked.emit(robot.name))
        
        return btn
    
    def _show_context_menu(self, pos, robot_name: str):
        """Контекстное меню робота."""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                padding: 5px;
            }
            QMenu::item {
                padding: 10px 20px;
                border-radius: 3px;
            }
            QMenu::item:hover {
                background-color: #3498db;
            }
        """)
        
        menu.addAction("⚙️ Настройки")
        menu.addAction("▶️ Запустить")
        menu.addAction("⏸️ Переименовать")
        menu.addSeparator()
        menu.addAction("🗑️ Удалить")
        menu.addAction("📋 Создать копию")
        menu.addSeparator()
        menu.addAction("📥 Импорт")
        menu.addAction("📤 Экспорт")
        menu.addSeparator()
        menu.addAction("📜 Журнал")
        
        action = menu.exec(QCursor.pos())
        
        if action:
            text = action.text()
            if "Настройки" in text:
                self.robot_clicked.emit(robot_name)
            elif "Запустить" in text:
                pass  # TODO: Запуск
            elif "Удалить" in text:
                self.robot_clicked.emit(f"DELETE:{robot_name}")
            elif "Экспорт" in text:
                self.robot_clicked.emit(f"EXPORT:{robot_name}")
            # и т.д.


class MainWindow(QMainWindow):
    """Главное окно в стиле расширения."""

    def __init__(self, ssid: str = DEMO_SSID):
        super().__init__()

        self.ssid = ssid
        self.account_is_demo = ssid_is_demo(ssid) if ssid else True
        self.worker: Optional[RobotWorker] = None
        self.robot_manager = RobotManager()
        self._is_connected = False
        self._current_symbol = "EURUSD_otc"
        self._current_period = 60

        # Создаём тестовых роботов
        if len(self.robot_manager.list()) == 0:
            self.robot_manager.create_default_robots()

        self._init_ui()
        self._load_strategies()
        self._connect_signals()

        logger.info("GUI v2.0 инициализирован")

    def _init_ui(self):
        """Инициализация интерфейса."""
        self.setWindowTitle("Pocket Option Robot v2.0")
        self.setGeometry(100, 100, 1400, 900)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a252f;
            }
        """)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Боковая панель
        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._on_page_changed)
        main_layout.addWidget(self.sidebar)

        # Стек страниц
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: transparent;")

        # Страница 1: Стратегии
        self.strategies_page = StrategiesPage()
        self.strategies_page.create_robot.connect(self._on_create_robot)
        self.strategies_page.robot_clicked.connect(self._on_robot_clicked)
        self.stack.addWidget(self.strategies_page)

        # Страница 2: Торговля
        self.trading_tab = TradingTab()
        self.stack.addWidget(self.trading_tab)

        # Страница 3: История (заглушка)
        self.history_page = QLabel("📜 История сделок\n\nВ разработке...")
        self.history_page.setAlignment(Qt.AlignCenter)
        self.history_page.setStyleSheet("color: #ecf0f1; font-size: 24px;")
        self.stack.addWidget(self.history_page)

        # Страница 4: Настройки
        self.settings_page = self._create_settings_page()
        self.stack.addWidget(self.settings_page)

        main_layout.addWidget(self.stack)

    def _create_settings_page(self) -> QWidget:
        """Страница настроек."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("⚙️ Настройки")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #ecf0f1; font-size: 24px; font-weight: bold; padding: 20px;")
        layout.addWidget(title)

        # Информация о подключении
        self.connection_info = QLabel("🔌 Подключение к платформе\n\n"
                     "Нажмите 'Подключить' в боковой панели")
        self.connection_info.setAlignment(Qt.AlignCenter)
        self.connection_info.setStyleSheet("color: #95a5a6; font-size: 16px; padding: 20px;")
        layout.addWidget(self.connection_info)

        self.btn_connection_settings = QPushButton("Параметры подключения")
        self.btn_connection_settings.clicked.connect(self._open_connection_settings)
        layout.addWidget(self.btn_connection_settings)

        self.btn_debug_chart = QPushButton("Открыть отладочный график")
        self.btn_debug_chart.clicked.connect(self._open_debug_chart)
        layout.addWidget(self.btn_debug_chart)

        layout.addStretch()

        return widget

    def _open_connection_settings(self):
        was_connected = self._is_connected
        dialog = ConnectionDialog(self, load_runtime_config())
        if dialog.exec() == QDialog.Accepted:
            if was_connected:
                self._disconnect()
            self.account_is_demo = dialog.selected_is_demo
            self.ssid = dialog.config.demo_ssid if self.account_is_demo else dialog.config.real_ssid
            self.connection_info.setText("Параметры сохранены. Нажмите «Подключить».")
            if was_connected and self.ssid:
                self._connect()

    def _open_debug_chart(self):
        if not self.ssid:
            self._open_connection_settings()
        if not self.ssid:
            return
        from ui.widgets.debug_chart_window import DebugChartWindow
        self.debug_chart_window = DebugChartWindow(self.ssid, self)
        self.debug_chart_window.show()

    def _connect_signals(self):
        """Подключение сигналов."""
        # От sidebar
        self.sidebar.btn_connect.clicked.connect(self._toggle_connection)
        
        # Панель разработчика
        self.sidebar.open_developer_panel.connect(self._open_developer_panel)
        self.trading_tab.btn_refresh_balance.clicked.connect(self._refresh_balance)

    def _refresh_balance(self):
        """Request an immediate server balance refresh without blocking Qt."""
        if not self.worker or not self.worker.engine or not self.worker._loop:
            self.log_message("Невозможно обновить баланс: нет подключения")
            return
        try:
            future = self.worker.submit(self.worker.refresh_balance())
            future.add_done_callback(self._balance_refresh_finished)
        except Exception as exc:
            self.log_message(f"Ошибка обновления баланса: {exc}")

    def _balance_refresh_finished(self, future):
        try:
            future.result()
        except Exception as exc:
            self.log_message(f"Ошибка обновления баланса: {exc}")

    def _open_developer_panel(self):
        """Открытие панели разработчика."""
        from ui.widgets.developer_panel import DeveloperPanel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔧 Панель разработчика")
        dialog.setMinimumSize(900, 700)
        
        layout = QVBoxLayout(dialog)
        
        # Панель разработчика
        developer_panel = DeveloperPanel(dialog)
        layout.addWidget(developer_panel)
        
        # Кнопка закрытия
        btn_close = QPushButton("❌ Закрыть")
        btn_close.clicked.connect(dialog.reject)
        layout.addWidget(btn_close)
        
        # Подключаем к текущему worker если есть
        if self.worker and self.worker.engine and self.worker.engine.is_connected():
            developer_panel.worker = self.worker
            developer_panel.connect_to_robot(self.ssid)
            
            # Подключаем сигналы для обновления UI
            self.worker.balance_signal.connect(developer_panel._on_balance_callback)
            self.worker.trade_signal.connect(developer_panel._on_trade_callback)
        else:
            developer_panel.log("❌ Сначала подключитесь к платформе в главном окне!")
        
        dialog.exec()
        
        # Отключаем сигналы после закрытия
        if self.worker:
            try:
                self.worker.balance_signal.disconnect(developer_panel._on_balance_callback)
                self.worker.trade_signal.disconnect(developer_panel._on_trade_callback)
            except:
                pass

    def _on_page_changed(self, index: int):
        """Переключение страницы."""
        self.stack.setCurrentIndex(index)

        # Сбрасываем все кнопки
        self.sidebar.btn_strategies.setChecked(False)
        self.sidebar.btn_trading.setChecked(False)
        self.sidebar.btn_history.setChecked(False)
        self.sidebar.btn_settings.setChecked(False)

        # Активируем нужную
        if index == 0:
            self.sidebar.btn_strategies.setChecked(True)
        elif index == 1:
            self.sidebar.btn_trading.setChecked(True)
        elif index == 2:
            self.sidebar.btn_history.setChecked(True)
        elif index == 3:
            self.sidebar.btn_settings.setChecked(True)

    def _load_strategies(self):
        """Загрузка стратегий."""
        robots = self.robot_manager.list()
        self.strategies_page.load_robots(robots)

    def _on_create_robot(self):
        """Создание робота (открытие конструктора стратегий)."""
        dialog = StrategyBuilderDialog(self)
        
        if dialog.exec() == QDialog.Accepted:
            strategy_config = dialog.get_strategy()
            
            # Создаём робота из стратегии
            from core.models import RobotConfig
            robot = RobotConfig.from_strategy_config(strategy_config)
            robot.name = strategy_config.name
            
            self.robot_manager.save(robot)
            self._load_strategies()
            logger.success(f"Создан робот: {robot.name}")

    def _on_robot_clicked(self, robot_name: str):
        """Клик по роботу."""
        if robot_name.startswith("DELETE:"):
            name = robot_name[7:]
            reply = QMessageBox.question(
                self,
                "Удаление",
                f"Удалить робота '{name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.robot_manager.delete(name)
                self._load_strategies()
        elif robot_name.startswith("EXPORT:"):
            name = robot_name[7:]
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Экспорт робота",
                f"{name}.json",
                "JSON файлы (*.json)"
            )
            if filepath:
                self.robot_manager.export_robot(name, filepath)
        else:
            # Редактирование
            robot = self.robot_manager.get(robot_name)
            if robot:
                dialog = RobotDialog(self, robot)
                if dialog.exec() == QDialog.Accepted:
                    self.robot_manager.save(robot)
                    self._load_strategies()

    # ==========================================================================
    # ПОДКЛЮЧЕНИЕ / ОТКЛЮЧЕНИЕ
    # ==========================================================================

    def _toggle_connection(self):
        """Переключение подключения."""
        if self._is_connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        """Подключение к Pocket Option."""
        if not self.ssid:
            self._open_connection_settings()
            if not self.ssid:
                return
        self.log_message("Подключение...")

        self.worker = RobotWorker(ssid=self.ssid)
        self.worker.connected_signal.connect(self._on_connected)
        self.worker.disconnected_signal.connect(self._on_disconnected)
        self.worker.candle_signal.connect(self._on_candle)
        self.worker.balance_signal.connect(self._on_balance_update)
        self.worker.trade_signal.connect(self._on_trade)
        self.worker.error_signal.connect(self._on_error)

        self.worker.start()

        self.sidebar.btn_connect.setEnabled(False)
        self.connection_info.setText("🔌 Подключение...\n\nОжидайте...")

    def _disconnect(self):
        """Отключение."""
        if self.worker:
            self.worker.stop()
            self.worker.wait(5000)
            self.worker = None

        self._is_connected = False
        self.log_message("Отключено")

    # ==========================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ
    # ==========================================================================

    def _on_connected(self, data: dict):
        """Обработчик подключения."""
        self._is_connected = True
        self.account_is_demo = bool(data["is_demo"])
        self.sidebar.btn_connect.setEnabled(True)
        self.sidebar.btn_connect.setText("⏹️ Отключить")
        self.sidebar.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 15px;
                margin: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)

        account_name = "DEMO" if data["is_demo"] else "REAL"
        self.connection_info.setText(
            f"🟢 Подключено ({account_name})\n\nБаланс: ${data['balance']:.2f}"
        )
        self.connection_info.setStyleSheet("color: #2ecc71; font-size: 16px; padding: 20px;")

        # Обновление баланса в trading_tab
        self.trading_tab.update_balance(data["balance"], data["is_demo"])

        # Подписка на активы
        self._subscribe_to_asset()

        self.log_message(f"Подключено | Баланс: ${data['balance']:.2f}")

    def _on_disconnected(self):
        """Обработчик отключения."""
        self._is_connected = False
        self.sidebar.btn_connect.setText("🔌 Подключить")
        self.sidebar.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 15px;
                margin: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)

        self.connection_info.setText("🔌 Подключение к платформе\n\nНажмите 'Подключить' в боковой панели")
        self.connection_info.setStyleSheet("color: #95a5a6; font-size: 16px; padding: 20px;")

        self.log_message("Отключено")

    def _on_candle(self, symbol: str, period: int, candles: list):
        """Обработчик свечей."""
        if symbol != self._current_symbol or period != self._current_period:
            return

        # Обновление котировок в trading_tab
        self.trading_tab.update_candles(candles)

    def _on_balance_update(self, balance: float, is_demo: bool):
        """Обработчик баланса."""
        self.trading_tab.update_balance(balance, is_demo)

    def _on_trade(self, deal: dict):
        """Обработчик сделки."""
        profit = deal.get("profit")
        if profit is None:
            profit_str = "0.00"
        else:
            profit_str = f"{profit:+.2f}"
        
        self.log_message(f"Сделка: {deal.get('direction', 'N/A').upper()} "
                        f"${deal.get('amount', 0):.2f} -> {profit_str}$")

    def _on_error(self, error: str):
        """Обработчик ошибки."""
        self.log_message(f"❌ Ошибка: {error}")
        QMessageBox.critical(self, "Ошибка", error)

    # ==========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ==========================================================================

    def _subscribe_to_asset(self):
        """Подписка на актив."""
        if self.worker:
            asyncio.get_event_loop().call_soon_threadsafe(
                asyncio.ensure_future,
                self.worker.subscribe(self._current_symbol, self._current_period)
            )

    def log_message(self, message: str):
        """Логирование сообщения."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.trading_tab.log(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """Закрытие окна."""
        if self.worker:
            self.worker.stop()
            self.worker.wait(5000)

        event.accept()


def run_gui(ssid: str | None = DEMO_SSID):
    """Запуск GUI."""
    print("=" * 70)
    print("Pocket Option Robot v2.0")
    print("=" * 70)
    print("\n📋 Возможности:")
    print("  • Интерфейс в стиле расширения")
    print("  • Конструктор роботов")
    print("  • Импорт/Экспорт JSON")
    print("  • Котировки через BinaryOptionsToolsV2")
    print("\n" + "=" * 70)
    print("Запуск графического интерфейса...")
    print("=" * 70)

    app = QApplication(sys.argv)

    # Применяем тёмную тему
    app.setStyle("Fusion")

    window = MainWindow(ssid=ssid)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
