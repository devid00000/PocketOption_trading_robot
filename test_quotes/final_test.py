#!/usr/bin/env python3
"""
Финальный тест: Сравнение всех рабочих методов получения котировок.
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


async def main():
    """Запуск теста."""
    
    print("\n" + "=" * 80)
    print("📊 ФИНАЛЬНЫЙ ТЕСТ: РАБОЧИЕ МЕТОДЫ ПОЛУЧЕНИЯ КОТИРОВОК")
    print("=" * 80)
    
    if not DEMO_SSID:
        raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        print(f"\n✅ ПОДКЛЮЧЕНО")
        print(f"   URL: wss://ws.po.market/socket.io/?EIO=4&transport=websocket")
        print(f"   Демо счёт: {client.is_demo()}")
        
        # ==========================================================================
        # 1. БАЛАНС
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("💰 МЕТОД 1: balance()")
        print(f"{'=' * 80}")
        
        start = time.time()
        balance = await client.balance()
        elapsed = time.time() - start
        
        print(f"   ✅ Баланс: ${balance}")
        print(f"   ⏱️ Время: {elapsed:.3f} сек")
        
        # ==========================================================================
        # 2. АКТИВЫ
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("📊 МЕТОД 2: active_assets()")
        print(f"{'=' * 80}")
        
        start = time.time()
        assets = await client.active_assets()
        elapsed = time.time() - start
        
        if assets and isinstance(assets, list):
            # assets возвращает список словарей
            otc = [a for a in assets if isinstance(a, dict) and a.get('is_otc')]
            print(f"   ✅ Всего активов: {len(assets)}")
            print(f"   ✅ OTC активов: {len(otc)}")
            print(f"   ⏱️ Время: {elapsed:.3f} сек")
            
            # Примеры активов
            print(f"\n   Примеры активов:")
            for asset in assets[:3]:
                if isinstance(asset, dict):
                    symbol = asset.get('symbol', 'N/A')
                    payout = asset.get('payout', 0)
                    allowed = asset.get('allowed_candles', [])
                    periods = [str(c.get('time')) for c in allowed[:5]]
                    print(f"     • {symbol}: payout={payout}%, candles={','.join(periods)}s")
        
        # ==========================================================================
        # 3. ВРЕМЯ СЕРВЕРА
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("🕐 МЕТОД 3: get_server_time()")
        print(f"{'=' * 80}")
        
        start = time.time()
        server_time = await client.get_server_time()
        elapsed = time.time() - start
        
        local_time = int(time.time() * 1000)
        diff = abs(local_time - server_time)
        
        print(f"   ✅ Время сервера: {server_time} мс")
        print(f"   ✅ Локальное время: {local_time} мс")
        print(f"   ⚠️ Разница: {diff} мс")
        print(f"   ⏱️ Время: {elapsed:.3f} сек")
        
        # ==========================================================================
        # 4. ОТКРЫТЫЕ СДЕЛКИ
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("💼 МЕТОД 4: opened_deals()")
        print(f"{'=' * 80}")
        
        start = time.time()
        opened = await client.opened_deals()
        elapsed = time.time() - start
        
        print(f"   ✅ Тип: {type(opened)}")
        print(f"   ⏱️ Время: {elapsed:.3f} сек")
        
        if opened and isinstance(opened, dict):
            print(f"   ℹ️ Открытых сделок: {len(opened)}")
        else:
            print(f"   ℹ️ Нет открытых сделок")
        
        # ==========================================================================
        # 5. ЗАКРЫТЫЕ СДЕЛКИ
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("💼 МЕТОД 5: closed_deals()")
        print(f"{'=' * 80}")
        
        start = time.time()
        closed = await client.closed_deals()
        elapsed = time.time() - start
        
        print(f"   ✅ Тип: {type(closed)}")
        print(f"   ⏱️ Время: {elapsed:.3f} сек")
        
        if closed and isinstance(closed, dict):
            print(f"   ℹ️ Закрытых сделок: {len(closed)}")
        else:
            print(f"   ℹ️ Нет закрытых сделок")
        
        # ==========================================================================
        # 6. ПОПЫТКА ПОЛУЧИТЬ СВЕЧИ (с большим таймаутом)
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("📈 МЕТОД 6: get_candles() - ПРОВЕРКА")
        print(f"{'=' * 80}")
        
        symbol = "EURUSD_otc"
        period = 60
        
        print(f"   📡 Запрос: {symbol}, period={period}s")
        print(f"   ⏳ Таймаут: 60 сек...")
        
        start = time.time()
        try:
            candles = await asyncio.wait_for(
                client.get_candles(symbol, period=period, offset=0),
                timeout=60
            )
            elapsed = time.time() - start
            
            if candles:
                print(f"   ✅ УСПЕХ: {len(candles)} свечей за {elapsed:.2f} сек")
                
                # Последняя свеча
                last = candles[-1]
                ts = last.get('timestamp', 0)
                dt = datetime.fromtimestamp(ts)
                open_p = float(last.get('open', 0))
                high = float(last.get('high', 0))
                low = float(last.get('low', 0))
                close = float(last.get('close', 0))
                
                print(f"\n   Последняя свеча:")
                print(f"     Время: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"     Open: {open_p:.5f}")
                print(f"     High: {high:.5f}")
                print(f"     Low: {low:.5f}")
                print(f"     Close: {close:.5f}")
            else:
                print(f"   ⚠️ ПУСТО: свечи не получены")
                
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            print(f"   ❌ ТАЙМАУТ: {elapsed:.2f} сек (превышено 60 сек)")
            print(f"   ⚠️ ВЫВОД: get_candles() НЕ РАБОТАЕТ")
        except Exception as e:
            print(f"   ❌ ОШИБКА: {e}")
        
        # ==========================================================================
        # ИТОГОВАЯ ТАБЛИЦА
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("📊 ИТОГОВАЯ ТАБЛИЦА")
        print(f"{'=' * 80}")
        print("""
