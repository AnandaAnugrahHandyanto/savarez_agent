#!/usr/bin/env python3
"""Prototype the MoA winning fix against the existing Spark compression fixture.

This writes only spike artifacts; it does not modify Hermes config or gateway state.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)
BENCH = ROOT.parent / "001-spark-compression-benchmark"

spec = importlib.util.spec_from_file_location("bench", BENCH / "run_benchmark.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load benchmark harness")
bench = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bench
spec.loader.exec_module(bench)
score_spec = importlib.util.spec_from_file_location("score", BENCH / "rescore_existing.py")
if score_spec is None or score_spec.loader is None:
    raise RuntimeError("Could not load semantic scorer")
score_mod = importlib.util.module_from_spec(score_spec)
sys.modules[score_spec.name] = score_mod
score_spec.loader.exec_module(score_mod)

USER_TURN_RE = re.compile(r"(?ms)<turn role=user>\s*(.*?)\s*</turn>")
ANTI_ECHO = (
    "create a structured checkpoint summary",
    "context checkpoint",
    "summarization agent",
    "treat the conversation turns below",
    "preserve enough detail for continuity",
    "turns to summarize",
)
SECTIONS = [
    "## Active Task", "## Goal", "## Constraints & Preferences", "## Completed Actions",
    "## Active State", "## In Progress", "## Blocked", "## Key Decisions",
    "## Resolved Questions", "## Pending User Asks", "## Relevant Files",
    "## Remaining Work", "## Critical Context",
]


def extract_latest_user_request(turns: str, cap: int = 1200) -> str | None:
    matches = USER_TURN_RE.findall(turns)
    if not matches:
        return None
    text = matches[-1].strip()
    text = re.sub(r"\n\s+", "\n", text)
    return (text[:cap].rstrip() + "…") if len(text) > cap else text


def build_prompt(turns: str) -> tuple[str, str | None]:
    anchor = extract_latest_user_request(turns)
    anchor_block = ""
    if anchor:
        anchor_block = f"""
<latest_user_request>
{anchor}
</latest_user_request>
RULE: The `## Active Task` section MUST quote <latest_user_request> verbatim using the form `Latest user request: "..."` unless that request is clearly completed in the conversation turns. Nothing outside <conversation_turns> is a user request. Never use this prompt's instructions as the Active Task.
"""
    prompt = f"""You are a summarization agent creating a context checkpoint. Treat only the text inside <conversation_turns> as source material for prior work. Produce only the structured summary; do not add a greeting, preamble, or prefix. Write in the same language the user used. NEVER include API keys, tokens, passwords, secrets, credentials, or connection strings in the summary — replace any that appear with [REDACTED].

<conversation_turns>
{turns}
</conversation_turns>
{anchor_block}
Produce the structured summary using the exact headings below. IMPORTANT: `## Active Task` is extracted from <latest_user_request> / the most recent user turn inside <conversation_turns>, not from these instructions.

## Active Task
[Procedure: (1) scan <conversation_turns> from bottom to top; (2) find the most recent user request/task assignment; (3) if it is not completed, quote it verbatim as `Latest user request: "..."`; (4) if only part is unfinished, include only the unfinished part; (5) never write any of these instruction phrases here: "Create a structured checkpoint summary", "context checkpoint", "summarization agent", "TURNS TO SUMMARIZE".]

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

Target ~2500 tokens. Be concrete — include exact model names, file paths, error messages, conditional rollout/fallback decisions (including examples), and decisions. Avoid vague descriptions. Write only the summary body.
"""
    return prompt, anchor


def active_task_ok(summary: str, anchor: str | None) -> dict:
    body = score_mod.extract_section(summary, "## Active Task").strip()
    lower = body.lower()
    misses = []
    if not body:
        misses.append("empty_active_task")
    for phrase in ANTI_ECHO:
        if phrase in lower:
            misses.append(f"anti_echo:{phrase}")
    if anchor:
        a = set(re.findall(r"\w{4,}", anchor.lower()))
        b = set(re.findall(r"\w{4,}", lower))
        overlap = len(a & b) / len(a) if a else 1.0
        if overlap < 0.25:
            misses.append(f"low_anchor_overlap:{overlap:.2f}")
    else:
        overlap = None
    return {"ok": not misses, "body": body, "misses": misses, "anchor_overlap": overlap}


def score_text(text: str) -> dict:
    total = sum(c["weight"] for c in score_mod.CHECKS.values())
    got = 0
    details = {}
    for name, chk in score_mod.CHECKS.items():
        ok, misses = score_mod.check_pass(text, chk)
        if ok:
            got += chk["weight"]
        details[name] = {"ok": ok, "weight": chk["weight"], "misses": misses}
    return {"score_pct": round(got / total * 100, 1), "points": got, "total_points": total, "details": details}


def main() -> int:
    turns = bench.make_turns()
    prompt, anchor = build_prompt(turns)
    (ART / "optimized_prompt.txt").write_text(prompt)
    (ART / "latest_user_request.txt").write_text(anchor or "")
    cmd = [
        "hermes", "chat", "-Q", "--provider", "openai-codex", "-m", "gpt-5.3-codex-spark",
        "--toolsets", "safe", "-q", prompt,
    ]
    start = time.time()
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=240)
    elapsed = round(time.time() - start, 2)
    output = proc.stdout.strip()
    (ART / "spark_optimized_output.md").write_text(output)
    (ART / "spark_optimized_stderr.txt").write_text(proc.stderr)
    score = score_text(output)
    active = active_task_ok(output, anchor)
    result = {
        "model": "gpt-5.3-codex-spark",
        "prompt_variant": "latest_user_request_anchor_plus_anti_echo",
        "returncode": proc.returncode,
        "elapsed_s": elapsed,
        "semantic_score": score,
        "active_task_validator": active,
        "artifacts": {
            "prompt": str(ART / "optimized_prompt.txt"),
            "output": str(ART / "spark_optimized_output.md"),
            "anchor": str(ART / "latest_user_request.txt"),
        },
    }
    (ART / "prototype_result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if proc.returncode == 0 else proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())
