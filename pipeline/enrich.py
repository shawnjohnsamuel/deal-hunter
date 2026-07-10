"""Enrichment for kill-filter survivors — free tiers only, budget-aware.

Sources, in order of trust:
  1. RentCast API (property record, tax assessment, rent estimate, AVM) — 50
     free calls/month, so calls are rationed: STR candidates first (Tier 1
     priority), and only deals missing the data a source provides.
  2. Claude web search: STR revenue estimates (Rabbu/AirDNA figures), county
     CAD tax records, live mortgage rates, STR ordinance status, Redfin/Zillow
     data via the search workaround (direct fetches 403).

Everything found lands in deal["enriched"]; anything search-derived is flagged
estimated. STR legality is NEVER auto-cleared to legal — best result is
"likely_ok" pending human verification.
"""
import json
import os
import re
import sys

MODEL = os.environ.get("DEAL_HUNTER_MODEL", "claude-sonnet-5")

_rate_cache: dict = {}


def enrich_deal(deal: dict, profile: dict) -> dict:
    enriched = deal.setdefault("enriched", {})
    if os.environ.get("RENTCAST_API_KEY"):
        try:
            _rentcast(deal, enriched)
        except Exception as e:
            print(f"WARNING: RentCast enrichment failed for {deal.get('address')}: {e}",
                  file=sys.stderr)
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            _web_search(deal, enriched)
        except Exception as e:
            print(f"WARNING: web-search enrichment failed for {deal.get('address')}: {e}",
                  file=sys.stderr)
    return enriched


# --- RentCast -----------------------------------------------------------

def _rentcast(deal: dict, enriched: dict):
    import urllib.parse
    import urllib.request

    def call(path: str, params: dict):
        qs = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"https://api.rentcast.io/v1/{path}?{qs}",
            headers={"X-Api-Key": os.environ["RENTCAST_API_KEY"], "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    addr = f"{deal.get('address', '')}, {deal.get('city', '')}, {deal.get('state', '')}"
    props = call("properties", {"address": addr})
    if props:
        p = props[0] if isinstance(props, list) else props
        enriched.setdefault("sqft", p.get("squareFootage"))
        deal.setdefault("beds", p.get("bedrooms"))
        deal.setdefault("baths", p.get("bathrooms"))
        tax_history = p.get("propertyTaxes") or {}
        if tax_history:
            latest = max(tax_history)
            enriched["property_tax_annual"] = tax_history[latest].get("total")
        hoa = (p.get("hoa") or {}).get("fee")
        if hoa:
            enriched["hoa_monthly"] = hoa

    if deal.get("tier") != "str":
        rent = call("avm/rent/long-term", {"address": addr})
        if rent.get("rent"):
            enriched["monthly_rent"] = rent["rent"]
    value = call("avm/value", {"address": addr})
    if value.get("price"):
        enriched["avm"] = value["price"]


# --- Claude web search ----------------------------------------------------

SEARCH_PROMPT = """Research this property for real estate underwriting. Use web search.

Property: {address}, {city}, {state} — {property_type}, listed at ${price:,.0f}. Strategy: {tier}.

Find (search "{address} {city} Redfin Zillow" for listing data — direct Redfin fetches fail):
1. Listing data: beds/baths/sqft, HOA fee if any, days on market, price history
2. Property tax: the COUNTY APPRAISAL DISTRICT record (e.g. Collin CAD) — actual annual tax, not a listing estimate
{tier_specific}
3. Current 30-year INVESTMENT PROPERTY mortgage rate (national average this week)

Return ONLY JSON:
{{
  "property_tax_annual": <number or null>,
  "hoa_monthly": <number or null>,
  "interest_rate": <decimal, e.g. 0.0715>,
  "monthly_rent": <number or null, LTR rent estimate>,
  "adr": <number or null>,
  "occupancy": <decimal or null>,
  "annual_str_revenue": <number or null>,
  "str_legality": "unverified" | "likely_ok" | "restricted",
  "str_legality_notes": "<what you found about ordinances/HOA>",
  "data_notes": "<sources + anything material>"
}}
Rules: numbers only when actually found — null over guesses. STR revenue figures
from Rabbu/AirDNA-style estimates are fine but note them in data_notes.
"str_legality" is "restricted" only with a found ordinance/HOA restriction;
"likely_ok" needs found evidence STRs operate legally there; else "unverified".
"""

STR_SPECIFIC = """3. STR data: Rabbu/AirDNA revenue estimates, market ADR and occupancy for {city}
4. STR legality: search "{city} short term rental ordinance" — permits required? banned? HOA-dependent?
5."""


def _web_search(deal: dict, enriched: dict):
    import anthropic

    tier = deal.get("tier", "ltr")
    tier_specific = (STR_SPECIFIC.format(city=deal.get("city", "")) if tier == "str"
                     else "3. Market rent estimate for this property (Zillow/RentCast-style)\n4.")
    prompt = SEARCH_PROMPT.format(
        address=deal.get("address", "?"), city=deal.get("city", "?"),
        state=deal.get("state", "?"), property_type=deal.get("property_type", "home"),
        price=deal.get("price") or 0, tier=tier.upper(), tier_specific=tier_specific)

    resp = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return
    try:
        found = json.loads(m.group(0))
    except json.JSONDecodeError:
        return

    for k in ("property_tax_annual", "hoa_monthly", "monthly_rent", "adr",
              "occupancy", "annual_str_revenue"):
        if found.get(k) is not None:
            enriched.setdefault(k, found[k])
    rate = found.get("interest_rate")
    if rate and 0.03 < rate < 0.12:
        _rate_cache["rate"] = rate
    if _rate_cache.get("rate"):
        enriched.setdefault("interest_rate", _rate_cache["rate"])
    if tier == "str":
        legality = found.get("str_legality", "unverified")
        enriched["str_legality"] = legality if legality in ("unverified", "likely_ok", "restricted") else "unverified"
        enriched["str_legality_notes"] = found.get("str_legality_notes", "")
        if enriched["str_legality"] == "restricted":
            deal["str_restricted"] = True
        if found.get("annual_str_revenue") or found.get("adr"):
            enriched["str_data_estimated"] = True
    if found.get("data_notes"):
        enriched["data_notes"] = found["data_notes"]
