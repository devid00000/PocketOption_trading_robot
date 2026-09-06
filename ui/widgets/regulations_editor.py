"""
Редактор регламента.

Вкладка "Регламент" в конструкторе стратегий:
- Режим работы (торговля/сигналы)
- Время работы
- Дни недели
- Мин. доходность
- Экспирация
- Ставка
- Стоп-лосс / Тейк-профит
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QTimeEdit, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QFont

from core.strategy_models import RegulationsConfig


class RegulationsEditorWidget(QWidget):
    """
    Виджет редактирования регламента.
    """

    regulations_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.regulations = RegulationsConfig()
        self._init_ui()
        self.load_regulations(self.regulations)

    def _init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("📋 Регламент работы")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        # Основная группа
        main_group = self._create_main_group()
        layout.addWidget(main_group)

        # Группа ограничений
        limits_group = self._create_limits_group()
        layout.addWidget(limits_group)

        layout.addStretch()

    def _create_main_group(self) -> QGroupBox:
        """Группа основных настроек."""
        group = QGroupBox("Основные настройки")
        layout = QFormLayout(group)

        # Режим работы
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Торговля", "trade")
        self.mode_combo.addItem("Только сигналы", "signals")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addRow("Режим работы:", self.mode_combo)

        # Время работы (от)
        self.time_from = QTimeEdit()
        self.time_from.setTime(QTime(0, 0))
        self.time_from.setDisplayFormat("HH:mm")
        self.time_from.timeChanged.connect(self._on_time_changed)
        layout.addRow("Время начала:", self.time_from)

        # Время работы (до)
        self.time_to = QTimeEdit()
        self.time_to.setTime(QTime(23, 59))
        self.time_to.setDisplayFormat("HH:mm")
        self.time_to.timeChanged.connect(self._on_time_changed)
        layout.addRow("Время окончания:", self.time_to)

        # Дни недели
        days_widget = QWidget()
        days_layout = QHBoxLayout(days_widget)
        days_layout.setContentsMargins(0, 0, 0, 0)
        
        self.day_checkboxes = {}
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for i, name in enumerate(day_names):
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.setProperty("day", i)
            cb.stateChanged.connect(self._on_days_changed)
            days_layout.addWidget(cb)
            self.day_checkboxes[i] = cb
        
        layout.addRow("Дни недели:", days_widget)

        # Мин. доходность
        self.min_profit_spin = QSpinBox()
        self.min_profit_spin.setRange(1, 99)
        self.min_profit_spin.setValue(85)
        self.min_profit_spin.setSuffix("%")
        self.min_profit_spin.valueChanged.connect(self._on_min_profit_changed)
        layout.addRow("Мин. доходность:", self.min_profit_spin)

        # Экспирация
        self.expiration_spin = QSpinBox()
        self.expiration_spin.setRange(5, 14400)
        self.expiration_spin.setValue(60)
        self.expiration_spin.setSuffix(" сек")
        self.expiration_spin.valueChanged.connect(self._on_expiration_changed)
        layout.addRow("Экспирация:", self.expiration_spin)

        # Ставка
        self.bet_spin = QDoubleSpinBox()
        self.bet_spin.setRange(0.5, 5000.0)
        self.bet_spin.setValue(1.0)
        self.bet_spin.setDecimals(2)
        self.bet_spin.setPrefix("$ ")
        self.bet_spin.valueChanged.connect(self._on_bet_changed)
        layout.addRow("Ставка:", self.bet_spin)

        # Макс. одновременных сделок
        self.max_trades_spin = QSpinBox()
        self.max_trades_spin.setRange(1, 10)
        self.max_trades_spin.setValue(1)
        self.max_trades_spin.valueChanged.connect(self._on_max_trades_changed)
        layout.addRow("Макс. сделок:", self.max_trades_spin)

        return group

    def _create_limits_group(self) -> QGroupBox:
        """Группа ограничений."""
        group = QGroupBox("Ограничения")
        layout = QFormLayout(group)

        # Стоп-лосс
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setRange(0, 10000)
        self.stop_loss_spin.setValue(0)
        self.stop_loss_spin.setPrefix("$ ")
        self.stop_loss_spin.valueChanged.connect(self._on_stop_loss_changed)
        layout.addRow("Стоп-лосс:", self.stop_loss_spin)

        # Стоп-лосс активен
        self.stop_loss_check = QCheckBox("Активен")
        self.stop_loss_check.stateChanged.connect(self._on_stop_loss_check_changed)
        layout.addRow("", self.stop_loss_check)

        # Тейк-профит
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setRange(0, 10000)
        self.take_profit_spin.setValue(0)
        self.take_profit_spin.setPrefix("$ ")
        self.take_profit_spin.valueChanged.connect(self._on_take_profit_changed)
        layout.addRow("Тейк-профит:", self.take_profit_spin)

        # Тейк-профит активен
        self.take_profit_check = QCheckBox("Активен")
        self.take_profit_check.stateChanged.connect(self._on_take_profit_check_changed)
        layout.addRow("", self.take_profit_check)

        return group

    # ==========================================================================
    # ОБРАБОТЧИКИ СОБЫТИЙ
    # ==========================================================================

    def _on_mode_changed(self):
        """Изменение режима работы."""
        idx = self.mode_combo.currentIndex()
        self.regulations.mode = self.mode_combo.currentData()
        self.regulations_changed.emit(self.regulations)

    def _on_time_changed(self):
        """Изменение времени работы."""
        self.regulations.time_from = self.time_from.time().toString("HH:mm")
        self.regulations.time_to = self.time_to.time().toString("HH:mm")
        self.regulations_changed.emit(self.regulations)

    def _on_days_changed(self):
        """Изменение дней недели."""
        work_days = []
        for day, cb in self.day_checkboxes.items():
            if cb.isChecked():
                work_days.append(day)
        self.regulations.work_days = work_days
        self.regulations_changed.emit(self.regulations)

    def _on_min_profit_changed(self, value: int):
        """Изменение мин. доходности."""
        self.regulations.min_profit = value
        self.regulations_changed.emit(self.regulations)

    def _on_expiration_changed(self, value: int):
        """Изменение экспирации."""
        self.regulations.expiration = value
        self.regulations_changed.emit(self.regulations)

    def _on_bet_changed(self, value: float):
        """Изменение ставки."""
        self.regulations.bet = value
        self.regulations_changed.emit(self.regulations)

    def _on_max_trades_changed(self, value: int):
        """Изменение макс. количества сделок."""
        self.regulations.max_bets = value
        self.regulations.max_active_trades = value
        self.regulations_changed.emit(self.regulations)

    def _on_stop_loss_changed(self, value: float):
        """Изменение стоп-лосса."""
        self.regulations.stop_loss = value
        if value > 0:
            self.stop_loss_check.setChecked(True)
        self.regulations_changed.emit(self.regulations)

    def _on_stop_loss_check_changed(self, state):
        """Изменение состояния стоп-лосса."""
        self.regulations.stop_on_loss = (state == Qt.Checked)
        self.regulations_changed.emit(self.regulations)

    def _on_take_profit_changed(self, value: float):
        """Изменение тейк-профита."""
        self.regulations.take_profit = value
        if value > 0:
            self.take_profit_check.setChecked(True)
        self.regulations_changed.emit(self.regulations)

    def _on_take_profit_check_changed(self, state):
        """Изменение состояния тейк-профита."""
        self.regulations.stop_on_profit = (state == Qt.Checked)
        self.regulations_changed.emit(self.regulations)

    # ==========================================================================
    # ЗАГРУЗКА/ПОЛУЧЕНИЕ ДАННЫХ
    # ==========================================================================

    def load_regulations(self, regulations: RegulationsConfig):
        """
        Загрузка регламента.

        Args:
            regulations: RegulationsConfig
        """
        self.regulations = regulations

        # Режим
        idx = self.mode_combo.findData(regulations.mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

        # Время
        self.time_from.setTime(QTime.fromString(regulations.time_from, "HH:mm"))
        self.time_to.setTime(QTime.fromString(regulations.time_to, "HH:mm"))

        # Дни недели
        for day, cb in self.day_checkboxes.items():
            cb.setChecked(day in regulations.work_days)

        # Мин. доходность
        self.min_profit_spin.setValue(regulations.min_profit)

        # Экспирация
        self.expiration_spin.setValue(regulations.expiration)

        # Ставка
        self.bet_spin.setValue(regulations.bet)

        # Макс. сделок
        self.max_trades_spin.setValue(regulations.max_bets)

        # Стоп-лосс
        self.stop_loss_spin.setValue(regulations.stop_loss)
        self.stop_loss_check.setChecked(regulations.stop_on_loss)

        # Тейк-профит
        self.take_profit_spin.setValue(regulations.take_profit)
        self.take_profit_check.setChecked(regulations.stop_on_profit)

    def get_regulations(self) -> RegulationsConfig:
        """
        Получение регламента.

        Returns:
            RegulationsConfig
        """
        return self.regulations


__all__ = ["RegulationsEditorWidget"]
