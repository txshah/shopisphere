"""Shopisphere backend: one small HTTP server (stdlib only) that

  - serves the dashboard (../Dashboard) at /
  - exposes the merchant tools at POST /api/tools/<name>  (ZooWork custom tools call these)
  - accepts events from any sponsor integration at POST /api/events
  - runs the mock flow, phone replies and approval gates for the demo

Run:  python3 Data/server.py        (PORT env var, default 8787)
"""
import hmac
import html
import json
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import adapters
import db
import orchestrator
import seed
import tools

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "Dashboard"


def state():
    """Everything the dashboard renders, in one payload."""
    q = db.query
    trust = q("backend", "SELECT * FROM trust_events WHERE id IN (SELECT MAX(id) FROM trust_events GROUP BY agent_handle) ORDER BY id DESC")
    for t in trust:
        t["layers"], t["reasons"] = json.loads(t["layers"]), json.loads(t["reasons"])
    offers = q("merchant", "SELECT o.*, c.name AS item FROM offers o JOIN catalog c USING(sku) ORDER BY offer_id DESC")
    gift_orders = q("merchant", "SELECT o.*, c.name AS item FROM orders o JOIN catalog c USING(sku) WHERE is_gift = 1 ORDER BY order_id DESC")
    for row in offers + gift_orders:
        row["emoji"] = tools.emoji(row["sku"])
    return {
        "modes": adapters.modes(),
        "customers": q("merchant", "SELECT * FROM merchant_customers ORDER BY order_count DESC"),
        "offers": offers,
        "gift_orders": gift_orders,
        "return_rates": q("merchant", "SELECT vouched, COUNT(*) AS n, SUM(returned) AS returned FROM orders WHERE is_gift = 1 GROUP BY vouched"),
        "forecast": tools.forecast_from_vouches(),
        "purchase_orders": q("merchant", "SELECT * FROM purchase_orders ORDER BY po_id DESC"),
        "trust": trust,
        "events": q("backend", "SELECT * FROM events ORDER BY id DESC LIMIT 80"),
        "messages": q("backend", "SELECT * FROM messages ORDER BY id"),
        "approvals": q("backend", "SELECT * FROM approvals ORDER BY id DESC"),
        "payments": q("merchant", "SELECT * FROM payments ORDER BY payment_id DESC"),
        "stores": {owner: {t: len(rows) for t, rows in db.tables(owner).items()} for owner in db.SCHEMAS},
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DASHBOARD_DIR), **kw)

    def log_message(self, fmt, *args):  # keep the terminal quiet for polling
        if not self.path.startswith("/api/state"):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Source")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _json(self, obj, code=200):
        data = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            return self._json(state())
        if path == "/api/tools":
            return self._json(tools.custom_tools())
        if m := re.fullmatch(r"/a/(\d+)/(approve|reject)/(\w+)", path):
            return self._approve_link(int(m[1]), m[2], m[3])
        if m := re.fullmatch(r"/api/stores/(\w+)", path):
            if m[1] not in db.SCHEMAS:
                return self._json({"error": "unknown store"}, 404)
            return self._json(db.tables(m[1]))
        return super().do_GET()

    def _approve_link(self, approval_id, decision, token):
        """One-tap approve/reject from the merchant's text message."""
        if not hmac.compare_digest(token, adapters.approval_token(approval_id)):
            result = {"error": "link expired or invalid"}
        else:
            result = tools.resolve_approval(approval_id, decision)
        text = result.get("error") or f"{result['status'].capitalize()}. The dashboard is updated."
        page = (f"<!doctype html><meta name=viewport content='width=device-width'>"
                f"<body style='font:20px system-ui;padding:24px'><h2>Trailhead</h2><p>{html.escape(text)}</p>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def do_POST(self):
        path, body = self.path.split("?")[0], self._body()
        try:
            if m := re.fullmatch(r"/api/tools/(\w+)", path):
                return self._json(tools.call_tool(m[1], body, self.headers.get("X-Source", "zoowork")))
            if path == "/api/events":
                db.log_event(body.get("source", "external"), body.get("kind", "event"),
                             body.get("summary", ""), body.get("payload"))
                return self._json({"ok": True})
            if path == "/api/demo/run":
                return self._json(adapters.zoowork_run(orchestrator.run_demo))
            if path == "/api/storefront/bot":
                ask, rpm = body.get("ask", "Buy 3 × TR-VEST at 15% off"), int(body.get("requests_per_min", 40))
                return self._json(adapters.band_storefront(ask, rpm, lambda: tools.call_tool(
                    "handle_storefront_request", {"agent_handle": "unverified-shopper", "ask": ask, "requests_per_min": rpm}, "dashboard")))
            if path == "/api/demo/reset":
                seed.seed()
                return self._json({"ok": True})
            if path == "/api/phone/reply":
                return self._json(tools.phone_reply(body.get("body", ""), body.get("customer_id", "cust_t")))
            if path == "/api/band/accept":
                return self._json(tools.band_accept(body.get("agent_handle", ""), body.get("person_said", ""),
                                                    body.get("offer_id")))
            if m := re.fullmatch(r"/api/approvals/(\d+)", path):
                return self._json(tools.resolve_approval(int(m[1]), body.get("decision", "approve")))
        except KeyError as e:
            return self._json({"error": str(e)}, 404)
        except Exception as e:
            db.log_event("backend", "error", f"{path}: {e}")
            return self._json({"error": str(e)}, 500)
        return self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    if not (db.DB_DIR / "merchant.db").exists():
        seed.seed()
    db.ensure()
    port = int(os.getenv("PORT", "8787"))
    print(f"Shopisphere backend on http://localhost:{port}  modes={adapters.modes()}")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
