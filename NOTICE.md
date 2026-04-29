# NOTICE

**Motion Granted Citation Database**
Copyright (c) 2026 Porter Tanner. Licensed under the MIT License — see [`LICENSE`](LICENSE) for the complete terms.

This NOTICE file provides third-party attributions, a product-positioning statement, and cross-references to the repository's legal and security documents. **No statement in this file waives, modifies, or supersedes any term of the `LICENSE` file or of `binding/v7.2.md`.** Where this file and `LICENSE` appear to conflict, `LICENSE` governs.

---

## 1. Third-Party Material — tanner-stack Harness

This repository's operator harness — `.claude/` (sub-agents, rules, commands, workflows), `skills/`, `docs/` (harness documentation), `personas/`, `prompts/`, and the root files `AGENTS.md`, `VERIFICATION.md`, `LEARNINGS.md`, `BACKLOG.md`, and the project-CLAUDE-md template — is flattened from the **tanner-stack** harness (approximately v0.3.1, per `docs/# Tanner-Stack Prompting Manual.txt:7` and `docs/build-notes/adversarial-cleanup-2026-04-22.md:165`).

Provenance notes:
- `personas/architect.md:2` carries the header "Extracted from: tanner-stack extraction session (self-generated)" with genericization date `2026-04-21` and operator `Porter Tanner`.
- `.claude/agents/grep-verifier.md:2` carries "Adapted from: personas/grep-verifier.md (tanner-stack v0.2.0)".
- `CHANGELOG.md:157` records the initial flatten commit `cf68d23` (2026-04-22 02:34:53) — "Initial: tanner-stack flattened, v7.2 promoted to binding/, source material archived".
- `CHANGELOG.md:161` confirms the flatten operation: the harness was brought into this repo from an external tanner-stack source and placed at the repo root alongside `binding/v7.2.md`.

Because tanner-stack was authored by the same operator (Porter Tanner) who is the copyright holder of this work, no separate third-party license attaches to the flattened harness files. The MIT license in `LICENSE` covers them. This attribution is recorded here for provenance, not for license compliance.

**MG-specific extensions to the harness** — `AGENT-DISCIPLINE.md`, the `binding/` directory, and any `.claude/rules/*.md` files created for this repo — are original work under the same MIT license. `AGENT-DISCIPLINE.md:168` explicitly states the relationship: "tanner-stack discipline conventions inherited via flattened harness; this AGENT-DISCIPLINE.md extends those for MG-specific failure modes."

---

## 2. Archive Material

Files under `archive/` are historical V1-era source material preserved for provenance (see `CLAUDE.md` §2 and `CHANGELOG.md:161`). They are **not binding**. The flatten commit explicitly moved them out of the active surface and into `archive/` to establish `binding/v7.2.md` as the single ratified architectural authority. Do not modify `archive/` files; if content needs correction, correct it in a new file outside `archive/` and let the archived original stand as provenance (`CLAUDE.md` §8).

Archive provenance includes: V1-era specifications, the v7.1 and v7.2 Pre-Send Audit HTML documents (`archive/Codebase Doc/6 - Pre-Send Audit v7.1.html`, `archive/Codebase Doc/6- Pre-Send Audit v7.2.html`), and the TAX-15to16 delta report (recorded in `CHANGELOG.md:163`).

---

## 3. Product Positioning — Research Tool, Not Legal Advice

The Motion Granted Citation Database is a **research acceleration tool**, not a legal-advice product and not a substitute for attorney judgment. This positioning is inherited verbatim from the Pre-Send Audit v7.2 recommendation at `archive/Codebase Doc/6- Pre-Send Audit v7.2.html:368`:

> "The citator is a research acceleration tool, not a substitute for professional legal judgment. All negative treatment flags include the model's reasoning and proof text for attorney verification."

That sentence is the only disclaimer language this file asserts as approved for product surfaces. It is the Pre-Send Audit's **recommendation** for cofounder review — one of three design decisions the audit surfaced at `archive/Codebase Doc/6- Pre-Send Audit v7.2.html:435` (confidence floor, "research tool" positioning, cofounder input request). Whether and how this sentence appears in the MCP response envelope, user interfaces, or other product surfaces is **cofounder-ratification-pending**; see `SECURITY.md` §2 and §11 for the relevant open items, and `BACKLOG.md` for how this flows into the Clay queue.

