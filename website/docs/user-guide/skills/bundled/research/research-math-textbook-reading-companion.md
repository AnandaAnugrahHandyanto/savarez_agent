---
title: "Math Textbook Reading Companion"
sidebar_label: "Math Textbook Reading Companion"
description: "Use when the user is reading a math textbook, lecture note, or paper and asks why a definition, theorem, proof, example, exercise, section, or chapter appear..."
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Math Textbook Reading Companion

Use when the user is reading a math textbook, lecture note, or paper and asks why a definition, theorem, proof, example, exercise, section, or chapter appears in its current form. Reconstruct the mathematical pressure, failed naive routes, exposition architecture, technique genealogy, source-grounded motivation, delayed payoffs, and why the material is interesting.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/research/math-textbook-reading-companion` |
| Version | `1.0.0` |
| Author | Hermes Agent |
| License | MIT |
| Tags | `math`, `textbooks`, `exposition`, `motivation`, `proofs`, `definitions`, `examples`, `reading` |
| Related skills | `math-natural-explainer`, [`ocr-and-documents`](/docs/user-guide/skills/bundled/productivity/productivity-ocr-and-documents) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Math Textbook Reading Companion

## Overview

Use this skill as a mathematical reading archaeologist. The goal is not to summarize a textbook passage, but to reconstruct why the passage has its shape: why a definition is introduced, what problem it solves, why a theorem matters, why an example is shown, why a proof uses its chosen strategy, what earlier technique is being imitated/generalized/specialized, how the section fits into the chapter, and why the phenomenon is interesting.

The default target feeling is:

> "Now I see what pressure made the author introduce this object/result/example/proof, and I can anticipate why the next part of the book needs it."

This skill is related to `math-natural-explainer`, but is more specifically for reading actual source material and explaining exposition architecture. If the user provides a PDF, image, passage, table of contents, or page range, use the source as primary evidence.

## When To Use

Use this skill when the user asks questions like:

- "Why is this definition made this way?"
- "What problem is this definition trying to solve?"
- "Why is this theorem important?"
- "Why does the book introduce this here?"
- "What is this example supposed to show?"
- "Why does the proof use this strategy?"
- "Where did this motivation come from?"
- "Is this technique imitating/generalizing/specializing something?"
- "Why is this result interesting?"
- "Explain the flow of this section/chapter."
- "Read this passage and tell me what the author is preparing for."

Do not require the user to name a mode. Infer the relevant lens automatically from the question and the source.

Do not use this skill for a pure computation request where no explanatory/motivational reading is needed, unless the user asks why the computation is set up in a particular way.

## Core Contract

For every substantial answer, distinguish:

1. **Surface content**: what the text literally states.
2. **Problem pressure**: what need, obstruction, failed route, missing language, or repeated pattern creates this item.
3. **Functional role**: what job this item performs in the exposition or proof machinery.
4. **Placement reason**: why it appears here rather than earlier or later.
5. **Payoff**: what it immediately enables and what delayed payoff it has later.
6. **Technique genealogy**: what simpler technique it imitates, what broader theory it previews, or what concrete case it abstracts.
7. **Interest**: why the phenomenon is surprising, useful, unifying, computable, or theory-opening.

Never stop at "this is useful" or "this is natural." State the structural reason.

## Source-First Protocol

When the user supplies a source file, passage, screenshot, table of contents, or page range:

1. Inspect the target item.
2. Inspect enough surrounding material to answer the flow question:
   - immediately preceding definitions/results/examples;
   - transition sentences before the target;
   - immediately following uses, corollaries, examples, exercises, or chapter transitions;
   - table of contents if the question is about a whole chapter/section.
3. Use the source as primary evidence.
4. Separate three claim types:
   - **Text-grounded**: explicitly stated or directly visible in the source.
   - **Expository inference**: a reasonable reading of how the text is functioning.
   - **External/background context**: standard mathematical context not stated in the source.
5. Do not invent authorial intent. Prefer wording like:
   - "This passage functions as..."
   - "One reason to place it here is..."
   - "The surrounding text suggests that..."
   - "A likely delayed payoff is..."

If the source is a PDF or scan, use document extraction/OCR tools as needed. If extraction is partial, say what pages/passages were inspected and avoid overclaiming.

## Functional Unit Taxonomy

When reading a passage, break it into functional units rather than merely paragraphs:

- definition;
- lemma;
- proposition/theorem/corollary;
- example;
- counterexample;
- remark/warning;
- proof construction;
- proof trick;
- computation;
- transition sentence;
- exercise;
- notation setup;
- convention/identification;
- historical aside;
- delayed-payoff seed.

For each major unit, assign a role name. Examples:

- "language-building definition";
- "weak substitute before the full theorem";
- "prototype example";
- "boundary/counterexample";
- "technical lemma for cancellation";
- "compression step hiding routine verification";
- "bridge from concrete computation to abstract structure";
- "warning that the naive analogy fails";
- "delayed payoff for the next chapter."

Role names make the exposition architecture visible.

## Universal Reading Pipeline

For a target definition/theorem/example/proof/section, use this pipeline:

```text
Surface item
-> prior context and reader state
-> local problem pressure
-> naive reader expectation
-> precise failure or insufficiency
-> obstruction exposed
-> author's chosen move
-> functional role of the move
-> immediate payoff
-> delayed payoff
-> technique genealogy
-> why interesting
```

Compress this pipeline for short answers, but preserve the causal chain from pressure to move to payoff.

## Proof-Pressure-First Mode For Definitions And Axiom Packages

When explaining a definition, especially a package of hypotheses such as "Dedekind domain", "Noetherian", "regular", "smooth", "compact", "complete", "exact", or any definition with several conditions, prefer a **proof-pressure-first** explanation when the surrounding text supports it.

Do **not** default to this weaker pattern:

```text
Here is the definition.
Condition (1) is used here.
Condition (2) is used there.
Condition (3) is used later.
```

That often makes the definition feel arbitrary. Instead, reconstruct the upstream mathematical need:

```text
We want theorem/operation/viewpoint T.
To prove or make T work, we first need mechanism M.
Trying to build M creates obstacle O1, O2, O3.
Obstacle O1 forces condition C1.
Obstacle O2 forces condition C2.
Obstacle O3 forces condition C3.
Therefore the definition packages exactly C1, C2, C3.
Once the package is in place, T follows by the now-enabled mechanism.
```

Use this mode when the definition is best understood as a bundle of conditions engineered to make a later theorem true. The answer should make the definition look **forced by the desired theorem**, not merely convenient.

### Standard output shape for proof-pressure-first definitions

```text
1. Desired theorem or arithmetic/geometric operation
2. Mechanism needed to make it work
3. First obstruction encountered in the proof
4. Condition that removes the first obstruction
5. Second obstruction encountered in the proof
6. Condition that removes the second obstruction
7. Third/further obstructions and their conditions
8. The resulting definition as the exact package of these requirements
9. Payoff: what theorem now becomes provable
10. Moral: the definition is not arbitrary; it is the proof's requirement list
```

### Example schema

For Dedekind domains, do not begin by saying only "A Dedekind domain is noetherian, integrally closed, and dimension one." A more explanatory route is:

```text
We want unique factorization of ideals.
For uniqueness, we need cancellation of ideal products.
Cancellation follows if nonzero ideals are invertible.
To prove invertibility, the proof needs:
- maximal counterexamples / finite generation -> noetherian;
- prime ideals comparable with maximal ideals -> every nonzero prime is maximal;
- determinant trick to force a non-ring element back into the ring -> integrally closed.
Thus the Dedekind conditions are the exact obstacles removed by the invertibility proof.
```

This is an example pattern, not a script to force onto every topic. Always adapt to the source text and the actual proof architecture.

For a compact reusable version with a Dedekind-domain worked schema, see `references/proof-pressure-first-definitions.md`.

## Lens 1: Definition Archaeology

Use this lens when the target is a definition, condition, notation, construction, category of objects, equivalence relation, invariant, or property.

Answer:

```text
Problem the definition is trying to make speakable:
Naive definition one might try first:
Why the naive definition is too weak/strong/non-functorial/non-canonical:
What each condition prevents or preserves:
Examples that force the boundary:
Non-examples or boundary cases:
What theorem or operation becomes possible after the definition:
```

For each defining condition, say whether it encodes:

- existence;
- uniqueness;
- composability;
- locality;
- gluing;
- invertibility;
- exactness;
- finiteness;
- compactness;
- separation;
- functoriality;
- invariance under equivalence/isomorphism;
- computability;
- independence of choices.

A useful slogan:

```text
This definition is the minimal structure needed to make [operation/viewpoint/theorem] behave coherently.
```

Only use this slogan after naming the operation/viewpoint/theorem.

## Lens 2: Theorem Importance

Use this lens when the target is a theorem, proposition, lemma, corollary, or named result.

Classify the theorem's role:

- **Bottleneck remover**: removes an obstruction that blocked the development.
- **Structure theorem**: turns messy objects into standard forms.
- **Existence theorem**: guarantees an object exists without arbitrary choices.
- **Uniqueness/canonicity theorem**: makes constructions independent of choices.
- **Computability theorem**: turns abstract data into calculable data.
- **Translation theorem**: converts geometry to algebra, algebra to topology, local to global, or global to local.
- **Classification theorem**: organizes all examples of a type.
- **Bridge theorem**: connects the current chapter to later theory.

Answer:

```text
What bottleneck this theorem removes:
What previous tools it activates:
Which hypotheses do real work:
What would fail without the theorem:
What immediate corollaries or examples it enables:
What later chapter/section likely depends on it:
Why this theorem is interesting rather than merely true:
```

If the theorem seems minor, explain its technical role rather than overstating it.

## Lens 3: Example Function

Use this lens when the target is an example, computation, counterexample, special case, exercise, diagram, or table.

First classify the example:

| Example type | Function |
|---|---|
| Prototype | The simplest model of a new definition. |
| Boundary case | Shows why a condition is sharp. |
| Counterexample | Breaks a naive expectation. |
| Warning | Prevents a misleading analogy. |
| Computational model | Shows how an abstract theorem becomes calculable. |
| Motivating example | Creates pressure for the next definition or theorem. |
| Special-case preview | Shows the easy version before the general proof. |
| Generalization seed | A concrete pattern that later becomes abstract theory. |
| Delayed-payoff example | Introduced now for use several sections later. |

Then answer:

```text
What the example literally computes/shows:
Which definition/theorem it tests:
What naive belief it supports or destroys:
What feature survives in the general case:
What feature is accidental to the example:
What the reader should learn to look for next:
```

Do not treat examples as decorative. Explain what they are doing in the exposition.

## Lens 4: Proof Strategy Reconstruction

Use this lens when the target is a proof or proof step.

Do not merely reproduce the proof. Reconstruct how one could have found the strategy.

Use:

```text
Goal:
Direct route a reader would try:
Why it is tempting:
Precise point where it fails:
Obstruction exposed:
Viewpoint shift:
Key construction/tool:
What this construction buys:
Verification burden left over:
Conclusion:
```

For each auxiliary object, diagram, quotient, localization, basis, cover, kernel, cokernel, completion, closure, compactification, or universal map, say:

```text
Tactical target:
Obstruction it answers:
Why this is the economical construction:
What property must be checked:
```

Separate at the end:

- real mathematical idea;
- tactical construction;
- technical mechanism;
- routine verification.

## Lens 5: Expository Flow Analysis

Use this lens when the user asks about a section, chapter, or book-level flow.

Distinguish:

1. **Logical dependency order**: what must be proved before what.
2. **Pedagogical absorption order**: what is easier for the reader to absorb first.
3. **Narrative pressure order**: what question is made inevitable by the previous passage.

Reconstruct:

```text
Prior reader state
-> current local goal
-> missing tool/language/obstruction
-> examples or definitions that expose the obstruction
-> lemmas that build proof machinery
-> theorem that pays off the machinery
-> transition pressure into the next section
```

For each major placement choice, answer:

```text
Why here:
What this prepares:
What would be confusing if earlier:
What would be unmotivated or impossible if later:
How it changes the reader's viewpoint:
Immediate payoff:
Delayed payoff:
```

When possible, produce a compact dependency/flow map.

## Lens 6: Technique Genealogy

Use this lens when the user asks what a technique is imitating, generalizing, specializing, or concretizing.

Classify the technique's ancestry:

- generalization of a familiar concrete trick;
- specialization of a broad theory;
- categorification or functorial version of an element argument;
- local version of a global question;
- global gluing of local data;
- replacement of choices by a universal property;
- replacement of equality by canonical/natural isomorphism;
- passage to a quotient to kill irrelevant differences;
- localization/completion to allow controlled denominators or limits;
- use of symmetry/group action to identify equivalent cases;
- use of an invariant to compress complex structure.

Answer:

```text
Simpler ancestor technique:
What changes in the current setting:
Why the old technique no longer works literally:
What is preserved in the generalization:
What new obstruction appears:
Why the adapted technique is the right fit:
```

## Lens 7: Interestingness Analysis

Use this lens when the user asks why something is interesting, beautiful, surprising, or worth caring about.

A result or construction is often interesting because it:

- contradicts a naive expectation;
- rescues a failed theorem at a different level;
- exposes a hidden invariant;
- makes an abstract object computable;
- unifies several examples;
- reveals local-global tension;
- shows where a hypothesis is sharp;
- bridges two areas or viewpoints;
- opens a new class of questions;
- turns non-canonical choices into canonical structure;
- explains why a familiar phenomenon was not accidental.

Do not say only "it is important because it is used later." Say what kind of mathematical power it gives later.

## Default Output Shapes

### For a definition

Default shape:

```text
1. What the definition says
2. What problem it is trying to solve
3. The naive definition and why it fails
4. Role of each condition
5. Examples / boundary cases
6. What the definition enables later
7. One-line moral
```

When the definition is an axiom package or hypothesis bundle, prefer the proof-pressure-first shape:

```text
1. Desired theorem/operation the text is trying to make possible
2. Mechanism needed before that theorem can be proved
3. Obstacles encountered while building the mechanism
4. Condition forced by each obstacle
5. The definition as the collected obstacle-removers
6. Immediate theorem unlocked by the definition
7. One-line moral: the definition is the proof's requirement list
```

### For a theorem

```text
1. The theorem's job in the chapter
2. Bottleneck it removes
3. Why the hypotheses are shaped this way
4. Proof strategy and obstruction
5. Immediate and delayed payoff
6. Why it is interesting
7. One-line moral
```

### For an example

```text
1. What the example shows on the surface
2. Example type and function
3. Which naive expectation it confirms or breaks
4. What general pattern it previews
5. What to remember from it
```

### For a proof

```text
1. Goal and pressure
2. Naive route and failure
3. Obstruction
4. Chosen strategy and why it fits
5. Key constructions
6. Real idea vs mechanics
7. Reproduce-it skeleton
```

### For a section/chapter flow

```text
1. Previous context
2. Local goal of the section
3. Flow map of definitions/lemmas/examples/theorems
4. Why each major item appears here
5. Immediate payoff
6. Delayed payoff
7. One-line narrative of the section
```

## Multi-Agent Pattern For Large Reading Tasks

For long chapters, dense PDFs, or broad questions, consider splitting work across subagents or internal passes:

1. **Source Cartographer**
   - Extract table of contents, section boundaries, definitions, theorems, examples, exercises, and transition sentences.
   - Return a source-grounded map with page/section references.

2. **Motivation Analyst**
   - For each major item, reconstruct problem pressure, naive route, obstruction, and functional role.

3. **Proof Strategist**
   - Analyze proof spines, auxiliary constructions, technique genealogy, and real idea vs mechanics.

4. **Skeptic / Source Verifier**
   - Check which claims are directly supported by the source, which are interpretive, and which require external background.

Synthesize the outputs into a coherent reader-facing explanation. Do not expose all subagent scaffolding unless useful.

## Source Discipline And Copyright-Safe Behavior

- Quote only short snippets when needed.
- Prefer paraphrase and analysis over long reproduction of copyrighted text.
- If the user supplies the source, you may analyze it, summarize it, and cite small fragments.
- Do not fabricate page contents, authorial intent, or historical claims.
- If historical motivation matters and no source is available, mark it as heuristic or request permission to use external references.

### Provenance and Tool Transparency

For source-grounded textbook explanations, especially when the user asks for detailed motivation/proof flow:

- Keep a mental ledger of what was inspected: target pages/sections, surrounding pages, and any earlier propositions or exercises used to explain the proof.
- If the answer introduces standard terminology not used verbatim in the source (e.g. "colon ideal", "fractional ideal", "determinant trick"), label it as background language used to explain the source's argument rather than as text-grounded wording.
- When asked whether external sources or subagents were used, answer directly and distinguish: supplied source material, internal skills/workflow guidance, tool extraction/OCR, subagents, web/external references, and the model's general mathematical background.
- For long explanatory answers, consider adding a short "source/provenance" note when it would prevent ambiguity: what was directly in the source, what is expository inference, and what is standard background context.

## Common Pitfalls

1. **Summary instead of archaeology.** Listing what the text says is not enough; explain why the text moves that way.
2. **Fake naturalness.** Do not call a move natural without naming the structural pressure.
3. **Authorial mind-reading.** Infer expository function from textual evidence; do not claim private intent.
4. **Example flattening.** Do not treat examples as mere computations; classify what they are demonstrating.
5. **Proof transcript.** Do not merely restate proof steps; reconstruct the strategy and failed alternatives.
6. **Hypothesis amnesia.** Track where assumptions start doing work.
7. **Overgeneralization.** Do not claim a technique is the only possible route unless justified.
8. **Prerequisite dumping.** Give only the background needed to explain the target passage.
9. **Delayed-payoff blindness.** Look ahead enough to see what the current item enables.
10. **Ignoring the user's language.** Match the user's language; keep standard mathematical notation as needed.
11. **Downstream-only definition explanation.** Avoid explaining a multi-condition definition only by listing where each condition is later used. When possible, move upstream: identify the desired theorem, the mechanism needed to prove it, the obstacles that arise, and how each condition removes one obstacle. This makes the definition feel forced rather than arbitrary.

## Verification Checklist

Before answering, check:

- [ ] Did I inspect the supplied source or clearly state when source access was unavailable?
- [ ] Did I identify the target item's functional role?
- [ ] Did I state the problem pressure or missing tool/language?
- [ ] Did I reconstruct a naive expectation and its failure when useful?
- [ ] Did I explain why the item is placed here?
- [ ] Did I identify immediate and delayed payoff?
- [ ] Did I distinguish text-grounded claims from interpretation?
- [ ] Did I explain any technique genealogy if the proof/construction uses a recognizable method?
- [ ] Did I say why the item is interesting in a mathematically specific way?
- [ ] Did I end with a concise moral or reading takeaway?
