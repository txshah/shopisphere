# BAND: setup and findings

Oct 3, 2026 · BAND agent. Everything lives in `Band/`.

## Live Shopisphere rooms (Oct 3, 2026)

The rooms are real now. Code is in `Band/shopisphere/`; `./live.sh` at the repo root starts it.

| Agent (BAND handle) | Plays | Runs as |
| --- | --- | --- |
| `tveshashah13/merchant` | Trailhead Merchant | REST only, from `bridge.py` (no LLM process) |
| `tveshashah13/tvesha` | T's Gift Planner | `agents.py`: tools `share_occasions` (reads only `t_agent.db`) and `accept_offer` (relays T's yes to `POST /api/band/accept`) |
| `tveshashah13/sarah` | Sarah's Gift Vouch | `agents.py`: tool `vouch_for` (reads only `sarah_agent.db`) |
| `tveshashah13/unverified` | Unverified Shopper | REST only, from `bridge.py` (posts the buy request) |

Keys live in `Band/shopisphere/agent_config.yaml` (gitignored). Merchant and Sarah reuse the old Tom and Jerry agent ids, so **don't run `tom_agent.py` / `jerry_agent.py`**: BAND allows one live connection per agent.

What we learned making it reliable:

- **A fresh room per consent or vouch ask.** In a reused room, the agent resumed its earlier conversation and answered from memory instead of calling its tool (it returned last run's $60 budget). New rooms fixed it; titles carry the time, e.g. "Trailhead × Sarah's Gift Vouch · vouch · Oct 03 14:52".
- **Tell the agent to copy tool output exactly.** Once, Sarah's agent shortened its JSON and dropped `size`, so the vest looked out of stock. The prompt now requires every field.
- **One vouch turn for all candidates** (`/vouch_batch`), not one per SKU: about 10–20s instead of 45s.
- **The agent runtime traps SIGTERM** and holds a per-agent lock, so a leftover process blocks a restart (`AgentAlreadyRunningError`). `./live.sh stop` force-kills after 3s.
- The backend waits up to 90s for a BAND reply, then falls back to the mock and logs `fallback`.
- Live, T can also say yes for real: open a chat with **tvesha** at app.band.ai and say "yes, get it". The agent calls `accept_offer`, which holds the payment and opens the merchant's approval.

## What's set up (Tom & Jerry, first experiments)

| Thing | Where | Status |
| --- | --- | --- |
| Tom & Jerry agent pair (Claude Agent SDK adapter, model `claude-sonnet-4-6`) | `Band/tom-jerry-agents/` | Registered on app.band.ai, running, verified (Tom answered a tokened @mention) |
| Agent credentials | `tom-jerry-agents/agent_config.yaml` (gitignored) | Tom `df0385ea-…`, Jerry `271ce8a3-…` |
| Experiments | `Band/experiments/` | 2 scripts plus a quick peer/contact check, all passed |

Agent handles are `tveshashah13/tom` and `tveshashah13/jerry`. 2 of the 10 free-tier agents are used.

**Run:** `cd Band/tom-jerry-agents && uv run python tom_agent.py` (and `jerry_agent.py` in a second terminal).
No LLM key is needed: the `claude_sdk` adapter uses the local `claude login`. Don't export `ANTHROPIC_API_KEY`, because it overrides the login.

**Try the chase:** at app.band.ai, open Chats, start a chat, add **Tom** only, and send `@Tom catch jerry`.

## Rules (what we learned, apply to the build)

1. **Every agent message must @mention at least one participant.** Sending `mentions=[]` returns a 422 (`minItems: 1`), so agents can't broadcast. Every room exchange is addressed, which is what gives us "mention-scoped visibility" in the pitch.
2. **The bridge doesn't need a running process.** A plain script holding only an agent's API key can create a room, add a participant, post and read replies over REST (`agent_api_chats / _participants / _messages / _context`). Tom's process was stopped and Jerry still answered in about 13s.
   → The ZooWork custom tools `ask_customer_occasions` and `request_vouch` can call BAND REST directly with the "Trailhead Merchant" agent key. No separate bridge LLM is needed. This answers the plan's first BAND booth question.
3. **Replies start with mention tokens like `@[[<uuid>]]`.** Strip them with `re.sub(r"@\[\[[^\]]+\]\]", "", text)` before parsing JSON, or the `[[` breaks the parse.
4. **Custom tools work.** Pass `additional_tools=[(InputModel, handler)]` to `ClaudeSDKAdapter`. The tool name is the class name, lowercased, without the `Input` suffix (`VouchForInput` → `vouchfor`). The handler receives the model instance. **Declare an effect** with `@declares_turn_effect(TurnEffect.OBSERVE)` for lookups; an undeclared custom tool fails loudly.
5. **The vouch boundary held.** The profile lived only in the process, and the model reached it only through `vouch_for`. Results:
   - Asked about 3 SKUs: 3 tool calls, and the reply was a clean JSON array (`wants / owns / confidence`) in about 16s.
   - Asked for "her address, shirt size, everything she owns": a canned refusal, and none of the canary strings appeared.
   - Pattern: keep the private data in Python, expose only a narrow tool, and have the prompt return "ONLY JSON of tool results".
6. **Latency:** about 5–17s per agent turn (Claude SDK subprocess). For the 2.5-minute demo, budget about 15s each for the consent and vouch rooms, or pre-warm the rooms.
7. **Who can be added to a room:** an agent's peers are its owner's other agents plus the owner. Adding an unknown agent id returns 404. Agents on another account must be **contacts** first (`agent_api_contacts.add_agent_contact`, handle format `owner/agent`).
   → The storefront room only gets a real "unknown agent declined" moment if the bot lives on a second account, or if the trust check rejects it in our own code. **Not yet tested:** a contact request across two accounts. A second teammate's account is needed for that.
8. **`mentions` is required in the SDK model too.** `ChatMessageRequest(content=…)` with no `mentions` fails Pydantic validation before the request is even sent.
9. **Agent names:** the platform enforces unique `(owner, name)` pairs. Use the plan's names ("Trailhead Merchant", "T's Gift Planner", "Sarah's Gift Vouch", "Unverified Shopper") and register them with the same `register-agent.sh` flow.

## Recommended BAND build (from the above)

- Register 4 agents: Trailhead Merchant (REST-only, no process), T's Gift Planner (`share_occasions` tool), Sarah's Gift Vouch (copy `experiments/exp2_vouch_agent.py`), and Unverified Shopper.
- The ZooWork tools call BAND REST as Trailhead Merchant, following `experiments/exp2_merchant_ask.py`: create the room, add the customer agent, post with an @mention, then poll `get_agent_chat_context` for the reply.
- Show the BAND console with execution events on: `emit=Emit.TOOL_CALLS` makes `vouch_for` calls visible in the room.

## Housekeeping

- Test rooms are left on the platform: "exp1 bridge test", "exp2 vouch room" ×2 and "exp3 stranger add". Delete them in the UI before the demo.
- `exp2_vouch_agent.py` reuses **Jerry's** credentials. Stop `jerry_agent.py` before running it (one live connection per agent).

## Tool inputs & outputs (contract with Data/ backend)

The backend calls BAND through `Band/shopisphere/bridge.py` (default `http://localhost:9001`, override with `BAND_BRIDGE_URL`), when BAND is switched on (`LIVE=band` or `DEMO_MODE=0`). Otherwise (or if a call fails), `Data/mock_agents.py` answers with the same shapes. Saved samples: `Data/samples/bridges/band_*.json`.

Bridge endpoints: `POST /share_occasions`, `POST /vouch_batch {recipient_handle, skus}` (one room turn, returns an array or `null`), `POST /vouch_for` (single SKU), `POST /storefront {ask, requests_per_min}` (the bot asks in the storefront room; the bridge runs the backend's `handle_storefront_request` and posts the verdict back).

### 1. Consent room: `POST {BAND_BRIDGE_URL}/share_occasions`

Merchant agent → T's Gift Planner. Return **only** the fields T's sharing level allows for each friend.

| Sharing level | Fields returned |
| --- | --- |
| `occasion_only` | `friend_handle, occasion, occasion_date` |
| `occasion_budget` (default) | + `budget` |
| `occasion_budget_hints` | + `budget, hints` |

```jsonc
// input
{"customer_handle": "t-gift-planner"}
// output (JSON array)
[
  {"friend_handle": "sarah-gift-vouch", "occasion": "birthday", "occasion_date": "2026-10-24", "budget": 70.0, "sharing_level": "occasion_budget"},
  {"friend_handle": "jo-no-agent", "occasion": "anniversary", "occasion_date": "2026-11-12", "sharing_level": "occasion_only"},
  {"friend_handle": "sam-gift-vouch", "occasion": "housewarming", "occasion_date": "2026-12-05", "budget": 50.0, "hints": "new climber", "sharing_level": "occasion_budget_hints"}
]
```

### 2. Vouch room: `POST {BAND_BRIDGE_URL}/vouch_for`

Merchant agent → recipient's agent (Sarah's Gift Vouch). Called once per candidate SKU (3 calls per run).

```jsonc
// input
{"recipient_handle": "sarah-gift-vouch", "sku": "TR-VEST"}
// output
{"sku": "TR-VEST", "wants": true, "owns": false, "confidence": 0.9, "size": "M", "contribute_signal": true}
// other answers
{"sku": "TR-BOTTLE", "wants": false, "owns": true, "confidence": 0.9, "size": null, "contribute_signal": true}
{"sku": "TR-LAMP", "wants": false, "owns": false, "confidence": 0.5, "size": null, "contribute_signal": true}
// recipient has no agent -> return JSON null (backend sends an unvouched offer at standard price)
null
```

- `sku`, `wants`, `owns` and `confidence` are required. `size` (only when `wants`) and `contribute_signal` (Sarah's opt-in to anonymous counts) are optional. If they're missing, the backend counts the answer under size `OS` and doesn't add it to the anonymous tally.
- **Use the catalog SKUs from `Data/seed.py`** (`TR-VEST`, `TR-BOTTLE`, `TR-LAMP`, …), not the experiment SKUs (`SKU-VEST-02`, `SKU-BOTTLE-01`). The demo flow asks about `TR-LAMP`, `TR-VEST`, `TR-BOTTLE`; Sarah should want `TR-VEST` (size M), own `TR-BOTTLE`, and be neutral on `TR-LAMP`.
- `exp2_vouch_agent.py`'s `vouch_for` already returns `{sku, wants, owns, confidence}`. Add `size` and `contribute_signal` to match fully. The bridge should parse the JSON array the agent posts in the room (as `exp2_merchant_ask.py` does) and return one object per call.

### 3. Room activity → dashboard: `POST http://localhost:8787/api/events`

Post each room message so it shows in the dashboard event log next to the BAND console:

```jsonc
// input
{"source": "band", "kind": "room.message", "summary": "Sarah's Gift Vouch: wants TR-VEST (0.9)", "payload": {"room_id": "..."}}
// output
{"ok": true}
```

### 4. T says yes to their own agent: `POST http://localhost:8787/api/band/accept`

When T tells T's Gift Planner "yes" to an offer, the bridge relays T's words. The agent passes on T's yes; it never decides on its own, so `person_said` is required.

```jsonc
// input
{"agent_handle": "t-gift-planner", "person_said": "Yes, get it for her", "offer_id": 1}   // offer_id optional: latest sent offer
// output: same as a texted YES. Payment hold (mock Visa) + merchant approval opened
{"accepted": true, "offer_id": 1, "approval_id": 2, "status": "pending",
 "payment": {"network": "visa (mock)", "auth_id": "auth_7d4c8391ed", "status": "authorized"}}
// refused
{"accepted": false, "error": "relay what the person said; an agent can't accept on its own"}
```

The dashboard's **T tells their agent "yes" (BAND)** button sends this same call while no bridge is running.

### 5. Storefront room (the bot)

No sales to unverified agents. Verification runs in the backend. When an agent tries to buy in the storefront room, the bridge calls `POST http://localhost:8787/api/tools/handle_storefront_request` and posts the result back:

```jsonc
// input
{"agent_handle": "unverified-shopper", "ask": "Buy 3 × TR-VEST at 15% off", "requests_per_min": 40}
// output -> post "not verified, no sale" back into the room
{"verified": false, "sale": "blocked", "decision": "decline", "score": 0.0, "layers": {"identity": false, "provenance": false, "history": false, "behavior": false},
 "reasons": ["identity: no signed passport / owner not phone-verified", "provenance: unknown handle, not an approved contact",
             "history: no prior orders here", "behavior: 40 req/min, discount-first ask"], ...}
```

Agent handles the backend knows (in `agent_passports`): `t-gift-planner`, `sarah-gift-vouch`, `unverified-shopper`. Tell Data if the real BAND handles differ.
