# feat(patch): add mode="hashline" — content-hash-anchored line editing

## Motivation

The default `mode="replace"` patch path uses a 9-strategy fuzzy match chain.
Two failure modes are reproducible today:

1. **Stale view (most dangerous)**: when the model's `old_string` reflects an
   outdated file read, the `context_aware` fuzzy strategy can silently edit
   the **wrong** content instead of rejecting.
2. **Duplicate text**: when `old_string` matches multiple locations, the tool
   reports *"Found N matches"* and the model loops adding ever more context.

## What this PR does

Adds a third `mode` to the existing `patch` tool: `mode="hashline"`. It
addresses lines by **number** and verifies the file hasn't changed under the
model via a 4-hex **content hash** (TAG). If the TAG doesn't match, the edit
is **rejected** — never silently mis-applied.

The existing `mode="replace"` and `mode="patch"` paths are **completely
unchanged**. The default mode remains `"replace"`. All existing callers
(skill_manager, MCP transports, file_operations) are unaffected.

## Changes

| File | Change |
|------|--------|
| `tools/hashline_core.py` | **New.** Pure-algorithm module: normalize, content_tag (blake2b 4-hex), parse, preflight, apply. Zero Hermes imports. |
| `tools/file_operations.py` | `FileOperations.patch_hashline` abstract declaration + `ShellFileOperations.patch_hashline` implementation. Reuses `write_file`/`_unified_diff`/`_check_lint_delta`/`_is_write_denied`. |
| `tools/file_tools.py` | `patch_tool` signature adds `patch_text`; mode dispatch adds `"hashline"` branch; security check adds hashline path traversal guard (same `has_traversal_component` as V4A); `PATCH_SCHEMA` adds `"hashline"` enum + `patch_text` param; `_handle_patch` passes through `patch_text`. |
| `tests/tools/test_hashline_core.py` | 16 unit tests (all ops, stale rejection, atomicity, edges). |
| `tests/tools/test_patch_hashline_integration.py` | 5 integration tests (ShellFileOperations end-to-end + replace regression). |
| `tests/tools/test_hashline_llm_e2e.py` | Real-LLM (DeepSeek) end-to-end: valid patch applies, stale-anchor rejects. |
| `tests/tools/compare_fuzzy_vs_hashline.py` | Head-to-head evidence script. |

## Compatibility

- **No new tool name**: still `patch`, still in `file` toolset, no `toolsets.py` change.
- **No new dependencies**: pure stdlib (hashlib, re, dataclasses).
- **Default mode unchanged**: `"replace"` — existing agent system prompts work as-is.
- **Existing test suite**: 47/47 fuzzy_match tests pass, 0 regressions.
  (3 pre-existing macOS tmpdir/sensitive-path failures unrelated to this PR.)
- **System prompt follow-up**: adding `HASHLINE MODE` description to the system
  prompt template is a separate follow-up (not blocking).

## Attribution

The hashline concept and patch format are adapted from
[can1357/oh-my-pi](https://github.com/can1357/oh-my-pi) (MIT License).
This is an independent Python reimplementation sharing no source with the
original TypeScript.

## Test results

```
tests/tools/test_hashline_core.py       16 passed
tests/tools/test_patch_hashline_integration.py  5 passed (incl. replace regression)
tests/tools/test_hashline_llm_e2e.py     2 passed (DeepSeek real API)
tests/tools/test_fuzzy_match.py         47 passed (0 regressions)
```
