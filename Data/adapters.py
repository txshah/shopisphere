"""Outbound calls to sponsor tools. One function per external dependency.

Each adapter goes live when its *_BRIDGE_URL env var is set and DEMO_MODE=0;
otherwise (or if the live call fails) it uses the mock, so the demo never breaks.
Teammates plug in by running a small HTTP bridge that accepts the JSON shown
in each function and returns the same shape the mock returns.
"""
import hashlib
import hmac
import json
import os
import smtplib
import threading
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
MOCK_DIR = Path(__file__).resolve().parent / "mock"


def _bridge(env_var):
    url = os.getenv(env_var)
    return None if DEMO_MODE or not url else url.rstrip("/")


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def _call(source, env_var, path, body, mock):
    url = _bridge(env_var)
    if url:
        try:
            result = _post(url + path, body)
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
        "band": "live" if _bridge("BAND_BRIDGE_URL") else "mock",
        "tavily": "live" if _bridge("TAVILY_BRIDGE_URL") else "mock",
        "sms": "live" if _bridge("SMS_BRIDGE_URL") else "fake phone",
        "merchant_ping": "gmail → " + MERCHANT_SMS_TO if _gmail_live() else "dashboard only",
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


# --- Tavily: competitor price check --------------------------------------------
def tavily_competitor_prices(sku, query, our_price):
    """POST {TAVILY_BRIDGE_URL}/competitor_prices {sku, query, our_price} -> {competitors: [{retailer, price, url}], label?}"""
    def mock():
        cached = json.loads((MOCK_DIR / "competitor_prices.json").read_text())
        return {"competitors": cached.get(sku, [])}
    return _call("tavily", "TAVILY_BRIDGE_URL", "/competitor_prices", {"sku": sku, "query": query, "our_price": our_price}, mock)


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
    return not DEMO_MODE and bool(os.getenv("GMAIL_APP_PASSWORD"))


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
