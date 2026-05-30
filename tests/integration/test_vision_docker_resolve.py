"""Gated Docker integration tests for the vision image-source resolver.

Reproduces #32709: vision_analyze must read images that live only inside the
Docker terminal backend — including a tmpfs ``/workspace`` file with no host
path, and a root-owned mode-600 file the host user cannot read. Both are
served by the in-container ``base64`` exec-read fallback.

Run locally with Docker:  HERMES_DOCKER_TESTS=1 pytest tests/integration/test_vision_docker_resolve.py
In CI without the flag:    SKIPPED.
"""
import base64
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("HERMES_DOCKER_TESTS"),
    reason="set HERMES_DOCKER_TESTS=1 to run Docker integration tests",
)

# A real 1x1 PNG.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def docker_backend():
    from tools import terminal_tool
    from tools.environments import docker as docker_env

    task_id = "vision-docker-resolve-test"
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
