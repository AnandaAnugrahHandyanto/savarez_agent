---
name: savarez-release-manager
description: "Release readiness auditing, changelog assistance, version recommendations, and tag planning for maintained forks."
version: 1.0.0
author: Savarez Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [release, version, changelog, tag, planning, audit, fork]
    related_skills: [savarez-git-maintainer, github-repo-management]
---

# Savarez Release Manager

## Overview

Release management skill for maintained forks.
Provides auditing, versioning, changelog, and tag planning.

All version recommendations are derived from repository state:
- Latest reachable tag
- Commits since tag
- Commit categories

No hardcoded versions.

## When to Use

- Before creating a release
- When deciding version bump
- When drafting changelog
- When planning tags
- When verifying release success

**Don't use for:**

- Fork health audit (use savarez-git-maintainer)
- General git operations (use github-repo-management)
- Release creation (use github-repo-management)

---

## Fork Release Mode

### Supported Strategies

| Strategy | Tag Format | Example | Use Case |
|----------|------------|---------|----------|
| Upstream SemVer | `v{major}.{minor}.{patch}` | v0.18.0 | Tracking upstream releases |
| Fork SemVer | `savarez/v{major}.{minor}.{patch}` | savarez/v0.18.0 | Fork-specific releases |
| Phase Tags | `savarez/phase-{N}` | savarez/phase-4 | Development phases |
| Experimental | `savarez/nightly-{date}` | savarez/nightly-20260620 | Nightly builds |

### Strategy Detection

The skill auto-detects repository strategy from existing tags:

```bash
# Detect strategy from tags
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)

if [[ "$LATEST_TAG" =~ ^v[0-9] ]]; then
    STRATEGY="upstream-semver"
elif [[ "$LATEST_TAG" =~ ^savarez/v[0-9] ]]; then
    STRATEGY="fork-semver"
elif [[ "$LATEST_TAG" =~ ^savarez/phase-[0-9] ]]; then
    STRATEGY="phase-tags"
elif [[ "$LATEST_TAG" =~ ^savarez/nightly ]]; then
    STRATEGY="experimental"
else
    STRATEGY="fork-semver"  # default
fi
```

### Manual Override

User can specify strategy:

```
Release using strategy: fork-semver
```

---

## Capabilities

### Capability 1: Release Readiness Audit

**Purpose:** Comprehensive check before release.

**Checks:**

| Check | Weight | Description |
|-------|--------|-------------|
| Version consistency | 20% | pyproject.toml matches expected |
| Working tree | 20% | Clean working tree |
| Commits since tag | 15% | Non-zero commits exist |
| Tag reachability | 15% | Latest tag is ancestor of HEAD |
| Documentation | 15% | README, CONTRIBUTING, DEVELOPMENT exist |
| No conflicting tags | 15% | Proposed tag not in use |

**How to Run:**

```bash
# 1. Get current version
VERSION=$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
echo "Current version: $VERSION"

# 2. Check working tree
if [ -z "$(git status --porcelain)" ]; then
    echo "Working tree: Clean"
else
    echo "Working tree: Dirty"
fi

# 3. Count commits since tag
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)
if [ -n "$LATEST_TAG" ]; then
    COMMITS_SINCE=$(git rev-list --count $LATEST_TAG..HEAD)
    echo "Commits since $LATEST_TAG: $COMMITS_SINCE"
else
    echo "No tags found"
fi

# 4. Verify tag reachable
if [ -n "$LATEST_TAG" ]; then
    git merge-base --is-ancestor $LATEST_TAG HEAD 2>/dev/null && \
        echo "Tag reachable: Yes" || echo "Tag reachable: No"
fi

# 5. Check documentation
for f in README.md CONTRIBUTING.md DEVELOPMENT.md; do
    [ -f "$f" ] && echo "$f: Exists" || echo "$f: Missing"
done

# 6. Check proposed tag
PROPOSED_TAG="v$VERSION"
git rev-parse "$PROPOSED_TAG" >/dev/null 2>&1 && \
    echo "Tag $PROPOSED_TAG: Already exists" || \
    echo "Tag $PROPOSED_TAG: Available"
```

**Output:**

```
=== Release Readiness ===

Version: X.Y.Z
Working tree: Clean/Dirty
Commits since tag: N
Tag reachable: Yes/No
Documentation: Complete/Incomplete
Proposed tag: Available/Exists

Status: READY/NOT READY
```

---

### Capability 2: Version Recommendation

**Purpose:** Suggest next version based on changes.

**Rules:**

| Condition | Bump | Rationale |
|-----------|------|-----------|
| Any `BREAKING CHANGE:` or `major:` commit | Major | Incompatible changes |
| Any `feat:` or `feature:` commit | Minor | New functionality |
| Only `fix:`, `docs:`, `chore:` commits | Patch | Bug fixes, docs |
| No relevant commits | Current | No release needed |

**How to Run:**

