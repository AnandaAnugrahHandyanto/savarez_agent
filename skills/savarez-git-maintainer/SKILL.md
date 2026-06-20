---
name: savarez-git-maintainer
description: "Audit fork health, upstream sync, rebranding status, release readiness, maintenance mode compliance, and installer integrity for Savarez Agent."
version: 1.0.0
author: Savarez Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [git, fork, upstream, sync, rebranding, maintenance, audit, health-score, installer]
    related_skills: [github-repo-management, github-pr-workflow]
---

# Savarez Git Maintainer

## Overview

Skill ini menyediakan procedure untuk audit kesehatan fork Savarez Agent.
Tidak mendaftarkan slash commands — gunakan procedure secara langsung saat dibutuhkan.

Cocok digunakan sebelum release, saat maintenance rutin, atau ketika memecah masalah sync dengan upstream.

## When to Use

- Audit fork health sebelum release
- Cek sync status dengan upstream
- Verifikasi rebranding completeness
- Validasi maintenance mode compliance
- Debug merge conflicts
- Verifikasi installer integrity
- Cek status tag dan release readiness

**Don't use for:**

- Runtime debugging (gunakan systematic-debugging)
- Code review (gunakan github-code-review)
- General git operations (gunakan github-repo-management)

## Savarez Health Score

### Scoring System

| Component | Weight | Description |
|-----------|--------|-------------|
| Runtime Stability | 40% | Python, entrypoints, imports, gateway |
| Upstream Compatibility | 30% | Sync status, divergence, conflicts |
| Ease of Merge | 20% | Working tree, change scope, runtime files |
| Branding Consistency | 10% | Display text, docs, installer URLs |

### Graded Scoring

#### Runtime Stability (40 points max)

| Score | Status | Description |
|-------|--------|-------------|
| 40 | Perfect | All checks pass, zero issues |
| 30 | Minor warnings | Non-critical warnings, functionally sound |
| 20 | Degraded | Some components have issues, core works |
| 10 | Serious issue | Major component broken, needs immediate fix |
| 0 | Broken | Critical failure, cannot proceed |

#### Upstream Compatibility (30 points max)

| Score | Status | Description |
|-------|--------|-------------|
| 30 | Perfect | Fully synced, zero divergence |
| 20 | Minor drift | Few commits behind, easy merge |
| 10 | Significant drift | Many commits behind, conflict risk |
| 5 | Major drift | Substantial divergence, complex merge |
| 0 | Diverged | Incompatible changes, manual resolution needed |

#### Ease of Merge (20 points max)

| Score | Status | Description |
|-------|--------|-------------|
| 20 | Perfect | Clean tree, minimal additive changes |
| 15 | Good | Minor modifications, low conflict risk |
| 10 | Moderate | Some modified files, medium conflict risk |
| 5 | Difficult | Many modified files, high conflict risk |
| 0 | Blocked | Runtime files modified, merge not recommended |

#### Branding Consistency (10 points max)

| Score | Status | Description |
|-------|--------|-------------|
| 10 | Perfect | All branding correct, zero hermes in user-facing |
| 7 | Good | Minor remnants, non-critical |
| 4 | Fair | Some inconsistencies, needs cleanup |
| 1 | Poor | Major inconsistencies, rebranding incomplete |
| 0 | Failed | No rebranding applied |

### Score Interpretation

| Total Score | Status | Recommendation |
|-------------|--------|----------------|
| 90-100 | Excellent | Ready for release |
| 70-89 | Good | Minor issues, can release with caution |
| 50-69 | Fair | Significant work needed before release |
| 30-39 | Poor | Major issues, do not release |
| 0-29 | Critical | System needs attention, halt releases |

## Procedures

### Procedure 1: Fork Health Audit

**Purpose:** Comprehensive health check of the fork repository.

**What It Checks:**
- Repository status (clean/dirty)
- Branch divergence from upstream
- Remote configuration
- Working tree state

**How to Run:**

1. Check current branch and status
2. Fetch upstream remote
3. Compare HEAD with upstream/main
4. Check for uncommitted changes
5. Verify remote configuration
6. Calculate Runtime Stability component

**Expected Output:**
- Current branch name
- Clean/dirty status
- Commits ahead/behind upstream
- Remote URLs configured
- Health score component

---

### Procedure 2: Upstream Sync Check

**Purpose:** Verify synchronization status with upstream Hermes Agent.

**What It Checks:**
- Commits behind upstream
- Commits ahead of upstream
- Recent upstream changes
- Merge conflict potential

**How to Run:**

