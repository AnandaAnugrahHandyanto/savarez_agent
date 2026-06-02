"""Dashboard memory-view integration tests."""
from pathlib import Path


ENTRY_DELIMITER = "\n§\n"


def _write_memory(profile_dir: Path, *, memory=(), user=()):
    mem_dir = profile_dir / "memories"
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "MEMORY.md").write_text(ENTRY_DELIMITER.join(memory), encoding="utf-8")
    (mem_dir / "USER.md").write_text(ENTRY_DELIMITER.join(user), encoding="utf-8")


class TestDashboardMemoryEndpoints:
    def test_list_memories_returns_profile_and_agent_tags(self, monkeypatch, _isolate_hermes_home):
        try:
            from starlette.testclient import TestClient
        except ImportError:  # pragma: no cover - optional dependency in tiny envs
            import pytest

            pytest.skip("fastapi/starlette not installed")

        import hermes_state
        from hermes_constants import get_hermes_home
        from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

        hermes_home = get_hermes_home()
        monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", hermes_home / "state.db")

        _write_memory(
            hermes_home,
            memory=("Default agent memory",),
            user=("Default user profile",),
        )
        coder_home = hermes_home / "profiles" / "coder"
        _write_memory(
            coder_home,
            memory=("Coder agent memory", "Coder second note"),
            user=("Coder user profile",),
        )

        client = TestClient(app)
        client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

        resp = client.get("/api/memories?profile=all")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert {profile["name"] for profile in data["profiles"]} == {"default", "coder"}
        assert all("path" not in profile for profile in data["profiles"])
        by_content = {entry["content"]: entry for entry in data["memories"]}

        coder_entry = by_content["Coder agent memory"]
        assert coder_entry["profile"] == "coder"
        assert coder_entry["agent"] == "coder"
        assert coder_entry["target"] == "memory"
        assert "path" not in coder_entry
        assert coder_entry["tags"] == [
            "agent:coder",
            "profile:coder",
            "target:memory",
            "store:memory",
        ]

        user_entry = by_content["Default user profile"]
        assert user_entry["tags"] == [
            "agent:default",
            "profile:default",
            "target:user",
            "store:user_profile",
        ]

    def test_list_memories_can_filter_profile_and_target(self, monkeypatch, _isolate_hermes_home):
        try:
            from starlette.testclient import TestClient
        except ImportError:  # pragma: no cover - optional dependency in tiny envs
            import pytest

            pytest.skip("fastapi/starlette not installed")

        import hermes_state
        from hermes_constants import get_hermes_home
        from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

        hermes_home = get_hermes_home()
        monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", hermes_home / "state.db")
        _write_memory(hermes_home, memory=("Default memory",), user=("Default user",))
        writer_home = hermes_home / "profiles" / "writer"
        _write_memory(writer_home, memory=("Writer memory",), user=("Writer user",))

        client = TestClient(app)
        client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

        resp = client.get("/api/memories?profile=writer&target=user")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["memories"][0]["content"] == "Writer user"
        assert data["memories"][0]["tags"] == [
            "agent:writer",
            "profile:writer",
            "target:user",
            "store:user_profile",
        ]

    def test_list_memories_requires_dashboard_session_token(self, _isolate_hermes_home):
        try:
            from starlette.testclient import TestClient
        except ImportError:  # pragma: no cover - optional dependency in tiny envs
            import pytest

            pytest.skip("fastapi/starlette not installed")

        from hermes_cli.web_server import app

        unauth_client = TestClient(app)

        resp = unauth_client.get("/api/memories")

        assert resp.status_code == 401

    def test_list_memories_rejects_invalid_target(self, _isolate_hermes_home):
        try:
            from starlette.testclient import TestClient
        except ImportError:  # pragma: no cover - optional dependency in tiny envs
            import pytest

            pytest.skip("fastapi/starlette not installed")

        from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

        client = TestClient(app)
        client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

        resp = client.get("/api/memories?target=secrets")

        assert resp.status_code == 400
        assert "Invalid target" in resp.text

    def test_list_memories_read_error_does_not_disclose_paths(
        self,
        monkeypatch,
        _isolate_hermes_home,
    ):
        try:
            from starlette.testclient import TestClient
        except ImportError:  # pragma: no cover - optional dependency in tiny envs
            import pytest

            pytest.skip("fastapi/starlette not installed")

        import hermes_state
        from hermes_constants import get_hermes_home
        from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

        hermes_home = get_hermes_home()
        monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", hermes_home / "state.db")
        _write_memory(hermes_home, memory=("Default memory",), user=())

        real_read_text = Path.read_text

        def fail_memory_reads(path, *args, **kwargs):
            if path.name == "MEMORY.md":
                raise OSError(f"Permission denied: '{path}'")
            return real_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fail_memory_reads)
        client = TestClient(app)
        client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

        resp = client.get("/api/memories?target=memory")

        assert resp.status_code == 500
        assert "Could not read memory file" in resp.text
        assert str(hermes_home) not in resp.text
        assert "MEMORY.md" not in resp.text


class TestDashboardMemoryPageStaticWiring:
    def test_dashboard_has_memory_route_nav_and_api_client(self):
        repo = Path(__file__).resolve().parents[2]
        app = (repo / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
        api = (repo / "web" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
        page = repo / "web" / "src" / "pages" / "MemoryPage.tsx"

        assert page.exists()
        page_content = page.read_text(encoding="utf-8")
        assert "agent:" in page_content
        assert "profile:" in page_content
        assert "target:" in page_content

        assert "MemoryPage" in app
        assert '"/memories": MemoryPage' in app
        assert 'path: "/memories"' in app
        assert "getMemories" in api
        assert '"/api/memories' in api
