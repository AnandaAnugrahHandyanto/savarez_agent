---
sidebar_position: 17
title: "xAI Capability Matrix"
description: "What xAI/Grok capabilities Hermes Agent supports today, what is partial, and which xAI API surfaces are not exposed yet."
---

# xAI Capability Matrix

This matrix describes the current Hermes Agent surface for xAI/Grok. It is a support matrix, not a roadmap: "supported" means Hermes has a first-class provider, tool, plugin, command, or guide on `main`; "not exposed" means xAI documents the API surface, but Hermes does not yet provide a dedicated user-facing integration for it.

Last reviewed against xAI docs on May 20, 2026.

## Credential Paths

Most direct xAI surfaces in Hermes share one credential resolver:

| Credential | Hermes path | Notes |
|------------|-------------|-------|
| xAI API key | `XAI_API_KEY`, provider `xai` | Uses `https://api.x.ai/v1` by default. |
| Grok OAuth | `hermes auth add xai-oauth`, provider `xai-oauth` | Browser OAuth for SuperGrok / X Premium+ users. Hermes prefers this bearer token when it is available. |

See [xAI Grok OAuth](./xai-grok-oauth.md) for setup details.

## Supported Or Partially Supported

| Capability | xAI API surface | Hermes surface | Status | Notes |
|------------|-----------------|----------------|--------|-------|
| Chat / agent runtime | [Responses-compatible text generation](https://docs.x.ai/developers/models) | Providers `xai` and `xai-oauth` | Supported | Hermes routes xAI through the `codex_responses` transport. `grok-4.3` is pinned as the safe top model, and retired May 15, 2026 models are excluded from the curated fallback list. |
| OAuth and shared credentials | xAI account OAuth plus API keys | `xai-oauth`, shared `tools.xai_http` resolver | Supported | The same xAI bearer can cover chat, web search, X search, image generation, video generation, TTS, and STT. |
| General web search | [Responses `web_search`](https://docs.x.ai/developers/tools/web-search) | `web_search` with `web.search_backend: "xai"` or `web.backend: "xai"` | Supported, search-only | Hermes exposes xAI as an explicit web-search backend. It supports domain filters, respecting xAI's max-5 `allowed_domains` / `excluded_domains` limit, but does not expose `web_extract` or crawl through this backend. |
| X search | [Responses `x_search`](https://docs.x.ai/developers/tools/x-search) | `x_search` toolset | Supported | Read-only discovery over public X content. It supports allowed/excluded handles, date filters, and optional image/video understanding flags. |
| Image generation | [`/images/generations`](https://docs.x.ai/developers/model-capabilities/images/generation) | `image_gen.provider: xai`, `image_generate` | Supported for text-to-image | Hermes exposes `grok-imagine-image` and `grok-imagine-image-quality`, 1k / 2k output, and the common Hermes aspect-ratio set. xAI image editing and multi-image editing are not exposed by this provider. |
| Video generation | [`/videos/generations`](https://docs.x.ai/developers/model-capabilities/video/generation) | `video_gen.provider: xai`, `video_generate` | Partially supported | Hermes supports text-to-video, image-to-video, and up to 7 reference images. xAI video edit and extend endpoints are not exposed in the unified Hermes video tool. |
| Text to speech | [`/tts`](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech) | `tts.provider: xai`, `text_to_speech` | Supported | Defaults to voice `eve`, language `en`, MP3 output, and the documented 15,000-character xAI text limit. Hermes can optionally insert conservative pause speech tags. |
| Speech to text | [`/stt`](https://docs.x.ai/developers/model-capabilities/audio/speech-to-text) | `stt.provider: xai`, voice-message transcription | Supported | Uses the xAI STT endpoint with optional `language`, `format`, and `diarize` settings. Hermes resolves either Grok OAuth or `XAI_API_KEY`. |
| Model retirement guard | [May 15, 2026 retirement guide](https://docs.x.ai/developers/migration/may-15-retirement) | `hermes doctor`, `hermes migrate xai` | Supported | Hermes detects retired xAI model IDs in config and can rewrite them with `hermes migrate xai --apply`. |

:::note X Search vs xurl
`x_search` is xAI's read-only server-side search tool for public X content. The `xurl` skill is separate: it wraps the official X developer-platform CLI for authenticated X API actions such as posting, replying, liking, DMs, timelines, and account-specific lookups.
:::

## Not First-Class In Hermes Yet

These xAI surfaces are documented by xAI, but Hermes does not currently expose them as dedicated first-class xAI integrations:

| xAI surface | xAI docs | Hermes status |
|-------------|----------|---------------|
| Batch jobs | [Batch API](https://docs.x.ai/developers/advanced-api-usage/batch-api) | Not exposed as an `xai_batch` tool or job manager. Hermes chat remains interactive/synchronous from the user's point of view. |
| Deferred chat completions | [Deferred Chat Completions](https://docs.x.ai/developers/advanced-api-usage/deferred-chat-completions) | Not exposed as a submit-and-poll xAI tool. |
| Server-side code execution | [Code Execution Tool](https://docs.x.ai/developers/tools/code-execution) | Hermes has its own `code_execution` tool, but it is not xAI's server-side Responses `code_execution` / `code_interpreter` surface. |
| Collections search / RAG | [Collections Search](https://docs.x.ai/developers/tools/collections-search) | Not exposed as an xAI collections or `file_search` tool. |
| Image editing | [Image Editing](https://docs.x.ai/developers/model-capabilities/images/editing) | Not exposed by the Hermes xAI image provider, which currently implements text-to-image generation. |
| Video editing | [Video Editing](https://docs.x.ai/developers/model-capabilities/video/editing) | Not exposed by the Hermes xAI video provider. |
| Video extension | [Video Extension](https://docs.x.ai/developers/model-capabilities/video/extension) | Not exposed by the Hermes xAI video provider. |

## Maintenance Notes

- When xAI adds, retires, or renames capabilities, update this page and the focused docs test together.
- Prefer linking to this matrix when reviewing xAI PRs that add a new Hermes surface. It keeps the distinction between xAI API availability and Hermes user-facing availability explicit.
- Keep provider-agnostic Hermes tools separate from xAI-specific surfaces. For example, `web_search` can use xAI as one backend, while `x_search` is a distinct xAI/X tool.
