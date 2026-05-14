# Bidding Auditor — Synthesis Playbook

Cascade of hypotheses, ordered by handoff layer. Phase 1.5 walks this list before any recommendation. Two layers are **blocking**: M (Measurement) and B (Business). The rest are sequenced or informational.

---

## M — Measurement (BLOCKING)

### M1 — Tracking gap on a flagged campaign

**Trigger:** BID-D26 raised, OR `/tracking-specialist` has unresolved findings on a campaign present in this audit.

**Why blocking:** Bid validation against actual CPA/ROAS is meaningless when conversions are mis-counted.

**Action:** Hard refuse to recommend any target/strategy change. Route to `/tracking-specialist`.

### M2 — Conversion lag exceeds learning window

**Trigger:** primary KPI is delayed > 14 days (per business.md or config).

**Action:** Re-run audit at a longer window (`/bidding-auditor 60` or `90`).

---

## B — Business (BLOCKING for target validation)

### B1 — Unit economics missing in business.md

**Trigger:** `breakEvenCPA` or `breakEvenROAS` placeholder/unset.

**Action:** Hard refuse target validation. Route to `/strategy-audit --execute unit-economics`.

### B2 — Stale unit economics (>60d since last confirm)

**Trigger:** `biddingAudit.lastConfirmed` >60d ago AND business.md has been edited since.

**Action:** Phase 0 prompts the user to reconfirm or update before proceeding.

---

## Vol — Conversion Volume (sub-cascade)

### Vol1 — Smart bidding without sufficient conv data (BID-D03)

**Trigger:** Smart bidding strategy + monthly conv below the channel-strategy absolute minimum.

**Action:** Present an options menu (auditor does NOT pick a single handoff):

> Options:
> A. Switch to MaxConv (no target, works at any volume) — `/bidding-optimizer setup`
> B. Broaden match types — `/keyword-optimizer expand` (estimated +X conv/30d)
> C. Raise budget — `/budget-optimizer raise` (estimated +Y conv/30d at current CPA)
> D. Accept 30 more days of current trajectory before re-evaluating

User picks; auditor sequences the chosen route.

---

## Eff — Efficiency Recovery (sequenced)

### Eff1 — Search-term waste depressing efficiency

**Trigger:** A target is being missed AND `/search-term-auditor` shows >threshold non-converting spend.

**Action:** Route to `/search-term-auditor` before any target loosening.

### Eff2 — Low Quality Score limiting deliverability

**Trigger:** Average QS on flagged campaigns < 5.

**Action:** Route to `/quality-score-auditor`.

### Eff3 — Weak RSAs depressing CTR/CVR

**Trigger:** RSA strength below "Good" majority on flagged campaigns.

**Action:** Route to `/rsa-maker`.

---

## Conv — Conversion (sequenced)

### Conv1 — LP/offer driving low CVR

**Trigger:** CVR for the campaign is <50% of account median, AND the campaign isn't blocked by Eff.

**Action:** Route to `/lp-auditor` and `/offer-auditor` before bid changes.

---

## Bud — Budget peer (sequenced)

### Bud1 — Budget-limited campaign (target alone won't help)

**Trigger:** `metrics.search_budget_lost_impression_share` > 30% on flagged campaign.

**Action:** Route to `/budget-auditor` first; bidding adjustments alone won't recover the lost share.

### Bud2 — Shared budget + portfolio strategy conflict (BID-D17)

**Trigger:** D17 fires.

**Action:** Route to `/bidding-optimizer fix-shared-portfolio` (the structural fix lives in this skill, not the budget skill).

---

## Comp — Competitive (informational)

### Comp1 — CPC spike from competitor entry / auction shift

**Trigger:** BID-D22 OR BID-D23 fires.

**Action:** Suggest `/competitive-analyst` for context, but do not block.

---

## Struct — Structural (informational)

### Struct1 — Recent strategy/target change still in learning

**Trigger:** BID-D11 / BID-D13 fires.

**Action:** Auditor recommends *waiting* — hard refuse on optimizer for this campaign until learning window clears.

### Struct2 — Mixed campaign types in portfolio

**Trigger:** BID-D14 fires.

**Action:** Route to `/account-auditor` for portfolio-structure review.

---

## T — Traffic / own optimizer (last)

### T1 — Pure bidding action

After every higher layer is clear OR explicitly overridden:

- BID-D05/D06 FAIL → `/bidding-optimizer adjust-targets`
- BID-D02 FAIL → Manual: Google Ads UI → Drafts & Experiments (50/50, 14–30d, promote on KPI win)
- BID-D09 starvation → `/bidding-optimizer adjust-targets --rationale=starvation-recovery`
- BID-D17 → `/bidding-optimizer fix-shared-portfolio`
- BID-D24 opportunity → `/bidding-optimizer scale` (paired with `/budget-optimizer raise`)

---

## Anti-patterns

- Never recommend a target change while M or B are blocking. Replace with the handoff.
- Never queue a strategy change AND a target change on the same campaign in the same session.
- Never recommend a target step >20% (or >30% with `--aggressive`).
- Never write a flat "recommended actions" table that mixes a tracking handoff with a target tweak — segment by cascade state.
