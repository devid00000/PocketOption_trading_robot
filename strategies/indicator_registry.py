"""
Реестр индикаторов.

Централизованная регистрация всех доступных индикаторов.
Позволяет динамически добавлять новые индикаторы.

Пример использования:
    from strategies.indicator_registry import IndicatorRegistry
    
    # Регистрация нового индикатора
    IndicatorRegistry.register("my_indicator", MyIndicator)
    
    # Получение индикатора по типу
    indicator = IndicatorRegistry.get("rsi")(parameters={...})
    
    # Список всех доступных индикаторов
    available = IndicatorRegistry.list()
"""

from typing import Dict, Type, List, Optional, Any
from strategies.indicator_base import BaseIndicator


class IndicatorRegistry:
    """
    Реестр индикаторов.
    
    Хранит映射 типов индикаторов и предоставляет методы для:
    - Регистрации новых индикаторов
    - Получения индикатора по типу
    - Списка доступных индикаторов
    """
    
    # Внутренний реестр
    _registry: Dict[str, Type[BaseIndicator]] = {}
    
    @classmethod
    def register(cls, name: str, indicator_class: Type[BaseIndicator]):
        """
        Регистрация индикатора.

        Args:
            name: Уникальное имя индикатора
            indicator_class: Класс индикатора

        Пример:
            IndicatorRegistry.register("rsi", RsiIndicator)
        """
        if not issubclass(indicator_class, BaseIndicator):
            raise TypeError(f"Indicator class must inherit from BaseIndicator, got {indicator_class}")
        
        cls._registry[name.lower()] = indicator_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseIndicator]]:
        """
        Получение класса индикатора по имени.

        Args:
            name: Имя индикатора

        Returns:
            Класс индикатора или None

        Пример:
            RsiClass = IndicatorRegistry.get("rsi")
            indicator = RsiClass(parameters={"period": 14})
        """
        return cls._registry.get(name.lower())

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[BaseIndicator]:
        """
        Создание экземпляра индикатора.

        Args:
            name: Имя индикатора
            **kwargs: Аргументы для конструктора индикатора

        Returns:
            Экземпляр индикатора или None

        Пример:
            indicator = IndicatorRegistry.create("rsi", period=14, overbought=70)
        """
        indicator_class = cls.get(name)
        if indicator_class:
            return indicator_class(**kwargs)
        return None

    @classmethod
    def list(cls) -> List[str]:
        """
        Список зарегистрированных индикаторов.

        Returns:
            Список имён индикаторов

        Пример:
            available = IndicatorRegistry.list()
            # ["rsi", "bollinger", "macd", ...]
        """
        return list(cls._registry.keys())

    @classmethod
    def list_with_info(cls) -> List[Dict[str, Any]]:
        """
        Список индикаторов с информацией.

        Returns:
            Список словарей с информацией об индикаторах

        Пример:
            [
                {
                    "name": "rsi",
                    "display_name": "RSI",
                    "description": "Relative Strength Index",
                    "parameters": {"period": 14, ...},
                    "conditions": {"call": "...", "sell": "..."}
                },
                ...
            ]
        """
        result = []
        for name, indicator_class in cls._registry.items():
            # Создаём временный экземпляр для получения информации
            try:
                indicator = indicator_class()
                result.append({
                    "name": name,
                    "display_name": getattr(indicator_class, "DISPLAY_NAME", name.title()),
                    "description": getattr(indicator_class, "DESCRIPTION", ""),
                    "default_parameters": indicator_class.DEFAULT_PARAMETERS,
                    "default_conditions": indicator_class.DEFAULT_CONDITIONS,
                    "conditions_description": getattr(indicator_class, "CONDITIONS_DESCRIPTION", {})
                })
            except Exception:
                result.append({
                    "name": name,
                    "display_name": getattr(indicator_class, "DISPLAY_NAME", name.title()),
                    "description": getattr(indicator_class, "DESCRIPTION", ""),
                    "default_parameters": {},
                    "default_conditions": {},
                    "conditions_description": {}
                })
        
        return result

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Проверка: зарегистрирован ли индикатор.

        Args:
            name: Имя индикатора

        Returns:
            True если индикатор зарегистрирован
        """
        return name.lower() in cls._registry

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Удаление индикатора из реестра.

        Args:
            name: Имя индикатора

        Returns:
            True если индикатор был удалён
        """
        name = name.lower()
        if name in cls._registry:
            del cls._registry[name]
            return True
        return False

    @classmethod
    def clear(cls):
        """Очистка реестра."""
        cls._registry.clear()

    @classmethod
    def count(cls) -> int:
        """Количество зарегистрированных индикаторов."""
        return len(cls._registry)


# ==============================================================================
# ДЕКОРАТОР ДЛЯ АВТОМАТИЧЕСКОЙ РЕГИСТРАЦИИ
# ==============================================================================

def register_indicator(name: str):
    """
    Декоратор для автоматической регистрации индикатора.

    Пример:
        @register_indicator("rsi")
        class RsiIndicator(BaseIndicator):
            DISPLAY_NAME = "RSI"
            ...
    """
    def decorator(indicator_class: Type[BaseIndicator]) -> Type[BaseIndicator]:
        IndicatorRegistry.register(name, indicator_class)
        return indicator_class
    return decorator


# ==============================================================================
# АВТОМАТИЧЕСКАЯ РЕГИСТРАЦИЯ БАЗОВЫХ ИНДИКАТОРОВ
# ==============================================================================

def register_builtin_indicators():
    """
    Регистрация встроенных индикаторов.
    
    Вызывается автоматически при первом импорте модуля.
    """
    # Импортируем индикаторы для регистрации
    # Это создаст экземпляры и зарегистрирует их в реестре
    try:
        from strategies.indicator_wrappers import (
            RsiIndicator,
            BollingerBandsIndicator,
            MacdIndicator,
            StochasticIndicator,
            CciIndicator,
            ParabolicSarIndicator,
            SuperTrendIndicator,
            TwoMaIndicator,
            CandleIndicator
        )
    except ImportError as e:
        print(f"[IndicatorRegistry] Ошибка импорта индикаторов: {e}")


# Автоматическая регистрация при импорте
register_builtin_indicators()


__all__ = [
    "IndicatorRegistry",
    "register_indicator",
    "register_builtin_indicators"
]
