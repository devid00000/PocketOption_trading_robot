# 📊 Pocket Option Quotes Viewer

Тестовый проект для получения котировок Pocket Option через BinaryOptionsToolsV2 и отображения их на графике.

## 🚀 Установка

```bash
# Установите зависимости
pip install -r requirements.txt

# Установите BinaryOptionsToolsV2 (если ещё не установлена)
pip install "https://github.com/ChipaDevTeam/BinaryOptionsTools-v2/releases/download/v0.2.9/binaryoptionstoolsv2-0.2.9-cp39-abi3-manylinux_2_28_x86_64.whl"
```

## 📋 Возможности

- ✅ Подключение к Pocket Option через BinaryOptionsToolsV2
- ✅ Получение исторических свечей через `get_candles()`
- ✅ Отображение японских свечей на графике (PyQtGraph)
- ✅ Обновление цены в реальном времени (каждую секунду)
- ✅ Обновление свечей каждые 5 секунд
- ✅ Выбор актива (EURUSD_otc, BTCUSD_otc, и др.)
- ✅ Выбор периода свечей (5 сек - 1 час)

## 🎯 Запуск

```bash
python quotes_viewer.py
```

## 📊 Способы получения котировок

### 1. Исторические данные (get_candles)

```python
candles = await client.get_candles("EURUSD_otc", period=60, offset=0)
for candle in candles:
    print(f"Timestamp: {candle['timestamp']}")
    print(f"Open: {candle['open']}, High: {candle['high']}")
    print(f"Low: {candle['low']}, Close: {candle['close']}")
```

### 2. Подписка на свечи в реальном времени (subscribe_symbol)

```python
candles_stream = await client.subscribe_symbol("EURUSD_otc")
async for candle in candles_stream:
    print(f"Новая свеча: {candle}")
```

### 3. Получение последней цены

```python
# Из последней свечи
candles = await client.get_candles("EURUSD_otc", period=60, offset=0)
if candles:
    last_close = candles[-1]['close']
    print(f"Текущая цена: {last_close}")
```

## 🔍 BinaryOptionsToolsV2 API

### Основные методы:

| Метод | Описание |
|-------|----------|
| `get_candles(asset, period, offset)` | Получить свечи |
| `subscribe_symbol(asset)` | Подписаться на поток свечей |
| `balance()` | Получить баланс |
| `buy(asset, amount, duration)` | Открыть сделку CALL |
| `sell(asset, amount, duration)` | Открыть сделку PUT |
| `check_win(trade_id)` | Проверить результат сделки |
| `closed_deals()` | Получить закрытые сделки |
| `opened_deals()` | Получить открытые сделки |

## 📝 Примечания

- **period**: Период свечи в секундах (60 = 1 мин, 300 = 5 мин)
- **offset**: Смещение в секундах (0 = текущие свечи)
- **asset**: ID актива (EURUSD_otc, BTCUSD_otc, и др.)

## 🐛 Известные проблемы

1. `get_candles()` может таймаутить при плохом соединении
2. `subscribe_symbol()` требует правильной подписки через `subscribe()`
3. `closePrice` в `opened_deals()` всегда возвращает 0

## 📚 Источники

- [BinaryOptionsToolsV2 Documentation](https://github.com/ChipaDevTeam/BinaryOptionsTools-v2)
- [PocketOption API](https://lu-yi-hsun.github.io/pocketoptionapi/)
- [Pocket Option Trading Bot](https://github.com/VitalySvyatyuk/pocket_option_trading_bot)
