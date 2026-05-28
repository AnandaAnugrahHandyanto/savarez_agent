# header_timeout_seconds Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add per-provider `header_timeout_seconds` config to control how long Hermes waits for response headers (time-to-first-byte), separate from the overall `request_timeout_seconds`.

**Architecture:** Mirror the existing `request_timeout_seconds` / `stale_timeout_seconds` pattern. New `get_provider_header_timeout()` in `hermes_cli/timeouts.py`. Wire it into OpenAI client creation as `httpx.Timeout(read=...)` and into Anthropic client as the `read` component of the existing `Timeout` object. When unset, behavior is unchanged.

**Tech Stack:** Python, httpx, openai SDK, anthropic SDK, pytest

---

### Task 1: Add `get_provider_header_timeout()` to timeouts.py

**Objective:** New config reader function for `header_timeout_seconds`, following the exact pattern of `get_provider_request_timeout()`.

**Files:**
- Modify: `hermes_cli/timeouts.py`
- Test: `tests/hermes_cli/test_timeouts.py`

**Step 1: Write failing tests**

Add to `tests/hermes_cli/test_timeouts.py`:

```python
from hermes_cli.timeouts import (
    get_provider_request_timeout,
    get_provider_stale_timeout,
    get_provider_header_timeout,
)

def test_provider_header_timeout(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, """\
        providers:
          ollama-local:
            header_timeout_seconds: 600
    """)
    assert get_provider_header_timeout("ollama-local") == 600.0


def test_model_header_timeout_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, """\
        providers:
          openrouter:
            header_timeout_seconds: 30
            models:
              openai/gpt-4o-mini:
                header_timeout_seconds: 10
    """)
    assert get_provider_header_timeout("openrouter", "openai/gpt-4o-mini") == 10.0


def test_header_timeout_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, """\
        providers:
          openai:
            request_timeout_seconds: 300
    """)
    assert get_provider_header_timeout("openai", "gpt-4o") is None
    assert get_provider_header_timeout("missing-provider") is None


def test_invalid_header_timeout_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, """\
        providers:
          ollama:
            header_timeout_seconds: "slow"
    """)
    assert get_provider_header_timeout("ollama") is None
```

**Step 2: Run tests to verify failure**

Run: `cd /home/ubuntu/.hermes/hermes-agent && python -m pytest tests/hermes_cli/test_timeouts.py -v -k header 2>&1`
Expected: FAIL — `ImportError: cannot import name 'get_provider_header_timeout'`

**Step 3: Implement `get_provider_header_timeout()`**

Add to `hermes_cli/timeouts.py` after `get_provider_request_timeout`:

```python
def get_provider_header_timeout(
    provider_id: str, model: str | None = None
) -> float | None:
    """Return a configured provider header timeout in seconds, if any.

    This controls how long to wait for response headers (time-to-first-byte)
    before timing out, separate from the overall request timeout.
    """
    if not provider_id:
        return None

    try:
        from hermes_cli.config import load_config_readonly
        config = load_config_readonly()
    except Exception:
        return None

    providers = config.get("providers", {}) if isinstance(config, dict) else {}
    provider_config = (
        providers.get(provider_id, {}) if isinstance(providers, dict) else {}
    )
    if not isinstance(provider_config, dict):
        return None

    model_config = _get_model_config(provider_config, model)
    if model_config is not None:
        timeout = _coerce_timeout(model_config.get("header_timeout_seconds"))
        if timeout is not None:
            return timeout

    return _coerce_timeout(provider_config.get("header_timeout_seconds"))
```

**Step 4: Run tests to verify pass**

Run: `cd /home/ubuntu/.hermes/hermes-agent && python -m pytest tests/hermes_cli/test_timeouts.py -v -k header 2>&1`
Expected: 4 passed

**Step 5: Commit**

```bash
git add hermes_cli/timeouts.py tests/hermes_cli/test_timeouts.py
git commit -m "feat: add get_provider_header_timeout() config reader"
```

---

### Task 2: Add `header_timeout_seconds` to config validation allowlist

**Objective:** Prevent the "unknown config keys" warning when users set `header_timeout_seconds`.

