<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/session-start/SKILL.md
Original purpose: Session startup briefing — git state, branch-safety check, dev-server status, recent commit history.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: session-start
description: Use PROACTIVELY at the start of a new working session — when user says "brief me", "what's the state", "where were we", or starts a chat after a gap. Displays git state, branch safety check, dev-server status (if applicable), and recent commit history. Also invokable as /start (alias).
disable-model-invocation: true
allowed-tools: Bash(git *) Bash(curl *) Read
---

# Session Start Briefing

> Also invokable as `/start` (alias).

You are beginning a new Claude Code session. Below is the pre-loaded state. Review it and present a concise briefing.

## Pre-Loaded State

**Branch:**
!`git branch --show-current`

**Server status** (edit target URL for your project):
!`curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://localhost:3000 2>/dev/null || echo "DOWN"`

**Recent commits:**
!`git log --oneline -5`

**Working tree:**
!`git status --short`

**Changed files:**
!`git diff --stat`

---

## Your Task

Using the pre-loaded state above, present a concise briefing.

### 1. Branch Safety Check

- If the current branch is `main`, `master`, or contains `LIVE` or `Production` → report **🚨 DANGER: You are on a protected branch. Do NOT edit files. Switch to a feature branch immediately.**
- Otherwise → report "Branch: {name} ✓"

Production merges belong to a human.

### 2. Format Briefing

```
═══════════════════════════════════════════════
  SESSION BRIEFING
═══════════════════════════════════════════════

  Branch:      {branch} {status_icon}
  Dev Server:  {UP on :3000 / DOWN}
  Dirty Files: {count} modified, {count} staged

  Recent Commits:
    {from pre-loaded state}

  Uncommitted Changes:
    {from pre-loaded state, or "Working tree clean"}

═══════════════════════════════════════════════
```

### 3. Surface Risks

Flag any of these if detected in the pre-loaded state:

- **Uncommitted changes in danger-zone files** — maintain a project-specific list of large or fragile files where merge conflicts are painful.
- **Changes to known dead-code files** — maintain a project-specific list of deprecated paths that should never be edited. Warn loudly if any appear in the diff.
- **Line-ending issues** — if any file shows as fully modified with no logical changes, suspect CRLF/LF drift. Suggest `file <filename>` to check.

### 4. Session Reminders

Pull the top 3-5 inviolable rules from the project's `.claude/rules/inviolable-decisions.md` (or equivalent) and surface them concisely. Don't over-lecture; keep the briefing tight. Pre-flight checklist, not a novel.
