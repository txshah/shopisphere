"""BAND bridge: the backend's door into real BAND rooms.

Posts as Trailhead Merchant (REST only, no LLM process needed) into three rooms:
  consent    Trailhead Merchant + T's Gift Planner     occasions T allows us to see (new room per ask)
  vouch      Trailhead Merchant + Sarah's Gift Vouch   wants / owns / confidence per SKU (new room per ask)
  storefront Trailhead Merchant + Unverified Shopper   a bot tries to buy and gets no sale

Implements the contract in Data/adapters.py (Band/Rules.md):
  POST /share_occasions {customer_handle}           -> [{friend_handle, occasion, occasion_date, ...}]
  POST /vouch_batch     {recipient_handle, skus}    -> [{sku, wants, owns, confidence, size, contribute_signal}] | null
  POST /vouch_for       {recipient_handle, sku}     -> {sku, ...} | null
  POST /storefront      {ask, requests_per_min}     -> the backend's verification result
Every room message is mirrored to the dashboard via POST /api/events.

Run (from the repo root, after Band/shopisphere/agents.py is up):
    uv run --project Band/tom-jerry-agents python Band/shopisphere/bridge.py      # :9001
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml
from band.client.rest import ChatMessageRequest, ChatMessageRequestMentionsItem, RestClient
from band_rest import ChatRoomRequest, ParticipantRequest

HERE = Path(__file__).resolve().parent
CFG = yaml.safe_load((HERE / "agent_config.yaml").read_text())
ROOMS_FILE = HERE / "rooms.json"          # room ids, reused across runs (gitignored)
BAND_URL = "https://app.band.ai"
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8787")
TIMEOUT = float(os.getenv("BAND_REPLY_TIMEOUT", "120"))

merchant = RestClient(api_key=CFG["merchant_agent"]["api_key"], base_url=BAND_URL)
shopper = RestClient(api_key=CFG["shopper_agent"]["api_key"], base_url=BAND_URL)
MERCHANT_ID = CFG["merchant_agent"]["agent_id"]

# Backend handles (Data/seed.py) -> BAND agents. A handle missing here has no agent.
AGENTS = {
    "t-gift-planner": CFG["t_agent"],
    "sarah-gift-vouch": CFG["sarah_agent"],
    "unverified-shopper": CFG["shopper_agent"],
}
ROOM_TITLES = {
    "consent": "Trailhead × T's Gift Planner · consent",
    "vouch": "Trailhead × Sarah's Gift Vouch · vouch",
    "storefront": "Trailhead storefront",
}
_lock = threading.Lock()


def dashboard(summary, payload=None):
    body = json.dumps({"source": "band", "kind": "room.message", "summary": summary, "payload": payload}).encode()
    req = urllib.request.Request(f"{BACKEND}/api/events", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass  # the dashboard log is nice to have, never a reason to fail a room call


def backend_tool(name, args):
    req = urllib.request.Request(f"{BACKEND}/api/tools/{name}", data=json.dumps(args).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Source": "band"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def room(kind, member, fresh=False):
    """Create the room as Trailhead Merchant and add the member. Consent and vouch asks get a fresh room
    each time, so the customer's agent answers from its tool, not from an earlier conversation."""
    with _lock:
        rooms = json.loads(ROOMS_FILE.read_text()) if ROOMS_FILE.exists() else {}
        if fresh or kind not in rooms:
            title = ROOM_TITLES[kind] + (f" · {time.strftime('%b %d %H:%M')}" if fresh else "")
            rid = merchant.agent_api_chats.create_agent_chat(chat=ChatRoomRequest(title=title)).data.id
            merchant.agent_api_participants.add_agent_chat_participant(rid, participant=ParticipantRequest(participant_id=member["agent_id"]))
            rooms[kind] = rid
            ROOMS_FILE.write_text(json.dumps(rooms, indent=2))
        return rooms[kind]


def post(client, room_id, to, text):
    client.agent_api_messages.create_agent_chat_message(
        room_id, message=ChatMessageRequest(content=f"@{to['name']} {text}",
                                            mentions=[ChatMessageRequestMentionsItem(id=to["agent_id"], name=to["name"])]))


def context_ids(room_id):
    return {m.id for m in merchant.agent_api_context.get_agent_chat_context(room_id, limit=100).data}


