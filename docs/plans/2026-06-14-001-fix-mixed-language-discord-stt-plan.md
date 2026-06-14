---
title: "fix: Make Discord STT robust for mixed Estonian/English voice messages"
type: fix
status: completed
date: 2026-06-14
---

# fix: Make Discord STT robust for mixed Estonian/English voice messages

## Summary

Make the inbound Discord audio transcription path preserve multilingual auto-detection end to end, with tests that protect Kadri-style mixed Estonian/English voice notes from being forced through an English-only local STT fallback.

---

## Problem Frame

Kadri Hermes already caches Discord audio attachments into local audio cache paths and `gateway/run.py` feeds those paths to `tools.transcription_tools.transcribe_audio`. A cached Kadri Discord `.ogg` transcribed successfully with the local faster-whisper provider. The remaining robustness gap is configuration and fallback behavior: Kadri's intended mixed-language posture is `stt.local.language: ""` so faster-whisper can auto-detect Estonian or English, but the local command fallback currently treats a blank language as English and the auto-detected whisper CLI template always emits `--language {language}`. If faster-whisper becomes unavailable and Hermes falls back to a local CLI, mixed-language Discord messages can silently regress to English-biased transcription.

---

## Requirements

**Mixed-language transcription**

- R1. Blank `stt.local.language` must mean language auto-detection for local STT, not English.
- R2. Explicit local language settings such as `et` or `en` must continue to force that language when configured.
- R3. Discord audio attachment handling must continue to provide local paths and `audio/*` media types so gateway STT enrichment sees the attachments.

**Fallback and compatibility**

- R4. The faster-whisper path must keep its current auto-detect behavior when language is blank.
- R5. The local command fallback must support auto-detect without forcing `--language en`, while preserving compatibility for user-provided command templates that include `{language}`.
- R6. The change must not mutate Kadri's live profile config; deployment/config changes remain an operator step after code verification.

---

## Key Technical Decisions

- KTD1. Treat blank local language as an explicit auto-detect signal: The code should distinguish “missing language” from “English default” for local STT. This matches Kadri's current config and faster-whisper's native behavior.
- KTD2. Make the auto-detected whisper CLI template omit `--language` by default: Many Whisper CLIs auto-detect when the language flag is absent. Omitting the flag is safer for mixed Estonian/English than filling `{language}` with `en`.
- KTD3. Preserve user template compatibility with a resolved language token: Custom `HERMES_LOCAL_STT_COMMAND` templates may already include `{language}`. For those, leave `{language}` available and only use the legacy English fallback when neither config nor env supplies a language.
- KTD4. Verify through focused unit tests rather than live Discord: The Discord adapter already has attachment-path behavior in code; the risk here is STT language resolution. Unit tests on `tools/transcription_tools.py` are the smallest meaningful regression gate.

---

## Implementation Units

### U1. Pin local STT language resolution semantics

- **Goal:** Add a small helper or equivalent local logic that makes blank config/env language resolve to auto-detect for native faster-whisper and for auto-detected CLI commands.
- **Requirements:** R1, R2, R4, R5.
- **Dependencies:** None.
- **Files:**
  - `tools/transcription_tools.py`
  - `tests/tools/test_transcription_tools.py`
- **Approach:** Keep faster-whisper passing no `language` kwarg when config/env language is blank. Adjust the local command fallback so the built-in whisper CLI template can omit the language flag entirely when no language is configured. Preserve explicit language behavior for `et`, `en`, or other valid language codes.
- **Patterns to follow:** Existing `_transcribe_local()` language resolution and `TestTranscribeLocalCommand` command-capture style in `tests/tools/test_transcription_tools.py`.
- **Test scenarios:**
  - Blank `stt.local.language` with faster-whisper calls model transcription without a `language` kwarg.
  - Explicit `stt.local.language: et` with faster-whisper passes `language="et"`.
  - Auto-detected local whisper CLI command with no configured language builds a command without `--language`.
  - Auto-detected local whisper CLI command with `HERMES_LOCAL_STT_LANGUAGE=et` includes `--language et`.
