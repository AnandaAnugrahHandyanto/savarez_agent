# Hermes Application Evals Design & Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a Hermes-native eval system for agent workflows that measures quality, tool correctness, cost, latency, and regression risk across analyses, reviews, research, CI briefings, and multimodal orchestration.

**Architecture:** Start with a Hermes-native eval layer that reuses existing session traces, tool-call data, trajectory saving, and insights/cost plumbing already present in the repo. Implement deterministic checks first, add rubric-based judge scoring second, and wire the system into local scripts, CI, and scheduled regression runs before considering any hosted eval platform.

**Tech Stack:** Python, SQLite (`state.db` / `kanban.db` patterns), Hermes session store (`hermes_state.py`), Hermes runtime (`run_agent.py`), insights engine (`agent/insights.py`), local JSON/YAML datasets, pytest, cron, optional OpenAI/OpenRouter judge model.

---

## 1. Problem Statement

Hermes currently has strong runtime capabilities but weak systematic quality control for application-level agent behavior. The repo already contains useful primitives:

- `hermes_state.py` stores sessions, messages, tool calls, reasoning fields, token counts, and cost fields.
- `agent/insights.py` already aggregates model, token, tool-call, and cost usage.
- `run_agent.py` supports trajectory saving.
- kanban, cron, and gateway flows already provide durable execution surfaces.

What is missing is a first-class eval layer that can answer questions like:

- Did a routing or prompt change improve or regress end-to-end task quality?
- Is GPT-5.5 worth its cost uplift for analysis/review workloads?
- Did the agent choose the correct tools and use them efficiently?
- Are CI briefings, reviews, or multimodal analyses decision-ready?
- Did quality improve enough to justify latency or cost increases?

This design solves that gap without introducing a premature external platform dependency.

---

## 2. Scope

### In scope

- Hermes-native offline eval runner for curated test cases
- Deterministic assertions for tool use, format, required content, language, and groundedness proxies
- Judge-model scoring for nuanced outputs like analyses and reviews
- Structured datasets and result artifacts on disk
- Cost/latency/quality comparisons across models and prompts
- Reuse of session traces and optional trajectory exports
- CI/cron integration for regression testing
- Kanban-based implementation rollout

### Out of scope for MVP

- Full hosted observability UI (LangSmith/Braintrust class)
- Automatic prompt optimization
- Real-time live traffic shadowing
- Complex OpenTelemetry instrumentation
- Training/fine-tuning loops
- Full human annotation product/UI

---

## 3. Design Principles

1. **Hermes-native first.** Reuse existing storage and runtime surfaces before adding SaaS.
2. **Deterministic before judge.** Cheap, robust assertions form the base layer.
3. **Task-specific, not generic.** Evaluate analyses, reviews, briefings, and multimodal workflows differently.
4. **Cost-aware quality.** Every run must carry quality, latency, and cost together.
5. **Production-fed.** Failing real traces should become new eval cases.
6. **Provider-agnostic.** The eval framework must compare Hermes behaviors across different model routes.
7. **Decision-ready outputs.** Scores must explain what regressed and whether the change should ship.

---

## 4. Target Use Cases

### 4.1 Core Hermes / routing evals

Examples:
- Should a task stay on GPT-5.4 or escalate to GPT-5.5?
- Did a fallback route produce worse tool choice?
- Did a browser-vs-web_extract policy change improve reliability?

Primary metrics:
- task completion
- tool correctness
- tool efficiency
- latency
- token usage
- estimated/actual cost
- failure rate

### 4.2 Analysis / review evals

Examples:
- company analysis
- PR/code review
- research synthesis
- strategic recommendation memo

Primary metrics:
- factuality
- groundedness
- completeness
- novelty / non-genericness
- actionability
- decision usefulness
- prioritization quality

### 4.3 CI / briefing evals

Examples:
- homepage competitor briefing
- daily summary artifact
- multimodal commercial readout

Primary metrics:
- correct campaign detection
- change detection accuracy
- concise output compliance
- commercial relevance
- source linkage
- hallucination rate

### 4.4 Multimodal / tool orchestration evals

Examples:
- browser-driven screenshot analysis
- image+web synthesis
- extract → analyze → summarize workflows

Primary metrics:
- correct tool choice
- correct modality coverage
- end-to-end answer usefulness
- trace completeness
- latency and failure rate under tool orchestration

---

## 5. Proposed System Architecture

## 5.1 High-level components

