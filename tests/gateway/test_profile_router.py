import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.profile_router import (
    ProfileRoute,
    build_profile_subprocess_command,
    build_profile_subprocess_env,
    extract_session_id,
    load_profile_route_sessions,
    load_profile_routes,
    match_profile_route,
    parse_profile_scoped_command,
    profile_home,
    profile_route_sessions_path,
    routed_profile_payload,
    routed_text,
    save_profile_route_sessions,
    validate_profile_routes,
)
from gateway.session import SessionSource


def _event(text="hello", **source_kwargs):
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=str(source_kwargs.pop("chat_id", "123")),
        user_id=str(source_kwargs.pop("user_id", "u1")),
        user_name=source_kwargs.pop("user_name", "andrei"),
        thread_id=source_kwargs.pop("thread_id", None),
        chat_type=source_kwargs.pop("chat_type", "dm"),
        **source_kwargs,
    )
    return MessageEvent(text=text, source=source)


def _media_event(text="", media_urls=None, media_types=None, **source_kwargs):
    event = _event(text, **source_kwargs)
    event.media_urls = list(media_urls or [])
    event.media_types = list(media_types or [])
    return event


def test_load_profile_routes_supports_telegram_section():
    routes = load_profile_routes(
        {
            "telegram": {
                "profile_routes": [
                    {"profile": "sasha", "chat_id": 123, "text_prefix": "/sasha"},
                    {"profile": "default", "chat_id": 999},
                    "not-a-route",
                ]
            }
        }
    )

    assert routes == [
        ProfileRoute(
            profile="sasha",
            name="route-1",
            chat_id="123",
            text_prefix="/sasha",
        )
    ]


def test_load_profile_routes_rejects_unsafe_profile_names():
    routes = load_profile_routes(
        {
            "telegram": {
                "profile_routes": [
                    {"profile": "../escape", "chat_id": 123},
                    {"profile": "/tmp/escape", "chat_id": 123},
                    {"profile": "nested/name", "chat_id": 123},
                    {"profile": "safe.profile-1", "chat_id": 123},
                ]
            }
        }
    )

    assert [route.profile for route in routes] == ["safe.profile-1"]


def test_profile_home_rejects_path_escape_names(tmp_path):
    for unsafe in ["../escape", "/tmp/escape", "nested/name", "default"]:
        with pytest.raises(ValueError):
            profile_home(unsafe, root=tmp_path)

    assert profile_home("safe.profile-1", root=tmp_path) == (tmp_path / "profiles" / "safe.profile-1").resolve()


def test_match_profile_route_requires_prefix_boundary():
    route = ProfileRoute(profile="coder", text_prefix="/coder")

    assert match_profile_route(_event("/coder implement"), [route]) is route
    assert match_profile_route(_event("/coder/status"), [route]) is route
    assert match_profile_route(_event("/coder_status"), [route]) is route
    assert match_profile_route(_event("/coderx should not route"), [route]) is None


def test_load_profile_routes_keeps_media_forwarding_opt_in():
    routes = load_profile_routes(
        {
            "telegram": {
                "profile_routes": [
                    {"profile": "plain", "chat_id": 123},
                    {"profile": "media", "chat_id": 456, "pass_media": True},
                ]
            }
        }
    )

    assert routes[0].pass_media is False
    assert routes[1].pass_media is True


def test_routed_profile_payload_ignores_media_unless_enabled():
    route = ProfileRoute(profile="coder", text_prefix="/coder", pass_media=False)
    event = _media_event(
        "/coder what is this?",
        media_urls=["/tmp/diagram.png"],
        media_types=["image/png"],
    )

    payload = routed_profile_payload(event, route)

    assert payload.text == "what is this?"
    assert payload.image_path is None


def test_routed_profile_payload_forwards_first_image_and_media_notes_when_enabled():
    route = ProfileRoute(profile="coder", text_prefix="/coder", pass_media=True)
    event = _media_event(
        "/coder analyze these",
        media_urls=["/tmp/first.png", "/tmp/voice.ogg", "/tmp/second.jpg"],
        media_types=["image/png", "audio/ogg", "image/jpeg"],
    )

    payload = routed_profile_payload(event, route)

    assert payload.image_path == "/tmp/first.png"
    assert payload.text.startswith("analyze these")
    assert "Telegram media attachments" in payload.text
    assert "attached via --image" in payload.text
    assert "/tmp/voice.ogg" in payload.text
    assert "/tmp/second.jpg" in payload.text


