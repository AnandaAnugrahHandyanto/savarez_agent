# Savarez Health Score — Detailed Criteria

## Overview

The Savarez Health Score provides a quantified measure of fork health.
Score ranges from 0-100, composed of four weighted components.

**Design Principle:** Measure fork health realistically. A maintained fork should score high even if not perfectly synced with upstream.

---

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

### Expected References (Not Flagged)

These are internal runtime requirements, NOT branding issues:

- `from hermes_cli` imports
- `HERMES_HOME` environment variable
- `hermes-agent` package references
- Gateway internals

---

## Component 2: Upstream Compatibility (30 points)

### Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Sync status | 10% | Commits behind/ahead upstream |
| Divergence | 10% | File differences with upstream |
| Conflict risk | 5% | Overlap of modified files |
| Update logic | 5% | Update mechanism intact |

### Graded Divergence Thresholds

**Key Principle:** A maintained fork SHOULD have some divergence. Perfect sync is not required for health.

| Commits Behind | Score | Status | Description |
|----------------|-------|--------|-------------|
| 0-20 | 30/30 | Excellent | Fork is current, easy merge |
| 21-100 | 25/30 | Good | Minor drift, manageable merge |
| 101-500 | 20/30 | Acceptable | Moderate drift, planned merge |
| 501-1000 | 10/30 | Significant | Major drift, needs attention |
| >1000 | 0/30 | Critical | Fork is abandoned or incompatible |

### Why These Thresholds?

- **0-20 commits:** Normal maintenance window. Most projects merge within this range.
- **21-100 commits:** Acceptable for actively developed forks. Merge is straightforward.
- **101-500 commits:** Fork is diverging but still maintainable. Requires planning.
- **501-1000 commits:** Fork is significantly behind. Major effort to sync.
- **>1000 commits:** Fork is likely abandoned or incompatible with upstream.

### Fetch Verification

**Critical:** Always verify upstream is fetched before counting divergence.

```bash
# Verify upstream exists
if ! git remote get-url upstream >/dev/null 2>&1; then
    STATUS="NO_UPSTREAM"
    BEHIND="N/A"
else
    # Fetch latest
    git fetch upstream 2>/dev/null
    
    # Verify upstream/main exists
    if ! git rev-parse upstream/main >/dev/null 2>&1; then
        STATUS="UNAVAILABLE"
        BEHIND="N/A"
    else
        STATUS="FETCHED"
        BEHIND=$(git rev-list --count HEAD..upstream/main)
    fi
fi
```

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

### Expected References (Not Flagged)

These are NOT upstream compatibility issues:

- Local feature branches
- Documentation-only changes
- Branding customizations
- Installer modifications

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
| Display text | 4% | User-facing says Savarez |
| Docs commands | 4% | Documentation uses savarez |
| Installer URLs | 2% | Point to Savarez fork |

### User-Facing Audit Surfaces

**ONLY these files are audited for branding:**

| Surface | Examples |
|---------|----------|
| Documentation | README.md, CONTRIBUTING.md, DEVELOPMENT.md |
| Installer banners | install.sh, install.ps1, install.cmd output |
| CLI help text | --help output, version strings |
| Release notes | CHANGELOG.md, RELEASES.md |

**NOT audited (expected internal references):**

| Pattern | Reason |
|---------|--------|
| `HERMES_HOME` | Environment variable, required for runtime |
| `hermes_cli` | Python module path, required for imports |
| `hermes-agent` | Package name, required for pip |
| `from hermes_` | Python imports, required for functionality |
| Gateway internals | Runtime code, not user-facing |
| Update logic | Runtime code, not user-facing |

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
# Define user-facing surfaces
USER_FACING="README.md DEVELOPMENT.md CONTRIBUTING.md"

# User-facing hermes (FLAGGED)
grep -r "hermes " $USER_FACING | \
    grep -v "HERMES_HOME\|hermes-agent\|equivalent to\|HermesClaw\|fork of\|Based on" | \
    wc -l

# Internal hermes (EXPECTED, not flagged)
grep -r "from hermes_" --include="*.py" . | wc -l
grep -r "HERMES_HOME" --include="*.py" . | wc -l

# Documentation savarez commands
grep -r "savarez" $USER_FACING | wc -l

# Installer URLs
grep "savarez_agent" scripts/install.sh scripts/install.ps1 | wc -l
```

### Expected Output Format

```
=== Branding Consistency ===

User-facing issues: 0
- "Hermes Agent" in text: 0
- hermes commands in docs: 0
- Installer URLs wrong: 0

Expected internal references (not flagged):
- Python imports: 5,086
- HERMES_HOME: 2,608
- hermes_cli: 1,200
```

---

## Score Calculation

### Formula

```
Total = Runtime + Upstream + Merge + Branding
```

### Example (Healthy Maintained Fork)

```
Runtime Stability:      40/40 (Perfect)
Upstream Compatibility: 25/30 (Good - 50 commits behind)
Ease of Merge:          18/20 (Good)
Branding Consistency:    8/10 (Good)

Total: 91/100 (Excellent)
```

### Example (v1.0 False Positive)

```
Runtime Stability:      20/40 (WRONG - flagged internal imports)
Upstream Compatibility:  8/30 (WRONG - fetch not verified)
Ease of Merge:          12/20 (OK)
Branding Consistency:    8/10 (WRONG - flagged internal refs)

Total: 48/100 (FALSE NEGATIVE)
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

**Note:** Score of 20-29 is normal for active forks. Only act if score < 20.

### If Ease of Merge < 20

1. Clean working tree
2. Reduce change scope
3. Move runtime changes to documentation
4. Separate commits logically

### If Branding Consistency < 10

1. Search user-facing files only
2. Replace hermes with savarez in user-facing text
3. Keep internal identifiers unchanged
4. Verify installer URLs
