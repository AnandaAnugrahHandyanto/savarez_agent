---
name: hermes-inspector
description: Query the native HermesAgent instance from inside a Docker container using the Inspector API. Use this skill when you need to discover available skills, check gateway status, or read public configuration from within a containerized environment.
license: MIT
metadata:
  category: devops
  locale: en
  phase: v1
---

# HermesAgent Inspector Skill

## What this skill does

Docker 컨테이너(ClaudeCode, Antigravity 등) 내부에서 실행되는 AI 에이전트가 **네이티브 HermesAgent 인스턴스**의 공개 정보를 조회할 수 있게 합니다.

- 설치된 스킬 목록 조회
- 특정 스킬의 사용법(SKILL.md) 읽기
- 게이트웨이 상태 및 활성 에이전트 수 확인
- 공개 설정 (모델, 프로바이더, 툴셋 등) 조회

## When to use

- "어떤 HermesAgent 스킬이 설치되어 있는지 알고 싶을 때"
- "특정 스킬의 사용법을 알아야 할 때"
- "HermesAgent가 현재 어떤 모델을 사용하는지 확인할 때"
- "게이트웨이가 정상 동작 중인지 확인할 때"

---

## 환경 설정

컨테이너 내에서 Inspector URL을 환경 변수로 설정합니다:

```bash
export HERMES_INSPECTOR_URL="http://host.docker.internal:8646"
# 또는 docker-compose 네트워크 내에서:
export HERMES_INSPECTOR_URL="http://hermes-agent:8646"
```

---

## 스킬 목록 조회

### curl

```bash
curl "${HERMES_INSPECTOR_URL}/skills"
```

### Python

```python
import os
import requests

base_url = os.environ.get("HERMES_INSPECTOR_URL", "http://host.docker.internal:8646")

def list_skills():
    """설치된 스킬 목록 반환 (name, category, description)."""
    resp = requests.get(f"{base_url}/skills", timeout=5)
    resp.raise_for_status()
    return resp.json()

skills = list_skills()
for skill in skills:
    print(f"[{skill.get('category', 'unknown')}] {skill['name']}: {skill.get('description', '')}")
```

**응답 예시**
```json
[
  {
    "name": "blue-ribbon-nearby",
    "category": "food",
    "description": "Use when the user asks for nearby restaurants or 근처 맛집 and wants 블루리본 picks."
  },
  {
    "name": "korean-stock-search",
    "category": "finance",
    "description": "Search Korean stock market data."
  }
]
```

---

## 특정 스킬 내용 가져오기

### curl

```bash
curl "${HERMES_INSPECTOR_URL}/skills/blue-ribbon-nearby"
```

### Python

```python
import os
import requests

base_url = os.environ.get("HERMES_INSPECTOR_URL", "http://host.docker.internal:8646")

def get_skill_content(skill_name: str) -> str | None:
    """스킬의 SKILL.md 전문을 반환. 없으면 None."""
    resp = requests.get(f"{base_url}/skills/{skill_name}", timeout=5)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["content"]

content = get_skill_content("blue-ribbon-nearby")
if content:
    print(content)
else:
    print("Skill not found")
```

**응답 예시**
```json
{
  "name": "blue-ribbon-nearby",
  "content": "---\nname: blue-ribbon-nearby\ndescription: ...\n---\n\n# Blue Ribbon Nearby\n\n..."
}
```

---

## 게이트웨이 상태 확인

### curl

```bash
curl "${HERMES_INSPECTOR_URL}/health"
curl "${HERMES_INSPECTOR_URL}/status"
```

### Python

```python
import os
import requests

base_url = os.environ.get("HERMES_INSPECTOR_URL", "http://host.docker.internal:8646")

def check_gateway_health() -> dict:
    resp = requests.get(f"{base_url}/health", timeout=5)
    resp.raise_for_status()
    return resp.json()

def get_gateway_status() -> dict:
    resp = requests.get(f"{base_url}/status", timeout=5)
    resp.raise_for_status()
    return resp.json()

health = check_gateway_health()
print(f"Gateway PID: {health['pid']}, Uptime: {health['uptime_seconds']}s")

status = get_gateway_status()
print(f"Model: {status['model']}, State: {status['gateway_state']}, Active agents: {status['active_agents']}")
```

---

## 공개 설정 조회

```bash
curl "${HERMES_INSPECTOR_URL}/config/public"
```

```python
def get_public_config() -> dict:
    resp = requests.get(f"{base_url}/config/public", timeout=5)
    resp.raise_for_status()
    return resp.json()

config = get_public_config()
print(f"Default model: {config.get('model', {}).get('default')}")
print(f"Max turns: {config.get('agent', {}).get('max_turns')}")
```

---

## HERMES_INSPECTOR_URL 활용 패턴

### 연결 확인 후 스킬 동적 로딩

```python
import os
import requests
from functools import lru_cache

_INSPECTOR_URL = os.environ.get("HERMES_INSPECTOR_URL")

def inspector_available() -> bool:
    """Inspector 서버가 접근 가능한지 확인."""
    if not _INSPECTOR_URL:
        return False
    try:
        resp = requests.get(f"{_INSPECTOR_URL}/health", timeout=2)
        return resp.status_code == 200
    except requests.RequestException:
        return False

@lru_cache(maxsize=1)
def get_all_skills() -> list[dict]:
    """스킬 목록을 캐시해서 반환 (Inspector 미사용 시 빈 리스트)."""
    if not inspector_available():
        return []
    try:
        resp = requests.get(f"{_INSPECTOR_URL}/skills", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []

def find_skill_by_description(keyword: str) -> list[dict]:
    """description에 키워드가 포함된 스킬 검색."""
    return [
        s for s in get_all_skills()
        if keyword.lower() in (s.get("description") or "").lower()
    ]
```

### 에이전트 시스템 프롬프트에 스킬 목록 주입

```python
def build_skills_context() -> str:
    """사용 가능한 스킬 목록을 시스템 프롬프트용 텍스트로 반환."""
    skills = get_all_skills()
    if not skills:
        return ""
    lines = ["## Available HermesAgent Skills\n"]
    for skill in skills:
        name = skill.get("name", "unknown")
        desc = skill.get("description", "")
        cat = skill.get("category", "")
        cat_tag = f"[{cat}] " if cat else ""
        lines.append(f"- **{name}**: {cat_tag}{desc}")
    return "\n".join(lines)
```

---

## 보안 참고사항

Inspector API는 다음 정보를 **절대 노출하지 않습니다**:
- API 키, 토큰, 인증 정보
- 대화 세션 및 메모리
- `.env` 파일 내용
- config.yaml의 민감 키

따라서 `HERMES_INSPECTOR_URL`을 컨테이너 환경 변수에 노출하는 것은 보안상 안전합니다.
