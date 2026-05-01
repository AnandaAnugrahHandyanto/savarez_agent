# Achievements Upgrades — Build Spec

> Implementation plan for PR #18151. Ordered by dependency: each commit is independently testable.

## Commit 1: Filtering & Sorting (backend)

### What
Add `filter_and_sort_achievements()` pure function + query params on `/achievements` endpoint.

### Files

**`plugins/hermes-achievements/dashboard/plugin_api.py`**

1. Add `filter_and_sort_achievements()` after `display_achievement()` (~line 549). Signature:
   ```python
   def filter_and_sort_achievements(
       items: List[Dict[str, Any]],
       state: Optional[str] = None,
       category: Optional[str] = None,
       sort_by: Optional[str] = None,
       order: Optional[str] = None,
       limit: Optional[int] = None,
   ) -> List[Dict[str, Any]]:
   ```
   Logic: filter by state, filter by category, sort (evidence_depth / unlocked_at / tier / progress / name), apply limit. Evidence depth = `progress` for tiered, `progress_pct` for multi-condition. Default sort desc for evidence/unlocked_at, asc for everything else.

2. Replace the `/achievements` handler (line ~991) to accept query params:
   ```python
   @router.get("/achievements")
   async def achievements(
       state: Optional[str] = None,
       category: Optional[str] = None,
       sort_by: Optional[str] = None,
       order: Optional[str] = None,
       limit: Optional[int] = None,
   ):
       data = evaluate_all()
       items = filter_and_sort_achievements(
           data.get("achievements", []),
           state=state, category=category,
           sort_by=sort_by, order=order, limit=limit,
       )
       payload = {k: data[k] for k in ["achievements", "unlocked_count", "discovered_count", "secret_count", "total_count", "error", "generated_at"] if k in data}
       payload["achievements"] = items
       payload["filtered_count"] = len(items)
       payload["is_stale"] = _is_snapshot_stale(data)
       payload["scan_meta"] = {**(data.get("scan_meta") or {}), "status": _scan_status_payload()}
       return payload
   ```

   **Important**: Do NOT use FastAPI `Query()` validation. The `APIRouter` stub at lines 16-23 (used when FastAPI is not installed) doesn't support `Query()`. Just accept plain optional params — FastAPI will parse query strings automatically, and the stub just passes them through.

3. Add `TIER_ORDER` dict at module level (near `TIER_NAMES`, line ~45):
   ```python
   TIER_ORDER = {"Olympian": 5, "Diamond": 4, "Gold": 3, "Silver": 2, "Copper": 1}
   ```
   This is reused by the CLI handler (commit 3).

**`plugins/hermes-achievements/tests/test_achievement_engine.py`**

4. Add 5 new test methods to `AchievementEngineTests`:
   - `test_filter_by_state_returns_only_matching` — filter unlocked vs discovered
   - `test_sort_by_evidence_orders_by_progress_depth` — desc order check
   - `test_sort_by_tier_orders_highest_first` — tier ranking check
   - `test_limit_caps_results` — simple limit check
   - `test_filter_by_category` — category match check

   All tests call `filter_and_sort_achievements()` directly on `compute_all()` output. No HTTP needed.

### Verify
```bash
cd ~/.hermes/hermes-agent
python3 -m unittest plugins/hermes-achievements/tests/test_achievement_engine.py -v
# Expect 15/15 pass (10 existing + 5 new)
```

Then spin up the dashboard and verify the API:
```bash
# Start dashboard, then:
curl -s 'http://localhost:9119/api/plugins/hermes-achievements/achievements?state=unlocked&sort_by=evidence&limit=5' | python3 -m json.tool | head -30
curl -s 'http://localhost:9119/api/plugins/hermes-achievements/achievements?category=Debugging%20Chaos' | python3 -m json.tool | head -20
```

---

## Commit 2: Export Formatters & Agent Summary

### What
Add `export_json()`, `export_markdown()`, `export_svg()`, `_build_agent_summary()` to `plugin_api.py`. Add `/export` and `/achievements/summary` endpoints. Write `agent_summary.json` on rescan.

### Files

**`plugins/hermes-achievements/dashboard/plugin_api.py`**

1. Add `from datetime import datetime` to imports (top of file).

