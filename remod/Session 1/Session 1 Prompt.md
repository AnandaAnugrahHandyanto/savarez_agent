This is a reading-only session. Do not modify any files.

You are working on a fork of NousResearch/hermes-agent that we
are customizing into "Jade" — the executive orchestrator of a
multi-agent system called Oracule Zero.

Read the following files in this exact order. After reading each
one, give me a 3-sentence summary of what you learned from it
before moving to the next.

STEP 1 — Read the contributor guide:
File: AGENTS.md
Tell me:
(a) The exact list of files we must NEVER modify
(b) How the plugin system works in one paragraph
(c) The directory structure of plugins/

STEP 2 — Read the plugin architecture:
File: plugins/jade-identity/ (does not exist yet — skip)
Instead read two existing plugins. Find them yourself by
listing plugins/ and picking two that seem simple.
Tell me:
(a) The exact file structure of each plugin
(b) What **init**.py contains
(c) What the main plugin.py structure looks like
(d) How a plugin registers itself (what hook/method it uses)

STEP 3 — Read the skill system:
File: skills/ directory — list all files
File: Read the first 3 skill files you find
File: optional-skills/ directory — list all files
Tell me:
(a) The exact frontmatter format of a skill file
(b) How skills are loaded (is there a loader file?)
(c) The difference between skills/ and optional-skills/

STEP 4 — Read the config system:
File: Look for config.yaml or config_schema.yaml or similar
File: Look in hermes_cli/ for config loading code
Tell me:
(a) Every config key that exists with its default value
(b) How config.yaml is loaded at startup
(c) Where the config file lives on disk (~/.hermes/ or in repo?)

STEP 5 — Read the TUI:
File: ui-tui/src/entry.tsx (or the main entry point)
File: ui-tui/src/app.tsx
Tell me:
(a) Where the title/header text lives (exact file + line)
(b) Where the startup banner is rendered
(c) What components exist in ui-tui/src/app/components/

STEP 6 — Find all branding strings:
Search the entire repository for these exact strings and list
every file + approximate line number where each appears:

- "Hermes Agent"
- "Hermes"
- "NousResearch"
- "Nous Research"
- "nous"
  Tell me: which of these are in user-visible strings vs
  import paths vs package internals

STEP 7 — Read the gateway/messaging system:
File: gateway/run.py (read first 100 lines only — do not read
the core functions, just understand the structure)
File: Look in plugins/platforms/ or similar for Discord adapter
Tell me:
(a) How Discord is configured (what config keys?)
(b) Where platform adapters live
(c) The config keys for enabling Discord gateway

STEP 8 — Final summary:
After all reading, give me:

1. The complete plugin file structure I must follow
2. The complete skill frontmatter format I must follow
3. The exact files I must never touch
4. The 10 most important things I learned about this codebase
   that will affect how we customize it

Do not guess. If a file doesn't exist where you expect it,
say so and look for it in a logical alternative location.
