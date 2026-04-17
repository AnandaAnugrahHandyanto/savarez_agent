from agent.recovery_policy import recovery_safe_lanes, validate_restore_targets


def test_recovery_safe_lanes_are_explicit():
    assert recovery_safe_lanes() == [
        "chain_of_shells",
        "file_anchors",
        "clerk_reset",
    ]


def test_restore_critical_targets_require_recovery_safe_lane():
    ok, flags = validate_restore_targets(["sqlite_memory", "wiki_compiled"], restore_critical=True)
    assert ok is False
    assert "missing_recovery_safe_lane" in flags

    ok, flags = validate_restore_targets(["sqlite_memory", "chain_of_shells"], restore_critical=True)
    assert ok is True
    assert flags == []