### A. Eval case store
Versioned case files stored in-repo.

Proposed path:
- `evals/cases/*.yaml`
- `evals/cases/<suite>/<case>.yaml`

Each case defines:
- task type
- prompt/user input
- optional context
- expected tools
- assertions
- rubric
- tags
- optional gold answer / notes

### B. Eval runner
A Python runner that:
- loads one or more cases
- runs Hermes in a reproducible way
- captures final output, messages, tool calls, timing, and cost
- executes deterministic checks
- optionally invokes a judge model
- writes structured results

Proposed path:
- `evals/runner.py`
- `scripts/run_evals.py`

### C. Deterministic check engine
A library of machine-checkable assertions.

Proposed path:
- `evals/checks.py`

Examples:
- required substring / regex present
- max length / bullet count
- exact tool used / forbidden tool absent
- language check
- schema validity
- source URL presence
- no empty output

### D. Judge scoring layer
Rubric-based scoring for nuanced outputs.

Proposed path:
- `evals/judges.py`
- `evals/rubrics/*.yaml`

Judge outputs should be structured JSON with:
- dimension scores
- short justification
- pass/fail recommendation

### E. Report writer
Outputs human-readable and machine-readable artifacts.

Proposed path:
- `evals/reporting.py`
- output dir under `.hermes/artifacts/evals/` or `evals/results/`

Artifacts:
- JSON raw results
- Markdown summary
- optional HTML summary later

### F. Trace / production mining utilities
Turn existing Hermes traces/sessions into candidate eval cases.

Proposed path:
- `evals/mining.py`
- `scripts/mine_eval_cases.py`

Source surfaces:
- `state.db`
- saved trajectories
- cron outputs
- manually curated failcases

---

## 5.2 Hermes integration points

The implementation should explicitly reuse these existing files/surfaces:

- `run_agent.py`
  - existing trajectory support
  - direct reusable runtime entrypoint for eval execution
- `agent/trajectory.py`
  - leverage current trajectory format instead of inventing another one
- `hermes_state.py`
  - session/message/tool-call schema already stores useful eval evidence
- `agent/insights.py`
  - reuse cost/token aggregation logic
- `batch_runner.py`
  - inspect for reusable patterns around batch execution and result capture
- `cron/scheduler.py`
  - scheduled regression runs later
- `gateway/run.py`
  - optional notification/report delivery later
- `tests/stress/test_benchmarks.py`
  - existing regression mindset, but extend from performance into quality

---

## 6. Data Model

## 6.1 EvalCase schema

Proposed file: `evals/schemas.py`

```python
from dataclasses import dataclass, field
from typing import Any, Literal

TaskType = Literal[
    "analysis",
    "review",
    "briefing",
    "browser",
    "multimodal",
    "routing",
    "tooling",
]

@dataclass
class DeterministicAssertion:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    required: bool = True

@dataclass
class JudgeDimension:
    name: str
    description: str
    scale_min: int = 1
    scale_max: int = 5
    pass_threshold: float | None = None

@dataclass
class EvalCase:
    case_id: str
    suite: str
    task_type: TaskType
    title: str
    prompt: str
    context: str | None = None
    tags: list[str] = field(default_factory=list)
    enabled_toolsets: list[str] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    assertions: list[DeterministicAssertion] = field(default_factory=list)
    judge_dimensions: list[JudgeDimension] = field(default_factory=list)
    gold_answer: str | None = None
    notes: str | None = None
```

### Example case YAML

```yaml
case_id: briefing.hp.homepage.visible-campaigns
suite: ci-briefings
task_type: briefing
title: Detect visible homepage campaigns and summarize changes
prompt: >
  Review the provided homepage capture and summarize the visible campaigns,
  banners, and promotional hooks in at most 10 lines.
context: >
  Output must be concise, observation-led, and avoid invented commercial claims.
tags: [igo, homepage, daily, concise]
enabled_toolsets: [browser, vision]
expected_tools: [browser_navigate, browser_vision]
forbidden_tools: [terminal]
assertions:
  - kind: max_lines
    params: {max_lines: 10}
  - kind: required_regex
    params: {pattern: '(banner|campaign|promotion|discount)'}
  - kind: no_placeholder_language
    params: {}
judge_dimensions:
  - name: factuality
    description: Are claims grounded in visible evidence?
    pass_threshold: 4
  - name: commercial_relevance
    description: Does the summary isolate commercially relevant signals?
    pass_threshold: 4
  - name: non_genericness
    description: Is the summary specific instead of boilerplate?
    pass_threshold: 4
```

