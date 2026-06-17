"""Tool output hashing and deduplication logic for Context Pager.

This module is responsible for:
1. Hashing tool output content using SHA-256 (stdlib, no extra deps)
2. Detecting duplicate tool outputs across turns
3. Generating stub messages for duplicates
4. Merging adjacent redundant turns

All functions are pure — they accept data and return transformed data,
with no I/O or side effects.  Callers (engine.py, store.py) handle I/O.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def hash_tool_content(content: Any) -> str:
    """Return a SHA-256 hex digest of tool output content.

    Handles both string and dict content (some hosts return JSON-like
    tool output as dicts).  Empty content produces a well-known hash.
    """
    if isinstance(content, (dict, list)):
        import json
        raw = json.dumps(content, sort_keys=True, ensure_ascii=False)
    elif content is None:
        raw = ""
    else:
        raw = str(content)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Turn extraction
# ---------------------------------------------------------------------------


def extract_turns(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Group messages into logical turns and annotate with hashes.

    A turn = sequence starting with user, followed by assistant (possibly
    with tool_calls), followed by zero or more tool messages.

    Returns augmented messages with a ``_turn_index`` and ``_tool_hashes``
    annotation added (for internal use; stripped before returning).
    Only messages with content worth hashing get annotations.
    """
    turns: List[Dict[str, Any]] = []
    current_turn: List[Dict[str, Any]] = []
    turn_idx = 0

    # system prompt is turn -1, always preserved
    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            msg_copy = dict(msg)
            msg_copy["_turn_index"] = -1
            msg_copy["_tool_hashes"] = []
            turns.append(msg_copy)
            continue

        role = msg.get("role", "")
        if role == "user":
            # start a new turn
            if current_turn:
                _annotate_turn(current_turn, turn_idx)
                turns.extend(current_turn)
                turn_idx += 1
            current_turn = [dict(msg)]
        elif role == "assistant":
            current_turn.append(dict(msg))
        elif role == "tool":
            current_turn.append(dict(msg))
        elif role == "function":
            current_turn.append(dict(msg))
        # skip other roles

    # last turn
    if current_turn:
        _annotate_turn(current_turn, turn_idx)
        turns.extend(current_turn)

    return turns


def _annotate_turn(turn_msgs: List[Dict[str, Any]], turn_idx: int) -> None:
    """Add _turn_index and _tool_hashes to all messages in a turn."""
    tool_hashes: List[str] = []
    for msg in turn_msgs:
        if msg.get("role") == "tool":
            h = hash_tool_content(msg.get("content", ""))
            tool_hashes.append(h)
    for msg in turn_msgs:
        msg["_turn_index"] = turn_idx
        msg["_tool_hashes"] = list(tool_hashes)


