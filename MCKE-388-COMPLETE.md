Files changed:
- gateway/platforms/telegram.py
- tests/gateway/test_telegram_approval_buttons.py
- MCKE-388-COMPLETE.md

Tests run:
- `python -m pytest tests/gateway/test_telegram_approval_buttons.py -q` — FAIL before collection, exit 4. Active pytest rejected configured addopts `--timeout=30 --timeout-method=signal`.
- `source $HOME/.hermes/hermes-agent/venv/bin/activate && python -m pytest tests/gateway/test_telegram_approval_buttons.py -q` — FAIL before collection, exit 4, same missing pytest-timeout/addopts issue.
- `source $HOME/.hermes/hermes-agent/venv/bin/activate && python -m pytest tests/gateway/test_telegram_approval_buttons.py -q -o addopts=''` — PASS, 24 passed.
- `python -m py_compile gateway/platforms/telegram.py` — PASS.
- `source $HOME/.hermes/hermes-agent/venv/bin/activate && python -m py_compile gateway/platforms/telegram.py` — PASS.
- `rg -n "[ \\t]+$" gateway/platforms/telegram.py tests/gateway/test_telegram_approval_buttons.py` — found pre-existing trailing whitespace in `gateway/platforms/telegram.py`; no cleanup attempted outside this task's approval-card area.

Follow-up for orchestrator:
- Rerun the exact focused pytest command in an environment with the pytest-timeout plugin available, or override the stale addopts as above.
