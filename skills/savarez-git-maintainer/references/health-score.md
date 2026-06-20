# Savarez Health Score — Detailed Criteria

## Overview

The Savarez Health Score provides a quantified measure of fork health.
Score ranges from 0-100, composed of four weighted components.

## Component 1: Runtime Stability (40 points)

### Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Python syntax | 10% | All .py files compile without error |
| Entry points | 10% | hermes, savarez, hermes-agent, hermes-acp working |
| Core imports | 10% | No ImportError in critical modules |
| Gateway startup | 10% | Gateway process starts without exception |

### Graded Scoring

| Score | Status | Indicators |
|-------|--------|------------|
| 40 | Perfect | All checks pass, zero warnings |
| 30 | Minor warnings | Deprecation warnings, non-critical issues |
| 20 | Degraded | One component has issues, core works |
| 10 | Serious issue | Major component broken (gateway, entrypoints) |
| 0 | Broken | Multiple critical failures, cannot run |

### How to Check

```bash
# Python syntax
find . -name "*.py" -not -path "./node_modules/*" -exec python -m py_compile {} \;

# Entry points
hermes --version
savarez --version

# Core imports
python -c "from hermes_cli.main import main; print('OK')"

# Gateway (start and check)
hermes gateway run &
sleep 2
# Check if process is running
```

---

## Component 2: Upstream Compatibility (30 points)

### Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Sync status | 10% | Commits behind/ahead upstream |
| Divergence | 10% | File differences with upstream |
| Conflict risk | 5% | Overlap of modified files |
| Update logic | 5% | Update mechanism intact |

### Graded Scoring

| Score | Status | Indicators |
|-------|--------|------------|
| 30 | Perfect | 0 commits behind, minimal divergence |
| 20 | Minor drift | 1-5 commits behind, easy merge |
| 10 | Significant drift | 6-20 commits behind, conflict possible |
| 5 | Major drift | 20+ commits behind, complex merge |
| 0 | Diverged | Incompatible changes, manual resolution |

### How to Check

```bash
# Fetch upstream
git fetch upstream

# Count divergence
BEHIND=$(git rev-list --count HEAD..upstream/main)
AHEAD=$(git rev-list --count upstream/main..HEAD)

# Show differences
git diff --stat upstream/main

# Check update mechanism
grep -n "update" hermes_cli/main.py | head -5
```

---

## Component 3: Ease of Merge (20 points)

### Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Working tree | 5% | Clean working tree |
| Change scope | 5% | Number of files modified |
| Change type | 5% | Additive vs modifications |
| Runtime files | 5% | No runtime code modified |

### Graded Scoring

| Score | Status | Indicators |
|-------|--------|------------|
| 20 | Perfect | Clean tree, <5 files, additive only |
| 15 | Good | Clean tree, <10 files, minimal mods |
| 10 | Moderate | Dirty tree or 10-20 files modified |
| 5 | Difficult | 20+ files, runtime modifications |
| 0 | Blocked | Runtime code modified, merge unsafe |

### How to Check

```bash
# Working tree status
git status --short

# Count modified files
git diff --name-only | wc -l

# Check file types
git diff --name-only | grep -E "\.py$|\.ts$|\.js$" | wc -l

# Check runtime files
git diff --name-only | grep -E "hermes_cli/|gateway/|agent/" | wc -l
```

---

## Component 4: Branding Consistency (10 points)

### Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Display text | 3% | User-facing says Savarez |
| Internal IDs | 2% | Internal stays Hermes |
| Docs commands | 3% | Documentation uses savarez |
| Installer URLs | 2% | Point to Savarez fork |

### Graded Scoring

| Score | Status | Indicators |
|-------|--------|------------|
| 10 | Perfect | Zero hermes in user-facing, all correct |
| 7 | Good | 1-2 minor remnants, non-critical |
| 4 | Fair | Some inconsistencies, needs cleanup |
| 1 | Poor | Major hermes references in user-facing |
| 0 | Failed | No rebranding applied |

### How to Check

```bash
# User-facing hermes (should be 0)
grep -r "hermes " README.md DEVELOPMENT.md CONTRIBUTING.md | grep -v "HERMES_HOME\|hermes-agent\|equivalent to" | wc -l

# Internal hermes (expected, unchanged)
grep -r "from hermes_" --include="*.py" . | wc -l

# Documentation savarez commands
grep -r "savarez" DEVELOPMENT.md CONTRIBUTING.md | wc -l

# Installer URLs
grep "savarez_agent" scripts/install.sh scripts/install.ps1 | wc -l
```

---

## Score Calculation

### Formula

```
Total = Runtime + Upstream + Merge + Branding
```

### Example

```
Runtime Stability:     40/40 (Perfect)
Upstream Compatibility: 25/30 (Minor drift)
Ease of Merge:         18/20 (Good)
Branding Consistency:   9/10 (Good)

Total: 92/100 (Excellent)
```

### Interpretation

| Range | Status | Release Recommendation |
|-------|--------|----------------------|
| 90-100 | Excellent | Ready for release |
| 70-89 | Good | Release with caution |
| 50-69 | Fair | Work needed before release |
| 30-39 | Poor | Do not release |
| 0-29 | Critical | Halt, fix critical issues |

---

## Action Items by Score

### If Runtime Stability < 40

1. Fix Python syntax errors
2. Verify entry points
3. Fix import errors
4. Test gateway startup

### If Upstream Compatibility < 30

1. Fetch upstream
2. Merge/rebase upstream changes
3. Resolve conflicts
4. Verify update mechanism

### If Ease of Merge < 20

1. Clean working tree
2. Reduce change scope
3. Move runtime changes to documentation
4. Separate commits logically

### If Branding Consistency < 10

1. Search user-facing files
2. Replace hermes with savarez
3. Keep internal identifiers
4. Verify installer URLs
