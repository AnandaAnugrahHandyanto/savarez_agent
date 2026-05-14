from unittest.mock import patch

from agent.bmad.index import list_bmad_skills


def _project_with_skill(tmp_path):
    project = tmp_path / 'app'; skill_dir = project / '_bmad' / 'core' / 'bmad-help'
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text('''---
name: bmad-help
description: Help.
---

# Help
''', encoding='utf-8')
    return project


def test_bmad_disabled_hides_project_skills(tmp_path):
    project = _project_with_skill(tmp_path)
    with patch('hermes_cli.config.load_config', return_value={'bmad': {'enabled': False}}):
        assert list_bmad_skills(project) == []


def test_disabled_bmad_skill_is_filtered(tmp_path):
    project = _project_with_skill(tmp_path)
    with patch('hermes_cli.config.load_config', return_value={'bmad': {'enabled': True, 'disabled_skills': ['bmad-help']}}):
        assert list_bmad_skills(project) == []


def test_allowed_roots_blocks_outside_project(tmp_path):
    project = _project_with_skill(tmp_path); allowed = str(tmp_path / 'other')
    with patch('hermes_cli.config.load_config', return_value={'bmad': {'enabled': True, 'allowed_roots': [allowed]}}):
        assert list_bmad_skills(project) == []
