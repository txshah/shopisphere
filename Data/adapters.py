"""Outbound calls to sponsor tools. One function per external dependency.

A sponsor is "switched on" when DEMO_MODE=0 (all of them) or its name is in
LIVE (e.g. LIVE=tavily,gmail keeps the rest mocked). A switched-on adapter calls
its *_BRIDGE_URL, or for Tavily calls the API directly with the TAV key.
Otherwise (or if the live call fails) it uses the mock, so the demo never breaks.
Teammates plug in by running a small HTTP bridge that accepts the JSON shown
in each function and returns the same shape the mock returns.
"""
import hashlib
import hmac
import importlib.util
import json
import os
import smtplib
import threading
import uuid
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

import db
import mock_agents


def _load_dotenv(path=Path(__file__).resolve().parent.parent / ".env"):
    """Fill missing env vars from the repo-root .env (gitignored)."""
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


_load_dotenv()
DEMO_MODE = os.getenv("DEMO_MODE", "1") != "0"
LIVE = {s.strip().lower() for s in os.getenv("LIVE", "").split(",") if s.strip()}
MOCK_DIR = Path(__file__).resolve().parent / "mock"
TAVILY_DIR = Path(__file__).resolve().parent.parent / "Tavily"


def _switched_on(sponsor):
    return not DEMO_MODE or sponsor in LIVE


# Where each bridge listens when its env var isn't set (the scripts in Band/ and Zooworks/ default to these).
BRIDGE_DEFAULTS = {"BAND_BRIDGE_URL": "http://localhost:9001", "ZOOWORK_BRIDGE_URL": "http://localhost:8788"}


def _bridge(env_var):
    url = os.getenv(env_var) or BRIDGE_DEFAULTS.get(env_var)
    return url.rstrip("/") if url and _switched_on(env_var.split("_")[0].lower()) else None


# BAND room turns are LLM replies (about 5-25s each), so they get a longer wait than the other bridges.
TIMEOUTS = {"band": 90}


