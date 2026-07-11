"""One-time Gmail OAuth setup. Run locally, never in CI.

Prerequisites (≈8 minutes, once, signed into the DEDICATED deal-flow account):
  1. https://console.cloud.google.com → create project "deal-hunter"
  2. APIs & Services → Library → enable "Gmail API"
  3. APIs & Services → OAuth consent screen → External → add the dedicated
     address as a test user
  4. APIs & Services → Credentials → Create Credentials → OAuth client ID →
     Application type: "Desktop app" → download the JSON as client_secret.json
     into this scripts/ directory
  5. pip install google-auth-oauthlib
  6. python3 scripts/gmail_oauth_setup.py [--push-gh-secrets]

Secrets are NEVER printed. They are written to scripts/.gmail_secrets.env
(gitignored); --push-gh-secrets uploads them to the GitHub repo via `gh` and
is safe to run in a shared terminal.

Scope is gmail.readonly ONLY — the token can read mail, never send or delete.
"""
import json
import subprocess
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
HERE = Path(__file__).parent
SECRETS_IN = HERE / "client_secret.json"
SECRETS_OUT = HERE / ".gmail_secrets.env"


def main():
    if not SECRETS_IN.exists():
        sys.exit(f"Missing {SECRETS_IN} — follow the steps in this file's docstring first.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_IN), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    client = json.load(open(SECRETS_IN))["installed"]
    values = {
        "GMAIL_CLIENT_ID": client["client_id"],
        "GMAIL_CLIENT_SECRET": client["client_secret"],
        "GMAIL_REFRESH_TOKEN": creds.refresh_token,
    }
    SECRETS_OUT.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    SECRETS_OUT.chmod(0o600)
    print(f"\nWrote {SECRETS_OUT} (gitignored; values not displayed).")

    if "--push-gh-secrets" in sys.argv:
        for key, value in values.items():
            subprocess.run(["gh", "secret", "set", key, "--body", value],
                           check=True, capture_output=True)
            print(f"gh secret set {key}: done")
        print("All three Gmail secrets pushed to the repo.")
    else:
        print("Push to GitHub with:  python3 scripts/gmail_oauth_setup.py --push-gh-secrets"
              "\n(or rerun; an existing .gmail_secrets.env is reused without re-consent)")


if __name__ == "__main__":
    if SECRETS_OUT.exists() and "--push-gh-secrets" in sys.argv and "--fresh" not in sys.argv:
        import subprocess
        values = dict(line.split("=", 1) for line in
                      SECRETS_OUT.read_text().strip().splitlines())
        for key, value in values.items():
            subprocess.run(["gh", "secret", "set", key, "--body", value],
                           check=True, capture_output=True)
            print(f"gh secret set {key}: done (from existing .gmail_secrets.env)")
    else:
        main()
