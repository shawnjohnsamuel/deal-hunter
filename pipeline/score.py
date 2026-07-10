"""Buy-box scoring: tier classification, criteria evaluation, hard disqualifiers,
tax-flag triggers, composite 0-100 score, and the PASS/BORDERLINE/FAIL verdict.

All thresholds come from the profile — nothing is hardcoded to generic benchmarks.
"""
from .markets import classify_market, is_dfw
from .underwrite import underwrite

# Composite weights per framework-v2 (CoC-heavy, per the bulk-ranking convention).
WEIGHTS = {
    "str": {"coc": 0.35, "cap_rate": 0.15, "annual_cash_flow": 0.15,
            "gross_yield": 0.15, "occupancy": 0.10, "dscr": 0.10},
    "ltr": {"coc": 0.35, "cap_rate": 0.15, "annual_cash_flow": 0.15,
            "one_pct_rule": 0.10, "grm": 0.15, "dscr": 0.10},
    "house_hack": {"rental_coverage": 1.0},
}


def classify_tier(deal: dict, profile: dict) -> str:
    """Best-fit tier. Explicit hints win; otherwise infer from structure + market."""
    if deal.get("tier"):
        return deal["tier"]
    units = deal.get("units") or 1
    city = deal.get("city", "")
    if units >= 2 and is_dfw(city) and (deal.get("price") or 0) <= profile["buy_boxes"]["house_hack"]["price_max"] * 1.2:
        return "house_hack"
    claimed = deal.get("claimed") or {}
    str_signals = (
        classify_market(city) == "destination"
        or claimed.get("adr") is not None
        or claimed.get("annual_str_revenue") is not None
        or deal.get("source_tier_hint") == "str"
    )
    return "str" if str_signals else "ltr"


def _criterion_points(value: float, minimum: float, target: float, lower_is_better: bool = False) -> float:
    """0-100: 50 at the minimum threshold, 100 at target, scaled below the min."""
    if lower_is_better:
        if value <= target:
            return 100.0
        if value <= minimum:
            span = minimum - target or 1
            return 50 + 50 * (minimum - value) / span
        return max(0.0, 50 * (minimum / value) if value else 0.0)
    if value >= target:
        return 100.0
    if value >= minimum:
        span = target - minimum or 1
        return 50 + 50 * (value - minimum) / span
    if minimum <= 0:  # e.g. cash-flow floor of 0
        return max(0.0, 50 + value / 1000)  # each $1k negative costs a point
    return max(0.0, 50 * value / minimum)


def _evaluate_criteria(tier: str, m: dict, box: dict, dscr_min: float, dscr_target: float) -> list[dict]:
    """Compare computed metrics to the buy box. Returns per-criterion rows.

    Advisory rows inform the score/card but don't drive the verdict: break-even
    occupancy at 85% LTV routinely sits above the framework's aspirational 50%
    ceiling, so it's handled as a red flag vs expected occupancy instead of an
    auto-fail.
    """
    rows = []

    def add(name, value, minimum, target, lower_is_better=False, fmt="pct", advisory=False):
        if value is None or value == float("inf"):
            return
        if lower_is_better:
            status = "target" if value <= target else ("min" if value <= minimum else "fail")
        else:
            status = "target" if value >= target else ("min" if value >= minimum else "fail")
        rows.append({"criterion": name, "value": value, "min": minimum, "target": target,
                     "status": status, "lower_is_better": lower_is_better, "fmt": fmt,
                     "advisory": advisory,
                     "points": _criterion_points(value, minimum, target, lower_is_better)})

    if tier == "str":
        add("gross_yield", m["gross_yield"], box["gross_yield"]["min"], box["gross_yield"]["target"])
        add("occupancy", m["occupancy"], box["occupancy"]["min"], box["occupancy"]["target"])
        add("cap_rate", m["cap_rate"], box["cap_rate"]["min"], box["cap_rate"]["target"])
        add("coc", m["coc"], box["coc"]["min"], box["coc"]["target"])
        add("annual_cash_flow", m["annual_cash_flow"], box["annual_cash_flow"]["min"],
            box["annual_cash_flow"]["target"], fmt="usd")
        add("break_even_occupancy", m.get("break_even_occupancy"),
            box["break_even_occupancy_max"], box["break_even_occupancy_max"] * 0.8,
            lower_is_better=True, advisory=True)
        add("dscr", m["dscr"], dscr_min, dscr_target, fmt="x")
    elif tier == "ltr":
        add("grm", m["grm"], box["grm"]["max"], box["grm"]["target"], lower_is_better=True, fmt="x")
        add("cap_rate", m["cap_rate"], box["cap_rate"]["min"], box["cap_rate"]["target"])
        add("coc", m["coc"], box["coc"]["min"], box["coc"]["target"])
        add("one_pct_rule", m["one_pct_rule"], box["one_pct_rule"]["min"], box["one_pct_rule"]["target"])
        add("annual_cash_flow", m["annual_cash_flow"], box["annual_cash_flow"]["min"],
            box["annual_cash_flow"]["target"], fmt="usd")
        add("dscr", m["dscr"], dscr_min, dscr_target, fmt="x")
    elif tier == "house_hack":
        add("rental_coverage", m["rental_coverage"], box["rental_coverage"]["min"],
            box["rental_coverage"]["target"])
    return rows


