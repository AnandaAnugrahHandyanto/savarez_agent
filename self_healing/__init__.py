"""
Self-Healing Tool System for Hermes Agent

Provides automatic tool generation and skill discovery when the agent
encounters missing tools, following the browser-use/browser-harness philosophy
of self-repairing agent infrastructure.

Modules:
    tool_generator: Generates new tool code when tools are missing
    skill_discovery: Auto-discovers and loads skills from ~/.hermes/skills/
    domain_skills: Pre-built domain-specific skill templates
    hot_patch: Runtime hot-patching of the tool registry
"""

try:
    # When hermes_agent is properly installed or in path
    from self_healing.tool_generator import ToolGenerator  # noqa: F401,E402
    from self_healing.hot_patch import HotPatch  # noqa: F401,E402
    from self_healing.skill_discovery import SkillDiscovery  # noqa: F401,E402
    from self_healing.domain_skills import DomainSkills  # noqa: F401,E402
except ImportError:
    # Fallback for relative imports when running from hermes_agent directory
    from self_healing.tool_generator import ToolGenerator  # noqa: F401,E402
    from self_healing.hot_patch import HotPatch  # noqa: F401,E402
    from self_healing.skill_discovery import SkillDiscovery  # noqa: F401,E402
    from self_healing.domain_skills import DomainSkills  # noqa: F401,E402

__all__ = [
    "ToolGenerator",
    "HotPatch",
    "SkillDiscovery",
    "DomainSkills",
]

__version__ = "1.0.0"
