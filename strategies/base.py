"""
Базовый класс торговой стратегии.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from core.market_data import Candle


@dataclass
class Signal:
    """Торговый сигнал."""
    direction: str  # "call", "put", "none"
    strength: float  # Сила сигнала (0-100)
    reason: str  # Причина сигнала
    timestamp: datetime = None
    metadata: Dict = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}

    def is_valid(self) -> bool:
        """Проверка валидности сигнала."""
        return self.direction in ["call", "put"] and self.strength > 0


class BaseStrategy(ABC):
    """
    Базовый класс для всех стратегий.

    Наследники должны реализовать метод analyze(), который возвращает Signal.
    """

    def __init__(self, name: str = "Base Strategy", config: Dict = None):
        """
        Инициализация стратегии.

        Args:
            name: Название стратегии
            config: Конфигурация стратегии
        """
        self.name = name
        self.config = config or {}
        self._last_signal: Optional[Signal] = None
        self._signals_history: List[Signal] = []

    @abstractmethod
    def analyze(self, candles: List[Candle]) -> Signal:
        """
        Анализ рынка и генерация сигнала.

        Args:
            candles: Список свечей для анализа

        Returns:
            Signal с направлением сделки
        """
        pass

    def get_last_signal(self) -> Optional[Signal]:
        """Последний сигнал."""
        return self._last_signal

    def get_signals_history(self, count: int = 10) -> List[Signal]:
        """История сигналов."""
        return self._signals_history[-count:]

    def _save_signal(self, signal: Signal):
        """Сохранение сигнала в историю."""
        self._last_signal = signal
        self._signals_history.append(signal)
        # Оставляем только последние 100 сигналов
        self._signals_history = self._signals_history[-100:]

    def get_config(self) -> Dict:
        """Получение конфигурации."""
        return self.config.copy()

    def set_config(self, config: Dict):
        """Установка конфигурации."""
        self.config = config

    def to_dict(self) -> Dict:
        """Сериализация стратегии."""
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "config": self.config
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'BaseStrategy':
        """Десериализация стратегии."""
        return cls(name=data.get("name", "Strategy"), config=data.get("config", {}))


class CombinedStrategy(BaseStrategy):
    """
    Комбинированная стратегия - объединяет несколько стратегий.
    """

    def __init__(self, name: str = "Combined Strategy", strategies: List[BaseStrategy] = None,
                 min_agreement: int = 1):
        """
        Инициализация комбинированной стратегии.

        Args:
            name: Название
            strategies: Список стратегий
            min_agreement: Минимальное количество стратегий, согласных с сигналом
        """
        super().__init__(name=name)
        self.strategies = strategies or []
        self.min_agreement = min_agreement

    def add_strategy(self, strategy: BaseStrategy):
        """Добавить стратегию."""
        self.strategies.append(strategy)

    def remove_strategy(self, name: str):
        """Удалить стратегию по названию."""
        self.strategies = [s for s in self.strategies if s.name != name]

    def analyze(self, candles: List[Candle]) -> Signal:
        """
        Анализ всеми стратегиями и агрегация сигналов.
        """
        if not self.strategies:
            return Signal(direction="none", strength=0, reason="Нет стратегий")

        call_count = 0
        put_count = 0
        reasons = []
        total_strength = 0

        for strategy in self.strategies:
            signal = strategy.analyze(candles)
            if signal.is_valid():
                if signal.direction == "call":
                    call_count += 1
                elif signal.direction == "put":
                    put_count += 1
                reasons.append(f"{strategy.name}: {signal.direction} ({signal.strength}%)")
                total_strength += signal.strength

        # Определение итогового сигнала
        if call_count >= self.min_agreement and call_count > put_count:
            direction = "call"
            avg_strength = total_strength / (call_count + put_count) if (call_count + put_count) > 0 else 0
            reason = f"CALL: {call_count} из {len(self.strategies)} стратегий"
        elif put_count >= self.min_agreement and put_count > call_count:
            direction = "put"
            avg_strength = total_strength / (call_count + put_count) if (call_count + put_count) > 0 else 0
            reason = f"PUT: {put_count} из {len(self.strategies)} стратегий"
        else:
            direction = "none"
            avg_strength = 0
            reason = "Нет согласия стратегий"

        signal = Signal(
            direction=direction,
            strength=avg_strength,
            reason=reason + " | " + ", ".join(reasons[:3]),  # Первые 3 причины
            metadata={
                "call_count": call_count,
                "put_count": put_count,
                "total_strategies": len(self.strategies)
            }
        )

        self._save_signal(signal)
        return signal

    def to_dict(self) -> Dict:
        """Сериализация комбинированной стратегии."""
        return {
            "name": self.name,
            "type": "CombinedStrategy",
            "min_agreement": self.min_agreement,
            "strategies": [s.to_dict() for s in self.strategies]
        }


__all__ = ["Signal", "BaseStrategy", "CombinedStrategy"]
