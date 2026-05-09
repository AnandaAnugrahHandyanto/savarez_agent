# Implementation Plan

## 1. Read-Only Mode for Hermes Agent

### Goal
Implement a configurable read-only mode that prevents destructive operations (file writes, patches, terminal commands, etc.) while allowing read operations (file reads, web search, etc.).

### Approach
- Add a `read_only` config option under `security` section in `DEFAULT_CONFIG`
- Add a `/readonly` slash command to toggle read-only mode
- Modify the tool dispatch layer to check read-only status before executing destructive tools
- Add read-only guards to: `write_file`, `patch`, `terminal`, `execute_code`, `browser_click`, `browser_type`
- Display read-only status in the CLI banner and session status

### Files to modify
- `hermes_cli/config.py` - Add `read_only` to DEFAULT_CONFIG
- `hermes_cli/commands.py` - Add `/readonly` command
- `cli.py` - Add handler for `/readonly`, show status in banner
- `model_tools.py` - Add read-only check in tool dispatch
- `tools/*.py` - Add read-only guards to destructive tools

## 2. PR Creation Workflow (GitHub Integration)

### Goal
Implement a workflow for creating GitHub pull requests from within Hermes Agent.

### Approach
- Add a `github-pr-workflow` skill (or extend existing `github-pr-workflow` skill)
- Create a new tool `create_pr` that uses `gh` CLI or GitHub API
- Add slash command `/pr` to open a PR
- Support: creating branch, committing changes, pushing, and opening PR
- Integrate with existing `github-auth` skill for authentication

### Files to modify
- `tools/github_pr_tool.py` - New tool for PR creation
- `hermes_cli/commands.py` - Add `/pr` command
- `cli.py` - Add handler for `/pr`
- `toolsets.py` - Register new tool

## 3. Feature Request Handling System

### Goal
Implement a system for handling feature requests - tracking, prioritizing, and implementing them.

### Approach
- Create a new `feature_request` tool that stores requests in a structured format
- Add `/feature` slash command to submit/view feature requests
- Store feature requests in `~/.hermes/features/` directory
- Support status tracking: pending, approved, in-progress, completed, rejected
- Allow linking feature requests to kanban tasks

### Files to modify
- `tools/feature_request_tool.py` - New tool for feature requests
- `hermes_cli/commands.py` - Add `/feature` command
- `cli.py` - Add handler for `/feature`
- `toolsets.py` - Register new tool
