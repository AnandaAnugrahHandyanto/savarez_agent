"""Tests for credential exclusion during profile export.

Profile exports should NEVER include auth.json or .env — these contain
API keys, OAuth tokens, and credential pool data. Users share exported
profiles; leaking credentials in the archive is a security issue.
"""

import tarfile

from hermes_cli.profiles import (
    audit_profile,
    export_profile,
    _CLONE_ALL_DEFAULT_EXCLUDE_ROOT,
    _DEFAULT_EXPORT_EXCLUDE_ROOT,
)


class TestCredentialExclusion:

    def test_auth_json_in_default_exclude_set(self):
        """auth.json must be in the default export exclusion set."""
        assert "auth.json" in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_dotenv_in_default_exclude_set(self):
        """.env must be in the default export exclusion set."""
        assert ".env" in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_default_clone_all_excludes_default_infra_dirs(self):
        """--clone-all from default should skip local infrastructure/caches."""
        for name in {
            "hermes-agent",
            "hermes-agent-prclean",
            "profiles",
            "node",
            "lsp",
            "cache",
            "backups",
            "state-snapshots",
            "heapdumps",
            "kanban",
            "image_cache",
            "sandboxes",
            "logs",
            ".skills_prompt_snapshot.json",
        }:
            assert name in _CLONE_ALL_DEFAULT_EXCLUDE_ROOT

    def test_cache_in_default_exclude_set(self):
        """Volatile tool/browser caches must be excluded from default export."""
        assert "cache" in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_large_runtime_dirs_in_default_exclude_set(self):
        """Default export should skip bulky local runtime/backup directories."""
        for name in {"backups", "state-snapshots", "heapdumps", "kanban", "node", "lsp"}:
            assert name in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_default_profile_export_excludes_volatile_cache(self, tmp_path, monkeypatch):
        """Default profile export should not fail on volatile cache entries."""
        default_home = tmp_path / ".hermes"
        default_home.mkdir()
        (default_home / "config.yaml").write_text("model: gpt-4\n")
        (default_home / "SOUL.md").write_text("I am helpful.\n")
        cache_dir = default_home / "cache" / "browser-profile"
        cache_dir.mkdir(parents=True)
        (cache_dir / "SingletonLock").write_text("volatile\n")

        monkeypatch.setattr("hermes_cli.profiles._get_default_hermes_home", lambda: default_home)
        monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda n: default_home)
        monkeypatch.setattr("hermes_cli.profiles.validate_profile_name", lambda n: None)

        output = tmp_path / "default-export.tar.gz"
        result = export_profile("default", str(output))

        with tarfile.open(result, "r:gz") as tf:
            names = tf.getnames()

        assert any("config.yaml" in n for n in names), "config.yaml should be in export"
        assert not any("/cache/" in n or n.endswith("/cache") for n in names), "cache must NOT be in export"

    def test_named_profile_export_excludes_auth(self, tmp_path, monkeypatch):
        """Named profile export must not contain auth.json or .env."""
        profiles_root = tmp_path / "profiles"
        profile_dir = profiles_root / "testprofile"
        profile_dir.mkdir(parents=True)

        # Create a profile with credentials
        (profile_dir / "config.yaml").write_text("model: gpt-4\n")
        (profile_dir / "auth.json").write_text('{"tokens": {"access": "sk-secret"}}')
        (profile_dir / ".env").write_text("OPENROUTER_API_KEY=sk-secret-key\n")
        (profile_dir / "SOUL.md").write_text("I am helpful.\n")
        (profile_dir / "memories").mkdir()
        (profile_dir / "memories" / "MEMORY.md").write_text("# Memories\n")

        monkeypatch.setattr("hermes_cli.profiles._get_profiles_root", lambda: profiles_root)
        monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("hermes_cli.profiles.validate_profile_name", lambda n: None)

        output = tmp_path / "export.tar.gz"
        result = export_profile("testprofile", str(output))

        # Check archive contents
        with tarfile.open(result, "r:gz") as tf:
            names = tf.getnames()

        assert any("config.yaml" in n for n in names), "config.yaml should be in export"
        assert any("SOUL.md" in n for n in names), "SOUL.md should be in export"
        assert not any("auth.json" in n for n in names), "auth.json must NOT be in export"
        assert not any(".env" in n for n in names), ".env must NOT be in export"

    def test_profile_audit_reports_default_cleanup_candidates(self, tmp_path, monkeypatch):
        """Read-only audit should quantify excluded default-profile bloat."""
        default_home = tmp_path / ".hermes"
        default_home.mkdir()
        (default_home / "config.yaml").write_text("model:\n  default: gpt-4\n")
        (default_home / ".env").write_text("OPENROUTER_API_KEY=redacted\n")
        (default_home / "SOUL.md").write_text("I am helpful.\n")
        (default_home / "skills" / "demo").mkdir(parents=True)
        (default_home / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n")
        (default_home / "memories").mkdir()
        (default_home / "memories" / "MEMORY.md").write_text("# Memory\n")
        (default_home / "cron").mkdir()
        (default_home / "cron" / "jobs.json").write_text("[]\n")
        (default_home / "cache").mkdir()
        (default_home / "cache" / "volatile.bin").write_bytes(b"x" * 128)
        (default_home / "backups").mkdir()
        (default_home / "backups" / "old.tar.gz").write_bytes(b"x" * 256)

        monkeypatch.setattr("hermes_cli.profiles._get_default_hermes_home", lambda: default_home)
        monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda n: default_home)
        monkeypatch.setattr("hermes_cli.profiles._check_gateway_running", lambda p: False)

        audit = audit_profile("default", top=5)

        assert audit["profile"] == "default"
        assert audit["has_env"] is True
        assert audit["has_soul"] is True
        assert audit["skills"] == 1
        assert audit["memory_files"] == 1
        assert audit["cron_files"] == 1
        assert audit["export_excluded_bytes"] > 0
        excluded_names = {entry["name"] for entry in audit["top_entries"] if entry["export_excluded"]}
        assert {"cache", "backups"} & excluded_names

    def test_profile_audit_does_not_mark_named_profile_entries_as_default_excluded(self, tmp_path, monkeypatch):
        """Named profile audit must not apply default-root exclusion semantics."""
        profile_dir = tmp_path / "profiles" / "coder"
        profile_dir.mkdir(parents=True)
        (profile_dir / "config.yaml").write_text("model: gpt-4\n")
        (profile_dir / "cache").mkdir()
        (profile_dir / "cache" / "user-data.txt").write_text("keep me\n")

        monkeypatch.setattr("hermes_cli.profiles.profile_exists", lambda n: True)
        monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("hermes_cli.profiles._check_gateway_running", lambda p: False)

        audit = audit_profile("coder", top=5)

        cache_entry = next(entry for entry in audit["top_entries"] if entry["name"] == "cache")
        assert cache_entry["export_excluded"] is False
        assert cache_entry["clone_all_excluded"] is False
