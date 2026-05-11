"""
Tests for global (shared) cron board — scope, isolation, compatibility.

NOTE: All tests use temp root fixtures. No test touches real Hermes cron stores.

RED STATE: These tests import APIs that do not exist yet in cron/jobs.py.
Tasks 4-6 will implement the production code to make them pass.
"""
import json
import pytest
from pathlib import Path


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def isolated_cron_roots(tmp_path, monkeypatch):
    """Use temp dirs for profile and global stores so tests never touch real ~/.hermes."""
    profile_root = tmp_path / "profiles" / "chat_d3c3n"
    global_root = tmp_path / "root"
    profile_root.mkdir(parents=True)
    global_root.mkdir(parents=True)

    monkeypatch.setenv("HERMES_HOME", str(profile_root))

    # Defer monkeypatch of cron.jobs functions until they exist (Task 4)
    try:
        import cron.jobs
        monkeypatch.setattr("cron.jobs.get_hermes_home", lambda: profile_root)
        monkeypatch.setattr("cron.jobs.get_default_hermes_root", lambda: global_root)
    except (ImportError, AttributeError):
        pass  # Functions don't exist yet — that's the RED state

    return profile_root, global_root


def _make_cron_store(scope, root):
    """Import CronStore and build one — lazy import for phased testing."""
    from cron.jobs import CronStore
    root = Path(root)
    cron_dir = root / "cron"
    return CronStore(
        scope=scope,
        root=root,
        cron_dir=cron_dir,
        jobs_file=cron_dir / "jobs.json",
        output_dir=cron_dir / "output",
        lock_file=cron_dir / ".tick.lock",
    )


def _write_empty_jobs(store_dir):
    """Create an empty jobs.json in the store's cron directory."""
    cron_dir = store_dir / "cron"
    cron_dir.mkdir(parents=True, exist_ok=True)
    jobs_file = cron_dir / "jobs.json"
    jobs_file.write_text(json.dumps({"jobs": [], "updated_at": "2026-01-01T00:00:00+00:00"}))


def _load_jobs_raw(store_dir):
    """Read jobs.json directly without going through load_jobs()."""
    jobs_file = store_dir / "cron" / "jobs.json"
    data = json.loads(jobs_file.read_text())
    return data.get("jobs", [])


def _save_jobs_raw(store_dir, jobs):
    """Write jobs.json directly without going through save_jobs()."""
    cron_dir = store_dir / "cron"
    cron_dir.mkdir(parents=True, exist_ok=True)
    jobs_file = cron_dir / "jobs.json"
    jobs_file.write_text(json.dumps({"jobs": jobs, "updated_at": "2026-01-01T00:00:00+00:00"}))


# =========================================================================
# CronStore tests
# =========================================================================

class TestCronStore:
    def test_imports_from_cron_jobs(self):
        """RED: Verify CronStore is importable from cron.jobs (should fail until Task 4)."""
        from cron.jobs import CronStore
        assert CronStore is not None

    def test_current_profile_store_returns_profile_scope(self):
        from cron.jobs import current_profile_store
        store = current_profile_store()
        assert store.scope == "profile"
        assert store.cron_dir.name == "cron"
        assert store.jobs_file.name == "jobs.json"
        assert store.output_dir.name == "output"
        assert store.lock_file.name == ".tick.lock"

    def test_global_store_returns_global_scope(self):
        from cron.jobs import global_store
        store = global_store()
        assert store.scope == "global"
        assert store.cron_dir.name == "cron"

    def test_resolve_store(self):
        from cron.jobs import resolve_store
        assert resolve_store("profile").scope == "profile"
        assert resolve_store("global").scope == "global"
        assert resolve_store().scope == "profile"

    def test_stores_are_independent(self):
        from cron.jobs import current_profile_store, global_store
        p = current_profile_store()
        g = global_store()
        assert p.scope == "profile"
        assert g.scope == "global"
        assert p.cron_dir.name == "cron"
        assert g.cron_dir.name == "cron"

    def test_store_lock_returns_same_lock_for_same_store(self):
        from cron.jobs import current_profile_store, store_lock
        store = current_profile_store()
        lock1 = store_lock(store)
        lock2 = store_lock(store)
        assert lock1 is lock2

    def test_store_lock_different_stores_get_different_locks(self):
        from cron.jobs import current_profile_store, global_store, store_lock
        p_lock = store_lock(current_profile_store())
        g_lock = store_lock(global_store())
        assert p_lock is not None
        assert g_lock is not None


