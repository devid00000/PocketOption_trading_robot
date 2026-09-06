"""
Конкретные торговые стратегии.
"""

from typing import List, Dict
from strategies.base import BaseStrategy, Signal
from strategies.indicators import TechnicalIndicators, IndicatorResult
from core.market_data import Candle


# ==============================================================================
# RSI СТРАТЕГИИ
# ==============================================================================

class RSIStrategy(BaseStrategy):
    """
    Стратегия на основе RSI.

    Логика:
    - RSI < oversold -> CALL (перепроданность)
    - RSI > overbought -> PUT (перекупленность)
    """

    def __init__(self, name: str = "RSI Strategy", config: Dict = None):
        default_config = {
            "period": 14,
            "overbought": 70,
            "oversold": 30,
            "price_type": "close",
            "signal_strength": True  # Усиливать сигнал при дивергенции
        }
        super().__init__(name=name, config={**default_config, **(config or {})})

    def analyze(self, candles: List[Candle]) -> Signal:
        if len(candles) < self.config["period"] + 1:
            return Signal(direction="none", strength=0, reason="Недостаточно данных")

        # Конвертируем в dict для индикатора
        candles_dict = [c.to_dict() for c in candles]

        # Расчёт RSI
        rsi_result: IndicatorResult = TechnicalIndicators.rsi(
            candles_dict,
            period=self.config["period"],
            price_type=self.config["price_type"],
            overbought=self.config["overbought"],
            oversold=self.config["oversold"]
        )

        rsi_value = rsi_result.value

        # Определение направления и силы сигнала
        if rsi_value <= self.config["oversold"]:
            direction = "call"
            # Чем ниже RSI, тем сильнее сигнал
            strength = min(100, (self.config["oversold"] - rsi_value) * 2 + 50)
            reason = f"RSI перепроданность: {rsi_value:.1f} < {self.config['oversold']}"
        elif rsi_value >= self.config["overbought"]:
            direction = "put"
            # Чем выше RSI, тем сильнее сигнал
            strength = min(100, (rsi_value - self.config["overbought"]) * 2 + 50)
            reason = f"RSI перекупленность: {rsi_value:.1f} > {self.config['overbought']}"
        else:
            direction = "none"
            strength = 0
            reason = f"RSI в нейтральной зоне: {rsi_value:.1f}"

        signal = Signal(
            direction=direction,
            strength=strength,
            reason=reason,
            metadata={"rsi": rsi_value, **rsi_result.metadata}
        )

        self._save_signal(signal)
        return signal