2. Add `export_json()` after `filter_and_sort_achievements()`:
   ```python
   def export_json(data: Dict[str, Any], state: Optional[str] = None) -> str:
       items = filter_and_sort_achievements(data.get("achievements", []), state=state)
       export = {
           "generated_at": data.get("generated_at"),
           "unlocked_count": data.get("unlocked_count", 0),
           "total_count": data.get("total_count", 0),
           "achievements": items,
       }
       return json.dumps(export, indent=2, default=str)
   ```

3. Add `export_markdown()`:
   - Group by category
   - Per-category table with name, tier badge (shields.io URL), unicode progress bar
   - Tier color map: Copper=CD7F32, Silver=C0C0C0, Gold=FFD700, Diamond=B9F2FF, Olympian=FF00FF
   - Header line: `**X/Y unlocked** | Last scanned: YYYY-MM-DD`

4. Add `export_svg()`:
   - Dark-themed badge sheet, one row per unlocked achievement
   - Tier-colored dot + name + tier label
   - Dimensions: 280w × (rows × 36)h

5. Add `_build_agent_summary(data)`:
   - Returns dict with: total_sessions, total_tool_calls, unlocked_count, total_count, top_categories (categories with most unlocks), top_tier (highest tier across unlocked), strengths (= top_categories), gaps (categories with zero unlocks but highest discovery %), unlocked_ids
   - Reuses `TIER_ORDER` for tier ranking

6. Add two endpoints:
   ```python
   @router.get("/export")
   async def export_achievements(format: str = "json", state: Optional[str] = None):
       data = evaluate_all()
       if format == "markdown":
           return export_markdown(data, state=state)  # FastAPI auto-serializes str as JSON; wrap in dict
       elif format == "svg":
           return {"svg": export_svg(data, state=state)}
       return json.loads(export_json(data, state=state))

   @router.get("/achievements/summary")
   async def achievements_summary_for_agents():
       data = evaluate_all()
       return _build_agent_summary(data)
   ```

   **Gotcha**: FastAPI auto-wraps string returns as `{"content": "..."}`. For markdown, return `{"markdown": export_markdown(...)}` so the caller gets a parseable JSON. For SVG, return `{"svg": "..."}`. The CLI handler (commit 3) will unwrap these. If we want proper content-type negotiation later, we can add `PlainTextResponse` — but that requires importing from fastapi.responses, which breaks the no-FastAPI stub path. Keep it simple for now.

7. Write `agent_summary.json` on rescan. In `_run_scan_and_update_cache()`, after `_SNAPSHOT_CACHE = _json_safe(computed)` (~line 899):
   ```python
   try:
       summary = _build_agent_summary(computed)
       _summary_path = Path.home() / ".hermes" / "plugins" / "hermes-achievements" / "agent_summary.json"
       _summary_path.parent.mkdir(parents=True, exist_ok=True)
       _summary_path.write_text(json.dumps(summary, indent=2))
   except Exception:
       pass
   ```

**`plugins/hermes-achievements/tests/test_achievement_engine.py`**

8. Add 4 new tests:
   - `test_export_json_produces_valid_json` — parse and check keys
   - `test_export_markdown_produces_category_headers` — check `## ` in output
   - `test_export_svg_produces_valid_svg` — check `<svg` and `</svg>`
   - `test_agent_summary_has_strengths_and_gaps` — check structure

### Verify
```bash
python3 -m unittest plugins/hermes-achievements/tests/test_achievement_engine.py -v
# Expect 19/19 pass (15 + 4 new)

# Dashboard smoke test:
curl -s 'http://localhost:9119/api/plugins/hermes-achievements/export?format=markdown&state=unlocked' | head -20
curl -s 'http://localhost:9119/api/plugins/hermes-achievements/achievements/summary' | python3 -m json.tool

# Agent summary file written:
cat ~/.hermes/plugins/hermes-achievements/agent_summary.json | python3 -m json.tool
```

---

## Commit 3: CLI Subcommand & Slash Command

### What
Create `hermes_cli/achievements_cmd.py` and `hermes_cli/achievements_export.py`. Register `hermes achievements` subcommand and `/achievements` slash command.

### Files

**`hermes_cli/achievements_cmd.py`** (new file, ~200 lines)

