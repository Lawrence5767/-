"""Facebook Graph API integration for reading comments and posting replies."""

import hashlib
import hmac
import logging

import requests

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class FacebookAPI:
    """Client for interacting with the Facebook Graph API."""

    def __init__(self, page_access_token: str, app_secret: str):
        self.page_access_token = page_access_token
        self.app_secret = app_secret
        self.page_id = self._get_page_id()

    def _get_page_id(self) -> str:
        """Retrieve the Page ID from the access token."""
        resp = requests.get(
            f"{GRAPH_API_BASE}/me",
            params={"access_token": self.page_access_token},
            timeout=10,
        )
        resp.raise_for_status()
        page_id = resp.json()["id"]
        logger.info("Connected to Facebook Page ID: %s", page_id)
        return page_id

    def get_comment(self, comment_id: str) -> dict:
        """Fetch a single comment by ID, including the parent post message."""
        resp = requests.get(
            f"{GRAPH_API_BASE}/{comment_id}",
            params={
                "fields": "id,message,from,created_time,parent,post",
                "access_token": self.page_access_token,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def get_post(self, post_id: str) -> dict:
        """Fetch a post by ID to get its content for context."""
        resp = requests.get(
            f"{GRAPH_API_BASE}/{post_id}",
            params={
                "fields": "id,message,created_time",
                "access_token": self.page_access_token,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def reply_to_comment(self, comment_id: str, message: str) -> dict:
        """Post a reply to a specific comment."""
        resp = requests.post(
            f"{GRAPH_API_BASE}/{comment_id}/comments",
            data={
                "message": message,
                "access_token": self.page_access_token,
            },
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("Replied to comment %s with reply ID: %s", comment_id, result.get("id"))
        return result

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify that a webhook payload was sent by Facebook."""
        if not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            self.app_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    def is_page_comment(self, sender_id: str) -> bool:
        """Check if a comment was made by the page itself (to avoid reply loops)."""
        return sender_id == self.page_id
