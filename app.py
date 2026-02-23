"""Main entry point for the Facebook Auto-Reply Agent."""

import logging
import os
import sys

from dotenv import load_dotenv

from facebook_api import FacebookAPI
from reply_generator import ReplyGenerator
from webhook import create_app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # --- Validate required environment variables ---
    required_vars = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "FACEBOOK_PAGE_ACCESS_TOKEN": os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN"),
        "FACEBOOK_APP_SECRET": os.getenv("FACEBOOK_APP_SECRET"),
        "FACEBOOK_VERIFY_TOKEN": os.getenv("FACEBOOK_VERIFY_TOKEN"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    # --- Initialize components ---
    facebook = FacebookAPI(
        page_access_token=required_vars["FACEBOOK_PAGE_ACCESS_TOKEN"],
        app_secret=required_vars["FACEBOOK_APP_SECRET"],
    )

    generator = ReplyGenerator()

    app = create_app(
        facebook=facebook,
        generator=generator,
        verify_token=required_vars["FACEBOOK_VERIFY_TOKEN"],
    )

    # --- Start server ---
    port = int(os.getenv("PORT", "5000"))
    logger.info("Starting Facebook Auto-Reply Agent on port %d", port)
    logger.info("Webhook URL: http://your-domain:%d/webhook", port)
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
