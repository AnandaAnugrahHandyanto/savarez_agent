# Changelog Format Reference

## Overview

Changelog is generated from commits since last tag.
Entries are grouped by commit type.

---

## Format

```markdown
## [VERSION] - YYYY-MM-DD

### Features
- description (#issue)

### Fixes
- description (#issue)

### Documentation
- description (#issue)

### Maintenance
- description (#issue)

### Breaking Changes
- description (#issue)
```

---

## Commit Grouping Rules

| Commit Pattern | Changelog Section |
|----------------|-------------------|
| `feat:` | Features |
| `feature:` | Features |
| `fix:` | Fixes |
| `bugfix:` | Fixes |
| `patch:` | Fixes |
| `docs:` | Documentation |
| `doc:` | Documentation |
| `chore:` | Maintenance |
| `maintenance:` | Maintenance |
| `refactor:` | Maintenance |
| `BREAKING CHANGE:` | Breaking Changes |
| `major:` | Breaking Changes |

---

## Generation Algorithm

### Input

- Commits since last tag
- Release version
- Release date

### Processing

```bash
# 1. Get commits
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)
COMMITS=$(git log --oneline $LATEST_TAG..HEAD 2>/dev/null || git log --oneline)

# 2. Group by type
FEATURES=$(echo "$COMMITS" | grep -i "feat:\|feature:" || true)
FIXES=$(echo "$COMMITS" | grep -i "fix:\|bugfix:\|patch:" || true)
DOCS=$(echo "$COMMITS" | grep -i "docs:\|doc:" || true)
MAINTENANCE=$(echo "$COMMITS" | grep -i "chore:\|maintenance:\|refactor:" || true)
BREAKING=$(echo "$COMMITS" | grep -i "BREAKING CHANGE\|major:" || true)

# 3. Format entries
format_entries() {
    local entries="$1"
    if [ -n "$entries" ]; then
        echo "$entries" | sed 's/^/- /'
    else
        echo "- (none)"
    fi
}
```

### Output

```markdown
## [1.2.0] - 2026-06-20

### Features
- feat: add new skill (#123)
- feature: improve version logic (#124)

### Fixes
- fix: resolve false positives (#125)

### Documentation
- docs: update README (#126)

### Maintenance
- chore: sync with upstream (#127)

### Breaking Changes
- (none)
```

---

## Entry Formatting

### Standard Entry

```
- <type>: <description> (#<issue>)
```

### Examples

```markdown
- feat: add release manager skill (#123)
- fix: resolve version calculation bug (#124)
- docs: update contributing guide (#125)
- chore: sync with upstream v0.17.0 (#126)
- BREAKING CHANGE: remove deprecated API (#127)
```

### Without Issue Number

```markdown
- feat: add release manager skill
- fix: resolve version calculation bug
```

---

## Empty Sections

If a section has no entries, use `(none)`:

```markdown
### Breaking Changes
- (none)
```

Or omit the section entirely:

```markdown
## [1.2.0] - 2026-06-20

### Features
- feat: add new skill

### Fixes
- fix: resolve bug
```

---

## Date Format

Use ISO 8601 format:

```
YYYY-MM-DD
```

Example: `2026-06-20`

---

## Version Placeholder

Use `NEXT_VERSION` as placeholder until version is confirmed:

```markdown
## [NEXT_VERSION] - YYYY-MM-DD
```

Replace with actual version during release.

---

## File Location

Changelog can be stored in:

1. `CHANGELOG.md` (root)
2. `RELEASES.md`
3. GitHub Release Notes
4. Tag annotation

### Recommendation

For maintained forks:
- Use GitHub Release Notes for official releases
- Use `CHANGELOG.md` for local reference
- Use tag annotation for lightweight releases

---

## Integration with Release Workflow

### Pre-Release

```bash
# Generate draft changelog
./scripts/generate-changelog.sh > CHANGELOG_DRAFT.md
```

### During Release

```bash
# Include in release notes
gh release create v1.2.0 --notes-file CHANGELOG_DRAFT.md
```

### Post-Release

```bash
# Archive to CHANGELOG.md
cat CHANGELOG_DRAFT.md >> CHANGELOG.md
```

---

## Conventional Commits Integration

If repository uses [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Changelog Section |
|------|-------------------|
| `feat` | Features |
| `fix` | Fixes |
| `docs` | Documentation |
| `chore` | Maintenance |
| `refactor` | Maintenance |
| `perf` | Fixes (performance) |
| `test` | Maintenance |
| `ci` | Maintenance |
| `build` | Maintenance |
| `revert` | Fixes |

### Breaking Change Indicator

```markdown
feat!: remove deprecated API

BREAKING CHANGE: removed deprecated API endpoint
```

---

## Custom Categories

Repository can define custom categories:

```yaml
# .changelog-config.yml
categories:
  - pattern: "feat:"
    section: "Features"
  - pattern: "fix:"
    section: "Bug Fixes"
  - pattern: "security:"
    section: "Security"
  - pattern: "perf:"
    section: "Performance"
```

---

## Examples

### Example 1: Standard Release

```markdown
## [1.2.0] - 2026-06-20

### Features
- feat: add release manager skill
- feat: support multiple tag strategies

### Fixes
- fix: resolve version calculation bug
- fix: handle no tags case

### Documentation
- docs: update README with new commands

### Maintenance
- chore: sync with upstream

### Breaking Changes
- (none)
```

### Example 2: Breaking Release

```markdown
## [2.0.0] - 2026-06-20

### Features
- feat: add new API endpoint

### Fixes
- fix: resolve memory leak

### Documentation
- docs: update API reference

### Maintenance
- chore: cleanup deprecated code

### Breaking Changes
- BREAKING CHANGE: remove deprecated /old-api endpoint
- BREAKING CHANGE: change response format for /users
```

### Example 3: Patch Release

```markdown
## [1.2.1] - 2026-06-20

### Features
- (none)

### Fixes
- fix: resolve critical security vulnerability
- fix: handle edge case in parser

### Documentation
- (none)

### Maintenance
- (none)

### Breaking Changes
- (none)
```
