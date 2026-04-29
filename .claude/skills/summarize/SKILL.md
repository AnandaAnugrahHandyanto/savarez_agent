<!--
Written fresh: v0.3.1 cleanup pass (closes dry-run trace #15 from docs/build-notes/adversarial-cleanup-2026-04-22.md)
Original purpose: Document compression with signal preservation — produces a length-targeted summary retaining facts, decisions, and action items.
Created: 2026-04-22
Operator: Porter Tanner
-->

---
name: summarize
description: MUST BE USED when user says "summarize this document", "compress this", "give me the short version", "tldr this", or pastes long content and asks for a condensed version. Produces length-targeted summary preserving facts, decisions, action items, numerical data, and named entities while dropping rhetorical scaffolding. DO NOT USE for debugging pipeline data loss or information loss within code execution flows — that is the `lossy` skill. DO NOT USE to silence Claude or reduce response verbosity — that is the `shutup` skill.
argument-hint: "[target length: e.g. 'one paragraph', '3 bullets', 'one page'; omit to ask]"
allowed-tools: Read Grep Glob
---

# Summarize — Document Compression with Signal Preservation

Produce a length-targeted summary of document content. Preserve signal, drop scaffolding.

**Target length / source**: $ARGUMENTS

---

## The Problem This Solves

Long documents (meeting notes, PR descriptions, design docs, research reports, transcripts) have a signal-to-noise ratio that drops as length increases. A summary is not "shorter version of the same thing" — it is signal extracted and scaffolding dropped.

The `lossy` skill is about *debugging* silent data loss in pipelines. The `shutup` skill is about silencing Claude for the rest of the session. Neither compresses a document on request. `summarize` is the compressor.

---

## Step 1: Establish the target length

If the user named a target length, use it:
- "one paragraph" → ~80 words
- "three bullets" → 3 bullet points, each ≤ 20 words
- "one page" → ~400 words
- "tldr" → 1–3 sentences
- Explicit word or line count → respect it

**If no target length is given**, ask:
> "What target length? A paragraph / 3 bullets / one page / TLDR line?"

Do not guess — compression intensity drives what gets cut.

## Step 2: Read the source

Read the full source document. Do not compress from the first paragraph alone. Note:
- Named entities (people, places, systems, products, metrics)
- Numerical data (dates, sizes, percentages, counts, thresholds)
- Decisions made (and by whom)
- Action items (and owners, if stated)
- Key facts / claims (and their evidence if provided)
- Structural landmarks (sections, lists, tables)

If the source is too long to read in one pass, chunk it and track the above per chunk before compressing.

## Step 3: Extract the signal

For every sentence or paragraph in the source, classify:

- **PRESERVE**: a fact, decision, action item, numerical value, named entity, or novel claim
- **DROP**: rhetorical scaffolding (meta-commentary on the document, repeated framing, prose connecting two preserved facts), example redundancy, parenthetical asides

The target length sets the compression ratio. A one-paragraph summary drops ~90% of an 800-word source. A three-bullet summary drops ~95%. TLDR drops 99%.

## Step 4: Write the compressed version

Structure matches the requested length:
- **Paragraph**: prose, 60–100 words, no bullets.
- **N bullets**: exactly N bullets, each self-contained, parallel structure.
- **Page**: sections mirroring the source's natural divisions, scaled down.
- **TLDR**: 1–3 sentences, no structure.

Preserve fidelity on:
- Names (never summarize to "some people" when specific people were named).
- Numbers (round only with explicit note; never drop a figure the source treated as load-bearing).
- Decisions (always include verbatim the decision made, not a paraphrase).
- Action items (include owner and deadline if stated).

## Step 5: Flag compression limits

If the source is too dense to compress to the requested target without losing material signal, **state it explicitly**:

> "At the requested target of <length>, the following load-bearing facts had to be cut: [list]. Want a longer target, or should I keep them and exceed the length?"

Do not silently drop material signal to hit a length budget.

---

## Output Format

```
SUMMARY ({target length})

{compressed body matching the structure: paragraph / bullets / sections / TLDR}

(optional) COMPRESSION NOTES
  - Dropped at this length: {material items cut}
  - Need longer to retain: {what would come back}
```

If compression was clean with no material loss, omit the COMPRESSION NOTES section entirely.

---

## Rules

1. **Establish target length before compressing.** If not given, ask.
2. **Read the full source first.** No summarizing from the first paragraph.
3. **Preserve facts, decisions, action items, numbers, names.** These are the signal.
4. **Drop rhetorical scaffolding, not evidence.** Trim the framing, keep the claims.
5. **Flag compression limits explicitly.** Never silently drop material signal to fit a budget.
6. **Structure matches the requested length.** Paragraph asks get prose, bullet asks get bullets, page asks get sections.
