---
type: session-handover
canonical: true
project: hermes-agent
session_end: 2026-06-13 07:53
git_branch: feat/wave-role-board
git_commit: 27b259f84
---

# Session Handover — hermes-agent (2026-06-13 07:53)

## 1. 현재 상태 (다음 세션 시작점)

Wave Terminal 로컬 병행 작업대 모델을 `hermes-hugo` / `hermes-clara`로 단순화하는 작업을 진행했다. 현재 repo `/Users/392yes/.hermes/hermes-agent` 브랜치 `feat/wave-role-board`에는 미커밋 변경이 남아 있다. 핵심 구현은 완료되어 테스트 29개가 통과했지만, 이미 떠 있는 Hermes/Wave pane은 plugin/CLI 코드를 메모리에 로드했을 수 있으므로 새 동작을 확실히 쓰려면 해당 pane을 재시작해야 한다. 다음 세션은 `git diff`를 검토한 뒤, 필요한 경우 CLI/gateway 재시작/스모크 테스트 후 커밋 여부를 사용자에게 확인하면 된다.

## 2. 가장 최근 작업 (100% 보존)

### 2.1 Wave role-board 내부 라우팅 문구 노출 버그 수정

문제:
- 사용자-facing 답변/T1/Slack에 내부 문구가 섞여 나오는 문제가 있었다.
- 노출 문구 예:
  ```text
  Wave role-board routing for this turn:
  - mode: project
  - scope: project
  - reason: project_work_trigger
  - needs_project: False
  - recommended_action: use_project_path_and_emit_progress_at_stage_boundaries
  Rules: chat/scratch mode should avoid automatic four-subagent calls ...
  ```
- 원인: `wave-role-board` plugin의 `pre_llm_call` hook이 내부 routing block을 `{"context": ...}`로 반환했고, Hermes는 이 context를 current turn user message 뒤에 붙인다. 모델이 이 block을 실제 사용자 입력처럼 보고 최종 답변에 그대로 인용할 수 있었다.

수정 파일:
- `/Users/392yes/.hermes/plugins/wave-role-board/__init__.py`
- `/Users/392yes/.hermes/hermes-agent/plugins/wave-role-board/__init__.py`
- `/Users/392yes/.hermes/hermes-agent/tests/plugins/test_wave_role_board_plugin.py`

수정 내용:
- user-local plugin과 repo bundled plugin 둘 다 `_pre_llm_call(...)`에서 routing context를 반환하지 않게 변경했다.
- T2 notes/stage marker 동작은 유지한다.
- 핵심 주석:
  ```python
  # Do not return routing text as pre_llm_call context.  Hermes injects
  # plugin context into the user message, and LLMs can echo that block in
  # T1/Slack replies.  The route is used only for T2 notes/stage markers;
  # user-facing replies must never include the internal
  # "Wave role-board routing for this turn" block.
  return None
  ```
- 테스트명 변경:
  - 기존: `test_pre_llm_call_injects_mode_context_and_notes`
  - 변경: `test_pre_llm_call_emits_mode_notes_without_user_context`
- 새 테스트 기대값:
  - `ret is None`
  - T2 messages는 4개 생성
  - `messages.jsonl`에는 `Wave role-board routing` 문구가 없음

검증 명령 및 결과:
```bash
venv/bin/python -m pytest tests/plugins/test_wave_role_board_plugin.py -q -o 'addopts='
```
결과:
```text
.......                                                                  [100%]
7 passed in 0.14s
```

추가 직접 검증:
```bash
PYTHONPATH=/Users/392yes/.hermes/plugins/wave-role-board /Users/392yes/.hermes/hermes-agent/venv/bin/python - <<'PY'
import importlib.util, sys, types, os, json, tempfile
from pathlib import Path
home=Path(tempfile.mkdtemp())/'.hermes'; home.mkdir(); os.environ['HERMES_HOME']=str(home); os.environ.pop('WAVE_HUB_HOME',None)
if 'hermes_plugins' not in sys.modules:
    ns=types.ModuleType('hermes_plugins'); ns.__path__=[]; sys.modules['hermes_plugins']=ns
p=Path('/Users/392yes/.hermes/plugins/wave-role-board/__init__.py')
spec=importlib.util.spec_from_file_location('hermes_plugins.wave_role_board_user', p, submodule_search_locations=[str(p.parent)])
mod=importlib.util.module_from_spec(spec); mod.__package__='hermes_plugins.wave_role_board_user'; mod.__path__=[str(p.parent)]; sys.modules['hermes_plugins.wave_role_board_user']=mod; spec.loader.exec_module(mod)
ret=mod._pre_llm_call(user_message='프로젝트 작업 진행해줘')
print('ret=', ret)
print('messages_exists=', (home/'wave-hub'/'messages.jsonl').exists())
PY
```
결과:
```text
ret= None
messages_exists= False
```

