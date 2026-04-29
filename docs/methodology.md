# Methodology — How the tanner-stack System Works

<!-- provenance: written from first principles; methodology distilled from Motion-Granted-Production practice -->

This document explains the operating philosophy behind tanner-stack in plain English. Read this before reading any skill or persona file.

---

## The Core Problem

AI coding assistants make confident mistakes. They produce plausible-sounding findings, fix the wrong file, or miss the 10 other places the same pattern appears. The bigger the codebase, the worse this gets. Without a discipline layer, you get:

- Fixes applied to dead code (correct logic, zero impact)
- Audit findings that are 40–50% false positives
- Pattern fixes that address one instance and miss 10 others
- Read-side fixes that don't work because the write side never populated the data

tanner-stack is a set of reusable protocols that address each of these failure modes systematically.

---

## The Four Disciplines

### 1. Evidence Labeling (CONFIRMED / INFERRED / UNVERIFIED)

Every finding gets a label based on what you can mechanically prove:

- **CONFIRMED** — You have file:line evidence from grep or file read. This is a fact.
- **INFERRED** — The logic is sound but you haven't verified it mechanically. You can point to what would upgrade it.
- **UNVERIFIED** — You suspect it but have no evidence. You know what check would confirm it.

Why this matters: AI auditors consistently state inferences as facts. This label discipline forces the distinction. A finding labeled CONFIRMED must survive "show me the grep."

### 2. Live Path Verification

Before editing any file, verify it's actually on the live execution path. Trace imports upward from the file to a known entry point (API route, CLI, event handler). If the chain breaks — the file is dead, and any fix there has zero production impact.

This is the single most common source of wasted effort in AI-assisted coding.

### 3. Pattern Census

When a bug is a pattern (not a one-off), find every instance before fixing any of them. `grep -n '{pattern}' {file}` is the minimum. One correct instance does NOT mean all sibling instances are correct — they often aren't.

### 4. Bidirectional Tracing

Before declaring a fix complete, trace BOTH directions: upstream (who feeds this?) and downstream (who consumes this?). A read-side fix only works if the write side actually writes the data. A schema fix only works if the code reads the right column.

---

## The Persona Layer

tanner-stack ships four operating identities, each suited to a specific class of work:

| Persona | Role | When to use |
|---------|------|-------------|
| **Architect** | System-level design and decision-making | Planning, architecture reviews, trade-off analysis |
| **Chen** | Adversarial audit — hostile, evidence-demanding | Audit sessions, pre-merge reviews, finding false positives |
| **Code Reviewer** | Post-edit quality check | After any significant change |
| **Grep Verifier** | Skeptical claim validation | When an audit finding needs mechanical confirmation |

Personas are declared at session start. They're not personas in a theatrical sense — they're different operating modes with different default behaviors and rigor standards.

---

## The Skill Layer

Skills are single-purpose capabilities that auto-invoke based on description matching — each skill's `description` frontmatter field names the task signals that should fire it. Each skill changes the session's operating standard in a specific way:

- `chen` — activates the adversarial audit protocol (preloaded in the chen sub-agent)
- `100` — requires file:line proof for every claim
- `zero` — activates zero false positives / zero false negatives mode
- `soft` — bans soft conclusions (no "likely", "probably", "should work" without proof)

Skills compose. The rigor-mode skills (`100`, `zero`, `soft`) stay active for the rest of the session once invoked. The `.claude/commands/max.md` command wraps a preset combination for operators who want one-shot activation of the strictest rigor tier.

---

## The Command Layer

Commands (`/impact`, `/blast`, `/dead`, `/verify`, etc.) are reusable workflows — multi-step investigation or verification protocols. Unlike skills, which change behavior, commands produce a specific structured output.

Key commands:

| Command | What it produces |
|---------|-----------------|
| `/impact` | Full upstream/downstream impact map for a change |
| `/blast` | Blast radius analysis (files, types, pipeline stages affected) |
| `/dead` | Live/dead path verdict for a file or function |
| `/verify` | 3-leg verification: build + grep facts + tests |
| `/zt` | Zero-tolerance violation scan across the project |
| `/root` | Root-cause matrix for a symptom |
| `/zt` | Zero-tolerance violation scan |

---

## The Inviolable Rule Pattern

Every serious codebase has constraints that must never be violated — not for convenience, not under time pressure, not "just this once." tanner-stack formalizes these as Inviolable Rules in CLAUDE.md.

Each rule should be:
- **Specific** — not "be careful with errors" but "catch blocks must never return the success state"
- **Greppable** — there's a grep that would catch a violation
- **Named** — so it can be referenced in commit messages and findings

The `/zt` command is a mechanical sweep for violations of all inviolable rules.

---

## The GitNexus Layer

GitNexus is a code intelligence MCP that indexes the codebase into a symbol and execution flow graph. When connected, it enables:

- **Impact analysis** — before editing any symbol, see the full blast radius
- **Safe renames** — rename with graph awareness instead of find-and-replace
- **Change detection** — before committing, verify only expected symbols changed
- **Concept search** — find execution flows by concept, not just text

GitNexus integration is optional but strongly recommended for any codebase with >50 files.

---

## The Session Lifecycle

A well-formed session follows this sequence:

1. **Branch check** — `git branch --show-current`
2. **Context load** — read CLAUDE.md, any relevant rules files
3. **Mode declaration** — IMPLEMENT, AUDIT, or DISCOVERY
4. **Work** — with the appropriate discipline layer active
5. **Verification** — `/verify` before closing any significant task
6. **Scope discipline** — out-of-scope findings → BACKLOG.md, not inline
7. **Session close** — LEARNINGS.md update if anything new was learned
