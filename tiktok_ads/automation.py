"""High-level automation for TikTok ad creation.

Provides a single function `create_full_ad` that orchestrates the entire
workflow: upload creative → create campaign → create ad group → create ad.
"""

import time
from datetime import datetime, timedelta
from tiktok_ads.client import TikTokAdsClient


# TikTok location codes for common countries
LOCATION_CODES = {
    "US": "6252001",
    "UK": "2635167",
    "CA": "6251999",
    "AU": "2077456",
    "DE": "2921044",
    "FR": "3017382",
    "JP": "1861060",
    "KR": "1835841",
    "BR": "3469034",
    "MX": "3996063",
    "IN": "1269750",
    "ID": "1643084",
    "TH": "1605651",
    "VN": "1562822",
    "MY": "1733045",
    "PH": "1694008",
    "SG": "1880251",
    "TW": "1668284",
    "HK": "1819730",
    "SA": "102358",
    "AE": "290557",
    "EG": "357994",
    "NG": "2328926",
    "ZA": "953987",
}

# Common objective types
OBJECTIVES = {
    "reach": "REACH",
    "traffic": "TRAFFIC",
    "video_views": "VIDEO_VIEWS",
    "lead_generation": "LEAD_GENERATION",
    "conversions": "WEBSITE_CONVERSIONS",
    "app_installs": "APP_INSTALLS",
    "product_sales": "PRODUCT_SALES",
}

# Common call-to-action values
CTA_OPTIONS = [
    "LEARN_MORE", "SHOP_NOW", "SIGN_UP", "DOWNLOAD_NOW",
    "CONTACT_US", "SUBSCRIBE", "GET_QUOTE", "APPLY_NOW",
    "ORDER_NOW", "BOOK_NOW", "WATCH_MORE", "LISTEN_NOW",
]


def resolve_locations(locations):
    """Convert country names/codes to TikTok location IDs.

    Accepts a list of 2-letter country codes or full country names.
    Returns a list of TikTok location ID strings.
    """
    result = []
    for loc in locations:
        loc_upper = loc.upper().strip()
        if loc_upper in LOCATION_CODES:
            result.append(LOCATION_CODES[loc_upper])
        else:
            # Try matching by country name (case-insensitive)
            for code, loc_id in LOCATION_CODES.items():
                if loc.lower() in code.lower():
                    result.append(loc_id)
                    break
            else:
                # Assume it's already a numeric location ID
                result.append(str(loc))
    return result


