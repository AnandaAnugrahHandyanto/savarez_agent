# Rule: plugins

Paths: `plugins/`.

DO NOT:
- Read-only zone: all current `plugins/<name>/` directories are upstream-vendored; never modify.
- Authoring zone: new operator-authored plugins go in `plugins/legal-tech-<name>/`.

Architecture Notes: expand generic plugin hooks instead of hardcoding plugin-specific behavior into core.

Thresholds: plugin contract changes require upstream coordination.

Key Files: `hermes_cli/plugins.py`, `plugins/`, `agent/memory_manager.py`.
