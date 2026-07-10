# Personal Financial Profile — Template

> **This is a sanitized template.** The real profile lives at `private/profile.json`, which is gitignored and never committed. The pipeline reads the real file when present and falls back to `config/profile.example.json` otherwise, so the repo runs out of the box for anyone.

## What goes in the profile

| Input | Why it matters |
|---|---|
| W2 income + combined marginal tax rate | Converts paper losses to real cash value (each $1 of deduction saves $<rate> in cash) |
| Income replacement target (monthly) | Sizes the long-game portfolio (how many cash-flowing doors) |
| Liquid capital | Sets the price ceiling the kill filter enforces (down payment reach at your LTV) |
| Risk tolerance | Aggressive → higher LTV ceiling, act on BORDERLINE verdicts; conservative → PASS-only |
| Buy-box thresholds (3 tiers) | Every verdict is scored against *your* numbers, not generic benchmarks |
| Assumption defaults | What the engine assumes when a listing is missing data — always tagged `assumed` in output |
| Tax triggers | STR loophole stay length, cost-seg price trigger, bonus depreciation %, REP status |

## Setup

1. Copy the template: `cp config/profile.example.json private/profile.json`
2. Replace every financial value with your real numbers
3. Adjust buy-box thresholds if your strategy differs from the defaults
4. `private/` is already in `.gitignore` — verify with `git check-ignore private/profile.json`

## Standing caveats baked into every analysis

- Tax projections are planning estimates. Confirm with a CPA and a licensed cost segregation specialist before acting.
- STR legality flags are search-based and **never auto-cleared** — verify with the county/city and HOA before making an offer.
