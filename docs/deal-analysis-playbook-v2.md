# Deal Analysis Playbook — v2.0

How this project runs day to day. The strategy and thresholds live in [framework-v2.md](framework-v2.md); this document tracks milestones, roles, and operating rules.

## Vision

A messy email, link, or address goes in; within seconds a verdict comes out — tier-classified, enriched with public data, scored against a personalized buy box, tax angle flagged — calibrated to Shawn's financial situation. v2 upgrades v1's "paste a deal at me" workflow into an **automated daily pipeline** that hunts deals from email without being asked.

## Milestones

| Milestone | Status | What it is |
|---|---|---|
| 1 — Financial Blueprint | ✅ **COMPLETE (July 7, 2026)** | Personal financial profile locked; all buy-box thresholds are Shawn's numbers, not generic defaults. Lives in `private/profile.json` (never committed). |
| 2 — Analysis Engine, stress-tested | 🔄 **IN PROGRESS — now automated** | v1 planned "manually submit 5–10 deals." v2 replaces that with the daily pipeline: every deal email is parsed, scored, and logged automatically, so deal volume accrues daily. Market-specific assumption sets get locked in once patterns emerge from the accumulated database. |
| 3 — Portable App | 🔄 **IN SCOPE NOW (was deferred)** | The GitHub Pages dashboard + the `/add-deal` skill together are the portable app: any device can view scored deals; any address can be dropped into the pipeline. |

## The Daily Loop (automated)

1. **07:00 CT** — GitHub Action wakes, pulls the last 48h of email from the five deal sources:
   - `victor@steffenrealtycorp.com` — all deal types
   - `theoffersheet@mail.beehiiv.com`, `here@mail.beehiiv.com`, `team@bnbflow.co`, `info@theshorttermshop.com` — STR-focused
2. Claude extracts candidate properties (address, price, claimed financials — always tagged *seller-claimed*)
3. Dedupe against the database → tier classification → **first-pass kill filter** (no research spent on dead deals)
4. Survivors get enriched (RentCast, Rabbu/web search, CAD taxes, live rates, STR-legality search)
5. Deterministic scoring → PASS / BORDERLINE / FAIL + 0–100 composite score
6. **Daily digest** posted as a GitHub issue: summary table ranked by score, full Deal Cards for the top 3, judgment calls flagged for Shawn
7. Dashboard redeploys automatically with the updated database

## Division of Labor

| The pipeline (deterministic code) | Claude (LLM) | Shawn (human judgment — never automated) |
|---|---|---|
| All metric math | Parsing messy emails into structured deals | Borderline destination-market calls |
| Buy-box scoring & verdicts | Web-search enrichment synthesis | Which BORDERLINE deals to act on |
| Hard disqualifiers | Summarizing red flags in plain English | ARV & condition/CapEx risk from photos |
| Tax-flag triggers | | Negotiation strategy |
| Assumption defaults | | STR regulatory-trajectory risk |
| Dedupe & ranking | | Final STR-legality verification before offers |

## Operating Rules (carried forward + evolved)

- Verdict + top 3 metrics first; full Deal Card on request. Bulk: summary table ranked by composite score, full cards for top 3.
- State all assumptions explicitly, once.
- Seller pro formas are always recomputed independently.
- Direct verdicts, plain English, no disclaimer-machine — but the CPA/cost-seg caveat rides on every tax projection.
- If an output feels wrong, Shawn flags it and the assumption set gets corrected in the framework — the framework is living, versioned in git.

## Success Definition

The system is working when: deal emails are triaged every morning without prompting; anything surfaced in the digest is genuinely worth a human look; a dropped-in address returns a verdict in under a minute; and the Tier 1 STR gets found, underwritten, and placed in service in 2026.
