# Korean teen-popular webtoon style research

## Goal
실사감이 강하고 컷마다 미묘하게 다른 현재 프롬프트를, **한국 10대 대중 웹툰 문법** 쪽으로 재정렬하기 위한 스타일 리서치.

## Representative anchor titles
- `여신강림` — polished school/romance faces, clean color, idealized teen readability
- `작전명 순정` — bright emotional readability, soft blush, clean romance staging
- `청춘블라썸` — school slice-of-life/drama, clear acting, uncluttered panels
- `피라미드 게임` — school drama/thriller with restrained but neat faces
- `스터디그룹` — school action, sharper poses but simplified youth faces
- `약한영웅` — cooler palette, cleaner youth drama stylization over realism
- `외모지상주의` — highly popular youth title with polished idealized anatomy
- `풋사과 보습학원` — softer nostalgic youth style, readable and stylized
- `오늘도 사랑스럽개` — approachable mainstream romance-comedy face design

## Common style signals
### 1. Linework
- clean, controlled, medium-thin outlines
- outer silhouette slightly stronger than inner face detail
- minimal scratch texture, minimal manga hatching
- hair rendered in grouped clumps, not strand realism

### 2. Face proportions
- youthful Korean webtoon face proportions
- soft V-line or oval jaw
- small nose, small mouth
- eyes larger than realism but not giant anime eyes
- male teen lead should stay slim, refined, and readable rather than skeletal-realistic

### 3. Eye style
- almond or rounded-almond eyes
- clean upper lash emphasis
- simple readable highlight, not realistic iris fiber detail
- emotional readability > anatomical realism

### 4. Rendering / shading
- soft cel shading or semi-flat shading
- one or two major shadow groups on the face
- subtle blush / gradient on cheeks
- smooth even skin, no pores, no cinematic live-action lighting

### 5. Palette
- school/teen drama: bright clean pastel-to-mid saturation
- thriller/drama: cool grays/blues with selective accent colors
- no heavy brown cinematic realism

### 6. Backgrounds
- simplified but believable school/interior backgrounds
- selective detail, not hyper-detailed realism
- dialogue scenes prioritize silhouette readability and negative space

### 7. Vertical webtoon readability
- mid-shot / bust-shot heavy
- clear emotional acting at phone-screen size
- repeatable costume silhouette and repeatable hair shape are critical

## Prompt guidance — what to add
- "mainstream Korean school webtoon aesthetic"
- "clean Naver-style romance/drama lineart"
- "stylized Korean webtoon illustration, not photorealistic"
- "soft cel shading, polished flat colors, smooth even skin"
- "youthful male lead with soft V-line face, small nose, almond eyes"
- "simplified school interior background, mobile-readable composition"
- "repeatable character model sheet proportions across panels"

## Prompt guidance — what to suppress
- no photorealism
- no skin pores
- no cinematic live-action lighting
- no painterly rendering
- no realistic hair strands
- no harsh facial structure
- no mature prestige-drama realism
- no glossy idol face
- no oversized anime eyes

## Practical tuning takeaway
현재 결과는 "grounded realism" 쪽으로 너무 기울어 있다.
다음 버전은 **현실 고증은 유지하되 렌더링은 더 stylized mainstream Korean webtoon 쪽**으로 옮겨야 한다.
핵심은:
1. 더 깨끗한 라인아트
2. 더 단순한 얼굴 공식
3. 더 부드러운 cel shading
4. 더 억제된 배경 디테일
5. anti-photoreal negative prompt 강화
