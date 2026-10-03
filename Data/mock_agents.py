"""Stand-ins for the BAND customer agents, used when no live BAND bridge is set.

Each function reads ONLY its owner's store, and returns only what that owner
allows. The real versions live in Band/ and must return the same shapes.
"""
import json

import db

SHARING_FIELDS = {
    "occasion_only": ["friend_handle", "occasion", "occasion_date"],
    "occasion_budget": ["friend_handle", "occasion", "occasion_date", "budget"],
    "occasion_budget_hints": ["friend_handle", "occasion", "occasion_date", "budget", "hints"],
}


def t_share_occasions():
    """T's Gift Planner: upcoming occasions, trimmed to each friend's sharing level."""
    rows = db.query("t_agent", "SELECT * FROM t_occasions ORDER BY occasion_date")
    return [
        {k: r[k] for k in SHARING_FIELDS[r["sharing_level"]]} | {"sharing_level": r["sharing_level"]}
        for r in rows
    ]


def sarah_vouch_for(sku):
    """Sarah's Gift Vouch: wants / owns / confidence (+ size if she wants it). Nothing else."""
    p = db.one("sarah_agent", "SELECT * FROM sarah_profile WHERE id = 1")
    likes, owns, sizes = json.loads(p["likes"]), json.loads(p["owns"]), json.loads(p["sizes"])
    if sku in owns:
        return {"sku": sku, "wants": False, "owns": True, "confidence": 0.9, "size": None,
                "contribute_signal": bool(p["contributes_signals"])}
    wants = sku in likes
    return {"sku": sku, "wants": wants, "owns": False, "confidence": 0.9 if wants else 0.5,
            "size": sizes.get("apparel") if wants else None,
            "contribute_signal": bool(p["contributes_signals"])}


RECIPIENT_AGENTS = {"sarah-gift-vouch": sarah_vouch_for}
