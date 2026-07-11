"""The four-pillar grading engine (framework-v2 §3½, Victor Steffen methodology).

Pillars 1–3 (asset quality, neighborhood, vacancy risk) are qualitative:
Victor's stated grades win, LLM estimates fill in for other sources (always
marked estimated), otherwise ungraded. Pillar 4 (cash-flow margin) is ALWAYS
computed deterministically — never LLM, never source-claimed.

Each pillar: {"grade": "A".."D" | None, "provenance": victor|estimated|computed|ungraded, "note": str}
"""

PILLAR_NAMES = ("asset_quality", "neighborhood", "vacancy", "cash_flow")

VICTOR_GRADE_KEYS = {
    "asset_quality": ("asset_quality", "asset", "condition"),
    "neighborhood": ("neighborhood", "neighborhood_quality", "location"),
    "vacancy": ("vacancy", "vacancy_risk", "occupancy"),
    "cash_flow": ("cash_flow", "cashflow", "cash_flow_margin"),
}


def _normalize_grade(raw) -> str | None:
    """'B+', 'a-', 'A' → single letter A–D."""
    if not raw:
        return None
    letter = str(raw).strip().upper()[:1]
    return letter if letter in "ABCD" else None


def _victor_grade(deal: dict, pillar: str) -> str | None:
    grades = ((deal.get("victor") or {}).get("grades")) or {}
    for key in VICTOR_GRADE_KEYS[pillar]:
        g = _normalize_grade(grades.get(key))
        if g:
            return g
    return None


def _estimated_grade(deal: dict, pillar: str) -> tuple[str | None, str]:
    est = ((deal.get("enriched") or {}).get("pillar_estimates")) or {}
    entry = est.get(pillar) or {}
    return _normalize_grade(entry.get("grade")), entry.get("why", "")


def _grade_cash_flow(deal: dict, uw: dict, profile: dict) -> dict:
    """Pillar 4 — deterministic bands from the metric engine."""
    m = uw["metrics"]
    tier = uw["tier"]
    if tier == "house_hack":
        cov = m.get("rental_coverage", 0)
        box = profile["buy_boxes"]["house_hack"]["rental_coverage"]
        if cov >= box["target"]:
            grade = "A"
        elif cov >= box["min"]:
            grade = "B"
        elif cov >= box["min"] * 0.8:
            grade = "C"
        else:
            grade = "D"
        return {"grade": grade, "provenance": "computed",
                "note": f"rental coverage {cov:.0%}"}

    coc = m.get("coc", 0)
    dscr = m.get("dscr", 0)
    cf = m.get("annual_cash_flow", 0)
    box = profile["buy_boxes"][tier]["coc"]
    floor = profile["pillars"]["str_coc_floor"] if tier == "str" else 0.0
    if dscr < profile["dscr_min"] or cf < 0 or coc < floor:
        grade = "D"
        note = f"CoC {coc:.1%}, DSCR {dscr:.2f}, cash flow ${cf:,.0f}/yr"
        if tier == "str" and 0 <= coc < floor:
            note += f" — below the {floor:.0%} STR posting floor"
    elif coc >= box["target"] and dscr >= profile["dscr_target"]:
        grade, note = "A", f"CoC {coc:.1%} at/above target with DSCR {dscr:.2f}"
    elif coc >= box["min"]:
        grade, note = "B", f"CoC {coc:.1%} at/above buy-box min"
    else:
        grade, note = "C", f"CoC {coc:.1%} below buy-box min, above the floor"
    return {"grade": grade, "provenance": "computed", "note": note}


