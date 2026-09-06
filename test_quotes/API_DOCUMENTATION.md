# 📚 Pocket Option API — Полная документация

## 🔑 SSID — Структура и назначение

### Что такое SSID?

SSID (Session ID) — это **не просто набор цифр**, а **полноценный WebSocket запрос** в формате Socket.IO для авторизации на платформе Pocket Option.

### Структура SSID

```python
SSID = '42["auth",{"session":"YOUR_SESSION","isDemo":1,"uid":YOUR_UID,"platform":3}]'
```

### Разбор по частям:

| Часть | Значение | Описание |
|-------|----------|----------|
| `42` | Тип сообщения | Socket.IO: 4=событие, 2=ACK |
| `["auth", {...}]` | JSON payload | Команда авторизации |
| `session` | Строка | Уникальный идентификатор сессии |
| `isDemo` | 0 или 1 | Тип счёта (0=реал, 1=демо) |
| `uid` | Число | ID пользователя |
| `platform` | 3 | Тип платформы (3=веб) |
| `isFastHistory` | true | Быстрая история |
| `isOptimized` | true | Оптимизированный режим |

### Как получить SSID?

#### Способ 1: Через браузер (Chrome DevTools)

```python
# 1. Откройте https://po.market/
# 2. Нажмите F12 → Network → WS (WebSocket)
# 3. Найдите сообщение с "auth"
# 4. Скопируйте payload
```

#### Способ 2: Через cookie

```python
import requests

session = requests.Session()
session.get('https://po.market/')

# Получаем cookie
cookie = session.cookies.get('session')
print(f"Session cookie: {cookie}")

# Формируем SSID
ssid = f'42["auth",{{"session":"{cookie}","isDemo":1,"uid":YOUR_UID,"platform":3}}]'
```

#### Способ 3: Готовый скрипт

```python
# get_session_cookie.py
from utils.logger import Logger

logger = Logger("SSID")

# Пример демо SSID
DEMO_SSID = '42["auth",{"session":"YOUR_DEMO_SESSION","isDemo":1,"uid":YOUR_UID,"platform":3}]'

# Пример реал SSID (замените на свой)
REAL_SSID = '42["auth",{"session":"YOUR_REAL_SESSION","isDemo":0,"uid":YOUR_UID,"platform":3,"isFastHistory":true,"isOptimized":true}]'
```

---

## 💹 Получение цены в реальном времени

### Метод 1: subscribe_symbol_timed() ✅ РЕКОМЕНДУЕМЫЙ

**Описание:** Подписка на поток свечей в реальном времени.

**Преимущества:**
- ✅ Работает в реальном времени
- ✅ Автоматическое обновление
- ✅ Минимальная задержка

**Пример кода:**

```python
import asyncio
from datetime import timedelta
from BinaryOptionsToolsV2 import PocketOptionAsync

SSID = '42["auth",{"session":"YOUR_DEMO_SESSION","isDemo":1,"uid":YOUR_UID,"platform":3}]'

async def get_realtime_price():
    async with PocketOptionAsync(ssid=SSID) as client:
        # Подписка на свечи каждые 5 секунд
        stream = await client.subscribe_symbol_timed(
            "EURUSD_otc",
            timedelta(seconds=5)
        )
        
        # Получаем свечи в реальном времени
        async for candle in stream:
            current_price = candle['close']
            timestamp = candle['timestamp']
            
            print(f"Цена: {current_price:.5f} | Время: {timestamp}")

asyncio.run(get_realtime_price())
```

**Формат свечи:**

```python
{
    'timestamp': 1774645090,      # Unix timestamp (секунды)
    'open': 1.15675,              # Цена открытия
    'high': 1.15675,              # Максимум
    'low': 1.15664,               # Минимум
    'close': 1.15665,             # Цена закрытия (текущая)
    'volume': None,               # Объём (обычно None)
    'period': 0                   # Период (0 = агрегировано)
}
```

---

### Метод 2: get_candles() ❌ НЕ РАБОТАЕТ

**Описание:** Получение исторических свечей.

**Статус:** ❌ ТАЙМАУТ (>60 сек)

```python
# НЕ РАБОТАЕТ!
candles = await client.get_candles("EURUSD_otc", period=60, offset=0)
```

---

### Метод 3: balance() ✅ ДЛЯ РЕЗУЛЬТАТА СДЕЛКИ

**Описание:** Получение баланса счёта.

**Пример:**

```python
balance = await client.balance()
print(f"Баланс: ${balance}")
```

---

## 📊 Получение истории цен

### Проблема

BinaryOptionsToolsV2 **НЕ ВОЗВРАЩАЕТ** исторические свечи через `get_candles()` (таймаут).

### Решение 1: Сохранение из realtime потока

