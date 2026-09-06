#!/usr/bin/env python3
"""
Pocket Option Robot - Главная точка входа.
Интеграция всех компонентов: RobotEngine, Стратегии, TradeLogger, GUI.
"""

import sys
import asyncio
import argparse
from pathlib import Path

# Добавляем корень проекта в path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ==============================================================================
# КОНФИГУРАЦИЯ
# ==============================================================================

from config.paths import ensure_project_dirs
from config.runtime import load_runtime_config

# ==============================================================================
# КОМАНДЫ
# ==============================================================================

def cmd_gui(args):
    """Запуск GUI интерфейса."""
    from ui.app import run_gui

    config = load_runtime_config()
    ssid = config.real_ssid if args.real else config.demo_ssid

    if args.real and not ssid:
        print("❌ SSID для реального счёта не установлен!")
        print("   Заполните POCKET_OPTION_REAL_SSID в .env или используйте настройки подключения.")
        sys.exit(1)

    print("🚀 Запуск GUI...")
    run_gui(ssid=ssid)


def cmd_trade(args):
    """Запуск торгового бота (CLI)."""
    print("❌ CLI-бот ещё не подключён к новой архитектуре.")
    print("   Используйте GUI для ручной проверки после завершения этапов 1-3.")
    sys.exit(2)



