# Version Logic Reference

## Overview

Version recommendations are derived from repository state:
- Latest reachable tag
- Commits since tag
- Commit categories

No hardcoded versions.

---

## Semantic Versioning (SemVer)

### Format

```
MAJOR.MINOR.PATCH
```

### Rules

| Change Type | Bump | Example |
|-------------|------|---------|
| Breaking changes | MAJOR | 1.0.0 → 2.0.0 |
| New features | MINOR | 1.0.0 → 1.1.0 |
| Bug fixes | PATCH | 1.0.0 → 1.0.1 |

### Breaking Changes

- Incompatible API changes
- Removed public functions
- Changed function signatures
- Modified behavior

### Features

- New functionality
- New parameters (optional)
- New return values
- New skills

### Fixes

- Bug corrections
- Performance improvements
- Security patches
- Documentation corrections

---

## Commit Message Conventions

### Format

```
<type>(<scope>): <description>
```

### Types

| Type | Version Impact | Category |
|------|----------------|----------|
| `feat` | Minor | Features |
| `feature` | Minor | Features |
| `fix` | Patch | Fixes |
| `bugfix` | Patch | Fixes |
| `patch` | Patch | Fixes |
| `docs` | None | Documentation |
| `doc` | None | Documentation |
| `chore` | None | Maintenance |
| `maintenance` | None | Maintenance |
| `refactor` | None | Maintenance |
| `BREAKING CHANGE` | Major | Breaking |

### Detection Patterns

```bash
# Major bump
grep -i "BREAKING CHANGE\|major:"

# Minor bump
grep -i "feat:\|feature:"

# Patch bump
grep -i "fix:\|bugfix:\|patch:"

# No version impact
grep -i "docs:\|doc:\|chore:\|maintenance:\|refactor:"
```

---

## Fork-Specific Rules

### Upstream Sync

When merging upstream changes:

| Change Type | Recommended Bump |
|-------------|------------------|
| New upstream release | Match upstream version |
| Upstream bug fix | Patch |
| Upstream feature | Minor |
| Upstream breaking | Major |

### Branding Changes

| Change Type | Recommended Bump |
|-------------|------------------|
| Text updates | None |
| New skill | Minor |
| Skill API change | Major |
| Installer update | Patch |

### Documentation Only

| Change Type | Recommended Bump |
|-------------|------------------|
| README update | None |
| New documentation | None |
| Typo fixes | None |

---

## Version Calculation Algorithm

### Input

- Current version: `MAJOR.MINOR.PATCH`
- Commits since tag: list of commit messages

### Processing

```bash
# 1. Count commit types
MAJOR_COUNT=$(echo "$COMMITS" | grep -c -i "BREAKING CHANGE\|major:")
MINOR_COUNT=$(echo "$COMMITS" | grep -c -i "feat:\|feature:")
PATCH_COUNT=$(echo "$COMMITS" | grep -c -i "fix:\|bugfix:")

# 2. Determine bump
if [ "$MAJOR_COUNT" -gt 0 ]; then
    BUMP="major"
elif [ "$MINOR_COUNT" -gt 0 ]; then
    BUMP="minor"
elif [ "$PATCH_COUNT" -gt 0 ]; then
    BUMP="patch"
else
    BUMP="none"
fi

# 3. Calculate next version
case $BUMP in
    major) NEXT="$((MAJOR + 1)).0.0";;
    minor) NEXT="$MAJOR.$((MINOR + 1)).0";;
    patch) NEXT="$MAJOR.$MINOR.$((PATCH + 1))";;
    none) NEXT="$MAJOR.$MINOR.$PATCH";;
esac
```

### Output

- Next version: `A.B.C`
- Bump type: major/minor/patch/none
- Rationale: commit analysis

---

## Edge Cases

### No Tags Found

```bash
if [ -z "$LATEST_TAG" ]; then
    # First release
    echo "First release: v1.0.0"
    BUMP="initial"
fi
```

### No Relevant Commits

```bash
if [ "$MAJOR_COUNT" -eq 0 ] && [ "$MINOR_COUNT" -eq 0 ] && [ "$PATCH_COUNT" -eq 0 ]; then
    # No version-worthy changes
    echo "No release needed"
    BUMP="none"
fi
```

### Multiple Bump Types

```bash
# Major wins over minor, minor wins over patch
if [ "$MAJOR_COUNT" -gt 0 ]; then
    BUMP="major"  # Even if minor/patch exist
elif [ "$MINOR_COUNT" -gt 0 ]; then
    BUMP="minor"  # Even if patch exists
fi
```

---

## Examples

### Example 1: Feature Release

```bash
# Commits since tag:
# feat: add new skill
# feat: improve version logic
# fix: resolve false positives

# Analysis:
MAJOR_COUNT=0
MINOR_COUNT=2
PATCH_COUNT=1

# Result:
BUMP="minor"
NEXT="1.1.0"  # from 1.0.0
```

### Example 2: Breaking Release

```bash
# Commits since tag:
# feat: add new skill
# BREAKING CHANGE: remove deprecated API

# Analysis:
MAJOR_COUNT=1
MINOR_COUNT=1
PATCH_COUNT=0

# Result:
BUMP="major"
NEXT="2.0.0"  # from 1.1.0
```

### Example 3: Patch Release

```bash
# Commits since tag:
# fix: resolve memory leak
# docs: update README

# Analysis:
MAJOR_COUNT=0
MINOR_COUNT=0
PATCH_COUNT=1

# Result:
BUMP="patch"
NEXT="1.1.1"  # from 1.1.0
```

---

## Integration with Tag Strategy

### Upstream SemVer

```
Tag: v{NEXT_VERSION}
Example: v1.2.0
```

### Fork SemVer

```
Tag: savarez/v{NEXT_VERSION}
Example: savarez/v1.2.0
```

### Phase Tags

```
Tag: savarez/phase-{N}
Increment: N = N + 1
Example: savarez/phase-5
```

### Experimental

```
Tag: savarez/nightly-{DATE}
Format: YYYYMMDD
Example: savarez/nightly-20260620
```
