"""Run every tool and bridge once against fresh mock data and save the real
input/output pairs to Data/samples/. Re-run after changing tools or seed data:

    python3 Data/capture_samples.py

Leaves the stores reseeded (clean) when done.
"""
import json
from pathlib import Path

import adapters
import db
import mock_agents
import seed
import server
import tools

OUT = Path(__file__).resolve().parent / "samples"


def save(name, obj):
    path = OUT / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    return obj


def tool(name, args):
    output = tools.call_tool(name, args, "capture")
    save(f"tools/{name}", {"tool": name, "endpoint": f"POST /api/tools/{name}", "input": args, "output": output})
    return output


def main():
    seed.seed()

    # Merchant tools, in plan.md flow order.
    t = tool("get_top_customers", {"limit": 3})[0]
    trust = tool("score_agent_trust", {"agent_handle": t["agent_handle"]})
    occ = tool("ask_customer_occasions", {"customer_id": t["customer_id"]})["occasions"][0]
    cands = tool("match_catalog", {"customer_id": t["customer_id"], "budget": occ["budget"]})
    vouch = tool("request_vouch", {"recipient_handle": occ["friend_handle"], "skus": [c["sku"] for c in cands]})
    top = vouch["ranked"][0]
    price = tool("check_competitor_price", {"sku": top["sku"]})
    offer = tool("make_offer", {"customer_id": t["customer_id"], "sku": top["sku"],
                                "occasion_ref": f"{occ['friend_handle']}:{occ['occasion']}:{occ['occasion_date']}",
                                "discount_pct": price["suggested_discount_pct"], "trust_score": trust["score"],
                                "vouch_result": top, "size": top["size"], "budget": occ["budget"]})
    tool("send_message", {"customer_id": t["customer_id"], "offer_id": offer["offer_id"],
                          "body": tools.gift_offer_text(offer["offer_id"])})
    # T replies YES on the phone -> place_order opens the approval gate.
    reply = tools.phone_reply("YES", t["customer_id"])
    save("api/phone_reply", {"endpoint": "POST /api/phone/reply", "input": {"body": "YES", "customer_id": t["customer_id"]},
                             "output": reply})
    save("tools/place_order", {"tool": "place_order", "endpoint": "POST /api/tools/place_order",
                               "input": {"offer_id": offer["offer_id"]},
                               "output": {k: reply[k] for k in ("approval_id", "status")}})
    tool("handle_storefront_request", {"agent_handle": "unverified-shopper", "ask": "Buy 3 × TR-VEST at 15% off",
                                       "requests_per_min": 40})
    row = tool("forecast_from_vouches", {})[0]
    tool("draft_purchase_order", {"sku": row["sku"], "size": row["size"], "quantity": row["suggested_qty"],
                                  "reason": row["note"]})

    # Human gates: approve the order, which also runs screen_return_risk on it.
    pending = db.query("backend", "SELECT * FROM approvals WHERE status = 'pending' ORDER BY id")
    save("api/approvals_resolve", {"endpoint": "POST /api/approvals/<id>", "input": {"decision": "approve"},
                                   "output": [tools.resolve_approval(a["id"], "approve") for a in pending]})
    tool("screen_return_risk", {})

    # Bridges (what Band/Tavily/SMS teammates must return). Mock outputs = the contract.
    save("bridges/band_share_occasions", {"endpoint": "POST {BAND_BRIDGE_URL}/share_occasions",
                                          "input": {"customer_handle": t["agent_handle"]},
                                          "output": mock_agents.t_share_occasions()})
    save("bridges/band_vouch_for", {"endpoint": "POST {BAND_BRIDGE_URL}/vouch_for",
                                    "input": {"recipient_handle": "sarah-gift-vouch", "sku": "TR-VEST"},
                                    "output": mock_agents.sarah_vouch_for("TR-VEST"),
                                    "other_examples": [mock_agents.sarah_vouch_for(s) for s in ("TR-BOTTLE", "TR-LAMP")],
                                    "no_agent_output": None})
    save("bridges/tavily_competitor_prices", {"endpoint": "POST {TAVILY_BRIDGE_URL}/competitor_prices",
                                              "input": {"sku": "TR-VEST", "query": "Salomon ADV Skin 5 running vest", "our_price": 68.0},
                                              "output": adapters.tavily_competitor_prices("TR-VEST", "Salomon ADV Skin 5 running vest", 68.0)})
    save("bridges/sms_send", {"endpoint": "POST {SMS_BRIDGE_URL}/send",
                              "input": {"to": "+15550100", "body": "…Reply YES."}, "output": {"status": "delivered"}})

    # API payloads the dashboard and other teammates use.
    save("api/state", server.state())
    save("api/tools_custom_tools", tools.custom_tools())
    save("api/events_post", {"endpoint": "POST /api/events",
                             "input": {"source": "band", "kind": "room.message",
                                       "summary": "Sarah's Gift Vouch: wants TR-VEST (0.9)", "payload": {"room_id": "…"}},
                             "output": {"ok": True}})
    for owner in db.SCHEMAS:
        save(f"stores/{owner}", db.tables(owner))

    seed.seed()
    print(f"Saved samples to {OUT}")


if __name__ == "__main__":
    main()