The schema-level enforcement of "research tool" positioning — requirement that every negative-treatment flag carry `reasoning` + `proof_text` for attorney verification — is inherited by `binding/v7.2.md` §12 (Cardinal Sin, L893-917) and the STOP-gate discipline at `binding/v7.2.md` §9 (L608-623). Those schema requirements are binding and enforced fail-closed. The product-surface disclaimer language around them is not yet ratified and MUST NOT be invented.

---

## 4. Legal Scope and Disclaimers

- **No warranty.** The software is provided "AS IS" under `LICENSE` §15-21 (MIT standard disclaimer). Nothing in this NOTICE file modifies that disclaimer.
- **No legal advice.** Neither this file nor the repository constitutes legal advice. Operators, downstream integrators, and end users are responsible for their own legal compliance, including bar-admission and practice-of-law questions surfaced by the Pre-Send Audit at `archive/Codebase Doc/6- Pre-Send Audit v7.2.html:361`.
- **No waiver.** Nothing in this file waives any right or obligation under `LICENSE`, `binding/v7.2.md`, or any other controlling document. If a statement here appears to conflict with a binding document, the binding document governs and this file should be corrected.
- **Retention disclaimers are counsel-pending.** Retention-policy language per `binding/v7.2.md` §26 is an open Clay-queue item (§24 blocker S-5 cross-ref; see `BACKLOG.md` and `SECURITY.md` §10). This file does not assert retention periods, destruction schedules, or privilege-waiver interpretations. Those require legal counsel sign-off before any product surface communicates them.

---

## 5. Trademarks and Names

- "Motion Granted" is used as the product name. No claim is made about trademark registration status in this file.
- "tanner-stack" is used to refer to the flattened harness origin. No claim is made about trademark registration status in this file.
- Third-party product names that may appear in `archive/` material (e.g., CourtListener, eyecite, pgvector, vLLM, Paxton AI, Descrybe.ai — all enumerated at `archive/Codebase Doc/6- Pre-Send Audit v7.2.html:455`) are the property of their respective owners and are referenced for technical-comparison purposes only.

---

## 6. Cross-References

| Document | Purpose | Binding? |
|----------|---------|----------|
| [`LICENSE`](LICENSE) | MIT License — full legal terms | Yes |
| [`binding/v7.2.md`](binding/v7.2.md) | Single ratified architectural authority | Yes |
| [`SECURITY.md`](SECURITY.md) | Schema guardrails, threat model, reporting channel | Partially (§4 guardrails cite v7.2; §11 reporting channel is operator-decision) |
| [`CHANGELOG.md`](CHANGELOG.md) | Commit history and provenance | Descriptive, not binding |
| [`README.md`](README.md) | Entry point and repo orientation | Descriptive |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Operator workflow and discipline | Operational |
| [`AGENT-DISCIPLINE.md`](AGENT-DISCIPLINE.md) | MG-specific agent-failure-mode guardrails | Operational |
| [`BACKLOG.md`](BACKLOG.md) | Open Clay-queue items + tier ladder | Operational |

---

## 7. Operator and Cofounder-Pending Items

This NOTICE file is **scaffold-ready, not counsel-ratified**. The following items are flagged for cofounder / counsel review before any public or customer-facing release:

1. **MCP-envelope disclaimer wording** — whether the L368 sentence appears verbatim in the MCP response, whether it is paraphrased, and whether it is accompanied by additional hedge language. Cofounder-pending per Pre-Send Audit `:435`.
2. **Trademark registration status** — none is asserted here; status to be confirmed or added before any marketing surface references "Motion Granted" as a registered mark.
3. **Retention-policy disclosure wording** — counsel-pending per §26; no language is asserted in this file beyond "counsel-pending."
4. **Third-party attribution of tanner-stack** — if tanner-stack is later separated under a non-MIT license or assigned to a different copyright holder, this file must be updated to reflect that. As of 2026-04-23, the harness is same-operator-authored and MIT-covered.
5. **Jurisdiction-specific practice-of-law disclaimers** — the Pre-Send Audit `:361` flags the practice-of-law question as a cofounder concern. No jurisdiction-specific language is asserted here.

Items 1-5 are listed in `DOC-TODOS.md` (if present) and flow into `BACKLOG.md` as operator-facing open items.

---

*This NOTICE file is not a LICENSE. For the complete legal grant, see [`LICENSE`](LICENSE). For schema-level security guarantees and threat-model detail, see [`SECURITY.md`](SECURITY.md). For architectural authority, see [`binding/v7.2.md`](binding/v7.2.md).*
