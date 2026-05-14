# Module 4 — Portfolio Health (BID-D14 → BID-D17)

Total module weight: 15 points. Portfolios silently constrain campaigns; this module surfaces the structural risks.

## BID-D14 — Mixed Campaign Types in Portfolio (4 pts)

**Logic:** Group campaigns by `campaign.bidding_strategy` (portfolio resource). If a portfolio's members span multiple `advertising_channel_type` values → WARN. Single-channel portfolios PASS. No portfolios in account → SKIP.

**Why:** Smart bidding's auction signals differ between Search and Shopping/PMax. A mixed portfolio dilutes both.

## BID-D15 — CPC Cap Active (3 pts)

**Detection:** Any non-zero `cpc_bid_ceiling_micros` on tROAS / TIS / Manual or Maximize-* on portfolios *or* inline campaign settings.

**Verdict:** WARN if any cap exists on smart bidding. The cap can constrain the system unnecessarily — see /sops/Bid Strategy Selection Reference.md.

## BID-D16 — Cap vs. Top CPCs (4 pts)

**Verdict:** INFO. Compare any active CPC cap to the 75th-percentile keyword CPC over the audit window (read from `keyword-auditor` output if available). If the cap is below the top quartile → recommend reviewing.

## BID-D17 — Shared Budget + Portfolio Strategy (4 pts)

**Logic:** A campaign on a shared budget AND a portfolio bid strategy fights pacing against the portfolio target. FAIL.

**Routing:** Hard handoff to `/bidding-optimizer fix-shared-portfolio` — the optimizer's only "structure-fixing" subcommand.