---

## 6.2 EvalRunResult schema

```python
@dataclass
class AssertionResult:
    kind: str
    passed: bool
    score: float
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class JudgeResult:
    dimension: str
    score: float
    passed: bool
    rationale: str

@dataclass
class EvalRunResult:
    run_id: str
    case_id: str
    suite: str
    provider: str | None
    model: str | None
    judge_provider: str | None
    judge_model: str | None
    started_at: str
    ended_at: str
    elapsed_ms: int
    completed: bool
    failed: bool
    error: str | None
    final_response: str
    tool_calls: list[dict[str, Any]]
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    estimated_cost_usd: float | None
    actual_cost_usd: float | None
    assertions: list[AssertionResult]
    judge_results: list[JudgeResult]
    aggregate_scores: dict[str, float]
    labels: dict[str, Any] = field(default_factory=dict)
```

---

## 7. Scoring Model

## 7.1 Deterministic score

Compute a weighted ratio over assertions.

Example:
- required tool used = 2.0
- output within max length = 1.0
- source link present = 1.5

`deterministic_score = passed_weight / total_weight`

If a `required=True` assertion fails, the case may still continue to judge scoring, but the overall case cannot become an unconditional pass.

## 7.2 Judge score

Per-dimension 1–5 scoring, normalized to 0–1.

Example normalized score:
`(score - min) / (max - min)`

Judge must emit strict JSON to reduce parsing fragility.

## 7.3 Aggregate score

Recommended MVP aggregation:
- deterministic: 50%
- judge: 40%
- efficiency modifier: 10%

Where efficiency modifier rewards acceptable cost/latency bands rather than raw cheapness.

### Important rule
A run cannot pass overall if any critical gate fails, for example:
- missing required tool
- empty final output
- explicit hallucination marker / unsupported claim gate
- case-level minimum factuality threshold

---

## 8. Deterministic Assertion Library

Proposed file: `evals/checks.py`

MVP assertions:
- `non_empty_output`
- `max_chars`
- `max_lines`
- `contains_substring`
- `required_regex`
- `forbidden_regex`
- `tool_used`
- `tool_not_used`
- `allowed_toolset_only`
- `contains_url`
- `json_schema_valid`
- `language_is`
- `no_placeholder_language`
- `response_not_generic`
- `minimum_bullet_count`

Later assertions:
- exact extraction match
- fuzzy extraction match
- source-grounding check against supplied snippets
- tool-order correctness
- multimodal evidence mention

---

## 9. Judge Layer Design

## 9.1 Judge prompt shape

The judge should score against:
- original task
- optional context/rules
- final output
- optional tool summary
- optional source snippets
- rubric dimensions

The judge prompt must explicitly separate:
- facts visible in the source material
- claims made by the agent
- unsupported extrapolations

## 9.2 Judge output contract

Return strict JSON like:

```json
{
  "scores": [
    {"dimension": "factuality", "score": 4, "passed": true, "rationale": "Most claims grounded in source."},
    {"dimension": "actionability", "score": 5, "passed": true, "rationale": "Output ends with specific recommendation."}
  ],
  "overall_pass": true,
  "summary": "Strong result with one overgeneralized claim."
}
```

## 9.3 Judge model policy

Recommended:
- deterministic checks always run
- cheaper judge allowed for low-stakes suites
- stronger judge for analysis/review suites
- frontier judge only for calibration, approval-board quality review, or spot checks

This matches the broader Hermes routing strategy rather than putting the whole eval pipeline on the most expensive model.

---

## 10. Execution Flow

## 10.1 Offline curated eval flow

1. Load selected cases.
2. For each case, start a fresh Hermes eval run.
3. Capture final response, trace metadata, tool calls, elapsed time, and cost.
4. Run deterministic assertions.
5. If case requires judge scoring, call judge model.
6. Compute aggregate score and pass/fail.
7. Write JSON + markdown report.
8. Optionally compare against a baseline snapshot.

## 10.2 Trace-mined eval flow

1. Query `state.db` or saved trajectories for target sessions.
2. Filter failures, regressions, surprising tool traces, or user-corrected outputs.
3. Convert selected sessions into draft eval cases.
4. Human review the draft cases.
5. Promote approved cases into versioned `evals/cases/`.

