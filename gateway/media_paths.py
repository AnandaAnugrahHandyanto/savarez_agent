"""Path helpers for gateway MEDIA file delivery."""

from __future__ import annotations

import json
import logging
import os
import posixpath
from typing import Iterable

logger = logging.getLogger(__name__)


MEDIA_EXPORT_CONTAINER_ROOTS = ("/output", "/outputs")


def parse_docker_volume_spec(spec: str) -> tuple[str, str] | None:
    """Parse a Docker ``-v`` bind mount as ``(host_path, container_path)``.

    Hermes stores ``terminal.docker_volumes`` in ``TERMINAL_DOCKER_VOLUMES`` as
    JSON strings like ``/host/exports:/output[:options]``. Docker's optional
    third field can be ``ro``, ``rw``, ``cached``, ``delegated``, propagation
    flags, SELinux flags, or comma-separated combinations. Named volumes and
    malformed entries are ignored because the host gateway cannot derive a
    readable filesystem path from them.
    """
    if not isinstance(spec, str):
        return None

    raw = spec.strip()
    if not raw:
        return None

    parts = raw.split(":")
    if len(parts) < 2:
        return None

    if parts[-1].strip().startswith("/"):
        # host:container with no options. Join earlier parts so unusual but
        # valid POSIX host paths containing ':' still round-trip.
        host_path = ":".join(parts[:-1])
        container_path = parts[-1]
    elif len(parts) >= 3 and parts[-2].strip().startswith("/"):
        # host:container:options. The options field is intentionally not
        # enumerated: Docker supports more than ro/rw, and unknown options do
        # not change the host/container path relationship.
        host_path = ":".join(parts[:-2])
        container_path = parts[-2]
    else:
        return None

    if not host_path or not container_path:
        return None

    host_path = os.path.expandvars(os.path.expanduser(host_path.strip()))
    container_path = posixpath.normpath(container_path.strip())

    if not os.path.isabs(host_path) or not container_path.startswith("/"):
        return None

    return os.path.normpath(host_path), container_path


def docker_bind_mounts_from_env(raw_volumes: str | None = None) -> tuple[tuple[str, str], ...]:
    """Return configured Docker bind mounts from ``TERMINAL_DOCKER_VOLUMES``.

    Invalid or missing environment values return an empty tuple so gateway
    response post-processing can continue with the original MEDIA path.
    """
    raw = os.getenv("TERMINAL_DOCKER_VOLUMES", "") if raw_volumes is None else raw_volumes
    raw = str(raw or "").strip()
    if not raw:
        return ()

    try:
        parsed = json.loads(raw)
    except Exception:
        logger.debug("Could not parse TERMINAL_DOCKER_VOLUMES", exc_info=True)
        return ()

    if not isinstance(parsed, list):
        return ()

    mounts = []
    for entry in parsed:
        mount = parse_docker_volume_spec(entry)
        if mount:
            mounts.append(mount)
    return tuple(mounts)


def _container_path_is_within(path: str, root: str) -> bool:
    if root == "/":
        return path.startswith("/")
    return path == root or path.startswith(f"{root}/")


def is_media_export_mount(
    container_root: str,
    *,
    allowed_roots: Iterable[str] = MEDIA_EXPORT_CONTAINER_ROOTS,
) -> bool:
    """Return whether a container mount root is intended for MEDIA exports."""
    container_root = posixpath.normpath(container_root)
    if container_root == "/":
        return False

    for root in allowed_roots:
        root = posixpath.normpath(str(root))
        if root.startswith("/") and _container_path_is_within(container_root, root):
            return True
    return False


def docker_media_bind_mounts_from_env(raw_volumes: str | None = None) -> tuple[tuple[str, str], ...]:
    """Return Docker bind mounts eligible for outbound MEDIA path mapping."""
    return tuple(
        (host_root, container_root)
        for host_root, container_root in docker_bind_mounts_from_env(raw_volumes)
        if is_media_export_mount(container_root)
    )


def _translate_docker_path_to_host(
    path: str,
    mounts: Iterable[tuple[str, str]],
) -> str | None:
    container_path = posixpath.normpath(path)
    if not container_path.startswith("/"):
        return None

    best_mount = None
    for host_root, container_root in mounts:
        if not _container_path_is_within(container_path, container_root):
            continue
        if best_mount is None or len(container_root) > len(best_mount[1]):
            best_mount = (host_root, container_root)

    if best_mount is None:
        return None

    host_root, container_root = best_mount
    rel_path = posixpath.relpath(container_path, container_root)
    if rel_path == ".":
        return host_root
    return os.path.normpath(os.path.join(host_root, *rel_path.split("/")))


def resolve_outbound_media_path(path: str) -> str:
    """Return a host-readable path for an extracted ``MEDIA:`` directive.

    The gateway delivers files from the host process, but terminal tools can run
    in a Docker sandbox.  When Docker is the active backend and the MEDIA path is
    inside a configured Docker bind mount, this maps the container path to the
    corresponding host path.  The automatic mapping is intentionally limited to
    explicit MEDIA export mounts under ``/output`` or ``/outputs``; other Docker
    bind mounts continue to behave like unmapped paths.  Host-visible paths
    outside those mapped export roots, non-Docker backends, malformed volume
    config, and unmapped paths fall back to the expanded original path without
    raising.
    """
    try:
        expanded = os.path.expanduser(path)

        if os.getenv("TERMINAL_ENV", "local").strip().lower() == "docker":
            translated = _translate_docker_path_to_host(
                expanded,
                docker_media_bind_mounts_from_env(),
            )
            if translated:
                return translated

        try:
            if os.path.exists(expanded):
                return expanded
        except OSError:
            pass

        return expanded
    except Exception:
        logger.debug("Could not resolve outbound MEDIA path", exc_info=True)
        try:
            return os.path.expanduser(path)
        except Exception:
            return path
