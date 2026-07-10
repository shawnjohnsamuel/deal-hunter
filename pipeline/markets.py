"""Market classification for the STR destination-market requirement.

Destination status is a tax-compliance gate, not just a yield question. Known
markets are classified deterministically; everything else is UNKNOWN and gets
flagged as a human judgment call — the pipeline never decides edge cases.
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
    "boone", "banner elk",
    # Mountain west
    "pagosa springs", "red river", "angel fire", "cloudcroft", "ruidoso",
}

BEACH_MARKETS = {
    "galveston", "port aransas", "south padre island", "rockport",
    "gulf shores", "orange beach", "destin", "panama city beach",
    "30a", "santa rosa beach", "navarre",
}

LAKE_RIVER_MARKETS = {
    "fredericksburg", "new braunfels", "canyon lake", "wimberley", "granbury",
    "possum kingdom lake", "concan",
}

DESTINATION_MARKETS = MOUNTAIN_MARKETS | BEACH_MARKETS | LAKE_RIVER_MARKETS

# Bedroom communities and lake-adjacent suburbs that do NOT count as destination
# markets for the STR tax strategy, regardless of a lake being nearby.
NON_DESTINATION_MARKETS = {
    "little elm", "frisco", "plano", "mckinney", "allen", "prosper", "celina",
    "the colony", "lewisville", "denton", "anna", "melissa", "princeton",
    "royse city", "forney", "rockwall", "wylie", "sherman", "garland",
    "arlington", "grand prairie", "irving", "mesquite", "carrollton",
    "fort worth", "dallas",
}

DFW_METRO = {
    "dallas", "fort worth", "plano", "frisco", "mckinney", "allen", "richardson",
    "garland", "irving", "arlington", "grand prairie", "carrollton", "lewisville",
    "denton", "mesquite", "rockwall", "wylie", "the colony", "little elm",
    "prosper", "celina", "anna", "melissa", "princeton", "forney", "royse city",
    "duncanville", "desoto", "cedar hill", "lancaster", "grapevine", "euless",
    "bedford", "hurst", "keller", "southlake", "coppell", "flower mound",
}


def classify_market(city: str) -> str:
    """Return 'destination', 'non_destination', or 'unknown'."""
    c = (city or "").strip().lower()
    if c in DESTINATION_MARKETS:
        return "destination"
    if c in NON_DESTINATION_MARKETS:
        return "non_destination"
    return "unknown"


def market_flavor(city: str) -> str | None:
    """'mountain' | 'beach' | 'lake_river' for known destination markets."""
    c = (city or "").strip().lower()
    if c in MOUNTAIN_MARKETS:
        return "mountain"
    if c in BEACH_MARKETS:
        return "beach"
    if c in LAKE_RIVER_MARKETS:
        return "lake_river"
    return None


def is_dfw(city: str) -> bool:
    return (city or "").strip().lower() in DFW_METRO
