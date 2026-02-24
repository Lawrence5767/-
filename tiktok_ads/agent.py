#!/usr/bin/env python3
"""
TikTok Ads Agent — Conversational campaign creator powered by Claude.

Usage:
    export ANTHROPIC_API_KEY="your-anthropic-key"
    export TIKTOK_ACCESS_TOKEN="your-tiktok-token"
    export TIKTOK_ADVERTISER_ID="your-advertiser-id"
    python agent.py
"""

import json
import os
import sys

import anthropic

from tiktok_client import TikTokAdsClient
from tools import TOOLS

MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """\
You are a TikTok Ads campaign creation assistant. You help users create \
advertising campaigns on TikTok through natural conversation.

You have access to the TikTok Marketing API through the following tools:
- create_campaign: Create a top-level campaign (defines objective and budget)
- create_adgroup: Create an ad group within a campaign (defines targeting, schedule, bidding)
- create_ad: Create an ad within an ad group (defines creative: text, video, CTA, landing page)
- list_campaigns: View existing campaigns
- list_adgroups: View existing ad groups
- list_ads: View existing ads

**Campaign structure**: Campaign → Ad Group → Ad

**Workflow**:
1. Ask the user about their advertising goal (objective)
2. Gather details: budget, target audience, schedule, ad creative
3. Create the campaign first, then the ad group, then the ad
4. Confirm each step with the user before calling the API

**Guidelines**:
- Be concise but thorough — ask for missing required info
- Suggest sensible defaults when the user is unsure
- Explain what each parameter means in simple terms
- After creating each resource, share the ID and confirm success
- If an API call fails, explain the error and suggest a fix
- Always confirm the full plan before executing any API calls
"""


def execute_tool(tiktok: TikTokAdsClient, tool_name: str, tool_input: dict) -> str:
    """Execute a TikTok Ads API tool and return the result as a string."""
    try:
        if tool_name == "create_campaign":
            result = tiktok.create_campaign(
                campaign_name=tool_input["campaign_name"],
                objective_type=tool_input["objective_type"],
                budget=tool_input.get("budget"),
                budget_mode=tool_input.get("budget_mode", "BUDGET_MODE_INFINITE"),
            )
        elif tool_name == "create_adgroup":
            result = tiktok.create_adgroup(
                campaign_id=tool_input["campaign_id"],
                adgroup_name=tool_input["adgroup_name"],
                placement_type=tool_input.get("placement_type", "PLACEMENT_TYPE_AUTOMATIC"),
                placements=tool_input.get("placements"),
                location_ids=tool_input.get("location_ids"),
                age_groups=tool_input.get("age_groups"),
                gender=tool_input.get("gender", "GENDER_UNLIMITED"),
                budget=tool_input.get("budget"),
                budget_mode=tool_input.get("budget_mode", "BUDGET_MODE_DAY"),
                schedule_type=tool_input.get("schedule_type", "SCHEDULE_FROM_NOW"),
                schedule_start_time=tool_input.get("schedule_start_time"),
                schedule_end_time=tool_input.get("schedule_end_time"),
                optimize_goal=tool_input.get("optimize_goal", "CLICK"),
                billing_event=tool_input.get("billing_event", "CPC"),
                bid_type=tool_input.get("bid_type", "BID_TYPE_NO_BID"),
                bid=tool_input.get("bid"),
                pacing=tool_input.get("pacing", "PACING_MODE_SMOOTH"),
            )
        elif tool_name == "create_ad":
            result = tiktok.create_ad(
                adgroup_id=tool_input["adgroup_id"],
                ad_name=tool_input["ad_name"],
                ad_text=tool_input["ad_text"],
                video_id=tool_input.get("video_id"),
                image_ids=tool_input.get("image_ids"),
                call_to_action=tool_input.get("call_to_action", "LEARN_MORE"),
                landing_page_url=tool_input.get("landing_page_url"),
                display_name=tool_input.get("display_name"),
                identity_id=tool_input.get("identity_id"),
                identity_type=tool_input.get("identity_type", "CUSTOMIZED_USER"),
            )
        elif tool_name == "list_campaigns":
            result = tiktok.get_campaigns()
        elif tool_name == "list_adgroups":
            result = tiktok.get_adgroups(
                campaign_id=tool_input.get("campaign_id"),
            )
        elif tool_name == "list_ads":
            result = tiktok.get_ads(
                adgroup_id=tool_input.get("adgroup_id"),
            )
        else:
            result = {"success": False, "error": f"Unknown tool: {tool_name}"}

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def run_agent():
    """Run the conversational TikTok Ads agent."""
    # Validate environment
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is required.")
        sys.exit(1)

    sandbox = os.environ.get("TIKTOK_SANDBOX", "").lower() in ("1", "true", "yes")

    try:
        tiktok = TikTokAdsClient(sandbox=sandbox)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    client = anthropic.Anthropic()
    messages: list[dict] = []

    mode_label = "SANDBOX" if sandbox else "PRODUCTION"
    print(f"TikTok Ads Agent [{mode_label}]")
    print("=" * 50)
    print("I can help you create TikTok ad campaigns.")
    print("Tell me about your advertising goals!")
    print("Type 'quit' or 'exit' to end the session.\n")

    while True:
        # Get user input
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # Agentic loop: keep going until Claude stops calling tools
        while True:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                thinking={"type": "adaptive"},
                messages=messages,
            )

            # Collect tool use blocks
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            # Print any text blocks
            for block in response.content:
                if block.type == "text":
                    print(f"\nAssistant: {block.text}")

            # If no tool calls, we're done with this turn
            if response.stop_reason == "end_turn" or not tool_use_blocks:
                # Append assistant response to message history
                messages.append({"role": "assistant", "content": response.content})
                break

            # Append assistant response (with tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tools and collect results
            tool_results = []
            for tool_block in tool_use_blocks:
                print(f"\n  [Calling {tool_block.name}...]")
                result = execute_tool(tiktok, tool_block.name, tool_block.input)

                # Parse for display
                result_data = json.loads(result)
                if result_data.get("success"):
                    print(f"  [Success]")
                else:
                    print(f"  [Error: {result_data.get('error', 'unknown')}]")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result,
                })

            # Append tool results as a user message
            messages.append({"role": "user", "content": tool_results})

        print()  # blank line between turns


if __name__ == "__main__":
    run_agent()
