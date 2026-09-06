"""
Торговая серия — последовательность сделок до первого выигрыша.

Используется для отслеживания мартингейла:
- Серия начинается с сигнала по активу
- Продолжается до первого выигрыша или исчерпания шагов мартингейла
- После выигрыша серия завершается и начинается новая
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
from core.market_data import Deal


@dataclass
class TradeSeries:
    """
    Торговая серия — последовательность сделок мартингейла.

    Attributes:
        series_id: Уникальный ID серии (формат: {asset}_{timestamp})
        strategy_id: ID стратегии
        symbol: Актив
        start_time: Время начала серии
        end_time: Время завершения (если завершена)
        deals: Список сделок в серии
        status: Статус серии
        total_invested: Общая сумма вложений
        total_return: Общая сумма возврата
        total_profit: Общая прибыль/убыток
    """
    series_id: str
    strategy_id: str
    symbol: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    deals: List[Deal] = field(default_factory=list)
    status: str = "active"  # "active", "won", "lost", "exhausted"
    
    # Статистика
    total_invested: float = 0.0
    total_return: float = 0.0
    total_profit: float = 0.0

    def add_deal(self, deal: Deal):
        """
        Добавить сделку в серию.

        Args:
            deal: Сделка для добавления
        """
        self.deals.append(deal)
        self.total_invested += deal.amount
        
        # Если сделка закрыта, обновляем возврат
        if deal.status == "closed" and deal.profit is not None:
            if deal.profit > 0:
                # Выигрышная сделка — добавляем прибыль + ставку
                self.total_return += deal.amount + deal.profit
            else:
                # Проигрышная сделка — ничего не возвращаем
                pass
        
        self.total_profit = self.total_return - self.total_invested

    def update_deal(self, trade_id: str, profit: float):
        """
        Обновить результат сделки.

        Args:
            trade_id: ID сделки
            profit: Прибыль/убыток
        """
        for deal in self.deals:
            if deal.trade_id == trade_id:
                deal.profit = profit
                deal.status = "closed"
                deal.close_time = datetime.now()
                
                # Пересчитываем статистику
                self._recalculate_stats()
                break

    def _recalculate_stats(self):
        """Пересчёт статистики серии."""
        self.total_invested = sum(d.amount for d in self.deals)
        self.total_return = 0.0
        
        for deal in self.deals:
            if deal.status == "closed":
                if deal.profit and deal.profit > 0:
                    # Выигрышная сделка — получаем ставку + прибыль
                    self.total_return += deal.amount + deal.profit
                # Проигрышная сделка — ничего не получаем
        
        self.total_profit = self.total_return - self.total_invested

    def is_won(self) -> bool:
        """
        Проверка: есть ли выигрышная сделка в серии.

        Returns:
            True если есть хотя бы одна выигрышная сделка
        """
        return any(d.is_won for d in self.deals)

    def is_active(self) -> bool:
        """
        Проверка: активна ли серия.

        Returns:
            True если серия ещё не завершена
        """
        return self.status == "active"

    def get_last_deal(self) -> Optional[Deal]:
        """
        Получить последнюю сделку в серии.

        Returns:
            Последняя сделка или None
        """
        return self.deals[-1] if self.deals else None

    def get_last_loss_deal(self) -> Optional[Deal]:
        """
        Получить последнюю проигрышную сделку.

        Returns:
            Последняя проигрышная сделка или None
        """
        for deal in reversed(self.deals):
            if deal.status == "closed" and (deal.profit is None or deal.profit <= 0):
                return deal
        return None

    def get_current_step(self) -> int:
        """
        Получить текущий шаг мартингейла.

        Returns:
            Номер текущего шага (0 = первая сделка)
        """
        if not self.deals:
            return 0
        return max(d.martingale_step for d in self.deals)

    def close(self, status: str = "won"):
        """
        Завершить серию.

        Args:
            status: Статус завершения ("won", "lost", "exhausted")
        """
        self.end_time = datetime.now()
        self.status = status
        self._recalculate_stats()

    def get_next_deal_amount(self, base_amount: float, martingale_steps: List[Dict]) -> float:
        """
        Рассчитать сумму следующей сделки с учётом мартингейла.

        Args:
            base_amount: Базовая сумма (первой сделки)
            martingale_steps: Конфигурация шагов мартингейла

        Returns:
            Сумма следующей сделки
        """
        current_step = self.get_current_step()
        
        if current_step < 0 or current_step >= len(martingale_steps):
            return base_amount
        
        step_config = martingale_steps[current_step]
        ratio = step_config.get("ratio", 2.0)
        
        # Если auto_ratio=True, рассчитываем коэффициент автоматически
        if step_config.get("auto_ratio", True):
            # Рассчитываем коэффициент для покрытия убытков и получения прибыли
            total_loss = abs(self.total_profit) if self.total_profit < 0 else 0
            min_profit = step_config.get("min_profit", 75) / 100.0
            
            # Формула: (total_loss + base_amount * min_profit) / (profit_percent / 100)
            # Упрощённо: base_amount * ratio
            return base_amount * ratio
        else:
            return base_amount * ratio

    def get_next_deal_duration(self, base_duration: int, martingale_steps: List[Dict]) -> int:
        """
        Получить длительность следующей сделки.

        Args:
            base_duration: Базовая длительность
            martingale_steps: Конфигурация шагов мартингейла

        Returns:
            Длительность следующей сделки
        """
        current_step = self.get_current_step()
        
        if current_step < 0 or current_step >= len(martingale_steps):
            return base_duration
        
        step_config = martingale_steps[current_step]
        expiration = step_config.get("expiration", 0)
        
        return expiration if expiration > 0 else base_duration

    def get_next_deal_direction(self, last_direction: str, martingale_steps: List[Dict]) -> str:
        """
        Получить направление следующей сделки.

        Args:
            last_direction: Направление последней сделки
            martingale_steps: Конфигурация шагов мартингейла

        Returns:
            Направление следующей сделки
        """
        current_step = self.get_current_step()
        
        if current_step < 0 or current_step >= len(martingale_steps):
            return last_direction
        
        step_config = martingale_steps[current_step]
        direction = step_config.get("direction", "previous")
        
        if direction == "previous":
            return last_direction
        elif direction == "opposite":
            return "call" if last_direction == "put" else "put"
        else:
            return direction  # "call" или "put"

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "series_id": self.series_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "deals": [d.to_dict() for d in self.deals],
            "status": self.status,
            "total_invested": self.total_invested,
            "total_return": self.total_return,
            "total_profit": self.total_profit
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeSeries':
        """Создание из словаря."""
        series = cls(
            series_id=data.get("series_id", ""),
            strategy_id=data.get("strategy_id", ""),
            symbol=data.get("symbol", ""),
            start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else datetime.now(),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            status=data.get("status", "active"),
            total_invested=float(data.get("total_invested", 0)),
            total_return=float(data.get("total_return", 0)),
            total_profit=float(data.get("total_profit", 0))
        )
        
        for deal_data in data.get("deals", []):
            series.deals.append(Deal.from_dict(deal_data))
        
        return series


class TradeSeriesManager:
    """
    Менеджер торговых серий.

    Управляет активными и завершёнными сериями:
    - Создание новых серий
    - Обновление результатов сделок
    - Завершение серий
    - История серий
    """

    def __init__(self):
        self._active_series: Dict[str, TradeSeries] = {}  # series_id -> TradeSeries
        self._history: List[TradeSeries] = []

    def create_series(self, strategy_id: str, symbol: str) -> TradeSeries:
        """
        Создать новую торговую серию.

        Args:
            strategy_id: ID стратегии
            symbol: Актив

        Returns:
            Новая торговая серия
        """
        timestamp = int(datetime.now().timestamp() * 1000)
        series_id = f"{symbol}_{timestamp}"
        
        series = TradeSeries(
            series_id=series_id,
            strategy_id=strategy_id,
            symbol=symbol
        )
        
        self._active_series[series_id] = series
        return series

    def get_series(self, series_id: str) -> Optional[TradeSeries]:
        """
        Получить серию по ID.

        Args:
            series_id: ID серии

        Returns:
            Серия или None
        """
        return self._active_series.get(series_id)

    def get_active_series(self, strategy_id: str, symbol: str) -> Optional[TradeSeries]:
        """
        Получить активную серию для стратегии и актива.

        Args:
            strategy_id: ID стратегии
            symbol: Актив

        Returns:
            Активная серия или None
        """
        for series in self._active_series.values():
            if series.strategy_id == strategy_id and series.symbol == symbol and series.is_active():
                return series
        return None

    def get_active_series_for_strategy(self, strategy_id: str) -> List[TradeSeries]:
        """
        Получить все активные серии для стратегии.

        Args:
            strategy_id: ID стратегии

        Returns:
            Список активных серий
        """
        return [
            series for series in self._active_series.values()
            if series.strategy_id == strategy_id and series.is_active()
        ]

    def add_deal_to_series(self, series_id: str, deal: Deal):
        """
        Добавить сделку в серию.

        Args:
            series_id: ID серии
            deal: Сделка
        """
        series = self._active_series.get(series_id)
        if series:
            series.add_deal(deal)

    def update_deal_result(self, series_id: str, trade_id: str, profit: float):
        """
        Обновить результат сделки.

        Args:
            series_id: ID серии
            trade_id: ID сделки
            profit: Прибыль/убыток
        """
        series = self._active_series.get(series_id)
        if series:
            series.update_deal(trade_id, profit)
            
            # Если сделка выигрышная, завершаем серию
            if profit > 0:
                self.close_series(series_id, "won")

    def close_series(self, series_id: str, status: str = "won"):
        """
        Завершить серию.

        Args:
            series_id: ID серии
            status: Статус завершения
        """
        series = self._active_series.get(series_id)
        if series:
            series.close(status)
            self._history.append(series)
            del self._active_series[series_id]

    def get_history(self, limit: int = 50) -> List[TradeSeries]:
        """
        Получить историю серий.

        Args:
            limit: Максимальное количество

        Returns:
            Список завершённых серий
        """
        return self._history[-limit:]

    def get_stats(self) -> Dict:
        """
        Получить статистику по сериям.

        Returns:
            Словарь со статистикой
        """
        total_series = len(self._history)
        won_series = sum(1 for s in self._history if s.status == "won")
        lost_series = sum(1 for s in self._history if s.status in ["lost", "exhausted"])
        
        total_profit = sum(s.total_profit for s in self._history)
        total_invested = sum(s.total_invested for s in self._history)
        
        return {
            "total_series": total_series,
            "won_series": won_series,
            "lost_series": lost_series,
            "win_rate": (won_series / total_series * 100) if total_series > 0 else 0,
            "total_profit": total_profit,
            "total_invested": total_invested,
            "active_series": len(self._active_series)
        }


__all__ = ["TradeSeries", "TradeSeriesManager"]