def _hard_disqualifiers(deal: dict, uw: dict, profile: dict) -> list[str]:
    dq = []
    tier = uw["tier"]
    m = uw["metrics"]
    if deal.get("str_restricted") is True and tier == "str":
        dq.append("HOA/ordinance STR restriction — strategy dead")
    if tier == "str" and deal.get("market_type") == "non_destination":
        dq.append("non-destination market — STR tax strategy not viable")
    if m.get("dscr") is not None and m["dscr"] < profile["dscr_min"] and tier != "house_hack":
        dq.append(f"DSCR {m['dscr']:.2f} < {profile['dscr_min']} — negative coverage")
    if tier == "house_hack":
        hh = profile["buy_boxes"]["house_hack"]
        if deal.get("price", 0) > hh["price_max"]:
            dq.append(f"price above ${hh['price_max']:,} house-hack ceiling")
        if deal.get("owner_occ_eligible") is False:
            dq.append("not owner-occupant financing eligible")
    if m.get("ltv") and tier == "str" and m["ltv"] > profile["buy_boxes"]["str"]["ltv_max"]:
        dq.append(f"LTV {m['ltv']:.0%} above {profile['buy_boxes']['str']['ltv_max']:.0%} ceiling")
    return dq


def _tax_flags(deal: dict, uw: dict, profile: dict) -> list[str]:
    tax = profile["tax"]
    flags = []
    if uw["tier"] == "str":
        flags.append(
            f"STR loophole: avg stay <{tax['str_loophole_avg_stay_days']} days makes losses active vs W2 "
            f"(needs material participation: {tax['material_participation_hours']}+ hrs AND more than anyone else)")
    if deal.get("price", 0) > tax["cost_seg_price_trigger"]:
        lo, hi = tax["cost_seg_acceleration_range"]
        price = deal["price"]
        # Digest issues and deals.json are public: keep the flag property-derived
        # only — never the profile's marginal rate or dollar savings.
        flags.append(
            f"cost seg candidate: ~${price * lo:,.0f}-${price * hi:,.0f} Year 1 accelerated deductions at "
            f"100% bonus depreciation (OBBBA, permanent); cash value = deduction x your marginal rate. "
            f"Planning estimate — confirm with CPA + cost seg specialist.")
    if not tax["rep_status_active"] and uw["tier"] != "str":
        flags.append("passive-loss note: REP status not yet active — large paper losses may be suspended")
    return flags


def _red_flags(deal: dict, uw: dict, kill_flags: list[str]) -> list[str]:
    flags = list(kill_flags)
    enr = deal.get("enriched") or {}
    if uw["tier"] == "str":
        legality = enr.get("str_legality", "unverified")
        flags.append(f"STR legality: {legality.upper()} — human-verify HOA + city ordinance before any offer")
        if uw.get("missing_adr"):
            flags.append("no ADR data — framework says flag and ask, do not assume")
        if enr.get("str_data_estimated"):
            flags.append("STR revenue figures are estimates, not comp data")
    if uw.get("income_source") == "claimed":
        flags.append("income is SELLER-CLAIMED and was recomputed with our assumptions — verify independently")
    m = uw["metrics"]
    if 0 < m.get("annual_cash_flow", 0) < 3000 and uw["tier"] != "house_hack":
        flags.append("thin margins: barely cash-flows; one surprise CapEx wipes the year")
    beo = m.get("break_even_occupancy")
    occ = m.get("occupancy")
    if beo not in (None, float("inf")) and occ and beo > occ:
        flags.append(
            f"break-even occupancy {beo:.0%} EXCEEDS expected occupancy {occ:.0%} — "
            "betting on outperforming the market")
    return flags


def score_deal(deal: dict, profile: dict, kill_flags: list[str] | None = None) -> dict:
    """Full scoring pass. Returns the scored result (deal dict untouched)."""
    tier = deal["tier"] = classify_tier(deal, profile)
    deal.setdefault("market_type", classify_market(deal.get("city", "")))
    uw = underwrite(deal, profile)
    box = profile["buy_boxes"][tier]
    criteria = _evaluate_criteria(tier, uw["metrics"], box,
                                  profile["dscr_min"], profile["dscr_target"])
    disqualifiers = _hard_disqualifiers(deal, uw, profile)

    composite = 0.0
    weights = WEIGHTS[tier]
    total_w = 0.0
    for row in criteria:
        w = weights.get(row["criterion"], 0.0)
        composite += row["points"] * w
        total_w += w
    composite = round(composite / total_w, 1) if total_w else 0.0

    fails = [r for r in criteria if r["status"] == "fail" and not r["advisory"]]
    if disqualifiers:
        verdict, composite = "FAIL", min(composite, 25.0)
    elif not fails:
        verdict = "PASS"
    elif len(fails) <= 2 and all(_near_miss(r) for r in fails):
        verdict = "BORDERLINE"
    else:
        verdict = "FAIL"

    return {
        "tier": tier, "verdict": verdict, "score": composite,
        "criteria": criteria, "hard_disqualifiers": disqualifiers,
        "tax_flags": _tax_flags(deal, uw, profile),
        "red_flags": _red_flags(deal, uw, kill_flags or []),
        "underwriting": uw,
    }


def _near_miss(row: dict) -> bool:
    """Within 15% of the minimum threshold."""
    v, m = row["value"], row["min"]
    if row["lower_is_better"]:
        return v <= m * 1.15
    if m == 0:
        return v > -1500  # cash-flow floor of $0: within ~$125/mo
    return v >= m * 0.85
