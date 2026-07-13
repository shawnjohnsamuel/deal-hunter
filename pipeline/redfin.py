"""OpenWebNinja Real-Time Redfin Data client (framework §3c primary listing source).

Free tier: 100 requests/month — every call counts, so callers ration:
enrichment costs 2 calls per deal (search + details) and runs on kill-filter
survivors only. Filters are applied locally over search results rather than as
query params (only `location` is a verified param), which also keeps one
search reusable for several checks in the same market.

Env: REDFIN_API_KEY (required), REDFIN_BASE_URL (optional override).
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .dedupe import normalize_address

DEFAULT_BASE = "https://api.openwebninja.com/real-time-redfin-data"

calls_made = 0  # per-process counter, reported in hunt summaries


def available() -> bool:
    return bool(os.environ.get("REDFIN_API_KEY"))


def _call(path: str, params: dict) -> dict | None:
    global calls_made
    base = os.environ.get("REDFIN_BASE_URL", DEFAULT_BASE).rstrip("/")
    url = f"{base}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "x-api-key": os.environ["REDFIN_API_KEY"], "Accept": "application/json"})
    calls_made += 1
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.load(r)
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    return payload.get("data") if isinstance(payload, dict) else None


def search(location: str) -> list[dict]:
    """Active for-sale listings for a zip / 'City, ST' / region. One request."""
    data = _call("search", {"location": location})
    return (data or {}).get("results") or []


def property_details(property_id: str) -> dict | None:
    """Full record: tax_history, price_history, hoa_dues, redfin_estimate,
    public_description, schools, year_built... One request."""
    return _call("property-details", {"property_id": str(property_id)})


def market_trends(location: str) -> dict | None:
    """Region snapshot: median sale/list price, DOM, sale-to-list, YoY. One request."""
    return _call("market-trends", {"location": location})


def find_property(address: str, city: str = "", state: str = "",
                  zip_code: str = "", results: list[dict] | None = None) -> dict | None:
    """Match a street address against search results (normalized), searching
    by zip (preferred) or 'City, ST' when results aren't supplied."""
    if results is None:
        location = zip_code or (f"{city}, {state}" if city else "")
        if not location:
            return None
        results = search(location)
    want = normalize_address(address)
    for rec in results:
        got = rec.get("street_address") or ""
        if got and normalize_address(got) == want:
            return rec
    return None


def latest_tax(details: dict) -> float | None:
    history = details.get("tax_history") or []
    if not history:
        return None
    newest = max(history, key=lambda h: h.get("year", 0))
    return newest.get("taxes")


def hoa_monthly_from(details: dict, search_rec: dict | None = None) -> float | None:
    if search_rec and search_rec.get("hoa_monthly") is not None:
        return search_rec["hoa_monthly"]
    dues, freq = details.get("hoa_dues"), (details.get("hoa_frequency") or "").lower()
    if dues is None:
        return None
    if freq.startswith("year") or freq.startswith("annual"):
        return round(dues / 12, 2)
    if freq.startswith("quarter"):
        return round(dues / 3, 2)
    return dues  # monthly or unspecified


def price_history_note(details: dict) -> str:
    events = details.get("price_history") or []
    if not events:
        return ""
    recent = events[:3]
    return "; ".join(
        f"{e.get('event', '?')} ${e.get('price'):,} {str(e.get('date', ''))[:10]}"
        if e.get("price") else f"{e.get('event', '?')} {str(e.get('date', ''))[:10]}"
        for e in recent)
