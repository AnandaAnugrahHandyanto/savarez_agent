"""Tests for plugin-owned plaintext gateway command aliases."""

from gateway.config import Platform
from gateway.platforms.base import MessageEvent, coerce_plaintext_gateway_command
from gateway.session import SessionSource


def _make_event(text: str, *, chat_type: str = "dm") -> MessageEvent:
    return MessageEvent(
        text=text,
        message_id="m1",
        source=SessionSource(
            platform=Platform.TELEGRAM,
            user_id="u1",
            chat_id="c1",
            user_name="tester",
            chat_type=chat_type,
        ),
    )


def test_plugin_plaintext_alias_rewrites_dm(monkeypatch):
    """Exact plugin aliases are rewritten to slash commands in DMs."""
    monkeypatch.setattr(
        "hermes_cli.plugins.resolve_plaintext_command_alias",
        lambda text, *, is_dm=True: "mycmd" if text == "aliascmd" and is_dm else None,
    )
    event = _make_event("aliascmd")

    coerce_plaintext_gateway_command(event)

    assert event.text == "/mycmd"


def test_plugin_plaintext_alias_rewrites_first_token_args(monkeypatch):
    """First-token plugin aliases preserve the message remainder as command args."""
    monkeypatch.setattr(
        "hermes_cli.plugins.resolve_plaintext_command_alias",
        lambda text, *, is_dm=True: "mycmd do it" if text == "aliascmd do it" and is_dm else None,
    )
    event = _make_event("aliascmd do it")

    coerce_plaintext_gateway_command(event)

    assert event.text == "/mycmd do it"


def test_plugin_plaintext_alias_group_stays_plain_text_by_default(monkeypatch):
    """Plugin plaintext aliases remain DM-scoped unless the plugin opts out."""
    monkeypatch.setattr(
        "hermes_cli.plugins.resolve_plaintext_command_alias",
        lambda text, *, is_dm=True: "mycmd" if text == "aliascmd" and is_dm else None,
    )
    event = _make_event("aliascmd", chat_type="group")

    coerce_plaintext_gateway_command(event)

    assert event.text == "aliascmd"


def test_plugin_plaintext_alias_group_can_be_allowed_by_plugin(monkeypatch):
    """Plugins can opt an alias into non-DM chats through resolver metadata."""
    monkeypatch.setattr(
        "hermes_cli.plugins.resolve_plaintext_command_alias",
        lambda text, *, is_dm=True: "mycmd" if text == "aliascmd" and not is_dm else None,
    )
    event = _make_event("aliascmd", chat_type="group")

    coerce_plaintext_gateway_command(event)

    assert event.text == "/mycmd"


def test_plugin_plaintext_alias_exception_preserves_text(monkeypatch):
    """Alias lookup failures never break message processing."""
    def _raise(_text, *, is_dm=True):
        raise RuntimeError("plugin failed")

    monkeypatch.setattr("hermes_cli.plugins.resolve_plaintext_command_alias", _raise)
    event = _make_event("aliascmd")

    coerce_plaintext_gateway_command(event)

    assert event.text == "aliascmd"


def test_plugin_plaintext_alias_registration_to_gateway_rewrite(tmp_path, monkeypatch):
    """Real plugin alias registration feeds the gateway plaintext rewrite path."""
    plugin_dir = tmp_path / "plugins" / "alias-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        "name: alias-plugin\nversion: 0.1.0\ndescription: alias test\n",
        encoding="utf-8",
    )
    (plugin_dir / "__init__.py").write_text(
        "def register(ctx):\n"
        "    ctx.register_command('mycmd', lambda args: args)\n"
        "    ctx.register_plaintext_command_alias(\n"
        "        'aliascmd', target_command='mycmd', first_token=True, dm_only=False\n"
        "    )\n",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - alias-plugin\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    import hermes_cli.plugins as plugins_mod

    monkeypatch.setattr(plugins_mod, "_plugin_manager", None)
    event = _make_event("AliasCmd do it", chat_type="group")

    coerce_plaintext_gateway_command(event)

    assert event.text == "/mycmd do it"
