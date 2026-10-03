"""Mock data for the demo: 1 merchant (~20 products, 6 customers), T's agent,
Sarah's agent, the backend passports and ~30 past anonymous vouches.

Run directly to reset and reseed:  python3 Data/seed.py
"""
import json

import db

# sku, name, line, price, cost, tags, stock, competitor_query (for Tavily)
CATALOG = [
    ("TR-VEST", "Trail Running Vest", "trail", 68, 34, "running,hydration,apparel", 9, "Salomon ADV Skin 5 running vest"),
    ("TR-BOTTLE", "Insulated Trail Bottle 32oz", "trail", 42, 15, "hydration,gift", 25, "Hydro Flask 32 oz Wide Mouth"),
    ("TR-LAMP", "Trail Headlamp 400", "trail", 55, 24, "night,running,gift", 14, "Black Diamond Spot 400 headlamp"),
    ("TR-CAP", "Trail Running Cap", "trail", 28, 9, "running,apparel", 30, None),
    ("TR-SOCKS", "Merino Trail Socks (3pk)", "trail", 24, 8, "running,apparel,gift", 40, None),
    ("TR-POLES", "Carbon Trekking Poles", "trail", 129, 61, "hiking", 6, None),
    ("TR-GAITERS", "Trail Gaiters", "trail", 32, 11, "running", 12, None),
    ("CP-MUG", "Enamel Camp Mug", "camp", 18, 5, "camp,gift", 50, None),
    ("CP-LANTERN", "Rechargeable Camp Lantern", "camp", 49, 20, "camp,night", 10, None),
    ("CP-HAMMOCK", "Ultralight Hammock", "camp", 79, 33, "camp,relax", 7, None),
    ("CP-STOVE", "Pocket Camp Stove", "camp", 59, 26, "camp,cooking", 8, None),
    ("CP-BLANKET", "Packable Down Blanket", "camp", 99, 45, "camp,gift", 5, None),
    ("CL-CHALK", "Chalk Bag + Chalk", "climb", 26, 8, "climbing,gift", 22, None),
    ("CL-BRUSH", "Boar-Hair Climbing Brush Set", "climb", 16, 4, "climbing", 18, None),
    ("CL-HARNESS", "All-Round Harness", "climb", 75, 36, "climbing", 6, None),
    ("WA-DRYBAG", "Roll-Top Dry Bag 20L", "water", 35, 12, "paddling,gift", 20, None),
    ("WA-TOWEL", "Quick-Dry Towel", "water", 29, 9, "travel,gift", 35, None),
    ("AP-FLEECE", "Grid Fleece Quarter-Zip", "apparel", 89, 38, "apparel,layering", 11, None),
    ("AP-BEANIE", "Merino Beanie", "apparel", 32, 10, "apparel,gift", 28, None),
    ("AP-SHELL", "Packable Rain Shell", "apparel", 139, 64, "apparel,rain", 4, None),
]

SIZED = {"TR-VEST", "AP-FLEECE", "AP-SHELL"}

CUSTOMERS = [
    # customer_id, name, agent_handle, phone, order_count, favorite_lines
    ("cust_t", "T", "t-gift-planner", "+15550100", 6, "trail"),
    ("cust_ana", "Ana", None, "+15550101", 4, "camp,water"),
    ("cust_raj", "Raj", None, "+15550102", 3, "climb"),
    ("cust_mei", "Mei", None, "+15550103", 3, "trail,apparel"),
    ("cust_lou", "Lou", None, "+15550104", 2, "camp"),
    ("cust_kim", "Kim", None, "+15550105", 1, "apparel"),
]

# customer_id, sku, size, price, is_gift, vouched, returned, return_reason
ORDERS = [
    ("cust_t", "TR-CAP", "OS", 28, 0, 0, 0, None),
    ("cust_t", "TR-SOCKS", "OS", 24, 0, 0, 0, None),
    ("cust_t", "TR-GAITERS", "OS", 32, 0, 0, 0, None),
    ("cust_t", "TR-POLES", "OS", 129, 0, 0, 0, None),
    ("cust_t", "TR-SOCKS", "OS", 24, 1, 0, 1, "already owned"),
    ("cust_t", "TR-LAMP", "OS", 55, 0, 0, 0, None),
    ("cust_ana", "CP-MUG", "OS", 18, 1, 0, 0, None),
    ("cust_ana", "CP-BLANKET", "OS", 99, 1, 0, 1, "not their style"),
    ("cust_ana", "WA-DRYBAG", "OS", 35, 0, 0, 0, None),
    ("cust_ana", "CP-LANTERN", "OS", 49, 1, 1, 0, None),
    ("cust_raj", "CL-CHALK", "OS", 26, 0, 0, 0, None),
    ("cust_raj", "CL-HARNESS", "OS", 75, 1, 0, 1, "wrong size"),
    ("cust_raj", "CL-BRUSH", "OS", 16, 0, 0, 0, None),
    ("cust_mei", "AP-FLEECE", "S", 89, 1, 0, 1, "too small"),
    ("cust_mei", "TR-VEST", "M", 68, 1, 1, 0, None),
    ("cust_mei", "TR-BOTTLE", "OS", 42, 1, 1, 0, None),
    ("cust_lou", "CP-STOVE", "OS", 59, 1, 0, 0, None),
    ("cust_lou", "CP-HAMMOCK", "OS", 79, 1, 0, 1, "duplicate gift"),
    ("cust_kim", "AP-SHELL", "L", 139, 1, 0, 1, "wrong color"),
    ("cust_kim", "AP-BEANIE", "OS", 32, 1, 0, 0, None),
    ("cust_mei", "TR-SOCKS", "OS", 24, 1, 0, 0, None),
    ("cust_ana", "WA-TOWEL", "OS", 29, 1, 0, 0, None),
    ("cust_lou", "CP-MUG", "OS", 18, 1, 0, 0, None),
    ("cust_raj", "CL-CHALK", "OS", 26, 1, 1, 0, None),
]