최종 통합 검증:
```bash
/Users/392yes/.hermes/hermes-agent/venv/bin/python -m py_compile /Users/392yes/.hermes/plugins/wave-role-board/__init__.py plugins/wave-role-board/__init__.py && venv/bin/python -m pytest tests/plugins/test_wave_role_board_plugin.py tests/gateway/test_claude_code_bridge.py tests/gateway/test_orchestrator_modes.py -q -o 'addopts='
```
결과:
```text
.............................                                            [100%]
29 passed in 1.91s
```

주의:
- 이미 실행 중인 Hermes/Wave pane은 plugin 코드를 메모리에 들고 있을 수 있다. 새 수정 적용을 확실히 하려면 pane 재시작 필요.

## 3. 이전 작업 (내림차순 압축)

### 3.1 `hermes-hugo` / `hermes-clara` 로컬 작업대 도입

사용자 요구:
- 기존 `clara-lead` / `hugo-lead` 전역 모드 전환이 복잡하고, 한 Wave pane에서 lead를 바꾸면 다른 pane도 같이 바뀌는 문제가 있었다.
- 사용자는 앞으로 `hermes-hugo`와 `hermes-clara`만 구분해서 쓰고 싶다고 결정했다.
- pane 개수는 제한하면 안 된다. 필요에 따라 1개, 2개, 3개, 4개 이상 가능해야 한다.

구현:
- 새 파일 생성:
  - `/Users/392yes/.hermes/hermes-agent/hermes_cli/lead_entrypoints.py`
- `pyproject.toml` entry point 추가:
  ```toml
  hermes-hugo = "hermes_cli.lead_entrypoints:main_hugo"
  hermes-clara = "hermes_cli.lead_entrypoints:main_clara"
  ```
- 실제 사용 가능한 wrapper 생성:
  - `/Users/392yes/.local/bin/hermes-hugo`
  - `/Users/392yes/.local/bin/hermes-clara`
- wrapper 동작:
  - `hermes-hugo`는 `HERMES_LEAD_MODE=hugo-lead`를 export 후 기존 Hermes 실행
  - `hermes-clara`는 `HERMES_LEAD_MODE=clara-lead`를 export 후 기존 Hermes 실행
  - 둘 다 `PYTHONPATH`, `PYTHONHOME` unset 후 `/Users/392yes/.hermes/hermes-agent/venv/bin/hermes` 실행

검증:
```bash
which hermes-hugo hermes-clara
hermes-hugo --version
hermes-clara --version
HERMES_LEAD_MODE=clara-lead venv/bin/python - <<'PY'
from gateway.orchestrator_modes import handle_mode_text
print(handle_mode_text('휴고 주도 모드'))
PY
```
결과:
```text
/Users/392yes/.local/bin/hermes-hugo
/Users/392yes/.local/bin/hermes-clara
hugo ok: Hermes Agent v0.14.0 (2026.5.16)
clara ok: Hermes Agent v0.14.0 (2026.5.16)
이 세션은 HERMES_LEAD_MODE=clara-lead 로 고정(pinned)되어 있어 모드를 전환하지 않았습니다.
이 pane은 계속 고정된 lead로 동작하며, 전역 모드 전환은 고정 없이 실행된 세션이나 Slack에서 해주세요.
```

운영 규칙:
- `hermes-hugo` = 해당 pane은 Hugo 작업대.
- `hermes-clara` = 해당 pane은 Clara 작업대.
- pane 개수 제한 없음.
- 모든 pane은 default Hermes home을 공유하므로 같은 `/Users/392yes/.hermes/state.db`, memory, skills, Wave active project/context를 본다.
- 상주성은 pane/session 단위다. 같은 Clara pane은 같은 Claude resume 세션을 재사용한다. 다른 Clara pane은 별도 Claude 세션으로 시작한다.

### 3.2 Clara bridge에 pane/session-local Claude `--resume` 재사용 구현

문제:
- 기존 `clara-lead` Hermes 경로는 매 턴 새 Claude Code CLI job을 띄워서 Hugo보다 느렸다.
- 사용자는 Clara도 Hugo처럼 속도와 상주성이 동일한 수준이 되기를 원했다.

