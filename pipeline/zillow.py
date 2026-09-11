"""Last-resort listing lookup by reading the public Zillow listing page.

Why this exists: the paid listing API (OpenWebNinja) has a 100-request/month
free tier, and sources like The Short Term Shop hand us a Zillow URL per
listing but no price. Without a price nothing can be underwritten, so a deal
with a known URL and an exhausted quota would otherwise be dead weight.

Caveats, deliberately loud:
  * This reads a page meant for humans. It is NOT an API, it is outside
    Zillow's terms of service, and it can break or be blocked at any time.
    Every failure is soft — the deal keeps its missing price and says so.
  * Anything it returns is marked with source "zillow_page" so a number's
    provenance is never ambiguous in a deal card.

Prefer the paid API when a key is configured; this is the fallback.
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

fetches_made = 0  # per-process counter, reported in hunt summaries


def _fetch(url: str, timeout: int = 25) -> str | None:
    global fetches_made
    fetches_made += 1
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
        return body.decode("utf8", "replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _first_int(page: str, *patterns: str, lo: int = 0, hi: int = 10 ** 9) -> int | None:
    for pat in patterns:
        for m in re.finditer(pat, page):
            try:
                val = int(float(m.group(1)))
            except (TypeError, ValueError):
                continue
            if lo <= val <= hi:
                return val
    return None


def parse_listing(page: str) -> dict:
    """Pull the few facts we need out of a listing page's embedded JSON."""
    out: dict = {}
    price = _first_int(page, r'"price"\s*:\s*(\d{4,9})',
                       r'"unformattedPrice"\s*:\s*(\d{4,9})',
                       lo=10_000, hi=100_000_000)
    if price:
        out["price"] = price
    beds = _first_int(page, r'"bedrooms"\s*:\s*(\d{1,2})', lo=1, hi=30)
    if beds:
        out["beds"] = beds
    baths = _first_int(page, r'"bathrooms"\s*:\s*([\d.]+)', lo=1, hi=30)
    if baths:
        out["baths"] = baths
    sqft = _first_int(page, r'"livingArea"\s*:\s*(\d{3,7})', lo=200, hi=100_000)
    if sqft:
        out["sqft"] = sqft
    status = re.search(r'"homeStatus"\s*:\s*"([A-Z_]+)"', page)
    if status:
        out["status"] = status.group(1)
    return out


def lookup(url: str) -> dict | None:
    """{'price', 'beds', ...} for a Zillow listing URL, or None on any failure."""
    if "zillow.com/homedetails" not in url:
        return None
    page = _fetch(url)
    if not page:
        return None
    data = parse_listing(page)
    if not data.get("price"):
        return None
    data["source"] = "zillow_page"
    data["source_url"] = url
    return data
