import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "railway-start.sh"


def _write_fake_hermes(bin_dir: Path) -> Path:
    hermes_path = bin_dir / "hermes"
    hermes_path.write_text(
        "#!/bin/sh\n"
        "printf 'ARGS=%s\\n' \"$*\"\n"
        "printf 'API_SERVER_ENABLED=%s\\n' \"$API_SERVER_ENABLED\"\n"
        "printf 'API_SERVER_HOST=%s\\n' \"$API_SERVER_HOST\"\n"
        "printf 'API_SERVER_PORT=%s\\n' \"$API_SERVER_PORT\"\n"
        "printf 'HERMES_HOME=%s\\n' \"$HERMES_HOME\"\n",
        encoding="utf-8",
    )
    hermes_path.chmod(0o755)
    return hermes_path


def _run_start_script(tmp_path: Path, env_overrides: dict[str, str | None]) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_hermes(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"

    for key, value in env_overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value

    return subprocess.run(
        ["/bin/bash", str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )


def test_railway_start_requires_port(tmp_path: Path) -> None:
    result = _run_start_script(
        tmp_path,
        {
            "PORT": None,
            "API_SERVER_KEY": "test-key",
        },
    )

    assert result.returncode != 0
    assert "PORT" in result.stderr


def test_railway_start_requires_api_server_key(tmp_path: Path) -> None:
    result = _run_start_script(
        tmp_path,
        {
            "PORT": "8642",
            "API_SERVER_KEY": None,
        },
    )

    assert result.returncode != 0
    assert "API_SERVER_KEY" in result.stderr


def test_railway_start_exports_required_gateway_env(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes-home"
    result = _run_start_script(
        tmp_path,
        {
            "PORT": "19444",
            "API_SERVER_KEY": "test-key",
            "HERMES_HOME": str(hermes_home),
        },
    )

    assert result.returncode == 0
    assert "ARGS=gateway run --replace" in result.stdout
    assert "API_SERVER_ENABLED=true" in result.stdout
    assert "API_SERVER_HOST=0.0.0.0" in result.stdout
    assert "API_SERVER_PORT=19444" in result.stdout
    assert f"HERMES_HOME={hermes_home}" in result.stdout