- **Verification:** Focused transcription tests show blank means auto-detect and explicit language still forces the requested language.

### U2. Preserve custom local command template compatibility

- **Goal:** Ensure existing `HERMES_LOCAL_STT_COMMAND` users do not break when their templates contain `{language}`.
- **Requirements:** R2, R5.
- **Dependencies:** U1.
- **Files:**
  - `tools/transcription_tools.py`
  - `tests/tools/test_transcription_tools.py`
- **Approach:** When a user-provided command template contains `{language}`, continue to substitute a concrete language token. If config/env has a non-empty language, use it; otherwise keep the previous English fallback for that compatibility path rather than failing template formatting.
- **Patterns to follow:** Existing shell/list mode split in `_transcribe_local_command()` and `TestShellSafety`.
- **Test scenarios:**
  - Existing custom template containing `{language}` still receives `en` by default when no config/env language is set.
  - Custom template receives `et` when `HERMES_LOCAL_STT_LANGUAGE=et`.
  - Invalid custom templates still report the existing placeholder error path.
- **Verification:** Local command tests pass without changing the shell-safety contract.

### U3. Confirm Discord-to-STT path remains intact

- **Goal:** Protect against accidental regression in the Discord attachment path while changing STT internals.
- **Requirements:** R3, R6.
- **Dependencies:** U1.
- **Files:**
  - `gateway/platforms/discord.py`
  - `gateway/run.py`
  - `tests/gateway/test_discord_document_handling.py` or a focused Discord attachment test if existing coverage lacks audio-path assertions.
- **Approach:** Prefer inspection and existing tests if audio attachment coverage already proves cached path + `audio/*` media types. Add only a narrow regression test if there is no coverage for Discord audio attachments entering `event.media_urls`/`media_types`.
- **Patterns to follow:** Existing Discord document and image attachment tests that construct fake attachments and call adapter message processing helpers.
- **Test scenarios:**
  - Discord audio attachment with `content_type="audio/ogg"` is cached to a local audio path and marked as `audio/ogg`.
  - A no-text Discord audio message remains eligible for gateway transcription rather than being treated as a plain document.
- **Verification:** Existing or added gateway tests show audio attachments still flow into STT enrichment.

---

## Scope Boundaries

- Do not edit or deploy Kadri's live profile config in this code change.
- Do not change provider selection priority, cloud STT providers, or Discord voice-channel live audio behavior.
- Do not add a translation layer; this work is transcription language detection, not cross-language response policy.

---

## Risks & Dependencies

- The local whisper CLI's exact option behavior varies by implementation. The safe default is to omit `--language` for auto-detect, but tests should validate command construction rather than invoking a real CLI.
- Existing users with custom templates may rely on `{language}` always being non-empty; keeping a compatibility fallback avoids breaking them.
- Mixed-language accuracy still depends on model size and audio quality. Code can preserve auto-detect, but Kadri's profile should still use a model such as `small` for better Estonian/English accuracy once code is verified.

---

## Documentation / Operational Notes

After code verification, Kadri's runtime profile can be checked separately for:

- `stt.enabled: true`
- `stt.provider: local`
- `stt.local.model: small`
- `stt.local.language: ""`

That runtime check is intentionally outside this repo mutation unless the operator explicitly asks to deploy config.

---

## Sources / Research

- `gateway/platforms/discord.py` caches inbound `audio/*` Discord attachments with `cache_audio_from_bytes` / URL fallback and records local paths in `media_urls`.
- `gateway/run.py` collects `audio_paths` from `audio/*` media and calls `tools.transcription_tools.transcribe_audio` during message enrichment.
- `tools/transcription_tools.py` already lets faster-whisper auto-detect when `stt.local.language` is blank; the local command fallback is the weaker path because it defaults blank language to English.
- `tests/tools/test_transcription_tools.py` contains existing provider selection, local command, shell-safety, and faster-whisper regression coverage to extend.
