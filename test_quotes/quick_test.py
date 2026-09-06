#!/usr/bin/env python3
"""
Быстрый тест получения котировок.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from BinaryOptionsToolsV2 import PocketOptionAsync

from config.runtime import load_runtime_config

DEMO_SSID = load_runtime_config().demo_ssid


async def main():
    print("🚀 Быстрый тест BinaryOptionsToolsV2")
    print("=" * 70)
    
    try:
        if not DEMO_SSID:
            raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
        async with PocketOptionAsync(ssid=DEMO_SSID) as client:
            print("\n✅ Подключено")
            
            # Тест 1: Баланс
            print("\n💰 Баланс...")
            balance = await client.balance()
            print(f"   Баланс: ${balance}")
            
            # Тест 2: Активные активы
            print("\n📊 Активные активы...")
            assets = await client.active_assets()
            print(f"   Найдено активов: {len(assets) if assets else 0}")
            
            # Тест 3: Свечи с таймаутом
            print("\n📡 Запрос свечей EURUSD_otc (60s) с таймаутом 5 сек...")
            try:
                candles = await asyncio.wait_for(
                    client.get_candles("EURUSD_otc", period=60, offset=0),
                    timeout=5
                )
                print(f"   ✅ Получено {len(candles)} свечей")
                if candles:
                    last = candles[-1]
                    print(f"   Последняя: close={last.get('close', 0):.5f}")
            except asyncio.TimeoutError:
                print("   ⏳ Таймаут (5 сек)")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
            
            # Тест 4: Подписка на свечи
            print("\n📡 Подписка на EURUSD_otc с таймаутом 10 сек...")
            try:
                stream = await client.subscribe_symbol("EURUSD_otc")
                count = 0
                async with asyncio.timeout(10):
                    async for candle in stream:
                        count += 1
                        print(f"   [{count}] {candle.get('close', 0):.5f}")
                        if count >= 3:
                            break
                print(f"   ✅ Получено {count} свечей")
            except asyncio.TimeoutError:
                print("   ⏳ Таймаут (10 сек)")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ Тест завершён")


if __name__ == "__main__":
    asyncio.run(main())
