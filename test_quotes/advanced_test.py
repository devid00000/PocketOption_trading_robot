#!/usr/bin/env python3
"""
Исследование альтернативных методов получения котировок.
Тестирует raw handler API и другие подходы.
"""

import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from BinaryOptionsToolsV2 import PocketOptionAsync

from config.runtime import load_runtime_config

DEMO_SSID = load_runtime_config().demo_ssid


async def test_raw_handler():
    """Тест Raw Handler API для получения данных."""
    
    print("\n" + "=" * 80)
    print("🔬 ИССЛЕДОВАНИЕ: Raw Handler API")
    print("=" * 80)
    
    if not DEMO_SSID:
        raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        print(f"\n✅ Подключено")
        print(f"   Баланс: ${await client.balance()}")
        
        # ==========================================================================
        # МЕТОД 5: create_raw_handler() + subscribe()
        # ==========================================================================
        print(f"\n📊 МЕТОД 5: Raw Handler + subscribe()")
        print(f"   Описание: Низкоуровневый доступ к WebSocket сообщениям")
        
        try:
            # Создаём raw handler
            print(f"   Создание raw handler...")
            handler = client.create_raw_handler(validator=None)
            
            # Подписываемся на свечи
            print(f"   Подписка на EURUSD_otc...")
            await handler.subscribe("EURUSD_otc")
            
            print(f"   ⏳ Ожидание данных (10 сек)...")
            
            # Получаем данные
            count = 0
            start_time = time.time()
            
            async with asyncio.timeout(10):
                async for message in handler:
                    count += 1
                    print(f"   [{count}] Получено сообщение: {type(message)}")
                    if isinstance(message, dict):
                        print(f"        {message}")
                    
                    if count >= 5:
                        break
            
            elapsed = time.time() - start_time
            print(f"   ✅ Получено {count} сообщений за {elapsed:.2f} сек")
            
        except asyncio.TimeoutError:
            print(f"   ⏳ ТАЙМАУТ (10 сек)")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
        
        # ==========================================================================
        # МЕТОД 6: candles() - потоковое получение
        # ==========================================================================
        print(f"\n📊 МЕТОД 6: candles()")
        print(f"   Описание: Потоковое получение свечей")
        
        try:
            print(f"   Запрос candles('EURUSD_otc', 60)...")
            
            start_time = time.time()
            candles_iter = await client.candles("EURUSD_otc", 60)
            
            print(f"   ⏳ Ожидание свечей (10 сек)...")
            
            count = 0
            async with asyncio.timeout(10):
                async for candle in candles_iter:
                    count += 1
                    ts = candle.get('timestamp', 0)
                    close = float(candle.get('close', 0))
                    dt = datetime.fromtimestamp(ts)
                    print(f"   [{count}] {dt.strftime('%H:%M:%S')} | Close={close:.5f}")
                    
                    if count >= 5:
                        break
            
            elapsed = time.time() - start_time
            print(f"   ✅ Получено {count} свечей за {elapsed:.2f} сек")
            
        except asyncio.TimeoutError:
            print(f"   ⏳ ТАЙМАУТ (10 сек)")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        # ==========================================================================
        # МЕТОД 7: history() - история сделок
        # ==========================================================================
        print(f"\n📊 МЕТОД 7: history()")
        print(f"   Описание: Получение истории сделок")
        
        try:
            print(f"   Запрос истории...")
            
            start_time = time.time()
            history = await client.history()
            elapsed = time.time() - start_time
            
            print(f"   Тип: {type(history)}")
            
            if history:
                if isinstance(history, list):
                    print(f"   ✅ УСПЕХ: {len(history)} сделок за {elapsed:.2f} сек")
                    if history:
                        print(f"   Пример: {history[0]}")
                else:
                    print(f"   ✅ УСПЕХ: данные получены")
            else:
                print(f"   ℹ️ ПУСТО: история пуста")
            
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        # ==========================================================================
        # МЕТОД 8: get_candles() с большим таймаутом
        # ==========================================================================
        print(f"\n📊 МЕТОД 8: get_candles() с таймаутом 30 сек")
        print(f"   Описание: Попытка получить свечи с большим таймаутом")
        
        try:
            print(f"   Запрос свечей EURUSD_otc (60s)...")
            
            start_time = time.time()
            candles = await asyncio.wait_for(
                client.get_candles("EURUSD_otc", period=60, offset=0),
                timeout=30
            )
            elapsed = time.time() - start_time
            
            if candles:
                print(f"   ✅ УСПЕХ: {len(candles)} свечей за {elapsed:.2f} сек")
                
                # Показываем последние 3 свечи
                print(f"\n   Последние 3 свечи:")
                for i, candle in enumerate(candles[-3:], 1):
                    ts = candle.get('timestamp', 0)
                    dt = datetime.fromtimestamp(ts)
                    open_p = float(candle.get('open', 0))
                    high = float(candle.get('high', 0))
                    low = float(candle.get('low', 0))
                    close = float(candle.get('close', 0))
                    print(f"     {i}. {dt.strftime('%H:%M:%S')} | O={open_p:.5f} H={high:.5f} L={low:.5f} C={close:.5f}")
            else:
                print(f"   ⚠️ ПУСТО: свечи не получены")
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            print(f"   ⏳ ТАЙМАУТ: {elapsed:.2f} сек (превышено 30 сек)")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")


