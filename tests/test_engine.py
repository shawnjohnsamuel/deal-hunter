"""End-to-end engine tests: kill filter, tier classification, scoring, verdicts."""
import pytest

from pipeline.dedupe import deal_key, normalize_address
from pipeline.kill_filter import run_kill_filter
from pipeline.profile import load_profile
from pipeline.score import classify_tier, score_deal


@pytest.fixture
def profile():
    return load_profile()


# --- Fixtures -----------------------------------------------------------

def broken_bow_str():
    """Destination-market cabin that should PASS."""
    return {
        "address": "123 Pine Ridge Trl", "city": "Broken Bow", "state": "OK",
        "property_type": "cabin", "units": 1, "price": 475000, "furnished": False,
        "claimed": {},
        "enriched": {"adr": 350, "occupancy": 0.70},
        "tier": "str",
    }


def dfw_ltr_weak():
    """Survives the kill filter but fails underwriting (DSCR < 1)."""
    return {
        "address": "456 Suburbia Ln", "city": "Little Elm", "state": "TX",
        "property_type": "SFR", "units": 1, "price": 385000,
        "claimed": {"monthly_rent": 2600},
        "tier": "ltr",
    }


def dallas_house_hack():
    return {
        "address": "789 Duplex Dr", "city": "Dallas", "state": "TX",
        "property_type": "duplex", "units": 2, "price": 420000,
        "claimed": {"other_units_monthly_rent": 1800},
        "tier": "house_hack",
    }


# --- Kill filter --------------------------------------------------------

def test_kill_str_over_price_ceiling(profile):
    deal = broken_bow_str() | {"price": 650000}
    killed, reasons, _ = run_kill_filter(deal, profile)
    assert killed and "ceiling" in reasons[0]


def test_kill_str_non_destination(profile):
    deal = broken_bow_str() | {"city": "Frisco"}
    killed, reasons, _ = run_kill_filter(deal, profile)
    assert killed and "non-destination" in reasons[0]


def test_unknown_market_flags_but_does_not_kill(profile):
    deal = broken_bow_str() | {"city": "Somewheresville"}
    killed, _, flags = run_kill_filter(deal, profile)
    assert not killed
    assert any("judgment call" in f for f in flags)


def test_kill_house_hack_over_450k(profile):
    deal = dallas_house_hack() | {"price": 500000}
    killed, reasons, _ = run_kill_filter(deal, profile)
    assert killed and "house-hack ceiling" in reasons[0]


def test_kill_ltr_fails_sellers_own_math(profile):
    deal = {"address": "1 Overpriced Way", "city": "Anna", "state": "TX",
            "price": 385000, "claimed": {"monthly_rent": 2200}, "tier": "ltr"}
    killed, reasons, _ = run_kill_filter(deal, profile)
    assert killed and "seller's own math" in reasons[0]


def test_ltr_survives_kill_when_grm_ok(profile):
    killed, _, _ = run_kill_filter(dfw_ltr_weak(), profile)
    assert not killed


def test_no_price_passes_with_flag(profile):
    killed, _, flags = run_kill_filter({"address": "x", "city": "Dallas", "tier": "ltr"}, profile)
    assert not killed and any("no price" in f for f in flags)


# --- Tier classification ------------------------------------------------

def test_classify_dfw_duplex_as_house_hack(profile):
    deal = dallas_house_hack()
    del deal["tier"]
    assert classify_tier(deal, profile) == "house_hack"


def test_classify_destination_market_as_str(profile):
    deal = broken_bow_str()
    del deal["tier"]
    assert classify_tier(deal, profile) == "str"


def test_classify_default_ltr(profile):
    deal = {"address": "x", "city": "Tulsa", "state": "OK", "price": 200000, "units": 1}
    assert classify_tier(deal, profile) == "ltr"


# --- Scoring ------------------------------------------------------------

def test_str_pass(profile):
    result = score_deal(broken_bow_str(), profile)
    assert result["verdict"] == "PASS"
    assert result["score"] > 70
    m = result["underwriting"]["metrics"]
    assert m["gross_yield"] == pytest.approx(0.188, abs=0.005)
    assert m["cap_rate"] > 0.08
    assert m["coc"] > 0.08
    assert m["dscr"] > 1.25
    # Tax triggers: STR loophole + cost seg (price > $300k trigger)
    assert any("STR loophole" in f for f in result["tax_flags"])
    assert any("cost seg" in f for f in result["tax_flags"])
    # STR legality must always ride along unverified
    assert any("STR legality: UNVERIFIED" in f for f in result["red_flags"])


def test_dfw_ltr_fails_on_dscr(profile):
    result = score_deal(dfw_ltr_weak(), profile)
    assert result["verdict"] == "FAIL"
    assert any("DSCR" in d for d in result["hard_disqualifiers"])
    assert result["underwriting"]["metrics"]["dscr"] < 1.0


def test_house_hack_borderline(profile):
    result = score_deal(dallas_house_hack(), profile)
    # coverage ~48-49% vs 50% min → near-miss → BORDERLINE
    assert result["verdict"] == "BORDERLINE"
    cov = result["underwriting"]["metrics"]["rental_coverage"]
    assert 0.42 < cov < 0.50


def test_hoa_restriction_hard_fails_str(profile):
    deal = broken_bow_str() | {"str_restricted": True}
    result = score_deal(deal, profile)
    assert result["verdict"] == "FAIL"
    assert any("STR restriction" in d for d in result["hard_disqualifiers"])
    assert result["score"] <= 25


def test_seller_claimed_income_is_flagged(profile):
    deal = broken_bow_str()
    deal["enriched"] = {}
    deal["claimed"] = {"annual_str_revenue": 95000}
    result = score_deal(deal, profile)
    assert any("SELLER-CLAIMED" in f for f in result["red_flags"])
    # No ADR anywhere → framework: flag and ask
    assert any("no ADR" in f for f in result["red_flags"])


def test_assumptions_are_stated(profile):
    result = score_deal(broken_bow_str(), profile)
    a = result["underwriting"]["assumptions"]
    assert "property_tax_annual" in a  # fell back to 1.2% of price
    assert "furnishing" in a           # unfurnished → capex added


# --- Dedupe -------------------------------------------------------------

def test_address_normalization():
    assert normalize_address("123 Pine Ridge Trail", "Broken Bow", "OK") == \
        normalize_address("123 Pine Ridge Trl.", "broken bow", "ok")


def test_deal_key_stable():
    assert deal_key("123 Main Street", "Dallas", "TX") == deal_key("123 Main St", "Dallas", "TX")
