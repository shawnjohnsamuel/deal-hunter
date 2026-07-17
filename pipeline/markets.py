"""Market classification for the STR destination-market requirement.

Destination status is a tax-compliance gate, not just a yield question. Known
markets are classified deterministically; everything else is UNKNOWN and gets
flagged as a human judgment call — the pipeline never decides edge cases.

Two layers:
  * The flavor sets below (MOUNTAIN/BEACH/LAKE_RIVER) are matched on city name
    ALONE — cheap and good enough for markets with distinctive names.
  * PRIORITY_MARKETS (The Short Term Shop / Avery Carl coverage — Shawn's
    preferred STR universe) is matched on (city, STATE) so common names like
    Franklin TN, Madison WI, or Canton OH can't be mistaken for the mountain
    town of the same name and handed a priority bonus they don't deserve.
"""

# Destination markets by flavor. Mountain markets are the STR Tier 1 priority
# (framework-v2 §4) — classification feeds a scoring bonus, so a market's flavor
# matters, not just its destination status.
MOUNTAIN_MARKETS = {
    # Ouachitas / Ozarks
    "broken bow", "hochatown", "hot springs", "branson", "hollister", "eureka springs",
    # Smokies / Blue Ridge / Appalachians
    "gatlinburg", "pigeon forge", "sevierville", "wears valley", "townsend",
    "blue ridge", "ellijay", "helen", "bryson city", "maggie valley", "asheville",
    "boone", "banner elk", "blowing rock", "murphy", "cullowhee",
    # Poconos / Catskills (NYC drive-to)
    "greentown", "grahamsville", "freeland",
    # Mountain west / Cascades
    "pagosa springs", "red river", "angel fire", "cloudcroft", "ruidoso",
    "cle elum", "wolf creek", "candler", "tijeras", "kila", "great cacapon",
    "suches", "seven devils", "stanton", "rockbridge", "travelers rest",
    "speculator", "lyndonville", "pocono lake", "pocono summit", "lost river", "jasper",
}

BEACH_MARKETS = {
    "galveston", "port aransas", "south padre island", "rockport",
    "gulf shores", "orange beach", "destin", "panama city beach",
    "30a", "santa rosa beach", "navarre", "buxton", "port orford", "crystal beach", "fort bragg", "ocean springs",
    "orange beach",
}

LAKE_RIVER_MARKETS = {
    "fredericksburg", "new braunfels", "canyon lake", "wimberley", "granbury",
    "possum kingdom lake", "concan", "mammoth spring", "sulphur", "seneca falls",
}

DESTINATION_MARKETS = MOUNTAIN_MARKETS | BEACH_MARKETS | LAKE_RIVER_MARKETS

# ---------------------------------------------------------------------------
# The Short Term Shop target markets (Avery Carl) — Shawn's priority STR
# universe. State-qualified {(city, state): flavor} so same-named metros don't
# collide (Franklin TN, Madison WI, Canton OH...). These outrank generic
# mountain markets in scoring via the str priority_market_bonus.
#
# NOTE: Broken Bow, OK is STS-covered but DELIBERATELY excluded here — Shawn
# does not want it prioritized. It stays a plain MOUNTAIN market (normal +5),
# so Avery's other mountain destinations rank above it.
# ---------------------------------------------------------------------------
def _priority_region(flavor: str, state: str, *cities: str) -> dict:
    return {(c, state): flavor for c in cities}


PRIORITY_MARKETS: dict[tuple[str, str], str] = {
    # Blue Ridge, GA
    **_priority_region("mountain", "GA", "blue ridge", "mccaysville", "morganton",
                       "ellijay", "mineral bluff", "east ellijay", "cherry log"),
    # Branson, MO (Ozarks / Table Rock Lake — kept mountain, matching Branson)
    **_priority_region("mountain", "MO", "branson", "branson west", "hollister",
                       "kimberling city", "lampe", "ridgedale", "shell knob"),
    # High Country, NC
    **_priority_region("mountain", "NC", "banner elk", "beech mountain", "blowing rock",
                       "boone", "deep gap", "linville", "newland", "seven devils",
                       "sugar grove", "sugar mountain", "todd", "west jefferson"),
    # North Carolina Smoky Mountains
    **_priority_region("mountain", "NC", "black mountain", "brevard", "bryson city",
                       "candler", "canton", "cashiers", "clyde", "franklin",
                       "hendersonville", "maggie valley", "waynesville", "weaverville",
                       "whittier", "woodfin"),
    # Shenandoah, VA
    **_priority_region("mountain", "VA", "basye", "front royal", "luray", "madison",
                       "mount jackson", "mcgaheysville", "shenandoah", "stanardsville",
                       "stanley"),
    # Smoky Mountains, TN
    **_priority_region("mountain", "TN", "gatlinburg", "sevierville", "pigeon forge",
                       "wears valley", "townsend", "pittman center", "cosby"),
    # Texas Hill Country
    **_priority_region("lake_river", "TX", "canyon lake", "fredericksburg", "wimberley"),
}

DFW_METRO = {
    "dallas", "fort worth", "plano", "frisco", "mckinney", "allen", "richardson",
    "garland", "irving", "arlington", "grand prairie", "carrollton", "lewisville",
    "denton", "mesquite", "rockwall", "wylie", "the colony", "little elm",
    "prosper", "celina", "anna", "melissa", "princeton", "forney", "royse city",
    "duncanville", "desoto", "cedar hill", "lancaster", "grapevine", "euless",
    "bedford", "hurst", "keller", "southlake", "coppell", "flower mound",
    "richardson", "addison", "farmers branch", "sachse", "rowlett",
    "north richland hills", "haltom city", "burleson", "mansfield", "grapevine",
}

# Bedroom communities and lake-adjacent suburbs that do NOT count as destination
# markets for the STR tax strategy, regardless of a lake being nearby. Every
# DFW-metro city is non-destination by definition; the extras are non-DFW
# examples from the framework. Metro cores like Houston/Austin/San Antonio are
# deliberately NOT listed — they stay "unknown", a human judgment call.
NON_DESTINATION_MARKETS = DFW_METRO | {
    "sherman", "anna", "melissa", "princeton", "royse city", "forney",
}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def is_priority_market(city: str, state: str = None) -> bool:
    """True when (city, state) is in Shawn's Short Term Shop target universe.
    Requires state — the priority set is intentionally state-qualified."""
    if not state:
        return False
    return (_norm(city), state.strip().upper()) in PRIORITY_MARKETS


def classify_market(city: str, state: str = None) -> str:
    """Return 'destination', 'non_destination', or 'unknown'."""
    if is_priority_market(city, state):
        return "destination"
    c = _norm(city)
    if c in DESTINATION_MARKETS:
        return "destination"
    if c in NON_DESTINATION_MARKETS:
        return "non_destination"
    return "unknown"


def market_flavor(city: str, state: str = None) -> str | None:
    """'mountain' | 'beach' | 'lake_river' for known destination markets."""
    if state and (flavor := PRIORITY_MARKETS.get((_norm(city), state.strip().upper()))):
        return flavor
    c = _norm(city)
    if c in MOUNTAIN_MARKETS:
        return "mountain"
    if c in BEACH_MARKETS:
        return "beach"
    if c in LAKE_RIVER_MARKETS:
        return "lake_river"
    return None


def is_dfw(city: str) -> bool:
    return _norm(city) in DFW_METRO
