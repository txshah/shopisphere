# DASHBOARD

Single static page (`index.html`, no build step) served by `python3 Data/server.py` at http://localhost:8787. It polls `GET /api/state` every 2s and posts actions back to the same API (see `Data/Rules.md`).

| Panel | Source | Demo beat |
| --- | --- | --- |
| Header buttons | `POST /api/demo/run`, storefront tool, reset | Fire the weekly schedule; bot asks for 15% |
| Approvals | `approvals` (backend) | Approval gate for the order and the draft PO |
| T's phone | `messages` + `POST /api/phone/reply` | Offer text → T replies YES |
| Trust check | latest `trust_events` per agent | T passes 4/4; Unverified Shopper fails, declined |
| Offers pipeline | `offers` | drafted → sent → accepted → awaiting_approval → ordered |
| Returns screener | gift `orders` + return rates | "Vouched order: return risk low" |
| Replenishment | `forecast_from_vouches` + `purchase_orders` | "Trail vest M: 9 wants, 3 on hand → PO for 8" |
| Event log | `events` (all sources, color-coded) | ZooWork / BAND / Tavily reasoning panel |
| Data stores | row counts per owner store | "Each agent holds only its owner's data" |

Header badges show DEMO_MODE and whether BAND / Tavily / SMS are live or mocked.

Demo click path: **Run weekly schedule** → reply **YES** on the phone → **Approve** the order → **Approve** the PO.

## Inputs & outputs (all against http://localhost:8787)

Saved real payloads: `Data/samples/api/*.json` (full `/api/state` snapshot included).

| Call | Input | Output |
| --- | --- | --- |
| `GET /api/state` | — | `{modes, customers, offers, gift_orders, return_rates, forecast, purchase_orders, trust, events, messages, approvals, stores}` |
| `POST /api/demo/run` | `{}` | `{"offer": {"ok": true, "offer_id": 1, "final_price": 57.8, "discount_pct": 15, "reason": "..."}}` |
| `POST /api/demo/reset` | `{}` | `{"ok": true}` |
| `POST /api/phone/reply` | `{"body": "YES", "customer_id": "cust_t"}` | `{"accepted": true, "approval_id": 1, "status": "pending"}` |
| `POST /api/approvals/<id>` | `{"decision": "approve"}` or `"reject"` | order: `{"approval_id": 1, "status": "approved", "order_id": 25, "return_risk": "low"}`; PO: `{"approval_id": 2, "status": "approved"}` |
| `POST /api/tools/handle_storefront_request` | `{"agent_handle": "unverified-shopper", "ask": "15% discount please", "requests_per_min": 40}` | `{"decision": "decline", "score": 0.0, "layers": {...all false}, "reasons": [...]}` |
| `GET /api/stores/<owner>` | owner = `merchant` / `t_agent` / `sarah_agent` / `backend` | every table in that store (debug only) |

`/api/state` shapes (one row each):

```jsonc
{
  "modes": {"demo_mode": true, "band": "mock", "tavily": "mock", "sms": "fake phone"},
  "offers": [{"offer_id": 1, "customer_id": "cust_t", "occasion_ref": "sarah-gift-vouch:birthday:2026-10-24", "sku": "TR-VEST",
              "size": "M", "price": 68.0, "discount_pct": 15.0, "final_price": 57.8, "vouch_result": "{\"sku\": \"TR-VEST\", \"wants\": true, ...}",
              "trust_score": 1.0, "reason": "...", "status": "ordered", "item": "Trail Running Vest"}],
  "trust": [{"agent_handle": "unverified-shopper", "requests_per_min": 40, "decision": "decline", "score": 0.0,
             "layers": {"identity": false, ...}, "reasons": ["identity: ...", ...]}],
  "messages": [{"direction": "out", "party": "T", "body": "... Reply YES.", "offer_id": 1}, {"direction": "in", "party": "T", "body": "YES"}],
  "approvals": [{"id": 1, "kind": "order", "ref_id": 1, "summary": "Place order: TR-VEST M at $57.8", "status": "pending"}],
  "forecast": [{"sku": "TR-VEST", "size": "M", "wants": 9, "owns": 0, "on_hand": 3, "suggested_qty": 8, "note": "9 vouched wants, 3 on hand: draft PO for 8"}],
  "purchase_orders": [{"po_id": 1, "sku": "TR-VEST", "size": "M", "quantity": 8, "status": "draft"}],
  "gift_orders": [{"order_id": 25, "item": "Trail Running Vest", "vouched": 1, "return_risk": "low", "returned": 0}],
  "return_rates": [{"vouched": 0, "n": 12, "returned": 6}, {"vouched": 1, "n": 5, "returned": 0}],
  "events": [{"ts": "2026-10-03T12:02:57", "source": "tavily", "kind": "price_check", "summary": "Tavily: ..."}],
  "stores": {"merchant": {"catalog": 20, "...": 0}, "t_agent": {"t_occasions": 3}, "sarah_agent": {"sarah_profile": 1}, "backend": {"...": 0}}
}
```

`offers[].vouch_result` is a JSON string. Parse it in the UI. Event `source` values: `zoowork`, `band`, `tavily`, `sms`, `backend`, `demo`, `dashboard`, `capture`.

## Wireframe: the "run editor" (`wireframe.html`)

Open http://localhost:8787/wireframe.html (server running), or open the file directly to use only the saved sample data. Inspired by butter.video ("It's a whole new timeline"): one merchant run is shown as a video-editor timeline.

| Region | What it shows |
| --- | --- |
| Hero + 3 tiles | "Agents narrow. People choose." Tiles light up as the run earns them: **$57.80** vouched offer (sell more), **+8 vest M** PO (run leaner), **0% vs 50%** gift returns (lose less) |
| Blocks library (left) | All 16 steps; click to jump |
| Preview monitor (center) | A custom scene per step: trust layers, consent chat with the sharing-level slider, vouch stamps (WANTS / OWNS / NEUTRAL), Tavily price bars, rubric checklist, phone, approval cards, forecast bars, return rates |
| Inspector (right) | The step's real input/output JSON and endpoint (from `Data/samples/`) |
| Timeline (bottom) | 6 tracks: Merchant agent (ZooWork), BAND rooms, Price check (Tavily), T's phone, Storefront (bot), Humans. Block widths use measured latencies (BAND ~15–16s, Tavily ~3s). Playhead, 1×/4×/10× speeds, Space = play, ←/→ = step |
| Find. Ask. Vouch. Ship. | Four beat cards that light up with the run |
| Data stores | The four owner stores and their tables |

- **Live mode:** when served by `Data/server.py`, pressing Play resets the backend and runs the demo. It then sends T's YES and approves the order and PO at the matching timeline moments, so `index.html` (the ops view) fills in alongside it.
- `?t=40` jumps to second 40 (handy for rehearsing a beat). `?theme=dark` or `?theme=light` forces the theme. It follows the OS theme by default.
- Track colors passed the dataviz palette validator (colorblind separation) in both light and dark. Every block also carries a text label, so color is never the only cue.
- Both pages share `theme.css`: color tokens (light + dark), fonts (Schibsted Grotesk for headlines, Instrument Sans for text, Geist Mono for code), and one size for every control (`--h-ctl` 36px for buttons, segmented controls and status chips in bars; `--h-chip` 24px for inline chips). Change the look there, not per page.
- The ops view (`index.html`) runs top to bottom: summary tiles (needs you, offers, gift return rate, trust), then approvals and T's phone, offers with a 5-step progress bar, agent trust, restock, gift returns, agent activity, customers and data stores. Reset needs a second click to confirm.