## 10.3 Regression gate flow

1. Run suite against baseline config/model.
2. Run suite against candidate config/model.
3. Compare:
   - aggregate quality
   - case pass rate
   - tool correctness
   - median latency
   - median cost
4. Emit ship / no-ship recommendation.

---

## 11. CLI / Script Surface

### MVP: script-first, not CLI-first

Do **not** start by adding a fully polished `hermes evals` CLI subcommand. That is a second-step convenience layer.

### Required MVP entrypoints

Create:
- `scripts/run_evals.py`
- `scripts/mine_eval_cases.py`

### `scripts/run_evals.py` contract

Example usages:

```bash
python scripts/run_evals.py --suite ci-briefings
python scripts/run_evals.py --suite analysis --model gpt-5.4
python scripts/run_evals.py --suite review --model gpt-5.5 --judge-model gpt-5.5
python scripts/run_evals.py --case routing.browser-vs-webextract --output evals/results/manual/
```

Arguments:
- `--suite`
- `--case`
- `--model`
- `--provider`
- `--judge-model`
- `--judge-provider`
- `--max-cases`
- `--output`
- `--baseline`
- `--fail-under`
- `--json`

### Phase 2 CLI integration

Once the core is proven, add:
- `hermes evals run`
- `hermes evals compare`
- `hermes evals mine`

Likely files later:
- `hermes_cli/main.py`
- `hermes_cli/commands.py`
- possibly dedicated `hermes_cli/evals.py`

---

## 12. Storage Layout

Proposed repo structure:

```text
hermes-agent/
  evals/
    __init__.py
    schemas.py
    loader.py
    runner.py
    checks.py
    judges.py
    reporting.py
    mining.py
    baselines.py
    cases/
      analysis/
      review/
      briefing/
      routing/
      multimodal/
    rubrics/
      analysis.yaml
      review.yaml
      briefing.yaml
      multimodal.yaml
    results/
      .gitignore
  scripts/
    run_evals.py
    mine_eval_cases.py
  tests/
    evals/
      test_loader.py
      test_checks.py
      test_judges.py
      test_runner.py
      test_mining.py
```

### Artifact policy

- Keep cases and rubrics in git.
- Keep run results out of git by default via `evals/results/.gitignore`.
- For decision-grade comparisons, allow explicit export to `docs/` or `.hermes/artifacts/`.

---

## 13. Baseline & Comparison Strategy

Proposed file: `evals/baselines.py`

A baseline snapshot should include:
- suite name
- git sha
- Hermes config fingerprint
- run date
- model/provider route
- aggregate pass rate
- per-case scores
- median cost/latency

Comparison report should answer:
- Which cases regressed?
- Which dimensions improved?
- Did quality increase enough to justify extra cost?
- Is the candidate safe to ship?

Decision output example:

```json
{
  "recommendation": "ship_with_scope_limit",
  "summary": "Quality improved materially on review tasks but not on briefings.",
  "improvements": ["review factuality +0.6", "tool correctness +8%"],
  "regressions": ["briefing concision -0.3", "median latency +41%"],
  "guardrails": ["route only analysis/review suites to GPT-5.5"]
}
```

---

## 14. CI / Cron Integration

## 14.1 CI

Add a lightweight job for deterministic and smoke evals.

Proposed future files:
- `.github/workflows/evals-smoke.yml`
- optional `.github/workflows/evals-nightly.yml`

### CI gates for MVP

On pull request or important config/runtime changes:
- loader/check unit tests must pass
- smoke suite must pass
- no critical case regression allowed

## 14.2 Cron

Use scheduled jobs for:
- nightly regression run
- weekly model comparison run
- production failcase mining digest

Likely later command pattern:
- cron invokes `scripts/run_evals.py`
- optionally posts markdown summary back to Telegram

---

## 15. Initial Golden Set

Seed the system with **25–40 cases**, not 200.

### Recommended first suites

#### Suite A — routing/core (5–8 cases)
- browser vs web_extract routing
- safe fallback behavior
- correct tool use under dynamic page conditions
- escalation-to-reviewer gate behavior

#### Suite B — analyses/reviews (8–10 cases)
- strategic analysis summary
- code review finding quality
- decision memo usefulness
- hallucination-sensitive synthesis

#### Suite C — CI/briefings (8–10 cases)
- homepage campaign detection
- change summary concision
- seasonal/commercial signal extraction
- exactness vs speculation