# Anonymous, aggregated: (sku, size, time_window, wants, owns). Sums to ~30 past vouches.
VOUCH_SIGNALS = [
    ("TR-VEST", "M", "2026-Q4", 8, 0),
    ("TR-VEST", "L", "2026-Q4", 3, 0),
    ("TR-VEST", "S", "2026-Q4", 2, 1),
    ("TR-BOTTLE", "OS", "2026-Q4", 2, 6),
    ("TR-LAMP", "OS", "2026-Q4", 4, 1),
    ("AP-FLEECE", "M", "2026-Q4", 2, 0),
    ("CP-MUG", "OS", "2026-Q4", 1, 0),
]

T_OCCASIONS = [
    # friend_handle, friend_name, occasion, date, budget, hints, sharing_level
    ("sarah-gift-vouch", "Sarah", "birthday", "2026-10-24", 60, "into trail running", "occasion_budget"),
    ("jo-no-agent", "Jo", "anniversary", "2026-11-12", 80, "likes camping", "occasion_only"),
    ("sam-gift-vouch", "Sam", "housewarming", "2026-12-05", 50, "new climber", "occasion_budget_hints"),
]

SARAH_PROFILE = {
    "likes": ["TR-VEST", "trail running", "bright colors"],
    "owns": ["TR-BOTTLE"],
    "sizes": {"apparel": "M"},
    "contributes_signals": 1,
}

PASSPORTS = [
    # handle, owner, phone verified, token, registered on BAND, approved contact
    ("t-gift-planner", "T", 1, "pp_signed_t_7f3a", 1, 1),
    ("sarah-gift-vouch", "Sarah", 1, "pp_signed_sarah_91c2", 1, 1),
    ("unverified-shopper", None, 0, None, 0, 0),
]


def seed():
    db.reset()
    db.executemany("merchant", "INSERT INTO catalog VALUES (?,?,?,?,?,?,?,?)", CATALOG)
    db.executemany("merchant", "INSERT INTO merchant_customers VALUES (?,?,?,?,?,?)", CUSTOMERS)
    db.executemany(
        "merchant",
        "INSERT INTO orders(customer_id, sku, size, price, is_gift, vouched, returned, return_reason, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,'2026-09-01')",
        ORDERS,
    )
    db.executemany("merchant", "INSERT INTO vouch_signals VALUES (?,?,?,?,?)", VOUCH_SIGNALS)

    inventory = []
    for sku, *_rest, stock, _q in CATALOG:
        if sku in SIZED:
            on_hand = {"TR-VEST": {"S": 3, "M": 3, "L": 3}}.get(sku, {"S": 4, "M": 4, "L": 3})
            inventory += [(sku, s, n, "Summit Supply Co", 14) for s, n in on_hand.items()]
        else:
            inventory.append((sku, "OS", stock, "Summit Supply Co", 10))
    db.executemany("merchant", "INSERT INTO inventory VALUES (?,?,?,?,?)", inventory)

    db.executemany(
        "t_agent",
        "INSERT INTO t_occasions(friend_handle, friend_name, occasion, occasion_date, budget, hints, sharing_level) "
        "VALUES (?,?,?,?,?,?,?)",
        T_OCCASIONS,
    )
    p = SARAH_PROFILE
    db.execute("sarah_agent", "INSERT INTO sarah_profile VALUES (1,?,?,?,?)",
               (json.dumps(p["likes"]), json.dumps(p["owns"]), json.dumps(p["sizes"]), p["contributes_signals"]))
    db.executemany("backend", "INSERT INTO agent_passports VALUES (?,?,?,?,?,?)", PASSPORTS)
    db.log_event("backend", "seed", "Stores reset and seeded with mock data")


if __name__ == "__main__":
    seed()
    print(f"Seeded stores in {db.DB_DIR}")
