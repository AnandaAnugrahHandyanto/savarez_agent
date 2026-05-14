"""Goalify — turn rambling voice text into a locked Hermes /goal contract.

Goalify is intentionally a structuring layer, not a second autonomous loop.
It stores pending drafts per session, renders a verifiable /goal prompt, and
only hands the prompt to the existing goal engine after an explicit natural-
language lock confirmation.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # yaml is already a Hermes dependency, but keep goalify resilient.
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


VAGUE_WORDS = (
    "works well",
    "look good",
    "looks good",
    "fast",
    "feels right",
    "clean",
    "done properly",
    "great ux",
    "better ux",
    "polished",
)

FIELD_NAMES = {
    "final_outcome": "FINAL_OUTCOME",
    "outcome": "FINAL_OUTCOME",
    "goal": "FINAL_OUTCOME",
    "project": "PROJECT",
    "stack": "STACK",
    "current_state": "CURRENT_STATE",
    "state": "CURRENT_STATE",
    "working_dir": "WORKING_DIR",
    "cwd": "WORKING_DIR",
    "constraints": "CONSTRAINTS",
    "audience": "AUDIENCE",
    "criterion_1": "CRITERION_1",
    "criteria_1": "CRITERION_1",
    "criterion 1": "CRITERION_1",
    "criteria 1": "CRITERION_1",
    "first criterion": "CRITERION_1",
    "criterion_2": "CRITERION_2",
    "criteria_2": "CRITERION_2",
    "criterion 2": "CRITERION_2",
    "criteria 2": "CRITERION_2",
    "second criterion": "CRITERION_2",
    "criterion_3": "CRITERION_3",
    "criteria_3": "CRITERION_3",
    "criterion 3": "CRITERION_3",
    "criteria 3": "CRITERION_3",
    "third criterion": "CRITERION_3",
}

TEMPLATE_FIELDS = [
    "FINAL_OUTCOME",
    "PROJECT",
    "STACK",
    "CURRENT_STATE",
    "WORKING_DIR",
    "CONSTRAINTS",
    "AUDIENCE",
    "CRITERION_1",
    "CRITERION_2",
    "CRITERION_3",
]


@dataclass
class GoalifyResult:
    kind: str  # clarify | propose | execute | cancel | error
    message: str
    locked_prompt: Optional[str] = None


@dataclass
class GoalifyState:
    session_id: str
    raw_input: str
    cwd: str = ""
    fields: Dict[str, str] = field(default_factory=dict)
    sources: Dict[str, str] = field(default_factory=dict)
    status: str = "clarifying"  # clarifying | proposed
    rendered_prompt: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    clarify_turns: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "GoalifyState":
        data = json.loads(raw)
        return cls(
            session_id=str(data.get("session_id") or ""),
            raw_input=str(data.get("raw_input") or ""),
            cwd=str(data.get("cwd") or ""),
            fields={str(k): str(v) for k, v in (data.get("fields") or {}).items()},
            sources={str(k): str(v) for k, v in (data.get("sources") or {}).items()},
            status=str(data.get("status") or "clarifying"),
            rendered_prompt=str(data.get("rendered_prompt") or ""),
            created_at=float(data.get("created_at") or 0.0),
            updated_at=float(data.get("updated_at") or 0.0),
            clarify_turns=int(data.get("clarify_turns") or 0),
        )


def goalify_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        root = Path(get_hermes_home())
    except Exception:  # pragma: no cover
        root = Path.home() / ".hermes"
    return root / "goalify"


def _meta_key(session_id: str) -> str:
    return f"goalify:{session_id}"


def _get_session_db() -> Optional[Any]:
    try:
        from hermes_cli.goals import _get_session_db as _goal_db

        return _goal_db()
    except Exception:
        return None


def load_pending(session_id: str) -> Optional[GoalifyState]:
    if not session_id:
        return None
    db = _get_session_db()
    if db is None:
        return None
    raw = db.get_meta(_meta_key(session_id))
    if not raw:
        return None
    try:
        return GoalifyState.from_json(raw)
    except Exception:
        return None


def save_pending(state: GoalifyState) -> None:
    if not state.session_id:
        return
    db = _get_session_db()
    if db is None:
        return
    state.updated_at = time.time()
    db.set_meta(_meta_key(state.session_id), state.to_json())


def clear_pending(session_id: str) -> None:
    db = _get_session_db()
    if db is None or not session_id:
        return
    # SessionDB exposes set_meta/get_meta; storing an empty value makes load_pending falsey.
    db.set_meta(_meta_key(session_id), "")


def load_defaults(cwd: str = "") -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load Hermes-native defaults from ~/.hermes/goalify/defaults.yml.

    Compatibility with ~/.claude/goal-defaults.yml can be added later; v1 keeps
    the canonical file in Hermes territory as requested.
    """
    defaults_path = goalify_home() / "defaults.yml"
    if yaml is None or not defaults_path.exists():
        return {}, {}
    try:
        data = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}, {}
    fields: Dict[str, str] = {}
    sources: Dict[str, str] = {}
    baseline = data.get("defaults") or {}
    if isinstance(baseline, dict):
        for key, value in baseline.items():
            field = _normalize_field_name(str(key))
            if field in TEMPLATE_FIELDS and value not in (None, ""):
                fields[field] = str(value).strip()
                sources[field] = "default"
    overrides = data.get("project_overrides") or []
    if isinstance(overrides, list):
        for item in overrides:
            if not isinstance(item, dict):
                continue
            match = str(item.get("cwd_match") or "").strip()
            if match and cwd and match in cwd:
                for key, value in item.items():
                    if key == "cwd_match":
                        continue
                    field = _normalize_field_name(str(key))
                    if field in TEMPLATE_FIELDS and value not in (None, ""):
                        fields[field] = str(value).strip()
                        sources[field] = "project_override"
                break
    return fields, sources