def cmd_stats(args):
    """Показать статистику торговли."""
    from storage.trade_logger import TradeLogger

    logger = TradeLogger()

    if args.today:
        stats = logger.get_today_stats()
        print("\n📊 СТАТИСТИКА ЗА СЕГОДНЯ:")
        print(f"   Сделок: {stats.get('total_trades', 0)}")
        print(f"   Побед: {stats.get('winning_trades', 0)}")
        print(f"   Поражений: {stats.get('losing_trades', 0)}")
        print(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
        print(f"   Прибыль: ${stats.get('total_profit', 0):.2f}")
    else:
        stats = logger.get_summary(days=args.days)
        print(f"\n📊 СТАТИСТИКА ЗА {args.days} ДНЕЙ:")
        print(f"   Сделок: {stats.get('total_trades', 0)}")
        print(f"   Побед: {stats.get('wins', 0)}")
        print(f"   Поражений: {stats.get('losses', 0)}")
        print(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
        print(f"   Прибыль: ${stats.get('total_profit', 0):.2f}")
        print(f"   Profit Factor: {stats.get('profit_factor', 0):.2f}")

        if stats.get('by_strategy'):
            print("\n   ПО СТРАТЕГИЯМ:")
            for s in stats['by_strategy']:
                print(f"   - {s.get('strategy_name', 'N/A')}: "
                      f"{s.get('trades', 0)} сделок, "
                      f"${s.get('total_profit', 0):.2f}")

        if stats.get('by_symbol'):
            print("\n   ПО АКТИВАМ:")
            for s in stats['by_symbol']:
                print(f"   - {s.get('symbol', 'N/A')}: "
                      f"{s.get('trades', 0)} сделок, "
                      f"${s.get('total_profit', 0):.2f}")


def cmd_strategies(args):
    """Управление стратегиями."""
    from strategies.manager import StrategyManager

    manager = StrategyManager()

    if args.list:
        strategies = manager.list_strategies()
        print("\n📊 ДОСТУПНЫЕ СТРАТЕГИИ:")
        for s in strategies:
            print(f"   • {s}")

    elif args.create:
        strategy_configs = {
            "rsi": {
                "type": "RSIStrategy",
                "config": {"period": 14, "overbought": 70, "oversold": 30}
            },
            "bb": {
                "type": "BollingerBandsStrategy",
                "config": {"period": 20, "std_dev": 2.0}
            },
            "macd": {
                "type": "MACDStrategy",
                "config": {"fast_period": 12, "slow_period": 26, "signal_period": 9}
            },
            "multi": {
                "type": "MultiIndicatorStrategy",
                "config": {"use_rsi": True, "use_bb": True, "use_macd": True, "min_agreement": 2}
            }
        }

        config = strategy_configs.get(args.create.lower())
        if config:
            strategy = manager.create_strategy(config["type"], config=config["config"])
            filepath = manager.save_strategy(strategy)
            print(f"✅ Стратегия создана: {strategy.name}")
            print(f"   Файл: {filepath}")
        else:
            print(f"❌ Неизвестная стратегия: {args.create}")

    elif args.defaults:
        manager.create_default_strategies()
        print("✅ Стратегии по умолчанию созданы")

    elif args.export:
        count = manager.import_all(args.export)
        print(f"✅ Импортировано {count} стратегий")


def cmd_init(args):
    """Инициализация проекта."""
    print("🚀 Инициализация Pocket Option Robot...")

    # Создание стандартных директорий относительно корня проекта.
    ensure_project_dirs()
    for d in ("strategies/configs", "storage", "logs", "exports"):
        print(f"   ✅ {d}")

    # Создание .env файла
    env_path = project_root / ".env"
    if not env_path.exists():
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("""# Pocket Option Robot Configuration

# SSID для демо-счёта (получить через get_session_cookie.py)
POCKET_OPTION_DEMO_SSID=

# SSID для реального счёта (опционально)
POCKET_OPTION_REAL_SSID=

# Настройки по умолчанию
DEFAULT_SYMBOL=EURUSD_otc
DEFAULT_PERIOD=60
DEFAULT_AMOUNT=1.0
DEFAULT_DURATION=60
""")
        print("   ✅ .env создан")

    # Стратегии по умолчанию
    from strategies.manager import StrategyManager
    manager = StrategyManager()
    manager.create_default_strategies()

    print("\n✅ Инициализация завершена!")
    print("\n📋 Следующие шаги:")
    print("   1. Получите SSID: python get_session_cookie.py")
    print("   2. Добавьте SSID в .env")
    print("   3. Запустите GUI: python main.py gui")
    print("   4. Или запустите бота: python main.py trade --strategy rsi")


def cmd_check(args):
    """Проверка подключения."""
    from core.robot_engine import RobotEngine

    config = load_runtime_config()
    ssid = config.real_ssid if args.real else config.demo_ssid

    if args.real and not ssid:
        print("❌ SSID для реального счёта не установлен!")
        sys.exit(1)

    async def check():
        engine = RobotEngine(ssid=ssid)
        try:
            await engine.connect()
            balance = engine.get_balance()
            print("✅ Подключено!")
            print(f"   Баланс: ${balance.current:.2f}")
            print(f"   Тип счёта: {'DEMO' if balance.is_demo else 'REAL'}")
            await engine.disconnect()
            return True
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    result = asyncio.run(check())
    sys.exit(0 if result else 1)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Pocket Option Robot - Автоматизация торговли",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python main.py gui                     # Запуск GUI (демо)
  python main.py gui --real              # Запуск GUI (реал)
  python main.py trade --strategy rsi    # Торговля с RSI
  python main.py stats --today           # Статистика за сегодня
  python main.py strategies --defaults   # Создать стратегии
  python main.py check                   # Проверка подключения
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Команда")

    # GUI команда
    gui_parser = subparsers.add_parser("gui", help="Запуск GUI интерфейса")
    gui_parser.add_argument("--real", action="store_true", help="Реальный счёт")
    gui_parser.set_defaults(func=cmd_gui)

    # Trade команда
    trade_parser = subparsers.add_parser("trade", help="Запуск торгового бота")
    trade_parser.add_argument("--real", action="store_true", help="Реальный счёт")
    trade_parser.add_argument("--strategy", default="simple",
                             choices=["simple", "rsi", "bb", "macd", "multi"],
                             help="Стратегия")
    trade_parser.add_argument("--symbol", default="EURUSD_otc", help="Актив")
    trade_parser.add_argument("--amount", type=float, default=1.0, help="Сумма сделки")
    trade_parser.add_argument("--duration", type=int, default=60, help="Длительность (сек)")
    trade_parser.add_argument("--max-trades", type=int, default=10, help="Макс. сделок")
    trade_parser.add_argument("--stop-loss", type=float, help="Stop Loss ($)")
    trade_parser.add_argument("--take-profit", type=float, help="Take Profit ($)")
    trade_parser.set_defaults(func=cmd_trade)

    # Stats команда
    stats_parser = subparsers.add_parser("stats", help="Статистика торговли")
    stats_parser.add_argument("--today", action="store_true", help="За сегодня")
    stats_parser.add_argument("--days", type=int, default=30, help="Период (дней)")
    stats_parser.set_defaults(func=cmd_stats)

    # Strategies команда
    strat_parser = subparsers.add_parser("strategies", help="Управление стратегиями")
    strat_parser.add_argument("--list", action="store_true", help="Список стратегий")
    strat_parser.add_argument("--create", help="Создать стратегию (rsi, bb, macd, multi)")
    strat_parser.add_argument("--defaults", action="store_true", help="Стратегии по умолчанию")
    strat_parser.add_argument("--export", help="Импорт стратегий из файла")
    strat_parser.set_defaults(func=cmd_strategies)

    # Init команда
    init_parser = subparsers.add_parser("init", help="Инициализация проекта")
    init_parser.set_defaults(func=cmd_init)

    # Check команда
    check_parser = subparsers.add_parser("check", help="Проверка подключения")
    check_parser.add_argument("--real", action="store_true", help="Реальный счёт")
    check_parser.set_defaults(func=cmd_check)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