class RSIDivergenceStrategy(BaseStrategy):
    """
    Стратегия дивергенции RSI.

    Логика:
    - Бычья дивергенция: цена делает новый минимум, RSI - нет -> CALL
    - Медвежья дивергенция: цена делает новый максимум, RSI - нет -> PUT
    """

    def __init__(self, name: str = "RSI Divergence", config: Dict = None):
        default_config = {
            "period": 14,
            "lookback": 5,  # Количество свечей для поиска дивергенции
            "overbought": 70,
            "oversold": 30
        }
        super().__init__(name=name, config={**default_config, **(config or {})})

    def analyze(self, candles: List[Candle]) -> Signal:
        if len(candles) < self.config["period"] + self.config["lookback"] + 1:
            return Signal(direction="none", strength=0, reason="Недостаточно данных")

        candles_dict = [c.to_dict() for c in candles]

        # Текущий RSI
        current_rsi = TechnicalIndicators.rsi(
            candles_dict,
            period=self.config["period"]
        ).value

        # Поиск дивергенции
        lookback = self.config["lookback"]

        # Цены
        current_low = min(c.low for c in candles[-lookback:])
        prev_low = min(c.low for c in candles[-lookback*2:-lookback])

        current_high = max(c.high for c in candles[-lookback:])
        prev_high = max(c.high for c in candles[-lookback*2:-lookback])

        # RSI значения
        rsi_values = []
        for i in range(len(candles) - self.config["period"] - lookback, len(candles) - self.config["period"]):
            if i >= 0:
                rsi_val = TechnicalIndicators.rsi(
                    [c.to_dict() for c in candles[i:i+self.config["period"]]],
                    period=self.config["period"]
                ).value
                rsi_values.append(rsi_val)

        if len(rsi_values) < lookback * 2:
            return Signal(direction="none", strength=0, reason="Недостаточно данных RSI")

        current_rsi_avg = sum(rsi_values[-lookback:]) / lookback
        prev_rsi_avg = sum(rsi_values[:lookback]) / lookback

        # Бычья дивергенция
        if current_low < prev_low and current_rsi_avg > prev_rsi_avg:
            if current_rsi < self.config["oversold"] + 10:
                signal = Signal(
                    direction="call",
                    strength=75,
                    reason=f"Бычья дивергенция (RSI: {current_rsi:.1f})",
                    metadata={"type": "bullish_divergence"}
                )
                self._save_signal(signal)
                return signal

        # Медвежья дивергенция
        if current_high > prev_high and current_rsi_avg < prev_rsi_avg:
            if current_rsi > self.config["overbought"] - 10:
                signal = Signal(
                    direction="put",
                    strength=75,
                    reason=f"Медвежья дивергенция (RSI: {current_rsi:.1f})",
                    metadata={"type": "bearish_divergence"}
                )
                self._save_signal(signal)
                return signal

        return Signal(direction="none", strength=0, reason="Нет дивергенции")


# ==============================================================================
# BOLLINGER BANDS СТРАТЕГИИ
# ==============================================================================

class BollingerBandsStrategy(BaseStrategy):
    """
    Стратегия на основе полос Боллинджера.

    Логика:
    - Цена касается нижней полосы -> CALL (отскок вверх)
    - Цена касается верхней полосы -> PUT (отскок вниз)
    - Пробой полосы с сильным движением -> сигнал по тренду
    """

    def __init__(self, name: str = "Bollinger Bands", config: Dict = None):
        default_config = {
            "period": 20,
            "std_dev": 2.0,
            "price_type": "close",
            "breakout_mode": False  # Режим пробоя
        }
        super().__init__(name=name, config={**default_config, **(config or {})})

    def analyze(self, candles: List[Candle]) -> Signal:
        if len(candles) < self.config["period"]:
            return Signal(direction="none", strength=0, reason="Недостаточно данных")

        candles_dict = [c.to_dict() for c in candles]

        bb_result: IndicatorResult = TechnicalIndicators.bollinger_bands(
            candles_dict,
            period=self.config["period"],
            std_dev=self.config["std_dev"],
            price_type=self.config["price_type"]
        )

        percent_b = bb_result.metadata.get("percent_b", 0.5)
        bandwidth = bb_result.metadata.get("bandwidth", 0)

        if self.config["breakout_mode"]:
            # Режим пробоя
            if percent_b > 1.0 and bandwidth > 0.1:
                direction = "call"
                strength = min(100, (percent_b - 1) * 100 + 50)
                reason = f"Прой верхней полосы BB ({{percent_b:.2f}})"
            elif percent_b < 0.0 and bandwidth > 0.1:
                direction = "put"
                strength = min(100, (0 - percent_b) * 100 + 50)
                reason = f"Пробой нижней полосы BB (percent_b: {percent_b:.2f})"
            else:
                direction = "none"
                strength = 0
                reason = f"Цена внутри полос BB (percent_b: {percent_b:.2f})"
        else:
            # Режим отскока
            if percent_b <= 0:
                direction = "call"
                strength = min(100, (0 - percent_b + 0.5) * 100)
                reason = f"Цена у нижней полосы BB (percent_b: {percent_b:.2f})"
            elif percent_b >= 1:
                direction = "put"
                strength = min(100, (percent_b - 0.5) * 100)
                reason = f"Цена у верхней полосы BB (percent_b: {percent_b:.2f})"
            else:
                direction = "none"
                strength = 0
                reason = f"Цена внутри полос BB (percent_b: {percent_b:.2f})"

        signal = Signal(
            direction=direction,
            strength=strength,
            reason=reason,
            metadata=bb_result.metadata
        )

        self._save_signal(signal)
        return signal