1. Fetch latest from upstream
2. Count commits behind upstream/main
3. Count commits ahead of upstream/main
4. List recent upstream commits
5. Analyze file overlap for conflict risk
6. Calculate Upstream Compatibility component

**Expected Output:**
- Commits behind: N
- Commits ahead: N
- Recent upstream commits (last 5)
- Conflict risk level
- Health score component

---

### Procedure 3: Release Readiness Check

**Purpose:** Verify repository is ready for release.

**What It Checks:**
- Version consistency in pyproject.toml
- Git tags present and reachable
- Documentation files exist
- Test status

**How to Run:**

1. Read version from pyproject.toml
2. List git tags
3. Verify latest tag is reachable from HEAD
4. Check documentation files exist
5. Run basic syntax checks
6. Calculate Release Readiness component

**Expected Output:**
- Current version
- List of tags
- Tag reachability status
- Documentation status
- Readiness assessment

---

### Procedure 4: Rebranding Audit

**Purpose:** Verify rebranding completeness and correctness.

**What It Checks:**
- User-facing text (should be Savarez)
- Internal identifiers (should stay Hermes)
- Documentation commands (should use savarez)
- Installer URLs (should point to fork)

**How to Run:**

1. Search user-facing files for "Hermes Agent" (excluding attribution)
2. Verify internal Python references unchanged
3. Check documentation uses savarez commands
4. Verify installer URLs point to Savarez fork
5. Calculate Branding Consistency component

**Expected Output:**
- User-facing hermes references (should be 0)
- Internal hermes references (expected count)
- Documentation savarez commands
- Installer URL status
- Health score component

---

### Procedure 5: Maintenance Mode Compliance

**Purpose:** Verify maintenance mode rules are followed.

**What It Checks:**
- DO NOT MODIFY items unchanged
- ALLOWED changes present
- Priority compliance
- Merge conflict risk

**How to Run:**

1. Check HERMES_HOME references unchanged
2. Check internal module names unchanged
3. Check Python imports unchanged
4. Check gateway internals unchanged
5. Verify allowed changes (README, docs, installer URLs, branding)
6. Calculate Ease of Merge component

**Expected Output:**
- HERMES_HOME reference count
- Internal module reference count
- Python import count
- Gateway code untouched
- Allowed changes present
- Health score component

---

### Procedure 6: Tag Audit

**Purpose:** Verify tag status and release trail.

**What It Checks:**
- Latest tag identification
- Tag reachability from HEAD
- Tag pushed to remote
- Working tree clean at tag

**How to Run:**

1. List all tags
2. Identify latest tag
3. Verify tag is ancestor of HEAD
4. Check tag exists on remote
5. Check working tree status
6. Calculate tag health

**Expected Output:**
- All tags list
- Latest tag name
- Reachability status
- Remote sync status
- Working tree status

---

### Procedure 7: Installer Audit

**Purpose:** Verify installer integrity and fork routing.

**What It Checks:**
- install.sh repository URL
- install.ps1 repository URL
- install.cmd repository URL
- Installer clone target
- savarez launcher creation
- hermes launcher preservation

**How to Run:**

1. Read REPO_URL from install.sh
2. Read RepoUrl from install.ps1
3. Read launch URL from install.cmd
4. Verify all point to Savarez fork
5. Check savarez launcher code present
6. Check hermes launcher code present
7. Verify no upstream clone targets

**Expected Output:**
- install.sh URL status
- install.ps1 URL status
- install.cmd URL status
- Clone target verification
- Launcher creation status
- Compatibility preservation status

**Expected Values:**
- install.sh: `AnandaAnugrahHandyanto/savarez_agent`
- install.ps1: `AnandaAnugrahHandyanto/savarez_agent`
- install.cmd: `AnandaAnugrahHandyanto/savarez_agent`
- savarez launcher: Present
- hermes launcher: Present

---

## Common Pitfalls

1. **Running audit on dirty working tree**
   - Solution: Commit or stash changes first

2. **Forgetting to fetch upstream before sync check**
   - Solution: Always run `git fetch upstream` first

3. **Misinterpreting health score**
   - Solution: Read score breakdown, not just total

4. **Not verifying tag reachability**
   - Solution: Use `git merge-base --is-ancestor`

5. **Checking installer URLs in wrong files**
   - Solution: Verify file paths match expected locations

## Verification Checklist

After running any procedure:

- [ ] Understand the output
- [ ] Note the health score component
- [ ] Identify action items
- [ ] Prioritize fixes if needed
- [ ] Re-run audit after fixes
