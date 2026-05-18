---
name: korean-writing-editor
description: "Use when editing Korean writing to remove translationese and AI-like phrasing while preserving author voice, clarity, and natural Korean style."
version: 1.3.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [korean, writing, editing, proofreading, translationese, ai-tone, clarity]
    category: creative
    related_skills: [humanizer]
---

# Korean Writing Editor

Use this skill when the user asks to review, polish, rewrite, or edit Korean writing, especially blogs, essays, newsletters, technical writing, documentation, announcements, and Korean prose that sounds translated, stiff, abstract, verbose, or AI-generated.

This skill is **not** for LaTeX/PDF-rendering checks. Use a separate LaTeX-focused workflow for that.

Core rule:

> 좋은 한국어 글 수정은 더 그럴듯하게 꾸미는 일이 아니다. 원래 의도와 목소리를 보존하면서 번역투, AI 말투, 과장, 어색한 조사, 긴 문장, 불필요한 추상성을 줄이는 일이다.

## Default stance

1. Preserve the author's intent, rhythm, and stance.
2. Make the writing clear first, stylish second.
3. Prefer short, direct sentences.
4. Prefer concrete verbs over nominalized nouns.
5. Prefer easy words unless technical precision requires otherwise.
6. Do not rewrite more than necessary unless asked.
7. If the user asks for suggestions, do not edit files yet.
8. Put the key point first and structure the answer.
9. Unless requested otherwise, keep Korean endings consistent, preferably `~했습니다` / `~입니다`.
10. Do not remove every translationese-looking expression. Remove it only when it hurts clarity, rhythm, or naturalness.

## Editing pass order

1. Split long sentences.
2. Bring subject and predicate closer.
3. Move modifiers next to what they modify.
4. Replace noun-heavy phrases with verbs.
5. Restore actors hidden by passive or abstract expressions.
6. Remove harmful translationese patterns.
7. Remove AI-like signposting and empty evaluation.
8. Simplify difficult Sino-Korean words.
9. Check particles.
10. Read aloud once and remove remaining stiffness.

## What to detect

### Translationese

Look for:
- abstract noun chains
- noun-heavy predicates
- unnatural collocations
- distant subject/predicate pairs
- modifiers far from targets
- English-paper or product-copy phrasing
- sentences that must be decoded rather than read

Do not remove translationese mechanically. Ask:
1. Is it already naturalized in Korean?
2. Does it make the sentence longer?
3. Does it hide the actor or action?
4. Does it make the meaning abstract?
5. Can simpler Korean preserve the meaning?

### Korean AI tone

Look for prose that is too smooth, balanced, generic, or assistant-like.

Common signs:
- `핵심은 다음과 같습니다`, `이제부터 살펴보겠습니다`
- `매우 중요합니다`, `의미 있는 결과입니다`, `주목할 만합니다`
- `~라고 볼 수 있습니다`, `~라고 할 수 있습니다`, `~하는 것입니다`
- `A뿐만 아니라 B도`, `단순히 A가 아니라 B입니다`
- `결론적으로`, `앞으로의 가능성이 기대됩니다`
- `도움이 되었기를 바랍니다`, `궁금한 점이 있으면 알려주세요`

Fix: say the point directly. If an evaluation remains, explain why it matters.

### Korean-specific awkwardness

Check:
- particles: `은/는`, `이/가`, `을/를`, `와/과`, `로/으로`
- missing particles that make the sentence memo-like
- noun-verb mismatch: `문제를 수행하다`, `결과를 발생하다`
- redundant expressions: `가장 최선`, `미리 예측`, `서로 상호`, `현재 진행 중`
- double passive: `해결되어졌다`, `보여진다`, `사용되어진다`
- stiff endings: `~라 할 수 있다`, `~라고 볼 수 있다`
- overuse of `것`: `~하는 것이다`, `~라는 것이다`, `~일 것이다`

## Pattern dictionary

Apply these only when they improve the sentence.

- `~의 경우` -> `~은/는`
  - `저의 경우에는` -> `저는`
  - `이 제품의 경우` -> `이 제품은`

- `~에 대해`, `~에 대하여`, `~에 관하여` -> direct connection
  - `문제에 대해 답하다` -> `문제에 답하다`
  - `성능에 대한 분석` -> `성능 분석`

- `~을 통해` -> context-specific verb/relation
  - `실험을 통해 확인했다` -> `실험으로 확인했다`
  - `대화를 통해 알게 됐다` -> `대화하면서 알게 됐다`
  - `자료를 통해 알 수 있다` -> `자료를 보면 알 수 있다`

- `~에 있어서`, `~함에 있어서` -> delete or simplify
  - `개발에 있어서 중요한 점` -> `개발에서 중요한 점`
  - `사용함에 있어서` -> `사용하는 데`

- `~로부터` -> `~에서`, `~에게`, `~와/과`
  - `회사로부터 연락을 받았다` -> `회사에서 연락을 받았다`
  - `친구로부터 들었다` -> `친구에게 들었다`

- `~하기 위해`, `~을 위하여` -> `~하려고`, `~하려면`, direct modifier
  - `문제를 해결하기 위해` -> `문제를 해결하려고`
  - `성공하기 위해서는` -> `성공하려면`

- `가지다`, `가지고 있다` -> `있다`, `이다`, specific verb
  - `의미를 가지고 있다` -> `의미다`
  - `목소리를 가지고 있다` -> `목소리가 아름답다`

