"""
Модели данных для конфигурации стратегий.

Поддерживает:
- Множественные активы
- Множественные индикаторы с индивидуальными настройками
- Регламент работы
- Мартингейл с шагами
- Импорт/экспорт формата расширения
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import uuid


# ==============================================================================
# ИНДИКАТОРЫ
# ==============================================================================

@dataclass
class IndicatorConfig:
    """
    Конфигурация одного индикатора.

    Attributes:
        type: Тип индикатора ("rsi", "bollinger", "macd", и т.д.)
        id: Уникальный ID индикатора
        name: Пользовательское название
        enabled: Статус индикатора
        timeframe: Таймфрейм в секундах
        bar_index: На каком баре проверять (0 = текущий, -1 = предыдущий)
        parameters: Параметры индикатора
        conditions: Условия сигналов (call/sell выражения)
        weight: Вес индикатора (0.0-1.0)
        time_inspection: Когда проверять ("newBar", "always")
    """
    type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    enabled: bool = True
    timeframe: int = 60
    bar_index: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, str] = field(default_factory=dict)  # {"call": "valRsi<btl", "sell": "valRsi>tpl"}
    weight: float = 1.0
    time_inspection: str = "newBar"

    def to_dict(self) -> Dict:
        """Конвертация в словарь (формат расширения)."""
        # Преобразуем conditions в signal_up/signal_down
        settings = self.parameters.copy()
        settings["tf"] = self.timeframe
        settings["bar"] = self.bar_index
        settings["time_inspection"] = self.time_inspection
        
        if "call" in self.conditions:
            settings["signal_up"] = self.conditions["call"]
        if "sell" in self.conditions:
            settings["signal_down"] = self.conditions["sell"]
        
        return {
            "type": self.type,
            "enabled": self.enabled,
            "id": self.id,
            "settings": settings,
            "weight": self.weight
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'IndicatorConfig':
        """Создание из словаря (формат расширения)."""
        settings = data.get("settings", {}).copy()
        
        # Извлекаем timeframe и bar
        timeframe = settings.pop("tf", 60)
        bar_index = settings.pop("bar", 0)
        time_inspection = settings.pop("time_inspection", "newBar")
        
        # Извлекаем условия
        conditions = {}
        if "signal_up" in settings:
            conditions["call"] = settings.pop("signal_up")
        if "signal_down" in settings:
            conditions["sell"] = settings.pop("signal_down")
        
        # Название по умолчанию
        name = settings.pop("name", "")
        if not name:
            name = f"{data['type'].title()}({data.get('id', '')[:8]})"
        
        return cls(
            type=data.get("type", ""),
            id=data.get("id", str(uuid.uuid4())),
            name=name,
            enabled=data.get("enabled", True),
            timeframe=timeframe,
            bar_index=bar_index,
            time_inspection=time_inspection,
            parameters=settings,
            conditions=conditions,
            weight=float(data.get("weight", 1.0))
        )


# ==============================================================================
# РЕГЛАМЕНТ
# ==============================================================================

@dataclass
class RegulationsConfig:
    """
    Регламент работы стратегии.

    Attributes:
        mode: Режим работы ("trade", "signal")
        time_from: Время начала работы
        time_to: Время окончания работы
        timezone: Часовой пояс
        work_days: Дни недели для работы (0=Пн, 6=Вс)
        min_profit: Минимальный % доходности актива
        expiration: Экспирация в секундах
        bet: Ставка
        max_active_trades: Макс. одновременных сделок
        max_bets: Макс. ставок (лимит)
        max_daily_loss: Макс. дневной убыток ($)
        max_daily_profit: Макс. дневная прибыль ($)
        stop_loss: Стоп-лосс ($)
        take_profit: Тейк-профит ($)
        stop_on_loss: Остановить при достижении стоп-лосса
        stop_on_profit: Остановить при достижении тейк-профита
    """
    mode: str = "trade"  # "trade" или "signal"
    time_from: str = "00:00"
    time_to: str = "23:59"
    timezone: str = "UTC"
    work_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    
    min_profit: int = 85  # Мин. % доходности
    expiration: int = 60  # Экспирация (сек)
    bet: float = 1.0  # Ставка
    
    max_active_trades: int = 1
    max_bets: int = 1
    max_daily_loss: float = 100.0
    max_daily_profit: float = 500.0
    
    stop_loss: float = 0.0  # 0 = отключен
    take_profit: float = 0.0  # 0 = отключен
    stop_on_loss: bool = False
    stop_on_profit: bool = False

    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'RegulationsConfig':
        """Создание из словаря."""
        return cls(
            mode=data.get("mode", "trade"),
            time_from=data.get("time_from", "00:00"),
            time_to=data.get("time_to", "23:59"),
            timezone=data.get("timezone", "UTC"),
            work_days=data.get("work_days", [0, 1, 2, 3, 4, 5, 6]),
            min_profit=int(data.get("min_profit", 85)),
            expiration=int(data.get("expiration", 60)),
            bet=float(data.get("bet", 1.0)),
            max_active_trades=int(data.get("max_active_trades", 1)),
            max_bets=int(data.get("max_bets", 1)),
            max_daily_loss=float(data.get("max_daily_loss", 100)),
            max_daily_profit=float(data.get("max_daily_profit", 500)),
            stop_loss=float(data.get("stop_loss", 0)),
            take_profit=float(data.get("take_profit", 0)),
            stop_on_loss=data.get("stop_on_loss", False),
            stop_on_profit=data.get("stop_on_profit", False)
        )


# ==============================================================================
# МАРТИНГЕЙЛ
# ==============================================================================

@dataclass
class MartingaleStep:
    """
    Шаг мартингейла.

    Attributes:
        step: Номер шага (1, 2, 3...)
        ratio: Множитель ставки
        auto_ratio: Авто-расчёт коэффициента
        expiration: Экспирация для этого шага (0 = как в регламенте)
        direction: Направление сделки
        action_on_loss: Действие после проигрыша
        min_profit: Мин. прибыль % для авто-расчёта
    """
    step: int
    ratio: float = 2.0
    auto_ratio: bool = True
    expiration: int = 0  # 0 = как в регламенте
    direction: str = "previous"  # "previous", "opposite", "call", "put"
    action_on_loss: str = "new_asset"  # "new_asset", "stop", "continue"
    min_profit: int = 75

    def to_dict(self) -> Dict:
        """Конвертация в словарь (формат расширения)."""
        return {
            "step": self.step,
            "ratio": self.ratio,
            "auto_ratio": self.auto_ratio,
            "expiration": self.expiration,
            "direction": self.direction,
            "action_on_loss": self.action_on_loss,
            "min_profit": self.min_profit
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MartingaleStep':
        """Создание из словаря."""
        return cls(
            step=int(data.get("step", 1)),
            ratio=float(data.get("ratio", 2.0)),
            auto_ratio=data.get("auto_ratio", True),
            expiration=int(data.get("expiration", 0)),
            direction=data.get("direction", "previous"),
            action_on_loss=data.get("action_on_loss", "new_asset"),
            min_profit=int(data.get("min_profit", 75))
        )


@dataclass
class MartingaleConfig:
    """
    Конфигурация мартингейла.

    Attributes:
        enabled: Включён ли мартингейл
        max_steps: Максимальное количество шагов
        reset_on_win: Сброс на шаг 0 после выигрыша
        steps: Список шагов мартингейла
    """
    enabled: bool = True
    max_steps: int = 3
    reset_on_win: bool = True
    steps: List[MartingaleStep] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Конвертация в словарь (формат расширения)."""
        return {
            "enabled": self.enabled,
            "max_steps": self.max_steps,
            "reset_on_win": self.reset_on_win,
            "steps": [s.to_dict() for s in self.steps]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MartingaleConfig':
        """Создание из словаря."""
        steps = []
        for step_data in data.get("steps", []):
            steps.append(MartingaleStep.from_dict(step_data))
        
        return cls(
            enabled=data.get("enabled", True),
            max_steps=int(data.get("max_steps", 3)),
            reset_on_win=data.get("reset_on_win", True),
            steps=steps
        )

    def get_step(self, step_number: int) -> Optional[MartingaleStep]:
        """
        Получить шаг по номеру.

        Args:
            step_number: Номер шага (0-based для первой сделки)

        Returns:
            Конфигурация шага или None
        """
        if step_number < 0 or step_number >= len(self.steps):
            return None
        return self.steps[step_number]

    def get_next_step(self, current_step: int) -> int:
        """
        Получить следующий шаг.

        Args:
            current_step: Текущий шаг

        Returns:
            Номер следующего шага или -1 если достигнут максимум
        """
        next_step = current_step + 1
        if next_step >= self.max_steps:
            return -1  # Достигнут максимум
        return next_step


# ==============================================================================
# СТРАТЕГИЯ
# ==============================================================================

@dataclass
class StrategyConfig:
    """
    Конфигурация стратегии.

    Attributes:
        name: Название стратегии
        description: Описание
        id: Уникальный ID стратегии
        type: Тип стратегии ("personal", "public")
        
        # Активы
        assets: Список выбранных активов
        asset_groups: Выбранные группы активов
        max_active_assets: Макс. одновременных активов
        exclude_assets: Исключённые активы
        
        # Индикаторы
        indicators: Список индикаторов
        min_agreement: Мин. количество индикаторов для сигнала
        use_weights: Использовать ли веса индикаторов
        
        # Регламент
        regulations: Регламент работы
        
        # Мартингейл
        martingale: Конфигурация мартингейла
        
        # Статистика
        total_trades: Всего сделок
        profitable_trades: Прибыльных сделок
        total_profit: Общая прибыль
    """
    name: str
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "personal"  # "personal" или "public"
    
    # Активы
    assets: List[str] = field(default_factory=list)
    asset_groups: List[str] = field(default_factory=list)
    max_active_assets: int = 10
    exclude_assets: List[str] = field(default_factory=list)
    
    # Индикаторы
    indicators: List[IndicatorConfig] = field(default_factory=list)
    min_agreement: int = 1
    use_weights: bool = False
    
    # Регламент
    regulations: RegulationsConfig = field(default_factory=RegulationsConfig)
    
    # Мартингейл
    martingale: MartingaleConfig = field(default_factory=MartingaleConfig)
    
    # Статистика
    total_trades: int = 0
    profitable_trades: int = 0
    total_profit: float = 0.0
    user_title: str = ""  # Пользовательское название

    def to_dict(self) -> Dict:
        """Конвертация в словарь (наш формат)."""
        return {
            "name": self.name,
            "description": self.description,
            "id": self.id,
            "type": self.type,
            "assets": self.assets,
            "asset_groups": self.asset_groups,
            "max_active_assets": self.max_active_assets,
            "exclude_assets": self.exclude_assets,
            "indicators": [i.to_dict() for i in self.indicators],
            "min_agreement": self.min_agreement,
            "use_weights": self.use_weights,
            "regulations": self.regulations.to_dict(),
            "martingale": self.martingale.to_dict(),
            "total_trades": self.total_trades,
            "profitable_trades": self.profitable_trades,
            "total_profit": self.total_profit,
            "user_title": self.user_title
        }

    def to_extension_format(self) -> Dict:
        """Конвертация в формат расширения."""
        return {
            "data": {
                "title": self.name,
                "userTitle": self.user_title or self.name
            },
            "id": self.id,
            "type": self.type,
            "assets": {
                "enabled": self.assets,
                "exclude": self.exclude_assets,
                "groups": self.asset_groups,
                "max_active": self.max_active_assets
            },
            "indicators": [i.to_dict() for i in self.indicators],
            "martingale": {
                "enabled": self.martingale.enabled,
                "max_steps": self.martingale.max_steps,
                "reset_on_win": self.martingale.reset_on_win,
                "steps": [s.to_dict() for s in self.martingale.steps]
            },
            "regulations": {
                "bet": self.regulations.bet,
                "expiration": self.regulations.expiration,
                "max_active_trades": self.regulations.max_active_trades,
                "max_bets": self.regulations.max_bets,
                "max_daily_loss": self.regulations.max_daily_loss,
                "max_daily_profit": self.regulations.max_daily_profit,
                "min_profit": self.regulations.min_profit,
                "mode": self.regulations.mode,
                "stop_loss": self.regulations.stop_loss,
                "stop_on_loss": self.regulations.stop_on_loss,
                "stop_on_profit": self.regulations.stop_on_profit,
                "take_profit": self.regulations.take_profit,
                "time_from": self.regulations.time_from,
                "time_to": self.regulations.time_to,
                "timezone": self.regulations.timezone
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'StrategyConfig':
        """Создание из словаря (наш формат)."""
        # Индикаторы
        indicators = []
        for ind_data in data.get("indicators", []):
            if isinstance(ind_data, dict):
                indicators.append(IndicatorConfig.from_dict(ind_data))
        
        # Регламент
        regulations = RegulationsConfig.from_dict(data.get("regulations", {}))
        
        # Мартингейл
        martingale = MartingaleConfig.from_dict(data.get("martingale", {}))
        
        return cls(
            name=data.get("name", "Strategy"),
            description=data.get("description", ""),
            id=data.get("id", str(uuid.uuid4())),
            type=data.get("type", "personal"),
            assets=data.get("assets", []),
            asset_groups=data.get("asset_groups", []),
            max_active_assets=int(data.get("max_active_assets", 10)),
            exclude_assets=data.get("exclude_assets", []),
            indicators=indicators,
            min_agreement=int(data.get("min_agreement", 1)),
            use_weights=data.get("use_weights", False),
            regulations=regulations,
            martingale=martingale,
            total_trades=int(data.get("total_trades", 0)),
            profitable_trades=int(data.get("profitable_trades", 0)),
            total_profit=float(data.get("total_profit", 0)),
            user_title=data.get("user_title", "")
        )

    @classmethod
    def from_extension_format(cls, data: Dict) -> 'StrategyConfig':
        """Создание из формата расширения."""
        # Данные
        data_section = data.get("data", {})
        name = data_section.get("userTitle") or data_section.get("title", "Strategy")
        
        # Активы
        assets_section = data.get("assets", {})
        assets = assets_section.get("enabled", [])
        exclude = assets_section.get("exclude", [])
        groups = assets_section.get("groups", [])
        max_active = assets_section.get("max_active", 10)
        
        # Индикаторы
        indicators = []
        for ind_data in data.get("indicators", []):
            indicators.append(IndicatorConfig.from_dict(ind_data))
        
        # Мартингейл
        martingale_data = data.get("martingale", {})
        martingale = MartingaleConfig(
            enabled=martingale_data.get("enabled", True),
            max_steps=martingale_data.get("max_steps", 3),
            reset_on_win=martingale_data.get("reset_on_win", True)
        )
        for step_data in martingale_data.get("steps", []):
            martingale.steps.append(MartingaleStep.from_dict(step_data))
        
        # Регламент
        regulations_data = data.get("regulations", {})
        regulations = RegulationsConfig(
            mode=regulations_data.get("mode", "trade"),
            time_from=regulations_data.get("time_from", "00:00"),
            time_to=regulations_data.get("time_to", "23:59"),
            timezone=regulations_data.get("timezone", "UTC"),
            min_profit=int(regulations_data.get("min_profit", 85)),
            expiration=int(regulations_data.get("expiration", 60)),
            bet=float(regulations_data.get("bet", 1.0)),
            max_active_trades=int(regulations_data.get("max_active_trades", 1)),
            max_bets=int(regulations_data.get("max_bets", 1)),
            max_daily_loss=float(regulations_data.get("max_daily_loss", 100)),
            max_daily_profit=float(regulations_data.get("max_daily_profit", 500)),
            stop_loss=float(regulations_data.get("stop_loss", 0)),
            take_profit=float(regulations_data.get("take_profit", 0)),
            stop_on_loss=regulations_data.get("stop_on_loss", False),
            stop_on_profit=regulations_data.get("stop_on_profit", False)
        )
        
        return cls(
            name=name,
            description="",
            id=data.get("id", str(uuid.uuid4())),
            type=data.get("type", "personal"),
            assets=assets,
            asset_groups=groups,
            max_active_assets=max_active,
            exclude_assets=exclude,
            indicators=indicators,
            min_agreement=1,
            use_weights=False,
            regulations=regulations,
            martingale=martingale
        )

    def to_json(self, indent: int = 2) -> str:
        """Конвертация в JSON строку."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_extension_json(self, indent: int = 2) -> str:
        """Конвертация в JSON строку (формат расширения)."""
        return json.dumps(self.to_extension_format(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'StrategyConfig':
        """Создание из JSON строки."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_extension_json(cls, json_str: str) -> 'StrategyConfig':
        """Создание из JSON строки (формат расширения)."""
        data = json.loads(json_str)
        return cls.from_extension_format(data)

    def to_file(self, filepath: str, extension_format: bool = False):
        """
        Сохранение в файл.

        Args:
            filepath: Путь к файлу
            extension_format: Сохранять в формате расширения
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            if extension_format:
                f.write(self.to_extension_json())
            else:
                f.write(self.to_json())

    @classmethod
    def from_file(cls, filepath: str, extension_format: bool = False) -> 'StrategyConfig':
        """
        Загрузка из файла.

        Args:
            filepath: Путь к файлу
            extension_format: Формат расширения

        Returns:
            Загруженная стратегия
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            json_str = f.read()
        
        if extension_format:
            return cls.from_extension_json(json_str)
        else:
            return cls.from_json(json_str)

    def get_enabled_indicators(self) -> List[IndicatorConfig]:
        """Получить включённые индикаторы."""
        return [i for i in self.indicators if i.enabled]

    def is_asset_allowed(self, asset_id: str) -> bool:
        """
        Проверка: разрешён ли актив.

        Args:
            asset_id: ID актива

        Returns:
            True если актив разрешён
        """
        if asset_id in self.exclude_assets:
            return False
        if self.assets and asset_id not in self.assets:
            return False
        return True

    def get_stats(self) -> Dict:
        """Получить статистику стратегии."""
        return {
            "total_trades": self.total_trades,
            "profitable_trades": self.profitable_trades,
            "total_profit": self.total_profit,
            "win_rate": (self.profitable_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            "active_indicators": len(self.get_enabled_indicators()),
            "active_assets": len(self.assets)
        }


__all__ = [
    "IndicatorConfig",
    "RegulationsConfig",
    "MartingaleStep",
    "MartingaleConfig",
    "StrategyConfig"
]
