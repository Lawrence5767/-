"""
SQLite data store for respond.io analytics.
Stores messages, conversations, contacts, and agent activity for real-time analytics.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional, Union


def to_iso(value: Union[str, int, float, None]) -> str:
    """Convert a value to ISO 8601 string. Handles Unix timestamps and ISO strings."""
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return str(value)


class DataStore:
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self):
        c = self.conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                country TEXT DEFAULT '',
                language TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                custom_fields TEXT DEFAULT '{}',
                channels TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                contact_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                assignee_id TEXT,
                assignee_name TEXT DEFAULT '',
                category TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                contact_id TEXT NOT NULL,
                conversation_id TEXT,
                direction TEXT NOT NULL,
                channel TEXT DEFAULT '',
                channel_type TEXT DEFAULT '',
                message_type TEXT DEFAULT 'text',
                content TEXT DEFAULT '',
                sender_type TEXT DEFAULT '',
                sender_id TEXT DEFAULT '',
                sender_name TEXT DEFAULT '',
                status TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            );

            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                agent_name TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                contact_id TEXT,
                conversation_id TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                processed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_messages_direction ON messages(direction);
            CREATE INDEX IF NOT EXISTS idx_conversations_contact ON conversations(contact_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
            CREATE INDEX IF NOT EXISTS idx_conversations_opened ON conversations(opened_at);
            CREATE INDEX IF NOT EXISTS idx_agent_events_agent ON agent_events(agent_id);
            CREATE INDEX IF NOT EXISTS idx_agent_events_created ON agent_events(created_at);
            CREATE INDEX IF NOT EXISTS idx_contacts_created ON contacts(created_at);
        """)
        c.commit()

    # ── Contacts ──────────────────────────────────────────────

    def upsert_contact(self, data: dict):
        now = datetime.now(timezone.utc).isoformat()
        contact_id = str(data.get("id", ""))
        # Handle assignee object from API
        assignee = data.get("assignee") or {}
        assignee_name = ""
        if isinstance(assignee, dict):
            assignee_name = f"{assignee.get('firstName', '')} {assignee.get('lastName', '')}".strip()
        self.conn.execute(
            """INSERT INTO contacts (id, first_name, last_name, phone, email, country, language, tags, custom_fields, channels, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 first_name=excluded.first_name, last_name=excluded.last_name,
                 phone=excluded.phone, email=excluded.email,
                 country=excluded.country, language=excluded.language,
                 tags=excluded.tags, custom_fields=excluded.custom_fields,
                 channels=excluded.channels, updated_at=excluded.updated_at""",
            (
                contact_id,
                data.get("firstName", data.get("first_name", "")) or "",
                data.get("lastName", data.get("last_name", "")) or "",
                data.get("phone", "") or "",
                data.get("email", "") or "",
                data.get("countryCode", data.get("country", "")) or "",
                data.get("language", "") or "",
                json.dumps(data.get("tags", [])),
                json.dumps(data.get("customFields", data.get("custom_fields", {}))),
                json.dumps(data.get("channels", [])),
                to_iso(data.get("created_at", data.get("createdAt"))),
                now,
            ),
        )
        self.conn.commit()

    def get_contacts_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM contacts").fetchone()
        return row["cnt"]

    def get_contacts_by_period(self, since: str):
        rows = self.conn.execute(
            "SELECT * FROM contacts WHERE created_at >= ? ORDER BY created_at DESC", (since,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Conversations ─────────────────────────────────────────

    def upsert_conversation(self, data: dict):
        conv_id = str(data.get("id", ""))
        contact_id = str(data.get("contactId", data.get("contact_id", "")))
        self.conn.execute(
            """INSERT INTO conversations (id, contact_id, status, assignee_id, assignee_name, category, summary, opened_at, closed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status, assignee_id=excluded.assignee_id,
                 assignee_name=excluded.assignee_name, category=excluded.category,
                 summary=excluded.summary, closed_at=excluded.closed_at""",
            (
                conv_id,
                contact_id,
                data.get("status", "open"),
                str(data.get("assigneeId", data.get("assignee_id", ""))),
                data.get("assigneeName", data.get("assignee_name", "")),
                data.get("category", ""),
                data.get("summary", ""),
                data.get("openedAt", data.get("opened_at", datetime.now(timezone.utc).isoformat())),
                data.get("closedAt", data.get("closed_at", None)),
            ),
        )
        self.conn.commit()

    def get_open_conversations_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM conversations WHERE status='open'").fetchone()
        return row["cnt"]

    def get_conversations_by_period(self, since: str, status: Optional[str] = None):
        if status:
            rows = self.conn.execute(
                "SELECT * FROM conversations WHERE opened_at >= ? AND status = ? ORDER BY opened_at DESC",
                (since, status),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM conversations WHERE opened_at >= ? ORDER BY opened_at DESC", (since,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Messages ──────────────────────────────────────────────

    def insert_message(self, data: dict):
        msg_id = str(data.get("id", ""))
        self.conn.execute(
            """INSERT OR IGNORE INTO messages (id, contact_id, conversation_id, direction, channel, channel_type, message_type, content, sender_type, sender_id, sender_name, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                msg_id,
                str(data.get("contactId", data.get("contact_id", ""))),
                str(data.get("conversationId", data.get("conversation_id", ""))),
                data.get("direction", "incoming"),
                data.get("channel", ""),
                data.get("channelType", data.get("channel_type", "")),
                data.get("messageType", data.get("message_type", "text")),
                data.get("content", data.get("text", "")),
                data.get("senderType", data.get("sender_type", "")),
                str(data.get("senderId", data.get("sender_id", ""))),
                data.get("senderName", data.get("sender_name", "")),
                data.get("status", ""),
                data.get("createdAt", data.get("created_at", datetime.now(timezone.utc).isoformat())),
            ),
        )
        self.conn.commit()

    def get_messages_count(self, direction: Optional[str] = None) -> int:
        if direction:
            row = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE direction=?", (direction,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()
        return row["cnt"]

    def get_messages_by_period(self, since: str, direction: Optional[str] = None):
        if direction:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE created_at >= ? AND direction=? ORDER BY created_at DESC",
                (since, direction),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE created_at >= ? ORDER BY created_at DESC", (since,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Agent Events ──────────────────────────────────────────

    def insert_agent_event(self, data: dict):
        self.conn.execute(
            """INSERT INTO agent_events (agent_id, agent_name, event_type, contact_id, conversation_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(data.get("agent_id", "")),
                data.get("agent_name", ""),
                data.get("event_type", ""),
                str(data.get("contact_id", "")),
                str(data.get("conversation_id", "")),
                data.get("created_at", datetime.now(timezone.utc).isoformat()),
            ),
        )
        self.conn.commit()

    def get_agent_events_by_period(self, since: str, agent_id: Optional[str] = None):
        if agent_id:
            rows = self.conn.execute(
                "SELECT * FROM agent_events WHERE created_at >= ? AND agent_id=? ORDER BY created_at DESC",
                (since, agent_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM agent_events WHERE created_at >= ? ORDER BY created_at DESC", (since,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Webhook Events (raw log) ──────────────────────────────

    def log_webhook_event(self, event_type: str, payload: dict):
        self.conn.execute(
            "INSERT INTO webhook_events (event_type, payload, created_at) VALUES (?, ?, ?)",
            (event_type, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    # ── Aggregation Queries ───────────────────────────────────

    def get_message_volume_hourly(self, since: str):
        rows = self.conn.execute(
            """SELECT strftime('%Y-%m-%dT%H:00:00', created_at) as hour,
                      direction,
                      COUNT(*) as count
               FROM messages WHERE created_at >= ?
               GROUP BY hour, direction
               ORDER BY hour""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_message_volume_daily(self, since: str):
        rows = self.conn.execute(
            """SELECT strftime('%Y-%m-%d', created_at) as day,
                      direction,
                      COUNT(*) as count
               FROM messages WHERE created_at >= ?
               GROUP BY day, direction
               ORDER BY day""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_channel_distribution(self, since: str):
        rows = self.conn.execute(
            """SELECT channel_type, COUNT(*) as count
               FROM messages WHERE created_at >= ? AND channel_type != ''
               GROUP BY channel_type
               ORDER BY count DESC""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_tag_distribution(self):
        rows = self.conn.execute("SELECT tags FROM contacts WHERE tags != '[]'").fetchall()
        tag_counts = {}
        for row in rows:
            tags = json.loads(row["tags"])
            for tag in tags:
                tag_name = tag if isinstance(tag, str) else tag.get("name", str(tag))
                tag_counts[tag_name] = tag_counts.get(tag_name, 0) + 1
        return [{"tag": k, "count": v} for k, v in sorted(tag_counts.items(), key=lambda x: -x[1])]

    def get_agent_performance(self, since: str):
        rows = self.conn.execute(
            """SELECT agent_id, agent_name, event_type, COUNT(*) as count
               FROM agent_events WHERE created_at >= ?
               GROUP BY agent_id, agent_name, event_type
               ORDER BY count DESC""",
            (since,),
        ).fetchall()
        agents = {}
        for row in rows:
            aid = row["agent_id"]
            if aid not in agents:
                agents[aid] = {"agent_id": aid, "agent_name": row["agent_name"], "events": {}}
            agents[aid]["events"][row["event_type"]] = row["count"]
        return list(agents.values())

    def get_avg_response_time(self, since: str) -> Optional[float]:
        """Calculate average first-response time per conversation (in seconds)."""
        rows = self.conn.execute(
            """SELECT c.id as conv_id, c.opened_at,
                      MIN(m.created_at) as first_response
               FROM conversations c
               JOIN messages m ON m.conversation_id = c.id AND m.direction = 'outgoing'
               WHERE c.opened_at >= ?
               GROUP BY c.id""",
            (since,),
        ).fetchall()
        if not rows:
            return None
        total = 0
        count = 0
        for row in rows:
            try:
                opened = datetime.fromisoformat(row["opened_at"].replace("Z", "+00:00"))
                responded = datetime.fromisoformat(row["first_response"].replace("Z", "+00:00"))
                diff = (responded - opened).total_seconds()
                if diff >= 0:
                    total += diff
                    count += 1
            except (ValueError, TypeError):
                continue
        return total / count if count > 0 else None

    def get_resolution_rate(self, since: str) -> dict:
        total = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE opened_at >= ?", (since,)
        ).fetchone()["cnt"]
        closed = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM conversations WHERE opened_at >= ? AND status='closed'",
            (since,),
        ).fetchone()["cnt"]
        return {"total": total, "closed": closed, "rate": round(closed / total * 100, 1) if total else 0}

    def get_contacts_growth_daily(self, since: str):
        rows = self.conn.execute(
            """SELECT strftime('%Y-%m-%d', created_at) as day, COUNT(*) as count
               FROM contacts WHERE created_at >= ?
               GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]
