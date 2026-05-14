# Hermes ↔ Notion Kanban Sync

Production-safe sync for the SoLoVision Notion Task Board and Hermes Kanban.

## Dry run

```bash
python -m hermes_cli.notion_kanban_sync --dry-run
```

The dry run writes a timestamped JSON report with:
- current Notion status distribution
- proposed legacy → canonical status migrations
- proposed Hermes task creations
- proposed two-way updates

## Safe sample/backfill

```bash
python -m hermes_cli.notion_kanban_sync --apply --limit 3
```

For batched permanent backfill without flooding workers:

```bash
python -m hermes_cli.notion_kanban_sync --apply --quiet --max-creates 25
```

For targeted verification or repair, constrain a run to one or more linked Hermes task ids:

```bash
python -m hermes_cli.notion_kanban_sync --apply --hermes-task-id t_abc12345 --max-creates 0
```

For a schema-safe lifecycle cleanup without mutating Hermes tasks, use the migration-only path:

```bash
python -m hermes_cli.notion_kanban_sync --dry-run --status-migration-only --prune-status-options --max-creates 0
python -m hermes_cli.notion_kanban_sync --apply --status-migration-only --prune-status-options --max-creates 0
```

`--status-migration-only` rewrites only Notion `Status` select values to canonical Hermes lifecycle values. `--prune-status-options` removes unused legacy select options after pages are migrated so the Task Board presents only `Triage`, `Todo`, `Ready`, `Running`, `Blocked`, `Done`, and `Archived`.

No hard deletes are performed. Legacy Notion statuses are not mass-rewritten unless `--status-migration` or `--status-migration-only` is explicitly passed after reviewing a dry-run report. Every apply run writes a timestamped `backup-*.json` export containing the affected Notion page ids, old `Status` values, legacy `Hermes Status` values, and schema snapshot before writes. Hermes `archived` maps to an explicit Notion `Status=Archived` select option; the retired `Hermes Status` rich_text field is renamed to `Legacy Hermes Status` when possible, or `Retired Hermes Status` if a legacy archive field already exists, and is no longer written by normal sync.

## Permanent timer

Install the operational script and systemd timer:

```bash
mkdir -p ~/.hermes/profiles/dev/scripts ~/.config/systemd/user
install -m 700 scripts/notion_kanban_sync_watchdog.sh ~/.hermes/profiles/dev/scripts/notion_kanban_sync_watchdog.sh
cp plugins/kanban/systemd/hermes-notion-kanban-sync.service ~/.config/systemd/user/
cp plugins/kanban/systemd/hermes-notion-kanban-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now hermes-notion-kanban-sync.timer
systemctl --user list-timers hermes-notion-kanban-sync.timer --no-pager
```

The watchdog runs `python -m hermes_cli.notion_kanban_sync` from `~/.hermes/hermes-agent` when the module is available there, with a fallback to `~/.hermes/profiles/dev/scripts/notion_kanban_sync.py` for pre-merge installs. Override `HERMES_NOTION_SYNC_REPO`, `HERMES_NOTION_SYNC_SCRIPT`, `HERMES_NOTION_SYNC_PYTHON`, `HERMES_NOTION_SYNC_REPORT_DIR`, or `HERMES_NOTION_SYNC_MAX_CREATES` in the systemd service environment if needed. If `HERMES_NOTION_SYNC_REPORT_DIR` is unset, the module writes to the profile-safe default `~/.hermes/reports/hermes-notion-sync/`.

The watchdog is quiet when no changes occur; non-empty stdout means a sync changed something or hit an error.
