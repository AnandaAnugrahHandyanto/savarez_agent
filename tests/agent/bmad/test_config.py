from agent.bmad.config import merge_bmad_values, resolve_bmad_config


def test_merge_scalars_tables_and_agent_arrays_by_code():
    base = {'communication_language': 'English', 'nested': {'a': 1, 'b': 2}, 'agents': [{'code': 'bmad-agent-pm', 'name': 'John', 'title': 'PM'}, {'code': 'bmad-agent-dev', 'name': 'Amelia'}], 'tags': ['base']}
    override = {'communication_language': 'Romanian', 'nested': {'b': 3, 'c': 4}, 'agents': [{'code': 'bmad-agent-pm', 'name': 'Ion'}, {'code': 'bmad-agent-architect', 'name': 'Winston'}], 'tags': ['override']}
    merged = merge_bmad_values(base, override)
    assert merged['communication_language'] == 'Romanian'
    assert merged['nested'] == {'a': 1, 'b': 3, 'c': 4}
    assert merged['agents'] == [{'code': 'bmad-agent-pm', 'name': 'Ion', 'title': 'PM'}, {'code': 'bmad-agent-dev', 'name': 'Amelia'}, {'code': 'bmad-agent-architect', 'name': 'Winston'}]
    assert merged['tags'] == ['base', 'override']


def test_resolve_bmad_config_reads_layers_in_order(tmp_path):
    bmad = tmp_path / '_bmad'; custom = bmad / 'custom'; custom.mkdir(parents=True)
    (bmad / 'config.toml').write_text('communication_language = "English"\n[paths]\noutput = "docs"\n', encoding='utf-8')
    (bmad / 'config.user.toml').write_text('communication_language = "Romanian"\n', encoding='utf-8')
    (custom / 'config.toml').write_text('[paths]\nplanning = "planning-artifacts"\n', encoding='utf-8')
    (custom / 'config.user.toml').write_text('user_name = "Ere"\n', encoding='utf-8')
    config = resolve_bmad_config(bmad)
    assert config['communication_language'] == 'Romanian'
    assert config['paths'] == {'output': 'docs', 'planning': 'planning-artifacts'}
    assert config['user_name'] == 'Ere'


def test_resolve_bmad_config_reads_real_module_yaml_layers(tmp_path):
    bmad = tmp_path / '_bmad'; (bmad / 'core').mkdir(parents=True); (bmad / 'bmm').mkdir(parents=True)
    (bmad / 'core' / 'config.yaml').write_text('user_name: Ere\ncommunication_language: English\n', encoding='utf-8')
    (bmad / 'bmm' / 'config.yaml').write_text('communication_language: Romanian\nagents:\n  - code: bmad-agent-pm\n    name: John\n', encoding='utf-8')
    config = resolve_bmad_config(bmad)
    assert config['user_name'] == 'Ere'
    assert config['communication_language'] == 'Romanian'
    assert config['agents'][0]['code'] == 'bmad-agent-pm'


def test_default_config_has_safe_bmad_gates():
    from hermes_cli.config import DEFAULT_CONFIG
    bmad = DEFAULT_CONFIG['bmad']
    assert bmad['enabled'] is True
    assert bmad['auto_detect'] is True
    assert bmad['expose_in_skill_index'] is False
    assert bmad['expose_slash_commands'] is True
    assert bmad['max_indexed_skills'] == 80
    assert bmad['allowed_roots'] == []
    assert bmad['disabled_skills'] == []
