from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_TESTS = REPO_ROOT / "scripts" / "run_tests.sh"


def _script_text() -> str:
    return RUN_TESTS.read_text(encoding="utf-8")


def test_run_tests_uses_git_common_dir_for_shared_venv_fallback():
    source = _script_text()

    assert 'git rev-parse --path-format=absolute --git-common-dir' in source
    assert 'SHARED_REPO_ROOT="${GIT_COMMON_DIR%/.git}"' in source
    assert '"$SHARED_REPO_ROOT/venv"' in source


def test_run_tests_full_suite_requires_optional_extras_and_repairs_pip():
    source = _script_text()

    assert 'NEEDS_FULL_SUITE_ENV=1' in source
    assert 'if [[ "$arg" != -* ]]; then' in source
    assert 'if [ "$#" -eq 0 ] || [ "$NEEDS_FULL_SUITE_ENV" -eq 1 ]; then' in source
    for module_name in ("acp", "dingtalk_stream", "fastapi", "faster_whisper"):
        assert f'"{module_name}"' in source
    assert '"$PYTHON" -m ensurepip --upgrade' in source
    assert 'pip is unavailable in $VENV and ensurepip could not restore it' in source


def test_run_tests_preserves_argument_forwarding_for_targeted_runs():
    source = _script_text()

    assert 'PYTEST_CMD=(' in source
    assert 'if [ "$#" -gt 0 ]; then' in source
    assert 'PYTEST_CMD+=("$@")' in source
    assert 'exec "${PYTEST_CMD[@]}"' in source