```bash
# 1. Get latest tag
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)

# 2. Get commits since tag
if [ -n "$LATEST_TAG" ]; then
    COMMITS=$(git log --oneline $LATEST_TAG..HEAD)
else
    COMMITS=$(git log --oneline)
fi

# 3. Analyze commits
MAJOR=$(echo "$COMMITS" | grep -c -i "BREAKING CHANGE\|major:")
MINOR=$(echo "$COMMITS" | grep -c -i "feat:\|feature:")
PATCH=$(echo "$COMMITS" | grep -c -i "fix:\|bugfix:")

# 4. Determine bump
if [ "$MAJOR" -gt 0 ]; then
    BUMP="major"
elif [ "$MINOR" -gt 0 ]; then
    BUMP="minor"
elif [ "$PATCH" -gt 0 ]; then
    BUMP="patch"
else
    BUMP="none"
fi

# 5. Parse current version
VERSION=$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
MAJOR_V=$(echo $VERSION | cut -d. -f1)
MINOR_V=$(echo $VERSION | cut -d. -f2)
PATCH_V=$(echo $VERSION | cut -d. -f3)

# 6. Calculate next version
case $BUMP in
    major) NEXT="$((MAJOR_V + 1)).0.0";;
    minor) NEXT="$MAJOR_V.$((MINOR_V + 1)).0";;
    patch) NEXT="$MAJOR_V.$MINOR_V.$((PATCH_V + 1))";;
    none) NEXT="$VERSION";;
esac

echo "Current: $VERSION"
echo "Recommended: $NEXT ($BUMP)"
```

**Output:**

```
=== Version Recommendation ===

Current version: X.Y.Z
Commits analyzed: N
- Breaking changes: N
- Features: N
- Fixes: N

Recommended: A.B.C (minor)
Rationale: N feature commits since last tag
```

---

### Capability 3: Changelog Drafting

**Purpose:** Generate changelog from commits.

**Commit Categories:**

| Pattern | Category |
|---------|----------|
| `feat:`, `feature:` | Features |
| `fix:`, `bugfix:`, `patch:` | Fixes |
| `docs:`, `doc:` | Documentation |
| `chore:`, `maintenance:`, `refactor:` | Maintenance |
| `BREAKING CHANGE:`, `major:` | Breaking Changes |

**How to Run:**

```bash
# 1. Get commits since tag
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)
if [ -n "$LATEST_TAG" ]; then
    COMMITS=$(git log --oneline $LATEST_TAG..HEAD)
    DATE=$(date +%Y-%m-%d)
else
    COMMITS=$(git log --oneline)
    DATE=$(date +%Y-%m-%d)
fi

# 2. Group commits
FEATURES=$(echo "$COMMITS" | grep -i "feat:\|feature:" || true)
FIXES=$(echo "$COMMITS" | grep -i "fix:\|bugfix:" || true)
DOCS=$(echo "$COMMITS" | grep -i "docs:\|doc:" || true)
MAINTENANCE=$(echo "$COMMITS" | grep -i "chore:\|maintenance:\|refactor:" || true)
BREAKING=$(echo "$COMMITS" | grep -i "BREAKING CHANGE\|major:" || true)

# 3. Generate changelog
cat <<EOF
## [NEXT_VERSION] - $DATE

### Features
$(echo "$FEATURES" | sed 's/^/- /')

### Fixes
$(echo "$FIXES" | sed 's/^/- /')

### Documentation
$(echo "$DOCS" | sed 's/^/- /')

### Maintenance
$(echo "$MAINTENANCE" | sed 's/^/- /')

### Breaking Changes
$(echo "$BREAKING" | sed 's/^/- /')
EOF
```

**Output:**

```markdown
=== Changelog Draft ===

## [X.Y.Z] - YYYY-MM-DD

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

### Capability 4: Tag Recommendation

**Purpose:** Suggest next tag based on repository strategy.

**How to Run:**

```bash
# 1. Detect strategy
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)

if [[ "$LATEST_TAG" =~ ^v[0-9] ]]; then
    STRATEGY="upstream-semver"
    PREFIX=""
elif [[ "$LATEST_TAG" =~ ^savarez/v[0-9] ]]; then
    STRATEGY="fork-semver"
    PREFIX="savarez/"
elif [[ "$LATEST_TAG" =~ ^savarez/phase-[0-9] ]]; then
    STRATEGY="phase-tags"
elif [[ "$LATEST_TAG" =~ ^savarez/nightly ]]; then
    STRATEGY="experimental"
else
    STRATEGY="fork-semver"
    PREFIX="savarez/"
fi

# 2. Get version recommendation
# (from Capability 2)
NEXT_VERSION="X.Y.Z"

# 3. Build tag
case $STRATEGY in
    upstream-semver) TAG="v$NEXT_VERSION";;
    fork-semver) TAG="savarez/v$NEXT_VERSION";;
    phase-tags) 
        CURRENT_PHASE=$(echo "$LATEST_TAG" | grep -o '[0-9]*$')
        NEXT_PHASE=$((CURRENT_PHASE + 1))
        TAG="savarez/phase-$NEXT_PHASE";;
    experimental) 
        TAG="savarez/nightly-$(date +%Y%m%d)";;