def test_build_profile_subprocess_command_can_attach_one_image(monkeypatch):
    monkeypatch.setattr("gateway.profile_router.shutil.which", lambda name: "/usr/bin/hermes")

    cmd = build_profile_subprocess_command(
        text="describe",
        source_tag="telegram-router",
        image_path="/tmp/diagram.png",
    )

    assert cmd == [
        "/usr/bin/hermes",
        "chat",
        "--quiet",
        "--source",
        "telegram-router",
        "--image",
        "/tmp/diagram.png",
        "--query",
        "describe",
    ]


def test_build_profile_subprocess_env_does_not_inherit_gateway_secrets(tmp_path):
    home = tmp_path / "profiles" / "coder"
    parent_env = {
        "PATH": "/usr/bin",
        "HOME": "/home/andrei",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TELEGRAM_BOT_TOKEN": "secret-token",
        "OPENAI_API_KEY": "provider-secret",
        "HERMES_HOME": "/home/andrei/.hermes",
    }

    env = build_profile_subprocess_env(home, parent_env=parent_env)

    assert env["HERMES_HOME"] == str(home)
    assert env["PATH"] == "/usr/bin"
    assert env["LC_ALL"] == "C.UTF-8"
    assert "TELEGRAM_BOT_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env


def test_match_profile_route_by_chat_and_thread():
    routes = [
        ProfileRoute(profile="wrong", chat_id="123", thread_id="2"),
        ProfileRoute(profile="research", chat_id="123", thread_id="7"),
    ]

    match = match_profile_route(_event(chat_id="123", thread_id="7"), routes)

    assert match is routes[1]


def test_match_profile_route_by_command_normalizes_bot_suffix():
    routes = [ProfileRoute(profile="coder", command="code")]

    match = match_profile_route(_event("/code@HermesBot fix tests"), routes)

    assert match is routes[0]


def test_routed_text_strips_prefix_when_enabled():
    route = ProfileRoute(profile="coder", text_prefix="/coder", strip_prefix=True)

    assert routed_text(_event("/coder implement thing"), route) == "implement thing"


def test_routed_text_preserves_prefix_when_disabled():
    route = ProfileRoute(profile="coder", text_prefix="/coder", strip_prefix=False)

    assert routed_text(_event("/coder implement thing"), route) == "/coder implement thing"


def test_extract_session_id_handles_quiet_output():
    assert extract_session_id("done\nSession ID: 20260517_abc\n") == "20260517_abc"
    assert extract_session_id("done\nsession_id=abc:def\n") == "abc:def"


def test_build_profile_subprocess_command_includes_resume(monkeypatch):
    monkeypatch.setattr("gateway.profile_router.shutil.which", lambda name: "/usr/bin/hermes")

    cmd = build_profile_subprocess_command(
        text="hello",
        source_tag="telegram-router",
        resume="sess-1",
    )

    assert cmd == [
        "/usr/bin/hermes",
        "chat",
        "--quiet",
        "--source",
        "telegram-router",
        "--resume",
        "sess-1",
        "--query",
        "hello",
    ]


def test_validate_profile_routes_reports_missing_profiles_and_duplicate_names(tmp_path):
    existing = tmp_path / "profiles" / "research"
    existing.mkdir(parents=True)
    routes = [
        ProfileRoute(profile="research", name="lane"),
        ProfileRoute(profile="missing", name="lane"),
    ]

    warnings = validate_profile_routes(routes, root=tmp_path)

    assert "duplicate route name 'lane'" in "\n".join(warnings)
    assert "profile 'missing' not found" in "\n".join(warnings)


def test_validate_profile_routes_warns_when_target_profile_has_telegram_token(tmp_path):
    profile_home = tmp_path / "profiles" / "research"
    profile_home.mkdir(parents=True)
    (profile_home / ".env").write_text("TELEGRAM_BOT_TOKEN=secret-token\n", encoding="utf-8")

    warnings = validate_profile_routes([ProfileRoute(profile="research", name="research")], root=tmp_path)

    joined = "\n".join(warnings)
    assert "profile 'research' has TELEGRAM_BOT_TOKEN configured" in joined
    assert "secret-token" not in joined


