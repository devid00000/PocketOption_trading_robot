"""
Обёртки индикаторов для реестра.

Каждый индикатор наследуется от BaseIndicator и регистрируется в реестре.
"""

from typing import List, Dict, Any
from strategies.indicator_base import CandlesIndicator, register_indicator


# ==============================================================================
# RSI (Relative Strength Index)
# ==============================================================================

@register_indicator("rsi")
class RsiIndicator(CandlesIndicator):
    """
    RSI (Relative Strength Index) — Индекс относительной силы.

    Параметры:
        period: Период RSI (по умолчанию 14)
        overbought: Уровень перекупленности (по умолчанию 70)
        oversold: Уровень перепроданности (по умолчанию 30)
        price_type: Тип цены (close, open, high, low, hl2, hlc3, ohlc4)

    Условия:
        valRsi — текущее значение RSI
        tpl — уровень перекупленности
        btl — уровень перепроданности
    """

    DISPLAY_NAME = "RSI"
    DESCRIPTION = "Индекс относительной силы для определения перекупленности/перепроданности"

    DEFAULT_PARAMETERS = {
        "period": 14,
        "overbought": 70,
        "oversold": 30,
        "price_type": "close"
    }

    DEFAULT_CONDITIONS = {
        "call": "valRsi<btl",  # RSI < 30 → CALL
        "sell": "valRsi>tpl"   # RSI > 70 → PUT
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Линия индикатора находится в зоне перепроданности (RSI < oversold)",
        "B": "Линия индикатора находится в зоне перекупленности (RSI > overbought)",
        "C": "Линия индикатора находится в умеренной зоне",
        "D": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление RSI."""
        if len(candles) < self.parameters["period"] + 1:
            return {"valRsi": 50.0, "tpl": self.parameters["overbought"], "btl": self.parameters["oversold"]}

        prices = self._get_prices(candles, self.parameters["price_type"])
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        period = self.parameters["period"]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            rsi_value = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_value = 100 - (100 / (1 + rs))

        return {
            "valRsi": rsi_value,
            "tpl": self.parameters["overbought"],
            "btl": self.parameters["oversold"]
        }

    def _calculate_strength(self, context: Dict[str, Any], direction: str) -> float:
        """Расчёт силы сигнала."""
        rsi = context.get("valRsi", 50)
        oversold = context.get("btl", 30)
        overbought = context.get("tpl", 70)

        if direction == "call":
            # Чем ниже RSI, тем сильнее сигнал
            if rsi <= oversold:
                return min(1.0, (oversold - rsi) / oversold + 0.5)
            return 0.3
        elif direction == "put":
            # Чем выше RSI, тем сильнее сигнал
            if rsi >= overbought:
                return min(1.0, (rsi - overbought) / (100 - overbought) + 0.5)
            return 0.3
        return 0.0


# ==============================================================================
# Bollinger Bands
# ==============================================================================

@register_indicator("bollinger")
class BollingerBandsIndicator(CandlesIndicator):
    """
    Bollinger Bands — Полосы Боллинджера.

    Параметры:
        period: Период средней линии (по умолчанию 20)
        std_dev: Количество стандартных отклонений (по умолчанию 2.0)
        price_type: Тип цены

    Условия:
        price — текущая цена
        upper — верхняя полоса
        middle — средняя линия
        lower — нижняя полоса
        percent_b — положение цены в полосах (0-1)
    """

    DISPLAY_NAME = "Bollinger Bands"
    DESCRIPTION = "Полосы Боллинджера для определения волатильности и уровней перекупленности/перепроданности"

    DEFAULT_PARAMETERS = {
        "period": 20,
        "std_dev": 2.0,
        "price_type": "close"
    }

    DEFAULT_CONDITIONS = {
        "call": "price<lower",  # Цена ниже нижней полосы → CALL
        "sell": "price>upper"   # Цена выше верхней полосы → PUT
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Цена ниже нижней линии индикатора",
        "B": "Цена выше верхней линии индикатора",
        "C": "Цена находится между верхней и нижней линией",
        "D": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление полос Боллинджера."""
        import math
        
        period = self.parameters["period"]
        std_dev = self.parameters["std_dev"]
        
        if len(candles) < period:
            return {"price": 0, "upper": 0, "middle": 0, "lower": 0, "percent_b": 0.5}

        prices = self._get_prices(candles, self.parameters["price_type"])
        
        # Средняя линия (SMA)
        middle = sum(prices[-period:]) / period
        
        # Стандартное отклонение
        variance = sum((p - middle) ** 2 for p in prices[-period:]) / period
        std = math.sqrt(variance)
        
        # Полосы
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        current_price = prices[-1]
        
        # Процентное положение в полосах
        band_width = upper - lower
        percent_b = (current_price - lower) / band_width if band_width > 0 else 0.5

        return {
            "price": current_price,
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "percent_b": percent_b
        }


# ==============================================================================
# MACD (Moving Average Convergence Divergence)
# ==============================================================================

@register_indicator("macd")
class MacdIndicator(CandlesIndicator):
    """
    MACD — Схождение/расхождение скользящих средних.

    Параметры:
        fast_period: Быстрый период EMA (по умолчанию 12)
        slow_period: Медленный период EMA (по умолчанию 26)
        signal_period: Период сигнальной линии (по умолчанию 9)
        price_type: Тип цены

    Условия:
        macd — значение MACD
        signal — значение сигнальной линии
        histogram — гистограмма MACD
    """

    DISPLAY_NAME = "MACD"
    DESCRIPTION = "Схождение/расхождение скользящих средних для определения тренда"

    DEFAULT_PARAMETERS = {
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "price_type": "close"
    }

    DEFAULT_CONDITIONS = {
        "call": "macd>signal and macd>0",  # MACD выше Signal и выше 0
        "sell": "macd<signal and macd<0"   # MACD ниже Signal и ниже 0
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Значение MACD выше значения Signal",
        "B": "Значение MACD выше значения Signal, обе линии выше нуля",
        "C": "Значение MACD выше значения Signal, обе линии ниже нуля",
        "D": "Значение MACD выше нуля",
        "E": "Значение MACD ниже значения Signal",
        "F": "Значение MACD ниже значения Signal, обе линии выше нуля",
        "G": "Значение MACD ниже значения Signal, обе линии ниже нуля",
        "H": "Значение MACD ниже нуля",
        "K": "MACD пересекает Signal сверху вниз (текущий бар)",
        "L": "MACD пересекает Signal снизу вверх (текущий бар)",
        "M": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление MACD."""
        fast = self.parameters["fast_period"]
        slow = self.parameters["slow_period"]
        signal_period = self.parameters["signal_period"]
        
        if len(candles) < slow + signal_period:
            return {"macd": 0, "signal": 0, "histogram": 0}

        prices = self._get_prices(candles, self.parameters["price_type"])
        
        # EMA быстрая и медленная
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        
        # MACD линия
        macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_fast))]
        
        # Сигнальная линия (EMA от MACD)
        macd_for_signal = macd_line[slow-1:]
        signal_line = self._ema(macd_for_signal, signal_period)
        
        # Гистограмма
        current_macd = macd_line[-1]
        current_signal = signal_line[-1] if signal_line else 0
        histogram = current_macd - current_signal

        return {
            "macd": current_macd,
            "signal": current_signal,
            "histogram": histogram
        }


# ==============================================================================
# Stochastic Oscillator
# ==============================================================================

@register_indicator("stochastic")
class StochasticIndicator(CandlesIndicator):
    """
    Stochastic Oscillator — Стохастический осциллятор.

    Параметры:
        k_period: Период %K (по умолчанию 14)
        d_period: Период %D (по умолчанию 3)
        slowdown: Замедление (по умолчанию 3)
        overbought: Уровень перекупленности (по умолчанию 80)
        oversold: Уровень перепроданности (по умолчанию 20)

    Условия:
        k — значение %K
        d — значение %D
    """

    DISPLAY_NAME = "Stochastic"
    DESCRIPTION = "Стохастический осциллятор для определения разворотов тренда"

    DEFAULT_PARAMETERS = {
        "k_period": 14,
        "d_period": 3,
        "slowdown": 3,
        "overbought": 80,
        "oversold": 20
    }

    DEFAULT_CONDITIONS = {
        "call": "k<d and k<oversold",  # %K пересекает %D снизу в зоне перепроданности
        "sell": "k>d and k>overbought"  # %K пересекает %D сверху в зоне перекупленности
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Обе линии стохастика K, D находятся в зоне перекупленности; значение K выше значения D",
        "B": "Обе линии стохастика K, D находятся в зоне перекупленности; значение K ниже значения D",
        "C": "Обе линии стохастика K, D находятся в умеренной зоне; значение K выше значения D",
        "D": "Обе линии стохастика K, D находятся в умеренной зоне; значение K ниже значения D",
        "E": "Обе линии стохастика K, D находятся в зоне перепроданности; значение K выше значения D",
        "F": "Обе линии стохастика K, D находятся в зоне перепроданности; значение K ниже значения D",
        "G": "Быстрая линия стохастика K находится в зоне перекупленности",
        "H": "Быстрая линия стохастика K находится в умеренной зоне",
        "I": "Быстрая линия стохастика K находится в зоне перепроданности",
        "J": "Медленная линия стохастика D находится в зоне перекупленности",
        "K": "Медленная линия стохастика D находится в умеренной зоне",
        "L": "Медленная линия стохастика D находится в зоне перепроданности",
        "M": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление стохастика."""
        k_period = self.parameters["k_period"]
        slowdown = self.parameters["slowdown"]
        d_period = self.parameters["d_period"]
        
        if len(candles) < k_period + slowdown:
            return {"k": 50, "d": 50}

        lows = self._get_prices(candles, "low")
        highs = self._get_prices(candles, "high")
        closes = self._get_prices(candles, "close")

        # %K сырой
        raw_k = []
        for i in range(k_period - 1, len(candles)):
            lowest_low = min(lows[i - k_period + 1:i + 1])
            highest_high = max(highs[i - k_period + 1:i + 1])
            if highest_high - lowest_low > 0:
                raw_k.append(((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100)
            else:
                raw_k.append(50)

        # %K сглаженный
        k_sma = self._sma(raw_k, slowdown)
        current_k = k_sma[-1] if k_sma else 50

        # %D (SMA от %K)
        d_sma = self._sma(k_sma, d_period)
        current_d = d_sma[-1] if d_sma else 50

        return {
            "k": current_k,
            "d": current_d,
            "overbought": self.parameters["overbought"],
            "oversold": self.parameters["oversold"]
        }


# ==============================================================================
# CCI (Commodity Channel Index)
# ==============================================================================

@register_indicator("cci")
class CciIndicator(CandlesIndicator):
    """
    CCI — Индекс товарного канала.

    Параметры:
        period: Период расчёта (по умолчанию 20)
        overbought: Уровень перекупленности (по умолчанию 100)
        oversold: Уровень перепроданности (по умолчанию -100)

    Условия:
        cci — значение индикатора
    """

    DISPLAY_NAME = "CCI"
    DESCRIPTION = "Индекс товарного канала для определения циклов"

    DEFAULT_PARAMETERS = {
        "period": 20,
        "overbought": 100,
        "oversold": -100
    }

    DEFAULT_CONDITIONS = {
        "call": "cci<oversold",  # CCI < -100 → CALL
        "sell": "cci>overbought"  # CCI > 100 → PUT
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Линия индикатора находится в зоне перепроданности",
        "B": "Линия индикатора находится в зоне перекупленности",
        "C": "Линия индикатора находится в умеренной зоне",
        "D": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление CCI."""
        import math
        
        period = self.parameters["period"]
        
        if len(candles) < period:
            return {"cci": 0}

        # Типичная цена
        tp = self._get_prices(candles, "hlc3")

        # SMA типичной цены
        sma_tp = sum(tp[-period:]) / period

        # Mean Deviation
        deviations = [abs(tp[i] - sma_tp) for i in range(-period, 0)]
        mean_dev = sum(deviations) / period

        if mean_dev == 0:
            return {"cci": 0}

        cci_value = (tp[-1] - sma_tp) / (0.015 * mean_dev)

        return {
            "cci": cci_value,
            "overbought": self.parameters["overbought"],
            "oversold": self.parameters["oversold"]
        }


# ==============================================================================
# Parabolic SAR
# ==============================================================================

@register_indicator("parabolic_sar")
class ParabolicSarIndicator(CandlesIndicator):
    """
    Parabolic SAR — Параболическая система остановок и разворотов.

    Параметры:
        step: Шаг ускорения (по умолчанию 0.02)
        max_step: Максимальный шаг (по умолчанию 0.2)

    Условия:
        sar — значение SAR
        trend — направление тренда ("up" или "down")
    """

    DISPLAY_NAME = "Parabolic SAR"
    DESCRIPTION = "Параболическая система для определения тренда и точек разворота"

    DEFAULT_PARAMETERS = {
        "step": 0.02,
        "max_step": 0.2
    }

    DEFAULT_CONDITIONS = {
        "call": "trend=='up'",   # Цена выше SAR → CALL
        "sell": "trend=='down'"  # Цена ниже SAR → PUT
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Расположение Parabolic SAR над графиком цены",
        "B": "Расположение Parabolic SAR под графиком цены",
        "C": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление Parabolic SAR."""
        if len(candles) < 10:
            return {"sar": 0, "trend": "none"}

        highs = self._get_prices(candles, "high")
        lows = self._get_prices(candles, "low")

        step = self.parameters["step"]
        max_step = self.parameters["max_step"]

        # Инициализация
        sar = [0] * len(candles)
        trend = 1  # 1 = восходящий, -1 = нисходящий
        af = step

        if highs[1] > highs[0]:
            trend = 1
            sar[0] = lows[0]
            ep = highs[1]
        else:
            trend = -1
            sar[0] = highs[0]
            ep = lows[1]

        # Расчёт SAR
        for i in range(1, len(candles)):
            sar[i] = sar[i-1] + af * (ep - sar[i-1])

            if trend == 1:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + step, max_step)
                if lows[i] < sar[i]:
                    trend = -1
                    sar[i] = ep
                    ep = lows[i]
                    af = step
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + step, max_step)
                if highs[i] > sar[i]:
                    trend = 1
                    sar[i] = ep
                    ep = highs[i]
                    af = step

        current_sar = sar[-1]
        current_price = highs[-1]

        return {
            "sar": current_sar,
            "trend": "up" if trend == 1 else "down",
            "af": af,
            "ep": ep
        }


# ==============================================================================
# SuperTrend
# ==============================================================================

@register_indicator("super_trend")
class SuperTrendIndicator(CandlesIndicator):
    """
    SuperTrend — Супер тренд.

    Параметры:
        period: Период ATR (по умолчанию 10)
        multiplier: Множитель (по умолчанию 3.0)

    Условия:
        supertrend — значение индикатора
        trend — направление тренда
    """

    DISPLAY_NAME = "SuperTrend"
    DESCRIPTION = "Супер тренд для определения направления тренда"

    DEFAULT_PARAMETERS = {
        "period": 10,
        "multiplier": 3.0
    }

    DEFAULT_CONDITIONS = {
        "call": "trend=='up'",   # Тренд вверх → CALL
        "sell": "trend=='down'"  # Тренд вниз → PUT
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Трендовая линия указывает на продажу",
        "B": "Трендовая линия указывает на покупку",
        "C": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление SuperTrend."""
        import math
        
        period = self.parameters["period"]
        multiplier = self.parameters["multiplier"]
        
        if len(candles) < period + 10:
            return {"supertrend": 0, "trend": "none", "atr": 0}

        highs = self._get_prices(candles, "high")
        lows = self._get_prices(candles, "low")
        closes = self._get_prices(candles, "close")

        # ATR
        tr = []
        for i in range(1, len(candles)):
            tr.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            ))
        
        atr = self._sma(tr, period)

        # Базовая линия
        hl2 = [(highs[i] + lows[i]) / 2 for i in range(len(highs))]

        # Полосы
        upper = [hl2[i] + (multiplier * atr[i]) for i in range(len(atr))]
        lower = [hl2[i] - (multiplier * atr[i]) for i in range(len(atr))]

        # SuperTrend
        st = []
        trend = []

        if len(upper) > 0:
            st.append(upper[0])
            trend.append(-1)

            for i in range(1, len(upper)):
                idx = period + i
                if idx >= len(candles):
                    break
                if closes[idx] > st[i-1]:
                    st.append(lower[i])
                    trend.append(1)
                else:
                    st.append(upper[i])
                    trend.append(-1)

        current_st = st[-1] if st else 0
        current_trend = trend[-1] if trend else 0

        return {
            "supertrend": current_st,
            "trend": "up" if current_trend == 1 else "down",
            "atr": atr[-1] if atr else 0
        }


# ==============================================================================
# Two MA (пересечение двух скользящих средних)
# ==============================================================================

@register_indicator("two_ma")
class TwoMaIndicator(CandlesIndicator):
    """
    Two MA — Пересечение двух скользящих средних.

    Параметры:
        one_ma_period: Период быстрой MA (по умолчанию 5)
        one_ma_method: Метод быстрой MA (sma, ema)
        one_ma_price_type: Тип цены быстрой MA
        to_ma_period: Период медленной MA (по умолчанию 15)
        to_ma_method: Метод медленной MA (sma, ema)
        to_ma_price_type: Тип цены медленной MA

    Условия:
        onema — значение быстрой MA
        toma — значение медленной MA
    """

    DISPLAY_NAME = "Two MA"
    DESCRIPTION = "Пересечение двух скользящих средних"

    DEFAULT_PARAMETERS = {
        "one_ma_period": 5,
        "one_ma_method": "ema",
        "one_ma_price_type": "close",
        "to_ma_period": 15,
        "to_ma_method": "ema",
        "to_ma_price_type": "close"
    }

    DEFAULT_CONDITIONS = {
        "call": "onema>toma",   # Быстрая выше медленной → CALL
        "sell": "onema<toma"    # Быстрая ниже медленной → PUT
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Быстрая MA выше медленной MA",
        "B": "Быстрая MA ниже медленной MA",
        "C": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление двух MA."""
        period1 = self.parameters["one_ma_period"]
        period2 = self.parameters["to_ma_period"]
        method1 = self.parameters["one_ma_method"]
        method2 = self.parameters["to_ma_method"]
        price_type1 = self.parameters["one_ma_price_type"]
        price_type2 = self.parameters["to_ma_price_type"]

        if len(candles) < max(period1, period2):
            return {"onema": 0, "toma": 0}

        prices1 = self._get_prices(candles, price_type1)
        prices2 = self._get_prices(candles, price_type2)

        if method1 == "ema":
            ma1 = self._ema(prices1, period1)
        else:
            ma1 = self._sma(prices1, period1)

        if method2 == "ema":
            ma2 = self._ema(prices2, period2)
        else:
            ma2 = self._sma(prices2, period2)

        return {
            "onema": ma1[-1] if ma1 else 0,
            "toma": ma2[-1] if ma2 else 0
        }


# ==============================================================================
# Candle (свечной анализ)
# ==============================================================================

@register_indicator("candle")
class CandleIndicator(CandlesIndicator):
    """
    Candle — Свечной анализ.

    Параметры:
        num_candles: Количество проверяемых свечей (по умолчанию 2)
        type_candle: Тип комбинации (repeat, opposite)
        min_size_bar: Мин. размер свечи в пунктах
        max_size_bar: Макс. размер свечи в пунктах
        bar: На каком баре проверять

    Условия:
        lastdir — направление последней свечи ("up", "down")
    """

    DISPLAY_NAME = "Candle"
    DESCRIPTION = "Свечной анализ для определения паттернов"

    DEFAULT_PARAMETERS = {
        "num_candles": 2,
        "type_candle": "repeat",
        "min_size_bar": 2,
        "max_size_bar": 100,
        "bar": -1
    }

    DEFAULT_CONDITIONS = {
        "call": "lastdir=='up'",   # Последняя свеча вверх → CALL
        "sell": "lastdir=='down'"  # Последняя свеча вниз → PUT
    }

    CONDITIONS_DESCRIPTION = {
        "A": "Первая проверяемая свеча закрылась вверх",
        "B": "Первая проверяемая свеча закрылась вниз",
        "C": "Не открывать сделку"
    }

    def compute(self, candles: List[Dict]) -> Dict[str, Any]:
        """Вычисление свечного паттерна."""
        if not candles:
            return {"lastdir": "none"}

        bar_index = self.parameters.get("bar", -1)
        if bar_index < -len(candles) or bar_index >= len(candles):
            bar_index = -1

        candle = candles[bar_index]
        lastdir = "up" if candle["close"] > candle["open"] else "down"

        return {
            "lastdir": lastdir
        }


__all__ = [
    "RsiIndicator",
    "BollingerBandsIndicator",
    "MacdIndicator",
    "StochasticIndicator",
    "CciIndicator",
    "ParabolicSarIndicator",
    "SuperTrendIndicator",
    "TwoMaIndicator",
    "CandleIndicator"
]