def _normalize_field_name(name: str) -> str:
    compact = name.strip().lower().replace("-", "_")
    return FIELD_NAMES.get(compact, compact.upper())


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?:\n+|(?<=[.!?])\s+|;\s+)", text.strip())
    return [p.strip(" .\n\t") for p in parts if p and p.strip(" .\n\t")]


def _is_measurable(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return False
    if any(v == s or v in s for v in VAGUE_WORDS):
        # A phrase can contain "fast" and still be measurable if it has a threshold.
        if not re.search(r"(<|>|<=|>=|=|\b\d+(?:\.\d+)?\s*(ms|s|sec|seconds|%|kb|mb|gb)\b)", s):
            return False
    measurable_patterns = [
        r"\b(pass|passes|passed|exit[s]? 0|returns?\s+\d{3}|status\s*ok|200|201|204)\b",
        r"\b(get|post|put|delete|patch)\s+/[\w/{}.-]+",
        r"\b(pytest|npm|pnpm|yarn|ruff|mypy|make|cargo|go test)\b",
        r"\b(file|artifact|row|count|table|url|screenshot|docs?/|readme|changelog)\b",
        r"(<|>|<=|>=|=)\s*\d+",
        r"\b\d+(?:\.\d+)?\s*(ms|s|sec|seconds|%|kb|mb|gb)\b",
        r"\b(no|zero)\s+(errors?|failures?|unrelated files?|files? outside)\b",
    ]
    return any(re.search(pattern, s) for pattern in measurable_patterns)


def _contains_vague(text: str) -> Optional[str]:
    s = (text or "").lower()
    for word in VAGUE_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, s):
            return word
    return None


def _clean_one_line(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).strip(" .")


