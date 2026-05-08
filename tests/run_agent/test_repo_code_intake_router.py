from pathlib import Path

from hermes_cli import kanban_db as kb


def test_repo_code_intake_routes_to_kanban_without_model_call(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    codex_profile = home / "profiles" / "codex"
    codex_profile.mkdir(parents=True)
    (codex_profile / "config.yaml").write_text("model: {}\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    import run_agent

    monkeypatch.setattr(run_agent, "_detect_repo_code_intake", lambda _msg: repo)

    agent = run_agent.AIAgent(
        api_key="test",
        base_url="https://openrouter.ai/api/v1",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )
    result = agent.run_conversation("implemente algo em /home/ubuntu/repos/example")

    assert result["api_calls"] == 0
    assert result["turn_exit_reason"] == "repo_code_intake_routed"
    assert "Roteei essa tarefa de código para o Kanban" in result["final_response"]

    with kb.connect() as conn:
        tasks = kb.list_tasks(conn)
    assert len(tasks) == 1
    task = tasks[0]
    assert task.assignee == "codex"
    assert task.workspace_kind == "dir"
    assert task.workspace_path == str(repo)
    assert task.skills == ["prd-phased-codex"]