# ==============================================================================
# MACD СТРАТЕГИИ
# ==============================================================================

class MACDStrategy(BaseStrategy):
    """
    Стратегия на основе MACD.

    Логика:
    - MACD пересекает сигнальную линию снизу вверх -> CALL
    - MACD пересекает сигнальную линию сверху вниз -> PUT
    - Гистограмма меняет знак -> подтверждение
    """

    def __init__(self, name: str = "MACD Strategy", config: Dict = None):
        default_config = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "price_type": "close",
            "histogram_confirmation": True
        }
        super().__init__(name=name, config={**default_config, **(config or {})})

    def analyze(self, candles: List[Candle]) -> Signal:
        if len(candles) < self.config["slow_period"] + self.config["signal_period"]:
            return Signal(direction="none", strength=0, reason="Недостаточно данных")

        candles_dict = [c.to_dict() for c in candles]

        macd_result: IndicatorResult = TechnicalIndicators.macd(
            candles_dict,
            fast_period=self.config["fast_period"],
            slow_period=self.config["slow_period"],
            signal_period=self.config["signal_period"],
            price_type=self.config["price_type"]
        )

        macd_line = macd_result.metadata.get("macd_line", 0)
        signal_line = macd_result.metadata.get("signal_line", 0)
        histogram = macd_result.metadata.get("histogram", 0)

        direction = macd_result.signal
        strength = 50

        # Усиление сигнала гистограммой
        if self.config["histogram_confirmation"]:
            if direction == "call" and histogram > 0:
                strength = min(100, strength + abs(histogram) * 10)
                reason = f"MACD бычий + гистограмма > 0 ({histogram:.4f})"
            elif direction == "put" and histogram < 0:
                strength = min(100, strength + abs(histogram) * 10)
                reason = f"MACD медвежий + гистограмма < 0 ({histogram:.4f})"
            else:
                strength = max(0, strength - 20)
                reason = f"MACD сигнал без подтверждения гистограммы"
        else:
            reason = f"MACD пересечение: MACD={macd_line:.4f}, Signal={signal_line:.4f}"

        if direction == "neutral":
            direction = "none"
            strength = 0
            reason = "Нет сигнала MACD"

        signal = Signal(
            direction=direction,
            strength=strength,
            reason=reason,
            metadata=macd_result.metadata
        )

        self._save_signal(signal)
        return signal


# ==============================================================================
# КОМБИНИРОВАННЫЕ СТРАТЕГИИ
# ==============================================================================

