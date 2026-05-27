from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .checks import aggregate_assertion_scores, evaluate_assertions
from .judges import aggregate_eval_scores, build_judge_prompt, evaluate_judge_output
from .schemas import EvalCase, EvalRunResult, JudgeResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_eval_case(
    case: EvalCase,
    *,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    save_trajectories: bool = False,
    max_turns: int = 90,
    judge_model: str | None = None,
    judge_provider: str | None = None,
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
    injected_agent: Any = None,
    injected_judge: Any = None,
) -> EvalRunResult:
    """Run a single eval case through Hermes and return a structured result."""
    if injected_agent is not None:
        agent = injected_agent
    else:
        from run_agent import AIAgent

        agent = AIAgent(
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            max_iterations=max_turns,
            enabled_toolsets=case.enabled_toolsets or None,
            save_trajectories=save_trajectories,
        )

    run_id = _generate_run_id()
    started_at = datetime.now(timezone.utc)
    ended_at = started_at
    error: str | None = None
    failed = False
    final_response = ""
    completed = False

    try:
        result = agent.run_conversation(
            case.prompt,
            system_message=case.context,
        )
    except Exception as exc:
        failed = True
        error = f"{type(exc).__name__}: {exc}"
    else:
        final_response = result.get("final_response", "") or ""
        completed = result.get("completed", False)
        if not completed:
            failed = True
    finally:
        ended_at = datetime.now(timezone.utc)

    elapsed_ms = int((ended_at - started_at).total_seconds() * 1000)

    metrics = _extract_session_metrics(agent)
    assertion_results = evaluate_assertions(
        case.assertions,
        final_response=final_response,
        tool_calls=metrics["tool_calls"],
    )
    det_score = aggregate_assertion_scores(case.assertions, assertion_results)

    judge_results = _run_judge_if_configured(
        case,
        final_response=final_response,
        judge_model=judge_model,
        judge_provider=judge_provider,
        judge_base_url=judge_base_url,
        judge_api_key=judge_api_key,
        injected_judge=injected_judge,
    )
    aggregate_scores = aggregate_eval_scores(
        deterministic_score=det_score.score,
        judge_results=judge_results,
    )

    agent_model = getattr(agent, "model", None)
    agent_provider = getattr(agent, "provider", None)

    return EvalRunResult(
        run_id=run_id,
        case_id=case.case_id,
        suite=case.suite,
        provider=agent_provider,
        model=agent_model,
        judge_provider=judge_provider if judge_results else None,
        judge_model=judge_model if judge_results else None,
        started_at=_iso_now(started_at),
        ended_at=_iso_now(ended_at),
        elapsed_ms=elapsed_ms,
        completed=completed,
        failed=failed,
        error=error,
        final_response=final_response,
        tool_calls=metrics["tool_calls"],
        input_tokens=metrics["input_tokens"],
        output_tokens=metrics["output_tokens"],
        cache_read_tokens=metrics["cache_read_tokens"],
        cache_write_tokens=metrics["cache_write_tokens"],
        estimated_cost_usd=metrics["estimated_cost_usd"],
        actual_cost_usd=metrics["actual_cost_usd"],
        assertions=assertion_results,
        judge_results=judge_results,
        aggregate_scores=aggregate_scores,
        labels={},
    )


def run_eval_suite(
    cases: list[EvalCase],
    *,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    save_trajectories: bool = False,
    max_turns: int = 90,
    judge_model: str | None = None,
    judge_provider: str | None = None,
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
    injected_judge: Any = None,
) -> list[EvalRunResult]:
    """Run multiple eval cases sequentially."""
    return [
        run_eval_case(
            case,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            save_trajectories=save_trajectories,
            max_turns=max_turns,
            judge_model=judge_model,
            judge_provider=judge_provider,
            judge_base_url=judge_base_url,
            judge_api_key=judge_api_key,
            injected_judge=injected_judge,
        )
        for case in cases
    ]


