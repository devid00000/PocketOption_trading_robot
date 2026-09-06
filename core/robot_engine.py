"""
Robot Engine для Pocket Option.
Использует BinaryOptionsToolsV2 для работы с API.

Методы получения котировок:
- subscribe_symbol_timed() — свечи в реальном времени (✅ РАБОТАЕТ)
- balance() — баланс счёта (✅ РАБОТАЕТ)
- opened_deals()/closed_deals() — сделки (✅ РАБОТАЕТ)
"""

import asyncio
import json
import time
from typing import Optional, Callable, Dict, Any, List, Set
from datetime import datetime, timedelta
from collections import deque

try:
    from BinaryOptionsToolsV2 import PocketOptionAsync
except ImportError:
    print("❌ BinaryOptionsToolsV2 не установлена!")
    print("Установка: pip install \"https://github.com/ChipaDevTeam/BinaryOptionsTools-v2/releases/download/v0.2.9/binaryoptionstoolsv2-0.2.9-cp39-abi3-manylinux_2_28_x86_64.whl\"")
    raise

from .market_data import Candle, Tick, Balance, Subscription, Deal
from config.runtime import is_valid_ssid


class RobotEngine:
    """
    Движок для торговли на Pocket Option.

    Использует BinaryOptionsToolsV2 для подключения к Pocket Option.
    Получает котировки в реальном времени, управляет подписками и сделками.

    Attributes:
        ssid: SSID для авторизации
        candles: Хранилище свечей по активам
        ticks: Хранилище тиков по активам
        balance: Текущий баланс
        subscriptions: Активные подписки
    """

    def __init__(self, ssid: str):
        """
        Инициализация RobotEngine.

        Args:
            ssid: SSID для авторизации (формат: 42["auth",{...}])

        Example:
            >>> ssid = '42["auth",{"session":"abc123","isDemo":1,"uid":123456,"platform":3}]'
            >>> engine = RobotEngine(ssid=ssid)
        """
        self.ssid = ssid
        self.client: Optional[PocketOptionAsync] = None

        # Состояние
        self._running = False
        self._connected = False

        # Рыночные данные
        self._candles: Dict[str, Dict[int, deque]] = {}  # {symbol: {period: deque}}
        self._ticks: Dict[str, deque] = {}  # {symbol: deque}
        self._balance = Balance(is_demo=True)

        # Подписки
        self._subscriptions: Dict[str, Subscription] = {}  # key -> Subscription

        # Сделки
        self._trades: Dict[str, Deal] = {}  # trade_id -> Deal
        self._pending_checks: Set[str] = set()  # trade_id для проверки
        self._trade_balances: Dict[str, float] = {}  # trade_id -> balance_before

        # Callbacks
        self._on_candle: Optional[Callable] = None
        self._on_tick: Optional[Callable] = None
        self._on_balance: Optional[Callable] = None
        self._on_trade: Optional[Callable] = None
        self._on_connected: Optional[Callable] = None
        self._on_disconnected: Optional[Callable] = None

        # Задачи
        self._candle_tasks: Dict[str, asyncio.Task] = {}  # key -> task
        self._balance_task: Optional[asyncio.Task] = None
        self._trade_check_task: Optional[asyncio.Task] = None
        self._candle_stream_task: Optional[asyncio.Task] = None
        
        # Кэш свечей (asset_id -> список свечей)
        self._candle_cache: Dict[str, List[Dict]] = {}  # asset_id -> [candle_data, ...]

        # Настройки
        self._max_candles_per_period = 1000  # Максимум свечей на период
        self._max_ticks = 500  # Максимум тиков
        self._balance_update_interval = 2  # Секунды (уменьшил для быстрого обновления)

    # ==========================================================================
    # ПОДКЛЮЧЕНИЕ
    # ==========================================================================

    async def connect(self):
        """
        Подключение к Pocket Option.

        Raises:
            Exception: Ошибка подключения
        """
        if not self.ssid or not str(self.ssid).strip():
            raise ValueError("SSID не задан. Заполните POCKET_OPTION_DEMO_SSID или POCKET_OPTION_REAL_SSID в .env")
        if not is_valid_ssid(self.ssid):
            raise ValueError('Некорректный SSID. Ожидается строка формата 42["auth",{...}]')

        print("[RobotEngine] Подключение...")
        print("[RobotEngine] SSID получен из конфигурации")

        try:
            print("[RobotEngine] Создание клиента...")
            self.client = PocketOptionAsync(ssid=self.ssid)
            print("[RobotEngine] Подключение к серверу...")
            await self.client.__aenter__()

            # The account type belongs to the SSID/API client, not to the
            # default Balance value. This is essential for real-account polling.
            self._balance.is_demo = bool(self.client.is_demo())
            self._connected = True
            self._running = True

            print("[RobotEngine] ✅ Подключено")

            # Получение баланса
            balance_value = await self.client.balance()
            self._store_balance(balance_value)
            print(f"[RobotEngine] 💰 Баланс: ${self._balance.current}")

            # Запуск фоновых задач
            self._balance_task = asyncio.create_task(self._balance_loop())
            self._trade_check_task = asyncio.create_task(self._trade_check_loop())
            # Candle streams are started explicitly by subscribe(). Starting a
            # second discovery loop here races with that call and duplicates WS
            # subscriptions.

            # Callback
            if self._on_connected:
                # Вызываем callback без await, если это не coroutine
                result = self._on_connected()
                if asyncio.iscoroutine(result):
                    await result

        except Exception as e:
            print(f"[RobotEngine] ❌ Ошибка подключения: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        """Отключение от Pocket Option."""
        print("[RobotEngine] Отключение...")

        self._running = False

        # Отмена задач
        await self._cancel_all_tasks()

        # Закрытие клиента
        if self.client:
            await self.client.__aexit__(None, None, None)

        self._connected = False

        # Callback
        if self._on_disconnected:
            await self._on_disconnected()

        print("[RobotEngine] ✅ Отключено")

    async def _cancel_all_tasks(self):
        """Отмена всех фоновых задач."""
        # Отмена задач свечей
        for key, task in self._candle_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Отмена задачи баланса
        if self._balance_task:
            self._balance_task.cancel()
            try:
                await self._balance_task
            except asyncio.CancelledError:
                pass

        # Отмена задачи проверки сделок
        if self._trade_check_task:
            self._trade_check_task.cancel()
            try:
                await self._trade_check_task
            except asyncio.CancelledError:
                pass

        # Отмена задачи потока свечей
        if self._candle_stream_task:
            self._candle_stream_task.cancel()
            try:
                await self._candle_stream_task
            except asyncio.CancelledError:
                pass

        self._candle_tasks.clear()
        self._candle_cache.clear()

    async def _candle_stream_loop(self):
        """
        Фоновый поток для получения свечей в реальном времени.
        
        Подписывается на активы из подписок и обновляет кэш.
        """
        print("[RobotEngine] 🔁 Запуск потока свечей...")
        
        while self._running:
            try:
                # Подписываемся на все активы из подписок
                for key, subscription in self._subscriptions.items():
                    if subscription.active and key not in self._candle_tasks:
                        # Запускаем поток для этого актива
                        task = asyncio.create_task(
                            self._subscribe_candle_stream(subscription.symbol, subscription.period)
                        )
                        self._candle_tasks[key] = task
                        print(f"[RobotEngine] 📊 Подписка на {subscription.symbol} ({subscription.period}s)")
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[RobotEngine] ✗ Ошибка потока свечей: {e}")
                await asyncio.sleep(5)

    async def _subscribe_candle_stream(self, symbol: str, period: int):
        """
        Подписка на свечи актива через subscribe_symbol_timed().

        Args:
            symbol: ID актива
            period: Период свечей в секундах
        """
        try:
            print(f"[RobotEngine] 📡 Подписка на {symbol} (period={period}s) через subscribe_symbol_timed...")

            await self._load_candle_history(symbol, period)
            
            # Подписываемся на свечи с указанным периодом
            candles_stream = await self.client.subscribe_symbol_timed(
                symbol,
                timedelta(seconds=period)
            )
            
            print(f"[RobotEngine] ✅ Подписка на {symbol} успешна")
            
            count = 0
            async for candle_data in candles_stream:
                if not self._running:
                    break
                
                count += 1
                
                # Добавляем в кэш
                if symbol not in self._candle_cache:
                    self._candle_cache[symbol] = []
                
                self._candle_cache[symbol].append(candle_data)
                
                # Оставляем только последние 100 свечей
                if len(self._candle_cache[symbol]) > 100:
                    self._candle_cache[symbol] = self._candle_cache[symbol][-100:]
                
                if count % 10 == 0:
                    print(f"[RobotEngine] 📊 {symbol}: получено {count} свечей, в кэше: {len(self._candle_cache[symbol])}")
                
                # Callback
                if self._on_candle:
                    await self._on_candle(symbol, period, [Candle.from_dict(candle_data)])
                    
            print(f"[RobotEngine] ⚠️ Поток {symbol} завершён (получено {count} свечей)")
                    
        except asyncio.CancelledError:
            print(f"[RobotEngine] ⚠️ Подписка {symbol} отменена")
            pass
        except Exception as e:
            print(f"[RobotEngine] ✗ Ошибка подписки {symbol}: {e}")

    def _get_candle_price(self, symbol: str, timestamp: int) -> Optional[float]:
        """
        Получение цены закрытия из кэша.

        Args:
            symbol: ID актива
            timestamp: Время свечи

        Returns:
            Цена закрытия или None
        """
        if symbol not in self._candle_cache:
            print(f"[RobotEngine] ⚠️ Кэш пуст для {symbol}")
            return None

        # Ищем свечу с нужным временем (допускаем погрешность ±5 сек)
        for candle in reversed(self._candle_cache[symbol]):
            candle_ts = candle.get("timestamp", 0)
            if abs(candle_ts - timestamp) <= 5:
                close = float(candle.get("close", 0))
                print(f"[RobotEngine] 📊 Найдена свеча: ts={candle_ts}, close={close:.5f}")
                return close

        # Если не нашли точную, возвращаем последнюю
        if self._candle_cache[symbol]:
            last_close = float(self._candle_cache[symbol][-1].get("close", 0))
            print(f"[RobotEngine] 📊 Свеча не найдена, возвращаем последнюю: {last_close:.5f}")
            return last_close

        print(f"[RobotEngine] ⚠️ Кэш пуст после проверки")
        return None

    # ==========================================================================
    # ПОДПИСКИ
    # ==========================================================================

    async def subscribe(self, symbol: str, period: int = 60) -> bool:
        """
        Подписка на свечи актива.

        Args:
            symbol: ID актива (EURUSD_otc, BTCUSD_otc, etc.)
            period: Период свечи в секундах (60, 300, 900, etc.)

        Returns:
            True если подписка успешна

        Example:
            >>> await engine.subscribe("EURUSD_otc", 60)
            >>> await engine.subscribe("BTCUSD_otc", 300)
        """
        if not self._connected:
            print("[RobotEngine] ❌ Не подключено")
            return False

        key = f"{symbol}_{period}"

        # Уже подписаны
        if key in self._subscriptions:
            print(f"[RobotEngine] ℹ️ Уже подписаны на {key}")
            return True

        # Добавляем в подписки
        subscription = Subscription(symbol=symbol, period=period, active=True)
        self._subscriptions[key] = subscription

        # Инициализируем хранилище
        if symbol not in self._candles:
            self._candles[symbol] = {}
        if period not in self._candles[symbol]:
            self._candles[symbol][period] = deque(maxlen=self._max_candles_per_period)

        if symbol not in self._ticks:
            self._ticks[symbol] = deque(maxlen=self._max_ticks)

        # Запускаем поток свечей
        await self._start_candle_stream(symbol, period)

        print(f"[RobotEngine] ✅ Подписка на {symbol} ({period}s)")
        return True

    async def replace_subscription(self, symbol: str, period: int = 60) -> bool:
        """Replace all active candle streams with one requested stream."""
        for subscription in list(self.get_subscriptions()):
            if subscription.symbol != symbol or subscription.period != period:
                await self.unsubscribe(subscription.symbol, subscription.period)
        return await self.subscribe(symbol, period)

    async def unsubscribe(self, symbol: str, period: int = 60) -> bool:
        """
        Отписка от свечей актива.

        Args:
            symbol: ID актива
            period: Период свечи в секундах

        Returns:
            True если отписка успешна
        """
        key = f"{symbol}_{period}"

        if key not in self._subscriptions:
            return False

        # Отмечаем как неактивную
        self._subscriptions[key].active = False

        # Отменяем задачу
        if key in self._candle_tasks:
            task = self._candle_tasks[key]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._candle_tasks[key]

        del self._subscriptions[key]

        print(f"[RobotEngine] ℹ️ Отписка от {symbol} ({period}s)")
        return True

    async def _start_candle_stream(self, symbol: str, period: int):
        """Запуск потока свечей."""
        key = f"{symbol}_{period}"

        if not self.client:
            return

        try:
            print(f"[RobotEngine] 📊 OHLC-поток: {symbol} ({period}s)")

            await self._load_candle_history(symbol, period)

            # The library's raw/timed subscriptions use a different price
            # feed than compile_candles(). Poll the same server OHLC endpoint
            # used for the seed to avoid mixing incompatible price series.
            task = asyncio.create_task(self._candle_poll_handler(key, symbol, period))
            self._candle_tasks[key] = task

        except Exception as e:
            print(f"[RobotEngine] ❌ Ошибка потока свечей {symbol} ({period}s): {e}")

    async def _candle_handler(self, key: str, symbol: str, period: int, stream):
        """Обработчик свечей."""
        try:
            async for candle_data in stream:
                if not self._running:
                    break

                # Проверяем активна ли подписка
                if key not in self._subscriptions or not self._subscriptions[key].active:
                    break

                await self._ingest_candle_snapshot(symbol, period, candle_data)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[RobotEngine] ✗ Ошибка обработчика свечей {key}: {e}")

    @staticmethod
    def _normalize_tick_timestamp(timestamp: int) -> int:
        """Normalize the API timestamp to the local Unix timeline."""
        if timestamp > int(time.time()) + 1800:
            return timestamp - 7200
        return timestamp

    async def _tick_handler(self, key: str, symbol: str, period: int, stream):
        """Aggregate raw ticks into calendar-aligned candles."""
        try:
            async for tick_data in stream:
                if not self._running:
                    break
                if key not in self._subscriptions or not self._subscriptions[key].active:
                    break
                if not isinstance(tick_data, dict):
                    continue
                timestamp = int(float(tick_data.get("timestamp", tick_data.get("time", 0))))
                price = float(tick_data.get("price", tick_data.get("close", 0)))
                if timestamp > 0 and price > 0:
                    await self._ingest_tick(symbol, period, timestamp, price)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"[RobotEngine] ✗ Ошибка tick-потока {key}: {exc}")

    async def _load_candle_history(self, symbol: str, period: int, count: int = 50) -> None:
        """Load server-aggregated OHLC candles for history and polling."""
        if not self.client:
            return
        try:
            history = await asyncio.wait_for(
                self.client.compile_candles(symbol, period, count * period),
                timeout=10,
            )
            if not isinstance(history, list):
                return
            target = self._candles[symbol][period]
            target.clear()
            for data in history[-count:]:
                if not isinstance(data, dict):
                    continue
                target.append(Candle.from_dict({**data, "symbol": symbol}))
            self._candle_cache[symbol] = [item.to_dict() for item in target]
            if target and self._on_candle:
                result = self._on_candle(symbol, period, list(target))
                if asyncio.iscoroutine(result):
                    await result
            print(f"[RobotEngine] 📚 OHLC-история {symbol}: загружено {len(target)} свечей")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[RobotEngine] ⚠️ История {symbol} недоступна: {exc}")

    async def _candle_poll_handler(self, key: str, symbol: str, period: int) -> None:
        """Refresh history/current OHLC from one consistent API endpoint."""
        try:
            while self._running and key in self._subscriptions and self._subscriptions[key].active:
                await asyncio.sleep(min(max(period, 5), 15))
                await self._load_candle_history(symbol, period)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"[RobotEngine] ✗ Ошибка OHLC-потока {key}: {exc}")

    async def _ingest_tick(self, symbol: str, period: int, timestamp: int, price: float) -> None:
        """Update or append one calendar-aligned candle."""
        timestamp = self._normalize_tick_timestamp(timestamp)
        bucket = (timestamp // period) * period
        target = self._candles[symbol][period]
        if target and target[-1].timestamp == bucket:
            candle = target[-1]
            candle.high = max(candle.high, price)
            candle.low = min(candle.low, price)
            candle.close = price
            candle.is_closed = False
        elif not target or bucket > target[-1].timestamp:
            if target:
                target[-1].is_closed = True
            target.append(Candle(symbol, bucket, price, price, price, price, is_closed=False))
        else:
            return
        self._candle_cache[symbol] = [item.to_dict() for item in target]
        if self._on_candle:
            result = self._on_candle(symbol, period, list(target))
            if asyncio.iscoroutine(result):
                await result

    async def _ingest_candle_snapshot(self, symbol: str, period: int, data: dict) -> None:
        """Merge realtime snapshots instead of appending duplicate bars."""
        if not isinstance(data, dict):
            return
        normalized = {**data, "symbol": symbol, "is_closed": bool(data.get("is_closed", False))}
        timestamp = int(float(normalized.get("timestamp", normalized.get("time", 0))))
        # BinaryOptionsToolsV2 currently returns aligned stream timestamps
        # two hours ahead of the local Unix clock, while compile_candles()
        # returns already-normalized timestamps.
        if timestamp > int(time.time()) + 1800:
            normalized["timestamp"] = timestamp - 7200
        candle = Candle.from_dict(normalized)
        target = self._candles[symbol][period]
        if target and target[-1].timestamp == candle.timestamp:
            target[-1] = candle
        elif not target or candle.timestamp > target[-1].timestamp:
            if target:
                target[-1].is_closed = True
            target.append(candle)
        else:
            for index, existing in enumerate(target):
                if existing.timestamp == candle.timestamp:
                    target[index] = candle
                    break
            else:
                return
        self._candle_cache[symbol] = [item.to_dict() for item in target]
        if self._on_candle:
            result = self._on_candle(symbol, period, list(target))
            if asyncio.iscoroutine(result):
                await result

    # ==========================================================================
    # ФОНОВЫЕ ЗАДАЧИ
    # ==========================================================================

    async def _balance_loop(self):
        """Обновление баланса каждые N секунд."""
        while self._running:
            try:
                await asyncio.sleep(self._balance_update_interval)
                if self._connected and self.client:
                    self._balance.is_demo = bool(self.client.is_demo())
                    balance_value = await self.client.balance()
                    self._store_balance(balance_value)

                    # Callback
                    if self._on_balance:
                        await self._on_balance(self._balance)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[RobotEngine] ✗ Ошибка баланса: {e}")

    def _store_balance(self, value: float) -> None:
        """Store the server balance in the field matching the account mode."""
        value = float(value)
        if self._balance.is_demo:
            self._balance.demo = value
        else:
            self._balance.real = value

    async def refresh_balance(self) -> Balance:
        """Fetch the current server balance and notify listeners immediately."""
        if not self._connected or not self.client:
            raise RuntimeError("Не подключено")
        self._balance.is_demo = bool(self.client.is_demo())
        self._store_balance(await self.client.balance())
        if self._on_balance:
            result = self._on_balance(self._balance)
            if asyncio.iscoroutine(result):
                await result
        return self._balance

    async def get_active_assets(self) -> list:
        """Return active assets from the API without exposing the raw client."""
        if not self._connected or not self.client:
            raise RuntimeError("Не подключено")
        assets = await self.client.active_assets()
        return assets if isinstance(assets, list) else []

    async def _trade_check_loop(self):
        """Проверка результатов сделок."""
        print(f"[RobotEngine] 🔍 _trade_check_loop запущен, pending_checks: {len(self._pending_checks)}")
        
        while self._running:
            try:
                await asyncio.sleep(1)  # Проверяем каждую секунду
                
                print(f"[RobotEngine] 🔁 Проверка сделок... pending_checks: {self._pending_checks}")

                if not self._pending_checks:
                    continue

                # Проверяем каждую сделку
                for trade_id in list(self._pending_checks):
                    if trade_id not in self._trades:
                        self._pending_checks.discard(trade_id)
                        continue

                    deal = self._trades[trade_id]
                    
                    if deal.status != "open":
                        self._pending_checks.discard(trade_id)
                        continue
                    
                    # Прошло ли достаточно времени
                    elapsed = (datetime.now() - deal.open_time).total_seconds()
                    
                    if elapsed < deal.duration + 2:
                        continue
                    
                    # Пробуем получить результат через get_deal_end_time
                    try:
                        print(f"[RobotEngine] 🔎 Вызов get_deal_end_time для {trade_id}")
                        end_time = await self.client.get_deal_end_time(trade_id)
                        print(f"[RobotEngine] ✅ get_deal_end_time вернул: {end_time}")
                        
                        if end_time and end_time > 0:
                            print(f"[RobotEngine] ⏱️ Сделка закрыта, ждём результат...")
                            # Сделка закрыта по времени, получаем результат из opened_deals
                            await asyncio.sleep(1)  # Ждём обновления
                            
                            try:
                                opened = await self.client.opened_deals()
                                print(f"[RobotEngine] 📊 opened_deals: {type(opened)}")
                                
                                if opened and isinstance(opened, dict) and trade_id in opened:
                                    deal_data = opened[trade_id]
                                    
                                    # Получаем все поля для отладки
                                    print(f"[RobotEngine] 📊 deal_data: {deal_data}")
                                    
                                    close_time = deal_data.get("closeTime")
                                    profit_field = deal_data.get("profit")  # '0.92' = коэффициент
                                    close_price = deal_data.get("closePrice")  # Цена закрытия
                                    open_price = deal_data.get("openPrice")  # Цена открытия
                                    command = deal_data.get("command")  # 0=CALL, 1=PUT
                                    
                                    print(f"[RobotEngine] 📊 closeTime={close_time}, profit={profit_field}, closePrice={close_price}, openPrice={open_price}, command={command}")
                                    
                                    deal.status = "closed"
                                    deal.close_time = datetime.now()
                                    
                                    # Если closeTime есть — сделка закрыта
                                    if close_time:
                                        # Сравниваем цену открытия с ценой закрытия в момент экспирации
                                        try:
                                            print(f"[RobotEngine] 🔎 Определение результата по цене закрытия...")
                                            
                                            open_price = float(open_price) if open_price else 0
                                            command = deal_data.get("command", 0)  # 0=CALL, 1=PUT
                                            close_timestamp = deal_data.get("closeTimestamp", 0)
                                            asset = deal_data.get("asset", "EURUSD_otc")
                                            
                                            # Запрашиваем свечи для получения цены закрытия
                                            print(f"[RobotEngine] 📡 Запрос свечей для {asset}...")
                                            candles = await self.client.get_candles(asset, period=60, offset=0)
                                            
                                            print(f"[RobotEngine] 📊 Получено свечей: {len(candles) if candles else 0}")
                                            
                                            # Ищем свечу с нужным временем
                                            close_price_actual = None
                                            if candles:
                                                for candle in candles:
                                                    candle_ts = candle.get("timestamp", 0)
                                                    if abs(candle_ts - close_timestamp) <= 2:
                                                        close_price_actual = float(candle.get("close", 0))
                                                        print(f"[RobotEngine] 📊 Найдена свеча: ts={candle_ts}, close={close_price_actual}")
                                                        break
                                                
                                                # Если не нашли, берём последнюю
                                                if not close_price_actual and candles:
                                                    close_price_actual = float(candles[-1].get("close", 0))
                                                    print(f"[RobotEngine] 📊 Свеча не найдена, используем последнюю: {close_price_actual}")
                                            
                                            print(f"[RobotEngine] 📊 open_price={open_price}, close_price={close_price_actual}, command={command}")
                                            
                                            deal.status = "closed"
                                            deal.close_time = datetime.now()
                                            
                                            if close_price_actual and open_price:
                                                # Определяем результат по направлению и цене
                                                if command == 0:  # CALL
                                                    if close_price_actual > open_price:
                                                        # Выигрыш
                                                        deal.profit = deal.amount * 0.92  # 92% прибыль
                                                        print(f"[RobotEngine] 💰 CALL ВЫИГРЫШ: +${deal.profit:.2f}")
                                                    else:
                                                        # Проигрыш
                                                        deal.profit = -deal.amount
                                                        print(f"[RobotEngine] ❌ CALL ПРОИГРЫШ: -${deal.amount:.2f}")
                                                else:  # PUT
                                                    if close_price_actual < open_price:
                                                        # Выигрыш
                                                        deal.profit = deal.amount * 0.92  # 92% прибыль
                                                        print(f"[RobotEngine] 💰 PUT ВЫИГРЫШ: +${deal.profit:.2f}")
                                                    else:
                                                        # Проигрыш
                                                        deal.profit = -deal.amount
                                                        print(f"[RobotEngine] ❌ PUT ПРОИГРЫШ: -${deal.amount:.2f}")
                                            else:
                                                print(f"[RobotEngine] ⚠️ Цена не найдена (close={close_price_actual}, open={open_price})")
                                                deal.profit = -deal.amount
                                                print(f"[RobotEngine] ❌ ПРОИГРЫШ (no price): -${deal.amount:.2f}")
                                                
                                        except Exception as e:
                                            print(f"[RobotEngine] ✗ Ошибка определения результата: {e}")
                                            deal.profit = -deal.amount
                                            print(f"[RobotEngine] ❌ ПРОИГРЫШ (error): -${deal.amount:.2f}")
                                    else:
                                        # Сделка ещё не закрыта
                                        print(f"[RobotEngine] ⚠️ Сделка ещё не закрыта")
                                        continue
                                    
                                    # Баланс обновится в _balance_loop
                                    
                                    if self._on_trade:
                                        print(f"[RobotEngine] 📢 Вызов on_trade: {trade_id} profit={deal.profit}")
                                        await self._on_trade(deal)
                                    
                                    self._pending_checks.discard(trade_id)
                                    print(f"[RobotEngine] 💼 Сделка {trade_id}: {'+' if deal.profit > 0 else ''}{deal.profit}$")
                                    
                                else:
                                    print(f"[RobotEngine] ⚠️ Сделка не найдена в opened_deals, ждём...")
                                    
                            except Exception as e:
                                print(f"[RobotEngine] ✗ Ошибка получения результата: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"[RobotEngine] ⚠️ Сделка ещё не закрыта (end_time={end_time})")
                            
                    except Exception as e:
                        print(f"[RobotEngine] ✗ Ошибка проверки сделки {trade_id}: {e}")
                        import traceback
                        traceback.print_exc()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[RobotEngine] ✗ Ошибка проверки сделок: {e}")

    # ==========================================================================
    # ТОРГОВЛЯ
    # ==========================================================================

    async def buy(self, symbol: str, amount: float, duration: int, direction: str = "call") -> tuple:
        """
        Открытие сделки на повышение (CALL).

        Args:
            symbol: ID актива
            amount: Сумма сделки
            duration: Длительность в секундах
            direction: "call" или "put"

        Returns:
            (trade_id, deal_data)

        Raises:
            Exception: Если не подключено или ошибка торговли

        Example:
            >>> trade_id, deal = await engine.buy("EURUSD_otc", 1.0, 60, "call")
            >>> print(f"Сделка: {trade_id}, Результат: {deal}")
        """
        if not self._connected:
            raise Exception("Не подключено")

        print(f"[RobotEngine] 💼 Buy {direction.upper()} {symbol} ${amount} {duration}s")

        if direction.lower() == "call":
            trade_id, deal_data = await self.client.buy(symbol, amount, duration)
        else:
            trade_id, deal_data = await self.client.sell(symbol, amount, duration)

        # Создаем сделку
        current_price = float(deal_data.get("price", 0)) if isinstance(deal_data, dict) else 0.0

        deal = Deal(
            trade_id=trade_id,
            strategy_id="robot_engine",
            series_id=f"series-{trade_id[:8]}",
            symbol=symbol,
            direction=direction.lower(),
            amount=amount,
            duration=duration,
            open_price=current_price,
            status="open"
        )

        self._trades[trade_id] = deal
        self._pending_checks.add(trade_id)

        # Сохраняем баланс до сделки для определения результата
        self._trade_balances[trade_id] = self._balance.current

        # Обновляем баланс (списываем сумму сделки)
        if self._balance.is_demo:
            self._balance.demo -= amount
        else:
            self._balance.real -= amount
        
        # Callback для обновления баланса
        if self._on_balance:
            await self._on_balance(self._balance)

        # Callback для сделки
        if self._on_trade:
            await self._on_trade(deal)

        return trade_id, deal_data

    async def sell(self, symbol: str, amount: float, duration: int) -> tuple:
        """
        Открытие сделки на понижение (PUT).

        Args:
            symbol: ID актива
            amount: Сумма сделки
            duration: Длительность в секундах

        Returns:
            (trade_id, deal_data)
        """
        return await self.buy(symbol, amount, duration, "put")

    # ==========================================================================
    # CALLBACKS
    # ==========================================================================

    def on_candle(self, callback: Callable):
        """
        Регистрация обработчика свечей.

        Args:
            callback: Асинхронная функция(symbol, period, candles)

        Example:
            >>> async def on_candle(symbol, period, candles):
            ...     print(f"{symbol}: {candles[-1].close}")
            >>> engine.on_candle(on_candle)
        """
        self._on_candle = callback

    def on_tick(self, callback: Callable):
        """Регистрация обработчика тиков."""
        self._on_tick = callback

    def on_balance(self, callback: Callable):
        """
        Регистрация обработчика баланса.

        Args:
            callback: Асинхронная функция(balance)

        Example:
            >>> async def on_balance(balance):
            ...     print(f"Баланс: ${balance.current}")
            >>> engine.on_balance(on_balance)
        """
        self._on_balance = callback

    def on_trade(self, callback: Callable):
        """
        Регистрация обработчика сделок.

        Args:
            callback: Асинхронная функция(deal)

        Example:
            >>> async def on_trade(deal):
            ...     print(f"Сделка {deal.trade_id}: {deal.profit}$")
            >>> engine.on_trade(on_trade)
        """
        self._on_trade = callback

    def on_connected(self, callback: Callable):
        """Регистрация обработчика подключения."""
        self._on_connected = callback

    def on_disconnected(self, callback: Callable):
        """Регистрация обработчика отключения."""
        self._on_disconnected = callback

    # ==========================================================================
    # ДАННЫЕ
    # ==========================================================================

    def get_candles(self, symbol: str, period: int = 60, count: int = 100) -> List[Candle]:
        """
        Получение свечей.

        Args:
            symbol: ID актива
            period: Период свечи в секундах
            count: Количество свечей

        Returns:
            Список свечей

        Example:
            >>> candles = engine.get_candles("EURUSD_otc", 60, 100)
            >>> for candle in candles:
            ...     print(f"{candle.time}: {candle.close}")
        """
        if symbol not in self._candles:
            return []
        if period not in self._candles[symbol]:
            return []
        return list(self._candles[symbol][period])[-count:]

    def get_ticks(self, symbol: str, count: int = 50) -> List[Tick]:
        """Получение тиков."""
        if symbol not in self._ticks:
            return []
        return list(self._ticks[symbol])[-count:]

    def get_balance(self) -> Balance:
        """Получение баланса."""
        return self._balance

    def get_trades(self, count: int = 20) -> List[Deal]:
        """
        Получение сделок.

        Args:
            count: Количество сделок

        Returns:
            Список сделок
        """
        return list(self._trades.values())[-count:]

    def get_subscriptions(self) -> List[Subscription]:
        """Получение активных подписок."""
        return [sub for sub in self._subscriptions.values() if sub.active]

    # ==========================================================================
    # СТАТУС
    # ==========================================================================

    def is_running(self) -> bool:
        """Статус работы."""
        return self._running

    def is_connected(self) -> bool:
        """Статус подключения."""
        return self._connected

    def get_stats(self) -> Dict:
        """
        Получение статистики.

        Returns:
            Словарь со статистикой

        Example:
            >>> stats = engine.get_stats()
            >>> print(f"Баланс: ${stats['balance']}, Свечей: {stats['candles_count']}")
        """
        total_candles = sum(
            len(period_candles)
            for symbol_candles in self._candles.values()
            for period_candles in symbol_candles.values()
        )

        total_ticks = sum(len(ticks) for ticks in self._ticks.values())

        return {
            "connected": self._connected,
            "running": self._running,
            "balance": self._balance.current,
            "is_demo": self._balance.is_demo,
            "subscriptions_count": len(self._subscriptions),
            "candles_count": total_candles,
            "ticks_count": total_ticks,
            "trades_count": len(self._trades)
        }

    # ==========================================================================
    # CONTEXT MANAGER
    # ==========================================================================

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


__all__ = ["RobotEngine"]
