"""Load .eml files (raw RFC-822 email exports) into the same email-dict shape
that ingest_gmail.fetch_recent_emails produces, so saved emails — like Victor's
example deals — flow through the identical extraction path as live Gmail.
"""
import email
import email.policy
from pathlib import Path

from .ingest_gmail import SENDER_META, gmail_link, html_to_text


def _message_text(msg) -> str:
    """Prefer text/plain, fall back to stripped text/html."""
    plain, html = [], []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            content = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True)
            content = payload.decode("utf-8", errors="replace") if payload else ""
        (plain if ctype == "text/plain" else html).append(content)
    if plain:
        return "\n".join(plain)
    return html_to_text("\n".join(html))


def load_eml(path: Path) -> dict:
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=email.policy.default)
    sender_raw = str(msg.get("From", ""))
    sender = next((s for s in SENDER_META if s in sender_raw), sender_raw)
    meta = SENDER_META.get(sender, {"name": sender or path.name, "kind": "unknown"})
    return {
        "sender": sender,
        "sender_name": meta["name"],
        "sender_kind": meta["kind"],
        "subject": str(msg.get("Subject", "(no subject)")),
        "date": str(msg.get("Date", "")),
        "link": gmail_link(msg.get("Message-ID"), None),
        "text": _message_text(msg),
    }


def load_eml_inputs(path_str: str) -> list[dict]:
    """Accept a single .eml file or a directory of them."""
    path = Path(path_str).expanduser()
    if path.is_dir():
        files = sorted(path.glob("*.eml"))
        if not files:
            raise FileNotFoundError(f"no .eml files in {path}")
        return [load_eml(p) for p in files]
    return [load_eml(path)]
