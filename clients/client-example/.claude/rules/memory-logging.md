# Memory Logging — Operational Work Log

Operational work logs track what was done in the account. They live in `context/memory/YYYY-MM-DD.md` and are version-controlled per client.

## When to Read Memory

Read `context/memory/` logs ONLY when:
1. User references past work ("what did we do yesterday", "continue from last time", "check what we changed")
2. Working on same campaign/ad group across multiple sessions
3. Before creating outputs that may already exist (RSAs, analysis reports)
4. Checking if budget/bid changes were made recently

**How to read:**
- Check last 3 days: `context/memory/YYYY-MM-DD.md` (today, yesterday, 2 days ago)
- Scan for relevant campaign names or task types
- If found, acknowledge what was done previously

**Don't read memory for:**
- First-time tasks (no prior context needed)
- Data pulls (gads-context, account-changelog)
- Fresh context generation (brand, offer-angles)

## When to Write to Memory

Be proactive when logging to memory. The more context we have for later the better.

Log to `context/memory/YYYY-MM-DD.md` after completing important work:

**Always log:**
- RSA creation (campaign, count, angle focus, output file)
- Campaign budget changes (old -> new, reason)
- Bid strategy changes (what, why)
- Bulk keyword/negative adds (count, campaign/level, reason)
- Major analysis (what analyzed, findings, action taken)

**Never log:**
- Data pulls or file reads
- Context file updates (business.md, brand.md)
- Questions to user
- Minor changes (< 5 keywords/negatives)

**Format:**
- One entry per section (## RSAs Created, ## Campaign Changes, ## Analysis Completed, ## Keywords Added, ## Negatives Added)
- Short: one line per action + brief context
- Link to output files when applicable (e.g., `created/rsas/campaign-name-2026-02-14.csv`)
- If today's file exists, append new section; if not, create with `# YYYY-MM-DD` header

**Example entry:**

```markdown
# 2026-02-14

## RSAs Created
- Added 5 RSAs to "Non-Brand High-Intent" campaign
- Focus: faster delivery + transparent pricing (top angles from offer-angles.md)
- Output: created/rsas/non-brand-high-intent-2026-02-14.csv

## Campaign Changes
- Increased budget on Brand campaign: $2000 -> $2500/mo
- Reason: CPA at $18 (below $20 scale threshold from business.md)
```

## Memory vs Account Changelog

| What | File | Tracks | Read When |
|------|------|--------|-----------|
| Workspace memory | `context/memory/YYYY-MM-DD.md` | Work done by user + Claude | User references past work |
| Account changelog | `context/account-changelog.md` | Changes in Google Ads UI by anyone | Before making recommendations |

**Why both?**
- Memory = your workspace decisions and outputs
- Changelog = what happened in the account (including other users' changes)

**Retention:**
Keep last 60 days. Older logs can be archived or deleted manually.
