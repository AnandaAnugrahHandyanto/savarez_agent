"""
Fix for gpt_skill_audit (Issue #595)
====================================
Problem: Curator only collects skills but doesn't evaluate quality

Root Cause Analysis:
- In curator.py, the curator does umbrella-building and lifecycle management
- It focuses on consolidation (merging narrow skills into broad umbrellas)
- It does NOT evaluate whether a skill's instructions are well-written
- No quality metrics are computed: clarity, completeness, actionability

Fix Implementation:
1. Add skill quality evaluation via LLM after curator review
2. Add quality dimensions: clarity, completeness, actionability, specificity
3. Add skill quality scoring and threshold-based recommendations
4. Integrate quality feedback into skill_manage actions
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger(__name__)

# Quality dimension weights
QUALITY_DIMENSIONS = {
    "clarity": 0.25,        # Clear, unambiguous language
    "completeness": 0.25,   # All necessary context present
    "actionability": 0.30,  # Can be executed without clarification
    "specificity": 0.20,    # Not overly broad or narrow
}

QUALITY_THRESHOLDS = {
    "excellent": 0.85,
    "good": 0.70,
    "needs_improvement": 0.50,
    "poor": 0.0,
}

QUALITY_REVIEW_PROMPT = """You are evaluating the QUALITY of a skill for the Hermes agent skill library.

Evaluate the skill's SKILL.md content across these dimensions:

1. CLARITY (weight: 25%)
   - Is the language clear and unambiguous?
   - Are instructions easy to understand without domain knowledge?
   - Are edge cases and error conditions documented?

2. COMPLETENESS (weight: 25%)
   - Does it cover the full workflow from trigger to completion?
   - Are prerequisites listed?
   - Are expected inputs and outputs defined?
   - Are alternative approaches mentioned when relevant?

3. ACTIONABILITY (weight: 30%)
   - Can an agent execute this skill without additional clarification?
   - Are concrete steps provided, not just high-level goals?
   - Are success criteria explicit?

4. SPECIFICITY (weight: 20%)
   - Is it neither overly broad (one skill does everything) nor overly narrow?
   - Does it have a well-defined scope?
   - Are edge cases handled without bloating the main flow?

Skill to evaluate:
```
{skill_content}
```

For each dimension, provide:
- Score: 0.0 to 1.0
- Reasoning: 1-2 sentences explaining the score
- Suggestion: Specific improvement recommendation if score < 0.7

