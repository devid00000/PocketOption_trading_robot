#!/usr/bin/env python3
"""
Комплексный тест получения котировок Pocket Option.
Использует несколько методов для получения текущей цены.
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


async def test_all_methods():
    """Тест всех методов получения котировок."""
    
    print("\n" + "=" * 80)
    print("🧪 КОМПЛЕКСНЫЙ ТЕСТ ПОЛУЧЕНИЯ КОТИРОВОК")
    print("=" * 80)
    
    if not DEMO_SSID:
        raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        # Показываем информацию о подключении
        print(f"\n📡 ИНФОРМАЦИЯ О ПОДКЛЮЧЕНИИ:")
        print("   SSID: задан (значение скрыто)")
        print(f"   Демо счёт: {client.is_demo()}")
        
        # Получаем баланс
        print(f"\n💰 БАЛАНС:")
        balance = await client.balance()
        print(f"   Баланс: ${balance}")
        
        # Получаем активные активы
        print(f"\n📊 АКТИВНЫЕ АКТИВЫ:")
        assets = await client.active_assets()
        
        # active_assets() возвращает список ID активов (строки)
        if assets and isinstance(assets, list):
            otc_assets = [a for a in assets if isinstance(a, str) and 'otc' in a.lower()]
            print(f"   Всего активов: {len(assets)}")
            print(f"   OTC активов: {len(otc_assets)}")
            print(f"   Примеры: {assets[:5] if len(assets) > 5 else assets}")
        else:
            print(f"   ℹ️ Активы не получены или формат: {type(assets)}")
        
        # Тестируем на EURUSD_otc
        symbol = "EURUSD_otc"
        print(f"\n{'=' * 80}")
        print(f"📈 ТЕСТИРОВАНИЕ НА {symbol}")
        print(f"{'=' * 80}")
        
        # ==========================================================================
        # МЕТОД 1: get_candles()
        # ==========================================================================
        print(f"\n📊 МЕТОД 1: get_candles()")
        print(f"   Описание: Получение исторических свечей")
        print(f"   URL: wss://ws.po.market/socket.io/?EIO=4&transport=websocket")
        
        start_time = time.time()
        try:
            candles = await asyncio.wait_for(
                client.get_candles(symbol, period=60, offset=0),
                timeout=15
            )
            elapsed = time.time() - start_time
            
            if candles:
                print(f"   ✅ УСПЕХ: получено {len(candles)} свечей за {elapsed:.2f} сек")
                
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
                
                # Текущая цена из последней свечи
                current_price = float(candles[-1].get('close', 0))
                print(f"\n   💹 ТЕКУЩАЯ ЦЕНА: ${current_price:.5f}")
            else:
                print(f"   ⚠️ ПУСТО: свечи не получены")
                
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            print(f"   ⏳ ТАЙМАУТ: {elapsed:.2f} сек (превышено 15 сек)")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        # ==========================================================================
        # МЕТОД 2: subscribe_symbol() + получение последних данных
        # ==========================================================================
        print(f"\n📊 МЕТОД 2: subscribe_symbol()")
        print(f"   Описание: Подписка на поток свечей в реальном времени")
        print(f"   URL: wss://ws.po.market/socket.io/?EIO=4&transport=websocket")
        
        start_time = time.time()
        try:
            print(f"   ⏳ Подписка на {symbol}...")
            candles_stream = await client.subscribe_symbol(symbol)
            
            print(f"   ✅ Подписка успешна, ожидание свечей...")
            
            candles_received = []
            async with asyncio.timeout(10):
                async for candle in candles_stream:
                    period = candle.get('period', 0)
                    # Фильтруем только свечи с нужным периодом
                    if period == 60:
                        candles_received.append(candle)
                        ts = candle.get('timestamp', 0)
                        dt = datetime.fromtimestamp(ts)
                        close = float(candle.get('close', 0))
                        print(f"      [{len(candles_received)}] {dt.strftime('%H:%M:%S')} | Close={close:.5f}")
                        
                        if len(candles_received) >= 3:
                            break
            
            elapsed = time.time() - start_time
            
            if candles_received:
                print(f"   ✅ УСПЕХ: получено {len(candles_received)} свечей за {elapsed:.2f} сек")
                current_price = float(candles_received[-1].get('close', 0))
                print(f"   💹 ТЕКУЩАЯ ЦЕНА: ${current_price:.5f}")
            else:
                print(f"   ⚠️ ПУСТО: свечи не получены")
                
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            print(f"   ⏳ ТАЙМАУТ: {elapsed:.2f} сек (превышено 10 сек)")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        # ==========================================================================
        # МЕТОД 3: opened_deals() + анализ цены
        # ==========================================================================
        print(f"\n📊 МЕТОД 3: opened_deals()")
        print(f"   Описание: Получение открытых сделок с данными о цене")
        print(f"   URL: wss://ws.po.market/socket.io/?EIO=4&transport=websocket")
        
        start_time = time.time()
        try:
            opened = await client.opened_deals()
            elapsed = time.time() - start_time
            
            print(f"   Тип данных: {type(opened)}")
            
            if opened:
                if isinstance(opened, dict):
                    print(f"   ✅ УСПЕХ: {len(opened)} открытых сделок за {elapsed:.2f} сек")
                    
                    # Ищем сделки по нашему активу
                    for trade_id, deal in opened.items():
                        if deal.get('asset') == symbol:
                            open_price = float(deal.get('openPrice', 0))
                            close_price = deal.get('closePrice', 'N/A')
                            command = 'CALL' if deal.get('command') == 0 else 'PUT'
                            print(f"\n   Сделка {trade_id[:8]}...:")
                            print(f"     Направление: {command}")
                            print(f"     Цена открытия: {open_price:.5f}")
                            print(f"     Цена закрытия: {close_price}")
                else:
                    print(f"   ✅ УСПЕХ: данные получены за {elapsed:.2f} сек")
            else:
                print(f"   ℹ️ НЕТ ОТКРЫТЫХ СДЕЛОК")
                
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        # ==========================================================================
        # МЕТОД 4: get_server_time() + расчёт
        # ==========================================================================
        print(f"\n📊 МЕТОД 4: get_server_time()")
        print(f"   Описание: Получение времени сервера для синхронизации")
        
        start_time = time.time()
        try:
            server_time = await client.get_server_time()
            elapsed = time.time() - start_time
            
            print(f"   ✅ УСПЕХ: время сервера получено за {elapsed:.2f} сек")
            print(f"   Время сервера: {server_time}")
            print(f"   Локальное время: {int(time.time() * 1000)}")
            
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        # ==========================================================================
        # СРАВНЕНИЕ МЕТОДОВ
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("📊 СРАВНЕНИЕ МЕТОДОВ")
        print(f"{'=' * 80}")
        print("""
