"""Assemble tier-specific underwriting from a deal dict + investor profile.

Data precedence: enriched (independent) > claimed (seller) > profile defaults.
Every defaulted value lands in `assumptions` so Deal Cards can state them.
Seller-claimed income is used only when nothing independent exists, and is
flagged as such.
"""
from . import metrics


def _pick(deal: dict, key: str, assumptions: dict, default=None, note: str | None = None):
    """enriched > claimed > default, recording assumptions."""
    enriched = (deal.get("enriched") or {}).get(key)
    claimed = (deal.get("claimed") or {}).get(key)
    if enriched is not None:
        return enriched, "enriched"
    if claimed is not None:
        assumptions[key] = f"seller-claimed ({note or 'recompute before trusting'})"
        return claimed, "claimed"
    if default is not None:
        assumptions[key] = f"assumed: {default}" + (f" ({note})" if note else "")
    return default, "assumed"


def underwrite(deal: dict, profile: dict) -> dict:
    tier = deal.get("tier", "ltr")
    if tier == "str":
        return _underwrite_str(deal, profile)
    if tier == "house_hack":
        return _underwrite_house_hack(deal, profile)
    return _underwrite_ltr(deal, profile)


def _financing(deal: dict, profile: dict, assumptions: dict, down_pct_default: float):
    fin = profile["assumptions"]["financing"]
    price = deal["price"]
    down_pct = deal.get("down_payment_pct") or down_pct_default
    rate, rate_src = _pick(deal, "interest_rate", assumptions,
                           default=fin["fallback_interest_rate"], note="search live rate")
    down = price * down_pct
    loan = price - down
    closing = price * profile["assumptions"]["ltr"]["closing_costs_pct"]
    pi = metrics.monthly_mortgage_payment(loan, rate, fin["loan_term_years"])
    return {
        "price": price, "down_payment_pct": down_pct, "down_payment": down,
        "loan_amount": loan, "interest_rate": rate, "closing_costs": closing,
        "monthly_pi": pi, "annual_debt_service": pi * 12,
        "ltv": metrics.ltv(loan, price),
    }


def _tax_and_insurance(deal: dict, profile: dict, assumptions: dict, insurance_multiplier: float = 1.0):
    a = profile["assumptions"]["ltr"]
    price = deal["price"]
    tax_annual, _ = _pick(deal, "property_tax_annual", assumptions,
                          default=round(price * a["property_tax_pct_price"]),
                          note="1.2% of price fallback — pull CAD record")
    # Stated insurance (e.g. Victor's "real insurance" underwriting) beats the
    # formula default: % of value annually (market-calibrated Jul 2026 —
    # national landlord policies ~0.4-0.5% of value; Victor's TX actuals
    # ~0.76%; STR endorsement multiplier on top).
    ins_monthly, ins_src = _pick(deal, "insurance_monthly", assumptions)
    if ins_monthly is None:
        pct = a["insurance_pct_value_annual"]
        ins_monthly = price * pct * insurance_multiplier / 12
        assumptions["insurance"] = (
            f"assumed {pct * insurance_multiplier:.2%} of value/yr"
            + (" (STR policy)" if insurance_multiplier > 1.0 else ""))
    hoa_monthly, _ = _pick(deal, "hoa_monthly", assumptions, default=0)
    return tax_annual, ins_monthly, hoa_monthly


def _management_pct(deal: dict, assumptions: dict, default: float) -> float:
    pct, _ = _pick(deal, "management_pct", assumptions)
    if pct is None:
        return default
    if pct > 1:  # tolerate "20" meaning 20%
        pct /= 100
    return pct


