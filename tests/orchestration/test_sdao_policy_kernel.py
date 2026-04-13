from agent.orchestration_policy import decide_orchestration_mode


def test_simple_task_defaults_to_solo():
    assert decide_orchestration_mode(
        task_count_estimate=1,
        has_dependencies=False,
        complexity="simple",
        subtasks_independent=False,
        explicit_no_subagents=False,
    ) == "solo"


def test_complex_dependent_work_prefers_sequential():
    assert decide_orchestration_mode(
        task_count_estimate=1,
        has_dependencies=True,
        complexity="complex",
        subtasks_independent=False,
        explicit_no_subagents=False,
    ) == "sequential"


def test_complex_independent_multi_task_work_allows_parallel():
    assert decide_orchestration_mode(
        task_count_estimate=3,
        has_dependencies=False,
        complexity="complex",
        subtasks_independent=True,
        explicit_no_subagents=False,
    ) == "parallel"


def test_ambiguous_task_prefers_solo():
    assert decide_orchestration_mode(
        task_count_estimate=2,
        has_dependencies=False,
        complexity="medium",
        subtasks_independent=None,
        explicit_no_subagents=False,
    ) == "solo"


def test_explicit_no_subagents_forces_solo():
    assert decide_orchestration_mode(
        task_count_estimate=3,
        has_dependencies=False,
        complexity="complex",
        subtasks_independent=True,
        explicit_no_subagents=True,
    ) == "solo"


def test_dependency_conflict_blocks_parallel():
    assert decide_orchestration_mode(
        task_count_estimate=3,
        has_dependencies=True,
        complexity="complex",
        subtasks_independent=True,
        explicit_no_subagents=False,
    ) == "sequential"