def parse_raw_input(raw: str, cwd: str = "") -> Tuple[Dict[str, str], Dict[str, str]]:
    fields: Dict[str, str] = {}
    sources: Dict[str, str] = {}
    text = _clean_one_line(raw)
    lower = text.lower()

    if cwd:
        fields["WORKING_DIR"] = cwd
        sources["WORKING_DIR"] = "cwd"

    # Project/stack/current/audience explicit phrases.
    explicit_patterns = [
        ("PROJECT", r"\bproject\s+(?:is|=|:)\s*([^.;]+)"),
        ("STACK", r"\bstack\s+(?:is|=|:)\s*([^.;]+)"),
        ("CURRENT_STATE", r"\b(?:current state|right now|currently)\s+(?:(?:is|=|:)\s*)?([^.;]+)"),
        ("AUDIENCE", r"\b(?:audience|for)\s+(?:is|=|:)\s*([^.;]+)"),
    ]
    for field, pattern in explicit_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            fields[field] = _clean_one_line(m.group(1))
            sources[field] = "parsed"

    # Outcome: first intent sentence, stripped of common voice preamble.
    sentences = _split_sentences(text)
    outcome = ""
    for sent in sentences:
        m = re.search(r"\b(?:i want to|i need to|please|can you|build|make|fix|ship|implement|create|add|update)\b\s*(.+)", sent, re.I)
        if m:
            outcome = m.group(1) if sent.lower().startswith(("i want", "i need", "please", "can you")) else sent
            break
    if not outcome and sentences:
        outcome = sentences[0]
    if outcome:
        # Stop before explicit metadata that often follows in the same dictated sentence.
        outcome = re.split(r"\b(?:project is|stack is|right now|currently|current state|audience is|done when|success means)\b", outcome, flags=re.I)[0]
        fields["FINAL_OUTCOME"] = _clean_one_line(outcome)
        sources["FINAL_OUTCOME"] = "parsed"

    constraints = []
    for m in re.finditer(r"\b(?:must|can't|cannot|without|by\s+\w+|under\s+\$?\d+)[^.;]*", text, re.I):
        constraints.append(_clean_one_line(m.group(0)))
    if constraints:
        fields["CONSTRAINTS"] = "; ".join(constraints)
        sources["CONSTRAINTS"] = "parsed"

    # Criteria after "done when" / "success means" / "I'll know...".
    criteria_blob = ""
    m = re.search(r"\b(?:done when|success means|i'?ll know it'?s done when|criteria are)\b\s*(.+)", text, re.I)
    if m:
        criteria_blob = m.group(1)
    candidates: List[str] = []
    if criteria_blob:
        candidates = [
            _clean_one_line(p)
            for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", criteria_blob)
            if _clean_one_line(p)
        ]
    else:
        # Pull measurable-looking sentences from the whole raw input.
        candidates = [_clean_one_line(s) for s in sentences if _is_measurable(s)]
    idx = 1
    for cand in candidates:
        if idx > 3:
            break
        if cand and _is_measurable(cand):
            fields[f"CRITERION_{idx}"] = cand
            sources[f"CRITERION_{idx}"] = "parsed"
            idx += 1

    if "CONSTRAINTS" not in fields:
        fields["CONSTRAINTS"] = "Respect Hermes safety boundaries; pause before destructive, irreversible, external-send, publishing, purchasing, credential, or broad security changes."
        sources["CONSTRAINTS"] = "hermes_default"

    return fields, sources


