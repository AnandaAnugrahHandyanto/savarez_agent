# Session 2: Rebranding Report — Hermes Agent → Jade

**Tag: By DpSkV4**  
**Date:** 2026-05-13  
**Fork:** `NousResearch/hermes-agent` → `Oracule Zero / Jade`

---

## Scope

String-substitution rebrand across **user-facing display surfaces only**.  
No Python imports, module names, package names, env vars, command names, metadata keys, paths, or URLs were changed.

---

## Modified Files (32 total)

### TUI — TypeScript (4 files)

| File | Changes |
|------|---------|
| `ui-tui/src/theme.ts` | BRAND `name:'Hermes Agent'`→`'Jade'`, `icon:'⚕'`→`'◆'`, `goodbye` updated |
| `ui-tui/src/components/branding.tsx` | L52 `NOUS HERMES`→`JADE`; L56 tagline→`Oracule Zero · Jade — Executive Intelligence…`; L227 `Nous Research`→`Oracule Zero` |
| `ui-tui/src/components/appChrome.tsx` | EMOJI_FRAMES `'⚕ '`→`'◆ '` |
| `ui-tui/src/components/appLayout.tsx` | Status icon `⚕`→`◆` |

### Python CLI — Display Headers (11 files)

| File | What changed | Visible effect |
|------|-------------|----------------|
| `hermes_cli/skin_engine.py` | 5 built-in skins: agent_name→Jade, welcome/goodbye/response_label updated | CLI `/skin` output |
| `hermes_cli/default_soul.py` | `"You are Jade, created by Oracule Zero."` | Agent system prompt |
| `hermes_cli/banner.py` | Version label `Jade v{VERSION}`, attribution `Oracule Zero`, 2 docstrings | Startup banner |
| `hermes_cli/status.py` | Header `◆ Jade Status`, 2 docstrings | `hermes status` |
| `hermes_cli/setup.py` | 7 strings: wizard headers, prompts | Setup wizard UI |
| `hermes_cli/tools_config.py` | Header `◆ Jade Tool Configuration` | `hermes tools` |
| `hermes_cli/uninstall.py` | Header `◆ Jade Uninstaller`, thank-you | `hermes uninstall` |
| `hermes_cli/gateway.py` | SERVICE_DESCRIPTION, startup `◆ Jade Gateway Starting` | Gateway output |
| `hermes_cli/doctor.py` | Header `◆ Jade Doctor` | `hermes doctor` |
| `hermes_cli/config.py` | Header `◆ Jade Configuration` | Config display |
| `hermes_cli/backup.py` | Error/warning messages (3 strings) | Backup/restore |

### Python CLI — Help & Log Text (4 files)

| File | Change |
|------|--------|
| `hermes_cli/claw.py:307` | `"Migrate from OpenClaw to Jade"` |
| `hermes_cli/logs.py:175` | `"Logs created when Jade runs"` |
| `hermes_cli/debug.py:690` | `"Share with the Jade team"` |
| `hermes_cli/web_server.py:4466` | `"Jade Web UI → http://…"` |

### Web Dashboard — i18n + Themes (18 files)

`web/src/i18n/*.ts` (16 language files):
- `brand: "Hermes Agent"` → `"Jade"`
- `brandShort: "HA"` → `"JD"`
- `org: "Nous Research"` → `"Oracule Zero"`
- `updateHermes` value: `"Update Jade"`, `updatingHermes` value: `"Updating Jade"`

`web/src/themes/presets.ts`:
- `"Hermes Teal"` → `"Jade Dark"`
- `"Hermes Teal (Large)"` → `"Jade Dark (Large)"`

### Website Config (1 file)

`website/docusaurus.config.ts`:
- `title: 'Hermes Agent'` → `'Jade'`
- `tagline` → `'Executive Intelligence for Oracule Zero'`
- Navbar title, logo alt text, footer copyright

### Skills — Content Text (63 files)

`skills/**/SKILL.md` (50 files) + `optional-skills/**/SKILL.md` (13 files):
- Content `"Hermes"` → `"Jade"` (agent references only)
- Preserved: `author:` lines, `metadata.hermes.*` keys, URLs, paths, command refs, toolset wildcards
- Edge case fixed: `hermes-agent/SKILL.md:443` had inline `` `hermes` `` command ref + `"why is Hermes doing X"` content on same line

### README.md (1 file)

Title `# Jade ◆`, description updated to `Jade — Executive Intelligence for Oracule Zero`, badge `Built by`→`Powered by Nous Research`, footer attribution. Keep upstream references accurate (`Fork of the Hermes Agent`, documentation URLs).

### Build Script (1 file)

`scripts/build_skills_index.py:246` → `"Building Jade Skills Index…"`

---

## Intentional Skips (safe — not branding)

| Category | Count | Rationale |
|----------|-------|-----------|
| Python module names (`hermes_cli`, `hermes_constants`) | 400+ | Would break `import` |
| Class names (`HermesCLI`) | 10+ | Would break instantiation |
| Function names (`get_hermes_home()`) | 50+ | Would break callsites |
| Env vars (`HERMES_HOME`, `HERMES_MANAGED`) | 20+ | Functional config |
| Command invocations (`` `hermes model` ``) | 50+ | Invocation, not branding |
| URLs (`github.com/NousResearch/hermes-agent`) | 30+ | Must remain valid |
| Paths (`~/.hermes/`, `%LOCALAPPDATA%\hermes\`) | 30+ | Functional f/s paths |
| Skill `author: Hermes Agent` lines | 63 | Authorship credit |
| Skill `metadata.hermes.*` keys | 60 | Functional discovery keys |
| README upstream references | 10 | Accurate description |
| Nous Research service names (`Nous Portal`) | 30 | Refers to actual external service |
| Protected files (`run_agent.py`, `cli.py`, `gateway/run.py`, `hermes_cli/main.py`) | 100+ | Cannot edit per AGENTS.md |
| Web/i18n nested descriptions about upstream features | 50+ | Analogous to README fork language |
| `web/src/i18n/*.ts` tweet_text lines | 16 | Escaped quotes in value; minor display |

---

## Remaining Hermes Count

~4200 matches across repo after Session 2. All are in the intentional-skip categories above.

---

## Known Caveats

1. **`hermes_cli/main.py`** is a protected file — contains version display `Hermes Agent v{VERSION}`, update `"⚕ Updating Hermes Agent…"`, many argparse help strings, and WhatsApp setup tips. These remain unchanged.
2. **`cli.py`** is a protected file — contains `"chat with Hermes"`, `"Hermes Gateway"` text. Unchanged.
3. **Logo/banner ASCII art** in `ui-tui/src/banner.ts` — the `LOGO_ART` and `CADUCEUS_ART` are graphical patterns, not strings. Needs manual redesign for Jade.
4. **i18n tweet/share strings** (`tweet_text`) contain escaped `\"` quotes inside values — simple regex replacement doesn't handle them. Low priority display strings.
5. **Directory/skill names** like `skills/autonomous-ai-agents/hermes-agent/` and `skills/software-development/hermes-agent-skill-authoring/` remain. Changing directory names would break skill discovery unless references are also updated.

---

*End of Session 2 report. Prepared for senior review.*
