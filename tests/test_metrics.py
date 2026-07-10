"""Metric math vs hand-calculated values."""
import pytest

from pipeline import metrics


def test_mortgage_payment_standard():
    # $400,000 @ 7.25% / 30yr — verified against standard amortization: $2,728.71
    assert metrics.monthly_mortgage_payment(400000, 0.0725, 30) == pytest.approx(2728.71, abs=1)


def test_mortgage_payment_zero_loan():
    assert metrics.monthly_mortgage_payment(0, 0.07) == 0.0


def test_cap_rate():
    assert metrics.cap_rate(24000, 300000) == pytest.approx(0.08)


def test_cash_on_cash():
    assert metrics.cash_on_cash(9000, 75000) == pytest.approx(0.12)
    assert metrics.cash_on_cash(9000, 0) == 0.0


def test_grm():
    assert metrics.grm(240000, 24000) == pytest.approx(10.0)
    assert metrics.grm(240000, 0) == float("inf")


def test_one_percent_rule():
    assert metrics.one_percent_rule(2000, 200000) == pytest.approx(0.01)


def test_gross_rental_yield():
    assert metrics.gross_rental_yield(80000, 400000) == pytest.approx(0.20)


def test_dscr():
    assert metrics.dscr(30000, 24000) == pytest.approx(1.25)


def test_break_even_occupancy():
    # $80k total costs, $350 ADR: 80000 / (350*365) = 62.6%
    assert metrics.break_even_occupancy(80000, 350) == pytest.approx(0.6262, abs=1e-3)
    assert metrics.break_even_occupancy(80000, 0) == float("inf")


def test_rental_coverage():
    assert metrics.rental_coverage(1800, 3600) == pytest.approx(0.50)


def test_ltv():
    assert metrics.ltv(340000, 400000) == pytest.approx(0.85)
