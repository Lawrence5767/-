"""
XAU/USD Trading Tracker - FastAPI Backend
Receives trade data from MT5 Expert Advisor via HTTP push.
Works on macOS/Linux/Windows - no MetaTrader5 Python package needed.

Architecture:
  MT5 Terminal (EA) --HTTP POST--> This Server (FastAPI) --WebSocket--> Browser Dashboard
"""

import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mt5_service import DataStore
from pydantic import BaseModel

# --- Configuration ---
API_KEY = os.environ.get("TRACKER_API_KEY", "")  # Optional: protect push endpoint

# Alert thresholds (configurable via API)
alert_config = {
    "price_upper": None,
    "price_lower": None,
    "pnl_upper": None,
    "pnl_lower": None,
    "margin_level_lower": None,
}


# --- App setup ---
store = DataStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Tracker] XAU/USD Trading Tracker started")
    print("[Tracker] Dashboard: http://localhost:8000")
    print("[Tracker] Waiting for data from MT5 Expert Advisor...")
    if API_KEY:
        print(f"[Tracker] API key is set - EA must send X-API-Key header")
    else:
        print(
            "[Tracker] No API key set - push endpoint is open (set TRACKER_API_KEY env var to secure)"
        )
    yield
    print("[Tracker] Shutting down")


app = FastAPI(title="XAU/USD Trading Tracker", version="2.0.0", lifespan=lifespan)

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


# --- Auth helper ---
def verify_api_key(x_api_key: Optional[str] = None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


# --- Pydantic models for push endpoint ---
class PushPayload(BaseModel):
    account: Optional[dict] = None
    price: Optional[dict] = None
    positions: Optional[list] = None
    orders: Optional[list] = None
    deals: Optional[list] = None


# --- REST Endpoints ---


@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/status")
async def get_status():
    return {
        "connected": store.is_connected,
        "last_push": store.last_push_time,
        "mode": "ea_push",
    }


# ----- EA Push Endpoint -----


@app.post("/api/push")
async def push_data(payload: PushPayload, x_api_key: Optional[str] = Header(None)):
    """Receive a snapshot of trade data from the MT5 Expert Advisor."""
    verify_api_key(x_api_key)
    store.push_snapshot(payload.model_dump())

    # Broadcast to all connected WebSocket clients
    data = _build_ws_payload()
    await manager.broadcast(data)

    return {"status": "ok", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


# ----- Demo Data -----


@app.post("/api/demo")
async def load_demo():
    """Load sample demo data for testing the dashboard."""
    result = store.load_demo_data()

    # Broadcast to all connected WebSocket clients
    data = _build_ws_payload()
    await manager.broadcast(data)

    return result


# ----- Read Endpoints -----


@app.get("/api/account")
async def get_account():
    info = store.get_account_info()
    if info is None:
        return {"error": "No account data yet. Waiting for MT5 EA push."}
    return info.to_dict()


@app.get("/api/price")
async def get_price():
    price = store.get_symbol_price()
    if price is None:
        return {"error": "No price data yet. Waiting for MT5 EA push."}
    return price


@app.get("/api/positions")
async def get_positions():
    positions = store.get_open_positions()
    return {"positions": [p.to_dict() for p in positions]}


@app.get("/api/orders")
async def get_orders():
    orders = store.get_pending_orders()
    return {"orders": [o.to_dict() for o in orders]}


@app.get("/api/history")
async def get_history(days: int = Query(default=30, ge=1, le=365)):
    deals = store.get_trade_history(days)
    return {"deals": [d.to_dict() for d in deals], "count": len(deals)}


@app.get("/api/analytics")
async def get_analytics(days: int = Query(default=30, ge=1, le=365)):
    return store.compute_analytics(days)


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
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(data)
            except Exception:
                dead.append(conn)
        for conn in dead:
            if conn in self.active_connections:
                self.active_connections.remove(conn)


manager = ConnectionManager()


def _build_ws_payload() -> dict:
    """Build a WebSocket payload from current store data."""
    price_data = store.get_symbol_price() or {}
    positions = [p.to_dict() for p in store.get_open_positions()]
    orders = [o.to_dict() for o in store.get_pending_orders()]
    acct_info = store.get_account_info()
    account = acct_info.to_dict() if acct_info else {}

    alerts = check_alerts(price_data, positions, account)

    return {
        "type": "update",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "price": price_data,
        "positions": positions,
        "orders": orders,
        "account": account,
        "alerts": alerts,
    }


def check_alerts(price_data: dict, positions: list, account: dict) -> list[dict]:
    """Check alert thresholds and return triggered alerts."""
    triggered = []
    bid = price_data.get("bid", 0)

    if alert_config["price_upper"] and bid >= alert_config["price_upper"]:
        triggered.append(
            {
                "type": "PRICE_UPPER",
                "message": f"XAU/USD bid {bid:.2f} reached upper alert {alert_config['price_upper']:.2f}",
                "severity": "warning",
            }
        )

    if alert_config["price_lower"] and bid <= alert_config["price_lower"]:
        triggered.append(
            {
                "type": "PRICE_LOWER",
                "message": f"XAU/USD bid {bid:.2f} reached lower alert {alert_config['price_lower']:.2f}",
                "severity": "warning",
            }
        )

    total_pnl = sum(p.get("profit", 0) for p in positions)
    if alert_config["pnl_upper"] and total_pnl >= alert_config["pnl_upper"]:
        triggered.append(
            {
                "type": "PNL_UPPER",
                "message": f"Total P&L ${total_pnl:.2f} reached upper threshold ${alert_config['pnl_upper']:.2f}",
                "severity": "success",
            }
        )

    if alert_config["pnl_lower"] and total_pnl <= alert_config["pnl_lower"]:
        triggered.append(
            {
                "type": "PNL_LOWER",
                "message": f"Total P&L ${total_pnl:.2f} hit lower threshold ${alert_config['pnl_lower']:.2f}",
                "severity": "danger",
            }
        )

    margin_level = account.get("margin_level", 0)
    if (
        alert_config["margin_level_lower"]
        and margin_level > 0
        and margin_level <= alert_config["margin_level_lower"]
    ):
        triggered.append(
            {
                "type": "MARGIN_LOW",
                "message": f"Margin level {margin_level:.1f}% below threshold {alert_config['margin_level_lower']:.1f}%",
                "severity": "danger",
            }
        )

    return triggered


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        data = _build_ws_payload()
        await websocket.send_json(data)

        while True:
            # Listen for messages from the client (alert config updates)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                data = json.loads(msg)
                if data.get("action") == "set_alerts":
                    for key in alert_config:
                        if key in data:
                            alert_config[key] = data[key]
                    await websocket.send_json(
                        {
                            "type": "alert_config_updated",
                            "alerts": alert_config,
                        }
                    )
                elif data.get("action") == "refresh":
                    # Client requesting a refresh
                    payload = _build_ws_payload()
                    await websocket.send_json(payload)
            except asyncio.TimeoutError:
                # Send periodic heartbeat with current data
                if store.is_connected:
                    payload = _build_ws_payload()
                    await websocket.send_json(payload)
                else:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "connected": False,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
