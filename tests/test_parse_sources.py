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


# Every phrasing below shipped in a real spotlight and produced a
# revenue-less deal, which then underwrote at a catastrophic negative CoC.
# The common cause was case: the patterns were lowercase, the emails are
# headline Title Case.
REV_PHRASINGS = [
    ("$120,000 in Revenue in 2025", 120000, "actual"),
    ("**$130,839 in Rental Revenue in 2025**", 130839, "actual"),
    ("💵 **2025 Revenue: $120,000**", 120000, "actual"),
    ("💵 **2025 Gross Bookings: Nearly $60K**", 60000, "actual"),
    ("**$200,000+ in Revenue Last Year on a $999,999 Asking Price**", 200000, "actual"),
    ("**$132,000 in Gross Rental Revenue**", 132000, "actual"),
    ("generated **$45,000 in gross rental revenue in one year**", 45000, "actual"),
    ("💵 **Proven Gross Revenue: $45,000**", 45000, "verified"),
    ("nearly $60,000 in documented gross bookings across Airbnb and Vrbo", 60000, "verified"),
    ("**$96,000 in Verified Annual Gross Revenue**", 96000, "verified"),
    ("**Projected Gross Revenue: $210,000 Annually**", 210000, "projected"),
]


def test_revenue_phrasings_and_kinds():
    from pipeline.parse_sources import _revenue
    for text, amount, kind in REV_PHRASINGS:
        got, got_kind = _revenue(text)
        assert got == amount, f"{text!r} -> {got}"
        assert got_kind == kind, f"{text!r} -> {got_kind}"


def test_projected_never_reads_as_actual():
    """A projected figure sitting next to an actual-shaped phrase must stay
    projected — otherwise a seller's forecast underwrites as proven income."""
    from pipeline.parse_sources import _revenue
    amount, kind = _revenue("**Projected Gross Revenue: $210,000 Annually**")
    assert (amount, kind) == (210000, "projected")
    amount, kind = _revenue("~$157.5K projected 2027 revenue")
    assert kind == "projected"


VICTOR_SLASH_MO = """
----------
**SUMMARY:** Three deals jump out today: a San Antonio triplex, an off-market
quad with built-in equity, and a turnkey Allen STR averaging about $90K a year.

----------**San Antonio New Triplex $6,050/mo $625K**
$6,050/month is the projected rent across three brand-new four-bedroom units.
[726 Arthur St San Antonio TX 78202](https://redf.in/AQX09i)

Sale Price
$ 625,000
Monthly Annual
Income
$ 6,050
$ 72,600
"""


def test_victor_slash_mo_rent_and_no_summary_bleed():
    """Rent is written '/mo' as often as 'per month'. And the opening summary
    names the *other* deals — an unbounded lookback made this triplex a quad."""
    d = parse_victor(VICTOR_SLASH_MO, "m", "s", "2026-08-24")[0]
    assert d["price"] == 625000
    assert d["claimed"]["monthly_rent"] == 6050
    assert d["units"] == 3
    assert "PROJECTED" in d["notes"]


VICTOR_TABLE_ONLY = """
----------**Fully Leased Garland Quad $550K**
Four occupied doors, leases in place through next summer.
[2105 W Walnut St Garland TX 75042](https://redf.in/xx1)

Sale Price
$ 550,000
Monthly Annual
Income
$ 4,600
$ 55,200
"""


def test_victor_falls_back_to_proforma_income_row():
    """When the prose never states a monthly rent, Victor's pasted pro-forma
    table still does — and a rent-less deal underwrites at zero income."""
    d = parse_victor(VICTOR_TABLE_ONLY, "m", "s", "2026-09-03")[0]
    assert d["claimed"]["monthly_rent"] == 4600
    assert d["units"] == 4


VICTOR_PRICE_TRAPS = """
----------**Arlington Legal 8-Unit STR Averaging $228K/yr $1.495M**
$228K average annual gross revenue across five full years from an established
legal STR operation. Eight furnished units are already operating.
[1006 Thannisch Dr Arlington TX 76011](https://redf.in/ebYVlT)

Sale Price
$ 1,450,000

----------**San Antonio Fourplex $5,490/mo Target $675K**
$5,290/month is already coming in across four occupied 3/2.5 units, and I
believe every lease has room for at least a $50/month bump.
[10514 Spring Creek Rd San Antonio TX 78230](https://redf.in/xx2)
"""


