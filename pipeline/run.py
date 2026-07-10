"""Pipeline orchestrator.

Daily (GitHub Action):   python -m pipeline.run --daily
Manual (/add-deal):      python -m pipeline.run --manual "123 Main St, Broken Bow OK ..."
Structured (seed/tests): python -m pipeline.run --json path/to/deals.json [--no-enrich]

Degrades gracefully: missing Gmail secrets → skip ingest; missing API keys →
skip LLM extraction/enrichment (structured input still works end to end).
"""
import argparse
import json
import os
import sys

from . import db as dbmod
from .deal_card import render_deal_card, summary_line
from .dedupe import deal_key_for
from .kill_filter import run_kill_filter
from .profile import load_profile
from .score import classify_tier, score_deal


def process_deal(deal: dict, profile: dict, conn, *, enrich_enabled: bool = True,
                 rescore: bool = False) -> dict:
    """Run one deal through dedupe → kill filter → identify (teasers) →
    enrich → score → store."""
    key = deal_key_for(deal)
    if dbmod.seen(conn, key) and not rescore:
        return {"key": key, "outcome": "duplicate", "deal": deal}

    deal["tier"] = classify_tier(deal, profile)
    killed, reasons, flags = run_kill_filter(deal, profile)
    if killed:
        dbmod.upsert(conn, key, deal, status="killed", verdict="KILLED", kill_reasons=reasons)
        return {"key": key, "outcome": "killed", "deal": deal, "kill_reasons": reasons}

    # Paywalled teaser without an address: try to identify the listing by its
    # teased attributes, then re-dedupe — the identified address may already be
    # in the db from an agent email or a previous day.
    if deal.get("teaser") and not deal.get("address") and enrich_enabled:
        try:
            from .identify import identify_property
            if identify_property(deal):
                addr_key = deal_key_for(deal)
                if dbmod.seen(conn, addr_key) and not rescore:
                    return {"key": addr_key, "outcome": "duplicate", "deal": deal}
                key = addr_key
        except Exception as e:
            flags.append(f"identification error: {e}")

    if enrich_enabled:
        try:
            from .enrich import enrich_deal
            enrich_deal(deal, profile)
        except Exception as e:  # enrichment failure flags the deal, never sinks the run
            flags.append(f"enrichment error: {e}")

    result = score_deal(deal, profile, kill_flags=flags)
    card = render_deal_card(deal, result)
    dbmod.upsert(conn, key, deal, status="scored", verdict=result["verdict"],
                 score=result["score"], result=result, deal_card_md=card)
    return {"key": key, "outcome": "scored", "deal": deal, "result": result, "card": card}


def run_batch(deals: list[dict], *, enrich_enabled: bool = True, rescore: bool = False) -> list[dict]:
    profile = load_profile()
    if profile["_source"] == "example":
        print("NOTE: using sanitized example profile (private/profile.json not found)",
              file=sys.stderr)
    conn = dbmod.connect()
    outcomes = [process_deal(d, profile, conn, enrich_enabled=enrich_enabled, rescore=rescore)
                for d in deals]
    stats = dbmod.export_site_json(conn)
    print(f"db: {stats['total']} deals total ({stats['pass']} PASS / "
          f"{stats['borderline']} BORDERLINE / {stats['fail']} FAIL / {stats['killed']} killed)",
          file=sys.stderr)
    return outcomes


def print_outcomes(outcomes: list[dict], full_cards: bool = False):
    for o in outcomes:
        if o["outcome"] == "duplicate":
            print(f"DUPLICATE — already in database: {o['deal'].get('address')}")
        elif o["outcome"] == "killed":
            print(f"**KILLED** — {o['deal'].get('address')}, {o['deal'].get('city')}: "
                  + "; ".join(o["kill_reasons"]))
        else:
            print(summary_line(o["deal"], o["result"]))
            if full_cards:
                print()
                print(o["card"])
                print()


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--daily", action="store_true", help="Gmail ingest + full pipeline")
    mode.add_argument("--manual", metavar="TEXT", help="address / link / pasted listing text")
    mode.add_argument("--json", metavar="PATH", help="structured deal list (no LLM needed)")
    ap.add_argument("--no-enrich", action="store_true")
    ap.add_argument("--rescore", action="store_true", help="re-run deals already in the db")
    ap.add_argument("--full-card", action="store_true", help="print full Deal Cards")
    args = ap.parse_args()

    if args.json:
        with open(args.json) as f:
            deals = json.load(f)
        outcomes = run_batch(deals, enrich_enabled=not args.no_enrich, rescore=args.rescore)
        print_outcomes(outcomes, full_cards=args.full_card)
        return

    if args.manual:
        from .extract import extract_candidates
        deals = extract_candidates(args.manual, source="manual")
        if not deals:
            print("Could not extract a property from that input — give me at least "
                  "an address or a city plus any numbers you have.")
            sys.exit(1)
        outcomes = run_batch(deals, enrich_enabled=not args.no_enrich, rescore=args.rescore)
        print_outcomes(outcomes, full_cards=args.full_card)
        return

    if args.daily:
        from .digest import build_digest, write_digest
        from .ingest_gmail import fetch_recent_emails

        emails = []
        if all(os.environ.get(k) for k in
               ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")):
            emails = fetch_recent_emails()
            print(f"ingest: {len(emails)} email(s) from deal senders", file=sys.stderr)
        else:
            print("WARNING: Gmail secrets not set — skipping ingest", file=sys.stderr)

        deals = []
        if emails and os.environ.get("ANTHROPIC_API_KEY"):
            from .extract import extract_candidates
            for em in emails:
                try:
                    deals.extend(extract_candidates(em["text"], source=em["sender"],
                                                    email_meta=em))
                except Exception as e:
                    print(f"WARNING: extraction failed for '{em['subject']}': {e}",
                          file=sys.stderr)
        elif emails:
            print("WARNING: ANTHROPIC_API_KEY not set — cannot extract", file=sys.stderr)

        print(f"extract: {len(deals)} candidate deal(s)", file=sys.stderr)
        outcomes = run_batch(deals, enrich_enabled=not args.no_enrich)
        digest_md = build_digest(outcomes)
        path = write_digest(digest_md)
        print(f"digest: {path}", file=sys.stderr)
        print(digest_md)


if __name__ == "__main__":
    main()
