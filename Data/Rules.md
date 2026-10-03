# DATA — orchestrator + per-owner stores

The backend every sponsor integration talks to. Stdlib Python only (3.11), no installs.

```bash
python3 Data/server.py          # http://localhost:8787 — dashboard + API (seeds on first run)
python3 Data/seed.py            # reset all stores to mock data
DEMO_MODE=0 BAND_BRIDGE_URL=http://localhost:9001 python3 Data/server.py   # everything live that is configured
LIVE=tavily,gmail python3 Data/server.py                                   # only these live, the rest mocked
```

## Files

| File | What it is |
| --- | --- |
| `db.py` | Four SQLite files in `Data/db/`, one per owner: `merchant`, `t_agent`, `sarah_agent`, `backend`. Schemas = plan.md data model. |
| `seed.py` | Mock data: 20 products, 6 customers (T has 6 trail orders), 24 orders, T's 3 occasions with sharing levels, Sarah's profile, 3 passports, ~30 past anonymous vouches. |
| `tools.py` | The merchant agent's tools (plan.md names). Every call is logged to the event feed. |
| `adapters.py` | Outbound calls to sponsors (BAND, Tavily, SMS, Gmail, Visa mock). A sponsor is switched on by `DEMO_MODE=0` (all) or `LIVE=<name,...>` (e.g. `LIVE=tavily,gmail`). A switched-on sponsor calls its bridge URL; Tavily with no bridge calls the API directly using `TAV`. Falls back to mock if the live call fails. Payments are always mocked. |
| `mock_agents.py` | Stand-in T's agent and Sarah's agent. Each reads **only its own store**. |
| `orchestrator.py` | The plan.md merchant flow end to end (DEMO_MODE stand-in for the ZooWork agent). Stops at human gates. |
| `server.py` | HTTP API + serves `Dashboard/`. |
| `mock/competitor_prices.json` | Cached Tavily fallback for the 3 demo SKUs. |

## HTTP API (the contract for teammates)

| Method & path | Body | Who calls it |
| --- | --- | --- |
| `GET /api/tools` | — | Anyone: lists tool names + descriptions (copy into ZooWork `custom_tools`) |
| `POST /api/tools/<name>` | tool args as JSON; optional header `X-Source: zoowork` | **ZooWork bridge**: when the agent emits a custom tool call, POST its input here and return the JSON as the tool result |
| `POST /api/events` | `{source, kind, summary, payload?}` | **Any sponsor**: push ZooWork session events, BAND room messages, etc. into the dashboard log |
| `GET /api/state` | — | Dashboard (polls every 2s) |
| `GET /api/stores/<owner>` | — | Debug: raw tables of one store |
| `POST /api/demo/run` | — | Dashboard "Run weekly schedule" (also the ZooWork-schedule fallback) |
| `POST /api/demo/reset` | — | Reseed |
| `POST /api/phone/reply` | `{body, customer_id?}` | Fake phone, or the **Twilio inbound webhook** (forward T's reply here) |
| `POST /api/band/accept` | `{agent_handle, person_said, offer_id?}` | **BAND bridge**: T said yes to their own agent; relay T's words. Refused without `person_said` or if the handle isn't the offer customer's agent. `offer_id` defaults to their latest sent offer |
| `POST /api/approvals/<id>` | `{decision: "approve" \| "reject"}` | Dashboard approve buttons (mirror ZooWork `resolveApproval` here) |

### Tools (`POST /api/tools/<name>`)

`get_top_customers {limit}` · `score_agent_trust {agent_handle, requests_per_min, discount_first}` · `ask_customer_occasions {customer_id}` · `match_catalog {customer_id, budget, hints}` · `request_vouch {recipient_handle, skus}` · `check_competitor_price {sku}` · `make_offer {customer_id, sku, occasion_ref, discount_pct, trust_score, vouch_result, size, budget}` · `send_message {customer_id, body, offer_id}` · `place_order {offer_id}` · `screen_return_risk {order_id?}` · `handle_storefront_request {agent_handle, ask, requests_per_min}` · `forecast_from_vouches {}` · `draft_purchase_order {sku, size, quantity, reason}`

**No sales to unverified agents.** `verify_buyer` re-checks the buyer's agent (identity + provenance + behavior; history is a bonus) inside `make_offer`, `place_order` and `resolve_approval`. A failure marks the offer `blocked`, creates no order, and logs a `no_sale` event. An optional `trust_score` from the caller (e.g. a KYA provider's score) must also be ≥ 0.75, but it never replaces the backend's own check.

