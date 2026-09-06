"""
Панель разработчика для тестирования.

Предоставляет интерфейс для:
- Просмотра баланса (демо/реал)
- Выбора актива
- Настройки экспирации и ставки
- Ручного открытия сделок (CALL/PUT)
- Просмотра результата сделок
- Лога операций
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QTextEdit, QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QColor

from core.robot_engine import RobotEngine
from core.market_data import Deal
from datetime import datetime
from typing import Optional, List, Dict
import asyncio


class DeveloperPanel(QWidget):
    """
    Панель разработчика для тестирования торговли.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.worker = None
        self._is_connected = False
        self._current_symbol = "EURUSD_otc"
        self._current_period = 60
        self._trade_amount = 1.0
        self._trade_duration = 15
        self._pending_deals = {}  # trade_id -> deal
        
        self._init_ui()
        self._setup_timers()

    def _init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout(self)
        
        # Вкладки
        tabs = QTabWidget()
        
        # Вкладка 1: Торговля
        trade_tab = self._create_trade_tab()
        tabs.addTab(trade_tab, "💱 Торговля")
        
        # Вкладка 2: История сделок
        self.history_tab = self._create_history_tab()
        tabs.addTab(self.history_tab, "📜 История сделок")
        
        # Вкладка 3: Лог
        self.log_tab = self._create_log_tab()
        tabs.addTab(self.log_tab, "📋 Лог")
        
        layout.addWidget(tabs)

    def _create_trade_tab(self) -> QWidget:
        """Вкладка торговли."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ===== БАЛАНС =====
        balance_group = self._create_balance_group()
        layout.addWidget(balance_group)
        
        # ===== НАСТРОЙКИ ТОРГОВЛИ =====
        settings_group = self._create_settings_group()
        layout.addWidget(settings_group)
        
        # ===== КНОПКИ ТОРГОВЛИ =====
        buttons_group = self._create_buttons_group()
        layout.addWidget(buttons_group)
        
        # ===== ПОСЛЕДНЯЯ СДЕЛКА =====
        last_deal_group = self._create_last_deal_group()
        layout.addWidget(last_deal_group)
        
        layout.addStretch()
        
        return widget

    def _create_balance_group(self) -> QGroupBox:
        """Группа баланса."""
        group = QGroupBox("💰 Баланс")
        layout = QHBoxLayout(group)
        
        # Демо счёт
        demo_label = QLabel("Демо:")
        demo_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(demo_label)
        
        self.lbl_demo_balance = QLabel("$0.00")
        self.lbl_demo_balance.setFont(QFont("Arial", 18, QFont.Bold))
        self.lbl_demo_balance.setStyleSheet("color: #3498db;")
        layout.addWidget(self.lbl_demo_balance)
        
        layout.addSpacing(20)
        
        # Реал счёт
        real_label = QLabel("Реал:")
        real_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        layout.addWidget(real_label)
        
        self.lbl_real_balance = QLabel("$0.00")
        self.lbl_real_balance.setFont(QFont("Arial", 18, QFont.Bold))
        self.lbl_real_balance.setStyleSheet("color: #2ecc71;")
        layout.addWidget(self.lbl_real_balance)
        
        # Статус подключения
        layout.addStretch()
        
        self.lbl_connection = QLabel("⚪ Отключено")
        self.lbl_connection.setFont(QFont("Arial", 12))
        layout.addWidget(self.lbl_connection)
        
        return group

    def _create_settings_group(self) -> QGroupBox:
        """Группа настроек торговли."""
        group = QGroupBox("⚙️ Настройки торговли")
        layout = QFormLayout(group)
        
        # Актив
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems([
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
            "BTCUSD_otc", "ETHUSD_otc", "USDBDT_otc", "SYPUSD_otc"
        ])
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        layout.addRow("Актив:", self.symbol_combo)
        
        # Экспирация
        self.expiration_spin = QSpinBox()
        self.expiration_spin.setRange(5, 3600)
        self.expiration_spin.setValue(15)
        self.expiration_spin.setSuffix(" сек")
        self.expiration_spin.valueChanged.connect(
            lambda v: setattr(self, '_trade_duration', v)
        )
        layout.addRow("Экспирация:", self.expiration_spin)
        
        # Ставка
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(1.0, 1000.0)  # Минимум $1
        self.amount_spin.setValue(1.0)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setPrefix("$ ")
        self.amount_spin.setSingleStep(0.5)  # Шаг 50 центов
        self.amount_spin.valueChanged.connect(
            lambda v: setattr(self, '_trade_amount', v)
        )
        layout.addRow("Ставка:", self.amount_spin)
        
        return group

    def _create_buttons_group(self) -> QGroupBox:
        """Группа кнопок торговли."""
        group = QGroupBox("🎯 Открытие сделок")
        layout = QHBoxLayout(group)
        
        # Кнопка CALL
        self.btn_call = QPushButton("📈 CALL (Вверх)")
        self.btn_call.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 20px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.btn_call.clicked.connect(self._on_call_clicked)
        self.btn_call.setEnabled(False)
        layout.addWidget(self.btn_call)
        
        # Кнопка PUT
        self.btn_put = QPushButton("📉 PUT (Вниз)")
        self.btn_put.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 20px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.btn_put.clicked.connect(self._on_put_clicked)
        self.btn_put.setEnabled(False)
        layout.addWidget(self.btn_put)
        
        return group

    def _create_last_deal_group(self) -> QGroupBox:
        """Группа последней сделки."""
        group = QGroupBox("📊 Последняя сделка")
        layout = QFormLayout(group)
        
        self.lbl_last_symbol = QLabel("-")
        layout.addRow("Актив:", self.lbl_last_symbol)
        
        self.lbl_last_direction = QLabel("-")
        layout.addRow("Направление:", self.lbl_last_direction)
        
        self.lbl_last_amount = QLabel("-")
        layout.addRow("Ставка:", self.lbl_last_amount)
        
        self.lbl_last_profit = QLabel("-")
        layout.addRow("Результат:", self.lbl_last_profit)
        
        return group

    def _create_history_tab(self) -> QWidget:
        """Вкладка истории сделок."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Таблица сделок
        self.deals_table = QTableWidget()
        self.deals_table.setColumnCount(7)
        self.deals_table.setHorizontalHeaderLabels([
            "Время", "Актив", "Направление", "Ставка", "Экспирация", "Прибыль", "Статус"
        ])
        self.deals_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.deals_table.verticalHeader().setVisible(False)
        layout.addWidget(self.deals_table)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("🗑️ Очистить историю")
        btn_clear.clicked.connect(self._clear_history)
        btn_layout.addWidget(btn_clear)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        return widget

    def _create_log_tab(self) -> QWidget:
        """Вкладка лога."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a252f;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.log_text)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("🗑️ Очистить лог")
        btn_clear.clicked.connect(self.log_text.clear)
        btn_layout.addWidget(btn_clear)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        return widget

    def _setup_timers(self):
        """Настройка таймеров."""
        # Таймер обновления баланса (если подключено)
        self.balance_timer = QTimer()
        self.balance_timer.timeout.connect(self._update_balance_tick)

    # ==========================================================================
    # ПОДКЛЮЧЕНИЕ / ОТКЛЮЧЕНИЕ
    # ==========================================================================

    def connect_to_robot(self, ssid: str):
        """
        Подключение к RobotEngine.
        Использует существующий worker из главного окна.

        Args:
            ssid: SSID для авторизации
        """
        # Если worker уже есть и подключен, используем его
        if self.worker and self.worker.engine and self.worker.engine.is_connected():
            self.log("✅ Уже подключено")
            balance = self.worker.get_balance()
            self._on_connected_callback({"balance": balance, "is_demo": True})
            return

        self.log("⚠️ RobotEngine не подключен. Сначала подключитесь в главном окне.")
        self.lbl_connection.setText("🔴 Ошибка подключения")
        self.lbl_connection.setStyleSheet("color: #e74c3c;")

    def disconnect_from_robot(self):
        """Отключение от RobotEngine."""
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)
            self.worker = None
        
        self._is_connected = False
        self.btn_call.setEnabled(False)
        self.btn_put.setEnabled(False)
        self.lbl_connection.setText("⚪ Отключено")
        self.lbl_connection.setStyleSheet("color: #95a5a6;")
        
        self.log("❌ Отключено")

    # ==========================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ
    # ==========================================================================

    def _on_connected_callback(self, data: dict):
        """Обработчик подключения."""
        self._is_connected = True
        self.lbl_connection.setText("🟢 Подключено")
        self.lbl_connection.setStyleSheet("color: #2ecc71;")
        
        self.btn_call.setEnabled(True)
        self.btn_put.setEnabled(True)
        
        # Обновляем баланс
        balance = data.get("balance", 0)
        is_demo = data.get("is_demo", True)
        
        if is_demo:
            self.lbl_demo_balance.setText(f"${balance:.2f}")
        else:
            self.lbl_real_balance.setText(f"${balance:.2f}")
        
        self.log(f"✅ Подключено | Баланс: ${balance:.2f} ({'DEMO' if is_demo else 'REAL'})")

    def _on_disconnected_callback(self):
        """Обработчик отключения."""
        self._is_connected = False
        self.lbl_connection.setText("⚪ Отключено")
        self.lbl_connection.setStyleSheet("color: #95a5a6;")
        self.btn_call.setEnabled(False)
        self.btn_put.setEnabled(False)
        self.log("❌ Отключено")

    def _on_balance_callback(self, balance: float, is_demo: bool):
        """Обработчик баланса."""
        if is_demo:
            self.lbl_demo_balance.setText(f"${balance:.2f}")
        else:
            self.lbl_real_balance.setText(f"${balance:.2f}")
        self.log(f"💰 Баланс обновлён: ${balance:.2f}")

    def _on_trade_callback(self, deal_data: dict):
        """Обработчик сделки."""
        # deal_data может быть объектом Deal или словарём
        if hasattr(deal_data, 'to_dict'):
            deal_data = deal_data.to_dict()
        
        trade_id = deal_data.get("trade_id", "")
        profit = deal_data.get("profit")
        status = deal_data.get("status", "open")
        
        # Игнорируем уведомления об открытии сделки (profit=None)
        if profit is None:
            return
        
        symbol = deal_data.get("symbol", "")
        direction = deal_data.get("direction", "")
        amount = deal_data.get("amount", 0)
        
        self.log(f"🔍 Получен результат сделки: {trade_id} profit={profit}")
        
        # Ищем сделку в ожидающих по trade_id
        deal = self._pending_deals.get(trade_id)
        
        # Если не нашли по trade_id, ищем по symbol+direction+amount
        if not deal:
            for tid, d in self._pending_deals.items():
                if (d["symbol"] == symbol and 
                    d["direction"] == direction and 
                    abs(d["amount"] - amount) < 0.01):
                    deal = d
                    self.log(f"   ✅ Найдена по symbol/direction/amount: {tid[:8]}...")
                    break
        
        if deal:
            deal["profit"] = profit if profit else 0
            deal["status"] = "closed"
            deal["close_time"] = datetime.now()
            
            # Обновляем UI
            profit_value = profit if profit else 0
            if profit_value > 0:
                self.lbl_last_profit.setText(f"+${profit_value:.2f} (+{profit_value/deal['amount']*100:.0f}%)")
                self.lbl_last_profit.setStyleSheet("color: #2ecc71;")
                self.log(f"✅ +${profit_value:.2f} ({deal['symbol']} {deal['direction'].upper()})")
            else:
                self.lbl_last_profit.setText(f"${profit_value:.2f}")
                self.lbl_last_profit.setStyleSheet("color: #e74c3c;")
                self.log(f"❌ ${profit_value:.2f} ({deal['symbol']} {deal['direction'].upper()})")
            
            # Обновляем таблицу
            self._update_deal_in_table(deal)
            
            # Удаляем из ожидающих
            if deal["trade_id"] in self._pending_deals:
                del self._pending_deals[deal["trade_id"]]
        else:
            self.log(f"⚠️ Сделка {trade_id[:8]}... не найдена в ожидающих!")
            self.log(f"   Ожидающие: {[(k[:8], v['symbol'], v['direction']) for k,v in self._pending_deals.items()]}")

    def _on_error_callback(self, error: str):
        """Обработчик ошибки."""
        self.log(f"❌ Ошибка: {error}")
        QMessageBox.critical(self, "Ошибка", error)

    # ==========================================================================
    # ТОРГОВЛЯ
    # ==========================================================================

    def _on_call_clicked(self):
        """Кнопка CALL."""
        self._execute_trade("call")

    def _on_put_clicked(self):
        """Кнопка PUT."""
        self._execute_trade("put")

    def _execute_trade(self, direction: str):
        """
        Открытие сделки через RobotEngine.

        Args:
            direction: "call" или "put"
        """
        if not self._is_connected:
            QMessageBox.warning(self, "Ошибка", "Не подключено к платформе")
            return

        if not self.worker or not self.worker.engine:
            QMessageBox.warning(self, "Ошибка", "RobotEngine не инициализирован")
            return

        symbol = self.symbol_combo.currentText()
        amount = self._trade_amount
        duration = self._trade_duration

        self.log(f"📈 {direction.upper()} {symbol} ${amount} {duration}s")

        # Создаём сделку для отслеживания ДО отправки
        deal = {
            "trade_id": f"pending-{datetime.now().strftime('%H%M%S%f')}",
            "symbol": symbol,
            "direction": direction,
            "amount": amount,
            "duration": duration,
            "open_time": datetime.now(),
            "profit": None,
            "status": "open"
        }
        self._pending_deals[deal["trade_id"]] = deal

        # Обновляем UI
        self.lbl_last_symbol.setText(symbol)
        self.lbl_last_direction.setText(direction.upper())
        self.lbl_last_amount.setText(f"${amount}")
        self.lbl_last_profit.setText("Ожидание...")
        self.lbl_last_profit.setStyleSheet("color: #f39c12;")

        # Добавляем в таблицу
        self._add_deal_to_table(deal)

        # Отправляем сделку через RobotEngine
        import threading
        def trade_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                real_trade_id, deal_data = loop.run_until_complete(
                    self.worker.engine.buy(symbol, amount, duration, direction)
                )
                loop.close()
                
                # Обновляем trade_id реальным
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._update_trade_id(deal["trade_id"], real_trade_id))
                    
            except Exception as e:
                self.log(f"❌ Ошибка торговли: {e}")
                # Удаляем из ожидающих
                if deal["trade_id"] in self._pending_deals:
                    del self._pending_deals[deal["trade_id"]]

        thread = threading.Thread(target=trade_thread)
        thread.daemon = True
        thread.start()

    def _update_trade_id(self, old_id: str, new_id: str):
        """Обновление trade_id после получения от платформы."""
        if old_id in self._pending_deals:
            deal = self._pending_deals[old_id]
            deal["trade_id"] = new_id
            self._pending_deals[new_id] = deal
            del self._pending_deals[old_id]
            self.log(f"🔑 Trade ID обновлён: {old_id[:8]}... → {new_id[:8]}...")

    # ==========================================================================
    # ОБНОВЛЕНИЕ UI
    # ==========================================================================

    def _on_symbol_changed(self, symbol: str):
        """Изменение актива."""
        self._current_symbol = symbol
        self.log(f"Актив изменён: {symbol}")

    def _update_balance_tick(self):
        """Обновление баланса (таймер)."""
        # Будет реализовано при интеграции с RobotEngine
        pass

    def update_balance(self, demo: float, real: float):
        """
        Обновление баланса.

        Args:
            demo: Баланс демо счёта
            real: Баланс реального счёта
        """
        self.lbl_demo_balance.setText(f"${demo:.2f}")
        self.lbl_real_balance.setText(f"${real:.2f}")

    def _add_deal_to_table(self, deal: dict):
        """Добавление сделки в таблицу."""
        row = self.deals_table.rowCount()
        self.deals_table.insertRow(row)

        time_str = deal["open_time"].strftime("%H:%M:%S")
        self.deals_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.deals_table.setItem(row, 1, QTableWidgetItem(deal["symbol"]))
        
        direction = deal["direction"].upper()
        direction_item = QTableWidgetItem(direction)
        if deal["direction"] == "call":
            direction_item.setForeground(QColor("#2ecc71"))
        else:
            direction_item.setForeground(QColor("#e74c3c"))
        self.deals_table.setItem(row, 2, direction_item)
        
        self.deals_table.setItem(row, 3, QTableWidgetItem(f"${deal['amount']:.2f}"))
        self.deals_table.setItem(row, 4, QTableWidgetItem(f"{deal['duration']}s"))
        self.deals_table.setItem(row, 5, QTableWidgetItem("Ожидание"))
        self.deals_table.setItem(row, 6, QTableWidgetItem("Открыта"))

    def _update_deal_in_table(self, deal: dict):
        """Обновление сделки в таблице."""
        # Находим сделку по времени
        for row in range(self.deals_table.rowCount()):
            time_item = self.deals_table.item(row, 0)
            if time_item and time_item.text() == deal["open_time"].strftime("%H:%M:%S"):
                if deal["profit"] and deal["profit"] > 0:
                    profit_str = f"+${deal['profit']:.2f}"
                    self.deals_table.item(row, 5).setForeground(QColor("#2ecc71"))
                else:
                    profit_str = f"${deal['profit']:.2f}"
                    self.deals_table.item(row, 5).setForeground(QColor("#e74c3c"))

                self.deals_table.item(row, 5).setText(profit_str)
                self.deals_table.item(row, 6).setText("Закрыта")
                break

    def _clear_history(self):
        """Очистка истории сделок."""
        self.deals_table.setRowCount(0)
        self.log("История сделок очищена")

    def log(self, message: str):
        """
        Логирование сообщения.

        Args:
            message: Сообщение
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")


__all__ = ["DeveloperPanel"]