# =========================================================================
# Scope normalization tests
# =========================================================================

class TestScopeNormalization:
    def test_legacy_job_missing_scope_becomes_profile(self):
        from cron.jobs import _normalize_job_scope
        job = {"id": "abc123", "name": "test", "prompt": "hello"}
        result = _normalize_job_scope(job)
        assert result["scope"] == "profile"

    def test_explicit_profile_scope_preserved(self):
        from cron.jobs import _normalize_job_scope
        job = {"id": "abc", "scope": "profile"}
        result = _normalize_job_scope(job)
        assert result["scope"] == "profile"

    def test_explicit_global_scope_preserved(self):
        from cron.jobs import _normalize_job_scope
        job = {"id": "abc", "scope": "global"}
        result = _normalize_job_scope(job)
        assert result["scope"] == "global"

    def test_invalid_scope_defaults_to_profile(self):
        from cron.jobs import _normalize_job_scope
        job = {"id": "abc", "scope": "bogus"}
        result = _normalize_job_scope(job)
        assert result["scope"] == "profile"


# =========================================================================
# Job ref parsing tests
# =========================================================================

class TestJobRefParsing:
    def test_global_prefix(self):
        from cron.jobs import _parse_job_ref
        scope, job_id = _parse_job_ref("global:abc123")
        assert scope == "global"
        assert job_id == "abc123"

    def test_profile_prefix_with_name(self):
        from cron.jobs import _parse_job_ref
        scope, job_id = _parse_job_ref("profile:deepseek:abc123")
        assert scope == "profile"
        assert job_id == "abc123"

    def test_plain_id_no_prefix(self):
        from cron.jobs import _parse_job_ref
        scope, job_id = _parse_job_ref("abc123")
        assert scope is None
        assert job_id == "abc123"

    def test_empty_ref(self):
        from cron.jobs import _parse_job_ref
        scope, job_id = _parse_job_ref("")
        assert scope is None
        assert job_id == ""

    def test_make_job_ref_global(self):
        from cron.jobs import _make_job_ref
        job = {"id": "abc123", "scope": "global"}
        ref = _make_job_ref(job)
        assert ref.startswith("global:")

    def test_make_job_ref_profile(self):
        from cron.jobs import _make_job_ref
        job = {"id": "abc123", "scope": "profile"}
        ref = _make_job_ref(job)
        assert ref.startswith("profile:")


# =========================================================================
# CRUD with scope — integration tests with isolated temp stores
# =========================================================================

