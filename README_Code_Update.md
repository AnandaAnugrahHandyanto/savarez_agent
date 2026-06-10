# HermesAgent Code Update — 2026-06-10

이 문서는 2026-06-10에 수정된 코드 변경 사항을 정리합니다.
오픈소스 기여를 위한 PR 제출 가이드도 함께 포함합니다.

---

## 목차

1. [변경 요약](#1-변경-요약)
2. [변경 상세](#2-변경-상세)
   - [PR 1 — Fallback Context Bridge](#pr-1--fallback-context-bridge)
   - [PR 2 — Inspector HTTP API](#pr-2--inspector-http-api)
   - [PR 3 — providers.py hostname 정확도 개선](#pr-3--providerspyhostname-정확도-개선)
   - [PR 4 — skill_view 중첩 디렉토리 오탐 수정](#pr-4--skill_view-중첩-디렉토리-오탐-수정)
3. [오픈소스 기여 방법](#3-오픈소스-기여-방법)
4. [PR별 commit 명령어](#4-pr별-commit-명령어)

---

## 1. 변경 요약

| PR | 유형 | 범위 | 제목 |
|----|------|------|------|
| #1 | `fix` + `feat` | `agent` | Fallback 시 api_mode 변경으로 인한 컨텍스트 단절 수정 |
| #2 | `feat` | `gateway` | 외부 컨테이너용 읽기전용 Inspector HTTP API 추가 |
| #3 | `fix` | `hermes_cli` | `api.openai.com` hostname 부분 일치 오탐 수정 |
| #4 | `fix` | `tools` | `skill_view` 중첩 스킬 디렉토리 내 오탐 수정 |

---

## 2. 변경 상세

---

### PR 1 — Fallback Context Bridge

#### 문제

`openai-codex` (api_mode: `codex_responses`) 를 Primary Provider로 사용하다가 Rate Limit, 네트워크 오류 등으로 `try_activate_fallback()` 이 발동되면, 다른 provider (예: `anthropic_messages`, `chat_completions`) 로 전환된다.

이때 두 가지 문제가 발생했다:

1. **Codex 전용 필드가 새 provider 요청에 포함됨**
   - `codex_reasoning_items`: Codex가 발급한 `encrypted_content` 블록. 다른 provider에 전달하면 HTTP 400 `invalid_encrypted_content` 오류 발생
   - `codex_message_items`: Codex 중간 출력 아이템. 다른 provider API 스키마에 없는 필드
   - `_thinking_prefill`: 내부 마커. 외부 API로 나가면 엄격한 게이트웨이에서 422 오류

2. **시스템 프롬프트(스킬 목록)가 재빌드되지 않음**
   - `api_messages`는 루프 진입 시점(Primary provider 기준)에 한 번만 빌드됨
   - Fallback 전환 후에도 구 provider용 시스템 프롬프트가 그대로 사용됨
   - Codex 세션 중 생성/수정된 스킬 정보가 새 provider에 전달되지 않음

#### 해결

**`agent/fallback_context_bridge.py`** (신규)

`apply_fallback_context_bridge()` 함수:
- **Context Bridge**: `codex_responses` → 다른 provider 전환 시 `api_messages`에서 Codex 전용 필드 제거, `_disable_codex_reasoning_replay()` 호출
- **Skill Re-injection**: `agent._build_system_prompt()` 재실행 후 `api_messages[0]` (system message) 를 새 provider용으로 교체

**`agent/chat_completion_helpers.py`** (수정)

`try_activate_fallback()` 에서 api_mode 변경 감지:
```python
old_api_mode = getattr(agent, "api_mode", "chat_completions")
# ...provider swap...
if old_api_mode != fb_api_mode:
    agent._pending_context_bridge = {"old_api_mode": ..., "new_api_mode": ...}
    agent._cached_system_prompt = None  # 재빌드 트리거
```

**`agent/conversation_loop.py`** (수정)

retry loop 안에서 `_reapply_reasoning_echo_for_provider()` 직후, `_build_api_kwargs()` 직전에 브릿지 실행:
```python
_bridge = getattr(agent, "_pending_context_bridge", None)
if _bridge:
    agent._pending_context_bridge = None
    apply_fallback_context_bridge(agent, api_messages, ...)
```

#### 수정된 파일

| 파일 | 변경 유형 |
|------|-----------|
| `agent/fallback_context_bridge.py` | 신규 |
| `agent/chat_completion_helpers.py` | 수정 (+17줄) |
| `agent/conversation_loop.py` | 수정 (+22줄) |
| `tests/agent/test_fallback_context_bridge_integration.py` | 신규 (19개 테스트) |
| `scripts/simulate_codex_fallback.py` | 신규 (수동 검증 스크립트) |

#### 검증

```bash
# 유닛 테스트 (19개 전부 통과)
venv/bin/python -m pytest tests/agent/test_fallback_context_bridge_integration.py -v

# 시뮬레이션 스크립트
venv/bin/python scripts/simulate_codex_fallback.py
```

---

### PR 2 — Inspector HTTP API

#### 문제

Docker 컨테이너(ClaudeCode, Antigravity 등)에서 실행되는 AI 에이전트는 Native HermesAgent 인스턴스의 스킬 목록, 현재 모델, 게이트웨이 상태를 알 수 없다.

기존 해결책 후보:
- **전체 `.hermes/` 마운트**: `config.yaml`, `auth.json`, `.env` 등 API 키가 모두 노출되어 위험
- **`skills/` 만 마운트**: 심볼릭 링크 처리 문제, 실시간 상태 조회 불가
- **Inspector HTTP API** (채택): 민감 정보를 구조적으로 제외한 읽기전용 엔드포인트

#### 해결

**`gateway/inspector.py`** (신규)

`InspectorServer` 클래스 — aiohttp 기반 읽기전용 HTTP 서버:

| 엔드포인트 | 응답 내용 |
|------------|-----------|
| `GET /health` | `{status, pid, uptime_seconds}` |
| `GET /status` | `{model, provider, gateway_state, active_agents, platforms}` |
| `GET /skills` | 181개 스킬 목록 `[{slug, name, category, description}]` |
| `GET /skills/<slug>` | SKILL.md 전문 (flat: `blue-ribbon-nearby`, nested: `devops/kanban-worker`) |
| `GET /config/public` | api_key 제외된 안전 config |

보안 설계:
- `_SENSITIVE_KEY_PATTERNS` 정규식으로 api_key / token / secret / password / auth / credential 키 재귀적 제거
- path traversal 방어: slug 이름은 `^[a-zA-Z0-9_\-]+(/[a-zA-Z0-9_\-]+)?$` 허용
- 심볼릭 링크 지원 (`~/.agents/skills/` 에 링크된 스킬 포함)
- 기본 바인드: `127.0.0.1:8646` (환경 변수로 오버라이드 가능)

**`gateway/run.py`** (수정)

`cron_thread.start()` 직후, `wait_for_shutdown()` 직전에 Inspector 서버 시작:
```python
HERMES_INSPECTOR_HOST=0.0.0.0  # Docker 접근 허용 시
HERMES_INSPECTOR_PORT=8646      # 기본값
HERMES_INSPECTOR_DISABLED=1    # 비활성화
```

#### 수정된 파일

| 파일 | 변경 유형 |
|------|-----------|
| `gateway/inspector.py` | 신규 |
| `gateway/run.py` | 수정 (+30줄) |
| `docs/hermes-inspector-api.md` | 신규 (API 레퍼런스) |
| `docs/hermes-inspector-skill.md` | 신규 (SKILL.md) |

#### 검증

```bash
# Inspector 서버 시작 확인
HERMES_INSPECTOR_HOST=0.0.0.0 hermes gateway run

# 엔드포인트 테스트
curl http://127.0.0.1:8646/health
curl http://127.0.0.1:8646/skills | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d), '개 스킬')"
curl http://127.0.0.1:8646/skills/blue-ribbon-nearby | python3 -c "import json,sys; print(json.load(sys.stdin)['content'][:100])"
curl http://127.0.0.1:8646/skills/devops/kanban-worker | python3 -c "import json,sys; print(json.load(sys.stdin)['content'][:100])"

# Docker 컨테이너에서 (Linux)
docker run --rm --add-host=host.docker.internal:host-gateway curlimages/curl \
  http://host.docker.internal:8646/health
```

---

### PR 3 — providers.py hostname 정확도 개선

#### 문제

`determine_api_mode()` 에서 `api.openai.com` 을 포함하는 URL 판별 시 `in` 연산자를 사용해 부분 일치로 처리했다. 예를 들어 `https://custom-proxy.api.openai.com.evil.com/v1` 같은 악의적인 URL도 `codex_responses` 모드로 잘못 분류될 수 있다.

```python
# 수정 전
if "api.openai.com" in url_lower:
    return "codex_responses"

# 수정 후
if base_url_hostname(base_url) == "api.openai.com":
    return "codex_responses"
```

#### 수정된 파일

| 파일 | 변경 유형 |
|------|-----------|
| `hermes_cli/providers.py` | 수정 (1줄) |

---

### PR 4 — skill_view 중첩 디렉토리 오탐 수정

#### 문제

`skill_view()` 의 Strategy 3 (legacy flat `.md` 파일 검색) 에서 다른 스킬의 하위 디렉토리에 존재하는 동명 파일을 잘못 매칭했다.

예: `devops/kanban-worker/` 안에 `code-review.md` 가 있을 때 `/code-review` 스킬 조회 시 이 파일이 후보로 잡히는 문제.

#### 해결

검색 중인 파일(`found_md`)의 상위 경로를 순회하며, `SKILL.md` 가 있는 다른 스킬 디렉토리 안에 포함된 경우 후보에서 제외한다.

```python
in_other_skill = False
for p in found_md.parents:
    if p == search_dir:
        break
    if (p / "SKILL.md").exists():
        in_other_skill = True
        break
if not in_other_skill:
    _record(None, found_md)
```

#### 수정된 파일

| 파일 | 변경 유형 |
|------|-----------|
| `tools/skills_tool.py` | 수정 (+16줄) |

---

## 3. 오픈소스 기여 방법

CONTRIBUTING.md의 규칙 요약: [docs](CONTRIBUTING.md)

### 기본 원칙

- **PR은 하나의 논리적 변경만 포함** — 버그픽스와 새 기능을 섞지 않는다
- **Conventional Commits 형식** 사용
- **테스트 필수** — 새 코드에는 테스트 추가
- **라이선스**: 기여 내용은 MIT 라이선스 적용에 동의

### Fork → Branch → PR 워크플로우

```
1. GitHub에서 NousResearch/hermes-agent Fork
2. 로컬에 fork 추가
3. 변경별 브랜치 생성
4. 커밋 & 포크에 push
5. GitHub에서 PR 생성
```

### Step 1: GitHub에서 Fork

[https://github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 에서 **Fork** 버튼 클릭.

### Step 2: fork를 remote로 추가

```bash
# 본인 GitHub 계정명으로 교체
GITHUB_USER="your-github-username"

git remote add fork https://github.com/${GITHUB_USER}/hermes-agent.git
git remote -v
# origin  https://github.com/NousResearch/hermes-agent.git (fetch/push)  ← upstream
# fork    https://github.com/YOUR_USER/hermes-agent.git    (fetch/push)  ← 기여용
```

### Step 3: upstream 최신 상태로 동기화

```bash
git fetch origin
git checkout main
git rebase origin/main
```

### Step 4: 변경별 브랜치 생성

PR마다 별도 브랜치를 만든다. 브랜치명 규칙: `fix/description` 또는 `feat/description`

```bash
# PR 1
git checkout -b fix/fallback-context-bridge-cross-mode

# PR 2
git checkout -b feat/gateway-inspector-api

# PR 3
git checkout -b fix/providers-hostname-exact-match

# PR 4
git checkout -b fix/skill-view-nested-dir-false-positive
```

### Step 5: Commit 메시지 형식

```
<type>(<scope>): <subject>

[body — 생략 가능, 72자 줄바꿈]

[footer — Closes #123, Breaking changes 등]
```

| type | 용도 |
|------|------|
| `fix` | 버그 수정 |
| `feat` | 새 기능 |
| `docs` | 문서 |
| `test` | 테스트 |
| `refactor` | 동작 변경 없는 리팩토링 |

### Step 6: fork에 push

```bash
git push fork <브랜치명>
```

### Step 7: PR 생성

GitHub에서 `fork/<브랜치>` → `NousResearch/hermes-agent:main` PR 생성.

PR 본문에 포함:
- **What**: 무엇이 바뀌었고 왜
- **How to test**: 재현 방법 또는 테스트 명령어
- **Platforms tested**: Linux / macOS / WSL2 등

---

## 4. PR별 commit 명령어

> **사전 조건**: `GITHUB_USER` 에 본인 계정명 설정, fork remote 등록 완료

---

### PR 1: Fallback Context Bridge

```bash
git checkout main
git fetch origin && git rebase origin/main

git checkout -b fix/fallback-context-bridge-cross-mode

git add \
  agent/fallback_context_bridge.py \
  agent/chat_completion_helpers.py \
  agent/conversation_loop.py \
  tests/agent/test_fallback_context_bridge_integration.py \
  scripts/simulate_codex_fallback.py

git commit -m "$(cat <<'EOF'
fix(agent): preserve context and skills when fallback crosses api_mode boundary

When try_activate_fallback() switches from codex_responses to
anthropic_messages (or chat_completions), the already-built api_messages
list contains Codex-specific fields (codex_reasoning_items,
codex_message_items, encrypted reasoning blobs) that the new provider
rejects with HTTP 400 / 422.  Additionally, the cached system prompt was
not rebuilt for the new provider, so skills created or updated during the
Codex session were invisible to the fallback model.

Introduce agent/fallback_context_bridge.py with two responsibilities:

  1. Context Bridge: strip codex_* fields and disable reasoning replay
     when leaving codex_responses; strip cache_control / reasoning_content
     pads when entering codex_responses from another provider.

  2. Skill Re-injection: call agent._build_system_prompt() and replace
     api_messages[0] so the fallback provider receives an up-to-date
     skill index.

try_activate_fallback() now records the api_mode delta on
agent._pending_context_bridge and clears _cached_system_prompt when the
mode changes.  conversation_loop.run_conversation() consumes the flag
immediately before _build_api_kwargs(), after the existing
_reapply_reasoning_echo_for_provider() call.  The bridge is fail-open:
exceptions are logged at WARNING and the retry continues.

Includes 19 unit tests and a standalone simulation script.
EOF
)"

git push fork fix/fallback-context-bridge-cross-mode
```

---

### PR 2: Inspector HTTP API

```bash
git checkout main
git fetch origin && git rebase origin/main

git checkout -b feat/gateway-inspector-api

git add \
  gateway/inspector.py \
  gateway/run.py \
  docs/hermes-inspector-api.md \
  docs/hermes-inspector-skill.md

git commit -m "$(cat <<'EOF'
feat(gateway): add read-only Inspector HTTP API for external containers

Docker containers (ClaudeCode, Antigravity, etc.) running alongside a
native HermesAgent have no way to discover installed skills, current
model/provider, or gateway status without mounting ~/.hermes/ — which
exposes API keys, auth.json, session history, and other sensitive data.

Add gateway/inspector.py (InspectorServer) — a lightweight aiohttp
server that starts alongside the gateway and exposes five GET-only
endpoints on 127.0.0.1:8646 (configurable):

  GET /health           → {status, pid, uptime_seconds}
  GET /status           → {model, provider, gateway_state, active_agents, platforms}
  GET /skills           → skill list with slug/name/category/description
  GET /skills/<slug>    → SKILL.md content (flat and nested slugs supported)
  GET /config/public    → safe config subset (api_key and all sensitive keys excluded)

Security design:
  - Sensitive keys (api_key/token/secret/password/auth/credential/bearer)
    are recursively stripped from config responses via regex allowlist.
  - Skill slug validation uses ^[a-zA-Z0-9_\-]+(/[a-zA-Z0-9_\-]+)?$ to
    prevent path traversal without needing symlink resolution (skills are
    commonly symlinked from ~/.agents/skills/).
  - Default bind is 127.0.0.1; set HERMES_INSPECTOR_HOST=0.0.0.0 to
    allow Docker container access.
  - Set HERMES_INSPECTOR_DISABLED=1 to opt out entirely.

Supports both flat skill layouts (skill-name/SKILL.md) and one-level
nested layouts (category/skill-name/SKILL.md), and follows symlinks so
skills installed via ~/.agents/ are included.
EOF
)"

git push fork feat/gateway-inspector-api
```

---

### PR 3: providers.py hostname 정확도 개선

```bash
git checkout main
git fetch origin && git rebase origin/main

git checkout -b fix/providers-hostname-exact-match

git add hermes_cli/providers.py

git commit -m "$(cat <<'EOF'
fix(hermes_cli): use exact hostname match for api.openai.com api_mode detection

determine_api_mode() used a substring check ("api.openai.com" in url_lower)
to decide whether to return codex_responses.  A URL like
https://proxy.api.openai.com.evil.com/v1 would satisfy the substring test
and be misclassified.

Replace with base_url_hostname(base_url) == "api.openai.com" which
extracts only the hostname component before comparing, matching the
existing pattern used elsewhere in this file.
EOF
)"

git push fork fix/providers-hostname-exact-match
```

---

### PR 4: skill_view 중첩 디렉토리 오탐 수정

```bash
git checkout main
git fetch origin && git rebase origin/main

git checkout -b fix/skill-view-nested-dir-false-positive

git add tools/skills_tool.py

git commit -m "$(cat <<'EOF'
fix(tools): exclude files inside other skills from skill_view legacy search

skill_view() Strategy 3 searches for legacy flat <name>.md files using
rglob.  When a nested skill directory contains a file whose name matches
the queried skill name (e.g. devops/kanban-worker/code-review.md while
searching for the code-review skill), it was incorrectly added as a
candidate.

Add an ancestor-walk check: if any directory between found_md and the
search root contains its own SKILL.md, the file belongs to another skill's
directory and is excluded from the candidate set.
EOF
)"

git push fork fix/skill-view-nested-dir-false-positive
```

---

## PR 본문 템플릿 (GitHub용)

```markdown
## What changed and why

<!-- 무엇이 바뀌었고 왜 필요한지 설명 -->

## How to test

```bash
# 테스트 명령어
```

## Platforms tested

- [x] Linux (Ubuntu 24.04)
- [ ] macOS
- [ ] Windows / WSL2

## Related issues

Closes #
```

---

## 참고 링크

- [CONTRIBUTING.md](CONTRIBUTING.md) — 프로젝트 기여 가이드 (필독)
- [GitHub Issues](https://github.com/NousResearch/hermes-agent/issues) — 버그 리포트
- [Nous Research Discord](https://discord.gg/NousResearch) — 커뮤니티, 스킬 공유
- [Conventional Commits](https://www.conventionalcommits.org/) — 커밋 메시지 형식
