# Rule: agent-loop

Paths: `run_agent.py`, `model_tools.py`, `tools/`, `toolsets.py`.

DO NOT:
- Never edit AIAgent core loop without integration tests.
- Never modify tool-call schema without coordinated upstream PR.

Architecture Notes: prompt caching and toolset stability are load-bearing.

Thresholds: any core-loop change requires `scripts/run_tests.sh` and `ruff check .`.

Key Files: `run_agent.py`, `model_tools.py`, `toolsets.py`, `tools/registry.py`.
