"""hermes webhook — CLI에서 동적 웹훅 구독을 관리.

사용법:
    hermes webhook subscribe <name> [options]
    hermes webhook list
    hermes webhook remove <name>
    hermes webhook test <name> [--payload '{"key": "value"}']

구독 정보는 ~/.hermes/webhook_subscriptions.json에 저장되며,
게이트웨이를 재시작하지 않아도 webhook adapter가 즉시 다시 불러옵니다.
"""

import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Dict

from hermes_constants import display_hermes_home


_SUBSCRIPTIONS_FILENAME = "webhook_subscriptions.json"


def _hermes_home() -> Path:
    from hermes_constants import get_hermes_home
    return get_hermes_home()


def _subscriptions_path() -> Path:
    return _hermes_home() / _SUBSCRIPTIONS_FILENAME


def _load_subscriptions() -> Dict[str, dict]:
    path = _subscriptions_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_subscriptions(subs: Dict[str, dict]) -> None:
    path = _subscriptions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(subs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(str(tmp_path), str(path))


def _get_webhook_config() -> dict:
    """Load webhook platform config. Returns {} if not configured."""
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        return cfg.get("platforms", {}).get("webhook", {})
    except Exception:
        return {}


def _is_webhook_enabled() -> bool:
    return bool(_get_webhook_config().get("enabled"))


def _get_webhook_base_url() -> str:
    wh = _get_webhook_config().get("extra", {})
    host = wh.get("host", "0.0.0.0")
    port = wh.get("port", 8644)
    display_host = "localhost" if host == "0.0.0.0" else host
    return f"http://{display_host}:{port}"


def _setup_hint() -> str:
    _dhh = display_hermes_home()
    return f"""
  Webhook 플랫폼이 활성화되어 있지 않아요. 설정 방법:

  1. 게이트웨이 설정 마법사 실행:
     hermes gateway setup

  2. 또는 {_dhh}/config.yaml에 직접 추가:
     platforms:
       webhook:
         enabled: true
         extra:
           host: "0.0.0.0"
           port: 8644
           secret: "your-global-hmac-secret"

  3. 또는 {_dhh}/.env에 환경 변수 설정:
     WEBHOOK_ENABLED=true
     WEBHOOK_PORT=8644
     WEBHOOK_SECRET=your-g...cret

  그다음 게이트웨이 시작: hermes gateway run
"""


def _require_webhook_enabled() -> bool:
    """Check webhook is enabled. Print setup guide and return False if not."""
    if _is_webhook_enabled():
        return True
    print(_setup_hint())
    return False


def webhook_command(args):
    """Entry point for 'hermes webhook' subcommand."""
    sub = getattr(args, "webhook_action", None)

    if not sub:
        print("사용법: hermes webhook {subscribe|list|remove|test}")
        print("자세한 내용은 'hermes webhook --help'를 실행하세요.")
        return

    if not _require_webhook_enabled():
        return

    if sub in ("subscribe", "add"):
        _cmd_subscribe(args)
    elif sub in ("list", "ls"):
        _cmd_list(args)
    elif sub in ("remove", "rm"):
        _cmd_remove(args)
    elif sub == "test":
        _cmd_test(args)


def _cmd_subscribe(args):
    name = args.name.strip().lower().replace(" ", "-")
    if not re.match(r'^[a-z0-9][a-z0-9_-]*$', name):
        print(f"오류: 이름 '{name}' 이(가) 올바르지 않아요. 소문자 영숫자와 하이픈/밑줄만 사용해 주세요.")
        return

    subs = _load_subscriptions()
    is_update = name in subs

    secret = args.secret or secrets.token_urlsafe(32)
    events = [e.strip() for e in args.events.split(",")] if args.events else []

    route = {
        "description": args.description or f"에이전트가 만든 구독: {name}",
        "events": events,
        "secret": secret,
        "prompt": args.prompt or "",
        "skills": [s.strip() for s in args.skills.split(",")] if args.skills else [],
        "deliver": args.deliver or "log",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if args.deliver_chat_id:
        route["deliver_extra"] = {"chat_id": args.deliver_chat_id}

    subs[name] = route
    _save_subscriptions(subs)

    base_url = _get_webhook_base_url()
    status = "업데이트됨" if is_update else "생성됨"

    print(f"\n  {status} 웹훅 구독: {name}")
    print(f"  URL:    {base_url}/webhooks/{name}")
    print(f"  Secret: {secret}")
    if events:
        print(f"  이벤트: {', '.join(events)}")
    else:
        print("  이벤트: (전체)")
    print(f"  전달:   {route['deliver']}")
    if route.get("prompt"):
        prompt_preview = route["prompt"][:80] + ("..." if len(route["prompt"]) > 80 else "")
        print(f"  프롬프트: {prompt_preview}")
    print(f"\n  서비스가 위 URL로 POST를 보내도록 설정하세요.")
    print(f"  HMAC-SHA256 서명 검증에는 위 secret을 사용하세요.")
    print(f"  이벤트를 받으려면 게이트웨이가 실행 중이어야 해요(hermes gateway run).\n")


def _cmd_list(args):
    subs = _load_subscriptions()
    if not subs:
        print("  동적 웹훅 구독이 없어요.")
        print("  만들려면: hermes webhook subscribe <name>")
        return

    base_url = _get_webhook_base_url()
    print(f"\n  웹훅 구독 {len(subs)}개:\n")
    for name, route in subs.items():
        events = ", ".join(route.get("events", [])) or "(전체)"
        deliver = route.get("deliver", "log")
        desc = route.get("description", "")
        print(f"  ◆ {name}")
        if desc:
            print(f"    {desc}")
        print(f"    URL:     {base_url}/webhooks/{name}")
        print(f"    이벤트:  {events}")
        print(f"    전달:    {deliver}")
        print()


def _cmd_remove(args):
    name = args.name.strip().lower()
    subs = _load_subscriptions()

    if name not in subs:
        print(f"  '{name}' 이름의 구독이 없어요.")
        print("  참고: config.yaml의 정적 라우트는 여기서 제거할 수 없어요.")
        return

    del subs[name]
    _save_subscriptions(subs)
    print(f"  웹훅 구독을 제거했어요: {name}")


def _cmd_test(args):
    """Send a test POST to a webhook route."""
    name = args.name.strip().lower()
    subs = _load_subscriptions()

    if name not in subs:
        print(f"  '{name}' 이름의 구독이 없어요.")
        return

    route = subs[name]
    secret = route.get("secret", "")
    base_url = _get_webhook_base_url()
    url = f"{base_url}/webhooks/{name}"

    payload = args.payload or '{"test": true, "event_type": "test", "message": "hermes webhook test에서 보낸 인사"}'

    import hmac
    import hashlib
    sig = "sha256=" + hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    print(f"  테스트 POST를 전송하는 중: {url}")
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            data=payload.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "test",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            print(f"  응답 ({resp.status}): {body}")
    except Exception as e:
        print(f"  오류: {e}")
        print("  게이트웨이가 실행 중인가요? (hermes gateway run)")
