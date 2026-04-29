# Verification Report

> **v0.3.1 note (2026-04-22):** This file is the v0.2-era verification snapshot. Slash-prefixed skill references (`/100`, `/adverse`, `/diagnose`, etc.) in this document reflect the v0.2 invocation convention. v0.3.0 and v0.3.1 superseded that convention with description-based auto-invocation (see CLAUDE.md §3 and §3.5). The historical content is preserved as-is for audit-trail continuity.

**Produced:** 2026-04-21 (MODE 3 / VERIFY)
**Operator:** Porter Tanner
**Target:** tanner-stack — cold-start adoption check + R8 additions
**Commits verified:** 320e3ec → 01afa4d (10 commits total since inception)

---

## Summary Verdict

**PROVISIONALLY CLEAN, pending operator review.** No blocking defects. Ten findings surfaced — two structural (F1, F4) worth fixing before shipping to a client, the other eight are polish-level and optional.

R8 greps clean at body level. All eight teaching sections present in root CLAUDE.md. Provenance headers: 100% coverage on `personas/`, `skills/`, `workflows/`, `docs/`, `prompts/`. Karpathy synthesis is real enforcement mapping, not generic advice. Hook points for Swarm / Hermes / Mythos / Arsenal all documented with the four-field template the operator specified (what / where / invokers / status).

---

## Method

1. **Cold-start simulation.** Opened `CLAUDE.md` and followed every link as if I had zero prior context about Motion Granted, the source repos, or this session. Traced the chain through `docs/methodology.md` → `personas/` → `skills/` → `workflows/` → `docs/architecture.md` → `docs/extending.md` and confirmed each destination is self-sufficient.
2. **R8 greps (exhaustive).** Ran the two required greps twice each: once for all-line coverage (confirms most matches are in provenance headers), once for body-only (skip first 10 lines of each file, confirm no domain leakage in content).
3. **Provenance audit.** Scripted header-presence check across every file under `personas/`, `skills/`, `workflows/`, `docs/`, `prompts/`. Result: 100% coverage.
4. **Structural spot checks.** Read `docs/architecture.md` end-to-end to confirm Hook Points subsections. Re-read the Karpathy synthesis in `CLAUDE.md §8` to evaluate mapping quality. Spot-read a sample of skill files (`chen`, `100`, `grep-verify`, `code`, `diagnose`, `swarm`, `lossy`) to confirm they read without domain context.

---

## Spec Question 1 — Does the root `CLAUDE.md`, read in isolation, teach a new agent how to use this system?

**Verdict: YES, with one referenced-but-not-linked gap (F1).**

All 8 required teaching sections present and numbered:

| # | Section | Line | Status |
|---|---|---|---|
| 1 | What This Stack Is | 10 | ✓ |
| 2 | Read the Methodology First | 27 | ✓ links to `docs/methodology.md`, `docs/architecture.md`, `docs/extending.md` |
| 3 | Personas — How to Pick One | 39 | ✓ table of all 4 personas with file links + one-line when-to-invoke |
| 4 | Skills — Check Before Writing Code | 54 | ✓ grouped index of all 25 skills by category |
| 5 | Audit → Fix → Build Loop | 73 | ✓ summary + links to all 3 workflow docs |
| 6 | Extending the Stack | 90 | ✓ covers persona/skill/command/rule/workflow additions |
| 7 | Swarm Mode — Parallel-Agent Activation | 104 | ✓ links `skills/swarm/SKILL.md` + `docs/architecture.md § Future Hook Points` |
| 8 | Common LLM Coding Pitfalls | 126 | ✓ 4 Karpathy principles mapped to enforcement surfaces (see Q7) |

Additional sections 9 (What This File Is NOT) and 10 (Handoff) are welcome extras that disambiguate the teaching file vs. the project template.

**Gap flagged:** `AGENTS.md` exists at the repo root with mode selection rules, parallel-agent rules, model routing, and the GitNexus mandate — but **the teaching CLAUDE.md does not link to AGENTS.md**. A cold session reading only CLAUDE.md will miss the session-mode selection framework (IMPLEMENT / AUDIT / DISCOVERY) and the model-routing table. See F1 below.

---

## Spec Question 2 — Can a new project adopt this repo as a template by copying it into their codebase?

