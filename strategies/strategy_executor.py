"""
Исполнитель стратегии.

Движок для исполнения торговых стратегий:
- Получает котировки для каждого актива
- Вычисляет значения индикаторов на своих таймфреймах
- Проверяет условия сигналов
- Агрегирует сигналы от всех индикаторов
- Принимает решение о торговле
- Управляет мартингейлом

Пример использования:
    from strategies.strategy_executor import StrategyExecutor
    from core.strategy_models import StrategyConfig
    
    # Создание исполнителя
    executor = StrategyExecutor(strategy_config)
    
    # Анализ актива
    signal = executor.analyze("EURUSD_otc", candles)
    
    if signal.is_valid:
        print(f"Сигнал: {signal.direction}, Сила: {signal.strength}")
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

from core.strategy_models import StrategyConfig, IndicatorConfig
from core.market_data import Candle
from core.trade_series import TradeSeries, TradeSeriesManager
from strategies.indicator_registry import IndicatorRegistry
from strategies.indicator_base import IndicatorSignal


logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    """
    Торговый сигнал стратегии.

    Attributes:
        asset_id: ID актива
        direction: Направление ("call", "put", "none")
        strength: Сила сигнала (0.0-1.0)
        reason: Причина сигнала
        indicator_signals: Сигналы от отдельных индикаторов
        timestamp: Время сигнала
        strategy_id: ID стратегии
        series_id: ID торговой серии (если есть)
        martingale_step: Шаг мартингейла (0 = первая сделка)
    """
    asset_id: str
    direction: str = "none"
    strength: float = 0.0
    reason: str = ""
    indicator_signals: Dict[str, IndicatorSignal] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    strategy_id: str = ""
    series_id: str = ""
    martingale_step: int = 0

    @property
    def is_valid(self) -> bool:
        """Проверка валидности сигнала."""
        return self.direction in ["call", "put"] and self.strength > 0

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "asset_id": self.asset_id,
            "direction": self.direction,
            "strength": self.strength,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "strategy_id": self.strategy_id,
            "series_id": self.series_id,
            "martingale_step": self.martingale_step
        }


class StrategyExecutor:
    """
    Исполнитель торговой стратегии.

    Управляет исполнением стратегии:
    - Вычисление индикаторов
    - Генерация сигналов
    - Агрегация сигналов
    - Управление торговыми сериями
    - Мартингейл
    """

    def __init__(self, strategy: StrategyConfig):
        """
        Инициализация исполнителя.

        Args:
            strategy: Конфигурация стратегии
        """
        self.strategy = strategy
        self.strategy_id = strategy.id or "default"
        
        # Менеджер торговых серий
        self.series_manager = TradeSeriesManager()
        
        # Кэш индикаторов (по активу и таймфрейму)
        self._indicator_cache: Dict[str, Dict[int, Any]] = {}
        
        # Последние сигналы по активам
        self._last_signals: Dict[str, TradingSignal] = {}
        
        logger.info(f"[StrategyExecutor] Инициализирован: {strategy.name}")

    def analyze(self, asset_id: str, candles: List[Candle]) -> TradingSignal:
        """
        Анализ актива и генерация сигнала.

        Args:
            asset_id: ID актива
            candles: Список свечей

        Returns:
            TradingSignal с результатом анализа
        """
        # Проверка: разрешён ли актив
        if not self.strategy.is_asset_allowed(asset_id):
            return TradingSignal(
                asset_id=asset_id,
                direction="none",
                reason=f"Актив {asset_id} не разрешён стратегией",
                strategy_id=self.strategy_id
            )

        # Проверка регламента (время, мин. доходность)
        if not self._check_regulations(asset_id):
            return TradingSignal(
                asset_id=asset_id,
                direction="none",
                reason="Регламент не позволяет торговлю",
                strategy_id=self.strategy_id
            )

        # Вычисление индикаторов
        indicator_signals = {}
        for indicator_config in self.strategy.get_enabled_indicators():
            signal = self._compute_indicator(asset_id, indicator_config, candles)
            if signal:
                indicator_signals[indicator_config.name] = signal

        # Агрегация сигналов
        signal = self._aggregate_signals(asset_id, indicator_signals)
        signal.strategy_id = self.strategy_id

        # Проверка активной торговой серии
        active_series = self.series_manager.get_active_series(self.strategy_id, asset_id)
        if active_series:
            signal.series_id = active_series.series_id
            signal.martingale_step = active_series.get_current_step() + 1
        else:
            signal.martingale_step = 0

        # Сохранение последнего сигнала
        self._last_signals[asset_id] = signal

        return signal

    def _compute_indicator(
        self,
        asset_id: str,
        indicator_config: IndicatorConfig,
        candles: List[Candle]
    ) -> Optional[IndicatorSignal]:
        """
        Вычисление индикатора.

        Args:
            asset_id: ID актива
            indicator_config: Конфигурация индикатора
            candles: Список свечей

        Returns:
            IndicatorSignal или None
        """
        # Получаем индикатор из реестра
        indicator = IndicatorRegistry.create(
            indicator_config.type,
            parameters=indicator_config.parameters,
            conditions=indicator_config.conditions,
            timeframe=indicator_config.timeframe,
            bar_index=indicator_config.bar_index
        )

        if not indicator:
            logger.warning(f"[StrategyExecutor] Индикатор не найден: {indicator_config.type}")
            return None

        # Конвертируем свечи в формат индикатора
        candles_dict = [c.to_dict() for c in candles]

        # Вычисляем сигнал
        try:
            signal = indicator.check_signal(candles_dict)
            return signal
        except Exception as e:
            logger.error(f"[StrategyExecutor] Ошибка вычисления {indicator_config.type}: {e}")
            return None

    def _aggregate_signals(
        self,
        asset_id: str,
        indicator_signals: Dict[str, IndicatorSignal]
    ) -> TradingSignal:
        """
        Агрегация сигналов от индикаторов.

        Args:
            asset_id: ID актива
            indicator_signals: Сигналы от индикаторов

        Returns:
            TradingSignal с агрегированным результатом
        """
        if not indicator_signals:
            return TradingSignal(
                asset_id=asset_id,
                direction="none",
                reason="Нет сигналов от индикаторов",
                strategy_id=self.strategy_id
            )

        # Подсчёт голосов
        call_count = 0
        put_count = 0
        call_strength = 0.0
        put_strength = 0.0
        reasons = []

        for name, signal in indicator_signals.items():
            if signal.direction == "call":
                call_count += 1
                call_strength += signal.strength
                reasons.append(f"{name}: CALL ({signal.strength:.2f})")
            elif signal.direction == "put":
                put_count += 1
                put_strength += signal.strength
                reasons.append(f"{name}: PUT ({signal.strength:.2f})")

        # Определение итогового сигнала
        total_indicators = len(indicator_signals)
        min_agreement = self.strategy.min_agreement

        if self.strategy.use_weights:
            # Взвешенное голосование
            if call_strength > put_strength and call_strength >= min_agreement:
                direction = "call"
                strength = min(1.0, call_strength / total_indicators)
                reason = f"CALL: {call_count} из {total_indicators} | Сила: {strength:.2f}"
            elif put_strength > call_strength and put_strength >= min_agreement:
                direction = "put"
                strength = min(1.0, put_strength / total_indicators)
                reason = f"PUT: {put_count} из {total_indicators} | Сила: {strength:.2f}"
            else:
                direction = "none"
                strength = 0.0
                reason = "Нет согласия индикаторов"
        else:
            # Простое большинство
            if call_count >= min_agreement and call_count > put_count:
                direction = "call"
                strength = call_count / total_indicators
                reason = f"CALL: {call_count} из {total_indicators} индикаторов"
            elif put_count >= min_agreement and put_count > call_count:
                direction = "put"
                strength = put_count / total_indicators
                reason = f"PUT: {put_count} из {total_indicators} индикаторов"
            else:
                direction = "none"
                strength = 0.0
                reason = "Нет согласия индикаторов"

        return TradingSignal(
            asset_id=asset_id,
            direction=direction,
            strength=strength,
            reason=reason + " | " + ", ".join(reasons[:3]),
            indicator_signals=indicator_signals,
            strategy_id=self.strategy_id
        )

    def _check_regulations(self, asset_id: str) -> bool:
        """
        Проверка регламента.

        Args:
            asset_id: ID актива

        Returns:
            True если регламент позволяет торговлю
        """
        regulations = self.strategy.regulations

        # Проверка времени
        now = datetime.now()
        time_from = datetime.strptime(regulations.time_from, "%H:%M").time()
        time_to = datetime.strptime(regulations.time_to, "%H:%M").time()
        
        if time_from <= time_to:
            # Обычный диапазон (например, 09:00-17:00)
            if not (time_from <= now.time() <= time_to):
                return False
        else:
            # Переход через полночь (например, 22:00-06:00)
            if not (now.time() >= time_from or now.time() <= time_to):
                return False

        # Проверка дня недели
        if now.weekday() not in regulations.work_days:
            return False

        # Проверка мин. доходности (здесь должна быть логика проверки доходности актива)
        # Пока заглушка
        min_profit = regulations.min_profit
        # if asset_profit < min_profit: return False

        return True

    # ==========================================================================
    # УПРАВЛЕНИЕ ТОРГОВЫМИ СЕРИЯМИ
    # ==========================================================================

    def start_trade_series(
        self,
        asset_id: str,
        direction: str,
        amount: float,
        duration: int
    ) -> TradeSeries:
        """
        Запуск новой торговой серии.

        Args:
            asset_id: ID актива
            direction: Направление ("call" или "put")
            amount: Сумма сделки
            duration: Длительность в секундах

        Returns:
            Новая торговая серия
        """
        series = self.series_manager.create_series(self.strategy_id, asset_id)
        logger.info(f"[StrategyExecutor] Новая серия: {series.series_id}")
        return series

    def get_active_series(self, asset_id: str) -> Optional[TradeSeries]:
        """
        Получение активной серии для актива.

        Args:
            asset_id: ID актива

        Returns:
            Активная серия или None
        """
        return self.series_manager.get_active_series(self.strategy_id, asset_id)

    def has_active_series(self, asset_id: str) -> bool:
        """
        Проверка: есть ли активная серия для актива.

        Args:
            asset_id: ID актива

        Returns:
            True если есть активная серия
        """
        series = self.get_active_series(asset_id)
        return series is not None and series.is_active()

    def get_next_martingale_params(
        self,
        asset_id: str,
        base_amount: float,
        base_duration: int,
        last_direction: str
    ) -> Tuple[float, int, str]:
        """
        Получение параметров для следующей сделки мартингейла.

        Args:
            asset_id: ID актива
            base_amount: Базовая сумма
            base_duration: Базовая длительность
            last_direction: Направление последней сделки

        Returns:
            (amount, duration, direction)
        """
        series = self.get_active_series(asset_id)
        if not series:
            return base_amount, base_duration, last_direction

        current_step = series.get_current_step()
        martingale_config = self.strategy.martingale

        # Проверка: достигнут ли максимум шагов
        if current_step >= martingale_config.max_steps - 1:
            return base_amount, base_duration, last_direction

        # Получаем конфигурацию следующего шага
        next_step_config = martingale_config.get_step(current_step + 1)
        if not next_step_config:
            return base_amount, base_duration, last_direction

        # Расчёт суммы
        if next_step_config.auto_ratio:
            # Авто-расчёт коэффициента для покрытия убытков
            total_loss = abs(series.total_profit) if series.total_profit < 0 else 0
            min_profit = next_step_config.min_profit / 100.0
            # Формула: (total_loss + base_amount) / (profit_percent / 100)
            # Упрощённо: base_amount * ratio
            amount = base_amount * next_step_config.ratio
        else:
            amount = base_amount * next_step_config.ratio

        # Длительность
        duration = next_step_config.expiration if next_step_config.expiration > 0 else base_duration

        # Направление
        if next_step_config.direction == "previous":
            direction = last_direction
        elif next_step_config.direction == "opposite":
            direction = "call" if last_direction == "put" else "put"
        else:
            direction = next_step_config.direction  # "call" или "put"

        return amount, duration, direction

    def complete_trade_series(
        self,
        series_id: str,
        won: bool
    ):
        """
        Завершение торговой серии.

        Args:
            series_id: ID серии
            won: True если серия выигрышная
        """
        series = self.series_manager.get_series(series_id)
        if not series:
            return

        if won:
            # Выигрыш — завершаем серию
            self.series_manager.close_series(series_id, "won")
            logger.info(f"[StrategyExecutor] Серия завершена (win): {series_id}")
        else:
            # Проигрыш — проверяем, есть ли ещё шаги мартингейла
            current_step = series.get_current_step()
            if current_step >= self.strategy.martingale.max_steps - 1:
                # Достигнут максимум — завершаем серию
                self.series_manager.close_series(series_id, "exhausted")
                logger.info(f"[StrategyExecutor] Серия завершена (exhausted): {series_id}")

    def add_deal_to_series(
        self,
        series_id: str,
        deal: Any
    ):
        """
        Добавление сделки в серию.

        Args:
            series_id: ID серии
            deal: Сделка (Deal)
        """
        self.series_manager.add_deal_to_series(series_id, deal)

    def update_series_result(
        self,
        series_id: str,
        trade_id: str,
        profit: float
    ):
        """
        Обновление результата сделки в серии.

        Args:
            series_id: ID серии
            trade_id: ID сделки
            profit: Прибыль/убыток
        """
        self.series_manager.update_deal_result(series_id, trade_id, profit)
        
        # Если сделка выигрышная, завершаем серию
        if profit > 0:
            self.complete_trade_series(series_id, won=True)

    # ==========================================================================
    # СТАТИСТИКА
    # ==========================================================================

    def get_stats(self) -> Dict:
        """
        Получение статистики исполнителя.

        Returns:
            Словарь со статистикой
        """
        series_stats = self.series_manager.get_stats()
        
        return {
            "strategy_name": self.strategy.name,
            "strategy_id": self.strategy_id,
            "total_indicators": len(self.strategy.indicators),
            "enabled_indicators": len(self.strategy.get_enabled_indicators()),
            "total_assets": len(self.strategy.assets),
            "series": series_stats,
            "last_signals": {
                asset_id: signal.to_dict()
                for asset_id, signal in self._last_signals.items()
            }
        }

    def reset(self):
        """Сброс состояния исполнителя."""
        self._indicator_cache.clear()
        self._last_signals.clear()
        logger.info("[StrategyExecutor] Сброшен")


__all__ = [
    "TradingSignal",
    "StrategyExecutor"
]
