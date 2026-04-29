# Rule: gateway

Paths: `gateway/`, `gateway/platforms/`, `tui_gateway/`.

DO NOT:
- Never delete a platform adapter without operator approval.
- Smoke-test every enabled platform after adapter changes.

Architecture Notes: base adapter and runner guards both control in-flight message behavior.

Thresholds: platform changes require targeted gateway tests.

Key Files: `gateway/run.py`, `gateway/session.py`, `gateway/platforms/base.py`.
