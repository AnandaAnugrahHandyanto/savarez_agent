# Acta sprint slice: archive index source-signal cards

## CEO feature bet selection

### 1. Obvious but necessary — Archive index source-signal cards
- Why it matters to P: Archive currently behaves like a date list; P has to open each day to know whether it contains real operator output, silent runs, or gaps.
- User moment: P opens Archive on mobile to find yesterday's useful briefing/action trail without scanning dead cron dates.
- Higher-order payoff: Archive becomes an operator memory surface: days can later accrue tags, read state, incident markers, and resurfacing logic.
- Risk of overbuild/dumbness: Low if limited to source-derived counts and latest title; dumb if it invents sentiment/KPI scoring.
- MVP slice: Render date cards with visible source-derived run counts (visible/silent/missing), latest title, lane mix (Daily/Dev/System), no fake data; add tests and archive UAT scenario.
- CEO leverage rating: 8/10.
- Rank: BUILD NOW.

### 2. High-leverage personal workflow — Telegram follow-up prep from archive days
- Why it matters to P: Could let P ask targeted follow-up about a day from the archive.
- User moment: P opens last Tuesday and wants to ask “what changed since then?”
- Higher-order payoff: Turns archive into action prep, not just storage.
- Risk of overbuild/dumbness: Medium; needs safe source routing and not fake follow-up automation.
- MVP slice: Spike a validated per-day ASK link only where a safe thread exists.
- CEO leverage rating: 7/10.
- Rank: SPIKE-PROTOTYPE.

### 3. Weird/magical — Archive anomaly resurfacer
- Why it matters to P: Acta could notice days with unusual churn/gaps and surface them.
- User moment: P checks “what did the system learn this week?”
- Higher-order payoff: Compounding memory and decision support.
- Risk of overbuild/dumbness: High; anomaly labels can become fake scoring without enough data.
- MVP slice: None this run.
- CEO leverage rating: 6/10.
- Rank: KILL FOR NOW.

## Persona/scenario
Persona: P as mobile operator reviewing previous days.
Scenario: Open Archive at 390px, pick the most relevant prior day, and decide whether it is worth opening based on visible counts/provenance before tapping.

## Acceptance criteria
- Archive cards show date plus source-derived visible/silent/missing counts.
- Cards show latest source title and compact lane mix (Daily/Dev/System) when summary data is available.
- Empty/no-summary archive still renders safely.
- No generic dashboard KPIs, fake scores, old amber tokens, or raw paths.
- 390px browser UAT for archive passes: no horizontal overflow, console clean, archive cards are clickable with usable hrefs, source-signal copy visible.

## Implementation scope
- `cron/acta_dashboard.py`: add archive summary data structure/helper and render card metadata; pass summaries from `build_dashboard()` publish path.
- `scripts/acta_browser_uat.py`: add `archive` scenario validator.
- `tests/cron/test_acta_dashboard.py` and `tests/cron/test_acta_browser_uat.py`: cover renderer and harness.

## Verification
- Targeted pytest: `python -m pytest tests/cron/test_acta_dashboard.py tests/cron/test_acta_browser_uat.py -q --no-isolate`.
- Real-browser fixture UAT for archive at 390x844 if browser CLI available.
- Stale token scan for old amber/generic markers in touched generated output.
