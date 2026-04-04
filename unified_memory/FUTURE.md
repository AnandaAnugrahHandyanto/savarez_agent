# Unified Memory — Future Work & Nice-to-Haves

Items identified during development that would improve the system but are not
required for the initial PR. Organized by priority and source.

## High Priority (measurable benchmark or production impact)

### 1. Meta-Engram Extraction (from PLUR)
**What:** LLM pipeline that distills individual facts into cross-domain structural
principles. Extracts relational triples → clusters by structural similarity →
aligns to cognitive frames → formulates falsifiable principles → organizes into
hierarchy.

**Why:** We store bottom-up facts but never synthesize them into transferable
principles. "API retry uses exponential backoff" + "DB reconnect uses exponential
backoff" → principle: "transient failures should use exponential backoff."
The falsifiability filter is key — it gates on whether a principle is specific
enough to be wrong (rejects platitudes).

**Impact:** Would improve cross_reference benchmarks where answers require
combining multiple facts. Currently 93.3%, could potentially reach 100%.

**Source:** PLUR (plur-ai/plur) — `packages/core/src/meta/pipeline.ts`

### 2. Bi-Temporal Validity Windows (from PLUR)
**What:** `valid_from` and `valid_until` timestamps on facts. "API endpoint was
X from 2024-01 until 2025-06." Facts automatically suppressed at retrieval time
when outside their validity window.

**Why:** Currently, superseded facts are marked as such but we don't model
"this was true from date A to date B." Temporal queries like "what was the API
endpoint last January?" would return the correct historical answer.

**Impact:** Would improve temporal_decay scenarios and prevent stale-fact
hallucination. Also enables historical queries that our current system can't
answer.

**Source:** PLUR — `schemas/engram.ts` temporal field

### 3. Training Data Export (from Icarus-Daedalus)
**What:** Export high-quality memory interactions as fine-tuning pairs. Three
pair types:
- Task completion: query → recalled facts
- Review-correction: original answer + feedback → improved answer
- Cross-context: memory from context A used successfully in context B

**Why:** We already have Q-values that track which memories were useful.
Combining Q-value signals with training data export = self-improving agents.
High-Q memories become training data; the fine-tuned model mirrors the agent's
best retrieval patterns at lower cost.

**How to adapt:** Export facts where `q_value > 0.7` and `access_count > 3` as
training pairs. The store/recall pattern gives natural input→output pairs.
Session reward tracking already identifies store-after-recall patterns.

**Source:** Icarus-Daedalus — `export-training.py`

### 4. Consider Pool / Soft Injection (from PLUR, DIP-0019)
**What:** Beyond direct hot-facts injection, a "consider" pool of slightly-below-
threshold facts passed to the agent at lower priority. Injected in a separate
section like `[ALSO CONSIDER]` with smaller token budget.

**Why:** Currently hot-facts injection is binary — either a fact is injected or
not. A consider pool gives the model awareness of borderline-relevant facts
without overwhelming the directive space. Particularly valuable when switching
topics mid-conversation.

**Impact:** Production UX improvement. Would help with scope_lifecycle scenarios
where facts from adjacent scopes might be relevant.

**Source:** PLUR — `inject.ts` DIP-0019 consider pool