def test_profile_route_sessions_round_trip_json(tmp_path):
    sessions = {
        ("research-agent", "research-topic", "telegram:-100:2:u1"): "session-research",
        ("coder", "coder-prefix", "telegram:dm:u1"): "session-coder",
    }

    save_profile_route_sessions(sessions, root=tmp_path)

    path = profile_route_sessions_path(root=tmp_path)
    assert path == tmp_path / "gateway" / "profile-router-sessions.json"
    loaded = load_profile_route_sessions(root=tmp_path)
    assert loaded == sessions


def test_profile_route_sessions_ignore_malformed_records(tmp_path):
    path = profile_route_sessions_path(root=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"version": 1, "sessions": ['
        '{"profile": "coder", "route": "coder-prefix", "gateway_session_key": "telegram:1", "child_session_id": "child"},'
        '{"profile": "missing-session", "route": "bad", "gateway_session_key": "telegram:2"},'
        '"not-a-record"]}',
        encoding="utf-8",
    )

    assert load_profile_route_sessions(root=tmp_path) == {
        ("coder", "coder-prefix", "telegram:1"): "child"
    }


@pytest.mark.asyncio
async def test_gateway_routes_authorized_telegram_message(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._profile_router_sessions = {}
    runner._is_user_authorized = lambda source: True
    runner._session_key_for_source = lambda source: "telegram:123:u1"

    async def fake_dispatch(event, route, resume_session_id=None):
        assert route.profile == "sasha"
        assert resume_session_id is None
        return "from sasha", "sess-sasha"

    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {
        "telegram": {"profile_routes": [{"profile": "sasha", "chat_id": "123"}]}
    })
    monkeypatch.setattr("gateway.profile_router.dispatch_to_profile", fake_dispatch)

    response = await gateway_run.GatewayRunner._maybe_route_telegram_profile_message(
        runner, _event("hi", chat_id="123"), is_internal=False
    )

    assert response == "from sasha"
    assert runner._profile_router_sessions[("sasha", "route-1", "telegram:123:u1")] == "sess-sasha"


@pytest.mark.asyncio
async def test_gateway_profile_router_keeps_broad_routes_from_swallowing_local_commands(monkeypatch):
    from gateway import run as gateway_run

    runner = object.__new__(gateway_run.GatewayRunner)
    runner._profile_router_sessions = {}
    runner._session_key_for_source = lambda source: "telegram:123:u1"

    async def fail_dispatch(*args, **kwargs):
        raise AssertionError("local gateway command should not be routed")

    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {
        "telegram": {"profile_routes": [{"profile": "sasha", "chat_id": "123"}]}
    })
    monkeypatch.setattr("gateway.profile_router.dispatch_to_profile", fail_dispatch)

    response = await gateway_run.GatewayRunner._maybe_route_telegram_profile_message(
        runner, _event("/help", chat_id="123"), is_internal=False
    )

    assert response is None


@pytest.mark.asyncio
async def test_gateway_profile_router_resumes_previous_child_session(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    runner = object.__new__(gateway_run.GatewayRunner)
    runner._profile_router_sessions = None
    runner._profile_router_sessions_path = tmp_path / "gateway" / "profile-router-sessions.json"
    runner._session_key_for_source = lambda source: "telegram:123:u1"
    save_profile_route_sessions(
        {("sasha", "route-1", "telegram:123:u1"): "child-session"},
        path=runner._profile_router_sessions_path,
    )

    async def fake_dispatch(event, route, resume_session_id=None):
        assert resume_session_id == "child-session"
        return "resumed", "child-session-2"

    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {
        "telegram": {"profile_routes": [{"profile": "sasha", "chat_id": "123"}]}
    })
    monkeypatch.setattr("gateway.profile_router.dispatch_to_profile", fake_dispatch)

    response = await gateway_run.GatewayRunner._maybe_route_telegram_profile_message(
        runner, _event("hi again", chat_id="123"), is_internal=False
    )

    assert response == "resumed"
    assert runner._profile_router_sessions[("sasha", "route-1", "telegram:123:u1")] == "child-session-2"
    assert load_profile_route_sessions(path=runner._profile_router_sessions_path) == {
        ("sasha", "route-1", "telegram:123:u1"): "child-session-2"
    }


