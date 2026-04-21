---
name: comfyui-skill-openclaw
description: Run ComfyUI workflows from the terminal — import, manage dependencies, execute across multiple servers, and track history via a single CLI.
version: 1.0.0
author: HuangYuChuh
license: Apache-2.0
platforms: [macos, linux, windows]
prerequisites:
  commands: ["comfyui-skill"]
metadata:
  hermes:
    tags: [image-generation, comfyui, ai-art, workflow, stable-diffusion, flux, creative]
    related_skills: []
    category: creative
setup:
  help: "Install the CLI: pip install -U comfyui-skill-cli. Source: https://github.com/HuangYuChuh/ComfyUI_Skills_OpenClaw"
---

# ComfyUI Agent Skill

Run ComfyUI workflows from any AI agent via a single CLI. Import workflows, manage dependencies, execute across multiple servers, and track history — all through shell commands.

## When to Use

- User requests to "generate an image", "draw a picture", or "execute a ComfyUI workflow"
- User has specific stylistic, character, or scene requirements for image generation
- User asks to import, register, sync, or configure saved ComfyUI workflows for later reuse

## Prerequisites

```bash
pip install -U comfyui-skill-cli
```

After installation, clone the skill workspace:

```bash
git clone https://github.com/HuangYuChuh/ComfyUI_Skills_OpenClaw.git
cd ComfyUI_Skills_OpenClaw
```

> [!IMPORTANT]
> **Directory Sensitivity**: The CLI reads `config.json` and `data/` from the current directory.
> You **MUST** `cd` into the project root before running any command.
> **Symptom**: `list` returns `[]` or `server status` reports not found → you are in the wrong directory.

## Quick Decision

- User says "generate image / draw a picture" → **Execution Flow (Step 1–4)**
- User says "import workflow / add workflow" → `comfyui-skill --json workflow import <path>`
- User says "img2img / use this image" → first `comfyui-skill --json upload <image>`, then execute
- User says "inpainting / mask this area" → `comfyui-skill --json upload <mask> --mask`, then execute
- User says "show previous results" → `comfyui-skill --json history list <id>`
- User says "what failed / check job status" → `comfyui-skill --json jobs list --status failed`
- User says "which server has more VRAM" → `comfyui-skill --json server stats --all`
- User says "what nodes are available" → `comfyui-skill --json nodes list`
- User says "dry run / test without executing" → `comfyui-skill --json run <id> --validate`

## Core Concepts

- **Skill ID**: `<server_id>/<workflow_id>` (e.g., `local/txt2img`). If server is omitted, the default server is used.
- **Schema**: Each workflow has a `schema.json` that maps business parameter names (e.g., `prompt`, `seed`) to internal ComfyUI node fields. Never expose node IDs to the user.
- **Server**: One or more ComfyUI instances configured in `config.json`. Check health with `server status`.

## Command Reference

| Command | Purpose |
|---------|---------|
| `comfyui-skill --json server status` | Check if ComfyUI server is online |
| `comfyui-skill --json server stats` | Show VRAM, RAM, GPU, versions (`--all` for multi-server) |
| `comfyui-skill --json list` | List all available workflows and parameters |
| `comfyui-skill --json info <id>` | Show workflow details and parameter schema |
| `comfyui-skill --json submit <id> --args '{...}'` | Submit a workflow (non-blocking) |
| `comfyui-skill --json status <prompt_id>` | Check execution status |
| `comfyui-skill --json run <id> --args '{...}'` | Execute a workflow (blocking, real-time streaming) |
| `comfyui-skill --json run <id> --validate` | Validate workflow without executing |
| `comfyui-skill --json upload <path>` | Upload image to ComfyUI (for img2img workflows) |
| `comfyui-skill --json upload <path> --mask` | Upload mask image (for inpainting workflows) |
| `comfyui-skill --json nodes list` | List all available ComfyUI nodes |
| `comfyui-skill --json jobs list` | List server-side job history (`--status failed` to filter) |
| `comfyui-skill --json deps check <id>` | Check missing dependencies |
| `comfyui-skill --json deps install <id> --repos '[...]'` | Install missing custom nodes |
| `comfyui-skill --json workflow import <path>` | Import workflow (auto-detect, warns about deprecated nodes) |
| `comfyui-skill --json history list <id>` | List execution history for a workflow |

## Execution Flow

### Step 1: Query Available Workflows

```bash
comfyui-skill --json list
```

Returns a JSON array of all enabled workflows with their parameters.

- `required: true` parameters → **ask the user** if not provided.
- `required: false` parameters → infer from context (e.g., `seed` = random number), or omit.
- Never expose node IDs; only use business parameter names (e.g., prompt, style).

### Step 2: Parameter Assembly

Assemble parameters into a JSON string:
```json
{"prompt": "A beautiful landscape, high quality, masterpiece", "seed": 40128491}
```

If critical parameters are missing, ask the user.

### Step 3: Pre-flight Dependency Check

**Always** run before first execution of a workflow:

```bash
comfyui-skill --json deps check <server_id>/<workflow_id>
```

- If `is_ready` is `true` → proceed to Step 4.
- If `is_ready` is `false`:
  1. Present missing nodes and models to the user.
  2. If user agrees to install:
     ```bash
     comfyui-skill --json deps install <id> --repos '["https://github.com/repo1"]'
     ```
  3. If `needs_restart` is `true`, inform the user to restart ComfyUI, then re-check.
  4. Missing models must be downloaded manually — tell the user which folder to place them in.

### Step 4: Execute the Workflow

> JSON args must be wrapped in single quotes to prevent bash from parsing double quotes.

#### Interactive mode: `submit` + `status` (recommended for chat)

**Submit:**
```bash
comfyui-skill --json submit <id> --args '{"prompt": "..."}'
```
Returns: `{"status": "submitted", "prompt_id": "..."}`.

**Poll:**
```bash
comfyui-skill --json status <prompt_id>
```

Status values: `queued` (with `position`) → `running` → `success` (with `outputs`) or `error`.

Each `status` call must be a **separate tool invocation**. Do NOT write a shell loop.

#### Non-interactive mode: one-shot blocking

```bash
comfyui-skill --json run <id> --args '{"prompt": "..."}'
```

Blocks until finished.

### Step 5: Present Results

On success, the result contains an `outputs` array with file references (`filename`, `subfolder`, `type`). Present the files to the user.

## Workflow Import

```bash
comfyui-skill --json workflow import <json_path>
```

- Supports both API format and editor format (auto-detected, auto-converted).
- Automatically generates `schema.json` with smart parameter extraction.
- After import, check dependencies before first execution.

## Troubleshooting

1. **ComfyUI Offline**: Run `comfyui-skill --json server status`. If offline, ask the user to start ComfyUI.
2. **Workflow Not Found**: Run `comfyui-skill --json list`. If missing, import it first.
3. **Parameter Format Error**: Ensure `--args` is valid JSON wrapped in single quotes.
4. **Cloud Node Unauthorized**: Guide user to generate API Key at https://platform.comfy.org.
