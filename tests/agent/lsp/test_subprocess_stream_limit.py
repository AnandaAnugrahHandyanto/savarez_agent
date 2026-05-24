"""Verify the LSP client spawns its child process with a raised
StreamReader limit so large LSP messages and verbose stderr logs do not
trip ``asyncio.LimitOverrunError`` (#31417).
"""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from agent.lsp.client import LSP_SUBPROCESS_STREAM_LIMIT, LSPClient


def test_lsp_subprocess_stream_limit_is_well_above_default():
    """The constant must comfortably exceed asyncio's 64 KiB default,
    otherwise the whole point of this guard is moot.
    """
    DEFAULT_ASYNCIO_STREAM_LIMIT = 64 * 1024
    assert LSP_SUBPROCESS_STREAM_LIMIT > DEFAULT_ASYNCIO_STREAM_LIMIT
    # And it should be a sane upper bound — not unbounded.
    assert LSP_SUBPROCESS_STREAM_LIMIT <= 64 * 1024 * 1024


@pytest.mark.asyncio
async def test_lsp_client_passes_limit_kwarg_to_create_subprocess(tmp_path):
    """Asserts ``LSPClient._spawn`` forwards ``limit`` to
    ``asyncio.create_subprocess_exec``. Without this, asyncio falls back
    to its 64 KiB default and verbose LSP servers (pyright completion
    lists, rust-analyzer macro expansions) trip ``LimitOverrunError``
    on the very first big message.
    """
    fake_proc = AsyncMock()
    fake_proc.stdout = AsyncMock()
    fake_proc.stderr = AsyncMock()
    fake_proc.stdin = AsyncMock()

    captured: dict = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured.update(kwargs)
        return fake_proc

    client = LSPClient(
        command=[sys.executable, "-c", "import sys; sys.stdin.read()"],
        workspace_root=str(tmp_path),
        server_id="test-server",
    )

    with patch.object(
        asyncio, "create_subprocess_exec", side_effect=fake_create_subprocess_exec
    ):
        # We only need _spawn to run; skip the initialize handshake.
        with patch.object(client, "_drain_stderr", new=AsyncMock()):
            with patch.object(client, "_reader_loop", new=AsyncMock()):
                await client._spawn()

    assert "limit" in captured, (
        "LSPClient._spawn must pass limit= kwarg to create_subprocess_exec"
    )
    assert captured["limit"] == LSP_SUBPROCESS_STREAM_LIMIT, (
        f"limit kwarg should equal LSP_SUBPROCESS_STREAM_LIMIT "
        f"({LSP_SUBPROCESS_STREAM_LIMIT}), got {captured['limit']}"
    )


@pytest.mark.asyncio
async def test_large_stderr_line_does_not_trip_limit_overrun(tmp_path):
    """End-to-end: a real child process emits a single >64 KiB stderr
    line. With the raised limit, ``readline()`` succeeds. Without it,
    asyncio raises ``LimitOverrunError`` on the very first read.
    """
    big_line_size = 200_000  # well above the 64 KiB default
    # Emit one big line on stderr followed by exit.  Use chr(10) so the
    # source string survives any shell-quoting layer cleanly.
    code = (
        "import sys; "
        f"sys.stderr.write('x' * {big_line_size} + chr(10)); "
        "sys.stderr.flush()"
    )
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=LSP_SUBPROCESS_STREAM_LIMIT,
    )
    assert proc.stderr is not None
    line = await proc.stderr.readline()
    await proc.wait()
    # On Windows, stderr is opened in text mode and ``\n`` gets translated
    # to ``\r\n`` on the way out — so the received line is one byte longer
    # than ``big_line_size + 1``. Accept either form.
    assert len(line) in (big_line_size + 1, big_line_size + 2), (
        f"unexpected line length: {len(line)} (expected ~{big_line_size + 1})"
    )
    assert line.startswith(b"x" * 1024)
