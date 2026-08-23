"""Parser tests for the recurring deal-flow email formats.

These lock in the field extraction so a hunt does not have to re-derive it —
and so a template change (a swapped emoji, a renamed row) fails loudly here
instead of silently producing price-less or address-less deals.
"""
from pipeline.parse_sources import (
    _slug_to_address, parse_bnbflow, parse_here, parse_message,
    parse_offersheet_daily, parse_offersheet_spotlight, parse_victor,
)


def test_slug_to_address_handles_multiword_cities_and_units():
    assert _slug_to_address("855-sullivant-ave-columbus-oh-43223")[:3] == \
        ("855 Sullivant Ave", "Columbus", "OH")
    # multi-word city
    assert _slug_to_address("40-long-leaf-cir-santa-rosa-beach-fl-32459")[:3] == \
        ("40 Long Leaf Cir", "Santa Rosa Beach", "FL")
    # 'creek'/'ridge' are street suffixes AND city words — the city must win
    assert _slug_to_address("22447-s-214th-street-queen-creek-az-85142")[:3] == \
        ("22447 S 214th Street", "Queen Creek", "AZ")
    assert _slug_to_address("1049-rock-water-rd-blue-ridge-ga-30513")[:3] == \
        ("1049 Rock Water Rd", "Blue Ridge", "GA")
    # trailing unit number stays with the street
    assert _slug_to_address("2691-jessie-rd-1-sevierville-tn-37876")[:3] == \
        ("2691 Jessie Rd 1", "Sevierville", "TN")


DAILY = """
# [497 Bear Ridge Rd, Franklin, NC 28734](https://www.theoffersheet.app/properties/x)
\U0001F4B0 $259,000
\U0001F6CF️ 2 Bedrooms, 2 Bathrooms
\U0001F319 Average Daily Rate: $254
\U0001F4C5 Expected Occupancy Rate: 60%
\U0001F4CA **Expected Cash on Cash Return: 38.7%**

# [12 Scenic Vista Lane, Bartlett, NH 03812](https://www.theoffersheet.app/properties/y)
\U0001F4B5 $529,000
\U0001F6CF️ 3 Bedrooms, 2 Bathrooms
\U0001F319 Average Daily Rate: $288
\U0001F4C5 Expected Occupancy Rate: 61%
"""


def test_offersheet_daily_parses_both_money_emojis():
    d = parse_offersheet_daily(DAILY, "mid1", "July 21: 11 Potential STRs", "2026-07-21")
    assert len(d) == 2
    assert d[0]["address"] == "497 Bear Ridge Rd" and d[0]["city"] == "Franklin"
    assert d[0]["price"] == 259000 and d[0]["beds"] == 2
    assert d[0]["claimed"]["adr"] == 254 and d[0]["claimed"]["occupancy"] == 0.60
    # the alternate money emoji must not produce a price-less deal
    assert d[1]["price"] == 529000 and d[1]["parse_confidence"] == "high"


SPOTLIGHT = """
SUBJECT: \U0001F4B0 $96K+ in Annual Revenue on This Turnkey Mountain Airbnb
\U0001F44D [Express Interest](https://www.theoffersheet.app/contact/210-savannah-ln-stanley-va-22851)
### \U0001F3D4 $496K • $96K+ Verified Annual Revenue • 3 Bedrooms • 2 Bathrooms • 1,512 Sq Ft
### \U0001F4B0 Offered at: $496,000
* 3 Bedrooms
* 2 Bathrooms
* 1,512 Sq Ft
**$96,000 in Verified Annual Gross Revenue**
"""


def test_offersheet_spotlight_extracts_address_from_contact_slug():
    d = parse_offersheet_spotlight(SPOTLIGHT, "mid2", "s", "2026-08-15")[0]
    assert d["address"] == "210 Savannah Ln" and d["city"] == "Stanley"
    assert d["state"] == "VA" and d["price"] == 496000
    assert d["beds"] == 3 and d["sqft"] == 1512
    assert d["claimed"]["annual_str_revenue"] == 96000
    assert d["parse_confidence"] == "high"


PROJECTED = """
[x](https://www.theoffersheet.app/contact/213-matterhorn-dr-gatlinburg-tn-37738)
### \U0001F4B0 Offered at: $2,425,000
* 8 Bedrooms
**Projected Gross Revenue: $210,000 Annually**
"""


def test_projected_revenue_is_flagged_for_review():
    d = parse_offersheet_spotlight(PROJECTED, "mid3", "s", "2026-08-16")[0]
    assert d["claimed"]["annual_str_revenue"] == 210000
    assert d["parse_confidence"] == "review"
    assert "PROJECTED" in d["notes"]


