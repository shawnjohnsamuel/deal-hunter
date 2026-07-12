"""Processed-email registry — makes ingestion idempotent across runs and modes.

Interactive triage (Claude session via the Gmail connector) and the future
automated cron share this file, so "grab everything not yet scraped" means the
same thing everywhere. Keyed by RFC-822 Message-ID when available (stable across
clients), else any unique id the fetcher provides.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "data" / "processed_emails.json"


def _normalize(msg_id: str) -> str:
    return (msg_id or "").strip().strip("<>")


def load_registry() -> dict:
    if REGISTRY.exists():
        with open(REGISTRY) as f:
            return json.load(f)
    return {}


def is_processed(msg_id: str) -> bool:
    return _normalize(msg_id) in load_registry()


def mark_processed(msg_id: str, note: str = ""):
    reg = load_registry()
    reg[_normalize(msg_id)] = {
        "processed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note,
    }
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY, "w") as f:
        json.dump(reg, f, indent=1, sort_keys=True)


def filter_new(emails: list[dict], id_key: str = "link") -> list[dict]:
    """Drop emails whose Message-ID (parsed out of the deep link) or explicit
    'message_id' field is already in the registry."""
    reg = load_registry()
    fresh = []
    for em in emails:
        mid = _normalize(em.get("message_id", ""))
        if not mid and em.get(id_key):
            # deep links embed rfc822msgid:<id>
            _, _, tail = em[id_key].partition("rfc822msgid:")
            mid = _normalize(tail)
        if mid and mid in reg:
            continue
        fresh.append(em)
    return fresh
