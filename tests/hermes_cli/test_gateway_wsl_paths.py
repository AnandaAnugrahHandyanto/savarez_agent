from hermes_cli import gateway


def test_build_wsl_interop_paths_dedupes_trailing_slash(monkeypatch):
    monkeypatch.setattr(gateway, "is_wsl", lambda: True)
    monkeypatch.setattr(gateway.shutil, "which", lambda _name: None)
    windows_root = "/mnt/" + "c/WINDOWS/System32"
    powershell_dir = windows_root + "/WindowsPowerShell/v1.0"
    monkeypatch.setenv(
        "PATH",
        f"/usr/bin:{powershell_dir}/:{windows_root}",
    )

    result = gateway._build_wsl_interop_paths([
        powershell_dir,
    ])

    assert powershell_dir + "/" not in result
    assert windows_root in result
