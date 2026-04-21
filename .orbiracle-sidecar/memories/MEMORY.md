`company-wiki` is the canonical Slack+Trello+GitHub wiki surface; `slack-org-wiki` is the live Slack source-adapter lane.
§
For Slack wiki/company-wiki work, default to the assistant's configured bot token path; treat old Slack CLI credential routes as deprecated fallback/diagnostic only.
§
오르비 웹소설 품질에서 핵심 실패 모드는 미세한 입시/학원/학교 제도 고증 오류다. 대표 예시: 11월 수시 지원, 노량진 재수, 고등학생의 재수종합학원, 말이 안 되는 수능 점수/전형 디테일. 이런 오류는 감정몰입을 깨고 AI가 쓴 느낌을 강하게 만든다.
§
오르비 웹소설 품질 기준에서 사용자는 단순 현실고증보다 연재 엔진을 중시한다. 좋은 글은 그럴듯한 단편이 아니라 20화 이상 굴러갈 반복 갈등 구조, 조연/제도 압력, 초반 후킹, 다음 화 클릭 압박을 가져야 한다.
§
사용자는 기존 오르비 웹소설 파이프라인/스킬을 아카이브하고, bellman-move/awesome-novel-studio 프라이빗 포크를 새 웹소설 베이스로 쓰길 원한다.
§
이 환경은 Ubuntu 24.04.4 LTS이며 sudo 비밀번호 없는 비승인 상태다. Obsidian 데스크톱은 FUSE/GTK 일부 시스템 라이브러리와 GUI display가 없어 AppImage 직접 실행이 안 돼서, 로컬 추출 런타임 + 사용자 홈 라이브러리 번들 + ~/.local/bin/obsidian 래퍼로 셋업해야 한다.
§
For company-wiki, default toward Obsidian as the primary query surface: Dataview-friendly frontmatter, dashboard/query notes, and a cron-backed loop that continuously refreshes connector raw data and rebuilds the canonical wiki.
§
사용자 정정: Duct Tape는 아직 API가 공개되지 않았고 공식 출시 전 단계로 취급해야 한다. 웹툰 툴체인 제안 시 즉시 사용 가능한 공개 API처럼 전제하면 안 된다.
§
사용자가 '비둘기관리자' 문체로 글을 요청하면, 오르비 운영자 캐릭터 톤(구구, 공지/이벤트형 카피, CTA 포함)을 반영해 HTML 본문 중심으로 작성한다. 직접 게시가 아니라 붙여넣기용 HTML 초안 제공이 기본이다.
§
In the user's webtoon pipeline, end-to-end outputs should be treated as valid only when produced via live FAL generation; storyboard/fallback renders should not count as completion artifacts.
§
For this user's webtoon post-processing contract, speech balloons are tail-less across lanes; regressions should be prevented by tests rather than lane-specific behavior.