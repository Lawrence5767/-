"""
MetaTrader 5 Service Layer
Handles all communication with the MT5 terminal for XAU/USD tracking.
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional


SYMBOL = "XAUUSD"


@dataclass
class PositionInfo:
    ticket: int
    symbol: str
    type: str  # "BUY" or "SELL"
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
    entry: str  # "IN", "OUT", "INOUT"

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


ORDER_TYPE_MAP = {
    mt5.ORDER_TYPE_BUY: "BUY",
    mt5.ORDER_TYPE_SELL: "SELL",
    mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
    mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
    mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
    mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
    mt5.ORDER_TYPE_BUY_STOP_LIMIT: "BUY_STOP_LIMIT",
    mt5.ORDER_TYPE_SELL_STOP_LIMIT: "SELL_STOP_LIMIT",
}

DEAL_TYPE_MAP = {
    mt5.DEAL_TYPE_BUY: "BUY",
    mt5.DEAL_TYPE_SELL: "SELL",
    mt5.DEAL_TYPE_BALANCE: "BALANCE",
    mt5.DEAL_TYPE_CREDIT: "CREDIT",
    mt5.DEAL_TYPE_CHARGE: "CHARGE",
    mt5.DEAL_TYPE_CORRECTION: "CORRECTION",
}

DEAL_ENTRY_MAP = {
    mt5.DEAL_ENTRY_IN: "IN",
    mt5.DEAL_ENTRY_OUT: "OUT",
    mt5.DEAL_ENTRY_INOUT: "INOUT",
    mt5.DEAL_ENTRY_OUT_BY: "OUT_BY",
}


def _format_time(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


class MT5Service:
    def __init__(self):
        self._connected = False

    def connect(self, path: Optional[str] = None, login: Optional[int] = None,
                password: Optional[str] = None, server: Optional[str] = None) -> bool:
        kwargs = {}
        if path:
            kwargs["path"] = path
        if login:
            kwargs["login"] = login
        if password:
            kwargs["password"] = password
        if server:
            kwargs["server"] = server

        if not mt5.initialize(**kwargs):
            error = mt5.last_error()
            raise ConnectionError(f"MT5 initialization failed: {error}")

        self._connected = True
        return True

    def disconnect(self):
        mt5.shutdown()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        terminal = mt5.terminal_info()
        return terminal is not None

    def get_account_info(self) -> AccountInfo:
        info = mt5.account_info()
        if info is None:
            raise RuntimeError("Failed to get account info")
        return AccountInfo(
            login=info.login,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level if info.margin_level else 0.0,
            profit=info.profit,
            currency=info.currency,
            server=info.server,
            name=info.name,
        )

    def get_symbol_price(self) -> dict:
        tick = mt5.symbol_info_tick(SYMBOL)
        if tick is None:
            raise RuntimeError(f"Failed to get tick for {SYMBOL}")
        return {
            "symbol": SYMBOL,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": round(tick.ask - tick.bid, 2),
            "time": _format_time(tick.time),
        }

    def get_open_positions(self) -> list[PositionInfo]:
        positions = mt5.positions_get(symbol=SYMBOL)
        if positions is None:
            return []
        result = []
        for p in positions:
            result.append(PositionInfo(
                ticket=p.ticket,
                symbol=p.symbol,
                type="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                volume=p.volume,
                open_price=p.price_open,
                current_price=p.price_current,
                sl=p.sl,
                tp=p.tp,
                profit=p.profit,
                swap=p.swap,
                commission=p.commission if hasattr(p, 'commission') else 0.0,
                open_time=_format_time(p.time),
                magic=p.magic,
                comment=p.comment,
            ))
        return result

    def get_pending_orders(self) -> list[OrderInfo]:
        orders = mt5.orders_get(symbol=SYMBOL)
        if orders is None:
            return []
        result = []
        for o in orders:
            result.append(OrderInfo(
                ticket=o.ticket,
                symbol=o.symbol,
                type=ORDER_TYPE_MAP.get(o.type, f"UNKNOWN({o.type})"),
                volume=o.volume_current,
                price=o.price_open,
                sl=o.sl,
                tp=o.tp,
                time_setup=_format_time(o.time_setup),
                magic=o.magic,
                comment=o.comment,
            ))
        return result

    def get_trade_history(self, days: int = 30) -> list[DealInfo]:
        date_from = datetime.now() - timedelta(days=days)
        date_to = datetime.now()
        deals = mt5.history_deals_get(date_from, date_to, group=f"*{SYMBOL}*")
        if deals is None:
            return []
        result = []
        for d in deals:
            result.append(DealInfo(
                ticket=d.ticket,
                order=d.order,
                symbol=d.symbol,
                type=DEAL_TYPE_MAP.get(d.type, f"UNKNOWN({d.type})"),
                volume=d.volume,
                price=d.price,
                profit=d.profit,
                swap=d.swap,
                commission=d.commission,
                fee=d.fee,
                time=_format_time(d.time),
                magic=d.magic,
                comment=d.comment,
                entry=DEAL_ENTRY_MAP.get(d.entry, f"UNKNOWN({d.entry})"),
            ))
        return result

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

        # Calculate max drawdown from cumulative P&L
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for d in closing_deals:
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
            "win_rate": round(len(winners) / len(closing_deals) * 100, 2) if closing_deals else 0.0,
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
