from gateway.run import (
    classify_kanban_dispatch_health,
    resolve_kanban_capacity_policy,
)


def test_capacity_policy_target_raises_auto_decompose_without_capping() -> None:
    policy = resolve_kanban_capacity_policy({"target_active_workers": 10})

    assert policy["target_active_workers"] == 10
    assert policy["auto_decompose_per_tick"] == 10
    assert policy["max_spawn"] is None
    assert policy["max_in_progress"] is None


def test_capacity_policy_preserves_larger_explicit_auto_decompose() -> None:
    policy = resolve_kanban_capacity_policy(
        {"target_active_workers": 10, "auto_decompose_per_tick": 25}
    )

    assert policy["auto_decompose_per_tick"] == 25


def test_capacity_policy_uses_strictest_hard_cap_across_new_and_legacy_keys() -> None:
    policy = resolve_kanban_capacity_policy(
        {
            "target_active_workers": 10,
            "max_active_workers": 8,
            "max_spawn": 6,
            "max_in_progress": 7,
        }
    )

    assert policy["max_active_workers"] == 8
    assert policy["max_spawn"] == 6
    assert policy["max_in_progress"] == 6


def test_dispatch_health_distinguishes_feeder_starvation_from_profile_stuck() -> None:
    health = classify_kanban_dispatch_health(
        running=3,
        target_active_workers=10,
        ready_or_review=0,
        spawnable_ready_or_review=0,
        capacity_full=False,
        auto_decompose_enabled=True,
        triage_pending=9,
    )

    assert health == "feeder_starvation"


def test_dispatch_health_warns_only_for_spawnable_ready_work() -> None:
    assert (
        classify_kanban_dispatch_health(
            running=0,
            target_active_workers=10,
            ready_or_review=4,
            spawnable_ready_or_review=0,
            capacity_full=False,
            auto_decompose_enabled=True,
            triage_pending=0,
        )
        == "no_safe_or_no_ready_work"
    )
    assert (
        classify_kanban_dispatch_health(
            running=0,
            target_active_workers=10,
            ready_or_review=4,
            spawnable_ready_or_review=1,
            capacity_full=False,
            auto_decompose_enabled=True,
            triage_pending=0,
        )
        == "spawnable_ready_queue_stuck"
    )


def test_dispatch_health_capacity_full_is_not_stuck() -> None:
    health = classify_kanban_dispatch_health(
        running=10,
        target_active_workers=10,
        ready_or_review=4,
        spawnable_ready_or_review=2,
        capacity_full=True,
        auto_decompose_enabled=True,
        triage_pending=0,
    )

    assert health == "capacity_full"
