# XAU/USD Trading Tracker for MetaTrader 5

A real-time web dashboard for tracking XAU/USD (Gold) trades in MetaTrader 5. **Works on macOS, Linux, and Windows** — no Windows-only dependencies.

## Architecture

```
MT5 Terminal (Windows/VM/VPS)          Your Mac
┌───────────────────────┐         ┌──────────────────────┐
│  XAU_USD_Tracker EA   │──HTTP──>│  FastAPI Backend      │
│  (sends trade data    │  POST   │  (stores in SQLite)   │
│   every 2 seconds)    │         │         │              │
└───────────────────────┘         │    WebSocket           │
                                  │         │              │
                                  │  Browser Dashboard     │
                                  │  (real-time updates)   │
                                  └──────────────────────┘
```

The MT5 Expert Advisor collects your account info, open positions, pending orders, price data, and deal history, then sends it via HTTP POST to the Python backend running on your Mac. The backend stores everything in SQLite and pushes updates to the browser dashboard via WebSocket.

## Features

- **Live Price Feed** — Real-time bid/ask/spread display for XAU/USD
- **Open Positions** — Monitor all active XAU/USD positions with P&L, SL/TP, swap
- **Pending Orders** — Track limit/stop orders with price levels
- **Trade History** — Browse closed trades with filters (period, type, entry direction)
- **Analytics Dashboard** — Win rate, profit factor, max drawdown, P&L breakdown with charts
- **Real-time Alerts** — Configurable price, P&L, and margin level alerts with sound notifications
- **Demo Mode** — Test the dashboard with sample data (no MT5 needed)

## Requirements

- **Python 3.10+** (on any OS — macOS, Linux, Windows)
- **MetaTrader 5 Terminal** (running anywhere — Windows, VM, VPS)

## Quick Start

### 1. Start the Dashboard (on your Mac)

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Open your browser to `http://localhost:8000`

### 2. Try Demo Mode

Click the **"Load Demo"** button in the dashboard, or:

```bash
curl -X POST http://localhost:8000/api/demo
```

### 3. Connect MT5 (when ready)

1. Copy `mt5_ea/XAU_USD_Tracker.mq5` to your MT5's `MQL5/Experts/` folder
2. In MT5: **Tools > Options > Expert Advisors**
   - Check **"Allow WebRequest for listed URL"**
   - Add your Mac's URL: `http://YOUR_MAC_IP:8000`
3. Compile the EA in MetaEditor (F7)
4. Drag the EA onto any XAUUSD chart
5. Set the `ServerURL` input to `http://YOUR_MAC_IP:8000`
6. Enable **AutoTrading**

## Configuration

### Backend Environment Variables

| Variable | Description | Default |
|---|---|---|
| `TRACKER_API_KEY` | Protect the push endpoint with an API key | _(none — open)_ |

### EA Input Parameters

| Parameter | Description | Default |
|---|---|---|
| `ServerURL` | URL of your dashboard server | `http://localhost:8000` |
| `ApiKey` | API key (must match `TRACKER_API_KEY`) | _(empty)_ |
| `PushInterval` | Seconds between data pushes | `2` |
| `HistoryDays` | Days of deal history to send | `30` |
| `SendDeals` | Whether to send deal history | `true` |

### Securing the Connection

Set an API key to prevent unauthorized data pushes:

```bash
# On your Mac
TRACKER_API_KEY=my-secret-key python app.py

# In MT5 EA settings
# Set ApiKey input to: my-secret-key
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Dashboard UI |
| GET | `/api/status` | Connection status |
| POST | `/api/push` | **EA pushes trade data here** |
| POST | `/api/demo` | Load demo/sample data |
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
│   ├── mt5_service.py      # SQLite data store service
│   ├── requirements.txt    # Python dependencies
│   └── tracker.db          # SQLite database (auto-created)
├── frontend/
│   └── index.html          # Single-page dashboard (HTML/CSS/JS)
├── mt5_ea/
│   └── XAU_USD_Tracker.mq5 # MetaTrader 5 Expert Advisor
└── README.md
```

## Network Setup Tips for macOS

If MT5 runs on a different machine (Windows VM, VPS, etc.):

1. **Find your Mac's local IP**: `ifconfig | grep "inet " | grep -v 127.0.0.1`
2. **Allow through firewall**: System Settings > Network > Firewall > allow port 8000
3. **Use the IP in EA settings**: e.g. `http://192.168.1.50:8000`

If using **Parallels/VMware** on your Mac:
- The host Mac is typically reachable at `http://10.211.55.2:8000` (Parallels) or `http://host.docker.internal:8000`
