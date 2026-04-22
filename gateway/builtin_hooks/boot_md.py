"""Built-in boot-md hook — run ~/.hermes/BOOT.md on gateway startup.

This hook is always registered. It silently skips if no BOOT.md exists.
To activate, create ``~/.hermes/BOOT.md`` with instructions for the
agent to execute on every gateway restart.

Example BOOT.md::

    # Startup Checklist

    1. Check if any cron jobs failed overnight
    2. Send a status update to Discord #general
    3. If there are errors in /opt/app/deploy.log, summarize them

The agent runs in a background thread so it doesn't block gateway
startup. If nothing needs attention, it replies with [SILENT] to
suppress delivery.
"""

import logging
import threading
import subprocess
import os

logger = logging.getLogger("hooks.boot-md")

from hermes_constants import get_hermes_home
HERMES_HOME = get_hermes_home()
BOOT_FILE = HERMES_HOME / "BOOT.md"
BOOT_NOTIFY_SCRIPT = HERMES_HOME / "send_boot_notification.py"


def _run_boot_notify() -> None:
    """直接调用Python脚本发送启动通知，不走AI agent。"""
    if not BOOT_NOTIFY_SCRIPT.exists():
        return
    try:
        result = subprocess.run(
            ["python3", str(BOOT_NOTIFY_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "HERMES_SESSION_PLATFORM": "feishu"},
        )
        if result.returncode == 0:
            logger.info("boot notify: notification sent successfully")
        else:
            logger.error("boot notify: script failed: %s", result.stderr.strip())
    except Exception as e:
        logger.error("boot notify: failed to run script: %s", e)


def _build_boot_prompt(content: str) -> str:
    """Wrap BOOT.md content in a system-level instruction."""
    return (
        "You are running a startup boot checklist. Follow the BOOT.md "
        "instructions below exactly.\n\n"
        "---\n"
        f"{content}\n"
        "---\n\n"
        "Execute each instruction. If you need to send a message to a "
        "platform, use the send_message tool.\n"
        "If nothing needs attention and there is nothing to report, "
        "reply with ONLY: [SILENT]"
    )


def _run_boot_agent(content: str) -> None:
    """Spawn a one-shot agent session to execute the boot instructions."""
    try:
        # Set HERMES_SESSION_PLATFORM so send_message's check_fn passes.
        # Without this, the check_fn sees no active gateway session and blocks
        # the tool even when the gateway IS running with a feishu adapter.
        os.environ.setdefault("HERMES_SESSION_PLATFORM", "feishu")

        from run_agent import AIAgent

        prompt = _build_boot_prompt(content)
        agent = AIAgent(
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            max_iterations=20,
        )
        result = agent.run_conversation(prompt)
        response = result.get("final_response", "")
        if response and "[SILENT]" not in response:
            logger.info("boot-md completed: %s", response[:200])
        else:
            logger.info("boot-md completed (nothing to report)")
    except Exception as e:
        logger.error("boot-md agent failed: %s", e)


async def handle(event_type: str, context: dict) -> None:
    """Gateway startup handler — run BOOT.md if it exists."""
    # 先用subprocess直接发通知，不走AI agent
    t1 = threading.Thread(target=_run_boot_notify, name="boot-notify", daemon=True)
    t1.start()

    if not BOOT_FILE.exists():
        return

    content = BOOT_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return

    logger.info("Running BOOT.md (%d chars)", len(content))

    # Run in a background thread so we don't block gateway startup.
    thread = threading.Thread(
        target=_run_boot_agent,
        args=(content,),
        name="boot-md",
        daemon=True,
    )
    thread.start()
