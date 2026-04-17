from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from hermes_constants import get_hermes_home

from agent.memory_event import MemoryEvent
from agent.recovery_policy import validate_restore_targets


class WriteCompiler:
    def __init__(self, hermes_home: Path | None = None):
        self.hermes_home = Path(hermes_home or get_hermes_home())

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _event_dirs(self) -> Dict[str, Path]:
        return {
            "control_plane": self.hermes_home / "memory" / "control-plane-events",
            "chain_of_shells": self.hermes_home / "memory" / "chain-of-shells" / "control-plane-events",
            "file_anchors": self.hermes_home / "memory" / "file-anchors" / "control-plane-events",
            "state": self.hermes_home / "state",
        }

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _default_target_lanes(self, *, restore_critical: bool) -> list[str]:
        lanes = ["sqlite_memory", "wiki_compiled"]
        if restore_critical:
            lanes.extend(["chain_of_shells", "file_anchors"])
        return lanes

    def compile_memory_write(
        self,
        *,
        action: str,
        target: str,
        content: str,
        store_result: Dict[str, Any],
        kind: str = "lesson",
        scope: str = "global",
        scope_value: str | None = None,
        source: str = "manual",
        restore_critical: bool = False,
        provenance_ref: str = "",
        target_lanes: Optional[Iterable[str]] = None,
    ) -> MemoryEvent:
        lanes = list(target_lanes or self._default_target_lanes(restore_critical=restore_critical))
        ok, flags = validate_restore_targets(lanes, restore_critical=restore_critical)
        event_id = f"mem-{uuid.uuid4().hex[:12]}"
        entry = store_result.get("entry") or {}
        payload_base = {
            "event_id": event_id,
            "action": action,
            "target": target,
            "content": content,
            "source_lane": "sqlite_memory",
            "target_lanes": lanes,
            "scope": scope,
            "scope_value": scope_value,
            "kind": kind,
            "restore_critical": restore_critical,
            "provenance_ref": provenance_ref,
            "entry_id": entry.get("id"),
            "supersedes_entry_id": entry.get("supersedes_id"),
            "created_at": self._now(),
            "flags": flags[:],
        }
        status = {"sqlite_memory": "written", "wiki_compiled": "mirrored"}
        results: Dict[str, Any] = {}

        dirs = self._event_dirs()
        control_plane_path = dirs["control_plane"] / f"{event_id}.json"
        results["control_plane"] = {"path": str(control_plane_path)}

        if restore_critical and ok:
            for lane_name in ("chain_of_shells", "file_anchors"):
                if lane_name in lanes:
                    lane_path = dirs[lane_name] / f"{event_id}.json"
                    status[lane_name] = "written"
                    results[lane_name] = {"path": str(lane_path)}
        elif restore_critical:
            for lane_name in ("chain_of_shells", "file_anchors"):
                if lane_name in lanes:
                    status[lane_name] = "skipped"

        event = MemoryEvent(
            materialization_status=status,
            materialization_results=results,
            **payload_base,
        )
        event_payload = event.to_dict()
        self._write_json(control_plane_path, event_payload)
        if restore_critical and ok:
            for lane_name in ("chain_of_shells", "file_anchors"):
                lane_meta = results.get(lane_name)
                if lane_meta:
                    self._write_json(Path(lane_meta["path"]), event_payload)
        self._write_json(dirs["state"] / "last_memory_event.json", event_payload)
        return event
