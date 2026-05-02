"""Tests for tools/codex_job_tool.py."""

import json
import subprocess


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _make_repo(tmp_path):
    repo = tmp_path / "FocusLock"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    (repo / "README.md").write_text("# FocusLock\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return repo


def test_start_worktree_creates_codex_shaped_worktree_without_launching(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    repo = _make_repo(tmp_path)

    from tools.codex_job_tool import codex_job_tool

    result = json.loads(codex_job_tool({
        "action": "start",
        "title": "Fix onboarding bug",
        "prompt": "Inspect only; do not modify files.",
        "repo_path": str(repo),
        "workspace_mode": "worktree",
        "launch": False,
        "discord": False,
    }))

    assert result["success"] is True
    assert result["workspace_mode"] == "worktree"
    assert result["job_id"]
    assert result["worktree_path"].startswith(str(tmp_path / ".codex" / "worktrees" / result["job_id"]))
    assert result["branch"] == f"codex/fix-onboarding-bug-{result['job_id']}"
    assert result["tmux_session"] == f"codex-{result['job_id']}"
    assert result["attach_command"] == f"tmux attach -t codex-{result['job_id']}"
    assert _git(result["worktree_path"], "rev-parse", "--show-toplevel") == result["worktree_path"]
    assert _git(result["worktree_path"], "branch", "--show-current") == result["branch"]


def test_start_local_uses_existing_checkout_without_worktree(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    repo = _make_repo(tmp_path)

    from tools.codex_job_tool import codex_job_tool

    result = json.loads(codex_job_tool({
        "action": "start",
        "title": "Local FocusLock task",
        "prompt": "Inspect only.",
        "repo_path": str(repo),
        "workspace_mode": "local",
        "launch": False,
        "discord": False,
    }))

    assert result["success"] is True
    assert result["workspace_mode"] == "local"
    assert result["worktree_path"] is None
    assert result["workspace_path"] == str(repo.resolve())
    assert result["branch"] == "main"


def test_start_scratch_creates_documents_codex_git_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from tools.codex_job_tool import codex_job_tool

    result = json.loads(codex_job_tool({
        "action": "start",
        "title": "Research calorie app idea",
        "prompt": "Research only.",
        "workspace_mode": "scratch",
        "launch": False,
        "discord": False,
    }))

    assert result["success"] is True
    assert result["workspace_mode"] == "scratch"
    assert result["workspace_path"].startswith(str(tmp_path / "Documents" / "Codex"))
    assert result["branch"] == "main"
    assert _git(result["workspace_path"], "rev-parse", "--is-inside-work-tree") == "true"
    for name in ["inputs", "outputs", "scripts", "scratch"]:
        assert (tmp_path / "Documents" / "Codex").joinpath(*result["workspace_path"].split("/Documents/Codex/", 1)[1].split("/"), name).exists()


def test_build_tmux_commands_include_no_alt_screen_log_and_prompt(tmp_path):
    from tools.codex_job_tool import _build_tmux_commands

    workspace = tmp_path / "FocusLock"
    workspace.mkdir()
    log_path = tmp_path / "job.log"
    commands = _build_tmux_commands(
        session="codex-abcd",
        workspace_path=workspace,
        prompt="Do the task safely",
        log_path=log_path,
        model="gpt-5.5",
        approval="never",
        sandbox="workspace-write",
    )

    joined = "\n".join(commands)
    assert "tmux new-session -d -s codex-abcd" in joined
    assert "codex -C" in joined
    assert "--no-alt-screen" in joined
    assert "-m gpt-5.5" in joined
    assert "-a never" in joined
    assert "-s workspace-write" in joined
    assert "Do the task safely" in joined
    assert "tmux pipe-pane -o -t codex-abcd" in joined
    assert str(log_path) in joined


def test_codex_job_registration_does_not_gate_terminal_toolset():
    from tools.codex_job_tool import registry

    entry = registry.get_entry("codex_job")
    assert entry is not None
    assert entry.toolset == "terminal"
    assert entry.check_fn is None


def test_status_reads_job_record(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    repo = _make_repo(tmp_path)

    from tools.codex_job_tool import codex_job_tool

    start = json.loads(codex_job_tool({
        "action": "start",
        "title": "Status test",
        "prompt": "Inspect only.",
        "repo_path": str(repo),
        "workspace_mode": "local",
        "launch": False,
        "discord": False,
    }))
    status = json.loads(codex_job_tool({"action": "status", "job_id": start["job_id"]}))

    assert status["success"] is True
    assert status["job"]["job_id"] == start["job_id"]
    assert status["job"]["workspace_path"] == str(repo.resolve())
    assert status["tmux_alive"] is False


def test_monitor_status_surfaces_key_findings_and_workspace_changes(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "README.md").write_text("# FocusLock\n\nChanged\n", encoding="utf-8")

    from tools.codex_job_tool import _render_monitor_status

    job = {
        "job_id": "abcd",
        "title": "Critical bug hunt",
        "workspace_path": str(repo),
        "branch": "codex/critical-bug-abcd",
        "model": "gpt-5.5",
        "effort": "xhigh",
        "attach_command": "tmux attach -t codex-abcd",
    }
    output = """
• Explored
  └ Read HabitServices.swift

• I found one high-confidence Major bug to fix:

Bug: Free-tier habit access is only enforced at creation time.
Severity: Major. Existing over-limit habits remain user-visible after downgrade.
Root cause: PlanLimitEnforcer only has schedule/mode enforcement.
Planned fix: Apply habit limits at presentation and reminder boundaries.

• Ran swift test
"""

    message = _render_monitor_status(job, alive=True, output=output)

    assert "**Task summary / key findings**" in message
    assert "Bug: Free-tier habit access" in message
    assert "Root cause: PlanLimitEnforcer" in message
    assert "**Workspace changes**" in message
    assert "README.md" in message
    assert "**Recent useful activity**" in message
    assert len(message) <= 3900


def test_monitor_status_surfaces_generic_task_summary_for_non_bug_tasks(tmp_path):
    repo = _make_repo(tmp_path)

    from tools.codex_job_tool import _render_monitor_status

    job = {
        "job_id": "ef01",
        "title": "Build onboarding analytics",
        "workspace_path": str(repo),
        "branch": "codex/onboarding-analytics-ef01",
        "model": "gpt-5.5",
        "effort": "high",
        "attach_command": "tmux attach -t codex-ef01",
    }
    output = """
• Explored
  └ Read AnalyticsService.swift and OnboardingView.swift

Objective: Add privacy-safe onboarding funnel instrumentation.
Approach: Introduce an AnalyticsEvent enum and emit step-complete events from the view model.
Decision: Keep event payloads aggregate-only; no user-entered text.
Next step: Add tests for event emission and wire the sink into app services.

• Edited AnalyticsService.swift
"""

    message = _render_monitor_status(job, alive=True, output=output)

    assert "**Task summary / key findings**" in message
    assert "Objective: Add privacy-safe onboarding funnel instrumentation." in message
    assert "Approach: Introduce an AnalyticsEvent enum" in message
    assert "Decision: Keep event payloads aggregate-only" in message
    assert "Next step: Add tests for event emission" in message
    assert "**Bug / key findings**" not in message
    assert "**Recent useful activity**" in message