def strip_annotations(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove internal _turn_index and _tool_hashes keys."""
    result = []
    for msg in messages:
        clean = {k: v for k, v in msg.items() if not k.startswith("_")}
        result.append(clean)
    return result


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def compute_turn_signature(turn_msgs: List[Dict[str, Any]]) -> str:
    """Compute a stable signature for a turn based on its tool hashes."""
    hashes = []
    for msg in turn_msgs:
        if msg.get("role") == "tool":
            hashes.append(hash_tool_content(msg.get("content", "")))
    return "+".join(sorted(hashes)) if hashes else ""


def find_duplicate_tool_turns(
    annotated_messages: List[Dict[str, Any]],
    middle_start: int,
    middle_end: int,
    total_turns: int,
    hash_lookup_fn,
) -> List[Tuple[int, Dict[str, Any]]]:
    """Identify tool outputs in the middle window that duplicate more recent ones.

    Args:
        annotated_messages: Full message list with _turn_index annotations.
        middle_start: Index of first message in the middle window.
        middle_end: Index of last message in the middle window.
        total_turns: Total number of turns in the conversation.
        hash_lookup_fn: Callable(content_hash, older_than_turn) -> List[duplicates].

    Returns:
        A list of (msg_index, replacement_stub) tuples for messages to replace.
    """
    replacements: List[Tuple[int, Dict[str, Any]]] = []

    for i in range(middle_start, middle_end + 1):
        msg = annotated_messages[i]
        if msg.get("role") != "tool":
            continue

        content_hash = hash_tool_content(msg.get("content", ""))
        msg_turn: int = msg.get("_turn_index") or 0

        # Look for more recent occurrences of the same hash
        dups = hash_lookup_fn(content_hash, msg_turn)
        if dups:
            # Found a more recent occurrence — replace this one with a stub
            latest = dups[-1]  # closest more-recent duplicate
            stub = {
                "role": "tool",
                "content": f"[repeated output — same as turn {latest['turn_index']}]",
                "tool_call_id": msg.get("tool_call_id", ""),
                "name": msg.get("name", ""),
                "_deduped": True,
            }
            replacements.append((i, stub))

    return replacements


def merge_adjacent_turns(
    annotated_messages: List[Dict[str, Any]],
    middle_start: int,
    middle_end: int,
) -> List[Dict[str, Any]]:
    """Merge adjacent turns in the middle window that have identical tool signatures.

    Returns the (possibly shorter) message list for the middle window section.
    """
    if middle_start > middle_end:
        return []

    # Collect turn groups in the middle window
    turn_groups: List[List[Dict[str, Any]]] = []
    current_group: List[Dict[str, Any]] = []
    current_turn_idx = None

    for i in range(middle_start, middle_end + 1):
        msg = annotated_messages[i]
        ti = msg.get("_turn_index", -1)
        if ti != current_turn_idx:
            if current_group:
                turn_groups.append(current_group)
            current_group = [msg]
            current_turn_idx = ti
        else:
            current_group.append(msg)
    if current_group:
        turn_groups.append(current_group)

    if len(turn_groups) < 2:
        # Nothing to merge
        result = []
        for g in turn_groups:
            result.extend(g)
        return result

    # Build signatures
    sigs = [compute_turn_signature(g) for g in turn_groups]

    # Merge adjacent groups with same signature
    merged_groups: List[List[Dict[str, Any]]] = []
    i = 0
    while i < len(turn_groups):
        if (
            i + 1 < len(turn_groups)
            and sigs[i]
            and sigs[i] == sigs[i + 1]
        ):
            # Merge: keep user from first, assistant from last, tools deduped
            merged = _merge_two_turns(turn_groups[i], turn_groups[i + 1])
            merged_groups.append(merged)
            i += 2
        else:
            merged_groups.append(turn_groups[i])
            i += 1

    result = []
    for g in merged_groups:
        result.extend(g)
    return result


def _merge_two_turns(
    turn_a: List[Dict[str, Any]],
    turn_b: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge two adjacent turns with identical tool output signatures.

    Keeps: user from turn_a, assistant from turn_b, tool messages deduped.
    """
    result: List[Dict[str, Any]] = []

    # User message from first turn
    for msg in turn_a:
        if msg.get("role") == "user":
            result.append(msg)
            break

    # Assistant from second turn
    for msg in turn_b:
        if msg.get("role") == "assistant":
            result.append(msg)
            break

    # Tool messages: deduplicated set from both turns, keeping turn_b's versions
    seen_hashes: set = set()
    for msg in turn_b:
        if msg.get("role") == "tool":
            h = hash_tool_content(msg.get("content", ""))
            if h not in seen_hashes or msg.get("_deduped"):
                result.append(msg)
                seen_hashes.add(h)
    for msg in turn_a:
        if msg.get("role") == "tool":
            h = hash_tool_content(msg.get("content", ""))
            if h not in seen_hashes:
                result.append(msg)
                seen_hashes.add(h)
            elif msg.get("_deduped"):
                result.append(msg)

    return result


# ---------------------------------------------------------------------------
# Role alternation validation
# ---------------------------------------------------------------------------


def validate_role_alternation(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure no two consecutive messages have the same role.

    If two same-role messages appear consecutively, inject a minimal
    filler message to maintain alternation.  This prevents API rejections.
    """
    if not messages:
        return messages

    result = [messages[0]]
    for msg in messages[1:]:
        last_role = result[-1].get("role", "")
        this_role = msg.get("role", "")

        if this_role == last_role and this_role in ("user", "assistant"):
            # Inject an empty assistant message as a separator
            result.append({
                "role": "assistant" if this_role == "user" else "user",
                "content": "",
            })

        result.append(msg)

    return result


# ---------------------------------------------------------------------------
# High-level compress operation
# ---------------------------------------------------------------------------


def apply_dedup_compression(
    messages: List[Dict[str, Any]],
    protect_first_n: int,
    protect_last_n: int,
    hash_lookup_fn,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply dedup-based compression to message list.

    Args:
        messages: Full message list (raw dicts).
        protect_first_n: Number of initial non-system turns to protect.
        protect_last_n: Number of final turns to protect.
        hash_lookup_fn: Callable(hash, older_than_turn) -> list of dup dicts.

    Returns:
        Tuple of (compressed_messages, original_middle_turns_for_archive).
        The compressed messages are clean (no annotations).
        The original middle turns are returned for optional OV archival.
    """
    if not messages:
        return [], []

    # Annotate
    annotated = extract_turns(messages)

    # System prompt is at index 0, turn -1
    system_msgs = [m for m in annotated if m.get("_turn_index") == -1]
    non_system = [m for m in annotated if m.get("_turn_index") >= 0]

    if not non_system:
        return strip_annotations(annotated), []

    # Compute actual turn count (not message count — critical bug fix)
    try:
        max_turn = max(m.get("_turn_index", -1) for m in non_system)
        total_turns = max_turn + 1 if max_turn >= 0 else 0
    except ValueError:
        total_turns = 0

    # Cap protection in terms of turns, not messages
    first_protected_turns = min(protect_first_n, total_turns)
    last_protected_turns = min(
        protect_last_n,
        max(0, total_turns - first_protected_turns),
    )

    # Find middle window message indices
    head_count = len(system_msgs)
    if first_protected_turns > 0:
        first_head_msgs = _count_msgs_for_turns(
            non_system, 0, first_protected_turns - 1
        )
    else:
        first_head_msgs = 0

    if last_protected_turns > 0:
        tail_start_from_end = _count_msgs_for_turns(
            non_system,
            total_turns - last_protected_turns,
            total_turns - 1,
        )
    else:
        tail_start_from_end = 0

    total_non_system_msgs = len(non_system)
    tail_start_idx = total_non_system_msgs - tail_start_from_end

    middle_start = head_count + first_head_msgs
    middle_end = head_count + tail_start_idx - 1

    if middle_start > middle_end:
        # Nothing compressible
        return strip_annotations(annotated), []

    # Save original middle for archiving
    middle_originals = list(annotated[middle_start:middle_end + 1])

    # Step 1: Apply dedup replacements
    replacements = find_duplicate_tool_turns(
        annotated, middle_start, middle_end,
        len([m for m in non_system if m.get("_turn_index") >= 0]),
        hash_lookup_fn,
    )
    for msg_idx, stub in replacements:
        annotated[msg_idx] = stub

    # Step 2: Merge adjacent redundant turns
    merged_middle = merge_adjacent_turns(
        annotated, middle_start, middle_end,
    )

    # Step 3: Rebuild full message list
    result = (
        system_msgs
        + annotated[head_count:head_count + first_head_msgs]
        + merged_middle
        + annotated[head_count + tail_start_idx:]
    )

    # Step 4: Validate alternation
    result = validate_role_alternation(result)

    # Step 5: Strip annotations
    result = strip_annotations(result)
    middle_originals_clean = strip_annotations(middle_originals)

    return result, middle_originals_clean


def _count_msgs_for_turns(
    msgs: List[Dict[str, Any]], start_turn: int, end_turn: int
) -> int:
    """Count how many messages belong to turn indices [start_turn, end_turn]."""
    count = 0
    for m in msgs:
        ti: int = m.get("_turn_index") or 0
        if start_turn <= ti <= end_turn:
            count += 1
    return count
