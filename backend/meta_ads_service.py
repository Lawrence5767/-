"""
Meta Ads Manager - Marketing API Service
Handles all interactions with the Meta (Facebook) Marketing API.

Hierarchy: Campaign -> Ad Set -> Ad (uses Ad Creative)
API Docs: https://developers.facebook.com/docs/marketing-apis

Required environment variables:
  META_ACCESS_TOKEN  - Meta user/system-user access token
  META_AD_ACCOUNT_ID - Ad account ID (format: act_XXXXXXXXXX)
  META_APP_ID        - (optional) Meta App ID
  META_APP_SECRET    - (optional) Meta App Secret
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx


META_API_VERSION = "v21.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


@dataclass
class MetaAdsConfig:
    access_token: str = ""
    ad_account_id: str = ""
    page_id: str = ""

    @classmethod
    def from_env(cls) -> "MetaAdsConfig":
        return cls(
            access_token=os.environ.get("META_ACCESS_TOKEN", ""),
            ad_account_id=os.environ.get("META_AD_ACCOUNT_ID", ""),
            page_id=os.environ.get("META_PAGE_ID", ""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token and self.ad_account_id)


class MetaAdsService:
    """Client for the Meta Marketing API."""

    def __init__(self, config: Optional[MetaAdsConfig] = None):
        self.config = config or MetaAdsConfig.from_env()
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated request to the Meta Marketing API."""
        if not self.config.is_configured:
            raise ValueError(
                "Meta Ads not configured. Set META_ACCESS_TOKEN and META_AD_ACCOUNT_ID."
            )

        url = f"{META_BASE_URL}/{endpoint}"
        params = kwargs.pop("params", {})
        params["access_token"] = self.config.access_token

        resp = await self._client.request(method, url, params=params, **kwargs)
        data = resp.json()

        if "error" in data:
            err = data["error"]
            raise MetaAdsAPIError(
                message=err.get("message", "Unknown error"),
                error_type=err.get("type", ""),
                code=err.get("code", 0),
                fbtrace_id=err.get("fbtrace_id", ""),
            )

        return data

    # ── Campaigns ──────────────────────────────────────────────────────

    async def create_campaign(
        self,
        name: str,
        objective: str = "OUTCOME_AWARENESS",
        status: str = "PAUSED",
        special_ad_categories: Optional[list[str]] = None,
        daily_budget: Optional[int] = None,
        lifetime_budget: Optional[int] = None,
    ) -> dict:
        """Create a new ad campaign.

        Args:
            name: Campaign name.
            objective: OUTCOME_AWARENESS, OUTCOME_TRAFFIC, OUTCOME_ENGAGEMENT,
                       OUTCOME_LEADS, OUTCOME_APP_PROMOTION, OUTCOME_SALES.
            status: ACTIVE or PAUSED.
            special_ad_categories: e.g. ["HOUSING", "EMPLOYMENT", "CREDIT"].
            daily_budget: Daily budget in cents (e.g. 5000 = $50.00).
            lifetime_budget: Lifetime budget in cents.
        """
        payload = {
            "name": name,
            "objective": objective,
            "status": status,
            "special_ad_categories": json.dumps(special_ad_categories or []),
        }
        if daily_budget is not None:
            payload["daily_budget"] = str(daily_budget)
        if lifetime_budget is not None:
            payload["lifetime_budget"] = str(lifetime_budget)

        return await self._request(
            "POST",
            f"{self.config.ad_account_id}/campaigns",
            data=payload,
        )

    async def get_campaigns(self, limit: int = 25) -> dict:
        """List campaigns for the ad account."""
        return await self._request(
            "GET",
            f"{self.config.ad_account_id}/campaigns",
            params={
                "fields": "id,name,objective,status,daily_budget,lifetime_budget,"
                          "created_time,updated_time,start_time,stop_time",
                "limit": str(limit),
            },
        )

    async def get_campaign(self, campaign_id: str) -> dict:
        """Get a single campaign by ID."""
        return await self._request(
            "GET",
            campaign_id,
            params={
                "fields": "id,name,objective,status,daily_budget,lifetime_budget,"
                          "created_time,updated_time",
            },
        )

    async def update_campaign(self, campaign_id: str, **fields) -> dict:
        """Update campaign fields (name, status, budget, etc.)."""
        return await self._request("POST", campaign_id, data=fields)

    async def delete_campaign(self, campaign_id: str) -> dict:
        """Delete (archive) a campaign."""
        return await self._request("DELETE", campaign_id)

    # ── Ad Sets ────────────────────────────────────────────────────────

    async def create_ad_set(
        self,
        name: str,
        campaign_id: str,
        daily_budget: int,
        optimization_goal: str = "REACH",
        billing_event: str = "IMPRESSIONS",
        bid_amount: Optional[int] = None,
        targeting: Optional[dict] = None,
        status: str = "PAUSED",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> dict:
        """Create a new ad set within a campaign.

        Args:
            name: Ad set name.
            campaign_id: Parent campaign ID.
            daily_budget: Daily budget in cents.
            optimization_goal: REACH, LINK_CLICKS, IMPRESSIONS, CONVERSIONS, etc.
            billing_event: IMPRESSIONS, LINK_CLICKS, etc.
            bid_amount: Bid amount in cents (optional).
            targeting: Targeting spec dict (geo, age, interests, etc.).
            status: ACTIVE or PAUSED.
            start_time: ISO 8601 start time.
            end_time: ISO 8601 end time.
        """
        payload = {
            "name": name,
            "campaign_id": campaign_id,
            "daily_budget": str(daily_budget),
            "optimization_goal": optimization_goal,
            "billing_event": billing_event,
            "status": status,
            "targeting": json.dumps(targeting or {"geo_locations": {"countries": ["US"]}}),
        }
        if bid_amount is not None:
            payload["bid_amount"] = str(bid_amount)
        if start_time:
            payload["start_time"] = start_time
        if end_time:
            payload["end_time"] = end_time

        return await self._request(
            "POST",
            f"{self.config.ad_account_id}/adsets",
            data=payload,
        )

    async def get_ad_sets(self, campaign_id: Optional[str] = None, limit: int = 25) -> dict:
        """List ad sets, optionally filtered by campaign."""
        endpoint = (
            f"{campaign_id}/adsets" if campaign_id
            else f"{self.config.ad_account_id}/adsets"
        )
        return await self._request(
            "GET",
            endpoint,
            params={
                "fields": "id,name,campaign_id,status,daily_budget,optimization_goal,"
                          "billing_event,targeting,created_time",
                "limit": str(limit),
            },
        )

    # ── Ad Creatives ───────────────────────────────────────────────────

    async def create_ad_creative(
        self,
        name: str,
        page_id: str,
        link: str,
        message: str,
        headline: str,
        description: str,
        image_hash: Optional[str] = None,
        image_url: Optional[str] = None,
        call_to_action_type: str = "LEARN_MORE",
    ) -> dict:
        """Create an ad creative with link ad format.

        Args:
            name: Creative name.
            page_id: Facebook Page ID to publish from.
            link: Destination URL.
            message: Primary text (body copy).
            headline: Headline text.
            description: Link description / newsfeed description.
            image_hash: Hash of an uploaded ad image.
            image_url: URL of the image (alternative to image_hash).
            call_to_action_type: LEARN_MORE, SHOP_NOW, SIGN_UP, etc.
        """
        link_data: dict = {
            "link": link,
            "message": message,
            "name": headline,
            "description": description,
            "call_to_action": {"type": call_to_action_type},
        }
        if image_hash:
            link_data["image_hash"] = image_hash
        elif image_url:
            link_data["picture"] = image_url

        object_story_spec = {
            "page_id": page_id,
            "link_data": link_data,
        }

        return await self._request(
            "POST",
            f"{self.config.ad_account_id}/adcreatives",
            data={
                "name": name,
                "object_story_spec": json.dumps(object_story_spec),
            },
        )

    # ── Ads ────────────────────────────────────────────────────────────

    async def create_ad(
        self,
        name: str,
        adset_id: str,
        creative_id: str,
        status: str = "PAUSED",
    ) -> dict:
        """Create an ad that links a creative to an ad set.

        Args:
            name: Ad name.
            adset_id: Parent ad set ID.
            creative_id: Creative ID to use.
            status: ACTIVE or PAUSED.
        """
        return await self._request(
            "POST",
            f"{self.config.ad_account_id}/ads",
            data={
                "name": name,
                "adset_id": adset_id,
                "creative": json.dumps({"creative_id": creative_id}),
                "status": status,
            },
        )

    async def get_ads(self, adset_id: Optional[str] = None, limit: int = 25) -> dict:
        """List ads, optionally filtered by ad set."""
        endpoint = (
            f"{adset_id}/ads" if adset_id
            else f"{self.config.ad_account_id}/ads"
        )
        return await self._request(
            "GET",
            endpoint,
            params={
                "fields": "id,name,adset_id,creative,status,created_time",
                "limit": str(limit),
            },
        )

    # ── Images ─────────────────────────────────────────────────────────

    async def upload_image(self, image_path: str) -> dict:
        """Upload an ad image and return its hash."""
        with open(image_path, "rb") as f:
            return await self._request(
                "POST",
                f"{self.config.ad_account_id}/adimages",
                files={"filename": f},
            )

    # ── Insights / Reporting ───────────────────────────────────────────

    async def get_campaign_insights(
        self,
        campaign_id: str,
        date_preset: str = "last_7d",
    ) -> dict:
        """Get performance insights for a campaign."""
        return await self._request(
            "GET",
            f"{campaign_id}/insights",
            params={
                "fields": "campaign_name,impressions,reach,clicks,cpc,cpm,ctr,"
                          "spend,actions,cost_per_action_type",
                "date_preset": date_preset,
            },
        )

    async def get_account_insights(self, date_preset: str = "last_7d") -> dict:
        """Get performance insights for the entire ad account."""
        return await self._request(
            "GET",
            f"{self.config.ad_account_id}/insights",
            params={
                "fields": "impressions,reach,clicks,cpc,cpm,ctr,spend,actions",
                "date_preset": date_preset,
            },
        )

    # ── Targeting Search ───────────────────────────────────────────────

    async def search_targeting(
        self, query: str, target_type: str = "adinterest"
    ) -> dict:
        """Search for targeting options (interests, behaviors, etc.)."""
        return await self._request(
            "GET",
            "search",
            params={
                "type": target_type,
                "q": query,
            },
        )

    async def close(self):
        await self._client.aclose()


class MetaAdsAPIError(Exception):
    """Error from the Meta Marketing API."""

    def __init__(self, message: str, error_type: str = "", code: int = 0, fbtrace_id: str = ""):
        self.message = message
        self.error_type = error_type
        self.code = code
        self.fbtrace_id = fbtrace_id
        super().__init__(self.message)
