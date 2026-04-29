# LEARNINGS.md — Mistakes We Don't Make Twice

<!-- provenance: generic lessons extracted from Motion-Granted-Production/LEARNINGS.md; MG-specific lessons omitted -->

**Last Updated:** [date]

This file exists so Claude Code stops repeating the most expensive mistakes. Read it. Internalize it. If you find yourself about to violate one of these, stop and re-read.

_Add project-specific lessons below as you discover them. Use the format: problem → lesson → prevention._

---

## 1. The Dead Code Trap

**What happened:** Multiple fix sessions applied correct changes to a dead file. Every fix was technically correct. Every fix had zero production impact because the file was no longer on the live execution path.

**The lesson:** ALWAYS grep-verify the live execution path before editing any file. Trace the call chain forward from the known entry point — don't assume a file is active because it exists and compiles.

**Dead code map:** _(fill in your project's dead paths in CLAUDE.md → DO NOT Edit section)_

| Dead File/Directory | Live Equivalent |
|---|---|
| `{dead_path}` | `{live_path}` |

**Prevention:** Before editing any file, run: `grep -r "import.*from.*{filename}" {source_dir}/` to confirm something actually imports it. If zero results and it's not a known entry point, it's dead.

---

## 2. False Positive Audit Findings (38–54% Rate)

**What happened:** AI-generated audit reports consistently flagged bugs that didn't exist in the actual code. Across multiple audit sessions, 38–54% of reported findings were false positives — phantom bugs created by the auditor misreading code, missing context, or hallucinating function behavior.

**The lesson:** Never accept an audit finding at face value. Every finding must be grep-verified against the actual source before it's acted on. The forcing function: "Are you 100% certain? Show me the grep evidence."

**Common false positive patterns:**
- "Missing null check" — value is guaranteed by a prior step or database constraint
- "Unused variable" — used via destructuring, spread, or dynamic access
- "Hardcoded value" — actually imported from config; the import just isn't on the same screen
- "Function never called" — called via event routing or dynamic dispatch
- "Dead code path" — actually the active path (the reverse of Lesson #1)

---

## 3. CRLF Line Terminators — Silent Edit Failures

**What happened:** Claude Code's Edit tool silently failed when files had CRLF line terminators. The edit appeared to succeed but the file was unchanged. No error message. No warning. Nothing happened.

**The fix:** `git config --global core.autocrlf input`. This is permanent. Never revert to `true`.

**Detection:** If a Claude Code edit seems to have no effect, check line endings: `file <filename>` or `cat -A <filename> | head -5` (look for `^M` at line ends). Fix with `dos2unix <filename>`.

---

## 4. Write-Side vs Read-Side Fix Ordering

**What happened:** Read-side fixes were technically correct but complete no-ops because the field being read was never written upstream. The read-side consumers would correctly use the field — but only if the write-side actually populated it first.

**The fix:** Find and fix all write sites first. Verify the data is written. Then verify the read side uses it correctly.

**The lesson:** ALWAYS trace BOTH directions before declaring a fix complete. Ask: "Is this value actually being written before it's read?" A read-side fix only works if the write-side populates the data. Trace the full pipeline: origin → write → read → consumer.

---

## 5. Undefined Fallbacks Must Be Restrictive

**What happened:** A fallback value for an undefined state was set to the permissive option. TypeScript guaranteed the value was always present at runtime, but the fallback existed as a safety net. When the safety net triggered unexpectedly, it let bad data through instead of blocking it.

**The fix:** Every fallback and default in a data pipeline must be the most restrictive option. Unknown or missing states should produce the safest outcome, not the happiest path.

**The lesson:** Every fallback/default should answer: "If this value is unexpectedly missing, what's the safest thing to do?" The answer is always the restrictive option. This is especially critical in pipelines where downstream consumers make trust decisions based on upstream values.

---

## 6. Pattern Census Before Declaring Complete

**What happened:** One instance of a pattern was found and fixed. The fix was correct. But 10+ sibling instances of the same pattern existed elsewhere in the same file and weren't checked. The bug continued via the unfixed instances.

**The fix:** Run a full-file (or full-codebase) pattern census before declaring any pattern-level bug fixed. One correct instance does NOT mean all sibling instances are correct.

**The lesson:** For any fix that addresses a pattern (not just a single specific line), run: `grep -n '{pattern}' {file}` to find every instance. Fix all of them. Report the total count.

---

## 7. Silent Data Truncation at Stage Boundaries

**What happened:** A JSON repair / parser library silently truncated oversized output from an upstream stage before the downstream stage consumed it. No error was thrown. No warning logged. The downstream stage received partial data, accepted it as valid, and proceeded to produce incomplete results. The truncation was only discovered weeks later when output quality metrics diverged from expectations.

**The fix:** Every cross-stage handoff that uses serialization, repair, or transformation must (a) log when a size limit is reached, (b) fail loud rather than pass partial data downstream, and (c) include a length/completeness check on the receiving side that rejects obviously-truncated payloads.

**The lesson:** Silent data loss is the worst kind of bug — it produces plausible-looking output that is quietly wrong. Any step that can truncate, repair, coerce, or re-serialize data across a boundary is a ticking time bomb unless you explicitly verify completeness. Invoke the `lossy` skill before trusting any cross-boundary transformation.

**Detection heuristics:**
- Look for every `JSON.parse`, `jsonrepair`, or equivalent call — what happens if the input exceeds its limit?
- Look for every `slice`, `substring`, `.slice(0, N)`, or `LIMIT N` on data that crosses a boundary — what signals truncation to the consumer?
- Look for every schema/type assertion that narrows a nullable-rich input to a required-field output — what happens when the input lacks the fields?
- Look for every `try { parse } catch { return default }` — does the default logging include the fact that parsing failed?

**Prevention:** Explicit completeness assertions at boundaries. A sentinel/marker pattern (`{ complete: true, payload: ... }`) on producer side that consumer can verify. And a test case for the "oversized input" path on every transformation step.

---

## Meta-Lesson: Schema Before Code

Database migrations must deploy before code changes. The deployment sequence is non-negotiable: **schema → code → verify**. If your code change depends on a new column, table, or constraint, the migration must land first. The operator owns migration deployment.
