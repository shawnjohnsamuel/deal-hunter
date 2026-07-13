"""Redfin client + enrichment mapping against captured live fixtures
(tests/fixtures/redfin/*, recorded 2026-07-12). No live calls in CI."""
import json
from pathlib import Path

import pytest

from pipeline import redfin

FIXTURES = Path(__file__).parent / "fixtures" / "redfin"


def load(name):
    return json.load(open(FIXTURES / name))["data"]


@pytest.fixture
def search_results():
    return load("search_18426.json")["results"]


@pytest.fixture
def bartleson_details():
    return load("details_bartleson.json")


def test_find_property_matches_normalized_address(search_results):
    rec = redfin.find_property("106 Bartleson Deer Trail", results=search_results)
    assert rec and rec["property_id"] == "138181597"
    assert rec["price"] == 420000 and rec["beds"] == 3


def test_find_property_no_match(search_results):
    assert redfin.find_property("1 Nonexistent Blvd", results=search_results) is None


def test_latest_tax(bartleson_details):
    # 2026 tax year: $1,941.74 — vs the 1.2% fallback ($5,040) this is 61% lower
    assert redfin.latest_tax(bartleson_details) == pytest.approx(1941.74)


def test_hoa_and_estimate(bartleson_details):
    assert redfin.hoa_monthly_from(bartleson_details) is None  # no-HOA claim verified
    assert bartleson_details["redfin_estimate"] == 421385


def test_price_history_note(bartleson_details):
    note = redfin.price_history_note(bartleson_details)
    assert "Listed" in note and "420,000" in note


def test_hoa_frequency_conversion():
    assert redfin.hoa_monthly_from({"hoa_dues": 1200, "hoa_frequency": "Yearly"}) == 100
    assert redfin.hoa_monthly_from({"hoa_dues": 300, "hoa_frequency": "Quarterly"}) == 100
    assert redfin.hoa_monthly_from({"hoa_dues": 85, "hoa_frequency": "Monthly"}) == 85
    assert redfin.hoa_monthly_from({}) is None


def test_enrich_mapping(monkeypatch, search_results, bartleson_details):
    from pipeline.enrich import _redfin
    monkeypatch.setattr(redfin, "available", lambda: True)
    monkeypatch.setattr(redfin, "search", lambda loc: search_results)
    monkeypatch.setattr(redfin, "property_details", lambda pid: bartleson_details)

    deal = {"address": "106 Bartleson Deer Trl", "city": "Greentown", "state": "PA",
            "zip": "18426", "price": 420000}
    enriched = {}
    _redfin(deal, enriched)
    assert enriched["property_tax_annual"] == pytest.approx(1941.74)
    assert enriched["listing_status"] == "Active"
    assert enriched["avm"] == 421385
    assert enriched["photo_url"].startswith("https://ssl.cdn-redfin.com/")
    assert deal["sqft"] == 1128          # backfilled from the listing
    assert any("redfin.com" in u for u in deal["listing_urls"])


def test_identify_via_redfin_unique_match(monkeypatch, search_results):
    from pipeline.identify import _identify_via_redfin
    monkeypatch.setattr(redfin, "available", lambda: True)
    monkeypatch.setattr(redfin, "search", lambda loc: search_results)

    teaser = {"city": "Greentown", "state": "PA", "price": 420000, "beds": 3, "teaser": True}
    assert _identify_via_redfin(teaser) is True
    assert teaser["address"] == "106 Bartleson Deer Trl"
    assert teaser["identification"]["confidence"] == "high"


def test_identify_via_redfin_no_match(monkeypatch, search_results):
    from pipeline.identify import _identify_via_redfin
    monkeypatch.setattr(redfin, "available", lambda: True)
    monkeypatch.setattr(redfin, "search", lambda loc: search_results)
    teaser = {"city": "Greentown", "state": "PA", "price": 123456, "beds": 9}
    assert _identify_via_redfin(teaser) is False
    assert "address" not in teaser


def test_fixtures_contain_no_embedded_secrets():
    """Raw API responses can embed third-party keys (e.g. Redfin's Google Maps
    key in static_map_url — GitHub alert #1). Fixtures must be scrubbed."""
    import re
    patterns = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|sk-[A-Za-z0-9]{20,}|api[_-]?key=[A-Za-z0-9]")
    for f in FIXTURES.rglob("*.json"):
        text = f.read_text()
        assert not patterns.search(text), f"embedded credential-like string in {f.name}"
