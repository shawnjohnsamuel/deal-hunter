---
name: add-deal
description: Add a property to the deal-hunter database and score it against the personalized buy box. Use when the user drops in an address, a Redfin/Zillow link, pasted listing text, or says "add this deal", "score this property", "analyze this address".
---

# Add a deal to the pipeline

Run a property through the same pipeline the daily automation uses: parse → dedupe → kill filter → enrich → score → store → dashboard.

## Steps

1. **Collect the input.** Anything works: bare address, listing URL, pasted MLS/newsletter text, or a list of numbers. If the user gave a URL, fetch what you can first (Redfin/Zillow direct fetches 403 — search "full address + Redfin Zillow" instead) and combine what you learn with the user's text so extraction has maximum material. Include any numbers the user or listing states (price, rent, ADR, occupancy).

2. **Run the pipeline** from the repo root (the directory containing `pipeline/`):

   ```bash
   python3 -m pipeline.run --manual "<all the text/details you collected>"
   ```

   - Requires `ANTHROPIC_API_KEY` in the environment (extraction is LLM-parsed). If it's missing, tell the user and offer the structured path: write the deal as JSON (see `pipeline/run.py --json`) which needs no API key.
   - Add `--no-enrich` if the user wants a fast claimed-numbers-only score, or if enrichment keys (`RENTCAST_API_KEY`) are unavailable.
   - Add `--rescore` if the property is already in the database and the user wants it re-run (e.g., price drop).
   - Add `--full-card` if the user asked for the full breakdown.

3. **Report in the framework's output contract:** verdict + top 3 metrics first (the script's summary line), then offer the full Deal Card. Do not dump the card unasked.

4. **Surface the judgment calls.** If output flags say "judgment call for the human" (destination-market status, unverified STR legality, seller-claimed income), state them explicitly — these are the user's decisions, never yours.

5. **Publish.** If the run changed `data/deals.db` / `site/deals.json`, commit and push so the dashboard redeploys:

   ```bash
   git add data/deals.db site/deals.json && git commit -m "Add deal: <address>" && git push
   ```

   Skip the push if the user says they're just experimenting.

## Notes

- The scoring thresholds come from `private/profile.json` (falls back to the sanitized example — warn the user if the fallback fired, verdicts won't be personalized).
- KILLED means the first-pass filter ended it (price ceiling, confirmed non-destination market, fails the seller's own math). Report the kill reasons verbatim — they're designed to be plain English.
- Never soften verdicts. FAIL is FAIL with reasons, per the framework's tone rules.
