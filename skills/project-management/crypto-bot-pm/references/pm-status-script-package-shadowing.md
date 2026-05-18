# PM Status `scripts` Package Shadowing Repair

Use this when `crypto-bot-pm` PM status reports provider import isolation even though the plugin files exist, especially errors like:

- `ModuleNotFoundError: No module named 'scripts.hermes_pm'`
- `provider_import_failed` for `scripts.hermes_pm.gitea_readonly_snapshot`, `issue_lifecycle_status`, or `work_state`
- PM status recommending "Repair PM status provider import isolation" while direct plugin paths are present

## Durable cause

A third-party/site-packages module named `scripts` can be imported before the plugin-local `plugins/crypto-bot-pm/scripts/` directory is bound as the `scripts` package. If that happens, later imports of `scripts.hermes_pm.*` resolve under the unrelated package and fail, even when the plugin's local modules exist.

## Repair pattern

1. Add a plugin-local package anchor:
   - `plugins/crypto-bot-pm/scripts/__init__.py`
   - Keep it small; its purpose is only to ensure the local `scripts` package wins.
2. In `plugins/crypto-bot-pm/scripts/hermes_pm/project_status.py`, after inserting the plugin root into `sys.path`, clear any already-loaded unrelated `scripts` module before provider imports:

```python
_local_scripts_dir = repo_root_for_import / "scripts"
_loaded_scripts = sys.modules.get("scripts")
_loaded_scripts_paths = [Path(p).resolve() for p in getattr(_loaded_scripts, "__path__", [])]
if _loaded_scripts is not None and _local_scripts_dir.resolve() not in _loaded_scripts_paths:
    sys.modules.pop("scripts", None)
```

3. Sync runtime and source copies when active-runtime parity is required:
   - source: `/Users/preston/.hermes/hermes-agent/plugins/crypto-bot-pm/...`
   - installed runtime: `/Users/preston/.hermes/plugins/crypto-bot-pm/...`
4. Validate without exposing secrets:
   - `python3 -m py_compile plugins/crypto-bot-pm/scripts/__init__.py plugins/crypto-bot-pm/scripts/hermes_pm/project_status.py plugins/crypto-bot-pm/scripts/hermes_pm/hermes_pm_status.py`
   - `python3 plugins/crypto-bot-pm/scripts/hermes_pm/hermes_pm_status.py --project-id crypto_bot --repo-root /Users/preston/robinhood/crypto_bot --live-gitea-read --format json`
   - Assert `provider_import_status.gitea_snapshot.available`, `issue_lifecycle.available`, and `work_state.available` are true.
   - Run `python3 tools/crypto_bot_control_plane_self_check.py --format json` and confirm `native_control_plane_ready: true` with no blockers.

## Reporting nuance

Optional 404s from Gitea endpoints such as `/actions/runs` or `/projects` can remain snapshot limitations. Do not classify them as the same provider-import regression if the local providers import and live read-only PM status otherwise works.
