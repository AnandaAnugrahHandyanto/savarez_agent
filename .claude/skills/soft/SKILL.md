<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/soft/SKILL.md
Original purpose: Enforces hard-evidence-only debugging; bans "likely" / "probably" hand-waving.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: soft
description: Use PROACTIVELY when user says "no guessing", "hard evidence only", "prove it with the source", or Claude has been hand-waving instead of proving. Bans soft conclusions — no "likely", "probably", "should work", "might be" without exact file / line / runtime value / fix shown. Less strict than /100 (which also requires full-file pattern census and deep wire trace). Stays active for the rest of the session.
user-invocable: true
disable-model-invocation: true
---

# NO SOFT CONCLUSIONS MODE — Active for This Session

From this point forward in this session, the following rules override all other behavior:

## Rules

1. **No "likely" or "probably."** If you cannot show the exact file, exact line, exact runtime value, and exact fix — say "I don't know yet" and explain what you'd need to find out.

2. **No "prompt-related" hand-waving.** If you claim something is caused by a prompt instruction, show: (a) the exact prompt file path, (b) the exact instruction text, (c) the exact runtime payload that was affected, (d) before and after values.

3. **No "this might be."** Every diagnostic claim must have grep evidence or SQL evidence. CONFIRMED or INDETERMINATE. Nothing in between.

4. **No "I've seen this pattern before."** Pattern recognition is not evidence. Show the code. Show the data. Show the delta.

5. **No speculative fixes.** If you can't prove the root cause, you can't propose a fix. Diagnose first. Prove second. Fix third.

6. **If asked "are you sure?"** — treat it as "show me the grep." Not as "say yes more confidently."

## What You CAN Say

- "I confirmed at {file}:{line} that {exact behavior}"
- "I found no evidence for this claim after checking {list of places searched}"
- "I need to check {specific thing} before I can answer — running that now"
- "I don't know. Here's what I'd need to investigate."

## What You CANNOT Say

- "This is likely caused by..."
- "It's probably a prompt issue"
- "Based on the pattern, I think..."
- "This might be related to..."
- "I believe the fix would be..."

Hard evidence or honest uncertainty. Nothing in between.
