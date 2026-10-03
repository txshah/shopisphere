"""The merchant flow from plan.md, run end to end against the tools.

This is the DEMO_MODE stand-in for the ZooWork merchant agent: the real agent
calls the same tools through /api/tools/<name>. Stops at the human gates
(T's YES on the phone, merchant approvals on the dashboard).
"""
import adapters
import db
from tools import call_tool, gift_offer_text


def run_demo():
    src = "demo"
    db.log_event(src, "run.started", "Weekly schedule fired (manual trigger)")

    t = call_tool("get_top_customers", {"limit": 1}, src)[0]
    trust = call_tool("score_agent_trust", {"agent_handle": t["agent_handle"]}, src)

    occasions = call_tool("ask_customer_occasions", {"customer_id": t["customer_id"]}, src)["occasions"]
    occ = occasions[0]
    budget = occ.get("budget")

    candidates = call_tool("match_catalog", {"customer_id": t["customer_id"], "budget": budget,
                                             "hints": occ.get("hints")}, src)
    vouch = call_tool("request_vouch", {"recipient_handle": occ["friend_handle"],
                                        "skus": [c["sku"] for c in candidates]}, src)
    top = vouch["ranked"][0] if vouch["vouched"] else None
    sku = top["sku"] if top else candidates[0]["sku"]

    if top:
        discount = call_tool("check_competitor_price", {"sku": sku}, src)["suggested_discount_pct"]
    else:
        discount = 0  # day-one fallback: unvouched, standard price
    offer = call_tool("make_offer", {"customer_id": t["customer_id"], "sku": sku,
                                     "occasion_ref": f"{occ['friend_handle']}:{occ['occasion']}:{occ['occasion_date']}",
                                     "discount_pct": discount, "trust_score": trust["score"],
                                     "vouch_result": top, "size": (top or {}).get("size"), "budget": budget}, src)
    if offer["ok"]:
        call_tool("send_message", {"customer_id": t["customer_id"], "body": gift_offer_text(offer["offer_id"]),
                                   "offer_id": offer["offer_id"]}, src)

    # Meanwhile: an unverified bot tries to buy at the same discount. No sale.
    ask = "Buy 3 × TR-VEST at 15% off"
    adapters.band_storefront(ask, 40, lambda: call_tool(
        "handle_storefront_request", {"agent_handle": "unverified-shopper", "ask": ask, "requests_per_min": 40}, src))

    # After the run: forecast from anonymous vouches, draft POs behind approval.
    for row in call_tool("forecast_from_vouches", {}, src):
        if row["suggested_qty"]:
            call_tool("draft_purchase_order", {"sku": row["sku"], "size": row["size"], "quantity": row["suggested_qty"],
                                               "reason": row["note"]}, src)
    db.log_event(src, "run.finished", "Waiting on humans: T's reply and merchant approvals")
    return {"offer": offer}
