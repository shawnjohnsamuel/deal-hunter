# 🏠 Deal Hunter

**An automated daily real estate deal pipeline.** Every morning it reads my deal-flow
emails, extracts candidate properties, enriches the survivors with public data,
underwrites them against a personalized three-tier buy box, and publishes ranked
verdicts — with the judgment calls deliberately left human.

**[Live dashboard →](https://shawnjohnsamuel.github.io/deal-hunter/)** ·
**[How it works →](https://shawnjohnsamuel.github.io/deal-hunter/architecture.html)** ·
Built with [Claude Code](https://claude.com/claude-code)

```
Gmail (2 agents + 3 paywalled teaser newsletters) ─► GitHub Action (daily cron)
   ─► Claude extracts candidates (seller numbers tagged, never trusted;
       every deal carries a deep link back to its source email)
   ─► dedupe ─► deterministic kill filter (zero research spent on dead deals)
   ─► teaser identification (paywalled deals arrive address-less — a strict
       web-search match on price/beds/sqft/features recovers the listing,
       graded HIGH/MEDIUM/LOW and always flagged for human verification)
   ─► enrichment (RentCast · county tax records · live rates · STR-ordinance search)
   ─► unit-tested scoring: metrics → buy box → hard disqualifiers → tax triggers
       (mountain-market STRs get a Tier 1 priority bonus)
   ─► PASS / BORDERLINE / FAIL + 0–100 ─► digest issue + dashboard redeploy
```

## Why it's built this way

- **LLM only where language is messy; code everywhere math must be right.** Claude
  parses newsletters and synthesizes web research. Every metric, threshold, and verdict
  is deterministic Python with a test suite ([pipeline/](pipeline/), [tests/](tests/)).
- **The kill filter runs before any money or tokens are spent.** Most emailed deals fail
  arithmetic the seller's own numbers already fail — those die free, and the rationed
  free-tier API budget goes to deals that might survive.
- **Judgment stays human.** Borderline destination-market calls, which BORDERLINE deals
  to act on, rehab risk, and final STR-legality verification are flagged, never automated.
- **Personal financials never enter the repo.** Scoring reads a gitignored
  `private/profile.json`; a sanitized [example](config/profile.example.json) ships so the
  pipeline runs for anyone. The dashboard shows verdicts, never income.
- **The strategy is versioned.** The [investment framework](docs/framework-v2.md) is
  markdown in this repo — when an assumption proves wrong, the fix is a commit.

## Repo map

| Path | What |
|---|---|
| [docs/framework-v2.md](docs/framework-v2.md) | The single source of truth: buy boxes, kill filter, assumption defaults, tax triggers |
| [docs/deal-analysis-playbook-v2.md](docs/deal-analysis-playbook-v2.md) | Operating rules, milestones, division of labor |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Design decisions + the document-reconciliation story behind v2 |
| [pipeline/](pipeline/) | Ingest → extract → kill filter → enrich → score → digest |
| [tests/](tests/) | Metric math + verdict fixtures (`python -m pytest`) |
| [site/](site/) | The dashboard (vanilla HTML/JS, GitHub Pages) |
| [.claude/skills/add-deal/](.claude/skills/add-deal/SKILL.md) | `/add-deal` — drop any address into the pipeline from Claude Code |
| [.github/workflows/daily-hunt.yml](.github/workflows/daily-hunt.yml) | The daily cron |

## Setup (to run your own)

1. **Clone, install, test:** `pip install -r requirements.txt && python -m pytest`
2. **Profile:** `cp config/profile.example.json private/profile.json`, put in your real
   numbers. For CI, store the file's contents as the `PROFILE_JSON` repo secret.
3. **Gmail (read-only):** follow the docstring in
   [scripts/gmail_oauth_setup.py](scripts/gmail_oauth_setup.py) — Google Cloud project,
   enable Gmail API, desktop OAuth client, run the script once locally. Store
   `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` as repo secrets.
   Edit `DEAL_SENDERS` in [pipeline/ingest_gmail.py](pipeline/ingest_gmail.py) to your senders.
4. **API keys:** `ANTHROPIC_API_KEY` (extraction + web-search enrichment), optional
   `RENTCAST_API_KEY` (free tier: 50 calls/mo). The pipeline degrades gracefully —
   anything missing is skipped with a warning, never a crash.
5. **Pages:** repo Settings → Pages → Source: GitHub Actions. The daily workflow deploys
   `site/` after each run. Trigger a first run from the Actions tab (`workflow_dispatch`).

Manual intake anytime:

```bash
python -m pipeline.run --manual "123 Pine Ridge Trl, Broken Bow OK — $475k cabin, ADR $350"
python -m pipeline.run --json data/seed_demo.json --no-enrich   # offline demo
```

## Current status & roadmap

- ✅ Framework v2 reconciled (OBBBA tax law, personalized thresholds, STR expense defaults)
- ✅ Scoring engine + kill filter + tests · ✅ daily automation · ✅ dashboard · ✅ `/add-deal`
- 🔜 Vet community Redfin/Zillow MCP servers (no official public MCP exists yet)
- 🔜 AirDNA comps instead of estimates · price-drop re-scoring · MTR buy box ·
  market-specific assumption sets once deal volume accumulates

*Early dashboard entries are seeded demo deals so the pipeline's behavior is visible
while live email volume accumulates.*

---

*Personal project — not investment advice. Tax projections are planning estimates
requiring CPA + cost-segregation-specialist confirmation.*