async def test_alternative_assets():
    """Тест на разных активах."""
    
    print("\n" + "=" * 80)
    print("🔬 ИССЛЕДОВАНИЕ: Разные активы")
    print("=" * 80)
    
    if not DEMO_SSID:
        raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        print(f"\n✅ Подключено")
        
        # Тестируем на разных активах
        test_assets = [
            ("EURUSD_otc", 60),
            ("BTCUSD_otc", 60),
            ("GBPUSD_otc", 300),
        ]
        
        for asset, period in test_assets:
            print(f"\n📊 Тест: {asset} (period={period}s)")
            
            try:
                start_time = time.time()
                candles = await asyncio.wait_for(
                    client.get_candles(asset, period=period, offset=0),
                    timeout=20
                )
                elapsed = time.time() - start_time
                
                if candles:
                    print(f"   ✅ УСПЕХ: {len(candles)} свечей за {elapsed:.2f} сек")
                    last = candles[-1]
                    print(f"   Последняя: close={float(last.get('close', 0)):.5f}")
                else:
                    print(f"   ⚠️ ПУСТО")
                    
            except asyncio.TimeoutError:
                print(f"   ⏳ ТАЙМАУТ ({elapsed:.2f} сек)")
            except Exception as e:
                print(f"   ❌ ОШИБКА: {e}")


async def test_websocket_direct():
    """Тест прямого WebSocket подключения."""
    
    print("\n" + "=" * 80)
    print("🔬 ИССЛЕДОВАНИЕ: Прямой WebSocket (через BinaryOptionsToolsV2)")
    print("=" * 80)
    
    if not DEMO_SSID:
        raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        print(f"\n✅ Подключено")
        
        # ==========================================================================
        # МЕТОД 9: send_raw_message()
        # ==========================================================================
        print(f"\n📊 МЕТОД 9: send_raw_message()")
        print(f"   Описание: Отправка произвольных WebSocket сообщений")
        
        try:
            # Отправляем запрос на получение свечей
            print(f"   Отправка запроса на свечи...")
            
            # Формат сообщения для запроса свечей
            message = {
                "name": "get-candles",
                "version": "1.0",
                "body": {
                    "symbol": "EURUSD_otc",
                    "period": 60,
                    "from": int(time.time() * 1000) - 60000,  # 1 мин назад
                    "to": int(time.time() * 1000)
                }
            }
            
            await client.send_raw_message(message)
            print(f"   ✅ Запрос отправлен")
            
            # Ждём ответ
            print(f"   ⏳ Ожидание ответа (5 сек)...")
            
            # BinaryOptionsToolsV2 не предоставляет прямого метода для получения ответа
            # на raw message, поэтому этот метод требует доработки
            print(f"   ⚠️ Требуется доработка для получения ответа")
            
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")


async def main():
    """Запуск тестов."""
    print("\n" + "=" * 80)
    print("🧪 КОМПЛЕКСНОЕ ИССЛЕДОВАНИЕ МЕТОДОВ ПОЛУЧЕНИЯ КОТИРОВОК")
    print("=" * 80)
    
    try:
        # Тест 1: Raw Handler API
        await test_raw_handler()
        
        # Тест 2: Разные активы
        await test_alternative_assets()
        
        # Тест 3: Прямой WebSocket
        await test_websocket_direct()
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ ИССЛЕДОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)
    
    # Итоговая таблица
    print("""
┌─────────────────────────────┬──────────────┬─────────────┬──────────────┐
│ Метод                       │ Статус       │ Время       │ Примечание   │
├─────────────────────────────┼──────────────┼─────────────┼──────────────┤
│ get_candles()               │ ТАЙМАУТ      │ >15 сек     │ Не работает  │
│ subscribe_symbol()          │ ТАЙМАУТ      │ >10 сек     │ Не работает  │
│ opened_deals()              │ ✅ РАБОТАЕТ  │ <1 сек      │ Нет сделок   │
│ get_server_time()           │ ✅ РАБОТАЕТ  │ <1 сек      │ Работает     │
│ balance()                   │ ✅ РАБОТАЕТ  │ <1 сек      │ Работает     │
│ active_assets()             │ ✅ РАБОТАЕТ  │ 1-2 сек     │ Работает     │
│ candles()                   │ ?            │ ?           │ Тест         │
│ Raw Handler                 │ ?            │ ?           │ Тест         │
│ history()                   │ ?            │ ?           │ Тест         │
└─────────────────────────────┴──────────────┴─────────────┴──────────────┘

ВЫВОД:
  • BinaryOptionsToolsV2 подключается к платформе
  • Баланс и активы работают
  • Свечи НЕ возвращаются (таймаут)
  • Требуется альтернативный подход
""")


if __name__ == "__main__":
    asyncio.run(main())