1. Module purpose: handle both `hermes achievements` (CLI) and `/achievements` (slash command).

2. Import strategy for the engine: use `importlib.util` to load `plugin_api.py` from the bundled plugin path. Same pattern as the existing test file:
   ```python
   import importlib.util
   from pathlib import Path
   
   _PLUGIN_DIR = Path.home() / ".hermes" / "hermes-agent" / "plugins" / "hermes-achievements" / "dashboard"
   # Try bundled path first, fall back to user-installed path
   if not (_PLUGIN_DIR / "plugin_api.py").exists():
       _PLUGIN_DIR = Path.home() / ".hermes" / "plugins" / "hermes-achievements" / "dashboard"
   
   try:
       _spec = importlib.util.spec_from_file_location("achievements_api", _PLUGIN_DIR / "plugin_api.py")
       _api = importlib.util.module_from_spec(_spec)
       _spec.loader.exec_module(_api)
   except Exception:
       _api = None
   ```

3. Functions to implement:
   - `achievements_summary()` — Rich Panel with unlock stats + top 5 unlocked by tier
   - `achievements_list(state, category, sort_by, order, limit)` — Rich Table, calls `_api.filter_and_sort_achievements()`
   - `achievements_show(achievement_id)` — Rich Panel with full detail, evidence, tier ladder
   - `achievements_rescan()` — calls `_api.evaluate_all(force=True)`, prints result
   - `handle_achievements_command(args_str)` — entry point, parses subcommands: summary/list/show/rescan/export

4. Rich dependency: already in `pyproject.toml` requires. Fallback: if Rich import fails, print plain text.

5. Tier colors for Rich markup:
   ```python
   TIER_COLORS = {
       "Copper": "#B87333", "Silver": "#C0C0C0", "Gold": "#FFD700",
       "Diamond": "#B9F2FF", "Olympian": "#FF00FF",
   }
   ```

6. Progress bar helper:
   ```python
   def _tier_bar(tier, pct, width=10):
       filled = int(width * pct / 100)
       return "█" * filled + "░" * (width - filled) + f" {pct}%"
   ```

**`hermes_cli/achievements_export.py`** (new file, ~60 lines)

7. `handle_export(args)` — parses `--format json|markdown|svg`, `--output PATH`, `--state X`, calls the engine's export functions, writes to file or stdout.

**`hermes_cli/commands.py`**

8. Add to `COMMAND_REGISTRY` (after the `plugins` entry, ~line 168):
   ```python
   CommandDef("achievements", "Show achievement progress, list badges, or rescan history",
              "Info", aliases=("ach", "badges"),
              subcommands=("list", "show", "rescan", "export", "summary")),
   ```

**`cli.py`**

9. Add dispatch in `process_command()` (~line 6472, after the `plugins` block):
   ```python
   elif canonical == "achievements":
       from hermes_cli.achievements_cmd import handle_achievements_command
       rest = cmd_original.split(maxsplit=1)
       args_str = rest[1] if len(rest) > 1 else ""
       with self._busy_command("Scanning achievements…"):
           handle_achievements_command(args_str)
   ```

   The `_busy_command` context manager shows a spinner while the first scan loads. Subsequent calls hit the snapshot cache and are instant.

**`hermes_cli/main.py`**

