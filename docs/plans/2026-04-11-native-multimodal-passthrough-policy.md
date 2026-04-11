# Native Multimodal Passthrough Policy

Date: 2026-04-11

## Goal

Introduce a professional, future-proof multimodal policy layer in Hermes so omni-capable models can receive native media inputs when the runtime safely supports them, while Hermes still has explicit fallback behavior when it does not.

The first implementation slice is image input only.

## Why this plan exists

We do not want another muddled “image passthrough” patch that quietly mixes together:
- Telegram/gateway image enrichment
- API server uploaded-file behavior
- Anthropic fallback quirks
- documentation that overclaims native multimodal support
- unrelated fast-mode or provider-routing churn

This plan resets the work on a clean `main` and keeps the change surgical.

## Source of truth

For this work, the source of truth is:
1. this plan document for scope and naming
2. code behavior in `main`
3. website docs for user-facing behavior
4. concise GitHub issue + PR descriptions derived from this plan

Do not let issue text or stale PR history become the source of truth.

## Terms to use

Use this terminology consistently in code comments, docs, issue text, and PR text:
- omni model
- native multimodal passthrough
- fallback preprocessing
- per-modality policy
- omni runtime support

Avoid image-specific naming like `gateway_mode` in the new design.

## Policy names

Use these mode names:
- `fallback`
  - always preprocess before handing off to the main model
- `auto`
  - use native passthrough when the active runtime is known to support the modality; otherwise fallback
- `strict`
  - require native passthrough; fail clearly if runtime support is unknown or unsupported

## Scope for the first PR

In scope:
- native image passthrough for gateway inputs
- native image passthrough for API server uploaded-image/file inputs where safe
- transcript-safe shadow persistence for multimodal inputs
- conditional Anthropic downgrade only when native image passthrough is not safe
- documentation correction so claimed behavior matches real behavior

Out of scope:
- native audio passthrough
- native video passthrough
- generic document/PDF multimodal redesign
- fast mode / service tier work
- broad CLI multimodal redesign unless required for correctness of docs or shared helpers

## Design principles

1. Keep the default conservative.
2. Do not silently degrade in `strict` mode.
3. Keep persistence text-only unless there is an explicit storage redesign.
4. Reuse shared helpers instead of open-coding modality handling in multiple places.
5. Do not hardcode a giant provider:model allowlist in gateway code.
6. Keep issue and PR copy short and blunt.

## Proposed config shape

Add a new top-level config section:

```yaml
multimodal:
  image_input_policy: fallback   # fallback | auto | strict
```

Rationale:
- this avoids burying multimodal behavior under `auxiliary.vision`
- it is future-proof for later `audio_input_policy`, `video_input_policy`, etc.
- it keeps the first PR surgical because only one key is implemented

Default for upstream should be `fallback`.

Do not flip the default to `auto` in this first PR.

## Current code surfaces that matter

### Gateway image ingestion
- `gateway/run.py`
  - currently collects image paths and unconditionally calls `_enrich_message_with_vision()`
  - this is the main legacy image-to-description path

### Gateway audio ingestion
- `gateway/run.py`
  - currently uses `_enrich_message_with_transcription()`
  - this remains untouched in the first PR

### API server uploaded files
- `gateway/platforms/api_server.py`
  - `_normalize_message_content()` currently inlines small images as `image_url`
  - larger images become a text note via `_file_note()`
  - `MAX_INLINE_IMAGE_ATTACHMENT_BYTES = 2_000_000` is the current threshold

### Agent runtime multimodal handling
- `run_agent.py`
  - must preserve structured multimodal content through provider preflight
  - must only downgrade image blocks to text when the active runtime actually needs fallback

### Anthropic compatibility path
- `run_agent.py`
- `agent/anthropic_adapter.py`
  - native image support exists at the adapter layer
  - fallback behavior should be conditional, not unconditional

### Config defaults and docs
- `hermes_cli/config.py`
- `website/docs/user-guide/configuration.md`
- `website/docs/user-guide/features/vision.md`
- `website/docs/user-guide/features/api-server.md`

## File plan

### 1. New shared helper
Create:
- `agent/multimodal.py`

Responsibilities:
- central `image_input_policy` parsing
- helper(s) to decide whether native image passthrough is safe for the active runtime
- helper(s) to build provider-facing image parts from local files / URLs / uploaded assets
- helper(s) to create transcript-safe shadow text for persisted message history

Why:
- keeps gateway, API server, and runtime logic aligned
- prevents a second round of duplicated “can this runtime take images?” logic

### 2. Config
Modify:
- `hermes_cli/config.py`

Changes:
- add `multimodal.image_input_policy`
- default it to `fallback`
- include comments that explicitly describe `fallback | auto | strict`
- bump config version only if required by the repo’s migration rules

### 3. Gateway runtime path
Modify:
- `gateway/run.py`

Changes:
- replace unconditional `_enrich_message_with_vision()` usage with mode-aware logic
- in `fallback`, keep current behavior
- in `auto`, pass native image parts when safe; otherwise call `_enrich_message_with_vision()`
- in `strict`, fail clearly rather than silently enriching
- preserve text-only `persist_user_message` / transcript-friendly shadow content

Important:
- do not touch audio behavior in this PR
- do not mix in fast mode or unrelated gateway config changes

### 4. API server path
Modify:
- `gateway/platforms/api_server.py`

