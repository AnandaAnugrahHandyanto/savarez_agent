import json
import stat
from pathlib import Path

import model_tools


def _fake_preflight(tmp_path: Path, exit_code: int, text: str = "fake preflight") -> Path:
    script = tmp_path / "preflight.py"
    script.write_text(f"#!/usr/bin/env python3\nprint({text!r})\nraise SystemExit({exit_code})\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _selective_preflight(tmp_path: Path, fail_when_contains: str) -> Path:
    script = tmp_path / "selective_preflight.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"needle = {fail_when_contains!r}\n"
        "target = sys.argv[1] if len(sys.argv) > 1 else ''\n"
        "print(target)\n"
        "raise SystemExit(2 if needle in target else 0)\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _disable_user_config(monkeypatch):
    monkeypatch.setattr(model_tools, "_github_guard_load_user_config", lambda: {})


def _enable_guard(monkeypatch, projects: Path, preflight: Path, *, require_branch: bool = True):
    monkeypatch.setenv("HERMES_GITHUB_GOVERNANCE_GUARD", "1")
    monkeypatch.setenv("HERMES_PROJECTS_ROOT", str(projects))
    monkeypatch.setenv("HERMES_GITHUB_PREFLIGHT", str(preflight))
    monkeypatch.setattr(model_tools, "_github_guard_load_user_config", lambda: {})
    monkeypatch.setattr(model_tools, "_github_guard_default_require_branch", lambda: require_branch)


def test_guard_is_disabled_by_default_even_for_project_paths(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _disable_user_config(monkeypatch)
    monkeypatch.delenv("HERMES_GITHUB_GOVERNANCE_GUARD", raising=False)
    monkeypatch.delenv("HERMES_DISABLE_GITHUB_GOVERNANCE_GUARD", raising=False)
    monkeypatch.delenv("HERMES_PROJECTS_ROOT", raising=False)
    monkeypatch.delenv("HERMES_GITHUB_PREFLIGHT", raising=False)

    block = model_tools._github_governance_block_message(
        "write_file",
        {"path": str(projects / "demo" / "app.py"), "content": "x"},
    )

    assert block is None


def test_write_file_under_projects_blocks_when_preflight_fails(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2, "blocked demo"))

    result = model_tools.handle_function_call(
        "write_file",
        {"path": str(projects / "demo" / "app.py"), "content": "print('x')\n"},
    )

    payload = json.loads(result)
    assert "GitHub governance blocker" in payload["error"]
    assert "blocked demo" in payload["error"]
    assert not (projects / "demo" / "app.py").exists()


def test_patch_v4a_under_projects_blocks_when_preflight_fails(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "patch",
        {
            "mode": "patch",
            "patch": "*** Begin Patch\n*** Update File: " + str(projects / "demo" / "app.py") + "\n*** End Patch\n",
        },
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_terminal_mutation_under_projects_blocks(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    result = model_tools.handle_function_call(
        "terminal",
        {"command": "touch file.txt", "workdir": str(projects / "demo")},
    )

    payload = json.loads(result)
    assert "GitHub governance blocker" in payload["error"]


def test_terminal_unknown_command_under_project_checks_preflight(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": "python build.py", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_terminal_read_only_under_projects_does_not_trigger(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": "git status --short --branch", "workdir": str(projects / "demo")},
    )

    assert block is None


def test_read_only_prefix_with_chained_unknown_command_still_blocks(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": "git status --short --branch && python build.py", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_read_only_prefix_with_no_space_redirection_still_blocks(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": "git diff>out.patch", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_read_only_prefix_with_fd_redirection_still_blocks(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": "git diff 2>err.log", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_find_delete_under_project_still_blocks(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": "find . -delete", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_git_output_option_under_project_still_blocks(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": "git diff --output=out.patch", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_preflight_name_substring_does_not_bypass_terminal_guard(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    preflight = _fake_preflight(tmp_path, 2)
    _enable_guard(monkeypatch, projects, preflight)

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": f"echo {preflight.name} && python build.py", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_embedded_project_path_in_terminal_code_triggers_preflight(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 2))

    target = projects / "demo" / "app.py"
    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": f"python -c \"open('{target}', 'w').write('x')\"", "workdir": str(tmp_path)},
    )

    assert block is not None
    assert "GitHub governance blocker" in block


def test_embedded_project_path_with_parent_traversal_checks_resolved_project(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    (projects / "other").mkdir(parents=True)
    preflight = _selective_preflight(tmp_path, "other")
    _enable_guard(monkeypatch, projects, preflight)

    target = projects / "demo" / ".." / "other" / "app.py"
    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": f"python -c \"open('{target}', 'w').write('x')\"", "workdir": str(tmp_path)},
    )

    assert block is not None
    assert str(projects / "other") in block


def test_write_file_allows_when_preflight_passes(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    _enable_guard(monkeypatch, projects, _fake_preflight(tmp_path, 0, "ok"))

    block = model_tools._github_governance_block_message(
        "write_file",
        {"path": str(projects / "demo" / "app.py"), "content": "x"},
    )

    assert block is None


def test_preflight_command_itself_is_not_blocked(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    preflight = _fake_preflight(tmp_path, 2)
    _enable_guard(monkeypatch, projects, preflight)

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": f"{preflight} demo", "workdir": str(projects / "demo")},
    )

    assert block is None


def test_preflight_command_with_chained_mutation_is_not_exempt(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    preflight = _fake_preflight(tmp_path, 0)
    _enable_guard(monkeypatch, projects, preflight)

    block = model_tools._github_governance_block_message(
        "terminal",
        {"command": f"{preflight} {projects / 'demo'} --require-branch && touch file.txt", "workdir": str(projects / "demo")},
    )

    assert block is not None
    assert "not a direct preflight invocation" in block


def test_disable_env_overrides_enabled_config(monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    (projects / "demo").mkdir(parents=True)
    preflight = _fake_preflight(tmp_path, 2)
    monkeypatch.setattr(
        model_tools,
        "_github_guard_load_user_config",
        lambda: {
            "governance": {
                "github_project_guard": {
                    "enabled": True,
                    "projects_root": str(projects),
                    "preflight_command": str(preflight),
                }
            }
        },
    )
    monkeypatch.setenv("HERMES_DISABLE_GITHUB_GOVERNANCE_GUARD", "1")

    block = model_tools._github_governance_block_message(
        "write_file",
        {"path": str(projects / "demo" / "app.py"), "content": "x"},
    )

    assert block is None
