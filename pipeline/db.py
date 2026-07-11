"""SQLite storage + sanitized JSON export for the dashboard.

The db is committed to the repo (zero infra, git history = audit trail).
The JSON export contains deal data and verdicts only — never profile data.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "deals.db"
SITE_JSON = REPO_ROOT / "site" / "deals.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    key TEXT PRIMARY KEY,
    address TEXT, city TEXT, state TEXT,
    tier TEXT, market_type TEXT,
    price REAL,
    source TEXT,
    status TEXT,               -- extracted | killed | scored
    verdict TEXT,              -- PASS | BORDERLINE | FAIL | KILLED
    score REAL,
    kill_reasons TEXT,         -- JSON list
    deal_json TEXT,            -- full deal dict (claimed + enriched)
    result_json TEXT,          -- full scoring result
    deal_card_md TEXT,
    first_seen TEXT, last_updated TEXT
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


def seen(conn: sqlite3.Connection, key: str) -> bool:
    return conn.execute("SELECT 1 FROM deals WHERE key=?", (key,)).fetchone() is not None


def _json_default(o):
    if o == float("inf"):
        return None
    return str(o)


def upsert(conn: sqlite3.Connection, key: str, deal: dict, *, status: str,
           verdict: str | None = None, score: float | None = None,
           kill_reasons: list | None = None, result: dict | None = None,
           deal_card_md: str | None = None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = conn.execute("SELECT first_seen FROM deals WHERE key=?", (key,)).fetchone()
    first_seen = row[0] if row else now
    conn.execute(
        """INSERT OR REPLACE INTO deals
           (key, address, city, state, tier, market_type, price, source, status,
            verdict, score, kill_reasons, deal_json, result_json, deal_card_md,
            first_seen, last_updated)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (key, deal.get("address"), deal.get("city"), deal.get("state"),
         deal.get("tier"), deal.get("market_type"), deal.get("price"),
         deal.get("source"), status, verdict, score,
         json.dumps(kill_reasons or []),
         json.dumps(deal, default=_json_default),
         json.dumps(result or {}, default=_json_default),
         deal_card_md, first_seen, now))
    conn.commit()


def export_site_json(conn: sqlite3.Connection, out_path: Path = SITE_JSON):
    """Sanitized export for the public dashboard. No profile data, ever."""
    rows = conn.execute(
        """SELECT key, address, city, state, tier, market_type, price, source,
                  status, verdict, score, kill_reasons, result_json, deal_card_md,
                  first_seen, last_updated, deal_json
           FROM deals ORDER BY score DESC NULLS LAST, last_updated DESC""").fetchall()
    deals = []
    for r in rows:
        result = json.loads(r[12] or "{}")
        uw = result.get("underwriting") or {}
        deal = json.loads(r[16] or "{}")
        deals.append({
            "key": r[0], "address": r[1], "city": r[2], "state": r[3],
            "tier": r[4], "market_type": r[5], "price": r[6], "source": r[7],
            "status": r[8], "verdict": r[9] or ("KILLED" if r[8] == "killed" else None),
            "score": r[10], "kill_reasons": json.loads(r[11] or "[]"),
            "metrics": uw.get("metrics") or {},
            "assumptions": uw.get("assumptions") or {},
            "tax_flags": result.get("tax_flags") or [],
            "red_flags": result.get("red_flags") or [],
            "hard_disqualifiers": result.get("hard_disqualifiers") or [],
            "deal_card_md": r[13],
            "first_seen": r[14], "last_updated": r[15],
            # provenance + iteration-2 fields
            "source_name": deal.get("source_name") or r[7],
            "source_kind": deal.get("source_kind"),
            "email_subject": deal.get("email_subject"),
            "email_date": deal.get("email_date"),
            "email_link": deal.get("email_link"),
            "listing_urls": deal.get("listing_urls") or [],
            "identification": deal.get("identification"),
            "market_flavor": deal.get("market_flavor") or result.get("market_flavor"),
            "priority_note": result.get("priority_note"),
            # v3: four pillars + Victor comparison
            "pillars": result.get("pillars"),
            "exception_factors": result.get("exception_factors") or [],
            "victor": deal.get("victor"),
        })
    stats = {
        "total": len(deals),
        "killed": sum(1 for d in deals if d["status"] == "killed"),
        "pass": sum(1 for d in deals if d["verdict"] == "PASS"),
        "borderline": sum(1 for d in deals if d["verdict"] == "BORDERLINE"),
        "fail": sum(1 for d in deals if d["verdict"] == "FAIL"),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"stats": stats, "deals": deals}, f, indent=1)
    return stats