Changes:
- route uploaded image/file inputs through the same image policy semantics
- avoid the current “small images native, large images text note” split as the only decision rule
- keep size limits, but make policy and failure behavior explicit
- make large-image behavior consistent with `fallback | auto | strict`
- preserve persisted message content in a storage-safe form

Important:
- the API server must not advertise capabilities the runtime path cannot actually honor
- file upload docs must match the real behavior after the change

### 5. Agent runtime preflight
Modify:
- `run_agent.py`

Changes:
- preserve structured image parts through the live API path
- keep shadow text separate from provider-facing content
- downgrade Anthropics image blocks only when required by runtime capability checks
- ensure previews/logging do not explode on list-based content

### 6. Anthropic runtime compatibility
Modify only if necessary:
- `agent/anthropic_adapter.py`
- possibly `agent/auxiliary_client.py`

Changes:
- only if the shared helper needs a small adapter-level hook or capability bridge
- avoid broad refactors here

### 7. Documentation
Modify:
- `website/docs/user-guide/configuration.md`
- `website/docs/user-guide/features/vision.md`
- `website/docs/user-guide/features/api-server.md`
- optionally `website/docs/developer-guide/provider-runtime.md` if the runtime decision rules need developer-facing explanation

Documentation goals:
- stop overclaiming native multimodal support where the code still falls back
- document the new `multimodal.image_input_policy`
- explain `fallback | auto | strict` clearly
- make explicit that audio/video remain follow-up work

## Impact assessment

### Expected user-facing impact
Positive:
- clearer behavior for image inputs
- fewer surprising auxiliary-vision hops in supported runtimes
- better alignment between omni-capable model expectations and Hermes runtime behavior
- better docs

Risk:
- runtime capability detection mistakes could cause false passthrough or false fallback
- large-image handling in API server could regress if not tested carefully
- provider-specific paths could break if structured content is mutated incorrectly

### Backward compatibility
- default `fallback` preserves current behavior for existing users
- `auto` and `strict` are opt-in behavior changes
- transcript/session persistence remains text-only

### Styling / professionalism guardrails
- follow existing Hermes naming and config comment style
- keep user-facing descriptions concise
- do not add speculative config for audio/video yet
- no emoji-heavy docs or noisy PR prose
- no dead compatibility aliases unless absolutely necessary

## Test plan

### New tests to add
Create:
- `tests/gateway/test_gateway_multimodal_passthrough.py`

Cover:
- `fallback` keeps current enrichment path
- `auto` uses native passthrough when runtime supports images
- `auto` falls back when runtime support is unknown/unsupported
- `strict` raises a clear error instead of silently enriching
- persisted shadow message remains text-only

### Existing tests to extend
Modify:
- `tests/gateway/test_api_server.py`
  - uploaded image handling under `fallback | auto | strict`
  - large uploaded image behavior
- `tests/run_agent/test_run_agent.py`
  - structured image content survives provider preflight
  - persist-user shadow behavior remains stable
  - Anthropic fallback is conditional
- `tests/agent/test_anthropic_adapter.py`
  - only if adapter expectations need explicit multimodal coverage
- `tests/agent/test_auxiliary_config_bridge.py`
  - config shape / bridge assertions if needed

### Test commands
Run at minimum:

```bash
source venv/bin/activate
python -m pytest \
  tests/gateway/test_gateway_multimodal_passthrough.py \
  tests/gateway/test_api_server.py \
  tests/run_agent/test_run_agent.py \
  tests/agent/test_anthropic_adapter.py \
  tests/agent/test_auxiliary_config_bridge.py -q
```

Then run a focused secondary pass around existing provider/runtime behavior:

```bash
source venv/bin/activate
python -m pytest \
  tests/run_agent/test_provider_parity.py \
  tests/gateway/test_fast_command.py \
  tests/gateway/test_agent_cache.py -q
```

Finally, if the change lands cleanly, run the full suite before PR finalization.

## Implementation sequence

1. Create the plan and keep it as the source of truth.
2. Create a fresh branch from `main`.
3. Add `agent/multimodal.py` and config wiring.
4. Make gateway image handling mode-aware.
5. Make API server uploaded-image handling follow the same policy.
6. Tighten `run_agent.py` runtime preservation and conditional fallback.
7. Update docs so behavior claims match reality.
8. Run targeted tests.
9. Only then open a new issue and PR.

## Branch and PR strategy

Start from:
- `main` only

Suggested branch name:
- `feat/native-multimodal-image-policy`

Suggested issue title:
- `[Feature]: Native multimodal passthrough with per-modality fallback policy (image slice)`

Suggested PR title:
- `feat(multimodal): add native image passthrough policy for gateway and API server`

## Commit strategy

Prefer small commits:
1. `docs: add native multimodal passthrough plan`
2. `feat(config): add multimodal image input policy`
3. `feat(gateway): make image handling policy-aware`
4. `feat(api-server): apply image input policy to uploaded images`
5. `fix(agent): preserve native image parts and conditional anthropic fallback`
6. `docs: align multimodal docs with runtime behavior`
7. `test(multimodal): add gateway and runtime passthrough coverage`

## Explicit non-bullshit note

This first PR does not make Hermes fully omni.

It creates the right language and policy model, then implements the first clean slice for images. Audio, video, and broader document/file multimodal behavior should follow as separate work once this foundation is stable.
