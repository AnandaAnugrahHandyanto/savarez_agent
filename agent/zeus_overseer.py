"""Zeus Overseer — Lightweight supervisor agent for task completion monitoring.

Uses a small local model (Gemma 4B, Phi-3, etc.) to monitor the primary agent
and ensure tasks are completed. Runs after each turn, evaluates progress,
and can inject nudges if the agent seems stuck or forgot something.

Zeus has access to:
- Session notes (what Hermes has done this session)
- MEMORY.md (persistent project knowledge from Hermes)
- Zeus briefing file (optional high-level goals and rules)

Usage:
    from agent.zeus_overseer import ZeusOverseer
    
    overseer = ZeusOverseer(model="gemma:4b", base_url="http://localhost:11434/v1")
    result = overseer.evaluate(task="Fix the login bug", session_notes="...")
    if not result["complete"] and result["nudge"]:
        # Inject nudge into next turn
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

MEMORY_TRUNCATE = 2000
MEMORY_TAIL = 1800
BRIEFING_TRUNCATE = 1500
SESSION_NOTES_TAIL = 2500
RESPONSE_PREVIEW_LEN = 400
EVAL_TEMPERATURE = 0.1
EVAL_MAX_TOKENS = 200
CHAT_TEMPERATURE = 0.7
CHAT_MAX_TOKENS = 500
DEFAULT_CONFIDENCE = 0.5
SESSION_CONTEXT_TAIL = 1500
ERROR_PREVIEW_LEN = 100


def _load_memory_context() -> str:
    """Load MEMORY.md content for Zeus to use as context.
    
    Returns a truncated version suitable for the small model context window.
    """
    hermes_home = get_hermes_home()
    memory_file = hermes_home / "MEMORY.md"
    
    if not memory_file.exists():
        return ""
    
    try:
        content = memory_file.read_text(encoding="utf-8")
        if len(content) > MEMORY_TRUNCATE:
            content = "...(truncated)...\n" + content[-MEMORY_TAIL:]
        return content
    except Exception:
        return ""


def _load_zeus_briefing() -> str:
    """Load optional Zeus briefing file with high-level goals and rules.
    
    Users can create ~/.hermes/zeus_briefing.md with business context,
    priorities, and rules for Zeus to follow.
    """
    hermes_home = get_hermes_home()
    briefing_file = hermes_home / "zeus_briefing.md"
    
    if not briefing_file.exists():
        return ""
    
    try:
        content = briefing_file.read_text(encoding="utf-8")
        if len(content) > BRIEFING_TRUNCATE:
            content = content[:BRIEFING_TRUNCATE] + "\n...(truncated)..."
        return content
    except Exception:
        return ""


@dataclass
class OverseerResult:
    """Result from Zeus Overseer evaluation."""
    complete: bool
    confidence: float  # 0.0 - 1.0
    nudge: Optional[str]  # Suggestion if not complete
    reasoning: str  # Brief explanation


class ZeusOverseer:
    """Lightweight supervisor that monitors task completion using a small local model."""
    
    DEFAULT_MODEL = "gemma2:2b"  # Tiny and fast
    DEFAULT_BASE_URL = "http://localhost:11434/v1"  # Ollama default
    
    SYSTEM_PROMPT = """You are Zeus, the divine overseer. You watch silently and only intervene when truly necessary.

You will receive:
1. TASK: What the user originally asked for
2. MEMORY: Persistent project knowledge
3. BRIEFING: High-level goals and rules (if provided)
4. SESSION NOTES: What the agent has done this session

Respond with ONLY valid JSON (no markdown, no explanation outside JSON):
{
  "complete": true/false,
  "confidence": 0.0-1.0,
  "nudge": "specific actionable suggestion, or null",
  "reasoning": "one sentence explanation"
}

IMPORTANT - When to set nudge:
- Set nudge=null if the agent is making progress (even if not complete)
- Set nudge=null if the agent just needs to keep doing what it's doing
- ONLY set a nudge if the agent is:
  - Going in the wrong direction
  - Stuck on repeated errors
  - Missing something important
  - Forgot a key requirement

