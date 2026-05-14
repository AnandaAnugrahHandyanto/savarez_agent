from pathlib import Path

from agent.bmad.models import BmadProject, BmadSkill


def _write_skill(root: Path, rel: str, name: str = 'bmad-help', description: str = 'Help choose workflows.') -> Path:
    skill_dir = root / rel
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(f'''---
name: {name}
description: {description}
---

# {name}
''', encoding='utf-8')
    return skill_dir


def test_bmad_models_are_importable():
    project = BmadProject(project_root=Path('/workspace/app'), bmad_root=Path('/workspace/app/_bmad'), manifest_path=Path('/workspace/app/_bmad/_config/manifest.yaml'), config={}, agents=[], skills=[])
    skill = BmadSkill(name='bmad-help', description='Help choose the right BMAD workflow.', skill_dir=Path('/workspace/app/_bmad/core/bmad-help'), skill_file=Path('/workspace/app/_bmad/core/bmad-help/SKILL.md'), module='core', category='core', frontmatter={'name': 'bmad-help'})
    assert project.bmad_root.name == '_bmad'
    assert skill.identifier == 'bmad:bmad-help'


def test_find_bmad_root_from_nested_directory(tmp_path):
    from agent.bmad.discovery import find_bmad_root, find_project_root
    project = tmp_path / 'project'; nested = project / 'src' / 'feature'; bmad = project / '_bmad'
    nested.mkdir(parents=True); (bmad / '_config').mkdir(parents=True)
    assert find_bmad_root(nested) == bmad
    assert find_project_root(nested) == project


def test_find_bmad_root_returns_none_without_bmad(tmp_path):
    from agent.bmad.discovery import find_bmad_root, find_project_root
    nested = tmp_path / 'project' / 'src'; nested.mkdir(parents=True)
    assert find_bmad_root(nested) is None
    assert find_project_root(nested) is None


def test_find_bmad_root_stops_at_git_root_by_default(tmp_path):
    from agent.bmad.discovery import find_bmad_root
    workspace_bmad = tmp_path / '_bmad'; project = tmp_path / 'project'; nested = project / 'src' / 'feature'
    workspace_bmad.mkdir(); (project / '.git').mkdir(parents=True); nested.mkdir(parents=True)
    assert find_bmad_root(nested) is None
    assert find_bmad_root(nested, stop_at_git_root=False) == workspace_bmad


def test_get_active_bmad_project_returns_config_agents_and_skills(tmp_path):
    from agent.bmad.index import get_active_bmad_project, list_bmad_skills
    project = tmp_path / 'app'; bmad = project / '_bmad'
    (bmad / '_config').mkdir(parents=True)
    (bmad / 'config.toml').write_text('[[agents]]\ncode = "bmad-agent-pm"\nname = "John"\ntitle = "PM"\n', encoding='utf-8')
    _write_skill(bmad, 'core/bmad-help')
    active = get_active_bmad_project(project)
    assert active is not None
    assert active.project_root == project
    assert active.config['agents'][0]['code'] == 'bmad-agent-pm'
    assert active.agents[0].name == 'John'
    assert active.skills[0].name == 'bmad-help'
    assert list_bmad_skills(project)[0].identifier == 'bmad:bmad-help'


def test_manifest_driven_discovery_reads_real_bmad_skill_manifest_shape(tmp_path):
    from agent.bmad.index import list_bmad_skills
    project = tmp_path / 'app'; bmad = project / '_bmad'
    (bmad / '_config').mkdir(parents=True)
    skill_dir = _write_skill(bmad, 'bmm/4-implementation/bmad-quick-dev', 'bmad-quick-dev', 'Quick dev.')
    (bmad / '_config' / 'skill-manifest.csv').write_text('canonicalId,name,description,module,path,install_to_bmad\n"bmad-quick-dev","bmad-quick-dev","Quick dev.","bmm","_bmad/bmm/4-implementation/bmad-quick-dev/SKILL.md","true"\n', encoding='utf-8')
    skills = list_bmad_skills(project)
    assert [(s.name, s.module, s.skill_dir) for s in skills] == [('bmad-quick-dev', 'bmm', skill_dir)]


def test_manifest_yaml_modules_expand_discovery_without_skill_manifest(tmp_path):
    from agent.bmad.index import list_bmad_skills
    project = tmp_path / 'app'; bmad = project / '_bmad'
    (bmad / '_config').mkdir(parents=True)
    skill_dir = _write_skill(bmad, 'tea/workflows/testarch/bmad-tea', 'bmad-tea', 'Tea.')
    (bmad / '_config' / 'manifest.yaml').write_text('modules:\n  - name: tea\n', encoding='utf-8')

    skills = list_bmad_skills(project)

    assert [(s.name, s.module, s.skill_dir) for s in skills] == [('bmad-tea', 'tea', skill_dir)]


def test_find_bmad_root_rejects_symlinked_bmad_root(tmp_path):
    from agent.bmad.discovery import find_bmad_root
    project = tmp_path / 'project'; project.mkdir()
    outside = tmp_path / 'outside-bmad'; outside.mkdir()
    try:
        (project / '_bmad').symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        import pytest; pytest.skip(f'symlinks unavailable: {exc}')

    assert find_bmad_root(project) is None