HERE = """
## [13475 Chumstick Hwy, Leavenworth, WA 98826](https://www.zillow.com/homedetails/a/1_zpid/)
* $408,800

* 2 BR / 1 BA

* 864 sq/ft

* Average Daily Rate: $331

* Occupancy Rate: 62%
"""


def test_here_parses_block():
    d = parse_here(HERE, "mid4", "#1068", "2026-07-21")[0]
    assert d["city"] == "Leavenworth" and d["price"] == 408800
    assert d["beds"] == 2 and d["sqft"] == 864
    assert d["claimed"]["adr"] == 331 and d["listing_urls"]


BNB = """
### [167 Valley View Dr, Albrightsville, PA 18210](https://www.zillow.com/homedetails/b/2_zpid/)
* **List Price: **$499,900
* **Layout:** 4 Bedroom, 2 Bathroom
* **Average Daily Rate (ADR):** $438
* **Occupancy Rate:** 52%
* **Estimated Revenue:** $83,200
"""


def test_bnbflow_marks_revenue_as_estimate():
    d = parse_bnbflow(BNB, "mid5", "Northeast", "2026-07-20")[0]
    assert d["price"] == 499900 and d["beds"] == 4
    assert d["claimed"]["annual_str_revenue"] == 83200
    assert "ESTIMATE" in d["notes"]


VICTOR = """
**1) Port Lavaca Quad Producing $5,000/mo $374,900**
$5,000 per month is already in place across four fully occupied 2-bedroom units.
[1601 Meadowview Dr Port Lavaca TX 77979](https://redf.in/3Ei7Xo)

**2) South Austin Turnkey PROVEN PRODUCER STR $510K**
$90,000 in gross Airbnb income annualizes to roughly $108,000 against a $510,000 purchase price.
[3410 Plantation Rd Austin TX 78745](https://redf.in/884Sp9)
"""


def test_victor_parses_price_rent_units_and_str_hint():
    d = parse_victor(VICTOR, "mid6", "7 deals", "2026-07-22")
    assert len(d) == 2
    quad = d[0]
    assert quad["address"] == "1601 Meadowview Dr" and quad["city"] == "Port Lavaca"
    assert quad["price"] == 374900 and quad["claimed"]["monthly_rent"] == 5000
    assert quad["units"] == 4
    str_deal = d[1]
    assert str_deal["source_tier_hint"] == "str"
    assert str_deal["price"] == 510000


def test_parse_message_dispatches_on_sender():
    msg = ("SUBJECT: Northeast\nSENDER: team@bnbflow.co\n"
           "DATE: 2026-07-20T00:00:00Z\nMSGID: abc\n" + "=" * 60 + "\n" + BNB)
    d = parse_message(msg)
    assert len(d) == 1 and d[0]["source"] == "bnb_flow"
    assert d[0]["email_link"].endswith("abc")


PRICE_VARIANTS = """
[x](https://www.theoffersheet.app/contact/1403-waterfront-dr-tobyhanna-pa-18466)
Offered at just **$399,900**, this established Poconos STR has generated:
\U0001F4B0 **Price: $399,900**
* 4 Bedrooms
**$96,000 in Verified Annual Gross Revenue**
"""


def test_spotlight_price_variants():
    """'Offered at just **$X**' and '**Price: $X**' are both used in the wild;
    missing them silently produced a price-less (unscorable) deal."""
    d = parse_offersheet_spotlight(PRICE_VARIANTS, "m", "s", "2026-08-21")[0]
    assert d["price"] == 399900
    assert d["city"] == "Tobyhanna" and d["state"] == "PA"
    assert d["claimed"]["annual_str_revenue"] == 96000


def test_spotlight_revenue_shorthand_and_phrasings():
    """'$96K' shorthand and 'verifiable STR rental income' both appear; missing
    them left a priced deal with zero revenue, which scores as a disaster."""
    from pipeline.parse_sources import _money_k
    assert _money_k("96K") == 96000 and _money_k("1.2M") == 1200000
    assert _money_k("96,000") == 96000
    txt = ("[x](https://www.theoffersheet.app/contact/1403-waterfront-dr-tobyhanna-pa-18466)\n"
           "Offered at just **$399,900**\n"
           "* 4 Bedrooms\n"
           "$96,000 in verifiable STR rental income\n")
    d = parse_offersheet_spotlight(txt, "m", "s", "2026-08-21")[0]
    assert d["price"] == 399900
    assert d["claimed"]["annual_str_revenue"] == 96000
