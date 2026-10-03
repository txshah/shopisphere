"""Record the backup demo video: the real ops dashboard during a live run.

Needs ./live.sh running (backend + BAND + ZooWork). Uses Playwright's Chromium.
    python3 Demo/record.py            -> Demo/backup-run.webm
Every step is real: the ZooWork agent's tool calls, the BAND rooms, the approvals.
Captions are added on screen so the video stands on its own.
"""
import json
import shutil
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8787"
OUT = Path(__file__).resolve().parent / "backup-run.webm"


def state():
    return json.loads(urllib.request.urlopen(f"{BASE}/api/state", timeout=10).read())


def wait_for(pred, timeout, every=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = state()
        if pred(s):
            return s
        time.sleep(every)
    raise TimeoutError("step did not finish in time")


def caption(page, text):
    page.evaluate("""t => {
      let c = document.getElementById('rec-caption');
      if (!c) { c = document.createElement('div'); c.id = 'rec-caption';
        c.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:9999;max-width:900px;'
          + 'padding:14px 22px;border-radius:14px;background:rgba(20,22,24,.92);color:#fff;font:600 20px/1.35 system-ui;'
          + 'box-shadow:0 8px 30px rgba(0,0,0,.35);text-align:center';
        document.body.appendChild(c); }
      c.textContent = t; }""", text)


def approve_first(page, kind):
    s = state()
    a = next(a for a in s["approvals"] if a["status"] == "pending" and a["kind"] == kind)
    page.click(f'button[data-approval="{a["id"]}"][data-decision="approve"]')


def main():
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/demo/reset", data=b"{}", method="POST")).read()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=str(OUT.parent / "_video"),
                                  record_video_size={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(BASE)
        page.wait_for_timeout(2500)
        caption(page, "Shopisphere · Trailhead's ops view. Every agent here is live: ZooWork, BAND rooms, real competitor prices.")
        page.wait_for_timeout(5000)

        caption(page, "1 · The weekly ZooWork schedule fires. Trailhead's merchant agent starts its gifting run.")
        page.click("#runBtn")
        wait_for(lambda s: any(e["kind"] == "room.message" and "T's Gift Planner →" in e["summary"] for e in s["events"]), 120)
        caption(page, "2 · BAND consent room: T's own agent shares only what T allows. A birthday Oct 24, about $70.")
        wait_for(lambda s: any("Sarah's Gift Vouch →" in e["summary"] for e in s["events"]), 150)
        caption(page, "3 · BAND vouch room: Sarah's agent says she wants the vest in M and already owns the bottle.")
        wait_for(lambda s: s["offers"], 120)
        caption(page, "4 · Real prices: Fleet Feet sells the comparable vest at $80, we're $84, so loyal T gets 15% off: $71.40.")
        page.wait_for_timeout(6000)
        wait_for(lambda s: any(e["kind"] == "run.finished" and e["source"] == "zoowork" for e in s["events"]), 300)
        caption(page, "5 · ZooWork's Outcome rubric grades the run: verified, in stock, in budget, above margin, with a reason.")
        page.wait_for_timeout(7000)

        caption(page, "6 · Meanwhile an unverified bot tries to buy 3 vests at 15% off in the BAND storefront room. No sale.")
        page.click("#botBtn")
        page.wait_for_timeout(7000)

        caption(page, "7 · T says yes to their own agent. Agents narrow, people choose. A Visa payment hold is placed (mocked).")
        page.click("#bandYes")
        wait_for(lambda s: any(a["status"] == "pending" and a["kind"] == "order" for a in s["approvals"]), 30)
        page.wait_for_timeout(5000)

        caption(page, "8 · The merchant approves. Payment captured, order tagged vouched: low return risk.")
        approve_first(page, "order")
        page.wait_for_timeout(6000)

        caption(page, "9 · Restock from anonymous vouches: 9 wants for the vest in M, 3 on hand. Approve a PO for 8.")
        approve_first(page, "purchase_order")
        page.wait_for_timeout(6000)
        caption(page, "Fewer gift returns: gifts people want, no sales to unverified bots, the best price for loyal customers.")
        page.wait_for_timeout(6000)

        video = page.video.path()
        ctx.close()
        browser.close()
    shutil.move(video, OUT)
    shutil.rmtree(OUT.parent / "_video", ignore_errors=True)
    print(f"saved {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
