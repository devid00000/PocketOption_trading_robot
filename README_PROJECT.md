# 🚀 Pocket Option Robot

**Проект терминала автоматической торговли для Pocket Option (в активной разработке)**

---

## ✅ Реализовано / проверено

| Компонент | Статус | Описание |
|-----------|--------|----------|
| 📈 **Торговые стратегии** | ✅ | RSI, Bollinger Bands, MACD, Stochastic, CCI, SuperTrend |
| 💼 **Тест торговли** | ⚠️ | CLI-команда оставлена как заглушка до подключения торгового runtime |
| 🖥️ **GUI интерфейс** | ✅ | PySide6 приложение |
| 📊 **История сделок** | ⚠️ | SQLite и базовый экспорт есть, интеграция с движком не завершена |
| 🎯 **Конструктор стратегий** | ⚠️ | JSON-конфигурации и редакторы есть, runtime запуска роботов не завершён |

---

## 🚀 Быстрый старт

### 1. Инициализация

```bash
python main.py init
```

### 2. Проверка подключения

```bash
python main.py check
```

### 3. Запуск

```bash
# GUI интерфейс
python main.py gui

# Торговый бот
python main.py trade --strategy rsi
```

---

## 📋 Команды

```bash
# Инициализация
python main.py init

# GUI
python main.py gui
python main.py gui --real          # Реальный счёт

# Торговля
python main.py trade --strategy rsi
python main.py trade --strategy macd --symbol GBPUSD_otc --amount 2.0
python main.py trade --strategy multi --max-trades 20

# Статистика
python main.py stats --today
python main.py stats --days 30

# Стратегии
python main.py strategies --list
python main.py strategies --create rsi
python main.py strategies --defaults

# Проверка
python main.py check
python main.py check --real
```

---

## 📈 Стратегии

### 1. Simple Test
- Тестовая стратегия (всегда CALL)
- Для проверки механики

### 2. RSI Classic
- RSI < 30 → CALL
- RSI > 70 → PUT

### 3. BB Rebound
- Цена у нижней полосы → CALL
- Цена у верхней полосы → PUT

### 4. MACD Classic
- Пересечение линий MACD

### 5. Multi Indicator
- RSI + BB + MACD вместе
- Требуется согласие 2+ индикаторов

---

## 🖥️ GUI Интерфейс

![GUI](gui_screenshot.png)

**Реализовано в текущем checkpoint:**
- Подключение/отключение
- Автоматический перехват auth SSID через Playwright
- Подключение через `BinaryOptionsToolsV2` на demo
- Автоматический перехват auth SSID через Playwright
- Обновление баланса через polling
- Экспериментальный DebugChartWindow
- Выбор стратегии
- История сделок
- Статистика
- Логи

---

## 📊 Статистика

```bash
$ python main.py stats --today

📊 СТАТИСТИКА ЗА СЕГОДНЯ:
   Сделок: 15
   Побед: 9
   Поражений: 6
   Win Rate: 60.0%
   Прибыль: $7.65
```

---

## 🎯 Примеры

### Торговля с RSI

```bash
python main.py trade --strategy rsi \
    --symbol EURUSD_otc \
    --amount 1.0 \
    --duration 60 \
    --max-trades 10 \
    --stop-loss 5.0 \
    --take-profit 10.0
```

### Создание стратегии

```python
from strategies.manager import StrategyManager

manager = StrategyManager()

# Создать RSI стратегию
strategy = manager.create_strategy(
    "RSIStrategy",
    name="My RSI",
    config={
        "period": 14,
        "overbought": 75,
        "oversold": 25
    }
)

# Сохранить
manager.save_strategy(strategy)
```

### JSON стратегия

```json
{
  "name": "Super Strategy",
  "type": "CombinedStrategy",
  "min_agreement": 2,
  "strategies": [
    {
      "type": "RSIStrategy",
      "config": {"period": 14, "overbought": 70, "oversold": 30}
    },
    {
      "type": "MACDStrategy",
      "config": {"fast_period": 12, "slow_period": 26}
    }
  ]
}
```

---

## 📁 Структура

```
pocket_option_robot/
├── main.py                    # Главная точка входа
├── roadmap.md                  # Аудит и дорожная карта
├── test_robot_engine.py       # Тест Robot Engine
│
├── core/                      # Ядро
│   ├── robot_engine.py        # Robot Engine
│   └── market_data.py         # Модели данных
│
├── strategies/                # Стратегии
│   ├── indicators.py          # Индикаторы
│   ├── strategies.py          # Стратегии
│   ├── base.py                # Базовый класс
│   └── manager.py             # Менеджер
│
├── storage/                   # Хранилище
│   └── trade_logger.py        # SQLite логгер
│
└── ui/                        # Интерфейс
    └── app.py                 # PySide6 GUI
```

---

## 🔧 Установка

### Зависимости

```bash
pip install -r requirements.txt

# Если используется автоматический перехват SSID
playwright install chromium
```

### Основные пакеты

```txt
BinaryOptionsToolsV2    # WebSocket API
PySide6                 # GUI
pandas-ta               # Индикаторы
sqlalchemy              # База данных
```

---

## ⚠️ Предупреждения

1. **Торговля связана с риском потери средств**
2. **Тестируйте на демо-счёте**
3. **Не используйте деньги, которые не готовы потерять**
4. **Мартингейл опасен для депозита**

---

## 📞 Поддержка

### Логи

- GUI: Вкладка "Логи"
- CLI: Консоль
- Файлы: `storage/logs/`

### Частые проблемы

| Проблема | Решение |
|----------|---------|
| Не подключается | Проверьте SSID |
| Нет свечей | Смените актив |
| Ошибка торговли | Проверьте баланс |

## Checkpoint: 2026-09-06

Текущая точка остановки описана подробно в [`roadmap.md`](roadmap.md).

Работает и проверено на demo:

- подключение по полному Socket.IO SSID с обязательными `session`, `uid` и `isDemo`;
- автоматический перехват auth SSID через Playwright;
- корректное отключение Qt worker без ошибки `Event loop stopped before Future completed`;
- обновление demo-баланса;
- получение списка активов через `active_assets()`;
- загрузка до 50 исторических OHLC-свечей через `compile_candles()`;
- локальное создание UI и индикаторов.

Текущая проблема:

- график в `DebugChartWindow` визуально не совпадает с графиком Pocket Option по цветам, размерам и иногда по ценам;
- разные методы `BinaryOptionsToolsV2` (`compile_candles`, `get_ticks`, `subscribe_symbol`, `subscribe_symbol_timed`, `subscribe_symbol_time_aligned`) в текущей версии могут отдавать несовместимые ценовые серии;
- `get_candles_live()` в установленной версии `0.2.14` падает внутри библиотеки при обработке `None`;
- поэтому следующий шаг: оставить браузер после перехвата SSID открытым и исследовать WebSocket/внутренний источник котировок самой платформы, либо написать отдельный проверяемый адаптер единого источника OHLC.

Важно: текущий DebugChartWindow является исследовательским прототипом. Автоматическую торговлю и real-сделки до завершения проверки источника котировок не включать.

---

## 📚 Документация

- [Полная документация](FULL_IMPLEMENTATION.md)
- [Стратегии](strategies/README.md)
- [API Reference](docs/API.md)

---

**Статус:** базовый каркас и локальные компоненты проверены; сетевые функции требуют demo-приёмки.

**Для начала:**
```bash
python main.py init
python main.py gui
```