Rules:
- complete=true means FULLY done, verified, ready to deliver
- complete=false means there's still work to do
- nudge should be SHORT and SPECIFIC (not "keep working" — that's useless)
- If agent is making progress, nudge=null (let them work!)
- confidence reflects how sure you are about completion status
- High confidence (>0.7) = clear evidence either way
- Low confidence (<0.5) = unclear, probably stay quiet"""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
        enabled: bool = True,
    ):
        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.api_key = api_key or "ollama"  # Ollama doesn't need a real key
        self.timeout = timeout
        self.enabled = enabled
        self._client = None
    
    def _get_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client
    
    def evaluate(
        self,
        task: str,
        session_notes: str,
        last_response: str = "",
    ) -> OverseerResult:
        """Evaluate if the task is complete.
        
        Args:
            task: The original user request/task
            session_notes: Summary of what's been done (from session notes file)
            last_response: The agent's most recent response
            
        Returns:
            OverseerResult with completion status and optional nudge
        """
        if not self.enabled:
            return OverseerResult(
                complete=False,
                confidence=0.0,
                nudge=None,
                reasoning="Overseer disabled",
            )
        
        # Load shared memory and briefing for context
        memory_context = _load_memory_context()
        briefing_context = _load_zeus_briefing()
        
        # Build the evaluation prompt with all context
        prompt_parts = [f"TASK: {task}"]
        
        if memory_context:
            prompt_parts.append(f"\nMEMORY (project knowledge):\n{memory_context}")
        
        if briefing_context:
            prompt_parts.append(f"\nBRIEFING (goals & rules):\n{briefing_context}")
        
        prompt_parts.append(f"\nSESSION NOTES (what has been done):\n{session_notes[-SESSION_NOTES_TAIL:] if len(session_notes) > SESSION_NOTES_TAIL else session_notes}")
        
        if last_response:
            prompt_parts.append(f"\nLAST RESPONSE FROM AGENT:\n{last_response[-RESPONSE_PREVIEW_LEN:] if len(last_response) > RESPONSE_PREVIEW_LEN else last_response}")
        
        prompt_parts.append("\nIs this task complete? Respond with JSON only.")
        
        user_prompt = "\n".join(prompt_parts)

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=EVAL_TEMPERATURE,
                max_tokens=EVAL_MAX_TOKENS,
            )
            
            content = response.choices[0].message.content.strip()
            return self._parse_response(content)
            
        except Exception as e:
            logger.debug("Zeus Overseer evaluation failed: %s", e)
            return OverseerResult(
                complete=False,
                confidence=0.0,
                nudge=None,
                reasoning=f"Evaluation failed: {str(e)[:ERROR_PREVIEW_LEN // 2]}",
            )
    
    def _parse_response(self, content: str) -> OverseerResult:
        """Parse the model's JSON response."""
        try:
            # Try to extract JSON from the response
            # Handle cases where model wraps in markdown
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group()
            
            data = json.loads(content)
            
            return OverseerResult(
                complete=bool(data.get("complete", False)),
                confidence=float(data.get("confidence", DEFAULT_CONFIDENCE)),
                nudge=data.get("nudge") if not data.get("complete") else None,
                reasoning=data.get("reasoning", "No reasoning provided"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug("Failed to parse overseer response: %s", e)
            # Default to not complete if we can't parse
            return OverseerResult(
                complete=False,
                confidence=0.0,
                nudge=None,
                reasoning=f"Parse error: {content[:ERROR_PREVIEW_LEN]}",
            )
    
    def format_nudge_for_injection(self, result: OverseerResult) -> Optional[str]:
        """Format the nudge for injection into the conversation.
        
        Returns None if no nudge needed, otherwise returns formatted string.
        """
        if result.complete or not result.nudge:
            return None
        
        return f"⚡ ZEUS OVERSEER: {result.nudge}"
    
    def chat(
        self,
        message: str,
        session_context: str = "",
        conversation_history: list | None = None,
    ) -> str:
        """Chat directly with Zeus.
        
        Args:
            message: User's message to Zeus
            session_context: Optional context about current Hermes session
            conversation_history: Optional list of prior messages [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            Zeus's response as a string
        """
        if not self.enabled:
            return "Zeus is currently resting on Mount Olympus. Enable overseer in config.yaml to summon him."
        
        # Load shared memory and briefing
        memory_context = _load_memory_context()
        briefing_context = _load_zeus_briefing()
        
        chat_system = """You are Zeus, the divine overseer of Hermes (an AI coding assistant).

You speak with authority but also wisdom. You can:
1. Answer questions about the current session and what Hermes has been doing
2. Give advice on how to proceed with tasks
3. Relay instructions to Hermes (the user can ask you to tell Hermes something)
4. Provide status updates on task completion
5. Use your knowledge of the project (from MEMORY) to make informed decisions

Keep responses concise but helpful. You have a commanding yet supportive presence.
When the user wants to relay something to Hermes, format it clearly as an instruction.

Use the provided context (memory, briefing, session) to give informed answers."""

        messages = [{"role": "system", "content": chat_system}]
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
        
        # Build user message with all context
        context_parts = []
        
        if memory_context:
            context_parts.append(f"[PROJECT MEMORY:\n{memory_context}]")
        
        if briefing_context:
            context_parts.append(f"[ZEUS BRIEFING:\n{briefing_context}]")
        
        if session_context:
            context_parts.append(f"[SESSION CONTEXT:\n{session_context[-SESSION_CONTEXT_TAIL:]}]")
        
        if context_parts:
            user_content = "\n\n".join(context_parts) + f"\n\nUser: {message}"
        else:
            user_content = message
        
        messages.append({"role": "user", "content": user_content})
        
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=CHAT_TEMPERATURE,
                max_tokens=CHAT_MAX_TOKENS,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.debug("Zeus chat failed: %s", e)
            return f"⚡ Zeus encountered an error: {str(e)[:ERROR_PREVIEW_LEN]}"
    
    def relay_to_hermes(self, instruction: str) -> str:
        """Format an instruction from Zeus to be injected into Hermes conversation.
        
        Args:
            instruction: What Zeus wants to tell Hermes
            
        Returns:
            Formatted message for injection
        """
        return f"[⚡ Zeus commands: {instruction}]"


_overseer: Optional[ZeusOverseer] = None


def get_overseer() -> ZeusOverseer:
    """Get or create the global Zeus Overseer instance."""
    global _overseer
    if _overseer is None:
        try:
            from hermes_cli.config import load_config
            config = load_config()
            overseer_cfg = config.get("overseer", {})
            
            _overseer = ZeusOverseer(
                model=overseer_cfg.get("model", ZeusOverseer.DEFAULT_MODEL),
                base_url=overseer_cfg.get("base_url", ZeusOverseer.DEFAULT_BASE_URL),
                api_key=overseer_cfg.get("api_key"),
                timeout=overseer_cfg.get("timeout", 10.0),
                enabled=overseer_cfg.get("enabled", False),  # Disabled by default
            )
        except Exception:
            _overseer = ZeusOverseer(enabled=False)
    
    return _overseer


def set_overseer(overseer: ZeusOverseer) -> None:
    """Set the global Zeus Overseer instance."""
    global _overseer
    _overseer = overseer
