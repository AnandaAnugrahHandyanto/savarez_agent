import json
from pathlib import Path


def test_lazyhermes_registers_commands_hook_and_skills(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - lazyhermes\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HERMES_BUNDLED_PLUGINS", str(Path(__file__).resolve().parents[2] / "plugins"))

    import hermes_cli.plugins as plugins_mod
    from hermes_cli.plugins import get_plugin_commands, invoke_hook
    from tools.skills_tool import skill_view

    monkeypatch.setattr(plugins_mod, "_plugin_manager", None)

    commands = get_plugin_commands()
    assert {"ulw", "ulw-plan", "ultrawork-plan", "ulw-loop", "ultrawork-loop", "start-work"} <= set(commands)

    hook_results = invoke_hook(
        "pre_llm_call",
        session_id="s1",
        user_message="please use ulw for this",
        conversation_history=[],
        is_first_turn=True,
        model="test",
    )
    assert hook_results
    assert "lazyhermes-ultrawork" in hook_results[0]["context"]
    assert "lazyhermes-goal-bootstrap" in hook_results[0]["context"]
    assert "First call get_goal" in hook_results[0]["context"]
    assert '"status": "active"' in hook_results[0]["context"]

    result = json.loads(skill_view("lazyhermes:ultrawork"))
    assert result["success"] is True
    assert "LazyHermes Ultrawork" in result["content"]


def test_lazyhermes_bundled_plugin_auto_loads_without_enabled_config(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text("plugins:\n  enabled: []\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HERMES_BUNDLED_PLUGINS", str(Path(__file__).resolve().parents[2] / "plugins"))

    import hermes_cli.plugins as plugins_mod
    from hermes_cli.plugins import get_plugin_commands

    monkeypatch.setattr(plugins_mod, "_plugin_manager", None)

    commands = get_plugin_commands()

    assert "ulw" in commands
    assert "ulw-loop" in commands
    assert "ulw-plan" in commands


def test_ulw_plan_command_creates_plan_and_goal_dispatch(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)

    from plugins.lazyhermes import core

    result = core.command_ulw_plan('"Retrofit Hermes with LazyCodex patterns"')

    assert result["display"].startswith("Created LazyHermes plan")
    assert "Forwarding goal bootstrap to Hermes agent now." in result["display"]
    created = tmp_path / "plans" / "retrofit-hermes-with-lazycodex-patterns.md"
    assert created.exists()
    assert "Completion Promise" in created.read_text(encoding="utf-8")
    assert result["plan"] == str(created)
    assert result["agent_message"].startswith("Retrofit Hermes with LazyCodex patterns")
    assert str(created) in result["agent_message"]
    assert "<lazyhermes-goal-instruction>" in result["agent_message"]
    assert "First call get_goal" in result["agent_message"]
    assert "create_goal payload" in result["agent_message"]
    assert '"status": "active"' in result["agent_message"]
    assert "update_goal" in result["agent_message"]


def test_ulw_plan_goal_dispatch_handles_existing_goal_before_create(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)

    from plugins.lazyhermes import core

    result = core.command_ulw_plan('"Respect active Codex goal"')

    assert "If get_goal reports the same objective as active, continue without creating a duplicate" in result["agent_message"]
    assert "If get_goal reports a different active goal, finish or checkpoint it before starting this plan" in result["agent_message"]


def test_ulw_loop_command_creates_local_run_state_and_agent_dispatch(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)

    from plugins.lazyhermes import core

    result = core.command_ulw_loop(
        '"Ship plugin" --completion-promise "commands and skills work" --strategy reset'
    )

    assert result["display"].startswith("Started LazyHermes Ultrawork run")
    assert result["agent_message"].startswith("Ship plugin")
    assert "<lazyhermes-run-context>" in result["agent_message"]
    assert "Ship plugin" in result["agent_message"]
    assert "commands and skills work" in result["display"]
    run_dirs = list((tmp_path / ".hermes" / "lazyhermes" / "runs").glob("lazyhermes-*"))
    assert len(run_dirs) == 1
    state = json.loads((run_dirs[0] / "state.json").read_text(encoding="utf-8"))
    assert state["command"] == "ulw-loop"
    assert state["task"] == "Ship plugin"
    assert state["completion_promise"] == "commands and skills work"
    assert state["strategy"] == "reset"
    assert (run_dirs[0] / "ledger.jsonl").exists()
    assert result["run_dir"] == str(run_dirs[0])


def test_ulw_alias_command_creates_dispatch_payload(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)

    from plugins.lazyhermes import core

    result = core.command_ulw('"Summarize this folder"')

    assert result["display"].startswith("Started LazyHermes Ultrawork run")
    assert result["agent_message"].startswith("Summarize this folder")
    assert "<lazyhermes-run-context>" in result["agent_message"]
    run_dirs = list((tmp_path / ".hermes" / "lazyhermes" / "runs").glob("lazyhermes-*"))
    assert len(run_dirs) == 1
    state = json.loads((run_dirs[0] / "state.json").read_text(encoding="utf-8"))
    assert state["command"] == "ulw"


def test_bare_ulw_pre_llm_call_creates_run_context(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)

    from plugins.lazyhermes import core

    result = core.pre_llm_call(
        session_id="s1",
        user_message="ulw analyze this folder",
        conversation_history=[],
        is_first_turn=True,
        model="test",
    )

    assert result is not None
    assert "lazyhermes-run-context" in result["context"]
    assert "lazyhermes-goal-instruction" in result["context"]
    assert "First call get_goal" in result["context"]
    assert '"status": "active"' in result["context"]
    assert "analyze this folder" in result["context"]
    run_dirs = list((tmp_path / ".hermes" / "lazyhermes" / "runs").glob("lazyhermes-*"))
    assert len(run_dirs) == 1


def test_pre_llm_call_does_not_duplicate_internal_dispatch_context(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)

    from plugins.lazyhermes import core

    result = core.pre_llm_call(
        session_id="s1",
        user_message="Ship\n\n<lazyhermes-run-context>\ntask: Ship\n</lazyhermes-run-context>",
        conversation_history=[],
        is_first_turn=True,
        model="test",
    )

    assert result is None
    run_root = tmp_path / ".hermes" / "lazyhermes" / "runs"
    assert not run_root.exists()


def test_start_work_dry_run_reads_plan_items(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)
    plans = tmp_path / "plans"
    plans.mkdir()
    plan = plans / "demo.md"
    plan.write_text(
        "# Demo\n\n- [ ] First task\n- [x] Done task\n- [ ] Second task\n",
        encoding="utf-8",
    )

    from plugins.lazyhermes import core

    message = core.command_start_work("demo --dry-run")

    assert f"LazyHermes dry-run for {plan}" in message
    assert "First task" in message
    assert "Second task" in message
    assert "Done task" not in message


def test_start_work_creates_run_for_plan(tmp_path, monkeypatch):
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.chdir(tmp_path)
    plans = tmp_path / "plans"
    plans.mkdir()
    plan = plans / "demo.md"
    plan.write_text("# Demo\n\n- [ ] First task\n", encoding="utf-8")

    from plugins.lazyhermes import core

    message = core.command_start_work("demo")

    assert "Started LazyHermes work run" in message
    run_dirs = list((tmp_path / ".hermes" / "lazyhermes" / "runs").glob("lazyhermes-*"))
    assert len(run_dirs) == 1
    state = json.loads((run_dirs[0] / "state.json").read_text(encoding="utf-8"))
    assert state["plan"] == str(plan.resolve())
