"""
Claude tool definitions for TikTok Ads campaign creation.
These are passed to the Claude API as the `tools` parameter.
"""

TOOLS = [
    {
        "name": "create_campaign",
        "description": (
            "Create a new TikTok Ads campaign. A campaign is the top-level container "
            "that defines the advertising objective and optional budget. "
            "You must create a campaign before creating ad groups or ads."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_name": {
                    "type": "string",
                    "description": "A descriptive name for the campaign.",
                },
                "objective_type": {
                    "type": "string",
                    "enum": [
                        "REACH",
                        "TRAFFIC",
                        "VIDEO_VIEWS",
                        "LEAD_GENERATION",
                        "COMMUNITY_INTERACTION",
                        "APP_PROMOTION",
                        "WEB_CONVERSIONS",
                        "PRODUCT_SALES",
                        "ENGAGEMENT",
                    ],
                    "description": (
                        "The advertising objective. "
                        "REACH: maximize impressions. "
                        "TRAFFIC: drive visits to a URL. "
                        "VIDEO_VIEWS: get more video views. "
                        "LEAD_GENERATION: collect leads. "
                        "APP_PROMOTION: drive app installs. "
                        "WEB_CONVERSIONS: drive website conversions. "
                        "PRODUCT_SALES: drive product purchases. "
                        "ENGAGEMENT: drive community engagement."
                    ),
                },
                "budget": {
                    "type": "number",
                    "description": (
                        "Budget amount in the advertiser's currency. "
                        "Required if budget_mode is not BUDGET_MODE_INFINITE."
                    ),
                },
                "budget_mode": {
                    "type": "string",
                    "enum": [
                        "BUDGET_MODE_DAY",
                        "BUDGET_MODE_TOTAL",
                        "BUDGET_MODE_INFINITE",
                    ],
                    "description": (
                        "BUDGET_MODE_DAY: daily budget. "
                        "BUDGET_MODE_TOTAL: lifetime budget. "
                        "BUDGET_MODE_INFINITE: no campaign-level budget (set at ad group level)."
                    ),
                },
            },
            "required": ["campaign_name", "objective_type"],
        },
    },
    {
        "name": "create_adgroup",
        "description": (
            "Create an ad group within an existing campaign. "
            "The ad group defines targeting (location, age, gender), placement, "
            "schedule, budget, and bidding strategy. "
            "You need a campaign_id from a previously created campaign."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "The ID of the parent campaign.",
                },
                "adgroup_name": {
                    "type": "string",
                    "description": "A descriptive name for the ad group.",
                },
                "placement_type": {
                    "type": "string",
                    "enum": ["PLACEMENT_TYPE_AUTOMATIC", "PLACEMENT_TYPE_NORMAL"],
                    "description": (
                        "PLACEMENT_TYPE_AUTOMATIC: TikTok decides where to show ads. "
                        "PLACEMENT_TYPE_NORMAL: you choose specific placements."
                    ),
                },
                "placements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific placements when using PLACEMENT_TYPE_NORMAL. "
                        "Options: PLACEMENT_TIKTOK, PLACEMENT_PANGLE, PLACEMENT_GLOBAL_APP_BUNDLE."
                    ),
                },
                "location_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "Location IDs for geo-targeting. "
                        "Examples: 6252001 (US), 2635167 (UK), 2921044 (Germany), "
                        "1269750 (India), 1861060 (Japan), 2077456 (Australia)."
                    ),
                },
                "age_groups": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "AGE_13_17",
                            "AGE_18_24",
                            "AGE_25_34",
                            "AGE_35_44",
                            "AGE_45_54",
                            "AGE_55_100",
                        ],
                    },
                    "description": "Target age groups.",
                },
                "gender": {
                    "type": "string",
                    "enum": ["GENDER_UNLIMITED", "GENDER_MALE", "GENDER_FEMALE"],
                    "description": "Target gender. GENDER_UNLIMITED for all.",
                },
                "budget": {
                    "type": "number",
                    "description": "Ad group budget amount.",
                },
                "budget_mode": {
                    "type": "string",
                    "enum": ["BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"],
                    "description": "BUDGET_MODE_DAY: daily budget. BUDGET_MODE_TOTAL: lifetime budget.",
                },
                "schedule_type": {
                    "type": "string",
                    "enum": ["SCHEDULE_FROM_NOW", "SCHEDULE_START_END"],
                    "description": (
                        "SCHEDULE_FROM_NOW: start immediately and run continuously. "
                        "SCHEDULE_START_END: run between specific dates."
                    ),
                },
                "schedule_start_time": {
                    "type": "string",
                    "description": "Start time in 'YYYY-MM-DD HH:MM:SS' format. Required if SCHEDULE_START_END.",
                },
                "schedule_end_time": {
                    "type": "string",
                    "description": "End time in 'YYYY-MM-DD HH:MM:SS' format. Required if SCHEDULE_START_END.",
                },
                "optimize_goal": {
                    "type": "string",
                    "enum": ["CLICK", "REACH", "SHOW", "CONVERT", "INSTALL"],
                    "description": "What to optimize for.",
                },
                "billing_event": {
                    "type": "string",
                    "enum": ["CPC", "CPM", "CPV", "OCPM"],
                    "description": "How you're billed. CPC=per click, CPM=per 1000 impressions, OCPM=optimized CPM.",
                },
                "bid_type": {
                    "type": "string",
                    "enum": ["BID_TYPE_NO_BID", "BID_TYPE_CUSTOM", "BID_TYPE_MAX"],
                    "description": "Bidding strategy. NO_BID for lowest cost automatic bidding.",
                },
                "bid": {
                    "type": "number",
                    "description": "Bid amount if using BID_TYPE_CUSTOM.",
                },
                "pacing": {
                    "type": "string",
                    "enum": ["PACING_MODE_SMOOTH", "PACING_MODE_FAST"],
                    "description": "SMOOTH: spread budget evenly. FAST: spend budget quickly.",
                },
            },
            "required": ["campaign_id", "adgroup_name"],
        },
    },
    {
        "name": "create_ad",
        "description": (
            "Create an ad within an existing ad group. "
            "The ad contains the creative elements users see: text, video/image, "
            "call-to-action, and landing page URL. "
            "You need an adgroup_id from a previously created ad group."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "adgroup_id": {
                    "type": "string",
                    "description": "The ID of the parent ad group.",
                },
                "ad_name": {
                    "type": "string",
                    "description": "A descriptive name for the ad.",
                },
                "ad_text": {
                    "type": "string",
                    "description": "The ad copy / caption text that users will see.",
                },
                "video_id": {
                    "type": "string",
                    "description": "TikTok video ID for video ads (from a previous upload).",
                },
                "image_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of image IDs for image/carousel ads.",
                },
                "call_to_action": {
                    "type": "string",
                    "enum": [
                        "LEARN_MORE",
                        "SHOP_NOW",
                        "SIGN_UP",
                        "DOWNLOAD",
                        "CONTACT_US",
                        "SUBSCRIBE",
                        "GET_QUOTE",
                        "APPLY_NOW",
                        "BOOK_NOW",
                        "ORDER_NOW",
                        "GET_SHOWTIMES",
                        "LISTEN_NOW",
                        "INSTALL_NOW",
                        "PLAY_GAME",
                    ],
                    "description": "The call-to-action button text.",
                },
                "landing_page_url": {
                    "type": "string",
                    "description": "The URL users are taken to when they click the ad.",
                },
                "display_name": {
                    "type": "string",
                    "description": "The display name shown on the ad (brand name).",
                },
                "identity_id": {
                    "type": "string",
                    "description": "TikTok identity ID for the ad (your TikTok account or custom identity).",
                },
                "identity_type": {
                    "type": "string",
                    "enum": ["CUSTOMIZED_USER", "AUTH_CODE"],
                    "description": "Type of identity used for the ad.",
                },
            },
            "required": ["adgroup_id", "ad_name", "ad_text"],
        },
    },
    {
        "name": "list_campaigns",
        "description": "List all existing campaigns for the advertiser account.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_adgroups",
        "description": "List ad groups, optionally filtered by campaign ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {
                    "type": "string",
                    "description": "Optional campaign ID to filter ad groups.",
                },
            },
        },
    },
    {
        "name": "list_ads",
        "description": "List ads, optionally filtered by ad group ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "adgroup_id": {
                    "type": "string",
                    "description": "Optional ad group ID to filter ads.",
                },
            },
        },
    },
]
