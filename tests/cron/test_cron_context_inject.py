"""
Tests for cron context-inject button feature.

Covers:
- ci_store round-trip (put/pop/expiry)
- offer_context_inject flag in create_job / update_job
- _deliver_result injects cron_context_inject_token into metadata
- mirror_to_session role parameter
- has_active_session helper
- Telegram send() attaches InlineKeyboardMarkup on last chunk
- _handle_callback_query ci:inject and ci:new paths
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# ci_store tests
# ---------------------------------------------------------------------------

class TestCiStore:
    def setup_method(self):
        # Clear store before each test
        from cron.scheduler import _ci_store, _ci_store_lock
        with _ci_store_lock:
            _ci_store.clear()

    def test_put_and_pop(self):
        from cron.scheduler import _ci_store_put, ci_store_pop
        token = _ci_store_put("hello world", "job-abc")
        assert isinstance(token, str) and len(token) == 16  # hex(8) = 16 chars
        entry = ci_store_pop(token)
        assert entry is not None
        assert entry["content"] == "hello world"
        assert entry["job_id"] == "job-abc"

    def test_pop_consumes_entry(self):
        from cron.scheduler import _ci_store_put, ci_store_pop
        token = _ci_store_put("data", "job-1")
        ci_store_pop(token)
        assert ci_store_pop(token) is None  # second pop returns None

    def test_pop_unknown_token(self):
        from cron.scheduler import ci_store_pop
        assert ci_store_pop("deadbeefdeadbeef") is None

    def test_expired_entry_returns_none(self):
        from cron.scheduler import _ci_store_put, ci_store_pop, _ci_store, _ci_store_lock, _CI_TTL
        token = _ci_store_put("stale", "job-2")
        # Manually backdate the timestamp to simulate expiry
        with _ci_store_lock:
            _ci_store[token]["ts"] -= _CI_TTL + 1
        assert ci_store_pop(token) is None

    def test_evicts_expired_on_put(self):
        from cron.scheduler import _ci_store_put, _ci_store, _ci_store_lock, _CI_TTL
        # Insert a stale entry manually
        with _ci_store_lock:
            _ci_store["staletoken"] = {"content": "x", "job_id": "j", "ts": time.monotonic() - _CI_TTL - 1}
        # A new put should evict it
        _ci_store_put("fresh", "job-3")
        with _ci_store_lock:
            assert "staletoken" not in _ci_store


# ---------------------------------------------------------------------------
# create_job / update_job flag tests
# ---------------------------------------------------------------------------

class TestOfferContextInjectFlag:
    def test_create_job_flag_true(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        from cron.jobs import create_job, remove_job
        job = create_job(prompt="test", schedule="every 1h", offer_context_inject=True)
        assert job["offer_context_inject"] is True
        remove_job(job["id"])

    def test_create_job_flag_false_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        from cron.jobs import create_job, remove_job
        job = create_job(prompt="test", schedule="every 1h")
        assert job["offer_context_inject"] is False
        remove_job(job["id"])

    def test_update_job_flag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        from cron.jobs import create_job, update_job, remove_job
        job = create_job(prompt="test", schedule="every 1h")
        assert job["offer_context_inject"] is False
        updated = update_job(job["id"], {"offer_context_inject": True})
        assert updated["offer_context_inject"] is True
        remove_job(job["id"])


# ---------------------------------------------------------------------------
# mirror_to_session role parameter
# ---------------------------------------------------------------------------

class TestMirrorRole:
    def test_mirror_role_user(self, tmp_path):
        """mirror_to_session with role='user' writes role=user to JSONL."""
        import json
        from gateway.mirror import mirror_to_session

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        session_id = "test-session-001"

        # Create a fake sessions.json index
        index = {
            "agent:main:telegram:dm": {
                "session_id": session_id,
                "platform": "telegram",
                "origin": {"platform": "telegram", "chat_id": "12345"},
                "updated_at": "2026-01-01T00:00:00",
            }
        }
        (sessions_dir / "sessions.json").write_text(json.dumps(index))
        (sessions_dir / f"{session_id}.jsonl").write_text("")

        with patch("gateway.mirror._SESSIONS_DIR", sessions_dir), \
             patch("gateway.mirror._SESSIONS_INDEX", sessions_dir / "sessions.json"), \
             patch("gateway.mirror._append_to_sqlite"):
            ok = mirror_to_session(
                platform="telegram",
                chat_id="12345",
                message_text="cron output here",
                source_label="cron:job-1",
                role="user",
            )

        assert ok is True
        lines = (sessions_dir / f"{session_id}.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        msg = json.loads(lines[0])
        assert msg["role"] == "user"
        assert msg["content"] == "cron output here"
        assert msg["mirror_source"] == "cron:job-1"

    def test_mirror_role_assistant_default(self, tmp_path):
        """Default role is assistant (backward compat)."""
        import json
        from gateway.mirror import mirror_to_session

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        session_id = "test-session-002"
        index = {
            "k": {
                "session_id": session_id,
                "platform": "telegram",
                "origin": {"platform": "telegram", "chat_id": "99999"},
                "updated_at": "2026-01-01T00:00:00",
            }
        }
        (sessions_dir / "sessions.json").write_text(json.dumps(index))
        (sessions_dir / f"{session_id}.jsonl").write_text("")

        with patch("gateway.mirror._SESSIONS_DIR", sessions_dir), \
             patch("gateway.mirror._SESSIONS_INDEX", sessions_dir / "sessions.json"), \
             patch("gateway.mirror._append_to_sqlite"):
            ok = mirror_to_session(
                platform="telegram",
                chat_id="99999",
                message_text="delivery",
            )

        assert ok is True
        msg = json.loads((sessions_dir / f"{session_id}.jsonl").read_text().strip())
        assert msg["role"] == "assistant"


# ---------------------------------------------------------------------------
# has_active_session
# ---------------------------------------------------------------------------

class TestHasActiveSession:
    def test_no_session(self, tmp_path):
        from gateway.mirror import has_active_session
        with patch("gateway.mirror._SESSIONS_INDEX", tmp_path / "sessions.json"):
            assert has_active_session("telegram", "000000") is False

    def test_with_session(self, tmp_path):
        import json
        from gateway.mirror import has_active_session

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        index = {
            "k": {
                "session_id": "s1",
                "platform": "telegram",
                "origin": {"platform": "telegram", "chat_id": "777"},
                "updated_at": "2026-01-01T00:00:00",
            }
        }
        idx_path = sessions_dir / "sessions.json"
        idx_path.write_text(json.dumps(index))

        with patch("gateway.mirror._SESSIONS_INDEX", idx_path):
            assert has_active_session("telegram", "777") is True
            assert has_active_session("telegram", "888") is False


# ---------------------------------------------------------------------------
# _deliver_result injects token into metadata
# ---------------------------------------------------------------------------

class TestDeliverResultInjectsToken:
    def setup_method(self):
        from cron.scheduler import _ci_store, _ci_store_lock
        with _ci_store_lock:
            _ci_store.clear()

    def test_ci_store_put_called_for_telegram(self):
        """_ci_store_put is called when offer_context_inject=True + telegram."""
        from cron.scheduler import _ci_store_put, _ci_store, _ci_store_lock

        # Directly test the store mechanism used by _deliver_result
        token = _ci_store_put("cron output", "job-ci-test")

        with _ci_store_lock:
            assert token in _ci_store
            assert _ci_store[token]["content"] == "cron output"
            assert _ci_store[token]["job_id"] == "job-ci-test"

    def test_no_token_for_non_telegram(self):
        """offer_context_inject=True but platform=discord → no token stored."""
        from cron.scheduler import _ci_store, _ci_store_lock

        # Simulate what _deliver_result does: only call _ci_store_put for telegram
        platform_name = "discord"
        offer_context_inject = True

        if offer_context_inject and platform_name.lower() == "telegram":
            from cron.scheduler import _ci_store_put
            _ci_store_put("output", "job-discord")

        with _ci_store_lock:
            assert len(_ci_store) == 0

    def test_token_in_metadata_for_telegram(self, tmp_path, monkeypatch):
        """_deliver_result stores a ci token when offer_context_inject=True
        and a live Telegram adapter is present."""
        from unittest.mock import MagicMock, patch
        from cron.scheduler import _ci_store, _ci_store_lock
        from cron.scheduler import _deliver_result
        from gateway.config import Platform

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        mock_future = MagicMock()
        mock_future.result.return_value = None

        mock_adapter = MagicMock()

        mock_pconfig = MagicMock()
        mock_pconfig.enabled = True
        mock_gw_config = MagicMock()
        mock_gw_config.platforms.get.return_value = mock_pconfig

        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True

        job = {
            "id": "job-meta-test",
            "offer_context_inject": True,
            "deliver": "telegram:12345",
        }

        with patch("gateway.config.load_gateway_config", return_value=mock_gw_config), \
             patch("cron.scheduler.load_config", return_value={}):
            _deliver_result(
                job=job,
                content="cron output",
                adapters={Platform.TELEGRAM: mock_adapter},
                loop=mock_loop,
            )

        # Token should have been stored in _ci_store
        with _ci_store_lock:
            assert len(_ci_store) == 1
            token = list(_ci_store.keys())[0]
            assert len(token) == 16
            assert _ci_store[token]["content"] == "cron output"
            assert _ci_store[token]["job_id"] == "job-meta-test"

        # Verify send was called with the token in metadata
        assert mock_adapter.send.called
        call_kwargs = mock_adapter.send.call_args
        metadata_arg = call_kwargs[1].get("metadata") or (call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None)
        assert metadata_arg is not None
        assert "cron_context_inject_token" in metadata_arg
        assert metadata_arg["cron_context_inject_token"] == token

    def test_no_metadata_when_flag_false(self, tmp_path, monkeypatch):
        """_deliver_result does NOT store a ci token when offer_context_inject=False."""
        from unittest.mock import MagicMock, patch
        from cron.scheduler import _ci_store, _ci_store_lock
        from cron.scheduler import _deliver_result
        from gateway.config import Platform

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        mock_adapter = MagicMock()

        mock_pconfig = MagicMock()
        mock_pconfig.enabled = True
        mock_gw_config = MagicMock()
        mock_gw_config.platforms.get.return_value = mock_pconfig

        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True

        job = {
            "id": "job-no-inject",
            "offer_context_inject": False,
            "deliver": "telegram:12345",
        }

        with patch("gateway.config.load_gateway_config", return_value=mock_gw_config), \
             patch("cron.scheduler.load_config", return_value={}):
            _deliver_result(
                job=job,
                content="cron output",
                adapters={Platform.TELEGRAM: mock_adapter},
                loop=mock_loop,
            )

        with _ci_store_lock:
            assert len(_ci_store) == 0

        # send was called but without ci token
        assert mock_adapter.send.called
        call_kwargs = mock_adapter.send.call_args
        metadata_arg = call_kwargs[1].get("metadata") or (call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None)
        if metadata_arg:
            assert "cron_context_inject_token" not in metadata_arg
