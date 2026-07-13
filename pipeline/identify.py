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

def _identify_via_redfin(deal: dict) -> bool:
    """Deterministic identification: search the stated market's active
    listings, match price within 1.5% + exact beds (+baths when stated).
    Exactly one survivor = high confidence; two = ambiguous (low, recorded);
    otherwise fall through. Costs one API request."""
    from . import redfin
    if not redfin.available():
        return False
    location = deal.get("zip") or (
        f"{deal.get('city')}, {deal.get('state')}" if deal.get("city") else "")
    price = deal.get("price")
    if not location or not price:
        return False

    results = redfin.search(location)
    matches = []
    for rec in results:
        if not rec.get("price") or abs(rec["price"] - price) / price > 0.015:
            continue
        if deal.get("beds") and rec.get("beds") != deal["beds"]:
            continue
        if deal.get("baths") and rec.get("baths") and rec["baths"] != deal["baths"]:
            continue
        matches.append(rec)

    if len(matches) == 1:
        rec = matches[0]
        deal["identification"] = {
            "confidence": "high",
            "candidate_address": rec.get("street_address"),
            "evidence": (f"Redfin structured match in {location}: price ${rec['price']:,} "
                         f"within 1.5%, beds/baths exact; sole active-listing match"),
            "listing_url": rec.get("listing_url"),
        }
        deal["address"] = rec.get("street_address")
        deal["city"] = rec.get("city") or deal.get("city")
        deal["state"] = rec.get("state") or deal.get("state")
        deal["zip"] = rec.get("zip_code") or deal.get("zip")
        if rec.get("listing_url"):
            deal.setdefault("listing_urls", []).append(rec["listing_url"])
        return True
    if len(matches) == 2:
        deal["identification"] = {
            "confidence": "low",
            "candidate_address": matches[0].get("street_address"),
            "evidence": (f"Redfin search in {location}: two active listings match "
                         f"price/beds — ambiguous: "
                         + " vs ".join(m.get("street_address", "?") for m in matches)),
            "listing_url": None,
        }
    return False


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
    True when a high/medium-confidence address was found.

    Two passes: a structured Redfin search when the teaser states a market
    (price/beds/baths matched locally — deterministic and API-key-cheap),
    then the LLM web-search pass as fallback."""
    if _identify_via_redfin(deal):
        return True
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
