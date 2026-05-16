from pathlib import Path
from unittest.mock import patch


def test_service_path_skips_nonexistent_node_modules(tmp_path):
    """Service PATH should not include node_modules/.bin if it doesn't exist."""
    from hermes_cli.gateway import _build_service_path_dirs
    with patch("hermes_cli.gateway.get_hermes_home", return_value=tmp_path / ".hermes"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    node_modules_bin = str(tmp_path / "node_modules" / ".bin")
    assert node_modules_bin not in dirs


def test_service_path_includes_node_modules_when_present(tmp_path):
    """Service PATH should include node_modules/.bin when it exists."""
    nm_bin = tmp_path / "node_modules" / ".bin"
    nm_bin.mkdir(parents=True)
    from hermes_cli.gateway import _build_service_path_dirs
    with patch("hermes_cli.gateway.get_hermes_home", return_value=tmp_path / ".hermes"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    assert str(nm_bin) in dirs


def test_service_path_includes_hermes_home_node_modules(tmp_path):
    """Service PATH should include ~/.hermes/node_modules/.bin when it exists."""
    hermes_nm = tmp_path / ".hermes" / "node_modules" / ".bin"
    hermes_nm.mkdir(parents=True)
    from hermes_cli.gateway import _build_service_path_dirs
    with patch("hermes_cli.gateway.get_hermes_home", return_value=tmp_path / ".hermes"):
        dirs = _build_service_path_dirs(project_root=tmp_path)
    assert str(hermes_nm) in dirs


def test_service_path_treats_permission_error_as_missing(tmp_path):
    """A ``PermissionError`` from ``is_dir()`` must not crash unit
    generation — treat the path as missing and continue.

    Reproduces the CI baseline (#26622 audit): on locked-down Ubuntu
    runners, ``stat('/root/.hermes/node/bin')`` returns ``EACCES`` from
    the sandboxed filesystem layer even when the path is otherwise
    reachable. Before the guard, ``generate_systemd_unit()`` and
    ``generate_launchd_plist()`` propagated the ``OSError`` and refused
    to produce any unit at all.
    """
    from hermes_cli.gateway import _build_service_path_dirs

    real_is_dir = Path.is_dir
    target = tmp_path / ".hermes" / "node" / "bin"

    def fake_is_dir(self):
        # Only the hermes_home node/bin probe trips EACCES; other paths
        # must keep their real behavior so the rest of the function is
        # exercised normally.
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_dir(self)

    with patch("hermes_cli.gateway.get_hermes_home", return_value=tmp_path / ".hermes"), \
         patch.object(Path, "is_dir", fake_is_dir):
        dirs = _build_service_path_dirs(project_root=tmp_path)

    assert str(target) not in dirs


def test_service_path_treats_oserror_as_missing(tmp_path):
    """Broken-symlink / unreachable network mount probes (``OSError``)
    must also be treated as "directory not present" rather than crashing.
    """
    from hermes_cli.gateway import _build_service_path_dirs

    real_is_dir = Path.is_dir
    target = tmp_path / ".hermes" / "node_modules" / ".bin"

    def fake_is_dir(self):
        if self == target:
            raise OSError(5, "Input/output error", str(self))
        return real_is_dir(self)

    with patch("hermes_cli.gateway.get_hermes_home", return_value=tmp_path / ".hermes"), \
         patch.object(Path, "is_dir", fake_is_dir):
        dirs = _build_service_path_dirs(project_root=tmp_path)

    assert str(target) not in dirs
