"""Backend implementations of the merchant agent's tools (ZooWork custom tools).

ZooWork executes custom tools in our app: the ZooWork bridge receives a tool
call and POSTs its input to /api/tools/<name>; the JSON returned here is the
tool result. Every call is written to the event log for the dashboard.
"""
import json
from datetime import date

import adapters
import db

MARGIN_FLOOR = 1.3      # final price must be >= cost * 1.3

# We have no product photos, so each product gets an emoji for texts and the dashboard.
EMOJI = {
    "TR-VEST": "🦺", "TR-BOTTLE": "🥤", "TR-LAMP": "🔦", "TR-CAP": "🧢", "TR-SOCKS": "🧦", "TR-POLES": "⛰️",
    "TR-GAITERS": "🥾", "CP-MUG": "☕", "CP-LANTERN": "🏮", "CP-HAMMOCK": "🏕️", "CP-STOVE": "🔥", "CP-BLANKET": "🛌",
    "CL-CHALK": "🧗", "CL-BRUSH": "🪥", "CL-HARNESS": "🪢", "WA-DRYBAG": "🎒", "WA-TOWEL": "🏖️", "AP-FLEECE": "🧥",
    "AP-BEANIE": "🧶", "AP-SHELL": "☔",
}


def emoji(sku):
    return EMOJI.get(sku, "🎁")


def _money(x):
    return f"${x:,.2f}"


