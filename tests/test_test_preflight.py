import importlib.util
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
script_path = repo_root / "scripts" / "test_preflight.py"
spec = importlib.util.spec_from_file_location("test_preflight", str(script_path))
test_preflight = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(test_preflight)


def test_find_missing_modules_reports_missing_entries():
    missing = test_preflight.find_missing_modules(
        lambda name: None if name in {"prompt_toolkit", "pytest_asyncio"} else object()
    )

    assert "prompt_toolkit" in missing
    assert "pytest_asyncio" in missing
    assert "xdist" not in missing


def test_main_success_path(capsys, monkeypatch):
    monkeypatch.setattr(test_preflight, "find_missing_modules", lambda find_spec=None: {})

    exit_code = test_preflight.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Hermes test preflight passed." in output
    assert "pytest tests/ -q" in output


def test_main_failure_prints_install_guidance(capsys, monkeypatch):
    monkeypatch.setattr(
        test_preflight,
        "find_missing_modules",
        lambda find_spec=None: {
            "prompt_toolkit": "required by CLI command/help imports used in tests",
            "pytest_asyncio": "required for @pytest.mark.asyncio gateway tests",
        },
    )

    exit_code = test_preflight.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Hermes test preflight failed." in output
    assert 'uv pip install -e ".[all,dev]"' in output