#### Suite D — multimodal/tool orchestration (5–8 cases)
- screenshot analysis
- image + text synthesis
- browser screenshot + summarization
- failure handling and fallback

### Curation rule

At least one-third of cases should come from real Hermes outputs or user-corrected failures, not purely synthetic prompts.

---

## 16. Testing Strategy

## Unit tests

Create:
- `tests/evals/test_loader.py`
- `tests/evals/test_checks.py`
- `tests/evals/test_judges.py`
- `tests/evals/test_reporting.py`

Cover:
- case parsing
- invalid schema rejection
- assertion behavior
- judge result parsing
- aggregate scoring logic

## Integration tests

Create:
- `tests/evals/test_runner.py`
- `tests/evals/test_mining.py`

Cover:
- single case end-to-end execution against a mocked/minimal runtime
- result artifact generation
- trace/session mining from fixture data

### Important constraint

Do not make the unit suite depend on live model calls. Judge responses and run outputs should be mockable or fixture-driven.

---

## 17. Rollout Plan

## Phase 0 — design and scaffolding
- finalize schemas
- create directory structure
- add loader/check/report skeletons

## Phase 1 — deterministic MVP
- implement case loader
- implement deterministic checks
- implement runner with final output + tool trace capture
- add markdown/json reporting
- seed first 8–12 cases

## Phase 2 — judge scoring
- implement rubric files
- implement structured judge scoring
- add aggregate scoring
- calibrate first judge suite on analysis/review cases

## Phase 3 — baseline comparisons
- add baseline snapshotting
- add compare reports
- define pass/fail regression policy

## Phase 4 — production-fed eval flywheel
- mine failcases from `state.db` / trajectories
- human review promotion flow
- nightly/weekly scheduled runs

## Phase 5 — optional CLI + hosted integration
- add `hermes evals` CLI
- consider Braintrust/LangSmith/OpenAI Evals only if the Hermes-native layer proves insufficient

---

## 18. Risks & Mitigations

### Risk: judge-model overconfidence
Mitigation:
- deterministic gates first
- rubric-based scoring only
- periodic human calibration
- use stronger judge only where needed

### Risk: eval harness becomes too abstract
Mitigation:
- ship script-first MVP
- force every case to map to a real Hermes task type
- keep first suites small and high-signal

### Risk: cost blowout
Mitigation:
- cheap deterministic layer by default
- judge only on selected suites
- explicit cost metrics in every result
- separate calibration runs from routine runs

### Risk: fragile integration with runtime internals
Mitigation:
- reuse existing session/trajectory formats
- prefer wrappers and adapters over invasive runtime changes in phase 1
- add tests around integration seams

### Risk: synthetic test bias
Mitigation:
- mine production traces and user-corrected failures into the dataset

---

## 19. Concrete File Plan

### Create
- `evals/__init__.py`
- `evals/schemas.py`
- `evals/loader.py`
- `evals/checks.py`
- `evals/judges.py`
- `evals/runner.py`
- `evals/reporting.py`
- `evals/mining.py`
- `evals/baselines.py`
- `evals/cases/analysis/`
- `evals/cases/review/`
- `evals/cases/briefing/`
- `evals/cases/routing/`
- `evals/cases/multimodal/`
- `evals/rubrics/analysis.yaml`
- `evals/rubrics/review.yaml`
- `evals/rubrics/briefing.yaml`
- `evals/rubrics/multimodal.yaml`
- `evals/results/.gitignore`
- `scripts/run_evals.py`
- `scripts/mine_eval_cases.py`
- `tests/evals/test_loader.py`
- `tests/evals/test_checks.py`
- `tests/evals/test_judges.py`
- `tests/evals/test_runner.py`
- `tests/evals/test_mining.py`

### Read / reuse / likely modify
- `run_agent.py`
- `agent/trajectory.py`
- `agent/insights.py`
- `hermes_state.py`
- `batch_runner.py`
- later: `hermes_cli/main.py`, `hermes_cli/commands.py`

---

## 20. Implementation Tasks (for execution)

### Task 1: Scaffold eval package and schemas

