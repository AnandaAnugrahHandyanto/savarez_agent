---
sidebar_position: 1
title: "Tools & Toolsets"
description: "Overview of Hermes Agent's tools — what's available, how toolsets work, and terminal backends"
---

# Tools & Toolsets

Tools are functions that extend the agent's capabilities. They're organized into logical **toolsets** that can be enabled or disabled per platform.

## Available Tools

Hermes ships with a broad built-in tool registry covering web search, browser automation, terminal execution, file editing, memory, delegation, RL training, messaging delivery, Home Assistant, and more.

:::note
**Honcho cross-session memory** is available as a memory provider plugin (`plugins/memory/honcho/`), not as a built-in toolset. See [Plugins](./plugins.md) for installation.
:::

High-level categories:

| Category | Examples | Description |
|----------|----------|-------------|
| **Web** | `web_search`, `web_extract` | Search the web and extract page content. |
| **Terminal & Files** | `terminal`, `process`, `read_file`, `patch` | Execute commands and manipulate files. |
| **Browser** | `browser_navigate`, `browser_snapshot`, `browser_vision` | Interactive browser automation with text and vision support. |
| **Media** | `vision_analyze`, `image_generate`, `text_to_speech` | Multimodal analysis and generation. |
| **Agent orchestration** | `todo`, `clarify`, `execute_code`, `delegate_task` | Planning, clarification, code execution, and subagent delegation. |
| **Memory & recall** | `memory`, `session_search` | Persistent memory and session search. |
| **Automation & delivery** | `cronjob`, `send_message` | Scheduled tasks with create/list/update/pause/resume/run/remove actions, plus outbound messaging delivery. |
| **Integrations** | `ha_*`, MCP server tools, `rl_*` | Home Assistant, MCP, RL training, and other integrations. |

For the authoritative code-derived registry, see [Built-in Tools Reference](/docs/reference/tools-reference) and [Toolsets Reference](/docs/reference/toolsets-reference).

