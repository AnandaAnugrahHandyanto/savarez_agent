#!/usr/bin/env python3
"""
Result Aggregator - Collecting and Merging Sub-Agent Results

Aggregates results from multiple sub-agents using various strategies:
- First complete (return first result)
- All must succeed (wait for all, fail on any failure)
- Majority/voting (aggregate by vote/consensus)
- Priority (use priority to break ties)
- Custom aggregation functions

Features:
- Configurable retry on failure
- Timeout handling
- Partial result collection
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AggregationStrategy(Enum):
    """
    Strategy for aggregating results from multiple sub-agents.
    """
    # Wait for all, combine all results
    ALL = "all"
    
    # Return first successful result
    FIRST_SUCCESS = "first_success"
    
    # Wait for majority (more than 50%)
    MAJORITY = "majority"
    
    # Voting/consensus among results
    VOTING = "voting"
    
    # Priority-based selection
    PRIORITY = "priority"
    
    # Best effort (collect what we can)
    BEST_EFFORT = "best_effort"
    
    # Custom aggregation function
    CUSTOM = "custom"


@dataclass
class AggregationResult:
    """
    The result of aggregating multiple sub-agent results.
    """
    success: bool
    strategy: AggregationStrategy
    
    # Aggregated output
    result: Any = None
    
    # Individual results
    results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Success/failure counts
    success_count: int = 0
    failure_count: int = 0
    
    # Errors encountered
    errors: List[str] = field(default_factory=list)
    
    # Timing
    duration_seconds: float = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "strategy": self.strategy.value,
            "result": self.result,
            "results": self.results,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


@dataclass
class AggregatorConfig:
    """Configuration for the ResultAggregator."""
    strategy: AggregationStrategy = AggregationStrategy.ALL
    timeout: float = 300.0  # Max seconds to wait
    min_success: int = 1     # Minimum successful results required
    retry_failed: bool = False
    max_retries: int = 2
    retry_delay: float = 5.0  # Seconds between retries
    
    # For VOTING strategy
    vote_threshold: float = 0.5  # 50% threshold for consensus
    
    # Custom aggregation function
    custom_aggregator: Optional[Callable[[List[Any]], Any]] = None


class ResultAggregator:
    """
    Aggregates results from multiple sub-agents.
    
    Supports various strategies for combining results and handles:
    - Timeout management
    - Retry logic
    - Partial success scenarios
    - Custom aggregation functions
    """
    
    def __init__(self, config: Optional[AggregatorConfig] = None):
        """
        Initialize the ResultAggregator.
        
        Args:
            config: AggregatorConfig for customization
        """
        self.config = config or AggregatorConfig()
        self._lock = None  # Will be initialized if needed
    
    async def aggregate(
        self,
        results: List[Dict[str, Any]],
        strategy: Optional[AggregationStrategy] = None,
        **kwargs,
    ) -> AggregationResult:
        """
        Aggregate results from sub-agents.
        
        Args:
            results: List of result dictionaries from sub-agents
            strategy: Override default aggregation strategy
            **kwargs: Additional config overrides
            
        Returns:
            AggregationResult with combined output
        """
        start_time = time.time()
        
        # Merge config with kwargs
        effective_strategy = strategy or self.config.strategy
        
        # Create effective config
        eff_config = AggregatorConfig(
            strategy=effective_strategy,
            timeout=kwargs.get("timeout", self.config.timeout),
            min_success=kwargs.get("min_success", self.config.min_success),
            retry_failed=kwargs.get("retry_failed", self.config.retry_failed),
            max_retries=kwargs.get("max_retries", self.config.max_retries),
            retry_delay=kwargs.get("retry_delay", self.config.retry_delay),
            custom_aggregator=kwargs.get("custom_aggregator", self.config.custom_aggregator),
        )
        
        # Separate successes and failures
        successes = [r for r in results if r.get("status") == "completed" or r.get("success")]
        failures = [r for r in results if r.get("status") not in ("completed", "success", None)]
        
        # Apply strategy
        if effective_strategy == AggregationStrategy.ALL:
            return await self._aggregate_all(
                results, successes, failures, start_time, eff_config
            )
        elif effective_strategy == AggregationStrategy.FIRST_SUCCESS:
            return await self._aggregate_first_success(
                results, successes, failures, start_time, eff_config
            )
        elif effective_strategy == AggregationStrategy.MAJORITY:
            return await self._aggregate_majority(
                results, successes, failures, start_time, eff_config
            )
        elif effective_strategy == AggregationStrategy.VOTING:
            return await self._aggregate_voting(
                results, successes, failures, start_time, eff_config
            )
        elif effective_strategy == AggregationStrategy.PRIORITY:
            return await self._aggregate_priority(
                results, successes, failures, start_time, eff_config
            )
        elif effective_strategy == AggregationStrategy.BEST_EFFORT:
            return await self._aggregate_best_effort(
                results, successes, failures, start_time, eff_config
            )
        elif effective_strategy == AggregationStrategy.CUSTOM:
            return await self._aggregate_custom(
                results, successes, failures, start_time, eff_config
            )
        else:
            raise ValueError(f"Unknown aggregation strategy: {effective_strategy}")
    
    async def _aggregate_all(
        self,
        results: List[Dict],
        successes: List[Dict],
        failures: List[Dict],
        start_time: float,
        config: AggregatorConfig,
    ) -> AggregationResult:
        """Aggregate all results."""
        duration = time.time() - start_time
        
        if failures and not config.retry_failed:
            return AggregationResult(
                success=False,
                strategy=AggregationStrategy.ALL,
                results=results,
                success_count=len(successes),
                failure_count=len(failures),
                errors=[f.get("error", "Unknown error") for f in failures],
                duration_seconds=duration,
            )
        
        # All must succeed
        if len(successes) < len(results) and len(successes) < config.min_success:
            return AggregationResult(
                success=False,
                strategy=AggregationStrategy.ALL,
                results=results,
                success_count=len(successes),
                failure_count=len(failures),
                errors=[f"Only {len(successes)}/{len(results)} succeeded" for f in failures],
                duration_seconds=duration,
            )
        
        # Combine all successful results
        combined = self._combine_results(successes)
        
        return AggregationResult(
            success=True,
            strategy=AggregationStrategy.ALL,
            result=combined,
            results=results,
            success_count=len(successes),
            failure_count=len(failures),
            duration_seconds=duration,
        )
    
    async def _aggregate_first_success(
        self,
        results: List[Dict],
        successes: List[Dict],
        failures: List[Dict],
        start_time: float,
        config: AggregatorConfig,
    ) -> AggregationResult:
        """Return first successful result."""
        duration = time.time() - start_time
        
        if successes:
            first = successes[0]
            return AggregationResult(
                success=True,
                strategy=AggregationStrategy.FIRST_SUCCESS,
                result=first.get("result") or first.get("final_response"),
                results=[first],
                success_count=1,
                failure_count=len(results) - 1,
                duration_seconds=duration,
                metadata={"first_result_task_id": first.get("task_id")},
            )
        
        return AggregationResult(
            success=False,
            strategy=AggregationStrategy.FIRST_SUCCESS,
            results=[],
            success_count=0,
            failure_count=len(results),
            errors=[f.get("error", "Unknown error") for f in failures],
            duration_seconds=duration,
        )
    
    async def _aggregate_majority(
        self,
        results: List[Dict],
        successes: List[Dict],
        failures: List[Dict],
        start_time: float,
        config: AggregatorConfig,
    ) -> AggregationResult:
        """Wait for majority (>50%) to succeed."""
        duration = time.time() - start_time
        total = len(results)
        majority = (total // 2) + 1
        
        if len(successes) >= majority:
            combined = self._combine_results(successes)
            return AggregationResult(
                success=True,
                strategy=AggregationStrategy.MAJORITY,
                result=combined,
                results=successes,
                success_count=len(successes),
                failure_count=len(failures),
                duration_seconds=duration,
            )
        
        return AggregationResult(
            success=False,
            strategy=AggregationStrategy.MAJORITY,
            results=results,
            success_count=len(successes),
            failure_count=len(failures),
            errors=[f"Only {len(successes)}/{majority} needed for majority" for f in failures],
            duration_seconds=duration,
        )
    
    async def _aggregate_voting(
        self,
        results: List[Dict],
        successes: List[Dict],
        failures: List[Dict],
        start_time: float,
        config: AggregatorConfig,
    ) -> AggregationResult:
        """Aggregate by voting/consensus."""
        duration = time.time() - start_time
        
        if not successes:
            return AggregationResult(
                success=False,
                strategy=AggregationStrategy.VOTING,
                results=[],
                success_count=0,
                failure_count=len(results),
                errors=["No successful results to vote on"],
                duration_seconds=duration,
            )
        
        # Count result frequencies
        result_votes: Dict[str, int] = {}
        result_items: Dict[str, Dict] = {}
        
        for r in successes:
            # Use a hashable key for the result
            result_val = r.get("result") or r.get("final_response") or ""
            result_key = str(result_val)[:100]  # Truncate for comparison
            
            result_votes[result_key] = result_votes.get(result_key, 0) + 1
            result_items[result_key] = r
        
        # Find consensus
        threshold = config.vote_threshold
        for key, count in result_votes.items():
            if count / len(successes) >= threshold:
                winner = result_items[key]
                return AggregationResult(
                    success=True,
                    strategy=AggregationStrategy.VOTING,
                    result=winner.get("result") or winner.get("final_response"),
                    results=successes,
                    success_count=len(successes),
                    failure_count=len(failures),
                    duration_seconds=duration,
                    metadata={"vote_count": count, "total_voters": len(successes)},
                )
        
        # No consensus - return most voted
        most_voted_key = max(result_votes.items(), key=lambda x: x[1])[0]
        most_voted = result_items[most_voted_key]
        
        return AggregationResult(
            success=True,
            strategy=AggregationStrategy.VOTING,
            result=most_voted.get("result") or most_voted.get("final_response"),
            results=successes,
            success_count=len(successes),
            failure_count=len(failures),
            duration_seconds=duration,
            metadata={
                "vote_count": result_votes[most_voted_key],
                "total_voters": len(successes),
                "consensus_reached": False,
            },
        )
    
    async def _aggregate_priority(
        self,
        results: List[Dict],
        successes: List[Dict],
        failures: List[Dict],
        start_time: float,
        config: AggregatorConfig,
    ) -> AggregationResult:
        """Select result based on priority."""
        duration = time.time() - start_time
        
        if not successes:
            return AggregationResult(
                success=False,
                strategy=AggregationStrategy.PRIORITY,
                results=[],
                success_count=0,
                failure_count=len(results),
                errors=["No successful results to select from"],
                duration_seconds=duration,
            )
        
        # Sort by priority (higher is better)
        def get_priority(r: Dict) -> int:
            return r.get("priority", r.get("task_priority", 0))
        
        successes.sort(key=get_priority, reverse=True)
        winner = successes[0]
        
        return AggregationResult(
            success=True,
            strategy=AggregationStrategy.PRIORITY,
            result=winner.get("result") or winner.get("final_response"),
            results=[winner],
            success_count=1,
            failure_count=len(results) - 1,
            duration_seconds=duration,
            metadata={"selected_task_id": winner.get("task_id"), "priority": get_priority(winner)},
        )
    
    async def _aggregate_best_effort(
        self,
        results: List[Dict],
        successes: List[Dict],
        failures: List[Dict],
        start_time: float,
        config: AggregatorConfig,
    ) -> AggregationResult:
        """Collect whatever results we can get."""
        duration = time.time() - start_time
        
        combined = self._combine_results(successes) if successes else None
        
        return AggregationResult(
            success=len(successes) >= config.min_success,
            strategy=AggregationStrategy.BEST_EFFORT,
            result=combined,
            results=results,
            success_count=len(successes),
            failure_count=len(failures),
            errors=[f.get("error") for f in failures if f.get("error")],
            duration_seconds=duration,
            metadata={"partial_success": len(successes) > 0 and len(successes) < len(results)},
        )
    
    async def _aggregate_custom(
        self,
        results: List[Dict],
        successes: List[Dict],
        failures: List[Dict],
        start_time: float,
        config: AggregatorConfig,
    ) -> AggregationResult:
        """Use custom aggregation function."""
        duration = time.time() - start_time
        
        if not config.custom_aggregator:
            return AggregationResult(
                success=False,
                strategy=AggregationStrategy.CUSTOM,
                results=results,
                success_count=len(successes),
                failure_count=len(failures),
                errors=["No custom aggregator function provided"],
                duration_seconds=duration,
            )
        
        try:
            custom_result = config.custom_aggregator(results)
            return AggregationResult(
                success=True,
                strategy=AggregationStrategy.CUSTOM,
                result=custom_result,
                results=results,
                success_count=len(successes),
                failure_count=len(failures),
                duration_seconds=duration,
            )
        except Exception as e:
            return AggregationResult(
                success=False,
                strategy=AggregationStrategy.CUSTOM,
                results=results,
                success_count=len(successes),
                failure_count=len(failures),
                errors=[str(e)],
                duration_seconds=duration,
            )
    
    def _combine_results(self, results: List[Dict]) -> Any:
        """
        Combine multiple results into a coherent output.
        
        Handles different result formats and merges them intelligently.
        """
        if not results:
            return None
        
        if len(results) == 1:
            return results[0].get("result") or results[0].get("final_response")
        
        # Check for common keys
        first = results[0]
        
        # If all have summaries, combine them
        if all("summary" in r for r in results):
            summaries = [r["summary"] for r in results]
            return self._combine_summaries(summaries)
        
        # If all have final_response (delegate_task format), combine
        if all("final_response" in r for r in results):
            responses = [r["final_response"] for r in results]
            return self._combine_summaries(responses)
        
        # If results are dicts with similar structure, merge them
        if all(isinstance(r, dict) for r in results):
            return self._merge_dict_results(results)
        
        # Fallback: return list of results
        return [r.get("result") or r.get("final_response") or r for r in results]
    
    def _combine_summaries(self, summaries: List[str]) -> str:
        """Combine text summaries from multiple agents."""
        combined = []
        for i, s in enumerate(summaries):
            if s:
                combined.append(f"## Result {i+1}\n{s}")
        return "\n\n".join(combined)
    
    def _merge_dict_results(self, results: List[Dict]) -> Dict:
        """Merge dictionary results."""
        merged = {}
        
        # Collect all keys
        all_keys = set()
        for r in results:
            all_keys.update(r.keys())
        
        # Merge each key
        for key in all_keys:
            values = [r.get(key) for r in results if key in r and r[key] is not None]
            
            if not values:
                continue
            
            if all(isinstance(v, (list, dict)) for v in values):
                # Merge lists/dicts
                if isinstance(values[0], list):
                    merged[key] = []
                    for v in values:
                        if isinstance(v, list):
                            merged[key].extend(v)
                else:
                    # Dict - recursive merge
                    merged[key] = values[0]
                    for v in values[1:]:
                        if isinstance(v, dict):
                            merged[key].update(v)
            else:
                # Take first non-null value
                merged[key] = values[0]
        
        return merged