Output format:
```json
{{
  "clarity": {{"score": 0.0-1.0, "reasoning": "...", "suggestion": "..."}},
  "completeness": {{"score": 0.0-1.0, "reasoning": "...", "suggestion": "..."}},
  "actionability": {{"score": 0.0-1.0, "reasoning": "...", "suggestion": "..."}},
  "specificity": {{"score": 0.0-1.0, "reasoning": "...", "suggestion": "..."}},
  "overall_score": 0.0-1.0,
  "overall_quality": "excellent|good|needs_improvement|poor",
  "recommendation": "keep|revise|rewrite|archive"
}}
```
"""


def _load_skill_content(skill_name: str) -> Optional[str]:
    """
    Load the SKILL.md content for a skill by name.
    
    Uses the skill_usage module path resolution.
    """
    try:
        from tools import skill_usage
        from pathlib import Path
        
        skills_dir = skill_usage._skills_dir()
        skill_path = skills_dir / skill_name / "SKILL.md"
        
        if not skill_path.exists():
            # Try archived path
            skill_path = skills_dir / ".archive" / skill_name / "SKILL.md"
        
        if skill_path.exists():
            return skill_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.debug(f"Failed to load skill content for {skill_name}: {e}")
    
    return None


def _compute_weighted_score(dimension_scores: Dict[str, float]) -> float:
    """Compute weighted overall score from dimension scores."""
    total = 0.0
    for dim, weight in QUALITY_DIMENSIONS.items():
        total += dimension_scores.get(dim, 0.0) * weight
    return total


def _determine_overall_quality(score: float) -> str:
    """Determine quality tier from score."""
    if score >= QUALITY_THRESHOLDS["excellent"]:
        return "excellent"
    elif score >= QUALITY_THRESHOLDS["good"]:
        return "good"
    elif score >= QUALITY_THRESHOLDS["needs_improvement"]:
        return "needs_improvement"
    else:
        return "poor"


def _determine_recommendation(quality: str, score: float) -> str:
    """Determine curator recommendation based on quality."""
    if quality == "excellent":
        return "keep"
    elif quality == "good":
        return "keep" if score >= 0.75 else "revise"
    elif quality == "needs_improvement":
        return "revise"
    else:
        return "rewrite"


def evaluate_skill_quality(
    skill_name: str,
    llm_callback: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """
    Evaluate a single skill's quality across all dimensions.
    
    Args:
        skill_name: Name of the skill to evaluate
        llm_callback: Optional LLM function that takes a prompt and returns response.
                     If None, uses heuristic scoring (for testing/backup).
    
    Returns:
        Dict with quality evaluation results
    """
    content = _load_skill_content(skill_name)
    if not content:
        return {
            "skill_name": skill_name,
            "error": "Could not load skill content",
            "overall_score": 0.0,
        }
    
    if llm_callback:
        prompt = QUALITY_REVIEW_PROMPT.format(skill_content=content[:8000])  # Cap content
        try:
            response = llm_callback(prompt)
            result = _parse_quality_response(response)
            result["skill_name"] = skill_name
            result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as e:
            logger.debug(f"LLM quality evaluation failed for {skill_name}: {e}")
            # Fall through to heuristic
    
    # Heuristic scoring (fallback when LLM unavailable)
    return _heuristic_quality_score(skill_name, content)


def _parse_quality_response(response: str) -> Dict[str, Any]:
    """Parse LLM quality evaluation response."""
    # Extract JSON from response
    try:
        # Find JSON block
        start = response.find("```json")
        if start != -1:
            start += 7
            end = response.find("```", start)
            if end != -1:
                json_str = response[start:end].strip()
            else:
                json_str = response[start:].strip()
        else:
            # Try plain JSON
            json_str = response.strip()
        
        parsed = json.loads(json_str)
        
        # Validate and normalize
        result = {
            "clarity": parsed.get("clarity", {}),
            "completeness": parsed.get("completeness", {}),
            "actionability": parsed.get("actionability", {}),
            "specificity": parsed.get("specificity", {}),
            "overall_score": float(parsed.get("overall_score", 0.0)),
            "overall_quality": parsed.get("overall_quality", "poor"),
            "recommendation": parsed.get("recommendation", "keep"),
        }
        
        return result
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse quality response: {e}")
        return {
            "error": "Parse error",
            "overall_score": 0.0,
        }


def _heuristic_quality_score(skill_name: str, content: str) -> Dict[str, Any]:
    """
    Heuristic quality scoring when LLM is unavailable.
    
    Uses structural analysis of the skill content.
    """
    scores = {}
    suggestions = {}
    
    # Clarity: Check for clear sections, lists, headers
    has_headers = content.count("#") >= 2
    has_lists = ("- " in content or "* " in content or "1." in content)
    avg_line_length = sum(len(line) for line in content.splitlines()) / max(1, len(content.splitlines()))
    line_length_ok = 20 <= avg_line_length <= 120
    
    clarity_score = 0.5
    if has_headers: clarity_score += 0.15
    if has_lists: clarity_score += 0.15
    if line_length_ok: clarity_score += 0.2
    scores["clarity"] = min(1.0, clarity_score)
    suggestions["clarity"] = "Add clear section headers and bullet lists" if clarity_score < 0.7 else "Good structure"
    
    # Completeness: Check for key sections
    has_description = "description" in content.lower() or "what" in content.lower()
    has_steps = ("step" in content.lower() or "how" in content.lower())
    has_examples = "example" in content.lower()
    has_prerequisites = "prerequisite" in content.lower() or "require" in content.lower()
    
    completeness_score = 0.4
    if has_description: completeness_score += 0.15
    if has_steps: completeness_score += 0.2
    if has_examples: completeness_score += 0.15
    if has_prerequisites: completeness_score += 0.1
    scores["completeness"] = min(1.0, completeness_score)
    suggestions["completeness"] = "Add prerequisites and examples" if completeness_score < 0.7 else "Covers essential sections"
    
    # Actionability: Check for concrete instructions
    has_verbs = any(word in content.lower() for word in ["run", "execute", "create", "update", "delete", "install"])
    has_error_handling = "error" in content.lower() or "exception" in content.lower() or "fail" in content.lower()
    
    actionability_score = 0.5
    if has_verbs: actionability_score += 0.25
    if has_error_handling: actionability_score += 0.25
    scores["actionability"] = min(1.0, actionability_score)
    suggestions["actionability"] = "Add concrete action steps and error handling" if actionability_score < 0.7 else "Clear actionable steps"
    
    # Specificity: Check for appropriate length and focus
    word_count = len(content.split())
    is_too_short = word_count < 50
    is_too_long = word_count > 5000
    
    specificity_score = 0.6
    if is_too_short: specificity_score -= 0.2
    if is_too_long: specificity_score -= 0.2
    # Check for focused scope
    if "and" not in content.lower()[:500] or content.lower().count("#") >= 3:
        specificity_score += 0.1
    scores["specificity"] = min(1.0, max(0.0, specificity_score))
    suggestions["specificity"] = "Too brief or too broad - refine scope" if specificity_score < 0.7 else "Good scope definition"
    
    # Compute overall
    overall = _compute_weighted_score(scores)
    quality = _determine_overall_quality(overall)
    recommendation = _determine_recommendation(quality, overall)
    
    return {
        "skill_name": skill_name,
        "clarity": {"score": scores["clarity"], "reasoning": suggestions["clarity"], "suggestion": suggestions["clarity"]},
        "completeness": {"score": scores["completeness"], "reasoning": suggestions["completeness"], "suggestion": suggestions["completeness"]},
        "actionability": {"score": scores["actionability"], "reasoning": suggestions["actionability"], "suggestion": suggestions["actionability"]},
        "specificity": {"score": scores["specificity"], "reasoning": suggestions["specificity"], "suggestion": suggestions["specificity"]},
        "overall_score": overall,
        "overall_quality": quality,
        "recommendation": recommendation,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_method": "heuristic",
    }


def evaluate_skill_batch(
    skill_names: List[str],
    llm_callback: Optional[Callable[[str], str]] = None,
    max_concurrent: int = 3,
) -> Dict[str, Any]:
    """
    Evaluate a batch of skills for quality.
    
    Args:
        skill_names: List of skill names to evaluate
        llm_callback: Optional LLM callback for evaluation
        max_concurrent: Max concurrent evaluations
    
    Returns:
        Summary of batch evaluation with per-skill results
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = []
    errors = []
    
    def eval_one(name: str) -> Dict[str, Any]:
        return evaluate_skill_quality(name, llm_callback)
    
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {executor.submit(eval_one, name): name for name in skill_names}
        
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                errors.append({"skill_name": name, "error": str(e)})
    
    # Aggregate statistics
    valid_results = [r for r in results if "error" not in r]
    scores = [r["overall_score"] for r in valid_results]
    
    summary = {
        "total_evaluated": len(valid_results),
        "total_errors": len(errors),
        "average_score": sum(scores) / max(1, len(scores)) if scores else 0.0,
        "score_distribution": {
            "excellent": sum(1 for r in valid_results if r.get("overall_quality") == "excellent"),
            "good": sum(1 for r in valid_results if r.get("overall_quality") == "good"),
            "needs_improvement": sum(1 for r in valid_results if r.get("overall_quality") == "needs_improvement"),
            "poor": sum(1 for r in valid_results if r.get("overall_quality") == "poor"),
        },
        "recommendations": {
            "keep": sum(1 for r in valid_results if r.get("recommendation") == "keep"),
            "revise": sum(1 for r in valid_results if r.get("recommendation") == "revise"),
            "rewrite": sum(1 for r in valid_results if r.get("recommendation") == "rewrite"),
            "archive": sum(1 for r in valid_results if r.get("recommendation") == "archive"),
        },
        "skills_needing_attention": [
            r["skill_name"] for r in valid_results 
            if r.get("recommendation") in ("revise", "rewrite")
        ],
        "per_skill": results,
        "errors": errors,
    }
    
    return summary


