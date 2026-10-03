# ZOOWORKS

Findings from experimenting with ZooWork's general setup and access, scoped to this folder only, cross-checked against `plan.md`. Sources: the `zoowork-managed-agents` skill installed here via `npx skills add SerendipityOneInc/zoowork-sdk-skills` (SKILL.md + `references/*.md`), the live current public docs (fetched directly, not just the bundled skill snapshot), and one real live test against the ZooWork API using the `ZOOWORKS` key from `.env` (see "Live test" below — cost: 1 `listModels` call + 1 agent created/started/stopped/deleted + 1 short session turn).

**Evidence labels used below** (same framework the skill itself uses): **Live-verified** = I called the real API with the real key and saw the result myself. **Source-reviewed** = confirmed in the installed skill's reference docs or the live public docs page, but I did not call an endpoint myself (often because no such endpoint/SDK method exists to call). **Unknown** = no evidence either way.

## Environment checks (done)

- `node --version` → `v22.23.1`. Satisfies both the skill's "Node.js 20+" floor and plan.md's "Node 22.20+" note for the quickstart.
- `npx skills add SerendipityOneInc/zoowork-sdk-skills` ran successfully **from this folder**. It installed to `Zooworks/.agents/skills/zoowork-managed-agents/` (symlinked for Claude Code) — nothing was written outside Zooworks.
- Install-time risk scan on the skill package: Gen = Medium risk, Socket = 0 alerts, Snyk = Low risk. Worth a glance (https://skills.sh/SerendipityOneInc/zoowork-sdk-skills) but not a blocker — it's the sponsor's own hackathon skill.
- The actual SDK packages (`@zoowork-ai/sdk` for TS, `zoowork` for Python) are **not installed yet** — only the coding-assistant skill and reference docs were pulled. Still need `npm install @zoowork-ai/sdk` or `python -m pip install zoowork` before writing real agent code, once the team picks a stack (plan.md decision #14).
- Found a key in the repo root `.env`: `ZOOWORKS=zwp_live_...` (a Project API key — `zwp_live_` prefix matches the format the skill docs describe for `ZOOWORK_API_KEY`). **Live-verified: the key works.** See "Live test" below.
- `@zoowork-ai/sdk` is now installed in this folder (`npm install @zoowork-ai/sdk`, version `0.10.2`, satisfies the skill's "0.10.0+" assumption). This added `node_modules/`, `package.json`, `package-lock.json` to `Zooworks/` — fine to delete/reinstall later, or keep if the team builds the merchant agent in TypeScript here.

## Live test (done — real API calls against the real key)

Script: `Zooworks/live-check.mjs` (reads the key from `.env` itself, never prints it, cleans up after itself). Ran it once:

1. `listModels()` → **42 models returned**, key is valid. Platform's primary chat default resolved to `litellm/gpt-5.6-terra`.
2. `createAgent` → `startAgent` → `waitUntilRunning` → **a real Agent actually started** (`agt_01m41jd5qa5rfn8s74bfzrr5je`), confirming plan.md's "agent starts stopped" gap note end-to-end, not just from docs.
3. `listAgentSkills(agentId)` on that brand-new agent → the **global skills attached by default** are: `chameleon-seedance`, `council`, `deep-research`, `designer`, `docx`, `glossary`, `humanizer`, `knowledge-base`, `meeting-notes`, `pdf`, `pptx`, `video-generator`, `web-designer`, `xlsx`, `zooclaw-asr`, `zooclaw-tts`. **No ZooData skill, no Amazon/TikTok tool, is attached by default.**
4. Asked the running agent directly, in a real session, to list every tool and skill it has, verbatim. Its own built-in tool list (`agent_db`, `web_search`, `web_fetch`, `composio_execute`/`composio_tools`, etc. — full list in the script's output) **contains nothing ZooData-, Amazon-, or TikTok-Shop-specific.**
5. Cleaned up: `stopAgent` + `deleteAgent` on the test agent — nothing was left running or billing in the background.

## Security flag (please see before committing anything)

- The hackathon repo root's `.gitignore` is **empty**, and `.env` (holding the live `zwp_live_...` key) is currently untracked only because the whole `walt-disney-hackathon` folder hasn't been `git add`-ed yet. A plain `git add -A` or `git add .` from the repo root would stage this live key. Recommend adding `.env` to `.gitignore` before anyone stages files.

## Corrections to plan.md's assumptions (confirmed against the docs)

1. **Decision #6 ("ZooWork schedule, fired manually on stage") and the gap note "use a far-off cron and fire the schedule manually" don't work as written.** `triggerSchedule` on a **disabled** schedule returns `triggered: true` but the run is silently skipped — this is not a test/dry-run mode. Manual execution only actually runs work if `enabled: true`, and enabling a schedule also arms its real cadence. Pick one:
   - Create the cron far in the future (e.g., yearly) **and enabled**, then use `triggerSchedule` live on stage — accept that it's technically "armed" the whole time.
   - Or skip ZooWork Schedules for the demo trigger entirely and use the contingency already in plan.md ("Dashboard button calls `createSession` with the same message") — this sidesteps the edge case completely and is simpler.
2. **iMessage/WhatsApp/Slack channels: there is nothing for you to set up, and no setting to flip — this is source-reviewed, not something I could call and watch fail, because no SDK method or endpoint for it exists at all.** I re-fetched the live, current public docs page (https://zoowork.ai/docs/en/build/channels) directly, not just the bundled skill's paraphrase of it, and it says in plain language: *"Managed channel bindings and guided setup are currently unavailable with Platform API keys"* and *"Platform API keys created in ZooWork Platform cannot list, create, update, or remove managed channel bindings, or run QR setup."* There's no `createChannel`/`bindChannel` method anywhere in the installed SDK (`@zoowork-ai/sdk` 0.10.2) to even attempt calling — the capability is absent, not hidden behind an error I could trigger. **What this means for you specifically:** don't spend booth time asking whether your key can get upgraded or whether there's an account toggle — the docs are explicit this applies to all Platform API keys, not a tier issue. Go straight to plan.md's own default (Twilio SMS, with the fake-phone panel as backup) and build it as "receive messages through that channel's own API and route them into a Session yourself" — exactly what the docs recommend in place of a managed channel. Root-Environment administration is a separate, smaller boundary (also 404 for Project keys per the skill docs) but doesn't affect the messaging decision.
3. **The Outcome rubric is real but schedule-only** — `payload.outcome` on a schedule (or `resource.outcome` as an agent-level default), with `description`, a `command` or `rubric` evaluator, `maxIterations` (1–5), and a `publish` policy. It does **not** exist on interactive Sessions (no rubric field on `createSession`, no outcome event in session streams). Plan.md's "Outcome rubric on the scheduled run" is already scoped correctly — keep it on the schedule path only; don't try to carry it over to the manual/fallback session trigger.
4. **The approval gate plan.md wants for `place_order` is real and REST-resolvable.** A pending approval shows as `agent.approval` / `phase: 'requested'`, with `listApprovals(agentId, { status: 'pending' })` for recovery and `resolveApproval` / `user.tool_confirmation` to resolve it against an `allowed_decisions` list. Build `place_order` as a tool call that genuinely blocks until a human approves — this maps directly to the dashboard's "visible approval gate" item.
5. **Confirmed: a new Agent starts stopped.** `createAgent` → must `startAgent(id)` then `waitUntilRunning(id)` before any Session, or Sessions 409. Matches plan.md's own gap note exactly.
6. **New finding, not in plan.md: create Agents one at a time.** Concurrent `createAgent` calls under the same key/Org can fail with `503 platform.runtime_credentials_unavailable` and create nothing — retry with backoff and the same idempotency key. Relevant if more than one teammate is provisioning agents simultaneously during the 11:30–12:15 "prove the plumbing" slot.
7. **Custom tool budget is generous: up to 32 entries under `resource.custom_tools`.** Plan.md's merchant + returns + replenishment tool list (`get_top_customers`, `ask_customer_occasions`, `match_catalog`, `request_vouch`, `check_competitor_price`, `score_agent_trust`, `make_offer`, `send_message`, `place_order`, `screen_return_risk`, `forecast_from_vouches`, `draft_purchase_order`, optionally `tiktok_shop_trends`) is ~13 tools — comfortably fits on one agent even combined.
8. **MCP is not a usable path for authenticated calls** — a declared MCP server's `credential` slug points at a store the key can't write to (404 behind the gateway by design), so only unauthenticated/public MCP servers really work. Plan.md already implements Tavily (`check_competitor_price`) and ZooData as **application-executed custom tools**, not MCP, so this doesn't block anything — just don't switch either one to MCP later expecting to pass an API key through it.
9. **Webhooks are confirmed outbound-only**, matching plan.md's own gap note: the platform can push events to a public HTTPS receiver (port 443 required — ngrok/Cloudflare Tunnel/early deploy), but there's no way to receive a reply over a webhook. Replies from T must come back through the backend and get forwarded into a Session, as plan.md already describes.

## ZooData: TikTok Shop and Amazon — tested, here's the real answer

This resolves plan.md's decision #17 and booth question. I checked two separate things:

**TikTok Shop — no, and it's not a credentials problem, the tooling doesn't exist yet.** I pulled the live `SerendipityOneInc/ZooData-Skills` GitHub repo (the one plan.md cites as the source). It documents 10 skills, all Amazon-focused (`zoodata` direct API with "25 Amazon commerce and keyword-intelligence endpoints", `amazon-analysis`, `amazon-market-analysis`, `amazon-pricing-command-center`, etc.). TikTok is mentioned only as marketing copy ("TikTok & beyond") in the repo header — **there is no TikTok skill, tool, or endpoint anywhere in the actual skill listings.** This is stronger than plan.md's own caveat ("documented skills are Amazon-only") — it's not that TikTok is undocumented, it's that it isn't built. Recommend following plan.md's own cut-list item #1 and dropping TikTok Shop trends entirely; don't spend the "2-minute ZooData console check" plan.md proposed, there's nothing there to find.

**Amazon — untested, and I couldn't test it with what's in this project today.** Two live findings say why:
1. ZooData needs its **own separate key**, not the ZooWork key: the repo's setup step is `export ZOODATA_API_KEY='hms_live_xxx'` (free tier: 1,000 signup credits, 1 credit = 1 API call). `.env` in this project only has `ZOOWORKS` (the `zwp_live_...` ZooWork key) — there is no `ZOODATA_API_KEY` anywhere.
2. I also live-verified (not just read) that ZooData is **not auto-attached** to a ZooWork agent: I created a real, running agent with this project's ZooWork key and listed its skills — the default global skill set is `chameleon-seedance`, `council`, `deep-research`, `designer`, `docx`, `glossary`, `humanizer`, `knowledge-base`, `meeting-notes`, `pdf`, `pptx`, `video-generator`, `web-designer`, `xlsx`, `zooclaw-asr`, `zooclaw-tts` — no ZooData skill is in that list, and the agent's own tool list (asked directly, in a real turn) confirms it has no Amazon/ZooData-specific tool either.

**What you'd need to actually get a live Amazon answer:** sign up at zoodata.ai for a `ZOODATA_API_KEY`, add it to `.env`, and either (a) call the ZooData REST API directly from the backend as a custom tool (matches plan.md's own design — ZooData/Tavily were already meant to be app-executed custom tools, not platform-attached skills), or (b) explicitly attach the ZooData skill package to the ZooWork agent via the Skill registry. Tell me if you get that key and I'll run a real Amazon query live.

## Still open (can't be resolved without the booth or a key you don't have yet)

- Whether memory tools are enabled on hackathon keys — not addressed in the docs pulled here, and not something the agent's own tool list (above) settled either way.
- Any per-key limit on number of agents or schedule frequency — not addressed in the docs pulled here (only the "one `createAgent` at a time" concurrency note above was found).

## What's installed in this folder

- `Zooworks/.agents/skills/zoowork-managed-agents/` — the ZooWork coding-agent skill: `SKILL.md` plus `references/{typescript-sdk,python-sdk,developer-api,events-and-streaming,deploy-your-agent,skill-registry,not-supported}.md`. Read the relevant reference file before writing any real agent code — SKILL.md has a routing table by task.
- `Zooworks/node_modules/`, `package.json`, `package-lock.json` — from `npm install @zoowork-ai/sdk` (0.10.2). Fine to keep if building the merchant agent in TypeScript here, or delete if the team picks Python instead.
- `Zooworks/live-check.mjs` — the live-test script described above. Safe to re-run any time (it cleans up its own test agent each time); costs roughly one `listModels` call + one short agent lifecycle + one session turn per run.

## Tool inputs & outputs (contract with Data/ backend)

The merchant agent's 13 custom tools are executed by our backend. Saved real samples for every tool: `Data/samples/tools/<name>.json` (regenerate with `python3 Data/capture_samples.py`). Ready-to-paste `resource.custom_tools` declarations (name, description, `input_schema`): `Data/samples/api/tools_custom_tools.json`, or live at `GET http://localhost:8787/api/tools`.

**Wiring (one loop in the ZooWork bridge):** on `agent.custom_tool_use` with `phase: "requested"` → `POST http://localhost:8787/api/tools/<call.name>` with `call.input` as the JSON body (header `X-Source: zoowork`) → resolve with `resolve_custom_tool_call(agent_id, call.call_id, content=[{"type": "json", "value": <response>}])`. Push session events to `POST /api/events` (`{source: "zoowork", kind, summary, payload}`) so they show in the dashboard log.

| Tool | Input (required **bold**) | Output |
| --- | --- | --- |
| `get_top_customers` | `limit` | `[{customer_id, name, agent_handle, phone, order_count, favorite_lines}]` |
| `score_agent_trust` | **`agent_handle`**, `requests_per_min`, `discount_first` | `{agent_handle, decision: allow\|decline, score 0–1, layers{identity, provenance, history, behavior}, reasons[]}` |
| `ask_customer_occasions` | **`customer_id`** | `{customer_id, occasions: [{friend_handle, occasion, occasion_date, budget?, hints?, sharing_level}]}` |
| `match_catalog` | **`customer_id`**, `budget`, `hints`, `k` | `[{sku, name, line, price, cost, tags, stock, competitor_query}]` (top k=3) |
| `request_vouch` | **`recipient_handle`**, **`skus[]`** | `{vouched, ranked: [{sku, wants, owns, confidence, size}], dropped_owned[]}`; no agent → `{vouched: false, ranked: [], note}` |
| `check_competitor_price` | **`sku`** | `{sku, our_price, competitors[], lowest, suggested_discount_pct, reason}` |
| `make_offer` | **`customer_id, sku, occasion_ref, discount_pct, trust_score`**, `vouch_result, size, budget` | `{ok: true, offer_id, final_price, discount_pct, reason}` or `{ok: false, problems[]}` (Outcome rubric) |
| `send_message` | **`customer_id, body`**, `offer_id` | `{sent: true, status}` |
| `place_order` | **`offer_id`** | `{approval_id, status: "pending"}` (order is created only on approval) |
| `screen_return_risk` | `order_id` (omit = all gift orders) | `{orders: [... return_risk: low\|medium], gift_return_rates: {vouched, unvouched}}` |
| `handle_storefront_request` | **`agent_handle, ask`**, `requests_per_min` | same as `score_agent_trust` + `ask` |
| `forecast_from_vouches` | `safety_stock` (default 2) | `[{sku, size, name, wants, owns, on_hand, suggested_qty, note}]` |
| `draft_purchase_order` | **`sku, size, quantity`**, `reason` | `{po_id, approval_id, status: "draft"}` |

**Samples (captured from the running backend, mock data):**

```jsonc
// get_top_customers
{"limit": 3}
→ [{"customer_id": "cust_t", "name": "T", "agent_handle": "t-gift-planner", "phone": "+15550100", "order_count": 6, "favorite_lines": "trail"}, ...]

// score_agent_trust
{"agent_handle": "t-gift-planner"}
→ {"agent_handle": "t-gift-planner", "decision": "allow", "score": 1.0,
   "layers": {"identity": true, "provenance": true, "history": true, "behavior": true}, "reasons": []}

// ask_customer_occasions  (fields trimmed per friend by T's sharing level)
{"customer_id": "cust_t"}
→ {"customer_id": "cust_t", "occasions": [
     {"friend_handle": "sarah-gift-vouch", "occasion": "birthday", "occasion_date": "2026-10-24", "budget": 60.0, "sharing_level": "occasion_budget"},
     {"friend_handle": "jo-no-agent", "occasion": "anniversary", "occasion_date": "2026-11-12", "sharing_level": "occasion_only"}, ...]}

// match_catalog
{"customer_id": "cust_t", "budget": 60.0}
→ [{"sku": "TR-LAMP", "name": "Trail Headlamp 400", "price": 55.0, ...}, {"sku": "TR-VEST", ...}, {"sku": "TR-BOTTLE", ...}]

// request_vouch
{"recipient_handle": "sarah-gift-vouch", "skus": ["TR-LAMP", "TR-VEST", "TR-BOTTLE"]}
→ {"vouched": true,
   "ranked": [{"sku": "TR-VEST", "wants": true, "owns": false, "confidence": 0.9, "size": "M", "contribute_signal": true},
              {"sku": "TR-LAMP", "wants": false, "owns": false, "confidence": 0.5, "size": null, "contribute_signal": true}],
   "dropped_owned": ["TR-BOTTLE"]}

// check_competitor_price
{"sku": "TR-VEST"}
→ {"sku": "TR-VEST", "our_price": 68.0, "competitors": [{"name": "Summit Outfitters", "price": 64.0, "url": "..."}, ...],
   "lowest": 64.0, "suggested_discount_pct": 15,
   "reason": "Tavily: Trail Running Vest at 2 competitors, lowest $64.0; we're $4.0 above, offer 15%"}

// make_offer
{"customer_id": "cust_t", "sku": "TR-VEST", "occasion_ref": "sarah-gift-vouch:birthday:2026-10-24", "discount_pct": 15,
 "trust_score": 1.0, "vouch_result": {"sku": "TR-VEST", "wants": true, "confidence": 0.9, ...}, "size": "M", "budget": 60.0}
→ {"ok": true, "offer_id": 1, "final_price": 57.8, "discount_pct": 15,
   "reason": "From the store you love, a gift she'll want: Trail Running Vest (her agent confirmed it), 15% off"}

// send_message
{"customer_id": "cust_t", "offer_id": 1, "body": "A friend's birthday is on 2026-10-24. ... Reply YES."}
→ {"sent": true, "status": "delivered to fake phone"}

// place_order
{"offer_id": 1}
→ {"approval_id": 1, "status": "pending"}

// handle_storefront_request  (the bot)
{"agent_handle": "unverified-shopper", "ask": "15% discount please", "requests_per_min": 40}
→ {"ask": "15% discount please", "agent_handle": "unverified-shopper", "decision": "decline", "score": 0.0,
   "layers": {"identity": false, "provenance": false, "history": false, "behavior": false},
   "reasons": ["identity: no signed passport / owner not phone-verified", "provenance: unknown handle, not an approved contact",
               "history: no prior orders here", "behavior: 40 req/min, discount-first ask"]}

// forecast_from_vouches
{}
→ [{"sku": "TR-VEST", "size": "M", "wants": 9, "owns": 0, "on_hand": 3, "name": "Trail Running Vest",
    "suggested_qty": 8, "note": "9 vouched wants, 3 on hand: draft PO for 8"}, ...]

// draft_purchase_order
{"sku": "TR-VEST", "size": "M", "quantity": 8, "reason": "9 vouched wants, 3 on hand: draft PO for 8"}
→ {"po_id": 1, "approval_id": 2, "status": "draft"}

// screen_return_risk
{}
→ {"orders": [{"order_id": 25, "sku": "TR-VEST", "is_gift": 1, "vouched": 1, "return_risk": "low", ...}, ...],
   "gift_return_rates": {"unvouched": 0.5, "vouched": 0.0}}
```

**Approval gate mirror:** the dashboard resolves approvals at `POST /api/approvals/<approval_id>` `{"decision": "approve"}` → `{"approval_id": 1, "status": "approved", "order_id": 25, "return_risk": "low"}`. If the real ZooWork `agent.approval` gate is used, call `resolveApproval` in ZooWork *and* this endpoint, so both stay in sync.

## Composio / Gmail check (live, 2026-10-03)

Script: `Zooworks/composio-check.mjs`. Output: `data/composio-check-output-2026-10-03.txt`. Raw events: `data/composio-check-events-2026-10-03.json`. Cost: one throwaway agent (created, then deleted) and two short turns.

- **Live-verified:** the agent really called `composio_tools` 3 times (`agent.tool` start/end events, `isError: false`). Every call returned: *"No Composio integrations are connected and enabled for this user."* The `provider: gmail` filter gave the same answer.
- The tool can only list or run integrations that are **already connected**. It has no action to start OAuth or get a connect link, so `composio_execute` had nothing to run.
- **Source-reviewed:** the SDK (`@zoowork-ai/sdk` 0.10.2) has no Composio or connected-account methods, and `not-supported.md` says "There is no vault resource of any kind and no credential methods on the client." A Platform key has no way to connect Gmail.
- **Decision:** don't use Composio. Send Gmail from the backend (`Data/adapters.py`, `send_email`, behind the same bridge-or-mock pattern as `send_sms`).
