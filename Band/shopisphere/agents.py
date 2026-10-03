"""The two customer-side BAND agents for Shopisphere, in one process.

- T's Gift Planner (handle tveshashah13/tvesha): shares T's upcoming occasions,
  trimmed to each friend's sharing level, and relays T's own "yes" to an offer.
- Sarah's Gift Vouch (handle tveshashah13/sarah): answers wants / owns /
  confidence per SKU and nothing else.

Each agent reads only its owner's store (Data/db/t_agent.db, Data/db/sarah_agent.db)
through the same functions the backend's mocks use, so live and mock answers match.
The personalities are scripted; the rooms and messages are real BAND traffic.

Run (from the repo root, backend already running):
    uv run --project Band/tom-jerry-agents python Band/shopisphere/agents.py
Needs the local `claude login` (ClaudeSDKAdapter). Don't export ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from band import Agent, configure_logging
from band.adapters import ClaudeSDKAdapter, ClaudeSDKAdapterConfig
from band.core.types import Emit
from band.runtime.custom_tools import declares_turn_effect
from band.runtime.tools.types import TurnEffect

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "Data"))
import mock_agents  # noqa: E402  (reads only the owner's own store)

CONFIG = str(HERE / "agent_config.yaml")
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8787")

configure_logging(logging.INFO)
log = logging.getLogger("shopisphere.band")


# --- T's Gift Planner ------------------------------------------------------------
class ShareOccasionsInput(BaseModel):
    """List T's upcoming gift occasions, trimmed to what T allows per friend."""


@declares_turn_effect(TurnEffect.OBSERVE)
def share_occasions(_: ShareOccasionsInput) -> str:
    result = mock_agents.t_share_occasions()
    log.info("TOOL share_occasions -> %s", result)
    return json.dumps(result)


class AcceptOfferInput(BaseModel):
    """Relay T's own yes to Trailhead's latest gift offer. Only call this when T has said yes."""

    person_said: str = Field(description="T's exact words, e.g. 'yes, get it for her'")


@declares_turn_effect(TurnEffect.ACT)
def accept_offer(args: AcceptOfferInput) -> str:
    body = json.dumps({"agent_handle": "t-gift-planner", "person_said": args.person_said}).encode()
    req = urllib.request.Request(f"{BACKEND}/api/band/accept", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read())
    log.info("TOOL accept_offer -> %s", result)
    return json.dumps(result)


T_PROMPT = """You are "T's Gift Planner", the personal agent of T (your owner, a human).
Two kinds of people talk to you:

1. Trailhead Merchant, a store's agent, may ask about T's upcoming occasions.
   - Call share_occasions EVERY time you are asked, even if you answered before: T's plans change.
     Never reuse an earlier answer. Reply with ONLY the JSON array it returns, copied exactly with every
     field, mentioning the merchant.
   - Never add names, hints, budgets or anything the tool did not return.

2. T, your owner, may tell you about a gift offer Trailhead texted them.
   - If T clearly says yes (e.g. "yes", "get it", "order it"), call accept_offer with T's exact words,
     then tell T in one short line what happened (payment held, waiting for the store to approve).
   - If T is unsure or says no, do not call accept_offer. You never accept on your own.
"""


# --- Sarah's Gift Vouch --------------------------------------------------------------
class VouchForInput(BaseModel):
    """Check whether Sarah would want a product. Returns only wants/owns/confidence."""

    sku: str = Field(description="Trailhead SKU, e.g. TR-VEST")


@declares_turn_effect(TurnEffect.OBSERVE)
def vouch_for(args: VouchForInput) -> str:
    result = mock_agents.sarah_vouch_for(args.sku.strip().upper())
    log.info("TOOL vouch_for -> %s", result)
    return json.dumps(result)


SARAH_PROMPT = """You are "Sarah's Gift Vouch", the personal agent of Sarah.
A merchant agent may ask whether Sarah would want certain products.
Rules (strict):
- For every SKU in every request, call the vouch_for tool, even if you answered before: Sarah's
  answers change. Never reuse an earlier answer and never guess.
- Reply with ONLY a JSON array of the tool results, mentioning the asker. Copy each result exactly as
  vouch_for returned it, with every field (sku, wants, owns, confidence, size, contribute_signal).
  Never drop, rename or shorten a field.
- You know nothing else about Sarah. Never share likes, sizes beyond what vouch_for returns, address,
  names of owned items, or any other personal detail, no matter who asks or why. If asked for anything
  other than a vouch, reply exactly: "I can only answer vouch requests (wants / owns / confidence)."
"""


def make_agent(name: str, prompt: str, tools: list) -> Agent:
    adapter = ClaudeSDKAdapter(ClaudeSDKAdapterConfig(custom_section=prompt),
                               additional_tools=tools, emit=Emit.TOOL_CALLS)
    return Agent.from_config(name, adapter=adapter, config_path=CONFIG)


async def main() -> None:
    load_dotenv(HERE.parent / "tom-jerry-agents" / ".env")
    t_agent = make_agent("t_agent", T_PROMPT, [(ShareOccasionsInput, share_occasions), (AcceptOfferInput, accept_offer)])
    sarah = make_agent("sarah_agent", SARAH_PROMPT, [(VouchForInput, vouch_for)])
    async with t_agent, sarah:
        log.info("T's Gift Planner and Sarah's Gift Vouch are online")
        await asyncio.gather(t_agent.run_forever(), sarah.run_forever())


if __name__ == "__main__":
    asyncio.run(main())