def test_parse_profile_scoped_command_supports_prefix_slash_and_telegram_safe_forms():
    route = ProfileRoute(profile="coder", name="coder-prefix", text_prefix="/coder")

    assert parse_profile_scoped_command(_event("/coder/new"), route) == ("new", "")
    assert parse_profile_scoped_command(_event("/coder_new"), route) == ("new", "")
    assert parse_profile_scoped_command(_event("/coder /status --verbose"), route) == (
        "status",
        "--verbose",
    )


def test_parse_profile_scoped_command_ignores_normal_profile_prompts():
    route = ProfileRoute(profile="coder", name="coder-prefix", text_prefix="/coder")

    assert parse_profile_scoped_command(_event("/coder new feature branch"), route) is None
    assert parse_profile_scoped_command(_event("/coder implement status command"), route) is None


@pytest.mark.asyncio
async def test_gateway_profile_scoped_new_clears_child_session_without_dispatch(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    runner = object.__new__(gateway_run.GatewayRunner)
    runner._profile_router_sessions = None
    runner._profile_router_sessions_path = tmp_path / "gateway" / "profile-router-sessions.json"
    runner._session_key_for_source = lambda source: "telegram:123:u1"
    save_profile_route_sessions(
        {("coder", "coder-prefix", "telegram:123:u1"): "old-child"},
        path=runner._profile_router_sessions_path,
    )

    async def fail_dispatch(*args, **kwargs):
        raise AssertionError("profile-scoped /new should not dispatch to the child agent")

    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {
        "telegram": {"profile_routes": [{"name": "coder-prefix", "profile": "coder", "text_prefix": "/coder"}]}
    })
    monkeypatch.setattr("gateway.profile_router.dispatch_to_profile", fail_dispatch)

    response = await gateway_run.GatewayRunner._maybe_route_telegram_profile_message(
        runner, _event("/coder/new", chat_id="123"), is_internal=False
    )

    assert "Started a new session" in response
    assert ("coder", "coder-prefix", "telegram:123:u1") not in runner._profile_router_sessions
    assert load_profile_route_sessions(path=runner._profile_router_sessions_path) == {}


@pytest.mark.asyncio
async def test_gateway_profile_scoped_status_reports_child_session_without_dispatch(monkeypatch, tmp_path):
    from gateway import run as gateway_run

    runner = object.__new__(gateway_run.GatewayRunner)
    runner._profile_router_sessions = None
    runner._profile_router_sessions_path = tmp_path / "gateway" / "profile-router-sessions.json"
    runner._session_key_for_source = lambda source: "telegram:123:u1"
    save_profile_route_sessions(
        {("coder", "coder-prefix", "telegram:123:u1"): "child-session"},
        path=runner._profile_router_sessions_path,
    )

    async def fail_dispatch(*args, **kwargs):
        raise AssertionError("profile-scoped /status should not dispatch to the child agent")

    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {
        "telegram": {"profile_routes": [{"name": "coder-prefix", "profile": "coder", "text_prefix": "/coder"}]}
    })
    monkeypatch.setattr("gateway.profile_router.dispatch_to_profile", fail_dispatch)

    response = await gateway_run.GatewayRunner._maybe_route_telegram_profile_message(
        runner, _event("/coder_status", chat_id="123"), is_internal=False
    )

    assert "Profile route: coder-prefix" in response
    assert "Profile: coder" in response
    assert "Child session: child-session" in response


@pytest.mark.asyncio
async def test_gateway_profile_router_failure_response_hides_child_error(monkeypatch):
    from gateway import run as gateway_run

    runner = object.__new__(gateway_run.GatewayRunner)
    runner._profile_router_sessions = {}
    runner._session_key_for_source = lambda source: "telegram:123:u1"

    async def fail_dispatch(*args, **kwargs):
        raise RuntimeError("provider token leaked in child stderr: secret-token")

    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {
        "telegram": {"profile_routes": [{"profile": "sasha", "chat_id": "123"}]}
    })
    monkeypatch.setattr("gateway.profile_router.dispatch_to_profile", fail_dispatch)

    response = await gateway_run.GatewayRunner._maybe_route_telegram_profile_message(
        runner, _event("hi", chat_id="123"), is_internal=False
    )

    assert response == "❌ Profile routing failed. Check the gateway logs for details."
    assert "secret-token" not in response
