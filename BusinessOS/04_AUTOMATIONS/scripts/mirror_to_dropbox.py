from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    data.setdefault('include_paths', [])
    data.setdefault('prune', False)
    return data


def _iter_files(root: Path):
    if not root.exists():
        return
    for path in sorted(root.rglob('*')):
        if path.is_file():
            yield path


def _needs_copy(source: Path, target: Path) -> bool:
    if not target.exists():
        return True
    source_stat = source.stat()
    target_stat = target.stat()
    return not (
        source_stat.st_size == target_stat.st_size
        and int(source_stat.st_mtime) == int(target_stat.st_mtime)
    )


def _delete_target_path(target_path: Path, include_path: Path) -> list[str]:
    if not target_path.exists():
        return []

    if target_path.is_file():
        target_path.unlink()
        return [include_path.as_posix()]

    deleted = [
        str((include_path / file_path.relative_to(target_path)).as_posix())
        for file_path in _iter_files(target_path)
    ]
    shutil.rmtree(target_path)
    return deleted


def run_dropbox_mirror(config_path: str | Path) -> dict[str, Any]:
    config = load_config(config_path)
    source_root = Path(config['source_root']).expanduser()
    dropbox_root = Path(config['dropbox_root']).expanduser()
    include_paths = [Path(part) for part in config.get('include_paths', [])]
    prune = bool(config.get('prune', False))

    dropbox_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    deleted: list[str] = []

    for include_path in include_paths:
        source_path = source_root / include_path
        target_path = dropbox_root / include_path

        if not source_path.exists():
            if prune:
                deleted.extend(_delete_target_path(target_path, include_path))
            continue

        if source_path.is_file():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if _needs_copy(source_path, target_path):
                shutil.copy2(source_path, target_path)
                copied.append(include_path.as_posix())
            continue

        target_path.mkdir(parents=True, exist_ok=True)

        source_files = {path.relative_to(source_path) for path in _iter_files(source_path)}
        for relative_path in sorted(source_files):
            source_file = source_path / relative_path
            target_file = target_path / relative_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            if _needs_copy(source_file, target_file):
                shutil.copy2(source_file, target_file)
                copied.append(str((include_path / relative_path).as_posix()))

        if prune and target_path.exists():
            for target_file in _iter_files(target_path):
                relative_path = target_file.relative_to(target_path)
                if relative_path not in source_files:
                    target_file.unlink()
                    deleted.append(str((include_path / relative_path).as_posix()))

    return {
        'copied_count': len(copied),
        'deleted_count': len(deleted),
        'copied': copied,
        'deleted': deleted,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Mirror selected BusinessOS paths into Dropbox.')
    parser.add_argument(
        'config_path',
        nargs='?',
        default=Path(__file__).resolve().parents[1] / 'configs' / 'dropbox-mirror.yaml',
    )
    args = parser.parse_args()
    result = run_dropbox_mirror(args.config_path)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