**Verdict: YES. Adoption path is documented and actionable.**

Evidence:
- `README.md` has a "Quick start" section with four concrete steps.
- `docs/project-claude-md-template.md` holds the downstream project's starter `CLAUDE.md` with all domain-specific slots called out.
- `docs/architecture.md § Configuration Slots` enumerates every placeholder that needs filling (`YOUR_REPO_NAME`, Inviolable Rules, Project section, Commands, DO NOT Edit, PreToolUse hook pattern, PostToolUse hook command, launch configurations, rule files).
- `docs/extending.md` covers adding personas, skills, commands, rules, workflows.
- `.claude/settings.json`, `launch.json`, `rules/example-rule.md`, `.github/pull_request_template.md` all ship as scaffolds.

**Minor observation (F5):** if a downstream operator skims the root and doesn't read §9 of CLAUDE.md carefully, they might initially confuse "the teaching CLAUDE.md in tanner-stack" with "the project CLAUDE.md they need to author" — but §9 addresses this explicitly. Non-blocking.

---

## Spec Question 3 — Are there any remaining references to Motion Granted, legal terminology, MG-specific infrastructure, or hardcoded paths?

**Verdict: NONE in body content. Provenance-header references only, which are within spec.**

### R8 Grep List 1 — `motion|attorney|docket|jurisdiction|CIV|phase-executor`

**Body-level matches (skip first 10 lines of each file):** **0**.

All 41 grep hits across the repo are confined to lines 2–5 of files — i.e., within the provenance header block of each extracted file. Spec (R7) permits source-domain references in provenance headers ("Extracted from: .../motion granted/..."). No content-level leakage.

### R8 Grep List 2 — `ptann|Tanner|Clay|Motion Granted|Motion-Granted`

**Body-level matches:** **0**.

Every match is either:
- A source path in an `Extracted from:` header (e.g., `C:/Users/ptann/OneDrive/Work/motion granted/...`), or
- An `Operator: Porter Tanner` line in the provenance header, or
- A `<!-- provenance: genericized from Motion-Granted-Production/... -->` HTML comment.

No "Clay", "Motion Granted", or similar name appears anywhere in the content of any `.md` file in the repo.

### Hardcoded paths

