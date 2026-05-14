from agent.bmad.discovery import build_bmad_fingerprint, discover_bmad_skills
from agent.bmad.skill_loader import load_bmad_skill, resolve_bmad_resource


def _write_bmad_skill(root, module, name, description='BMAD skill'):
    skill_dir = root / module / name
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(f'''---
name: {name}
description: {description}
---

# {name}

Use {{project-root}} and {{skill-root}} safely.
''', encoding='utf-8')
    (skill_dir / 'references').mkdir()
    (skill_dir / 'references' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    return skill_dir


def test_discover_bmad_skills_under_core_and_bmm(tmp_path):
    bmad = tmp_path / '_bmad'
    _write_bmad_skill(bmad, 'core', 'bmad-help', 'Help choose workflows')
    _write_bmad_skill(bmad, 'bmm', 'bmad-prd', 'Create or validate a PRD')
    skills = discover_bmad_skills(bmad)
    assert [skill.name for skill in skills] == ['bmad-help', 'bmad-prd']
    assert skills[0].module == 'core'
    assert skills[1].module == 'bmm'
    assert skills[1].identifier == 'bmad:bmad-prd'


def test_load_bmad_skill_rejects_path_traversal_resource(tmp_path):
    bmad = tmp_path / '_bmad'; skill_dir = _write_bmad_skill(bmad, 'core', 'bmad-help')
    skill = load_bmad_skill(skill_dir, module='core')
    assert skill is not None
    assert skill.name == 'bmad-help'
    assert resolve_bmad_resource(skill, '../secret.txt') is None


def test_resolve_bmad_resource_allows_only_linked_resource_dirs(tmp_path):
    bmad = tmp_path / '_bmad'; skill_dir = _write_bmad_skill(bmad, 'core', 'bmad-help')
    (skill_dir / 'notes.md').write_text('private note', encoding='utf-8')
    skill = load_bmad_skill(skill_dir, module='core')
    assert resolve_bmad_resource(skill, 'references/guide.md') == skill_dir / 'references' / 'guide.md'
    assert resolve_bmad_resource(skill, 'notes.md') is None


def test_resolve_bmad_resource_rejects_symlink_escape(tmp_path):
    bmad = tmp_path / '_bmad'; outside = tmp_path / 'outside.md'; outside.write_text('outside', encoding='utf-8')
    skill_dir = _write_bmad_skill(bmad, 'core', 'bmad-help')
    link = skill_dir / 'references' / 'outside.md'
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        import pytest; pytest.skip(f'symlinks unavailable: {exc}')
    skill = load_bmad_skill(skill_dir, module='core')
    assert resolve_bmad_resource(skill, 'references/outside.md') is None


def test_bmad_fingerprint_changes_when_nested_skill_changes(tmp_path):
    bmad = tmp_path / '_bmad'; skill_dir = _write_bmad_skill(bmad, 'core', 'bmad-help')
    before = build_bmad_fingerprint(bmad)
    (skill_dir / 'SKILL.md').write_text('''---
name: bmad-help
description: Changed.
---

# Changed
''', encoding='utf-8')
    after = build_bmad_fingerprint(bmad)
    assert before != after


def test_bmad_fingerprint_includes_config_and_manifest(tmp_path):
    bmad = tmp_path / '_bmad'; _write_bmad_skill(bmad, 'core', 'bmad-help')
    before = build_bmad_fingerprint(bmad)
    (bmad / 'config.toml').write_text('communication_language = "Romanian"\n', encoding='utf-8')
    (bmad / '_config').mkdir(); (bmad / '_config' / 'manifest.yaml').write_text('modules: []\n', encoding='utf-8')
    after = build_bmad_fingerprint(bmad)
    assert before != after


def test_load_bmad_skill_rejects_symlinked_skill_file_escape(tmp_path):
    bmad = tmp_path / '_bmad'
    skill_dir = bmad / 'core' / 'bmad-help'
    skill_dir.mkdir(parents=True)
    outside = tmp_path / 'outside.md'
    outside.write_text('''---
name: bmad-help
description: outside
---
# outside
''', encoding='utf-8')
    try:
        (skill_dir / 'SKILL.md').symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        import pytest; pytest.skip(f'symlinks unavailable: {exc}')

    assert load_bmad_skill(skill_dir, module='core') is None


def test_load_bmad_skill_rejects_missing_frontmatter(tmp_path):
    bmad = tmp_path / '_bmad'
    skill_dir = bmad / 'core' / 'bmad-help'
    skill_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text('# No frontmatter\n', encoding='utf-8')

    assert load_bmad_skill(skill_dir, module='core') is None
