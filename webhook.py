"""Flask webhook server for receiving Facebook comment notifications."""

import logging

from flask import Flask, request, jsonify

from facebook_api import FacebookAPI
from reply_generator import ReplyGenerator

logger = logging.getLogger(__name__)


def create_app(
    facebook: FacebookAPI,
    generator: ReplyGenerator,
    verify_token: str,
) -> Flask:
    """Create and configure the Flask webhook application.

    Args:
        facebook: Initialized Facebook API client.
        generator: Initialized reply generator.
        verify_token: Token to verify webhook subscription with Facebook.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)

    @app.route("/webhook", methods=["GET"])
    def verify_webhook():
        """Handle Facebook webhook verification challenge."""
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            logger.info("Webhook verified successfully")
            return challenge, 200
        logger.warning("Webhook verification failed")
        return "Forbidden", 403

    @app.route("/webhook", methods=["POST"])
    def handle_webhook():
        """Process incoming webhook events from Facebook."""
        # Verify signature
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not facebook.verify_webhook_signature(request.data, signature):
            logger.warning("Invalid webhook signature")
            return "Invalid signature", 403

        payload = request.get_json()
        if not payload or payload.get("object") != "page":
            return "OK", 200

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "feed":
                    continue
                _process_feed_change(change.get("value", {}), facebook, generator)

        return "OK", 200

    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok"})

    return app


def _process_feed_change(
    value: dict,
    facebook: FacebookAPI,
    generator: ReplyGenerator,
) -> None:
    """Process a single feed change event.

    Only handles new comments (item=comment, verb=add) and skips
    comments made by the page itself to avoid infinite reply loops.
    """
    item = value.get("item")
    verb = value.get("verb")

    if item != "comment" or verb != "add":
        return

    comment_id = value.get("comment_id")
    sender_id = value.get("from", {}).get("id", "")
    comment_message = value.get("message", "")

    if not comment_id or not comment_message:
        logger.debug("Skipping event with missing comment_id or message")
        return

    # Avoid replying to our own comments
    if facebook.is_page_comment(sender_id):
        logger.debug("Skipping comment from page itself: %s", comment_id)
        return

    sender_name = value.get("from", {}).get("name")
    post_id = value.get("post_id")

    # Fetch the original post for context
    post_text = None
    if post_id:
        try:
            post = facebook.get_post(post_id)
            post_text = post.get("message")
        except Exception:
            logger.exception("Failed to fetch post %s", post_id)

    # Generate and send the reply
    try:
        reply_text = generator.generate_reply(
            comment_text=comment_message,
            post_text=post_text,
            commenter_name=sender_name,
        )
        facebook.reply_to_comment(comment_id, reply_text)
        logger.info("Auto-replied to comment %s", comment_id)
    except Exception:
        logger.exception("Failed to reply to comment %s", comment_id)
