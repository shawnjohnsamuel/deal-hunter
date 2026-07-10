"""Daily digest: summary table ranked by composite score, full Deal Cards for
the top 3 (framework-v2 output contract), judgment calls surfaced explicitly."""
from datetime import date
from pathlib import Path

from .deal_card import METRIC_LABELS, TOP3, _fmt_metric

REPO_ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = REPO_ROOT / "data" / "digests"


def build_digest(outcomes: list[dict]) -> str:
    today = date.today().isoformat()
    scored = sorted((o for o in outcomes if o["outcome"] == "scored"),
                    key=lambda o: o["result"]["score"], reverse=True)
    killed = [o for o in outcomes if o["outcome"] == "killed"]
    dupes = [o for o in outcomes if o["outcome"] == "duplicate"]

    lines = [f"# Daily Deal Digest — {today}", ""]
    if not outcomes:
        lines += ["No new candidate properties today.", ""]
        return "\n".join(lines)

    lines += [f"**{len(outcomes)} candidate(s):** {len(scored)} scored, "
              f"{len(killed)} killed by first-pass filter, {len(dupes)} duplicate(s).", ""]

    if scored:
        lines += ["## Scored deals (ranked by composite score)", "",
                  "| # | Verdict | Score | Address | Tier | CoC | Cash Flow/yr | Top flag |",
                  "|---|---------|-------|---------|------|-----|--------------|----------|"]
        for i, o in enumerate(scored, 1):
            r, d = o["result"], o["deal"]
            m = r["underwriting"]["metrics"]
            top_flag = (r["hard_disqualifiers"] or r["red_flags"] or ["—"])[0]
            lines.append(
                f"| {i} | **{r['verdict']}** | {r['score']:.0f} "
                f"| {d.get('address', '?')}, {d.get('city', '?')} | {r['tier'].upper()} "
                f"| {_fmt_metric('coc', m.get('coc'))} "
                f"| {_fmt_metric('annual_cash_flow', m.get('annual_cash_flow'))} "
                f"| {top_flag[:80]} |")
        lines.append("")

        judgment = []
        for o in scored:
            for f in o["result"]["red_flags"]:
                if "judgment call" in f or "UNVERIFIED" in f or "UNKNOWN" in f:
                    judgment.append(f"- **{o['deal'].get('address', '?')}, "
                                    f"{o['deal'].get('city', '?')}**: {f}")
        if judgment:
            lines += ["## Judgment calls for the human", ""] + judgment + [""]

        lines += ["## Top deals — full cards", ""]
        for o in scored[:3]:
            lines += [f"### {o['deal'].get('address', '?')}, {o['deal'].get('city', '?')}",
                      "", o["card"], ""]

    if killed:
        lines += ["## Killed by first-pass filter (no research spent)", ""]
        for o in killed:
            lines.append(f"- **{o['deal'].get('address', '?')}, {o['deal'].get('city', '?')}** — "
                         + "; ".join(o["kill_reasons"]))
        lines.append("")

    lines += ["---", "*Verdicts are calibrated to the private investor profile. "
              "Tax figures are planning estimates — CPA + cost seg specialist before acting. "
              "STR legality flags are search-based and require human verification.*"]
    return "\n".join(lines)


def write_digest(md: str) -> Path:
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    path = DIGEST_DIR / f"{date.today().isoformat()}.md"
    path.write_text(md)
    return path
