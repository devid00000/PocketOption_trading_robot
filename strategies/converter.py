"""
Конвертер форматов стратегий.

Преобразует между форматами:
1. Формат расширения (extension) — JSON из расширения PocketOptionRobot
2. Внутренний формат (internal) — StrategyConfig

Пример использования:
    from strategies.converter import StrategyConverter
    
    # Импорт из расширения
    strategy = StrategyConverter.from_extension_file("strategy.json")
    
    # Экспорт в расширение
    StrategyConverter.to_extension_file(strategy, "output.json")
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from core.strategy_models import (
    StrategyConfig,
    IndicatorConfig,
    RegulationsConfig,
    MartingaleConfig,
    MartingaleStep
)


class StrategyConverter:
    """
    Конвертер стратегий между форматами.
    """

    # ==========================================================================
    # МАППИНГ ПОЛЕЙ ИНДИКАТОРОВ
    # ==========================================================================

    INDICATOR_TYPE_MAP = {
        "rsi": "rsi",
        "bollinger": "bollinger",
        "macd": "macd",
        "stochastic": "stochastic",
        "cci": "cci",
        "parabolicSAR": "parabolic_sar",
        "superTrend": "super_trend",
        "twoMa": "two_ma",
        "two_ma": "two_ma",
        "candle": "candle",
        "maCross": "two_ma"
    }

    # Маппинг параметров для каждого индикатора
    INDICATOR_PARAM_MAP = {
        "rsi": {
            "periodRsi": "period",
            "tpl": "overbought",
            "btl": "oversold",
            "priceType": "price_type",
            "checkBar": "bar_index"
        },
        "two_ma": {
            "oneMaPeriod": "one_ma_period",
            "oneMaMetod": "one_ma_method",
            "oneMaPriceType": "one_ma_price_type",
            "toMaPeriod": "to_ma_period",
            "toMaMetod": "to_ma_method",
            "toMaPriceType": "to_ma_price_type",
            "checkBar": "bar_index"
        },
        "candle": {
            "numСandles": "num_candles",
            "typeCandle": "type_candle",
            "minSizeBar": "min_size_bar",
            "maxSizeBar": "max_size_bar",
            "bar": "bar_index"
        },
        "bollinger": {
            "period": "period",
            "stdDev": "std_dev",
            "priceType": "price_type"
        },
        "macd": {
            "fastPeriod": "fast_period",
            "slowPeriod": "slow_period",
            "signalPeriod": "signal_period"
        },
        "stochastic": {
            "kPeriod": "k_period",
            "dPeriod": "d_period",
            "slowdown": "slowdown",
            "overbought": "overbought",
            "oversold": "oversold"
        }
    }

    # Маппинг условий сигналов
    SIGNAL_CONDITION_MAP = {
        "rsi": {
            "valRsi<btl": "valRsi<btl",
            "valRsi>tpl": "valRsi>tpl",
            "valRsi<tpl && valRsi>btl": "valRsi<tpl and valRsi>btl",
            "false": ""
        },
        "candle": {
            "lastdir=='up'": "lastdir=='up'",
            "lastdir=='down'": "lastdir=='down'",
            "candleFalse": ""
        },
        "two_ma": {
            "onema>toma": "onema>toma",
            "onema<toma": "onema<toma",
            "twoMaFalse": ""
        }
    }

    # ==========================================================================
    # ИМПОРТ ИЗ РАСШИРЕНИЯ
    # ==========================================================================

    @classmethod
    def from_extension(cls, data: Dict) -> StrategyConfig:
        """
        Импорт из формата расширения.

        Args:
            data: Словарь с данными в формате расширения

        Returns:
            StrategyConfig
        """
        # Данные стратегии
        data_section = data.get("data", {})
        name = data_section.get("userTitle") or data_section.get("title", "Strategy")

        # Активы
        assets = data.get("assets", [])

        # Индикаторы
        indicators = []
        for ind_data in data.get("indicators", []):
            indicator = cls._convert_indicator(ind_data)
            if indicator:
                indicators.append(indicator)

        # Регламент
        regulations = cls._convert_regulations(data.get("regulations", []))

        # Мартингейл
        martingale = cls._convert_martingale(data.get("martingale", []))

        return StrategyConfig(
            name=name,
            description="",
            id=data.get("id", ""),
            type=data.get("type", "personal"),
            assets=assets,
            asset_groups=[],
            max_active_assets=10,
            exclude_assets=[],
            indicators=indicators,
            min_agreement=1,
            use_weights=False,
            regulations=regulations,
            martingale=martingale
        )

    @classmethod
    def _convert_indicator(cls, ind_data: Dict) -> Optional[IndicatorConfig]:
        """
        Конвертация индикатора из формата расширения.

        Args:
            ind_data: Данные индикатора

        Returns:
            IndicatorConfig или None
        """
        ind_type = ind_data.get("id", "")  # Не приводим к нижнему регистру!
        
        # Маппинг типа (проверяем оба варианта)
        if ind_type not in cls.INDICATOR_TYPE_MAP:
            # Пробуем привести к нижнему регистру
            ind_type_lower = ind_type.lower()
            if ind_type_lower not in cls.INDICATOR_TYPE_MAP:
                return None
            mapped_type = cls.INDICATOR_TYPE_MAP[ind_type_lower]
        else:
            mapped_type = cls.INDICATOR_TYPE_MAP[ind_type]
        
        # Параметры
        settings = ind_data.get("settings", [])
        parameters = {}
        conditions = {}
        timeframe = 60
        bar_index = 0
        time_inspection = "newBar"

        # Получаем маппинг параметров для этого типа
        param_map = cls.INDICATOR_PARAM_MAP.get(mapped_type, {})

        for setting in settings:
            setting_id = setting.get("id", "")
            value = setting.get("value")

            # Специальные поля
            if setting_id == "tf":
                timeframe = int(value) if value else 60
            elif setting_id == "checkBar" or setting_id == "bar":
                bar_index = int(value) if value else 0
            elif setting_id == "timeInspection":
                time_inspection = value if value else "newBar"
            elif setting_id == "signalUp":
                conditions["call"] = value if value and value not in ["false", "candleFalse", "twoMaFalse"] else ""
            elif setting_id == "signalDown":
                conditions["sell"] = value if value and value not in ["false", "candleFalse", "twoMaFalse"] else ""
            else:
                # Конвертируем имя параметра
                param_name = param_map.get(setting_id, setting_id)
                if isinstance(value, str) and value.isdigit():
                    value = int(value)
                elif isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                parameters[param_name] = value

        # Название индикатора
        name = mapped_type.title()
        if "tempID" in ind_data:
            name = f"{name}({ind_data['tempID'][:8]})"

        return IndicatorConfig(
            type=mapped_type,
            name=name,
            enabled=True,
            timeframe=timeframe,
            bar_index=bar_index,
            time_inspection=time_inspection,
            parameters=parameters,
            conditions=conditions,
            weight=1.0
        )

    @classmethod
    def _convert_regulations(cls, regulations_data: List) -> RegulationsConfig:
        """
        Конвертация регламента из формата расширения.

        Args:
            regulations_data: Список настроек регламента

        Returns:
            RegulationsConfig
        """
        config = RegulationsConfig()

        for setting in regulations_data:
            setting_id = setting.get("id", "")
            value = setting.get("value")

            if setting_id == "mode":
                config.mode = value if value else "trade"
            elif setting_id == "timeFrom":
                # Формат "00:00-00:00"
                if value and "-" in value:
                    time_from, time_to = value.split("-")
                    config.time_from = time_from
                    config.time_to = time_to
            elif setting_id == "minProfit":
                config.min_profit = int(value) if value else 85
            elif setting_id == "expiration":
                config.expiration = int(value) if value else 60
            elif setting_id == "bet":
                config.bet = float(value) if value else 1.0
            elif setting_id == "maxBets":
                config.max_bets = int(value) if value else 1
            elif setting_id == "sl":
                config.stop_loss = float(value) if value else 0.0
            elif setting_id == "tp":
                config.take_profit = float(value) if value else 0.0

        return config

    @classmethod
    def _convert_martingale(cls, martingale_data: List) -> MartingaleConfig:
        """
        Конвертация мартингейла из формата расширения.

        Args:
            martingale_data: Список шагов мартингейла

        Returns:
            MartingaleConfig
        """
        if not martingale_data:
            return MartingaleConfig(enabled=False)

        config = MartingaleConfig(enabled=True)
        steps = []

        for i, step_data in enumerate(martingale_data):
            step = MartingaleStep(step=i + 1)

            for setting in step_data:
                setting_id = setting.get("id", "")
                value = setting.get("value")

                if setting_id == "minProfit":
                    step.min_profit = int(value) if value else 75
                elif setting_id == "actionDecreaseProfit":
                    # Маппинг действий
                    action_map = {
                        "newAsset": "new_asset",
                        "awaitProfit": "continue",
                        "stop": "stop"
                    }
                    step.action_on_loss = action_map.get(value, "new_asset")
                elif setting_id == "disabledAsset":
                    # Действие при недоступности актива
                    action_map = {
                        "newAsset": "new_asset",
                        "awaitAvailabl": "continue",
                        "stop": "stop"
                    }
                    # Сохраняем в action_on_loss для простоты
                    pass
                elif setting_id == "expiration":
                    step.expiration = int(value) if value else 0
                elif setting_id == "direction":
                    # Маппинг направления
                    direction_map = {
                        "previous": "previous",
                        "contrPrevious": "opposite",
                        "newSignals": "call"
                    }
                    step.direction = direction_map.get(value, "previous")
                elif setting_id == "autoRatio":
                    step.auto_ratio = (value == "on")
                elif setting_id == "ratio":
                    step.ratio = float(value) if value else 2.0

            steps.append(step)

        config.steps = steps
        config.max_steps = len(steps)

        return config

    @classmethod
    def from_extension_file(cls, filepath: str) -> StrategyConfig:
        """
        Импорт из файла расширения.

        Args:
            filepath: Путь к файлу

        Returns:
            StrategyConfig
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_extension(data)

    @classmethod
    def from_extension_json(cls, json_str: str) -> StrategyConfig:
        """
        Импорт из JSON строки (формат расширения).

        Args:
            json_str: JSON строка

        Returns:
            StrategyConfig
        """
        data = json.loads(json_str)
        return cls.from_extension(data)

    # ==========================================================================
    # ЭКСПОРТ В РАСШИРЕНИЕ
    # ==========================================================================

    @classmethod
    def to_extension(cls, strategy: StrategyConfig) -> Dict:
        """
        Экспорт в формат расширения.

        Args:
            strategy: StrategyConfig

        Returns:
            Словарь в формате расширения
        """
        return {
            "data": {
                "title": strategy.name,
                "userTitle": strategy.user_title or strategy.name
            },
            "id": strategy.id,
            "type": strategy.type,
            "assets": strategy.assets,
            "indicators": [cls._convert_indicator_to_extension(ind) for ind in strategy.indicators],
            "martingale": cls._convert_martingale_to_extension(strategy.martingale),
            "regulations": cls._convert_regulations_to_extension(strategy.regulations)
        }

    @classmethod
    def _convert_indicator_to_extension(cls, indicator: IndicatorConfig) -> Dict:
        """
        Конвертация индикатора в формат расширения.

        Args:
            indicator: IndicatorConfig

        Returns:
            Словарь в формате расширения
        """
        import uuid
        
        settings = []

        # timeInspection
        settings.append({
            "id": "timeInspection",
            "type": "select",
            "value": indicator.time_inspection,
            "values": ["newBar", "currentBar"]
        })

        # Параметры индикатора
        param_map = cls.INDICATOR_PARAM_MAP.get(indicator.type, {})
        reverse_param_map = {v: k for k, v in param_map.items()}

        for param_name, param_value in indicator.parameters.items():
            setting_id = reverse_param_map.get(param_name, param_name)
            settings.append({
                "id": setting_id,
                "type": "number" if isinstance(param_value, (int, float)) else "select",
                "value": str(param_value) if isinstance(param_value, (int, float)) else param_value,
                "values": []
            })

        # timeframe
        settings.append({
            "id": "tf",
            "type": "select",
            "value": str(indicator.timeframe),
            "values": ["5", "10", "15", "30", "60", "120", "180", "300", "600", "900", "1800", "3600", "14400", "86400"]
        })

        # bar_index
        settings.append({
            "id": "checkBar" if indicator.type != "candle" else "bar",
            "type": "number",
            "value": str(indicator.bar_index),
            "values": [0, -100, 0, 1]
        })

        # Условия сигналов
        call_condition = indicator.conditions.get("call", "")
        sell_condition = indicator.conditions.get("sell", "")

        settings.append({
            "id": "signalUp",
            "type": "select",
            "value": call_condition if call_condition else "false",
            "values": []
        })
        settings.append({
            "id": "signalDown",
            "type": "select",
            "value": sell_condition if sell_condition else "false",
            "values": []
        })

        return {
            "id": indicator.type,
            "tempID": indicator.id or str(uuid.uuid4()),
            "settings": settings,
            "otherData": {
                "iconImg": f"{indicator.type}.png"
            }
        }

    @classmethod
    def _convert_regulations_to_extension(cls, regulations: RegulationsConfig) -> List[Dict]:
        """
        Конвертация регламента в формат расширения.

        Args:
            regulations: RegulationsConfig

        Returns:
            Список настроек в формате расширения
        """
        return [
            {
                "id": "mode",
                "type": "select",
                "value": regulations.mode,
                "values": ["trade", "signals"]
            },
            {
                "id": "timeFrom",
                "type": "time",
                "value": f"{regulations.time_from}-{regulations.time_to}",
                "values": ["00:00-00:00"]
            },
            {
                "id": "minProfit",
                "type": "number",
                "value": str(regulations.min_profit),
                "values": [70, 1, 99, 1]
            },
            {
                "id": "expiration",
                "type": "number",
                "value": str(regulations.expiration),
                "values": [60, 5, 14400, 1]
            },
            {
                "id": "bet",
                "type": "number",
                "value": regulations.bet,
                "values": [1, 1, 5000, 0.5]
            },
            {
                "id": "maxBets",
                "type": "number",
                "value": str(regulations.max_bets),
                "values": [1, 1, 10, 1]
            },
            {
                "id": "sl",
                "type": "number",
                "value": str(regulations.stop_loss),
                "values": [0, 0, 10000, 1]
            },
            {
                "id": "tp",
                "type": "number",
                "value": str(regulations.take_profit),
                "values": [0, 0, 10000, 1]
            }
        ]

    @classmethod
    def _convert_martingale_to_extension(cls, martingale: MartingaleConfig) -> List[List[Dict]]:
        """
        Конвертация мартингейла в формат расширения.

        Args:
            martingale: MartingaleConfig

        Returns:
            Список шагов в формате расширения
        """
        if not martingale.enabled:
            return []

        result = []

        for step in martingale.steps:
            step_data = [
                {
                    "id": "minProfit",
                    "type": "verticalNumber",
                    "value": str(step.min_profit),
                    "values": [10, 99, 1]
                },
                {
                    "id": "actionDecreaseProfit",
                    "type": "select",
                    "value": step.action_on_loss,
                    "values": ["newAsset", "awaitProfit", "stop"]
                },
                {
                    "id": "disabledAsset",
                    "type": "select",
                    "value": step.action_on_loss,
                    "values": ["newAsset", "awaitAvailabl", "stop"]
                },
                {
                    "id": "expiration",
                    "type": "number",
                    "value": str(step.expiration) if step.expiration > 0 else "15",
                    "values": [60, 5, 14400, 1]
                },
                {
                    "id": "disabledExpiration",
                    "type": "select",
                    "value": "newAsset",
                    "values": ["newAsset", "minAvailabl", "awaitAvailablExpiration", "stop"]
                },
                {
                    "id": "direction",
                    "type": "select",
                    "value": step.direction,
                    "values": ["previous", "contrPrevious", "newSignals"]
                },
                {
                    "id": "excludePreviousAsset",
                    "type": "select",
                    "value": "yes",
                    "values": ["yes", "no"]
                },
                {
                    "id": "autoRatio",
                    "type": "select",
                    "value": "on" if step.auto_ratio else "off",
                    "values": ["on", "off"]
                },
                {
                    "id": "ratio",
                    "type": "number",
                    "value": step.ratio,
                    "values": [2.5, 1, 100, 0.1]
                }
            ]
            result.append(step_data)

        return result

    @classmethod
    def to_extension_file(cls, strategy: StrategyConfig, filepath: str):
        """
        Экспорт в файл расширения.

        Args:
            strategy: StrategyConfig
            filepath: Путь к файлу
        """
        data = cls.to_extension(strategy)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def to_extension_json(cls, strategy: StrategyConfig, indent: int = 2) -> str:
        """
        Экспорт в JSON строку (формат расширения).

        Args:
            strategy: StrategyConfig
            indent: Отступ

        Returns:
            JSON строка
        """
        data = cls.to_extension(strategy)
        return json.dumps(data, indent=indent, ensure_ascii=False)

    # ==========================================================================
    # УТИЛИТЫ
    # ==========================================================================

    @classmethod
    def validate_extension_format(cls, data: Dict) -> bool:
        """
        Проверка формата расширения.

        Args:
            data: Данные для проверки

        Returns:
            True если формат корректен
        """
        required_keys = ["data", "indicators", "regulations", "martingale"]
        for key in required_keys:
            if key not in data:
                return False
        
        if "title" not in data.get("data", {}) and "userTitle" not in data.get("data", {}):
            return False
        
        return True

    @classmethod
    def get_indicator_info(cls, ind_type: str) -> Dict[str, Any]:
        """
        Получение информации об индикаторе.

        Args:
            ind_type: Тип индикатора

        Returns:
            Информация об индикаторе
        """
        indicator_info = {
            "rsi": {
                "name": "RSI",
                "description": "Индекс относительной силы",
                "parameters": ["period", "overbought", "oversold", "price_type"]
            },
            "bollinger": {
                "name": "Bollinger Bands",
                "description": "Полосы Боллинджера",
                "parameters": ["period", "std_dev", "price_type"]
            },
            "macd": {
                "name": "MACD",
                "description": "Схождение/расхождение скользящих средних",
                "parameters": ["fast_period", "slow_period", "signal_period"]
            },
            "stochastic": {
                "name": "Stochastic",
                "description": "Стохастический осциллятор",
                "parameters": ["k_period", "d_period", "slowdown", "overbought", "oversold"]
            },
            "cci": {
                "name": "CCI",
                "description": "Индекс товарного канала",
                "parameters": ["period", "overbought", "oversold"]
            },
            "parabolic_sar": {
                "name": "Parabolic SAR",
                "description": "Параболическая система остановок и разворотов",
                "parameters": ["step", "max_step"]
            },
            "super_trend": {
                "name": "SuperTrend",
                "description": "Супер тренд",
                "parameters": ["period", "multiplier"]
            },
            "two_ma": {
                "name": "Two MA",
                "description": "Пересечение двух скользящих средних",
                "parameters": ["one_ma_period", "one_ma_method", "to_ma_period", "to_ma_method"]
            },
            "candle": {
                "name": "Candle",
                "description": "Свечной анализ",
                "parameters": ["num_candles", "type_candle", "min_size_bar", "max_size_bar"]
            }
        }
        
        return indicator_info.get(ind_type, {})


__all__ = ["StrategyConverter"]
