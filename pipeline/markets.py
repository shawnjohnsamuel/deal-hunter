"""Market classification for the STR destination-market requirement.

Destination status is a tax-compliance gate, not just a yield question. Known
markets are classified deterministically; everything else is UNKNOWN and gets
flagged as a human judgment call — the pipeline never decides edge cases.

Two layers:
  * The flavor sets below (MOUNTAIN/BEACH/LAKE_RIVER) are matched on city name
    ALONE — cheap and good enough for markets with distinctive names.
  * PRIORITY_REGIONS — Shawn's buy box (adapted from Avery Carl's): established
    mountain destinations, fed by major metros, STR friendly, within a drive-
    time cap of home base (NYC metro). Matched on (city, STATE); each region
    carries an approximate drive time so the cap is data, not a hardcoded list.
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
# Priority STR markets — Shawn's adaptation of Avery Carl's (The Short Term
# Shop) buy box, re-centered on his home base (NYC metro). Criteria:
#   1. established mountain vacation destination
#   2. drivable from major metros (feeder metros noted per region)
#   3. STR friendly (towns with hostile STR ordinances are excluded — e.g.
#      Woodstock and Saugerties NY; Asheville proper)
# plus a hard preference for the first buy: within ~14 hours' drive of home
# (max_drive_hours in the profile's str buy box). Regions beyond the cap stay
# listed for reference — they classify as destinations but earn no bonus.
#
# State-qualified {(city, state): region-record} because the list makes name
# collisions routine: Franklin TN vs NC, Wilmington VT vs NY, Woodstock
# NH/VT/NY, Stratton ME/VT, Jackson NH, Oakland MD, Madison NH/VA/WI...
#
# NOTE: Broken Bow, OK is STS-covered but DELIBERATELY excluded — Shawn does
# not want it prioritized (and at ~22h it's far beyond the drive cap anyway).
# It stays a plain MOUNTAIN market (normal +5).
# ---------------------------------------------------------------------------

def _region(name: str, flavor: str, state: str, drive_hours: float,
            metros: str, *cities: str) -> list[dict]:
    return [{"region": name, "flavor": flavor, "state": state,
             "drive_hours": drive_hours, "metros": metros, "city": c}
            for c in cities]


PRIORITY_REGIONS: list[dict] = [
    # --- Northeast: the close-in band (drive_hours ≈ from home base) ---
    *_region("Poconos", "mountain", "PA", 2.5, "NYC/Philly",
             "pocono summit", "pocono lake", "pocono pines", "mount pocono",
             "tobyhanna", "tannersville", "scotrun", "swiftwater", "henryville",
             "canadensis", "cresco", "mountainhome", "long pond", "blakeslee",
             "albrightsville", "lake harmony", "white haven", "jim thorpe",
             "east stroudsburg", "stroudsburg", "bushkill", "dingmans ferry",
             "milford", "hawley", "lakeville", "tafton", "paupack", "greentown",
             "newfoundland", "gouldsboro", "thornhurst", "lackawaxen", "freeland"),
    *_region("Catskills", "mountain", "NY", 3, "NYC",
             # Woodstock + Saugerties excluded: restrictive STR laws.
             "windham", "hunter", "tannersville", "jewett", "lexington",
             "prattsville", "east durham", "round top", "cairo", "palenville",
             "catskill", "phoenicia", "shandaken", "big indian", "pine hill",
             "fleischmanns", "margaretville", "roxbury", "andes",
             "livingston manor", "roscoe", "callicoon", "narrowsburg",
             "jeffersonville", "bethel", "white lake", "kerhonkson", "accord",
             "greenville", "grahamsville"),
    *_region("Adirondacks", "mountain", "NY", 5, "NYC/Boston/Montreal",
             # Lake Placid / North Elba caps unhosted STR permits — check per deal.
             "lake george", "bolton landing", "warrensburg", "chestertown",
             "schroon lake", "north creek", "indian lake", "long lake", "inlet",
             "old forge", "speculator", "lake placid", "saranac lake",
             "tupper lake", "wilmington", "keene", "keene valley"),
    *_region("Berkshires", "mountain", "MA", 3, "NYC/Boston",
             "great barrington", "lenox", "stockbridge", "lee", "becket",
             "otis", "adams", "north adams", "williamstown", "hancock"),
    *_region("Southern Vermont", "mountain", "VT", 4.5, "NYC/Boston",
             # Mount Snow / Stratton / Bromley / Okemo / Killington
             "west dover", "dover", "wilmington", "jamaica", "stratton",
             "winhall", "bondville", "londonderry", "peru", "manchester",
             "ludlow", "proctorsville", "cavendish", "mount holly", "plymouth",
             "bridgewater", "woodstock", "killington", "mendon", "chittenden",
             "pittsfield"),
    *_region("Northern Vermont", "mountain", "VT", 6.5, "NYC/Boston/Montreal",
             # Stowe / Smugglers' Notch / Mad River Valley / Burke / Jay Peak
             "stowe", "morrisville", "waterbury", "jeffersonville", "cambridge",
             "waitsfield", "warren", "fayston", "east burke", "burke",
             "lyndonville", "jay", "montgomery"),
    *_region("White Mountains", "mountain", "NH", 6.5, "Boston/NYC",
             "north conway", "conway", "bartlett", "glen", "jackson",
             "intervale", "bretton woods", "carroll", "twin mountain",
             "jefferson", "whitefield", "littleton", "bethlehem", "franconia",
             "sugar hill", "lincoln", "north woodstock", "woodstock",
             "thornton", "campton", "waterville valley", "gorham"),
    *_region("Maine Mountains", "mountain", "ME", 7.5, "Boston/Portland",
             # Sunday River / Sugarloaf / Rangeley
             "bethel", "newry", "carrabassett valley", "kingfield", "stratton",
             "eustis", "rangeley"),
    *_region("Deep Creek Lake", "mountain", "MD", 6, "DC/Baltimore/Pittsburgh",
             "mchenry", "oakland", "swanton", "friendsville", "accident"),
    *_region("Laurel Highlands", "mountain", "PA", 6, "Pittsburgh/DC",
             "seven springs", "champion", "hidden valley", "farmington",
             "ohiopyle"),
    *_region("Berkeley Springs / Lost River", "mountain", "WV", 5.5, "DC/Baltimore",
             "berkeley springs", "great cacapon", "lost river", "wardensville",
             "mathias"),
    *_region("Canaan Valley / Snowshoe", "mountain", "WV", 8, "DC/Baltimore",
             "davis", "thomas", "canaan valley", "cabins", "snowshoe",
             "slatyfork"),
    *_region("Shenandoah", "mountain", "VA", 6, "DC/Richmond",
             "basye", "front royal", "luray", "madison", "mount jackson",
             "mcgaheysville", "massanutten", "elkton", "shenandoah",
             "stanardsville", "stanley"),
    *_region("Wintergreen", "mountain", "VA", 7, "DC/Richmond",
             "wintergreen", "nellysford", "afton", "roseland"),
    # --- Avery Carl / STS southern mountain coverage, still in drive range ---
    *_region("High Country", "mountain", "NC", 11, "Charlotte/Atlanta/DC",
             "banner elk", "beech mountain", "blowing rock", "boone",
             "deep gap", "linville", "newland", "seven devils", "sugar grove",
             "sugar mountain", "todd", "west jefferson"),
    *_region("NC Smokies", "mountain", "NC", 11.5, "Charlotte/Atlanta",
             # Asheville proper excluded — city bans most new unhosted STRs.
             "black mountain", "brevard", "bryson city", "candler", "canton",
             "cashiers", "clyde", "franklin", "hendersonville", "maggie valley",
             "waynesville", "weaverville", "whittier", "woodfin"),
    *_region("Smoky Mountains", "mountain", "TN", 12, "Atlanta/Nashville/Charlotte",
             "gatlinburg", "sevierville", "pigeon forge", "wears valley",
             "townsend", "pittman center", "cosby"),
    *_region("Blue Ridge", "mountain", "GA", 13.5, "Atlanta",
             "blue ridge", "mccaysville", "morganton", "ellijay",
             "mineral bluff", "east ellijay", "cherry log"),
    # --- STS coverage beyond the drive cap: reference only, no bonus ---
    *_region("Branson", "mountain", "MO", 18.5, "Kansas City/St. Louis/Dallas",
             "branson", "branson west", "hollister", "kimberling city",
             "lampe", "ridgedale", "shell knob"),
    *_region("Texas Hill Country", "lake_river", "TX", 26, "Austin/San Antonio",
             "canyon lake", "fredericksburg", "wimberley"),
]

PRIORITY_MARKETS: dict[tuple[str, str], dict] = {
    (r["city"], r["state"]): r for r in PRIORITY_REGIONS
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


def priority_market_info(city: str, state: str = None) -> dict | None:
    """Region record (region, flavor, drive_hours, metros) for (city, state)
    in the priority universe, else None. Requires state — the priority set is
    intentionally state-qualified."""
    if not state:
        return None
    return PRIORITY_MARKETS.get((_norm(city), state.strip().upper()))


def is_priority_market(city: str, state: str = None) -> bool:
    return priority_market_info(city, state) is not None


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
    info = priority_market_info(city, state)
    if info:
        return info["flavor"]
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
