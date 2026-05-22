# SIMPLICIO_PROMPT Vendored Snapshot

The plugin ships a local copy of the SIMPLICIO_PROMPT runtime so Hermes can
inject and execute the policy without fetching or reading an external GitHub
repository at runtime.

- Local root: `plugins/simplicio_prompt/vendor/simplicio_prompt/`
- Source project: `simplicio-prompt`
- Source commit: `917fb15bf3b918fa43836623f611bc846a4eeb21`
- Hermes-local changes: the prompt source-of-truth line points at the bundled
  local path, and vendored Python files are formatted with the repository's
  Python formatter.
- Vendored files: 33 tracked files, including the prompt, spec, reference
  kernel, guardrails, examples, benchmarks, reports, and visual assets.

The vendored prompt file is adapted for Hermes so its source-of-truth
instruction points at the bundled local path before the context is injected
through `pre_llm_call`.