def _underwrite_str(deal: dict, profile: dict) -> dict:
    assumptions: dict = {}
    s = profile["assumptions"]["str"]
    fin = _financing(deal, profile, assumptions,
                     profile["assumptions"]["financing"]["down_payment_pct_str"])

    adr, adr_src = _pick(deal, "adr", assumptions)  # no default — framework: flag and ask
    occupancy, _ = _pick(deal, "occupancy", assumptions, default=s["occupancy_default"])
    revenue, rev_src = _pick(deal, "annual_str_revenue", assumptions)
    if revenue is None and adr:
        revenue = adr * 365 * occupancy
        assumptions["annual_str_revenue"] = f"derived: ADR ${adr:,.0f} x 365 x {occupancy:.0%} occupancy"
        rev_src = "derived"
    missing_adr = adr is None
    revenue = revenue or 0.0
    if missing_adr and revenue and occupancy:
        adr = revenue / (365 * occupancy)
        assumptions["adr"] = f"derived from revenue: ${adr:,.0f}"
        # ADR backed only by the seller's own revenue claim is not data —
        # the framework's "flag and ask" rule still applies.
        missing_adr = rev_src == "claimed"

    tax_annual, ins_monthly, hoa_monthly = _tax_and_insurance(
        deal, profile, assumptions, s["insurance_multiplier_vs_ltr"])

    mgmt_pct = _management_pct(deal, assumptions, s["management_pct_revenue"])

    # Lodging/HOT tax — Victor-calibrated (his TX P&Ls all budget it). Stated
    # figure wins; else % of revenue; $0 only when the platform remits it.
    if deal.get("lodging_tax_platform_remitted"):
        lodging_tax = 0.0
        assumptions["lodging_tax"] = "platform-remitted per listing — verify"
    else:
        lodging_tax, _ = _pick(deal, "lodging_tax_annual", assumptions)
        if lodging_tax is None:
            lodging_tax = revenue * s["lodging_tax_pct_revenue"]
            assumptions["lodging_tax"] = (
                f"assumed {s['lodging_tax_pct_revenue']:.0%} of revenue (state/local HOT)")

    # Cleaning — owner-paid by default (Victor-calibrated); guest-paid only
    # when the deal confirms it.
    if deal.get("cleaning_guest_paid"):
        cleaning_monthly = 0.0
        assumptions["cleaning"] = "guest-paid pass-through (confirmed)"
    else:
        cleaning_monthly, _ = _pick(deal, "cleaning_monthly", assumptions)
        if cleaning_monthly is None:
            cleaning_monthly = s["cleaning_monthly"]
            assumptions["cleaning"] = f"assumed owner-paid ${s['cleaning_monthly']}/mo"

    opex_annual = (
        revenue * mgmt_pct
        + revenue * s["supplies_pct_revenue"]
        + revenue * s["platform_fees_pct_revenue"]
        + revenue * profile["assumptions"]["ltr"]["capex_pct_rent"]
        + lodging_tax
        + cleaning_monthly * 12
        + s["utilities_monthly"] * 12
        + ins_monthly * 12
        + hoa_monthly * 12
        + tax_annual
    )
    annual_noi = metrics.noi(revenue, opex_annual)
    annual_cf = annual_noi - fin["annual_debt_service"]

    furnishing = 0 if deal.get("furnished") else s["furnishing_capex"]
    if furnishing:
        assumptions["furnishing"] = f"assumed unfurnished: ${furnishing:,} capex added to cash needed"
    cash_invested = fin["down_payment"] + fin["closing_costs"] + furnishing

    return {
        "tier": "str", "financing": fin, "assumptions": assumptions,
        "gross_annual_income": revenue, "income_source": rev_src,
        "adr": adr, "occupancy": occupancy, "missing_adr": missing_adr,
        "operating_expenses_annual": opex_annual,
        "noi_annual": annual_noi,
        "annual_cash_flow": annual_cf,
        "monthly_cash_flow": annual_cf / 12,
        "total_cash_invested": cash_invested,
        "metrics": {
            "gross_yield": metrics.gross_rental_yield(revenue, fin["price"]),
            "cap_rate": metrics.cap_rate(annual_noi, fin["price"]),
            "coc": metrics.cash_on_cash(annual_cf, cash_invested),
            "dscr": metrics.dscr(annual_noi, fin["annual_debt_service"]),
            "annual_cash_flow": annual_cf,
            "occupancy": occupancy,
            "break_even_occupancy": metrics.break_even_occupancy(
                opex_annual + fin["annual_debt_service"], adr or 0),
            "ltv": fin["ltv"],
        },
    }


