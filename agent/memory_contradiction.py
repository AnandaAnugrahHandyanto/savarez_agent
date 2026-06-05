import json
import re
import logging
from typing import Optional, List

from agent.auxiliary_client import call_llm

logger = logging.getLogger(__name__)

_CONTRADICTION_PROMPT = """You are an expert at detecting semantic contradictions.
Your task is to analyze a new user preference against their existing preferences.

EXISTING PREFERENCES:
{existing}

NEW PREFERENCE:
{new_content}

Does the new preference semantically contradict any of the existing preferences?
- Changing a tool/framework choice IS a contradiction (e.g. from Python to TypeScript).
- Refining a choice is NOT a contradiction (e.g. from Python to Python 3.12).
- Adding unrelated information is NOT a contradiction.

Respond ONLY with a JSON object in this format:
{{"contradiction": bool, "reason": "string (empty if none)"}}
"""

def check_contradiction(
    new_content: str,
    existing_entries: List[str],
) -> Optional[str]:
    """
    Check if new_content contradicts any existing entry.
    Returns conflict description string if conflict found, None if clean.
    """
    if not existing_entries:
        return None
        
    try:
        formatted_existing = "\n- ".join([""] + existing_entries).strip()
        prompt = _CONTRADICTION_PROMPT.format(
            existing=formatted_existing,
            new_content=new_content
        )
        
        # In case the provider does not support json_object natively,
        # we can prompt it or use the json_object mode if supported.
        # Here we just request JSON in the prompt as fallback.
        response = call_llm(
            task="memory_contradiction",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            timeout=10.0,
        )
        
        content = getattr(response.choices[0].message, "content", "{}")
        
        # Robustly extract JSON block
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
            
        result = json.loads(content.strip())
        
        if result.get("contradiction"):
            return result.get("reason", "Detected semantic conflict")
            
    except Exception as e:
        logger.debug(f"Failed to check memory contradiction: {e}")
        
    return None
