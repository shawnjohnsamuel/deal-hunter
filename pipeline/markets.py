"""Market classification for the STR destination-market requirement.

Destination status is a tax-compliance gate, not just a yield question. Known
markets are classified deterministically; everything else is UNKNOWN and gets
flagged as a human judgment call — the pipeline never decides edge cases.
"""

DESTINATION_MARKETS = {
    # Oklahoma / Texas drive-to
    "broken bow", "hochatown", "fredericksburg", "galveston", "port aransas",
    "new braunfels", "canyon lake", "wimberley", "granbury", "possum kingdom lake",
    "south padre island", "rockport", "concan", "ruidoso", "hot springs",
    # Smokies / Southeast
    "gatlinburg", "pigeon forge", "sevierville", "wears valley", "townsend",
    "blue ridge", "ellijay", "helen", "bryson city", "maggie valley", "asheville",
    "boone", "banner elk", "gulf shores", "orange beach", "destin", "panama city beach",
    "30a", "santa rosa beach", "navarre",
    # Branson / Ozarks
    "branson", "hollister", "eureka springs",
    # Mountain west
    "pagosa springs", "red river", "angel fire", "cloudcroft",
}

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


def is_dfw(city: str) -> bool:
    return (city or "").strip().lower() in DFW_METRO
