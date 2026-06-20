# Audit Procedures — Platform-Agnostic Reference

## Common Setup

All procedures assume:
- Git is installed and on PATH
- Repository is at current working directory
- Upstream remote is named "upstream"
- GitHub authentication is configured

### Environment Detection

Before running procedures, detect the platform:

```bash
# Detect OS
case "$(uname -s)" in
    Linux*)   OS="linux";;
    Darwin*)  OS="macos";;
    CYGWIN*|MINGW*|MSYS*) OS="windows";;
    *)        OS="unknown";;
esac

# Detect if gh is available
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
    USE_GH=true
else
    USE_GH=false
fi
```

---

## Procedure 1: Fork Health Audit

**Trigger:** User requests fork health check or before release

**Steps:**

1. **Check current branch**
   ```bash
   git branch --show-current
   ```

2. **Check working tree status**
   ```bash
   git status --short
   ```

3. **Fetch upstream**
   ```bash
   git fetch upstream 2>/dev/null
   ```

4. **Check divergence**
   ```bash
   BEHIND=$(git rev-list --count HEAD..upstream/main 2>/dev/null || echo "0")
   AHEAD=$(git rev-list --count upstream/main..HEAD 2>/dev/null || echo "0")
   ```

5. **Verify remotes**
   ```bash
   git remote -v
   ```

6. **Calculate score component**
   - Clean tree: +5
   - On main branch: +5
   - Synced with upstream: +10
   - Remotes configured: +5
   - No uncommitted changes: +5
   - Recent commits (last 7 days): +10

**Expected Output:**
- Branch: main
- Status: Clean/Dirty
- Behind upstream: N commits
- Ahead of upstream: N commits
- Remotes: origin, upstream

---

## Procedure 2: Upstream Sync Check

**Trigger:** User wants to check sync status or before merging

**Steps:**

1. **Fetch latest from upstream**
   ```bash
   git fetch upstream
   ```

2. **Count divergence**
   ```bash
   BEHIND=$(git rev-list --count HEAD..upstream/main)
   AHEAD=$(git rev-list --count upstream/main..HEAD)
   ```

3. **List recent upstream commits**
   ```bash
   git log --oneline HEAD..upstream/main | head -10
   ```

4. **Analyze conflict potential**
   ```bash
   git diff --name-only upstream/main | head -20
   ```

5. **Check file overlap**
   ```bash
   git diff --name-only HEAD | sort > /tmp/local.txt
   git diff --name-only upstream/main | sort > /tmp/upstream.txt
   comm -12 /tmp/local.txt /tmp/upstream.txt
   ```

6. **Calculate score component**
   - 0 commits behind: +30
   - 1-5 commits behind: +20
   - 6-20 commits behind: +10
   - 20+ commits behind: +5
   - No overlapping files: +5 (bonus)

**Expected Output:**
- Commits behind: N
- Commits ahead: N
- Recent upstream: list
- Overlapping files: list
- Conflict risk: Low/Medium/High

---

## Procedure 3: Release Readiness Check

**Trigger:** User wants to release or verify release status

**Steps:**

1. **Read version**
   ```bash
   grep '^version' pyproject.toml | head -1
   ```

2. **List tags**
   ```bash
   git tag --list
   ```

3. **Verify latest tag reachable**
   ```bash
   LATEST=$(git describe --tags --abbrev=0 2>/dev/null)
   git merge-base --is-ancestor $LATEST HEAD && echo "Reachable" || echo "Not reachable"
   ```

4. **Check documentation**
   ```bash
   for f in README.md DEVELOPMENT.md CONTRIBUTING.md; do
       [ -f "$f" ] && echo "$f: EXISTS" || echo "$f: MISSING"
   done
   ```

5. **Verify tag on remote**
   ```bash
   git ls-remote --tags origin | grep $LATEST
   ```

**Expected Output:**
- Version: x.y.z
- Tags: list
- Latest tag: name (reachable/not reachable)
- Documentation: all present/missing
- Remote sync: synced/not synced

---

## Procedure 4: Rebranding Audit

**Trigger:** User wants to verify rebranding status

**Steps:**

1. **Check user-facing text**
   ```bash
   grep -r "Hermes Agent" README.md CONTRIBUTING.md DEVELOPMENT.md 2>/dev/null | \
       grep -v "fork of\|Based on\|upstream" | wc -l
   ```

2. **Verify internal identifiers**
   ```bash
   grep -r "from hermes_" --include="*.py" . | wc -l
   ```

