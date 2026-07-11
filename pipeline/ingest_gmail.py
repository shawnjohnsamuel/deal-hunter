"""Gmail ingestion — read-only, sender-filtered, last 48h.

Auth: OAuth refresh token with the gmail.readonly scope only (the pipeline can
never send or delete). Secrets via env: GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET,
GMAIL_REFRESH_TOKEN. One-time setup: scripts/gmail_oauth_setup.py.
"""
import base64
import os
import re
from html.parser import HTMLParser

# Sender roster. `kind` drives extraction behavior:
#   agent_full_address — licensed agents; listings arrive with real addresses
#   teaser_paywall     — free teaser newsletters; the best deal's address is held
#                        behind the paywall, but every other detail is teased, so
#                        address-less candidates are extracted and sent to the
#                        identification step (pipeline/identify.py)
SENDER_META = {
    "victor@steffenrealtycorp.com": {
        "name": "Victor Steffen (Steffen Realty)", "kind": "agent_full_address"},
    "info@theshorttermshop.com": {
        "name": "Avery Carl (The Short Term Shop)", "kind": "agent_full_address"},
    "theoffersheet@mail.beehiiv.com": {
        "name": "The Offer Sheet", "kind": "teaser_paywall"},
    "here@mail.beehiiv.com": {
        "name": "Here (beehiiv)", "kind": "teaser_paywall"},
    "team@bnbflow.co": {
        "name": "BNB Flow", "kind": "teaser_paywall"},
}

DEAL_SENDERS = list(SENDER_META)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class _TextExtractor(HTMLParser):
    SKIP = {"style", "script", "head"}

    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith("http"):
                self.chunks.append(f" {href} ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.chunks.append(data)


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    text = "".join(p.chunks)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


def _body_text(payload: dict) -> str:
    """Prefer text/plain, fall back to stripped text/html, walk multiparts."""
    plain, html = [], []

    def walk(part):
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data:
            decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            (plain if mime == "text/plain" else html if mime == "text/html" else []).append(decoded)
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    if plain:
        return "\n".join(plain)
    return html_to_text("\n".join(html))


def gmail_link(rfc822_msgid: str | None, api_msg_id: str | None) -> str | None:
    """Deep link back to the source email in the Gmail web UI.

    rfc822msgid search is account-independent and survives label moves; the
    API message id (#all/<id>) is the fallback. GMAIL_ACCOUNT_INDEX selects
    which signed-in Gmail profile (/u/N) the link opens — numeric only, since
    these links are published in the public deals.json.
    """
    account = os.environ.get("GMAIL_ACCOUNT_INDEX", "0")
    if not account.isdigit():
        account = "0"
    base = f"https://mail.google.com/mail/u/{account}"
    if rfc822_msgid:
        return f"{base}/#search/rfc822msgid:" + rfc822_msgid.strip().strip("<>")
    if api_msg_id:
        return f"{base}/#all/{api_msg_id}"
    return None


def fetch_recent_emails(newer_than: str = "2d") -> list[dict]:
    """Fetch recent messages from the deal senders. Returns
    [{sender, sender_name, sender_kind, subject, date, link, text}, ...]."""
    svc = _service()
    query = f"from:({' OR '.join(DEAL_SENDERS)}) newer_than:{newer_than}"
    resp = svc.users().messages().list(userId="me", q=query, maxResults=50).execute()
    emails = []
    for ref in resp.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        sender_raw = headers.get("from", "")
        sender = next((s for s in DEAL_SENDERS if s in sender_raw), sender_raw)
        meta = SENDER_META.get(sender, {"name": sender, "kind": "unknown"})
        emails.append({
            "sender": sender,
            "sender_name": meta["name"],
            "sender_kind": meta["kind"],
            "subject": headers.get("subject", "(no subject)"),
            "date": headers.get("date", ""),
            "link": gmail_link(headers.get("message-id"), ref.get("id")),
            "text": _body_text(msg["payload"]),
        })
    return emails