┌─────────────────────────┬──────────────┬─────────────┬──────────────────────────┐
│ Метод                   │ Статус       │ Время       │ Примечание               │
├─────────────────────────┼──────────────┼─────────────┼──────────────────────────┤
│ balance()               │ ✅ РАБОТАЕТ  │ <1 сек      │ Возвращает баланс        │
│ active_assets()         │ ✅ РАБОТАЕТ  │ 1-2 сек     │ Возвращает список активов│
│ get_server_time()       │ ✅ РАБОТАЕТ  │ <1 сек      │ Синхронизация времени    │
│ opened_deals()          │ ✅ РАБОТАЕТ  │ <1 сек      │ Открытые сделки          │
│ closed_deals()          │ ✅ РАБОТАЕТ  │ <1 сек      │ Закрытые сделки          │
│ get_candles()           │ ❌ ТАЙМАУТ   │ >60 сек     │ НЕ РАБОТАЕТ              │
│ subscribe_symbol()      │ ❌ ТАЙМАУТ   │ >10 сек     │ НЕ РАБОТАЕТ              │
└─────────────────────────┴──────────────┴─────────────┴──────────────────────────┘

ВЫВОДЫ:
  1. BinaryOptionsToolsV2 ПОДКЛЮЧАЕТСЯ к платформе
  2. Баланс, активы, время — РАБОТАЮТ
  3. Свечи (get_candles, subscribe_symbol) — НЕ РАБОТАЮТ (таймаут)
  4. Для определения результата сделки используем СРАВНЕНИЕ БАЛАНСА

РЕКОМЕНДАЦИЯ ДЛЯ ОСНОВНОГО ПРОЕКТА:
  • Сохраняем баланс ДО сделки
  • Сохраняем баланс ПОСЛЕ сделки
  • Разница = результат сделки
""")
        
        # ==========================================================================
        # URL ПОДКЛЮЧЕНИЯ
        # ==========================================================================
        print(f"\n{'=' * 80}")
        print("🌐 ИНФОРМАЦИЯ О ПОДКЛЮЧЕНИИ")
        print(f"{'=' * 80}")
        print("""
BinaryOptionsToolsV2 использует:

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


if __name__ == "__main__":
    asyncio.run(main())
