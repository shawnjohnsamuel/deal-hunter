"""First-pass kill filter — deterministic, zero research spend (framework-v2 §3b).

Runs on seller-claimed numbers BEFORE any enrichment. Kills only on hard
arithmetic or confirmed facts; unknowns pass through as flags, never kills.
"""
from . import metrics
from .markets import classify_market


def run_kill_filter(deal: dict, profile: dict) -> tuple[bool, list[str], list[str]]:
    """Returns (killed, kill_reasons, flags)."""
    reasons: list[str] = []
    flags: list[str] = []
    tier = deal.get("tier", "ltr")
    price = deal.get("price") or 0
    claimed = deal.get("claimed") or {}
    boxes = profile["buy_boxes"]

    if price <= 0:
        flags.append("no price provided — cannot kill-filter, needs enrichment")
        return False, reasons, flags

    if deal.get("property_category") in ("land", "commercial"):
        reasons.append(f"{deal['property_category']} listing — outside all buy boxes")

    market_type = deal.get("market_type") or classify_market(deal.get("city", ""))
    deal["market_type"] = market_type

    if tier == "str":
        # The ceiling is really a down-payment-reach limit, so special financing
        # (e.g. 10% seller financing) legitimately extends it.
        default_down = profile["assumptions"]["financing"]["down_payment_pct_str"]
        down_pct = deal.get("down_payment_pct") or default_down
        ceiling = boxes["str"]["price_kill_ceiling"]
        down_budget = ceiling * default_down
        if price * down_pct > down_budget:
            reasons.append(
                f"price ${price:,.0f} needs ${price * down_pct:,.0f} down at {down_pct:.0%} — "
                f"beyond the ~${down_budget:,.0f} down-payment budget "
                f"(${ceiling:,.0f} ceiling at {default_down:.0%} down)")
        elif down_pct < default_down:
            flags.append(
                f"price ${price:,.0f} reachable only via the stated {down_pct:.0%}-down financing — "
                "verify those terms before anything else")
        if market_type == "non_destination":
            # Two-tier rule: anonymous teaser deals die here (no research spend);
            # full-address agent deals and manual adds get scored for the
            # database, capped at BORDERLINE in score.py. Flag goes LAST so it
            # never becomes the digest's "top flag".
            if deal.get("source_kind") == "teaser_paywall":
                reasons.append("non-destination market STR from a teaser newsletter — "
                               "not worth research spend (Tier-1 STRs are destination-market)")
            # else: scored for the database; score.py caps the verdict at
            # BORDERLINE and adds the note to the card's red flags.
        elif market_type == "unknown":
            flags.append("destination-market status UNKNOWN — judgment call for the human")

    if tier == "house_hack":
        hh = boxes["house_hack"]
        if price > hh["price_max"]:
            reasons.append(f"price ${price:,.0f} > ${hh['price_max']:,.0f} house-hack ceiling (hard disqualifier)")
        units = deal.get("units")
        if units is not None and units < hh["units"]["min"]:
            reasons.append(f"{units} unit(s) — house hack needs {hh['units']['min']}+")
        if deal.get("owner_occ_eligible") is False:
            reasons.append("not eligible for owner-occupant financing (hard disqualifier)")

    if tier == "ltr":
        rent = claimed.get("monthly_rent")
        if rent:
            one_pct = metrics.one_percent_rule(rent, price)
            g = metrics.grm(price, rent * 12)
            # Kill only when the seller's own optimistic numbers fail BOTH screens.
            if one_pct < boxes["ltr"]["one_pct_rule"]["min"] and g > 14:
                reasons.append(
                    f"fails seller's own math: 1% rule {one_pct:.2%} < "
                    f"{boxes['ltr']['one_pct_rule']['min']:.1%} AND GRM {g:.1f} > 14")

    if deal.get("str_restricted") is True and tier == "str":
        reasons.append("confirmed HOA/ordinance STR restriction (hard disqualifier)")

    return bool(reasons), reasons, flags
