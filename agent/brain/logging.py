"""Brain trace logging — observability for routing decisions.

Logs every routing decision to daily-rotated JSONL files:
  routing_trace_YYYYMMDD.jsonl — full layer-by-layer trace
  fallbacks_YYYYMMDD.jsonl     — fallback events
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List

from agent.brain.types import LayerTrace

logger = logging.getLogger(__name__)


class BrainTraceLogger:
    """Async-safe routing trace logger to JSONL files.

    Survives write failures silently — logging is best-effort.
    Daily file rotation based on local date.
    """

    def __init__(self, log_dir: str = "~/.hermes/logs/brain/"):
        self._dir = Path(log_dir.replace("~", str(Path.home())))
        self._dir.mkdir(parents=True, exist_ok=True)
        self._today = datetime.now().strftime("%Y%m%d")
        self._trace_path = self._dir / f"routing_trace_{self._today}.jsonl"
        self._fallback_path = self._dir / f"fallbacks_{self._today}.jsonl"

    def _rotate(self):
        """Rotate files if date has changed."""
        today = datetime.now().strftime("%Y%m%d")
        if today != self._today:
            self._today = today
            self._trace_path = self._dir / f"routing_trace_{today}.jsonl"
            self._fallback_path = self._dir / f"fallbacks_{today}.jsonl"

    def log_trace(
        self,
        session_id: str,
        traces: List[LayerTrace],
        outcome: str = "success",
    ):
        """Write a full routing trace entry."""
        self._rotate()
        entry = {
            "ts": datetime.now().isoformat(),
            "session_id": session_id,
            "outcome": outcome,
            "layers": [
                {
                    "layer": t.layer,
                    "decision": t.decision,
                    "confidence": t.confidence,
                    "source": t.source,
                    "meta": t.meta,
                }
                for t in traces
            ],
        }
        try:
            with open(self._trace_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug("Trace log write failed: %s", e)

    def log_fallback(
        self,
        route: str,
        model: str,
        reason: str,
        success: bool,
    ):
        """Log a fallback event (primary failed, used alternative)."""
        self._rotate()
        entry = {
            "ts": datetime.now().isoformat(),
            "event": "fallback",
            "route": route,
            "model": model,
            "reason": reason,
            "success": success,
        }
        try:
            with open(self._fallback_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug("Fallback log write failed: %s", e)