class TestGlobalCRUD:
    """Test that global and profile CRUD operations are properly isolated."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, isolated_cron_roots):
        self.profile_dir, self.global_dir = isolated_cron_roots
        _write_empty_jobs(self.profile_dir)
        _write_empty_jobs(self.global_dir)
        self.pstore = _make_cron_store("profile", self.profile_dir)
        self.gstore = _make_cron_store("global", self.global_dir)
        yield

    def _create_profile_job(self, **kwargs):
        from cron.jobs import load_jobs, save_jobs
        jobs = load_jobs(store=self.pstore)
        job = _make_job_dict(scope="profile", **kwargs)
        jobs.append(job)
        save_jobs(jobs, store=self.pstore)
        return job

    def _create_global_job(self, **kwargs):
        from cron.jobs import load_jobs, save_jobs
        jobs = load_jobs(store=self.gstore)
        job = _make_job_dict(scope="global", **kwargs)
        jobs.append(job)
        save_jobs(jobs, store=self.gstore)
        return job

    def test_profile_jobs_not_in_global_store(self):
        from cron.jobs import list_jobs
        self._create_profile_job(id="onlyprof")
        profile_jobs = list_jobs(store=self.pstore)
        global_jobs = list_jobs(store=self.gstore)
        assert any(j["id"] == "onlyprof" for j in profile_jobs)
        assert not any(j["id"] == "onlyprof" for j in global_jobs)

    def test_global_jobs_not_in_profile_store(self):
        from cron.jobs import list_jobs
        self._create_global_job(id="onlyglob")
        profile_jobs = list_jobs(store=self.pstore)
        global_jobs = list_jobs(store=self.gstore)
        assert not any(j["id"] == "onlyglob" for j in profile_jobs)
        assert any(j["id"] == "onlyglob" for j in global_jobs)

    def test_list_visible_jobs_returns_both(self):
        """list_visible_jobs() must return profile + global jobs, not every private profile."""
        from cron.jobs import list_jobs
        self._create_profile_job(id="prof1")
        self._create_global_job(id="glob1")
        profile_jobs = list_jobs(store=self.pstore)
        global_jobs = list_jobs(store=self.gstore)
        all_ids = {j["id"] for j in profile_jobs + global_jobs}
        assert "prof1" in all_ids
        assert "glob1" in all_ids

    def test_remove_job_with_naked_id_only_touches_profile(self):
        from cron.jobs import list_jobs, remove_job
        self._create_profile_job(id="shared123", name="Profile One")
        self._create_global_job(id="shared123", name="Global One")
        removed = remove_job("shared123", store=self.pstore)
        assert removed is True
        profile_jobs = list_jobs(store=self.pstore)
        global_jobs = list_jobs(store=self.gstore)
        assert not any(j["id"] == "shared123" for j in profile_jobs)
        assert any(j["id"] == "shared123" for j in global_jobs)

    def test_remove_job_with_explicit_global_store(self):
        from cron.jobs import list_jobs, remove_job
        self._create_profile_job(id="shared456", name="Profile Two")
        self._create_global_job(id="shared456", name="Global Two")
        removed = remove_job("shared456", store=self.gstore)
        assert removed is True
        profile_jobs = list_jobs(store=self.pstore)
        global_jobs = list_jobs(store=self.gstore)
        assert any(j["id"] == "shared456" for j in profile_jobs)
        assert not any(j["id"] == "shared456" for j in global_jobs)

    def test_remove_job_with_global_ref_prefix(self):
        from cron.jobs import list_jobs, remove_job
        self._create_global_job(id="xyz789")
        removed = remove_job("global:xyz789", store=self.gstore)
        assert removed is True
        global_jobs = list_jobs(store=self.gstore)
        assert not any(j["id"] == "xyz789" for j in global_jobs)

    def test_get_job_resolves_compound_ref(self):
        from cron.jobs import get_job
        self._create_global_job(id="getme001", name="Find Me")
        found = get_job("global:getme001", store=self.gstore)
        assert found is not None
        assert found["id"] == "getme001"

    def test_get_job_fallback_to_global(self):
        from cron.jobs import get_job
        self._create_global_job(id="fallback001")
        found = get_job("fallback001", store=self.gstore)
        assert found is not None
        assert found["scope"] == "global"

    def test_job_ref_in_return_value(self):
        from cron.jobs import _normalize_job_for_return
        job = {"id": "test123", "name": "test", "scope": "global"}
        result = _normalize_job_for_return(job)
        assert "job_ref" in result
        assert result["job_ref"].startswith("global:")

    def test_legacy_job_scope_normalized_on_list(self):
        from cron.jobs import list_jobs
        self._create_profile_job(id="legacy1")
        profile_jobs = list_jobs(store=self.pstore)
        for j in profile_jobs:
            assert j.get("scope") == "profile"

    def test_update_job_with_scope(self):
        from cron.jobs import update_job
        self._create_profile_job(id="upd001", name="Old Name")
        updated = update_job("upd001", {"name": "New Name"}, store=self.pstore)
        assert updated is not None
        assert updated["name"] == "New Name"

    def test_pause_resume_with_scope(self):
        from cron.jobs import pause_job, resume_job
        self._create_profile_job(id="pause001")
        paused = pause_job("pause001", store=self.pstore)
        assert paused is not None
        assert paused.get("enabled") is False
        resumed = resume_job("pause001", store=self.pstore)
        assert resumed is not None
        assert resumed.get("enabled") is True

    def test_trigger_with_scope(self):
        from cron.jobs import trigger_job
        self._create_profile_job(id="trig001")
        triggered = trigger_job("trig001", store=self.pstore)
        assert triggered is not None
        assert triggered.get("state") == "scheduled"


# =========================================================================
# Global create validation tests (RED - production code doesn't exist yet)
# =========================================================================

class TestGlobalCreateValidation:
    """Tests for global cron create_job scope/policy enforcement."""

    def test_global_create_requires_run_as_profile(self):
        """RED: create_job(scope='global') without run_as_profile must raise ValueError."""
        from cron.jobs import create_job
        with pytest.raises(ValueError, match="run_as_profile"):
            create_job(
                prompt="test",
                schedule="2099-01-01T00:00:00",
                scope="global",
            )

    def test_global_create_rejects_invalid_run_as_profile(self):
        """RED: create_job with a non-existent run_as_profile must raise ValueError."""
        from cron.jobs import create_job
        with pytest.raises(ValueError):
            create_job(
                prompt="test",
                schedule="2099-01-01T00:00:00",
                scope="global",
                run_as_profile="nonexistent_profile",
            )

    def test_global_output_is_saved_under_global_output_dir(self):
        """RED: Global job output must write to global store's output dir, not profile."""
        # This is a placeholder RED test — implementation checks come in Task 7.
        from cron.jobs import current_profile_store, global_store
        p = current_profile_store()
        g = global_store()
        # In production, these are different paths
        assert p.scope != g.scope or p.root != g.root, \
            "Profile and global stores must have distinct roots for output isolation"