:::tip Nous Tool Gateway
Paid [Nous Portal](https://portal.nousresearch.com) subscribers can use web search, image generation, TTS, and browser automation through the **[Tool Gateway](tool-gateway.md)** — no separate API keys needed. Run `hermes model` to enable it, or configure individual tools with `hermes tools`.
:::

## Using Toolsets

```bash
# Use specific toolsets
hermes chat --toolsets "web,terminal"

# See all available tools
hermes tools

# Configure tools per platform (interactive)
hermes tools
```

Common toolsets include `web`, `terminal`, `file`, `browser`, `vision`, `image_gen`, `moa`, `skills`, `tts`, `todo`, `memory`, `session_search`, `cronjob`, `code_execution`, `delegation`, `clarify`, `homeassistant`, and `rl`.

See [Toolsets Reference](/docs/reference/toolsets-reference) for the full set, including platform presets such as `hermes-cli`, `hermes-telegram`, and dynamic MCP toolsets like `mcp-<server>`.

## Terminal Backends

The terminal tool can execute commands in different environments:

| Backend | Description | Use Case |
|---------|-------------|----------|
| `local` | Run on your machine (default) | Development, trusted tasks |
| `docker` | Isolated containers | Security, reproducibility |
| `ssh` | Remote server | Sandboxing, keep agent away from its own code |
| `singularity` | HPC containers | Cluster computing, rootless |
| `modal` | Cloud execution | Serverless, scale |
| `daytona` | Cloud sandbox workspace | Persistent remote dev environments |

### Configuration

```yaml
# In ~/.hermes/config.yaml
terminal:
  backend: local    # or: docker, ssh, singularity, modal, daytona
  cwd: "."          # Working directory
  timeout: 180      # Command timeout in seconds
```

### Docker Backend

```yaml
terminal:
  backend: docker
  docker_image: python:3.11-slim
```

### SSH Backend

Recommended for security — agent can't modify its own code:

```yaml
terminal:
  backend: ssh
```
```bash
# Set credentials in ~/.hermes/.env
TERMINAL_SSH_HOST=my-server.example.com
TERMINAL_SSH_USER=myuser
TERMINAL_SSH_KEY=~/.ssh/id_rsa
```

### Singularity/Apptainer

```bash
# Pre-build SIF for parallel workers
apptainer build ~/python.sif docker://python:3.11-slim

# Configure
hermes config set terminal.backend singularity
hermes config set terminal.singularity_image ~/python.sif
```

### Modal (Serverless Cloud)

```bash
uv pip install modal
modal setup
hermes config set terminal.backend modal
```

### Container Resources

Configure CPU, memory, disk, and persistence for all container backends:

```yaml
terminal:
  backend: docker  # or singularity, modal, daytona
  container_cpu: 1              # CPU cores (default: 1)
  container_memory: 5120        # Memory in MB (default: 5GB)
  container_disk: 51200         # Disk in MB (default: 50GB)
  container_persistent: true    # Persist filesystem across sessions (default: true)
```

When `container_persistent: true`, installed packages, files, and config survive across sessions.

### Container Security

All container backends run with security hardening:

- Read-only root filesystem (Docker)
- All Linux capabilities dropped
- No privilege escalation
- PID limits (256 processes)
- Full namespace isolation
- Persistent workspace via volumes, not writable root layer

Docker can optionally receive an explicit env allowlist via `terminal.docker_forward_env`, but forwarded variables are visible to commands inside the container and should be treated as exposed to that session.

## Background Process Management

Start background processes and manage them:

```python
terminal(command="pytest -v tests/", background=true)
# Returns: {"session_id": "proc_abc123", "pid": 12345}

# Then manage with the process tool:
process(action="list")       # Show all running processes
process(action="poll", session_id="proc_abc123")   # Check status
process(action="wait", session_id="proc_abc123")   # Block until done
process(action="log", session_id="proc_abc123")    # Full output
process(action="kill", session_id="proc_abc123")   # Terminate
process(action="write", session_id="proc_abc123", data="y")  # Send input
```

PTY mode (`pty=true`) enables interactive CLI tools like Codex and Claude Code.

## Sudo Support

If a command needs sudo, you'll be prompted for your password (cached for the session). Or set `SUDO_PASSWORD` in `~/.hermes/.env`.

:::warning
On messaging platforms, if sudo fails, the output includes a tip to add `SUDO_PASSWORD` to `~/.hermes/.env`.
:::

## Web Backend Configuration

Hermes supports multiple web search backends: **Exa**, **Firecrawl**, **Parallel**, and **Tavily**. Configure your preferred backend with `hermes tools` or directly in `~/.hermes/config.yaml`.

```yaml
# Web backend configuration
web:
  backend: exa  # Options: exa, firecrawl, parallel, tavily
```

### Exa (Recommended for Agent Search)

[Exa.ai](https://exa.ai) provides **query-specific highlights** — AI-generated excerpts that are directly relevant to your search query, perfect for agent reasoning.

```bash
# Set your API key
export EXA_API_KEY="your-api-key"
```

#### Exa Highlights

Exa's highlights are query-specific rather than generic page snippets. This means when you search for "Python async patterns", the highlights contain relevant async programming content, not just the first 200 characters of the page.

```yaml
# Exa-specific configuration
web:
  backend: exa
  exa:
    highlights_max_characters: 2000  # Max chars per highlight (default: 2000)
    highlights_enabled: true       # Use highlights as primary content (default: true)
    full_text_fallback: true       # Fall back to full text when needed (default: true)
```

#### Search Result Structure

When using Exa, search results include structured highlights:

```json
{
  "success": true,
  "data": {
    "web": [
      {
        "url": "https://example.com/article",
        "title": "Article Title",
        "description": "Concatenated highlights for backward compatibility",
        "highlights": [
          "First relevant excerpt from the page...",
          "Second relevant excerpt..."
        ],
        "published_date": "2024-01-15",
        "position": 1
      }
    ]
  }
}
```

| Field | Description |
|-------|-------------|
| `url` | Result URL |
| `title` | Page title |
| `description` | Concatenated highlights (backward compatible) |
| `highlights` | **Query-specific excerpts** as a list |
| `published_date` | Publication date when available |
| `position` | Ranking position |

#### Full-Text Fallback

When highlights are completely empty (rare), Exa can fetch full page content as a fallback. The `_exa_search_with_fallback()` function automatically detects empty highlights and fetches full text only when needed.

```python
# Example: Search with fallback for empty highlights
from tools.web_tools import _exa_search_with_fallback

result = _exa_search_with_fallback(
    "machine learning tutorial",
    limit=5
)
```

Results with full-text fallback include a `full_text` field alongside `highlights` and `description`. Note: Per Exa research, short highlights should NOT trigger fallback—they remain efficient and relevant even at 500 characters.

### Firecrawl

[Firecrawl](https://firecrawl.dev) provides comprehensive web scraping and crawling.

```bash
export FIRECRAWL_API_KEY="your-api-key"
```

With a Nous subscription, Firecrawl can be accessed through the Tool Gateway:

```bash
hermes model  # Enable Nous Tool Gateway
```

### Parallel

[Parallel](https://parallel.ai) provides fast, agentic search with multiple modes.

```bash
export PARALLEL_API_KEY="your-api-key"
```

### Tavily

[Tavily](https://tavily.com) provides AI-optimized search for LLM applications.

```bash
export TAVILY_API_KEY="your-api-key"
```
