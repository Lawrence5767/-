"""
Claude Ad Service - AI-powered ad content generation.
Uses the Anthropic Claude API to generate ad copy, headlines,
targeting suggestions, and full campaign structures for Meta Ads.

Required environment variable:
  ANTHROPIC_API_KEY - Your Anthropic API key
"""

import json
import os
from typing import Optional

import anthropic


def _get_client() -> anthropic.Anthropic:
    """Return an Anthropic client (reads ANTHROPIC_API_KEY from env)."""
    return anthropic.Anthropic()


SYSTEM_PROMPT = """\
You are an expert Meta (Facebook/Instagram) advertising strategist and copywriter.
You create high-converting ad campaigns.  When generating ad content you must:

1. Follow Meta Ads policies (no misleading claims, prohibited content, etc.).
2. Write concise, compelling copy within Meta's character limits:
   - Primary text: ≤125 characters recommended (up to 2200 max).
   - Headline: ≤40 characters recommended.
   - Description: ≤30 characters recommended.
3. Always return valid JSON matching the requested schema.
4. Be creative but professional, adapting tone to the brand/product.
"""


async def generate_ad_copy(
    product_name: str,
    product_description: str,
    target_audience: str = "",
    tone: str = "professional",
    landing_page_url: str = "",
    num_variations: int = 3,
) -> dict:
    """Generate multiple ad copy variations using Claude.

    Returns a dict with "variations" containing a list of ad copy options,
    each having: headline, primary_text, description, call_to_action.
    """
    client = _get_client()

    user_prompt = f"""\
Generate {num_variations} Meta ad copy variations for the following:

Product/Service: {product_name}
Description: {product_description}
Target Audience: {target_audience or 'General audience'}
Tone: {tone}
Landing Page: {landing_page_url or 'N/A'}

Return a JSON object with this exact schema:
{{
  "variations": [
    {{
      "headline": "short punchy headline (≤40 chars)",
      "primary_text": "main ad body copy (≤125 chars recommended)",
      "description": "link description (≤30 chars)",
      "call_to_action": "one of: LEARN_MORE, SHOP_NOW, SIGN_UP, BOOK_TRAVEL, CONTACT_US, DOWNLOAD, GET_OFFER, GET_QUOTE, SUBSCRIBE, WATCH_MORE"
    }}
  ]
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "variations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "headline": {"type": "string"},
                                    "primary_text": {"type": "string"},
                                    "description": {"type": "string"},
                                    "call_to_action": {"type": "string"},
                                },
                                "required": ["headline", "primary_text", "description", "call_to_action"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["variations"],
                    "additionalProperties": False,
                },
            }
        },
    )

    return json.loads(response.content[0].text)


async def generate_targeting_suggestions(
    product_name: str,
    product_description: str,
    current_audience: str = "",
) -> dict:
    """Use Claude to suggest targeting parameters for Meta Ads.

    Returns a dict with suggested demographics, interests, behaviors,
    and lookalike audience recommendations.
    """
    client = _get_client()

    user_prompt = f"""\
Suggest Meta Ads targeting for:

Product/Service: {product_name}
Description: {product_description}
Current Audience Info: {current_audience or 'None provided'}

Return a JSON object with this exact schema:
{{
  "demographics": {{
    "age_min": 18,
    "age_max": 65,
    "genders": [1, 2],
    "geo_locations": {{
      "countries": ["US"],
      "cities": []
    }}
  }},
  "interests": [
    {{"name": "interest name", "rationale": "why this interest"}}
  ],
  "behaviors": [
    {{"name": "behavior name", "rationale": "why this behavior"}}
  ],
  "custom_audiences": [
    {{"type": "audience type", "description": "what to include"}}
  ],
  "strategy_notes": "brief targeting strategy explanation"
}}

For genders: 1 = male, 2 = female. Include both unless the product is gender-specific.
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "demographics": {
                            "type": "object",
                            "properties": {
                                "age_min": {"type": "integer"},
                                "age_max": {"type": "integer"},
                                "genders": {"type": "array", "items": {"type": "integer"}},
                                "geo_locations": {
                                    "type": "object",
                                    "properties": {
                                        "countries": {"type": "array", "items": {"type": "string"}},
                                        "cities": {"type": "array", "items": {"type": "string"}},
                                    },
                                    "required": ["countries", "cities"],
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["age_min", "age_max", "genders", "geo_locations"],
                            "additionalProperties": False,
                        },
                        "interests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "rationale": {"type": "string"},
                                },
                                "required": ["name", "rationale"],
                                "additionalProperties": False,
                            },
                        },
                        "behaviors": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "rationale": {"type": "string"},
                                },
                                "required": ["name", "rationale"],
                                "additionalProperties": False,
                            },
                        },
                        "custom_audiences": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                                "required": ["type", "description"],
                                "additionalProperties": False,
                            },
                        },
                        "strategy_notes": {"type": "string"},
                    },
                    "required": ["demographics", "interests", "behaviors", "custom_audiences", "strategy_notes"],
                    "additionalProperties": False,
                },
            }
        },
    )

    return json.loads(response.content[0].text)


