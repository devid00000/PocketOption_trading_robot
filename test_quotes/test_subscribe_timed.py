#!/usr/bin/env python3
"""
Тест метода subscribe_symbol_timed() от разработчика.
https://github.com/ChipaDevTeam/BinaryOptionsTools-v2/blob/master/examples/python/async/subscribe_symbol_timed.py
"""

import asyncio
import time
from datetime import timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

from config.runtime import load_runtime_config

DEMO_SSID = load_runtime_config().demo_ssid


async def test_subscribe_symbol_timed():
    """Тест subscribe_symbol_timed() с разными периодами."""
    
    print("\n" + "=" * 80)
    print("🧪 ТЕСТ: subscribe_symbol_timed()")
    print("=" * 80)
    print("Метод от разработчика: объединяет свечи в указанном временном диапазоне")
    print("=" * 80)
    
    if not DEMO_SSID:
        raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
    api = PocketOptionAsync(ssid=DEMO_SSID)
    
    # Даём время на подключение
    print("\n⏳ Подключение (5 сек)...")
    time.sleep(5)
    
    print(f"\n✅ API инициализирован")
    print(f"   Демо счёт: {api.is_demo()}")
    print(f"   Баланс: ${await api.balance()}")
    
    # ==========================================================================
    # ТЕСТ 1: Период 5 секунд
    # ==========================================================================
    print(f"\n{'=' * 80}")
    print("📊 ТЕСТ 1: subscribe_symbol_timed('EURUSD_otc', timedelta(seconds=5))")
    print(f"{'=' * 80}")
    
    try:
        print(f"   ⏳ Подписка...")
        stream = await api.subscribe_symbol_timed(
            "EURUSD_otc",
            timedelta(seconds=5)
        )
        
        print(f"   ✅ Подписка успешна, ожидание свечей (30 сек)...")
        
        count = 0
        start_time = time.time()
        
        async with asyncio.timeout(30):
            async for candle in stream:
                count += 1
                elapsed = time.time() - start_time
                
                # Форматируем свечу
                timestamp = candle.get('timestamp', 0)
                open_p = float(candle.get('open', 0))
                high = float(candle.get('high', 0))
                low = float(candle.get('low', 0))
                close = float(candle.get('close', 0))
                volume = candle.get('volume', 0)
                period = candle.get('period', 0)
                
                print(f"   [{count}] {elapsed:5.1f}сек | period={period}s | O={open_p:.5f} H={high:.5f} L={low:.5f} C={close:.5f} V={volume}")
                
                if count >= 10:
                    break
        
        print(f"\n   ✅ Получено {count} свечей за {elapsed:.2f} сек")
        print(f"   ⏱️ Средняя скорость: {elapsed/count:.2f} сек/свечу")
        
    except asyncio.TimeoutError:
        print(f"   ⏳ ТАЙМАУТ (30 сек)")
    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    # ==========================================================================
    # ТЕСТ 2: Период 10 секунд
    # ==========================================================================
    print(f"\n{'=' * 80}")
    print("📊 ТЕСТ 2: subscribe_symbol_timed('EURUSD_otc', timedelta(seconds=10))")
    print(f"{'=' * 80}")
    
    try:
        print(f"   ⏳ Подписка...")
        stream = await api.subscribe_symbol_timed(
            "EURUSD_otc",
            timedelta(seconds=10)
        )
        
        print(f"   ✅ Подписка успешна, ожидание свечей (30 сек)...")
        
        count = 0
        start_time = time.time()
        
        async with asyncio.timeout(30):
            async for candle in stream:
                count += 1
                elapsed = time.time() - start_time
                
                timestamp = candle.get('timestamp', 0)
                open_p = float(candle.get('open', 0))
                high = float(candle.get('high', 0))
                low = float(candle.get('low', 0))
                close = float(candle.get('close', 0))
                period = candle.get('period', 0)
                
                print(f"   [{count}] {elapsed:5.1f}сек | period={period}s | C={close:.5f}")
                
                if count >= 5:
                    break
        
        print(f"\n   ✅ Получено {count} свечей за {elapsed:.2f} сек")
        
    except asyncio.TimeoutError:
        print(f"   ⏳ ТАЙМАУТ (30 сек)")
    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")
    
    # ==========================================================================
    # ТЕСТ 3: Период 60 секунд (1 минута)
    # ==========================================================================
    print(f"\n{'=' * 80}")
    print("📊 ТЕСТ 3: subscribe_symbol_timed('EURUSD_otc', timedelta(seconds=60))")
    print(f"{'=' * 80}")
    
    try:
        print(f"   ⏳ Подписка...")
        stream = await api.subscribe_symbol_timed(
            "EURUSD_otc",
            timedelta(seconds=60)
        )
        
        print(f"   ✅ Подписка успешна, ожидание свечей (120 сек)...")
        
        count = 0
        start_time = time.time()
        
        async with asyncio.timeout(120):
            async for candle in stream:
                count += 1
                elapsed = time.time() - start_time
                
                timestamp = candle.get('timestamp', 0)
                open_p = float(candle.get('open', 0))
                high = float(candle.get('high', 0))
                low = float(candle.get('low', 0))
                close = float(candle.get('close', 0))
                period = candle.get('period', 0)
                
                print(f"   [{count}] {elapsed:5.1f}сек | period={period}s | C={close:.5f}")
                
                if count >= 3:
                    break
        
        print(f"\n   ✅ Получено {count} свечей за {elapsed:.2f} сек")
        
    except asyncio.TimeoutError:
        print(f"   ⏳ ТАЙМАУТ (120 сек)")
    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")
    
    # ==========================================================================
    # ИТОГИ
    # ==========================================================================
    print(f"\n{'=' * 80}")
    print("📊 ИТОГИ ТЕСТА subscribe_symbol_timed()")
    print(f"{'=' * 80}")
    print("""
subscribe_symbol_timed() — метод от разработчика для получения свечей в реальном времени.

ОСОБЕННОСТИ:
  • Использует timedelta для указания периода
  • Объединяет свечи в указанном временном диапазоне
  • Возвращает свечи в реальном времени
  • Работает как асинхронный генератор

ПРЕИМУЩЕСТВА:
  • ✅ Работает в реальном времени
  • ✅ Не требует запросов (push-модель)
  • ✅ Автоматическое объединение свечей

НЕДОСТАТКИ:
  • ⚠️ Требует длительного подключения
  • ⚠️ Не подходит для получения истории
  • ⚠️ Нужно обрабатывать поток непрерывно

РЕКОМЕНДАЦИЯ:
  • Использовать для отображения цены в реальном времени
  • Для истории использовать get_candles() (если работает)
  • Для определения результата сделки — сравнение баланса
""")


async def main():
    """Запуск теста."""
    try:
        await test_subscribe_symbol_timed()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
