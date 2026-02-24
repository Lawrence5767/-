#!/usr/bin/env python3
"""CLI entry point to create a TikTok ad.

Usage examples:

    # Minimal — uses defaults (reach objective, US, $50/day, 7 days)
    python -m tiktok_ads.create_ad \
        --campaign-name "Summer Sale 2026" \
        --ad-text "Shop our biggest sale ever!" \
        --video-url "https://example.com/video.mp4"

    # Full control
    python -m tiktok_ads.create_ad \
        --campaign-name "App Launch Q1" \
        --objective app_installs \
        --campaign-budget 100 \
        --locations US UK CA \
        --adgroup-budget 80 \
        --schedule-days 14 \
        --video-url "https://example.com/promo.mp4" \
        --ad-text "Download our new app today!" \
        --display-name "MyBrand" \
        --cta DOWNLOAD_NOW \
        --landing-url "https://example.com/app"
"""

import argparse
import json
import sys
from tiktok_ads.automation import create_full_ad, CTA_OPTIONS, OBJECTIVES, LOCATION_CODES


def main():
    parser = argparse.ArgumentParser(
        description="Create a TikTok ad (campaign + ad group + ad) in one command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Campaign
    parser.add_argument("--campaign-name", required=True, help="Campaign name (must be unique)")
    parser.add_argument(
        "--objective", default="reach",
        choices=list(OBJECTIVES.keys()),
        help="Campaign objective (default: reach)",
    )
    parser.add_argument("--campaign-budget", type=float, default=50.0, help="Daily campaign budget in USD (default: 50)")

    # Ad Group
    parser.add_argument("--adgroup-name", help="Ad group name (defaults to campaign name + '- Ad Group')")
    parser.add_argument(
        "--locations", nargs="+", default=["US"],
        help=f"Target countries, e.g. US UK CA. Available: {', '.join(sorted(LOCATION_CODES.keys()))}",
    )
    parser.add_argument("--adgroup-budget", type=float, default=50.0, help="Daily ad group budget (default: 50)")
    parser.add_argument("--schedule-days", type=int, default=7, help="Run for N days (default: 7)")
    parser.add_argument("--schedule-start", help="Start time 'YYYY-MM-DD HH:MM:SS' (default: 1 hour from now)")
    parser.add_argument("--age-groups", nargs="+", help="Age targeting, e.g. AGE_25_34 AGE_35_44")
    parser.add_argument("--gender", choices=["GENDER_MALE", "GENDER_FEMALE", "GENDER_UNLIMITED"], help="Gender targeting")

    # Creative
    parser.add_argument("--video-url", help="URL of the video creative")
    parser.add_argument("--video-file", help="Local path to video file")
    parser.add_argument("--image-url", help="URL of thumbnail image")
    parser.add_argument("--image-file", help="Local path to thumbnail image")

    # Ad
    parser.add_argument("--ad-name", help="Ad name (defaults to campaign name + '- Ad')")
    parser.add_argument("--ad-text", default="", help="Promotional text shown to users")
    parser.add_argument("--display-name", help="Brand name shown on the ad")
    parser.add_argument("--cta", choices=CTA_OPTIONS, help="Call-to-action button")
    parser.add_argument("--landing-url", help="Landing page URL")

    # Environment
    parser.add_argument("--env", choices=["sandbox", "production"], help="Override TIKTOK_ENV setting")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    print(f"Creating TikTok ad: {args.campaign_name}")
    print(f"Environment: {args.env or '(from .env)'}")
    print(f"Objective: {args.objective}")
    print(f"Locations: {args.locations}")

    try:
        results = create_full_ad(
            campaign_name=args.campaign_name,
            objective=args.objective,
            campaign_budget=args.campaign_budget,
            adgroup_name=args.adgroup_name,
            target_locations=args.locations,
            adgroup_budget=args.adgroup_budget,
            schedule_days=args.schedule_days,
            schedule_start=args.schedule_start,
            age_groups=args.age_groups,
            gender=args.gender,
            video_url=args.video_url,
            video_file=args.video_file,
            image_url=args.image_url,
            image_file=args.image_file,
            ad_name=args.ad_name,
            ad_text=args.ad_text,
            display_name=args.display_name,
            call_to_action=args.cta,
            landing_page_url=args.landing_url,
            env=args.env,
        )

        if args.json:
            # Serialize for JSON output (convert non-serializable types)
            print(json.dumps(results, indent=2, default=str))

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
