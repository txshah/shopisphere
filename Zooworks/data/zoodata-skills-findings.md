# ZooData-Skills — saved findings (fetched 2026-10-03)

Source: https://github.com/SerendipityOneInc/ZooData-Skills (live fetch, full repo overview)

## What it is
A collection of AI agent skills on ZooData's e-commerce data infrastructure: "200M+ products,
1B+ reviews" of Amazon commerce data, plus a general web-extraction tool.

## The 10 skills (all Amazon-focused)
Foundation:
- `zoodata/` — direct API access, "25 Amazon commerce and keyword-intelligence endpoints"
- `amazon-analysis/` — market research, competitor analysis, ASIN evaluation
- `amazon-keyword-traffic-analysis/` — keyword expansion and product traffic analysis
- `amazon-market-analysis/` — market discovery and entry assessment

Specialized:
- `amazon-competitor-intelligence-monitor/` — competitive intelligence, tiered alerts
- `amazon-daily-market-radar/` — automated monitoring, price/BSR/competitor alerts
- `amazon-listing-audit-pro/` — 8-dimension listing health scoring
- `amazon-pricing-command-center/` — pricing signals (RAISE/HOLD/LOWER)
- `amazon-review-intelligence-extractor/` — consumer insights from "1B+ pre-analyzed reviews"

Web tool:
- `web-extract/` — general public web data extraction (NOT TikTok-specific)

## TikTok Shop
**No TikTok-specific skill, tool, or endpoint exists in this repo.** "TikTok & beyond" appears
only as marketing copy in the repo header. Do not build against it — there is nothing to call.
Matches plan.md's cut-list item #1: cut TikTok Shop trends.

## Auth
Separate key from ZooWork: `export ZOODATA_API_KEY='hms_live_xxx'`. Free tier: 1,000 signup
credits, 1 credit = 1 API call. This project's `.env` does NOT have this key (only `ZOOWORKS`,
the ZooWork key, is present) — get one at zoodata.ai if the team wants real Amazon data.

## Live-verified cross-check (same day, this project's ZooWork key)
Created a real running ZooWork agent and listed its default global skills + its own reported
tool list (full transcript: `data/live-check-output-2026-10-03.txt`). No ZooData/Amazon/TikTok
skill or tool is attached by default — confirms ZooData is not "out of the box" on this key
without the separate ZOODATA_API_KEY and an explicit skill attach.
