#!/usr/bin/env python3
"""Targeted active-task retest for Spark using the exact Hermes wording."""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from run_benchmark import make_turns

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts"
OUT.mkdir(exist_ok=True)

MODELS = [
    ("baseline-gpt-5.5-active-task", "gpt-5.5"),
    ("spark-gpt-5.3-codex-spark-active-task", "gpt-5.3-codex-spark"),
]

turns = make_turns()
prompt = f'''You are a summarization agent creating a context checkpoint. Treat the conversation turns below as source material for a compact record of prior work. Produce only the structured summary; do not add a greeting, preamble, or prefix. Write the summary in the same language the user was using in the conversation — do not translate or switch to English. NEVER include API keys, tokens, passwords, secrets, credentials, or connection strings in the summary — replace any that appear with [REDACTED]. Note that the user had credentials present, but do not preserve their values.

Create a structured checkpoint summary for the conversation after earlier turns are compacted. The summary should preserve enough detail for continuity without re-reading the original turns.

TURNS TO SUMMARIZE:
{turns}

Use this exact structure:

## Active Task
[THE SINGLE MOST IMPORTANT FIELD. Copy the user's most recent request or
task assignment verbatim — the exact words they used. If multiple tasks
were requested and only some are done, list only the ones NOT yet completed.
Continuation should pick up exactly here. Example:
"User asked: 'Now refactor the auth module to use JWT instead of sessions'"
If no outstanding task exists, write "None."]

## Goal
[What the user is trying to accomplish overall]

## Constraints & Preferences
[User preferences, coding style, constraints, important decisions]

## Completed Actions
[Numbered list of concrete actions taken — include tool used, target, and outcome.
Format each as: N. ACTION target — outcome [tool: name]
Example:
1. READ config.py:45 — found `==` should be `!=` [tool: read_file]
2. PATCH config.py:45 — changed `==` to `!=` [tool: patch]
3. TEST `pytest tests/` — 3/50 failed: test_parse, test_validate, test_edge [tool: terminal]
Be specific with file paths, commands, line numbers, and results.]

## Active State
[Current working state — include:
- Working directory and branch (if applicable)
- Modified/created files with brief note on each
- Test status (X/Y passing)
- Any running processes or servers
- Environment details that matter]

## In Progress
[Work currently underway — what was being done when compaction fired]

## Blocked
[Any blockers, errors, or issues not yet resolved. Include exact error messages.]

## Key Decisions
[Important technical decisions and WHY they were made]

## Resolved Questions
[Questions the user asked that were ALREADY answered — include the answer so it is not repeated]

## Pending User Asks
[Questions or requests from the user that have NOT yet been answered or fulfilled. If none, write "None."]

## Relevant Files
[Files read, modified, or created — with brief note on each]

## Remaining Work
[What remains to be done — framed as context, not instructions]

## Critical Context
[Any specific values, error messages, configuration details, or data that would be lost without explicit preservation. NEVER include API keys, tokens, passwords, or credentials — write [REDACTED] instead.]

Target ~2500 tokens. Be CONCRETE — include file paths, command outputs, error messages, line numbers, and specific values. Avoid vague descriptions like "made some changes" — say exactly what changed.

Write only the summary body. Do not include any preamble or prefix.'''

(OUT / "active_task_retest_prompt.txt").write_text(prompt, encoding="utf-8")

section_re = re.compile(r"^## .*$", re.M)

def active_task(text: str) -> str:
    m = re.search(r"^## Active Task\s*$", text, re.M)
    if not m:
        return ""
    n = section_re.search(text, m.end())
    return text[m.end(): n.start() if n else len(text)].strip()

results = []
for label, model in MODELS:
    start = time.time()
    proc = subprocess.run([
        "hermes", "chat", "-Q", "--provider", "openai-codex", "-m", model,
        "--toolsets", "safe", "-q", prompt,
    ], text=True, capture_output=True, timeout=480)
    elapsed = round(time.time() - start, 2)
    out = proc.stdout.strip()
    path = OUT / f"{label}.md"
    path.write_text(out + "\n", encoding="utf-8")
    task = active_task(out)
    ok = all(re.search(p, task, re.I) for p in [r"gpt-5\.3-codex-spark", r"test|testing|benchmark|vet", r"compression"])
    bad = bool(re.search(r"Create a structured checkpoint summary", task, re.I))
    results.append({
        "label": label, "model": model, "returncode": proc.returncode, "elapsed_s": elapsed,
        "active_task_ok": bool(ok and not bad), "active_task_section": task[:800],
        "output_path": str(path), "stderr_tail": proc.stderr[-800:],
    })

(OUT / "active_task_retest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
