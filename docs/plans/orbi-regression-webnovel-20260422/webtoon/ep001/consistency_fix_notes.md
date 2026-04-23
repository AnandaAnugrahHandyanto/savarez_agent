# Character consistency fix notes

## Problem observed
- 컷마다 눈 크기, 턱선, 헤어 볼륨, 목/어깨 두께가 흔들림
- 특히 감정 컷에서 주인공이 더 어려지거나 더 미남형으로 재계산되는 경향

## Fix applied
- `character_anchor.md` 작성
- 프롬프트에 protagonist lock phrase 추가
- 금지 드리프트 명시: enlarged eyes, broad shoulders, glossy idol face, short tidy haircut
- 동일 인물성보다 감정 연출이 우선되지 않도록 “same protagonist design” 문구를 강하게 삽입

## New test asset
- prompt: `webtoon/ep001/prompts/02-p07-hero-consistency-lock.md`
- render: `renders/ep001/ep001_p07_hero_gpt_image2_consistency_lock.png`

## Next recommended hardening
1. EP 전체 패널에 동일 protagonist lock 문구 공통 삽입
2. p01/p04/p07을 캐릭터 앵커 컷으로 지정
3. 패널별 재생성 시 직전 컷이 아니라 anchor prompt를 반복 사용
4. 컷 간 복장 변화 최소화
