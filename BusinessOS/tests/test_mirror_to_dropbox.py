import json
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import mirror_to_dropbox


def test_run_dropbox_mirror_copies_only_included_paths(tmp_path):
    source_root = tmp_path / 'BusinessOS'
    dropbox_root = tmp_path / 'Dropbox' / 'BusinessOS'
    include_dir = source_root / '05_REPORTS' / 'support'
    ignored_dir = source_root / '04_AUTOMATIONS' / 'scripts'
    include_dir.mkdir(parents=True)
    ignored_dir.mkdir(parents=True)
    included_file = include_dir / 'daily.md'
    included_file.write_text('report v1\n', encoding='utf-8')
    (ignored_dir / 'secret.py').write_text('print("ignore")\n', encoding='utf-8')

    config_path = tmp_path / 'dropbox-mirror.yaml'
    config_path.write_text(
        yaml.safe_dump(
            {
                'source_root': str(source_root),
                'dropbox_root': str(dropbox_root),
                'include_paths': ['05_REPORTS'],
                'prune': False,
            }
        ),
        encoding='utf-8',
    )

    first = mirror_to_dropbox.run_dropbox_mirror(config_path)
    second = mirror_to_dropbox.run_dropbox_mirror(config_path)

    mirrored_file = dropbox_root / '05_REPORTS' / 'support' / 'daily.md'
    ignored_file = dropbox_root / '04_AUTOMATIONS' / 'scripts' / 'secret.py'

    assert first['copied_count'] == 1
    assert mirrored_file.read_text(encoding='utf-8') == 'report v1\n'
    assert not ignored_file.exists()
    assert second['copied_count'] == 0
    assert second['deleted_count'] == 0


def test_run_dropbox_mirror_optionally_prunes_deleted_files(tmp_path):
    source_root = tmp_path / 'BusinessOS'
    dropbox_root = tmp_path / 'Dropbox' / 'BusinessOS'
    source_dir = source_root / '03_DATA' / 'exports'
    source_dir.mkdir(parents=True)
    src_file = source_dir / 'fresh.json'
    src_file.write_text(json.dumps({'ok': True}), encoding='utf-8')

    config_path = tmp_path / 'dropbox-mirror.yaml'
    config_path.write_text(
        yaml.safe_dump(
            {
                'source_root': str(source_root),
                'dropbox_root': str(dropbox_root),
                'include_paths': ['03_DATA/exports'],
                'prune': True,
            }
        ),
        encoding='utf-8',
    )

    mirror_to_dropbox.run_dropbox_mirror(config_path)
    src_file.unlink()

    result = mirror_to_dropbox.run_dropbox_mirror(config_path)

    assert result['deleted_count'] == 1
    assert not (dropbox_root / '03_DATA' / 'exports' / 'fresh.json').exists()


def test_run_dropbox_mirror_supports_single_file_include_paths(tmp_path):
    source_root = tmp_path / 'BusinessOS'
    dropbox_root = tmp_path / 'Dropbox' / 'BusinessOS'
    readme = source_root / 'README.md'
    readme.parent.mkdir(parents=True)
    readme.write_text('# BusinessOS\n', encoding='utf-8')

    config_path = tmp_path / 'dropbox-mirror.yaml'
    config_path.write_text(
        yaml.safe_dump(
            {
                'source_root': str(source_root),
                'dropbox_root': str(dropbox_root),
                'include_paths': ['README.md'],
                'prune': True,
            }
        ),
        encoding='utf-8',
    )

    first = mirror_to_dropbox.run_dropbox_mirror(config_path)
    second = mirror_to_dropbox.run_dropbox_mirror(config_path)

    mirrored_readme = dropbox_root / 'README.md'

    assert first['copied_count'] == 1
    assert first['copied'] == ['README.md']
    assert mirrored_readme.read_text(encoding='utf-8') == '# BusinessOS\n'
    assert second['copied_count'] == 0

    readme.unlink()
    pruned = mirror_to_dropbox.run_dropbox_mirror(config_path)

    assert pruned['deleted_count'] == 1
    assert pruned['deleted'] == ['README.md']
    assert not mirrored_readme.exists()
