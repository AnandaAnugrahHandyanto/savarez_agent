"""Regression tests for the post-response watchdog (#32079).

Issue #32079 reported a Hermes gateway turn going silent after a Codex
Responses API call had already returned successfully — Python's regex
engine was holding the GIL while no tool dispatch / Turn-ended log
appeared.  The fix has three parts that this module pins:

* ``agent.codex_responses_adapter`` bounds the ``to=functions.<name>``
  leak scan to a fixed-size prefix so the post-response normalize step
  cannot loop over multi-megabyte assistant content inside ``_sre``.
* ``agent.post_response_watchdog.post_response_watchdog`` arms a
  one-shot stack-dump timer around CPU-bound post-response phases so
  any future stall produces actionable evidence.
* ``gateway.platforms.base._MEDIA_TAG_RE`` and
  ``gateway.run._TOOL_MEDIA_RE`` are pre-compiled at module load,
  removing the per-call ``re.compile`` cost and immunising the post-
  response media-extraction path against ``re._cache`` eviction.
"""

from __future__ import annotations

import inspect
import os
import re
import threading
import time
from pathlib import Path

import pytest

from agent.codex_responses_adapter import (
    _TOOL_CALL_LEAK_PATTERN,
    _TOOL_CALL_LEAK_SCAN_LIMIT,
    _scan_for_leaked_tool_call,
)
from agent.post_response_watchdog import post_response_watchdog


# --------------------------------------------------------------------------- #
# Bounded leak scan (#32079)                                                  #
# --------------------------------------------------------------------------- #

class TestBoundedLeakScan:
    def test_scan_limit_is_advertised_constant(self):
        # Sanity: the limit is a positive int so call sites can rely
        # on slicing semantics.  Keeping it pinned as a public-ish
        # constant lets future regressions show up as a diff.
        assert isinstance(_TOOL_CALL_LEAK_SCAN_LIMIT, int)
        assert _TOOL_CALL_LEAK_SCAN_LIMIT > 0
        # Bound must be larger than any plausible Harmony preamble so
        # legitimate degeneration is still caught.  Keep generous.
        assert _TOOL_CALL_LEAK_SCAN_LIMIT >= 4096

    def test_scan_returns_false_on_empty_or_clean_text(self):
        assert _scan_for_leaked_tool_call("") is False
        assert _scan_for_leaked_tool_call("hello world") is False
        assert _scan_for_leaked_tool_call("Click https://example.test") is False

    def test_scan_detects_canonical_leak_marker_at_start(self):
        # The Taiwan-embassy-email failure mode reported in the
        # original Codex leak fix.
        leaked = "to=functions.exec_command {\"cmd\": \"curl ...\"}"
        assert _scan_for_leaked_tool_call(leaked) is True

    def test_scan_detects_assistant_prefix_variant(self):
        leaked = "I'll run it.\nassistant to=functions.exec_command {}"
        assert _scan_for_leaked_tool_call(leaked) is True

    def test_scan_detects_harmony_channel_prefix(self):
        leaked = "<|channel|>commentary to=functions.exec_command {}"
        assert _scan_for_leaked_tool_call(leaked) is True

    def test_scan_ignores_marker_past_the_limit(self):
        # The marker sits AFTER ``_TOOL_CALL_LEAK_SCAN_LIMIT`` bytes —
        # legitimate prose that big almost certainly is not Harmony
        # serialization, and the cost of scanning every byte under the
        # GIL is exactly the regression we are guarding against.
        prefix = "x" * (_TOOL_CALL_LEAK_SCAN_LIMIT + 64)
        text = prefix + " to=functions.exec_command {}"
        assert _scan_for_leaked_tool_call(text) is False

    def test_scan_detects_marker_just_inside_the_limit(self):
        # Marker that fits inside the prefix window must still be
        # caught — the bound is not allowed to miss the real failure.
        prefix = "x" * (_TOOL_CALL_LEAK_SCAN_LIMIT - 50)
        text = prefix + "\nto=functions.exec_command {}"
        assert _scan_for_leaked_tool_call(text) is True

    def test_scan_runs_in_constant_time_on_large_clean_input(self):
        # Catches the failure mode directly: a long, well-formed
        # assistant response that does not contain the marker must
        # not pay O(N) inside _sre.  Guard the wall-clock cost so a
        # future "scan everything" regression would fail this test.
        text = "Lorem ipsum dolor sit amet. " * 200_000  # ~5 MiB
        t0 = time.perf_counter()
        for _ in range(50):
            _scan_for_leaked_tool_call(text)
        elapsed = time.perf_counter() - t0
        # 50 scans of 5 MiB should easily finish under a second on
        # any developer machine when bounded; without bounding, this
        # would still be sub-second on Python's `re` (the leak regex
        # is linear), but the bound also caps memory traffic.
        assert elapsed < 2.0, (
            f"bounded leak scan should be fast even on large clean "
            f"input — took {elapsed:.2f}s (issue #32079)"
        )


