# Hermes Caption Plugin — Plan v8 (Language Generalization)

**Hackathon**: Hermes Agent Creative Hackathon  
**Previous plans**: v1–v7 executed (see PLAN_v1.md … PLAN_v7.md)

---

## Goal

Remove the Vietnamese-specific hardcoding and make the plugin work with any
target language. The pipeline architecture stays identical — the change is
primarily string parameterization plus a Whisper-based auto-detection default.

---

## Design Decisions

### Language detection strategy

Whisper already runs with `language=None` (auto-detect) and emits a detected
language code per segment. We can infer the target language without requiring
the user to specify it:

> **Auto-detect rule**: `target_lang = most-frequent non-English language
> detected across all segments`

This covers the dominant use case (bilingual teaching video with English as
the known language) without any round-trip. When the auto-detect result is
ambiguous or wrong, the user can override via:

- **Telegram**: natural language, e.g. "caption this video, target language is Korean"
- **Dashboard**: language selector in the upload modal (defaults to auto-detected value)

Edge cases we explicitly defer (not in scope for v8):
- Non-English as the "known" language (e.g., Vietnamese learning Korean)
- 3+ language videos
- User's native language is not English

### Two entry points

| Entry point | Language selection | Notes |
|---|---|---|
| Telegram | Auto-detect (Whisper) + optional override in message | No usability hit for happy path |
| Dashboard | Auto-detect default + dropdown override in upload modal | Low-friction, power-user friendly |

---

## Changes

### 1. `pipeline.py` — introduce `target_lang` parameter

**`run_pipeline()`** gains a `target_lang: str = "auto"` parameter.

**Auto-detection** added after transcription:
```python
def _detect_target_lang(segments: list[dict]) -> str:
    """Return most-frequent non-English language code from Whisper segments."""
    from collections import Counter
    counts = Counter(s["lang"] for s in segments if s.get("lang") and s["lang"] != "en")
    return counts.most_common(1)[0][0] if counts else "vi"  # fallback: vi
```

**`_phonetics_prompt()`** parameterized — replace hardcoded "Vietnamese" with
`target_lang_name` (derived from a `LANG_NAMES` dict mapping code → display name).

**ASS logic** — replace `if lang == "vi"` with `if lang == target_lang`.

**Tool schema** — replace "Vietnamese language teaching" with
"bilingual language teaching" in description.

**`_handle_caption()`** — read `target_lang` from args, pass through pipeline.

### 2. `plugin_api.py` — parameterize system prompts + job model

**`CaptionJob`** model gains `target_lang: str = "vi"` field (backwards-compatible
default preserves existing jobs).

**`_NL_SYSTEM_PROMPT`**, **`_QA_SYSTEM_PROMPT`**, **`_STYLE_GENERATE_SYSTEM_PROMPT`** — 
convert to format-string templates parameterized on `target_lang_name`.

**`/upload` endpoint** — accept optional `target_lang` form field (default `"auto"`),
resolve via `_detect_target_lang()` after transcription, store on job.

**`/health` endpoint** — include `target_lang_detection: "whisper"` in response.

### 3. `dashboard/src/index.tsx` — language selector in upload modal

- Widen `lang` type from `"en" | "vi" | ""` to `string`.
- Add `SUPPORTED_LANGS` constant:
  ```ts
  const SUPPORTED_LANGS = [
    { code: "auto", label: "Auto-detect" },
    { code: "vi",   label: "Vietnamese" },
    { code: "ko",   label: "Korean" },
    { code: "ja",   label: "Japanese" },
    { code: "zh",   label: "Chinese (Mandarin)" },
    { code: "ar",   label: "Arabic" },
    { code: "fr",   label: "French" },
    { code: "es",   label: "Spanish" },
    { code: "de",   label: "German" },
  ];
  ```
- Upload modal: add `<select>` for target language (default `"auto"`), submit
  alongside file.
- Editor view: show resolved target language as a read-only badge next to job
  title (e.g., `🌐 Vietnamese`).
- `SegmentRow` badge: replace hardcoded `"vi"` color with `isTarget ? targetColor : "en-color"`.

### 4. Rebuild frontend

```bash
cd plugins/phonetic-captions/dashboard && npm run build
```

---

## What does NOT change

- Pipeline architecture (transcribe → classify → ASS → FFmpeg)
- Job storage format (only adds `target_lang` field)
- Gateway video path injection
- Whisper model or transcription logic
- Caption style config
- Plugin registration / `plugin.yaml`

---

## Fallback safety

If `_detect_target_lang()` finds no non-English segments (e.g. English-only
video), it returns `"vi"` as a safe default and logs a warning. The user can
always override via the dashboard language selector before triggering re-burn.

---

## Non-goals (explicitly out of scope for v8)

- Supporting multiple simultaneous target languages per video
- Non-English as the "primary" language
- Changing the phonetics guide language (always English for now)
- User-defined language lists or custom language codes
