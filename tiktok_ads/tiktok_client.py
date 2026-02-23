"""
TikTok Marketing API client for fetching ad campaign data.

Supports the TikTok Business API v1.3 endpoints for:
- Campaigns, Ad Groups, and Ads
- Reporting metrics (spend, impressions, clicks, conversions, video, engagement)
- Audience / demographic breakdowns

Setup:
1. Create a TikTok for Business developer account at https://business-api.tiktok.com/portal/docs
2. Create an app and get approved
3. Generate an access token for your advertiser account
4. Set TIKTOK_ACCESS_TOKEN and TIKTOK_ADVERTISER_ID in your .env file
"""

import os
import time
import json
from datetime import datetime, timedelta
from typing import Optional

import httpx

BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"

# All available metric fields for comprehensive analysis
BASIC_METRICS = [
    "spend", "impressions", "clicks", "cpc", "cpm", "ctr",
    "reach", "frequency",
]

CONVERSION_METRICS = [
    "conversion", "cost_per_conversion", "conversion_rate",
    "real_time_conversion", "real_time_cost_per_conversion",
    "real_time_conversion_rate", "result", "cost_per_result",
    "result_rate",
]

VIDEO_METRICS = [
    "video_play_actions", "video_watched_2s", "video_watched_6s",
    "video_views_p25", "video_views_p50", "video_views_p75",
    "video_views_p100", "average_video_play",
    "average_video_play_per_user",
]

ENGAGEMENT_METRICS = [
    "likes", "comments", "shares", "follows",
    "clicks_on_music_disc", "profile_visits",
    "profile_visits_rate",
]

ATTRIBUTION_METRICS = [
    "total_purchase_value", "total_purchase",
    "purchase_roas", "complete_payment_roas",
]

ALL_METRICS = (
    BASIC_METRICS + CONVERSION_METRICS + VIDEO_METRICS
    + ENGAGEMENT_METRICS + ATTRIBUTION_METRICS
)