esac

echo "Strategy: $STRATEGY"
echo "Recommended tag: $TAG"
```

**Output:**

```
=== Tag Recommendation ===

Detected strategy: fork-semver
Latest tag: savarez/v0.17.0
Recommended: savarez/v0.18.0

Reasoning:
- 3 feature commits → minor bump
- Strategy: fork-semver
- Confidence: HIGH
```

---

### Capability 5: Pre-Release Checklist

**Purpose:** Verify all pre-release conditions.

**Checks:**

| Check | Description |
|-------|-------------|
| Repository clean | No uncommitted changes |
| Tests passing | Basic syntax checks pass |
| Docs updated | Documentation files exist |
| Version bumped | pyproject.toml updated |
| Tag available | Proposed tag not in use |
| Changelog generated | CHANGELOG.md exists or draft ready |
| Breaking changes documented | If major bump, BREAKING CHANGES noted |

**How to Run:**

```bash
echo "=== Pre-Release Checklist ==="

# 1. Repository clean
if [ -z "$(git status --porcelain)" ]; then
    echo "[✓] Repository clean"
else
    echo "[✗] Repository dirty"
fi

# 2. Tests passing
python -m py_compile hermes_cli/main.py 2>/dev/null && \
    echo "[✓] Python syntax OK" || echo "[✗] Python syntax error"

# 3. Docs updated
[ -f "README.md" ] && echo "[✓] README.md exists" || echo "[✗] README.md missing"
[ -f "CONTRIBUTING.md" ] && echo "[✓] CONTRIBUTING.md exists" || echo "[✗] CONTRIBUTING.md missing"

# 4. Version bumped
VERSION=$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
echo "[✓] Version: $VERSION"

# 5. Tag available
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)
PROPOSED="v$VERSION"
git rev-parse "$PROPOSED" >/dev/null 2>&1 && \
    echo "[✗] Tag $PROPOSED exists" || echo "[✓] Tag $PROPOSED available"

# 6. Changelog
[ -f "CHANGELOG.md" ] && echo "[✓] CHANGELOG.md exists" || echo "[ ] CHANGELOG.md not found"

# 7. Breaking changes
MAJOR=$(git log --oneline $LATEST_TAG..HEAD 2>/dev/null | grep -c -i "BREAKING CHANGE" || echo "0")
[ "$MAJOR" -gt 0 ] && echo "[ ] Breaking changes need documentation" || echo "[✓] No breaking changes"
```

**Output:**

```
=== Pre-Release Checklist ===

[✓] Repository clean
[✓] Python syntax OK
[✓] README.md exists
[✓] CONTRIBUTING.md exists
[✓] Version: X.Y.Z
[✓] Tag vX.Y.Z available
[ ] CHANGELOG.md not found
[✓] No breaking changes

Status: 6/7 PASS
```

---

### Capability 6: Post-Release Verification

**Purpose:** Verify release was successful.

**Checks:**

| Check | Description |
|-------|-------------|
| Tag pushed | Tag exists on remote |
| Branch synced | Local matches remote |
| Release notes | Release notes generated |
| Version matches | Tag version matches pyproject.toml |

**How to Run:**

```bash
echo "=== Post-Release Verification ==="

TAG="vX.Y.Z"

# 1. Tag pushed
git ls-remote --tags origin | grep -q "$TAG" && \
    echo "[✓] Tag pushed: $TAG" || echo "[✗] Tag not pushed: $TAG"

# 2. Branch synced
BEHIND=$(git rev-list --count HEAD..origin/main)
[ "$BEHIND" -eq 0 ] && \
    echo "[✓] Branch synced" || echo "[✗] Branch behind by $BEHIND commits"

# 3. Release notes
git release view $TAG >/dev/null 2>&1 && \
    echo "[✓] Release notes generated" || echo "[ ] Release notes not found"

# 4. Version matches
TAG_VERSION=$(echo $TAG | sed 's/^v//')
PY_VERSION=$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)
[ "$TAG_VERSION" = "$PY_VERSION" ] && \
    echo "[✓] Version matches" || echo "[✗] Version mismatch"
```

**Output:**

```
=== Post-Release Verification ===

[✓] Tag pushed: vX.Y.Z
[✓] Branch synced
[ ] Release notes not found
[✓] Version matches

Status: 3/4 PASS
```

---

## Common Pitfalls

1. **Releasing with dirty working tree**
   - Solution: Commit or stash changes first

2. **Forgetting to fetch before tag check**
   - Solution: Always `git fetch --tags` first

3. **Wrong strategy detection**
   - Solution: Manually specify strategy if needed

4. **Missing changelog entries**
   - Solution: Use conventional commit messages

5. **Tag already exists**
   - Solution: Check tag availability before release

## Verification Checklist

After running any capability:

- [ ] Understand the output
- [ ] Verify recommendations make sense
- [ ] Check for conflicts
- [ ] Proceed with release if READY
- [ ] Post-release verification after release