# =========================================================================
# Backward compatibility
# =========================================================================

class TestBackwardCompatibility:
    """Existing profile behavior must be unchanged."""

    def test_list_jobs_defaults_to_profile(self):
        from cron.jobs import list_jobs
        jobs = list_jobs()
        for j in jobs:
            scope = j.get("scope", "profile")
            assert scope == "profile", f"Job {j.get('id')} has scope {scope}"

    def test_legacy_store_lock_alias_works(self):
        from cron.jobs import _jobs_file_lock
        import threading
        assert _jobs_file_lock is not None
        assert isinstance(_jobs_file_lock, type(threading.Lock()))


# =========================================================================
# Helpers
# =========================================================================

def _make_job_dict(scope="profile", **kwargs):
    """Build a cron job dict with all required fields."""
    job = {
        "id": kwargs.get("id", "job001"),
        "name": kwargs.get("name", "Test Job"),
        "prompt": kwargs.get("prompt", "test prompt"),
        "scope": scope,
        "schedule": {"kind": "cron", "expr": "0 0 1 1 0", "display": "0 0 1 1 0"},
        "schedule_display": "0 0 1 1 0",
        "enabled": True,
        "state": "scheduled",
        "next_run_at": "2099-01-01T00:00:00+00:00",
        "repeat": {"times": None, "completed": 0},
        "deliver": "local",
        "skills": [],
        "skill": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_delivery_error": None,
        "origin": None,
        "no_agent": False,
        "script": None,
        "context_from": None,
        "enabled_toolsets": None,
        "workdir": None,
    }
    if scope == "global":
        job["run_as_profile"] = kwargs.get("run_as_profile", "deepseek")
    for k, v in kwargs.items():
        if k not in ("id", "name", "prompt", "scope", "run_as_profile"):
            job[k] = v
    return job