class MultiIndicatorStrategy(BaseStrategy):
    """
    Стратегия, объединяющая несколько индикаторов.

    Логика:
    - Сигнал только если несколько индикаторов согласны
    - Взвешенная сила сигнала
    """

    def __init__(self, name: str = "Multi-Indicator", config: Dict = None):
        default_config = {
            "use_rsi": True,
            "use_bb": True,
            "use_macd": True,
            "min_agreement": 2,  # Минимум индикаторов должны быть согласны
            "rsi_config": {"period": 14, "overbought": 70, "oversold": 30},
            "bb_config": {"period": 20, "std_dev": 2.0},
            "macd_config": {"fast_period": 12, "slow_period": 26, "signal_period": 9}
        }
        super().__init__(name=name, config={**default_config, **(config or {})})

    def analyze(self, candles: List[Candle]) -> Signal:
        if len(candles) < 30:
            return Signal(direction="none", strength=0, reason="Недостаточно данных")

        candles_dict = [c.to_dict() for c in candles]

        signals = []

        # RSI
        if self.config["use_rsi"]:
            rsi_result = TechnicalIndicators.rsi(
                candles_dict,
                period=self.config["rsi_config"]["period"],
                overbought=self.config["rsi_config"]["overbought"],
                oversold=self.config["rsi_config"]["oversold"]
            )
            if rsi_result.signal != "neutral":
                signals.append(("RSI", rsi_result.signal, 1))

        # Bollinger Bands
        if self.config["use_bb"]:
            bb_result = TechnicalIndicators.bollinger_bands(
                candles_dict,
                period=self.config["bb_config"]["period"],
                std_dev=self.config["bb_config"]["std_dev"]
            )
            if bb_result.signal != "neutral":
                signals.append(("BB", bb_result.signal, 1))

        # MACD
        if self.config["use_macd"]:
            macd_result = TechnicalIndicators.macd(
                candles_dict,
                fast_period=self.config["macd_config"]["fast_period"],
                slow_period=self.config["macd_config"]["slow_period"],
                signal_period=self.config["macd_config"]["signal_period"]
            )
            if macd_result.signal != "neutral":
                signals.append(("MACD", macd_result.signal, 1))

        if not signals:
            return Signal(direction="none", strength=0, reason="Нет сигналов индикаторов")

        # Подсчёт голосов
        call_count = sum(1 for _, sig, _ in signals if sig == "buy")
        put_count = sum(1 for _, sig, _ in signals if sig == "sell")

        total_signals = len(signals)
        min_agreement = self.config["min_agreement"]

        if call_count >= min_agreement and call_count > put_count:
            direction = "call"
            strength = (call_count / total_signals) * 100
            reason = f"CALL: {call_count}/{total_signals} индикаторов"
        elif put_count >= min_agreement and put_count > call_count:
            direction = "put"
            strength = (put_count / total_signals) * 100
            reason = f"PUT: {put_count}/{total_signals} индикаторов"
        else:
            direction = "none"
            strength = 0
            reason = f"Нет согласия ({call_count} CALL, {put_count} PUT)"

        signal = Signal(
            direction=direction,
            strength=strength,
            reason=reason,
            metadata={
                "call_count": call_count,
                "put_count": put_count,
                "total_signals": total_signals,
                "indicators": [s[0] for s in signals]
            }
        )

        self._save_signal(signal)
        return signal


# ==============================================================================
# ПРОСТАЯ СТРАТЕГИЯ (ДЛЯ ТЕСТИРОВАНИЯ)
# ==============================================================================

class SimpleStrategy(BaseStrategy):
    """
    Простая стратегия для тестирования.

    Логика:
    - Всегда CALL (для проверки механики торговли)
    """

    def __init__(self, name: str = "Simple Test", config: Dict = None):
        default_config = {
            "always_trade": True,
            "strength": 50
        }
        super().__init__(name=name, config={**default_config, **(config or {})})

    def analyze(self, candles: List[Candle]) -> Signal:
        if len(candles) < 2:
            return Signal(direction="none", strength=0, reason="Недостаточно данных")

        if self.config["always_trade"]:
            signal = Signal(
                direction="call",
                strength=self.config["strength"],
                reason="Тестовый сигнал (всегда CALL)",
                metadata={"test_mode": True}
            )
        else:
            # Чередование CALL/PUT для теста
            last_close = candles[-1].close
            prev_close = candles[-2].close

            if last_close > prev_close:
                direction = "call"
                reason = "Цена растёт"
            else:
                direction = "put"
                reason = "Цена падает"

            signal = Signal(
                direction=direction,
                strength=self.config["strength"],
                reason=reason
            )

        self._save_signal(signal)
        return signal


__all__ = [
    "RSIStrategy",
    "RSIDivergenceStrategy",
    "BollingerBandsStrategy",
    "MACDStrategy",
    "MultiIndicatorStrategy",
    "SimpleStrategy"
]