┌─────────────────────┬──────────────┬─────────────┬──────────────┬─────────────┐
│ Метод               │ Скорость     │ Точность    │ Реальное время│ Надёжность  │
├─────────────────────┼──────────────┼─────────────┼──────────────┼─────────────┤
│ get_candles()       │ 5-15 сек     │ Высокая     │ Нет          │ Средняя     │
│ subscribe_symbol()  │ 1-3 сек      │ Высокая     │ Да           │ Высокая     │
│ opened_deals()      │ 1-2 сек      │ Средняя     │ Частично     │ Высокая     │
│ get_server_time()   │ <1 сек       │ Низкая      │ Нет          │ Высокая     │
└─────────────────────┴──────────────┴─────────────┴──────────────┴─────────────┘

РЕКОМЕНДАЦИЯ:
  • Для получения исторических данных: get_candles()
  • Для реального времени: subscribe_symbol()
  • Для проверки сделок: opened_deals()
  • Для синхронизации: get_server_time()
""")
        
        # ==========================================================================
        # URL ПОДКЛЮЧЕНИЯ
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("🌐 URL ПОДКЛЮЧЕНИЯ")
        print(f"{'=' * 80}")
        print("""
BinaryOptionsToolsV2 использует следующие URL:

1. WebSocket (основной):
   wss://ws.po.market/socket.io/?EIO=4&transport=websocket

2. Альтернативные серверы:
   wss://po.market/socket.io/
   wss://pocketoption.expert/socket.io/

3. API сервер:
   https://pocketoption.expert/api

4. Платформа:
   https://po.market/

Примечание: BinaryOptionsToolsV2 автоматически выбирает доступный сервер.
""")


async def main():
    """Запуск теста."""
    try:
        await test_all_methods()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
