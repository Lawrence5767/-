"""
respond.io Real-Time Analytics Dashboard
FastAPI backend with webhook receiver, WebSocket broadcast, and REST analytics API.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from data_store import DataStore
from respond_io_client import RespondIOClient

# ── Configuration ─────────────────────────────────────────────

RESPOND_IO_API_TOKEN = os.getenv("RESPOND_IO_API_TOKEN", "")
RESPOND_IO_WEBHOOK_SECRET = os.getenv("RESPOND_IO_WEBHOOK_SECRET", "")
DB_PATH = os.getenv("DB_PATH", "analytics.db")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))  # seconds between API syncs

# ── Global State ──────────────────────────────────────────────

store = DataStore(DB_PATH)
client: Optional[RespondIOClient] = None
connected_ws: set[WebSocket] = set()
sync_task: Optional[asyncio.Task] = None


# ── Lifespan ──────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, sync_task
    if RESPOND_IO_API_TOKEN:
        client = RespondIOClient(RESPOND_IO_API_TOKEN, RESPOND_IO_WEBHOOK_SECRET)
        sync_task = asyncio.create_task(periodic_sync())
        print(f"[respond.io] API client initialized. Sync every {SYNC_INTERVAL}s")
    else:
        print("[respond.io] No API token configured — running in webhook-only mode")
    yield
    if sync_task:
        sync_task.cancel()
    if client:
        await client.close()


app = FastAPI(title="respond.io Analytics", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Periodic Sync ─────────────────────────────────────────────

async def periodic_sync():
    """Periodically pull data from respond.io API to keep local DB fresh."""
    while True:
        try:
            contact_ids = await sync_contacts()
            await sync_users()
            await sync_messages(contact_ids[:20])  # Sync messages for 20 most recent contacts
        except Exception as e:
            print(f"[sync] Error: {e}")
        await asyncio.sleep(SYNC_INTERVAL)


async def sync_contacts() -> list:
    """Sync contacts from respond.io. Returns list of synced contact IDs."""
    if not client:
        return []
    cursor_id = 0
    total = 0
    contact_ids = []
    while True:
        try:
            result = await client.list_contacts(cursor_id=cursor_id, limit=50)
        except Exception as e:
            print(f"[sync] list_contacts error: {e}")
            break
        items = result.get("items", [])
        if not items:
            break
        for contact in items:
            store.upsert_contact(contact)
            contact_ids.append(contact.get("id"))
            total += 1
        # Check pagination - use last item's ID as cursor
        if len(items) < 50:
            break
        cursor_id = items[-1].get("id", 0)
    if total:
        print(f"[sync] Synced {total} contacts")
        await broadcast_update("contacts_synced", {"count": total})
    return contact_ids


async def sync_users():
    """Sync workspace users/agents from respond.io."""
    if not client:
        return
    try:
        result = await client.list_users()
        items = result.get("items", [])
        # Store users in agent_events for reference (if not already tracked)
        for user in items:
            store.conn.execute(
                """INSERT OR IGNORE INTO agent_events (agent_id, agent_name, event_type, contact_id, conversation_id, created_at)
                   VALUES (?, ?, 'registered', '', '', ?)""",
                (
                    str(user.get("id", "")),
                    f"{user.get('firstName', '')} {user.get('lastName', '')}".strip(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        store.conn.commit()
        print(f"[sync] Synced {len(items)} users/agents")
    except Exception as e:
        print(f"[sync] list_users error: {e}")


async def sync_messages(contact_ids: list):
    """Sync recent messages for a list of contact IDs."""
    if not client or not contact_ids:
        return
    total = 0
    for cid in contact_ids:
        try:
            result = await client.list_messages(cid, limit=20)
            for m in result.get("items", []):
                msg = m.get("message", {})
                store.insert_message({
                    "id": str(m.get("messageId", "")),
                    "contact_id": str(m.get("contactId", "")),
                    "direction": m.get("traffic", "incoming"),
                    "channel": str(m.get("channelId", "")),
                    "message_type": msg.get("type", "text") if isinstance(msg, dict) else "text",
                    "content": msg.get("text", "") if isinstance(msg, dict) else "",
                    "sender_type": m.get("sender", {}).get("source", ""),
                    "sender_id": str(m.get("sender", {}).get("userId", "") or ""),
                    "created_at": m.get("createdAt", ""),
                })
                total += 1
        except Exception as e:
            print(f"[sync] messages for contact {cid}: {e}")
        await asyncio.sleep(0.2)  # Rate limit courtesy
    if total:
        print(f"[sync] Synced {total} messages across {len(contact_ids)} contacts")


# ── WebSocket Manager ─────────────────────────────────────────

async def broadcast_update(event: str, data: dict):
    payload = json.dumps({"event": event, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
    dead = set()
    for ws in connected_ws:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    connected_ws.difference_update(dead)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_ws.add(ws)
    try:
        # Send initial snapshot
        snapshot = build_analytics_snapshot()
        await ws.send_text(json.dumps({"event": "snapshot", "data": snapshot}))
        while True:
            msg = await ws.receive_text()
            # Handle client requests
            try:
                req = json.loads(msg)
                if req.get("action") == "get_snapshot":
                    period = req.get("period", "24h")
                    snapshot = build_analytics_snapshot(period)
                    await ws.send_text(json.dumps({"event": "snapshot", "data": snapshot}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        connected_ws.discard(ws)


# ── Webhook Receiver ──────────────────────────────────────────

@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_respond_signature: Optional[str] = Header(None),
):
    body = await request.body()

    # Verify signature if configured
    if RESPOND_IO_WEBHOOK_SECRET and client:
        if not x_respond_signature:
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        if not client.verify_webhook_signature(body, x_respond_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body)
    event_type = payload.get("event", "unknown")
    data = payload.get("data", {})

    # Log raw event
    store.log_webhook_event(event_type, payload)

    # Process by event type
    await process_webhook_event(event_type, data)

    return {"status": "ok"}


async def process_webhook_event(event_type: str, data: dict):
    """Process a webhook event and update the data store."""
    now = datetime.now(timezone.utc).isoformat()

    if event_type == "message.created":
        # respond.io uses "traffic" (incoming/outgoing) in API, "direction" in webhooks
        direction = data.get("traffic", data.get("direction", "incoming"))
        # Message content may be nested in a "message" object
        message_obj = data.get("message", {})
        if isinstance(message_obj, dict):
            content = message_obj.get("text", message_obj.get("content", ""))
            msg_type = message_obj.get("type", "text")
        else:
            content = data.get("text", data.get("content", ""))
            msg_type = data.get("type", "text")
        # Sender info
        sender = data.get("sender", {})
        sender_source = sender.get("source", "") if isinstance(sender, dict) else ""
        sender_id = sender.get("userId", "") if isinstance(sender, dict) else data.get("senderId", "")
        msg_data = {
            "id": data.get("messageId", data.get("id", "")),
            "contact_id": data.get("contactId", ""),
            "conversation_id": data.get("conversationId", ""),
            "direction": direction,
            "channel": str(data.get("channelId", "")),
            "channel_type": data.get("channelType", data.get("channel_type", "")),
            "message_type": msg_type,
            "content": content,
            "sender_type": sender_source,
            "sender_id": str(sender_id or ""),
            "sender_name": data.get("senderName", sender_source),
            "status": json.dumps(data.get("status", "")) if isinstance(data.get("status"), list) else str(data.get("status", "")),
            "created_at": data.get("createdAt", now),
        }
        store.insert_message(msg_data)
        await broadcast_update("new_message", msg_data)

    elif event_type == "contact.created":
        store.upsert_contact(data)
        await broadcast_update("new_contact", {
            "id": str(data.get("id", "")),
            "name": f"{data.get('firstName', '')} {data.get('lastName', '')}".strip(),
            "created_at": data.get("createdAt", now),
        })

    elif event_type == "contact.updated":
        store.upsert_contact(data)
        await broadcast_update("contact_updated", {"id": str(data.get("id", ""))})

    elif event_type in ("conversation.opened", "conversation.open"):
        conv_data = {
            "id": data.get("id", data.get("conversationId", "")),
            "contact_id": data.get("contactId", ""),
            "status": "open",
            "assignee_id": data.get("assigneeId", ""),
            "assignee_name": data.get("assigneeName", ""),
            "opened_at": data.get("createdAt", now),
        }
        store.upsert_conversation(conv_data)
        await broadcast_update("conversation_opened", conv_data)

    elif event_type in ("conversation.closed", "conversation.close"):
        conv_data = {
            "id": data.get("id", data.get("conversationId", "")),
            "contact_id": data.get("contactId", ""),
            "status": "closed",
            "assignee_id": data.get("assigneeId", ""),
            "assignee_name": data.get("assigneeName", ""),
            "category": data.get("category", ""),
            "summary": data.get("summary", ""),
            "opened_at": data.get("openedAt", now),
            "closed_at": data.get("closedAt", data.get("createdAt", now)),
        }
        store.upsert_conversation(conv_data)
        await broadcast_update("conversation_closed", conv_data)

    elif event_type == "contact.assignee.updated":
        agent_data = {
            "agent_id": str(data.get("assigneeId", data.get("newAssigneeId", ""))),
            "agent_name": data.get("assigneeName", data.get("newAssigneeName", "")),
            "event_type": "assigned",
            "contact_id": str(data.get("contactId", "")),
            "conversation_id": str(data.get("conversationId", "")),
            "created_at": data.get("createdAt", now),
        }
        store.insert_agent_event(agent_data)
        await broadcast_update("agent_assigned", agent_data)

    elif event_type == "contact.tag.updated":
        # Update the contact's tags if we have the full contact info
        if "contactId" in data:
            contact_id = str(data["contactId"])
            existing = store.conn.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
            if existing:
                update_data = dict(existing)
                update_data["tags"] = data.get("tags", [])
                store.upsert_contact(update_data)
        await broadcast_update("tag_updated", data)

    elif event_type == "comment.created":
        await broadcast_update("new_comment", data)


# ── Analytics Snapshot Builder ────────────────────────────────

def get_since_datetime(period: str) -> str:
    now = datetime.now(timezone.utc)
    mapping = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }
    delta = mapping.get(period, timedelta(hours=24))
    return (now - delta).isoformat()


def build_analytics_snapshot(period: str = "24h") -> dict:
    since = get_since_datetime(period)
    use_daily = period in ("7d", "30d", "90d")

    # Message volume
    if use_daily:
        volume = store.get_message_volume_daily(since)
    else:
        volume = store.get_message_volume_hourly(since)

    # Response time
    avg_response_time = store.get_avg_response_time(since)

    # Resolution rate
    resolution = store.get_resolution_rate(since)

    return {
        "period": period,
        "overview": {
            "total_contacts": store.get_contacts_count(),
            "open_conversations": store.get_open_conversations_count(),
            "total_messages": store.get_messages_count(),
            "incoming_messages": store.get_messages_count("incoming"),
            "outgoing_messages": store.get_messages_count("outgoing"),
            "avg_response_time_seconds": round(avg_response_time, 1) if avg_response_time else None,
            "resolution_rate": resolution,
        },
        "message_volume": volume,
        "channel_distribution": store.get_channel_distribution(since),
        "tag_distribution": store.get_tag_distribution(),
        "agent_performance": store.get_agent_performance(since),
        "contacts_growth": store.get_contacts_growth_daily(since),
    }


# ── REST API Endpoints ────────────────────────────────────────

@app.get("/api/analytics")
async def get_analytics(period: str = "24h"):
    return build_analytics_snapshot(period)


@app.get("/api/messages")
async def get_messages(period: str = "24h", direction: Optional[str] = None):
    since = get_since_datetime(period)
    return store.get_messages_by_period(since, direction)


@app.get("/api/conversations")
async def get_conversations(period: str = "24h", status: Optional[str] = None):
    since = get_since_datetime(period)
    return store.get_conversations_by_period(since, status)


@app.get("/api/agents")
async def get_agents(period: str = "24h"):
    since = get_since_datetime(period)
    return store.get_agent_performance(since)


@app.get("/api/contacts")
async def get_contacts(period: str = "30d"):
    since = get_since_datetime(period)
    return store.get_contacts_by_period(since)


# ── Frontend Serving ──────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def serve_frontend():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>respond.io Analytics</h1><p>Frontend not found.</p>")


# ── Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    if not RESPOND_IO_API_TOKEN:
        print("=" * 60)
        print("  WARNING: RESPOND_IO_API_TOKEN not set")
        print("  Set it via environment variable to enable API sync.")
        print("  Webhook receiver is still active.")
        print("=" * 60)

    print(f"Starting respond.io Analytics on {HOST}:{PORT}")
    print(f"Webhook URL: http://{HOST}:{PORT}/webhook")
    print(f"Dashboard:   http://{HOST}:{PORT}/")
    uvicorn.run(app, host=HOST, port=PORT)
