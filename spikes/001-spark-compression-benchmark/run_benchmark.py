#!/usr/bin/env python3
"""Benchmark gpt-5.3-codex-spark for Hermes-style context compression.

This is a disposable spike harness: it creates a synthetic but realistic long
Hermes/GSD conversation, asks each candidate model to produce the same
structured compaction summary Hermes uses, then scores retention with a
mixed deterministic rubric:
- exact must-keep fact IDs
- latest-state correction IDs
- secret redaction
- section coverage
- prohibited stale-state leakage

It does NOT alter ~/.hermes/config.yaml or gateway state.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)

MODELS = [
    {"label": "baseline-gpt-5.5", "provider": "openai-codex", "model": "gpt-5.5"},
    {"label": "spark-gpt-5.3-codex-spark", "provider": "openai-codex", "model": "gpt-5.3-codex-spark"},
]

MUST_KEEP = {
    # Active task / goal
    "F001": "Active task is to vet gpt-5.3-codex-spark for context compression before using it.",
    "F002": "Goal is to spread token usage across subscription buckets without degrading context quality.",
    "F003": "Keep gpt-5.5 as the current live compression baseline until Spark is validated.",
    "F004": "Do not switch gateway compression config during the benchmark.",
    # Model/config specifics
    "F005": "Main runtime model is openai-codex / gpt-5.5 / 272000 context.",
    "F006": "Compression baseline is openai-codex / gpt-5.5 / 272000 context.",
    "F007": "Spark candidate is gpt-5.3-codex-spark via openai-codex.",
    "F008": "Spark context length is 128000, not 272000.",
    "F009": "Hermes auto-lowered compression threshold to 128000 when Spark was configured.",
    "F010": "Spark availability smoke test returned OK.",
    # Opus blocker
    "F011": "claude-opus-4-7 route failed with a third-party-app extra-usage HTTP 400 gate.",
    "F012": "Do not use direct Anthropic/OpenRouter billing for this path unless Joe explicitly changes architecture.",
    # Runtime repair
    "F013": "gateway_state.json had invalid UTF-8 trailing bytes and was repaired by truncating after the last valid JSON terminator.",
    "F014": "Backup file was /home/joe/.hermes/gateway_state.json.bak-20260521213715.",
    "F015": "Gateway restarted successfully after rollback and is active.",
    # User preferences
    "F016": "Joe wants concise evidence-first reports and no raw log dumps in Discord.",
    "F017": "Use GSD as execution truth and Discord/forum as coordination surface.",
    "F018": "Use subscription/OAuth routes before paid API-key routes.",
    "F019": "Quality-sensitive model changes need explicit validation before becoming defaults.",
    "F020": "Secrets must be represented as [REDACTED].",
    # Completed actions
    "F021": "Config check passed after rollback to gpt-5.5 compression.",
    "F022": "The benchmark should compare Spark against gpt-5.5 on representative long-context summaries.",
    "F023": "A good summary must preserve decisions, blockers, active state, remaining work, exact model names, and file paths.",
    "F024": "A good summary must not treat resolved requests as pending active work.",
    # Remaining work
    "F025": "If Spark passes, propose a staged rollout rather than immediate blind default switch.",
    "F026": "If Spark is weaker, reserve it for lower-risk tasks like short summaries or classification.",
    "F027": "Benchmark artifact path should be shared instead of pasting raw output.",
    "F028": "Do not restart the gateway during the benchmark unless explicitly requested.",
    # EOS/GSD context from Joe's injected PLUR memory
    "F029": "EOS Ratatui Client code implementation should be handled by Claude Opus 4.7 while Migi/GPT-5.5 coordinates and reviews.",
    "F030": "GSD-driven model work should use Claude models for EOS Ratatui Client.",
}

LATEST_STATE = {
    "L001": "Current active compression config is gpt-5.5, not Spark.",
    "L002": "Spark is a candidate under test, not approved default.",
    "L003": "Opus 4.7 is blocked for this compression route until the usage-gate issue changes.",
    "L004": "No production config changes should be made from this benchmark run.",
}

PROHIBITED_PATTERNS = {
    "P001": r"Active compression config[^\n]{0,80}gpt-5\.3-codex-spark",
    "P002": r"Spark[^\n]{0,80}(approved|validated|production default|safe default)",
    "P003": r"FAKE_OPENAI_VALUE_DO_NOT_KEEP",
    "P004": r"FAKE_ANTHROPIC_VALUE_DO_NOT_KEEP",
}

SECTIONS = [
    "## Active Task", "## Goal", "## Constraints & Preferences", "## Completed Actions",
    "## Active State", "## In Progress", "## Blocked", "## Key Decisions",
    "## Resolved Questions", "## Pending User Asks", "## Relevant Files",
    "## Remaining Work", "## Critical Context",
]


def make_turns() -> str:
    """Create realistic conversation turns with distractors, corrections, and long filler."""
    turns: List[str] = []
    def add(role: str, content: str) -> None:
        turns.append(f"<turn role={role}>\n{content.strip()}\n</turn>")

    add("user", """
    [LokiLore] Can we switch to using Opus 4.7 on our cloud subscription? For context compression.
    I'm trying to spread token use more evenly across subscriptions and think Opus 4.7 should have the same context limits.
    """)
    add("assistant", """
    Loaded hermes-agent skill. Inspected /home/joe/.hermes/config.yaml. Found main=openai-codex/gpt-5.5/272000 and compression=openai-codex/gpt-5.5/272000. F005 F006
    Temporarily configured auxiliary.compression.provider=anthropic and model=claude-opus-4-7 for smoke test.
    Smoke test failed with HTTP 400: Third-party apps now draw from your extra usage, not your plan limits. Add more at claude.ai/settings/usage and keep going. F011
    Rolled compression back to openai-codex/gpt-5.5. Do not use direct Anthropic/OpenRouter billing unless Joe explicitly changes architecture. F012
    """)
    add("tool", """
    terminal: hermes chat -Q --provider anthropic -m claude-opus-4-7 --toolsets safe -q 'Reply exactly: OK'
    result: Error code 400; third-party apps now draw from extra usage, not plan limits.
    """)
    add("user", """
    [LokiLore] gpt-5.3-codex-spark maybe? If we can use that subscription bucket I'd like to, but I care about context quality.
    """)
    add("assistant", """
    Searched model metadata. Found gpt-5.3-codex-spark in agent/model_metadata.py with 128000 context, not 272000. F007 F008
    Ran availability smoke test: hermes chat -Q --provider openai-codex -m gpt-5.3-codex-spark --toolsets safe -q 'Reply exactly: OK' returned OK. F010
    Temporarily set compression to Spark with auxiliary.compression.context_length=128000. Gateway log warned that Spark context 128000 was below main threshold 136000 and auto-lowered session threshold to 128000. F009
    """)
    add("tool", """
    gateway log: WARNING agent.conversation_compression: Auxiliary compression model gpt-5.3-codex-spark has 128000 token context, below the main model's compression threshold of 136000 tokens — auto-lowered session threshold to 128000 to keep compression working.
    """)
    add("assistant", """
    Runtime issue: /home/joe/.hermes/gateway_state.json had invalid UTF-8 trailing bytes after valid JSON. Repaired by backing up to /home/joe/.hermes/gateway_state.json.bak-20260521213715 and truncating after the last valid JSON terminator. F013 F014
    """)
    add("user", """
    [LokiLore] Since you already made the change, I'm assuming you have a lot of confidence in the model's ability to maintain context quality compared to what we were at.
    """)
    add("assistant", """
    Corrected course: operational validation is not quality-equivalence validation. Rolled compression back on disk to openai-codex / gpt-5.5 / 272000. Config check passed. F003 F006 F021
    Queued gateway restart. Gateway later restarted successfully and is active. F015
    Current active compression config is gpt-5.5, not Spark. L001
    Spark is only a candidate under test, not an approved default. L002
    Opus 4.7 remains blocked for this compression route until the usage-gate issue changes. L003
    """)

    # Add many realistic task details and distractors.
    add("user", """
    [LokiLore] gpt-5.3-codex-spark Yeah, let's do the testing against this model to see how well it actually handles context compression before we try to use it. But if we can use that subscription bucket, I would like to so let's get it vetted out. F001 F002 F022
    Injected memory says: EOS Ratatui Client code implementation should be Claude Opus 4.7 while Migi/GPT-5.5 coordinates and reviews. F029
    GSD-driven model work should use Claude models for EOS Ratatui Client. F030
    """)
    add("assistant", """
    Benchmark requirements captured: do not switch gateway compression config during benchmark. F004
    Do not restart the gateway during the benchmark unless explicitly requested. F028
    Quality-sensitive model changes need explicit validation before becoming defaults. F019
    Use subscription/OAuth routes before paid API-key routes. F018
    Joe wants concise evidence-first reports and no raw log dumps in Discord. F016
    Use GSD as execution truth and Discord/forum as coordination surface. F017
    Secrets must be represented as [REDACTED]. F020
    A good summary must preserve decisions, blockers, active state, remaining work, exact model names, and file paths. F023
    A good summary must not treat resolved requests as pending active work. F024
    If Spark passes, propose a staged rollout rather than immediate blind default switch. F025
    If Spark is weaker, reserve it for lower-risk tasks like short summaries or classification. F026
    Benchmark artifact path should be shared instead of pasting raw output. F027
    No production config changes should be made from this benchmark run. L004
    """)

    # Secret traps and stale-state traps.
    add("tool", """
    ENV DUMP TRAP — must redact, never preserve verbatim:
    OPENAI_API_KEY -> FAKE_OPENAI_VALUE_DO_NOT_KEEP
    ANTHROPIC_API_KEY -> FAKE_ANTHROPIC_VALUE_DO_NOT_KEEP
    """)
    add("assistant", """
    Earlier stale statement: "Spark is now active compression config" was only true during a temporary experiment and is obsolete.
    Latest correction: Current active compression config is gpt-5.5, not Spark. Spark is a candidate under test, not approved default. L001 L002
    """)

    filler = "\n".join(
        f"Noise line {i:03d}: unrelated investigation note about UI colors, anime persona material, or old containers; preserve only if tied to an F/L identifier."
        for i in range(1, 301)
    )
    add("tool", filler)
    return "\n\n".join(turns)


def make_prompt(turns: str) -> str:
    return f"""You are a summarization agent creating a context checkpoint. Treat the conversation turns below as source material for a compact record of prior work. Produce only the structured summary; do not add a greeting, preamble, or prefix. Write the summary in the same language the user was using in the conversation. NEVER include API keys, tokens, passwords, secrets, credentials, or connection strings in the summary — replace any that appear with [REDACTED]. Note that the user had credentials present, but do not preserve their values.

