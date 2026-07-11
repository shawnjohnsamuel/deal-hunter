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
    """Destination-market cabin that should PASS under the v2.2.1
    Victor-calibrated expense defaults (owner-paid cleaning + 7% lodging tax)."""
    return {
        "address": "123 Pine Ridge Trl", "city": "Broken Bow", "state": "OK",
        "property_type": "cabin", "units": 1, "price": 450000, "furnished": False,
        "claimed": {},
        "enriched": {"adr": 425, "occupancy": 0.70},
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


def test_kill_str_non_destination_teaser_only(profile):
    # Two-tier rule (v2.2.1): teaser-newsletter non-destination STRs die at the
    # kill filter; agent/manual ones proceed to scoring (capped at BORDERLINE).
    teaser = broken_bow_str() | {"city": "Frisco", "source_kind": "teaser_paywall"}
    killed, reasons, _ = run_kill_filter(teaser, profile)
    assert killed and "non-destination" in reasons[0]

    agent = broken_bow_str() | {"city": "Frisco", "source_kind": "agent_full_address"}
    killed2, _, _ = run_kill_filter(agent, profile)
    assert not killed2


def test_non_destination_str_capped_at_borderline(profile):
    # Same numbers PASS in Broken Bow; in Frisco (agent-sourced) the verdict is
    # capped at BORDERLINE with the note last in the red flags (card detail).
    assert score_deal(broken_bow_str(), profile)["verdict"] == "PASS"
    metro = broken_bow_str() | {"city": "Frisco", "source_kind": "agent_full_address"}
    result = score_deal(metro, profile)
    assert result["verdict"] == "BORDERLINE"
    assert "capped at BORDERLINE" in result["red_flags"][-1]


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
    assert m["gross_yield"] == pytest.approx(0.241, abs=0.005)
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


# --- Iteration 2: teaser keys, mountain priority, email links ------------

def test_deal_key_for_teaser_fallback():
    from pipeline.dedupe import deal_key_for
    teaser = {"city": "Gatlinburg", "state": "TN", "price": 585000,
              "beds": 3, "baths": 3, "sqft": 1850}
    assert deal_key_for(teaser) == deal_key_for(dict(teaser))
    assert deal_key_for(teaser).startswith("t")
    identified = dict(teaser, address="210 Chalet Village Way")
    assert deal_key_for(identified) != deal_key_for(teaser)
    assert not deal_key_for(identified).startswith("t")


def test_market_flavor():
    from pipeline.markets import market_flavor
    assert market_flavor("Broken Bow") == "mountain"
    assert market_flavor("Gatlinburg") == "mountain"
    assert market_flavor("Galveston") == "beach"
    assert market_flavor("Canyon Lake") == "lake_river"
    assert market_flavor("Tulsa") is None


def test_mountain_priority_bonus(profile):
    mountain = score_deal(broken_bow_str(), profile)
    beach = score_deal(broken_bow_str() | {"city": "Galveston", "state": "TX"}, profile)
    bonus = profile["buy_boxes"]["str"]["mountain_priority_bonus"]
    assert mountain["priority_note"] and "MOUNTAIN" in mountain["priority_note"]
    assert beach["priority_note"] is None
    assert mountain["score"] == pytest.approx(beach["score"] + bonus, abs=0.2)


def test_gmail_link_builder():
    from pipeline.ingest_gmail import gmail_link
    assert gmail_link("<abc@mail.beehiiv.com>", None) == \
        "https://mail.google.com/mail/u/0/#search/rfc822msgid:abc@mail.beehiiv.com"
    assert gmail_link(None, "18f2a") == "https://mail.google.com/mail/u/0/#all/18f2a"
    assert gmail_link(None, None) is None


def test_identified_teaser_gets_verification_flag(profile):
    deal = broken_bow_str() | {
        "teaser": True,
        "identification": {"confidence": "medium", "candidate_address": "123 Pine Ridge Trl",
                           "evidence": "price+beds match"},
    }
    result = score_deal(deal, profile)
    assert any("IDENTIFIED VIA RESEARCH" in f and "MEDIUM" in f for f in result["red_flags"])


def test_unidentified_teaser_flag(profile):
    deal = {"city": "Gatlinburg", "state": "TN", "price": 500000, "tier": "str",
            "teaser": True, "claimed": {"adr": 300, "occupancy": 0.68}}
    result = score_deal(deal, profile)
    assert any("UNIDENTIFIED" in f for f in result["red_flags"])


# --- v3: four pillars, divergence, exception factors ----------------------

def test_pillar_cash_flow_bands(profile):
    # Broken Bow: CoC 9.7% (>=8% min, <12% target) -> B
    result = score_deal(broken_bow_str(), profile)
    p = result["pillars"]
    assert p["cash_flow"]["grade"] == "B"
    assert p["cash_flow"]["provenance"] == "computed"
    # Vacancy graded from enriched occupancy (70% >= 65% min) -> B
    assert p["vacancy"]["grade"] == "B"
    # No asset/neighborhood data -> ungraded, never guessed
    assert p["asset_quality"]["grade"] is None
    assert p["asset_quality"]["provenance"] == "ungraded"


def test_pillar_str_coc_floor_is_d(profile):
    # Hochatown fixture: CoC ~3.1% < 6% floor -> D even though DSCR > 1
    deal = {"address": "88 Lakeview Loop", "city": "Hochatown", "state": "OK",
            "property_type": "cabin", "units": 1, "price": 540000, "furnished": False,
            "claimed": {}, "enriched": {"adr": 375, "occupancy": 0.66}, "tier": "str"}
    result = score_deal(deal, profile)
    assert result["pillars"]["cash_flow"]["grade"] == "D"


def test_victor_grades_win_and_are_marked(profile):
    deal = broken_bow_str() | {"victor": {"grades": {
        "asset_quality": "A", "neighborhood": "B+", "vacancy": "a"}}}
    result = score_deal(deal, profile)
    p = result["pillars"]
    assert p["asset_quality"] == {"grade": "A", "provenance": "victor", "note": ""}
    assert p["neighborhood"]["grade"] == "B"      # B+ normalizes
    assert p["vacancy"]["grade"] == "A"           # lowercase normalizes; beats computed


def test_estimated_grades_marked_estimated(profile):
    deal = broken_bow_str()
    deal["enriched"]["pillar_estimates"] = {
        "asset_quality": {"grade": "B", "why": "2019 build, turnkey per listing"}}
    result = score_deal(deal, profile)
    p = result["pillars"]["asset_quality"]
    assert p["grade"] == "B" and p["provenance"] == "estimated"


def test_neighborhood_d_hard_disqualifies(profile):
    deal = broken_bow_str() | {"victor": {"grades": {"neighborhood": "D"}}}
    result = score_deal(deal, profile)
    assert result["verdict"] == "FAIL"
    assert any("we don't do D" in d for d in result["hard_disqualifiers"])


def test_divergence_flagged(profile):
    deal = broken_bow_str()
    # Our computed monthly CF is ~$797; Victor claiming $1,500 is >10% apart
    deal["victor"] = {"underwriting": {"cash_flow_monthly": 1500}}
    result = score_deal(deal, profile)
    assert any("DIVERGENCE on monthly cash flow" in f for f in result["red_flags"])


def test_no_divergence_when_close(profile):
    deal = broken_bow_str()
    deal["victor"] = {"underwriting": {"cash_flow_monthly": 820}}  # within 10% of ours
    result = score_deal(deal, profile)
    assert not any("DIVERGENCE" in f for f in result["red_flags"])


def test_exception_factors_bonus_and_surfaced(profile):
    plain = score_deal(broken_bow_str(), profile)
    deal = broken_bow_str() | {"exception_factors": [
        {"type": "walk_in_equity", "note": "comps at $520k, listed $475k"}]}
    boosted = score_deal(deal, profile)
    assert boosted["score"] == pytest.approx(
        plain["score"] + profile["pillars"]["exception_factor_bonus"], abs=0.2)
    assert any("walk in equity" in e for e in boosted["exception_factors"])


def test_exception_factors_never_flip_fail(profile):
    deal = broken_bow_str() | {"str_restricted": True,
                               "exception_factors": [{"type": "financing_incentive", "note": "2% seller buydown"}]}
    result = score_deal(deal, profile)
    assert result["verdict"] == "FAIL" and result["score"] <= 25


def test_victor_stated_insurance_and_management_used(profile):
    deal = broken_bow_str()
    deal["claimed"] = {"insurance_monthly": 280, "management_pct": 18}
    result = score_deal(deal, profile)
    # Cheaper real insurance + mgmt than defaults -> better CoC than baseline
    baseline = score_deal(broken_bow_str(), profile)
    assert result["underwriting"]["metrics"]["coc"] > baseline["underwriting"]["metrics"]["coc"]


# --- v3: .eml ingestion ---------------------------------------------------

def test_load_eml(tmp_path):
    from email.message import EmailMessage
    from pipeline.eml import load_eml_inputs

    msg = EmailMessage()
    msg["From"] = "Victor Steffen <victor@steffenrealtycorp.com>"
    msg["Subject"] = "Occupied Sherman SFR - strong B/B/A"
    msg["Date"] = "Fri, 10 Jul 2026 08:00:00 -0500"
    msg["Message-ID"] = "<abc123@steffenrealtycorp.com>"
    msg.set_content("Plain text: 902 Crockett St, Sherman TX. $225,000. Rent $2,550.")
    msg.add_alternative(
        "<html><body><p>902 Crockett St, Sherman TX — <b>$225,000</b>, rent $2,550/mo.</p>"
        "<a href='https://example.com/listing'>View</a></body></html>",
        subtype="html")
    p = tmp_path / "victor.eml"
    with open(p, "wb") as f:
        f.write(bytes(msg))

    emails = load_eml_inputs(str(p))
    assert len(emails) == 1
    em = emails[0]
    assert em["sender"] == "victor@steffenrealtycorp.com"
    assert em["sender_name"].startswith("Victor Steffen")
    assert em["sender_kind"] == "agent_full_address"
    assert "902 Crockett St" in em["text"]
    assert em["link"] == "https://mail.google.com/mail/u/0/#search/rfc822msgid:abc123@steffenrealtycorp.com"

    # Directory form
    emails2 = load_eml_inputs(str(tmp_path))
    assert len(emails2) == 1


def test_kill_ceiling_respects_seller_financing(profile):
    # $800k at default 15% down -> dead; at stated 10% seller financing -> survives with flag
    deal = broken_bow_str() | {"price": 800000}
    killed, reasons, _ = run_kill_filter(deal, profile)
    assert killed and "down-payment budget" in reasons[0]
    financed = broken_bow_str() | {"price": 800000, "down_payment_pct": 0.10}
    killed2, _, flags2 = run_kill_filter(financed, profile)
    assert not killed2
    assert any("financing" in f for f in flags2)


def test_str_expense_overrides(profile):
    # Guest-paid cleaning + platform-remitted lodging tax lift cash flow vs defaults
    base = score_deal(broken_bow_str(), profile)
    lean = score_deal(broken_bow_str() | {"cleaning_guest_paid": True,
                                          "lodging_tax_platform_remitted": True}, profile)
    diff = lean["underwriting"]["annual_cash_flow"] - base["underwriting"]["annual_cash_flow"]
    # default cleaning 725*12 + lodging 7% of ~108.6k revenue ≈ $16.3k
    assert diff == pytest.approx(725 * 12 + 108588 * 0.07, rel=0.02)
    a = lean["underwriting"]["assumptions"]
    assert "guest-paid" in a["cleaning"] and "platform-remitted" in a["lodging_tax"]


def test_str_stated_lodging_tax_wins(profile):
    deal = broken_bow_str()
    deal["claimed"]["lodging_tax_annual"] = 5000
    deal["claimed"]["cleaning_monthly"] = 600
    result = score_deal(deal, profile)
    default = score_deal(broken_bow_str(), profile)
    # stated $5,000 HOT (< 7% default ≈ $7,601) and $600 cleaning (< $725) -> higher CF
    assert result["underwriting"]["annual_cash_flow"] > default["underwriting"]["annual_cash_flow"]
