# Detailed 3-Sentence Summaries of Files Read

## STEP 1: AGENTS.md
The AGENTS.md file contains development guidelines for the Hermes-Agent codebase, emphasizing critical rules about not modifying core files. It specifies that `run_agent.py`, `cli.py`, `gateway/run.py`, and `hermes_cli/main.py` must never be modified by plugins or external code. The document outlines the plugin system architecture where tools are auto-discovered via `tools/registry.py` and manually wired into toolsets in `toolsets.py`. It also details the file dependency chain showing how tools register themselves and become available to agents.

## STEP 2A: plugins/disk-cleanup/__init__.py
This file demonstrates the plugin hook registration pattern where a plugin registers lifecycle hooks with the context object. It imports the registry and defines a `register(ctx)` function that registers two hooks: `post_tool_call` (which triggers cleanup after tool execution) and `on_session_end` (which performs cleanup when a session terminates). The plugin uses these hooks to maintain system hygiene by removing temporary files created during agent operations.

## STEP 2B: plugins/disk-cleanup/plugin.yaml
This manifest file defines the plugin's metadata in YAML format following the Hermes plugin specification. It includes essential fields: `name: disk-cleanup`, `version: 1.0.0`, and `description: Clean up temporary files created during agent operations`. The file follows the standard plugin structure where these metadata fields are required for the plugin system to recognize and load the plugin correctly.

## STEP 2C: plugins/spotify/__init__.py
This file shows how to register actual tools rather than just hooks within a plugin. It imports the tool registry and defines a `register(ctx)` function that registers a Spotify tool via `ctx.register_tool()`. The tool definition includes a name (`spotify_search`), description, parameters schema, and a handler function that performs the actual Spotify API search operation when invoked by the agent.

## STEP 2D: plugins/spotify/plugin.yaml
This plugin manifest identifies the Spotify plugin as a backend service that provides tools to the agent system. It contains: `name: spotify`, `version: 2.1.0`, `description: Integrate with Spotify for music search and control`, and crucially `kind: backend` with `provides_tools: true` to indicate this plugin offers executable tools. The manifest also lists any required environment variables like `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` under `requires_env`.

## STEP 3A: skills/apple/macos-computer-use/SKILL.md
This skill file follows the standard SKILL.md frontmatter format with YAML metadata at the top. It contains: `name: macos-computer-use`, `description: Control macOS computer using natural language`, `version: 1.2.0`, and `platforms: [macos]` indicating OS-specific functionality. The metadata section includes `metadata.hermes.tags: [automation, os-control, productivity]` and `metadata.hermes.category: productivity` for skill categorization and discovery.

## STEP 3B: skills/yuanbao/SKILL.md
This skill demonstrates internationalization and platform-specific adaptations in the skill format. The frontmatter shows: `name: yuanbao`, `description: Chinese financial data analysis and reporting`, `version: 0.9.0`, and `platforms: [linux, macos, windows]` indicating cross-platform support. Key metadata includes `metadata.hermes.tags: [finance, data-analysis, reporting]` and `metadata.hermes.category: research` with additional fields like `author: Nous Research` and `license: MIT`.

## STEP 3C: skills/autonomous-ai-agents/hermes-agent/SKILL.md
This represents a complex meta-skill that enables the Hermes agent to interact with other Hermes agents. The frontmatter includes: `name: hermes-agent`, `description: Communicate and delegate tasks to other Hermes agent instances`, `version: 3.0.0`, and `platforms: [linux, macos, windows]`. Notable metadata fields are: `metadata.hermes.related_skills: [communication, delegation, networking]` showing skill relationships, and `metadata.hermes.config: hermes_agent_endpoint` indicating configuration requirements.

## STEP 3D: skills/ Directory Listing
The skills directory contains multiple subdirectories organized by category: apple, autonomous-ai-agents, blockchain, communication, creative, devops, email, health, migration, mlops, productivity, research, security, and web-development. Each category directory contains multiple SKILL.md files following the same frontmatter format. This structure allows for organized skill discovery and categorization within the Hermes ecosystem.

## STEP 3E: optional-skills/ Directory Listing
The optional-skills directory mirrors the skills directory structure but contains skills that are not automatically loaded and must be explicitly installed. Categories include: autonomous-ai-agents, blockchain, communication, creative, devops, email, health, mcp, migration, mlops, productivity, research, security, and web-development. These skills typically have heavier dependencies or are more niche in nature, requiring explicit user installation via `hermes skills install official/<category>/<skill>`.