# HermesAgent Inspector API

## 개요

**HermesAgent Inspector**는 외부 Docker 컨테이너(ClaudeCode, Antigravity 등)가 네이티브 HermesAgent 인스턴스의 공개 정보를 읽기 전용으로 조회할 수 있도록 제공하는 경량 HTTP 서버입니다.

- 기본 바인드: `http://127.0.0.1:8646`
- GET 전용 엔드포인트 (읽기 전용)
- CORS 허용 (`Access-Control-Allow-Origin: *`)
- 인증 없이 접근 가능 (단, 민감 정보는 구조적으로 제외됨)

---

## 엔드포인트 레퍼런스

### `GET /health`

게이트웨이 프로세스의 생존 여부와 업타임을 반환합니다.

**요청**
```
GET http://127.0.0.1:8646/health
```

**응답 예시**
```json
{
  "status": "ok",
  "pid": 12345,
  "uptime_seconds": 3720.45
}
```

---

### `GET /status`

현재 모델, 프로바이더, API 모드, 게이트웨이 상태, 활성 에이전트 수, 플랫폼 연결 상태를 반환합니다.

**요청**
```
GET http://127.0.0.1:8646/status
```

**응답 예시**
```json
{
  "model": "claude-opus-4-5",
  "provider": "anthropic",
  "api_mode": "api",
  "gateway_state": "running",
  "active_agents": 2,
  "platforms": {
    "telegram": {
      "state": "connected",
      "updated_at": "2026-06-10T04:00:00+00:00"
    },
    "discord": {
      "state": "connected",
      "updated_at": "2026-06-10T04:00:00+00:00"
    }
  }
}
```

---

### `GET /skills`

`~/.hermes/skills/` 디렉토리를 스캔하여 설치된 스킬 목록을 반환합니다. 각 스킬의 `SKILL.md` frontmatter에서 `name`, `category`, `description`을 추출합니다.

**요청**
```
GET http://127.0.0.1:8646/skills
```

**응답 예시**
```json
[
  {
    "slug": "blue-ribbon-nearby",
    "name": "blue-ribbon-nearby",
    "category": "food",
    "description": "Use when the user asks for nearby restaurants or 근처 맛집 and wants 블루리본 picks."
  },
  {
    "slug": "devops/kanban-worker",
    "name": "kanban-worker",
    "category": "devops",
    "description": "Pitfalls, examples, and edge cases for Hermes Kanban workers."
  }
]
```

`slug` 필드는 API 엔드포인트에 사용하는 경로 식별자입니다. 단순 스킬은 `name`과 동일하고, 카테고리 아래 중첩된 스킬은 `category/name` 형태입니다.

---

### `GET /skills/<slug>`

특정 스킬의 `SKILL.md` 전문(본문 포함)을 반환합니다. `slug`는 `/skills` 응답의 `slug` 필드 값을 사용합니다.

**요청 (단순)**
```
GET http://127.0.0.1:8646/skills/blue-ribbon-nearby
```

**요청 (중첩)**
```
GET http://127.0.0.1:8646/skills/devops/kanban-worker
```

**응답 예시**
```json
{
  "slug": "blue-ribbon-nearby",
  "content": "---\nname: blue-ribbon-nearby\ndescription: ...\n---\n\n# Blue Ribbon Nearby\n..."
}
```

**404 응답 예시 (스킬 없음)**
```json
{
  "error": "not_found",
  "message": "Skill 'nonexistent-skill' not found"
}
```

---

### `GET /config/public`

민감하지 않은 공개 설정만 반환합니다. `api_key`, `token`, `secret`, `password`, `auth`, `credential`, `bearer` 관련 키는 모두 제외됩니다.

노출되는 섹션: `model`, `agent`, `toolsets`, `compression`, `language`, `locale`, `ui`

**요청**
```
GET http://127.0.0.1:8646/config/public
```

**응답 예시**
```json
{
  "model": {
    "default": "claude-opus-4-5",
    "provider": "anthropic"
  },
  "agent": {
    "max_turns": 50,
    "timeout_seconds": 300
  },
  "toolsets": ["default", "web", "code"],
  "compression": {
    "enabled": true,
    "threshold_tokens": 8000
  }
}
```

---

## Docker Container에서 사용하는 법

Docker 컨테이너 내부에서 호스트의 Inspector에 접근할 때는 `host.docker.internal`을 사용합니다.