- `~하는 중이다` -> present tense or simpler progressive
  - `검토하는 중입니다` -> `검토합니다` / `검토하고 있습니다`
  - `업무를 담당하는 중입니다` -> `업무를 담당합니다`

- unnecessary `들`
  - `많은 문제들이 있다` -> `많은 문제가 있다`
  - `여러 가능성들이 있다` -> `여러 가능성이 있다`

- `~하지 않으면 안 된다` -> direct obligation
  - `확인하지 않으면 안 됩니다` -> `확인해야 합니다`

- `~에 의해`, `~에 의하여`, `~로 인하여` -> active voice or simpler cause/means
  - `경찰에 의해 진압되었다` -> `경찰이 진압했다`
  - `오류로 인하여 실패했다` -> `오류 때문에 실패했다`

## English transfer check

When prose feels translated, check whether an English structure is hiding behind it.

- about -> `~에 대해`, `~에 관하여`: shorten or connect directly.
- through -> `~을 통해`: replace with `사용해`, `거쳐`, `바탕으로`, `하면서`, `덕분에`, or a direct verb.
- by -> `~에 의해`, `~에 의하여`: prefer active voice or `~로`.
- from -> `~로부터`: prefer `~에서`, `~에게`, `~와/과`.
- for -> `~을 위해`, `~하기 위해`: prefer `~하려고`, `~하려면`, or direct modifier.
- in -> `~에 있어서`, `~에서`: delete when unnecessary or use `~에서`.
- of -> `~의`: delete when the noun phrase remains clear.

## Sentence and word rules

1. One sentence, one thought. Split sentences over 2–3 lines.
2. Keep subject and predicate close.
3. Put modifiers right before what they modify.
4. One paragraph, one topic.
5. Prefer easy words:
   - `상기하다` -> `떠올리다`
   - `도출하다` -> `끌어내다`
   - `개진하다` -> `말하다`
   - `유관하다` -> `관련 있다`
   - `수행하다` -> `하다`
   - `활용하다` -> `쓰다` / `사용하다`
   - `용이한` -> `쉬운`
6. Turn nominalizations into verbs:
   - `~의 개선을 수행하다` -> `~을 개선하다`
   - `~에 대한 검토를 진행하다` -> `~을 검토하다`
   - `~의 적용이 가능하다` -> `~을 적용할 수 있다`
7. Prefer active voice when the actor is clear:
   - `문제가 해결되었습니다` -> `팀이 문제를 해결했습니다`
   - `개선이 이루어졌습니다` -> `성능을 개선했습니다`
8. Reduce `-것입니다`:
   - `중요한 것은 꾸준히 하는 것입니다` -> `꾸준히 하는 게 중요합니다`
9. Remove duplicate meanings:
   - `가장 최선` -> `최선`
   - `미리 예측` -> `예측`
   - `서로 상호` -> `서로` / `상호`
   - `현재 진행 중` -> `진행 중`

## Technical term rule

Do not simplify technical terms if precision would be lost.

Instead:
1. Keep the technical term.
2. Explain it briefly at first use if readers may not know it.
3. Simplify the surrounding Korean sentence.
4. Keep the same Korean/English form consistently.

For technical or academic Korean manuscripts, especially when the user says technical terms should remain English:
- Leave terms such as `AUROC`, `Semantic Entropy`, `corpus support`, `entity co-occurrence`, `n-gram`, `fusion`, and model/dataset names in English.
- Fix only the Korean around them: particles, modifier order, sentence length, nominalization, and awkward connective structure.
- Do not translate technical terms just to make the paragraph look more Korean.
- Do not change claim strength, numbers, citations, labels, formulas, macros, or experimental interpretation while polishing Korean.

## Output formats

### Suggestions only

```markdown
## 핵심 요약
- ...

## 문장별/문단별 제안
1. 위치: ...
   - 원문: "..."
   - 문제: ...
   - 제안: "..."

## 우선 고치면 좋은 것
1. ...
2. ...

## 한 문장 정리
...
```

### After editing

```markdown
수정 완료했습니다.

## 핵심 요약
- ...

## 수정 파일
- ...

## 바꾼 점
1. 조사/띄어쓰기
2. 번역투 완화
3. 긴 문장 분리
4. 기술 용어 주변 한국어 정리

## 검증
- ...

## 확인할 점
- ...
```

When reporting edits to technical or thesis writing, give representative before/after examples for substantive Korean improvements. Avoid presenting routine style cleanup as a vague “한국어 말투 수정”; instead name the concrete categories such as particles, long sentence splitting, nominalization, or translationese.

## Pitfalls

- Do not over-polish.
- Do not replace the author's voice with a generic assistant voice.
- Do not add grand conclusions that were not in the original.
- Do not use difficult words to sound professional.
- Do not remove all translationese mechanically.
- Do not change technical meaning while simplifying wording.
- Do not edit files when the user only asked for feedback.
- Do not give vague praise. Give concrete examples and alternatives.

## Final check

Before finalizing:
- Key point first?
- Sentences short?
- Subject and predicate close?
- Harmful translationese and AI tone removed?
- Useful naturalized expressions preserved?
- Author meaning and voice preserved?
- Endings consistent unless asked otherwise?
- Technical meaning unchanged?
- Correct mode: suggestions only vs actual edit?