**Files:**
- Modify: `hermes_cli/config.py:3239-3245`

**Step 1: Add to `_KNOWN_KEYS` set**

In `hermes_cli/config.py` line 3239, add `"header_timeout_seconds"` to the `_KNOWN_KEYS` set:

```python
    _KNOWN_KEYS = {
        "name", "api", "url", "base_url", "api_key", "key_env", "api_key_env",
        "api_mode", "transport", "model", "default_model", "models",
        "context_length", "rate_limit_delay",
        "request_timeout_seconds", "stale_timeout_seconds", "header_timeout_seconds",
        "discover_models", "extra_body",
    }
```

**Step 2: Verify no test breakage**

Run: `cd /home/ubuntu/.hermes/hermes-agent && python -m pytest tests/hermes_cli/test_provider_config_validation.py -v 2>&1`
Expected: All existing tests pass.

**Step 3: Commit**

```bash
git add hermes_cli/config.py
git commit -m "feat: add header_timeout_seconds to provider config allowlist"
```

---

### Task 3: Wire header timeout into OpenAI client creation

**Objective:** When `header_timeout_seconds` is configured, build an `httpx.Timeout` object with separate `read` (header) and overall timeouts instead of passing a flat float.

**Files:**
- Modify: `agent/agent_init.py:585-713`
- Modify: `agent/agent_runtime_helpers.py:1482-1484` (switch_model path)

**Step 1: Create helper to build timeout object**

Add a helper function in `hermes_cli/timeouts.py`:

```python
def build_provider_timeout(provider_id: str, model: str | None = None):
    """Build an httpx.Timeout (or float) for the given provider/model.

    Returns:
        httpx.Timeout if header_timeout_seconds is configured (separating
        read from overall timeout), float if only request_timeout_seconds
        is configured, or None if neither is set.
    """
    req_timeout = get_provider_request_timeout(provider_id, model)
    hdr_timeout = get_provider_header_timeout(provider_id, model)

    if hdr_timeout is None:
        # No header timeout configured — return flat float (existing behavior)
        return req_timeout  # float or None

    try:
        from httpx import Timeout
    except ImportError:
        return req_timeout

    overall = req_timeout if (req_timeout is not None and req_timeout > 0) else 1800.0
    return Timeout(timeout=overall, connect=10.0, read=float(hdr_timeout))
```

**Step 2: Update `agent/agent_init.py` to use `build_provider_timeout`**

At line ~585, change:
```python
    _provider_timeout = get_provider_request_timeout(agent.provider, agent.model)
```
to:
```python
    from hermes_cli.timeouts import build_provider_timeout
    _provider_timeout = build_provider_timeout(agent.provider, agent.model)
```

And keep the existing:
```python
    if _provider_timeout is not None:
        client_kwargs["timeout"] = _provider_timeout
```
This now works with both float and httpx.Timeout (OpenAI SDK accepts both).

**Step 3: Update `agent/agent_runtime_helpers.py` switch_model path**

At line ~1482, change:
```python
            _sm_timeout = get_provider_request_timeout(agent.provider, agent.model)
```
to:
```python
            from hermes_cli.timeouts import build_provider_timeout
            _sm_timeout = build_provider_timeout(agent.provider, agent.model)
```

**Step 4: Update Anthropic adapter to honor header timeout**

In `agent/anthropic_adapter.py`, update `build_anthropic_client` (line ~604) to accept and use header_timeout:

```python
def _build_anthropic_client_inner(
    token_provider, base_url=None, timeout=None, *,
    drop_context_1m_beta=False, header_timeout=None,
):
    from httpx import Timeout
    from agent.azure_identity_adapter import build_bearer_http_client

    _read_timeout = timeout if (isinstance(timeout, (int, float)) and timeout > 0) else 900.0
    _connect = 10.0
    _header = float(header_timeout) if (isinstance(header_timeout, (int, float)) and header_timeout > 0) else None

    if _header is not None:
        timeout_obj = Timeout(timeout=float(_read_timeout), connect=_connect, read=_header)
    else:
        timeout_obj = Timeout(timeout=float(_read_timeout), connect=_connect)
    # ... rest unchanged
```