3. **Check documentation commands**
   ```bash
   grep -r "hermes " README.md DEVELOPMENT.md CONTRIBUTING.md 2>/dev/null | \
       grep -v "HERMES_HOME\|hermes-agent\|equivalent to" | wc -l
   ```

4. **Verify installer URLs**
   ```bash
   grep "REPO_URL" scripts/install.sh
   grep "RepoUrl" scripts/install.ps1
   ```

**Expected Output:**
- User-facing hermes: 0
- Internal hermes: N (expected)
- Doc hermes commands: 0
- Installer URLs: Savarez fork

---

## Procedure 5: Maintenance Mode Compliance

**Trigger:** User wants to verify maintenance rules

**Steps:**

1. **Check HERMES_HOME**
   ```bash
   grep -r "HERMES_HOME" --include="*.py" . | wc -l
   ```

2. **Check internal modules**
   ```bash
   grep -r "from hermes_" --include="*.py" . | wc -l
   ```

3. **Check Python imports**
   ```bash
   grep -r "import hermes" --include="*.py" . | wc -l
   ```

4. **Check gateway code**
   ```bash
   git diff upstream/main -- gateway/ | wc -l
   ```

5. **Verify allowed changes**
   ```bash
   git diff upstream/main --stat | grep -E "README|CONTRIBUTING|DEVELOPMENT|install"
   ```

**Expected Output:**
- HERMES_HOME: N (unchanged)
- Internal modules: N (unchanged)
- Imports: N (unchanged)
- Gateway diff: 0 lines
- Allowed files: list of changed

---

## Procedure 6: Tag Audit

**Trigger:** User wants to verify tag status

**Steps:**

1. **List all tags**
   ```bash
   git tag --list
   ```

2. **Identify latest tag**
   ```bash
   git describe --tags --abbrev=0 2>/dev/null || echo "No tags"
   ```

3. **Verify tag reachable from HEAD**
   ```bash
   TAG=$(git describe --tags --abbrev=0 2>/dev/null)
   if [ -n "$TAG" ]; then
       git merge-base --is-ancestor $TAG HEAD && echo "Reachable" || echo "Not reachable"
   fi
   ```

4. **Check tag on remote**
   ```bash
   git ls-remote --tags origin | grep "$TAG" && echo "Pushed" || echo "Not pushed"
   ```

5. **Verify clean tree at tag**
   ```bash
   TAG=$(git describe --tags --abbrev=0)
   git stash
   git checkout $TAG
   [ -z "$(git status --porcelain)" ] && echo "Clean" || echo "Dirty"
   git checkout -
   git stash pop
   ```

**Expected Output:**
- Tags: list
- Latest: tag-name
- Reachable: yes/no
- Remote: pushed/not pushed
- Clean at tag: yes/no

---

## Procedure 7: Installer Audit

**Trigger:** User wants to verify installer integrity

**Steps:**

1. **Check install.sh URL**
   ```bash
   grep 'REPO_URL_SSH\|REPO_URL_HTTPS' scripts/install.sh
   ```

2. **Check install.ps1 URL**
   ```bash
   grep 'RepoUrlSsh\|RepoUrlHttps' scripts/install.ps1
   ```

3. **Check install.cmd URL**
   ```bash
   grep 'raw.githubusercontent.com' scripts/install.cmd
   ```

4. **Verify clone target**
   ```bash
   grep 'savarez_agent' scripts/install.sh scripts/install.ps1 scripts/install.cmd
   ```

5. **Check savarez launcher**
   ```bash
   grep -A5 'savarez' scripts/install.sh | head -10
   ```

6. **Check hermes launcher preserved**
   ```bash
   grep -A5 'hermes' scripts/install.sh | grep 'cat >\|ln -sf' | head -5
   ```

**Expected Output:**
- install.sh: AnandaAnugrahHandyanto/savarez_agent
- install.ps1: AnandaAnugrahHandyanto/savarez_agent
- install.cmd: AnandaAnugrahHandyanto/savarez_agent
- Clone target: Savarez fork
- savarez launcher: Present
- hermes launcher: Present

---

## Cross-Procedure Dependencies

| Procedure | Depends On |
|-----------|------------|
| Fork Health | Git, remotes configured |
| Upstream Sync | Fork Health (fetch) |
| Release Readiness | Upstream Sync (synced) |
| Rebranding Audit | None |
| Maintenance Mode | None |
| Tag Audit | Git tags exist |
| Installer Audit | Installer files exist |

## Running All Procedures

For a complete audit, run in this order:

1. Fork Health Audit
2. Upstream Sync Check
3. Release Readiness Check
4. Rebranding Audit
5. Maintenance Mode Compliance
6. Tag Audit
7. Installer Audit

Then calculate total health score.
