#!/usr/bin/env python3
"""
Тест получения котировок через BinaryOptionsToolsV2.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from BinaryOptionsToolsV2 import PocketOptionAsync
except ImportError:
    print("❌ BinaryOptionsToolsV2 не установлена!")
    sys.exit(1)


from config.runtime import load_runtime_config

DEMO_SSID = load_runtime_config().demo_ssid


async def test_get_candles():
    """Тест получения свечей через get_candles()."""
    print("=" * 70)
    print("Тест 1: get_candles()")
    print("=" * 70)
    
    if not DEMO_SSID:
        raise RuntimeError("POCKET_OPTION_DEMO_SSID не задан в .env")
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        print("\n✅ Подключено")
        
        # Получаем свечи
        print("\n📡 Запрос свечей EURUSD_otc (60s)...")
        candles = await client.get_candles("EURUSD_otc", period=60, offset=0)
        
        if candles:
            print(f"✅ Получено {len(candles)} свечей")
            print("\nПоследние 5 свечей:")
            for candle in candles[-5:]:
                timestamp = candle.get("timestamp", 0)
                open_p = float(candle.get("open", 0))
                high = float(candle.get("high", 0))
                low = float(candle.get("low", 0))
                close = float(candle.get("close", 0))
                print(f"  {timestamp}: O={open_p:.5f}, H={high:.5f}, L={low:.5f}, C={close:.5f}")
        else:
            print("❌ Свечи не получены")


async def test_subscribe_symbol():
    """Тест подписки на свечи через subscribe_symbol()."""
    print("\n" + "=" * 70)
    print("Тест 2: subscribe_symbol()")
    print("=" * 70)
    
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        print("\n✅ Подключено")
        
        # Подписываемся на свечи
        print("\n📡 Подписка на EURUSD_otc...")
        candles_stream = await client.subscribe_symbol("EURUSD_otc")
        
        print("⏳ Ожидание свечей (10 секунд)...")
        
        count = 0
        try:
            async for candle in candles_stream:
                count += 1
                timestamp = candle.get("timestamp", 0)
                open_p = float(candle.get("open", 0))
                high = float(candle.get("high", 0))
                low = float(candle.get("low", 0))
                close = float(candle.get("close", 0))
                period = candle.get("period", 0)
                
                print(f"  [{count}] {timestamp}: O={open_p:.5f}, H={high:.5f}, L={low:.5f}, C={close:.5f}, period={period}s")
                
                if count >= 10:
                    break
                    
        except asyncio.TimeoutError:
            print("⏳ Таймаут")
        
        print(f"\n✅ Получено {count} свечей")


async def test_opened_deals():
    """Тест получения открытых сделок через opened_deals()."""
    print("\n" + "=" * 70)
    print("Тест 3: opened_deals()")
    print("=" * 70)
    
    async with PocketOptionAsync(ssid=DEMO_SSID) as client:
        print("\n✅ Подключено")
        
        # Получаем открытые сделки
        print("\n📡 Запрос открытых сделок...")
        opened = await client.opened_deals()
        
        print(f"Тип: {type(opened)}")
        
        if opened:
            if isinstance(opened, dict):
                print(f"✅ Найдено {len(opened)} сделок")
                for trade_id, deal in opened.items():
                    print(f"\n  Сделка {trade_id[:8]}...:")
                    print(f"    Актив: {deal.get('asset', 'N/A')}")
                    print(f"    Направление: {'CALL' if deal.get('command') == 0 else 'PUT'}")
                    print(f"    Сумма: ${deal.get('amount', 0)}")
                    print(f"    Прибыль: {deal.get('profit', 0)}")
                    print(f"    percentProfit: {deal.get('percentProfit', 0)}")
                    print(f"    percentLoss: {deal.get('percentLoss', 0)}")
            elif isinstance(opened, list):
                print(f"✅ Найдено {len(opened)} сделок")
                for deal in opened:
                    print(f"  {deal}")
        else:
            print("ℹ️ Нет открытых сделок")


async def main():
    """Запуск тестов."""
    print("\n🧪 Тестирование BinaryOptionsToolsV2")
    print("=" * 70)
    
    try:
        # Тест 1: get_candles()
        await test_get_candles()
        
        # Тест 2: subscribe_symbol()
        # await test_subscribe_symbol()
        
        # Тест 3: opened_deals()
        # await test_opened_deals()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ Тесты завершены")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
