from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

try:
    from aiohttp import web
except ImportError:  # pragma: no cover - exercised through api_server requirements tests
    web = None  # type: ignore[assignment]


@dataclass(frozen=True)
class WebSurfaceRuntime:
    surface_id: str
    plugin_name: str
    mount_path: str
    bootstrap_path: str
    extra_file_paths: dict[str, str]


@dataclass(frozen=True)
class WebSurfaceSpec:
    surface_id: str
    plugin_name: str
    static_dir: Path
    spa_fallback: bool = True
    extra_files: dict[str, Path] = field(default_factory=dict)
    bootstrap_factory: Callable[[WebSurfaceRuntime], Mapping[str, Any]] | None = None

    def runtime(self) -> WebSurfaceRuntime:
        mount_path = f"/web/{self.surface_id}/"
        return WebSurfaceRuntime(
            surface_id=self.surface_id,
            plugin_name=self.plugin_name,
            mount_path=mount_path,
            bootstrap_path=f"{mount_path}__hermes__.json",
            extra_file_paths={
                route_name: f"{mount_path}{route_name}" for route_name in sorted(self.extra_files)
            },
        )


def mount_web_surface(app: "web.Application", spec: WebSurfaceSpec) -> None:
    if web is None:  # pragma: no cover - guarded by api_server requirements
        raise RuntimeError("aiohttp is required for plugin web surfaces")

    runtime = spec.runtime()
    prefix = runtime.mount_path.rstrip("/")

    async def redirect_root(_request: "web.Request") -> "web.StreamResponse":
        raise web.HTTPTemporaryRedirect(runtime.mount_path)

    async def handle_bootstrap(_request: "web.Request") -> "web.StreamResponse":
        if spec.bootstrap_factory is None:
            raise web.HTTPNotFound()
        payload = spec.bootstrap_factory(runtime)
        return web.json_response(dict(payload))

    async def handle_static(request: "web.Request") -> "web.StreamResponse":
        relative_path = request.match_info.get("tail", "")
        resolved = _resolve_relative_path(spec.static_dir, relative_path or "index.html")
        if resolved is not None and resolved.is_file():
            return web.FileResponse(resolved)

        if spec.spa_fallback and _should_use_spa_fallback(relative_path):
            index_path = spec.static_dir / "index.html"
            if index_path.is_file():
                return web.FileResponse(index_path)

        raise web.HTTPNotFound()

    app.router.add_get(prefix, redirect_root)
    if spec.bootstrap_factory is not None:
        app.router.add_get(runtime.bootstrap_path, handle_bootstrap)
    for route_name, file_path in spec.extra_files.items():
        app.router.add_get(f"{prefix}/{route_name}", _make_file_handler(file_path))
    app.router.add_get(f"{prefix}/{{tail:.*}}", handle_static)


def _make_file_handler(path: Path):
    async def handle_file(_request: "web.Request") -> "web.StreamResponse":
        if not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    return handle_file


def _resolve_relative_path(static_dir: Path, relative_path: str) -> Path | None:
    candidate = (static_dir / relative_path).resolve()
    try:
        candidate.relative_to(static_dir.resolve())
    except ValueError:
        return None
    return candidate


def _should_use_spa_fallback(relative_path: str) -> bool:
    if not relative_path:
        return True
    normalized = PurePosixPath(relative_path)
    return normalized.suffix == ""
