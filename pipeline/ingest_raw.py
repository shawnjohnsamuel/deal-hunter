"""Turn saved Gmail connector RAW results into parseable message files.

An interactive hunt reads the inbox through the Gmail connector, and the body
of a deal newsletter is ~100KB — far past the tool-result token cap. Asking
for `RAW` deliberately overflows that cap, so the harness writes the result to
a file and hands back only a path. This module decodes those files, so an
email costs one short tool result instead of its whole body.

    python -m pipeline.ingest_raw <tool-results-dir-or-files...> -o /tmp/msgs

Output matches pipeline.ingest_web: the SUBJECT/SENDER/DATE/MSGID envelope
that pipeline.parse_sources dispatches on.
"""
from __future__ import annotations

import argparse
import base64
import email
import email.policy
import glob
import json
import os
import re

from .ingest_web import to_text


def decode_raw(path: str) -> dict:
    """{'subject','sender','date','msgid','text'} from one saved RAW result."""
    with open(path) as f:
        blob = json.load(f)
    raw = blob["raw"]
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)),
                                   policy=email.policy.default)

    plain, html = None, None
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        try:
            body = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            body = payload.decode(part.get_content_charset() or "utf8", "replace")
        if part.get_content_subtype() == "plain" and not plain:
            plain = body
        elif part.get_content_subtype() == "html" and not html:
            html = body

    # Prefer the sender's own plain-text part; fall back to rendering the HTML
    # into the same markdown-ish shape the parsers read.
    text = plain if plain and plain.strip() else to_text(html or "")
    sender = msg.get("From", "")
    m = re.search(r"<([^>]+)>", sender)
    if m:
        sender = m.group(1)
    return {
        "subject": (msg.get("Subject") or "").replace("\n", " ").strip(),
        "sender": sender.strip(),
        "date": blob.get("internalDate"),
        "msgid": blob.get("id", os.path.basename(path)),
        "text": text,
    }


def _iso(internal_ms) -> str:
    import datetime as dt
    try:
        return dt.datetime.fromtimestamp(int(internal_ms) / 1000,
                                         dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def write_msg(outdir: str, m: dict) -> str:
    day = _iso(m["date"])[:10] or "unknown"
    safe = re.sub(r"[^a-z0-9]+", "-", m["sender"].split("@")[0].lower())[:20]
    path = os.path.join(outdir, f"{day}_{safe}_{m['msgid'][-8:]}.txt")
    header = (f"SUBJECT: {m['subject']}\n"
              f"SENDER: {m['sender']}\n"
              f"DATE: {_iso(m['date'])}\n"
              f"MSGID: {m['msgid']}\n" + "=" * 60 + "\n")
    with open(path, "w") as f:
        f.write(header + m["text"] + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="saved RAW result files, or a directory of them")
    ap.add_argument("-o", "--outdir", required=True)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    files: list[str] = []
    for p in args.paths:
        files.extend(sorted(glob.glob(os.path.join(p, "*get_message*")))
                     if os.path.isdir(p) else [p])
    written = 0
    for f in files:
        try:
            m = decode_raw(f)
        except KeyError:
            continue  # an older saved result in a non-RAW format — not ours
        except Exception as e:
            print(f"WARNING {os.path.basename(f)}: {e}")
            continue
        written += 1
        out = write_msg(args.outdir, m)
        print(f"{os.path.basename(out)}  [{m['sender']}]  {m['subject'][:58]}")
    print(f"wrote {written} message(s) to {args.outdir}")


if __name__ == "__main__":
    main()