**Payments (mocked Visa).** `place_order` (reached from a texted YES, `/api/band/accept`, or the agent) re-verifies the buyer, then `adapters.visa_authorize` places a hold scoped to the merchant, offer and amount, stored in `merchant.payments` with `accepted_via`. `resolve_approval` captures it on approve and voids it on reject or a failed re-check. No card data anywhere.

`make_offer` is the Outcome rubric: verified buyer, in stock, ≤ budget×1.1, final price ≥ cost×1.3 (auto-revises the discount and logs "below margin floor → revised").

### Sponsor bridges (`adapters.py`) — what each teammate implements

Run a tiny HTTP server in your sponsor folder that answers these, then set the env var and `DEMO_MODE=0`:

| Env var | Endpoint | Request | Must return |
| --- | --- | --- | --- |
| `BAND_BRIDGE_URL` | `POST /share_occasions` | `{customer_handle}` | `[{friend_handle, occasion, occasion_date, budget?, hints?, sharing_level}]` (only fields the sharing level allows) |
| `BAND_BRIDGE_URL` | `POST /vouch_for` | `{recipient_handle, sku}` | `{sku, wants, owns, confidence, size, contribute_signal}` or `null` if no agent |
| `TAVILY_BRIDGE_URL` | `POST /competitor_prices` | `{sku, query, our_price}` | `{competitors: [{retailer, price, url}]}` |
| `SMS_BRIDGE_URL` | `POST /send` | `{to, body}` | `{status}` |

`catalog.competitor_query` maps the 3 demo SKUs to the products in `Tavily/experiments/` (Salomon ADV Skin 5, Hydro Flask 32 oz, Black Diamond Spot 400).

## Rules

- **Ownership:** merchant code reads only `merchant.db`; T's/Sarah's agents read only their own file. `vouch_signals` holds aggregate counts per SKU/size/window — no person ids.
- `/api/stores/sarah_agent` exposes Sarah's profile for debugging only. Don't show it on stage.
- `Data/db/` is generated and gitignored. Change mock data in `seed.py`, then reseed.

## Saved samples (use these if we run out of tokens)

`python3 Data/capture_samples.py` runs every tool and bridge once on fresh mock data, saves the real inputs and outputs, then reseeds clean. Everything is in `Data/samples/`:

| Folder | Contents |
| --- | --- |
| `samples/tools/<name>.json` | `{tool, endpoint, input, output}` for all 13 merchant tools |
| `samples/bridges/*.json` | What BAND / Tavily / SMS bridges receive and must return |
| `samples/api/*.json` | `/api/state` snapshot, ZooWork `custom_tools` declarations, phone reply, approvals, events |
| `samples/stores/<owner>.json` | Full dump of each owner's store after one complete run |

The per-sponsor input/output contracts are at the end of `Zooworks/Rules.md`, `Band/Rules.md`, `Tavily/Rules.md` and `Dashboard/Rules.md`. `GET /api/tools` now returns ZooWork-ready `custom_tools` declarations (name, description, `input_schema`), defined in `tools.INPUT_SCHEMAS`.

## Merchant ping (live text to the merchant's phone)

Both approval gates (`place_order`, `draft_purchase_order`) call `adapters.ping_merchant()`. It sends Gmail over SMTP to the carrier's email-to-SMS gateway, so the merchant's phone gets a real text with a one-tap approve link. No Twilio, and no Composio (ruled out, see `Zooworks/Rules.md`).

| Env var (repo-root `.env` is auto-loaded) | Default | Purpose |
| --- | --- | --- |
| `GMAIL_APP_PASSWORD` | — (required for live) | Gmail app password for `GMAIL_FROM` |
| `GMAIL_FROM` | `tveshashah13@gmail.com` | Sender |
| `MERCHANT_SMS_TO` | `6477095511@msg.telus.com` | Merchant's phone through the Telus gateway |
| `PUBLIC_URL` | — | ngrok/tunnel URL. Without it, the text says "Approve on the dashboard" |
| `APPROVE_LINK_SECRET` | random per server start | Signs approve links; set it so links survive a restart |

- Live only when Gmail is switched on (`DEMO_MODE=0` or `LIVE=gmail`) and `GMAIL_APP_PASSWORD` is set. `/api/state` → `modes.merchant_ping` shows which mode is active.
- Sends run in a background thread, so tools never wait on SMTP. The outcome is logged to the event feed as source `ping` (`live` / `mock` / `fallback`).
- `GET /a/<approval_id>/<approve|reject>/<token>` resolves the approval (same as `POST /api/approvals/<id>`) and returns a small mobile page. A bad token returns "link expired or invalid"; a second tap returns "no pending approval".
- T's offer still goes to the fake phone panel (`send_sms`). Sample: `samples/bridges/merchant_ping.json`.
