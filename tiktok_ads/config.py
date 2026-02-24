"""Configuration management for TikTok Ads API."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def get_config():
    """Return a dict of all TikTok API configuration values."""
    env = os.getenv("TIKTOK_ENV", "sandbox").lower()

    if env == "production":
        base_url = "https://business-api.tiktok.com/open_api"
    else:
        base_url = "https://sandbox-ads.tiktok.com/open_api"

    return {
        "env": env,
        "base_url": base_url,
        "app_id": os.getenv("TIKTOK_APP_ID", ""),
        "app_secret": os.getenv("TIKTOK_APP_SECRET", ""),
        "access_token": os.getenv("TIKTOK_ACCESS_TOKEN", ""),
        "advertiser_id": os.getenv("TIKTOK_ADVERTISER_ID", ""),
    }


def validate_config(config):
    """Check that required config values are present. Returns list of missing keys."""
    required = ["access_token", "advertiser_id"]
    return [k for k in required if not config.get(k)]