```python
import asyncio
from datetime import timedelta
from BinaryOptionsToolsV2 import PocketOptionAsync

class CandleHistory:
    def __init__(self):
        self.candles = []
        self.max_candles = 1000
    
    async def start(self):
        async with PocketOptionAsync(ssid=SSID) as client:
            stream = await client.subscribe_symbol_timed(
                "EURUSD_otc",
                timedelta(seconds=5)
            )
            
            async for candle in stream:
                self.candles.append(candle)
                
                # Храним только последние N свечей
                if len(self.candles) > self.max_candles:
                    self.candles = self.candles[-self.max_candles:]
                
                print(f"Получено свечей: {len(self.candles)}")
    
    def get_history(self, count=100):
        """Получить последние N свечей"""
        return self.candles[-count:]

# Использование
history = CandleHistory()
asyncio.run(history.start())
```

### Решение 2: Сравнение баланса для результата сделки

```python
async def get_trade_result(client, trade_id, duration=15):
    """Определение результата сделки через баланс"""
    
    # Баланс ДО
    balance_before = await client.balance()
    
    # Ждём окончания сделки
    await asyncio.sleep(duration + 2)
    
    # Баланс ПОСЛЕ
    balance_after = await client.balance()
    
    # Результат
    profit = balance_after - balance_before
    
    return {
        'trade_id': trade_id,
        'profit': profit,
        'balance_before': balance_before,
        'balance_after': balance_after
    }
```

---

## 🎯 ПОЛНЫЙ ПРИМЕР: Торговля с получением цены

```python
import asyncio
from datetime import timedelta
from BinaryOptionsToolsV2 import PocketOptionAsync

SSID = '42["auth",{"session":"YOUR_DEMO_SESSION","isDemo":1,"uid":YOUR_UID,"platform":3}]'

async def trade_with_realtime_price():
    async with PocketOptionAsync(ssid=SSID) as client:
        print(f"💰 Баланс: ${await client.balance()}")
        
        # Подписка на цену в реальном времени
        stream = await client.subscribe_symbol_timed(
            "EURUSD_otc",
            timedelta(seconds=5)
        )
        
        # Переменные для анализа
        prices = []
        
        async for candle in stream:
            current_price = candle['close']
            prices.append(current_price)
            
            # Оставляем последние 10 цен
            if len(prices) > 10:
                prices = prices[-10:]
            
            # Простой анализ: растёт цена или падает
            if len(prices) >= 3:
                if prices[-1] > prices[-3]:
                    direction = "CALL"
                elif prices[-1] < prices[-3]:
                    direction = "PUT"
                else:
                    direction = "HOLD"
                
                print(f"Цена: {current_price:.5f} | Сигнал: {direction}")
                
                # Пример торговли
                if direction == "CALL" and len(prices) == 10:
                    print(f"📈 Открытие CALL...")
                    
                    # Баланс ДО
                    balance_before = await client.balance()
                    
                    # Сделка
                    trade_id, _ = await client.buy("EURUSD_otc", 1.0, 15, "call")
                    print(f"Сделка открыта: {trade_id}")
                    
                    # Ждём окончания
                    await asyncio.sleep(17)
                    
                    # Баланс ПОСЛЕ
                    balance_after = await client.balance()
                    
                    # Результат
                    profit = balance_after - balance_before
                    print(f"Результат: ${profit:+.2f}")
                    
                    # Сбрасываем цены
                    prices = []

asyncio.run(trade_with_realtime_price())
```

---

## 📋 СВОДНАЯ ТАБЛИЦА МЕТОДОВ

| Метод | Назначение | Статус | Пример |
|-------|------------|--------|--------|
| `subscribe_symbol_timed()` | Цена в реальном времени | ✅ РАБОТАЕТ | `await client.subscribe_symbol_timed("EURUSD_otc", timedelta(seconds=5))` |
| `balance()` | Баланс счёта | ✅ РАБОТАЕТ | `await client.balance()` |
| `active_assets()` | Список активов | ✅ РАБОТАЕТ | `await client.active_assets()` |
| `opened_deals()` | Открытые сделки | ✅ РАБОТАЕТ | `await client.opened_deals()` |
| `closed_deals()` | Закрытые сделки | ✅ РАБОТАЕТ | `await client.closed_deals()` |
| `get_candles()` | Исторические свечи | ❌ ТАЙМАУТ | Не использовать |
| `subscribe_symbol()` | Подписка на свечи | ❌ ТАЙМАУТ | Не использовать |

---

## 🔗 ПОЛЕЗНЫЕ ССЫЛКИ

- [BinaryOptionsToolsV2 GitHub](https://github.com/ChipaDevTeam/BinaryOptionsTools-v2)
- [Пример subscribe_symbol_timed](https://github.com/ChipaDevTeam/BinaryOptionsTools-v2/blob/master/examples/python/async/subscribe_symbol_timed.py)
- [PocketOption API Docs](https://lu-yi-hsun.github.io/pocketoptionapi/)

---

## 📝 ПРИМЕЧАНИЯ

1. **SSID нужно обновлять** при истечении сессии (обычно 24 часа)
2. **subscribe_symbol_timed()** требует постоянного подключения
3. **balance()** может задерживаться на 1-2 секунды
4. **Для торговли** используйте демо-счёт для тестирования

---

**Документ обновлён:** 2026-03-27  
**Версия:** 1.0  
**Статус:** ✅ Актуально
