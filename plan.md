# Shopisphere — Hackathon Build Plan

Oct 3, 2026 · @T

## What we're building

**Shopisphere is a verified shopping network, built from the merchant's side.** The merchant's agent deals only with shopper agents that prove a real person is behind them, asks the recipient's agent before a gift is sold, and turns every answer into fewer returns and smarter restocking. Agents narrow the options; people make every choice.

**The brief we're answering:** ZooWork's opening slides framed the day as "The Shopper Now Has an Agent. The Merchant Needs One Too." The bar: "an agent a merchant would pay for, and could run on Monday." The instruction: "Pick a real merchant. Pick one line of their P&L. Move it."

**Our merchant and P&L lines:** a gift-heavy boutique (demo: an outdoor gear shop). The headline line is **gift returns** ("lose less"): vouched gift orders come back less, and bots posing as buyers get no discounts. The same vouch signal also drives **replenishment** ("run leaner"). The proactive gift offer ("sell more") is the mechanism that collects the vouches, not the pitch.

**Stats (quoted exactly, from the linked sources):**

| Stat | Exact wording | Source | Caveat |
| --- | --- | --- | --- |
| Holiday share of returns | "Nearly a quarter of all returns occur around Christmastime" | [Optoro](https://www.optoro.com/returns-news/your-holiday-gift-returns-cost-retailers-billions/) | Optoro's own figure; article is undated |
| Gift value vs. price | "the average yield of 83.9% was well short of 100%" | [American Economic Association, Dec 28, 2015](https://www.aeaweb.org/research/did-holiday-gift-giving-just-create-loss), on Waldfogel (1993) | Survey of Yale undergrads. Later studies found yields of 111% and 135%, so it's contested |
| AI making the purchase | "consumer willingness to let AI make purchase decisions topped out at 11% across lower-stakes categories" | Gartner press release, May 27, 2026 (link in Sources) | Surveys of 846 US consumers (Nov–Dec 2025) and 322 (Jan 2026). Same release: "31% were willing to allow AI to narrow choices for household supplies purchases" |

The same Optoro piece reports, per CNBC, that Optoro's CEO said a quarter to half of returned value can't be recouped. Not used: the "$180 billion" and per-category figures from the AI Overview, which trace to a YouTube video.

**How it works (one run):**

1. **Find the moment.** The merchant agent (ZooWork, weekly schedule) picks top customers from its own order history: "T, 6 orders, loves our trail line."
2. **Ask with consent (BAND consent room).** The merchant agent asks T's agent, "Any upcoming occasions we can help with?" T's agent shares only what T allows: "a friend, birthday Oct 24, about $60."
3. **Match from T's side.** The merchant agent pulls candidates from its own catalog that fit T's taste and the budget.
4. **Vouch from Sarah's side (BAND vouch room).** The merchant agent asks Sarah's agent about the top 3: "Wants the vest, already owns the bottle (0.9)." Her profile never leaves her agent.
5. **Offer.** The merchant texts T: "Sarah's birthday is in 3 weeks. She'd love the trail vest; her agent confirmed it. 15% off as a loyal customer. Reply YES." An approval gate fires, then the order is placed.
6. **Lose less.** A bot posing as a buyer agent asks for the same discount. It fails the trust check and is declined.

**What every vouch feeds:**

| Bucket | What the vouch signal does | Demo beat |
| --- | --- | --- |
| Lose less (headline) | Returns screener: vouched gift orders are tagged low return risk; unvouched gift orders and bot discount requests are flagged | "Vouched order: return risk low. Unknown shopper: declined." |
| Run leaner | Replenishment copilot: anonymous vouches are counted per SKU and size, compared with stock, and turned into a draft purchase order behind approval. "Already owns it" answers warn against over-ordering | "9 vouched wants for the trail vest in M, 3 in stock: draft PO for 8. Approve?" |
| Sell more (mechanism) | The gift offer to T is how vouches get collected | The text to T |

**Humans choose, agents narrow:** shopper agents and the merchant agent narrow the options, but T approves every purchase and the merchant approves every purchase order. That matches Gartner's finding that willingness to let AI make purchase decisions "topped out at 11%" (see stats table).

**Signal privacy:** replenishment uses only anonymous, aggregated counts ("9 recipients want size M"), never an individual's answer. Sarah's agent opts in to contributing anonymous signals.

**Data ownership rule:** every agent holds only its owner's data. The merchant knows only its own customers, orders and catalog. T's agent shares what T knows and allows, per friend. Sarah's preferences come only from Sarah's agent, as yes/no answers.

**Day-one fallback:** if the recipient has no agent, the merchant still sends an unvouched suggestion at standard price. The vouch is an upgrade, not a requirement, which answers the cold-start question.

**Why verified agents alone aren't the product:** "Know Your Agent" (KYA) is crowded. Mastercard Agent Pay (with Skyfire), Prove Verified Agent, Trulioo with Worldpay, and HUMAN with Riskified verify *who is buying*. Shopisphere consumes those identity signals and adds what nobody sells: *whether the gift will be wanted*.

**Naming check:** a wishlist site already uses the name at [shopisphere.com](https://shopisphere.com/). It's a different product, but have a one-line answer ready. "Verified shopping network" works as a tagline; avoid "Agentverse," which Fetch.ai already uses. "Vouch" stays as the name of the mechanic (the recipient's agent vouches for a gift).

**The parts:**

- **Merchant agent (ZooWork), the product:** weekly schedule, gifting Skill, catalog matching, trust scoring, offers, approval gate, returns screener and replenishment copilot.
- **Customer agents (BAND):** T's agent (occasions behind sharing levels), Sarah's agent (vouches), and an unverified shopper (the bot).
- **Backend:** data kept separate per owner (merchant, T, Sarah), the trust-check service, messaging, and the dashboard.

**Track fit:** merchant operations and AI agents/workflow automation, with storefront as secondary.

**Prizes (from the opening slides):**

| Prize | Amount | Our angle |
| --- | --- | --- |
| Grand prize | $1,000 / $500 / $250 | Merchant-first brief, one P&L line, live demo |
| Best Use of ZooWork | $800 | The merchant agent runs on ZooWork end to end |
| Best Use of Band | $500 | Consent and vouch rooms across accounts |
| Best Use of Entire | Not stated | Host the repo on Entire with one Trail |
| People's Choice | Not stated | Gallery-walk exhibit with a phone demo |

**Schedule (from the slides):** submission 5:00 PM, gallery walk 5:30 PM, top 5–8 projects on the main stage 6:15 PM, awards 7:00 PM.

## Decisions to debate

Settle these in the first 30 minutes. The recommended default is the fastest path to a live demo.

| # | Decision | Options | Recommended default | Why |
| --- | --- | --- | --- | --- |
| 1 | Messaging channel | ZooWork-native iMessage/WhatsApp · Twilio SMS · Composio Gmail · Gmail → carrier SMS gateway · fake phone panel | **Settled:** Gmail → carrier email-to-SMS gateway texts the *merchant* at each approval gate, with a one-tap approve link. T's offer stays on the fake phone panel | Native channels are unavailable on Platform API keys (live docs). Composio has no connected integrations and can't start OAuth (live test, `Zooworks/Rules.md`). Twilio needs carrier registration that takes days. The Gmail gateway works with an app password. |
| 2 | Where each agent lives | Everything on ZooWork · merchant on ZooWork, customer agents on BAND | Merchant agent on ZooWork; T's agent, Sarah's agent and the bot on BAND | The merchant agent is the product ZooWork judges want. Agents belonging to other people is what BAND is for. |
| 3 | Data storage | One shared DB · data separated per owner | Separate tables per owner (merchant, T's agent, Sarah's agent) | Makes "each agent holds only its owner's data" real, and visible on the dashboard. |
| 4 | Catalog source | Seeded merchant catalog · ZooData · Tavily | Seeded catalog of about 20 products; ZooData if the booth confirms it | The merchant's own catalog, not the open web. Slides say ZooData is "out of the box." |
| 5 | Tavily's role | Competitor price check · gift-trend research · skip | Competitor price check that sets the offer, labeled in the log | Gives Tavily a real merchant job: "we're $8 above a competitor, so offer 15%." |
| 6 | Trigger | ZooWork weekly schedule · backend cron · button | ZooWork schedule, fired manually on stage | Shows native scheduling; the manual trigger runs it on demand. |
| 7 | Agent verification | Real KYA provider · simulated layers | Four simulated layers: identity, provenance, history, behavior | Name Visa's Trusted Agent Protocol and Mastercard Agent Pay as the production source. |
| 8 | Sharing levels | All or nothing · per-friend levels | Per friend: occasion only / + budget / + hints; default "occasion + budget" | T decides what the merchant sees, per friend. |
| 9 | Recommendation | One-sided · two-sided match | Candidates from T's taste and the catalog; ranking from Sarah's vouch | "From the store you love, a gift she'll want." |
| 10 | Purchase | Real checkout · mock order behind approval | Mock order + ZooWork approval gate | No payment risk; the approval step is the point. |
| 11 | Scope cuts | Keep shop-for-self and price watch · cut both | Cut both | They pull focus from the merchant brief. |
| 12 | Moss | Use · skip | Skip; documented as an extension | No Moss prize, and demo data fits in a prompt. |
| 13 | Repo host | GitHub · Entire | Entire, with one Trail for the build | Near-zero effort entry for Best Use of Entire. |
| 14 | Stack | TypeScript · Python | Whichever the team is fastest in | ZooWork and BAND both have Python and TypeScript SDKs. ZooWork's skill needs Node 22.20+. |
| 15 | Headline P&L line | Gift revenue · gift returns · replenishment | Gift returns (lose less); replenishment as "the same signal runs your stock" | The slides say pick one line. Returns is the vouch's most direct effect and matches the slide's "returns screener" example. |
| 16 | Replenishment data | Live vouches only · seeded history | \~30 seeded past vouches plus the live one; say so if asked | One demo run can't produce a forecast. Frame vouches as a leading indicator alongside sales history. |
| 17 | TikTok Shop trends | ZooData call · skip | Do a 2-minute check in the ZooData console; add one call only if real TikTok Shop data comes back | ZooData's homepage claims TikTok Shop products, but its documented skills are Amazon-only. |
| 18 | Creator and social signals | Merchant reads people's posts · the person's own agent uses them · skip | Pitch only: Sarah's agent could use her own social signals when vouching | The merchant reading individuals' posts breaks the data-ownership rule. Product-level trends are fine. |

## Architecture

The merchant agent on ZooWork is the product. Customer agents meet it in BAND rooms, and the backend keeps each owner's data separate and runs the trust check.

&#91;embedded content: system architecture · backend, ZooWork, Tavily, phone\]

Messages to T go out through the backend's `send_message`. No agent holds another owner's data or any credentials.

**Data model (seed: 1 merchant with \~20 products and 6 customers, T, Sarah, 1 unverified shopper):**

| Table | Owner | Key fields |
| --- | --- | --- |
| merchant\_customers | Merchant | customer\_id, agent\_handle, order count, favorite lines |
| catalog | Merchant | sku, name, price, tags, stock |
| orders | Merchant | customer\_id, sku, price, gift flag, returned, return reason |
| offers | Merchant | customer\_id, occasion ref, sku, discount, vouch result, trust score, status |
| t\_occasions | T's agent | friend handle, occasion date, budget, hints, sharing level |
| sarah\_profile | Sarah's agent | likes, owns, sizes (never leaves her agent) |
| agent\_passports | Backend | agent handle, owner phone verified, signed token |
| trust\_events | Backend | agent handle, request count per minute, decision, reasons |
| vouch\_signals | Merchant (anonymous, aggregated) | sku, size, wants count, owns count, time window (no person ids) |
| inventory | Merchant | sku, size, on hand, supplier, lead time days |
| purchase\_orders | Merchant | sku, size, quantity, reason, status (draft / approved) |

**Merchant agent tools (ZooWork custom tools):** `get_top_customers`, `ask_customer_occasions` (posts in the BAND consent room), `match_catalog`, `request_vouch` (BAND vouch room), `check_competitor_price` (Tavily), `score_agent_trust`, `make_offer`, `send_message`, `place_order` (behind the approval gate).

**Customer agent tools (BAND agents in our process):** T's agent has `share_occasions`, which returns only fields allowed by each friend's sharing level. Sarah's agent has `vouch_for(sku)`, which returns wants / owns / confidence and nothing else.

**Lose-less and run-leaner tools (also ZooWork custom tools):** `screen_return_risk` tags each gift order as vouched (low risk) or unvouched, and flags bot patterns. `forecast_from_vouches` counts anonymous vouches per SKU and size against stock. `draft_purchase_order` proposes quantities behind the approval gate. Optional: `tiktok_shop_trends` (ZooData), only if the console check shows real data.

**Merchant flow:**

1. The weekly ZooWork schedule fires; `get_top_customers` returns T.
2. `score_agent_trust` checks T's agent (passes all four layers).
3. `ask_customer_occasions` → T's agent replies within its sharing level.
4. `match_catalog` picks 3 candidates from T's favorite lines within budget.
5. `request_vouch` → Sarah's agent ranks them; owned items drop out.
6. `check_competitor_price` sets the discount; the Outcome rubric checks the offer.
7. `send_message` texts T; on YES, `place_order` hits the approval gate and the order is placed.
8. In parallel, the unverified shopper asks for a discount and `score_agent_trust` declines it.

**After each run:**

- The vouch answer is stored as an anonymous count in `vouch_signals`.
- `forecast_from_vouches` flags "trail vest M: 9 wants, 3 on hand," and `draft_purchase_order` proposes 8 units for the merchant to approve.
- `screen_return_risk` tags T's order as vouched, low return risk.

## The BAND rooms: consent, vouch and trust

The merchant agent never reaches into anyone's data. It asks other people's agents in BAND rooms, and each agent answers only within its owner's rules.

| Room | Participants | What happens | Who sees what |
| --- | --- | --- | --- |
| Consent room | Merchant agent, T's agent | Merchant asks about upcoming occasions; T's agent answers within each friend's sharing level | Merchant sees only the allowed fields |
| Vouch room | Merchant agent, Sarah's agent | Merchant asks about 3 candidates; Sarah's agent answers wants / owns / confidence | Sarah's profile never leaves her agent |
| Storefront room | Merchant agent, Unverified Shopper | The bot asks for a discount; the trust check fails | Declined, with reasons on the dashboard |

**Sharing levels (set by T, per friend):**

| Level | Merchant sees | Example |
| --- | --- | --- |
| Occasion only | "A friend has a birthday on Oct 24" | Minimal; merchant suggests from T's favorites |
| Occasion + budget (default) | "A friend, birthday Oct 24, about $60" | Enough for a priced offer |
| Occasion + budget + hints | "… into trail running" | Better candidates before the vouch |

**Trust check: is this a real buyer's agent?** In production, identity comes from standards like Visa's Trusted Agent Protocol and Mastercard Agent Pay. We build what the merchant does with the signal, using four simulated layers:

| Layer | Question | Demo implementation | Unverified Shopper |
| --- | --- | --- | --- |
| Identity | Is a real person behind it? | Owner verified by phone OTP; agent carries a signed passport token from our backend | No token ❌ |
| Provenance | Is it who it says it is? | Registered BAND agent with a stable handle and a contact the merchant approved | Unknown handle, no contact ❌ |
| History | Has it bought here before? | Prior orders linked to the agent in the merchant's records | None ❌ |
| Behavior | Does it act like a buyer? | Rules on request rate, discount-first asks, and mismatched claims | 40 discount asks a minute ❌ |

**Two-sided match:** candidates come from T's side (what T loves at this store, within budget). Ranking comes from Sarah's side (her agent's vouch). The offer reads: "From the store you love, a gift she'll want." With no recipient agent, the offer goes out unvouched at standard price.

**Anonymous demand signals:** with Sarah's opt-in, her agent's answer also counts toward an anonymous tally per SKU and size. The merchant sees "9 recipients want the vest in M," never who.

**Next (pitch only):** a person's own agent could use their social signals, such as creators they follow, when it vouches. The merchant never reads anyone's posts.

**One run, end to end:**

`Schedule fires → trust check passes for T's agent → consent room: friend, Oct 24, ~$60 → 3 candidates from T's favorites → vouch room: wants the vest, owns the bottle (0.9) → Tavily price check → 15% off → text to T → YES → approval → order. Meanwhile: Unverified Shopper asks for 15% off → trust check fails → declined.`

**Why it passes BAND's "delete test":** remove the rooms and there is no consent boundary, no private vouch, and no way to decline the bot. It hits three of BAND's signals: a dependent handoff (the offer changes because of the vouch), a boundary BAND enforces (cross-account contacts plus mention-scoped visibility), and a verdict that can be blocked (the bot is declined).

**Build notes:**

- BAND agents run in our own process via `band-sdk` (Python) or `@band-ai/sdk` (TypeScript), with their own model key. Free tier: up to 10 agents, one live connection each. Slides include a BAND Pro code: BANDSEP26.
- The merchant agent lives on ZooWork. A small BAND bridge agent relays its questions into rooms, called through the `ask_customer_occasions` and `request_vouch` custom tools.
- Avoid agent names like "Bot", "Agent" or "Assistant"; BAND says routing degrades. Use "Trailhead Merchant", "T's Gift Planner", "Sarah's Gift Vouch" and "Unverified Shopper".
- Keep execution events on so the BAND console shows every message and tool call. Put it on screen beside the dashboard at the exhibit.
- **Fallback:** if BAND fights you past 3:45 PM, run the same exchanges through ZooWork custom tools and show them on the dashboard.

## Sponsor usage

ZooWork and BAND carry the product; Tavily and Entire each have one clear job.

| Sponsor | Role | Prize | Status |
| --- | --- | --- | --- |
| ZooWork | The merchant agent: weekly schedule, gifting Skill, Outcome rubric, custom tools, approval gate, delivery to T | Best Use of ZooWork, $800 | Core. $200 credits via code PFDQ5YJ3 (slide 19) |
| BAND | Consent, vouch and storefront rooms between agents owned by different people | Best Use of Band, $500 | Core. Pro code BANDSEP26 |
| Tavily | `check_competitor_price`: the price comparison that sets the discount | None listed | Supporting |
| Entire | Repo host, with one Trail for the build | Best Use of Entire | Cheap add |
| ZooData (ZooWork) | Catalog, competitor prices and, if real, TikTok Shop trends; slides call it "out of the box" | Counts toward ZooWork | Try first; Tavily is the fallback |
| Novita AI | Sponsors the open-source models on ZooWork; could also power the BAND agents | None listed | Optional |
| Moss | Retrieval at scale | None listed | Extension only (see Moss section) |

**ZooWork gaps to design around:**

- Managed channels (iMessage, WhatsApp, Slack) are unavailable on Platform API keys, per the live docs. The backend sends texts: the Gmail → SMS gateway pings the merchant (decision #1).
- Webhooks are outbound only. Replies from T reach the backend first and are forwarded into a session.
- It's a Developer Preview. Run the quickstart (`npx skills add SerendipityOneInc/zoowork-sdk-skills`) before building on it.
- A created agent starts stopped: call `startAgent` + `waitUntilRunning` first, or sessions return 409.
- Webhook receivers need public HTTPS on port 443 (ngrok, Cloudflare Tunnel, or an early deploy).
- Use a far-off cron and fire the schedule manually, so it doesn't keep burning credits.

## Sponsor upgrades

These make ZooWork's own features carry the visible workflow. The Skill and the Outcome rubric are config, not code, so do them first.

**ZooWork:**

- [ ] **Package the merchant's gifting playbook as a ZooWork Skill:** who counts as a top customer, how to ask for occasions, matching rules, discount limits and margin floor. Stage line: "A new store installs the playbook and runs it on Monday."
- [ ] **Outcome rubric on the scheduled run:** "Every offer has a passing trust check, an in-stock item within budget, a price above the margin floor, and a one-line reason." The dashboard shows "offer rejected: below margin floor → revised."
- [ ] **Visible approval gate:** show `approval.requested` at the moment of purchase. It ties to ZooWork's "asks before it commits."
- [ ] **ZooWork event log as the reasoning panel:** stream session events straight into the dashboard.
- [ ] **ZooData for catalog, competitor prices and TikTok Shop trends**, if it works out of the box as the slides say.
- [x] ~~Deliver through a ZooWork-native chat channel~~: not available on Platform API keys. Replaced by the Gmail merchant ping (`Data/Rules.md`).

**BAND:**

- [ ] Show the BAND console beside the dashboard at the exhibit, with execution events on.
- [ ] Write the four-line collaboration summary BAND asks for: the crew, who talks to whom, one flow end to end, and what breaks without the room.

**Tavily and Entire:**

- [ ] Label each Tavily call in the log, for example "Tavily: trail vest at 2 competitors, lowest $64."
- [ ] Create the Entire repo and one Trail at the start, so the build history is captured automatically.

## Contingencies

Every live dependency gets a fallback that keeps the demo intact. Keep a `DEMO_MODE` flag that swaps in each fallback.

| If this fails | Symptom | Fallback |
| --- | --- | --- |
| ZooWork quickstart or API | 409 / 5xx, agent won't start, preview API changed | Ask the FDE table first. Then run the merchant loop with a direct model call and keep ZooWork for the schedule. |
| ZooWork schedule | Trigger doesn't dispatch | Dashboard button calls `createSession` with the same message |
| ZooWork webhooks | No `run.finished` arriving | Stream session events from the backend instead |
| Custom tool round-trip | Run stuck in `awaiting_approval` | Pre-fetch candidates and prices in the backend and pass them in the session message |
| BAND | Agents won't connect or rooms misroute | Run the consent and vouch exchanges as ZooWork custom tools; show them on the dashboard |
| Messaging | Gmail ping fails or the text lags | Logged as `ping fallback`; approve on the dashboard. T's side is always the fake phone panel |
| ZooData | Not available on hackathon keys | Seeded catalog plus Tavily for competitor prices |
| Tavily | Junk or missing competitor prices | Cached JSON of competitor prices for the 3 demo products |
| Venue Wi-Fi | Slow or down | Phone hotspot; recorded backup video by 4:45 PM |
| Running out of time | Behind at 3:30 PM | Use the cut list in the timeline section |

## Timeline and cut list

The merchant loop on ZooWork must work end to end by 2:00 PM. The BAND rooms land by 3:45 PM, and everything after that is the exhibit.

1. **11:30–12:15: Prove the plumbing.** ZooWork key and $200 credits, quickstart reply. Two BAND agents talking. Ask the FDE table about iMessage and ZooData. Create the Entire repo and Trail.
2. **12:15–1:00: Backend and seed data.** Per-owner tables, \~20 products, 6 customers, T's occasions with sharing levels, Sarah's profile, the passport tokens.
3. **1:00–2:00: Merchant agent on ZooWork.** Schedule, gifting Skill, custom tools (`get_top_customers`, `match_catalog`, `check_competitor_price`, `make_offer`, `send_message`), Outcome rubric.
4. **2:00–3:45: BAND rooms and trust.** T's agent and Sarah's agent with their tools, the bridge from ZooWork custom tools into rooms, `score_agent_trust`, and the Unverified Shopper. Then the returns screener, forecast and purchase-order tools, with \~30 seeded past vouches.
5. **3:45–4:30: Dashboard.** Merchant view: top customers, offers pipeline, trust panel (four layers per agent), ZooWork event log, BAND console, phone mirror, returns screener and replenishment panel.
6. **4:30–5:00: Ship.** Rehearse twice, record the backup video, write BAND's four-line collaboration summary, submit before 5:00 PM.
7. **5:00–5:30: Exhibit setup** for the gallery walk.

**Cut in this order if behind:**

- [ ] TikTok Shop trends (cut first; build only if the ZooData console check shows real data)

* [ ] Sharing levels beyond the default (keep "occasion + budget" only)
* [ ] Tavily competitor price check (fixed 15% loyal-customer discount)
* [ ] Outcome rubric revision loop (keep the rubric, skip showing a revision)
* [ ] Live BAND (use the ZooWork-only fallback)
* [ ] Real messaging (fake phone panel)

## Demo script and pitch

The demo runs about 2.5 minutes, with the merchant dashboard, the BAND console and a phone side by side. The same screen doubles as the gallery-walk exhibit.

1. **Hook (20s):** "Last month, Meta launched Muse, a shopping agent, and Amazon blocked it. Shoppers now arrive as agents, and merchants can't tell a real customer's agent from a bot. Shopisphere is a verified shopping network, seen from the merchant's side."
2. **The merchant (10s):** Trailhead, an outdoor boutique. Its P&L line: gift returns.
3. **Find the moment (20s):** fire the weekly ZooWork schedule. Trust check passes for T's agent. Consent room: "A friend, birthday Oct 24, about $60."
4. **Vouch (25s):** 3 candidates from T's favorites. Sarah's agent: "wants the vest, already owns the bottle (0.9)." Her profile never leaves her agent.
5. **Humans choose (15s):** the phone gets the vest with a photo. T replies YES; the approval gate fires and the order is tagged "vouched, return risk low."
6. **Lose less (15s):** the Unknown Shopper asks for the same 15%. All four trust layers fail; declined.
7. **Run leaner (20s):** the replenishment panel: "Trail vest M: 9 vouched wants, 3 on hand. Draft PO for 8. Approve?" The merchant approves.
8. **Close (10s):** "Fewer gift returns, no discounts for bots, and stock that follows real demand. Agents narrow; people choose. A merchant could run this on Monday."

**Lines for judges:**

- *Which merchant pays for this?* Any gift-heavy boutique. It cuts gift returns and bot discount abuse, and the same signal improves restocking.
- *Isn't this creepy?* No. The merchant knows only its own customers. T's agent shares within T's sharing level, Sarah's agent answers yes/no, and restocking uses only anonymous counts.
- *What if the friend has no agent?* The offer still goes out, unvouched, at standard price. The vouch is an upgrade.
- *How do you know it's a real agent?* Four layers: identity, provenance, history, behavior. In production, identity comes from Visa's and Mastercard's agent protocols.
- *Aren't you replacing the shopper?* No. Gartner found willingness to let AI make purchase decisions "topped out at 11%." Agents narrow; people approve every purchase.
- *Is one store's vouch data enough to forecast?* It's a leading indicator alongside sales history, and it grows with the network.
- *Isn't this just Know Your Agent?* KYA verifies who is buying. Shopisphere also verifies that the gift will be wanted, and uses that to cut returns and guide stock.
- *Why ZooWork? Why BAND?* ZooWork runs the merchant's agent end to end. BAND hosts the conversations between agents owned by different people; without the rooms, there's no consent and no vouch.

## Extension: Moss for retrieval at scale

Moss is out of the demo build and becomes the retrieval layer once profiles, history and catalogs outgrow the prompt. At demo scale (4 people, 1 merchant), a DB lookup is enough.

**When it becomes worth it:** hundreds of people in a network, years of gift and return history, or merchant catalogs with thousands of SKUs that agents must match against taste.

**Where it plugs in:**

| Use | Indexed in Moss | Called from |
| --- | --- | --- |
| Taste matching | Profile likes, dislikes and free-text notes as embeddings | `share_occasions` and `vouch_for` answer from the top matching traits instead of loading a whole profile |
| No-repeat check | Gift history and owned items | Sarah's agent: "does she own anything like this?" by similarity, not exact name |
| Return-risk signal | Return reasons ("too small", "wrong color") | Merchant scoring: flags items similar to past returns |
| Catalog search | Merchant product catalogs | `match_catalog` queries Moss over the merchant's catalog for large stores |

**Why Moss over a vector DB:** it advertises sub-10ms semantic retrieval for agents without the infrastructure of a traditional vector database. That matters when an agent runs many retrieval calls per job.

**How to add it later:** keep every retrieval behind the existing custom tools. Swapping a DB query for a Moss query then needs no change to agent prompts or ZooWork config.

**Pitch line:** "Today the profile fits in a prompt. At scale, Moss is the memory layer, with sub-10ms retrieval across every profile, gift and return."

## Booth questions and sources

**ZooWork booth:**

- [x] ~~iMessage/WhatsApp delivery~~: answered by the docs (unavailable on Platform API keys)
- [ ] Is ZooData available on hackathon keys for catalog, competitor prices and TikTok Shop data (products, sales, creators)? Which fields?
- [ ] Are memory tools enabled on hackathon keys?
- [ ] Any limit on agents per key or schedule frequency?

**BAND booth:**

- [ ] Best pattern for a non-BAND agent (our ZooWork merchant agent) to post into a room: bridge agent or direct API?
- [ ] Can contacts across two accounts be set up quickly for the demo?

**Tavily booth:**

- [ ] Free credits, and how reliable is Extract on retail product pages?

**Sources:**

- [ZooWork Docs: Schedules](https://zoowork.ai/docs/en/build/schedules)
- [ZooWork Docs: Webhooks](https://zoowork.ai/docs/en/build/webhooks)
- [ZooWork Docs: Channels](https://zoowork.ai/docs/en/build/channels)
- [ZooWork Docs: An agent per user](https://zoowork.ai/docs/en/build/per-user-agents)
- [ZooWork Docs: Tools](https://zoowork.ai/docs/en/build/tools)
- [ZooWork Docs: Current API boundaries](https://zoowork.ai/docs/en/reference/not-supported)
- [ZooWork TypeScript SDK](https://github.com/SerendipityOneInc/zoowork-sdk-typescript)
- [ZooWork homepage](https://zoowork.ai)

**Added sources (vouch reframe):**

- [BAND Hacker Guide](https://www.band.ai/hacker-guide)
- [Optoro: Your holiday gift returns cost retailers billions](https://www.optoro.com/returns-news/your-holiday-gift-returns-cost-retailers-billions/)
- [AEA: Did holiday gift giving just create a multi-billion-dollar loss for the economy?](https://www.aeaweb.org/research/did-holiday-gift-giving-just-create-loss)
- [Mastercard Agent Pay trust services (FintechSpecs)](https://fintechspecs.com/blog/mastercard-agent-pay-trust-intelligence-skyfire-kya-2026/)
- [CB Insights: agentic commerce market map](https://cbinsights.com/research/report/agentic-commerce-market-map/)
- [Vouched: Know Your Agent](https://www.vouched.id/learn/blog/know-your-agent-kyc-service)

**Opening ceremony slides (Oct 3, 2026):** ZooWork brief, build and delivery slides (12–20), BAND idea slides (41–48), prizes (57–62), judging criteria (66), timeline (22).

**Added sources (Shopisphere pivot):**

- [Gartner: Consumers Want AI Shopping Help, But Not AI Purchase Decisions (May 27, 2026)](https://www.gartner.com/en/newsroom/press-releases/2026-05-27-gartner-survey-finds-consumers-want-ai-shopping-help-but-not-ai-purchase-decisions)
- [ZooData homepage](https://zoodata.ai)
- [ZooData Skills (GitHub)](https://github.com/SerendipityOneInc/ZooData-Skills)
- [shopisphere.com](https://shopisphere.com/)
