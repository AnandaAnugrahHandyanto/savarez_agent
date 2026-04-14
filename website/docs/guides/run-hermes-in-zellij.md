---
sidebar_position: 18
title: "Run Hermes in zellij"
description: "Use zellij as a PTY-backed multiplexer for long-lived interactive Hermes sessions and parallel agents"
---

# Run Hermes in zellij

This guide shows how to run Hermes Agent inside detached `zellij` sessions.

Use this when:
- you want a real PTY for `prompt_toolkit`
- `tmux` is not installed
- you prefer `zellij`
- you want one or more long-lived Hermes subprocesses

If you only need a quick bounded subtask, prefer `delegate_task` instead of spawning a separate Hermes process.

## Why zellij works

Hermes' interactive CLI needs a real terminal. A plain background shell process is not enough.

`zellij` provides the missing PTY and supports the core automation operations needed for spawned-agent workflows:
- create detached/background sessions
- run Hermes in a pane
- list panes
- send keystrokes
- dump pane output

## Fastest path: helper scripts

On systems where you have installed the helper scripts, the workflow is:

```bash
hermes-zellij-start agent1
hermes-zellij-send agent1 "Build a FastAPI auth service"
hermes-zellij-read agent1
hermes-zellij-stop agent1
```

For code-editing agents, prefer worktree mode:

```bash
hermes-zellij-start backend -w
hermes-zellij-start frontend -w
```

You can find example helper scripts in:

- `/docs/static/examples/hermes-zellij/hermes-zellij-common.sh`
- `/docs/static/examples/hermes-zellij/hermes-zellij-start.sh`
- `/docs/static/examples/hermes-zellij/hermes-zellij-send.sh`
- `/docs/static/examples/hermes-zellij/hermes-zellij-read.sh`
- `/docs/static/examples/hermes-zellij/hermes-zellij-stop.sh`

## Raw zellij workflow

### 1. Create a detached session

```bash
zellij attach -b agent1
```

### 2. Start Hermes in that session

```bash
zellij -s agent1 run --cwd "$PWD" -- hermes
```

### 3. List panes

```bash
zellij -s agent1 action list-panes --json
```

Look for a pane such as `terminal_0`.

### 4. Send a prompt

```bash
zellij -s agent1 action write-chars -p terminal_0 "Build a FastAPI auth service"
zellij -s agent1 action send-keys -p terminal_0 Enter
```

### 5. Read pane output

```bash
zellij -s agent1 action dump-screen -p terminal_0 --full
```

### 6. Exit and clean up

```bash
zellij -s agent1 action write-chars -p terminal_0 "/exit"
zellij -s agent1 action send-keys -p terminal_0 Enter
sleep 2
zellij kill-session agent1
```

## Resume an existing Hermes session

Resume most recent:

```bash
hermes-zellij-start resumed --continue
```

Resume a specific Hermes transcript:

```bash
hermes-zellij-start resumed --resume 20260225_143052_a1b2c3
```

## Two-agent pattern

Start two agents:

```bash
hermes-zellij-start backend -w
hermes-zellij-start frontend -w
```

Send tasks:

```bash
hermes-zellij-send backend "Build REST API for user management"
hermes-zellij-send frontend "Build React dashboard for user management"
```

Read status:

```bash
hermes-zellij-read backend
hermes-zellij-read frontend
```

Relay context manually:

```bash
hermes-zellij-send frontend "Here is the API schema from the backend agent: ..."
```

## Pitfalls

- Always confirm pane IDs if you are using raw `zellij` commands.
- If a session has multiple panes, explicit pane IDs are safer than auto-detection.
- `zellij list-sessions` may show old sessions as `EXITED`; this is normal session metadata.
- If Hermes config or tool changes were just made, restart Hermes or use `/reset` before relying on them.

## When to use tmux instead

You do not need to switch if `zellij` already works for you. `tmux` is only another valid PTY-backed option.

The important requirement is not tmux specifically — it is having a real terminal multiplexer for the interactive Hermes process.
