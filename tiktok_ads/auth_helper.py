#!/usr/bin/env python3
"""Helper script to obtain a TikTok Ads API access token.

This walks you through the OAuth2 flow step-by-step:
  1. Opens the authorization URL in your browser
  2. You approve permissions on TikTok
  3. TikTok redirects to your redirect URI with an auth_code
  4. This script exchanges the auth_code for an access_token
  5. Prints the token and advertiser IDs so you can add them to .env

Usage:
    python tiktok_ads/auth_helper.py
"""

import os
import sys
import webbrowser
from urllib.parse import urlencode
from pathlib import Path
from dotenv import load_dotenv

# Load .env
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def main():
    app_id = os.getenv("TIKTOK_APP_ID", "")
    app_secret = os.getenv("TIKTOK_APP_SECRET", "")

    if not app_id or app_id == "your_app_id_here":
        print("ERROR: TIKTOK_APP_ID is not set in your .env file.")
        print("  1. Go to https://business-api.tiktok.com/portal")
        print("  2. Open your app and copy the App ID")
        print("  3. Paste it in your .env file as TIKTOK_APP_ID=...")
        sys.exit(1)

    if not app_secret or app_secret == "your_app_secret_here":
        print("ERROR: TIKTOK_APP_SECRET is not set in your .env file.")
        print("  Copy the App Secret from your TikTok developer portal")
        print("  and paste it in your .env file as TIKTOK_APP_SECRET=...")
        sys.exit(1)

    # Step 1: Build the authorization URL
    redirect_uri = "https://localhost/callback"
    auth_params = {
        "app_id": app_id,
        "redirect_uri": redirect_uri,
        "state": "claude_code_auth",
    }
    auth_url = f"https://business-api.tiktok.com/portal/auth?{urlencode(auth_params)}"

    print("=" * 60)
    print("TikTok Ads API — Access Token Setup")
    print("=" * 60)
    print()
    print("Step 1: Open this URL in your browser and approve permissions:")
    print()
    print(f"  {auth_url}")
    print()

    try:
        webbrowser.open(auth_url)
        print("  (Attempted to open in your browser)")
    except Exception:
        print("  (Copy and paste the URL above into your browser)")

    print()
    print("Step 2: After approving, TikTok will redirect you to a URL like:")
    print(f"  {redirect_uri}?auth_code=XXXXX&state=claude_code_auth")
    print()
    print("  The page won't load (that's normal for localhost).")
    print("  Copy the 'auth_code' value from the URL bar.")
    print()

    auth_code = input("Step 3: Paste the auth_code here: ").strip()

    if not auth_code:
        print("ERROR: No auth_code provided.")
        sys.exit(1)

    # Step 4: Exchange auth_code for access_token
    print()
    print("Exchanging auth_code for access_token...")

    from tiktok_ads.client import TikTokAdsClient, TikTokAdsError

    try:
        data = TikTokAdsClient.get_access_token(app_id, app_secret, auth_code)
    except TikTokAdsError as e:
        print(f"ERROR: {e}")
        print()
        print("Common causes:")
        print("  - The auth_code was already used (each code works only once)")
        print("  - The auth_code expired (try the flow again)")
        print("  - App ID or Secret is incorrect")
        sys.exit(1)

    access_token = data.get("access_token", "")
    advertiser_ids = data.get("advertiser_ids", [])

    print()
    print("=" * 60)
    print("SUCCESS! Add these to your .env file:")
    print("=" * 60)
    print()
    print(f"TIKTOK_ACCESS_TOKEN={access_token}")
    if advertiser_ids:
        print(f"TIKTOK_ADVERTISER_ID={advertiser_ids[0]}")
        if len(advertiser_ids) > 1:
            print(f"  (Other advertiser IDs: {advertiser_ids[1:]})")
    print()
    print("Your .env file should look like:")
    print()
    print(f"  TIKTOK_ENV=sandbox")
    print(f"  TIKTOK_APP_ID={app_id}")
    print(f"  TIKTOK_APP_SECRET={app_secret}")
    print(f"  TIKTOK_ACCESS_TOKEN={access_token}")
    if advertiser_ids:
        print(f"  TIKTOK_ADVERTISER_ID={advertiser_ids[0]}")
    print()
    print("You're ready to create ads! Try:")
    print('  python -m tiktok_ads --campaign-name "Test Campaign" --ad-text "Hello TikTok!"')


if __name__ == "__main__":
    main()
