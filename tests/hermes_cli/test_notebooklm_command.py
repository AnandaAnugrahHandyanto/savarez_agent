from hermes_cli.notebooklm_command import (
    build_notebooklm_learnpack_prompt,
    notebooklm_usage,
)


def test_blank_args_return_empty_prompt():
    assert build_notebooklm_learnpack_prompt("") == ""
    assert "Usage: /notebooklm" in notebooklm_usage()


def test_topic_prompt_preserves_chinese_payload_and_uses_shared_dir_placeholder():
    prompt = build_notebooklm_learnpack_prompt("知识库里的 agent memory")

    assert "Run the NotebookLM LearnPack workflow for: 知识库里的 agent memory" in prompt
    assert "Preserve the user's original topic/source text exactly: 知识库里的 agent memory" in prompt
    assert "<shared-dir>/docs/notebooklm-learning/" in prompt
    assert "/Users/myartings/Sync" in prompt
    assert "/home/myartings/Sync" in prompt
    assert r"C:\Users\myartings\Sync" in prompt
    assert "<shared-dir>/docs/handoffs/" in prompt
    assert "Research Handoff draft" in prompt
    assert "candidate KB updates only" in prompt


def test_route_hints_for_kb_repo_url_and_inbox():
    assert "kb-notebooklm-bundler Flow B" in build_notebooklm_learnpack_prompt("kb agentic engineering")
    assert "repository source" in build_notebooklm_learnpack_prompt("repo https://github.com/user/project")
    assert "URL source" in build_notebooklm_learnpack_prompt("url https://example.com/article")
    assert "NotebookLM inbox" in build_notebooklm_learnpack_prompt("inbox ai-memory")


def test_prompt_gates_kb_writes_and_project_execution():
    prompt = build_notebooklm_learnpack_prompt("vibe coding")

    assert "Do not directly overwrite long-term wiki pages" in prompt
    assert "Formal KB ingest must go through the existing KB preflight/review/check/sync flow" in prompt
    assert "Do not start Happy/Codex project execution automatically" in prompt
