"""
XAU/USD Trading Tracker - Data Store Service
Stores all trade data pushed from the MT5 Expert Advisor in SQLite.
Supports CSV import from MT5/Tickmill for trade history analysis.
Works on macOS/Linux/Windows - no MetaTrader5 Python package needed.
"""

import csv
import io
import sqlite3
import json
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
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
            conn.execute("""
                INSERT INTO account (id, login, balance, equity, margin, free_margin,
                    margin_level, profit, currency, server, name, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    login=excluded.login, balance=excluded.balance, equity=excluded.equity,
                    margin=excluded.margin, free_margin=excluded.free_margin,
                    margin_level=excluded.margin_level, profit=excluded.profit,
                    currency=excluded.currency, server=excluded.server,
                    name=excluded.name, updated_at=excluded.updated_at
            """, (
                acct.get("login", 0), acct.get("balance", 0), acct.get("equity", 0),
                acct.get("margin", 0), acct.get("free_margin", 0),
                acct.get("margin_level", 0), acct.get("profit", 0),
                acct.get("currency", "USD"), acct.get("server", ""),
                acct.get("name", ""), now,
            ))

        # Price
        price = data.get("price")
        if price:
            conn.execute("""
                INSERT INTO price (id, symbol, bid, ask, spread, time, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol=excluded.symbol, bid=excluded.bid, ask=excluded.ask,
                    spread=excluded.spread, time=excluded.time, updated_at=excluded.updated_at
            """, (
                price.get("symbol", "XAUUSD"), price.get("bid", 0),
                price.get("ask", 0), price.get("spread", 0),
                price.get("time", now), now,
            ))

        # Positions - replace all
        positions = data.get("positions")
        if positions is not None:
            conn.execute("DELETE FROM positions")
            for p in positions:
                conn.execute("""
                    INSERT INTO positions (ticket, symbol, type, volume, open_price,
                        current_price, sl, tp, profit, swap, commission, open_time,
                        magic, comment, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p.get("ticket", 0), p.get("symbol", "XAUUSD"),
                    p.get("type", ""), p.get("volume", 0),
                    p.get("open_price", 0), p.get("current_price", 0),
                    p.get("sl", 0), p.get("tp", 0),
                    p.get("profit", 0), p.get("swap", 0),
                    p.get("commission", 0), p.get("open_time", now),
                    p.get("magic", 0), p.get("comment", ""), now,
                ))

        # Orders - replace all
        orders = data.get("orders")
        if orders is not None:
            conn.execute("DELETE FROM orders")
            for o in orders:
                conn.execute("""
                    INSERT INTO orders (ticket, symbol, type, volume, price,
                        sl, tp, time_setup, magic, comment, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    o.get("ticket", 0), o.get("symbol", "XAUUSD"),
                    o.get("type", ""), o.get("volume", 0),
                    o.get("price", 0), o.get("sl", 0), o.get("tp", 0),
                    o.get("time_setup", now), o.get("magic", 0),
                    o.get("comment", ""), now,
                ))

        # Deals (append/upsert)
        deals = data.get("deals")
        if deals:
            for d in deals:
                conn.execute("""
                    INSERT INTO deals (ticket, deal_order, symbol, type, volume,
                        price, profit, swap, commission, fee, time, magic,
                        comment, entry, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticket) DO UPDATE SET
                        profit=excluded.profit, swap=excluded.swap,
                        commission=excluded.commission, fee=excluded.fee,
                        updated_at=excluded.updated_at
                """, (
                    d.get("ticket", 0), d.get("order", 0),
                    d.get("symbol", "XAUUSD"), d.get("type", ""),
                    d.get("volume", 0), d.get("price", 0),
                    d.get("profit", 0), d.get("swap", 0),
                    d.get("commission", 0), d.get("fee", 0),
                    d.get("time", now), d.get("magic", 0),
                    d.get("comment", ""), d.get("entry", ""), now,
                ))

        conn.commit()

    # ----- Live Price Update -----

    def update_live_price(self, price_data: dict):
        """Update the price table with real-time data from external API."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = _get_conn()
        conn.execute("""
            INSERT INTO price (id, symbol, bid, ask, spread, time, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                symbol=excluded.symbol, bid=excluded.bid, ask=excluded.ask,
                spread=excluded.spread, time=excluded.time, updated_at=excluded.updated_at
        """, (
            price_data.get("symbol", "XAUUSD"),
            price_data.get("bid", 0),
            price_data.get("ask", 0),
            price_data.get("spread", 0),
            price_data.get("time", now),
            now,
        ))
        conn.commit()
        self._last_push = now

    # ----- Read methods -----

    def get_account_info(self) -> Optional[AccountInfo]:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
        if not row:
            return None
        return AccountInfo(
            login=row["login"], balance=row["balance"], equity=row["equity"],
            margin=row["margin"], free_margin=row["free_margin"],
            margin_level=row["margin_level"], profit=row["profit"],
            currency=row["currency"], server=row["server"], name=row["name"],
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
        rows = conn.execute("SELECT * FROM positions ORDER BY open_time DESC").fetchall()
        return [
            PositionInfo(
                ticket=r["ticket"], symbol=r["symbol"], type=r["type"],
                volume=r["volume"], open_price=r["open_price"],
                current_price=r["current_price"], sl=r["sl"], tp=r["tp"],
                profit=r["profit"], swap=r["swap"], commission=r["commission"],
                open_time=r["open_time"], magic=r["magic"], comment=r["comment"],
            )
            for r in rows
        ]

    def get_pending_orders(self) -> list[OrderInfo]:
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM orders ORDER BY time_setup DESC").fetchall()
        return [
            OrderInfo(
                ticket=r["ticket"], symbol=r["symbol"], type=r["type"],
                volume=r["volume"], price=r["price"], sl=r["sl"], tp=r["tp"],
                time_setup=r["time_setup"], magic=r["magic"], comment=r["comment"],
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
                ticket=r["ticket"], order=r["deal_order"], symbol=r["symbol"],
                type=r["type"], volume=r["volume"], price=r["price"],
                profit=r["profit"], swap=r["swap"], commission=r["commission"],
                fee=r["fee"], time=r["time"], magic=r["magic"],
                comment=r["comment"], entry=r["entry"],
            )
            for r in rows
        ]

    def compute_analytics(self, days: int = 30) -> dict:
        deals = self.get_trade_history(days)
        closing_deals = [d for d in deals if d.entry == "OUT"]

        if not closing_deals:
            return {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "win_rate": 0.0, "total_profit": 0.0, "total_loss": 0.0,
                "net_pnl": 0.0, "avg_profit": 0.0, "avg_loss": 0.0,
                "profit_factor": 0.0, "largest_win": 0.0, "largest_loss": 0.0,
                "total_volume": 0.0, "total_commission": 0.0, "total_swap": 0.0,
                "max_drawdown": 0.0, "period_days": days,
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
            "profit_factor": round(total_profit / total_loss, 2) if total_loss > 0 else float("inf"),
            "largest_win": round(max((d.profit for d in winners), default=0.0), 2),
            "largest_loss": round(min((d.profit for d in losers), default=0.0), 2),
            "total_volume": round(sum(d.volume for d in closing_deals), 2),
            "total_commission": round(sum(d.commission for d in closing_deals), 2),
            "total_swap": round(sum(d.swap for d in closing_deals), 2),
            "max_drawdown": round(max_dd, 2),
            "period_days": days,
        }

    # ----- CSV Import -----

    def import_csv(self, file_content: str, csv_format: str = "mt5") -> dict:
        """
        Import trade history from a CSV file.

        Supported formats:
        - "mt5": MetaTrader 5 trade history export (Account History tab -> right-click -> Report as CSV)
        - "tickmill": Tickmill client portal trade history export
        - "generic": Generic CSV with columns: time, type, volume, price, profit, swap, commission, comment
        """
        reader = csv.DictReader(io.StringIO(file_content))
        fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

        if csv_format == "auto":
            csv_format = self._detect_csv_format(fieldnames)

        imported = 0
        skipped = 0
        conn = _get_conn()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for row in reader:
            # Normalize keys to lowercase and strip whitespace
            row = {k.strip().lower(): v.strip() for k, v in row.items()}

            try:
                deal = self._parse_csv_row(row, csv_format)
                if deal is None:
                    skipped += 1
                    continue

                conn.execute("""
                    INSERT INTO deals (ticket, deal_order, symbol, type, volume,
                        price, profit, swap, commission, fee, time, magic,
                        comment, entry, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticket) DO UPDATE SET
                        profit=excluded.profit, swap=excluded.swap,
                        commission=excluded.commission, fee=excluded.fee,
                        updated_at=excluded.updated_at
                """, (
                    deal["ticket"], deal.get("order", 0),
                    deal.get("symbol", "XAUUSD"), deal["type"],
                    deal["volume"], deal["price"],
                    deal["profit"], deal.get("swap", 0),
                    deal.get("commission", 0), deal.get("fee", 0),
                    deal["time"], deal.get("magic", 0),
                    deal.get("comment", ""), deal["entry"], now,
                ))
                imported += 1
            except (ValueError, KeyError) as e:
                skipped += 1

        conn.commit()
        return {
            "status": "imported",
            "format_detected": csv_format,
            "imported": imported,
            "skipped": skipped,
        }

    def _detect_csv_format(self, fieldnames: list[str]) -> str:
        """Auto-detect CSV format based on column headers."""
        fields_set = set(fieldnames)
        # MT5 report has 'deal', 'order', 'symbol', 'type', 'direction', etc.
        if "deal" in fields_set and "direction" in fields_set:
            return "mt5"
        if "deal" in fields_set or "order" in fields_set:
            return "mt5"
        # Tickmill uses 'ticket', 'open time', 'close time', 'symbol', etc.
        if "open time" in fields_set and "close time" in fields_set:
            return "tickmill"
        if "ticket" in fields_set and ("open price" in fields_set or "close price" in fields_set):
            return "tickmill"
        return "generic"

    def _parse_csv_row(self, row: dict, csv_format: str) -> Optional[dict]:
        """Parse a single CSV row into a deal dict."""
        if csv_format == "mt5":
            return self._parse_mt5_row(row)
        elif csv_format == "tickmill":
            return self._parse_tickmill_row(row)
        else:
            return self._parse_generic_row(row)

    def _parse_mt5_row(self, row: dict) -> Optional[dict]:
        """Parse MT5 Account History CSV export row."""
        # MT5 exports typically have: Deal, Order, Time, Type, Direction (IN/OUT),
        # Volume, Price, S/L, T/P, Profit, Commission, Swap, Fee, Comment
        deal_type = row.get("type", "").strip().upper()
        if deal_type not in ("BUY", "SELL"):
            return None

        symbol = row.get("symbol", "").strip()
        if symbol and "XAU" not in symbol.upper() and "GOLD" not in symbol.upper():
            return None

        direction = row.get("direction", row.get("entry", "")).strip().upper()
        if direction not in ("IN", "OUT", "INOUT", "OUT_BY"):
            # Try to infer: if profit != 0, it's probably OUT
            profit = self._parse_float(row.get("profit", "0"))
            direction = "OUT" if profit != 0 else "IN"

        ticket_str = row.get("deal", row.get("ticket", "0"))
        ticket = int(float(ticket_str)) if ticket_str else 0
        if ticket == 0:
            # Generate a ticket from hash of time + type
            time_str = row.get("time", "")
            ticket = abs(hash(time_str + deal_type)) % 2000000000

        return {
            "ticket": ticket,
            "order": int(float(row.get("order", "0") or "0")),
            "symbol": symbol or "XAUUSD",
            "type": deal_type,
            "volume": self._parse_float(row.get("volume", row.get("lot", "0"))),
            "price": self._parse_float(row.get("price", "0")),
            "profit": self._parse_float(row.get("profit", "0")),
            "swap": self._parse_float(row.get("swap", "0")),
            "commission": self._parse_float(row.get("commission", "0")),
            "fee": self._parse_float(row.get("fee", "0")),
            "time": self._normalize_datetime(row.get("time", "")),
            "magic": int(float(row.get("magic", row.get("expert id", "0")) or "0")),
            "comment": row.get("comment", ""),
            "entry": direction,
        }

    def _parse_tickmill_row(self, row: dict) -> Optional[dict]:
        """
        Parse Tickmill client portal CSV export.
        Tickmill exports completed trades with open/close info in one row.
        We create two deals from each row: IN and OUT.
        """
        symbol = row.get("symbol", row.get("instrument", "")).strip()
        if symbol and "XAU" not in symbol.upper() and "GOLD" not in symbol.upper():
            return None

        trade_type = row.get("type", row.get("direction", "")).strip().upper()
        if trade_type not in ("BUY", "SELL"):
            return None

        ticket_str = row.get("ticket", row.get("order", row.get("deal", "0")))
        ticket = int(float(ticket_str)) if ticket_str else 0

        close_time = row.get("close time", row.get("time", ""))
        if not close_time:
            close_time = row.get("open time", "")

        # For Tickmill exports, each row is a completed trade (OUT deal)
        return {
            "ticket": ticket,
            "order": ticket,
            "symbol": symbol or "XAUUSD",
            "type": "SELL" if trade_type == "BUY" else "BUY",  # closing side
            "volume": self._parse_float(row.get("volume", row.get("lot", row.get("lots", "0")))),
            "price": self._parse_float(row.get("close price", row.get("price", "0"))),
            "profit": self._parse_float(row.get("profit", row.get("net profit", "0"))),
            "swap": self._parse_float(row.get("swap", "0")),
            "commission": self._parse_float(row.get("commission", "0")),
            "fee": self._parse_float(row.get("fee", "0")),
            "time": self._normalize_datetime(close_time),
            "magic": 0,
            "comment": row.get("comment", ""),
            "entry": "OUT",
        }

    def _parse_generic_row(self, row: dict) -> Optional[dict]:
        """Parse a generic CSV row with minimal required columns."""
        deal_type = row.get("type", row.get("direction", "")).strip().upper()
        if deal_type not in ("BUY", "SELL"):
            return None

        ticket_str = row.get("ticket", row.get("deal", row.get("order", row.get("id", "0"))))
        ticket = int(float(ticket_str)) if ticket_str else 0
        if ticket == 0:
            time_str = row.get("time", row.get("date", ""))
            ticket = abs(hash(time_str + deal_type)) % 2000000000

        profit = self._parse_float(row.get("profit", row.get("pnl", row.get("p&l", "0"))))
        entry = row.get("entry", row.get("direction_type", "")).strip().upper()
        if entry not in ("IN", "OUT", "INOUT", "OUT_BY"):
            entry = "OUT" if profit != 0 else "IN"

        return {
            "ticket": ticket,
            "order": int(float(row.get("order", "0") or "0")),
            "symbol": row.get("symbol", row.get("instrument", "XAUUSD")),
            "type": deal_type,
            "volume": self._parse_float(row.get("volume", row.get("lot", row.get("lots", row.get("size", "0"))))),
            "price": self._parse_float(row.get("price", row.get("close price", "0"))),
            "profit": profit,
            "swap": self._parse_float(row.get("swap", "0")),
            "commission": self._parse_float(row.get("commission", "0")),
            "fee": self._parse_float(row.get("fee", "0")),
            "time": self._normalize_datetime(row.get("time", row.get("date", row.get("close time", "")))),
            "magic": 0,
            "comment": row.get("comment", ""),
            "entry": entry,
        }

    def _parse_float(self, val: str) -> float:
        """Safely parse a float from various formats."""
        if not val or val == "--" or val == "N/A":
            return 0.0
        val = val.replace(",", "").replace(" ", "").replace("$", "")
        return float(val)

    def _normalize_datetime(self, dt_str: str) -> str:
        """Normalize various datetime formats to YYYY-MM-DD HH:MM:SS."""
        if not dt_str:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        dt_str = dt_str.strip()
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y.%m.%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y.%m.%d %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return dt_str

    # ----- Enhanced Analytics -----

    def compute_advanced_analytics(self, days: int = 365) -> dict:
        """Compute comprehensive trade analytics for XAU/USD history."""
        deals = self.get_trade_history(days)
        closing_deals = [d for d in deals if d.entry == "OUT"]

        basic = self.compute_analytics(days)

        if not closing_deals:
            return {
                **basic,
                "avg_holding_time": "N/A",
                "best_day": "N/A",
                "worst_day": "N/A",
                "consecutive_wins": 0,
                "consecutive_losses": 0,
                "monthly_pnl": [],
                "daily_pnl": [],
                "weekday_stats": [],
                "hourly_stats": [],
                "equity_curve": [],
                "trade_details": [],
            }

        sorted_deals = sorted(closing_deals, key=lambda x: x.time)

        # Equity curve
        equity_curve = []
        cumulative = 0.0
        for d in sorted_deals:
            cumulative += d.profit
            equity_curve.append({
                "time": d.time,
                "equity": round(cumulative, 2),
                "profit": round(d.profit, 2),
            })

        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        for d in sorted_deals:
            if d.profit > 0:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            elif d.profit < 0:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0

        # Monthly P&L
        monthly_map = defaultdict(float)
        for d in sorted_deals:
            try:
                month_key = d.time[:7]  # YYYY-MM
                monthly_map[month_key] += d.profit
            except (IndexError, TypeError):
                pass
        monthly_pnl = [
            {"month": k, "pnl": round(v, 2)}
            for k, v in sorted(monthly_map.items())
        ]

        # Weekly P&L (by calendar week)
        weekly_map = defaultdict(float)
        for d in sorted_deals:
            try:
                dt = datetime.strptime(d.time[:10], "%Y-%m-%d")
                week_key = dt.strftime("%Y-W%W")
                weekly_map[week_key] += d.profit
            except (ValueError, TypeError):
                pass
        weekly_pnl = [
            {"week": k, "pnl": round(v, 2)}
            for k, v in sorted(weekly_map.items())
        ]

        # Daily P&L
        daily_map = defaultdict(float)
        for d in sorted_deals:
            try:
                day_key = d.time[:10]  # YYYY-MM-DD
                daily_map[day_key] += d.profit
            except (IndexError, TypeError):
                pass
        daily_pnl = [
            {"date": k, "pnl": round(v, 2)}
            for k, v in sorted(daily_map.items())
        ]

        # Performance by day of week
        weekday_profits = defaultdict(list)
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for d in sorted_deals:
            try:
                dt = datetime.strptime(d.time[:10], "%Y-%m-%d")
                weekday_profits[dt.weekday()].append(d.profit)
            except (ValueError, TypeError):
                pass
        weekday_stats = []
        for i in range(7):
            profs = weekday_profits.get(i, [])
            if profs:
                wins = len([p for p in profs if p > 0])
                weekday_stats.append({
                    "day": weekday_names[i],
                    "trades": len(profs),
                    "total_pnl": round(sum(profs), 2),
                    "avg_pnl": round(sum(profs) / len(profs), 2),
                    "win_rate": round(wins / len(profs) * 100, 1),
                })

        # Performance by hour
        hourly_profits = defaultdict(list)
        for d in sorted_deals:
            try:
                dt = datetime.strptime(d.time, "%Y-%m-%d %H:%M:%S")
                hourly_profits[dt.hour].append(d.profit)
            except (ValueError, TypeError):
                pass
        hourly_stats = []
        for h in range(24):
            profs = hourly_profits.get(h, [])
            if profs:
                wins = len([p for p in profs if p > 0])
                hourly_stats.append({
                    "hour": f"{h:02d}:00",
                    "trades": len(profs),
                    "total_pnl": round(sum(profs), 2),
                    "avg_pnl": round(sum(profs) / len(profs), 2),
                    "win_rate": round(wins / len(profs) * 100, 1),
                })

        # Best and worst trading days
        best_day = max(daily_pnl, key=lambda x: x["pnl"]) if daily_pnl else {"date": "N/A", "pnl": 0}
        worst_day = min(daily_pnl, key=lambda x: x["pnl"]) if daily_pnl else {"date": "N/A", "pnl": 0}

        # Average holding time (from IN to OUT deals matched by order)
        entry_times = {}
        holding_times = []
        all_deals_sorted = sorted(deals, key=lambda x: x.time)
        for d in all_deals_sorted:
            if d.entry == "IN":
                entry_times[d.order] = d.time
            elif d.entry == "OUT" and d.order in entry_times:
                try:
                    t_in = datetime.strptime(entry_times[d.order], "%Y-%m-%d %H:%M:%S")
                    t_out = datetime.strptime(d.time, "%Y-%m-%d %H:%M:%S")
                    holding_times.append((t_out - t_in).total_seconds())
                except (ValueError, TypeError):
                    pass

        avg_holding_seconds = sum(holding_times) / len(holding_times) if holding_times else 0
        if avg_holding_seconds > 86400:
            avg_holding = f"{avg_holding_seconds / 86400:.1f} days"
        elif avg_holding_seconds > 3600:
            avg_holding = f"{avg_holding_seconds / 3600:.1f} hours"
        elif avg_holding_seconds > 60:
            avg_holding = f"{avg_holding_seconds / 60:.0f} minutes"
        elif avg_holding_seconds > 0:
            avg_holding = f"{avg_holding_seconds:.0f} seconds"
        else:
            avg_holding = "N/A"

        # Risk-reward ratio (avg win / avg loss)
        avg_win = basic["avg_profit"]
        avg_loss = basic["avg_loss"]
        risk_reward = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0

        # Drawdown periods
        peak = 0.0
        max_dd = 0.0
        dd_start = None
        dd_end = None
        dd_peak_time = None
        cumulative = 0.0
        drawdown_periods = []
        in_drawdown = False

        for d in sorted_deals:
            cumulative += d.profit
            if cumulative > peak:
                if in_drawdown and dd_start:
                    drawdown_periods.append({
                        "start": dd_start,
                        "end": d.time,
                        "depth": round(peak - (cumulative - d.profit), 2),
                    })
                peak = cumulative
                in_drawdown = False
                dd_start = None
            else:
                if not in_drawdown:
                    dd_start = d.time
                    in_drawdown = True
                dd = peak - cumulative
                if dd > max_dd:
                    max_dd = dd

        # Trade details for the table
        trade_details = []
        for d in sorted_deals:
            net = d.profit + d.swap + d.commission
            trade_details.append({
                "ticket": d.ticket,
                "time": d.time,
                "type": d.type,
                "volume": d.volume,
                "price": d.price,
                "profit": round(d.profit, 2),
                "swap": round(d.swap, 2),
                "commission": round(d.commission, 2),
                "net": round(net, 2),
                "comment": d.comment,
            })

        return {
            **basic,
            "risk_reward_ratio": risk_reward,
            "avg_holding_time": avg_holding,
            "best_day": best_day,
            "worst_day": worst_day,
            "consecutive_wins": max_consec_wins,
            "consecutive_losses": max_consec_losses,
            "monthly_pnl": monthly_pnl,
            "weekly_pnl": weekly_pnl,
            "daily_pnl": daily_pnl,
            "weekday_stats": weekday_stats,
            "hourly_stats": hourly_stats,
            "equity_curve": equity_curve,
            "trade_details": trade_details,
            "drawdown_periods": drawdown_periods[:10],  # Top 10
        }

    def clear_deals(self) -> dict:
        """Clear all deal history from the database."""
        conn = _get_conn()
        count = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        conn.execute("DELETE FROM deals")
        conn.commit()
        return {"status": "cleared", "deleted": count}

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
                    "open_time": (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
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
                    "open_time": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
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
                    "time_setup": (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
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
            demo["deals"].append({
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
            })

            # Exit deal
            if is_winner:
                pnl = round(random.uniform(20, 300) * volume * 10, 2)
            else:
                pnl = round(-random.uniform(15, 250) * volume * 10, 2)

            exit_time = deal_time + timedelta(minutes=random.randint(5, 480))
            exit_price = base_price + (pnl / (volume * 100))

            demo["deals"].append({
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
            })

        self.push_snapshot(demo)
        return {"status": "demo_loaded", "positions": len(demo["positions"]),
                "orders": len(demo["orders"]), "deals": len(demo["deals"])}
