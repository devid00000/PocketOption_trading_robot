#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live-график EURUSD_otc с 10-секундными свечами.
Версия с полной отладкой поступления данных.
"""

import asyncio
import os
import threading
import time
import json
from collections import deque
from datetime import datetime
from typing import Deque, Optional, Dict, Any

import pandas as pd
from dash import Dash, dcc, html, Input, Output, ctx
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.tracing import start_logs

# ================= НАСТРОЙКИ =================
ASSET = "EURUSD_otc"
TIMEFRAME = 10
MAX_CANDLES = 120
DASH_PORT = 8050
LOG_PATH = "logs/"
DEBUG_MODE = True  # 🔍 Включить подробное логирование


# =============================================


class CandleBuffer:
    """Потокoбезопасный буфер для свечей."""

    def __init__(self, timeframe: int = 10, max_candles: int = 120):
        self.timeframe = timeframe
        self.max_candles = max_candles
        self.current_candle: Optional[Dict[str, Any]] = None
        self.completed: Deque[Dict[str, Any]] = deque(maxlen=max_candles)
        self._lock = threading.Lock()
        self.tick_count = 0
        self.last_update = time.time()

    def add_tick(self, price: float, timestamp: Optional[float] = None):
        """Добавление тика с блокировкой."""
        with self._lock:
            ts = timestamp or time.time()
            candle_start = int(ts // self.timeframe) * self.timeframe

            if self.current_candle is None or self.current_candle['time'] != candle_start:
                if self.current_candle is not None:
                    self.completed.append(self.current_candle.copy())

                self.current_candle = {
                    'time': candle_start,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price
                }
            else:
                self.current_candle['high'] = max(self.current_candle['high'], price)
                self.current_candle['low'] = min(self.current_candle['low'], price)
                self.current_candle['close'] = price

            self.tick_count += 1
            self.last_update = time.time()

    def get_candles(self) -> list:
        """Получение всех свечей с блокировкой."""
        with self._lock:
            candles = list(self.completed)
            if self.current_candle:
                candles.append(self.current_candle.copy())
            return candles

    def get_stats(self) -> Dict[str, Any]:
        """Статистика буфера."""
        with self._lock:
            return {
                'ticks': self.tick_count,
                'completed': len(self.completed),
                'current': 1 if self.current_candle else 0,
                'last_update': self.last_update,
                'age': time.time() - self.last_update
            }


# Глобальный буфер
buffer = CandleBuffer(timeframe=TIMEFRAME, max_candles=MAX_CANDLES)


def create_figure(candles: list) -> go.Figure:
    """Создание графика свечей."""
    if not candles:
        fig = go.Figure()
        fig.add_annotation(
            text="⏳ Ожидание данных...<br>Проверьте консоль на ошибки",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font_size=16, align="center"
        )
        fig.update_layout(
            template='plotly_dark', height=600,
            title=f"{ASSET} • {TIMEFRAME}s Candles",
            xaxis_title="Время", yaxis_title="Цена"
        )
        return fig

    df = pd.DataFrame(candles)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')

    fig = go.Figure(data=[go.Candlestick(
        x=df['datetime'],
        open=df['open'], high=df['high'],
        low=df['low'], close=df['close'],
        name=ASSET,
        increasing_line_color='#00c853',
        decreasing_line_color='#ff5252'
    )])

    last = df.iloc[-1]
    change = last['close'] - last['open']
    sign = "📈" if change >= 0 else "📉"
    title = f"{ASSET} • {TIMEFRAME}s • {sign} {last['close']:.5f} ({change:+.5f})"

    fig.update_layout(
        template='plotly_dark',
        height=600,
        title=title,
        xaxis_title="Время",
        yaxis_title="Цена",
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        margin=dict(l=40, r=40, t=50, b=40)
    )
    fig.update_xaxes(tickformat='%H:%M:%S')

    return fig


def run_dash_app():
    """Запуск Dash-приложения в главном потоке."""
    app = Dash(__name__, update_title=None)
    app.title = f"📊 {ASSET} Live"

    app.layout = html.Div([
        html.H2(f"🔗 {ASSET} • {TIMEFRAME}-секундные свечи",
                style={'textAlign': 'center', 'color': '#fff', 'marginBottom': 10}),
        dcc.Graph(id='live-chart', config={'displayModeBar': True}),
        dcc.Interval(id='interval', interval=1000, n_intervals=0),
        html.Div(id='status', style={'textAlign': 'center', 'color': '#aaa', 'fontSize': 12}),
        html.Div(id='debug-info', style={'textAlign': 'center', 'color': '#ff9800', 'fontSize': 11})
    ], style={'backgroundColor': '#1e1e1e', 'padding': 20, 'fontFamily': 'Arial'})

    @app.callback(
        [Output('live-chart', 'figure'),
         Output('status', 'children'),
         Output('debug-info', 'children')],
        Input('interval', 'n_intervals')
    )
    def update_graph(n):
        stats = buffer.get_stats()
        candles = buffer.get_candles()

        # Отладочная информация
        debug_text = (
            f"📊 Тиков: {stats['ticks']} | "
            f"Свечей: {stats['completed']}+{stats['current']} | "
            f"Последнее обновление: {stats['age']:.1f}с назад"
        )

        if stats['age'] > 30:
            debug_text += " ⚠️ Данных нет более 30 секунд!"

        status_text = f"🕐 {datetime.now().strftime('%H:%M:%S')} | Буфер: {len(candles)} свечей"

        return create_figure(candles), status_text, debug_text

    print(f"🌐 График: http://localhost:{DASH_PORT}")
    print(f"🔍 Отладка: {DEBUG_MODE}")
    app.run(host='127.0.0.1', port=DASH_PORT, debug=False)


async def data_fetcher(ssid: str):
    """Асинхронный клиент для получения данных."""
    start_logs(path=LOG_PATH, level="WARNING", terminal=True)

    print(f"🔌 Подключение к {ASSET}...")

    try:
        async with PocketOptionAsync(ssid=ssid) as client:
            balance = await client.balance()
            print(f"✅ Баланс: ${balance:.2f}")

            # 🔍 Проверка доступных активов
            print(f"📋 Проверка актива {ASSET}...")
            # Библиотека должна была загрузить активы при подключении

            # 📥 Попытка загрузки истории
            print("📥 Загрузка истории свечей...")
            try:
                # Пробуем разные периоды
                for period in [60, 30, 10]:
                    try:
                        hist = await client.get_candles(ASSET, period=period, offset=0)
                        if hist:
                            print(f"✅ Получено {len(hist)} свечей (период {period}s)")
                            for c in hist[-20:]:  # Последние 20
                                buffer.add_tick(c.get('close', 0), c.get('time'))
                            break
                    except Exception as e:
                        print(f"⚠️ Период {period}s: {e}")
                        continue
            except Exception as e:
                print(f"❌ Ошибка истории: {e}")

            # 📡 Подписка на поток
            print(f"📡 Подписка на поток {ASSET}...")
            print("💡 Откройте http://localhost:8050 в браузере")
            print("🔍 Следите за консолью — должны появляться тики\n")

            # 🔍 Проверяем тип subscribe_symbol
            stream = client.subscribe_symbol(ASSET)
            print(f"📊 Тип потока: {type(stream)}")

            # Пробуем разные способы итерации
            try:
                async for tick in stream:
                    if DEBUG_MODE:
                        print(f"📥 Тик: {tick}")

                    price = None
                    ts = None

                    # 🔍 Парсим разные форматы ответа
                    if isinstance(tick, dict):
                        price = tick.get('close') or tick.get('value') or tick.get('price')
                        ts = tick.get('time') or tick.get('timestamp')
                    elif isinstance(tick, (int, float)):
                        price = tick
                        ts = time.time()

                    if price:
                        buffer.add_tick(float(price), ts)
                        now = datetime.now().strftime('%H:%M:%S')
                        stats = buffer.get_stats()
                        print(f"\r[{now}] 💹 {price:.5f} | Тиков: {stats['ticks']} | Свечей: {stats['completed']}",
                              end='', flush=True)

            except TypeError as e:
                print(f"\n❌ Ошибка итерации: {e}")
                print("💡 Попробуйте обновить библиотеку: pip install --upgrade binaryoptionstoolsv2")

    except KeyboardInterrupt:
        print("\n🛑 Остановка...")
    except Exception as e:
        print(f"\n❌ Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Точка входа."""
    from config.runtime import load_runtime_config
    ssid = load_runtime_config().demo_ssid
    if not ssid:
        print("🔑 Введите SSID от Pocket Option:")
        print("   F12 → Application → Cookies → ssid")
        ssid = input(">>> ").strip()

    if not ssid:
        print("❌ SSID не указан")
        return

    # Запуск Dash в главном потоке
    dash_thread = threading.Thread(target=run_dash_app, daemon=False)
    dash_thread.start()
    time.sleep(2)  # Дать время на запуск сервера

    # Запуск клиента в фоне
    asyncio.run(data_fetcher(ssid))


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    main()