class TikTokAdsClient:
    """Client for the TikTok Marketing API."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        advertiser_id: Optional[str] = None,
    ):
        self.access_token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "")
        self.advertiser_id = advertiser_id or os.getenv("TIKTOK_ADVERTISER_ID", "")

        if not self.access_token:
            raise ValueError(
                "TikTok access token required. Set TIKTOK_ACCESS_TOKEN env var "
                "or pass access_token parameter."
            )
        if not self.advertiser_id:
            raise ValueError(
                "TikTok advertiser ID required. Set TIKTOK_ADVERTISER_ID env var "
                "or pass advertiser_id parameter."
            )

        self.headers = {"Access-Token": self.access_token}
        self.client = httpx.Client(headers=self.headers, timeout=30.0)

    def _get(self, endpoint: str, params: dict) -> dict:
        """Make a GET request to the TikTok API with retry logic."""
        url = f"{BASE_URL}{endpoint}"
        last_err = None
        for attempt in range(3):
            try:
                resp = self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    raise RuntimeError(
                        f"TikTok API error {data.get('code')}: {data.get('message')}"
                    )
                return data.get("data", {})
            except (httpx.HTTPStatusError, httpx.ConnectError) as e:
                last_err = e
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"TikTok API request failed after 3 attempts: {last_err}")

    # ------------------------------------------------------------------
    # Entity listing
    # ------------------------------------------------------------------

    def get_campaigns(self, status: Optional[str] = None) -> list[dict]:
        """Fetch all campaigns for the advertiser."""
        params = {
            "advertiser_id": self.advertiser_id,
            "page_size": 100,
        }
        if status:
            params["filtering"] = json.dumps(
                {"status": status}
            )
        data = self._get("/campaign/get/", params)
        return data.get("list", [])

    def get_adgroups(self, campaign_ids: Optional[list[str]] = None) -> list[dict]:
        """Fetch ad groups, optionally filtered by campaign IDs."""
        params = {
            "advertiser_id": self.advertiser_id,
            "page_size": 100,
        }
        if campaign_ids:
            params["filtering"] = json.dumps(
                {"campaign_ids": campaign_ids}
            )
        data = self._get("/adgroup/get/", params)
        return data.get("list", [])

    def get_ads(self, adgroup_ids: Optional[list[str]] = None) -> list[dict]:
        """Fetch ads, optionally filtered by ad group IDs."""
        params = {
            "advertiser_id": self.advertiser_id,
            "page_size": 100,
        }
        if adgroup_ids:
            params["filtering"] = json.dumps(
                {"adgroup_ids": adgroup_ids}
            )
        data = self._get("/ad/get/", params)
        return data.get("list", [])

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_campaign_report(
        self,
        start_date: str,
        end_date: str,
        metrics: Optional[list[str]] = None,
        lifetime: bool = False,
    ) -> list[dict]:
        """
        Get performance report at the campaign level.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            metrics: List of metric field names (defaults to ALL_METRICS)
            lifetime: If True, aggregates over the full lifetime instead of date range
        """
        return self._get_report(
            data_level="AUCTION_CAMPAIGN",
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            lifetime=lifetime,
        )

    def get_adgroup_report(
        self,
        start_date: str,
        end_date: str,
        metrics: Optional[list[str]] = None,
        lifetime: bool = False,
    ) -> list[dict]:
        """Get performance report at the ad group level."""
        return self._get_report(
            data_level="AUCTION_ADGROUP",
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            lifetime=lifetime,
        )

    def get_ad_report(
        self,
        start_date: str,
        end_date: str,
        metrics: Optional[list[str]] = None,
        lifetime: bool = False,
    ) -> list[dict]:
        """Get performance report at the individual ad level."""
        return self._get_report(
            data_level="AUCTION_AD",
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            lifetime=lifetime,
        )

    def get_daily_report(
        self,
        start_date: str,
        end_date: str,
        data_level: str = "AUCTION_CAMPAIGN",
        metrics: Optional[list[str]] = None,
    ) -> list[dict]:
        """Get day-by-day breakdown for trend analysis."""
        return self._get_report(
            data_level=data_level,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            dimensions=["stat_time_day"],
        )

    def get_demographic_report(
        self,
        start_date: str,
        end_date: str,
        dimension: str = "age",
        metrics: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Get audience demographic breakdown.

        Args:
            dimension: One of 'age', 'gender', 'country', 'province'
        """
        return self._get_report(
            data_level="AUCTION_CAMPAIGN",
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            dimensions=[dimension],
        )

    def _get_report(
        self,
        data_level: str,
        start_date: str,
        end_date: str,
        metrics: Optional[list[str]] = None,
        lifetime: bool = False,
        dimensions: Optional[list[str]] = None,
    ) -> list[dict]:
        """Internal: fetch a report from the reporting endpoint."""
        if metrics is None:
            metrics = ALL_METRICS

        params = {
            "advertiser_id": self.advertiser_id,
            "report_type": "BASIC",
            "data_level": data_level,
            "metrics": json.dumps(metrics),
            "start_date": start_date,
            "end_date": end_date,
            "page_size": 200,
        }
        if lifetime:
            params["lifetime"] = "true"
        if dimensions:
            params["dimensions"] = json.dumps(dimensions)

        data = self._get("/report/integrated/get/", params)
        return data.get("list", [])

    # ------------------------------------------------------------------
    # Convenience: fetch everything for analysis
    # ------------------------------------------------------------------

    def fetch_full_analysis_data(
        self,
        days: int = 30,
        metrics: Optional[list[str]] = None,
    ) -> dict:
        """
        Fetch a comprehensive dataset for Claude to analyze.

        Returns a dict with:
        - campaigns: campaign metadata
        - campaign_report: aggregate performance per campaign
        - daily_report: day-by-day trends
        - adgroup_report: ad group level performance
        - ad_report: individual ad performance
        - demographic_age: age breakdown
        - demographic_gender: gender breakdown
        - date_range: {start, end}
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        print(f"Fetching TikTok Ads data from {start_date} to {end_date}...")

        campaigns = self.get_campaigns()
        print(f"  Found {len(campaigns)} campaigns")

        campaign_report = self.get_campaign_report(start_date, end_date, metrics)
        print(f"  Campaign report: {len(campaign_report)} rows")

        daily_report = self.get_daily_report(start_date, end_date, metrics=metrics)
        print(f"  Daily report: {len(daily_report)} rows")

        adgroup_report = self.get_adgroup_report(start_date, end_date, metrics)
        print(f"  Ad group report: {len(adgroup_report)} rows")

        ad_report = self.get_ad_report(start_date, end_date, metrics)
        print(f"  Ad report: {len(ad_report)} rows")

        age_report = self.get_demographic_report(
            start_date, end_date, dimension="age", metrics=metrics
        )
        print(f"  Age demographic: {len(age_report)} rows")

        gender_report = self.get_demographic_report(
            start_date, end_date, dimension="gender", metrics=metrics
        )
        print(f"  Gender demographic: {len(gender_report)} rows")

        return {
            "date_range": {"start": start_date, "end": end_date},
            "campaigns": campaigns,
            "campaign_report": campaign_report,
            "daily_report": daily_report,
            "adgroup_report": adgroup_report,
            "ad_report": ad_report,
            "demographic_age": age_report,
            "demographic_gender": gender_report,
        }

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