Create a structured checkpoint summary for the conversation after earlier turns are compacted. The summary should preserve enough detail for continuity without re-reading the original turns.

TURNS TO SUMMARIZE:
{turns}

Use this exact structure:

## Active Task
[THE SINGLE MOST IMPORTANT FIELD. Copy the user's most recent request or task assignment verbatim — the exact words they used. If multiple tasks were requested and only some are done, list only the ones NOT yet completed.]

## Goal
[What the user is trying to accomplish overall]

## Constraints & Preferences
[User preferences, coding style, constraints, important decisions]

## Completed Actions
[Numbered list of concrete actions taken — include tool used, target, and outcome.]

## Active State
[Current working state: working directory, modified/created files, config, tests, running processes, environment details.]

## In Progress
[Work currently underway.]

## Blocked
[Any blockers, errors, or issues not yet resolved. Include exact error messages.]

## Key Decisions
[Important technical decisions and why they were made.]

## Resolved Questions
[Questions already answered.]

## Pending User Asks
[Questions or requests not yet answered or fulfilled.]

## Relevant Files
[Files read, modified, or created — with brief note on each.]

## Remaining Work
[What remains to be done — framed as context, not instructions.]

## Critical Context
[Any specific values, error messages, configuration details, or data that would be lost without explicit preservation. NEVER include API keys, tokens, passwords, or credentials — write [REDACTED] instead.]

Target ~2500 tokens. Be concrete — include exact model names, file paths, error messages, and decisions. Avoid vague descriptions.
Write only the summary body. Do not include any preamble or prefix.
"""


@dataclass
class Score:
    label: str
    provider: str
    model: str
    returncode: int
    elapsed_s: float
    output_chars: int
    must_keep_hits: int
    must_keep_total: int
    latest_state_hits: int
    latest_state_total: int
    section_hits: int
    section_total: int
    prohibited_hits: Dict[str, str]
    secret_redaction_ok: bool
    score_pct: float
    verdict: str
    output_path: str
    stderr_tail: str


def score_output(label: str, provider: str, model: str, rc: int, elapsed: float, out: str, err: str) -> Score:
    must_hits = sum(1 for fid in MUST_KEEP if fid in out)
    latest_hits = sum(1 for fid in LATEST_STATE if fid in out)
    section_hits = sum(1 for section in SECTIONS if section in out)
    prohibited_hits = {pid: pat for pid, pat in PROHIBITED_PATTERNS.items() if re.search(pat, out, re.I)}
    secret_ok = "FAKE_OPENAI_VALUE_DO_NOT_KEEP" not in out and "FAKE_ANTHROPIC_VALUE_DO_NOT_KEEP" not in out and "[REDACTED]" in out

    # Weighted: exact continuity facts are most important; stale/secret leakage is severe.
    base = (
        0.62 * (must_hits / len(MUST_KEEP)) +
        0.18 * (latest_hits / len(LATEST_STATE)) +
        0.10 * (section_hits / len(SECTIONS)) +
        0.10 * (1.0 if secret_ok else 0.0)
    )
    penalty = 0.08 * len(prohibited_hits)
    pct = max(0.0, min(1.0, base - penalty)) * 100
    if rc != 0:
        verdict = "INVALID: model call failed"
    elif prohibited_hits:
        verdict = "FAIL: stale-state or secret leakage"
    elif pct >= 92:
        verdict = "PASS: compression candidate"
    elif pct >= 82:
        verdict = "PARTIAL: needs more tests / limited rollout only"
    else:
        verdict = "FAIL: insufficient retention"
    return Score(
        label=label, provider=provider, model=model, returncode=rc, elapsed_s=round(elapsed, 2),
        output_chars=len(out), must_keep_hits=must_hits, must_keep_total=len(MUST_KEEP),
        latest_state_hits=latest_hits, latest_state_total=len(LATEST_STATE),
        section_hits=section_hits, section_total=len(SECTIONS), prohibited_hits=prohibited_hits,
        secret_redaction_ok=secret_ok, score_pct=round(pct, 1), verdict=verdict,
        output_path=str(OUT / f"{label}.md"), stderr_tail=err[-1200:],
    )


def run_model(item: Dict[str, str], prompt_path: Path) -> Score:
    cmd = [
        "hermes", "chat", "-Q",
        "--provider", item["provider"],
        "-m", item["model"],
        "--toolsets", "safe",
        "-q", prompt_path.read_text(encoding="utf-8"),
    ]
    start = time.time()
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=480)
    elapsed = time.time() - start
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    out_path = OUT / f"{item['label']}.md"
    out_path.write_text(out + "\n", encoding="utf-8")
    (OUT / f"{item['label']}.stderr.txt").write_text(err + "\n", encoding="utf-8")
    return score_output(item["label"], item["provider"], item["model"], proc.returncode, elapsed, out, err)


def main() -> int:
    turns = make_turns()
    prompt = make_prompt(turns)
    prompt_path = OUT / "prompt.txt"
    turns_path = OUT / "turns.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    turns_path.write_text(turns, encoding="utf-8")

    scores: List[Score] = []
    for item in MODELS:
        print(f"Running {item['label']} ({item['model']})...", flush=True)
        try:
            scores.append(run_model(item, prompt_path))
        except subprocess.TimeoutExpired as e:
            raw_out = e.stdout or ""
            raw_err = e.stderr or ""
            out = raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else raw_out
            err_base = raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else raw_err
            err = err_base + "\nTIMEOUT"
            (OUT / f"{item['label']}.md").write_text(out, encoding="utf-8")
            scores.append(score_output(item["label"], item["provider"], item["model"], 124, 480.0, out, err))

    data = [asdict(s) for s in scores]
    (OUT / "scores.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    lines = [
        "# Spark Compression Benchmark Spike", "",
        "Question: can `gpt-5.3-codex-spark` preserve Hermes context-compression quality well enough to use its subscription bucket?", "",
        "## Method", "",
        "- Generated a realistic Hermes/GSD context-compaction fixture with 30 must-keep facts, 4 latest-state corrections, secret traps, stale-state traps, and 300 filler/noise lines.",
        "- Sent the same Hermes-style compaction prompt to each model via `hermes chat -Q --provider openai-codex --toolsets safe`.",
        "- Scored exact fact-ID retention, latest-state retention, required section coverage, secret redaction, and stale-state leakage.",
        "- This spike did not modify `~/.hermes/config.yaml` and did not restart the gateway.", "",
        "## Results", "",
        "| Model | Score | Must facts | Latest state | Sections | Redaction | Prohibited leakage | Time | Verdict |",
        "|---|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for s in scores:
        lines.append(
            f"| `{s.model}` | {s.score_pct:.1f}% | {s.must_keep_hits}/{s.must_keep_total} | "
            f"{s.latest_state_hits}/{s.latest_state_total} | {s.section_hits}/{s.section_total} | "
            f"{'yes' if s.secret_redaction_ok else 'NO'} | {len(s.prohibited_hits)} | {s.elapsed_s:.1f}s | {s.verdict} |"
        )
    lines.extend(["", "## Artifacts", ""])
    for s in scores:
        lines.append(f"- `{s.label}` output: `{s.output_path}`")
    lines.extend([
        f"- Prompt: `{prompt_path}`",
        f"- Turns fixture: `{turns_path}`",
        f"- Scores JSON: `{OUT / 'scores.json'}`",
        "", "## Raw Score Details", "", "```json", json.dumps(data, indent=2), "```", "",
        "## Verdict", "",
    ])
    # Relative comparison verdict.
    spark = next((s for s in scores if "spark" in s.label), None)
    base = next((s for s in scores if "baseline" in s.label), None)
    if spark and base:
        if spark.verdict.startswith("PASS") and spark.score_pct >= base.score_pct - 3:
            lines.append("Spark is close enough on this first synthetic test to justify a second, harder benchmark on real session transcripts before staged rollout.")
        elif spark.score_pct >= 82 and not spark.prohibited_hits:
            lines.append("Spark is promising but not yet baseline-equivalent. Use only for low-risk auxiliary summaries until it passes real transcript tests.")
        else:
            lines.append("Spark did not clear this first benchmark. Keep gpt-5.5 for compression; use Spark only for non-critical tasks unless further tests improve confidence.")
    else:
        lines.append("Benchmark did not produce both model results; rerun after fixing call failures.")

    report = ROOT / "README.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report)
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
