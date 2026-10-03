"""check_competitor_price: Tavily-backed competitor price check for the merchant agent.

Stdlib only. Reads TAV from ../.env. Usage:
    python3 check_competitor_price.py "Black Diamond Spot 400 headlamp" 64
Set DEMO_MODE=1 to answer from competitor_prices_cache.json without calling Tavily.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / "competitor_prices_cache.json"

# Resale, social, and review sites quote used, foreign or MSRP prices, not a competitor's live offer.
EXCLUDE = [
    "ebay.com", "poshmark.com", "mercari.com", "wornwear.patagonia.com", "reddit.com",
    "youtube.com", "pinterest.com", "pinterest.ca", "klarna.com", "pricehistory.app",
    "cleverhiker.com", "treelinereview.com", "outdoorgearlab.com", "switchbacktravel.com",
    "trailspace.com", "engearment.com", "corporategift.com",
]
PRICE = re.compile(r"(?<![\w.])(?:US)?\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)")
# Words just before a dollar amount that mean it is a threshold or discount, not a price.
NOT_A_PRICE = re.compile(r"(over|orders?|above|save|off|up to|spend|min(imum)?|under|reward)\W*$", re.I)
# Category, search and sale pages list many products; their prices belong to other items.
LISTING_URL = re.compile(r"/(c|b|s|shop|collections|category|categories|search|sale|deals)(/|\?|$)|[?&](k|q|query)=", re.I)


def load_key():
    if os.environ.get("TAV"):
        return os.environ["TAV"]
    for line in (HERE.parent / ".env").read_text().splitlines():
        if line.startswith("TAV="):
            return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("TAV not set")


def tavily_search(query):
    body = {
        "query": query,
        "search_depth": "basic",
        "country": "united states",
        "max_results": 8,
        "include_answer": True,
        "exclude_domains": EXCLUDE,
    }
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def prices_in(text):
    out = []
    for m in PRICE.finditer(text):
        if NOT_A_PRICE.search(text[max(0, m.start() - 20):m.start()]):
            continue
        out.append(float(m.group(1).replace(",", "")))
    return out


def check_competitor_price(product, our_price):
    if os.environ.get("DEMO_MODE") == "1":
        return json.loads(CACHE.read_text())[product]

    data = tavily_search(f"{product} price")
    # Keep amounts within a plausible band of our price; drops shipping thresholds and bundle totals.
    lo, hi = our_price * 0.5, our_price * 2.0
    offers = {}
    for r in data["results"]:
        if LISTING_URL.search(r["url"]):
            continue
        domain = urllib.parse.urlparse(r["url"]).netloc.removeprefix("www.")
        # On a product page the first plausible amount is the item's own price.
        ps = [p for p in prices_in(r["content"]) if lo <= p <= hi]
        if ps and (domain not in offers or ps[0] < offers[domain]["price"]):
            offers[domain] = {"retailer": domain, "price": ps[0], "url": r["url"]}

    offers = sorted(offers.values(), key=lambda o: o["price"])
    lowest = offers[0]["price"] if offers else None
    label = (
        f"Tavily: {product} at {len(offers)} competitors, lowest ${lowest:.2f}"
        if offers else f"Tavily: no competitor price found for {product}"
    )
    return {
        "product": product,
        "our_price": our_price,
        "lowest_competitor": lowest,
        "gap": round(our_price - lowest, 2) if lowest else None,
        "competitors": offers,
        "tavily_answer": data.get("answer"),
        "label": label,
        "source": "tavily_live",
    }


if __name__ == "__main__":
    print(json.dumps(check_competitor_price(sys.argv[1], float(sys.argv[2])), indent=2))