def _underwrite_ltr(deal: dict, profile: dict) -> dict:
    assumptions: dict = {}
    a = profile["assumptions"]["ltr"]
    fin = _financing(deal, profile, assumptions,
                     profile["assumptions"]["financing"]["down_payment_pct_ltr"])

    monthly_rent, rent_src = _pick(deal, "monthly_rent", assumptions)
    monthly_rent = monthly_rent or 0.0
    gross_annual = monthly_rent * 12
    vacancy = a["vacancy"]
    egi = gross_annual * (1 - vacancy)
    assumptions.setdefault("vacancy", f"assumed: {vacancy:.0%}")

    tax_annual, ins_monthly, hoa_monthly = _tax_and_insurance(deal, profile, assumptions)
    mgmt_pct = _management_pct(deal, assumptions, a["management_pct_rent"])
    opex_annual = (
        gross_annual * a["capex_pct_rent"]
        + gross_annual * mgmt_pct
        + ins_monthly * 12
        + hoa_monthly * 12
        + tax_annual
    )
    annual_noi = metrics.noi(egi, opex_annual)
    annual_cf = annual_noi - fin["annual_debt_service"]
    cash_invested = fin["down_payment"] + fin["closing_costs"]

    return {
        "tier": "ltr", "financing": fin, "assumptions": assumptions,
        "gross_annual_income": gross_annual, "income_source": rent_src,
        "monthly_rent": monthly_rent,
        "operating_expenses_annual": opex_annual,
        "noi_annual": annual_noi,
        "annual_cash_flow": annual_cf,
        "monthly_cash_flow": annual_cf / 12,
        "total_cash_invested": cash_invested,
        "metrics": {
            "grm": metrics.grm(fin["price"], gross_annual),
            "cap_rate": metrics.cap_rate(annual_noi, fin["price"]),
            "coc": metrics.cash_on_cash(annual_cf, cash_invested),
            "one_pct_rule": metrics.one_percent_rule(monthly_rent, fin["price"]),
            "gross_yield": metrics.gross_rental_yield(gross_annual, fin["price"]),
            "dscr": metrics.dscr(annual_noi, fin["annual_debt_service"]),
            "annual_cash_flow": annual_cf,
            "ltv": fin["ltv"],
        },
    }


def _underwrite_house_hack(deal: dict, profile: dict) -> dict:
    assumptions: dict = {}
    assumptions["financing"] = "assumed FHA owner-occupant, 3.5% down"
    fin = _financing(dict(deal, down_payment_pct=deal.get("down_payment_pct") or 0.035),
                     profile, assumptions, 0.035)

    # Rent from the unit(s) the owner does NOT occupy.
    other_rent, rent_src = _pick(deal, "other_units_monthly_rent", assumptions)
    if other_rent is None:
        total_rent, rent_src = _pick(deal, "monthly_rent", assumptions)
        units = deal.get("units") or 2
        other_rent = (total_rent or 0) * (units - 1) / units
        if total_rent:
            assumptions["other_units_monthly_rent"] = (
                f"derived: total rent x {units - 1}/{units} units")

    tax_annual, ins_monthly, hoa_monthly = _tax_and_insurance(deal, profile, assumptions)
    total_monthly_payment = fin["monthly_pi"] + tax_annual / 12 + ins_monthly + hoa_monthly
    coverage = metrics.rental_coverage(other_rent or 0, total_monthly_payment)
    net_housing_cost = total_monthly_payment - (other_rent or 0)

    return {
        "tier": "house_hack", "financing": fin, "assumptions": assumptions,
        "other_units_monthly_rent": other_rent or 0, "income_source": rent_src,
        "total_monthly_payment": total_monthly_payment,
        "net_housing_cost_monthly": net_housing_cost,
        "total_cash_invested": fin["down_payment"] + fin["closing_costs"],
        "annual_cash_flow": -net_housing_cost * 12,  # housing-cost reduction, not income
        "monthly_cash_flow": -net_housing_cost,
        "metrics": {
            "rental_coverage": coverage,
            "net_housing_cost_monthly": net_housing_cost,
            "units": deal.get("units") or 0,
            "ltv": fin["ltv"],
        },
    }
