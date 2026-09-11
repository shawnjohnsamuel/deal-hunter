"""Pull newsletter issues from their public web archives instead of the inbox.

Every recurring source except Victor is a beehiiv publication with a public
archive and a complete sitemap. Reading the issue from the web costs nothing
but bandwidth, while reading it out of Gmail costs a model round trip per
email — the dominant expense of a hunt. The sitemap also catches issues an
inbox scan can miss (deliverability gaps, a missed page of results).

    python -m pipeline.ingest_web --since 2026-08-23 -o /tmp/msgs
    python -m pipeline.ingest_web --since 2026-09-01 --source here -o /tmp/msgs

Output is one file per issue in exactly the shape pipeline.parse_sources
expects, so the parsers are shared with the Gmail path and stay tested.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import html as htmlmod
import os
import re
import urllib.request

# slug: (archive base, the From: address the Gmail path sees)
PUBLICATIONS = {
    "the_offer_sheet": ("https://www.theoffersheet.com", "theoffersheet@mail.beehiiv.com"),
    "here":            ("https://www.here.co",           "here@mail.beehiiv.com"),
    "bnb_flow":        ("https://www.bnbflow.co",         "team@bnbflow.co"),
}

UA = {"User-Agent": "Mozilla/5.0 (deal-hunter archive reader)"}


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as f:
        body = f.read()
        if f.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return body.decode("utf8", "replace")


def list_posts(base: str, since: str, until: str | None = None) -> list[tuple[str, str]]:
    """[(YYYY-MM-DD, url)] for every issue in the window, oldest first."""
    sm = _get(base + "/sitemap.xml")
    pat = r"<loc>(" + re.escape(base) + r"/p/[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>"
    out = []
    for url, mod in re.findall(pat, sm):
        day = mod[:10]
        if day >= since and (until is None or day <= until):
            out.append((day, url))
    return sorted(set(out))


# --- HTML -> the markdown-ish text the email plain-text part uses ------------
_BLOCK_END = re.compile(r"</(p|div|h[1-6]|li|ul|ol|tr|table|blockquote)>", re.I)
_DROP = re.compile(r"<(script|style|svg|noscript)\b.*?</\1>", re.I | re.S)


def to_text(html: str) -> str:
    """Render a beehiiv content block as text parse_sources can read.

    Only the structure the parsers key on is preserved — heading level, link
    target, list items and bold — because that is what carries the address,
    the price and the performance rows.
    """
    h = _DROP.sub(" ", html)
    h = re.sub(r"<h1[^>]*>", "\n# ", h, flags=re.I)
    h = re.sub(r"<h2[^>]*>", "\n## ", h, flags=re.I)
    h = re.sub(r"<h3[^>]*>", "\n### ", h, flags=re.I)
    h = re.sub(r"<h[456][^>]*>", "\n### ", h, flags=re.I)
    h = re.sub(r"<li[^>]*>", "\n* ", h, flags=re.I)
    h = re.sub(r"</?(b|strong)\s*[^>]*>", "**", h, flags=re.I)
    h = re.sub(r"<br\s*/?>", "\n", h, flags=re.I)
    # links: keep the text, keep the href — the address and the contact slug
    # both arrive this way
    h = re.sub(r'<a\b[^>]*?href="([^"]+)"[^>]*>(.*?)</a>',
               lambda m: "[" + re.sub(r"<[^>]+>", "", m.group(2)).strip() + "](" + m.group(1) + ")",
               h, flags=re.I | re.S)
    h = _BLOCK_END.sub("\n", h)
    h = re.sub(r"<[^>]+>", "", h)
    h = htmlmod.unescape(h)
    h = h.replace(" ", " ").replace("​", "")
    h = re.sub(r"\*\*\s*\*\*", "", h)          # emptied bold wrappers
    h = re.sub(r"[ \t]+", " ", h)
    h = re.sub(r" *\n *", "\n", h)
    h = re.sub(r"\n{3,}", "\n\n", h)
    return h.strip()


def fetch_post(url: str) -> dict:
    """{'title','date','text','url'} for one issue."""
    page = _get(url)
    i = page.find('id="content-blocks"')
    body = page[page.find(">", i) + 1:] if i >= 0 else page
    # stop at the subscribe/footer furniture that follows the content blocks
    for marker in ('id="post-footer"', "Upgrade to", "wt-footer", "</main>"):
        j = body.find(marker, 200)
        if j > 0:
            body = body[:j]
            break
    title = ""
    m = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    if m:
        title = htmlmod.unescape(m.group(1))
    date = ""
    m = re.search(r'"datePublished":"(\d{4}-\d{2}-\d{2})', page) or \
        re.search(r'property="article:published_time" content="(\d{4}-\d{2}-\d{2})', page)
    if m:
        date = m.group(1)
    return {"title": title, "date": date, "text": to_text(body), "url": url}


def write_msg(outdir: str, source: str, sender: str, post: dict, day: str) -> str:
    """Write one issue in the SUBJECT/SENDER/DATE/MSGID envelope."""
    slug = post["url"].rsplit("/p/", 1)[-1]
    name = f"{day}_{source}_{slug[:60]}.txt"
    path = os.path.join(outdir, name)
    header = (f"SUBJECT: {post['title']}\n"
              f"SENDER: {sender}\n"
              f"DATE: {post['date'] or day}T00:00:00Z\n"
              f"MSGID: web:{slug}\n" + "=" * 60 + "\n")
    with open(path, "w") as f:
        f.write(header + post["text"] + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--until", help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--source", action="append", choices=sorted(PUBLICATIONS),
                    help="default: all publications")
    ap.add_argument("-o", "--outdir", required=True)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    sources = args.source or sorted(PUBLICATIONS)
    total = 0
    for src in sources:
        base, sender = PUBLICATIONS[src]
        posts = list_posts(base, args.since, args.until)
        print(f"{src}: {len(posts)} issue(s) in window")
        for day, url in posts:
            try:
                post = fetch_post(url)
                write_msg(args.outdir, src, sender, post, day)
                total += 1
            except Exception as e:
                print(f"  WARNING {url}: {e}")
    print(f"wrote {total} issue(s) to {args.outdir}")


if __name__ == "__main__":
    main()