async def generate_full_campaign(
    product_name: str,
    product_description: str,
    goal: str = "awareness",
    budget_dollars: float = 50.0,
    duration_days: int = 7,
    target_audience: str = "",
    landing_page_url: str = "",
    tone: str = "professional",
) -> dict:
    """Generate a complete campaign plan: campaign settings, ad set config,
    and multiple ad creatives — all in one call.

    Returns a structured campaign plan ready to be executed via the Meta API.
    """
    client = _get_client()

    objective_map = {
        "awareness": "OUTCOME_AWARENESS",
        "traffic": "OUTCOME_TRAFFIC",
        "engagement": "OUTCOME_ENGAGEMENT",
        "leads": "OUTCOME_LEADS",
        "sales": "OUTCOME_SALES",
        "app_promotion": "OUTCOME_APP_PROMOTION",
    }
    objective = objective_map.get(goal.lower(), "OUTCOME_AWARENESS")

    user_prompt = f"""\
Create a complete Meta Ads campaign plan:

Product/Service: {product_name}
Description: {product_description}
Goal: {goal} (API objective: {objective})
Daily Budget: ${budget_dollars:.2f}
Duration: {duration_days} days
Target Audience: {target_audience or 'Suggest the best audience'}
Landing Page: {landing_page_url or 'N/A'}
Tone: {tone}

Return a JSON object with this exact schema:
{{
  "campaign": {{
    "name": "campaign name",
    "objective": "{objective}",
    "daily_budget_cents": {int(budget_dollars * 100)},
    "special_ad_categories": []
  }},
  "ad_set": {{
    "name": "ad set name",
    "optimization_goal": "REACH or LINK_CLICKS or CONVERSIONS etc.",
    "billing_event": "IMPRESSIONS",
    "targeting": {{
      "age_min": 18,
      "age_max": 65,
      "genders": [1, 2],
      "geo_locations": {{"countries": ["US"]}},
      "interests": [{{"id": "6003139266461", "name": "example interest"}}]
    }}
  }},
  "ad_creatives": [
    {{
      "name": "creative name",
      "headline": "≤40 char headline",
      "primary_text": "main ad text",
      "description": "≤30 char description",
      "call_to_action": "LEARN_MORE"
    }}
  ],
  "strategy_summary": "brief explanation of the campaign strategy"
}}

Generate 3 ad creative variations. Use realistic Meta interest IDs if possible.
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "campaign": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "objective": {"type": "string"},
                                "daily_budget_cents": {"type": "integer"},
                                "special_ad_categories": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["name", "objective", "daily_budget_cents", "special_ad_categories"],
                            "additionalProperties": False,
                        },
                        "ad_set": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "optimization_goal": {"type": "string"},
                                "billing_event": {"type": "string"},
                                "targeting": {
                                    "type": "object",
                                    "properties": {
                                        "age_min": {"type": "integer"},
                                        "age_max": {"type": "integer"},
                                        "genders": {"type": "array", "items": {"type": "integer"}},
                                        "geo_locations": {
                                            "type": "object",
                                            "properties": {
                                                "countries": {"type": "array", "items": {"type": "string"}},
                                            },
                                            "required": ["countries"],
                                            "additionalProperties": False,
                                        },
                                        "interests": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string"},
                                                    "name": {"type": "string"},
                                                },
                                                "required": ["id", "name"],
                                                "additionalProperties": False,
                                            },
                                        },
                                    },
                                    "required": ["age_min", "age_max", "genders", "geo_locations", "interests"],
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["name", "optimization_goal", "billing_event", "targeting"],
                            "additionalProperties": False,
                        },
                        "ad_creatives": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "headline": {"type": "string"},
                                    "primary_text": {"type": "string"},
                                    "description": {"type": "string"},
                                    "call_to_action": {"type": "string"},
                                },
                                "required": ["name", "headline", "primary_text", "description", "call_to_action"],
                                "additionalProperties": False,
                            },
                        },
                        "strategy_summary": {"type": "string"},
                    },
                    "required": ["campaign", "ad_set", "ad_creatives", "strategy_summary"],
                    "additionalProperties": False,
                },
            }
        },
    )

    text_block = next(b for b in response.content if b.type == "text")
    return json.loads(text_block.text)


async def analyze_ad_performance(insights_data: dict) -> dict:
    """Use Claude to analyze campaign performance data and provide
    optimization recommendations."""
    client = _get_client()

    user_prompt = f"""\
Analyze this Meta Ads performance data and provide optimization recommendations:

{json.dumps(insights_data, indent=2)}

Return a JSON object with this exact schema:
{{
  "performance_summary": "brief summary of overall performance",
  "key_metrics": [
    {{"metric": "metric name", "value": "current value", "assessment": "good/average/poor"}}
  ],
  "recommendations": [
    {{"area": "targeting/creative/budget/bidding", "action": "specific recommendation", "priority": "high/medium/low"}}
  ],
  "estimated_impact": "expected improvement from implementing recommendations"
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "performance_summary": {"type": "string"},
                        "key_metrics": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "metric": {"type": "string"},
                                    "value": {"type": "string"},
                                    "assessment": {"type": "string"},
                                },
                                "required": ["metric", "value", "assessment"],
                                "additionalProperties": False,
                            },
                        },
                        "recommendations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "area": {"type": "string"},
                                    "action": {"type": "string"},
                                    "priority": {"type": "string"},
                                },
                                "required": ["area", "action", "priority"],
                                "additionalProperties": False,
                            },
                        },
                        "estimated_impact": {"type": "string"},
                    },
                    "required": ["performance_summary", "key_metrics", "recommendations", "estimated_impact"],
                    "additionalProperties": False,
                },
            }
        },
    )

    text_block = next(b for b in response.content if b.type == "text")
    return json.loads(text_block.text)
