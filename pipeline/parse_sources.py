"""Deterministic parsers for the recurring deal-flow email formats.

Each source publishes to a rigid template, so once a layout is known a tested
regex parser is cheaper, faster, and far more reproducible than re-deriving the
extraction by hand (or by LLM) on every hunt. The model's judgment is then spent
only on what the parsers flag as ambiguous.

Covers:
  * The Offer Sheet daily digests   -- `# [addr](…/properties/…)` blocks
  * The Offer Sheet single-property spotlights -- address from the contact-link
    slug, price/beds/revenue from the body
  * Here newsletters                -- `## [addr](zillow…)` blocks
  * BnB Flow regional roundups      -- `### [addr]` blocks
  * Victor Steffen agent lists      -- `**n) Title $Price**` + `[addr](link)`

Every parsed deal carries `parse_confidence`: "high" when the fields came from
the template's own labelled rows, "review" when a value had to be inferred (or
is missing) and a human should look before trusting it.

CLI:
    python -m pipeline.parse_sources <dir-of-message-files> -o data/hunts/X.json

where each message file is the plain-text dump written by the hunt workflow:
    SUBJECT: …\nSENDER: …\nDATE: …\nMSGID: …\n====\n<plaintext body>
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Both money emojis appear in the wild; The Offer Sheet switched mid-run once
# and silently produced price-less deals until it was caught.
MONEY = r"[\U0001F4B0\U0001F4B5]"

STATE = r"[A-Z]{2}"


def _money_k(s: str | None) -> int | None:
    """Handles the '$96K' / '$1.2M' shorthand the newsletters mix with commas."""
    if not s:
        return None
    m = re.search(r"([\d,.]+)\s*([KM])?", s.strip(), re.I)
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (m.group(2) or "").upper()
    if unit == "K":
        n *= 1_000
    elif unit == "M":
        n *= 1_000_000
    return int(round(n))


def _money(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"[\d,]+", s)
    return int(m.group().replace(",", "")) if m else None


def _split_address(addr: str) -> tuple[str, str, str, str | None] | None:
    """'123 Main St, Boone, NC 28607' -> parts. None when it doesn't parse."""
    m = re.match(rf"(.+?),\s*([^,]+),\s*({STATE})\s*(\d{{5}})?", addr.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip(), m.group(3), m.group(4)


#: Street-type tokens. The city can be multiple words ('santa-rosa-beach'), so
#: splitting on word count fails; anchoring on the LAST street suffix does not.
_STREET_SUFFIX = {
    "st", "street", "ave", "avenue", "dr", "drive", "rd", "road", "ct", "court",
    "ln", "lane", "way", "blvd", "boulevard", "cir", "circle", "trl", "trail",
    "pl", "place", "ter", "terrace", "hwy", "highway", "pkwy", "parkway",
    "loop", "run", "path", "point", "pt", "pass", "row", "walk", "bnd", "bend",
    "cv", "cove", "crest", "ridge", "xing", "crossing", "sq", "square", "aly",
    "gap", "hl", "hill", "vw", "view", "spur", "creek", "trce", "trace",
}
#: Directional/unit tokens that may trail the street suffix.
_TRAILING = {"n", "s", "e", "w", "ne", "nw", "se", "sw", "unit", "apt", "ste"}


def _anchor_split(parts: list[str]) -> tuple[list[str], list[str]] | None:
    """Split '<street…> <city…>' tokens on the street-suffix anchor.

    Several suffixes ('creek', 'ridge', 'point') are also common city-name
    words — Queen Creek AZ, Blue Ridge GA. Scan right-to-left and take the
    first split that still leaves a city behind, so 'queen creek' stays the
    city while '…-214th-street' stays the street."""
    candidates = [i for i, tok in enumerate(parts) if tok.lower().strip(".") in _STREET_SUFFIX]
    for idx in reversed(candidates):
        end = idx
        # absorb a unit number or direction immediately after the suffix
        while end + 1 < len(parts) - 1 and (
                parts[end + 1].isdigit() or parts[end + 1].lower() in _TRAILING):
            end += 1
        if parts[:end + 1] and parts[end + 1:]:
            return parts[:end + 1], parts[end + 1:]
    return None


def _split_loose_address(raw: str) -> tuple[str, str, str, str | None] | None:
    """Victor's anchors have no commas: '1601 Meadowview Dr Port Lavaca TX 77979'."""
    toks = raw.replace(",", " ").split()
    zipc = None
    if toks and re.fullmatch(r"\d{5}", toks[-1]):
        zipc = toks.pop()
    if len(toks) < 3:
        return None
    state = toks.pop().upper()
    if not re.fullmatch(STATE, state):
        return None
    split = _anchor_split(toks)
    if not split:
        return None
    return " ".join(split[0]), " ".join(split[1]), state, zipc


def _slug_to_address(slug: str) -> tuple[str, str, str, str | None] | None:
    """The Offer Sheet contact links encode the address:
    '40-long-leaf-cir-santa-rosa-beach-fl-32459'
        -> ('40 Long Leaf Cir', 'Santa Rosa Beach', 'FL', '32459')

    Right-to-left: optional zip, then the state. The split between street and
    city is anchored on the last street-suffix token (plus any trailing unit
    number or direction), because both halves can be multi-word."""
    parts = slug.split("-")
    zipc = None
    if parts and re.fullmatch(r"\d{5}", parts[-1]):
        zipc = parts.pop()
    if len(parts) < 3:
        return None
    state = parts.pop().upper()
    if not re.fullmatch(STATE, state):
        return None

    # Several suffixes ('creek', 'ridge', 'point') are also common city-name
    # words — Queen Creek AZ, Blue Ridge GA. Scan right-to-left and take the
    # first split that still leaves a city behind, so 'queen creek' stays the
    # city and '…-214th-street' stays the street.
    split = _anchor_split(parts)
    if not split:
        return None
    street_tokens, city_tokens = split
    street = " ".join(street_tokens).title()
    # keep ordinals lowercase: '214Th' -> '214th'
    street = re.sub(r"\b(\d+)(St|Nd|Rd|Th)\b",
                    lambda m: m.group(1) + m.group(2).lower(), street)
    return street, " ".join(city_tokens).title(), state, zipc


def _base(mid: str, subject: str, date: str, source: str, name: str) -> dict:
    return {
        "source": source, "source_name": name, "source_kind":
            "agent" if source == "victor" else "teaser_newsletter",
        "email_subject": subject, "email_date": date,
        "email_link": f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{mid}",
    }


def _zillow(block: str) -> list[str]:
    m = re.search(r"(https://www\.zillow\.com/homedetails/[^\s)]+)", block)
    return [m.group(1)] if m else []


# --------------------------------------------------------------------------
# The Offer Sheet — daily digest
# --------------------------------------------------------------------------
_OS_DAILY_HDR = re.compile(
    r"^# \[([^\]]+)\]\(https://www\.theoffersheet\.app/properties/[^)]+\)", re.M)


def parse_offersheet_daily(text, mid, subject, date) -> list[dict]:
    deals, ms = [], list(_OS_DAILY_HDR.finditer(text))
    for i, mo in enumerate(ms):
        block = text[mo.end(): ms[i + 1].start() if i + 1 < len(ms) else len(text)]
        parts = _split_address(mo.group(1))
        if not parts:
            continue
        price = _money((re.search(rf"{MONEY}\s*\$([\d,]+)", block) or [None]) and
                       re.search(rf"{MONEY}\s*\$([\d,]+)", block).group(1))
        bb = re.search(r"\U0001F6CF️?\s*(\d+)\s*Bedrooms?,\s*([\d.]+)\s*Bathrooms?", block)
        adr = re.search(r"Average Daily Rate:\s*\$([\d,]+)", block)
        occ = re.search(r"Occupancy Rate:\s*([\d.]+)%", block)
        coc = re.search(r"Cash on Cash Return:\s*([\d.-]+)%", block)
        claimed = {}
        if adr:
            claimed["adr"] = _money(adr.group(1))
        if occ:
            claimed["occupancy"] = float(occ.group(1)) / 100
        deals.append({
            **_base(mid, subject, date, "the_offer_sheet", "The Offer Sheet"),
            "address": parts[0], "city": parts[1], "state": parts[2], "zip": parts[3],
            "price": price, "beds": int(bb.group(1)) if bb else None,
            "baths": float(bb.group(2)) if bb else None,
            "property_type": "STR cabin", "units": 1, "source_tier_hint": "str",
            "notes": f"OfferSheet projected CoC {coc.group(1)}%" if coc else "",
            "claimed": claimed,
            "parse_confidence": "high" if price else "review",
        })
    return deals


# --------------------------------------------------------------------------
# The Offer Sheet — single-property spotlight
# --------------------------------------------------------------------------
_REV_PATTERNS = [
    # most specific first — actual/verified beats projected
    (r"\$([\d,]+(?:\.\d+)?)\s*(?:in\s+)?(?:gross\s+)?(?:rental\s+)?revenue\s+in\s+20\d\d", "actual"),
    (r"20\d\d\s+Gross\s+Rental\s+Revenue:\s*\$([\d,]+)", "actual"),
    (r"20\d\d\s+(?:STR|Gross|Rental)\s+Revenue:?\s*~?\$([\d,]+)", "actual"),
    (r"\$([\d,]+)\s*(?:\+)?\s*(?:in\s+)?[Vv]erified\s+[Aa]nnual", "verified"),
    (r"(?:approximately|about|roughly)\s+\$([\d,]+)\s+in\s+annual\s+gross", "actual"),
    (r"\$([\d,]+)\s*(?:\+)?\s*(?:in\s+)?[Aa]nnual\s+(?:gross\s+)?(?:rental\s+)?(?:revenue|income)", "actual"),
    (r"\$([\d,.]+K?)\s*(?:\+)?\s*(?:in\s+)?(?:verifiable|verified|proven)\s+"
     r"(?:annual\s+)?(?:STR\s+)?(?:rental\s+)?(?:income|revenue)", "verified"),
    (r"\$([\d,.]+K?)\s+STR\s+Income\b", "actual"),
    (r"[Pp]rojected\s+[Gg]ross\s+[Rr]evenue:?\s*\$([\d,]+)", "projected"),
    (r"\$([\d,]+)\s*(?:\+)?\s*[Pp]rojected", "projected"),
]


def parse_offersheet_spotlight(text, mid, subject, date) -> list[dict] | list:
    slug = re.search(r"theoffersheet\.app/contact/([a-z0-9-]+)", text, re.I)
    parts = _slug_to_address(slug.group(1)) if slug else None

    price = None
    for pat in (rf"###\s*{MONEY}\s*Offered at:\s*\*?\*?\$([\d,]+)",
                r"Offered at(?:\s+\w+){0,2}?\s*\*\*\$([\d,]+)\*\*",
                r"Offered at:?(?:\s+just|\s+only)?\s*\$([\d,]+)",
                # 'ЁЯТ░ **Price: $399,900**' — the spec-list variant
                rf"{MONEY}?\s*\*\*Price:\s*\$([\d,]+)\*\*",
                r"\bPrice:\s*\$([\d,]+)"):
        m = re.search(pat, text)
        if m:
            price = _money(m.group(1))
            break

    beds = re.search(r"^\*\s*(\d+)\s*Bedrooms?\b", text, re.M) or \
        re.search(r"(\d+)\s*Bedrooms?\s*[•·]", text)
    baths = re.search(r"^\*\s*([\d.]+)\s*Bathrooms?\b", text, re.M) or \
        re.search(r"([\d.]+)\s*Bathrooms?\s*[•·]", text)
    sqft = re.search(r"([\d,]+)\s*(?:Heated\s+)?Sq\.?\s*Ft", text, re.I)

    revenue, rev_kind = None, None
    for pat, kind in _REV_PATTERNS:
        m = re.search(pat, text)
        if m:
            revenue, rev_kind = _money_k(m.group(1)), kind
            break

    conf = "high"
    notes = []
    if rev_kind == "projected":
        conf = "review"
        notes.append("revenue is PROJECTED, not actual")
    if revenue is None or price is None or parts is None:
        conf = "review"
    # A revenue window that isn't 12 months (e.g. "$120,309 from June 2025
    # through August 2026") must not be read as an annual figure.
    if re.search(r"(?:through|to)\s+\w+\s+\d{1,2},?\s*20\d\d", text) and \
            re.search(r"20\d\d\s*[-–—]\s*\w", text) is None and revenue:
        if re.search(r"(?:14|13|15|16|18)(?:\.\d)?\s*months", text):
            conf = "review"
            notes.append("revenue window is NOT 12 months — annualize before trusting")

    d = {
        **_base(mid, subject, date, "the_offer_sheet", "The Offer Sheet"),
        "address": parts[0] if parts else None,
        "city": parts[1] if parts else None,
        "state": parts[2] if parts else None,
        "zip": parts[3] if parts else None,
        "price": price,
        "beds": int(beds.group(1)) if beds else None,
        "baths": float(baths.group(1)) if baths else None,
        "sqft": _money(sqft.group(1)) if sqft else None,
        "property_type": "STR", "units": 1, "source_tier_hint": "str",
        "notes": "; ".join(notes),
        "claimed": {"annual_str_revenue": revenue} if revenue else {},
        "parse_confidence": conf,
    }
    if parts is None:
        d["teaser"] = True
    return [d]


# --------------------------------------------------------------------------
# Here newsletters
# --------------------------------------------------------------------------
_HERE_HDR = re.compile(
    r"^## \[([^\]]+)\]\((https://www\.zillow\.com/homedetails/[^)]+)\)", re.M)


def parse_here(text, mid, subject, date) -> list[dict]:
    deals, ms = [], list(_HERE_HDR.finditer(text))
    for i, mo in enumerate(ms):
        block = text[mo.end(): ms[i + 1].start() if i + 1 < len(ms) else len(text)]
        parts = _split_address(mo.group(1))
        if not parts:
            continue
        price = re.search(r"^\* \$([\d,]+)", block, re.M)
        bb = re.search(r"(\d+)\s*BR\s*/\s*([\d.]+)\s*BA", block)
        sq = re.search(r"([\d,]+)\s*sq/ft", block)
        adr = re.search(r"Average Daily Rate:\s*\$([\d,]+)", block)
        occ = re.search(r"Occupancy Rate:\s*([\d.]+)%", block)
        claimed = {}
        if adr:
            claimed["adr"] = _money(adr.group(1))
        if occ:
            claimed["occupancy"] = float(occ.group(1)) / 100
        deals.append({
            **_base(mid, subject, date, "here", "Here"),
            "address": parts[0], "city": parts[1], "state": parts[2], "zip": parts[3],
            "price": _money(price.group(1)) if price else None,
            "beds": int(bb.group(1)) if bb else None,
            "baths": float(bb.group(2)) if bb else None,
            "sqft": _money(sq.group(1)) if sq else None,
            "property_type": "STR cabin", "units": 1, "source_tier_hint": "str",
            "listing_urls": [mo.group(2)], "claimed": claimed,
            "parse_confidence": "high" if price else "review",
        })
    return deals


# --------------------------------------------------------------------------
# BnB Flow
# --------------------------------------------------------------------------
_BNB_HDR = re.compile(r"^### \[([^\]]+)\]", re.M)


def parse_bnbflow(text, mid, subject, date) -> list[dict]:
    deals, ms = [], list(_BNB_HDR.finditer(text))
    for i, mo in enumerate(ms):
        block = text[mo.end(): ms[i + 1].start() if i + 1 < len(ms) else len(text)]
        parts = _split_address(mo.group(1))
        if not parts:
            continue
        price = re.search(r"List Price:\s*\*\*\s*\$([\d,]+)", block) or \
            re.search(r"List Price[:*\s]+\$([\d,]+)", block)
        bb = re.search(r"Layout:\*\*\s*(\d+)\s*Bedroom,\s*(\d+)\s*Bathroom", block)
        adr = re.search(r"\(ADR\):\*\*\s*\$([\d,]+)", block)
        occ = re.search(r"Occupancy Rate:\*\*\s*([\d.]+)%", block)
        rev = re.search(r"Estimated Revenue:\*\*\s*\$([\d,]+)", block)
        claimed = {}
        if adr:
            claimed["adr"] = _money(adr.group(1))
        if occ:
            claimed["occupancy"] = float(occ.group(1)) / 100
        if rev:
            claimed["annual_str_revenue"] = _money(rev.group(1))
        deals.append({
            **_base(mid, subject, date, "bnb_flow", "BnB Flow"),
            "address": parts[0], "city": parts[1], "state": parts[2], "zip": parts[3],
            "price": _money(price.group(1)) if price else None,
            "beds": int(bb.group(1)) if bb else None,
            "baths": float(bb.group(2)) if bb else None,
            "property_type": "STR cabin", "units": 1, "source_tier_hint": "str",
            "listing_urls": _zillow(block), "claimed": claimed,
            "notes": "BnB Flow revenue is an ESTIMATE, not seller-reported",
            "parse_confidence": "high" if price else "review",
        })
    return deals


# --------------------------------------------------------------------------
# Victor Steffen — agent lists
# --------------------------------------------------------------------------
_VIC_LINK = re.compile(
    rf"\[_?([^\]]*?,?\s*[A-Za-z .'/-]+\s+{STATE}(?:\s+\d{{5}})?)_?\]\((https?://[^)]+)\)")


def parse_victor(text, mid, subject, date) -> list[dict]:
    """Victor's lists pair a bolded headline (carrying the asking price) with a
    Redfin/HAR link whose anchor text is the address. Rent is '$N,NNN per month'
    in the paragraph above the link."""
    deals = []
    for mo in _VIC_LINK.finditer(text):
        raw = mo.group(1).strip()
        raw = re.sub(r"^Link»\s*", "", raw)
        parts = _split_address(raw) or _split_loose_address(raw)
        if not parts:
            continue
        before = text[max(0, mo.start() - 1600): mo.start()]
        price = None
        for pm in re.finditer(r"\$\s?([\d.,]+)\s*([KM])?\b", before):
            val, unit = pm.group(1), pm.group(2)
            try:
                n = float(val.replace(",", ""))
            except ValueError:
                continue
            if unit == "M":
                n *= 1_000_000
            elif unit == "K":
                n *= 1_000
            if 80_000 <= n <= 20_000_000:
                price = int(n)
        rent = None
        rm = None
        for rm_ in re.finditer(r"\$([\d,]+)\s*(?:to\s*\$[\d,]+\s*)?per month", before):
            rm = rm_
        if rm:
            rent = _money(rm.group(1))
        units = 1
        u = re.search(r"\b(\d{1,2})[- ](?:unit|plex)\b", before, re.I)
        if u:
            units = int(u.group(1))
        elif re.search(r"\bfourplex|\bquad\b", before, re.I):
            units = 4
        elif re.search(r"\btriplex\b", before, re.I):
            units = 3
        elif re.search(r"\bduplex|two-unit\b", before, re.I):
            units = 2
        is_str = bool(re.search(r"\bSTR\b|Airbnb|short[- ]term", before, re.I))
        d = {
            **_base(mid, subject, date, "victor", "Victor Steffen (Steffen Realty)"),
            "address": parts[0], "city": parts[1], "state": parts[2], "zip": parts[3],
            "price": price, "units": units,
            "property_type": "STR" if is_str else ("multifamily" if units > 1 else "SFR"),
            "notes": "", "claimed": {},
            "parse_confidence": "high" if (price and (rent or is_str)) else "review",
        }
        if is_str:
            d["source_tier_hint"] = "str"
        if rent:
            d["claimed"]["monthly_rent"] = rent
        deals.append(d)
    # de-dup within one email (Victor repeats a deal in summary + detail)
    seen, out = set(), []
    for d in deals:
        k = (d["address"].lower(), d["state"])
        if k in seen:
            continue
        seen.add(k)
        out.append(d)
    return out


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------
def parse_message(text: str) -> list[dict]:
    head = text[:400]
    mid = (re.search(r"^MSGID: (.+)$", head, re.M) or [None, ""])[1] if \
        re.search(r"^MSGID: (.+)$", head, re.M) else ""
    mid = re.search(r"^MSGID: (.+)$", head, re.M)
    mid = mid.group(1).strip() if mid else ""
    sender = re.search(r"^SENDER: (.+)$", head, re.M)
    sender = sender.group(1).strip() if sender else ""
    subject = re.search(r"^SUBJECT: (.+)$", head, re.M)
    subject = subject.group(1).strip() if subject else ""
    date = re.search(r"^DATE: (\d{4}-\d{2}-\d{2})", head, re.M)
    date = date.group(1) if date else ""

    if "victor@" in sender:
        return parse_victor(text, mid, subject, date)
    if "here@" in sender:
        return parse_here(text, mid, subject, date)
    if "bnbflow" in sender:
        return parse_bnbflow(text, mid, subject, date)
    if "theoffersheet" in sender:
        if _OS_DAILY_HDR.search(text):
            return parse_offersheet_daily(text, mid, subject, date)
        if re.search(r"theoffersheet\.app/contact/", text) or \
                re.search(rf"{MONEY}\s*Offered at", text):
            return parse_offersheet_spotlight(text, mid, subject, date)
    return []


def parse_dir(d: str | Path) -> list[dict]:
    out = []
    for f in sorted(Path(d).glob("*.txt")):
        try:
            out += parse_message(f.read_text())
        except Exception as e:  # one malformed email must never sink the batch
            out.append({"_parse_error": f"{f.name}: {e}"})
    return out


def _cli():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory")
    ap.add_argument("-o", "--out")
    ap.add_argument("--only", help="comma-separated message ids to keep")
    a = ap.parse_args()

    deals = parse_dir(a.directory)
    errors = [d for d in deals if "_parse_error" in d]
    deals = [d for d in deals if "_parse_error" not in d]
    if a.only:
        keep = set(a.only.split(","))
        deals = [d for d in deals if any(k in d.get("email_link", "") for k in keep)]

    seen, uniq = set(), []
    for d in deals:
        k = ((d.get("address") or d.get("city") or "").lower(), d.get("state"))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(d)

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.out, "w") as f:
            json.dump(uniq, f, indent=1)

    from collections import Counter
    print(f"{len(uniq)} unique deals  {dict(Counter(d['source_name'] for d in uniq))}")
    review = [d for d in uniq if d.get("parse_confidence") == "review"]
    if review:
        print(f"\n{len(review)} need review:")
        for d in review:
            print(f"  {d['source_name'][:12]:<12} {d.get('city')},{d.get('state')} "
                  f"{(d.get('address') or '(no address)')[:30]:<30} "
                  f"${d.get('price')}  {d.get('notes','')}")
    for e in errors:
        print("  PARSE ERROR:", e["_parse_error"])
    if a.out:
        print(f"\n-> {a.out}")


if __name__ == "__main__":
    _cli()
