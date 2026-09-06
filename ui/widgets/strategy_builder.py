"""
Конструктор стратегий — главный виджет.

Вкладки:
1. Активы — выбор нескольких активов
2. Индикаторы — добавление/настройка индикаторов
3. Регламент — настройки торговли
4. Мартингейл — шаги мартингейла
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QDialog, QDialogButtonBox,
    QScrollArea, QFrame, QGroupBox, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QListWidget, QListWidgetItem, QSplitter,
    QMessageBox, QFileDialog, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.strategy_models import StrategyConfig
from strategies.converter import StrategyConverter


class StrategyBuilderWidget(QWidget):
    """
    Конструктор стратегий.

    Сигналы:
        strategy_saved: Стратегия сохранена
        strategy_loaded: Стратегия загружена
    """

    strategy_saved = Signal(StrategyConfig)
    strategy_loaded = Signal(StrategyConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_strategy: StrategyConfig = None
        self._init_ui()

    def _init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок
        header = self._create_header()
        layout.addWidget(header)

        # Вкладки
        self.tabs = QTabWidget()
        self.tabs.setObjectName("strategyBuilderTabs")

        # Вкладка 1: Активы
        from ui.widgets.asset_selector import AssetSelectorWidget
        self.asset_selector = AssetSelectorWidget()
        self.tabs.addTab(self.asset_selector, "💰 Активы")

        # Вкладка 2: Индикаторы
        from ui.widgets.indicator_editor import IndicatorEditorWidget
        self.indicator_editor = IndicatorEditorWidget()
        self.tabs.addTab(self.indicator_editor, "📊 Индикаторы")

        # Вкладка 3: Регламент
        from ui.widgets.regulations_editor import RegulationsEditorWidget
        self.regulations_editor = RegulationsEditorWidget()
        self.tabs.addTab(self.regulations_editor, "📋 Регламент")

        # Вкладка 4: Мартингейл
        from ui.widgets.martingale_editor import MartingaleEditorWidget
        self.martingale_editor = MartingaleEditorWidget()
        self.tabs.addTab(self.martingale_editor, "📈 Мартингейл")

        layout.addWidget(self.tabs)

        # Кнопки действий
        actions = self._create_actions()
        layout.addWidget(actions)

    def _create_header(self) -> QFrame:
        """Создание заголовка."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)

        # Название стратегии
        name_label = QLabel("Название:")
        layout.addWidget(name_label)

        self.strategy_name_input = QLineEdit()
        self.strategy_name_input.setPlaceholderText("Введите название стратегии")
        self.strategy_name_input.setMinimumWidth(300)
        layout.addWidget(self.strategy_name_input)

        layout.addStretch()

        return frame

    def _create_actions(self) -> QFrame:
        """Создание панели действий."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)

        # Кнопка "Новая"
        btn_new = QPushButton("➕ Новая")
        btn_new.clicked.connect(self._on_new_strategy)
        layout.addWidget(btn_new)

        # Кнопка "Загрузить"
        btn_load = QPushButton("📂 Загрузить")
        btn_load.clicked.connect(self._on_load_strategy)
        layout.addWidget(btn_load)

        # Кнопка "Сохранить"
        btn_save = QPushButton("💾 Сохранить")
        btn_save.clicked.connect(self._on_save_strategy)
        layout.addWidget(btn_save)

        # Кнопка "Импорт из расширения"
        btn_import = QPushButton("📥 Импорт")
        btn_import.clicked.connect(self._on_import_strategy)
        layout.addWidget(btn_import)

        # Кнопка "Экспорт в расширение"
        btn_export = QPushButton("📤 Экспорт")
        btn_export.clicked.connect(self._on_export_strategy)
        layout.addWidget(btn_export)

        layout.addStretch()

        # Кнопка "OK"
        btn_ok = QPushButton("✅ OK")
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        btn_ok.clicked.connect(self._on_ok_clicked)
        layout.addWidget(btn_ok)

        # Кнопка "Отмена"
        btn_cancel = QPushButton("❌ Отмена")
        btn_cancel.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(btn_cancel)

        return frame

    # ==========================================================================
    # ДЕЙСТВИЯ
    # ==========================================================================

    def _on_new_strategy(self):
        """Создание новой стратегии."""
        self.current_strategy = StrategyConfig(name="Новая стратегия")
        self._load_strategy_to_ui(self.current_strategy)

    def _on_load_strategy(self):
        """Загрузка стратегии из файла."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузка стратегии",
            "",
            "JSON файлы (*.json)"
        )

        if filepath:
            try:
                self.current_strategy = StrategyConfig.from_file(filepath)
                self._load_strategy_to_ui(self.current_strategy)
                self.strategy_loaded.emit(self.current_strategy)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить стратегию: {e}")

    def _on_save_strategy(self):
        """Сохранение стратегии в файл."""
        if not self.current_strategy:
            self.current_strategy = StrategyConfig(name="Новая стратегия")

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранение стратегии",
            f"{self.strategy_name_input.text() or 'strategy'}.json",
            "JSON файлы (*.json)"
        )

        if filepath:
            try:
                strategy = self._get_strategy_from_ui()
                strategy.to_file(filepath)
                self.current_strategy = strategy
                self.strategy_saved.emit(strategy)
                QMessageBox.information(self, "Сохранено", f"Стратегия сохранена в {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить стратегию: {e}")

    def _on_import_strategy(self):
        """Импорт стратегии из формата расширения."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт стратегии из расширения",
            "",
            "JSON файлы (*.json)"
        )

        if filepath:
            try:
                self.current_strategy = StrategyConverter.from_extension_file(filepath)
                self._load_strategy_to_ui(self.current_strategy)
                QMessageBox.information(self, "Импорт", "Стратегия импортирована успешно!")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать стратегию: {e}")

    def _on_export_strategy(self):
        """Экспорт стратегии в формат расширения."""
        if not self.current_strategy:
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите или создайте стратегию!")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт стратегии в расширение",
            f"{self.current_strategy.name}.json",
            "JSON файлы (*.json)"
        )

        if filepath:
            try:
                StrategyConverter.to_extension_file(self.current_strategy, filepath)
                QMessageBox.information(self, "Экспорт", f"Стратегия экспортирована в {filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать стратегию: {e}")

    def _on_ok_clicked(self):
        """Нажата кнопка OK."""
        strategy = self._get_strategy_from_ui()
        self.current_strategy = strategy
        self.strategy_saved.emit(strategy)

    def _on_cancel_clicked(self):
        """Нажата кнопка Отмена."""
        # Просто закрываем виджет (если он в диалоге)
        pass

    # ==========================================================================
    # ЗАГРУЗКА/ПОЛУЧЕНИЕ ДАННЫХ
    # ==========================================================================

    def _load_strategy_to_ui(self, strategy: StrategyConfig):
        """
        Загрузка стратегии в UI.

        Args:
            strategy: Стратегия для загрузки
        """
        # Название
        self.strategy_name_input.setText(strategy.name)

        # Активы
        self.asset_selector.load_assets(strategy.assets)

        # Индикаторы
        self.indicator_editor.load_indicators(strategy.indicators)

        # Регламент
        self.regulations_editor.load_regulations(strategy.regulations)

        # Мартингейл
        self.martingale_editor.load_martingale(strategy.martingale)

    def _get_strategy_from_ui(self) -> StrategyConfig:
        """
        Получение стратегии из UI.

        Returns:
            StrategyConfig
        """
        # Получаем данные из всех вкладок
        assets = self.asset_selector.get_selected_assets()
        indicators = self.indicator_editor.get_indicators()
        regulations = self.regulations_editor.get_regulations()
        martingale = self.martingale_editor.get_martingale()

        # Создаём стратегию
        strategy = StrategyConfig(
            name=self.strategy_name_input.text() or "Новая стратегия",
            assets=assets,
            regulations=regulations,
            martingale=martingale
        )
        strategy.indicators = indicators

        return strategy

    def load_strategy(self, strategy: StrategyConfig):
        """
        Публичный метод загрузки стратегии.

        Args:
            strategy: Стратегия для загрузки
        """
        self.current_strategy = strategy
        self._load_strategy_to_ui(strategy)

    def get_strategy(self) -> StrategyConfig:
        """
        Публичный метод получения стратегии.

        Returns:
            StrategyConfig
        """
        return self._get_strategy_from_ui()


class StrategyBuilderDialog(QDialog):
    """
    Диалог конструктора стратегий.
    """

    def __init__(self, parent=None, strategy: StrategyConfig = None):
        super().__init__(parent)
        self.setWindowTitle("Конструктор стратегий")
        self.setMinimumSize(1000, 700)

        # Конструктор
        self.builder = StrategyBuilderWidget(self)
        
        # Основной layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.builder)

        # Кнопки диалога
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Кнопка OK
        btn_ok = QPushButton("✅ OK")
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        btn_ok.clicked.connect(self.accept)
        button_layout.addWidget(btn_ok)
        
        # Кнопка Отмена
        btn_cancel = QPushButton("❌ Отмена")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)
        
        layout.addLayout(button_layout)

        # Если стратегия передана, загружаем её
        if strategy:
            self.builder.load_strategy(strategy)

    def get_strategy(self) -> StrategyConfig:
        """Получить стратегию из диалога."""
        return self.builder.get_strategy()


__all__ = ["StrategyBuilderWidget", "StrategyBuilderDialog"]
