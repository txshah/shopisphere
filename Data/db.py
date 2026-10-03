"""Per-owner SQLite stores.

Each owner gets its own .db file, so "every agent holds only its owner's data"
is literal: the merchant code never opens t_agent.db or sarah_agent.db.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent / "db"

SCHEMAS = {
    # Merchant (Trailhead): its own customers, catalog, orders, offers,
    # anonymous vouch counts, stock and purchase orders.
    "merchant": """
        CREATE TABLE IF NOT EXISTS merchant_customers(
            customer_id TEXT PRIMARY KEY, name TEXT, agent_handle TEXT, phone TEXT,
            order_count INTEGER, favorite_lines TEXT);
        CREATE TABLE IF NOT EXISTS catalog(
            sku TEXT PRIMARY KEY, name TEXT, line TEXT, price REAL, cost REAL,
            tags TEXT, stock INTEGER, competitor_query TEXT);
        CREATE TABLE IF NOT EXISTS orders(
            order_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT, sku TEXT,
            size TEXT, price REAL, is_gift INTEGER, vouched INTEGER,
            returned INTEGER DEFAULT 0, return_reason TEXT, return_risk TEXT,
            offer_id INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS offers(
            offer_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT,
            occasion_ref TEXT, sku TEXT, size TEXT, price REAL, discount_pct REAL,
            final_price REAL, vouch_result TEXT, trust_score REAL, reason TEXT,
            status TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS vouch_signals(
            sku TEXT, size TEXT, time_window TEXT, wants INTEGER, owns INTEGER,
            PRIMARY KEY(sku, size, time_window));
        CREATE TABLE IF NOT EXISTS inventory(
            sku TEXT, size TEXT, on_hand INTEGER, supplier TEXT, lead_time_days INTEGER,
            PRIMARY KEY(sku, size));
        CREATE TABLE IF NOT EXISTS purchase_orders(
            po_id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, size TEXT,
            quantity INTEGER, reason TEXT, status TEXT, created_at TEXT);
    """,
    # T's agent: occasions, gated per friend by sharing level.
    "t_agent": """
        CREATE TABLE IF NOT EXISTS t_occasions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, friend_handle TEXT, friend_name TEXT,
            occasion TEXT, occasion_date TEXT, budget REAL, hints TEXT,
            sharing_level TEXT);
    """,
    # Sarah's agent: her profile never leaves this file.
    "sarah_agent": """
        CREATE TABLE IF NOT EXISTS sarah_profile(
            id INTEGER PRIMARY KEY CHECK (id = 1), likes TEXT, owns TEXT,
            sizes TEXT, contributes_signals INTEGER);
    """,
    # Backend: trust service, event log, fake phone, approval gate mirror.
    "backend": """
        CREATE TABLE IF NOT EXISTS agent_passports(
            agent_handle TEXT PRIMARY KEY, owner TEXT, owner_phone_verified INTEGER,
            token TEXT, registered_band INTEGER, approved_contact INTEGER);
        CREATE TABLE IF NOT EXISTS trust_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent_handle TEXT,
            requests_per_min INTEGER, decision TEXT, score REAL, layers TEXT,
            reasons TEXT);
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, source TEXT, kind TEXT,
            summary TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, direction TEXT,
            party TEXT, body TEXT, offer_id INTEGER);
        CREATE TABLE IF NOT EXISTS approvals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, ref_id INTEGER,
            summary TEXT, status TEXT, resolved_at TEXT);
    """,
}


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect(owner):
    if owner not in SCHEMAS:
        raise ValueError(f"unknown owner store: {owner}")
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_DIR / f"{owner}.db")
    conn.row_factory = sqlite3.Row
    return conn


def query(owner, sql, args=()):
    with connect(owner) as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def one(owner, sql, args=()):
    rows = query(owner, sql, args)
    return rows[0] if rows else None


def execute(owner, sql, args=()):
    with connect(owner) as conn:
        return conn.execute(sql, args).lastrowid


def executemany(owner, sql, rows):
    with connect(owner) as conn:
        conn.executemany(sql, rows)


def tables(owner):
    """Every table in an owner's store, with all rows (for the ownership view)."""
    names = [r["name"] for r in query(owner, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {n: query(owner, f"SELECT * FROM {n}") for n in names}


def log_event(source, kind, summary, payload=None):
    execute("backend", "INSERT INTO events(ts, source, kind, summary, payload) VALUES (?,?,?,?,?)",
            (now(), source, kind, summary, json.dumps(payload, default=str) if payload is not None else None))


def reset():
    """Drop every store and recreate empty schemas."""
    DB_DIR.mkdir(exist_ok=True)
    for owner, schema in SCHEMAS.items():
        path = DB_DIR / f"{owner}.db"
        if path.exists():
            path.unlink()
        with connect(owner) as conn:
            conn.executescript(schema)