### curl 예시

```bash
# 컨테이너 내부에서 호스트 HermesAgent Inspector 조회
curl http://host.docker.internal:8646/health
curl http://host.docker.internal:8646/status
curl http://host.docker.internal:8646/skills
curl http://host.docker.internal:8646/skills/blue-ribbon-nearby
curl http://host.docker.internal:8646/config/public
```

### Python requests 예시

```python
import os
import requests

HERMES_INSPECTOR_URL = os.environ.get(
    "HERMES_INSPECTOR_URL", "http://host.docker.internal:8646"
)

def get_hermes_status():
    resp = requests.get(f"{HERMES_INSPECTOR_URL}/status", timeout=5)
    resp.raise_for_status()
    return resp.json()

def list_hermes_skills():
    resp = requests.get(f"{HERMES_INSPECTOR_URL}/skills", timeout=5)
    resp.raise_for_status()
    return resp.json()

def get_skill_content(name: str):
    resp = requests.get(f"{HERMES_INSPECTOR_URL}/skills/{name}", timeout=5)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["content"]
```

---

## 환경 변수

| 환경 변수 | 기본값 | 설명 |
|---|---|---|
| `HERMES_INSPECTOR_HOST` | `127.0.0.1` | Inspector 서버 바인드 호스트 |
| `HERMES_INSPECTOR_PORT` | `8646` | Inspector 서버 포트 |
| `HERMES_INSPECTOR_DISABLED` | (unset) | `1`, `true`, `yes`로 설정 시 Inspector 비활성화 |

Docker 컨테이너가 접근하려면 호스트에서 `HERMES_INSPECTOR_HOST=0.0.0.0`으로 설정하거나, Docker 네트워크 구성에 따라 적절히 조정하세요.

---

## 보안 고려사항

### 노출되는 정보

- 프로세스 PID 및 업타임
- 게이트웨이 상태 (`running`, `starting`, `degraded` 등)
- 활성 에이전트 수
- 플랫폼 연결 상태 (연결됨/끊김, 오류 코드)
- 현재 모델 이름 및 프로바이더
- API 모드 (`api`, `mcp` 등)
- 스킬 이름, 카테고리, 설명
- SKILL.md 전문 (설치된 스킬의 사용 방법)
- 비민감 config 섹션 (model.default, agent.max_turns, toolsets 등)

### 노출되지 않는 정보

- API 키, 토큰, Bearer 인증 정보
- `auth.json`, `.env` 파일 내용
- 세션 데이터 및 대화 기록
- 메모리(memories) 파일
- config.yaml의 민감 키 (`api_key`, `token`, `secret`, `password`, `auth`, `credential`)
- 플랫폼 인증 정보 (Telegram bot token, Discord token 등)

### 네트워크 접근 제어

기본값 `127.0.0.1` 바인딩은 같은 호스트에서만 접근 가능합니다. 외부 네트워크에 노출하려면 반드시 방화벽 규칙을 설정하세요.

---

## docker-compose.yml 예시

```yaml
version: "3.9"

services:
  hermes-agent:
    build: .
    environment:
      - HERMES_INSPECTOR_HOST=0.0.0.0
      - HERMES_INSPECTOR_PORT=8646
    ports:
      - "127.0.0.1:8646:8646"
    volumes:
      - ~/.hermes:/root/.hermes

  claude-code:
    image: ghcr.io/anthropics/claude-code:latest
    environment:
      - HERMES_INSPECTOR_URL=http://hermes-agent:8646
    depends_on:
      - hermes-agent
    networks:
      - hermes-net

  antigravity:
    image: antigravity:latest
    environment:
      - HERMES_INSPECTOR_URL=http://hermes-agent:8646
    depends_on:
      - hermes-agent
    networks:
      - hermes-net

networks:
  hermes-net:
    driver: bridge
```

### host.docker.internal 사용 (macOS/Windows Docker Desktop)

```yaml
version: "3.9"

services:
  claude-code:
    image: ghcr.io/anthropics/claude-code:latest
    environment:
      - HERMES_INSPECTOR_URL=http://host.docker.internal:8646
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

> **참고**: Linux Docker에서는 `extra_hosts: ["host.docker.internal:host-gateway"]`를 명시해야 합니다. macOS/Windows Docker Desktop에서는 자동으로 동작합니다.