10. Add `hermes achievements` subcommand. After the `curator_parser` block (~line 9215):
    ```python
    # =========================================================================
    # achievements command — badge progress and export
    # =========================================================================
    achievements_parser = subparsers.add_parser(
        "achievements",
        help="Achievement progress, badge list, and export",
        description="Query, filter, and export Hermes achievements from the terminal.",
    )
    achievements_subs = achievements_parser.add_subparsers(dest="achievements_command")

    achievements_subs.add_parser("summary", help="Compact summary of unlocked badges")
    
    achievements_list_p = achievements_subs.add_parser("list", help="List achievements in a table")
    achievements_list_p.add_argument("--state", choices=["unlocked", "discovered", "secret", "all"], default=None)
    achievements_list_p.add_argument("--category", default=None)
    achievements_list_p.add_argument("--sort-by", dest="sort_by", default=None,
                                     choices=["name", "tier", "progress", "evidence", "unlocked_at"])
    achievements_list_p.add_argument("--order", choices=["asc", "desc"], default=None)
    achievements_list_p.add_argument("--limit", type=int, default=None)

    achievements_show_p = achievements_subs.add_parser("show", help="Full detail for one achievement")
    achievements_show_p.add_argument("id", help="Achievement ID (e.g. let_him_cook)")
    
    achievements_subs.add_parser("rescan", help="Force a rescan of session history")
    
    achievements_export_p = achievements_subs.add_parser("export", help="Export achievements")
    achievements_export_p.add_argument("--format", "-f", dest="fmt", default="json",
                                       choices=["json", "markdown", "svg"])
    achievements_export_p.add_argument("--output", "-o", default=None, help="Write to file instead of stdout")
    achievements_export_p.add_argument("--state", default=None,
                                       choices=["unlocked", "discovered", "secret", "all"])

    def cmd_achievements(args):
        from hermes_cli.achievements_cmd import handle_achievements_command
        # Reconstruct the args string from the parsed namespace
        parts = []
        sub = getattr(args, "achievements_command", None) or "summary"
        parts.append(sub)
        if sub == "list":
            if args.state: parts.extend(["--state", args.state])
            if args.category: parts.extend(["--category", args.category])
            if args.sort_by: parts.extend(["--sort-by", args.sort_by])
            if args.order: parts.extend(["--order", args.order])
            if args.limit: parts.extend(["--limit", str(args.limit)])
        elif sub == "show":
            parts.append(args.id)
        elif sub == "export":
            parts.extend(["--format", args.fmt])
            if args.output: parts.extend(["--output", args.output])
            if args.state: parts.extend(["--state", args.state])
        handle_achievements_command(" ".join(parts))

    achievements_parser.set_defaults(func=cmd_achievements)
    ```

### Verify
```bash
# Slash command in interactive hermes:
# /achievements
# /achievements list --state unlocked --sort-by evidence --limit 5
# /achievements show let_him_cook

# CLI subcommand:
hermes achievements summary
hermes achievements list --state unlocked --sort-by evidence --limit 5
hermes achievements show let_him_cook
hermes achievements rescan

# Export:
hermes achievements export --format markdown --state unlocked
hermes achievements export --format svg --output /tmp/badges.svg
hermes achievements export --format json
```

---

## Commit 4: Dashboard Frontend Filter Bar

### What
Add filter/sort controls to the achievements dashboard tab.

### Files

**`plugins/hermes-achievements/dashboard/dist/index.js`**

1. This is a bundled JS file (~2500+ lines min). The current `AchievementsPage` component fetches `/api/plugins/hermes-achievements/achievements` with no params and renders the full achievement grid.

2. Patch approach: add state variables and a filter bar component. The fetch call already goes through an `api()` helper — we just need to append query params to the URL.

3. Add state to the `AchievementsPage` component:
   ```javascript
   const [filterState, setFilterState] = React.useState("all");
   const [sortBy, setSortBy] = React.useState("name");
   ```

4. Modify the fetch call to include params:
   ```javascript
   const params = new URLSearchParams();
   if (filterState !== "all") params.set("state", filterState);
   if (sortBy !== "name") params.set("sort_by", sortBy);
   const url = "/achievements" + (params.toString() ? "?" + params.toString() : "");
   const data = await api(url);
   ```

5. Add a filter bar component above the achievement grid. Uses SDK components (`C.Select`, `C.Button`):
   ```javascript
   function FilterBar({ filterState, setFilterState, sortBy, setSortBy }) {
     return React.createElement(C.Card, { className: "ha-filter-bar" },
       React.createElement(C.CardContent, { className: "ha-filter-bar-content" },
         React.createElement(C.Select, {
           value: filterState,
           onValueChange: setFilterState,
           options: [
             { value: "all", label: "All States" },
             { value: "unlocked", label: "Unlocked" },
             { value: "discovered", label: "Discovered" },
             { value: "secret", label: "Secret" },
           ],
         }),
         React.createElement(C.Select, {
           value: sortBy,
           onValueChange: setSortBy,
           options: [
             { value: "name", label: "Name" },
             { value: "evidence", label: "Evidence" },
             { value: "tier", label: "Tier" },
             { value: "progress", label: "Progress" },
             { value: "unlocked_at", label: "Recently Unlocked" },
           ],
         }),
       ),
     );
   }
   ```

