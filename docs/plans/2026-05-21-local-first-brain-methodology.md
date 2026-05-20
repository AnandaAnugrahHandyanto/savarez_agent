# Local-First Brain + Methodology Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a practical local-first development methodology layer and a user-installed Graphiti memory provider for Hermes.

**Architecture:** Keep upstream-safe methodology assets in the Hermes repo as built-in skills. Keep Graphiti as a user-installed memory provider under `$HERMES_HOME/plugins/graphiti` because `CONTRIBUTING.md` says new memory backends must not be added under `plugins/memory/` in-tree. Use local Ollama embeddings (`qwen3-embedding:4b`) and local Kuzu graph storage; use OpenRouter only for LLM extraction.

**Tech Stack:** Hermes SKILL.md, MemoryProvider plugin API, Graphiti Core, Kuzu, Ollama embeddings, OpenRouter-compatible chat completions.

---

### Task 1: Add methodology router skill

**Objective:** Add a built-in Hermes skill that chooses the right workflow size: quick edit, bugfix, spec-driven feature, product/SDLC mode, or brain-memory work.

**Files:**
- Create: `skills/software-development/methodology-router/SKILL.md`

**Verification:** Validate SKILL.md frontmatter and ensure it references existing peer skills.

### Task 2: Add spec-driven development skill

**Objective:** Add a Spec Kit-inspired skill that defines Hermes artifact flow from constitution/spec/plan/tasks/implementation.

**Files:**
- Create: `skills/software-development/spec-driven-development/SKILL.md`

**Verification:** Validate frontmatter and artifact paths.

### Task 3: Add brain protocol skill

**Objective:** Add a skill describing how Hermes should treat durable memory layers: working, episodic, semantic, procedural, knowledge, reflective.

**Files:**
- Create: `skills/software-development/agent-brain-protocol/SKILL.md`

**Verification:** Validate frontmatter and integration notes for Graphiti, Mem0, Cognee/LightRAG, and Obsidian mirror.

### Task 4: Create user-installed Graphiti memory provider

**Objective:** Create a local plugin in `$HERMES_HOME/plugins/graphiti` that Hermes can load via `memory.provider: graphiti`.

**Files:**
- Create: `/home/kairo/.hermes/plugins/graphiti/__init__.py`
- Create: `/home/kairo/.hermes/plugins/graphiti/plugin.yaml`
- Create: `/home/kairo/.hermes/plugins/graphiti/README.md`
- Create: `/home/kairo/.hermes/plugins/graphiti/requirements.txt`

**Verification:** Import via `plugins.memory.load_memory_provider("graphiti")`, assert `is_available()` with local config/deps, and check tool schemas.

### Task 5: Configure local-first defaults

**Objective:** Set up non-secret Graphiti config with Kuzu local graph path, Ollama embedding model, OpenRouter base URL/model, and no key disclosure.

**Files:**
- Create/update: `/home/kairo/.hermes/graphiti.json`
- Update Hermes config: `memory.provider=graphiti`

**Verification:** `ollama ps` shows GPU use for `qwen3-embedding:4b`; provider loads without reading or printing OpenRouter secret.

### Task 6: Validate repo changes and commit

**Objective:** Run targeted validation, commit repo skill additions, push branch, open PR.

**Commands:**
- `venv/bin/python -m pytest tests/agent/test_memory_provider.py -q`
- SKILL.md validation script
- `git status --short`
- `git add ... && git commit -m "feat: add local-first brain methodology skills"`
- `git push -u origin HEAD`
- `gh pr create ...`
