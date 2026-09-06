"""
Базовый класс для торговых индикаторов.

Все индикаторы наследуются от BaseIndicator и реализуют:
- compute() — вычисление значения индикатора
- get_context() — получение контекста переменных для условий
- check_signal() — проверка условий сигнала
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re


# ==============================================================================
# ДЕКОРАТОР ДЛЯ РЕГИСТРАЦИИ ИНДИКАТОРОВ
# ==============================================================================

def register_indicator(name: str):
    """
    Декоратор для автоматической регистрации индикатора в реестре.

    Пример:
        @register_indicator("rsi")
        class RsiIndicator(BaseIndicator):
            DISPLAY_NAME = "RSI"
            ...
    """
    def decorator(indicator_class):
        # Отложенная регистрация (чтобы избежать циклического импорта)
        from strategies.indicator_registry import IndicatorRegistry
        IndicatorRegistry.register(name, indicator_class)
        return indicator_class
    return decorator


# ==============================================================================
# БАЗОВЫЕ КЛАССЫ
# ==============================================================================

@dataclass
class IndicatorSignal:
    """
    Сигнал индикатора.

    Attributes:
        direction: Направление ("call", "put", "none")
        strength: Сила сигнала (0.0-1.0)
        reason: Причина сигнала
        context: Контекст переменных (значения индикатора)
        timestamp: Время сигнала
    """
    direction: str  # "call", "put", "none"
    strength: float = 0.0
    reason: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def is_valid(self) -> bool:
        """Проверка валидности сигнала."""
        return self.direction in ["call", "put"] and self.strength > 0


class BaseIndicator(ABC):
    """
    Базовый класс для всех индикаторов.

    Наследники должны реализовать:
    - compute() — вычисление значения индикатора
    - get_context() — получение контекста переменных
    """

    # Название индикатора (отображается в UI)
    DISPLAY_NAME: str = "Indicator"

    # Описание индикатора
    DESCRIPTION: str = ""

    # Параметры по умолчанию
    DEFAULT_PARAMETERS: Dict[str, Any] = {}

    # Условия сигналов по умолчанию
    DEFAULT_CONDITIONS: Dict[str, str] = {
        "call": "",  # Выражение для CALL
        "sell": ""   # Выражение для PUT
    }

    # Описание условий (для UI)
    CONDITIONS_DESCRIPTION: Dict[str, str] = {}

    def __init__(
        self,
        parameters: Dict[str, Any] = None,
        conditions: Dict[str, str] = None,
        timeframe: int = 60,
        bar_index: int = 0
    ):
        """
        Инициализация индикатора.

        Args:
            parameters: Параметры индикатора
            conditions: Условия сигналов (call/sell выражения)
            timeframe: Таймфрейм в секундах
            bar_index: На каком баре проверять (0 = текущий, -1 = предыдущий)
        """
        self.parameters = parameters or self.DEFAULT_PARAMETERS.copy()
        self.conditions = conditions or self.DEFAULT_CONDITIONS.copy()
        self.timeframe = timeframe
        self.bar_index = bar_index
        self._last_context: Dict[str, Any] = {}

    @abstractmethod
    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """
        Вычисление значения индикатора.

        Args:
            candles: Список свечей [ {open, high, low, close, volume, timestamp}, ... ]

        Returns:
            Словарь с результатами вычислений
        """
        pass

    def get_context(self, candles: List[Dict]) -> Dict[str, Any]:
        """
        Получение контекста переменных для условий.

        Args:
            candles: Список свечей

        Returns:
            Словарь переменных для использования в signal_up/signal_down
        """
        # Вычисляем индикатор
        result = self.compute(candles)
        
        # Сохраняем контекст
        self._last_context = result
        return result

    def check_signal(self, candles: List[Dict]) -> IndicatorSignal:
        """
        Проверка условий сигнала.

        Args:
            candles: Список свечей

        Returns:
            IndicatorSignal с результатом
        """
        # Получаем контекст
        context = self.get_context(candles)
        
        # Проверяем условия
        call_signal = self._check_condition(self.conditions.get("call", ""), context)
        put_signal = self._check_condition(self.conditions.get("sell", ""), context)
        
        # Определяем направление
        if call_signal:
            direction = "call"
            strength = self._calculate_strength(context, "call")
            reason = self._get_reason(context, "call")
        elif put_signal:
            direction = "put"
            strength = self._calculate_strength(context, "put")
            reason = self._get_reason(context, "put")
        else:
            direction = "none"
            strength = 0.0
            reason = "Нет сигнала"
        
        return IndicatorSignal(
            direction=direction,
            strength=strength,
            reason=reason,
            context=context
        )

    def _check_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Проверка условия.

        Args:
            condition: Выражение (например, "valRsi < btl")
            context: Контекст переменных

        Returns:
            True если условие выполнено
        """
        if not condition:
            return False
        
        try:
            # Безопасное вычисление выражения
            return self._safe_eval(condition, context)
        except Exception as e:
            print(f"[Indicator] Ошибка вычисления условия '{condition}': {e}")
            return False

    def _safe_eval(self, expression: str, context: Dict[str, Any]) -> bool:
        """
        Безопасное вычисление выражения.

        Args:
            expression: Выражение для вычисления
            context: Контекст переменных

        Returns:
            Результат вычисления
        """
        # Разрешённые функции
        allowed_functions = {
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
            "round": round,
            "int": int,
            "float": float,
            "str": str,
        }
        
        # Вычисляем с ограниченным контекстом
        try:
            return eval(expression, {"__builtins__": allowed_functions}, context)
        except Exception as e:
            print(f"[Indicator] Ошибка eval: {e}")
            return False

    def _calculate_strength(self, context: Dict[str, Any], direction: str) -> float:
        """
        Расчёт силы сигнала.

        Args:
            context: Контекст переменных
            direction: Направление ("call" или "put")

        Returns:
            Сила сигнала (0.0-1.0)
        """
        # По умолчанию — средняя сила
        return 0.5

    def _get_reason(self, context: Dict[str, Any], direction: str) -> str:
        """
        Получение причины сигнала.

        Args:
            context: Контекст переменных
            direction: Направление

        Returns:
            Описание причины сигнала
        """
        condition = self.conditions.get(direction, "")
        return f"Условие: {condition}"

    def get_parameters_description(self) -> Dict[str, str]:
        """
        Получение описания параметров.

        Returns:
            Словарь {параметр: описание}
        """
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализация индикатора.

        Returns:
            Словарь с параметрами
        """
        return {
            "type": self.__class__.__name__,
            "parameters": self.parameters,
            "conditions": self.conditions,
            "timeframe": self.timeframe,
            "bar_index": self.bar_index
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseIndicator':
        """
        Десериализация индикатора.

        Args:
            data: Словарь с параметрами

        Returns:
            Экземпляр индикатора
        """
        return cls(
            parameters=data.get("parameters", {}),
            conditions=data.get("conditions", {}),
            timeframe=data.get("timeframe", 60),
            bar_index=data.get("bar_index", 0)
        )


class CandlesIndicator(BaseIndicator):
    """
    Базовый класс для индикаторов, работающих со свечами.

    Предоставляет вспомогательные методы для работы со свечами.
    """

    def _get_prices(self, candles: List[Dict], price_type: str = "close") -> List[float]:
        """
        Получение массива цен из свечей.

        Args:
            candles: Список свечей
            price_type: Тип цены (open, high, low, close, hl2, hlc3, ohlc4)

        Returns:
            Список цен
        """
        if not candles:
            return []

        if price_type == "open":
            return [float(c["open"]) for c in candles]
        elif price_type == "high":
            return [float(c["high"]) for c in candles]
        elif price_type == "low":
            return [float(c["low"]) for c in candles]
        elif price_type == "close":
            return [float(c["close"]) for c in candles]
        elif price_type == "hl2":
            return [(float(c["high"]) + float(c["low"])) / 2 for c in candles]
        elif price_type == "hlc3":
            return [(float(c["high"]) + float(c["low"]) + float(c["close"])) / 3 for c in candles]
        elif price_type == "ohlc4":
            return [(float(c["open"]) + float(c["high"]) + float(c["low"]) + float(c["close"])) / 4 for c in candles]
        else:
            return [float(c["close"]) for c in candles]

    def _sma(self, data: List[float], period: int) -> List[float]:
        """
        Простая скользящая средняя (SMA).

        Args:
            data: Список значений
            period: Период

        Returns:
            Список значений SMA
        """
        if len(data) < period:
            return []
        
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(float('nan'))
            else:
                result.append(sum(data[i - period + 1:i + 1]) / period)
        
        return result

    def _ema(self, data: List[float], period: int) -> List[float]:
        """
        Экспоненциальная скользящая средняя (EMA).

        Args:
            data: Список значений
            period: Период

        Returns:
            Список значений EMA
        """
        if len(data) < period:
            return []
        
        multiplier = 2 / (period + 1)
        result = []
        
        # Первая EMA = SMA
        ema = sum(data[:period]) / period
        result.extend([float('nan')] * (period - 1))
        result.append(ema)
        
        # Остальные значения
        for i in range(period, len(data)):
            ema = (data[i] - ema) * multiplier + ema
            result.append(ema)
        
        return result

    def _std(self, data: List[float], period: int) -> List[float]:
        """
        Стандартное отклонение.

        Args:
            data: Список значений
            period: Период

        Returns:
            Список значений стандартного отклонения
        """
        import math
        
        if len(data) < period:
            return []
        
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(float('nan'))
            else:
                window = data[i - period + 1:i + 1]
                mean = sum(window) / period
                variance = sum((x - mean) ** 2 for x in window) / period
                result.append(math.sqrt(variance))
        
        return result

    def _max(self, data: List[float], period: int) -> List[float]:
        """
        Максимум за период.

        Args:
            data: Список значений
            period: Период

        Returns:
            Список максимумов
        """
        if len(data) < period:
            return []
        
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(float('nan'))
            else:
                result.append(max(data[i - period + 1:i + 1]))
        
        return result

    def _min(self, data: List[float], period: int) -> List[float]:
        """
        Минимум за период.

        Args:
            data: Список значений
            period: Период

        Returns:
            Список минимумов
        """
        if len(data) < period:
            return []
        
        result = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(float('nan'))
            else:
                result.append(min(data[i - period + 1:i + 1]))
        
        return result

    def _get_candle_direction(self, candles: List[Dict], index: int) -> str:
        """
        Направление свечи (up/down).

        Args:
            candles: Список свечей
            index: Индекс свечи

        Returns:
            "up" или "down"
        """
        if index < 0 or index >= len(candles):
            return "none"
        
        candle = candles[index]
        if candle["close"] > candle["open"]:
            return "up"
        elif candle["close"] < candle["open"]:
            return "down"
        else:
            return "none"

    def _get_last_candle_direction(self, candles: List[Dict]) -> str:
        """
        Направление последней свечи.

        Args:
            candles: Список свечей

        Returns:
            "up", "down" или "none"
        """
        if not candles:
            return "none"
        return self._get_candle_direction(candles, -1)

    def _get_candle_size(self, candles: List[Dict], index: int = -1) -> float:
        """
        Размер свечи в пунктах.

        Args:
            candles: Список свечей
            index: Индекс свечи

        Returns:
            Размер свечи
        """
        if index < -len(candles) or index >= len(candles):
            return 0.0
        
        candle = candles[index]
        return abs(candle["high"] - candle["low"])

    def _get_body_size(self, candles: List[Dict], index: int = -1) -> float:
        """
        Размер тела свечи.

        Args:
            candles: Список свечей
            index: Индекс свечи

        Returns:
            Размер тела
        """
        if index < -len(candles) or index >= len(candles):
            return 0.0
        
        candle = candles[index]
        return abs(candle["close"] - candle["open"])


__all__ = [
    "IndicatorSignal",
    "BaseIndicator",
    "CandlesIndicator",
    "register_indicator"
]
