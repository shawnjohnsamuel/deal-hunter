# Architecture — Real Estate Deal Hunter

An automated daily pipeline that reads deal-flow emails, extracts candidate properties, enriches them with public data, scores them against a personalized investment buy box, and publishes the results to a live dashboard — with a human-in-the-loop boundary drawn deliberately, not accidentally.

## Pipeline

```
Gmail (5 deal-flow senders) ──► GitHub Action (daily cron, ~7am CT)
                                    │
        ┌───────────────────────────┼────────────────────────────┐
        ▼                           ▼                            ▼
   1. INGEST                   2. EXTRACT                   3. DEDUPE
   Gmail API,                  Claude parses messy          normalized-address
   gmail.readonly scope,       newsletter HTML into         hash against SQLite
   last 48h, sender filter     structured candidates
                                    │
                                    ▼
                            4. KILL FILTER  ◄── deterministic, zero research spend:
                               price ceilings, 1% rule on seller-claimed rent,
                               confirmed non-destination markets, unit counts
                                    │ survivors only
                                    ▼
                            5. ENRICH
                               RentCast (records, tax, rent estimate, AVM)
                               Rabbu/AirDNA estimates via web search
                               County CAD tax records
                               Live investment mortgage rates
                               STR-ordinance legality search (never auto-cleared)
                                    │
                                    ▼
                            6. SCORE  ◄── pure Python, unit-tested:
                               metrics → buy box → hard disqualifiers →
                               tax triggers → PASS/BORDERLINE/FAIL + 0–100
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
              7a. DIGEST                      7b. DASHBOARD
              GitHub issue: ranked            static site on GitHub Pages,
              table + top-3 Deal Cards        redeployed on every run
```

## Design decisions

**LLM only where language is messy; code everywhere math must be right.**
Claude (claude-sonnet-5) does exactly two jobs: parsing unstructured newsletter emails into structured candidates, and synthesizing web-search enrichment. Every metric (cap rate, cash-on-cash, DSCR, GRM, break-even occupancy), every buy-box comparison, every hard disqualifier, and every tax-flag trigger is deterministic, unit-tested Python. A scoring engine you can't reproduce is a vibe, not an underwriting tool.

**The kill filter runs before any money or tokens are spent.**
Most emailed deals die on arithmetic the seller's own numbers already fail. The first-pass filter kills those with zero API calls, so the free-tier enrichment budget (RentCast: 50 calls/month) is rationed to deals that might actually survive — STR candidates first, per the Tier 1 priority.

**Judgment calls are flagged, never automated.**
Whether a borderline market counts as a "destination" (a tax-compliance question, not just a yield question), which BORDERLINE deals to act on, ARV, condition risk, and final STR-legality verification are surfaced as explicit flags in the digest and left to the human. The pipeline's job is to make the judgment call cheap, not to make it.

**Personal financial data never enters the repo.**
The scoring engine reads `private/profile.json` (gitignored). The repo ships a sanitized `config/profile.example.json` so the pipeline runs for anyone who clones it. The public dashboard shows deals, metrics, and verdicts — never income, capital, or tax numbers.

**Everything is versioned, including the strategy.**
The investment framework itself lives in the repo as markdown. When an assumption proves wrong, the fix is a commit — the strategy has a diff history.

## The document-reconciliation story (why v2 exists)

The project began as parallel AI-partner experiments: a complete but static framework (buy boxes, Deal Card template, metrics guide) and a series of newer working documents that evolved past it. By July 2026 the knowledge base contradicted itself on four load-bearing facts — LTV ceiling, bonus depreciation law (OBBBA made the original phase-down language dead law), capital allocation, and urgency. An audit established precedence (newest personalized document wins), identified gaps neither source covered (no first-pass filter stage, no STR operating-expense defaults, an undefined MTR tier), and the reconciliation became [framework-v2.md](framework-v2.md) — the single source of truth the pipeline is built on.

**Strengths and weaknesses of the two v1 sources:**

| | ChatGPT framework v1 | Claude working docs v1 |
|---|---|---|
| Structure | ✅ Complete: 3 buy boxes, Deal Card, 10-metric plain-English guide, tax context | ❌ Fragmentary (truncated exports) |
| Currency | ❌ Frozen: pre-OBBBA tax law, generic assumptions, 80% LTV | ✅ Current: OBBBA update, personalized numbers, evolved output format |
| Pipeline thinking | ❌ "Always produce a full Deal Card" — no triage stage | ✅ Evolved toward fast kills + deep dives on survivors (but never written down) |
| Personalization | ❌ Milestone 1 never completed in that thread | ✅ Milestone 1 complete: real income, capital, risk posture |

v2 = ChatGPT's completeness + Claude's currency + the audit's pipeline formalization.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Orchestration | GitHub Actions (cron + workflow_dispatch) | Free, runs regardless of any laptop, and the automation is itself public/reviewable |
| Email | Gmail API, `gmail.readonly` OAuth scope | Read-only blast radius; refresh token as a repo secret |
| Extraction / enrichment | Claude API (claude-sonnet-5) with web search | Structured-output parsing of messy HTML; live data where no API exists |
| Property data | RentCast + Rabbu free tiers, county CAD records | $0/month v1; upgrade path to paid tiers and AirDNA documented in README |
| Storage | SQLite committed to the repo + sanitized JSON export | Zero infra; the database has a git history |
| Frontend | Vanilla HTML/CSS/JS on GitHub Pages | No build step, free hosting, redeploys on every data commit |
| Manual intake | Claude Code skill (`/add-deal`) | Drop in any address/link/listing text; same pipeline, same database |

## Future iterations

- Vet community Redfin/Zillow MCP servers (no official public MCP exists as of July 2026)
- AirDNA subscription for real STR comps (ADR/occupancy) instead of estimates
- MTR tier with a real buy box (rent premium threshold, travel-nurse/corporate demand markers)
- Market-specific assumption sets once the database accumulates enough volume per market
- Price-drop tracking: re-score killed deals when a followup email shows a reduced price
