"""
TikTok Ads API Client
Handles HTTP requests to the TikTok Marketing API v1.3 for campaign,
ad group, and ad creation.
"""

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"
SANDBOX_URL = "https://sandbox-ads.tiktok.com/open_api/v1.3"


class TikTokAdsClient:
    """Client for the TikTok Marketing API."""

    def __init__(
        self,
        access_token: str | None = None,
        advertiser_id: str | None = None,
        sandbox: bool = False,
    ):
        self.access_token = access_token or os.environ.get("TIKTOK_ACCESS_TOKEN", "")
        self.advertiser_id = advertiser_id or os.environ.get("TIKTOK_ADVERTISER_ID", "")
        self.base_url = SANDBOX_URL if sandbox else BASE_URL
        self._client = httpx.Client(timeout=30.0)

        if not self.access_token:
            raise ValueError(
                "TikTok access token is required. "
                "Set TIKTOK_ACCESS_TOKEN env var or pass access_token."
            )
        if not self.advertiser_id:
            raise ValueError(
                "TikTok advertiser ID is required. "
                "Set TIKTOK_ADVERTISER_ID env var or pass advertiser_id."
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        logger.info("TikTok API %s %s", method, url)

        if method == "GET":
            resp = self._client.get(url, headers=self._headers(), params=payload)
        else:
            resp = self._client.post(url, headers=self._headers(), json=payload)

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            error_msg = data.get("message", "Unknown error")
            logger.error("TikTok API error: %s (code=%s)", error_msg, data.get("code"))
            return {"success": False, "error": error_msg, "code": data.get("code"), "data": data}

        return {"success": True, "data": data.get("data", {})}

    # ---- Campaign endpoints ----

    def create_campaign(
        self,
        campaign_name: str,
        objective_type: str,
        budget: float | None = None,
        budget_mode: str = "BUDGET_MODE_INFINITE",
    ) -> dict:
        """Create a new ad campaign.

        Args:
            campaign_name: Name for the campaign.
            objective_type: Campaign objective. One of:
                REACH, TRAFFIC, VIDEO_VIEWS, LEAD_GENERATION,
                COMMUNITY_INTERACTION, APP_PROMOTION, WEB_CONVERSIONS,
                PRODUCT_SALES, ENGAGEMENT.
            budget: Budget amount (required if budget_mode is not INFINITE).
            budget_mode: BUDGET_MODE_DAY, BUDGET_MODE_TOTAL, or BUDGET_MODE_INFINITE.
        """
        payload: dict[str, Any] = {
            "advertiser_id": self.advertiser_id,
            "campaign_name": campaign_name,
            "objective_type": objective_type,
            "budget_mode": budget_mode,
        }
        if budget is not None:
            payload["budget"] = budget

        return self._request("POST", "/campaign/create/", payload)

    def get_campaigns(self) -> dict:
        """List all campaigns for the advertiser."""
        payload = {"advertiser_id": self.advertiser_id}
        return self._request("GET", "/campaign/get/", payload)

    # ---- Ad Group endpoints ----

    def create_adgroup(
        self,
        campaign_id: str,
        adgroup_name: str,
        placement_type: str = "PLACEMENT_TYPE_AUTOMATIC",
        placements: list[str] | None = None,
        location_ids: list[int] | None = None,
        age_groups: list[str] | None = None,
        gender: str = "GENDER_UNLIMITED",
        budget: float | None = None,
        budget_mode: str = "BUDGET_MODE_DAY",
        schedule_type: str = "SCHEDULE_FROM_NOW",
        schedule_start_time: str | None = None,
        schedule_end_time: str | None = None,
        optimize_goal: str = "CLICK",
        billing_event: str = "CPC",
        bid_type: str = "BID_TYPE_NO_BID",
        bid: float | None = None,
        pacing: str = "PACING_MODE_SMOOTH",
    ) -> dict:
        """Create a new ad group within a campaign.

        Args:
            campaign_id: ID of the parent campaign.
            adgroup_name: Name for the ad group.
            placement_type: PLACEMENT_TYPE_AUTOMATIC or PLACEMENT_TYPE_NORMAL.
            placements: List of placements when using NORMAL type.
                e.g. ["PLACEMENT_TIKTOK", "PLACEMENT_PANGLE"].
            location_ids: List of location IDs for geo-targeting.
                e.g. [6252001] for United States.
            age_groups: List of age ranges. e.g. ["AGE_18_24", "AGE_25_34"].
            gender: GENDER_UNLIMITED, GENDER_MALE, or GENDER_FEMALE.
            budget: Budget amount.
            budget_mode: BUDGET_MODE_DAY or BUDGET_MODE_TOTAL.
            schedule_type: SCHEDULE_FROM_NOW or SCHEDULE_START_END.
            schedule_start_time: Start time (format: "2026-03-01 00:00:00").
            schedule_end_time: End time (format: "2026-04-01 00:00:00").
            optimize_goal: CLICK, REACH, SHOW, CONVERT, etc.
            billing_event: CPC, CPM, CPV, OCPM, etc.
            bid_type: BID_TYPE_NO_BID, BID_TYPE_CUSTOM, BID_TYPE_MAX.
            bid: Bid amount if using custom bidding.
            pacing: PACING_MODE_SMOOTH or PACING_MODE_FAST.
        """
        payload: dict[str, Any] = {
            "advertiser_id": self.advertiser_id,
            "campaign_id": campaign_id,
            "adgroup_name": adgroup_name,
            "placement_type": placement_type,
            "gender": gender,
            "budget_mode": budget_mode,
            "schedule_type": schedule_type,
            "optimize_goal": optimize_goal,
            "billing_event": billing_event,
            "bid_type": bid_type,
            "pacing": pacing,
        }

        if placements:
            payload["placements"] = placements
        if location_ids:
            payload["location_ids"] = location_ids
        if age_groups:
            payload["age_groups"] = age_groups
        if budget is not None:
            payload["budget"] = budget
        if schedule_start_time:
            payload["schedule_start_time"] = schedule_start_time
        if schedule_end_time:
            payload["schedule_end_time"] = schedule_end_time
        if bid is not None:
            payload["bid"] = bid

        return self._request("POST", "/adgroup/create/", payload)

    # ---- Ad endpoints ----

    def create_ad(
        self,
        adgroup_id: str,
        ad_name: str,
        ad_text: str,
        video_id: str | None = None,
        image_ids: list[str] | None = None,
        call_to_action: str = "LEARN_MORE",
        landing_page_url: str | None = None,
        display_name: str | None = None,
        identity_id: str | None = None,
        identity_type: str = "CUSTOMIZED_USER",
    ) -> dict:
        """Create a new ad within an ad group.

        Args:
            adgroup_id: ID of the parent ad group.
            ad_name: Name for the ad.
            ad_text: The ad copy / caption text.
            video_id: TikTok video ID for video ads.
            image_ids: List of image IDs for image ads.
            call_to_action: CTA button text. One of:
                LEARN_MORE, SHOP_NOW, SIGN_UP, DOWNLOAD, CONTACT_US,
                SUBSCRIBE, GET_QUOTE, APPLY_NOW, BOOK_NOW, ORDER_NOW,
                GET_SHOWTIMES, LISTEN_NOW, INSTALL_NOW, PLAY_GAME.
            landing_page_url: URL for the landing page.
            display_name: Display name shown on the ad.
            identity_id: TikTok identity ID for the ad.
            identity_type: CUSTOMIZED_USER or AUTH_CODE.
        """
        creatives: dict[str, Any] = {
            "ad_text": ad_text,
            "call_to_action": call_to_action,
            "identity_type": identity_type,
        }

        if video_id:
            creatives["video_id"] = video_id
        if image_ids:
            creatives["image_ids"] = image_ids
        if landing_page_url:
            creatives["landing_page_url"] = landing_page_url
        if display_name:
            creatives["display_name"] = display_name
        if identity_id:
            creatives["identity_id"] = identity_id

        payload: dict[str, Any] = {
            "advertiser_id": self.advertiser_id,
            "adgroup_id": adgroup_id,
            "creatives": [creatives],
        }
        # ad_name is top-level
        payload["ad_name"] = ad_name

        return self._request("POST", "/ad/create/", payload)

    # ---- Utility endpoints ----

    def get_adgroups(self, campaign_id: str | None = None) -> dict:
        """List ad groups, optionally filtered by campaign."""
        payload: dict[str, Any] = {"advertiser_id": self.advertiser_id}
        if campaign_id:
            payload["filtering"] = json.dumps({"campaign_ids": [campaign_id]})
        return self._request("GET", "/adgroup/get/", payload)

    def get_ads(self, adgroup_id: str | None = None) -> dict:
        """List ads, optionally filtered by ad group."""
        payload: dict[str, Any] = {"advertiser_id": self.advertiser_id}
        if adgroup_id:
            payload["filtering"] = json.dumps({"adgroup_ids": [adgroup_id]})
        return self._request("GET", "/ad/get/", payload)

    def upload_video(self, video_file_path: str) -> dict:
        """Upload a video file for use in ads."""
        url = f"{self.base_url}/file/video/ad/upload/"
        with open(video_file_path, "rb") as f:
            resp = self._client.post(
                url,
                headers={"Access-Token": self.access_token},
                data={"advertiser_id": self.advertiser_id},
                files={"video_file": f},
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            return {"success": False, "error": data.get("message"), "data": data}
        return {"success": True, "data": data.get("data", {})}

    def upload_image(self, image_file_path: str) -> dict:
        """Upload an image file for use in ads."""
        url = f"{self.base_url}/file/image/ad/upload/"
        with open(image_file_path, "rb") as f:
            resp = self._client.post(
                url,
                headers={"Access-Token": self.access_token},
                data={"advertiser_id": self.advertiser_id},
                files={"image_file": f},
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            return {"success": False, "error": data.get("message"), "data": data}
        return {"success": True, "data": data.get("data", {})}