6. Render `FilterBar` above the stats cards in `AchievementsPage`.

**Note**: If the `dist/index.js` is built from a source directory (TSX/JSX), we should patch the source and rebuild instead of editing the bundle directly. Check with @PCinkusz on whether a source directory exists upstream. If not, the minified bundle is the source of truth and we patch it directly.

### Verify
- Open dashboard in browser, navigate to Achievements tab
- Verify filter bar renders with All/Unlocked/Discovered/Secret dropdown
- Verify Sort dropdown works
- Verify the achievement list updates when filters change
- Verify URL params are sent correctly (check browser dev tools Network tab)

---

## Commit 5: Curator Dry-Run

### What
Add `--dry-run` flag to `hermes curator` subcommands. Add `DryRunRecorder` class. Add plugin `dry_run_preview()` hook.

### Files

**`hermes_cli/curator.py`**

1. Add `--dry-run` argument to each mutating subcommand in `register_cli()`:
   ```python
   # For p_run:
   p_run.add_argument("--dry-run", action="store_true",
                      help="Preview changes without applying them")
   # Same for p_pin, p_unpin, p_restore
   ```

2. Add `DryRunRecorder` class (can be in the same file since curator is small):
   ```python
   class DryRunRecorder:
       """Records planned mutations without executing them."""
       def __init__(self):
           self.file_ops = []
           self.config_ops = []
           self.state_ops = []
           self.warnings = []
       
       def record_file_write(self, path, size, exists=False):
           self.file_ops.append({"op": "write", "path": str(path), "size": size, "exists": exists})
       
       def record_file_delete(self, path, exists=False):
           self.file_ops.append({"op": "delete", "path": str(path), "exists": exists})
       
       def record_config_change(self, key, old, new):
           self.config_ops.append({"op": "set", "key": key, "old": old, "new": new})
       
       def record_config_remove(self, key, old):
           self.config_ops.append({"op": "remove", "key": key, "old": old})
       
       def record_state_transition(self, plugin, old_state, new_state):
           self.state_ops.append({"op": new_state, "plugin": plugin, "from": old_state})
       
       def add_warning(self, msg):
           self.warnings.append(msg)
       
       def has_breaking_changes(self):
           return (any(op["op"] == "delete" and op.get("exists") for op in self.file_ops)
                   or any(op["op"] == "remove" for op in self.config_ops)
                   or any(op["op"] == "remove" for op in self.state_ops))
       
       def format_report(self):
           lines = []
           if self.file_ops:
               lines.append("File changes:")
               for op in self.file_ops:
                   marker = "overwrite" if op.get("exists") else "create"
                   if op["op"] == "delete":
                       lines.append(f"  [delete] {op['path']}")
                   else:
                       lines.append(f"  [{marker}] {op['path']} ({op['size']} bytes)")
           if self.config_ops:
               lines.append("Config changes:")
               for op in self.config_ops:
                   if op["op"] == "set":
                       lines.append(f"  {op['key']}: {op['old']} -> {op['new']}")
                   else:
                       lines.append(f"  {op['key']}: {op['old']} -> (removed)")
           if self.state_ops:
               lines.append("Plugin state:")
               for op in self.state_ops:
                   lines.append(f"  {op['plugin']}: {op['from']} -> {op['op']}")
           if self.warnings:
               lines.append("Warnings:")
               for w in self.warnings:
                   lines.append(f"  WARNING: {w}")
           return "\n".join(lines)
   ```

3. Modify `_cmd_run` to check `args.dry_run`:
   ```python
   def _cmd_run(args) -> int:
       if getattr(args, "dry_run", False):
           print("curator dry-run: previewing skill review pass")
           recorder = DryRunRecorder()
           # The curator run would: scan skills, write reports, update state
           # For dry-run, we just record what it would do
           from agent import curator
           state = curator.load_state()
           recorder.record_state_transition("curator", "idle", "running")
           # Count agent-created skills that would be reviewed
           from tools import skill_usage
           rows = skill_usage.agent_created_report()
           for row in rows:
               skill_name = row.get("name", "unknown")
               skill_state = row.get("state", "active")
               if skill_state == "stale":
                   recorder.add_warning(f"Skill '{skill_name}' would be archived (stale)")
               elif skill_state == "active":
                   recorder.add_warning(f"Skill '{skill_name}' would be reviewed (active)")
           print(recorder.format_report())
           return 1 if recorder.has_breaking_changes() else 0
       
       # Existing run logic...
   ```