### 5. Aggregation-Mode Query Detection (from PLUR)
**What:** Detect counting/totaling queries ("how many times did I...", "list all
my...") and switch from top-K precision mode to exhaustive recall mode with 5x
wider retrieval net + specialized query expansion.

**Why:** Our intent classifier has 6 types but no aggregation detection. When
asked "how many databases do we use?" the system returns the most relevant
database fact, not all of them.

**Impact:** Would create a new benchmark category and improve recall metrics.
PLUR claims 86.7% on LongMemEval with this.

**Source:** PLUR — `hybrid-search.ts` aggregation detection

## Medium Priority (architectural improvements)

### 6. Emotional Weight / Salience Multiplier (from PLUR)
**What:** Facts have an emotional_weight (1-10) that scales retrieval score.
Surprising, important, or high-stakes facts get higher salience.

**Why:** Our importance scoring is static (set at store time). Salience could
be dynamically computed from Q-value signals + access patterns — facts that
consistently generate reward are more "salient."

**Source:** PLUR — `schemas/engram.ts` emotional_weight field

### 7. Polarity Splitting at Injection (from PLUR)
**What:** Separate "DO" directives from "DON'T" constraints in the hot-facts
injection block. The model sees them as distinct sections.

**Why:** Our C-type (constraint) facts are mixed with D-type (decision) and
V-type (value) in injection. Splitting by polarity could reduce constraint-
forgetting in long contexts.

**Source:** PLUR — `polarity.ts` + `inject.ts`

### 8. Hit/Miss Usage Tracking (from PLUR)
**What:** Track "injected N times, used M times" per fact. A fact injected 50
times but never referenced by the model is wasting tokens.

**Why:** Our IPS debiasing handles propensity but doesn't track injection
specifically. Explicit hit/miss at the fact level gives cleaner signal for
LinUCB to learn which facts to inject vs recall-only.

**Source:** PLUR — `quality.ts` usage metrics

### 9. Louvain Community Detection (from Ori-Mnemos)
**What:** Cluster the Hebbian link graph into communities using the Louvain
algorithm. Cross-community queries trigger different traversal behavior.

**Why:** Would improve PPR exploration by understanding graph structure —
explore() could prioritize cross-community bridges for novel associations.

**Source:** Ori-Mnemos — community detection in graph walking

### 10. Knowledge Anchors (from PLUR)
**What:** Tie facts to specific file paths + code snippets. Anchor boost:
overlap between task words and anchor snippets increases retrieval score.

**Why:** For code-related conversations, knowing that "use blue-green deploy"
is anchored to `deploy/config.yaml:45` gives grounding and verification.

**Source:** PLUR — anchor fields + scoring boost

## Lower Priority (nice-to-haves, post-release)

### 11. Recursive Sub-Question Exploration (from Ori-Mnemos)
**What:** LLM-driven sub-question generation during explore(). Identifies gaps
in retrieved results, generates 1-3 sub-questions, recursively retrieves.

**Why:** Would improve cross_reference scenarios that require chain reasoning.
Needs LLM call so adds latency and cost.

**Source:** Ori-Mnemos — `explore.ts` Phase 3

### 12. Exchange/Marketplace Fitness (from PLUR)
**What:** Fitness scoring for shared facts: quality × 0.40 + diversity × 0.25 +
adoption × 0.20 + age × 0.10 + (1-contradiction) × 0.05.

**Why:** Only relevant if we ever do cross-agent or cross-user fact sharing.
Pre-built scoring formula is useful.

**Source:** PLUR — `quality.ts` exchange fitness

### 13. Platitude Filter (from PLUR)
**What:** Pattern-match to reject overly generic facts before storage. "Always
write clean code" → rejected. "Use black formatter with line-length 88" → kept.

**Why:** Would reduce noise from auto-ingestion. Simple regex-based.

**Source:** PLUR — `meta/platitudes.ts`

### 14. Dual Coding (from PLUR)
**What:** Store example + analogy alongside each fact. "Use exponential backoff"
+ example: "retry after 1s, 2s, 4s, 8s" + analogy: "like a polite person
knocking louder each time."

**Why:** Improves retrieval via dual representation (verbal + concrete). Also
useful for injection — the model gets the rule AND an example.

**Source:** PLUR — dual_coding field

### 15. FFF Frecency Tuning (from fff.nvim)
**What:** fff.nvim differentiates AI vs human access patterns — AI gets 3-day
half-life vs 10-day for humans, 7-day history window vs 30-day.

**Why:** Our ACT-R decay rate (d=0.3) is tuned for benchmarks. For production,
we might want agent-type-specific decay: cron-invoked agents decay faster
(short sessions, operational tasks) vs interactive agents (longer, relational).

**Source:** fff.nvim — `frecency.rs`

## Not Worth Integrating

- **Warmth as 4th signal** (Ori-Mnemos) — Our spreading activation already
  covers associative retrieval. Adding a named "warmth" signal would be
  redundant with Hebbian spreading.
- **Three memory zones** (Ori-Mnemos) — Our metabolic rates per fact type are
  more granular than self/notes/ops zones.
- **Full note taxonomy** (Ori-Mnemos) — 50+ regex patterns for 6 categories.
  Our 6-type intent classifier + fact types cover this.
- **FFF file search** (fff.nvim) — File retrieval tool, not memory system.
  No overlap with our architecture.
