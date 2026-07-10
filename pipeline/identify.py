"""Teaser-deal identification — find the address the paywall withheld.

The three teaser newsletters (The Offer Sheet, Here, BNB Flow) publish every
detail of their headline deal EXCEPT the street address. Those details (exact
price, beds/baths/sqft, market, nightly rate, distinctive features) are usually
enough to pin the live listing with a web search. This step attempts that match
and records a confidence grade — the address is research-derived, never fact,
until a human verifies it against the listing.

Requires ANTHROPIC_API_KEY. No key or no confident match → the deal proceeds
address-less on claimed numbers only.
"""
import json
import os
import re

MODEL = os.environ.get("DEAL_HUNTER_MODEL", "claude-sonnet-5")

IDENTIFY_PROMPT = """A paywalled real estate newsletter teased a property without its street
address. Identify the exact listing by searching live listing sites.

Teased details:
{details}

Search strategy: query Zillow/Redfin/Realtor.com/agent sites with the market +
price + beds/baths (e.g. "{city} {state} {beds} bed {baths} bath ${price} zillow"),
try the distinctive features verbatim (e.g. "A-frame hot tub {city} listing"),
and cross-check any candidate against ALL the teased numbers.

Match grading — be strict:
- "high": price within 1% AND beds/baths exact AND (sqft within 3% OR a distinctive
  feature matches verbatim), same market
- "medium": price within 2% and beds/baths exact, but sqft/features unverified
- "low": plausible candidate, at least one material attribute unconfirmed or conflicting
- "none": nothing credible found

Return ONLY JSON:
{{
  "confidence": "high" | "medium" | "low" | "none",
  "address": "<street address or null>",
  "city": "<or null>", "state": "<or null>", "zip": "<or null>",
  "listing_url": "<or null>",
  "evidence": "<which teased attributes matched, with the numbers>"
}}"""


def _details_block(deal: dict) -> str:
    claimed = deal.get("claimed") or {}
    rows = {
        "market/city": f"{deal.get('city', '?')}, {deal.get('state', '?')}",
        "price": deal.get("price"),
        "property type": deal.get("property_type"),
        "beds/baths": f"{deal.get('beds')}/{deal.get('baths')}",
        "sqft": deal.get("sqft"),
        "claimed monthly rent": claimed.get("monthly_rent"),
        "claimed ADR": claimed.get("adr"),
        "claimed annual STR revenue": claimed.get("annual_str_revenue"),
        "claimed occupancy": claimed.get("occupancy"),
        "notes/features": deal.get("notes"),
    }
    return "\n".join(f"- {k}: {v}" for k, v in rows.items() if v not in (None, "None/None"))


def identify_property(deal: dict) -> bool:
    """Attempt to identify a teaser deal's address. Mutates the deal; returns
    True when a high/medium-confidence address was found."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    import anthropic

    prompt = IDENTIFY_PROMPT.format(
        details=_details_block(deal),
        city=deal.get("city", ""), state=deal.get("state", ""),
        beds=deal.get("beds", "?"), baths=deal.get("baths", "?"),
        price=f"{deal.get('price'):,.0f}" if deal.get("price") else "?")
    resp = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=3000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return False
    try:
        found = json.loads(m.group(0))
    except json.JSONDecodeError:
        return False

    confidence = found.get("confidence", "none")
    deal["identification"] = {
        "confidence": confidence,
        "evidence": found.get("evidence", ""),
        "listing_url": found.get("listing_url"),
        "candidate_address": found.get("address"),
    }
    if confidence in ("high", "medium") and found.get("address"):
        deal["address"] = found["address"]
        deal["city"] = found.get("city") or deal.get("city")
        deal["state"] = found.get("state") or deal.get("state")
        deal["zip"] = found.get("zip") or deal.get("zip")
        if found.get("listing_url"):
            deal.setdefault("listing_urls", []).append(found["listing_url"])
        return True
    return False
