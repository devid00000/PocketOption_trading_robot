"""
Базовый класс стратегии.
"""

from typing import List, Dict, Optional, Any


class Strategy:
    """
    Базовый класс для всех стратегий.
    """
    
    name = "Base Strategy"
    description = "Базовый класс стратегии"
    
    def __init__(self, settings: Dict[str, Any]):
        """
        Инициализация.
        
        Args:
            settings: Настройки стратегии
        """
        self.settings = settings
    
    def should_buy(self, candles: List[Dict]) -> Optional[str]:
        """
        Проверка сигнала на покупку.
        
        Args:
            candles: Список свечей [{"time": ..., "open": ..., "high": ..., "low": ..., "close": ...}]
        
        Returns:
            "call" — покупка CALL
            "put" — покупка PUT
            None — нет сигнала
        """
        raise NotImplementedError
    
    def get_settings_ui(self) -> Dict:
        """
        Получение настроек для UI.
        
        Returns:
            Dict с описанием полей настроек
        """
        return {}


class SimpleStrategy(Strategy):
    """
    Простая стратегия для теста.
    
    Всегда покупает CALL (для тестирования).
    """
    
    name = "Простая (тест)"
    description = "Всегда покупает CALL (для тестирования робота)"
    
    def __init__(self, settings: Dict[str, Any] = None):
        super().__init__(settings or {})
        self.interval = settings.get('interval', 30)  # Секунды между сделками
        self._last_trade_time = 0
    
    def should_buy(self, candles: List[Dict]) -> Optional[str]:
        """Всегда CALL."""
        import time
        
        now = int(time.time())
        
        # Проверяем интервал
        if now - self._last_trade_time < self.interval:
            return None
        
        self._last_trade_time = now
        return "call"
    
    def get_settings_ui(self) -> Dict:
        return {
            "interval": {
                "type": "number",
                "label": "Интервал между сделками (сек)",
                "default": 30,
                "min": 10,
                "max": 3600
            }
        }


class RSIStrategy(Strategy):
    """
    RSI стратегия.
    """
    
    name = "RSI"
    description = "Торговля по индикатору RSI"
    
    def __init__(self, settings: Dict[str, Any]):
        super().__init__(settings)
        self.period = settings.get('period', 14)
        self.overbought = settings.get('overbought', 70)
        self.oversold = settings.get('oversold', 30)
    
    def _calculate_rsi(self, candles: List[Dict]) -> Optional[float]:
        """Расчёт RSI."""
        if len(candles) < self.period + 1:
            return None
        
        # Берём close цены
        closes = [c['close'] for c in candles[-(self.period + 1):]]
        
        # Считаем изменения
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        # Средние значения
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def should_buy(self, candles: List[Dict]) -> Optional[str]:
        """Проверка сигнала RSI."""
        rsi = self._calculate_rsi(candles)
        
        if rsi is None:
            return None
        
        # CALL если перепроданность
        if rsi < self.oversold:
            return "call"
        
        # PUT если перекупленность
        if rsi > self.overbought:
            return "put"
        
        return None
    
    def get_settings_ui(self) -> Dict:
        return {
            "period": {
                "type": "number",
                "label": "Период RSI",
                "default": 14,
                "min": 3,
                "max": 50
            },
            "overbought": {
                "type": "number",
                "label": "Уровень перекупленности",
                "default": 70,
                "min": 50,
                "max": 90
            },
            "oversold": {
                "type": "number",
                "label": "Уровень перепроданности",
                "default": 30,
                "min": 10,
                "max": 50
            }
        }


# Реестр стратегий
STRATEGIES = {
    "simple": SimpleStrategy,
    "rsi": RSIStrategy,
    # TODO: Добавить MACD, Bollinger, etc.
}


def get_strategy(name: str, settings: Dict) -> Optional[Strategy]:
    """Получение стратегии по названию."""
    strategy_class = STRATEGIES.get(name)
    if strategy_class:
        return strategy_class(settings)
    return None


def list_strategies() -> List[Dict]:
    """Список доступных стратегий."""
    return [
        {"id": name, "name": cls.name, "description": cls.description}
        for name, cls in STRATEGIES.items()
    ]


__all__ = [
    "Strategy",
    "SimpleStrategy",
    "RSIStrategy",
    "get_strategy",
    "list_strategies",
]
