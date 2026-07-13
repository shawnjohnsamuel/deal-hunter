# Real Estate Investment Framework — v2.2.1

**Single source of truth.** Supersedes Framework v1.0 (both the ChatGPT and Claude variants) and incorporates the Personal Financial Profile (completed July 7, 2026) as the authoritative override wherever the two conflicted.

> **v2.2.1 (July 11, 2026) — calibrated against Victor's actual P&Ls:** STR defaults now include owner-paid cleaning ($725/mo) and lodging/HOT tax (7% of revenue), both overridable by stated figures. Non-destination STR rule is two-tier: teaser-newsletter ones still die at the kill filter; **full-address agent deals get scored for the database but are capped at BORDERLINE** — the Tier-1 buy is a mountain STR, and Victor's pipeline (DFW/Austin/San Antonio) feeds Tiers 2–3 primarily.
>
> **v2.2 (July 10, 2026):** Deal Card rebuilt around the **four-pillar methodology** of Victor Steffen (the highest-priority, highest-trust source) — asset quality, neighborhood quality, vacancy risk, cash-flow margin — applied uniformly to deals from every source. Victor's own underwriting is captured and compared side-by-side with ours (divergence >10% flagged). D-grade neighborhoods are a new hard disqualifier. Exception factors (financing incentive, walk-in equity, unicorn location) are recorded explicitly.
>
> **v2.1 (July 10, 2026):** mountain markets promoted to explicit STR Tier 1 priority (+composite bonus); deal-flow source roster documented with per-sender behavior (agents send addresses, teaser newsletters don't); teaser-identification procedure added; every deal now carries provenance (source name + deep link to the original email).

> **What changed from v1.0 → v2.0 (reconciliation record)**
>
> | Item | v1.0 said | v2.0 says (authoritative) | Why |
> |---|---|---|---|
> | LTV ceiling | ≤80% | **≤85%** | Aggressive risk posture, Financial Profile |
> | Bonus depreciation | Phasing down toward 20% by 2026 | **100%, permanent** | OBBBA (signed July 4, 2025) restored 100% bonus depreciation for property placed in service after Jan 19, 2025. The phase-down language is dead law. |
> | Tier 1 capital | Split across all three tiers upfront | **Concentrated: nearly all available capital into the Tier 1 STR** (amounts in the private profile) | Capture the Year 1 tax window; Tiers 2–3 funded later from tax savings + cash flow |
> | Year 1 tax offset | Important, not urgent | **Urgent — place STR in service in 2026** | Five-figure realistic Year 1 cash tax savings (projection in the private profile) |
> | Verdict posture | Wait for PASS | **Act on BORDERLINE** (which ones is a judgment call) | Aggressive posture; return floors unchanged |
> | Output format | Always produce full Deal Card | **Verdict + top 3 metrics first; full Deal Card on request** | Evolved working preference |
> | MTR | Implied in expert panel | **Out of scope** | No criteria were ever defined; add a real buy box before reintroducing |

---

## 1. Who This Is For

Beginner investor with W2 income, aggressive risk tolerance, and a defined pool of liquid capital (exact figures live in `private/profile.json`, never in this repo). Wife transitioning toward real estate professional status (REP); 3 young kids, so time-realistic strategies only. Considering relocation to Dallas, TX. The spouse-income-replacement target is a multi-year build requiring an estimated 8–10 cash-flowing properties, not a Year 1 outcome.

**Goals in priority order:**
1. **Tax optimization (urgent, 2026)** — STR loophole + cost segregation + 100% bonus depreciation to offset W2 income
2. **Replace wife's income** — reliable monthly cash flow
3. **Long-term appreciation & equity**
4. **Diversification**

## 2. Three-Tier Strategy

### Tier 1 — Short-Term Rental (STR) — ACTIVE PRIORITY
- **Goal:** activate the STR tax loophole in 2026. Average guest stay <7 days makes the STR a business activity; depreciation losses (accelerated via cost seg + 100% bonus depreciation) offset W2 income **without REP status**, given material participation (100+ hrs and more than anyone else).
- **Target:** destination markets (mountains/beach/lake) with year-round demand and verified STR legality. Price range $400K–$550K.
- **Capital:** concentrated — nearly all available capital into down payment + closing, with a non-negotiable reserve cushion (exact allocation in the private profile).
- **Value of the play:** each $1 of paper loss saves marginal-tax-rate cents in cash. A cost seg study on a target-range property typically accelerates 25–30% of value into Year 1 deductions — a five-figure cash tax saving at this profile's rate. Planning estimate — confirm with CPA + licensed cost seg specialist before acting.

### Tier 2 — House Hack in Dallas (deferred, funded from Tier 1 proceeds)
- Duplex/small multifamily as primary residence; owner-occupant financing (FHA 3.5% / conventional 5% down). Funded from the Year 1 tax refund + STR cash flow + W2 savings — not from the initial $100K.

### Tier 3 — Long-Term Rentals (Year 2+)
- SFR/small multifamily in cash-flow-positive markets, professionally managed. Funded by recycled equity/cash flow + BRRRR where applicable.

## 3. Analysis Pipeline (the order is the point)

Every deal — emailed, scraped, or manually submitted — moves through these stages. **Never skip the kill filter on bulk lists.**

```
INTAKE → TIER CLASSIFICATION → FIRST-PASS KILL FILTER → ENRICHMENT (survivors only)
       → DEAL CARD → METRICS → BUY BOX SCORING → VERDICT (+ tax flags, red flags)
```

### 3a′. Deal-flow source roster (who sends what)

| Sender | Who | Kind | What to expect |
|---|---|---|---|
| victor@steffenrealtycorp.com | Victor Steffen, Steffen Realty (agent) | **Full addresses** | **HIGHEST PRIORITY — trusted.** All deal types (STR + LTR), pre-vetted through his four-pillar filter, arrives with his grades and full underwriting |
| info@theshorttermshop.com | Avery Carl, The Short Term Shop (agent) | **Full addresses** | STR-focused |
| theoffersheet@mail.beehiiv.com | The Offer Sheet | **Teaser / paywall** | Best deal fully detailed except the address; lesser deals alongside |
| here@mail.beehiiv.com | Here (beehiiv) | **Teaser / paywall** | Same pattern |
| team@bnbflow.co | BNB Flow | **Teaser / paywall** | Same pattern |

**Teaser identification procedure** (`pipeline/identify.py`): for paywalled candidates missing an address, extraction captures every distinguishing detail (exact price, beds/baths/sqft, sleeps, features verbatim, nightly rate, revenue, list dates), then a web-search pass tries to pin the live listing. Match grading is strict — HIGH needs price within 1% + exact beds/baths + (sqft within 3% or a verbatim feature match); MEDIUM allows unverified sqft/features; LOW/NONE stays unidentified. High/medium matches adopt the address but are **permanently flagged "identified via research — verify before acting."** Unidentified teasers are scored on claimed numbers only and flagged.

### 3a. Tier classification (at intake)
The three tiers are NOT handled uniformly — different buy boxes, financing, data sources, and disqualifiers. Classify first: STR candidate (destination market, or STR-sourced lead), House Hack (2–4 units, DFW, owner-occ eligible), or LTR (everything else that rents). A property may be evaluated under more than one tier if genuinely ambiguous.

### 3b. First-pass kill filter (cheap, deterministic, before any research)
Kill immediately, with no enrichment spend, if any of:
- **STR:** price > $600K (capital can't reach it at 15% down), or confirmed non-destination market
- **House Hack:** price > $450K, or <2 units, or not owner-occ eligible
- **LTR:** 1% rule below 0.8% *on claimed rent* AND GRM > 14 (both, using seller-claimed numbers — if it fails even the seller's own optimistic math, it's dead)
- **Any tier:** confirmed HOA/ordinance STR prohibition (for STR strategy), or listing is land/commercial/uninhabitable

Unknown market status is a **flag, not a kill** — "is this a destination market" is a human judgment call (Broken Bow yes, Little Elm no; the edge cases are Shawn's).

### 3c. Enrichment (survivors only)
- **Listing data (primary): Redfin via OpenWebNinja API** — real tax history, HOA, listing status, days on market, price history, Redfin estimate, beds/baths/sqft backfill (2 requests/deal from a 100/month free tier; survivors only). Also powers deterministic teaser identification: search the stated market, match price ±1.5% + exact beds/baths, sole match = high confidence.
- Property record, tax assessment, rent estimate, AVM: RentCast (ration free-tier calls; STR candidates first)
- STR revenue: Rabbu/AirDNA estimates via web search; flag `str_data_estimated` when not from real comp data
- Property tax: **county appraisal district (CAD) records** (Collin CAD, etc.) — never listing estimates; fallback 1.2% of price
- Redfin/Zillow data fallback (no API key/quota): direct fetches 403 — **search "full address + Redfin Zillow"** then confirm with a second search
- Rates: search live 30-yr investment rates each run; never assume
- STR legality: search "[city] short-term rental ordinance" → status `unverified / likely_ok / restricted`. **Never auto-cleared. Human-verify before any offer.**
- Seller P&Ls and pro formas: **always recompute independently** with our vacancy/CapEx assumptions. Sellers omit CapEx and use fantasy vacancy.

## 3½. The Four Pillars (Deal Card headline — Victor Steffen methodology)

Every deal is graded A–D on four pillars before the buy-box math. The methodology comes from Victor Steffen's vetting filter (codified from his own description); his emails arrive with grades, other sources get estimated grades that are **always marked estimated**.

| Pillar | What it measures | Grade guidance | Provenance ladder |
|---|---|---|---|
| **1. Asset quality** | Renovation need + ongoing-maintenance risk. The failure mode is the "nickel-and-dime" property that eats the owner alive in month-6 | A: turnkey/new; B: minor cosmetic; C: dated but functional; D: major systems/reno risk | Victor's grade → LLM estimate from listing condition/age/reno mentions → ungraded |
| **2. Neighborhood quality** | Schools, crime, tenant/guest quality | A: top schools, low crime; B: solid in-between; C: sufficient safety, usually the cash-flow plays; **D: hard disqualifier — we don't do D** | Victor's grade → LLM estimate from schools/crime/market data → ungraded |
| **3. Vacancy risk** | Occupied now? Lease-up speed if not. The failure mode is the 120-days-vacant call | A: occupied / pre-leased; B: fast lease-up market (<7% vacancy); C: average; D: slow market or chronic vacancy | Victor's occupancy statement → market vacancy data → ungraded |
| **4. Cash-flow margin** | Margin, consistency, variability | **Always computed, never LLM.** A: at/above target CoC with DSCR ≥1.25; B: at/above buy-box min; C: below min but above the floor; D: below floor (STR floor = 6% CoC — "wouldn't even post it"), DSCR <1.0, or negative cash flow | Deterministic from the scoring engine |

**The pillars interact on a spectrum** (Victor's rule): weakness in one bucket is acceptable only when dramatically offset in another — C-neighborhood is where the highest CoC lives; a barely-break-even deal in a unicorn location can still be a push.

**Exception factors** — recorded explicitly on the card, never silently applied: exceptional financing terms; walk-in equity (price materially below comps/floor-plan sales); unicorn location (streets/neighborhoods where inventory never appears). They raise a deal's ranking and are flagged so the human sees *why* a thin deal is still surfaced — they never flip a FAIL.

**Composite v3** = pillar-weighted blend (cash-flow pillar carries the metric composite inside it; weights: cash flow 45%, asset 20%, neighborhood 20%, vacancy 15%; ungraded pillars renormalize). Mountain-STR bonus applies after the blend.

**Victor divergence check:** Victor's emails include his own underwriting ("real insurance, real taxes, actual income"). His inputs are extracted as high-trust claimed data; the engine still recomputes with our assumptions and shows both. Any line item or output diverging **>10%** is flagged with both numbers — trust, but make disagreement visible.

**Two floors, kept distinct:** Victor's 6% STR CoC is his *posting* floor (pillar-4 D-grade). Shawn's 8% buy-box minimum is the *buying* floor (verdict). A 7% CoC STR grades C on pillar 4 and still shows a buy-box fail on CoC.

**Appreciation context** (when stated): ~3–12% YoY in tertiary cash-flow markets; ~5.5–6% in premium A-grade markets — captured as a note, verified against MLS history when possible.

## 4. Buy Boxes

### STR Buy Box (Tier 1)
| Criteria | Minimum | Target |
|---|---|---|
| Gross Rental Yield | 15% | 20%+ |
| Occupancy (AirDNA/Rabbu) | 65% | 75%+ |
| ADR | Market competitive | Top 25% of comp set |
| Cap Rate | 6% | 8%+ |
| Cash-on-Cash Return | 8% | 12%+ |
| Annual Net Cash Flow | Break-even | $15,000+ |
| Break-Even Occupancy | <50% | — |
| Loan-to-Value | — | **≤85%** |
| HOA / STR Restrictions | None — verify explicitly | — |
| Market Type | Destination (mountain/beach/lake) | **Mountain markets — Tier 1 priority** (+5 composite bonus so equivalent mountain deals outrank beach/lake) |
| Price | — | $400K–$550K |

### House Hack Buy Box (Tier 2, Dallas)
| Criteria | Minimum | Target |
|---|---|---|
| Units | 2 | 2–4 |
| Rental Coverage of Mortgage | 50% | 75%+ |
| Purchase Price | — | ≤$450K |
| Neighborhood | B class+ | A/B class |
| Market Vacancy | — | <7% |
| Owner-Occ Financing | Required | FHA or Conv |

### LTR Buy Box (Tier 3)
| Criteria | Minimum | Target |
|---|---|---|
| GRM | <12 | <10 |
| Cap Rate | 6% | 8%+ |
| Cash-on-Cash Return | 6% | 10%+ |
| 1% Rule | 0.8% | 1%+ |
| Annual Net Cash Flow | $3,600 ($300/mo) | $6,000+ ($500/mo) |
| Market Population | 100,000+ | 250,000+ |
| Rent Growth YoY | 2% | 4%+ |

### Hard disqualifiers (auto-FAIL, no discussion)
1. HOA or local ordinance restricts/prohibits STRs → kills the STR strategy (tax-compliance issue, not just yield)
2. Non-destination market for the STR strategy (bedroom communities and lake-adjacent suburbs don't count)
3. DSCR < 1.0
4. House hack above ~$450K or ineligible for owner-occupant financing

## 5. Deal Card (standard format)

```
DEAL CARD
─────────────────────────────────────
Property Address:
Market / City:
Property Type: [SFR / Duplex / STR / Multi-family]
Strategy Fit: [STR / House Hack / LTR]

PURCHASE
  List Price:            Estimated ARV:
  Down Payment (% / $):  Loan Amount:
  Interest Rate (assumed):  Loan Term:
  Estimated Closing Costs:  Furnishing (STR, if unfurnished):
  Total Cash Needed:

INCOME
  Gross Monthly Rent (LTR) or Gross Annual STR Revenue:
  Vacancy / Occupancy Assumption:
  Effective Gross Income:

EXPENSES (Monthly)
  Mortgage (P&I):  Property Tax (CAD):  Insurance:  HOA:
  CapEx Reserve:   Management:          Utilities:  Other:
  Total Monthly Expenses:

NET CASH FLOW
  Monthly NOI:  Monthly Cash Flow (after debt):  Annual Cash Flow:

KEY METRICS
  Cap Rate:  CoC:  GRM:  1% Rule:  Gross Yield:  DSCR:  Break-Even Occ (STR):

BUY BOX VERDICT
  [ ] PASS  [ ] BORDERLINE  [ ] FAIL
  Tax flags:   Red flags:   Judgment calls for Shawn:
─────────────────────────────────────
```

**Output contract:** verdict + top 3 metrics first; full Deal Card only on request. Bulk submissions: summary table ranked by composite score (CoC-weighted), full cards for top 3 only. State assumptions once, never repeat them.

## 6. Assumption Defaults (when data is missing)

### LTR / general
| Item | Default |
|---|---|
| Vacancy (LTR) | 8% |
| CapEx Reserve | 5% of gross rent |
| Property Management (LTR) | 8% of gross rent |
| Insurance | **0.5% of value/yr** (×1.5 for STR policies = 0.75%) — market-calibrated Jul 2026; the v1 "$100–150/mo per $100K" default was 2–4× market and silently failed even target-yield deals. Stated figures always override. |
| Interest Rate | Live 30-yr investment rate (search) |
| Property Tax | CAD record, else 1.2% of price |
| Closing Costs | 3% of price |

### STR-specific (new in v2 — was a v1.0 gap)
| Item | Default |
|---|---|
| Occupancy (no data) | 65% |
| ADR (no data) | **Flag and ask — never assume** |
| STR Management | 20% of revenue (15–25% range) |
| Cleaning | **Owner-paid $725/mo** (Victor-calibrated); $0 only when guest-paid is confirmed |
| Lodging / HOT tax | **7% of revenue** (Victor-calibrated for TX; override with stated figure; $0 only if platform-remitted) |
| Utilities (owner-paid) | $300/mo |
| Supplies / consumables | 2% of revenue |
| Platform fees | 3% of revenue |
| Furnishing capex (unfurnished) | $12–15K, added to Total Cash Needed |
| STR insurance | 1.5× the LTR insurance default (short-term rental policy) |

## 7. Key Metrics (formulas)

- **Cap Rate** = NOI ÷ Price (6% min / 8% target) — ignores financing
- **Cash-on-Cash** = Annual pre-tax cash flow ÷ Total cash invested — **the most important metric** (LTR 6/10, STR 8/12)
- **GRM** = Price ÷ Gross annual rent (<12 / <10)
- **1% Rule** = Monthly rent ÷ Price (0.8% / 1%+) — filter, not dealbreaker
- **NOI** = Effective gross income − operating expenses (excl. mortgage); always include vacancy + CapEx
- **DSCR** = NOI ÷ Annual debt service (1.0 min / 1.25+ target; lenders want 1.25)
- **Gross Rental Yield** = Gross annual rent ÷ Price (STR 15% min / LTR 8%)
- **Break-Even Occupancy (STR)** = Total annual expenses ÷ (ADR × 365) — must sit **below 50%**; if break-even > market average occupancy, you're betting on outperforming
- **ROE** = Annual cash flow ÷ Current equity (Year 3+ refinance/1031 signal)
- **Equity Multiple** = Total cash returned ÷ Total cash invested (full-hold measure)

## 8. Tax Strategy (mechanical triggers — flag on every deal)

| Trigger | Flag |
|---|---|
| Average guest stay < 7 days | STR loophole eligible — active losses offset W2 without REP, given material participation (100+ hrs AND more than anyone else) |
| Purchase price > $300K | Cost segregation candidate (25–30% of value typically accelerated) |
| Cost seg + **100% bonus depreciation (OBBBA, permanent)** | Front-load deductions into Year 1; cash value = deductions × the marginal rate in the private profile |
| HOA / ordinance STR restriction | STR strategy dead — hard disqualifier |
| Large paper losses without STR treatment or REP status | Flag as suspended until REP (wife: 750+ hrs AND more than any other profession — building toward, not yet active) |

Standing caveat (say once per analysis, not per line): planning estimates — confirm with CPA and licensed cost segregation specialist.

## 9. Behavior & Tone (system instructions)

- Direct, unsoftened verdicts. Challenge instinct when it conflicts with data. No disclaimer-machine hedging; flag uncertainty plainly and still give a verdict.
- Plain-English summaries — this investor is learning, not an expert. Educational asides only when genuinely relevant.
- **Always flag:** HOA/STR-restriction verification status, seller-number recomputation, DSCR < 1.0, thin margins, the tax angle.
- **Never assume:** STR viability outside confirmed destination markets; ADR without data (ask); that listing tax figures are accurate.
- **Never skip:** the first-pass kill filter on bulk lists.
- **Never automate (human judgment):** borderline destination-market calls, which BORDERLINE deals to act on, ARV, condition/CapEx risk from photos, negotiation strategy, regulatory-trajectory risk, rent-comp sanity checks.

## 10. Out of Scope (v2)

- **MTR (mid-term rentals):** no buy box exists. To add in v3: define rent premium threshold (typically 1.5–2× LTR), demand markers (hospitals/travel-nurse/corporate), 30+ day stay tax treatment.
- Market-specific assumption sets: not enough deal volume yet (Milestone 2 in progress via the automated pipeline). DFW suburban is the only proven pattern, and that pattern is "everything fails."

---
*Framework v2.0 — July 2026. Reconciled from Framework v1.0 (ChatGPT + Claude variants), the Personal Financial Profile (July 7, 2026), and the project audit.*
