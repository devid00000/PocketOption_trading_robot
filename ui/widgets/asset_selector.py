"""
Виджет выбора активов.

Вкладка "Активы" в конструкторе стратегий:
- Список всех доступных активов по группам
- Поиск активов
- Выбор/снятие всех
- Список выбранных активов
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QLabel,
    QScrollArea, QFrame, QGridLayout, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


# Список активов по умолчанию (можно загрузить из config/api_config.json)
DEFAULT_ASSETS = {
    "currency": [
        ("EURUSD_otc", "EUR/USD OTC"),
        ("GBPUSD_otc", "GBP/USD OTC"),
        ("USDJPY_otc", "USD/JPY OTC"),
        ("AUDUSD_otc", "AUD/USD OTC"),
        ("USDCAD_otc", "USD/CAD OTC"),
        ("USDCHF_otc", "USD/CHF OTC"),
        ("EURUSD", "EUR/USD"),
        ("GBPUSD", "GBP/USD"),
    ],
    "cryptocurrency": [
        ("BTCUSD_otc", "Bitcoin OTC"),
        ("ETHUSD_otc", "Ethereum OTC"),
        ("LTCUSD_otc", "Litecoin OTC"),
        ("XRPUSD_otc", "Ripple OTC"),
        ("BTCUSD", "Bitcoin"),
        ("ETHUSD", "Ethereum"),
    ],
    "stock": [
        ("#AAPL_otc", "Apple OTC"),
        ("#TSLA_otc", "Tesla OTC"),
        ("#MSFT_otc", "Microsoft OTC"),
        ("#GOOGL_otc", "Google OTC"),
        ("#AMZN_otc", "Amazon OTC"),
    ],
    "index": [
        ("CAC40", "CAC 40"),
        ("DJI30_otc", "DJI 30 OTC"),
        ("SPX500_otc", "S&P 500 OTC"),
    ],
    "commodity": [
        ("GOLD", "Gold"),
        ("SILVER", "Silver"),
        ("GOLD_otc", "Gold OTC"),
    ],
    "oils": [
        ("OIL", "Oil"),
        ("BRENT", "Brent"),
        ("OIL_otc", "Oil OTC"),
    ]
}

ASSET_GROUP_NAMES = {
    "currency": "💱 Валюты",
    "cryptocurrency": "🪙 Криптовалюты",
    "stock": "📈 Акции",
    "index": "📊 Индексы",
    "commodity": "🏭 Сырьё",
    "oils": "🛢️ Нефть"
}


class AssetSelectorWidget(QWidget):
    """
    Виджет выбора активов.
    """

    assets_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_assets = set()
        self._init_ui()
        self._load_all_assets()

    def _init_ui(self):
        """Инициализация интерфейса."""
        layout = QHBoxLayout(self)

        # Левая панель: список групп
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel, 1)

        # Правая панель: сетка активов
        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, 3)

    def _create_left_panel(self) -> QWidget:
        """Левая панель с группами."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Заголовок
        title = QLabel("Группы активов")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)

        # Список групп
        self.group_list = QListWidget()
        self.group_list.addItem("🔍 Все")
        for group_id, group_name in ASSET_GROUP_NAMES.items():
            self.group_list.addItem(f"{group_name}")
        
        self.group_list.currentRowChanged.connect(self._on_group_changed)
        layout.addWidget(self.group_list)

        # Выбранные активы
        selected_group = QGroupBox("✅ Выбранные")
        selected_layout = QVBoxLayout(selected_group)

        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QListWidget.ExtendedSelection)
        selected_layout.addWidget(self.selected_list)

        # Кнопки управления выбранными
        btn_remove = QPushButton("❌ Удалить выбранные")
        btn_remove.clicked.connect(self._remove_selected_assets)
        selected_layout.addWidget(btn_remove)

        layout.addWidget(selected_group)

        return widget

    def _create_right_panel(self) -> QWidget:
        """Правая панель с сеткой активов."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Поиск
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Поиск:")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название актива...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        # Кнопки "Выбрать всё" / "Снять всё"
        btn_select_all = QPushButton("✅ Выбрать всё")
        btn_select_all.clicked.connect(self._select_all_visible)
        search_layout.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("❌ Снять всё")
        btn_deselect_all.clicked.connect(self._deselect_all)
        search_layout.addWidget(btn_deselect_all)

        layout.addLayout(search_layout)

        # Скролл для сетки активов
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Контейнер для сетки
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)

        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)

        return widget

    def _load_all_assets(self):
        """Загрузка всех активов."""
        self.all_assets = {}
        for group_id, assets in DEFAULT_ASSETS.items():
            for asset_id, asset_name in assets:
                self.all_assets[asset_id] = {
                    "id": asset_id,
                    "name": asset_name,
                    "group": group_id
                }

        # Отображаем все активы
        self._display_assets(list(self.all_assets.keys()))

    def _display_assets(self, asset_ids: list):
        """
        Отображение активов в сетке.

        Args:
            asset_ids: Список ID активов для отображения
        """
        # Очищаем сетку
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Создаём чекбоксы для активов
        row = 0
        col = 0
        max_cols = 4

        for asset_id in asset_ids:
            asset = self.all_assets.get(asset_id)
            if not asset:
                continue

            checkbox = QCheckBox(f"{asset['name']}\n({asset_id})")
            checkbox.setProperty("asset_id", asset_id)
            checkbox.setChecked(asset_id in self.selected_assets)
            checkbox.stateChanged.connect(self._on_asset_toggled)

            self.grid_layout.addWidget(checkbox, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Добавляем растягиватель
        self.grid_layout.addItem(QGridLayout(), row + 1, 0, 1, max_cols)

    def _on_group_changed(self, index: int):
        """Изменение выбранной группы."""
        if index == 0:
            # Все активы
            self._display_assets(list(self.all_assets.keys()))
        else:
            # Конкретная группа
            group_id = list(ASSET_GROUP_NAMES.keys())[index - 1]
            group_assets = [
                asset_id for asset_id, asset in self.all_assets.items()
                if asset["group"] == group_id
            ]
            self._display_assets(group_assets)

    def _on_search_changed(self, text: str):
        """Изменение текста поиска."""
        if not text:
            # Возвращаем текущую группу
            self._on_group_changed(self.group_list.currentRow())
            return

        # Фильтруем активы
        text = text.lower()
        filtered = [
            asset_id for asset_id, asset in self.all_assets.items()
            if text in asset_id.lower() or text in asset["name"].lower()
        ]
        self._display_assets(filtered)

    def _on_asset_toggled(self, state):
        """Изменение состояния чекбокса актива."""
        checkbox = self.sender()
        asset_id = checkbox.property("asset_id")

        if state == Qt.Checked:
            self.selected_assets.add(asset_id)
            self._add_to_selected_list(asset_id)
        else:
            self.selected_assets.discard(asset_id)
            self._remove_from_selected_list(asset_id)

        self.assets_changed.emit(list(self.selected_assets))

    def _add_to_selected_list(self, asset_id: str):
        """Добавление актива в список выбранных."""
        # Проверяем, нет ли уже в списке
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            if item.data(Qt.UserRole) == asset_id:
                return

        asset = self.all_assets.get(asset_id)
        if not asset:
            return

        item = QListWidgetItem(f"{asset['name']} ({asset_id})")
        item.setData(Qt.UserRole, asset_id)
        self.selected_list.addItem(item)

    def _remove_from_selected_list(self, asset_id: str):
        """Удаление актива из списка выбранных."""
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            if item.data(Qt.UserRole) == asset_id:
                self.selected_list.takeItem(i)
                return

    def _remove_selected_assets(self):
        """Удаление выбранных активов из списка выбранных."""
        selected_items = self.selected_list.selectedItems()
        for item in selected_items:
            asset_id = item.data(Qt.UserRole)
            self.selected_assets.discard(asset_id)
            self._remove_from_selected_list(asset_id)

            # Снимаем галочку в сетке
            for i in range(self.grid_layout.count()):
                item = self.grid_layout.itemAt(i)
                if item and item.widget():
                    checkbox = item.widget()
                    if isinstance(checkbox, QCheckBox) and checkbox.property("asset_id") == asset_id:
                        checkbox.setChecked(False)

        self.assets_changed.emit(list(self.selected_assets))

    def _select_all_visible(self):
        """Выбрать все видимые активы."""
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                checkbox = item.widget()
                if isinstance(checkbox, QCheckBox):
                    checkbox.setChecked(True)

    def _deselect_all(self):
        """Снять все активы."""
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                checkbox = item.widget()
                if isinstance(checkbox, QCheckBox):
                    checkbox.setChecked(False)

    def load_assets(self, asset_ids: list):
        """
        Загрузка выбранных активов.

        Args:
            asset_ids: Список ID выбранных активов
        """
        self.selected_assets = set(asset_ids)

        # Обновляем чекбоксы в сетке
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                checkbox = item.widget()
                if isinstance(checkbox, QCheckBox):
                    asset_id = checkbox.property("asset_id")
                    checkbox.setChecked(asset_id in self.selected_assets)

        # Обновляем список выбранных
        self.selected_list.clear()
        for asset_id in self.selected_assets:
            self._add_to_selected_list(asset_id)

    def get_selected_assets(self) -> list:
        """
        Получение списка выбранных активов.

        Returns:
            Список ID активов
        """
        return list(self.selected_assets)


__all__ = ["AssetSelectorWidget"]
