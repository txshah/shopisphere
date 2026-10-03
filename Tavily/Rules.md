# TAVILY

Findings from live experiments with the Tavily API (key `TAV` in the repo root `.env`), scoped to this folder and to Tavily's one job in `plan.md`: **`check_competitor_price`, the price comparison that sets the discount** (decision #5), with **cached JSON for the demo products** as its fallback (Contingencies table). All raw responses are saved in `experiments/`.

## Demo prices: fixed snapshot of real retailers (Oct 3, 2026)

Trailhead and its products are fictional, so each demo SKU is compared with the closest real product, at prices checked on the retailers' own pages. This is the default (`Data/mock/competitor_prices.json`); `LIVE=tavily` searches live instead.

| SKU (our price) | Comparable product | Retailers |
| --- | --- | --- |
| TR-VEST ($84) | Nathan QuickStart 2.0 4L vest | Fleet Feet $80.00 · ShopAbunda $89.99 → lowest $80, we're $4 above → **15% off, $71.40** |
| TR-BOTTLE ($42) | Hydro Flask 32 oz Wide Mouth | Hydro Flask $44.95 · Eastside Sports $44.95 → we're lowest → 10% |
| TR-LAMP ($55) | Black Diamond Spot 400 | Black Diamond $59.95 → we're lowest → 10% |

To keep the 15% moment, the vest moved from $68 to $84 and Sarah's budget from $60 to $70. Nathan prices swing with sales (brand site HyperNight variant $39.99 on clearance; Portland Running and League Outfitters pages returned 404), so we kept only regular-price listings we could open.

## TL;DR for the team