def apply_defaults(raw_fields: Dict[str, str], raw_sources: Dict[str, str], cwd: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    fields, sources = load_defaults(cwd)
    # Parsed user input wins over defaults/project overrides.
    fields.update(raw_fields)
    sources.update(raw_sources)
    return fields, sources


def gaps_for(fields: Dict[str, str]) -> List[str]:
    gaps: List[str] = []
    required = ["FINAL_OUTCOME", "PROJECT", "STACK", "CURRENT_STATE", "WORKING_DIR", "AUDIENCE"]
    for field in required:
        value = fields.get(field, "")
        if not value or (field != "FINAL_OUTCOME" and _contains_vague(value)):
            gaps.append(field)
    for i in range(1, 4):
        field = f"CRITERION_{i}"
        if not _is_measurable(fields.get(field, "")):
            gaps.append(field)
    return gaps


def _infer_project_from_cwd(cwd: str) -> str:
    if not cwd:
        return "this project"
    try:
        name = Path(cwd).name
    except Exception:
        name = "this project"
    return name or "this project"


def _proposal_fill(fields: Dict[str, str], cwd: str) -> Dict[str, str]:
    filled = dict(fields)
    filled.setdefault("PROJECT", _infer_project_from_cwd(cwd))
    filled.setdefault("STACK", "project-detected stack")
    filled.setdefault("CURRENT_STATE", "as described in the raw request")
    filled.setdefault("WORKING_DIR", cwd or "current working directory")
    filled.setdefault("AUDIENCE", "Julian / project maintainers")
    filled.setdefault("CONSTRAINTS", "Respect Hermes safety boundaries; pause before destructive, irreversible, external-send, publishing, purchasing, credential, or broad security changes.")
    return filled


def render_prompt(fields: Dict[str, str], cwd: str = "") -> str:
    f = _proposal_fill(fields, cwd)
    outcome = _clean_one_line(f.get("FINAL_OUTCOME") or "Complete the requested goal")
    return f"""/goal {outcome}
— CONTEXT —
· Project: {f.get('PROJECT', '')}
· Stack: {f.get('STACK', '')}
· Current state: {f.get('CURRENT_STATE', '')}
· Working dir: {f.get('WORKING_DIR', '')}
· Constraints: {f.get('CONSTRAINTS', '')}
· Audience: {f.get('AUDIENCE', '')}
— SUCCESS CRITERIA (ALL MUST BE TRUE) —
1. {f.get('CRITERION_1', '')}
2. {f.get('CRITERION_2', '')}
3. {f.get('CRITERION_3', '')}
4. Final deliverable runs without errors
5. You can show proof (screenshot · test output · URL)
— OPERATING RULES — NON-NEGOTIABLE —
1. PLAN FIRST. Output a numbered task list before writing any code.
2. WORK AUTONOMOUSLY. Don't ask clarifying Qs unless genuinely blocked.
3. SELF-VERIFY. After every step: run tests, inspect output, confirm it worked.
4. DEBUG YOURSELF. If it fails, diagnose + fix. Don't hand it back.
5. USE THE RIGHT TOOLS. Use MCPs, terminal, web, code exec, browser, and real data when they materially improve correctness, grounding, or verification.
6. NO PLACEHOLDERS. No TODOs · no stubs · real components + real states.
7. PROGRESS LOG. Track completed · in-flight · decisions · blockers.
8. STAY ON GOAL. Discoveries off-spec? Note + keep moving.
9. IF BLOCKED. Log the wall · continue everything parallelizable.
10. CHECK SUCCESS BEFORE STOPPING. Re-read criteria · confirm each is met.
11. RESPECT SAFETY BOUNDARIES. Pause before destructive, irreversible, external-send, publishing, purchasing, credential, or broad security changes.
— QUALITY BAR —
· Code: clean, typed, follows project conventions
· Design: looks like a well-funded startup shipped it
· Output: survives a senior code review
· Docs: every new pattern / env var / decision logged
— FINAL DELIVERABLE —
✅ Confirmation each criterion is satisfied
📁 Every file created / modified
🚀 How to run / test / deploy
📊 Proof (screenshot · test output · URL)
📝 Decisions made + anything to know
⚠️  Known limitations + follow-ups
Begin by outputting your plan. Then execute end-to-end without checking in
until done or genuinely blocked."""


def render_proposal(state: GoalifyState) -> str:
    prompt = render_prompt(state.fields, state.cwd)
    state.rendered_prompt = prompt
    lines = ["Goalify proposal:", "", "```", prompt, "```", "", "Field sources:"]
    for field in TEMPLATE_FIELDS:
        lines.append(f"  {field:<14} ← {state.sources.get(field, 'proposed')}")
    lines.extend([
        "",
        "Lock and engage goal-loop? [yes / edit <field>: <value> / cancel]",
        "Natural language works too: 'yes go ahead', 'change the audience to product engineers', or 'cancel this'.",
    ])
    return "\n".join(lines)


def render_clarify(raw: str, fields: Dict[str, str], gaps: List[str]) -> str:
    questions: List[str] = []
    vague = _contains_vague(raw)
    criteria_gaps = [g for g in gaps if g.startswith("CRITERION_")]
    if criteria_gaps:
        quote = f" You said '{vague}' — what's the threshold?" if vague else ""
        questions.append(
            "1. What are the measurable criteria for this run?"
            f"{quote} Examples: `pytest tests/foo.py passes`, `GET /api/health returns 200`, `page load < 2s`."
        )
    ordered = ["FINAL_OUTCOME", "CURRENT_STATE", "AUDIENCE", "PROJECT", "STACK", "WORKING_DIR"]
    for field in ordered:
        if len(questions) >= 3:
            break
        if field not in gaps:
            continue
        label = field.lower().replace("_", " ")
        examples = {
            "FINAL_OUTCOME": "Example: `ship the health endpoint` or `fix Discord mention routing`.",
            "CURRENT_STATE": "Example: `tests fail with 404` or `prototype exists but no auth`.",
            "AUDIENCE": "Example: `internal operators`, `founders`, or `project maintainers`.",
            "PROJECT": "Example: repo/app name such as `gtm-run`.",
            "STACK": "Example: `Next.js + Supabase` or `Python FastAPI`.",
            "WORKING_DIR": "Example: `/Users/juli/src/project`.",
        }.get(field, "")
        questions.append(f"{len(questions) + 1}. What's the {label}? {examples}")
    return "Goalify needs a little structure before it can lock. Answer in one sentence if you want.\n\n" + "\n".join(questions)


def _extract_edit(text: str) -> Optional[Tuple[str, str]]:
    clean = _clean_one_line(text)
    # edit FIELD: value
    m = re.match(r"(?:edit|change|set|update)\s+(?:the\s+)?([a-zA-Z0-9_ -]+?)\s*(?:to|:|=)\s*(.+)$", clean, re.I)
    if m:
        field = _normalize_field_name(m.group(1))
        if field in TEMPLATE_FIELDS:
            return field, _clean_one_line(m.group(2))
    # natural: "change the audience to product engineers" where field includes filler words.
    for phrase, field in FIELD_NAMES.items():
        phrase_re = re.escape(phrase.replace("_", " "))
        m = re.search(rf"\b(?:edit|change|set|update)\s+(?:the\s+)?{phrase_re}\s+(?:to|as)\s+(.+)$", clean, re.I)
        if m:
            return field, _clean_one_line(m.group(1))
    return None


def _is_yes(text: str) -> bool:
    s = _clean_one_line(text).lower()
    yes_patterns = (
        "yes",
        "yeah",
        "yep",
        "correct",
        "looks good",
        "go ahead",
        "start",
        "lock",
        "engage",
        "do it",
        "run it",
        "ship it",
        "that's good",
        "that is good",
    )
    return any(p in s for p in yes_patterns) and not _is_cancel(text)


def _is_cancel(text: str) -> bool:
    s = _clean_one_line(text).lower()
    return any(p in s for p in ("cancel", "never mind", "nevermind", "stop this", "don't", "do not", "no thanks"))


def _append_audit(state: GoalifyState, outcome: str) -> None:
    home = goalify_home()
    home.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": time.time(),
        "session_id": state.session_id,
        "raw_input": state.raw_input,
        "locked_prompt": state.rendered_prompt,
        "outcome": outcome,
    }
    with (home / "runs.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


class GoalifyManager:
    def __init__(self, session_id: str):
        self.session_id = session_id

    def start(self, raw_input: str, *, cwd: str = "") -> GoalifyResult:
        raw_fields, raw_sources = parse_raw_input(raw_input, cwd)
        fields, sources = apply_defaults(raw_fields, raw_sources, cwd)
        now = time.time()
        state = GoalifyState(
            session_id=self.session_id,
            raw_input=raw_input,
            cwd=cwd,
            fields=fields,
            sources=sources,
            created_at=now,
            updated_at=now,
        )
        gaps = gaps_for(fields)
        if gaps:
            state.status = "clarifying"
            save_pending(state)
            return GoalifyResult("clarify", render_clarify(raw_input, fields, gaps))
        state.status = "proposed"
        state.rendered_prompt = render_prompt(fields, cwd)
        save_pending(state)
        return GoalifyResult("propose", render_proposal(state))

    def followup(self, text: str) -> GoalifyResult:
        state = load_pending(self.session_id)
        if state is None:
            return GoalifyResult("error", "No pending goalify draft. Start with /goalify <voice text>.")
        if _is_cancel(text):
            clear_pending(self.session_id)
            return GoalifyResult("cancel", "Goalify cancelled. No goal fired.")
        edit = _extract_edit(text)
        if edit:
            field, value = edit
            state.fields[field] = value
            state.sources[field] = "user"
            state.status = "proposed"
            state.rendered_prompt = render_prompt(state.fields, state.cwd)
            save_pending(state)
            return GoalifyResult("propose", render_proposal(state))
        if state.status == "proposed" and _is_yes(text):
            state.rendered_prompt = state.rendered_prompt or render_prompt(state.fields, state.cwd)
            _append_audit(state, "locked")
            clear_pending(self.session_id)
            return GoalifyResult(
                "execute",
                "Goal locked. Engaging goal-loop now.\n\n" + state.rendered_prompt,
                locked_prompt=state.rendered_prompt,
            )

        # Clarification reply or non-edit feedback: reparse combined text. This
        # keeps voice replies flexible while still requiring explicit lock.
        combined = f"{state.raw_input}\n{text}"
        raw_fields, raw_sources = parse_raw_input(combined, state.cwd)
        fields = dict(state.fields)
        sources = dict(state.sources)
        fields.update(raw_fields)
        sources.update({k: "clarified" for k in raw_sources})
        # If criteria are still missing, use measurable sentences from the reply.
        idx = 1
        for field in ("CRITERION_1", "CRITERION_2", "CRITERION_3"):
            if _is_measurable(fields.get(field, "")):
                idx += 1
        for sent in _split_sentences(text):
            if idx > 3:
                break
            if _is_measurable(sent):
                field = f"CRITERION_{idx}"
                fields[field] = _clean_one_line(sent)
                sources[field] = "clarified"
                idx += 1
        state.raw_input = combined
        state.fields = fields
        state.sources = sources
        state.clarify_turns += 1
        gaps = gaps_for(fields)
        if gaps:
            save_pending(state)
            return GoalifyResult("clarify", render_clarify(combined, fields, gaps))
        state.status = "proposed"
        state.rendered_prompt = render_prompt(fields, state.cwd)
        save_pending(state)
        return GoalifyResult("propose", render_proposal(state))


def ensure_report() -> Path:
    home = goalify_home()
    home.mkdir(parents=True, exist_ok=True)
    path = home / "goalify-hermes-report.md"
    if not path.exists():
        path.write_text(
            "# Goalify Hermes Report\n\n"
            "Goalify is installed as a Hermes-native wrapper around `/goal`.\n\n"
            "## Paths\n"
            "- Config/defaults: `~/.hermes/goalify/defaults.yml`\n"
            "- Audit trail: `~/.hermes/goalify/runs.jsonl`\n"
            "- Pending state: Hermes SessionDB state_meta key `goalify:<session_id>`\n\n"
            "## Triggers\n"
            "- `/goalify <voice text>`\n"
            "- `$goalify <voice text>` in CLI text input\n"
            "- `goalify this: <voice text>` in CLI text input\n\n"
            "## Reply flow\n"
            "Natural language replies are supported: `yes go ahead`, "
            "`change the audience to product engineers`, `cancel this`.\n\n"
            "## Hermes-specific notes\n"
            "Goalify requires an explicit lock before it fires the existing `/goal` loop. "
            "It uses the safer Hermes wording: use the right tools, not every tool.\n",
            encoding="utf-8",
        )
    return path
