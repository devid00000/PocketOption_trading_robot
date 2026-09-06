"""
Диалог создания/редактирования робота.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QTextEdit, QDoubleSpinBox, QSpinBox, QComboBox,
    QPushButton, QLabel, QCheckBox, QTabWidget, QWidget, QMessageBox,
    QFileDialog, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.models import RobotConfig, StrategySettings, MartingaleLevel
from core.strategies.base import list_strategies


class RobotDialog(QDialog):
    """Диалог создания/редактирования робота."""
    
    def __init__(self, parent=None, robot: RobotConfig = None):
        super().__init__(parent)
        
        self.robot = robot
        self.is_edit = robot is not None
        
        self._init_ui()
        
        if self.is_edit:
            self._load_robot()
    
    def _init_ui(self):
        """Инициализация интерфейса."""
        self.setWindowTitle("➕ Новый робот" if not self.is_edit else "✏️ Редактировать робота")
        self.setMinimumSize(800, 700)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a252f;
            }
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
            QLabel {
                color: #ecf0f1;
                font-size: 13px;
            }
            QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 3px;
                padding: 5px;
                font-size: 13px;
            }
            QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {
                border: 2px solid #3498db;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
            QCheckBox {
                color: #ecf0f1;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QTabWidget::pane {
                border: 2px solid #34495e;
                background-color: #2c3e50;
            }
            QTabBar::tab {
                background-color: #1a252f;
                color: #ecf0f1;
                padding: 10px 20px;
                border: 2px solid #34495e;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #34495e;
            }
        """)
        
        # Основной layout
        main_layout = QVBoxLayout(self)
        
        # Создаём вкладки
        tabs = QTabWidget()
        
        # Вкладка 1: Основное
        self.main_tab = self._create_main_tab()
        tabs.addTab(self.main_tab, "📝 Основное")
        
        # Вкладка 2: Стратегия
        self.strategy_tab = self._create_strategy_tab()
        tabs.addTab(self.strategy_tab, "📈 Стратегия")
        
        # Вкладка 3: Мартингейл
        self.martingale_tab = self._create_martingale_tab()
        tabs.addTab(self.martingale_tab, "💰 Мартингейл")
        
        # Вкладка 4: Ограничения
        self.limits_tab = self._create_limits_tab()
        tabs.addTab(self.limits_tab, "⚠️ Ограничения")
        
        main_layout.addWidget(tabs)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("💾 Сохранить")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("❌ Отмена")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        main_layout.addLayout(btn_layout)
    
    def _create_main_tab(self) -> QWidget:
        """Вкладка 'Основное'."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setSpacing(10)
        
        # Название
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Например: RSI Агрессив")
        layout.addRow("Название:", self.edit_name)
        
        # Описание
        self.edit_description = QTextEdit()
        self.edit_description.setMaximumHeight(80)
        self.edit_description.setPlaceholderText("Описание робота...")
        layout.addRow("Описание:", self.edit_description)
        
        # Актив
        self.combo_asset = QComboBox()
        self.combo_asset.setEditable(True)
        popular_assets = [
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
            "USDCAD_otc", "USDCHF_otc", "BTCUSD_otc", "ETHUSD_otc"
        ]
        self.combo_asset.addItems(popular_assets)
        layout.addRow("Актив:", self.combo_asset)
        
        # Сумма
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(1, 10000)
        self.spin_amount.setValue(1.0)
        self.spin_amount.setSuffix(" $")
        layout.addRow("Сумма сделки:", self.spin_amount)
        
        # Длительность
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(5, 3600)
        self.spin_duration.setValue(60)
        self.spin_duration.setSuffix(" сек")
        layout.addRow("Длительность сделки:", self.spin_duration)
        
        # Интервал
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(10, 3600)
        self.spin_interval.setValue(30)
        self.spin_interval.setSuffix(" сек")
        layout.addRow("Интервал между сделками:", self.spin_interval)
        
        # Макс. сделок
        self.spin_max_trades = QSpinBox()
        self.spin_max_trades.setRange(0, 10000)
        self.spin_max_trades.setValue(0)
        self.spin_max_trades.setSpecialValueText("Без лимита")
        layout.addRow("Макс. сделок:", self.spin_max_trades)
        
        return widget
    
    def _create_strategy_tab(self) -> QWidget:
        """Вкладка 'Стратегия'."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Выбор стратегии
        form_layout = QFormLayout()
        
        self.combo_strategy = QComboBox()
        strategies = list_strategies()
        for strat in strategies:
            self.combo_strategy.addItem(f"{strat['name']} - {strat['description']}", strat['id'])
        self.combo_strategy.currentIndexChanged.connect(self._on_strategy_changed)
        form_layout.addRow("Стратегия:", self.combo_strategy)
        
        layout.addLayout(form_layout)
        
        # Настройки стратегии (будут заполняться динамически)
        self.strategy_settings_widget = QWidget()
        self.strategy_settings_layout = QFormLayout(self.strategy_settings_widget)
        layout.addWidget(self.strategy_settings_widget)
        
        layout.addStretch()
        
        # Загружаем настройки первой стратегии
        self._on_strategy_changed(0)
        
        return widget
    
    def _create_martingale_tab(self) -> QWidget:
        """Вкладка 'Мартингейл'."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Чекбокс использования
        self.check_martingale = QCheckBox("✓ Использовать мартингейл")
        self.check_martingale.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.check_martingale)
        
        # Уровни (упрощённо)
        form_layout = QFormLayout()
        
        # Уровень 1
        group1 = QGroupBox("Уровень 1")
        layout1 = QFormLayout(group1)
        
        self.spin_m1_profit = QSpinBox()
        self.spin_m1_profit.setRange(10, 99)
        self.spin_m1_profit.setValue(75)
        self.spin_m1_profit.setSuffix(" %")
        layout1.addRow("Мин. прибыль:", self.spin_m1_profit)
        
        self.spin_m1_multiplier = QDoubleSpinBox()
        self.spin_m1_multiplier.setRange(1.0, 10.0)
        self.spin_m1_multiplier.setValue(2.0)
        self.spin_m1_multiplier.setSuffix(" x")
        layout1.addRow("Множитель:", self.spin_m1_multiplier)
        
        form_layout.addRow(group1)
        
        # Уровень 2
        group2 = QGroupBox("Уровень 2")
        layout2 = QFormLayout(group2)
        
        self.spin_m2_profit = QSpinBox()
        self.spin_m2_profit.setRange(10, 99)
        self.spin_m2_profit.setValue(60)
        self.spin_m2_profit.setSuffix(" %")
        layout2.addRow("Мин. прибыль:", self.spin_m2_profit)
        
        self.spin_m2_multiplier = QDoubleSpinBox()
        self.spin_m2_multiplier.setRange(1.0, 10.0)
        self.spin_m2_multiplier.setValue(2.5)
        self.spin_m2_multiplier.setSuffix(" x")
        layout2.addRow("Множитель:", self.spin_m2_multiplier)
        
        form_layout.addRow(group2)
        
        # Уровень 3
        group3 = QGroupBox("Уровень 3")
        layout3 = QFormLayout(group3)
        
        self.spin_m3_profit = QSpinBox()
        self.spin_m3_profit.setRange(10, 99)
        self.spin_m3_profit.setValue(60)
        self.spin_m3_profit.setSuffix(" %")
        layout3.addRow("Мин. прибыль:", self.spin_m3_profit)
        
        self.spin_m3_multiplier = QDoubleSpinBox()
        self.spin_m3_multiplier.setRange(1.0, 10.0)
        self.spin_m3_multiplier.setValue(3.0)
        self.spin_m3_multiplier.setSuffix(" x")
        layout3.addRow("Множитель:", self.spin_m3_multiplier)
        
        form_layout.addRow(group3)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        return widget
    
    def _create_limits_tab(self) -> QWidget:
        """Вкладка 'Ограничения'."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setSpacing(10)
        
        # Стоп-лосс
        self.spin_stop_loss = QDoubleSpinBox()
        self.spin_stop_loss.setRange(0, 10000)
        self.spin_stop_loss.setValue(0)
        self.spin_stop_loss.setSuffix(" $")
        self.spin_stop_loss.setSpecialValueText("Отключен")
        layout.addRow("Стоп-лосс:", self.spin_stop_loss)
        
        # Тейк-профит
        self.spin_take_profit = QDoubleSpinBox()
        self.spin_take_profit.setRange(0, 10000)
        self.spin_take_profit.setValue(0)
        self.spin_take_profit.setSuffix(" $")
        self.spin_take_profit.setSpecialValueText("Отключен")
        layout.addRow("Тейк-профит:", self.spin_take_profit)
        
        # Время работы
        time_layout = QHBoxLayout()
        
        self.edit_time_from = QLineEdit("00:00")
        self.edit_time_from.setFixedWidth(80)
        time_layout.addWidget(self.edit_time_from)
        time_layout.addWidget(QLabel("до"))
        self.edit_time_to = QLineEdit("23:59")
        self.edit_time_to.setFixedWidth(80)
        time_layout.addWidget(self.edit_time_to)
        
        layout.addRow("Время работы:", time_layout)
        
        # Дни недели
        days_layout = QHBoxLayout()
        self.check_days = []
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for i, day in enumerate(days):
            check = QCheckBox(day)
            check.setChecked(True)  # По умолчанию все дни
            self.check_days.append(check)
            days_layout.addWidget(check)
        
        layout.addRow("Дни недели:", days_layout)
        
        return widget
    
    def _on_strategy_changed(self, index: int):
        """Изменение стратегии."""
        # Очищаем настройки
        while self.strategy_settings_layout.count():
            item = self.strategy_settings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Получаем ID стратегии
        strategy_id = self.combo_strategy.currentData()
        
        # TODO: Загрузить настройки для выбранной стратегии
        # Пока заглушка
        label = QLabel(f"Настройки для стратегии: {strategy_id}")
        self.strategy_settings_layout.addRow(label)
    
    def _load_robot(self):
        """Загрузка данных робота."""
        if not self.robot:
            return
        
        # Основное
        self.edit_name.setText(self.robot.name)
        self.edit_description.setText(self.robot.description)
        self.combo_asset.setCurrentText(self.robot.asset_id)
        self.spin_amount.setValue(self.robot.amount)
        self.spin_duration.setValue(self.robot.duration)
        self.spin_interval.setValue(self.robot.interval)
        self.spin_max_trades.setValue(self.robot.max_trades)
        
        # Матингейл
        self.check_martingale.setChecked(self.robot.use_martingale)
        if self.robot.martingale_levels:
            for i, level in enumerate(self.robot.martingale_levels[:3]):
                if i == 0:
                    self.spin_m1_profit.setValue(level.min_profit)
                    self.spin_m1_multiplier.setValue(level.multiplier)
                elif i == 1:
                    self.spin_m2_profit.setValue(level.min_profit)
                    self.spin_m2_multiplier.setValue(level.multiplier)
                elif i == 2:
                    self.spin_m3_profit.setValue(level.min_profit)
                    self.spin_m3_multiplier.setValue(level.multiplier)
        
        # Ограничения
        self.spin_stop_loss.setValue(self.robot.stop_loss)
        self.spin_take_profit.setValue(self.robot.take_profit)
        self.edit_time_from.setText(self.robot.time_from)
        self.edit_time_to.setText(self.robot.time_to)
    
    def _on_save(self):
        """Сохранение робота."""
        # Проверка названия
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название робота!")
            return
        
        # Создаём или обновляем
        if self.is_edit:
            # Обновление
            self.robot.name = name
            self.robot.description = self.edit_description.toPlainText().strip()
            self.robot.asset_id = self.combo_asset.currentText()
            self.robot.amount = self.spin_amount.value()
            self.robot.duration = self.spin_duration.value()
            self.robot.interval = self.spin_interval.value()
            self.robot.max_trades = self.spin_max_trades.value()
            
            # Мартингейл
            self.robot.use_martingale = self.check_martingale.isChecked()
            if self.robot.use_martingale:
                self.robot.martingale_levels = [
                    MartingaleLevel(self.spin_m1_profit.value(), self.spin_m1_multiplier.value(), "continue"),
                    MartingaleLevel(self.spin_m2_profit.value(), self.spin_m2_multiplier.value(), "continue"),
                    MartingaleLevel(self.spin_m3_profit.value(), self.spin_m3_multiplier.value(), "stop")
                ]
            
            # Ограничения
            self.robot.stop_loss = self.spin_stop_loss.value()
            self.robot.take_profit = self.spin_take_profit.value()
            self.robot.time_from = self.edit_time_from.text()
            self.robot.time_to = self.edit_time_to.text()
            
            self.accept()
        else:
            # Создание нового
            strategy_id = self.combo_strategy.currentData()
            
            robot = RobotConfig(
                name=name,
                description=self.edit_description.toPlainText().strip(),
                asset_id=self.combo_asset.currentText(),
                amount=self.spin_amount.value(),
                duration=self.spin_duration.value(),
                interval=self.spin_interval.value(),
                max_trades=self.spin_max_trades.value(),
                strategy=StrategySettings(strategy_type=strategy_id),
                use_martingale=self.check_martingale.isChecked(),
                stop_loss=self.spin_stop_loss.value(),
                take_profit=self.spin_take_profit.value(),
                time_from=self.edit_time_from.text(),
                time_to=self.edit_time_to.text()
            )
            
            if self.check_martingale.isChecked():
                robot.martingale_levels = [
                    MartingaleLevel(self.spin_m1_profit.value(), self.spin_m1_multiplier.value(), "continue"),
                    MartingaleLevel(self.spin_m2_profit.value(), self.spin_m2_multiplier.value(), "continue"),
                    MartingaleLevel(self.spin_m3_profit.value(), self.spin_m3_multiplier.value(), "stop")
                ]
            
            # Возвращаем робота
            self.new_robot = robot
            self.accept()
    
    @classmethod
    def create_robot(cls, parent=None) -> RobotConfig:
        """Создание нового робота (удобный метод)."""
        dialog = cls(parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.new_robot
        return None


__all__ = ["RobotDialog"]