def _grade_vacancy_fallback(deal: dict, uw: dict, profile: dict) -> dict:
    """Structured-data heuristic when neither Victor nor an estimate graded it."""
    status = (deal.get("occupancy_status") or "").lower()
    if status == "occupied":
        return {"grade": "A", "provenance": "computed", "note": "occupied at listing"}
    if status == "partial":
        pct = deal.get("occupied_pct")
        grade = "B" if (pct or 0) >= 0.75 else "C"
        note = f"partially occupied ({pct:.0%})" if pct else "partially occupied"
        return {"grade": grade, "provenance": "computed", "note": note}
    if status == "vacant":
        return {"grade": "C", "provenance": "computed", "note": "vacant — lease-up risk"}

    if uw["tier"] == "str":
        occ = uw.get("occupancy")
        box = profile["buy_boxes"]["str"]["occupancy"]
        assumed = "occupancy" in (uw.get("assumptions") or {})
        if occ is None:
            return {"grade": None, "provenance": "ungraded", "note": "no occupancy data"}
        provenance = "estimated" if assumed else "computed"
        if occ >= box["target"]:
            return {"grade": "A", "provenance": provenance, "note": f"market occupancy {occ:.0%}"}
        if occ >= box["min"]:
            return {"grade": "B", "provenance": provenance, "note": f"market occupancy {occ:.0%}"}
        return {"grade": "D", "provenance": provenance,
                "note": f"market occupancy {occ:.0%} below the {box['min']:.0%} minimum"}

    mv = (deal.get("enriched") or {}).get("market_vacancy")
    if mv is not None:
        grade = "B" if mv < 0.07 else "C"
        return {"grade": grade, "provenance": "computed", "note": f"market vacancy {mv:.0%}"}
    return {"grade": None, "provenance": "ungraded", "note": "no vacancy data"}


def grade_pillars(deal: dict, uw: dict, profile: dict) -> dict:
    pillars = {}
    for pillar in ("asset_quality", "neighborhood", "vacancy"):
        vg = _victor_grade(deal, pillar)
        if vg:
            pillars[pillar] = {"grade": vg, "provenance": "victor", "note": ""}
            continue
        eg, why = _estimated_grade(deal, pillar)
        if eg:
            pillars[pillar] = {"grade": eg, "provenance": "estimated",
                               "note": why or "estimated from listing/market data"}
            continue
        if pillar == "vacancy":
            pillars[pillar] = _grade_vacancy_fallback(deal, uw, profile)
        else:
            pillars[pillar] = {"grade": None, "provenance": "ungraded", "note": "no data"}
    pillars["cash_flow"] = _grade_cash_flow(deal, uw, profile)
    return pillars


def pillar_composite(pillars: dict, metric_composite: float, profile: dict) -> float:
    """Composite v3: pillar-weighted blend. The cash-flow pillar carries the
    full metric composite (0–100) for granularity; graded pillars map through
    grade points; ungraded pillars drop out and weights renormalize."""
    cfg = profile["pillars"]
    total_w = points = 0.0
    for name, p in pillars.items():
        w = cfg["weights"].get(name, 0)
        if name == "cash_flow":
            points += metric_composite * w
            total_w += w
        elif p["grade"]:
            points += cfg["grade_points"][p["grade"]] * w
            total_w += w
    return round(points / total_w, 1) if total_w else 0.0


def check_divergence(deal: dict, uw: dict, profile: dict) -> list[str]:
    """Victor's underwriting vs ours — >threshold relative divergence flagged
    with both numbers (trust, but make disagreement visible)."""
    victor_uw = ((deal.get("victor") or {}).get("underwriting")) or {}
    if not victor_uw:
        return []
    threshold = profile["pillars"]["divergence_threshold"]
    m = uw["metrics"]
    ours = {
        "monthly cash flow": ("cash_flow_monthly", uw.get("monthly_cash_flow"), "usd"),
        "cash-on-cash": ("coc", m.get("coc"), "pct"),
        "cap rate": ("cap_rate", m.get("cap_rate"), "pct"),
        "gross income (annual)": ("gross_annual_income", uw.get("gross_annual_income"), "usd"),
    }
    flags = []
    for label, (vkey, our_val, fmt) in ours.items():
        his = victor_uw.get(vkey)
        if his is None or our_val is None:
            continue
        denom = max(abs(our_val), abs(his), 1e-9)
        rel = abs(his - our_val) / denom
        if rel > threshold:
            f = (lambda v: f"${v:,.0f}") if fmt == "usd" else (lambda v: f"{v:.1%}")
            flags.append(
                f"DIVERGENCE on {label}: Victor {f(his)} vs ours {f(our_val)} "
                f"({rel:.0%} apart) — reconcile before trusting either")
    return flags
