"""Test that setup.py has shutil available for Matrix E2EE auto-install."""
import ast
from types import SimpleNamespace


def _parse_setup_imports():
    """Parse setup.py and return top-level import names."""
    with open("hermes_cli/setup.py") as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.name)
    return names


class TestSetupShutilImport:
    def test_shutil_imported_at_module_level(self):
        """shutil must be imported at module level so setup_gateway can use it
        for the mautrix auto-install path."""
        names = _parse_setup_imports()
        assert "shutil" in names, (
            "shutil is not imported at the top of hermes_cli/setup.py. "
            "This causes a NameError when the Matrix E2EE auto-install "
            "tries to call shutil.which('uv')."
        )


def test_setup_matrix_e2ee_installs_missing_companion_deps(monkeypatch):
    """E2EE setup must install missing companion deps, not just mautrix itself."""
    import hermes_cli.setup as setup_mod
    import tools.lazy_deps as lazy_deps

    saved_env = {}
    prompts = iter([
        "https://matrix-client.matrix.org",
        "secret-token",
        "@bot:matrix.org",
        "",
        "",
    ])
    install_calls = []

    monkeypatch.setattr(setup_mod, "get_env_value", lambda key: saved_env.get(key, ""))
    monkeypatch.setattr(setup_mod, "save_env_value", lambda key, value: saved_env.__setitem__(key, value))
    monkeypatch.setattr(setup_mod, "prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(setup_mod, "prompt_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(setup_mod, "print_header", lambda *args, **kwargs: None)
    monkeypatch.setattr(setup_mod, "print_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(setup_mod, "print_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(setup_mod, "print_warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(setup_mod.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
    monkeypatch.setattr(lazy_deps, "feature_missing", lambda feature: ("asyncpg==0.31.0",))
    monkeypatch.setattr(
        lazy_deps,
        "feature_specs",
        lambda feature: (
            "mautrix[encryption]==0.21.0",
            "Markdown==3.10.2",
            "aiosqlite==0.22.1",
            "asyncpg==0.31.0",
            "aiohttp-socks==0.11.0",
        ),
    )

    def fake_run(args, capture_output=True, text=True):
        install_calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    setup_mod._setup_matrix()

    assert install_calls == [[
        "/usr/bin/uv",
        "pip",
        "install",
        "--python",
        setup_mod.sys.executable,
        "asyncpg==0.31.0",
    ]]
    assert saved_env["MATRIX_ENCRYPTION"] == "true"
