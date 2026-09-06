"""
Trade Logger - Логирование сделок в SQLite.
"""

import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict

from core.market_data import Deal, Candle
from config.paths import TRADES_DB


class TradeLogger:
    """
    Логгер сделок с сохранением в SQLite базу данных.

    Хранит:
    - Историю всех сделок
    - Статистику по стратегиям
    - Дневные/недельные/месячные отчёты
    """

    def __init__(self, db_path: str = str(TRADES_DB)):
        """
        Инициализация логгера.

        Args:
            db_path: Путь к базе данных
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self):
        """Инициализация базы данных."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Таблица сделок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                strategy_name TEXT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                amount REAL NOT NULL,
                duration INTEGER NOT NULL,
                open_time TIMESTAMP NOT NULL,
                close_time TIMESTAMP,
                open_price REAL,
                close_price REAL,
                profit REAL,
                profit_percent REAL,
                status TEXT DEFAULT 'open',
                balance_before REAL,
                balance_after REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица сигналов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                strength REAL,
                reason TEXT,
                timestamp TIMESTAMP NOT NULL,
                traded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица дневной статистики
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_profit REAL DEFAULT 0,
                total_loss REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0,
                best_trade REAL DEFAULT 0,
                worst_trade REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Индексы для ускорения поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_open_time ON trades(open_time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date)
        """)

        conn.commit()
        conn.close()

    # ==========================================================================
    # ЛОГИРОВАНИЕ СДЕЛОК
    # ==========================================================================

    def log_trade_open(self, deal: Deal, strategy_name: str = None,
                       balance_before: float = None) -> bool:
        """
        Логирование открытия сделки.

        Args:
            deal: Объект сделки
            strategy_name: Название стратегии
            balance_before: Баланс до сделки

        Returns:
            True если успешно
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO trades 
                (trade_id, strategy_name, symbol, direction, amount, duration,
                 open_time, open_price, status, balance_before)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deal.trade_id,
                strategy_name,
                deal.symbol,
                deal.direction,
                deal.amount,
                deal.duration,
                deal.open_time.isoformat(),
                deal.open_price,
                deal.status,
                balance_before
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"[TradeLogger] Ошибка логирования открытия сделки: {e}")
            return False

    def log_trade_close(self, trade_id: str, profit: float,
                        close_price: float = None, balance_after: float = None) -> bool:
        """
        Логирование закрытия сделки.

        Args:
            trade_id: ID сделки
            profit: Прибыль/убыток
            close_price: Цена закрытия
            balance_after: Баланс после сделки

        Returns:
            True если успешно
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            close_time = datetime.now().isoformat()
            status = "win" if profit > 0 else "loss" if profit < 0 else "tie"

            # Сначала получаем amount для расчёта profit_percent
            cursor.execute("SELECT amount FROM trades WHERE trade_id = ?", (trade_id,))
            row = cursor.fetchone()
            amount = row[0] if row else 1
            profit_percent = (profit / amount) * 100 if amount > 0 else 0

            cursor.execute("""
                UPDATE trades 
                SET close_time = ?,
                    close_price = ?,
                    profit = ?,
                    profit_percent = ?,
                    status = ?,
                    balance_after = ?
                WHERE trade_id = ?
            """, (
                close_time,
                close_price,
                profit,
                profit_percent,
                status,
                balance_after,
                trade_id
            ))

            conn.commit()

            # Обновление дневной статистики
            self._update_daily_stats(conn)

            conn.close()
            return True

        except Exception as e:
            print(f"[TradeLogger] Ошибка логирования закрытия сделки: {e}")
            return False

    def log_signal(self, strategy_name: str, symbol: str, direction: str,
                   strength: float = 0, reason: str = None,
                   traded: bool = False) -> bool:
        """
        Логирование сигнала.

        Args:
            strategy_name: Название стратегии
            symbol: Актив
            direction: Направление
            strength: Сила сигнала
            reason: Причина
            traded: Была ли открыта сделка

        Returns:
            True если успешно
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO signals 
                (strategy_name, symbol, direction, strength, reason, timestamp, traded)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_name,
                symbol,
                direction,
                strength,
                reason,
                datetime.now().isoformat(),
                1 if traded else 0
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"[TradeLogger] Ошибка логирования сигнала: {e}")
            return False

    def _update_daily_stats(self, conn: sqlite3.Connection):
        """Обновление дневной статистики."""
        cursor = conn.cursor()
        today = datetime.now().date().isoformat()

        # Получаем все сделки за сегодня
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN profit > 0 THEN profit ELSE 0 END) as total_profit,
                SUM(CASE WHEN profit < 0 THEN ABS(profit) ELSE 0 END) as total_loss,
                MAX(profit) as best_trade,
                MIN(profit) as worst_trade
            FROM trades
            WHERE DATE(open_time) = ? AND status IN ('win', 'loss', 'tie')
        """, (today,))

        row = cursor.fetchone()

        if row and row[0] > 0:
            total = row[0]
            wins = row[1] or 0
            losses = row[2] or 0
            total_profit = row[3] or 0
            total_loss = row[4] or 0
            best_trade = row[5] or 0
            worst_trade = row[6] or 0

            win_rate = (wins / total) * 100 if total > 0 else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

            cursor.execute("""
                INSERT OR REPLACE INTO daily_stats 
                (date, total_trades, winning_trades, losing_trades,
                 total_profit, total_loss, win_rate, profit_factor,
                 best_trade, worst_trade, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                today, total, wins, losses,
                total_profit, total_loss, win_rate,
                profit_factor if profit_factor != float('inf') else None,
                best_trade, worst_trade
            ))

    # ==========================================================================
    # ПОЛУЧЕНИЕ ДАННЫХ
    # ==========================================================================

    def get_trades(self, limit: int = 100, symbol: str = None,
                   status: str = None, days: int = None) -> List[Dict]:
        """
        Получение списка сделок.

        Args:
            limit: Максимальное количество
            symbol: Фильтр по активу
            status: Фильтр по статусу
            days: Фильтр по дням

        Returns:
            Список сделок
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if status:
            query += " AND status = ?"
            params.append(status)

        if days:
            query += " AND open_time >= datetime('now', ?)"
            params.append(f"-{days} days")

        query += " ORDER BY open_time DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        trades = [dict(row) for row in rows]

        conn.close()
        return trades

    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """Получение сделки по ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()

        conn.close()

        return dict(row) if row else None

    def get_signals(self, limit: int = 100, strategy_name: str = None,
                    days: int = None) -> List[Dict]:
        """Получение списка сигналов."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM signals WHERE 1=1"
        params = []

        if strategy_name:
            query += " AND strategy_name = ?"
            params.append(strategy_name)

        if days:
            query += " AND timestamp >= datetime('now', ?)"
            params.append(f"-{days} days")

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """Получение дневной статистики."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM daily_stats 
            WHERE date >= date('now', ?)
            ORDER BY date DESC
        """, (f"-{days} days",))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ==========================================================================
    # СТАТИСТИКА
    # ==========================================================================

    def get_summary(self, days: int = 30) -> Dict:
        """
        Получение сводной статистики.

        Args:
            days: Период в днях

        Returns:
            Словарь со статистикой
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Общая статистика
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit,
                MAX(profit) as best_trade,
                MIN(profit) as worst_trade,
                AVG(profit_percent) as avg_profit_percent
            FROM trades
            WHERE open_time >= datetime('now', ?) AND status IN ('win', 'loss', 'tie')
        """, (f"-{days} days",))

        row = cursor.fetchone()
        stats = dict(row) if row else {}

        # Win rate
        total = stats.get('total_trades', 0) or 0
        wins = stats.get('wins', 0) or 0
        stats['win_rate'] = (wins / total * 100) if total > 0 else 0

        # Profit factor
        total_profit = stats.get('total_profit', 0) or 0
        cursor.execute("""
            SELECT SUM(ABS(profit)) as total_loss
            FROM trades
            WHERE open_time >= datetime('now', ?) AND profit < 0
        """, (f"-{days} days",))
        row = cursor.fetchone()
        total_loss = row[0] if row and row[0] else 0
        stats['profit_factor'] = total_profit / total_loss if total_loss > 0 else float('inf')

        # Статистика по стратегиям
        cursor.execute("""
            SELECT 
                strategy_name,
                COUNT(*) as trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(profit) as total_profit
            FROM trades
            WHERE open_time >= datetime('now', ?) AND strategy_name IS NOT NULL
            GROUP BY strategy_name
        """, (f"-{days} days",))

        stats['by_strategy'] = [dict(row) for row in cursor.fetchall()]

        # Статистика по активам
        cursor.execute("""
            SELECT 
                symbol,
                COUNT(*) as trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(profit) as total_profit
            FROM trades
            WHERE open_time >= datetime('now', ?)
            GROUP BY symbol
        """, (f"-{days} days",))

        stats['by_symbol'] = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return stats

    def get_today_stats(self) -> Dict:
        """Статистика за сегодня."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM daily_stats WHERE date = date('now')
        """)

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0,
            'win_rate': 0
        }

    # ==========================================================================
    # ЭКСПОРТ / ИМПОРТ
    # ==========================================================================

    def export_to_csv(self, filepath: str, days: int = 30) -> bool:
        """Экспорт сделок в CSV."""
        try:
            trades = self.get_trades(days=days, limit=10000)

            if not trades:
                return False

            with open(filepath, 'w', encoding='utf-8') as f:
                # Заголовок
                headers = trades[0].keys()
                f.write(','.join(headers) + '\n')

                # Данные
                for trade in trades:
                    values = [str(v) if v is not None else '' for v in trade.values()]
                    f.write(','.join(values) + '\n')

            return True

        except Exception as e:
            print(f"[TradeLogger] Ошибка экспорта в CSV: {e}")
            return False

    def clear_old_trades(self, days: int = 90) -> int:
        """
        Удаление старых сделок.

        Args:
            days: Удалять сделки старше N дней

        Returns:
            Количество удалённых записей
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM trades 
            WHERE open_time < datetime('now', ?)
        """, (f"-{days} days",))

        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted


__all__ = ["TradeLogger"]