**Objective:** Create the package structure and strict case/result schemas.

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/schemas.py`
- Create: `tests/evals/test_loader.py`

**Done when:**
- case schema can parse valid YAML
- invalid cases fail with clear errors
- test suite passes locally

### Task 2: Implement deterministic check engine

**Objective:** Build the first assertion library and scoring helper.

**Files:**
- Create: `evals/checks.py`
- Create: `tests/evals/test_checks.py`

**Done when:**
- core assertions listed in section 8 are implemented
- weighted scoring works
- required-failure semantics are tested

### Task 3: Build case loader and result writer

**Objective:** Load suites from disk and emit structured JSON/markdown results.

**Files:**
- Create: `evals/loader.py`
- Create: `evals/reporting.py`
- Create: `evals/results/.gitignore`

**Done when:**
- loader resolves suites/cases deterministically
- report writer emits stable machine-readable output
- markdown report is human-usable

### Task 4: Build Hermes-native eval runner

**Objective:** Execute a case through Hermes, capture output, tool calls, timing, and cost.

**Files:**
- Create: `evals/runner.py`
- Create: `tests/evals/test_runner.py`
- Read/reuse: `run_agent.py`, `agent/trajectory.py`, `hermes_state.py`, `agent/insights.py`

**Done when:**
- one case runs end-to-end
- final output and tool summary are captured
- run result includes timing and cost fields

### Task 5: Seed first golden cases

**Objective:** Add the first 8–12 high-signal eval cases across routing, review, briefing, and multimodal work.

**Files:**
- Create under: `evals/cases/...`
- Create rubrics under: `evals/rubrics/...`

**Done when:**
- each suite has at least two cases
- each case has assertions
- at least some cases require judge scoring

### Task 6: Implement judge scoring layer

**Objective:** Add rubric-driven judge evaluation with strict JSON parsing.

**Files:**
- Create: `evals/judges.py`
- Create: `tests/evals/test_judges.py`
- Create: `evals/rubrics/*.yaml`

**Done when:**
- judge prompt is structured
- judge output parser is robust
- aggregate scoring combines deterministic and judge scores

### Task 7: Add runnable scripts and baseline compare flow

**Objective:** Make eval execution operational from scripts.

**Files:**
- Create: `scripts/run_evals.py`
- Create: `evals/baselines.py`

**Done when:**
- suite runs from CLI script
- baseline snapshot saves cleanly
- comparison report calls out regressions and ship recommendation

### Task 8: Add trace mining utilities

**Objective:** Turn production/session traces into candidate eval cases.

**Files:**
- Create: `evals/mining.py`
- Create: `scripts/mine_eval_cases.py`
- Create: `tests/evals/test_mining.py`

**Done when:**
- mining can read fixture or real `state.db`-derived examples
- draft cases can be exported for human review

### Task 9: Wire smoke suite into CI / scheduled execution

**Objective:** Make evals part of the actual release/regression loop.

**Files:**
- Create/modify: CI workflow file(s)
- Optionally create cron wrapper script

**Done when:**
- smoke suite runs automatically
- failure status is visible
- nightly scheduled run path is defined

### Task 10: Document operator workflow

**Objective:** Make the eval flywheel usable by future operators.

**Files:**
- Update docs as needed
- optionally add `docs/evals/README.md`

**Done when:**
- there is a clear workflow for: create case → run suite → compare baseline → promote failcase into dataset

---

## 21. Recommended Kanban Graph

Use these task lanes:

1. **Foundation**
   - schemas
   - loader
   - checks
2. **Runtime integration**
   - runner
   - reporting
3. **Content calibration**
   - golden cases
   - rubrics
   - judge layer
4. **Operationalization**
   - scripts
   - baselines
   - CI/cron
   - mining
5. **Documentation & rollout**
   - operator docs
   - adoption guide

### Dependency shape

- Task 1 → Tasks 2, 3
- Tasks 2 + 3 → Task 4
- Task 4 → Tasks 5, 7
- Task 5 → Task 6
- Tasks 6 + 7 → Task 9
- Task 4 → Task 8
- Tasks 8 + 9 → Task 10

This allows useful parallelism without forcing speculative downstream work too early.

---

## 22. Recommendation

Proceed with the Hermes-native MVP rather than jumping straight to an external eval platform.

**Why:**
- the repo already contains enough trace, tool-call, and cost data to support a serious first eval system
- the immediate bottleneck is discipline and structure, not UI
- this approach preserves provider/model neutrality
- it creates a concrete basis for later deciding whether hosted observability is actually necessary

**Success criterion for MVP:**
Within one iteration, Hermes should be able to run a 10+ case suite and produce a decision-ready regression report showing quality, tool correctness, latency, and cost differences across at least two model routes.
