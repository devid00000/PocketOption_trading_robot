"""
Менеджер стратегий и конструктор стратегий из JSON.
"""

import json
from typing import Dict, List, Optional, Type
from pathlib import Path

from strategies.base import BaseStrategy, CombinedStrategy, Signal
from strategies.strategies import (
    RSIStrategy,
    RSIDivergenceStrategy,
    BollingerBandsStrategy,
    MACDStrategy,
    MultiIndicatorStrategy,
    SimpleStrategy
)
from core.market_data import Candle


class StrategyManager:
    """
    Менеджер торговых стратегий.

    Управление жизненным циклом стратегий:
    - Создание стратегий из конфигурации
    - Загрузка/сохранение в JSON
    - Выполнение анализа
    """

    # Карта типов стратегий
    STRATEGY_TYPES: Dict[str, Type[BaseStrategy]] = {
        "RSIStrategy": RSIStrategy,
        "RSIDivergenceStrategy": RSIDivergenceStrategy,
        "BollingerBandsStrategy": BollingerBandsStrategy,
        "MACDStrategy": MACDStrategy,
        "MultiIndicatorStrategy": MultiIndicatorStrategy,
        "SimpleStrategy": SimpleStrategy,
        "CombinedStrategy": CombinedStrategy
    }

    def __init__(self, config_dir: str = "strategies/configs"):
        """
        Инициализация менеджера стратегий.

        Args:
            config_dir: Директория для хранения конфигураций
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._strategies: Dict[str, BaseStrategy] = {}
        self._active_strategy: Optional[str] = None

    # ==========================================================================
    # СОЗДАНИЕ СТРАТЕГИЙ
    # ==========================================================================

    def create_strategy(self, strategy_type: str, name: str = None,
                        config: Dict = None) -> BaseStrategy:
        """
        Создание стратегии по типу.

        Args:
            strategy_type: Тип стратегии (RSIStrategy, MACDStrategy, etc.)
            name: Название стратегии
            config: Конфигурация

        Returns:
            Экземпляр стратегии

        Raises:
            ValueError: Если тип стратегии не найден
        """
        if strategy_type not in self.STRATEGY_TYPES:
            available = ", ".join(self.STRATEGY_TYPES.keys())
            raise ValueError(f"Неизвестный тип стратегии: {strategy_type}. Доступные: {available}")

        strategy_class = self.STRATEGY_TYPES[strategy_type]
        name = name or f"{strategy_type}_{len(self._strategies) + 1}"

        strategy = strategy_class(name=name, config=config)
        self._strategies[name] = strategy

        return strategy

    def create_from_dict(self, data: Dict) -> BaseStrategy:
        """
        Создание стратегии из словаря.

        Args:
            data: Словарь с данными стратегии

        Returns:
            Экземпляр стратегии
        """
        strategy_type = data.get("type", data.get("strategy_type"))
        name = data.get("name", strategy_type)
        config = data.get("config", data.get("parameters", {}))

        if strategy_type == "CombinedStrategy":
            # Создание комбинированной стратегии
            return self._create_combined_from_dict(data)

        return self.create_strategy(strategy_type, name, config)

    def _create_combined_from_dict(self, data: Dict) -> CombinedStrategy:
        """Создание комбинированной стратегии из словаря."""
        name = data.get("name", "CombinedStrategy")
        min_agreement = data.get("min_agreement", 1)
        strategies_data = data.get("strategies", [])

        combined = CombinedStrategy(name=name, min_agreement=min_agreement)

        for strat_data in strategies_data:
            strategy = self.create_from_dict(strat_data)
            combined.add_strategy(strategy)

        return combined

    # ==========================================================================
    # ЗАГРУЗКА / СОХРАНЕНИЕ
    # ==========================================================================

    def save_strategy(self, strategy: BaseStrategy, filename: str = None) -> Path:
        """
        Сохранение стратегии в JSON файл.

        Args:
            strategy: Стратегия для сохранения
            filename: Имя файла (без расширения)

        Returns:
            Путь к сохранённому файлу
        """
        if filename is None:
            filename = strategy.name.replace(" ", "_").lower()

        filepath = self.config_dir / f"{filename}.json"

        data = strategy.to_dict()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return filepath

    def load_strategy(self, filename: str) -> BaseStrategy:
        """
        Загрузка стратегии из JSON файла.

        Args:
            filename: Имя файла (без расширения)

        Returns:
            Загруженная стратегия
        """
        filepath = self.config_dir / f"{filename}.json"

        if not filepath.exists():
            raise FileNotFoundError(f"Файл стратегии не найден: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        strategy = self.create_from_dict(data)
        self._strategies[strategy.name] = strategy

        return strategy

    def load_all_strategies(self) -> List[BaseStrategy]:
        """Загрузка всех стратегий из директории."""
        strategies = []

        for filepath in self.config_dir.glob("*.json"):
            try:
                strategy = self.load_strategy(filepath.stem)
                strategies.append(strategy)
            except Exception as e:
                print(f"[StrategyManager] Ошибка загрузки {filepath}: {e}")

        return strategies

    def delete_strategy(self, name: str) -> bool:
        """
        Удаление стратегии.

        Args:
            name: Название стратегии

        Returns:
            True если удалена
        """
        if name not in self._strategies:
            return False

        filepath = self.config_dir / f"{name.replace(' ', '_').lower()}.json"
        if filepath.exists():
            filepath.unlink()

        del self._strategies[name]

        if self._active_strategy == name:
            self._active_strategy = None

        return True

    # ==========================================================================
    # УПРАВЛЕНИЕ
    # ==========================================================================

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Получение стратегии по названию."""
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        """Список названий стратегий."""
        return list(self._strategies.keys())

    def set_active_strategy(self, name: str) -> bool:
        """
        Установка активной стратегии.

        Args:
            name: Название стратегии

        Returns:
            True если стратегия найдена
        """
        if name not in self._strategies:
            return False

        self._active_strategy = name
        return True

    def get_active_strategy(self) -> Optional[BaseStrategy]:
        """Получение активной стратегии."""
        if not self._active_strategy:
            return None
        return self._strategies.get(self._active_strategy)

    def analyze(self, candles: List[Candle], strategy_name: str = None) -> Signal:
        """
        Анализ рынка стратегией.

        Args:
            candles: Список свечей
            strategy_name: Название стратегии (или активная)

        Returns:
            Signal с результатом анализа
        """
        if strategy_name is None:
            strategy = self.get_active_strategy()
            if not strategy:
                return Signal(direction="none", strength=0, reason="Нет активной стратегии")
        else:
            strategy = self.get_strategy(strategy_name)
            if not strategy:
                return Signal(direction="none", strength=0, reason=f"Стратегия не найдена: {strategy_name}")

        return strategy.analyze(candles)

    def analyze_all(self, candles: List[Candle]) -> Dict[str, Signal]:
        """
        Анализ всеми стратегиями.

        Args:
            candles: Список свечей

        Returns:
            Словарь {название: сигнал}
        """
        results = {}

        for name, strategy in self._strategies.items():
            results[name] = strategy.analyze(candles)

        return results

    # ==========================================================================
    # ПРЕДНАСТРОЕННЫЕ СТРАТЕГИИ
    # ==========================================================================

    def create_default_strategies(self):
        """Создание набора стратегий по умолчанию."""
        # RSI стратегия
        self.create_strategy(
            "RSIStrategy",
            name="RSI Classic",
            config={
                "period": 14,
                "overbought": 70,
                "oversold": 30
            }
        )

        # Bollinger Bands стратегия
        self.create_strategy(
            "BollingerBandsStrategy",
            name="BB Rebound",
            config={
                "period": 20,
                "std_dev": 2.0,
                "breakout_mode": False
            }
        )

        # MACD стратегия
        self.create_strategy(
            "MACDStrategy",
            name="MACD Classic",
            config={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
                "histogram_confirmation": True
            }
        )

        # Мульти-индикатор
        self.create_strategy(
            "MultiIndicatorStrategy",
            name="Multi Indicator",
            config={
                "use_rsi": True,
                "use_bb": True,
                "use_macd": True,
                "min_agreement": 2
            }
        )

        # Простая для тестов
        self.create_strategy(
            "SimpleStrategy",
            name="Simple Test",
            config={
                "always_trade": True,
                "strength": 50
            }
        )

        print(f"[StrategyManager] Создано {len(self._strategies)} стратегий по умолчанию")

    def export_all(self, filepath: str) -> bool:
        """
        Экспорт всех стратегий в один файл.

        Args:
            filepath: Путь к файлу

        Returns:
            True если успешно
        """
        data = {
            "strategies": [s.to_dict() for s in self._strategies.values()],
            "active": self._active_strategy
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[StrategyManager] Ошибка экспорта: {e}")
            return False

    def import_all(self, filepath: str) -> int:
        """
        Импорт всех стратегий из файла.

        Args:
            filepath: Путь к файлу

        Returns:
            Количество импортированных стратегий
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for strat_data in data.get("strategies", []):
                strategy = self.create_from_dict(strat_data)
                count += 1

            if data.get("active"):
                self._active_strategy = data["active"]

            return count
        except Exception as e:
            print(f"[StrategyManager] Ошибка импорта: {e}")
            return 0


__all__ = ["StrategyManager"]
