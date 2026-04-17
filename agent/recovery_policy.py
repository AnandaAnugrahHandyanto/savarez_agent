from __future__ import annotations

from typing import Iterable, List, Tuple

from agent.memory_lanes import get_lane, list_lanes


def recovery_safe_lanes() -> List[str]:
    return ["chain_of_shells", "file_anchors", "clerk_reset"]


def validate_restore_targets(target_lanes: Iterable[str], *, restore_critical: bool) -> Tuple[bool, List[str]]:
    if not restore_critical:
        return True, []
    lanes = list(target_lanes)
    safe = {lane for lane in lanes if get_lane(lane).recovery_safe}
    if safe:
        return True, []
    return False, ["missing_recovery_safe_lane"]