# ============================================================================
# INTEGRATION PATCHES for curator.py
# ============================================================================
"""
To integrate these fixes, add the following patches to curator.py:

1. Add new function after evaluate_skill_quality definitions:

def run_quality_audit(dry_run: bool = False) -> Dict[str, Any]:
    '''
    Run quality audit on agent-created skills.
    
    This evaluates each skill for clarity, completeness, actionability,
    and specificity. Results are persisted and used to prioritize
    curator review passes.
    '''
    from tools import skill_usage
    
    candidates = skill_usage.agent_created_report()
    if not candidates:
        return {"evaluated": 0, "summary": "No skills to audit"}
    
    skill_names = [r["name"] for r in candidates]
    
    # Run batch evaluation
    results = evaluate_skill_batch(skill_names, llm_callback=None)
    
    # Persist results
    _persist_quality_results(results)
    
    return {
        "evaluated": results["total_evaluated"],
        "average_score": results["average_score"],
        "needs_attention": len(results["skills_needing_attention"]),
        "summary": results,
    }

2. In the curator review flow (run_curator_review), add quality audit step:

def run_curator_review(...):
    ...
    # First: Quality audit (NEW)
    if not dry_run:
        quality_results = run_quality_audit()
        if quality_results.get("needs_attention", 0) > 0:
            # Add quality issues to summary
            ...
    
    # Then: Automatic transitions (existing)
    counts = apply_automatic_transitions(now=start)
    ...

3. Add quality score to skill_manage recommendations:
   - When curator suggests actions, factor in quality scores
   - Low-quality skills get higher consolidation priority
"""