수정 파일:
- `/Users/392yes/.hermes/hermes-agent/gateway/claude_code_bridge.py`
- `/Users/392yes/.hermes/hermes-agent/cli.py`
- `/Users/392yes/.hermes/hermes-agent/gateway/run.py`
- `/Users/392yes/.hermes/hermes-agent/tests/gateway/test_claude_code_bridge.py`

구현:
- `run_claude_code_bridge_sync(..., bridge_session_key: str | None = None)` 인자 추가.
- CLI 경로에서 `bridge_session_key=f"cli:{self.session_id}"` 전달.
- one-shot CLI 경로에서 `bridge_session_key=f"cli:{cli.session_id}"` 전달.
- gateway 경로에서 `bridge_session_key=f"gateway:{session_id}"` 전달.
- Claude Code 결과 JSON의 `session_id`를 저장하고, 다음 호출에서 같은 bridge key + 같은 workdir이면 `claude --resume <session_id> -p <prompt> ...`로 실행.
- 매핑 저장 위치:
  - `/Users/392yes/.hermes/runtime/claude-code-bridge-sessions.json`
- 환경 변수로 비활성화 가능:
  - `HERMES_CLARA_DISABLE_RESUME=1`
- workdir이 달라지면 기존 Claude session을 resume하지 않게 했다.

테스트 추가:
- `test_run_bridge_reuses_claude_session_for_same_bridge_key`
- 첫 호출은 `--resume` 없음.
- 두 번째 호출은 `--resume session-1` 포함.
- session map은 두 번째 결과의 `session-2`로 업데이트됨.

주의/한계:
- Claude 계정 월 사용 한도 429가 걸려 있으면 실제 Clara 응답은 여전히 실패한다. 구조적 상주성은 구현됐지만 체감 속도 검증은 Claude 한도 해제 후 가능하다.
- 사용자가 “hermes-clara도 hermes-hugo처럼 속도가 똑같이 잘 나와야 한다”고 요청했지만, 실제 속도는 Claude Code CLI/구독/한도/모델 상태에 의존한다. 구현상으로는 매턴 fresh job 비용을 줄였다.

### 3.3 기존 `/hugo-lead`, `/clara-lead` 정리 방향

사용자 결정:
- 로컬 Wave 병행 작업에서는 `hermes-hugo` / `hermes-clara`만 쓰기로 했다.

구현/정리:
- slash command 자체는 삭제하지 않았다.
- 이유: Slack/gateway 전역 모드 전환 호환성이 필요할 수 있기 때문.
- 대신 `hermes_cli/commands.py` 설명을 legacy global switch로 변경:
  - `hugo-lead`: `Legacy global switch; prefer hermes-hugo for a fixed Wave pane`
  - `clara-lead`: `Legacy global switch; prefer hermes-clara for a fixed Wave pane`
- Claude quota/spend limit 안내도 `/hugo-lead` 전환 대신 `hermes-hugo` 실행 안내로 변경.

### 3.4 세션 초반: Logitech Options+ 제거 및 속도 원인 분석

- Wave T2 로그 확인이 답변 속도에 미치는 영향은 작고, 실제 로컬 CPU 점유 요인으로 Logitech Options+가 높게 나타났었다.
- 사용자가 Logitech Options+ 삭제를 지시했고, root 권한 명령을 직접 실행했다.
- 검증 로그 원문:
  ```text
  === 실행 시각: 2026년  6월 12일 금요일 21시 04분 34초 KST / 호스트: MacMini.local / 실행자: root ===
  --- 1. launchd 데몬 해제 ---
  updater bootout OK
  RightSight bootout 생략
  --- 2. 잔존 프로세스 강제 종료 ---
  남은 프로세스 없음
  --- 3. 파일 삭제 ---
  rm 완료 (exit=0)
  --- 4. 자체 검증 ---
  === 결과: 삭제 완료 (잔존 0건) ===
  ```
- 그 뒤 Clara/Hugo 응답 타이밍을 비교했고, 핵심 차이는 gateway가 아니라 Clara가 매 턴 fresh Claude CLI job으로 뜨는 구조와 모델 왕복 루프에 있음을 설명했다.

## 4. 사용자 결정사항·승인 내역 (무압축)

