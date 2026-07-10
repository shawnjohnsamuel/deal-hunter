"""Pure metric math. No I/O, no LLM, no profile lookups — numbers in, numbers out.

Formulas follow framework-v2.md §7. Percent metrics are returned as decimals
(0.08 == 8%).
"""


def monthly_mortgage_payment(loan_amount: float, annual_rate: float, term_years: int = 30) -> float:
    """Standard amortized P&I payment."""
    if loan_amount <= 0:
        return 0.0
    r = annual_rate / 12
    n = term_years * 12
    if r == 0:
        return loan_amount / n
    return loan_amount * r * (1 + r) ** n / ((1 + r) ** n - 1)


def noi(effective_gross_income: float, operating_expenses: float) -> float:
    """Annual NOI. Operating expenses exclude debt service."""
    return effective_gross_income - operating_expenses


def cap_rate(annual_noi: float, price: float) -> float:
    return annual_noi / price if price else 0.0


def cash_on_cash(annual_cash_flow: float, total_cash_invested: float) -> float:
    return annual_cash_flow / total_cash_invested if total_cash_invested else 0.0


def grm(price: float, gross_annual_rent: float) -> float:
    return price / gross_annual_rent if gross_annual_rent else float("inf")


def one_percent_rule(monthly_rent: float, price: float) -> float:
    return monthly_rent / price if price else 0.0


def gross_rental_yield(gross_annual_income: float, price: float) -> float:
    return gross_annual_income / price if price else 0.0


def dscr(annual_noi: float, annual_debt_service: float) -> float:
    return annual_noi / annual_debt_service if annual_debt_service else float("inf")


def break_even_occupancy(total_annual_costs: float, adr: float) -> float:
    """Occupancy needed to cover ALL costs (operating + debt service)."""
    if not adr:
        return float("inf")
    return total_annual_costs / (adr * 365)


def rental_coverage(other_units_monthly_rent: float, total_monthly_payment: float) -> float:
    """House hack: what share of the full payment the rented units cover."""
    return other_units_monthly_rent / total_monthly_payment if total_monthly_payment else 0.0


def ltv(loan_amount: float, price: float) -> float:
    return loan_amount / price if price else 0.0