def _post(url, body, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _call(source, env_var, path, body, mock):
    url = _bridge(env_var)
    if url:
        try:
            result = _post(url + path, body, TIMEOUTS.get(source, 20))
            db.log_event(source, "live", f"{path} via {url}", {"request": body, "response": result})
            return result
        except Exception as e:  # fall back to mock, per plan.md contingencies
            db.log_event(source, "fallback", f"{path} live call failed ({e}); using mock")
    result = mock()
    db.log_event(source, "mock", path, {"request": body, "response": result})
    return result


def modes():
    return {
        "demo_mode": DEMO_MODE,
        "zoowork": "live" if _bridge("ZOOWORK_BRIDGE_URL") else "local stand-in",
        "band": "live" if _bridge("BAND_BRIDGE_URL") else "mock",
        "tavily": "live" if _bridge("TAVILY_BRIDGE_URL") or _tavily_direct() else "real prices, Oct 3 snapshot",
        "sms": "live" if _bridge("SMS_BRIDGE_URL") else "fake phone",
        "merchant_ping": "gmail → " + MERCHANT_SMS_TO if _gmail_live() else "dashboard only",
        "payments": "visa (mock)",
    }


# --- BAND: consent room (T's agent) -------------------------------------------
def band_share_occasions(customer_handle):
    """POST {BAND_BRIDGE_URL}/share_occasions {customer_handle} -> [{friend_handle, occasion, occasion_date, budget?, hints?, sharing_level}]"""
    return _call("band", "BAND_BRIDGE_URL", "/share_occasions", {"customer_handle": customer_handle},
                 mock_agents.t_share_occasions)


# --- BAND: vouch room (recipient's agent) -------------------------------------
def band_vouch_for(recipient_handle, sku):
    """POST {BAND_BRIDGE_URL}/vouch_for {recipient_handle, sku} -> {sku, wants, owns, confidence, size, contribute_signal}"""
    def mock():
        agent = mock_agents.RECIPIENT_AGENTS.get(recipient_handle)
        return agent(sku) if agent else None  # no agent -> unvouched fallback
    return _call("band", "BAND_BRIDGE_URL", "/vouch_for", {"recipient_handle": recipient_handle, "sku": sku}, mock)


def band_vouch_batch(recipient_handle, skus):
    """POST {BAND_BRIDGE_URL}/vouch_batch {recipient_handle, skus} -> [answer per sku] or null if no agent.
    One room turn for all candidates instead of one per SKU."""
    def mock():
        agent = mock_agents.RECIPIENT_AGENTS.get(recipient_handle)
        return [agent(sku) for sku in skus] if agent else None
    return _call("band", "BAND_BRIDGE_URL", "/vouch_batch", {"recipient_handle": recipient_handle, "skus": skus}, mock)


# --- BAND: storefront room (the unverified bot) --------------------------------
def band_storefront(ask, requests_per_min, local):
    """POST {BAND_BRIDGE_URL}/storefront {ask, requests_per_min}: the bot asks in a real room and the
    bridge answers with the backend's verification. Mock: run the same check locally."""
    return _call("band", "BAND_BRIDGE_URL", "/storefront", {"ask": ask, "requests_per_min": requests_per_min}, local)


# --- ZooWork: the merchant agent's weekly run ------------------------------------
def zoowork_run(local):
    """POST {ZOOWORK_BRIDGE_URL}/run: fire the real ZooWork schedule (Zooworks/merchant/bridge.mjs).
    The agent then calls our tools through /api/tools/<name>. Mock: the local orchestrator."""
    return _call("zoowork", "ZOOWORK_BRIDGE_URL", "/run", {}, local)


# --- Tavily: competitor price check --------------------------------------------
def _tavily_direct():
    """Live Tavily without a bridge: switched on, no bridge URL, and a TAV key in .env."""
    return _switched_on("tavily") and not os.getenv("TAVILY_BRIDGE_URL") and bool(os.getenv("TAV"))


def _tavily_search_prices(query, our_price):
    spec = importlib.util.spec_from_file_location("tavily_prices", TAVILY_DIR / "check_competitor_price.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.search_prices(query, our_price)


def tavily_competitor_prices(sku, query, our_price):
    """POST {TAVILY_BRIDGE_URL}/competitor_prices {sku, query, our_price} -> {competitors: [{retailer, price, url}], label?}
    With no bridge but a TAV key, searches the web through Tavily directly (Tavily/check_competitor_price.py)."""
    def mock():
        cached = json.loads((MOCK_DIR / "competitor_prices.json").read_text())
        return {"competitors": cached.get(sku, []), "source": "snapshot 2026-10-03"}
    if _tavily_direct():
        try:
            r = _tavily_search_prices(query, our_price)
            db.log_event("tavily", "live", r["label"], {"query": query, "response": r})
            return {"competitors": r["competitors"], "label": r["label"]}
        except Exception as e:
            db.log_event("tavily", "fallback", f"Tavily search failed ({e}); using mock")
            result = mock()
            db.log_event("tavily", "mock", "/competitor_prices", {"response": result})
            return result
    return _call("tavily", "TAVILY_BRIDGE_URL", "/competitor_prices", {"sku": sku, "query": query, "our_price": our_price}, mock)


# --- Payments: agent payment network (always mocked) ---------------------------
# Stands in for Visa Intelligent Commerce / Trusted Agent Protocol: the buyer's yes
# gets a payment token scoped to this merchant and amount, the network places a hold,
# and the hold is captured only when the merchant approves (voided otherwise).
# No card data exists anywhere in this repo.
def visa_authorize(offer_id, amount, accepted_via):
    result = {"network": "visa (mock)", "token": "vtok_" + uuid.uuid4().hex[:12],
              "auth_id": "auth_" + uuid.uuid4().hex[:10], "amount": amount, "status": "authorized",
              "scope": f"Trailhead · offer #{offer_id} · max {amount:.2f} USD · one use"}
    db.log_event("payments", "mock", f"Visa (mock) hold of ${amount:.2f} for offer #{offer_id}, yes via {accepted_via}", result)
    return result


def visa_settle(auth_id, action):
    """action: 'capture' (merchant approved) or 'void' (rejected or blocked)."""
    status = "captured" if action == "capture" else "voided"
    db.log_event("payments", "mock", f"Visa (mock) {auth_id} {status}")
    return {"auth_id": auth_id, "status": status}


# --- Messaging: Twilio SMS or the fake phone panel ----------------------------
def send_sms(to, body):
    """POST {SMS_BRIDGE_URL}/send {to, body} -> {status}. The fake phone always mirrors it."""
    return _call("sms", "SMS_BRIDGE_URL", "/send", {"to": to, "body": body},
                 lambda: {"status": "delivered to fake phone"})


# --- Merchant ping: Gmail → carrier email-to-SMS gateway ------------------------
# Approval requests reach the merchant's phone as a real text. Live when DEMO_MODE=0
# and GMAIL_APP_PASSWORD is set; otherwise the dashboard approvals panel is the only gate.
GMAIL_FROM = os.getenv("GMAIL_FROM", "tveshashah13@gmail.com")
MERCHANT_SMS_TO = os.getenv("MERCHANT_SMS_TO", "6477095511@msg.telus.com")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")   # ngrok / tunnel URL, so the approve link works from the phone
_LINK_SECRET = os.getenv("APPROVE_LINK_SECRET") or os.urandom(16).hex()


def _gmail_live():
    return _switched_on("gmail") and bool(os.getenv("GMAIL_APP_PASSWORD"))


def approval_token(approval_id):
    return hmac.new(_LINK_SECRET.encode(), str(approval_id).encode(), hashlib.sha256).hexdigest()[:12]


def approval_link(approval_id, decision="approve"):
    if not PUBLIC_URL:
        return None
    return f"{PUBLIC_URL}/a/{approval_id}/{decision}/{approval_token(approval_id)}"


def _send_gmail(to, subject, body):
    msg = MIMEText(body)
    msg["From"], msg["To"], msg["Subject"] = GMAIL_FROM, to, subject
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
        s.login(GMAIL_FROM, os.environ["GMAIL_APP_PASSWORD"])
        s.sendmail(GMAIL_FROM, to, msg.as_string())


def ping_merchant(approval_id, summary):
    """Text the merchant about a pending approval. Sends in the background so tools never wait on SMTP."""
    link = approval_link(approval_id)
    body = f"Trailhead: {summary}" + (f"\nApprove: {link}" if link else "\nApprove on the dashboard.")
    if not _gmail_live():
        db.log_event("ping", "mock", f"merchant ping (dashboard only): {summary}", {"body": body})
        return {"status": "dashboard only"}

    def send():
        try:
            _send_gmail(MERCHANT_SMS_TO, "Approval needed", body)
            db.log_event("ping", "live", f"texted merchant via Gmail: {summary}", {"to": MERCHANT_SMS_TO, "body": body})
        except Exception as e:
            db.log_event("ping", "fallback", f"Gmail send failed ({e}); approve on the dashboard")

    threading.Thread(target=send, daemon=True).start()
    return {"status": "sending", "to": MERCHANT_SMS_TO}
