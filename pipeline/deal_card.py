"""Render a scored deal as the standard markdown Deal Card (framework-v2 §5)."""


def _usd(v):
    return f"${v:,.0f}" if v is not None else "—"


def _pct(v):
    return f"{v:.1%}" if v is not None and v != float("inf") else "—"


def _fmt_metric(name: str, value) -> str:
    if value is None or value == float("inf"):
        return "—"
    if name in ("annual_cash_flow", "net_housing_cost_monthly"):
        return _usd(value)
    if name == "grm":
        return f"{value:.1f}"
    if name in ("dscr", "units"):
        return f"{value:.2f}" if name == "dscr" else f"{value:.0f}"
    return _pct(value)


METRIC_LABELS = {
    "gross_yield": "Gross Yield", "cap_rate": "Cap Rate", "coc": "Cash-on-Cash",
    "dscr": "DSCR", "annual_cash_flow": "Annual Cash Flow", "occupancy": "Occupancy",
    "break_even_occupancy": "Break-Even Occupancy", "grm": "GRM",
    "one_pct_rule": "1% Rule", "rental_coverage": "Rental Coverage",
    "net_housing_cost_monthly": "Net Housing Cost/mo", "units": "Units", "ltv": "LTV",
}

TOP3 = {
    "str": ["coc", "gross_yield", "annual_cash_flow"],
    "ltr": ["coc", "cap_rate", "annual_cash_flow"],
    "house_hack": ["rental_coverage", "net_housing_cost_monthly", "units"],
}


def summary_line(deal: dict, result: dict) -> str:
    """Verdict + top-3 metrics — the default output contract."""
    m = result["underwriting"]["metrics"]
    top = ", ".join(
        f"{METRIC_LABELS[k]} {_fmt_metric(k, m.get(k))}" for k in TOP3[result["tier"]])
    return (f"**{result['verdict']}** ({result['score']:.0f}/100) — "
            f"{deal.get('address', 'unknown address')}, {deal.get('city', '?')} "
            f"[{result['tier'].upper()}] · {top}")


def render_deal_card(deal: dict, result: dict) -> str:
    uw = result["underwriting"]
    fin = uw["financing"]
    m = uw["metrics"]
    lines = [
        "```",
        "DEAL CARD",
        "─────────────────────────────────────",
        f"Property Address: {deal.get('address', '—')}",
        f"Market / City:    {deal.get('city', '—')}, {deal.get('state', '—')}"
        f"  (market type: {deal.get('market_type', 'unknown')})",
        f"Property Type:    {deal.get('property_type', '—')}   Units: {deal.get('units', 1)}",
        f"Strategy Fit:     {result['tier'].upper()}",
        "",
        "PURCHASE",
        f"  List Price: {_usd(fin['price'])}   Down: {_pct(fin['down_payment_pct'])} ({_usd(fin['down_payment'])})",
        f"  Loan: {_usd(fin['loan_amount'])} @ {_pct(fin['interest_rate'])} / 30yr   LTV: {_pct(fin['ltv'])}",
        f"  Closing (est): {_usd(fin['closing_costs'])}   Total Cash Needed: {_usd(uw.get('total_cash_invested'))}",
        "",
        "INCOME",
    ]
    if result["tier"] == "str":
        lines += [
            f"  Gross Annual STR Revenue: {_usd(uw['gross_annual_income'])} ({uw['income_source']})",
            f"  ADR: {_usd(uw.get('adr'))}   Occupancy: {_pct(uw.get('occupancy'))}",
        ]
    elif result["tier"] == "house_hack":
        lines += [f"  Rent from non-owner units: {_usd(uw['other_units_monthly_rent'])}/mo ({uw['income_source']})"]
    else:
        lines += [f"  Gross Monthly Rent: {_usd(uw.get('monthly_rent'))} ({uw['income_source']})"]

    if result["tier"] == "house_hack":
        lines += [
            "",
            "PAYMENT",
            f"  Total Monthly Payment (PITI+HOA): {_usd(uw['total_monthly_payment'])}",
            f"  Net Housing Cost: {_usd(uw['net_housing_cost_monthly'])}/mo",
        ]
    else:
        lines += [
            "",
            "CASH FLOW",
            f"  Operating Expenses (annual): {_usd(uw['operating_expenses_annual'])}",
            f"  NOI: {_usd(uw['noi_annual'])}   Debt Service: {_usd(fin['annual_debt_service'])}",
            f"  Cash Flow: {_usd(uw['monthly_cash_flow'])}/mo ({_usd(uw['annual_cash_flow'])}/yr)",
        ]

    lines += ["", "KEY METRICS"]
    for k, v in m.items():
        lines.append(f"  {METRIC_LABELS.get(k, k)}: {_fmt_metric(k, v)}")

    lines += ["", f"VERDICT: {result['verdict']}  (composite score {result['score']:.0f}/100)"]
    for row in result["criteria"]:
        arrow = {"target": "✓ target", "min": "~ min", "fail": "✗ FAIL"}[row["status"]]
        if row.get("advisory") and row["status"] == "fail":
            arrow = "! advisory"
        lines.append(f"  {arrow:9s} {METRIC_LABELS.get(row['criterion'], row['criterion'])}: "
                     f"{_fmt_metric(row['criterion'], row['value'])} "
                     f"(min {_fmt_metric(row['criterion'], row['min'])}, "
                     f"target {_fmt_metric(row['criterion'], row['target'])})")
    if result["hard_disqualifiers"]:
        lines.append("  HARD DISQUALIFIERS:")
        lines += [f"    ✗ {d}" for d in result["hard_disqualifiers"]]
    lines.append("```")

    if uw["assumptions"]:
        lines += ["", "**Assumptions:** " + "; ".join(
            f"{k}: {v}" for k, v in uw["assumptions"].items())]
    if result["tax_flags"]:
        lines += ["", "**Tax angle:**"] + [f"- {t}" for t in result["tax_flags"]]
    if result["red_flags"]:
        lines += ["", "**Red flags:**"] + [f"- {r}" for r in result["red_flags"]]
    return "\n".join(lines)
