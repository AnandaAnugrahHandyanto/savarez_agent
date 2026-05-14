from agent.bmad.invocation import build_bmad_skill_message


def test_build_bmad_skill_message_substitutes_paths_and_instruction(tmp_path):
    project = tmp_path / 'app'; bmad = project / '_bmad'; skill_dir = bmad / 'core' / 'bmad-help'
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text('''---
name: bmad-help
description: Help choose workflows.
---

# Help

Read {project-root}/_bmad/config.toml and use {skill-root}.
''', encoding='utf-8')
    message = build_bmad_skill_message('bmad-help', 'what next?', start_path=project)
    assert message is not None
    assert '[IMPORTANT: The user invoked BMAD project skill "bmad-help"' in message
    assert str(project) in message
    assert str(skill_dir) in message
    assert 'what next?' in message
    assert '{project-root}' not in message
    assert '{skill-root}' not in message


def test_build_bmad_skill_message_returns_none_when_no_project(tmp_path):
    assert build_bmad_skill_message('bmad-help', start_path=tmp_path) is None
