"""
Вкладка "Торговля" — полная версия с роботами.
Интеграция с RobotEngine для котировок.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QFileDialog, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor

from core.models import RobotManager, RobotConfig
from ui.widgets.robot_dialog import RobotDialog


class TradingTab(QWidget):
    """Вкладка 'Торговля'."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.robot_manager = RobotManager()
        self.balance_timer = None
        self._current_robot_index = -1
        self._current_candles = []

        # Создаём тестовых роботов если пусто
        if len(self.robot_manager.list()) == 0:
            self.robot_manager.create_default_robots()

        self._init_ui()
        self._load_robots()
    
    def _init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # ===== БАЛАНС =====
        balance_group = QGroupBox("💰 Баланс")
        balance_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        balance_layout = QHBoxLayout()
        
        # Метки "Демо" и "Реал" - яркий белый текст
        demo_label = QLabel("Демо:")
        demo_label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        balance_layout.addWidget(demo_label)
        
        self.lbl_demo_balance = QLabel("$0.00")
        self.lbl_demo_balance.setFont(QFont("Arial", 20, QFont.Bold))
        self.lbl_demo_balance.setStyleSheet("color: #3498db;")
        balance_layout.addWidget(self.lbl_demo_balance)
        
        real_label = QLabel("Реал:")
        real_label.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold;")
        balance_layout.addWidget(real_label)
        
        self.lbl_real_balance = QLabel("$0.00")
        self.lbl_real_balance.setFont(QFont("Arial", 20, QFont.Bold))
        self.lbl_real_balance.setStyleSheet("color: #2ecc71;")
        balance_layout.addWidget(self.lbl_real_balance)
        
        balance_layout.addStretch()
        
        # Кнопка обновления
        self.btn_refresh_balance = QPushButton("🔄 Обновить")
        self.btn_refresh_balance.setMaximumWidth(150)
        self.btn_refresh_balance.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        balance_layout.addWidget(self.btn_refresh_balance)
        
        balance_group.setLayout(balance_layout)
        layout.addWidget(balance_group)

        # ===== КОТИРОВКИ =====
        quotes_group = QGroupBox("📊 Котировки EURUSD_otc (60s)")
        quotes_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        quotes_layout = QVBoxLayout()

        # Таблица котировок
        self.quotes_table = QTableWidget()
        self.quotes_table.setColumnCount(6)
        self.quotes_table.setHorizontalHeaderLabels([
            "Время", "Open", "High", "Low", "Close", "Изменение"
        ])
        self.quotes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.quotes_table.verticalHeader().setVisible(False)
        self.quotes_table.setMaximumHeight(200)
        self.quotes_table.setStyleSheet("""
            QTableWidget {
                background-color: #2c3e50;
                color: #ffffff;
                border: 2px solid #34495e;
                border-radius: 5px;
                gridline-color: #34495e;
            }
            QTableWidget::item {
                padding: 5px;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: #ffffff;
                padding: 10px;
                border: none;
                font-weight: bold;
            }
        """)
        quotes_layout.addWidget(self.quotes_table)
        quotes_group.setLayout(quotes_layout)
        layout.addWidget(quotes_group)

        # ===== РОБОТЫ =====
        robots_group = QGroupBox("🤖 Роботы")
        robots_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        robots_layout = QVBoxLayout()
        
        # Таблица роботов
        self.robots_table = QTableWidget()
        self.robots_table.setColumnCount(5)
        self.robots_table.setHorizontalHeaderLabels([
            "Название", "Статус", "Сделок", "Прибыль", "Win Rate"
        ])
        self.robots_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.robots_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.robots_table.setAlternatingRowColors(False)  # Отключаем чередование
        self.robots_table.verticalHeader().setVisible(False)  # Скрываем номера строк
        self.robots_table.itemSelectionChanged.connect(self._on_robot_selected)
        self.robots_table.setStyleSheet("""
            QTableWidget {
                background-color: #2c3e50;
                color: #ffffff;
                border: 2px solid #34495e;
                border-radius: 5px;
                gridline-color: #34495e;
            }
            QTableWidget::item {
                padding: 5px;
                color: #ffffff;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: #ffffff;
                padding: 10px;
                border: none;
                font-weight: bold;
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
        robots_layout.addWidget(self.robots_table)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        
        self.btn_add_robot = QPushButton("➕ Добавить робота")
        self.btn_add_robot.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.btn_add_robot.clicked.connect(self._on_add_robot)
        btn_layout.addWidget(self.btn_add_robot)
        
        self.btn_edit_robot = QPushButton("✏️ Редактировать")
        self.btn_edit_robot.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.btn_edit_robot.setEnabled(False)
        self.btn_edit_robot.clicked.connect(self._on_edit_robot)
        btn_layout.addWidget(self.btn_edit_robot)
        
        self.btn_delete_robot = QPushButton("🗑️ Удалить")
        self.btn_delete_robot.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.btn_delete_robot.setEnabled(False)
        self.btn_delete_robot.clicked.connect(self._on_delete_robot)
        btn_layout.addWidget(self.btn_delete_robot)
        
        btn_layout.addStretch()
        
        self.btn_import = QPushButton("📥 Импорт")
        self.btn_import.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.btn_import.clicked.connect(self._on_import_robot)
        btn_layout.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("📤 Экспорт")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7d3c98;
            }
        """)
        self.btn_export.clicked.connect(self._on_export_robot)
        btn_layout.addWidget(self.btn_export)
        
        robots_layout.addLayout(btn_layout)
        robots_group.setLayout(robots_layout)
        layout.addWidget(robots_group)
        
        # ===== СТАТИСТИКА =====
        stats_group = QGroupBox("📊 Статистика")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        stats_layout = QHBoxLayout()
        
        # Метки статистики - яркий белый текст
        label_style = "color: #ffffff; font-size: 14px; font-weight: bold;"
        
        total_trades_label = QLabel("Всего сделок:")
        total_trades_label.setStyleSheet(label_style)
        stats_layout.addWidget(total_trades_label)
        
        self.lbl_total_trades = QLabel("0")
        self.lbl_total_trades.setFont(QFont("Arial", 16, QFont.Bold))
        self.lbl_total_trades.setStyleSheet("color: #ffffff;")
        stats_layout.addWidget(self.lbl_total_trades)

        profitable_label = QLabel("Прибыльных:")
        profitable_label.setStyleSheet(label_style)
        stats_layout.addWidget(profitable_label)

        self.lbl_profitable = QLabel("0")
        self.lbl_profitable.setFont(QFont("Arial", 16, QFont.Bold))
        self.lbl_profitable.setStyleSheet("color: #ffffff;")
        stats_layout.addWidget(self.lbl_profitable)

        win_rate_label = QLabel("Win Rate:")
        win_rate_label.setStyleSheet(label_style)
        stats_layout.addWidget(win_rate_label)

        self.lbl_win_rate = QLabel("0%")
        self.lbl_win_rate.setFont(QFont("Arial", 16, QFont.Bold))
        self.lbl_win_rate.setStyleSheet("color: #f39c12;")
        stats_layout.addWidget(self.lbl_win_rate)

        total_profit_label = QLabel("Общая прибыль:")
        total_profit_label.setStyleSheet(label_style)
        stats_layout.addWidget(total_profit_label)

        self.lbl_total_profit = QLabel("$0.00")
        self.lbl_total_profit.setFont(QFont("Arial", 16, QFont.Bold))
        self.lbl_total_profit.setStyleSheet("color: #2ecc71;")
        stats_layout.addWidget(self.lbl_total_profit)
        
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # ===== ЛОГИ =====
        logs_group = QGroupBox("📋 Логи")
        logs_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        logs_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a252f;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
            }
        """)
        logs_layout.addWidget(self.log_text)
        
        # Кнопки логов
        log_btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("🗑️ Очистить")
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        btn_clear.clicked.connect(lambda: self.log_text.clear())
        log_btn_layout.addWidget(btn_clear)
        
        log_btn_layout.addStretch()
        logs_group.setLayout(log_btn_layout)
        logs_group.setLayout(logs_layout)
        layout.addWidget(logs_group)
    
    def _load_robots(self):
        """Загрузка роботов в таблицу."""
        self.robots_table.setRowCount(0)
        
        robots = self.robot_manager.list()
        for robot in robots:
            row = self.robots_table.rowCount()
            self.robots_table.insertRow(row)
            
            # Название
            self.robots_table.setItem(row, 0, QTableWidgetItem(robot.name))
            
            # Статус
            status = "Остановлен"
            if robot.total_trades > 0:
                if robot.win_rate >= 60:
                    status = "🟢 Прибыльный"
                elif robot.win_rate >= 40:
                    status = "🟡 Средний"
                else:
                    status = "🔴 Убыточный"
            self.robots_table.setItem(row, 1, QTableWidgetItem(status))
            
            # Сделок
            self.robots_table.setItem(row, 2, QTableWidgetItem(str(robot.total_trades)))
            
            # Прибыль
            profit_str = f"${robot.total_profit:.2f}"
            if robot.total_profit > 0:
                profit_str = "✅ " + profit_str
            elif robot.total_profit < 0:
                profit_str = "❌ " + profit_str
            self.robots_table.setItem(row, 3, QTableWidgetItem(profit_str))
            
            # Win Rate
            win_rate_str = f"{robot.win_rate:.1f}%"
            self.robots_table.setItem(row, 4, QTableWidgetItem(win_rate_str))
        
        self._update_stats()
        self.log(f"Загружено {len(robots)} роботов")
    
    def _on_robot_selected(self):
        """Выбор робота в таблице."""
        selected_rows = self.robots_table.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            self._current_robot_index = row
            self.btn_edit_robot.setEnabled(True)
            self.btn_delete_robot.setEnabled(True)
        else:
            self._current_robot_index = -1
            self.btn_edit_robot.setEnabled(False)
            self.btn_delete_robot.setEnabled(False)

    def _on_add_robot(self):
        """Добавление робота."""
        dialog = RobotDialog(self)
        if dialog.exec() == QDialog.Accepted:
            robot = dialog.new_robot
            self.robot_manager.save(robot)
            self._load_robots()
            self.log(f"Добавлен робот: {robot.name}")
    
    def _on_edit_robot(self):
        """Редактирование робота."""
        if self._current_robot_index < 0:
            return
        
        robot_name = self.robots_table.item(self._current_robot_index, 0).text()
        robot = self.robot_manager.get(robot_name)
        
        if robot:
            dialog = RobotDialog(self, robot)
            if dialog.exec() == QDialog.Accepted:
                self.robot_manager.save(robot)
                self._load_robots()
                self.log(f"Обновлён робот: {robot.name}")
    
    def _on_delete_robot(self):
        """Удаление робота."""
        if self._current_robot_index < 0:
            return
        
        robot_name = self.robots_table.item(self._current_robot_index, 0).text()
        
        # Применяем тёмную тему к QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление")
        msg_box.setText(f"Удалить робота '{robot_name}'?")
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #2c3e50;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QPushButton {
                background-color: #3498db;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton#qt messagebox button no {
                background-color: #95a5a6;
            }
        """)
        
        reply = msg_box.exec()
        
        if reply == QMessageBox.Yes:
            self.robot_manager.delete(robot_name)
            self._load_robots()
            self.log(f"Удалён робот: {robot_name}")
    
    def _on_import_robot(self):
        """Импорт робота."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт робота",
            "",
            "JSON файлы (*.json)"
        )
        
        if filepath:
            robot = self.robot_manager.import_robot(filepath)
            if robot:
                self._load_robots()
                self.log(f"Импортирован робот: {robot.name}")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось импортировать робота!")
    
    def _on_export_robot(self):
        """Экспорт робота."""
        if self._current_robot_index < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите робота для экспорта!")
            return
        
        robot_name = self.robots_table.item(self._current_robot_index, 0).text()
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт робота",
            f"{robot_name}.json",
            "JSON файлы (*.json)"
        )
        
        if filepath:
            if self.robot_manager.export_robot(robot_name, filepath):
                self.log(f"Экспортирован робот: {robot_name}")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось экспортировать робота!")
    
    def _update_stats(self):
        """Обновление статистики."""
        robots = self.robot_manager.list()
        
        total_trades = sum(r.total_trades for r in robots)
        profitable_trades = sum(r.profitable_trades for r in robots)
        total_profit = sum(r.total_profit for r in robots)
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        self.lbl_total_trades.setText(str(total_trades))
        self.lbl_profitable.setText(str(profitable_trades))
        self.lbl_win_rate.setText(f"{win_rate:.1f}%")
        
        profit_str = f"${total_profit:.2f}"
        if total_profit > 0:
            self.lbl_total_profit.setStyleSheet("color: #2ecc71;")
        elif total_profit < 0:
            self.lbl_total_profit.setStyleSheet("color: #e74c3c;")
        self.lbl_total_profit.setText(profit_str)
    
    def update_balance(self, balance: float, is_demo: bool = True):
        """Обновление баланса."""
        if is_demo:
            self.lbl_demo_balance.setText(f"${balance:.2f}")
        else:
            self.lbl_real_balance.setText(f"${balance:.2f}")

    def update_candles(self, candles: list):
        """Обновление таблицы котировок."""
        self._current_candles = candles
        
        # Показываем последние 20 свечей
        recent_candles = candles[-20:] if len(candles) > 20 else candles
        
        self.quotes_table.setRowCount(len(recent_candles))
        
        for i, candle in enumerate(reversed(recent_candles)):
            from datetime import datetime
            time_str = datetime.fromtimestamp(candle["timestamp"]).strftime("%H:%M:%S")
            
            self.quotes_table.setItem(i, 0, QTableWidgetItem(time_str))
            self.quotes_table.setItem(i, 1, QTableWidgetItem(f"{candle['open']:.5f}"))
            self.quotes_table.setItem(i, 2, QTableWidgetItem(f"{candle['high']:.5f}"))
            self.quotes_table.setItem(i, 3, QTableWidgetItem(f"{candle['low']:.5f}"))
            self.quotes_table.setItem(i, 4, QTableWidgetItem(f"{candle['close']:.5f}"))
            
            change = candle['close'] - candle['open']
            change_item = QTableWidgetItem(f"{change:+.5f}")
            if change >= 0:
                change_item.setForeground(QColor("#2ecc71"))
            else:
                change_item.setForeground(QColor("#e74c3c"))
            self.quotes_table.setItem(i, 5, change_item)

    def log(self, message: str):
        """Логирование."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def start_balance_timer(self, callback):
        """Запуск таймера обновления баланса."""
        self.balance_timer = QTimer()
        self.balance_timer.timeout.connect(callback)
        self.balance_timer.start(5000)  # 5 секунд
        self.log("Запущено обновление баланса")
    
    def stop_balance_timer(self):
        """Остановка таймера."""
        if self.balance_timer:
            self.balance_timer.stop()
            self.log("Остановлено обновление баланса")


__all__ = ["TradingTab"]
