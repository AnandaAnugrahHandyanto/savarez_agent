"""Integration tests against the real `claude` binary.

These tests are gated by @pytest.mark.integration. They consume real
Anthropic plan tokens — each test uses one short prompt.

Skipped automatically if `claude` is not on PATH or if
CLAUDE_CODE_OAUTH_TOKEN cannot be loaded.

Note: The test suite's global conftest.py strips all _TOKEN env vars via
_hermetic_environment (autouse). This test works around that by loading
the token directly from /run/infisical/hermes.env at test time.

Note: The global conftest also installs a 30-second SIGALRM per test.
Integration tests against the live claude binary can take up to 60
seconds on a slow response; the SIGALRM is cancelled at the start of the
async body (SIGALRM is not supported inside asyncio event loops anyway).
"""

import asyncio
import os
import re
import signal
import sys
from pathlib import Path
import pytest

from agent.claude_cli import probe
from agent.claude_cli.protocol import StreamJsonParser

pytestmark = pytest.mark.integration

_HERMES_ENV_PATH = Path("/run/infisical/hermes.env")
_TOKEN_RE = re.compile(r'^CLAUDE_CODE_OAUTH_TOKEN=["\']?([^"\']+)["\']?\s*$', re.MULTILINE)


def _load_oauth_token() -> str | None:
    """Read CLAUDE_CODE_OAUTH_TOKEN from /run/infisical/hermes.env directly.

    The global conftest strips it from os.environ, so we bypass os.environ
    and parse the file ourselves.
    """
    # First try os.environ in case it survived (e.g. non-hermetic runs).
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return os.environ["CLAUDE_CODE_OAUTH_TOKEN"]
    if not _HERMES_ENV_PATH.exists():
        return None
    text = _HERMES_ENV_PATH.read_text(encoding="utf-8")
    m = _TOKEN_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


def _skip_if_no_claude() -> tuple[str, str]:
    """Return (binary_path, oauth_token) or call pytest.skip()."""
    token = _load_oauth_token()
    if not token:
        pytest.skip(
            "CLAUDE_CODE_OAUTH_TOKEN not available (not in os.environ and "
            f"not found in {_HERMES_ENV_PATH}); integration test skipped"
        )
    try:
        binary = probe.discover_binary()
    except Exception as exc:
        pytest.skip(f"claude binary not available: {exc}")
    return binary, token  # type: ignore[return-value]


@pytest.mark.asyncio
@pytest.mark.live_system_guard_bypass
async def test_basic_stream_json_invocation():
    """Spawning `claude -p` with stdin prompt + stream-json yields parseable events.

    Verifies:
      * stdin prompt transport is supported by --print mode
      * --output-format stream-json + --verbose emits events
      * at least one 'assistant' event and one 'result' event arrive
      * exit code is 0 on success
    """
    # Cancel the global 30-second SIGALRM so the real-binary call can take
    # up to 120 seconds without being killed mid-run.  SIGALRM has no effect
    # inside an asyncio event loop (the signal arrives between iterations, not
    # mid-await), but clearing it prevents a stray delivery after the test
    # body resumes. Windows has no SIGALRM.
    if sys.platform != "win32":
        signal.alarm(0)

    binary, token = _skip_if_no_claude()

    # Build a sanitized env with the token injected.
    env = {k: v for k, v in os.environ.items()}
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env = probe.check_env_hygiene(env)

    proc = await asyncio.create_subprocess_exec(
        binary,
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--allowedTools", "",
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Write the prompt to stdin and close it.
    assert proc.stdin is not None
    proc.stdin.write(b"Reply with exactly one word: pong")
    await proc.stdin.drain()
    proc.stdin.close()

    parser = StreamJsonParser()
    stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=120)
    events = list(parser.feed(stdout_data)) + list(parser.close())

    assert proc.returncode == 0, (
        f"claude exited with {proc.returncode}; stderr: {stderr_data.decode()[:500]}"
    )
    assert any(e.get("type") == "assistant" for e in events), (
        f"no assistant event seen; events: {[e.get('type') for e in events]}"
    )
    assert any(e.get("type") == "result" for e in events), (
        f"no result event seen; events: {[e.get('type') for e in events]}"
    )
