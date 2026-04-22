"""CLI entry — same logic as repo-root ``run_bridge.py`` (kept importable after pip install)."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_a, **_k):
        return False

from wechat_hermes import MessageEvent, PlatformConfig, WeixinAdapter, check_weixin_requirements


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_env() -> None:
    load_dotenv()
    root = _repo_root()
    for p in (Path.home() / ".hermes" / ".env", root / ".env"):
        if p.is_file():
            load_dotenv(p)


async def _llm_reply(user_text: str) -> str:
    from openai import OpenAI

    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_text}],
        max_tokens=2048,
    )
    return (r.choices[0].message.content or "").strip() or "（无回复）"


async def _async_main() -> None:
    _load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not check_weixin_requirements():
        print("Install: pip install -e '.[dev]'", file=sys.stderr)
        raise SystemExit(1)

    token = os.environ.get("WEIXIN_TOKEN", "").strip()
    acct = os.environ.get("WEIXIN_ACCOUNT_ID", "").strip()
    if not token or not acct:
        print("Set WEIXIN_TOKEN and WEIXIN_ACCOUNT_ID", file=sys.stderr)
        raise SystemExit(1)

    mode = os.environ.get("CHAT_MODE", "echo").strip().lower()
    if mode not in ("echo", "llm"):
        print("CHAT_MODE must be 'echo' or 'llm'", file=sys.stderr)
        raise SystemExit(1)
    if mode == "llm" and not os.environ.get("OPENAI_API_KEY", "").strip():
        print("CHAT_MODE=llm requires OPENAI_API_KEY", file=sys.stderr)
        raise SystemExit(1)

    cfg = PlatformConfig(enabled=True, token=token, extra={"account_id": acct})
    adapter = WeixinAdapter(cfg)

    async def handler(event: MessageEvent) -> str | None:
        text = (event.text or "").strip()
        media_note = ""
        if event.media_urls:
            media_note = f"\n（收到 {len(event.media_urls)} 个媒体文件，已缓存为本地路径）"
        if not text and not event.media_urls:
            return None
        if mode == "echo":
            return (text or "（空消息）") + media_note
        try:
            reply = await _llm_reply(text or "用户发送了图片/文件，请简短回复。")
            return reply + media_note if media_note else reply
        except Exception as exc:
            logging.exception("LLM failed: %s", exc)
            return f"⚠️ LLM 错误：{exc}"

    adapter.set_message_handler(handler)

    ok = await adapter.connect()
    if not ok:
        raise SystemExit("Weixin adapter failed to connect — check logs")

    logging.info("Bridge running — Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        await adapter.disconnect()


def main() -> None:
    asyncio.run(_async_main())
