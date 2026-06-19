# Rebranding Rules — Savarez Agent

This document defines what can and cannot be rebranded when maintaining the Savarez Agent fork of Hermes Agent.

## Priority Order

```
Stabilitas Runtime > Kompatibilitas Upstream > Kemudahan Merge > Branding
```

If there is a conflict between branding and stability: **choose stability**.
If there is a conflict between branding and upstream compatibility: **choose upstream compatibility**.

---

## 🔵 SAFE TO REBRAND

These changes only affect user-facing display text and do not impact runtime, imports, or upstream compatibility.

| Area | Example | Risk | Merge Impact |
|------|---------|------|--------------|
| README.md | Display title, description | Very Low | Minimal |
| CONTRIBUTING.md | Contributor docs | Very Low | Minimal |
| Documentation text | User guides, tutorials | Very Low | Minimal |
| Dashboard UI text | Title, labels, buttons | Very Low | Minimal |
| Browser title | `<title>` tags | Very Low | Minimal |
| CLI help banner | `hermes --help` output text | Very Low | Minimal |
| About page text | App info display | Very Low | Minimal |
| Splash screen text | Startup display | Very Low | Minimal |
| pyproject.toml `description` | Package description | Very Low | Minimal |
| pyproject.toml `authors` | Author metadata | Very Low | Minimal |
| pyproject.toml `maintainer` | Maintainer metadata | Very Low | Minimal |
| package.json `description` | Package description | Very Low | Minimal |
| package.json `author` | Author metadata | Very Low | Minimal |

### Rules:
- Only change display strings, not identifiers
- Do not change package `name` fields in this category
- Do not change import paths or module names

---

## 🟡 REVIEW REQUIRED

These changes require careful analysis and explicit approval before implementation.

| Area | Risk | Why | Merge Impact |
|------|------|-----|--------------|
| pyproject.toml `name` | Medium | PyPI package identity, affects `pip install` | HIGH - every merge will conflict |
| package.json `name` | Medium | npm package identity | HIGH - every merge will conflict |
| CLI entrypoint script name | Medium | Executable name in PATH | Medium |
| Environment variable names | HIGH | 2756+ references in codebase | HIGH - runtime breakage |
| Config directory (`~/.hermes`) | HIGH | Existing installations, data migration | HIGH - user impact |
| Docker image names | Medium | Container registry references | Medium |
| Install script URLs | Medium | User-facing install commands | Medium |

### Rules:
- NEVER change these without explicit user approval
- ALWAYS warn about upstream merge conflicts
- ALWAYS create backward compatibility layer if changing
- ALWAYS test runtime after changes
- Document every change with reasoning

---

## 🔴 DO NOT TOUCH

These are internal identifiers that must remain as-is for runtime stability and upstream compatibility.

### Python Internal Modules

| Item | Reason |
|------|--------|
| `hermes_cli/` directory | Internal module path, 5003+ imports reference it |
| `hermes_constants.py` | Core constants module, 387+ imports |
| `hermes_logging.py` | Core logging module |
| `hermes_state.py` | Database module |
| `hermes_time.py` | Time utilities |
| `hermes_bootstrap.py` | Bootstrap module |
| `hermesclaw` | Internal utilities |
| `from hermes_cli import ...` | Import paths |
| `from hermes_constants import ...` | Import paths |
| `from hermes_state import ...` | Import paths |

### Environment Variables (Internal)

| Item | Reason |
|------|--------|
| `HERMES_HOME` | 2756+ references, runtime critical |
| `HERMES_*` internal env vars | Used by Docker, scripts, runtime |

### Published Dependencies

| Item | Reason |
|------|--------|
| `@nous-research/ui` | Published npm package, cannot rename |
| `hermes-protocol` | Published package |
| `hermes-hub` | Published package |

### TypeScript Types

| Item | Reason |
|------|--------|
| `HermesGateway` | Type definition |
| `HermesConfigRecord` | Type definition |
| `HermesConfig` | Type definition |
| `@/hermes` imports | Module path |

### HTTP/API

| Item | Reason |
|------|--------|
| `X-Hermes-Session-Token` | HTTP API header contract |
| API response field names | Client compatibility |

### Gateway/Runtime

| Item | Reason |
|------|--------|
| Gateway internal identifiers | Runtime stability |
| Plugin loader identifiers | Plugin compatibility |
| Dynamic import paths | Runtime stability |
| Serialization keys | Data compatibility |

### Electron/Desktop

| Item | Reason |
|------|--------|
| `hermes` in appId | Platform config |
| Electron IPC channel names | Runtime communication |

### Docker

| Item | Reason |
|------|--------|
| `HERMES_HOME` in shell scripts | Docker runtime |
| Container internal paths | Runtime stability |

---

## Upstream Sync Rules

When syncing with upstream Hermes Agent:

1. **Before merge**: Run `git fetch upstream && git diff upstream/main --stat`
2. **Identify conflicts**: Which files have branding changes that will conflict
3. **Resolve strategy**: 
   - For SAFE TO REBRAND files: Apply branding after merge
   - For REVIEW REQUIRED files: Manual resolution required
   - For DO NOT TOUCH files: Accept upstream version
4. **Verify**: Run full verification checklist after merge

### Merge Checklist:
```
✅ No Python syntax errors
✅ All imports resolve correctly
✅ CLI commands work
✅ Dashboard builds
✅ Gateway starts
✅ Update mechanism works
✅ No runtime errors
```

---

## Versioning

When forking, maintain awareness of upstream version:

- Current upstream version: 0.17.0
- Fork should track upstream releases
- Document any divergence from upstream

---

## Emergency Rollback

If a rebranding change causes regression:

1. Revert the specific commit: `git revert <commit>`
2. Run verification checklist
3. Document what went wrong
4. Update this rules file if needed

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-06-19 | Initial rules created | Fork stabilization |
