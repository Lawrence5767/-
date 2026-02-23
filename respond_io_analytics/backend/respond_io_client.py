"""
respond.io API v2 Client
Handles authentication, contacts, messages, users, and webhook verification.
"""

import asyncio
import hashlib
import hmac
from typing import Optional

import httpx


class RespondIOClient:
    BASE_URL = "https://api.respond.io/v2/"

    def __init__(self, api_token: str, webhook_secret: Optional[str] = None, timeout: int = 30, max_retries: int = 3):
        self.api_token = api_token
        self.webhook_secret = webhook_secret
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def close(self):
        await self._client.aclose()

    async def _request_with_retry(self, method: str, url: str, **kwargs):
        """Make an HTTP request with retry on 5xx errors."""
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._client.request(method, url, **kwargs)
                if resp.status_code < 500:
                    resp.raise_for_status()
                    return resp.json()
                last_exc = httpx.HTTPStatusError(
                    f"Server error {resp.status_code}", request=resp.request, response=resp
                )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        raise last_exc

    # ── Contacts ──────────────────────────────────────────────

    async def list_contacts(self, cursor_id: int = 0, limit: int = 50, search: str = ""):
        """POST /contact/list — requires search, timezone, filter in body; limit/cursorId as query params."""
        params = {"limit": limit}
        if cursor_id:
            params["cursorId"] = cursor_id
        return await self._request_with_retry(
            "POST", "contact/list",
            json={"search": search, "timezone": "UTC", "filter": {"$and": []}},
            params=params,
        )

    async def get_contact(self, contact_id: int):
        """GET /contact/id:{contactId}"""
        return await self._request_with_retry("GET", f"contact/id:{contact_id}")

    # ── Messages ──────────────────────────────────────────────

    async def list_messages(self, contact_id: int, cursor_id: int = 0, limit: int = 50):
        """GET /contact/id:{contactId}/message/list"""
        params = {"limit": limit}
        if cursor_id:
            params["cursorId"] = cursor_id
        return await self._request_with_retry(
            "GET", f"contact/id:{contact_id}/message/list", params=params,
        )

    # ── Users/Agents ──────────────────────────────────────────

    async def list_users(self):
        """GET /space/user — returns workspace users (agents)."""
        return await self._request_with_retry("GET", "space/user")

    # ── Conversations ─────────────────────────────────────────

    async def open_conversation(self, contact_id: int):
        return await self._request_with_retry(
            "POST", f"contact/id:{contact_id}/conversation", json={"status": "open"},
        )

    async def close_conversation(self, contact_id: int, summary: str = "", category: str = ""):
        payload = {"status": "close"}
        if summary:
            payload["summary"] = summary
        if category:
            payload["category"] = category
        return await self._request_with_retry(
            "POST", f"contact/id:{contact_id}/conversation", json=payload,
        )

    # ── Webhook Verification ──────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            return True
        digest = hmac.new(
            self.webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, signature)