Spot-checked: `.claude/settings.json`, `.claude/launch.json`, `docs/architecture.md`. No hardcoded MG paths (`C:\Users\ctann\MG-Test\`, `Motion-Granted-Production-LIVE`, etc.) remain. `docs/project-claude-md-template.md` has the original slot placeholders (`{path/to/dead/file}`, `{path/to/production-live-repo/}`) which is correct for a template.

### Residual domain terms worth noting

`dispatch 70c370b` extracted 17 of 18 commands; the one skipped (`sql`) was kept as a skill only. No legal-domain term appears in any of the 17 command files at the body level per the R8 grep.

---

## Spec Question 4 — Does each persona have a clear mode-declaration pattern?

**Verdict: PARTIAL. Architect has a multi-mode pattern; the other three don't explicitly declare.**

| Persona | Mode pattern | Evidence | Status |
|---|---|---|---|
| `architect.md` | Multi-mode (DISCOVER → EXTRACT → VERIFY) with halt gates. Declares mode at start of every response. | Lines 10, 19, "Operating Modes" subsection | ✓ Explicit |
| `chen.md` | Defers to superprompt's 4 internal audit modes (Deep Subsystem / Finding Expansion / Spec-to-Code Delta / Pre-Launch Failure). | No explicit mode declaration in chen.md body; superprompt has them. | ⚠ Implicit |
| `code-reviewer.md` | Single-mode (post-diff structural review). | No mode declaration; operates one-shot. | ⚠ Implicit |
| `grep-verifier.md` | Single-mode (skeptical claim validator). | No mode declaration; operates one-shot. | ⚠ Implicit |

**AGENTS.md defines three session-level modes** (IMPLEMENT, AUDIT, DISCOVERY). Chen belongs to AUDIT. Code Reviewer and Grep Verifier operate within IMPLEMENT (pre-commit) or AUDIT (post-hoc). The mapping is implicit.

Non-blocking, but inconsistent. See F4.

---

## Spec Question 5 — Does each skill have a SKILL.md that makes sense without MG context?

**Verdict: YES. Spot checks passed.**

Spot-checked 7 of 25 skills, chosen to cover different categories:

| Skill | Reads standalone? | Notes |
|---|---|---|
| `chen/SKILL.md` | ✓ | Wrapper that defers to superprompt. All references are relative links. |
| `100/SKILL.md` | ✓ | Rigor mode. Entirely generic — no MG terms. |
| `grep-verify/SKILL.md` | ✓ | Has placeholder syntax like `{field_X}` and `{functionName}`; the 38–54% baseline is attributed generically. |
| `code/SKILL.md` | ✓ | Deep-code-verification protocol. One reference to "highest-severity-protocol-violation patterns" is abstracted correctly. |
| `diagnose/SKILL.md` | ✓ | 4-phase protocol. Dead-code-trap table uses placeholders (`{deprecated module A}`). |
| `swarm/SKILL.md` | ✓ | Parallel-agent protocol. MG-specific examples replaced with generic `<zone-A>` etc. |
| `lossy/SKILL.md` | ✓ | Lossy-transformation hunter. The "Common Lossy Patterns" section describes abstract patterns (JSON repair truncation, field overwrite with wrong semantic) without legal-domain examples. |

Plus `_template/SKILL.md` — scaffold with clear placeholder slots.

All 25 other SKILL.md files pass the R8 body-level grep (zero hits). High confidence that the remaining unspotted skills are also standalone.

---

## Spec Question 6 — Are the Swarm / Mythos / Hermes / Arsenal hook points documented even though unimplemented?

**Verdict: YES. All four are documented in `docs/architecture.md § Future Hook Points` using the four-field template the operator specified.**

Each subsection includes:

| Subsystem | "What it is" | "Plug-in point" | "What's needed to implement" | Line |
|---|---|---|---|---|
| Swarm Mode | Parallel agent coordination layer | Persona-selection layer in AGENTS.md | Coordination bus, work-claiming protocol, synthesis step | 42 |
| Hermes (Notification / Routing Agent) | Lightweight routing agent for findings/alerts | Separate MCP-connected agent hooking session-end + violation events | MCP server with Slack/GitHub, finding serialization, routing rules | 52 |
| Mythos (Long-Term Memory Layer) | Persistent cross-session memory | Session-start (read) + session-end (write) hooks | Vector store / knowledge base, retrieval protocol, write discipline | 60 |
| Arsenal (Tool Registry) | Dynamic tool / MCP discovery registry | Session-init phase before mode selection | Tool manifest format, context-matching algorithm, dynamic MCP loading | 68 |

The **"do not fabricate detail"** directive from the operator's MODE-2 guidance is honored: descriptions are pitched at plausibility for a planning doc, not invented architecture. Each one names what's needed to implement rather than pretending a design exists.

Swarm additionally has current-state acknowledgment ("The `/swarm` command implements single-session swarm decomposition... Full multi-process swarm coordination is not implemented") which correctly distinguishes today's partial implementation from the future integration goal.

---

## Spec Question 7 — Does the Karpathy synthesis actually apply to general LLM coding, or is it too narrow / too broad?

**Verdict: APPLIES. The four principles generalize to any LLM-assisted coding project, and the mapping to tanner-stack enforcement surfaces is real.**

| Principle | Karpathy gist | Enforcement surface claimed | Mapping tightness |
|---|---|---|---|
| 8.1 Think Before Coding | State assumptions; ask if uncertain | `/100`, `/soft`, `/zero`, persona mode-declaration | **TIGHT.** `/100` mandates file:line proof (= explicit claims); `/soft` bans "likely"/"probably" (= no hidden confusion); `/zero` mandates pattern census (= thinking before declaring); mode declaration = explicit intent. All four enforce the principle directly. |
| 8.2 Simplicity First | Minimal code; no speculative features | Chen's "no rewrites when precise fixes are available"; Code Reviewer's scope-drift check | **TIGHT.** Chen superprompt §REQUIRED OUTPUT STYLE includes the exact quoted directive. Code Reviewer Check 8 (Scope Drift) directly catches speculative scope expansion via GitNexus `detect-changes`. |
| 8.3 Surgical Changes | Touch only what you must; don't "improve" unrelated areas | `/adverse` integration-wiring check; Code Reviewer's blast-radius analysis | **MOSTLY TIGHT.** Code Reviewer Check 7 (Blast Radius) is a direct match — it warns when a change affects many symbols, which is the "surgical" signal. `/adverse` is about completeness coverage and is a looser fit — it enforces "did you cover everything" rather than "did you touch only what you must." |
| 8.4 Goal-Driven Execution | Verifiable success criteria before implementation | `/diagnose` Phase 3 (FIX PROPOSAL); `/verify` three-leg loop; Chen's EXECUTION PROOF RULE | **TIGHT.** `/diagnose` Phase 3 step 7 mandates "Test strategy: How to verify the fix works". `/verify` is literally structure + facts + behavior. Chen's EXECUTION PROOF RULE: "Will this code actually execute? Will the right function run?" is exactly about provable success criteria. |

**Overall:** not generic advice dropped into a doc. Each principle is tied to a concrete, named enforcement surface in the stack. The weakest mapping (8.3 → `/adverse`) is defensible but could be tightened — see F3.

**Applicability test:** ran the principles through three independent scenarios (React feature build, Rust CLI refactor, Python data-pipeline bug) — the mappings hold for each. Not domain-specific to Motion-Granted or to the legal-tech origins of the source repos.

---

## R8 Additional Requirements

### R8a — Grep `motion|attorney|docket|jurisdiction|CIV|phase-executor` outside provenance headers
**Result: 0 matches.** Covered in Q3 above.

### R8b — Grep `ptann|Tanner|Clay|Motion Granted|Motion-Granted` outside provenance headers
**Result: 0 matches.** Covered in Q3 above.

### R8c — Every file under `personas/`, `skills/`, `workflows/`, `docs/` has a provenance header
**Result: 100% coverage.**

- `personas/`: 4/4 ✓ (architect, chen, code-reviewer, grep-verifier)
- `skills/`: 25/25 ✓ (all SKILL.md files + `_template/SKILL.md`)
- `workflows/`: 4/4 ✓ (audit-fix-build, audit-report-template, commit-conventions, pr-review)
- `docs/`: 4/4 ✓ (architecture, extending, methodology, project-claude-md-template)
- Bonus — also audited: `prompts/superprompts/chen-audit-protocol.md` ✓, `LEARNINGS.md` ✓, `BACKLOG.md` ✓, `AGENTS.md` ✓, `.claude/rules/example-rule.md` ✓

### R8d — Root `CLAUDE.md` contains all 8 required teaching sections
**Result: CONFIRMED.** See Q1 table above.

---

## Findings (with proposed fixes — NOT applied)

### F1 — `AGENTS.md` exists but is not linked from root `CLAUDE.md` (Medium)

**What:** A cold session reading only `CLAUDE.md` will miss the session-mode selection framework (IMPLEMENT / AUDIT / DISCOVERY), the parallel-agent rules, the model routing table, and the GitNexus inviolable mandate — all of which live in `AGENTS.md` at the repo root.

**Why it matters:** `AGENTS.md` is the governance layer. A fresh session that edits code without ever reading it will miss the "never self-promote from AUDIT to IMPLEMENT without approval" rule and the model routing guidance.

**Proposed fix (do not apply):** Add a one-line reference in `CLAUDE.md §1` under the asset table:

```md
| **Governance** | `AGENTS.md` | Session-level mode selection (IMPLEMENT / AUDIT / DISCOVERY), parallel-agent rules, model routing, GitNexus mandate. Read this after methodology.md. |
```

Alternative: add to §2 reading order: "Then read `AGENTS.md` for session governance."

---

### F2 — Dependency graph in `architecture.md` omits `workflows/` and `docs/` (Low)

**What:** `docs/architecture.md § Dependency Graph (Current)` lists CLAUDE.md, AGENTS.md, LEARNINGS.md, BACKLOG.md, `.claude/rules/`, `.claude/commands/`, `.claude/settings.json`, personas, skills, GitNexus — but not `workflows/` or `docs/`.

**Why it matters:** The graph is supposed to show everything that gets loaded. `workflows/` files are referenced from CLAUDE.md §5; `docs/` is referenced from CLAUDE.md §2.

**Proposed fix (do not apply):** Append two rows to the dependency graph:

```
workflows/*.md ──────────── referenced from CLAUDE.md §5 and persona PR flow
docs/*.md ───────────────── referenced from CLAUDE.md §2 for orientation
```

---

### F3 — Karpathy §8.3 mapping (Surgical Changes → `/adverse`) is the loosest (Low)

**What:** `/adverse` enforces completeness coverage (did you check all three dimensions?), which is not quite the same as surgical restraint (did you touch only what you must?). Code Reviewer's blast-radius check IS a tight match.

**Why it matters:** Minor — the overall synthesis is strong. This one mapping is the only one where a reader might think "that's not really what adverse does."

**Proposed fix (do not apply):** Replace the §8.3 enforcement line with:

```md
> Enforced by: Code Reviewer's blast-radius and scope-drift checks, Chen's directive "do not propose rewrites when precise fixes are available", `/100`'s "no fix without proven root cause" rule.
```

Drops `/adverse` from §8.3 (it stays in §8.1 and the integration-wiring angle lives in the broader Chen protocol anyway). Adds `/100`'s rule, which is a tighter fit for the "don't refactor as a side effect" principle.

---

### F4 — Persona mode declarations inconsistent (Medium)

**What:** `architect.md` has explicit multi-mode; `chen.md` defers implicitly; `code-reviewer.md` and `grep-verifier.md` don't declare at all. Not uniform.

**Why it matters:** Makes it harder for a future-session agent to know what mode a persona is operating in, especially chen vs. code-reviewer (both do code review but at different scopes).

**Proposed fix (do not apply):** Add a Mode section near the top of each persona file (under the frontmatter, before the body):

```md
## Mode

- `chen.md`: **AUDIT** mode (per AGENTS.md). Runs with forked context. Never self-promotes to IMPLEMENT.
- `code-reviewer.md`: **IMPLEMENT** mode, pre-commit phase. Single-pass structural review.
- `grep-verifier.md`: **AUDIT** mode, single-pass claim validation.
```

Alternative: add a `mode:` field to each persona's YAML frontmatter.

---

### F5 — Project template naming (Low)

**What:** `docs/project-claude-md-template.md` is clear-enough but a more explicit filename would signal its role at a glance.

**Why it matters:** Minor — §9 of CLAUDE.md handles the disambiguation.

**Proposed fix (do not apply):** Rename to `docs/downstream-project-CLAUDE-template.md` or `docs/project-CLAUDE-md-starter.md`. Non-blocking; only do this if you want the clarity bump.

---

### F6 — Chen persona renaming guidance not in `extending.md` (Low)

**What:** Operator decided to keep "Chen" as a persona name. If a downstream user wants to rebrand (e.g., call it "Auditor" for client optics), `docs/extending.md` doesn't cover renaming personas.

**Why it matters:** Not critical — renaming markdown files is trivially obvious — but a one-liner in extending.md would be operator-friendly.

**Proposed fix (do not apply):** Add a subsection to `docs/extending.md`:

```md
## Renaming a Persona

1. Rename the file: `git mv personas/chen.md personas/auditor.md`
2. Update the `name:` field in the frontmatter.
3. Update the skill wrapper: `skills/chen/SKILL.md` → `skills/auditor/SKILL.md` (also update internal references).
4. Update links in root `CLAUDE.md § Personas` and any workflow docs that reference the old name.
5. Grep for the old name: `grep -rn 'chen' . --include='*.md'`.
```

---

### F7 — `architect.md` provenance `Original purpose:` still references "Motion-Granted" (Low)

**What:** `personas/architect.md:3` reads: `Original purpose: Multi-mode systems-extraction persona that distilled Motion-Granted methodology into this repository.` This is inside the provenance header so it's within R7/R8 spec, but the header describes the persona's historical role. If tanner-stack is handed to a client, a reader will see "Motion-Granted" in the provenance.

**Why it matters:** Spec-allowed. Only matters if the operator wants 100% Motion-Granted-reference-free provenance on the signature persona.

**Proposed fix (do not apply):** Soften to: `Original purpose: Multi-mode systems-extraction persona; used to distill this repository from a production source codebase.`

---

### F8 — No `INDEX.md` files in `personas/`, `skills/`, `workflows/` (Low)

**What:** A fresh session browsing `personas/` directory directly (e.g., via a file tree) sees 4 files without an index explaining selection criteria. CLAUDE.md §3 and §4 provide the index, so this is only an issue if someone bypasses the teaching doc.

**Why it matters:** Minor. CLAUDE.md is the intended entry point.

**Proposed fix (do not apply):** Optional — add `personas/README.md`, `skills/README.md`, `workflows/README.md` mirroring the CLAUDE.md §3/§4 tables. OR leave as-is because CLAUDE.md covers it.

---

### F9 — Two paths in commands/ have subtle MG-echo in placeholder names (Low, non-blocking)

**What:** Not verified exhaustively in this pass; the R8 body grep was clean, but `.claude/commands/verify.md`, `db.md`, and a few others use placeholder names like `<CIV-fixes branch>` → wait, this was genericized. Let me re-check.

**Why it matters:** If a command still uses an MG branch name as an example, a new user might copy it literally.

**Status:** R8 grep showed 0 matches in `.claude/commands/*.md` bodies, so this finding is **SUPERSEDED** — the concern was unfounded. Keeping the entry for transparency about what I looked for.

---

### F10 — `DISCOVERY.md` from MODE 1 still at repo root (Low)

**What:** `DISCOVERY.md` (269 lines, MODE 1 findings report) is committed at the repo root of the shipped template. A downstream adopter will see it when they browse.

**Why it matters:** It's an artifact of the extraction process. Downstream users don't need the MG-specific discovery notes. On the other hand, it's useful provenance / evidence for the operator. Subjective call.

**Proposed fix (do not apply):** Either:
- (a) Move to `docs/extraction-history/DISCOVERY.md` so it's out of the way but preserved.
- (b) Delete after MODE 3 approval.
- (c) Leave as-is for operator's records.

Operator's call.

---

## Cold-Start Readability — Overall Impression

Reading tanner-stack as if for the first time, the orientation chain works:

1. Land on `README.md` — understand this is a methodology starter kit. ✓
2. Open `CLAUDE.md` — get the 10-section orientation, including what NOT to treat it as. ✓
3. Follow §2 to `docs/methodology.md` — understand the four disciplines. ✓
4. Pick a persona from §3 — links work, character sheets are self-contained. ✓
5. Want to audit something? §5 points to the audit-fix-build workflow. ✓
6. Want to extend? §6 points to `docs/extending.md`. ✓
7. Want to activate swarm / understand future integrations? §7 points to architecture.md. ✓
8. Want to avoid common LLM coding traps? §8 gives Karpathy's 4 principles with concrete enforcement surfaces. ✓

Two genuine friction points:

- **F1** — no link to `AGENTS.md` from the teaching doc. I noticed this the moment I looked at the root listing and saw both files. A cold session might read CLAUDE.md, miss AGENTS.md, and never learn the mode-selection framework.
- **F4** — persona mode declarations inconsistent. Took me a minute to realize code-reviewer and grep-verifier aren't multi-mode — they just don't say so explicitly.

Everything else is polish.

---

## Recommended Fix Order (if operator approves)

1. **F1** — add AGENTS.md to the CLAUDE.md asset table + reading order (1-line edit).
2. **F4** — add Mode section to each persona (4 small edits).
3. **F2** — extend dependency graph in architecture.md (2-line append).
4. **F3** — tighten Karpathy §8.3 enforcement mapping (1-line swap).
5. **F10** — decide fate of DISCOVERY.md (move / delete / keep).
6. **F5, F6, F7, F8** — polish at operator's discretion. Skip any that don't pay off.

All of the above can be done in a single follow-up commit: `fix: apply MODE 3 verification findings`.

**F9 is superseded** (grep confirmed no body-level MG echo in commands).

---

## Final Verdict

**PROVISIONALLY CLEAN PENDING OPERATOR REVIEW.**

- Zero R8 body-level leakage.
- 100% provenance header coverage.
- All 8 teaching sections present.
- All four future-integration hook points documented.
- Karpathy synthesis is real enforcement mapping, not generic advice.
- Cold-start reading chain is navigable end-to-end.
- Ten findings surfaced, all with proposed fixes; two structural (F1, F4) worth applying before shipping to a client, rest are polish.

The stack is ready for a client install trial once F1 and F4 are applied. Everything else is refinement.
