"""
Технические индикаторы для торговых стратегий.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class IndicatorResult:
    """Результат вычисления индикатора."""
    value: float
    signal: str  # "buy", "sell", "neutral"
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TechnicalIndicators:
    """
    Коллекция технических индикаторов.

    Все индикаторы работают со списком свечей.
    Свеча ожидается как dict с ключами: open, high, low, close, volume
    """

    # ==========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ==========================================================================

    @staticmethod
    def _get_prices(candles: List[Dict], price_type: str = "close") -> np.ndarray:
        """
        Получение массива цен из свечей.

        Args:
            candles: Список свечей
            price_type: Тип цены (open, high, low, close, hl2, hlc3, ohlc4)

        Returns:
            numpy массив цен
        """
        if not candles:
            return np.array([])

        if price_type == "open":
            return np.array([float(c["open"]) for c in candles])
        elif price_type == "high":
            return np.array([float(c["high"]) for c in candles])
        elif price_type == "low":
            return np.array([float(c["low"]) for c in candles])
        elif price_type == "close":
            return np.array([float(c["close"]) for c in candles])
        elif price_type == "hl2":
            return np.array([(float(c["high"]) + float(c["low"])) / 2 for c in candles])
        elif price_type == "hlc3":
            return np.array([(float(c["high"]) + float(c["low"]) + float(c["close"])) / 3 for c in candles])
        elif price_type == "ohlc4":
            return np.array([(float(c["open"]) + float(c["high"]) + float(c["low"]) + float(c["close"])) / 4 for c in candles])
        else:
            return np.array([float(c["close"]) for c in candles])

    @staticmethod
    def _sma(data: np.ndarray, period: int) -> np.ndarray:
        """Простая скользящая средняя."""
        if len(data) < period:
            return np.array([])
        result = np.convolve(data, np.ones(period)/period, mode='valid')
        return np.pad(result, (len(data) - len(result), 0), mode='constant', constant_values=np.nan)

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Экспоненциальная скользящая средняя."""
        if len(data) < period:
            return np.array([])

        multiplier = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[:period] = np.mean(data[:period])

        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]

        return ema

    # ==========================================================================
    # ИНДИКАТОРЫ
    # ==========================================================================

    @staticmethod
    def rsi(candles: List[Dict], period: int = 14, price_type: str = "close",
            overbought: float = 70, oversold: float = 30) -> IndicatorResult:
        """
        RSI (Relative Strength Index).

        Args:
            candles: Список свечей
            period: Период расчёта
            price_type: Тип цены
            overbought: Уровень перекупленности
            oversold: Уровень перепроданности

        Returns:
            IndicatorResult с текущим значением RSI
        """
        if len(candles) < period + 1:
            return IndicatorResult(value=50.0, signal="neutral", metadata={"error": "Недостаточно данных"})

        prices = TechnicalIndicators._get_prices(candles, price_type)
        deltas = np.diff(prices)

        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:]) if len(gains) >= period else np.mean(gains)
        avg_loss = np.mean(losses[-period:]) if len(losses) >= period else np.mean(losses)

        if avg_loss == 0:
            rsi_value = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_value = 100 - (100 / (1 + rs))

        # Определение сигнала
        if rsi_value >= overbought:
            signal = "sell"
        elif rsi_value <= oversold:
            signal = "buy"
        else:
            signal = "neutral"

        return IndicatorResult(
            value=rsi_value,
            signal=signal,
            metadata={
                "period": period,
                "overbought": overbought,
                "oversold": oversold,
                "price_type": price_type
            }
        )

    @staticmethod
    def bollinger_bands(candles: List[Dict], period: int = 20, std_dev: float = 2.0,
                        price_type: str = "close") -> IndicatorResult:
        """
        Bollinger Bands.

        Args:
            candles: Список свечей
            period: Период средней линии
            std_dev: Количество стандартных отклонений
            price_type: Тип цены

        Returns:
            IndicatorResult с текущими значениями полос
        """
        if len(candles) < period:
            return IndicatorResult(value=0, signal="neutral", metadata={"error": "Недостаточно данных"})

        prices = TechnicalIndicators._get_prices(candles, price_type)

        # Средняя линия (SMA)
        middle = TechnicalIndicators._sma(prices, period)[-1]

        # Стандартное отклонение
        std = np.std(prices[-period:])

        # Верхняя и нижняя полосы
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        current_price = prices[-1]

        # Определение сигнала
        if current_price >= upper:
            signal = "sell"  # Цена у верхней полосы - возможный разворот вниз
        elif current_price <= lower:
            signal = "buy"   # Цена у нижней полосы - возможный разворот вверх
        else:
            signal = "neutral"

        # Процентное положение цены в полосах
        band_width = upper - lower
        if band_width > 0:
            percent_b = (current_price - lower) / band_width
        else:
            percent_b = 0.5

        return IndicatorResult(
            value=current_price,
            signal=signal,
            metadata={
                "upper": upper,
                "middle": middle,
                "lower": lower,
                "std_dev": std_dev,
                "period": period,
                "percent_b": percent_b,
                "bandwidth": band_width / middle if middle > 0 else 0
            }
        )

    @staticmethod
    def macd(candles: List[Dict], fast_period: int = 12, slow_period: int = 26,
             signal_period: int = 9, price_type: str = "close") -> IndicatorResult:
        """
        MACD (Moving Average Convergence Divergence).

        Args:
            candles: Список свечей
            fast_period: Быстрый период EMA
            slow_period: Медленный период EMA
            signal_period: Период сигнальной линии
            price_type: Тип цены

        Returns:
            IndicatorResult с текущими значениями MACD
        """
        if len(candles) < slow_period + signal_period:
            return IndicatorResult(value=0, signal="neutral", metadata={"error": "Недостаточно данных"})

        prices = TechnicalIndicators._get_prices(candles, price_type)

        # EMA быстрая и медленная
        ema_fast = TechnicalIndicators._ema(prices, fast_period)
        ema_slow = TechnicalIndicators._ema(prices, slow_period)

        # MACD линия
        macd_line = ema_fast - ema_slow

        # Сигнальная линия (EMA от MACD)
        signal_line = TechnicalIndicators._ema(macd_line[slow_period:], signal_period)

        # Гистограмма
        histogram = macd_line[-1] - signal_line[-1] if len(signal_line) > 0 else 0

        current_macd = macd_line[-1]
        current_signal = signal_line[-1] if len(signal_line) > 0 else 0

        # Определение сигнала
        if current_macd > current_signal and histogram > 0:
            signal = "buy"
        elif current_macd < current_signal and histogram < 0:
            signal = "sell"
        else:
            signal = "neutral"

        return IndicatorResult(
            value=current_macd,
            signal=signal,
            metadata={
                "macd_line": current_macd,
                "signal_line": current_signal,
                "histogram": histogram,
                "fast_period": fast_period,
                "slow_period": slow_period,
                "signal_period": signal_period
            }
        )

    @staticmethod
    def stochastic(candles: List[Dict], k_period: int = 14, d_period: int = 3,
                   slowdown: int = 3, overbought: float = 80,
                   oversold: float = 20) -> IndicatorResult:
        """
        Stochastic Oscillator.

        Args:
            candles: Список свечей
            k_period: Период %K
            d_period: Период %D (сглаживание %K)
            slowdown: Замедление
            overbought: Уровень перекупленности
            oversold: Уровень перепроданности

        Returns:
            IndicatorResult с текущими значениями Stochastic
        """
        if len(candles) < k_period + slowdown:
            return IndicatorResult(value=50, signal="neutral", metadata={"error": "Недостаточно данных"})

        lows = TechnicalIndicators._get_prices(candles, "low")
        highs = TechnicalIndicators._get_prices(candles, "high")
        closes = TechnicalIndicators._get_prices(candles, "close")

        # %K сырой
        raw_k = np.zeros(len(candles))
        for i in range(k_period - 1, len(candles)):
            lowest_low = np.min(lows[i - k_period + 1:i + 1])
            highest_high = np.max(highs[i - k_period + 1:i + 1])
            if highest_high - lowest_low > 0:
                raw_k[i] = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100
            else:
                raw_k[i] = 50

        # %K сглаженный
        k_values = TechnicalIndicators._sma(raw_k, slowdown)
        current_k = k_values[-1] if len(k_values) > 0 else 50

        # %D (SMA от %K)
        d_values = TechnicalIndicators._sma(k_values, d_period)
        current_d = d_values[-1] if len(d_values) > 0 else 50

        # Определение сигнала
        if current_k >= overbought:
            signal = "sell"
        elif current_k <= oversold:
            signal = "buy"
        else:
            signal = "neutral"

        # Пересечение
        if len(k_values) > 1 and len(d_values) > 0:
            if k_values[-2] < d_values[-1] and current_k > current_d:
                signal = "buy"  # %K пересекает %D снизу вверх
            elif k_values[-2] > d_values[-1] and current_k < current_d:
                signal = "sell"  # %K пересекает %D сверху вниз

        return IndicatorResult(
            value=current_k,
            signal=signal,
            metadata={
                "k": current_k,
                "d": current_d,
                "overbought": overbought,
                "oversold": oversold
            }
        )

    @staticmethod
    def cci(candles: List[Dict], period: int = 20,
            overbought: float = 100, oversold: float = -100) -> IndicatorResult:
        """
        CCI (Commodity Channel Index).

        Args:
            candles: Список свечей
            period: Период расчёта
            overbought: Уровень перекупленности
            oversold: Уровень перепроданности

        Returns:
            IndicatorResult с текущим значением CCI
        """
        if len(candles) < period:
            return IndicatorResult(value=0, signal="neutral", metadata={"error": "Недостаточно данных"})

        # Типичная цена
        tp = TechnicalIndicators._get_prices(candles, "hlc3")

        # SMA типичной цены
        sma_tp = TechnicalIndicators._sma(tp, period)

        # Mean Deviation
        deviations = []
        for i in range(period - 1, len(tp)):
            mean_dev = np.mean(np.abs(tp[i - period + 1:i + 1] - sma_tp[i]))
            deviations.append(mean_dev)

        if not deviations or deviations[-1] == 0:
            return IndicatorResult(value=0, signal="neutral", metadata={"error": "Деление на ноль"})

        cci_value = (tp[-1] - sma_tp[-1]) / (0.015 * deviations[-1])

        # Определение сигнала
        if cci_value >= overbought:
            signal = "sell"
        elif cci_value <= oversold:
            signal = "buy"
        else:
            signal = "neutral"

        return IndicatorResult(
            value=cci_value,
            signal=signal,
            metadata={
                "period": period,
                "overbought": overbought,
                "oversold": oversold
            }
        )

    @staticmethod
    def parabolic_sar(candles: List[Dict], step: float = 0.02,
                      max_step: float = 0.2) -> IndicatorResult:
        """
        Parabolic SAR.

        Args:
            candles: Список свечей
            step: Шаг ускорения
            max_step: Максимальный шаг

        Returns:
            IndicatorResult с текущим значением SAR
        """
        if len(candles) < 10:
            return IndicatorResult(value=0, signal="neutral", metadata={"error": "Недостаточно данных"})

        highs = TechnicalIndicators._get_prices(candles, "high")
        lows = TechnicalIndicators._get_prices(candles, "low")

        # Инициализация
        sar = np.zeros(len(candles))
        trend = 1  # 1 = восходящий, -1 = нисходящий
        af = step  # Фактор ускорения

        # Начальные значения
        if highs[1] > highs[0]:
            trend = 1
            sar[0] = lows[0]
            ep = highs[1]  # Экстремум
        else:
            trend = -1
            sar[0] = highs[0]
            ep = lows[1]

        # Расчёт SAR
        for i in range(1, len(candles)):
            sar[i] = sar[i-1] + af * (ep - sar[i-1])

            # Обновление экстремума
            if trend == 1:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + step, max_step)
                if lows[i] < sar[i]:
                    # Разворот
                    trend = -1
                    sar[i] = ep
                    ep = lows[i]
                    af = step
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + step, max_step)
                if highs[i] > sar[i]:
                    # Разворот
                    trend = 1
                    sar[i] = ep
                    ep = highs[i]
                    af = step

        current_sar = sar[-1]
        current_price = highs[-1]

        # Определение сигнала
        if current_price > current_sar:
            signal = "buy"
        else:
            signal = "sell"

        return IndicatorResult(
            value=current_sar,
            signal=signal,
            metadata={
                "sar": current_sar,
                "trend": "up" if trend == 1 else "down",
                "af": af,
                "ep": ep
            }
        )

    @staticmethod
    def super_trend(candles: List[Dict], period: int = 10,
                    multiplier: float = 3.0) -> IndicatorResult:
        """
        SuperTrend.

        Args:
            candles: Список свечей
            period: Период ATR
            multiplier: Множитель для полос

        Returns:
            IndicatorResult с текущим значением SuperTrend
        """
        if len(candles) < period + 10:
            return IndicatorResult(value=0, signal="neutral", metadata={"error": "Недостаточно данных"})

        highs = TechnicalIndicators._get_prices(candles, "high")
        lows = TechnicalIndicators._get_prices(candles, "low")
        closes = TechnicalIndicators._get_prices(candles, "close")

        # ATR
        tr = np.maximum(highs[1:] - lows[1:],
                        np.maximum(np.abs(highs[1:] - closes[:-1]),
                                   np.abs(lows[1:] - closes[:-1])))
        atr = TechnicalIndicators._sma(tr, period)

        # Базовая линия
        hl2 = (highs + lows) / 2

        # Полосы
        upper = hl2[period:] + (multiplier * atr)
        lower = hl2[period:] - (multiplier * atr)

        # SuperTrend
        st = np.zeros(len(upper))
        trend = np.zeros(len(upper))

        st[0] = upper[0]
        trend[0] = -1

        for i in range(1, len(upper)):
            if closes[period + i] > st[i-1]:
                st[i] = lower[i]
                trend[i] = 1
            else:
                st[i] = upper[i]
                trend[i] = -1

        current_st = st[-1]
        current_trend = trend[-1]

        signal = "buy" if current_trend == 1 else "sell"

        return IndicatorResult(
            value=current_st,
            signal=signal,
            metadata={
                "supertrend": current_st,
                "trend": "up" if current_trend == 1 else "down",
                "atr": atr[-1] if len(atr) > 0 else 0
            }
        )

    @staticmethod
    def ma_cross(candles: List[Dict], fast_period: int = 9,
                 slow_period: int = 21, ma_type: str = "ema",
                 price_type: str = "close") -> IndicatorResult:
        """
        Пересечение скользящих средних.

        Args:
            candles: Список свечей
            fast_period: Период быстрой MA
            slow_period: Период медленной MA
            ma_type: Тип MA (sma, ema)
            price_type: Тип цены

        Returns:
            IndicatorResult с сигналом пересечения
        """
        if len(candles) < slow_period + 5:
            return IndicatorResult(value=0, signal="neutral", metadata={"error": "Недостаточно данных"})

        prices = TechnicalIndicators._get_prices(candles, price_type)

        if ma_type == "ema":
            fast_ma = TechnicalIndicators._ema(prices, fast_period)
            slow_ma = TechnicalIndicators._ema(prices, slow_period)
        else:
            fast_ma = TechnicalIndicators._sma(prices, fast_period)
            slow_ma = TechnicalIndicators._sma(prices, slow_period)

        current_fast = fast_ma[-1]
        current_slow = slow_ma[-1]
        prev_fast = fast_ma[-2]
        prev_slow = slow_ma[-2]

        # Определение пересечения
        if prev_fast <= prev_slow and current_fast > current_slow:
            signal = "buy"  # Быстрое пересекло медленное снизу вверх
        elif prev_fast >= prev_slow and current_fast < current_slow:
            signal = "sell"  # Быстрое пересекло медленное сверху вниз
        else:
            signal = "neutral"

        return IndicatorResult(
            value=current_fast,
            signal=signal,
            metadata={
                "fast_ma": current_fast,
                "slow_ma": current_slow,
                "ma_type": ma_type,
                "fast_period": fast_period,
                "slow_period": slow_period
            }
        )


__all__ = [
    "IndicatorResult",
    "TechnicalIndicators"
]