4. Add plugin dry_run_preview hook lookup:
   ```python
   def _check_plugin_dry_run_preview(plugin_name, recorder):
       """Call a plugin's dry_run_preview hook if it exists."""
       try:
           import importlib.util
           from pathlib import Path
           # Check bundled and user-installed paths
           for base in [
               Path.home() / ".hermes" / "hermes-agent" / "plugins",
               Path.home() / ".hermes" / "plugins",
           ]:
               api_path = base / plugin_name / "dashboard" / "plugin_api.py"
               if api_path.exists():
                   spec = importlib.util.spec_from_file_location(f"{plugin_name}_api", api_path)
                   mod = importlib.util.module_from_spec(spec)
                   spec.loader.exec_module(mod)
                   if hasattr(mod, "dry_run_preview"):
                       state_path = base / plugin_name / "state.json"
                       current_state = {}
                       if state_path.exists():
                           import json
                           current_state = json.loads(state_path.read_text())
                       preview = mod.dry_run_preview(
                           proposed_version="unknown",
                           current_state=current_state,
                       )
                       for warning in preview.get("warnings", []):
                           recorder.add_warning(warning)
                   break
       except Exception:
           pass  # Optional hook — failure is non-fatal
   ```

**`plugins/hermes-achievements/dashboard/plugin_api.py`**

5. Add `dry_run_preview()` function (after `_build_agent_summary`):
   ```python
   def dry_run_preview(proposed_version: str, current_state: dict) -> dict:
       """Preview what a version update would do to achievement state.
       Called by hermes curator --dry-run.
       """
       current_ids = {a["id"] for a in ACHIEVEMENTS}
       current_unlocks = current_state.get("unlocks", {})
       orphaned = [uid for uid in current_unlocks if uid not in current_ids]
       warnings = []
       if orphaned:
           warnings.append(f"{len(orphaned)} unlock(s) reference IDs no longer in catalog: {orphaned[:5]}")
       return {
           "current_achievement_count": len(ACHIEVEMENTS),
           "current_unlock_count": len(current_unlocks),
           "orphaned_unlock_ids": orphaned,
           "warnings": warnings,
       }
   ```

**`plugins/hermes-achievements/tests/test_achievement_engine.py`**

6. Add test:
   ```python
   def test_dry_run_preview_detects_orphaned_unlocks(self):
       state = {"unlocks": {"fake_id": {"unlocked_at": 1}, "let_him_cook": {"unlocked_at": 2}}}
       result = plugin_api.dry_run_preview("0.4.0", state)
       self.assertIn("fake_id", result["orphaned_unlock_ids"])
       self.assertNotIn("let_him_cook", result["orphaned_unlock_ids"])
       self.assertTrue(len(result["warnings"]) > 0)
   ```

### Verify
```bash
# Curator dry-run:
hermes curator run --dry-run

# Achievements-specific hook:
# (indirectly tested via the unit test above)

# Full test suite:
python3 -m unittest plugins/hermes-achievements/tests/test_achievement_engine.py -v
# Expect 20/20 pass (19 + 1 new)
```

---

## Commit 6: Manifest Version Bump & Final Integration Test

### What
Bump plugin version. Add integration test that exercises the full pipeline. Update the PR doc.

### Files

**`plugins/hermes-achievements/dashboard/manifest.json`**

1. Bump `"version": "0.3.1"` to `"version": "0.4.0"`

**`plugins/hermes-achievements/tests/test_achievement_engine.py`**

2. Add integration test:
   ```python
   def test_full_pipeline_filter_export_summary(self):
       """Integration: filter -> export -> summary all work on the same data."""
       data = plugin_api.compute_all()
       
       # Filter
       unlocked = plugin_api.filter_and_sort_achievements(
           data["achievements"], state="unlocked", sort_by="evidence", order="desc"
       )
       
       # Export each format
       json_str = plugin_api.export_json(data, state="unlocked")
       md_str = plugin_api.export_markdown(data, state="unlocked")
       svg_str = plugin_api.export_svg(data, state="unlocked")
       
       # Summary
       summary = plugin_api._build_agent_summary(data)
       
       # Basic shape checks
       self.assertIsInstance(json.loads(json_str), dict)
       self.assertIn("## ", md_str)
       self.assertIn("<svg", svg_str)
       self.assertIn("strengths", summary)
       self.assertIn("gaps", summary)
   ```

