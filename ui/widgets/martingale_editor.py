"""
Редактор мартингейла.

Вкладка "Мартингейл" в конструкторе стратегий:
- Включение/выключение мартингейла
- Добавление шагов мартингейла
- Настройка каждого шага (множитель, экспирация, направление, действия)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QLabel, QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QScrollArea, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.strategy_models import MartingaleConfig, MartingaleStep


class MartingaleEditorWidget(QWidget):
    """
    Виджет редактирования мартингейла.
    """

    martingale_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.martingale = MartingaleConfig(enabled=False)
        self._init_ui()
        self.load_martingale(self.martingale)

    def _init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("📈 Мартингейл")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        # Включение мартингейла
        self.enabled_check = QCheckBox("Включить мартингейл")
        self.enabled_check.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self.enabled_check)

        # Сброс при выигрыше
        self.reset_on_win_check = QCheckBox("Сброс на шаг 1 после выигрыша")
        self.reset_on_win_check.setChecked(True)
        self.reset_on_win_check.stateChanged.connect(self._on_reset_on_win_changed)
        layout.addWidget(self.reset_on_win_check)

        # Скролл для шагов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setSpacing(10)

        scroll.setWidget(self.steps_container)
        layout.addWidget(scroll)

        # Кнопка добавления шага
        btn_add = QPushButton("➕ Добавить шаг")
        btn_add.clicked.connect(self._on_add_step)
        layout.addWidget(btn_add)

        layout.addStretch()

    def _on_enabled_changed(self, state):
        """Изменение состояния включения мартингейла."""
        self.martingale.enabled = (state == Qt.Checked)
        self.martingale_changed.emit(self.martingale)

    def _on_reset_on_win_changed(self, state):
        """Изменение состояния сброса при выигрыше."""
        self.martingale.reset_on_win = (state == Qt.Checked)
        self.martingale_changed.emit(self.martingale)

    def _on_add_step(self):
        """Добавление шага мартингейла."""
        step_number = len(self.martingale.steps) + 1
        new_step = MartingaleStep(
            step=step_number,
            ratio=2.0,
            min_profit=75,
            action_on_loss="new_asset",
            direction="previous",
            expiration=0,
            auto_ratio=True
        )
        self.martingale.steps.append(new_step)
        self._render_steps()
        self.martingale_changed.emit(self.martingale)

    def _on_remove_step(self, index: int):
        """Удаление шага мартингейла."""
        if 0 <= index < len(self.martingale.steps):
            del self.martingale.steps[index]
            # Перенумеровываем шаги
            for i, step in enumerate(self.martingale.steps):
                step.step = i + 1
            self._render_steps()
            self.martingale_changed.emit(self.martingale)

    def _on_step_changed(self, index: int, field: str, value):
        """Изменение параметра шага."""
        if 0 <= index < len(self.martingale.steps):
            step = self.martingale.steps[index]
            setattr(step, field, value)
            self.martingale_changed.emit(self.martingale)

    def _render_steps(self):
        """Перерисовка шагов мартингейла."""
        # Очищаем контейнер
        while self.steps_layout.count():
            item = self.steps_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Создаём виджеты для каждого шага
        for i, step in enumerate(self.martingale.steps):
            step_widget = self._create_step_widget(step, i)
            self.steps_layout.addWidget(step_widget)

        self.steps_layout.addStretch()

    def _create_step_widget(self, step: MartingaleStep, index: int) -> QFrame:
        """
        Создание виджета шага мартингейла.

        Args:
            step: Конфигурация шага
            index: Индекс шага

        Returns:
            QFrame с настройками шага
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QFormLayout(frame)

        # Заголовок
        title = QLabel(f"🔢 Шаг №{step.step}")
        title.setFont(QFont("Arial", 11, QFont.Bold))
        
        # Кнопка удаления
        btn_remove = QPushButton("❌ Удалить")
        btn_remove.clicked.connect(lambda: self._on_remove_step(index))
        
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(btn_remove)
        
        layout.addRow(header_widget)

        # Мин. прибыль
        min_profit_spin = QSpinBox()
        min_profit_spin.setRange(10, 99)
        min_profit_spin.setValue(step.min_profit)
        min_profit_spin.setSuffix("%")
        min_profit_spin.valueChanged.connect(
            lambda v: self._on_step_changed(index, "min_profit", v)
        )
        layout.addRow("Мин. прибыль:", min_profit_spin)

        # Множитель
        ratio_spin = QDoubleSpinBox()
        ratio_spin.setRange(1.0, 10.0)
        ratio_spin.setDecimals(1)
        ratio_spin.setValue(step.ratio)
        ratio_spin.valueChanged.connect(
            lambda v: self._on_step_changed(index, "ratio", v)
        )
        layout.addRow("Множитель:", ratio_spin)

        # Авто-расчёт коэффициента
        auto_ratio_check = QCheckBox("Авто-расчёт")
        auto_ratio_check.setChecked(step.auto_ratio)
        auto_ratio_check.stateChanged.connect(
            lambda s: self._on_step_changed(index, "auto_ratio", s == Qt.Checked)
        )
        layout.addRow("", auto_ratio_check)

        # Экспирация
        expiration_spin = QSpinBox()
        expiration_spin.setRange(0, 14400)
        expiration_spin.setValue(step.expiration)
        expiration_spin.setSpecialValueText("Как в регламенте")
        expiration_spin.setSuffix(" сек")
        expiration_spin.valueChanged.connect(
            lambda v: self._on_step_changed(index, "expiration", v)
        )
        layout.addRow("Экспирация:", expiration_spin)

        # Направление
        direction_combo = QComboBox()
        direction_combo.addItem("Как предыдущая", "previous")
        direction_combo.addItem("Противоположное", "opposite")
        direction_combo.addItem("CALL", "call")
        direction_combo.addItem("PUT", "put")
        
        idx = direction_combo.findData(step.direction)
        if idx >= 0:
            direction_combo.setCurrentIndex(idx)
        
        direction_combo.currentIndexChanged.connect(
            lambda i: self._on_step_changed(index, "direction", direction_combo.currentData())
        )
        layout.addRow("Направление:", direction_combo)

        # Действие при проигрыше
        action_combo = QComboBox()
        action_combo.addItem("Перейти на новый актив", "new_asset")
        action_combo.addItem("Продолжить", "continue")
        action_combo.addItem("Остановить", "stop")
        
        idx = action_combo.findData(step.action_on_loss)
        if idx >= 0:
            action_combo.setCurrentIndex(idx)
        
        action_combo.currentIndexChanged.connect(
            lambda i: self._on_step_changed(index, "action_on_loss", action_combo.currentData())
        )
        layout.addRow("Действие при проигрыше:", action_combo)

        return frame

    def load_martingale(self, martingale: MartingaleConfig):
        """
        Загрузка мартингейла.

        Args:
            martingale: MartingaleConfig
        """
        self.martingale = martingale
        
        # Включение
        self.enabled_check.setChecked(martingale.enabled)
        
        # Сброс при выигрыше
        self.reset_on_win_check.setChecked(martingale.reset_on_win)
        
        # Шаги
        self._render_steps()

    def get_martingale(self) -> MartingaleConfig:
        """
        Получение мартингейла.

        Returns:
            MartingaleConfig
        """
        # Обновляем max_steps
        self.martingale.max_steps = len(self.martingale.steps)
        return self.martingale


__all__ = ["MartingaleEditorWidget"]