def wait_reply(room_id, sender_id, before):
    """Poll the room until the member posts a text message we haven't seen."""
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(1.5)
        for m in merchant.agent_api_context.get_agent_chat_context(room_id, limit=100).data:
            if m.id not in before and m.sender_id == sender_id and m.message_type == "text":
                return m.content or ""
    raise TimeoutError(f"no reply in {TIMEOUT:.0f}s")


def parse_json(text):
    body = re.sub(r"@\[\[[^\]]+\]\]", "", text)  # strip @[[uuid]] mention tokens
    m = re.search(r"(\[.*\]|\{.*\})", body, re.S)
    if not m:
        raise ValueError(f"no JSON in reply: {body[:200]}")
    return json.loads(m.group(1))


def ask(kind, member, text, label):
    rid = room(kind, member, fresh=True)
    before = context_ids(rid)
    t0 = time.monotonic()
    post(merchant, rid, member, text)
    dashboard(f"Trailhead Merchant → {label}: {text}", {"room_id": rid})
    reply = wait_reply(rid, member["agent_id"], before)
    dashboard(f"{label} → Trailhead Merchant ({time.monotonic() - t0:.0f}s): {re.sub(r'@\[\[[^\]]+\]\]', '', reply).strip()[:240]}",
              {"room_id": rid})
    return parse_json(reply)


# --- Endpoints -----------------------------------------------------------------------
def share_occasions(body):
    member = AGENTS.get(body.get("customer_handle"))
    if not member:
        return []
    return ask("consent", member, "Trailhead Merchant here. Any upcoming gift occasions T is OK sharing with us? "
                                  "Reply with the JSON from share_occasions.", "T's Gift Planner")


def vouch_batch(body):
    member = AGENTS.get(body.get("recipient_handle"))
    if not member or body.get("recipient_handle") != "sarah-gift-vouch":
        return None  # no agent -> the backend sends an unvouched offer
    skus = ", ".join(body["skus"])
    answers = ask("vouch", member, f"Trailhead Merchant here. A friend is considering a gift. Would Sarah want any of these? {skus}",
                  "Sarah's Gift Vouch")
    return answers if isinstance(answers, list) else [answers]


def vouch_for(body):
    answers = vouch_batch({"recipient_handle": body.get("recipient_handle"), "skus": [body["sku"]]})
    return answers[0] if answers else None


def storefront(body):
    """The bot asks to buy in the storefront room; Trailhead verifies it in the backend and answers there."""
    bot, rid = AGENTS["unverified-shopper"], room("storefront", AGENTS["unverified-shopper"])
    ask_text = body.get("ask", "Buy 3 × TR-VEST at 15% off")
    rpm = int(body.get("requests_per_min", 40))
    post(shopper, rid, CFG["merchant_agent"], ask_text)
    dashboard(f"Unverified Shopper → Trailhead Merchant: {ask_text} ({rpm} req/min)", {"room_id": rid})
    result = backend_tool("handle_storefront_request", {"agent_handle": "unverified-shopper", "ask": ask_text, "requests_per_min": rpm})
    answer = ("Verified, you can buy." if result.get("verified")
              else "Not verified, so no sale. " + "; ".join(result.get("reasons", [])))
    post(merchant, rid, bot, answer)
    dashboard(f"Trailhead Merchant → Unverified Shopper: {answer}", {"room_id": rid})
    return result


ROUTES = {"/share_occasions": share_occasions, "/vouch_batch": vouch_batch, "/vouch_for": vouch_for, "/storefront": storefront}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"ok": True, "rooms": json.loads(ROOMS_FILE.read_text()) if ROOMS_FILE.exists() else {}})

    def do_POST(self):
        fn = ROUTES.get(self.path.split("?")[0])
        if not fn:
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        try:
            self._send(200, fn(body))
        except Exception as e:  # the backend falls back to its mock on any non-200
            dashboard(f"BAND bridge error on {self.path}: {e}")
            self._send(502, {"error": str(e)})


if __name__ == "__main__":
    port = int(os.getenv("BAND_BRIDGE_PORT", "9001"))
    print(f"BAND bridge on http://localhost:{port} as Trailhead Merchant ({MERCHANT_ID})")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