3. Update `test_catalog_has_60_plus_unique_achievements` if the count changed (unlikely — we didn't add new achievements, just new features).

**`plugins/hermes-achievements/docs/PR-achievements-upgrades.md`**

4. Update the PR doc to reflect what was actually built (vs what was spec'd). Add a "Shipped" section at the top.

### Verify
```bash
# Full test suite
python3 -m unittest plugins/hermes-achievements/tests/test_achievement_engine.py -v
# Expect 21/21 pass

# End-to-end CLI smoke test
hermes achievements summary
hermes achievements list --state unlocked --sort-by evidence --limit 3
hermes achievements show let_him_cook
hermes achievements export --format markdown --state unlocked | head -15
hermes achievements export --format svg --output /tmp/hermes-badges.svg && file /tmp/hermes-badges.svg
hermes curator run --dry-run

# Dashboard check (if running)
curl -s 'http://localhost:9119/api/plugins/hermes-achievements/achievements?state=unlocked&sort_by=evidence&limit=3' | python3 -m json.tool
curl -s 'http://localhost:9119/api/plugins/hermes-achievements/export?format=markdown' | head -10
curl -s 'http://localhost:9119/api/plugins/hermes-achievements/achievements/summary' | python3 -m json.tool
```

---

## Build Order Summary

| Commit | Scope | Files | Depends on |
|--------|-------|-------|------------|
| 1 | Backend filtering | `plugin_api.py`, `test_achievement_engine.py` | Nothing |
| 2 | Export + summary | `plugin_api.py`, `test_achievement_engine.py` | Commit 1 (uses `filter_and_sort_achievements`) |
| 3 | CLI + slash command | `achievements_cmd.py` (new), `achievements_export.py` (new), `commands.py`, `cli.py`, `main.py` | Commits 1+2 (calls engine functions) |
| 4 | Dashboard filter bar | `dist/index.js` | Commit 1 (needs API params) |
| 5 | Curator dry-run | `curator.py`, `plugin_api.py`, `test_achievement_engine.py` | Independent (can parallel with 3-4) |
| 6 | Version bump + integration | `manifest.json`, `test_achievement_engine.py`, PR doc | Commits 1-5 |

Each commit should pass the full test suite independently. Each commit should be independently reviewable.

## Risks & Gotchas

1. **`dist/index.js` is a bundled file**: If there's an upstream source directory, we need to patch source + rebuild, not patch the bundle directly. Check with @PCinkusz. If no source exists, patch the bundle but note it in the commit message.

2. **FastAPI `Query()` validation breaks the stub**: The `APIRouter` fallback at lines 16-23 of `plugin_api.py` is used when FastAPI isn't installed (unit tests, standalone imports). Don't use `Query()` — just accept plain optional params in the handler signature.

3. **`plugin_api.py` is 1053 lines**: After all changes it'll be ~1300. Not bad but worth watching. If it crosses 1500, consider extracting export formatters into a separate `exporters.py` — but not yet.

4. **The `hermes achievements` subcommand needs the plugin to be bundled**: The import path points to `~/.hermes/hermes-agent/plugins/hermes-achievements/dashboard/plugin_api.py`. If the plugin isn't installed there (e.g. user-installed at `~/.hermes/plugins/`), the fallback path handles it. But the CLI command won't work if the plugin is completely absent. The `_api = None` fallback prints a helpful error message.

5. **Curator dry-run for `run` is partially simulated**: A true dry-run of the curator's LLM review pass would require actually running the LLM calls but intercepting writes. That's complex. The initial implementation just previews the file/config/state mutations without running the LLM. This is good enough for v1 — the real value is in the plugin-level `dry_run_preview()` hooks.

6. **`agent_summary.json` is written on rescan only**: If the user has never opened the dashboard or run a rescan, the file doesn't exist. The `context_files` entry in `config.yaml` is optional and will silently skip missing files. No breakage.
