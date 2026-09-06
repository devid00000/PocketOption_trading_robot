"""
Редактор индикаторов.

Вкладка "Индикаторы" в конструкторе стратегий:
- Список доступных индикаторов
- Добавление индикаторов
- Настройка параметров каждого индикатора
- Настройка условий сигналов
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QScrollArea,
    QFrame, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QLineEdit, QCheckBox, QSplitter, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.strategy_models import IndicatorConfig
from strategies.indicator_registry import IndicatorRegistry


# Конфигурация параметров для каждого типа индикатора
INDICATOR_PARAMETERS = {
    "rsi": [
        {"id": "period", "name": "Период RSI", "type": "spin", "default": 14, "min": 2, "max": 90},
        {"id": "overbought", "name": "Ур. перекупленности", "type": "spin", "default": 70, "min": 50, "max": 100},
        {"id": "oversold", "name": "Ур. перепроданности", "type": "spin", "default": 30, "min": 0, "max": 50},
        {"id": "price_type", "name": "Тип цены", "type": "combo", "values": ["close", "open", "high", "low"]},
    ],
    "bollinger": [
        {"id": "period", "name": "Период", "type": "spin", "default": 20, "min": 2, "max": 100},
        {"id": "std_dev", "name": "Стд. отклонение", "type": "double", "default": 2.0, "min": 0.5, "max": 5.0},
        {"id": "price_type", "name": "Тип цены", "type": "combo", "values": ["close", "open", "high", "low"]},
    ],
    "macd": [
        {"id": "fast_period", "name": "Быстрый период", "type": "spin", "default": 12, "min": 2, "max": 50},
        {"id": "slow_period", "name": "Медленный период", "type": "spin", "default": 26, "min": 2, "max": 100},
        {"id": "signal_period", "name": "Период сигнала", "type": "spin", "default": 9, "min": 2, "max": 50},
    ],
    "stochastic": [
        {"id": "k_period", "name": "Период %K", "type": "spin", "default": 14, "min": 2, "max": 50},
        {"id": "d_period", "name": "Период %D", "type": "spin", "default": 3, "min": 1, "max": 20},
        {"id": "slowdown", "name": "Замедление", "type": "spin", "default": 3, "min": 1, "max": 10},
        {"id": "overbought", "name": "Ур. перекупленности", "type": "spin", "default": 80, "min": 50, "max": 100},
        {"id": "oversold", "name": "Ур. перепроданности", "type": "spin", "default": 20, "min": 0, "max": 50},
    ],
    "cci": [
        {"id": "period", "name": "Период", "type": "spin", "default": 20, "min": 2, "max": 100},
        {"id": "overbought", "name": "Ур. перекупленности", "type": "spin", "default": 100, "min": 50, "max": 200},
        {"id": "oversold", "name": "Ур. перепроданности", "type": "spin", "default": -100, "min": -200, "max": -50},
    ],
    "parabolic_sar": [
        {"id": "step", "name": "Шаг ускорения", "type": "double", "default": 0.02, "min": 0.01, "max": 0.1},
        {"id": "max_step", "name": "Макс. шаг", "type": "double", "default": 0.2, "min": 0.1, "max": 0.5},
    ],
    "super_trend": [
        {"id": "period", "name": "Период ATR", "type": "spin", "default": 10, "min": 2, "max": 50},
        {"id": "multiplier", "name": "Множитель", "type": "double", "default": 3.0, "min": 1.0, "max": 10.0},
    ],
    "two_ma": [
        {"id": "one_ma_period", "name": "Период быстрой MA", "type": "spin", "default": 5, "min": 1, "max": 50},
        {"id": "one_ma_method", "name": "Метод быстрой MA", "type": "combo", "values": ["sma", "ema", "wma"]},
        {"id": "to_ma_period", "name": "Период медленной MA", "type": "spin", "default": 15, "min": 1, "max": 100},
        {"id": "to_ma_method", "name": "Метод медленной MA", "type": "combo", "values": ["sma", "ema", "wma"]},
    ],
    "candle": [
        {"id": "num_candles", "name": "Количество свечей", "type": "spin", "default": 2, "min": 1, "max": 10},
        {"id": "type_candle", "name": "Тип комбинации", "type": "combo", "values": ["repeat", "alternate"]},
        {"id": "min_size_bar", "name": "Мин. размер свечи", "type": "spin", "default": 2, "min": 0, "max": 1000},
        {"id": "max_size_bar", "name": "Макс. размер свечи", "type": "spin", "default": 100, "min": 1, "max": 5000},
    ],
}

# Условия сигналов для каждого типа индикатора
INDICATOR_CONDITIONS = {
    "rsi": {
        "call": [
            ("valRsi<btl", "RSI < перепроданность"),
            ("valRsi>tpl", "RSI > перекупленность"),
            ("valRsi<tpl and valRsi>btl", "RSI в умеренной зоне"),
        ],
        "sell": [
            ("valRsi>tpl", "RSI > перекупленность"),
            ("valRsi<btl", "RSI < перепроданность"),
            ("valRsi<tpl and valRsi>btl", "RSI в умеренной зоне"),
        ]
    },
    "bollinger": {
        "call": [
            ("price<lower", "Цена ниже нижней полосы"),
            ("price>upper", "Цена выше верхней полосы"),
            ("price>middle", "Цена выше средней"),
        ],
        "sell": [
            ("price>upper", "Цена выше верхней полосы"),
            ("price<lower", "Цена ниже нижней полосы"),
            ("price<middle", "Цена ниже средней"),
        ]
    },
    "macd": {
        "call": [
            ("macd>signal", "MACD > Signal"),
            ("macd>0", "MACD > 0"),
            ("macd>signal and macd>0", "MACD > Signal и > 0"),
        ],
        "sell": [
            ("macd<signal", "MACD < Signal"),
            ("macd<0", "MACD < 0"),
            ("macd<signal and macd<0", "MACD < Signal и < 0"),
        ]
    },
    "two_ma": {
        "call": [
            ("onema>toma", "Быстрая MA > медленной"),
            ("onema<toma", "Быстрая MA < медленной"),
        ],
        "sell": [
            ("onema<toma", "Быстрая MA < медленной"),
            ("onema>toma", "Быстрая MA > медленной"),
        ]
    },
    "candle": {
        "call": [
            ("lastdir=='up'", "Последняя свеча вверх"),
            ("lastdir=='down'", "Последняя свеча вниз"),
        ],
        "sell": [
            ("lastdir=='down'", "Последняя свеча вниз"),
            ("lastdir=='up'", "Последняя свеча вверх"),
        ]
    },
}


class IndicatorEditorWidget(QWidget):
    """
    Виджет редактирования индикаторов.
    """

    indicators_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.indicators = []
        self._init_ui()
        self._load_available_indicators()

    def _init_ui(self):
        """Инициализация интерфейса."""
        layout = QHBoxLayout(self)

        # Левая панель: список доступных индикаторов
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel, 1)

        # Правая панель: список добавленных индикаторов с настройками
        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, 2)

    def _create_left_panel(self) -> QWidget:
        """Левая панель с доступными индикаторами."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Заголовок
        title = QLabel("Доступные индикаторы")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)

        # Список индикаторов
        self.available_list = QListWidget()
        self.available_list.doubleClicked.connect(self._on_add_indicator)
        layout.addWidget(self.available_list)

        # Кнопка добавления
        btn_add = QPushButton("➕ Добавить")
        btn_add.clicked.connect(self._on_add_indicator)
        layout.addWidget(btn_add)

        return widget

    def _create_right_panel(self) -> QWidget:
        """Правая панель с добавленными индикаторами."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Заголовок
        title = QLabel("Добавленные индикаторы")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)

        # Скролл для индикаторов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.indicators_container = QWidget()
        self.indicators_layout = QVBoxLayout(self.indicators_container)
        self.indicators_layout.setSpacing(10)

        scroll.setWidget(self.indicators_container)
        layout.addWidget(scroll)

        return widget

    def _load_available_indicators(self):
        """Загрузка списка доступных индикаторов."""
        info_list = IndicatorRegistry.list_with_info()
        
        for info in info_list:
            item = QListWidgetItem(f"{info['display_name']}\n{info['description'][:50]}...")
            item.setData(Qt.UserRole, info['name'])
            self.available_list.addItem(item)

    def _on_add_indicator(self):
        """Добавление индикатора."""
        current_item = self.available_list.currentItem()
        if not current_item:
            return

        indicator_type = current_item.data(Qt.UserRole)
        
        # Создаём конфигурацию
        config = IndicatorConfig(
            type=indicator_type,
            name=indicator_type.title(),
            timeframe=60,
            bar_index=0
        )

        # Добавляем в список
        self.indicators.append(config)
        self._render_indicators()
        self.indicators_changed.emit(self.indicators)

    def _render_indicators(self):
        """Перерисовка списка индикаторов."""
        # Очищаем контейнер
        while self.indicators_layout.count():
            item = self.indicators_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Создаём виджеты для каждого индикатора
        for i, config in enumerate(self.indicators):
            indicator_widget = self._create_indicator_widget(config, i)
            self.indicators_layout.addWidget(indicator_widget)

        self.indicators_layout.addStretch()

    def _create_indicator_widget(self, config: IndicatorConfig, index: int) -> QFrame:
        """
        Создание виджета индикатора.

        Args:
            config: Конфигурация индикатора
            index: Индекс в списке

        Returns:
            QFrame с настройками индикатора
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout(frame)

        # Заголовок
        header_layout = QHBoxLayout()
        
        title = QLabel(f"📊 {config.name} ({config.type})")
        title.setFont(QFont("Arial", 11, QFont.Bold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Кнопка удаления
        btn_remove = QPushButton("❌ Удалить")
        btn_remove.clicked.connect(lambda: self._on_remove_indicator(index))
        header_layout.addWidget(btn_remove)

        layout.addLayout(header_layout)

        # Параметры
        params_group = QGroupBox("Параметры")
        params_layout = QFormLayout(params_group)

        # Таймфрейм
        tf_spin = QSpinBox()
        tf_spin.setRange(5, 86400)
        tf_spin.setValue(config.timeframe)
        tf_spin.setSuffix("s")
        tf_spin.valueChanged.connect(lambda v: setattr(config, 'timeframe', v))
        params_layout.addRow("Таймфрейм:", tf_spin)

        # Бар для проверки
        bar_spin = QSpinBox()
        bar_spin.setRange(-100, 0)
        bar_spin.setValue(config.bar_index)
        bar_spin.valueChanged.connect(lambda v: setattr(config, 'bar_index', v))
        params_layout.addRow("Номер бара:", bar_spin)

        # Параметры индикатора
        params = INDICATOR_PARAMETERS.get(config.type, [])
        for param in params:
            widget = self._create_param_widget(param, config)
            params_layout.addRow(param["name"], widget)

        layout.addWidget(params_group)

        # Условия сигналов
        conditions_group = QGroupBox("Условия сигналов")
        conditions_layout = QFormLayout(conditions_group)

        # CALL условие
        call_combo = QComboBox()
        call_conditions = INDICATOR_CONDITIONS.get(config.type, {}).get("call", [])
        for value, description in call_conditions:
            call_combo.addItem(description, value)
        
        # Выбираем текущее условие
        current_call = config.conditions.get("call", "")
        call_combo.setCurrentText(next(
            (desc for val, desc in call_conditions if val == current_call),
            ""
        ))
        call_combo.currentTextChanged.connect(
            lambda text: self._on_condition_changed(config, "call", call_combo)
        )
        conditions_layout.addRow("📈 CALL:", call_combo)

        # PUT условие
        put_combo = QComboBox()
        put_conditions = INDICATOR_CONDITIONS.get(config.type, {}).get("sell", [])
        for value, description in put_conditions:
            put_combo.addItem(description, value)
        
        current_put = config.conditions.get("sell", "")
        put_combo.setCurrentText(next(
            (desc for val, desc in put_conditions if val == current_put),
            ""
        ))
        put_combo.currentTextChanged.connect(
            lambda text: self._on_condition_changed(config, "sell", put_combo)
        )
        conditions_layout.addRow("📉 PUT:", put_combo)

        layout.addWidget(conditions_group)

        return frame

    def _create_param_widget(self, param: dict, config: IndicatorConfig):
        """Создание виджета параметра."""
        param_id = param["id"]
        param_type = param["type"]
        default_value = param.get("default")

        # Получаем текущее значение из config
        current_value = config.parameters.get(param_id, default_value)

        if param_type == "spin":
            widget = QSpinBox()
            widget.setRange(param.get("min", 0), param.get("max", 100))
            widget.setValue(current_value)
            widget.valueChanged.connect(
                lambda v: self._on_parameter_changed(config, param_id, v)
            )
        elif param_type == "double":
            widget = QDoubleSpinBox()
            widget.setRange(param.get("min", 0.0), param.get("max", 100.0))
            widget.setDecimals(2)
            widget.setValue(current_value)
            widget.valueChanged.connect(
                lambda v: self._on_parameter_changed(config, param_id, v)
            )
        elif param_type == "combo":
            widget = QComboBox()
            widget.addItems(param.get("values", []))
            if current_value in param.get("values", []):
                widget.setCurrentText(current_value)
            widget.currentTextChanged.connect(
                lambda v: self._on_parameter_changed(config, param_id, v)
            )
        else:
            widget = QLineEdit(str(current_value))
            widget.textChanged.connect(
                lambda v: self._on_parameter_changed(config, param_id, v)
            )

        return widget

    def _on_remove_indicator(self, index: int):
        """Удаление индикатора."""
        if 0 <= index < len(self.indicators):
            del self.indicators[index]
            self._render_indicators()
            self.indicators_changed.emit(self.indicators)

    def _on_parameter_changed(self, config: IndicatorConfig, param_id: str, value):
        """Изменение параметра индикатора."""
        config.parameters[param_id] = value
        self.indicators_changed.emit(self.indicators)

    def _on_condition_changed(self, config: IndicatorConfig, condition_type: str, combo: QComboBox):
        """Изменение условия сигнала."""
        value = combo.currentData()
        config.conditions[condition_type] = value
        self.indicators_changed.emit(self.indicators)

    def load_indicators(self, indicators: list):
        """
        Загрузка индикаторов.

        Args:
            indicators: Список IndicatorConfig
        """
        self.indicators = indicators.copy()
        self._render_indicators()

    def get_indicators(self) -> list:
        """
        Получение списка индикаторов.

        Returns:
            Список IndicatorConfig
        """
        return self.indicators.copy()


__all__ = ["IndicatorEditorWidget"]
