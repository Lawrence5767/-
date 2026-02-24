"""TikTok Ads API client.

Handles all direct communication with TikTok's Marketing API v1.3,
including authentication, campaign/ad-group/ad CRUD, and creative uploads.
"""

import json
import time
import requests
from tiktok_ads.config import get_config, validate_config

API_VERSION = "v1.3"


class TikTokAdsError(Exception):
    """Raised when the TikTok API returns a non-zero error code."""

    def __init__(self, code, message, request_id=None):
        self.code = code
        self.request_id = request_id
        super().__init__(f"TikTok API error {code}: {message} (request_id={request_id})")


class TikTokAdsClient:
    """Low-level client for the TikTok Marketing API."""

    def __init__(self, access_token=None, advertiser_id=None, env=None):
        cfg = get_config()
        self.access_token = access_token or cfg["access_token"]
        self.advertiser_id = advertiser_id or cfg["advertiser_id"]

        env = env or cfg["env"]
        if env == "production":
            self.base_url = "https://business-api.tiktok.com/open_api"
        else:
            self.base_url = "https://sandbox-ads.tiktok.com/open_api"

        missing = []
        if not self.access_token:
            missing.append("access_token")
        if not self.advertiser_id:
            missing.append("advertiser_id")
        if missing:
            raise ValueError(
                f"Missing required credentials: {', '.join(missing)}. "
                "Set them in .env or pass them directly."
            )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self):
        return {
            "Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    def _url(self, path):
        return f"{self.base_url}/{API_VERSION}/{path}"

    def _post(self, path, payload):
        """POST JSON to the API endpoint and return the parsed response data."""
        resp = requests.post(self._url(path), headers=self._headers(), json=payload)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise TikTokAdsError(
                body.get("code"), body.get("message", "Unknown error"),
                body.get("request_id"),
            )
        return body.get("data", {})

    def _get(self, path, params):
        """GET from the API endpoint and return the parsed response data."""
        resp = requests.get(self._url(path), headers=self._headers(), params=params)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise TikTokAdsError(
                body.get("code"), body.get("message", "Unknown error"),
                body.get("request_id"),
            )
        return body.get("data", {})

    # ------------------------------------------------------------------
    # Authentication helpers (class methods — no instance needed)
    # ------------------------------------------------------------------

    @staticmethod
    def get_access_token(app_id, app_secret, auth_code):
        """Exchange an auth_code for an access_token.

        Returns the full data dict including access_token, advertiser_ids, etc.
        """
        url = f"https://business-api.tiktok.com/open_api/{API_VERSION}/oauth2/access_token/"
        payload = {
            "app_id": app_id,
            "secret": app_secret,
            "auth_code": auth_code,
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise TikTokAdsError(
                body.get("code"), body.get("message"),
                body.get("request_id"),
            )
        return body["data"]

    # ------------------------------------------------------------------
    # Account info
    # ------------------------------------------------------------------

    def get_advertiser_info(self):
        """Retrieve info about the current advertiser account."""
        return self._get("advertiser/info/", {
            "advertiser_ids": json.dumps([self.advertiser_id]),
        })

    # ------------------------------------------------------------------
    # Campaign operations
    # ------------------------------------------------------------------

    def create_campaign(self, campaign_name, objective_type,
                        budget=None, budget_mode="BUDGET_MODE_DAY"):
        """Create a new campaign.

        Args:
            campaign_name: Unique campaign name.
            objective_type: One of REACH, TRAFFIC, VIDEO_VIEWS, LEAD_GENERATION,
                            WEBSITE_CONVERSIONS, APP_INSTALLS, PRODUCT_SALES, etc.
            budget: Daily or total budget amount (float). Required when budget_mode
                    is not BUDGET_MODE_INFINITE.
            budget_mode: BUDGET_MODE_DAY | BUDGET_MODE_TOTAL | BUDGET_MODE_INFINITE.

        Returns:
            dict with campaign_id.
        """
        payload = {
            "advertiser_id": self.advertiser_id,
            "campaign_name": campaign_name,
            "objective_type": objective_type,
            "budget_mode": budget_mode,
        }
        if budget is not None:
            payload["budget"] = budget
        return self._post("campaign/create/", payload)

    def list_campaigns(self, page=1, page_size=20):
        """List existing campaigns."""
        return self._get("campaign/get/", {
            "advertiser_id": self.advertiser_id,
            "page": page,
            "page_size": page_size,
        })

    def update_campaign(self, campaign_id, **kwargs):
        """Update a campaign. Pass any updatable fields as kwargs."""
        payload = {
            "advertiser_id": self.advertiser_id,
            "campaign_id": campaign_id,
            **kwargs,
        }
        return self._post("campaign/update/", payload)

    # ------------------------------------------------------------------
    # Ad Group operations
    # ------------------------------------------------------------------

    def create_ad_group(self, campaign_id, adgroup_name, placements,
                        location_ids, budget, schedule_start_time,
                        schedule_end_time=None, optimize_goal="REACH",
                        billing_event="CPM", bid_type="BID_TYPE_NO_BID",
                        budget_mode="BUDGET_MODE_DAY",
                        schedule_type="SCHEDULE_FROM_NOW",
                        pacing="PACING_MODE_SMOOTH",
                        age_groups=None, gender=None, **kwargs):
        """Create an ad group within a campaign.

        Args:
            campaign_id: Parent campaign ID.
            adgroup_name: Unique name.
            placements: List like ["PLACEMENT_TIKTOK"].
            location_ids: List of location codes (e.g. ["6252001"] for US).
            budget: Daily budget amount.
            schedule_start_time: Start time "YYYY-MM-DD HH:MM:SS".
            schedule_end_time: Optional end time.
            optimize_goal: REACH, CLICK, CONVERT, etc.
            billing_event: CPM, CPC, OCPM, etc.
            bid_type: BID_TYPE_NO_BID, BID_TYPE_CUSTOM, etc.
            budget_mode: BUDGET_MODE_DAY | BUDGET_MODE_TOTAL.
            schedule_type: SCHEDULE_FROM_NOW | SCHEDULE_START_END.
            pacing: PACING_MODE_SMOOTH | PACING_MODE_FAST.
            age_groups: Optional list like ["AGE_25_34", "AGE_35_44"].
            gender: Optional "GENDER_MALE" | "GENDER_FEMALE" | "GENDER_UNLIMITED".
            **kwargs: Additional fields.

        Returns:
            dict with adgroup_id.
        """
        payload = {
            "advertiser_id": self.advertiser_id,
            "campaign_id": campaign_id,
            "adgroup_name": adgroup_name,
            "placement_type": "PLACEMENT_TYPE_NORMAL",
            "placements": placements,
            "location_ids": location_ids,
            "budget_mode": budget_mode,
            "budget": budget,
            "schedule_type": schedule_type,
            "schedule_start_time": schedule_start_time,
            "optimize_goal": optimize_goal,
            "pacing": pacing,
            "billing_event": billing_event,
            "bid_type": bid_type,
        }
        if schedule_end_time:
            payload["schedule_end_time"] = schedule_end_time
            payload["schedule_type"] = "SCHEDULE_START_END"
        if age_groups:
            payload["age_groups"] = age_groups
        if gender:
            payload["gender"] = gender
        payload.update(kwargs)
        return self._post("adgroup/create/", payload)

    def list_ad_groups(self, campaign_ids=None, page=1, page_size=20):
        """List ad groups, optionally filtered by campaign."""
        params = {
            "advertiser_id": self.advertiser_id,
            "page": page,
            "page_size": page_size,
        }
        if campaign_ids:
            params["filtering"] = json.dumps({"campaign_ids": campaign_ids})
        return self._get("adgroup/get/", params)

    # ------------------------------------------------------------------
    # Creative / file upload operations
    # ------------------------------------------------------------------

    def upload_video_by_url(self, video_url, file_name=None):
        """Upload a video from a URL.

        Returns dict with video_id.
        """
        if not file_name:
            file_name = f"video_{int(time.time())}"
        payload = {
            "advertiser_id": self.advertiser_id,
            "upload_type": "UPLOAD_BY_URL",
            "video_url": video_url,
            "file_name": file_name,
        }
        return self._post("file/video/ad/upload/", payload)

    def upload_video_file(self, file_path):
        """Upload a video from a local file.

        Returns dict with video_id.
        """
        url = self._url("file/video/ad/upload/")
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                headers={"Access-Token": self.access_token},
                data={"advertiser_id": self.advertiser_id, "upload_type": "UPLOAD_BY_FILE"},
                files={"video_file": f},
            )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise TikTokAdsError(body.get("code"), body.get("message"), body.get("request_id"))
        return body["data"]

    def upload_image_by_url(self, image_url, file_name=None):
        """Upload an image (thumbnail) from a URL.

        Returns dict with image_id.
        """
        if not file_name:
            file_name = f"img_{int(time.time())}"
        payload = {
            "advertiser_id": self.advertiser_id,
            "upload_type": "UPLOAD_BY_URL",
            "image_url": image_url,
            "file_name": file_name,
        }
        return self._post("file/image/ad/upload/", payload)

    def upload_image_file(self, file_path):
        """Upload an image from a local file.

        Returns dict with image_id.
        """
        url = self._url("file/image/ad/upload/")
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                headers={"Access-Token": self.access_token},
                data={"advertiser_id": self.advertiser_id, "upload_type": "UPLOAD_BY_FILE"},
                files={"image_file": f},
            )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise TikTokAdsError(body.get("code"), body.get("message"), body.get("request_id"))
        return body["data"]

    def get_video_info(self, video_ids):
        """Get metadata for uploaded videos (dimensions, poster_url, etc.)."""
        return self._get("file/video/ad/info/", {
            "advertiser_id": self.advertiser_id,
            "video_ids": json.dumps(video_ids),
        })

    # ------------------------------------------------------------------
    # Ad operations
    # ------------------------------------------------------------------

    def create_ad(self, adgroup_id, ad_name, ad_text,
                  video_id=None, image_ids=None,
                  ad_format="SINGLE_VIDEO",
                  display_name=None, call_to_action=None,
                  landing_page_url=None, **kwargs):
        """Create an ad within an ad group.

        Args:
            adgroup_id: Parent ad group ID.
            ad_name: Unique ad name.
            ad_text: The promotional copy shown to users.
            video_id: ID of uploaded video creative.
            image_ids: List of image IDs (thumbnail).
            ad_format: SINGLE_VIDEO | SINGLE_IMAGE | CAROUSEL.
            display_name: Brand name shown instead of TikTok handle.
            call_to_action: CTA button text like "LEARN_MORE", "SHOP_NOW", etc.
            landing_page_url: Destination URL when user clicks.
            **kwargs: Additional fields.

        Returns:
            dict with ad_id(s).
        """
        creative = {
            "ad_name": ad_name,
            "ad_text": ad_text,
            "ad_format": ad_format,
        }
        if video_id:
            creative["video_id"] = video_id
        if image_ids:
            creative["image_ids"] = image_ids
        if display_name:
            creative["display_name"] = display_name
        if call_to_action:
            creative["call_to_action"] = call_to_action
        if landing_page_url:
            creative["landing_page_url"] = landing_page_url
        creative.update(kwargs)

        payload = {
            "advertiser_id": self.advertiser_id,
            "adgroup_id": adgroup_id,
            "creatives": [creative],
        }
        return self._post("ad/create/", payload)

    def list_ads(self, adgroup_ids=None, page=1, page_size=20):
        """List ads, optionally filtered by ad group."""
        params = {
            "advertiser_id": self.advertiser_id,
            "page": page,
            "page_size": page_size,
        }
        if adgroup_ids:
            params["filtering"] = json.dumps({"adgroup_ids": adgroup_ids})
        return self._get("ad/get/", params)

    def update_ad_status(self, ad_ids, status):
        """Enable or disable ads.

        Args:
            ad_ids: List of ad IDs.
            status: "ENABLE" | "DISABLE" | "DELETE".
        """
        return self._post("ad/status/update/", {
            "advertiser_id": self.advertiser_id,
            "ad_ids": ad_ids,
            "opt_status": status,
        })

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_campaign_report(self, campaign_ids, start_date, end_date,
                            metrics=None):
        """Get performance report for campaigns.

        Args:
            campaign_ids: List of campaign IDs.
            start_date: "YYYY-MM-DD".
            end_date: "YYYY-MM-DD".
            metrics: List of metric names. Defaults to common set.
        """
        if not metrics:
            metrics = [
                "spend", "impressions", "clicks", "ctr",
                "cpc", "cpm", "reach", "frequency",
            ]
        payload = {
            "advertiser_id": self.advertiser_id,
            "report_type": "BASIC",
            "dimensions": ["campaign_id"],
            "data_level": "AUCTION_CAMPAIGN",
            "start_date": start_date,
            "end_date": end_date,
            "metrics": metrics,
            "filtering": {"campaign_ids": campaign_ids},
        }
        return self._post("report/integrated/get/", payload)
