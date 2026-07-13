---
name: hunt-deals
description: Interactively triage the dedicated deal-flow inbox (realestatefrfr@gmail.com) — fetch all unscraped emails via the Gmail connector, extract deals, score them, and update the dashboard. Use when the user says "hunt deals", "check the deal inbox", "run the pipeline", "triage my deal emails", or similar.
---

# Interactive deal hunt (no-API-key mode)

You (Claude, in this session) play the role the Claude API plays in the automated
pipeline: read unscraped emails from the dedicated inbox, extract structured
deals, and feed them to the deterministic engine. Everything else — kill filter,
underwriting, pillars, verdicts, dedupe, export — is `pipeline/` code you run,
never math you do in your head.

## Procedure

1. **Fetch unscraped mail.** Use the Gmail connector (`search_threads` /
   `get_message`) on the dedicated inbox. The inbox receives ONLY deal flow, so
   search broadly (e.g. `in:inbox`) rather than filtering by sender. Collect
   each message's RFC-822 Message-ID (or the connector's message id as
   fallback), subject, date, sender, and full body text. Skip anything already
   in the registry:

   ```bash
   python3 -c "from pipeline.processed import is_processed; print(is_processed('<MSG_ID>'))"
   ```

2. **Identify the true source per email.** Match the From address against
   `SENDER_META` in [pipeline/ingest_gmail.py](../../../pipeline/ingest_gmail.py).
   **Forwarded emails** (e.g. testing via a personal address, subject "Fwd:"):
   the real sender is inside the body — look for the original `From:` line and
   match THAT against SENDER_META; use the original subject/date for metadata
   when visible. If no source matches, ask the user rather than guessing.

3. **Extract deals exactly as `pipeline/extract.py` specifies.** Read that
   file's `EXTRACTION_PROMPT` — it is your instruction set: same JSON fields,
   same rules (seller numbers into `claimed` verbatim; percentages as decimals;
   occupancy status; condition/neighborhood notes; exception factors).
   Apply the source-specific guidance:
   - **Victor** (`VICTOR_GUIDANCE`): capture his A–D grades into
     `victor.grades`, his OUTPUT numbers (cash flow, CoC, cap) into
     `victor.underwriting`, his INPUT numbers (tax, insurance, mgmt %,
     cleaning, HOT/lodging tax) into `claimed`. Use in-place income, not his
     pro-forma bumps (note the difference in `notes`).
   - **Teaser newsletters** (`TEASER_GUIDANCE`): extract address-less headline
     deals with every distinguishing detail; set `"teaser": true`.
   Attach provenance to every deal: `source`, `source_name`, `source_kind`,
   `email_subject`, `email_date`, `email_link`
   (`https://mail.google.com/mail/u/0/#search/rfc822msgid:<MSG_ID>`).

4. **Identify teaser addresses yourself.** For paywalled deals without an
   address, run the strict matching from
   [pipeline/identify.py](../../../pipeline/identify.py) using WebSearch:
   price within 1% + exact beds/baths + (sqft within 3% or verbatim feature)
   = high; fill the `identification` block with confidence + evidence; adopt
   the address only at high/medium. No credible match → leave address null.

5. **Score through the engine.** Write the extracted deals to
   `data/hunts/<date>.json` and run from the repo root. Source the shell
   profile first — `REDFIN_API_KEY` lives in ~/.zshrc and enables structured
   enrichment (real taxes, HOA, listing status, Redfin estimate; 2 API calls
   per addressed survivor from a 100/month free tier) plus deterministic
   teaser identification for market-stated teasers:

   ```bash
   source ~/.zshrc && python3 -m pipeline.run --json data/hunts/<date>.json
   ```

   Add `--no-enrich` only when the key is absent or quota is tight; report
   `pipeline.redfin.calls_made` awareness (survivors only, never killed deals).

6. **Mark emails processed** (only after a successful scoring run):

   ```bash
   python3 -c "from pipeline.processed import mark_processed; mark_processed('<MSG_ID>', note='<subject>')"
   ```

7. **Publish.** Commit `data/deals.db`, `data/processed_emails.json`,
   `site/deals.json` and push — the dashboard redeploys automatically on push.
   Pull --rebase first; if `site/deals.json` conflicts, keep the newest export.

8. **Report** in the framework's output contract: counts, then the summary
   lines ranked by score (the runner prints them), duplicates and kills noted,
   judgment calls surfaced explicitly. Full Deal Cards only on request.

## Rules

- Never invent numbers: anything not stated in the email is left null for the
  engine's assumption defaults (they get flagged as assumed automatically).
- Optional light enrichment (only if the user asks): live rates, CAD tax
  records, STR-legality checks via WebSearch — put findings in `enriched`.
- The registry is the source of truth for "unscraped" — never re-extract a
  processed email even if it looks new.