def build_result_from_components(
    case: EvalCase,
    *,
    final_response: str,
    completed: bool,
    failed: bool = False,
    error: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    actual_cost_usd: float | None = None,
    model: str | None = None,
    provider: str | None = None,
    judge_results: list[JudgeResult] | None = None,
    judge_model: str | None = None,
    judge_provider: str | None = None,
    efficiency_score: float | None = None,
    elapsed_ms: int = 0,
) -> EvalRunResult:
    """Construct an ``EvalRunResult`` from pre-extracted components."""
    tool_calls = tool_calls or []

    assertion_results = evaluate_assertions(
        case.assertions,
        final_response=final_response,
        tool_calls=tool_calls,
    )
    det_score = aggregate_assertion_scores(case.assertions, assertion_results)
    judge_results = judge_results or []
    aggregate_scores = aggregate_eval_scores(
        deterministic_score=det_score.score,
        judge_results=judge_results,
        efficiency_score=efficiency_score,
    )

    now = _iso_now(datetime.now(timezone.utc))
    return EvalRunResult(
        run_id=_generate_run_id(),
        case_id=case.case_id,
        suite=case.suite,
        provider=provider,
        model=model,
        judge_provider=judge_provider if judge_results else None,
        judge_model=judge_model if judge_results else None,
        started_at=now,
        ended_at=now,
        elapsed_ms=elapsed_ms,
        completed=completed,
        failed=failed,
        error=error,
        final_response=final_response,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        estimated_cost_usd=estimated_cost_usd,
        actual_cost_usd=actual_cost_usd,
        assertions=assertion_results,
        judge_results=judge_results,
        aggregate_scores=aggregate_scores,
        labels={},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_run_id() -> str:
    short = uuid.uuid4().hex[:12]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"run_{ts}_{short}"


def _iso_now(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_session_metrics(agent: Any) -> dict[str, Any]:
    """Pull token counts, cost, and tool-call names from the agent's session DB."""
    result: dict[str, Any] = {
        "tool_calls": [],
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "estimated_cost_usd": None,
        "actual_cost_usd": None,
    }

    try:
        session_db = getattr(agent, "_session_db", None)
        session_id = getattr(agent, "session_id", None)
        if session_db is None or session_id is None:
            return result

        session = session_db.get_session(session_id)
        if session:
            result["input_tokens"] = session.get("input_tokens")
            result["output_tokens"] = session.get("output_tokens")
            result["cache_read_tokens"] = session.get("cache_read_tokens")
            result["cache_write_tokens"] = session.get("cache_write_tokens")
            result["estimated_cost_usd"] = session.get("estimated_cost_usd")
            result["actual_cost_usd"] = session.get("actual_cost_usd")

        messages = session_db.get_messages(session_id)
        seen: set[str] = set()
        tool_calls_list: list[dict[str, Any]] = []
        for msg in messages:
            raw_tc = msg.get("tool_calls")
            if not raw_tc or not isinstance(raw_tc, list):
                continue
            for tc in raw_tc:
                func = tc.get("function", {})
                name = func.get("name", "") if isinstance(func, dict) else ""
                if not name:
                    name = tc.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    tool_calls_list.append({"name": name})
        result["tool_calls"] = tool_calls_list

    except Exception as exc:
        logger.warning("Failed to extract session metrics: %s", exc)

    return result


def _run_judge_if_configured(
    case: EvalCase,
    *,
    final_response: str,
    judge_model: str | None,
    judge_provider: str | None,
    judge_base_url: str | None,
    judge_api_key: str | None,
    injected_judge: Any = None,
) -> list[JudgeResult]:
    if not case.judge_dimensions or not final_response.strip():
        return []
    if injected_judge is None and not judge_model:
        return []

    prompt = build_judge_prompt(case, final_response=final_response)

    if injected_judge is not None:
        if callable(injected_judge):
            raw_output = injected_judge(case=case, final_response=final_response, prompt=prompt)
        else:
            judge_response = injected_judge.run_conversation(prompt)
            raw_output = (
                judge_response.get("final_response", "")
                if isinstance(judge_response, dict)
                else judge_response
            )
    else:
        from run_agent import AIAgent

        judge_agent_kwargs: dict[str, Any] = {
            "max_iterations": 8,
            "enabled_toolsets": [],
            "save_trajectories": False,
        }
        if judge_model is not None:
            judge_agent_kwargs["model"] = judge_model
        if judge_provider is not None:
            judge_agent_kwargs["provider"] = judge_provider
        if judge_base_url is not None:
            judge_agent_kwargs["base_url"] = judge_base_url
        if judge_api_key is not None:
            judge_agent_kwargs["api_key"] = judge_api_key

        judge_agent = AIAgent(**judge_agent_kwargs)
        judge_response = judge_agent.run_conversation(prompt)
        raw_output = (
            judge_response.get("final_response", "")
            if isinstance(judge_response, dict)
            else judge_response
        )

    if isinstance(raw_output, dict):
        judge_payload: str | dict[str, Any] = raw_output
    elif isinstance(raw_output, str):
        judge_payload = raw_output
    else:
        raise TypeError(f"unsupported judge output type: {type(raw_output).__name__}")

    return evaluate_judge_output(case, judge_payload)
