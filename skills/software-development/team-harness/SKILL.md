# Team Agent Harness Skill

이 스킬은 Hermes 에이전트가 코드를 작성하거나 툴을 사용할 때, 미리 정의된 엄격한 룰과 테스트(Quality Gate)를 통과하도록 강제하는 **품질/안전 관리자** 모듈입니다.

## 기능 (Features)
- **명령어 안전 검증:** 예기치 않은 파괴적인 터미널 명령어 실행을 가로채어 제어합니다.
- **물리적 테스트 강제:** 코딩이 끝나면 `verification_command` 를 실행하여 실제 TDD 커버리지를 만족하는지 확인합니다.
- **Staged Delegate 자동 개입:** 작업량이 방대할 경우(Enforcement Engine) 일반 에이전트가 아닌 `staged_delegate_tool`로 자동 위임을 안내(안전 모드)하거나 강제(엄격 모드)합니다.

## 독립 모듈화 (Plug-and-Play)
이 모듈은 Hermes의 공식 `tools/` 패키지에 의존하지 않고 독립적으로 동작합니다. 
`staged_delegate_tool.py` 파일은 이 스킬 폴더(`skills/software-development/team-harness/scripts`)가 존재할 경우에만 동적으로 로드하여 파이프라인에 결합합니다.
