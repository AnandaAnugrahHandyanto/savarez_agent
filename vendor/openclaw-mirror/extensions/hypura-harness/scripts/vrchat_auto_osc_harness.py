"""VRChat Auto OSC module for Hypura Harness — EVOLVED (v3.0 RTX Edition).

自動OSCメッセージ送受信 + GPU/RAM監視 + システム情報通知。
VRChat起動感知 → おかえりメッセージ + PC状態通知 → 定期ステータス更新。
"""
import asyncio
import logging
import random
import threading
import time
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_INTERVAL = 300  # 5 minutes
DEFAULT_SYSTEM_INTERVAL = 60  # 1 minute for system info updates

# Startup messages (with system info)
STARTUP_MESSAGES = [
    {"text": "おかえり！はくあだよ～", "emotion": "happy", "send_system": True},
    {"text": "おかえりなさい！PCの状況チェックするね", "emotion": "neutral", "send_system": True},
    {"text": "はくあだよ～！元気？", "emotion": "happy", "send_system": False},
    {"text": "おかえり！システム状況を送っておくね", "emotion": "curious", "send_system": True},
]

# Periodic system info messages
SYSTEM_MESSAGES = [
    {"text": "現在のPC状況を送るね", "emotion": "neutral"},
    {"text": "システムチェック！", "emotion": "happy"},
    {"text": "PCの状態はどうかな？", "emotion": "curious"},
    {"text": "パフォーマンス状況を見てみる", "emotion": "neutral"},
    {"text": "GPUとメモリの様子をお届け", "emotion": "excited"},
]

# Light periodic messages (less frequent, no system info)
PERIODIC_MESSAGES = [
    {"text": "はくあだよ～！何か手伝いましょうか？", "emotion": "neutral", "sfx": True},
    {"text": "VRChat楽しいね！", "emotion": "happy", "sfx": True},
    {"text": "今日はどんなことする？", "emotion": "curious", "sfx": True},
    {"text": "一緒にもっと遊ぼう！", "emotion": "excited", "sfx": True},
]


