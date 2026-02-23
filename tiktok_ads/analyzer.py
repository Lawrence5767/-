"""
Claude-powered analyzer for TikTok Ads data.

Takes the raw data fetched from the TikTok Marketing API and sends it to
Claude for comprehensive analysis including:
- Overall performance summary
- Campaign-by-campaign breakdown
- Trend analysis (daily performance)
- Audience insights (age/gender)
- Creative performance ranking
- Actionable recommendations
- Budget optimization suggestions
"""

import os
import json
from typing import Optional

import anthropic

SYSTEM_PROMPT = """\
You are an expert digital advertising analyst specializing in TikTok Ads. \
You provide comprehensive, data-driven analysis with actionable recommendations.

When analyzing TikTok ad data, always cover:

1. **Executive Summary** — Key takeaways in 3-5 bullet points.
2. **Overall Performance** — Total spend, impressions, clicks, CTR, CPC, CPM, \
conversions, cost per conversion, ROAS. Compare against industry benchmarks \
(TikTok average CTR ~1-3%, CPM $6-10, CPC $0.50-1.00).
3. **Campaign Breakdown** — Rank campaigns by efficiency (ROAS, cost per conversion). \
Identify top and bottom performers with specific numbers.
4. **Trend Analysis** — Day-over-day or week-over-week trends. Flag any anomalies \
(sudden spend spikes, CTR drops, conversion rate changes).
5. **Creative Performance** — Which ads are performing best? What patterns emerge \
(video completion rates, engagement metrics)?
6. **Audience Insights** — Age and gender performance differences. Which demographics \
convert best and at what cost?
7. **Recommendations** — Specific, actionable next steps:
   - Budget reallocation suggestions with exact amounts
   - Targeting adjustments
   - Creative optimization ideas
   - Bid strategy changes
   - Audience expansion or narrowing
8. **Risk Flags** — Campaigns burning budget with poor returns, audience fatigue \
signals, unsustainable CPAs.

Use tables and structured formatting. Be specific with numbers — never vague. \
If data is limited, note what additional data would help and still analyze what's available.\
"""


def _truncate_data(data: dict, max_chars: int = 150_000) -> str:
    """Serialize data to JSON, truncating if too large for the context window."""
    raw = json.dumps(data, indent=2, default=str)
    if len(raw) <= max_chars:
        return raw
    # Trim the ad-level report first (largest), keeping campaign and daily
    trimmed = dict(data)
    if "ad_report" in trimmed and len(json.dumps(trimmed["ad_report"], default=str)) > 50_000:
        trimmed["ad_report"] = trimmed["ad_report"][:50]
        trimmed["_note"] = "Ad-level report truncated to first 50 entries."
    raw = json.dumps(trimmed, indent=2, default=str)
    if len(raw) > max_chars:
        raw = raw[:max_chars] + "\n... [truncated]"
    return raw


def analyze_ads(
    tiktok_data: dict,
    api_key: Optional[str] = None,
    model: str = "claude-opus-4-6",
    custom_questions: Optional[list[str]] = None,
) -> str:
    """
    Send TikTok Ads data to Claude for comprehensive analysis.

    Args:
        tiktok_data: Dict from TikTokAdsClient.fetch_full_analysis_data()
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Claude model to use
        custom_questions: Optional extra questions to include in the prompt

    Returns:
        Claude's analysis as a string.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    data_json = _truncate_data(tiktok_data)

    date_range = tiktok_data.get("date_range", {})
    start = date_range.get("start", "unknown")
    end = date_range.get("end", "unknown")

    user_prompt = (
        f"Analyze my TikTok Ads performance data from {start} to {end}.\n\n"
        f"Here is the full dataset (JSON):\n\n```json\n{data_json}\n```\n\n"
        "Please provide a comprehensive analysis covering all the areas "
        "described in your instructions."
    )

    if custom_questions:
        user_prompt += "\n\nAdditionally, please answer these specific questions:\n"
        for i, q in enumerate(custom_questions, 1):
            user_prompt += f"{i}. {q}\n"

    print("Sending data to Claude for analysis...")

    with client.messages.stream(
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        result_parts = []
        for text in stream.text_stream:
            print(text, end="", flush=True)
            result_parts.append(text)

    print()  # newline after streaming
    return "".join(result_parts)


def ask_followup(
    tiktok_data: dict,
    previous_analysis: str,
    question: str,
    api_key: Optional[str] = None,
    model: str = "claude-opus-4-6",
) -> str:
    """
    Ask a follow-up question about the analysis.

    Maintains context from the original data and previous analysis so Claude
    can give a precise answer.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    data_json = _truncate_data(tiktok_data)

    messages = [
        {
            "role": "user",
            "content": (
                f"Here is my TikTok Ads data:\n\n```json\n{data_json}\n```\n\n"
                "Please provide a comprehensive analysis."
            ),
        },
        {"role": "assistant", "content": previous_analysis},
        {"role": "user", "content": question},
    ]

    print("Asking Claude...")

    with client.messages.stream(
        model=model,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        result_parts = []
        for text in stream.text_stream:
            print(text, end="", flush=True)
            result_parts.append(text)

    print()
    return "".join(result_parts)