- 2026-06-13: 사용자는 로컬 Wave 작업대 구분을 기존 `clara-lead` / `hugo-lead` 중심이 아니라 `hermes-hugo` / `hermes-clara` 중심으로 단순화하기로 결정했다.
- 2026-06-13: 사용자는 pane 개수를 2개로 제한하지 말라고 명확히 정정했다. 필요에 따라 하나만 쓸 수도 있고, 세 개/네 개 이상도 가능해야 한다.
- 2026-06-13: 사용자는 `hermes-clara`도 `hermes-hugo`처럼 속도와 상주성이 잘 나와야 하며, 둘 다 완벽히 같은 memory/state를 공유해야 한다고 요구했다.
- 2026-06-13: 사용자는 기존 `clara-lead` / `hugo-lead`가 필요 없으면 정리하고 `hermes-hugo` / `hermes-clara` 방식으로 진행하라고 승인했다.
- 2026-06-13: 사용자는 user-facing 답변에 노출되는 `Wave role-board routing for this turn...` 내부 문구를 마저 수정하라고 지시했고, 수정 완료했다.
- 2026-06-12: 사용자는 Logitech Options+ 완전 삭제를 지시했고, 관리자 권한 명령을 직접 실행했다. 삭제 검증 결과 잔존 0건이었다.

## 5. 미완료 작업 / 다음 액션

- [ ] 새 Hermes/Wave pane을 재시작해 `hermes-hugo` / `hermes-clara`가 실제 Wave 환경에서 기대대로 동작하는지 스모크 테스트한다.
- [ ] Claude monthly spend limit 429가 해제된 뒤 `hermes-clara` 실제 응답 속도와 `--resume` 재사용 효과를 측정한다.
- [ ] 현재 미커밋 변경 전체를 `git diff`로 리뷰하고, 필요한 경우 테스트 범위를 넓힌 뒤 커밋 여부를 사용자에게 확인한다.
- [ ] user-local plugin `/Users/392yes/.hermes/plugins/wave-role-board/__init__.py`와 repo bundled plugin `/Users/392yes/.hermes/hermes-agent/plugins/wave-role-board/__init__.py`의 source split을 유지할지/정리할지 결정한다.
- [ ] Slack/gateway 전역 `/hugo-lead`, `/clara-lead` 호환성을 계속 유지할지, 도움말에서 더 숨길지 사용자에게 확인한다.

## 6. 주의사항·함정

- 현재 git working tree에는 이번 세션 변경 외에 이미 존재하던 변경도 섞여 있을 수 있다. 절대 무턱대고 reset하지 말 것.
- 현재 `git status --short`:
  ```text
   M agent/skill_commands.py
   M cli.py
   M gateway/claude_code_bridge.py
   M gateway/orchestrator_modes.py
   M gateway/run.py
   M hermes_cli/commands.py
   M plugins/wave-role-board/__init__.py
   M pyproject.toml
   M tests/agent/test_skill_commands.py
   M tests/gateway/test_claude_code_bridge.py
   M tests/gateway/test_orchestrator_modes.py
   M tests/plugins/test_wave_role_board_plugin.py
  ?? hermes_cli/lead_entrypoints.py
  ```
- wrapper scripts `/Users/392yes/.local/bin/hermes-hugo`와 `/Users/392yes/.local/bin/hermes-clara`는 git tracked 파일이 아니다. 다음 세션에서 시스템 상태를 볼 때 이 점을 기억할 것.
- `hermes-clara`의 “상주성”은 Claude Code CLI의 `--resume` 기반이다. Hugo의 in-process agent와 완전히 같은 내부 구조는 아니다. 하지만 사용자가 원하는 운영 UX는 `hermes-hugo`/`hermes-clara` 작업대 모델로 맞췄다.
- `HERMES_LEAD_MODE` pin은 전역 mode file을 건드리지 않는다. 현재 전역 파일은 별도로 존재하며, 확인 당시 내용은 다음과 같았다:
  ```json
  {"mode": "hugo-lead", "updated_at": "2026-06-12T22:24:34+0900", "source": "codex:claude-spend-limit-fallback"}
  ```
- 이미 떠 있는 Hermes/Wave pane은 plugin/CLI 변경을 반영하지 않을 수 있다. 새 동작 검증 전 재시작 필요.
- Claude monthly spend limit 429가 현재 Clara 실제 경로 검증의 블로커다. 이 상태에서 `hermes-clara`는 구조는 개선됐지만 실제 응답은 실패할 수 있다.
- user message에 보이는 `Wave role-board routing...` block은 원래 내부 라우팅 힌트였고, 이제 plugin에서는 context로 반환하지 않도록 수정했다. 단, 이미 세션 기록에 남은 과거 메시지에는 해당 문구가 존재한다.