class VRChatAutoOSC:
    """Manages automatic OSC messages for VRChat with system monitoring."""

    def __init__(
        self,
        osc_controller,
        voicevox_sequencer=None,
        interval: int = DEFAULT_INTERVAL,
        system_interval: int = DEFAULT_SYSTEM_INTERVAL,
    ):
        self.osc = osc_controller
        self.voicevox = voicevox_sequencer
        self.interval = interval
        self.system_interval = system_interval
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._sender_thread: threading.Thread | None = None
        self._system_thread: threading.Thread | None = None
        self._vrchat_was_running = False
        self._message_index = 0
        self._system_message_index = 0
        self._consecutive_errors = 0
        self._max_errors = 3

    def is_vrchat_running(self) -> bool:
        """Check if VRChat.exe is running."""
        try:
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] == "VRChat.exe":
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False

    def get_system_info(self) -> dict[str, Any]:
        """Get current system info (GPU/RAM). Delegates to osc controller."""
        try:
            return self.osc.get_system_info()
        except Exception as e:
            logger.warning(f"System info failed: {e}")
            return {}

    def send_startup_message(self) -> bool:
        """Send startup message + system info when VRChat starts."""
        try:
            msg = random.choice(STARTUP_MESSAGES)
            self.osc.send_chatbox(msg["text"], immediate=True, sfx=True)
            self.osc.apply_emotion(msg["emotion"])

            if msg.get("send_system", True):
                time.sleep(0.5)  # Small delay between greeting and system info
                sys_msg = self.osc.format_system_message()
                self.osc.send_chatbox(sys_msg, immediate=True, sfx=False)

            if self.voicevox:
                try:
                    asyncio.create_task(
                        self.voicevox.speak(msg["text"], emotion=msg["emotion"], speaker=8)
                    )
                except Exception as e:
                    logger.warning(f"VoiceVox startup message failed: {e}")

            self._consecutive_errors = 0
            logger.info(f"Startup message sent: {msg['text']}")
            return True
        except Exception as e:
            self._consecutive_errors += 1
            logger.error(f"Startup message failed ({self._consecutive_errors}/{self._max_errors}): {e}")
            return False

    def send_system_info_message(self) -> bool:
        """Send periodic system info (GPU/RAM) while VRChat is running."""
        try:
            msg = random.choice(SYSTEM_MESSAGES)
            self.osc.apply_emotion(msg["emotion"])

            time.sleep(0.3)
            sys_msg = self.osc.format_system_message()
            self.osc.send_chatbox(sys_msg, immediate=True, sfx=False)

            self._consecutive_errors = 0
            logger.info(f"System info sent: {sys_msg[:60]}...")
            return True
        except Exception as e:
            self._consecutive_errors += 1
            logger.error(f"System info failed ({self._consecutive_errors}/{self._max_errors}): {e}")
            return False

    def send_periodic_message(self) -> bool:
        """Send periodic light message while VRChat is running."""
        try:
            msg = PERIODIC_MESSAGES[self._message_index % len(PERIODIC_MESSAGES)]
            self.osc.send_chatbox(msg["text"], immediate=True, sfx=msg.get("sfx", True))
            self.osc.apply_emotion(msg["emotion"])

            if self.voicevox:
                try:
                    asyncio.create_task(
                        self.voicevox.speak(msg["text"], emotion=msg["emotion"], speaker=8)
                    )
                except Exception as e:
                    logger.warning(f"VoiceVox periodic message failed: {e}")

            self._message_index += 1
            logger.info(f"Periodic message sent: {msg['text']}")
            return True
        except Exception as e:
            self._consecutive_errors += 1
            logger.error(f"Periodic message failed ({self._consecutive_errors}/{self._max_errors}): {e}")
            return False

    def _monitor_loop(self):
        """Monitor VRChat status and send startup message on start."""
        while self._running:
            try:
                is_running = self.is_vrchat_running()

                if is_running and not self._vrchat_was_running:
                    logger.info("VRChat detected — sending startup message")
                    self.send_startup_message()

                self._vrchat_was_running = is_running
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
            time.sleep(5)

    def _sender_loop(self):
        """Send periodic light messages while VRChat is running."""
        while self._running:
            try:
                if self._vrchat_was_running:
                    self.send_periodic_message()
            except Exception as e:
                logger.error(f"Sender loop error: {e}")
            time.sleep(self.interval)

    def _system_loop(self):
        """Send periodic system info while VRChat is running."""
        while self._running:
            try:
                if self._vrchat_was_running:
                    self.send_system_info_message()
            except Exception as e:
                logger.error(f"System loop error: {e}")
            time.sleep(self.system_interval)

    def start(self) -> dict[str, Any]:
        """Start the auto OSC service."""
        if self._running:
            logger.warning("Auto OSC already running")
            return {"success": False, "error": "Already running"}

        self._running = True
        self._vrchat_was_running = self.is_vrchat_running()
        self._consecutive_errors = 0

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()

        self._system_thread = threading.Thread(target=self._system_loop, daemon=True)
        self._system_thread.start()

        logger.info(
            f"VRChat Auto OSC started (interval={self.interval}s, "
            f"system_interval={self.system_interval}s)"
        )
        return {"success": True, "status": "started", "vrchat_active": self._vrchat_was_running}

    def stop(self) -> dict[str, Any]:
        """Stop the auto OSC service."""
        if not self._running:
            logger.warning("Auto OSC not running")
            return {"success": False, "error": "Not running"}

        self._running = False

        for thread, name in [
            (self._monitor_thread, "monitor"),
            (self._sender_thread, "sender"),
            (self._system_thread, "system"),
        ]:
            if thread:
                thread.join(timeout=3)
                logger.info(f"Stopped {name} thread")

        logger.info("VRChat Auto OSC stopped")
        return {"success": True, "status": "stopped"}

    def status(self) -> dict[str, Any]:
        """Get current status."""
        sys_info = {}
        try:
            sys_info = self.get_system_info()
        except Exception:
            pass
        return {
            "running": self._running,
            "vrchat_active": self._vrchat_was_running,
            "interval_sec": self.interval,
            "system_interval_sec": self.system_interval,
            "periodic_message_index": self._message_index,
            "system_message_index": self._system_message_index,
            "consecutive_errors": self._consecutive_errors,
            "max_errors": self._max_errors,
            "system": sys_info,
        }


# Global instance (will be initialized by harness_daemon.py)
auto_osc_instance: VRChatAutoOSC | None = None


def create_auto_osc(
    osc_controller,
    voicevox_sequencer=None,
    interval: int = DEFAULT_INTERVAL,
    system_interval: int = DEFAULT_SYSTEM_INTERVAL,
) -> VRChatAutoOSC:
    """Factory function to create VRChatAutoOSC instance."""
    return VRChatAutoOSC(osc_controller, voicevox_sequencer, interval, system_interval)