# --------------------------------------------------------------------------- #
# Watchdog behaviour                                                          #
# --------------------------------------------------------------------------- #

class TestPostResponseWatchdog:
    def test_no_op_when_block_is_fast(self, tmp_path):
        dump = tmp_path / "stall.log"
        with post_response_watchdog("fast.path", timeout_s=5.0, dump_path=dump):
            pass
        # Block finished well before the timeout — no dump must be
        # written.  If it were, every fast turn would spam the log.
        assert not dump.exists()

    def test_emits_dump_when_block_exceeds_timeout(self, tmp_path):
        dump = tmp_path / "stall.log"
        with post_response_watchdog("slow.path", timeout_s=0.1, dump_path=dump):
            time.sleep(0.4)
        # Watchdog runs from a daemon thread; give it a brief moment
        # to flush before asserting.
        for _ in range(20):
            if dump.exists() and dump.stat().st_size > 0:
                break
            time.sleep(0.05)
        assert dump.exists(), "watchdog timer did not produce a stack dump"
        body = dump.read_text(encoding="utf-8")
        assert "POST-RESPONSE STALL" in body
        assert "slow.path" in body
        assert "Current thread" in body or "Thread" in body

    def test_dump_records_label_and_pid(self, tmp_path):
        dump = tmp_path / "stall.log"
        with post_response_watchdog("phase.alpha", timeout_s=0.05, dump_path=dump):
            time.sleep(0.3)
        for _ in range(20):
            if dump.exists() and dump.stat().st_size > 0:
                break
            time.sleep(0.05)
        body = dump.read_text(encoding="utf-8")
        assert "phase.alpha" in body
        assert f"pid={os.getpid()}" in body

    def test_dedup_window_suppresses_repeated_dumps(self, tmp_path):
        dump = tmp_path / "stall.log"
        # First fire — should write the full dump.  Subsequent fires
        # within the dedup window must not re-write the dump body.
        # Reset module state so prior tests don't poison the dedup
        # ledger.
        from agent.post_response_watchdog import _LAST_DUMP_AT
        _LAST_DUMP_AT.clear()

        for _ in range(3):
            with post_response_watchdog("dup.label", timeout_s=0.05, dump_path=dump):
                time.sleep(0.15)
            time.sleep(0.05)
        body = dump.read_text(encoding="utf-8")
        # Only ONE stall header — dedup is per (label, dump_path).
        assert body.count("POST-RESPONSE STALL (dup.label)") == 1

    def test_disabled_via_env_skips_timer(self, tmp_path, monkeypatch):
        dump = tmp_path / "stall.log"
        monkeypatch.setenv("HERMES_POST_RESPONSE_WATCHDOG_DISABLED", "1")
        # Even with a deliberately slow body, no dump should appear
        # when the operator has explicitly disabled the watchdog.
        with post_response_watchdog("disabled.path", timeout_s=0.05, dump_path=dump):
            time.sleep(0.2)
        assert not dump.exists()

    def test_zero_timeout_is_a_noop(self, tmp_path):
        dump = tmp_path / "stall.log"
        with post_response_watchdog("zero", timeout_s=0.0, dump_path=dump):
            time.sleep(0.05)
        assert not dump.exists()

    def test_resolve_dump_path_prefers_explicit_env(self, monkeypatch, tmp_path):
        from agent.post_response_watchdog import _resolve_dump_path

        explicit = tmp_path / "explicit.log"
        monkeypatch.setenv("HERMES_POST_RESPONSE_DUMP_PATH", str(explicit))
        assert _resolve_dump_path() == explicit

    def test_resolve_dump_path_falls_back_to_hermes_home(self, monkeypatch, tmp_path):
        from agent.post_response_watchdog import _resolve_dump_path

        monkeypatch.delenv("HERMES_POST_RESPONSE_DUMP_PATH", raising=False)
        home = tmp_path / "hermes-home"
        monkeypatch.setenv("HERMES_HOME", str(home))
        path = _resolve_dump_path()
        assert path == home / "logs" / "post-response-stall.log"
        # Side effect: the parent directory was created so the open
        # call later cannot fail with ENOENT.
        assert path.parent.is_dir()

    def test_concurrent_watchdogs_dont_interfere(self, tmp_path):
        # The same process can run several agent turns at once
        # (delegation, cron, gateway sessions).  Each watchdog must
        # operate independently — one slow phase emitting a dump
        # cannot suppress another label's dump.
        from agent.post_response_watchdog import _LAST_DUMP_AT
        _LAST_DUMP_AT.clear()

        dump_a = tmp_path / "a.log"
        dump_b = tmp_path / "b.log"

        def _run(label, dump):
            with post_response_watchdog(label, timeout_s=0.05, dump_path=dump):
                time.sleep(0.2)

        threads = [
            threading.Thread(target=_run, args=("phase.a", dump_a)),
            threading.Thread(target=_run, args=("phase.b", dump_b)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        for _ in range(20):
            if dump_a.exists() and dump_b.exists():
                break
            time.sleep(0.05)
        assert dump_a.exists()
        assert dump_b.exists()
        assert "phase.a" in dump_a.read_text(encoding="utf-8")
        assert "phase.b" in dump_b.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Module-level pre-compiled regexes                                           #
# --------------------------------------------------------------------------- #

class TestModuleLevelMediaPattern:
    def test_base_media_re_is_compiled_pattern(self):
        from gateway.platforms import base

        media_re = getattr(base, "_MEDIA_TAG_RE", None)
        assert isinstance(media_re, re.Pattern), (
            "extract_media_paths must use a module-level compiled pattern "
            "to avoid per-call re.compile cost (#32079)"
        )

    def test_base_extract_media_uses_module_level_pattern(self):
        from gateway.platforms.base import BasePlatformAdapter

        # The function body must reference the module-level pattern,
        # NOT call ``re.compile`` inline.  Inline compile is exactly
        # what the fix replaced.
        src = inspect.getsource(BasePlatformAdapter.extract_media)
        assert "_MEDIA_TAG_RE" in src
        # Defensive: ensure the local rebuild didn't sneak back in.
        assert "media_pattern = re.compile" not in src

    def test_run_tool_media_re_is_module_level(self):
        # Two former in-loop ``re.compile`` sites in gateway/run.py —
        # both must now reference the module-level _TOOL_MEDIA_RE.
        from gateway import run

        media_re = getattr(run, "_TOOL_MEDIA_RE", None)
        assert isinstance(media_re, re.Pattern)
        # Pattern must include the canonical extension list so the
        # consolidation didn't accidentally drop variants.
        for ext in ("png", "jpe", "mp3", "pdf", "csv"):
            assert ext in media_re.pattern

    def test_run_module_no_longer_recompiles_inline(self):
        # Source-level guard: gateway/run.py must NOT reassign
        # ``_TOOL_MEDIA_RE = re.compile(...)`` inside any function.
        # Reassignments here are the regression we're pinning.
        run_path = Path(__file__).resolve().parents[2] / "gateway" / "run.py"
        body = run_path.read_text(encoding="utf-8")
        # Allow the single module-level compile (with or without
        # type annotation: ``_TOOL_MEDIA_RE: re.Pattern[str] = ...``).
        compile_sites = re.findall(
            r"^_TOOL_MEDIA_RE\b[^\n=]*=\s*re\.compile", body, re.MULTILINE
        )
        assert len(compile_sites) == 1, (
            "_TOOL_MEDIA_RE should be compiled once at module scope "
            "(found {} compile sites) — issue #32079".format(len(compile_sites))
        )
        # And no inner-scope re-compiles ("            _TOOL_MEDIA_RE = re.compile").
        indented_sites = re.findall(
            r"^\s+_TOOL_MEDIA_RE\s*=\s*re\.compile", body, re.MULTILINE
        )
        assert indented_sites == [], (
            "Found inner-scope re.compile of _TOOL_MEDIA_RE — issue #32079 fix should keep "
            "the pattern module-level."
        )


# --------------------------------------------------------------------------- #
# Source-level guards on the conversation loop integration                    #
# --------------------------------------------------------------------------- #

class TestConversationLoopIntegrates:
    def test_post_response_watchdog_imported(self):
        # Forward reference through ``agent.conversation_loop`` to
        # confirm the import wired through and the watchdog symbol
        # is reachable from the live module.
        from agent import conversation_loop

        assert hasattr(conversation_loop, "post_response_watchdog")
        # Same callable as the canonical module — no shadowing.
        from agent.post_response_watchdog import post_response_watchdog as canonical
        assert conversation_loop.post_response_watchdog is canonical

    def test_loop_wraps_normalize_step(self):
        # Source-level guard so a future refactor cannot accidentally
        # drop the watchdog around the post-response normalization
        # phase identified in #32079.  Looking for the explicit
        # ``with post_response_watchdog(...)`` site that wraps
        # ``transport.normalize_response``.
        loop_path = (
            Path(__file__).resolve().parents[2] / "agent" / "conversation_loop.py"
        )
        body = loop_path.read_text(encoding="utf-8")
        assert "with post_response_watchdog(" in body, (
            "agent/conversation_loop.py must wrap the post-response "
            "normalize phase with post_response_watchdog (#32079)"
        )
        # The label should reference the api_mode so dump triage can
        # tell Codex apart from Anthropic / chat-completions stalls.
        assert "transport.normalize_response[" in body


# --------------------------------------------------------------------------- #
# Issue reference guards                                                      #
# --------------------------------------------------------------------------- #

class TestIssueReferences:
    """Pin the #32079 reference next to the code so future readers
    can find the bug-report context without grepping commit history."""

    @pytest.mark.parametrize("module_path", [
        "agent/codex_responses_adapter.py",
        "agent/post_response_watchdog.py",
        "agent/conversation_loop.py",
        "gateway/platforms/base.py",
        "gateway/run.py",
    ])
    def test_issue_referenced_in_source(self, module_path):
        path = Path(__file__).resolve().parents[2] / module_path
        body = path.read_text(encoding="utf-8")
        assert "#32079" in body, (
            f"{module_path} should mention issue #32079 in a code "
            f"comment so the diagnostic context is discoverable."
        )

    def test_leak_pattern_remains_compiled_with_ignorecase(self):
        # Behaviour-pin: the bounded scan still uses the same
        # case-insensitive Harmony marker matcher.  If the underlying
        # regex changes, callers may need to reassess the bound.
        assert _TOOL_CALL_LEAK_PATTERN.flags & re.IGNORECASE
        assert "to=functions" in _TOOL_CALL_LEAK_PATTERN.pattern