def create_full_ad(
    # Campaign settings
    campaign_name,
    objective="reach",
    campaign_budget=50.0,
    # Ad group settings
    adgroup_name=None,
    target_locations=None,
    adgroup_budget=50.0,
    schedule_days=7,
    schedule_start=None,
    age_groups=None,
    gender=None,
    # Creative settings
    video_url=None,
    video_file=None,
    image_url=None,
    image_file=None,
    # Ad settings
    ad_name=None,
    ad_text="",
    display_name=None,
    call_to_action=None,
    landing_page_url=None,
    # Client settings
    access_token=None,
    advertiser_id=None,
    env=None,
):
    """Create a complete TikTok ad from scratch: campaign + ad group + ad.

    This is the main automation entry point. It handles the full workflow:
    1. Upload video/image creative assets
    2. Create a campaign
    3. Create an ad group with targeting
    4. Create the ad with creative

    Args:
        campaign_name: Name for the campaign.
        objective: Campaign objective (reach, traffic, video_views, conversions,
                   app_installs, product_sales, lead_generation).
        campaign_budget: Daily budget for the campaign.
        adgroup_name: Name for ad group (defaults to campaign_name + " - Ad Group").
        target_locations: List of country codes like ["US", "UK"]. Defaults to ["US"].
        adgroup_budget: Daily budget for the ad group.
        schedule_days: How many days to run the ad (from start date).
        schedule_start: Start datetime string "YYYY-MM-DD HH:MM:SS".
                        Defaults to now.
        age_groups: Optional list like ["AGE_25_34", "AGE_35_44"].
        gender: Optional "GENDER_MALE" | "GENDER_FEMALE" | "GENDER_UNLIMITED".
        video_url: URL of video to use as creative.
        video_file: Local path to video file.
        image_url: URL of thumbnail image.
        image_file: Local path to thumbnail image.
        ad_name: Name for the ad (defaults to campaign_name + " - Ad").
        ad_text: Promotional text shown to users.
        display_name: Brand name shown on the ad.
        call_to_action: CTA button (LEARN_MORE, SHOP_NOW, etc.).
        landing_page_url: Where users go when they click the ad.
        access_token: Override access token.
        advertiser_id: Override advertiser ID.
        env: Override environment (sandbox/production).

    Returns:
        dict with campaign_id, adgroup_id, ad_id, and all intermediate results.
    """
    client = TikTokAdsClient(
        access_token=access_token,
        advertiser_id=advertiser_id,
        env=env,
    )

    results = {"steps": []}

    def log_step(name, data):
        results["steps"].append({"step": name, "result": data})
        print(f"  [OK] {name}")

    # Defaults
    if not adgroup_name:
        adgroup_name = f"{campaign_name} - Ad Group"
    if not ad_name:
        ad_name = f"{campaign_name} - Ad"
    if not target_locations:
        target_locations = ["US"]

    location_ids = resolve_locations(target_locations)
    objective_type = OBJECTIVES.get(objective.lower(), objective.upper())

    # Schedule
    if not schedule_start:
        schedule_start = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    schedule_end = (
        datetime.strptime(schedule_start, "%Y-%m-%d %H:%M:%S") + timedelta(days=schedule_days)
    ).strftime("%Y-%m-%d %H:%M:%S")

    # ------------------------------------------------------------------
    # Step 1: Upload creative assets
    # ------------------------------------------------------------------
    print("\n--- Step 1: Upload Creative Assets ---")
    video_id = None
    image_ids = None

    if video_url:
        data = client.upload_video_by_url(video_url)
        video_id = data.get("video_id")
        log_step("Upload video (URL)", data)
    elif video_file:
        data = client.upload_video_file(video_file)
        video_id = data.get("video_id")
        log_step("Upload video (file)", data)

    if image_url:
        data = client.upload_image_by_url(image_url)
        image_ids = [data.get("image_id")]
        log_step("Upload image (URL)", data)
    elif image_file:
        data = client.upload_image_file(image_file)
        image_ids = [data.get("image_id")]
        log_step("Upload image (file)", data)
    elif video_id:
        # Try to get auto-generated thumbnail from the video
        print("  Waiting for video processing...")
        time.sleep(5)
        try:
            info = client.get_video_info([video_id])
            videos = info.get("list", [])
            if videos and videos[0].get("poster_url"):
                poster_url = videos[0]["poster_url"]
                img_data = client.upload_image_by_url(poster_url)
                image_ids = [img_data.get("image_id")]
                log_step("Upload auto-thumbnail", img_data)
        except Exception as e:
            print(f"  [WARN] Could not get auto-thumbnail: {e}")

    # ------------------------------------------------------------------
    # Step 2: Create campaign
    # ------------------------------------------------------------------
    print("\n--- Step 2: Create Campaign ---")
    campaign_data = client.create_campaign(
        campaign_name=campaign_name,
        objective_type=objective_type,
        budget=campaign_budget,
        budget_mode="BUDGET_MODE_DAY",
    )
    campaign_id = campaign_data.get("campaign_id")
    results["campaign_id"] = campaign_id
    log_step(f"Create campaign (ID: {campaign_id})", campaign_data)

    # ------------------------------------------------------------------
    # Step 3: Create ad group
    # ------------------------------------------------------------------
    print("\n--- Step 3: Create Ad Group ---")
    adgroup_data = client.create_ad_group(
        campaign_id=campaign_id,
        adgroup_name=adgroup_name,
        placements=["PLACEMENT_TIKTOK"],
        location_ids=location_ids,
        budget=adgroup_budget,
        schedule_start_time=schedule_start,
        schedule_end_time=schedule_end,
        optimize_goal=objective_type if objective_type in ("REACH", "CLICK") else "CLICK",
        budget_mode="BUDGET_MODE_DAY",
        age_groups=age_groups,
        gender=gender,
    )
    adgroup_id = adgroup_data.get("adgroup_id")
    results["adgroup_id"] = adgroup_id
    log_step(f"Create ad group (ID: {adgroup_id})", adgroup_data)

    # ------------------------------------------------------------------
    # Step 4: Create ad
    # ------------------------------------------------------------------
    print("\n--- Step 4: Create Ad ---")
    ad_format = "SINGLE_VIDEO" if video_id else "SINGLE_IMAGE"
    ad_data = client.create_ad(
        adgroup_id=adgroup_id,
        ad_name=ad_name,
        ad_text=ad_text,
        video_id=video_id,
        image_ids=image_ids,
        ad_format=ad_format,
        display_name=display_name,
        call_to_action=call_to_action,
        landing_page_url=landing_page_url,
    )
    ad_ids = ad_data.get("ad_ids", [])
    results["ad_ids"] = ad_ids
    log_step(f"Create ad (IDs: {ad_ids})", ad_data)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n--- Ad Creation Complete ---")
    print(f"  Campaign ID : {campaign_id}")
    print(f"  Ad Group ID : {adgroup_id}")
    print(f"  Ad ID(s)    : {ad_ids}")
    print(f"  Objective   : {objective_type}")
    print(f"  Locations   : {target_locations}")
    print(f"  Schedule    : {schedule_start} → {schedule_end}")
    print(f"  Budget      : ${campaign_budget}/day (campaign), ${adgroup_budget}/day (ad group)")

    return results
