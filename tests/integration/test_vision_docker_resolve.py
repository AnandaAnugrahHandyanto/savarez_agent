"""Docker integration tests for the vision image-source resolver.

Reproduces #32709: vision_analyze must read images that live only inside the
Docker terminal backend — including a tmpfs ``/workspace`` file with no host
path, and a root-owned mode-600 file the host user cannot read. Both are
served by the in-container ``base64`` exec-read fallback.

Gating follows the repo convention: the ``integration`` marker excludes these
from the default suite (``addopts = -m 'not integration'``); they run under
``pytest -m integration`` when a Docker daemon is available, and skip cleanly
when it is not. Container spin-up exceeds the 30s suite default, so the timeout
is bumped to 180s (mirrors tests/docker/conftest.py).

Run:  pytest -m integration tests/integration/test_vision_docker_resolve.py
"""
import base64
import shutil
import subprocess

import pytest


def _docker_available() -> bool:
    """True iff a docker CLI is on PATH and the daemon answers."""
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        ).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(180),
    pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available"),
]

# A real 1x1 PNG.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def docker_backend(request):
    from tools import terminal_tool
    from tools.environments import docker as docker_env

    # Unique per test: DockerEnvironment derives the container from task_id, so
    # a shared id would make one test's teardown remove the other's container.
    task_id = f"vision-docker-resolve-{request.node.name}"
    env = docker_env.DockerEnvironment(
        image="python:3.11-slim",
        cwd="/workspace",
        timeout=120,
        cpu=0,
        memory=0,
        disk=0,
        persistent_filesystem=True,
        task_id=task_id,
        volumes=[],
        network=False,
    )
    terminal_tool._active_environments[task_id] = env
    try:
        env.task_id = task_id
        yield env
    finally:
        terminal_tool._active_environments.pop(task_id, None)
        env.cleanup(force_remove=True)


def _write_png_in_container(env, path, *, mode=None):
    b64 = base64.b64encode(_TINY_PNG).decode()
    cmd = f"printf %s {b64} | base64 -d > {path}"
    if mode:
        cmd += f" && chmod {mode} {path}"
    res = env.execute(cmd)
    assert res.get("returncode", 1) == 0, res


@pytest.mark.asyncio
async def test_resolves_tmpfs_workspace_file(docker_backend):
    from tools.image_source import ResolveContext, resolve_image_source

    _write_png_in_container(docker_backend, "/workspace/shot.png")
    res = await resolve_image_source(
        "/workspace/shot.png", ResolveContext(task_id=docker_backend.task_id))
    assert res.origin == "container"
    assert res.mime == "image/png"
    assert res.data == _TINY_PNG


@pytest.mark.asyncio
async def test_resolves_root_owned_mode600_file(docker_backend):
    from tools.image_source import ResolveContext, resolve_image_source

    # Root-owned, mode 600 — unreadable from the host user, readable in-container.
    _write_png_in_container(docker_backend, "/workspace/secret.png", mode="600")
    res = await resolve_image_source(
        "/workspace/secret.png", ResolveContext(task_id=docker_backend.task_id))
    assert res.origin == "container"
    assert res.mime == "image/png"