def test_victor_price_is_the_headline_ask_not_a_revenue_figure():
    """'$228K/yr' revenue and '$5,490/mo' rent both sit where the old scan
    looked for a price, which turned an $1.5M 8-unit into a $228K bargain and
    scored it at 190% cash-on-cash."""
    deals = parse_victor(VICTOR_PRICE_TRAPS, "m", "s", "2026-09-10")
    by_addr = {d["address"]: d for d in deals}
    eight = by_addr["1006 Thannisch Dr"]
    assert eight["price"] == 1495000
    assert eight["units"] == 8
    assert eight["source_tier_hint"] == "str"
    quad = by_addr["10514 Spring Creek Rd"]
    assert quad["price"] == 675000
    assert quad["claimed"]["monthly_rent"] == 5290


def test_merge_duplicates_prefers_stated_revenue_over_derived_adr():
    """A daily teaser lists the cabin with an estimated ADR; the spotlight days
    later quotes its actual revenue. Keeping the first-seen record underwrote
    the property on the weaker number."""
    from pipeline.parse_sources import merge_duplicates
    daily = {"address": "89 Rocky Mountain Ln", "city": "New Market", "state": "VA",
             "price": 375000, "beds": 2, "email_date": "2026-09-04",
             "source_name": "The Offer Sheet", "claimed": {"adr": 215, "occupancy": 0.67}}
    spot = {"address": "89 Rocky Mountain Ln", "city": "New Market", "state": "VA",
            "price": 375000, "sqft": 992, "email_date": "2026-09-10",
            "source_name": "The Offer Sheet", "claimed": {"annual_str_revenue": 70000}}
    merged = merge_duplicates([daily, spot])
    assert len(merged) == 1
    m = merged[0]
    assert m["claimed"]["annual_str_revenue"] == 70000
    # the weaker record's extra detail is still absorbed
    assert m["claimed"]["occupancy"] == 0.67
    assert m["beds"] == 2 and m["sqft"] == 992


def test_merge_duplicates_records_a_price_change():
    from pipeline.parse_sources import merge_duplicates
    first = {"address": "1 A St", "state": "PA", "price": 499000,
             "email_date": "2026-08-24", "source_name": "X", "claimed": {"adr": 100}}
    later = {"address": "1 A St", "state": "PA", "price": 459000,
             "email_date": "2026-09-07", "source_name": "X", "claimed": {"adr": 100}}
    m = merge_duplicates([first, later])[0]
    assert m["price"] == 459000
    assert "price changed" in m["notes"]


def test_price_change_note_shows_both_prices():
    """`keep` is one of the two records being merged, so assigning the new
    price before formatting the note made it read '$X -> $X'."""
    from pipeline.parse_sources import merge_duplicates
    a = {"address": "9 B St", "state": "TX", "price": 1500000,
         "email_date": "2026-08-25", "source_name": "V", "claimed": {"monthly_rent": 19675}}
    b = {"address": "9 B St", "state": "TX", "price": 1450000,
         "email_date": "2026-09-03", "source_name": "V", "claimed": {"monthly_rent": 19675}}
    m = merge_duplicates([a, b])[0]
    assert m["price"] == 1450000
    assert "$1,500,000" in m["notes"] and "$1,450,000" in m["notes"]


def test_turnkey_ignores_the_newsletters_own_advertising():
    """The Offer Sheet's standing footer mentions 'turnkey STR' in a pitch to
    sellers. Matching it gave three properties a furnishing allowance they
    never claimed — including a $1M estate."""
    from pipeline.parse_sources import _turnkey_claim
    footer = ("# 200K Revenue on a 1M Hudson Valley Estate\n\n"
              "A nearly 7,000 sq ft historic estate with 6 bedrooms.\n\n"
              "Have a strong-performing Airbnb, unique vacation rental, or turnkey STR "
              "you may consider selling? Send it our way.\n")
    assert _turnkey_claim(footer) is False

    real = ("### Turnkey Operation\n\n"
            "Furnishings are included, with the existing cleaner available to continue.\n\n"
            "Have a strong-performing Airbnb, unique vacation rental, or turnkey STR "
            "you may consider selling? Send it our way.\n")
    assert _turnkey_claim(real) is True