- **The key works.** Plan: free "Researcher" tier, **1,000 credits/month**. The `/usage` counter still read 0 after ~30 calls, so it lags. Don't rely on it to see live spend.
- **Use Search, `search_depth: "basic"`, `country: "united states"`, plus a resale/review exclude list.** About 2.5–5s per call, and it gives the right product at the right price most of the time.
- **Don't trust a regex "lowest price" over raw results.** Category, search and sale pages mix in other products. Skipping listing URLs fixed every bad low price I saw (details below).
- **Extract is unreliable on big retailers.** REI, Moosejaw, Backcountry and Patagonia.com all failed or returned a "Sit tight" bot wall, even with `extract_depth: "advanced"`. Smaller shops (evo, Buckman's) worked.
- **Research (`/research`) returns clean structured JSON** via `output_schema`, but took **43s**. Use it to pre-build the cache before the demo, never live on stage.
- **Use the cache on stage.** `competitor_prices_cache.json` is ready, and `DEMO_MODE=1` makes the tool read from it. Re-capture it once the real demo catalog exists (see "To do").
- A working, stdlib-only prototype is in `check_competitor_price.py`. It returns the log label the plan asks for, e.g. `Tavily: Black Diamond Spot 400 headlamp at 2 competitors, lowest $59.95`.

## What's in this folder

| File | What it is |
| --- | --- |
| `check_competitor_price.py` | Prototype tool. `python3 check_competitor_price.py "<product>" <our_price>`. Python stdlib only. Reads `TAV` from env or `../.env`. `DEMO_MODE=1` reads the cache instead. |
| `competitor_prices_cache.json` | Cached results for 4 real outdoor products, captured 2026-10-03 |
| `experiments/` | Raw JSON response from every call, numbered in the order run (01–10). All files are valid JSON |
| `experiments/INDEX.json` | For each saved file: endpoint, exact request body, latency and HTTP status |
| `price_observations.json` | Every competitor price seen across all experiments (20 rows), with a `verified` flag. **Reusable without spending credits** |

Output shape (ready to return from a ZooWork custom tool):

```json
{
  "product": "Black Diamond Spot 400 headlamp",
  "our_price": 64,
  "lowest_competitor": 59.95,
  "gap": 4.05,
  "competitors": [{"retailer": "blackdiamondequipment.com", "price": 59.95, "url": "..."}],
  "tavily_answer": "...",
  "label": "Tavily: Black Diamond Spot 400 headlamp at 2 competitors, lowest $59.95",
  "source": "tavily_live"
}
```

## Experiments and results

### 1. Search: depth comparison (same 3 products, run in parallel)

| Depth | Latency | Quality |
| --- | --- | --- |
| `ultra-fast` | ~1.6s | Poor. UK shops (GBP prices), wrong variant (ADV Skin **12**), a $99 price from a stray Shopify mirror |
| `fast` | ~1.7s | Poor. Same UK/variant drift |
| `basic` | 2.5–5s | **Good.** Brand site, REI and specialty shops, correct item, USD |
| `advanced` | ~9s | Good, but pulled in used gear (Patagonia Worn Wear) and costs 2 credits |

- `country` **only works with `basic`/`advanced`**. With `fast`/`ultra-fast` it returns 400: `"Country parameter is not supported for fast or ultra-fast search_depth."`
- `include_answer: true` gives a readable one-paragraph summary. It's good for the reasoning log, but it mixes sources and currencies (one answer quoted MXN from Amazon). Don't parse a number out of it.

### 2. Search: allowlist vs. exclude list

- **An allowlist (`include_domains` of ~14 big US retailers) made results worse.** It returned mostly category and search pages (`rei.com/b/...`, `amazon.com/s?k=...`), and **zero results** for the Black Diamond headlamp.
- **An exclude list works better.** Drop resale, social, price-tracker and review sites: `ebay, poshmark, mercari, wornwear.patagonia.com, reddit, youtube, pinterest, klarna, pricehistory.app, cleverhiker, treelinereview, outdoorgearlab, switchbacktravel, trailspace, engearment, corporategift`.

### 3. Parsing prices out of results (the main gotcha)

The first version took the min `$` amount per result and got these wrong lows:

| Product | Wrong "lowest" | Actually was |
| --- | --- | --- |
| BD Spot 400 headlamp | $34.00 at Karst Sports | Spot **350** closeout on the same listing page |
| BD Spot 400 headlamp | $34.95 at REI | **Wiz Kid kids' headlamp** on REI's category page |
| Hydro Flask 32 oz | $22.72 at hydroflask.com | A **tumbler** on the `/shop/sale` page |

Fixes in the prototype, after which all three came out right ($59.95 and $44.95, matching brand MSRP):

1. **Skip listing URLs**: `/c/`, `/b/`, `/s`, `/shop/`, `/collections/`, `/search`, `/sale`, `/deals`, and `?k=`/`?q=` query strings.
2. **Take the first plausible price on a product page**, not the minimum.
3. **Keep only amounts between 0.5× and 2× our price.** This drops "free shipping over $50" and "$35 minimum" amounts, which show up constantly.
4. **Ignore amounts preceded by** `over / orders / save / off / up to / spend / minimum / reward`.

Noise that remains after the fixes, which a human or the merchant agent's LLM should glance at:

- Blog and review posts still slip through (`wenatcheeoutdoors.org/2022/...`, `trailandkale.com/...-review`). They quote MSRP, not a live offer.
- Variants: Karst returned the Spot 400-**R** ($69.95) for a Spot 400 query.
- Promo/bulk sites (`pinnaclepromotions.com`, $268 for a vest) when the band is wide.

**Better option if time allows:** pass the top results' `content` to the merchant agent's model with "extract {retailer, price, is_exact_product, is_new}" and let it reject non-matches. Tavily's raw content is good enough for that. It's regex parsing that's fragile.

### 4. Extract (`/extract`) on product pages

| URL | basic | advanced |
| --- | --- | --- |
| rei.com product page | Timed out | "Failed to fetch url" |
| moosejaw.com | "Error fetching content" | "Error fetching content" |
| backcountry.com | "Failed to fetch url" | n/a |
| patagonia.com | Returned the bot wall ("Sit tight… Routing to checkout") as **success** | Same |
| buckmans.com | n/a | Works: `Price $132.30-$189.00` |
| evo.com | n/a | Works: `$84.99` / `$149.00`, **and stock: "Sold Out (0 remaining)"** |

- Advanced extract of 5 URLs took **~19s**.
- **A "successful" extract can still be a bot wall.** Check the content before trusting it.
- **Bonus:** where Extract works, it exposes **stock status**. Plan.md doesn't use this. A competitor being sold out is a reason *not* to discount.
- Answer to plan.md's Tavily booth question ("how reliable is Extract on retail product pages?"): **not reliable on the big chains. Plan around Search.**

### 5. Research (`/research`, `model: "mini"`, with `output_schema`)

- Async: `POST /research` returns `pending`. Poll `GET /research/{request_id}`. Done in **43s**.
- Returned exactly the schema I asked for: `{offers: [{retailer, price_usd, url, in_stock}]}`, 3 offers plus 5 sources.
- Quality was mixed. Half-Moon Outfitters $99.98 and Alabama Outdoors $132.30 matched what Search found. **REI $98.83 came from a category page**, so the same caveat applies.
- **Use:** run it ahead of time to build or refresh the cache for the demo SKUs. **Too slow for a live tool call.**

### 6. Credits

- `GET https://api.tavily.com/usage` works, but it showed `plan_usage: 0` after ~30 searches, 2 extract batches and 1 research task. Rough cost per Tavily's pricing: basic search = 1 credit, advanced = 2, extract = 1 (basic) or 2 (advanced) per 5 URLs, research = variable. Estimated **well under 100 of 1,000 used**. Credits aren't a constraint for the hackathon.

## Recommended integration (for whoever wires up ZooWork)

1. Register `check_competitor_price(product, our_price)` as a **ZooWork application-executed custom tool**, not MCP. The ZooWork Rules.md confirms MCP can't carry the API key.
2. Search on the **brand + model name**, not our boutique's SKU name. Tavily can only price real products, so every demo catalog item needs a real-world equivalent (e.g. our "trail vest" maps to "Salomon ADV Skin 5 running vest"). Add a `competitor_query` column to the `catalog` table (owner: Merchant).
3. Turn the gap into a discount in our code, not in Tavily. For example: `gap > 0` → match the lowest competitor, capped at 15% and above the margin floor. Log the `label` string for the dashboard.
4. On stage: `DEMO_MODE=1` reads `competitor_prices_cache.json`. Live calls are fast enough (~3s) to show once, but the results can change between rehearsal and the demo.

## Corrections and notes on plan.md

- **Plan's example "Tavily: trail vest at 2 competitors, lowest $64":** a generic "trail vest" can't be price-checked. The demo item needs a real brand and model (see Integration #2). Real ~$60 options seen today: **Black Diamond Spot 400 headlamp ($59.95)** and **Hydro Flask 32 oz Wide Mouth ($44.95)**. Real trail/running vests cost more: **Salomon ADV Skin 5 is $140–145**, and the **Patagonia Nano Puff Vest is $99.98–149**. If the story stays "Sarah wants the vest, ~$60 budget", either raise the budget or pick a cheaper real vest and re-run the tool on it.
- **Decision #4/#5 fallback holds.** ZooData is untested here, but Tavily alone covers competitor pricing well enough for the demo.
- **Cut list:** the Tavily price check is #3 on the cut list. It's now built and cached, so it costs nothing to keep.

## To do / open

- [ ] When the Data folder's seeded catalog lands, add a real `competitor_query` for the 3 demo products and re-run the tool to refresh `competitor_prices_cache.json`.
- [ ] Optional: replace regex parsing with an LLM extraction pass (see experiment 3).
- [ ] Booth question: confirm whether hackathon keys get extra credits (not needed at current usage).

## Security note

- The repo root `.gitignore` is **empty**, and `.env` holds the live `tvly-...` key, along with the ZooWork and BAND keys. Add `.env` to `.gitignore` before anyone runs `git add .`. The ZooWork Rules.md flags the same thing. The prototype never prints the key.

## Tool reference: inputs, outputs and samples

Every sample below is trimmed from a real response saved in `experiments/`. The file each one came from is named, and `experiments/INDEX.json` has the exact request body for every file.

All Tavily endpoints share:

- **Base URL:** `https://api.tavily.com`
- **Headers:** `Authorization: Bearer $TAV` and `Content-Type: application/json`
- **Errors:** non-200 status with `{"detail": {"error": "<message>"}}` (see "Errors" below)

---

### A. `check_competitor_price` (our tool, the one the merchant agent calls)

Wraps Tavily Search. This is the ZooWork custom tool from plan.md.

**Input**

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `product` | string | yes | Real brand + model to search, e.g. `"Black Diamond Spot 400 headlamp"`. Comes from the catalog's `competitor_query` column, not our SKU name |
| `our_price` | number (USD) | yes | Our catalog price. Also sets the plausible band (0.5× to 2×) for parsing |
| env `DEMO_MODE` | `"1"` or unset | no | `"1"` reads `competitor_prices_cache.json`, with no API call |

**Output**

| Field | Type | Meaning |
| --- | --- | --- |
| `product` | string | Echo of input |
| `our_price` | number | Echo of input |
| `lowest_competitor` | number or null | Lowest price found on a product page; null if none |
| `gap` | number or null | `our_price - lowest_competitor`. Positive means we're more expensive |
| `competitors` | array of `{retailer, price, url}` | One row per domain, sorted cheapest first |
| `tavily_answer` | string or null | Tavily's prose summary. **Log only, don't parse** |
| `label` | string | Ready-made dashboard log line |
| `source` | string | `"tavily_live"` or `"cache (captured 2026-10-03 from Tavily)"` |

**Sample call**

```bash
python3 check_competitor_price.py "Black Diamond Spot 400 headlamp" 64
# or from Python:  from check_competitor_price import check_competitor_price
#                  check_competitor_price("Black Diamond Spot 400 headlamp", 64)
```

**Sample output** (`experiments/09_Black_Diamon.json`)

```json
{
  "product": "Black Diamond Spot 400 headlamp",
  "our_price": 64.0,
  "lowest_competitor": 59.95,
  "gap": 4.05,
  "competitors": [
    {"retailer": "blackdiamondequipment.com", "price": 59.95, "url": "https://blackdiamondequipment.com/products/spot-400-headlamp"},
    {"retailer": "karstsports.com", "price": 69.95, "url": "https://karstsports.com/black-diamond-spot-400-r-headlamp"}
  ],
  "tavily_answer": "The Black Diamond Spot 400 headlamp's price is listed as $59.95 USD ...",
  "label": "Tavily: Black Diamond Spot 400 headlamp at 2 competitors, lowest $59.95",
  "source": "tavily_live"
}
```

**No result:** `lowest_competitor`, `gap` = `null`, `competitors` = `[]`, label = `"Tavily: no competitor price found for <product>"`. The caller should fall back to the fixed 15% loyal-customer discount.

**Sample ZooWork custom-tool schema** (suggested):

```json
{
  "name": "check_competitor_price",
  "description": "Look up the lowest current US competitor price for a real product, to set the gift offer discount.",
  "input_schema": {
    "type": "object",
    "properties": {
      "product": {"type": "string", "description": "Brand and model, e.g. 'Hydro Flask 32 oz Wide Mouth bottle'"},
      "our_price": {"type": "number", "description": "Our catalog price in USD"}
    },
    "required": ["product", "our_price"]
  }
}
```

---

### B. Tavily Search: `POST /search`

**Input** (the fields we used)

| Field | Type | Values / default | Notes |
| --- | --- | --- | --- |
| `query` | string | required | We use `"<brand model> price"` |
| `search_depth` | string | `ultra-fast`, `fast`, `basic` (default), `advanced` | **Use `basic`.** `advanced` costs 2 credits |
| `max_results` | int | 0–20, default 5 | We use 6–8 |
| `include_answer` | bool or `"basic"`/`"advanced"` | false | `true` adds a prose `answer` |
| `include_domains` | string[] | — | Allowlist. **Made results worse** |
| `exclude_domains` | string[] | — | **Use this**, list in `check_competitor_price.py` |
| `country` | string | e.g. `"united states"` | Boosts results from that country. **Basic/advanced only, otherwise 400** |
| `chunks_per_source` | int | 1–3 | Advanced only. More snippet per page |

**Sample input**

```json
{
  "query": "Black Diamond Spot 400 headlamp price",
  "search_depth": "basic",
  "country": "united states",
  "max_results": 8,
  "include_answer": true,
  "exclude_domains": ["ebay.com", "poshmark.com", "wornwear.patagonia.com", "reddit.com", "youtube.com", "pinterest.com", "klarna.com"]
}
```

**Output**

| Field | Type | Meaning |
| --- | --- | --- |
| `query` | string | Echo |
| `answer` | string or null | Prose summary (only if `include_answer`) |
| `results[]` | array | `{url, title, content, score, raw_content, favicon}`. `content` is a markdown snippet, often with prices. `score` is 0–1 relevance |
| `images` | array | Empty unless `include_images` |
| `follow_up_questions` | null | Unused |
| `response_time` | number | Seconds, server side |
| `request_id` | string | For support |

**Sample output** (`experiments/01_search_basic.json`, trimmed)

```json
{
  "query": "Patagonia Nano Puff Vest men price",
  "answer": "The Patagonia Nano Puff Vest men's price ranges from $132.30 to $189.00 on Buckmans.com, with savings up to 30% off the MSRP. ...",
  "results": [
    {
      "url": "https://www.buckmans.com/product/28655/patagonia-nano-puff-vest-mens",
      "title": "Patagonia Men's Nano Puff Vest",
      "content": "# Patagonia Nano Puff Vest - Men's\n\n... Free shipping on most orders over $50!\n\n| Price $132.30-$189.00 | MSRP | Savings  up to 30% Off MSRP | ...",
      "score": 0.95,
      "raw_content": null
    }
  ],
  "images": [],
  "follow_up_questions": null,
  "response_time": 3.94,
  "request_id": "f35c22be-367a-4ea5-9b38-e60cd2399cfa"
}
```

---

### C. Tavily Extract: `POST /extract`

**Input**

| Field | Type | Values / default | Notes |
| --- | --- | --- | --- |
| `urls` | string or string[] | required | Up to 20 URLs |
| `extract_depth` | string | `basic` (default), `advanced` | Advanced renders JS. Slower (~19s for 5 URLs) and 2 credits per 5 URLs |
| `format` | string | `markdown` (default), `text` | |
| `query` | string | — | Reranks chunks toward this intent |
| `chunks_per_source` | int | 1–5 | Only with `query` |
| `timeout` | number | seconds | We used 30 |

**Sample input**

```json
{
  "urls": [
    "https://www.evo.com/outlet/vests/patagonia-nano-puff-vest",
    "https://www.buckmans.com/product/28655/patagonia-nano-puff-vest-mens"
  ],
  "extract_depth": "advanced",
  "format": "markdown",
  "query": "current sale price and regular price",
  "chunks_per_source": 3,
  "timeout": 30
}
```

**Output**

| Field | Type | Meaning |
| --- | --- | --- |
| `results[]` | array | `{url, title, raw_content}`. `raw_content` is the page as markdown |
| `failed_results[]` | array | `{url, error}`, e.g. `"Failed to fetch url"`, `"Error fetching content"`, `"Request timed out"` |
| `response_time` | number | Seconds |
| `request_id` | string | |

**Sample output** (`experiments/04_extract_advanced.json`, trimmed)

```json
{
  "results": [
    {
      "url": "https://www.evo.com/outlet/vests/patagonia-nano-puff-vest",
      "title": "Patagonia Nano Puff® Vest",
      "raw_content": "# Patagonia Nano Puff® Vest\n\nSKU# EB-102752-1013\n\nRated 4.8 out of 5\n\n## $84.99\n\n## $149.00\n\nSell Out Risk:\n\n Sold Out (0 remaining) ..."
    }
  ],
  "failed_results": [
    {"url": "https://www.rei.com/product/249153/patagonia-nano-puff-insulated-vest-mens", "error": "Failed to fetch url"},
    {"url": "https://www.moosejaw.com/p/patagonia-mens-nano-puff-vest-16ptgmmnnpffvstxxapo/16ptgmmnnpffvstxxapo", "error": "Error fetching content"}
  ],
  "response_time": 18.69,
  "request_id": "..."
}
```

**Watch out:** patagonia.com returned its "Sit tight" bot wall inside `results` (not `failed_results`). Check that `raw_content` contains a price before using it.

---

### D. Tavily Research: `POST /research`, then `GET /research/{request_id}`

This endpoint is async: create the task, then poll every ~5s until `status` is `completed` (or `failed`).

**Input (create)**

| Field | Type | Values / default | Notes |
| --- | --- | --- | --- |
| `input` | string | required | The research question in plain English |
| `model` | string | `mini`, `pro`, `auto` | We used `mini` (43s) |
| `output_schema` | JSON Schema object | optional | Makes `content` structured JSON. Every property needs a `description` |

**Sample input**

```json
{
  "input": "Current new (not used) retail price of the Patagonia Nano Puff Vest (men) at major US outdoor retailers",
  "model": "mini",
  "output_schema": {
    "properties": {
      "offers": {
        "type": "array",
        "description": "one per retailer",
        "items": {
          "type": "object",
          "properties": {
            "retailer": {"type": "string", "description": "store name"},
            "price_usd": {"type": "number", "description": "current price for a new item"},
            "url": {"type": "string", "description": "product page"},
            "in_stock": {"type": "boolean", "description": "whether purchasable now"}
          },
          "required": ["retailer", "price_usd", "url"]
        }
      }
    },
    "required": ["offers"]
  }
}
```

**Output of create** (`experiments/05_research_create.json`)

```json
{"status": "pending", "input": "Current new (not used) retail price of ...", "model": "mini",
 "created_at": "2026-10-03T18:58:31.505942+00:00", "response_time": 0.04,
 "request_id": "3ab2b0f0-9859-441f-ad7f-798b10cb88ff"}
```

**Output of poll when done** (`experiments/06_research_result.json`, trimmed)

| Field | Type | Meaning |
| --- | --- | --- |
| `status` | string | `pending` / `in_progress` / `completed` / `failed` |
| `content` | object or string | Matches `output_schema` if one was given, otherwise a markdown report |
| `sources[]` | array | `{url, title, favicon}` |
| `response_time` | number | Seconds the task took |

```json
{
  "status": "completed",
  "content": {
    "offers": [
      {"retailer": "Half-Moon Outfitters", "price_usd": 99.98, "url": "https://www.halfmoonoutfitters.com/products/pat_ms_84242", "in_stock": true},
      {"retailer": "Alabama Outdoors", "price_usd": 132.3, "url": "https://alabamaoutdoors.com/patagonia-mens-nano-puff-vest", "in_stock": true},
      {"retailer": "REI", "price_usd": 98.83, "url": "https://www.rei.com/b/patagonia/f/pl-nano-puff", "in_stock": true}
    ]
  },
  "sources": [{"url": "https://www.halfmoonoutfitters.com/products/pat_ms_84242", "title": "Patagonia Nano Puff Vest for Men (SALE) – Half-Moon Outfitters", "favicon": "..."}],
  "response_time": 43.42,
  "request_id": "3ab2b0f0-9859-441f-ad7f-798b10cb88ff"
}
```

---

### E. Tavily Usage: `GET /usage`

**Input:** none (header only).

**Sample output** (`experiments/10_usage.json`). The counters were still 0 after all the calls above, so they lag:

```json
{
  "key": {"usage": 0, "limit": null, "search_usage": 0, "crawl_usage": 0, "extract_usage": 0, "map_usage": 0, "research_usage": 0},
  "account": {"current_plan": "Researcher", "plan_usage": 0, "plan_limit": 1000, "search_usage": 0, "extract_usage": 0, "research_usage": 0, "paygo_usage": 0, "paygo_limit": null}
}
```

---

### F. Errors seen

| Status | Body | Cause |
| --- | --- | --- |
| 400 | `{"detail": {"error": "Country parameter is not supported for fast or ultra-fast search_depth."}}` | `country` with `fast`/`ultra-fast` (`experiments/08_fast_allow_*.json`) |
| 200 with empty `results` | `{"results": [], ...}` | Over-narrow `include_domains` (`experiments/08_basic_allow_Black_Diamond_Spot_4.json`) |
| 200, item in `failed_results` | `"Failed to fetch url"` / `"Error fetching content"` / `"Request timed out"` | Extract blocked by the retailer |

**Not tested:** `/map` and `/crawl`. They aren't needed for price checks, and crawling retailer sites would hit the same blocking as Extract.

## Saved data (reuse without spending credits)

| What | Where |
| --- | --- |
| Every raw API response | `experiments/01–10_*.json` |
| Request body, latency and status for each file | `experiments/INDEX.json` |
| All 20 competitor prices observed, with a verified flag | `price_observations.json` |
| Ready-to-serve tool output for 4 products | `competitor_prices_cache.json` (used by `DEMO_MODE=1`) |

Verified prices (seen on the exact product's own page), as of 2026-10-03:

| Product | Prices (USD) |
| --- | --- |
| Black Diamond Spot 400 headlamp | $59.95 (Black Diamond). Karst listing page shows $54.95 (unverified) |
| Hydro Flask 32 oz Wide Mouth | $44.95 (Hydro Flask, Eastside Sports). Sam's Club $36.98 per Tavily's answer text |
| Salomon ADV Skin 5 running vest | $145.00 (Salomon, REI, RunPacers) |
| Patagonia Nano Puff Vest (men) | $99.98 (Half-Moon), $132.30 (Alabama Outdoors, Buckman's). evo $84.99 but **sold out** |

## Tool inputs & outputs (contract with Data/ backend)

The merchant agent's `check_competitor_price` tool is handled in `Data/tools.py`. It calls Tavily through one HTTP bridge you run. Set `TAVILY_BRIDGE_URL=http://localhost:<port>` and `DEMO_MODE=0` when starting `python3 Data/server.py`. Until then (or if the call fails), it reads `Data/mock/competitor_prices.json`. Saved samples: `Data/samples/bridges/tavily_competitor_prices.json` and `Data/samples/tools/check_competitor_price.json`.

### Bridge: `POST {TAVILY_BRIDGE_URL}/competitor_prices`

```jsonc
// input
{"sku": "TR-VEST", "query": "Salomon ADV Skin 5 running vest", "our_price": 68.0}
// output: only "competitors" is required. Your check_competitor_price() return value fits as-is.
{"competitors": [{"retailer": "Summit Outfitters", "price": 64.0, "url": "https://..."},
                 {"retailer": "Ridge & Co", "price": 72.0, "url": "https://..."}],
 "label": "Tavily: ... at 2 competitors, lowest $64.00"}   // optional extra fields are ignored
```

The bridge is a thin wrapper: `check_competitor_price(body["query"], body["our_price"])` and return the result. `query` comes from the `competitor_query` column in the merchant catalog (`Data/seed.py`):

| SKU | Our name / price | `competitor_query` (matches your cache keys?) |
| --- | --- | --- |
| `TR-VEST` | Trail Running Vest, $68 | `Salomon ADV Skin 5 running vest` ✓ |
| `TR-BOTTLE` | Insulated Trail Bottle 32oz, $42 | `Hydro Flask 32 oz Wide Mouth` ✗ (cache key ends in `bottle`) |
| `TR-LAMP` | Trail Headlamp 400, $55 | `Black Diamond Spot 400 headlamp` ✓ |

### What the merchant tool returns to the agent

```jsonc
// POST /api/tools/check_competitor_price  input
{"sku": "TR-VEST"}
// output
{"sku": "TR-VEST", "our_price": 68.0,
 "competitors": [{"retailer": "Summit Outfitters", "price": 64.0, "url": "..."}, {"retailer": "Ridge & Co", "price": 72.0, "url": "..."}],
 "lowest": 64.0, "suggested_discount_pct": 15,
 "reason": "Tavily: Trail Running Vest at 2 competitors, lowest $64.0; we're $4.0 above, offer 15%"}
```

Discount rule (in `Data/tools.py`, not Tavily): we're above the lowest competitor → 15%, otherwise 10%. `make_offer` then enforces the 20% cap and the margin floor (cost × 1.3).

**Open conflict to settle:** the real Salomon ADV Skin 5 costs $140–145 (your finding), but the demo vest is priced at $68 for Sarah's ~$60 budget. With live Tavily, the vest would show "lowest $140", we'd be below it, and the offer would drop to 10%. Either pick a cheaper real vest for `competitor_query`, or keep the mock prices for the vest on stage.
