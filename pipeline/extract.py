"""LLM extraction: messy email/listing text → structured candidate deals.

The only place unstructured language gets interpreted. Everything downstream
is deterministic. Requires ANTHROPIC_API_KEY.
"""
import json
import os
import re

MODEL = os.environ.get("DEAL_HUNTER_MODEL", "claude-sonnet-5")

# Sender → tier hint (framework: victor sends all types; the rest are STR-focused)
SENDER_TIER_HINTS = {
    "victor@steffenrealtycorp.com": None,
    "theoffersheet@mail.beehiiv.com": "str",
    "here@mail.beehiiv.com": "str",
    "team@bnbflow.co": "str",
    "info@theshorttermshop.com": "str",
}

TEASER_GUIDANCE = """
IMPORTANT — this sender is a free teaser newsletter whose best deal's street address
is held behind a paywall. Extract those deals anyway with "address": null. Capture
EVERY distinguishing detail so the property can be identified by matching against
live listings: exact price, beds/baths/sqft, sleeps count, acreage, year built,
days on market, list date, price cuts, nightly rate, projected revenue, occupancy,
HOA mentions, and unique features (A-frame, hot tub, game room, mountain view,
creek frontage, hex/dome, new build...) — put features verbatim in "notes".
The city or market region is usually stated even when the address isn't; it is required.
"""

EXTRACTION_PROMPT = """You are a deal-intake parser for a real estate investment pipeline.
Extract EVERY candidate property from the text below. Newsletters often contain several.

Return ONLY a JSON array (no prose, no markdown fence). Each element:
{
  "address": "street address or null if not given",
  "city": "...", "state": "two-letter or null", "zip": "... or null",
  "property_type": "SFR|duplex|triplex|fourplex|multifamily|condo|cabin|townhouse|land|commercial|unknown",
  "units": <int or null>,
  "beds": <number or null>, "baths": <number or null>, "sqft": <int or null>,
  "price": <number or null>,
  "furnished": <true|false|null>,
  "claimed": {
    "monthly_rent": <number or null>,
    "annual_str_revenue": <number or null>,
    "adr": <number or null>,
    "occupancy": <decimal 0-1 or null>,
    "cap_rate": <decimal or null>,
    "cash_flow_annual": <number or null>
  },
  "listing_urls": ["..."],
  "notes": "anything material: condition, HOA mentions, STR permit claims, seller financing"
}

Rules:
- Everything in "claimed" is the SELLER'S/newsletter's number — extract as stated, never adjust.
- Percentages to decimals (17% -> 0.17). Strip $ and commas from numbers.
- Skip properties with neither an address nor a city.
- If the email is purely educational (no properties), return [].

TEXT:
"""


def _client():
    import anthropic
    return anthropic.Anthropic()


def extract_candidates(text: str, source: str = "manual",
                       email_meta: dict | None = None) -> list[dict]:
    """Parse arbitrary text into candidate deal dicts.

    email_meta (from ingest_gmail.fetch_recent_emails) attaches provenance —
    sender name/kind, subject, date, and a deep link back to the Gmail message —
    and switches on teaser extraction for paywalled newsletters.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set — cannot run LLM extraction")
    meta = email_meta or {}
    is_teaser_source = meta.get("sender_kind") == "teaser_paywall"
    prompt = EXTRACTION_PROMPT
    if is_teaser_source:
        prompt = TEASER_GUIDANCE + prompt
    resp = _client().messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt + text[:60000]}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    candidates = _parse_json_array(raw)
    hint = SENDER_TIER_HINTS.get(source)
    deals = []
    for c in candidates:
        if not (c.get("address") or c.get("city")):
            continue
        c["source"] = source
        c["source_name"] = meta.get("sender_name") or source
        c["source_kind"] = meta.get("sender_kind")
        if meta.get("subject"):
            c["email_subject"] = meta["subject"]
        if meta.get("date"):
            c["email_date"] = meta["date"]
        if meta.get("link"):
            c["email_link"] = meta["link"]
        if hint:
            c["source_tier_hint"] = hint
        if is_teaser_source and not c.get("address"):
            c["teaser"] = True
        if c.get("property_type") in ("land", "commercial"):
            c["property_category"] = c["property_type"]
        deals.append(c)
    return deals


def _parse_json_array(raw: str) -> list:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        parsed = json.loads(raw[start:end + 1])
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []
