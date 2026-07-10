"""Address normalization + stable dedupe key."""
import hashlib
import re

_ABBREV = {
    "street": "st", "avenue": "ave", "boulevard": "blvd", "drive": "dr",
    "lane": "ln", "road": "rd", "court": "ct", "circle": "cir", "place": "pl",
    "trail": "trl", "parkway": "pkwy", "highway": "hwy", "terrace": "ter",
    "north": "n", "south": "s", "east": "e", "west": "w",
    "apartment": "apt", "suite": "ste", "unit": "unit",
}


def normalize_address(address: str, city: str = "", state: str = "") -> str:
    text = f"{address} {city} {state}".lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = [(_ABBREV.get(w, w)) for w in text.split()]
    return " ".join(words)


def deal_key(address: str, city: str = "", state: str = "") -> str:
    return hashlib.sha256(normalize_address(address, city, state).encode()).hexdigest()[:16]