def _day(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def _item(offer):
    """'Trail Running Vest, size M' from an offer row."""
    name = db.one("merchant", "SELECT name FROM catalog WHERE sku = ?", (offer["sku"],))["name"]
    return name + (f", size {offer['size']}" if offer["size"] and offer["size"] != "OS" else "")


def gift_offer_text(offer_id):
    """The text T gets: occasion, the item with its emoji, why, price, and how to say yes."""
    o = db.one("merchant", "SELECT * FROM offers WHERE offer_id = ?", (offer_id,))
    _friend, occasion, when = (o["occasion_ref"].split(":") + ["", "", ""])[:3]
    vouch = json.loads(o["vouch_result"] or "null")
    lines = [f"🎁 Your friend's {occasion or 'big day'} is {_day(when)}." if when else "🎁 A gift idea for your friend.",
             f"{emoji(o['sku'])} {_item(o)}",
             "Their agent says they'd love it." if vouch and vouch.get("wants") else "From your favorite line at Trailhead.",
             f"{_money(o['final_price'])} for you ({o['discount_pct']:g}% off {_money(o['price'])})" if o["discount_pct"] else _money(o["final_price"]),
             "Reply YES, or tell your Gift Planner agent yes, to order."]
    return "\n".join(lines)
MAX_DISCOUNT_PCT = 20
SAFETY_STOCK = 2
# No sales to unverified agents. Verified = a real person (identity) behind a registered agent
# (provenance) acting like a buyer (behavior). History is a bonus, so first-time verified buyers can buy.
VERIFIED_LAYERS = ("identity", "provenance", "behavior")
# A trust_score sent by the caller (ZooWork, or a KYA provider in production) is an extra gate:
# it must clear this too. It can never replace the backend's own verification.
TRUST_MIN = 0.75


# --- Find the moment ------------------------------------------------------------
def get_top_customers(limit=3):
    """Top customers from the merchant's own order history."""
    return db.query("merchant", "SELECT * FROM merchant_customers ORDER BY order_count DESC LIMIT ?", (limit,))


def score_agent_trust(agent_handle, requests_per_min=1, discount_first=False):
    """Verify an agent with four simulated KYA layers: identity, provenance, history, behavior.
    Only verified agents (identity + provenance + behavior) can be sold to."""
    p = db.one("backend", "SELECT * FROM agent_passports WHERE agent_handle = ?", (agent_handle,))
    cust = db.one("merchant", "SELECT * FROM merchant_customers WHERE agent_handle = ?", (agent_handle,))
    layers = {
        "identity": bool(p and p["owner_phone_verified"] and p["token"]),
        "provenance": bool(p and p["registered_band"] and p["approved_contact"]),
        "history": bool(cust and cust["order_count"] > 0),
        "behavior": requests_per_min <= 10 and not discount_first,
    }
    reasons = {
        "identity": "no signed passport / owner not phone-verified",
        "provenance": "unknown handle, not an approved contact",
        "history": "no prior orders here",
        "behavior": f"{requests_per_min} req/min" + (", discount-first ask" if discount_first else ""),
    }
    failed = [f"{k}: {reasons[k]}" for k, ok in layers.items() if not ok]
    score = sum(layers.values()) / 4
    verified = all(layers[k] for k in VERIFIED_LAYERS)
    decision = "allow" if verified else "decline"
    db.execute("backend", "INSERT INTO trust_events(ts, agent_handle, requests_per_min, decision, score, layers, reasons) "
               "VALUES (?,?,?,?,?,?,?)",
               (db.now(), agent_handle, requests_per_min, decision, score, json.dumps(layers), json.dumps(failed)))
    return {"agent_handle": agent_handle, "verified": verified, "sale": "allowed" if verified else "blocked",
            "decision": decision, "score": score, "layers": layers, "reasons": failed}


def verify_buyer(customer_id):
    """Run before every sale step. A customer who shops through an agent must be verified;
    a customer with no agent is a person buying directly."""
    cust = db.one("merchant", "SELECT * FROM merchant_customers WHERE customer_id = ?", (customer_id,))
    if not cust:
        return {"verified": False, "sale": "blocked", "score": 0.0, "reasons": [f"unknown customer {customer_id}"]}
    if not cust["agent_handle"]:
        return {"verified": True, "sale": "allowed", "score": None, "reasons": [], "via": "person, no agent"}
    return score_agent_trust(cust["agent_handle"])


def _block_sale(where, customer_id, trust, offer_id=None):
    if offer_id:
        db.execute("merchant", "UPDATE offers SET status = 'blocked' WHERE offer_id = ?", (offer_id,))
    db.log_event("backend", "no_sale", f"{where}: {customer_id}'s agent is not verified → no sale", {"reasons": trust["reasons"]})
    return {"ok": False, "status": "blocked", "sale": "blocked", "reasons": trust["reasons"]}


def ask_customer_occasions(customer_id):
    """Consent room: ask the customer's agent; get back only what their sharing level allows."""
    cust = db.one("merchant", "SELECT * FROM merchant_customers WHERE customer_id = ?", (customer_id,))
    if not cust or not cust["agent_handle"]:
        return {"customer_id": customer_id, "occasions": [], "note": "customer has no agent"}
    return {"customer_id": customer_id, "occasions": adapters.band_share_occasions(cust["agent_handle"])}


# --- Match and vouch --------------------------------------------------------------
def match_catalog(customer_id, budget=None, hints=None, k=3):
    """Candidates from the customer's favorite lines, in stock, near budget."""
    cust = db.one("merchant", "SELECT * FROM merchant_customers WHERE customer_id = ?", (customer_id,))
    lines = cust["favorite_lines"].split(",") if cust else []
    rows = db.query("merchant", f"SELECT * FROM catalog WHERE stock > 0 AND line IN ({','.join('?' * len(lines))})", lines)
    if budget:
        rows = [r for r in rows if r["price"] <= budget * 1.2]
        rows.sort(key=lambda r: abs(r["price"] - budget))
    if hints:
        words = hints.lower().split()
        rows.sort(key=lambda r: -sum(w in r["tags"] for w in words))
    return rows[:k]


def request_vouch(recipient_handle, skus):
    """Vouch room: the recipient's agent answers wants/owns/confidence per SKU.
    Opted-in answers are added to anonymous per-SKU/size counts (no person ids)."""
    answers = adapters.band_vouch_batch(recipient_handle, skus)
    if not answers:
        return {"vouched": False, "ranked": [], "note": "recipient has no agent; send unvouched offer at standard price"}
    for a in answers:
        a.setdefault("confidence", 0.5)
        a.setdefault("owns", False)
        a.setdefault("wants", False)
        if a.get("contribute_signal"):
            size = a.get("size") or "OS"
            db.execute("merchant", "INSERT INTO vouch_signals VALUES (?,?,?,?,?) ON CONFLICT(sku, size, time_window) "
                       "DO UPDATE SET wants = wants + excluded.wants, owns = owns + excluded.owns",
                       (a["sku"], size, "2026-Q4", int(bool(a["wants"])), int(bool(a["owns"]))))
    ranked = sorted([a for a in answers if not a["owns"]], key=lambda a: (not a["wants"], -a["confidence"]))
    return {"vouched": True, "ranked": ranked, "dropped_owned": [a["sku"] for a in answers if a["owns"]]}


def check_competitor_price(sku):
    """Tavily price check that sets the discount."""
    item = db.one("merchant", "SELECT * FROM catalog WHERE sku = ?", (sku,))
    comps = adapters.tavily_competitor_prices(sku, item["competitor_query"] or item["name"], item["price"])["competitors"]
    lowest = min((c["price"] for c in comps), default=None)
    gap = round(item["price"] - lowest, 2) if lowest else None
    discount = 15 if gap and gap > 0 else 10
    where = min(comps, key=lambda c: c["price"])["retailer"] if comps else None
    reason = (f"Tavily: {item['name']} at {len(comps)} competitors, lowest ${lowest:.2f} ({where}); "
              + (f"we're ${gap:.2f} above, offer {discount}%" if gap and gap > 0 else f"we're already lowest, loyalty {discount}%")
              if comps else f"Tavily: no competitor prices for {sku}; default {discount}%")
    db.log_event("tavily", "price_check", reason)
    return {"sku": sku, "our_price": item["price"], "competitors": comps, "lowest": lowest,
            "suggested_discount_pct": discount, "reason": reason}


# --- Offer, message, order ---------------------------------------------------------
def make_offer(customer_id, sku, occasion_ref, discount_pct, trust_score=None, vouch_result=None, size=None, budget=None):
    """Outcome rubric: verified buyer, in stock, within budget, above margin floor, one-line reason.
    The backend always verifies the buyer itself. An optional trust_score must also be >= TRUST_MIN."""
    trust = verify_buyer(customer_id)
    if not trust["verified"]:
        return _block_sale("make_offer", customer_id, trust)
    if trust_score is not None and trust_score < TRUST_MIN:
        return _block_sale("make_offer", customer_id, {"reasons": [f"trust score {trust_score} below {TRUST_MIN}"]})
    item = db.one("merchant", "SELECT * FROM catalog WHERE sku = ?", (sku,))
    size = size or "OS"
    inv = db.one("merchant", "SELECT on_hand FROM inventory WHERE sku = ? AND size = ?", (sku, size))
    problems = []
    if not inv or inv["on_hand"] <= 0:
        problems.append(f"{sku} {size} out of stock")
    discount_pct = min(discount_pct, MAX_DISCOUNT_PCT)
    final = round(item["price"] * (1 - discount_pct / 100), 2)
    floor = item["cost"] * MARGIN_FLOOR
    if final < floor:
        revised = int((1 - floor / item["price"]) * 100)
        db.log_event("backend", "rubric", f"offer rejected: below margin floor at {discount_pct}% → revised to {revised}%")
        discount_pct, final = revised, round(item["price"] * (1 - revised / 100), 2)
    if budget and final > budget * 1.1:
        problems.append(f"${final} over budget ${budget}")
    if problems:
        db.log_event("backend", "rubric", "offer failed rubric: " + "; ".join(problems))
        return {"ok": False, "problems": problems}
    vouched = bool(vouch_result and vouch_result.get("wants"))
    reason = (f"From the store you love, a gift she'll want: {item['name']}"
              + (" (her agent confirmed it)" if vouched else " (unvouched)") + f", {discount_pct}% off")
    offer_id = db.execute(
        "merchant",
        "INSERT INTO offers(customer_id, occasion_ref, sku, size, price, discount_pct, final_price, vouch_result, "
        "trust_score, reason, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,'drafted',?)",
        (customer_id, occasion_ref, sku, size, item["price"], discount_pct, final,
         json.dumps(vouch_result), trust["score"], reason, db.now()))
    return {"ok": True, "offer_id": offer_id, "final_price": final, "discount_pct": discount_pct, "reason": reason,
            "buyer_verified": True, "trust_score": trust["score"] if trust_score is None else trust_score}


def send_message(customer_id, body="", offer_id=None):
    """Text the customer (Twilio bridge or fake phone panel). With an offer_id, the text is written from the
    offer record itself (occasion, item, vouch, price), so it can't misstate what the recipient's agent said."""
    cust = db.one("merchant", "SELECT * FROM merchant_customers WHERE customer_id = ?", (customer_id,))
    if offer_id:
        body = gift_offer_text(offer_id)
    result = adapters.send_sms(cust["phone"], body)
    db.execute("backend", "INSERT INTO messages(ts, direction, party, body, offer_id) VALUES (?,?,?,?,?)",
               (db.now(), "out", cust["name"], body, offer_id))
    if offer_id:
        db.execute("merchant", "UPDATE offers SET status = 'sent' WHERE offer_id = ?", (offer_id,))
    return {"sent": True, **result}


def place_order(offer_id, accepted_via="merchant agent"):
    """Re-verifies the buyer, places a payment hold, then opens the approval gate; the order is created only when a human approves."""
    offer = db.one("merchant", "SELECT * FROM offers WHERE offer_id = ?", (offer_id,))
    trust = verify_buyer(offer["customer_id"])
    if not trust["verified"]:
        return _block_sale("place_order", offer["customer_id"], trust, offer_id)
    pay = adapters.visa_authorize(offer_id, offer["final_price"], accepted_via)
    db.execute("merchant", "INSERT INTO payments(offer_id, amount, network, token, auth_id, accepted_via, status, created_at) "
                           "VALUES (?,?,?,?,?,?,?,?)",
               (offer_id, pay["amount"], pay["network"], pay["token"], pay["auth_id"], accepted_via, pay["status"], db.now()))
    db.execute("merchant", "UPDATE offers SET status = 'awaiting_approval' WHERE offer_id = ?", (offer_id,))
    approval_id = db.execute(
        "backend", "INSERT INTO approvals(ts, kind, ref_id, summary, status) VALUES (?,?,?,?,'pending')",
        (db.now(), "order", offer_id, f"Order for T: {_item(offer)}, {_money(offer['final_price'])} (payment held)"))
    db.log_event("backend", "approval.requested", f"place_order for offer #{offer_id}")
    adapters.ping_merchant(approval_id, f"T said YES to the {_item(offer)} for {_money(offer['final_price'])}. Approve the order?")
    return {"approval_id": approval_id, "status": "pending", "payment": {k: pay[k] for k in ("network", "auth_id", "status")}}


def _settle_payment(offer_id, action, order_id=None):
    """Capture the hold when the merchant approves; void it if the sale is rejected or blocked."""
    p = db.one("merchant", "SELECT * FROM payments WHERE offer_id = ? AND status = 'authorized'", (offer_id,))
    if not p:
        return None
    result = adapters.visa_settle(p["auth_id"], action)
    db.execute("merchant", "UPDATE payments SET status = ?, order_id = ?, settled_at = ? WHERE payment_id = ?",
               (result["status"], order_id, db.now(), p["payment_id"]))
    return result


# --- Lose less ------------------------------------------------------------------------
def screen_return_risk(order_id=None):
    """Vouched gift orders = low risk; unvouched gift orders = medium."""
    where = "WHERE is_gift = 1" + (" AND order_id = ?" if order_id else "")
    orders = db.query("merchant", f"SELECT * FROM orders {where}", (order_id,) if order_id else ())
    for o in orders:
        o["return_risk"] = "low" if o["vouched"] else "medium"
        db.execute("merchant", "UPDATE orders SET return_risk = ? WHERE order_id = ?", (o["return_risk"], o["order_id"]))
    stats = db.query("merchant", "SELECT vouched, COUNT(*) AS n, SUM(returned) AS returned FROM orders "
                                 "WHERE is_gift = 1 GROUP BY vouched")
    return {"orders": orders, "gift_return_rates": {("vouched" if s["vouched"] else "unvouched"):
                                                    round(s["returned"] / s["n"], 2) for s in stats}}


def handle_storefront_request(agent_handle, ask, requests_per_min=1):
    """An agent tries to buy (or asks for a discount) at the storefront. No sale unless it is verified."""
    trust = score_agent_trust(agent_handle, requests_per_min, discount_first="% off" in ask.lower() or "discount" in ask.lower())
    outcome = "verified, can buy" if trust["verified"] else "not verified → no sale"
    db.log_event("backend", "storefront" if trust["verified"] else "no_sale", f"{agent_handle} asked '{ask}' → {outcome}")
    return {"ask": ask, **trust}


# --- Run leaner -----------------------------------------------------------------------
def forecast_from_vouches(safety_stock=SAFETY_STOCK):
    """Anonymous vouch counts per SKU/size vs. stock."""
    rows = db.query("merchant", "SELECT v.sku, v.size, SUM(v.wants) AS wants, SUM(v.owns) AS owns, "
                                "COALESCE(i.on_hand, 0) AS on_hand, c.name FROM vouch_signals v "
                                "LEFT JOIN inventory i ON i.sku = v.sku AND i.size = v.size "
                                "LEFT JOIN catalog c ON c.sku = v.sku GROUP BY v.sku, v.size ORDER BY wants DESC")
    for r in rows:
        r["suggested_qty"] = max(0, r["wants"] + safety_stock - r["on_hand"]) if r["wants"] > r["on_hand"] else 0
        r["note"] = ("already-owns answers outweigh wants: don't over-order" if r["owns"] >= r["wants"] and r["owns"]
                     else f"{r['wants']} vouched wants, {r['on_hand']} on hand" + (f": draft PO for {r['suggested_qty']}" if r["suggested_qty"] else ""))
    return rows


def draft_purchase_order(sku, size, quantity, reason=""):
    """Draft PO behind the approval gate."""
    po_id = db.execute("merchant", "INSERT INTO purchase_orders(sku, size, quantity, reason, status, created_at) "
                                   "VALUES (?,?,?,?,'draft',?)", (sku, size, quantity, reason, db.now()))
    approval_id = db.execute("backend", "INSERT INTO approvals(ts, kind, ref_id, summary, status) VALUES (?,?,?,?,'pending')",
                             (db.now(), "purchase_order", po_id, f"Restock: {quantity} × {_item({'sku': sku, 'size': size})} — {reason}"))
    adapters.ping_merchant(approval_id, f"Restock {quantity} × {_item({'sku': sku, 'size': size})}"
                           + (f" ({reason.split(':')[0]})" if reason else "") + ". Approve the PO?")
    return {"po_id": po_id, "approval_id": approval_id, "status": "draft"}


# --- Human gates (dashboard / phone) ---------------------------------------------------
def resolve_approval(approval_id, decision):
    a = db.one("backend", "SELECT * FROM approvals WHERE id = ?", (approval_id,))
    if not a or a["status"] != "pending":
        return {"error": "no pending approval with that id"}
    status = "approved" if decision == "approve" else "rejected"
    db.execute("backend", "UPDATE approvals SET status = ?, resolved_at = ? WHERE id = ?", (status, db.now(), approval_id))
    db.log_event("backend", f"approval.{status}", a["summary"])
    if a["kind"] == "purchase_order":
        db.execute("merchant", "UPDATE purchase_orders SET status = ? WHERE po_id = ?", (status, a["ref_id"]))
        return {"approval_id": approval_id, "status": status}
    offer = db.one("merchant", "SELECT * FROM offers WHERE offer_id = ?", (a["ref_id"],))
    if status == "rejected":
        db.execute("merchant", "UPDATE offers SET status = 'rejected' WHERE offer_id = ?", (offer["offer_id"],))
        _settle_payment(offer["offer_id"], "void")
        return {"approval_id": approval_id, "status": status}
    trust = verify_buyer(offer["customer_id"])  # the moment of sale: verify again
    if not trust["verified"]:
        db.execute("backend", "UPDATE approvals SET status = 'blocked' WHERE id = ?", (approval_id,))
        _settle_payment(offer["offer_id"], "void")
        return {"approval_id": approval_id, **_block_sale("resolve_approval", offer["customer_id"], trust, offer["offer_id"])}
    vouch = json.loads(offer["vouch_result"] or "null")
    vouched = int(bool(vouch and vouch.get("wants")))
    order_id = db.execute("merchant", "INSERT INTO orders(customer_id, sku, size, price, is_gift, vouched, offer_id, created_at) "
                                      "VALUES (?,?,?,?,1,?,?,?)",
                          (offer["customer_id"], offer["sku"], offer["size"], offer["final_price"], vouched, offer["offer_id"], db.now()))
    db.execute("merchant", "UPDATE inventory SET on_hand = on_hand - 1 WHERE sku = ? AND size = ?", (offer["sku"], offer["size"]))
    db.execute("merchant", "UPDATE offers SET status = 'ordered' WHERE offer_id = ?", (offer["offer_id"],))
    _settle_payment(offer["offer_id"], "capture", order_id)
    risk = screen_return_risk(order_id)["orders"][0]["return_risk"]
    send_message(offer["customer_id"], f"✅ Ordered: {emoji(offer['sku'])} {_item(offer)}, {_money(offer['final_price'])}.\n"
                                       "We'll text you when it ships.")
    return {"approval_id": approval_id, "status": status, "order_id": order_id, "return_risk": risk}


def _latest_sent_offer(customer_id):
    return db.one("merchant", "SELECT * FROM offers WHERE customer_id = ? AND status = 'sent' "
                              "ORDER BY offer_id DESC LIMIT 1", (customer_id,))


def _accept(offer, via):
    db.execute("merchant", "UPDATE offers SET status = 'accepted' WHERE offer_id = ?", (offer["offer_id"],))
    result = place_order(offer["offer_id"], accepted_via=via)
    return {"accepted": result.get("status") != "blocked", "offer_id": offer["offer_id"], **result}


def phone_reply(body, customer_id="cust_t"):
    """Inbound text from the customer. YES accepts their latest sent offer."""
    cust = db.one("merchant", "SELECT * FROM merchant_customers WHERE customer_id = ?", (customer_id,))
    db.execute("backend", "INSERT INTO messages(ts, direction, party, body) VALUES (?,?,?,?)",
               (db.now(), "in", cust["name"], body))
    offer = _latest_sent_offer(customer_id)
    if body.strip().upper().startswith("YES") and offer:
        return _accept(offer, "phone")
    return {"accepted": False}


def band_accept(agent_handle, person_said, offer_id=None):
    """The customer said yes to their own BAND agent, and the agent relays it from the consent room.
    The agent carries the person's yes; it can't accept on its own. Same gates as a texted YES:
    buyer verified again, payment held, merchant approves before any order exists."""
    cust = db.one("merchant", "SELECT * FROM merchant_customers WHERE agent_handle = ?", (agent_handle,))
    if not cust:
        db.log_event("backend", "no_sale", f"band_accept: {agent_handle} is not a customer's agent → no sale")
        return {"accepted": False, "error": f"{agent_handle} is not a known customer's agent"}
    if not (person_said or "").strip():
        db.log_event("backend", "no_sale", f"band_accept: {agent_handle} sent no words from {cust['name']} → no sale")
        return {"accepted": False, "error": "relay what the person said; an agent can't accept on its own"}
    offer = (db.one("merchant", "SELECT * FROM offers WHERE offer_id = ? AND customer_id = ? AND status = 'sent'",
                    (offer_id, cust["customer_id"])) if offer_id else _latest_sent_offer(cust["customer_id"]))
    if not offer:
        return {"accepted": False, "error": f"no open offer for {cust['name']}"}
    db.log_event("band", "room.message", f"{agent_handle}: {cust['name']} said \"{person_said.strip()}\" → accept offer #{offer['offer_id']}")
    return _accept(offer, "band")


TOOLS = {f.__name__: f for f in [
    get_top_customers, score_agent_trust, ask_customer_occasions, match_catalog, request_vouch,
    check_competitor_price, make_offer, send_message, place_order, screen_return_risk,
    handle_storefront_request, forecast_from_vouches, draft_purchase_order,
]}

# JSON Schema for each tool's input, in ZooWork custom_tools format (see custom_tools()).
_S, _I, _N, _B = {"type": "string"}, {"type": "integer"}, {"type": "number"}, {"type": "boolean"}
INPUT_SCHEMAS = {
    "get_top_customers": ({"limit": _I}, []),
    "score_agent_trust": ({"agent_handle": _S, "requests_per_min": _I, "discount_first": _B}, ["agent_handle"]),
    "ask_customer_occasions": ({"customer_id": _S}, ["customer_id"]),
    "match_catalog": ({"customer_id": _S, "budget": _N, "hints": _S, "k": _I}, ["customer_id"]),
    "request_vouch": ({"recipient_handle": _S, "skus": {"type": "array", "items": _S}}, ["recipient_handle", "skus"]),
    "check_competitor_price": ({"sku": _S}, ["sku"]),
    "make_offer": ({"customer_id": _S, "sku": _S, "occasion_ref": _S, "discount_pct": _N, "trust_score": _N,
                    "vouch_result": {"type": ["object", "null"]}, "size": _S, "budget": _N},
                   ["customer_id", "sku", "occasion_ref", "discount_pct"]),
    "send_message": ({"customer_id": _S, "body": _S, "offer_id": _I}, ["customer_id"]),
    "place_order": ({"offer_id": _I}, ["offer_id"]),
    "screen_return_risk": ({"order_id": _I}, []),
    "handle_storefront_request": ({"agent_handle": _S, "ask": _S, "requests_per_min": _I}, ["agent_handle", "ask"]),
    "forecast_from_vouches": ({"safety_stock": _I}, []),
    "draft_purchase_order": ({"sku": _S, "size": _S, "quantity": _I, "reason": _S}, ["sku", "size", "quantity"]),
}


def custom_tools():
    """Ready-to-paste `resource.custom_tools` declarations for the ZooWork merchant agent."""
    return [{"name": n, "description": " ".join((f.__doc__ or n).split()),
             "input_schema": {"type": "object", "properties": INPUT_SCHEMAS[n][0], "required": INPUT_SCHEMAS[n][1]}}
            for n, f in TOOLS.items()]


def call_tool(name, args, source="backend"):
    if name not in TOOLS:
        raise KeyError(f"unknown tool: {name}")
    result = TOOLS[name](**args)
    db.log_event(source, "tool", f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())})",
                 {"args": args, "result": result})
    return result
