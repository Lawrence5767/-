# XAU/USD Trading Tracker for MetaTrader 5

A real-time web dashboard for tracking XAU/USD (Gold) trades in MetaTrader 5.

## Features

- **Live Price Feed** - Real-time bid/ask/spread display for XAU/USD
- **Open Positions** - Monitor all active XAU/USD positions with P&L, SL/TP, swap
- **Pending Orders** - Track limit/stop orders with price levels
- **Trade History** - Browse closed trades with filters (period, type, entry direction)
- **Analytics Dashboard** - Win rate, profit factor, max drawdown, P&L breakdown with charts
- **Real-time Alerts** - Configurable price, P&L, and margin level alerts with sound notifications

## Requirements

- **Windows OS** (MetaTrader 5 Python package is Windows-only)
- **MetaTrader 5 Terminal** installed and running
- **Python 3.10+**

## Setup

1. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

2. Ensure MetaTrader 5 terminal is running and logged in to your broker.

3. Start the server:

```bash
# Basic start (auto-connects to running MT5 terminal)
python app.py

# Or with explicit credentials via environment variables
MT5_LOGIN=12345678 MT5_PASSWORD=yourpass MT5_SERVER="YourBroker-Server" python app.py
```

4. Open your browser to `http://localhost:8000`

## Configuration

Set these environment variables before starting (all optional):

| Variable | Description |
|---|---|
| `MT5_PATH` | Path to MT5 terminal executable |
| `MT5_LOGIN` | MT5 account login number |
| `MT5_PASSWORD` | MT5 account password |
| `MT5_SERVER` | MT5 broker server name |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Dashboard UI |
| GET | `/api/status` | Connection status |
| POST | `/api/connect` | Connect to MT5 |
| GET | `/api/account` | Account info |
| GET | `/api/price` | Current XAU/USD price |
| GET | `/api/positions` | Open positions |
| GET | `/api/orders` | Pending orders |
| GET | `/api/history?days=30` | Trade history |
| GET | `/api/analytics?days=30` | Trade analytics |
| GET | `/api/alerts` | Alert configuration |
| POST | `/api/alerts` | Update alerts |
| WS | `/ws` | Real-time WebSocket feed |

## Project Structure

```
├── backend/
│   ├── app.py              # FastAPI server with REST + WebSocket
│   ├── mt5_service.py       # MetaTrader 5 connection and data layer
│   └── requirements.txt     # Python dependencies
├── frontend/
│   └── index.html           # Single-page dashboard (HTML/CSS/JS)
└── README.md
```
