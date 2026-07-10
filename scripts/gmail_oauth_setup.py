"""One-time Gmail OAuth setup. Run locally, never in CI.

Prerequisites (≈10 minutes, once):
  1. https://console.cloud.google.com → create project "deal-hunter"
  2. APIs & Services → Library → enable "Gmail API"
  3. APIs & Services → OAuth consent screen → External → add yourself as a test user
  4. APIs & Services → Credentials → Create Credentials → OAuth client ID →
     Application type: "Desktop app" → download the JSON as client_secret.json
     into this scripts/ directory
  5. pip install google-auth-oauthlib
  6. python3 scripts/gmail_oauth_setup.py

Then store the three printed values as GitHub repo secrets:
  gh secret set GMAIL_CLIENT_ID
  gh secret set GMAIL_CLIENT_SECRET
  gh secret set GMAIL_REFRESH_TOKEN

Scope is gmail.readonly ONLY — the token can read mail, never send or delete.
"""
import json
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SECRETS = Path(__file__).parent / "client_secret.json"


def main():
    if not SECRETS.exists():
        sys.exit(f"Missing {SECRETS} — follow the steps in this file's docstring first.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    client = json.load(open(SECRETS))["installed"]
    print("\nStore these as GitHub repo secrets:\n")
    print(f"GMAIL_CLIENT_ID={client['client_id']}")
    print(f"GMAIL_CLIENT_SECRET={client['client_secret']}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("\ne.g.  gh secret set GMAIL_REFRESH_TOKEN --body '<value>'")


if __name__ == "__main__":
    main()
