# Claude Code — TikTok Ads Automation

This project includes a TikTok Ads API integration at `tiktok_ads/`.
When the user asks to create, manage, or check TikTok ads, use the Python
modules below to do it.

## Setup

Credentials are in `.env` (see `.env.example` for the template).
Dependencies: `pip install requests python-dotenv`

## How to Create a TikTok Ad

When the user says something like "create a TikTok ad for …", use the
`tiktok_ads.automation.create_full_ad()` function by writing and running
a short Python script. Here's the pattern:

```python
import sys
sys.path.insert(0, "/home/user/-")
from tiktok_ads.automation import create_full_ad

result = create_full_ad(
    campaign_name="<descriptive campaign name>",
    objective="reach",          # reach | traffic | video_views | conversions | app_installs | product_sales
    campaign_budget=50.0,       # daily USD
    target_locations=["US"],    # country codes: US, UK, CA, AU, DE, FR, JP, etc.
    adgroup_budget=50.0,        # daily USD
    schedule_days=7,            # number of days to run
    video_url="<url>",          # OR video_file="<local path>"
    image_url="<url>",          # optional thumbnail; auto-extracted from video if omitted
    ad_text="<the ad copy>",
    display_name="<brand name>",
    call_to_action="LEARN_MORE",  # SHOP_NOW, SIGN_UP, DOWNLOAD_NOW, etc.
    landing_page_url="<url>",
)
```

## How to Use the CLI

```bash
python -m tiktok_ads \
    --campaign-name "Campaign Name" \
    --objective reach \
    --campaign-budget 50 \
    --locations US UK \
    --ad-text "Your ad copy here" \
    --video-url "https://example.com/video.mp4" \
    --display-name "BrandName" \
    --cta LEARN_MORE \
    --landing-url "https://example.com"
```

## Available Operations via Python

```python
from tiktok_ads.client import TikTokAdsClient
client = TikTokAdsClient()  # reads credentials from .env

# Campaigns
client.create_campaign(campaign_name, objective_type, budget, budget_mode)
client.list_campaigns(page, page_size)
client.update_campaign(campaign_id, **fields)

# Ad Groups
client.create_ad_group(campaign_id, adgroup_name, placements, location_ids, budget, ...)
client.list_ad_groups(campaign_ids)

# Ads
client.create_ad(adgroup_id, ad_name, ad_text, video_id, image_ids, ...)
client.list_ads(adgroup_ids)
client.update_ad_status(ad_ids, "ENABLE" | "DISABLE" | "DELETE")

# Creative uploads
client.upload_video_by_url(video_url)
client.upload_video_file(file_path)
client.upload_image_by_url(image_url)
client.upload_image_file(file_path)
client.get_video_info(video_ids)

# Reporting
client.get_campaign_report(campaign_ids, start_date, end_date, metrics)
```

## Objective Types
- `reach` — Maximize impressions
- `traffic` — Drive clicks to a URL
- `video_views` — Get video views
- `conversions` — Website conversions
- `app_installs` — App installs
- `product_sales` — E-commerce sales
- `lead_generation` — Collect leads

## Location Codes
US, UK, CA, AU, DE, FR, JP, KR, BR, MX, IN, ID, TH, VN, MY, PH, SG, TW, HK, SA, AE, EG, NG, ZA

## Call-to-Action Options
LEARN_MORE, SHOP_NOW, SIGN_UP, DOWNLOAD_NOW, CONTACT_US, SUBSCRIBE, GET_QUOTE, APPLY_NOW, ORDER_NOW, BOOK_NOW, WATCH_MORE, LISTEN_NOW

## Environment
- Set `TIKTOK_ENV=sandbox` in `.env` for testing (no real money spent)
- Set `TIKTOK_ENV=production` for live ads
- To get access token: `python tiktok_ads/auth_helper.py`