And update `build_anthropic_client()` (line ~642) to accept and forward `header_timeout`:

```python
def build_anthropic_client(
    api_key,
    base_url: str = None,
    timeout: float = None,
    *,
    drop_context_1m_beta: bool = False,
    header_timeout: float = None,
):
```

Forward `header_timeout` to the inner builder.

**Step 5: Update callers of `build_anthropic_client` to pass header_timeout**

In `run_agent.py` (line ~2964) and `agent/agent_runtime_helpers.py` (line ~1470), change:
```python
build_anthropic_client(..., timeout=get_provider_request_timeout(...))
```
to:
```python
from hermes_cli.timeouts import get_provider_header_timeout
build_anthropic_client(
    ...,
    timeout=get_provider_request_timeout(...),
    header_timeout=get_provider_header_timeout(...),
)
```

**Step 6: Verify no test breakage**

Run: `cd /home/ubuntu/.hermes/hermes-agent && python -m pytest tests/hermes_cli/test_timeouts.py tests/run_agent/ -v 2>&1`
Expected: All pass.

**Step 7: Commit**

```bash
git add hermes_cli/timeouts.py agent/agent_init.py agent/agent_runtime_helpers.py agent/anthropic_adapter.py run_agent.py
git commit -m "feat: wire header_timeout_seconds into OpenAI and Anthropic clients"
```

---

### Task 4: Integration tests for header timeout wiring

**Objective:** Verify that `header_timeout_seconds` produces the correct `httpx.Timeout` objects in the OpenAI and Anthropic client paths.

**Files:**
- Modify: `tests/hermes_cli/test_timeouts.py`

**Step 1: Write test for `build_provider_timeout`**

```python
def test_build_provider_timeout_with_header(monkeypatch, tmp_path):
    """build_provider_timeout returns httpx.Timeout when header_timeout_seconds is set."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, """\
        providers:
          ollama:
            request_timeout_seconds: 1800
            header_timeout_seconds: 600
    """)
    from hermes_cli.timeouts import build_provider_timeout
    result = build_provider_timeout("ollama")
    import httpx
    assert isinstance(result, httpx.Timeout)
    assert result.read == 600.0
    assert result.connect == 10.0


def test_build_provider_timeout_without_header(monkeypatch, tmp_path):
    """build_provider_timeout returns float when only request_timeout_seconds is set."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, """\
        providers:
          openai:
            request_timeout_seconds: 300
    """)
    from hermes_cli.timeouts import build_provider_timeout
    result = build_provider_timeout("openai")
    assert result == 300.0


def test_build_provider_timeout_returns_none_when_unset(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, """\
        providers:
          openai: {}
    """)
    from hermes_cli.timeouts import build_provider_timeout
    assert build_provider_timeout("openai") is None
```

**Step 2: Run tests**

Run: `cd /home/ubuntu/.hermes/hermes-agent && python -m pytest tests/hermes_cli/test_timeouts.py -v 2>&1`
Expected: All pass (including new tests).

**Step 3: Commit**

```bash
git add tests/hermes_cli/test_timeouts.py
git commit -m "test: add integration tests for header timeout wiring"
```

---

### Task 5: Manual verification

**Objective:** Confirm the feature works end-to-end with a real config.

**Step 1:** Create a test config:
```bash
cat > /tmp/test_header_timeout.yaml << 'EOF'
providers:
  ollama-local:
    request_timeout_seconds: 1800
    header_timeout_seconds: 600
EOF
```

**Step 2:** Run the existing timeout tests one final time:
```bash
cd /home/ubuntu/.hermes/hermes-agent && python -m pytest tests/hermes_cli/test_timeouts.py -v
```

**Step 3:** Verify config validation doesn't warn:
```bash
cd /home/ubuntu/.hermes/hermes-agent && python -c "
import os, tempfile
with tempfile.TemporaryDirectory() as d:
    os.environ['HERMES_HOME'] = d
    open(f'{d}/config.yaml', 'w').write('providers:\\n  test:\\n    header_timeout_seconds: 30\\n')
    from hermes_cli.config import load_config_readonly
    cfg = load_config_readonly()
    print('OK:', cfg['providers']['test'])
"
```
