"""
Модели данных для роботов.

Поддерживает два формата:
1. Старый формат (StrategySettings, MartingaleLevel) — для обратной совместимости
2. Новый формат (StrategyConfig) — с множественными активами и индикаторами
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Импортируем новые модели
from .strategy_models import (
    StrategyConfig,
    IndicatorConfig,
    RegulationsConfig,
    MartingaleConfig,
    MartingaleStep
)


@dataclass
class StrategySettings:
    """Настройки стратегии (старый формат для обратной совместимости)."""
    strategy_type: str  # "rsi", "macd", "bollinger", "candle", etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: Dict[str, str] = field(default_factory=dict)  # {"call": "rsi < 30", "put": "rsi > 70"}


@dataclass
class MartingaleLevel:
    """Уровень мартингейла (старый формат для обратной совместимости)."""
    min_profit: int = 75  # Минимальная прибыль %
    multiplier: float = 2.0  # Множитель ставки
    action: str = "continue"  # "continue", "stop", "new_asset"


@dataclass
class RobotConfig:
    """
    Конфигурация робота.
    
    Поддерживает два формата:
    1. Старый формат (один актив, одна стратегия) — для обратной совместимости
    2. Новый формат (множественные активы, StrategyConfig) — полный функционал
    """
    name: str
    description: str = ""
    
    # Активы (новый формат — множественный выбор)
    assets: List[str] = field(default_factory=list)  # ["EURUSD_otc", "GBPUSD_otc"]
    asset_id: str = "EURUSD_otc"  # Старый формат (один актив)
    
    # Торговые параметры
    amount: float = 1.0
    duration: int = 60  # секунды
    interval: int = 30  # секунды между сделками
    max_trades: int = 0  # 0 = без лимита

    # Стратегия (новый формат)
    strategy_config: Optional[StrategyConfig] = None
    
    # Стратегия (старый формат — для обратной совместимости)
    strategy: StrategySettings = field(default_factory=lambda: StrategySettings(strategy_type="simple"))

    # Мартингейл (новый формат)
    martingale_config: Optional[MartingaleConfig] = None
    
    # Мартингейл (старый формат — для обратной совместимости)
    use_martingale: bool = False
    martingale_levels: List[MartingaleLevel] = field(default_factory=list)

    # Ограничения (старый формат)
    stop_loss: float = 0.0  # 0 = отключен
    take_profit: float = 0.0  # 0 = отключен
    time_from: str = "00:00"
    time_to: str = "23:59"
    work_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # Пн-Вс

    # Статистика
    total_trades: int = 0
    profitable_trades: int = 0
    total_profit: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Инициализация после создания."""
        # Если assets пустой, но asset_id задан — добавляем его
        if not self.assets and self.asset_id:
            self.assets = [self.asset_id]
        
        # Если strategy_config пустой, создаём из старого формата
        if self.strategy_config is None:
            self.strategy_config = self._create_strategy_config_from_old()
        
        # Если martingale_config пустой, создаём из старого формата
        if self.martingale_config is None:
            self.martingale_config = self._create_martingale_config_from_old()

    def _create_strategy_config_from_old(self) -> StrategyConfig:
        """Создание StrategyConfig из старого формата."""
        config = StrategyConfig(
            name=self.name,
            description=self.description,
            assets=self.assets,
            regulations=RegulationsConfig(
                expiration=self.duration,
                bet=self.amount,
                time_from=self.time_from,
                time_to=self.time_to,
                work_days=self.work_days,
                min_profit=85
            )
        )
        
        # Добавляем индикатор из старой стратегии
        if self.strategy.strategy_type != "simple":
            indicator = IndicatorConfig(
                type=self.strategy.strategy_type,
                name=self.strategy.strategy_type.title(),
                parameters=self.strategy.parameters,
                conditions=self.strategy.conditions,
                timeframe=self.strategy.parameters.get("timeframe", 60)
            )
            config.indicators.append(indicator)
        
        return config

    def _create_martingale_config_from_old(self) -> MartingaleConfig:
        """Создание MartingaleConfig из старого формата."""
        if not self.use_martingale:
            return MartingaleConfig(enabled=False)
        
        config = MartingaleConfig(enabled=True, max_steps=len(self.martingale_levels))
        
        for i, level in enumerate(self.martingale_levels):
            config.steps.append(MartingaleStep(
                step=i + 1,
                ratio=level.multiplier,
                auto_ratio=False,
                min_profit=level.min_profit,
                action_on_loss=level.action
            ))
        
        return config

    def to_dict(self) -> Dict:
        """Конвертация в словарь (новый формат)."""
        return {
            "name": self.name,
            "description": self.description,
            "assets": self.assets,
            "amount": self.amount,
            "duration": self.duration,
            "interval": self.interval,
            "max_trades": self.max_trades,
            "strategy_config": self.strategy_config.to_dict() if self.strategy_config else None,
            "martingale_config": self.martingale_config.to_dict() if self.martingale_config else None,
            "total_trades": self.total_trades,
            "profitable_trades": self.profitable_trades,
            "total_profit": self.total_profit,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def to_json(self) -> str:
        """Конвертация в JSON строку."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict) -> 'RobotConfig':
        """Создание из словаря."""
        # StrategyConfig
        strategy_config = None
        if data.get("strategy_config"):
            strategy_config = StrategyConfig.from_dict(data["strategy_config"])
        
        # MartingaleConfig
        martingale_config = None
        if data.get("martingale_config"):
            martingale_config = MartingaleConfig.from_dict(data["martingale_config"])
        
        # Мартингейл (старый формат)
        martingale_levels = []
        if data.get("martingale_levels"):
            for level in data["martingale_levels"]:
                if isinstance(level, dict):
                    martingale_levels.append(MartingaleLevel(**level))
        
        return cls(
            name=data.get("name", "Robot"),
            description=data.get("description", ""),
            assets=data.get("assets", []),
            asset_id=data.get("asset_id", "EURUSD_otc"),
            amount=float(data.get("amount", 1.0)),
            duration=int(data.get("duration", 60)),
            interval=int(data.get("interval", 30)),
            max_trades=int(data.get("max_trades", 0)),
            strategy_config=strategy_config,
            martingale_config=martingale_config,
            use_martingale=data.get("use_martingale", False),
            martingale_levels=martingale_levels,
            stop_loss=float(data.get("stop_loss", 0)),
            take_profit=float(data.get("take_profit", 0)),
            time_from=data.get("time_from", "00:00"),
            time_to=data.get("time_to", "23:59"),
            work_days=data.get("work_days", [0, 1, 2, 3, 4, 5, 6]),
            total_trades=int(data.get("total_trades", 0)),
            profitable_trades=int(data.get("profitable_trades", 0)),
            total_profit=float(data.get("total_profit", 0)),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat())
        )

    @classmethod
    def from_strategy_config(cls, strategy_config: StrategyConfig) -> 'RobotConfig':
        """
        Создание RobotConfig из StrategyConfig.

        Args:
            strategy_config: Конфигурация стратегии

        Returns:
            RobotConfig
        """
        regulations = strategy_config.regulations
        
        return cls(
            name=strategy_config.name,
            description=strategy_config.description,
            assets=strategy_config.assets,
            amount=regulations.bet,
            duration=regulations.expiration,
            interval=30,
            max_trades=0,
            strategy_config=strategy_config,
            martingale_config=strategy_config.martingale,
            use_martingale=strategy_config.martingale.enabled,
            time_from=regulations.time_from,
            time_to=regulations.time_to,
            work_days=regulations.work_days,
            stop_loss=regulations.stop_loss,
            take_profit=regulations.take_profit
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'RobotConfig':
        """Создание из JSON строки."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, filepath: str) -> 'RobotConfig':
        """Загрузка из файла."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_file(self, filepath: str):
        """Сохранение в файл."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    def to_strategy_config(self) -> StrategyConfig:
        """
        Получить StrategyConfig.

        Returns:
            StrategyConfig (или созданный из старого формата)
        """
        if self.strategy_config:
            return self.strategy_config
        
        return self._create_strategy_config_from_old()

    @property
    def win_rate(self) -> float:
        """Процент побед."""
        if self.total_trades == 0:
            return 0.0
        return (self.profitable_trades / self.total_trades) * 100

    @property
    def status_text(self) -> str:
        """Текстовый статус."""
        if self.total_trades == 0:
            return "Новый"
        elif self.win_rate >= 60:
            return "🟢 Прибыльный"
        elif self.win_rate >= 40:
            return "🟡 Средний"
        else:
            return "🔴 Убыточный"


class RobotManager:
    """Менеджер роботов."""
    
    def __init__(self, robots_dir: str = str(__import__("config.paths", fromlist=["ROBOTS_DIR"]).ROBOTS_DIR)):
        """
        Инициализация.
        
        Args:
            robots_dir: Папка для хранения роботов
        """
        self.robots_dir = Path(robots_dir)
        self.robots_dir.mkdir(parents=True, exist_ok=True)
        self._robots: Dict[str, RobotConfig] = {}
        
        # Загружаем существующих роботов
        self.load_all()
    
    def load_all(self):
        """Загрузка всех роботов."""
        self._robots.clear()
        
        for filepath in self.robots_dir.glob("*.json"):
            try:
                robot = RobotConfig.from_file(filepath)
                self._robots[robot.name] = robot
            except Exception as e:
                print(f"[RobotManager] Ошибка загрузки {filepath}: {e}")
        
        print(f"[RobotManager] Загружено {len(self._robots)} роботов")
    
    def save(self, robot: RobotConfig):
        """Сохранение робота."""
        robot.updated_at = datetime.now().isoformat()
        filepath = self.robots_dir / f"{robot.name.replace(' ', '_')}.json"
        robot.to_file(filepath)
        self._robots[robot.name] = robot
        print(f"[RobotManager] Сохранён робот: {robot.name}")
    
    def delete(self, robot_name: str):
        """Удаление робота."""
        if robot_name in self._robots:
            robot = self._robots[robot_name]
            filepath = self.robots_dir / f"{robot.name.replace(' ', '_')}.json"
            if filepath.exists():
                filepath.unlink()
            del self._robots[robot_name]
            print(f"[RobotManager] Удалён робот: {robot_name}")
    
    def get(self, robot_name: str) -> Optional[RobotConfig]:
        """Получение робота."""
        return self._robots.get(robot_name)
    
    def list(self) -> List[RobotConfig]:
        """Список всех роботов."""
        return list(self._robots.values())
    
    def import_robot(self, filepath: str) -> Optional[RobotConfig]:
        """Импорт робота из файла."""
        try:
            robot = RobotConfig.from_file(filepath)
            # Проверяем уникальность имени
            base_name = robot.name
            counter = 1
            while robot.name in self._robots:
                robot.name = f"{base_name} ({counter})"
                counter += 1
            self.save(robot)
            return robot
        except Exception as e:
            print(f"[RobotManager] Ошибка импорта: {e}")
            return None
    
    def export_robot(self, robot_name: str, filepath: str) -> bool:
        """Экспорт робота в файл."""
        robot = self.get(robot_name)
        if robot:
            robot.to_file(filepath)
            return True
        return False
    
    def create_default_robots(self):
        """Создание тестовых роботов (новый формат)."""
        # Простой робот (частые сделки)
        simple_strategy = StrategyConfig(
            name="Simple Test",
            description="Простая стратегия для тестирования",
            assets=["EURUSD_otc"],
            regulations=RegulationsConfig(
                expiration=60,
                bet=1.0,
                min_profit=85
            )
        )
        simple_robot = RobotConfig.from_strategy_config(simple_strategy)
        simple_robot.name = "Тестовый робот"
        simple_robot.interval = 30
        self.save(simple_robot)

        # RSI робот
        rsi_strategy = StrategyConfig(
            name="RSI Агрессив",
            description="Торгует по RSI с частыми сделками",
            assets=["EURUSD_otc"],
            regulations=RegulationsConfig(
                expiration=60,
                bet=1.0,
                min_profit=85
            ),
            martingale=MartingaleConfig(
                enabled=True,
                max_steps=3,
                reset_on_win=True,
                steps=[
                    MartingaleStep(step=1, ratio=2.0, min_profit=75, action_on_loss="new_asset"),
                    MartingaleStep(step=2, ratio=2.5, min_profit=60, action_on_loss="new_asset"),
                    MartingaleStep(step=3, ratio=3.0, min_profit=60, action_on_loss="stop")
                ]
            )
        )
        
        # Добавляем индикатор RSI
        rsi_strategy.indicators.append(IndicatorConfig(
            type="rsi",
            name="RSI",
            timeframe=60,
            parameters={
                "period": 14,
                "overbought": 70,
                "oversold": 30,
                "price_type": "close"
            },
            conditions={
                "call": "valRsi<btl",
                "sell": "valRsi>tpl"
            }
        ))
        
        rsi_robot = RobotConfig.from_strategy_config(rsi_strategy)
        rsi_robot.interval = 30
        self.save(rsi_robot)

        print(f"[RobotManager] Создано {len(self._robots)} тестовых роботов")


__all__ = [
    # Старый формат (для обратной совместимости)
    "StrategySettings",
    "MartingaleLevel",
    
    # Новый формат
    "StrategyConfig",
    "IndicatorConfig",
    "RegulationsConfig",
    "MartingaleConfig",
    "MartingaleStep",
    
    # Робот
    "RobotConfig",
    "RobotManager",
]
