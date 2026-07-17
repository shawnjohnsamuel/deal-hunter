"""Processed-email registry — makes ingestion idempotent across runs and modes.

Interactive triage (Claude session via the Gmail connector) and the future
automated cron share this file, so "grab everything not yet scraped" means the
same thing everywhere. Keyed by RFC-822 Message-ID when available (stable across
clients), else any unique id the fetcher provides.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "data" / "processed_emails.json"
SITE_JSON = REPO_ROOT / "site" / "deals.json"

# Gmail deep links embed the message/thread id in one of two forms:
#   .../#all/<connector-id>   or   .../#search/rfc822msgid:<header-id>
_LINK_ID = re.compile(r"#(?:all/|search/rfc822msgid:)([^/?&#]+)")


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


def _message_id_from_link(link: str) -> str:
    """Extract the id embedded in a Gmail deep link (either form)."""
    m = _LINK_ID.search(link or "")
    return _normalize(m.group(1)) if m else ""


def surfaced_message_ids(deals_path: Path | str = SITE_JSON) -> set[str]:
    """Message-ids of emails that produced at least one PASS or BORDERLINE deal.

    Used by the /hunt-deals labeling step to decide which processed emails also
    get the 'Deal Hunter/Surfaced' Gmail label. Parses each deal's email_link.
    """
    path = Path(deals_path)
    if not path.exists():
        return set()
    with open(path) as f:
        deals = json.load(f).get("deals", [])
    surfaced = set()
    for d in deals:
        if d.get("verdict") in ("PASS", "BORDERLINE"):
            mid = _message_id_from_link(d.get("email_link", ""))
            if mid:
                surfaced.add(mid)
    return surfaced


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
