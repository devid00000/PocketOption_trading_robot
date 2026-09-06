"""
Модели данных для рыночных данных.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
import uuid


@dataclass
class Candle:
    """
    Свеча.

    Attributes:
        symbol: ID актива (EURUSD_otc, BTCUSD_otc, etc.)
        timestamp: Время открытия свечи (Unix timestamp)
        open: Цена открытия
        high: Максимальная цена
        low: Минимальная цена
        close: Цена закрытия
        volume: Объем (опционально)
    """
    symbol: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    is_closed: bool = True

    @property
    def time(self) -> datetime:
        """Время свечи как datetime."""
        return datetime.fromtimestamp(self.timestamp)

    @property
    def is_bullish(self) -> bool:
        """Бычья свеча (закрытие выше открытия)."""
        return self.close >= self.open

    @property
    def is_bearish(self) -> bool:
        """Медвежья свеча (закрытие ниже открытия)."""
        return self.close < self.open

    @property
    def body_size(self) -> float:
        """Размер тела свечи."""
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        """Полный диапазон свечи (high - low)."""
        return self.high - self.low

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "is_closed": self.is_closed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Candle':
        """Создание из словаря."""
        return cls(
            symbol=data.get("symbol", ""),
            timestamp=data.get("timestamp", 0),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", 0)),
            volume=data.get("volume"),
            is_closed=bool(data.get("is_closed", True))
        )


@dataclass
class Tick:
    """
    Тик (мгновенная цена).

    Attributes:
        symbol: ID актива
        timestamp: Время тика (Unix timestamp)
        price: Цена
    """
    symbol: str
    timestamp: int
    price: float

    @property
    def time(self) -> datetime:
        """Время тика как datetime."""
        return datetime.fromtimestamp(self.timestamp)

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "price": self.price
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Tick':
        """Создание из словаря."""
        return cls(
            symbol=data.get("symbol", ""),
            timestamp=data.get("timestamp", 0),
            price=float(data.get("price", 0))
        )


@dataclass
class Balance:
    """
    Баланс счета.

    Attributes:
        demo: Баланс демо-счета
        real: Баланс реального счета
        is_demo: Текущий режим (True = демо)
    """
    demo: float = 0.0
    real: float = 0.0
    is_demo: bool = True

    @property
    def current(self) -> float:
        """Текущий баланс в зависимости от режима."""
        return self.demo if self.is_demo else self.real

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "demo": self.demo,
            "real": self.real,
            "is_demo": self.is_demo
        }


@dataclass
class Subscription:
    """
    Подписка на актив.

    Attributes:
        symbol: ID актива
        period: Период свечи в секундах (60, 300, 900, etc.)
        active: Статус подписки
    """
    symbol: str
    period: int
    active: bool = True

    @property
    def key(self) -> str:
        """Уникальный ключ подписки."""
        return f"{self.symbol}_{self.period}"

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "symbol": self.symbol,
            "period": self.period,
            "active": self.active
        }


@dataclass
class Deal:
    """
    Сделка.

    Attributes:
        trade_id: ID сделки (UUID)
        strategy_id: ID стратегии
        series_id: ID торговой серии (для мартингейла)
        martingale_step: Шаг мартингейла (0 = первая сделка)
        parent_deal_id: ID родительской сделки (для мартингейла)
        symbol: ID актива
        direction: Направление ("call" или "put")
        amount: Сумма сделки
        duration: Длительность в секундах
        open_time: Время открытия
        close_time: Время закрытия (опционально)
        open_price: Цена открытия
        close_price: Цена закрытия (опционально)
        profit: Прибыль/убыток
        profit_percent: Процент прибыли актива
        status: Статус ("pending", "open", "closed", "expired")
    """
    trade_id: str
    strategy_id: str
    series_id: str
    symbol: str
    direction: str
    amount: float
    duration: int
    open_time: datetime = field(default_factory=datetime.now)
    close_time: Optional[datetime] = None
    open_price: float = 0.0
    close_price: Optional[float] = None
    profit: Optional[float] = None
    profit_percent: int = 0
    status: str = "open"
    
    # Для мартингейла
    martingale_step: int = 0
    parent_deal_id: Optional[str] = None

    @property
    def is_won(self) -> bool:
        """Сделка выигрышная."""
        if self.profit is None:
            return False
        return self.profit > 0

    @property
    def profit_percent_actual(self) -> float:
        """Фактический процент прибыли/убытка."""
        if self.amount == 0:
            return 0.0
        return (self.profit / self.amount) * 100 if self.profit else 0.0

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "trade_id": self.trade_id,
            "strategy_id": self.strategy_id,
            "series_id": self.series_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "amount": self.amount,
            "duration": self.duration,
            "open_time": self.open_time.isoformat(),
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "open_price": self.open_price,
            "close_price": self.close_price,
            "profit": self.profit,
            "profit_percent": self.profit_percent,
            "status": self.status,
            "martingale_step": self.martingale_step,
            "parent_deal_id": self.parent_deal_id
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Deal':
        """Создание из словаря."""
        return cls(
            trade_id=data.get("trade_id", str(uuid.uuid4())),
            strategy_id=data.get("strategy_id", ""),
            series_id=data.get("series_id", ""),
            symbol=data.get("symbol", ""),
            direction=data.get("direction", ""),
            amount=float(data.get("amount", 0)),
            duration=int(data.get("duration", 60)),
            open_time=datetime.fromisoformat(data["open_time"]) if data.get("open_time") else datetime.now(),
            close_time=datetime.fromisoformat(data["close_time"]) if data.get("close_time") else None,
            open_price=float(data.get("open_price", 0)),
            close_price=float(data["close_price"]) if data.get("close_price") else None,
            profit=float(data["profit"]) if data.get("profit") is not None else None,
            profit_percent=int(data.get("profit_percent", 0)),
            status=data.get("status", "open"),
            martingale_step=int(data.get("martingale_step", 0)),
            parent_deal_id=data.get("parent_deal_id")
        )


__all__ = [
    "Candle",
    "Tick",
    "Balance",
    "Subscription",
    "Deal"
]
