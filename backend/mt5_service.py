"""
XAU/USD Trading Tracker - Data Store Service
Stores all trade data pushed from the MT5 Expert Advisor in SQLite.
Works on macOS/Linux/Windows - no MetaTrader5 Python package needed.
"""

import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")

# Thread-local storage for SQLite connections
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PositionInfo:
    ticket: int
    symbol: str
    type: str
    volume: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float
    swap: float
    commission: float
    open_time: str
    magic: int
    comment: str

    def to_dict(self):
        return asdict(self)


@dataclass
class OrderInfo:
    ticket: int
    symbol: str
    type: str
    volume: float
    price: float
    sl: float
    tp: float
    time_setup: str
    magic: int
    comment: str

    def to_dict(self):
        return asdict(self)


@dataclass
class DealInfo:
    ticket: int
    order: int
    symbol: str
    type: str
    volume: float
    price: float
    profit: float
    swap: float
    commission: float
    fee: float
    time: str
    magic: int
    comment: str
    entry: str

    def to_dict(self):
        return asdict(self)


@dataclass
class AccountInfo:
    login: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit: float
    currency: str
    server: str
    name: str

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# DataStore
# ---------------------------------------------------------------------------


class DataStore:
    """SQLite-backed data store for XAU/USD trade data pushed from MT5 EA."""

    def __init__(self):
        self._last_push: Optional[str] = None
        self._init_db()

    def _init_db(self):
        conn = _get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                login INTEGER,
                balance REAL,
                equity REAL,
                margin REAL,
                free_margin REAL,
                margin_level REAL,
                profit REAL,
                currency TEXT,
                server TEXT,
                name TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS price (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                symbol TEXT,
                bid REAL,
                ask REAL,
                spread REAL,
                time TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS positions (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT,
                type TEXT,
                volume REAL,
                open_price REAL,
                current_price REAL,
                sl REAL,
                tp REAL,
                profit REAL,
                swap REAL,
                commission REAL,
                open_time TEXT,
                magic INTEGER,
                comment TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT,
                type TEXT,
                volume REAL,
                price REAL,
                sl REAL,
                tp REAL,
                time_setup TEXT,
                magic INTEGER,
                comment TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS deals (
                ticket INTEGER PRIMARY KEY,
                deal_order INTEGER,
                symbol TEXT,
                type TEXT,
                volume REAL,
                price REAL,
                profit REAL,
                swap REAL,
                commission REAL,
                fee REAL,
                time TEXT,
                magic INTEGER,
                comment TEXT,
                entry TEXT,
                updated_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_deals_time ON deals(time);
            CREATE INDEX IF NOT EXISTS idx_deals_entry ON deals(entry);
        """)
        conn.commit()

    @property
    def is_connected(self) -> bool:
        if self._last_push is None:
            return False
        try:
            last = datetime.fromisoformat(self._last_push)
            return (datetime.now() - last).total_seconds() < 30
        except (ValueError, TypeError):
            return False

    @property
    def last_push_time(self) -> Optional[str]:
        return self._last_push

    # ----- Ingest from EA -----

    def push_snapshot(self, data: dict):
        """
        Accept a full snapshot from the EA containing:
        - account: {...}
        - price: {...}
        - positions: [...]
        - orders: [...]
        - deals: [...] (optional, for history)
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._last_push = now
        conn = _get_conn()

        # Account
        acct = data.get("account")
        if acct:
            conn.execute(
                """
                INSERT INTO account (id, login, balance, equity, margin, free_margin,
                    margin_level, profit, currency, server, name, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    login=excluded.login, balance=excluded.balance, equity=excluded.equity,
                    margin=excluded.margin, free_margin=excluded.free_margin,
                    margin_level=excluded.margin_level, profit=excluded.profit,
                    currency=excluded.currency, server=excluded.server,
                    name=excluded.name, updated_at=excluded.updated_at
            """,
                (
                    acct.get("login", 0),
                    acct.get("balance", 0),
                    acct.get("equity", 0),
                    acct.get("margin", 0),
                    acct.get("free_margin", 0),
                    acct.get("margin_level", 0),
                    acct.get("profit", 0),
                    acct.get("currency", "USD"),
                    acct.get("server", ""),
                    acct.get("name", ""),
                    now,
                ),
            )

        # Price
        price = data.get("price")
        if price:
            conn.execute(
                """
                INSERT INTO price (id, symbol, bid, ask, spread, time, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol=excluded.symbol, bid=excluded.bid, ask=excluded.ask,
                    spread=excluded.spread, time=excluded.time, updated_at=excluded.updated_at
            """,
                (
                    price.get("symbol", "XAUUSD"),
                    price.get("bid", 0),
                    price.get("ask", 0),
                    price.get("spread", 0),
                    price.get("time", now),
                    now,
                ),
            )

        # Positions - replace all
        positions = data.get("positions")
        if positions is not None:
            conn.execute("DELETE FROM positions")
            for p in positions:
                conn.execute(
                    """
                    INSERT INTO positions (ticket, symbol, type, volume, open_price,
                        current_price, sl, tp, profit, swap, commission, open_time,
                        magic, comment, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        p.get("ticket", 0),
                        p.get("symbol", "XAUUSD"),
                        p.get("type", ""),
                        p.get("volume", 0),
                        p.get("open_price", 0),
                        p.get("current_price", 0),
                        p.get("sl", 0),
                        p.get("tp", 0),
                        p.get("profit", 0),
                        p.get("swap", 0),
                        p.get("commission", 0),
                        p.get("open_time", now),
                        p.get("magic", 0),
                        p.get("comment", ""),
                        now,
                    ),
                )

        # Orders - replace all
        orders = data.get("orders")
        if orders is not None:
            conn.execute("DELETE FROM orders")
            for o in orders:
                conn.execute(
                    """
                    INSERT INTO orders (ticket, symbol, type, volume, price,
                        sl, tp, time_setup, magic, comment, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        o.get("ticket", 0),
                        o.get("symbol", "XAUUSD"),
                        o.get("type", ""),
                        o.get("volume", 0),
                        o.get("price", 0),
                        o.get("sl", 0),
                        o.get("tp", 0),
                        o.get("time_setup", now),
                        o.get("magic", 0),
                        o.get("comment", ""),
                        now,
                    ),
                )

        # Deals (append/upsert)
        deals = data.get("deals")
        if deals:
            for d in deals:
                conn.execute(
                    """
                    INSERT INTO deals (ticket, deal_order, symbol, type, volume,
                        price, profit, swap, commission, fee, time, magic,
                        comment, entry, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticket) DO UPDATE SET
                        profit=excluded.profit, swap=excluded.swap,
                        commission=excluded.commission, fee=excluded.fee,
                        updated_at=excluded.updated_at
                """,
                    (
                        d.get("ticket", 0),
                        d.get("order", 0),
                        d.get("symbol", "XAUUSD"),
                        d.get("type", ""),
                        d.get("volume", 0),
                        d.get("price", 0),
                        d.get("profit", 0),
                        d.get("swap", 0),
                        d.get("commission", 0),
                        d.get("fee", 0),
                        d.get("time", now),
                        d.get("magic", 0),
                        d.get("comment", ""),
                        d.get("entry", ""),
                        now,
                    ),
                )

        conn.commit()

    # ----- Read methods -----

    def get_account_info(self) -> Optional[AccountInfo]:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
        if not row:
            return None
        return AccountInfo(
            login=row["login"],
            balance=row["balance"],
            equity=row["equity"],
            margin=row["margin"],
            free_margin=row["free_margin"],
            margin_level=row["margin_level"],
            profit=row["profit"],
            currency=row["currency"],
            server=row["server"],
            name=row["name"],
        )

    def get_symbol_price(self) -> Optional[dict]:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM price WHERE id = 1").fetchone()
        if not row:
            return None
        return {
            "symbol": row["symbol"],
            "bid": row["bid"],
            "ask": row["ask"],
            "spread": row["spread"],
            "time": row["time"],
        }

    def get_open_positions(self) -> list[PositionInfo]:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM positions ORDER BY open_time DESC"
        ).fetchall()
        return [
            PositionInfo(
                ticket=r["ticket"],
                symbol=r["symbol"],
                type=r["type"],
                volume=r["volume"],
                open_price=r["open_price"],
                current_price=r["current_price"],
                sl=r["sl"],
                tp=r["tp"],
                profit=r["profit"],
                swap=r["swap"],
                commission=r["commission"],
                open_time=r["open_time"],
                magic=r["magic"],
                comment=r["comment"],
            )
            for r in rows
        ]

    def get_pending_orders(self) -> list[OrderInfo]:
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM orders ORDER BY time_setup DESC").fetchall()
        return [
            OrderInfo(
                ticket=r["ticket"],
                symbol=r["symbol"],
                type=r["type"],
                volume=r["volume"],
                price=r["price"],
                sl=r["sl"],
                tp=r["tp"],
                time_setup=r["time_setup"],
                magic=r["magic"],
                comment=r["comment"],
            )
            for r in rows
        ]

    def get_trade_history(self, days: int = 30) -> list[DealInfo]:
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute(
            "SELECT * FROM deals WHERE time >= ? ORDER BY time DESC", (cutoff,)
        ).fetchall()
        return [
            DealInfo(
                ticket=r["ticket"],
                order=r["deal_order"],
                symbol=r["symbol"],
                type=r["type"],
                volume=r["volume"],
                price=r["price"],
                profit=r["profit"],
                swap=r["swap"],
                commission=r["commission"],
                fee=r["fee"],
                time=r["time"],
                magic=r["magic"],
                comment=r["comment"],
                entry=r["entry"],
            )
            for r in rows
        ]

    def compute_analytics(self, days: int = 30) -> dict:
        deals = self.get_trade_history(days)
        closing_deals = [d for d in deals if d.entry == "OUT"]

        if not closing_deals:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "total_loss": 0.0,
                "net_pnl": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "total_volume": 0.0,
                "total_commission": 0.0,
                "total_swap": 0.0,
                "max_drawdown": 0.0,
                "period_days": days,
            }

        winners = [d for d in closing_deals if d.profit > 0]
        losers = [d for d in closing_deals if d.profit < 0]

        total_profit = sum(d.profit for d in winners)
        total_loss = abs(sum(d.profit for d in losers))
        net_pnl = sum(d.profit for d in closing_deals)

        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for d in sorted(closing_deals, key=lambda x: x.time):
            cumulative += d.profit
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "total_trades": len(closing_deals),
            "winning_trades": len(winners),
            "losing_trades": len(losers),
            "win_rate": round(len(winners) / len(closing_deals) * 100, 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "net_pnl": round(net_pnl, 2),
            "avg_profit": round(total_profit / len(winners), 2) if winners else 0.0,
            "avg_loss": round(total_loss / len(losers), 2) if losers else 0.0,
            "profit_factor": (
                round(total_profit / total_loss, 2) if total_loss > 0 else float("inf")
            ),
            "largest_win": round(max((d.profit for d in winners), default=0.0), 2),
            "largest_loss": round(min((d.profit for d in losers), default=0.0), 2),
            "total_volume": round(sum(d.volume for d in closing_deals), 2),
            "total_commission": round(sum(d.commission for d in closing_deals), 2),
            "total_swap": round(sum(d.swap for d in closing_deals), 2),
            "max_drawdown": round(max_dd, 2),
            "period_days": days,
        }

    # ----- Demo data -----

    def load_demo_data(self):
        """Load sample data for testing the dashboard without a live MT5 connection."""
        import random

        now = datetime.now()

        demo = {
            "account": {
                "login": 12345678,
                "balance": 10000.00,
                "equity": 10245.80,
                "margin": 1520.00,
                "free_margin": 8725.80,
                "margin_level": 674.07,
                "profit": 245.80,
                "currency": "USD",
                "server": "Demo-Server",
                "name": "Demo Account",
            },
            "price": {
                "symbol": "XAUUSD",
                "bid": 2935.45,
                "ask": 2935.75,
                "spread": 0.30,
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "positions": [
                {
                    "ticket": 100001,
                    "symbol": "XAUUSD",
                    "type": "BUY",
                    "volume": 0.10,
                    "open_price": 2920.50,
                    "current_price": 2935.45,
                    "sl": 2910.00,
                    "tp": 2960.00,
                    "profit": 149.50,
                    "swap": -2.30,
                    "commission": -3.50,
                    "open_time": (now - timedelta(hours=6)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "magic": 0,
                    "comment": "Manual trade",
                },
                {
                    "ticket": 100002,
                    "symbol": "XAUUSD",
                    "type": "SELL",
                    "volume": 0.05,
                    "open_price": 2940.20,
                    "current_price": 2935.75,
                    "sl": 2955.00,
                    "tp": 2910.00,
                    "profit": 22.25,
                    "swap": -1.10,
                    "commission": -1.75,
                    "open_time": (now - timedelta(hours=2)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "magic": 0,
                    "comment": "",
                },
            ],
            "orders": [
                {
                    "ticket": 200001,
                    "symbol": "XAUUSD",
                    "type": "BUY_LIMIT",
                    "volume": 0.10,
                    "price": 2900.00,
                    "sl": 2885.00,
                    "tp": 2950.00,
                    "time_setup": (now - timedelta(hours=1)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "magic": 0,
                    "comment": "Pullback entry",
                },
            ],
            "deals": [],
        }

        # Generate 30 days of deal history
        for i in range(50):
            days_ago = random.randint(0, 29)
            hours_ago = random.randint(0, 23)
            deal_time = now - timedelta(days=days_ago, hours=hours_ago)
            is_buy = random.choice([True, False])
            is_winner = random.random() < 0.55
            volume = round(random.choice([0.01, 0.02, 0.05, 0.10, 0.20]), 2)
            base_price = 2900 + random.uniform(-50, 50)

            # Entry deal
            demo["deals"].append(
                {
                    "ticket": 300000 + i * 2,
                    "order": 400000 + i,
                    "symbol": "XAUUSD",
                    "type": "BUY" if is_buy else "SELL",
                    "volume": volume,
                    "price": round(base_price, 2),
                    "profit": 0.0,
                    "swap": 0.0,
                    "commission": round(-volume * 35, 2),
                    "fee": 0.0,
                    "time": deal_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "magic": 0,
                    "comment": "",
                    "entry": "IN",
                }
            )

            # Exit deal
            if is_winner:
                pnl = round(random.uniform(20, 300) * volume * 10, 2)
            else:
                pnl = round(-random.uniform(15, 250) * volume * 10, 2)

            exit_time = deal_time + timedelta(minutes=random.randint(5, 480))
            exit_price = base_price + (pnl / (volume * 100))

            demo["deals"].append(
                {
                    "ticket": 300000 + i * 2 + 1,
                    "order": 400000 + i,
                    "symbol": "XAUUSD",
                    "type": "SELL" if is_buy else "BUY",
                    "volume": volume,
                    "price": round(exit_price, 2),
                    "profit": pnl,
                    "swap": round(random.uniform(-5, 0), 2),
                    "commission": round(-volume * 35, 2),
                    "fee": 0.0,
                    "time": exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "magic": 0,
                    "comment": "",
                    "entry": "OUT",
                }
            )

        self.push_snapshot(demo)
        return {
            "status": "demo_loaded",
            "positions": len(demo["positions"]),
            "orders": len(demo["orders"]),
            "deals": len(demo["deals"]),
        }
