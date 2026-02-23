"""
XAU/USD Trading Tracker - FastAPI Backend
Connects to MetaTrader 5 and serves trade data via REST API + WebSocket.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from mt5_service import MT5Service


# --- Configuration ---
MT5_PATH = os.environ.get("MT5_PATH", "")
MT5_LOGIN = int(os.environ.get("MT5_LOGIN", "0")) or None
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "") or None
MT5_SERVER = os.environ.get("MT5_SERVER", "") or None

# Alert thresholds (configurable via API)
alert_config = {
    "price_upper": None,
    "price_lower": None,
    "pnl_upper": None,
    "pnl_lower": None,
    "margin_level_lower": None,
}


# --- App setup ---
mt5 = MT5Service()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to MT5
    try:
        mt5.connect(
            path=MT5_PATH if MT5_PATH else None,
            login=MT5_LOGIN,
            password=MT5_PASSWORD,
            server=MT5_SERVER,
        )
        print("[MT5] Connected successfully")
    except ConnectionError as e:
        print(f"[MT5] Warning: Could not connect on startup - {e}")
        print("[MT5] Use POST /api/connect to connect manually")
    yield
    # Shutdown
    mt5.disconnect()
    print("[MT5] Disconnected")


app = FastAPI(title="XAU/USD Trading Tracker", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# --- REST Endpoints ---

@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.post("/api/connect")
async def connect_mt5(
    path: Optional[str] = None,
    login: Optional[int] = None,
    password: Optional[str] = None,
    server: Optional[str] = None,
):
    try:
        mt5.connect(path=path, login=login, password=password, server=server)
        return {"status": "connected"}
    except ConnectionError as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/status")
async def get_status():
    return {"connected": mt5.is_connected}


@app.get("/api/account")
async def get_account():
    try:
        info = mt5.get_account_info()
        return info.to_dict()
    except RuntimeError as e:
        return {"error": str(e)}


@app.get("/api/price")
async def get_price():
    try:
        return mt5.get_symbol_price()
    except RuntimeError as e:
        return {"error": str(e)}


@app.get("/api/positions")
async def get_positions():
    try:
        positions = mt5.get_open_positions()
        return {"positions": [p.to_dict() for p in positions]}
    except RuntimeError as e:
        return {"error": str(e)}


@app.get("/api/orders")
async def get_orders():
    try:
        orders = mt5.get_pending_orders()
        return {"orders": [o.to_dict() for o in orders]}
    except RuntimeError as e:
        return {"error": str(e)}


@app.get("/api/history")
async def get_history(days: int = Query(default=30, ge=1, le=365)):
    try:
        deals = mt5.get_trade_history(days)
        return {"deals": [d.to_dict() for d in deals], "count": len(deals)}
    except RuntimeError as e:
        return {"error": str(e)}


@app.get("/api/analytics")
async def get_analytics(days: int = Query(default=30, ge=1, le=365)):
    try:
        return mt5.compute_analytics(days)
    except RuntimeError as e:
        return {"error": str(e)}


@app.get("/api/alerts")
async def get_alerts():
    return alert_config


@app.post("/api/alerts")
async def set_alerts(
    price_upper: Optional[float] = None,
    price_lower: Optional[float] = None,
    pnl_upper: Optional[float] = None,
    pnl_lower: Optional[float] = None,
    margin_level_lower: Optional[float] = None,
):
    alert_config["price_upper"] = price_upper
    alert_config["price_lower"] = price_lower
    alert_config["pnl_upper"] = pnl_upper
    alert_config["pnl_lower"] = pnl_lower
    alert_config["margin_level_lower"] = margin_level_lower
    return {"status": "updated", "alerts": alert_config}


# --- WebSocket for real-time updates ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(data)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.active_connections.remove(conn)


manager = ConnectionManager()


def check_alerts(price_data: dict, positions: list, account: dict) -> list[dict]:
    """Check alert thresholds and return triggered alerts."""
    triggered = []
    bid = price_data.get("bid", 0)

    if alert_config["price_upper"] and bid >= alert_config["price_upper"]:
        triggered.append({
            "type": "PRICE_UPPER",
            "message": f"XAU/USD bid {bid:.2f} reached upper alert {alert_config['price_upper']:.2f}",
            "severity": "warning",
        })

    if alert_config["price_lower"] and bid <= alert_config["price_lower"]:
        triggered.append({
            "type": "PRICE_LOWER",
            "message": f"XAU/USD bid {bid:.2f} reached lower alert {alert_config['price_lower']:.2f}",
            "severity": "warning",
        })

    total_pnl = sum(p.get("profit", 0) for p in positions)
    if alert_config["pnl_upper"] and total_pnl >= alert_config["pnl_upper"]:
        triggered.append({
            "type": "PNL_UPPER",
            "message": f"Total P&L ${total_pnl:.2f} reached upper threshold ${alert_config['pnl_upper']:.2f}",
            "severity": "success",
        })

    if alert_config["pnl_lower"] and total_pnl <= alert_config["pnl_lower"]:
        triggered.append({
            "type": "PNL_LOWER",
            "message": f"Total P&L ${total_pnl:.2f} hit lower threshold ${alert_config['pnl_lower']:.2f}",
            "severity": "danger",
        })

    margin_level = account.get("margin_level", 0)
    if alert_config["margin_level_lower"] and margin_level > 0 and margin_level <= alert_config["margin_level_lower"]:
        triggered.append({
            "type": "MARGIN_LOW",
            "message": f"Margin level {margin_level:.1f}% below threshold {alert_config['margin_level_lower']:.1f}%",
            "severity": "danger",
        })

    return triggered


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Gather all data
            try:
                price_data = mt5.get_symbol_price()
                positions = [p.to_dict() for p in mt5.get_open_positions()]
                orders = [o.to_dict() for o in mt5.get_pending_orders()]
                account = mt5.get_account_info().to_dict()

                alerts = check_alerts(price_data, positions, account)

                payload = {
                    "type": "update",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "price": price_data,
                    "positions": positions,
                    "orders": orders,
                    "account": account,
                    "alerts": alerts,
                }
            except Exception as e:
                payload = {
                    "type": "error",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "message": str(e),
                }

            await websocket.send_json(payload)

            # Check for incoming messages (alert config updates, etc.)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                data = json.loads(msg)
                if data.get("action") == "set_alerts":
                    for key in alert_config:
                        if key in data:
                            alert_config[key] = data[key]
                    await websocket.send_json({"type": "alert_config_updated", "alerts": alert_config})
            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
