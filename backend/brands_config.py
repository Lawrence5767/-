"""
Brand & Page Registry
All Facebook pages organized by brand for multi-brand Meta Ads management.

Each brand contains:
  - name: Display name
  - code: Short code prefix (e.g. NV, RZ, XH, MGH)
  - ad_account_id: Meta Ad Account ID (format: act_XXXXXXXXXX) - set per brand
  - pages: dict of page_code -> page info
    - name: Page display name
    - page_id: Facebook numeric Page ID
    - type: "brand" (main page) or "showroom"
    - location: Showroom location (if applicable)
    - url: Facebook page URL

Meta App ID: 910390974704285 (Claude Based app - Nova Furnishing)
"""

BRANDS = {
    "nova_furnishing": {
        "name": "Nova Furnishing",
        "code": "NV",
        "ad_account_id": "",
        "pages": {
            "NVMP": {
                "name": "Nova Furnishing Singapore",
                "page_id": "105932421718957",
                "type": "brand",
                "location": "Main Page",
                "url": "https://www.facebook.com/NovaFurnishingsSingapore/",
            },
            "NVTH": {
                "name": "Nova Furnishing Trade Hub",
                "page_id": "669250529935380",
                "type": "showroom",
                "location": "Trade Hub",
                "url": "https://www.facebook.com/NovaFurnishingTradeHub",
            },
            "NVCH": {
                "name": "Nova Furnishing CH",
                "page_id": "185922114614106",
                "type": "showroom",
                "location": "CH",
                "url": "https://www.facebook.com/profile.php?id=61556703561541",
            },
            "NVSK": {
                "name": "Nova Furnishing Sungei Kadut",
                "page_id": "101960971456344",
                "type": "showroom",
                "location": "Sungei Kadut",
                "url": "https://www.facebook.com/novafurnishingwarehouseatsungeikadut/",
            },
            "NVSD": {
                "name": "Nova Furnishing Sims Drive",
                "page_id": "102165434695810",
                "type": "showroom",
                "location": "Sims Drive",
                "url": "https://www.facebook.com/novafurnishingfactoryoutletatsimsdrive/",
            },
            "NVAMK": {
                "name": "Nova Furnishing AMK Ave 10",
                "page_id": "110062733892139",
                "type": "showroom",
                "location": "AMK Ave 10",
                "url": "https://www.facebook.com/novafurnishingamkave10/",
            },
        },
    },
    "rozel_furnishing": {
        "name": "Rozel Furnishing",
        "code": "RZ",
        "ad_account_id": "",
        "pages": {
            "RZMP": {
                "name": "Rozel Furnishing SG",
                "page_id": "122100820076000791",
                "type": "brand",
                "location": "Main Page",
                "url": "https://www.facebook.com/rozelfurnishingsg/",
            },
            "RZSK": {
                "name": "Rozel Furniture Sungei Kadut",
                "page_id": "113536130281839",
                "type": "showroom",
                "location": "Sungei Kadut",
                "url": "https://www.facebook.com/rozelfurniturefactoryoutletsungeikadut/",
            },
            "RZSA": {
                "name": "Rozel Furnishing Sims Avenue",
                "page_id": "104860588807604",
                "type": "showroom",
                "location": "Sims Avenue",
                "url": "https://www.facebook.com/rozelfurnishingsimsavenue/",
            },
            "RZLAB": {
                "name": "Rozel South",
                "page_id": "112692995147685",
                "type": "showroom",
                "location": "South",
                "url": "https://www.facebook.com/rozelsouth/",
            },
        },
    },
    "xclusive_home": {
        "name": "X'clusive Home",
        "code": "XH",
        "ad_account_id": "",
        "pages": {
            "XHMP": {
                "name": "X'clusive Home Singapore",
                "page_id": "110723125348805",
                "type": "brand",
                "location": "Main Page",
                "url": "https://www.facebook.com/XclusiveHomeSingapore/",
            },
            "XHLAB": {
                "name": "X'clusive Home Lab",
                "page_id": "175722218962104",
                "type": "showroom",
                "location": "Lab",
                "url": "https://www.facebook.com/profile.php?id=61554115932954",
            },
            "XHSD": {
                "name": "X'clusive Home Sims Drive",
                "page_id": "106822260918043",
                "type": "showroom",
                "location": "Sims Drive",
                "url": "https://www.facebook.com/xclusivehomewarehouseatsimsdrive/",
            },
            "XHSK": {
                "name": "X'clusive Home Sungei Kadut",
                "page_id": "2227175443991857",
                "type": "showroom",
                "location": "Sungei Kadut",
                "url": "https://www.facebook.com/xclusivehomesungeikadut/",
            },
            "XHTM": {
                "name": "X'clusive Home TM",
                "page_id": "61586864776960",
                "type": "showroom",
                "location": "TM (Coming Soon)",
                "url": "https://www.facebook.com/profile.php?id=61586864776960",
            },
        },
    },
    "megahome_furnishing": {
        "name": "Megahome Furnishing",
        "code": "MGH",
        "ad_account_id": "",
        "pages": {
            "MGH": {
                "name": "Megahome Furnishing",
                "page_id": "545566435804987",
                "type": "brand",
                "location": "Main Page",
                "url": "https://www.facebook.com/megahomefurnishing/",
            },
        },
    },
}

META_APP_ID = "910390974704285"


def get_all_brands() -> list[dict]:
    """Return a summary list of all brands with their pages."""
    result = []
    for brand_key, brand in BRANDS.items():
        pages = []
        for page_code, page in brand["pages"].items():
            pages.append({
                "code": page_code,
                "name": page["name"],
                "page_id": page["page_id"],
                "type": page["type"],
                "location": page["location"],
            })
        result.append({
            "key": brand_key,
            "name": brand["name"],
            "code": brand["code"],
            "ad_account_id": brand["ad_account_id"],
            "pages": pages,
        })
    return result


def get_brand(brand_key: str) -> dict | None:
    """Get a single brand by key."""
    return BRANDS.get(brand_key)


def get_page_id(brand_key: str, page_code: str) -> str | None:
    """Look up a page ID by brand key and page code."""
    brand = BRANDS.get(brand_key)
    if not brand:
        return None
    page = brand["pages"].get(page_code)
    return page["page_id"] if page else None


def find_page_by_id(page_id: str) -> dict | None:
    """Find brand and page info by page ID."""
    for brand_key, brand in BRANDS.items():
        for page_code, page in brand["pages"].items():
            if page["page_id"] == page_id:
                return {
                    "brand_key": brand_key,
                    "brand_name": brand["name"],
                    "page_code": page_code,
                    **page,
                }
    return None


def set_brand_ad_account(brand_key: str, ad_account_id: str) -> bool:
    """Set the ad account ID for a brand (runtime only)."""
    brand = BRANDS.get(brand_key)
    if not brand:
        return False
    brand["ad_account_id"] = ad_account_id
    return True
