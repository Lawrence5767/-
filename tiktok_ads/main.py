#!/usr/bin/env python3
"""
TikTok Ads Analyzer — powered by Claude.

Fetches your TikTok ad data and sends it to Claude for comprehensive analysis.

Usage:
    # Basic analysis (last 30 days)
    python tiktok_ads/main.py

    # Custom date range
    python tiktok_ads/main.py --days 7

    # With specific questions
    python tiktok_ads/main.py --question "Which campaign should I scale?"

    # Interactive mode (ask follow-up questions)
    python tiktok_ads/main.py --interactive

    # Export analysis to file
    python tiktok_ads/main.py --output report.md

    # Use demo data (no TikTok credentials needed — for testing)
    python tiktok_ads/main.py --demo
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the tiktok_ads directory or project root
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

from tiktok_client import TikTokAdsClient
from analyzer import analyze_ads, ask_followup


DEMO_DATA = {
    "date_range": {"start": "2026-01-24", "end": "2026-02-23"},
    "campaigns": [
        {
            "campaign_id": "1001",
            "campaign_name": "Spring Sale - Awareness",
            "objective_type": "REACH",
            "status": "CAMPAIGN_STATUS_ENABLE",
            "budget": 5000.00,
            "budget_mode": "BUDGET_MODE_DAY",
        },
        {
            "campaign_id": "1002",
            "campaign_name": "Spring Sale - Conversions",
            "objective_type": "CONVERSIONS",
            "status": "CAMPAIGN_STATUS_ENABLE",
            "budget": 8000.00,
            "budget_mode": "BUDGET_MODE_DAY",
        },
        {
            "campaign_id": "1003",
            "campaign_name": "Brand Video - Engagement",
            "objective_type": "VIDEO_VIEWS",
            "status": "CAMPAIGN_STATUS_ENABLE",
            "budget": 3000.00,
            "budget_mode": "BUDGET_MODE_DAY",
        },
    ],
    "campaign_report": [
        {
            "dimensions": {"campaign_id": "1001"},
            "metrics": {
                "campaign_name": "Spring Sale - Awareness",
                "spend": "4823.50", "impressions": "892340", "clicks": "15678",
                "ctr": "1.76", "cpc": "0.31", "cpm": "5.41",
                "reach": "654210", "frequency": "1.36",
                "conversion": "0", "cost_per_conversion": "0",
                "video_play_actions": "567890", "video_views_p25": "423100",
                "video_views_p50": "298450", "video_views_p75": "187600",
                "video_views_p100": "112340",
                "likes": "8934", "comments": "1234", "shares": "2345",
                "follows": "567", "profile_visits": "3456",
            },
        },
        {
            "dimensions": {"campaign_id": "1002"},
            "metrics": {
                "campaign_name": "Spring Sale - Conversions",
                "spend": "7456.80", "impressions": "534210", "clicks": "12890",
                "ctr": "2.41", "cpc": "0.58", "cpm": "13.96",
                "reach": "412340", "frequency": "1.30",
                "conversion": "834", "cost_per_conversion": "8.94",
                "conversion_rate": "6.47",
                "total_purchase_value": "41700.00", "total_purchase": "834",
                "purchase_roas": "5.59",
                "video_play_actions": "345670", "video_views_p25": "267800",
                "video_views_p50": "189340", "video_views_p75": "134560",
                "video_views_p100": "89230",
                "likes": "5678", "comments": "890", "shares": "1567",
                "follows": "234", "profile_visits": "2345",
            },
        },
        {
            "dimensions": {"campaign_id": "1003"},
            "metrics": {
                "campaign_name": "Brand Video - Engagement",
                "spend": "2890.20", "impressions": "678450", "clicks": "8234",
                "ctr": "1.21", "cpc": "0.35", "cpm": "4.26",
                "reach": "543210", "frequency": "1.25",
                "conversion": "0", "cost_per_conversion": "0",
                "video_play_actions": "498760", "video_views_p25": "387650",
                "video_views_p50": "276540", "video_views_p75": "198760",
                "video_views_p100": "145670",
                "likes": "12345", "comments": "3456", "shares": "5678",
                "follows": "890", "profile_visits": "5678",
            },
        },
    ],
    "daily_report": [
        {"dimensions": {"stat_time_day": f"2026-02-{d:02d}"}, "metrics": {
            "spend": str(round(450 + (d % 7) * 30 + (d * 13 % 50), 2)),
            "impressions": str(58000 + d * 1200 + (d * 37 % 5000)),
            "clicks": str(1050 + d * 20 + (d * 7 % 200)),
            "ctr": str(round(1.5 + (d % 5) * 0.15, 2)),
            "conversion": str(25 + (d * 3 % 15)),
            "cost_per_conversion": str(round(8.5 + (d % 4) * 0.5, 2)),
        }}
        for d in range(1, 24)
    ],
    "adgroup_report": [
        {
            "dimensions": {"adgroup_id": "2001"},
            "metrics": {
                "adgroup_name": "Awareness - Women 18-34",
                "spend": "2456.30", "impressions": "534120", "clicks": "9234",
                "ctr": "1.73", "cpc": "0.27", "conversion": "0",
            },
        },
        {
            "dimensions": {"adgroup_id": "2002"},
            "metrics": {
                "adgroup_name": "Awareness - Men 18-34",
                "spend": "2367.20", "impressions": "358220", "clicks": "6444",
                "ctr": "1.80", "cpc": "0.37", "conversion": "0",
            },
        },
        {
            "dimensions": {"adgroup_id": "2003"},
            "metrics": {
                "adgroup_name": "Conversions - Lookalike Purchasers",
                "spend": "4234.50", "impressions": "312340", "clicks": "8456",
                "ctr": "2.71", "cpc": "0.50",
                "conversion": "567", "cost_per_conversion": "7.47",
                "purchase_roas": "6.12",
            },
        },
        {
            "dimensions": {"adgroup_id": "2004"},
            "metrics": {
                "adgroup_name": "Conversions - Interest Targeting",
                "spend": "3222.30", "impressions": "221870", "clicks": "4434",
                "ctr": "2.00", "cpc": "0.73",
                "conversion": "267", "cost_per_conversion": "12.07",
                "purchase_roas": "4.14",
            },
        },
        {
            "dimensions": {"adgroup_id": "2005"},
            "metrics": {
                "adgroup_name": "Engagement - Broad",
                "spend": "2890.20", "impressions": "678450", "clicks": "8234",
                "ctr": "1.21", "cpc": "0.35", "conversion": "0",
            },
        },
    ],
    "ad_report": [
        {
            "dimensions": {"ad_id": "3001"},
            "metrics": {
                "ad_name": "Spring UGC - Unboxing",
                "spend": "3456.70", "impressions": "423100", "clicks": "10234",
                "ctr": "2.42", "cpc": "0.34",
                "conversion": "456", "cost_per_conversion": "7.58",
                "video_views_p100": "67890",
                "likes": "6789", "shares": "3456",
            },
        },
        {
            "dimensions": {"ad_id": "3002"},
            "metrics": {
                "ad_name": "Spring Sale - Product Showcase",
                "spend": "4000.10", "impressions": "111110", "clicks": "2656",
                "ctr": "2.39", "cpc": "1.51",
                "conversion": "378", "cost_per_conversion": "10.58",
                "video_views_p100": "34560",
                "likes": "2345", "shares": "890",
            },
        },
        {
            "dimensions": {"ad_id": "3003"},
            "metrics": {
                "ad_name": "Brand Story - Behind the Scenes",
                "spend": "2890.20", "impressions": "678450", "clicks": "8234",
                "ctr": "1.21", "cpc": "0.35",
                "conversion": "0", "cost_per_conversion": "0",
                "video_views_p100": "145670",
                "likes": "12345", "shares": "5678",
            },
        },
        {
            "dimensions": {"ad_id": "3004"},
            "metrics": {
                "ad_name": "Spring Sale - Testimonial",
                "spend": "4823.50", "impressions": "892340", "clicks": "15678",
                "ctr": "1.76", "cpc": "0.31",
                "conversion": "0", "cost_per_conversion": "0",
                "video_views_p100": "112340",
                "likes": "8934", "shares": "2345",
            },
        },
    ],
    "demographic_age": [
        {"dimensions": {"age": "AGE_18_24"}, "metrics": {
            "spend": "4567.80", "impressions": "678900", "clicks": "14234",
            "ctr": "2.10", "conversion": "345", "cost_per_conversion": "13.24",
        }},
        {"dimensions": {"age": "AGE_25_34"}, "metrics": {
            "spend": "5678.90", "impressions": "534210", "clicks": "12345",
            "ctr": "2.31", "conversion": "378", "cost_per_conversion": "15.02",
        }},
        {"dimensions": {"age": "AGE_35_44"}, "metrics": {
            "spend": "3456.70", "impressions": "345670", "clicks": "7890",
            "ctr": "2.28", "conversion": "89", "cost_per_conversion": "38.84",
        }},
        {"dimensions": {"age": "AGE_45_54"}, "metrics": {
            "spend": "1234.50", "impressions": "198760", "clicks": "2345",
            "ctr": "1.18", "conversion": "22", "cost_per_conversion": "56.11",
        }},
    ],
    "demographic_gender": [
        {"dimensions": {"gender": "FEMALE"}, "metrics": {
            "spend": "8456.70", "impressions": "1123450", "clicks": "23456",
            "ctr": "2.09", "conversion": "567", "cost_per_conversion": "14.92",
        }},
        {"dimensions": {"gender": "MALE"}, "metrics": {
            "spend": "6714.30", "impressions": "981550", "clicks": "13358",
            "ctr": "1.36", "conversion": "267", "cost_per_conversion": "25.15",
        }},
    ],
}


def main():
    parser = argparse.ArgumentParser(
        description="TikTok Ads Analyzer — powered by Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Number of days to analyze (default: 30)",
    )
    parser.add_argument(
        "--question", "-q", action="append", default=[],
        help="Specific question(s) to ask (can be repeated)",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Enter interactive mode for follow-up questions",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save analysis to a markdown file",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Use demo data instead of live TikTok API (no credentials needed)",
    )
    parser.add_argument(
        "--model", type=str, default="claude-opus-4-6",
        help="Claude model to use (default: claude-opus-4-6)",
    )

    args = parser.parse_args()

    # ---- Fetch data ----
    if args.demo:
        print("Using demo data (no TikTok API call).\n")
        data = DEMO_DATA
    else:
        missing = []
        if not os.getenv("TIKTOK_ACCESS_TOKEN"):
            missing.append("TIKTOK_ACCESS_TOKEN")
        if not os.getenv("TIKTOK_ADVERTISER_ID"):
            missing.append("TIKTOK_ADVERTISER_ID")
        if not os.getenv("ANTHROPIC_API_KEY"):
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            print("Missing required environment variables:")
            for var in missing:
                print(f"  - {var}")
            print("\nSee tiktok_ads/.env.example for setup instructions.")
            print("Or use --demo to test with sample data.\n")
            sys.exit(1)

        with TikTokAdsClient() as client:
            data = client.fetch_full_analysis_data(days=args.days)

    # ---- Analyze ----
    print("\n" + "=" * 60)
    print("  TIKTOK ADS ANALYSIS — POWERED BY CLAUDE")
    print("=" * 60 + "\n")

    analysis = analyze_ads(
        tiktok_data=data,
        model=args.model,
        custom_questions=args.question if args.question else None,
    )

    # ---- Save output ----
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(analysis, encoding="utf-8")
        print(f"\nAnalysis saved to {output_path}")

    # ---- Interactive follow-up ----
    if args.interactive:
        print("\n" + "-" * 60)
        print("Interactive mode — ask follow-up questions (type 'quit' to exit)")
        print("-" * 60)

        while True:
            try:
                question = input("\nYour question: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not question or question.lower() in ("quit", "exit", "q"):
                print("Exiting interactive mode.")
                break

            followup = ask_followup(
                tiktok_data=data,
                previous_analysis=analysis,
                question=question,
                model=args.model,
            )

            if args.output:
                with open(args.output, "a", encoding="utf-8") as f:
                    f.write(f"\n\n---\n\n**Follow-up: {question}**\n\n{followup}")


if __name__ == "__main__":
    main()
