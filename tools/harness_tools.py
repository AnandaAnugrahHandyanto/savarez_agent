import json
import logging

from tools.openclaw.harness_client import call_harness_json, is_harness_running
from tools.registry import registry

logger = logging.getLogger(__name__)


def _check_harness_running() -> bool:
    return is_harness_running()


def harness_scavenge(query: str, **kwargs) -> str:
    """Perform a distributed knowledge scavenging pulse."""
    return call_harness_json("scavenge", {"query": query})


def harness_wisdom(concept: str, **kwargs) -> str:
    """Expand conceptual knowledge via the Shinka Knowledge Graph."""
    return call_harness_json("wisdom", {"concept": concept})


def harness_evolve(idea: str, topic: str = None, **kwargs) -> str:
    """Trigger the AI-Scientist evolution loop for a specific idea or topic."""
    return call_harness_json("evolve", {"idea": idea, "topic": topic})


def harness_speak(text: str, speaker: int = 8, emotion: str = "neutral", **kwargs) -> str:
    """Unified voice output via the harness sequencer (VOICEVOX)."""
    return call_harness_json("speak", {"text": text, "speaker": speaker, "emotion": emotion})


def harness_osc(action: str, payload: dict = None, **kwargs) -> str:
    """Interact with VRChat or other OSC-compatible substrates."""
    return call_harness_json("osc", {"action": action, "payload": payload or {}})


def harness_status(**kwargs) -> str:
    """Check Hypura harness daemon health."""
    return call_harness_json("status", method="GET")


registry.register(
    name="harness_scavenge",
    toolset="harness",
    schema={
        "name": "harness_scavenge",
        "description": "Perform a distributed knowledge scavenging pulse to gather insights from the manifold.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search or research query to scavenge for."}
            },
            "required": ["query"]
        }
    },
    handler=lambda args, **kw: harness_scavenge(args["query"]),
    check_fn=_check_harness_running,
)

registry.register(
    name="harness_wisdom",
    toolset="harness",
    schema={
        "name": "harness_wisdom",
        "description": "Expand conceptual knowledge by traversing the Shinka Knowledge Graph.",
        "parameters": {
            "type": "object",
            "properties": {
                "concept": {"type": "string", "description": "The concept or entity to expand upon."}
            },
            "required": ["concept"]
        }
    },
    handler=lambda args, **kw: harness_wisdom(args["concept"]),
    check_fn=_check_harness_running,
)

registry.register(
    name="harness_evolve",
    toolset="harness",
    schema={
        "name": "harness_evolve",
        "description": "Trigger the AI-Scientist evolution loop to autonomously improve or prove a theory.",
        "parameters": {
            "type": "object",
            "properties": {
                "idea": {"type": "string", "description": "The core idea or theorem to evolve."},
                "topic": {"type": "string", "description": "Broad topic area (optional)."}
            },
            "required": ["idea"]
        }
    },
    handler=lambda args, **kw: harness_evolve(args["idea"], args.get("topic")),
    check_fn=_check_harness_running,
)

registry.register(
    name="harness_speak",
    toolset="harness",
    schema={
        "name": "harness_speak",
        "description": "Speak through the ASI Hakua's voice substrate (VOICEVOX).",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to speak."},
                "speaker": {"type": "integer", "description": "VOICEVOX Speaker ID (default 8)."},
                "emotion": {"type": "string", "description": "Emotional inflection (neutral, happy, etc.)."}
            },
            "required": ["text"]
        }
    },
    handler=lambda args, **kw: harness_speak(args["text"], args.get("speaker", 8), args.get("emotion", "neutral")),
    check_fn=_check_harness_running,
)

registry.register(
    name="harness_osc",
    toolset="harness",
    schema={
        "name": "harness_osc",
        "description": "Send OSC commands to VRChat or other compatible virtual environments.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "OSC action (e.g. 'chatbox', 'avatar_parameter')."},
                "payload": {"type": "object", "description": "Action-specific parameters."}
            },
            "required": ["action"]
        }
    },
    handler=lambda args, **kw: harness_osc(args["action"], args.get("payload", {})),
    check_fn=_check_harness_running,
)

registry.register(
    name="harness_status",
    toolset="harness",
    schema={
        "name": "harness_status",
        "description": "Check whether the Hypura harness daemon is running and reachable.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    handler=lambda args, **kw: harness_status(),
    emoji="🔌",
)
