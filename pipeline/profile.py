"""Load the investor profile: real private file if present, sanitized example otherwise."""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_PROFILE = REPO_ROOT / "private" / "profile.json"
EXAMPLE_PROFILE = REPO_ROOT / "config" / "profile.example.json"


def load_profile() -> dict:
    path = PRIVATE_PROFILE if PRIVATE_PROFILE.exists() else EXAMPLE_PROFILE
    with open(path) as f:
        profile = json.load(f)
    profile["_source"] = "private" if path == PRIVATE_PROFILE else "example"
    return profile
