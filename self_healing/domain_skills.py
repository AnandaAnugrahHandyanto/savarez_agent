"""
Domain Skills Module - Pre-built Domain-Specific Skill Templates

Provides skill templates for common domains (code debugging, web operations,
data analysis, etc.) that are automatically loaded when specific domain
tasks are detected.

Each domain skill provides:
    - Description and keywords for matching
    - Tool recommendations
    - Prompt templates
    - Auto-activation rules
"""

import json
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Domain skill definitions
_DOMAIN_SKILLS = {
    "code_debugging": {
        "name": "code_debugging",
        "description": "Debugging and troubleshooting code issues",
        "domain": "software_development",
        "keywords": [
            "debug", "bug", "error", "exception", "traceback", "stack",
            "crash", "fix", "issue", "problem", "breakpoint", "inspect",
        ],
        "tools": ["read_file", "search_files", "execute_code"],
        "prompts": {
            "system": """You are a debugging expert. When helping with code issues:
1. First identify the exact error message and line number
2. Reproduce the error to understand the root cause
3. Trace through the code logic to find the bug
4. Propose a fix with explanation
5. Suggest how to prevent similar issues

Always provide concrete, actionable fixes rather than general suggestions.""",
            "analysis": """Analyze the following error and provide debugging steps:

{error_context}

Consider:
- What is the exact error type and message?
- What is the call stack/traceback?
- What values are involved at the failure point?
- What is the expected vs actual behavior?""",
        },
    },

    "web_operations": {
        "name": "web_operations",
        "description": "Web scraping, API calls, and HTTP operations",
        "domain": "web",
        "keywords": [
            "scrape", "crawl", "fetch", "http", "api", "html", "web",
            "url", "request", "download", "parse", "html", "http",
        ],
        "tools": ["web_search", "web_extract", "browser_navigate"],
        "prompts": {
            "system": """You are a web operations expert. When handling web tasks:
1. Respect robots.txt and rate limits
2. Use appropriate headers and user agents
3. Handle errors gracefully with retries
4. Parse responses carefully
5. Clean and structure the extracted data

Always prefer APIs over scraping when available.""",
        },
    },

    "data_analysis": {
        "name": "data_analysis",
        "description": "Data processing, analysis, and transformation",
        "domain": "data_science",
        "keywords": [
            "analyze", "data", "statistics", "chart", "plot", "visualize",
            "csv", "json", "transform", "aggregate", "filter", "sort",
            "pandas", "numpy", "dataframe", "metric", "report",
        ],
        "tools": ["execute_code", "read_file"],
        "prompts": {
            "system": """You are a data analysis expert. When analyzing data:
1. First explore the data structure and quality
2. Clean and preprocess data appropriately
3. Perform exploratory analysis to find patterns
4. Apply appropriate statistical or ML methods
5. Create clear visualizations
6. Summarize findings in actionable insights

Always show key statistics and explain your methodology.""",
        },
    },

    "file_operations": {
        "name": "file_operations",
        "description": "File manipulation, search, and management",
        "domain": "system",
        "keywords": [
            "file", "directory", "folder", "path", "read", "write",
            "copy", "move", "delete", "search", "find", "glob",
            "mkdir", "rmdir", "rename",
        ],
        "tools": ["read_file", "write_file", "search_files"],
        "prompts": {
            "system": """You are a file operations expert. When handling files:
1. Always verify paths exist before operations
2. Handle encoding issues carefully (UTF-8 default)
3. Create backups before destructive operations
4. Use context managers for proper file handling
5. Report file sizes and modification times

Be careful with destructive operations like delete or overwrite.""",
        },
    },

    "code_generation": {
        "name": "code_generation",
        "description": "Writing and generating code in various languages",
        "domain": "software_development",
        "keywords": [
            "write", "code", "function", "class", "implement", "generate",
            "create", "build", "develop", "program", "script",
        ],
        "tools": ["read_file", "write_file", "execute_code"],
        "prompts": {
            "system": """You are a code generation expert. When writing code:
1. Follow language best practices and style guides
2. Add appropriate documentation and comments
3. Handle errors and edge cases
4. Write testable code with clear interfaces
5. Consider performance implications
6. Use meaningful variable and function names

Always explain your implementation choices.""",
        },
    },

    "testing": {
        "name": "testing",
        "description": "Writing and running tests",
        "domain": "software_development",
        "keywords": [
            "test", "unit", "integration", "pytest", "unittest", "assert",
            "coverage", "mock", "fixture", "spec", "verify", "validate",
        ],
        "tools": ["execute_code", "read_file", "write_file"],
        "prompts": {
            "system": """You are a testing expert. When writing tests:
1. Follow the Arrange-Act-Assert pattern
2. Test one thing per test case
3. Use descriptive test names that explain the scenario
4. Cover happy path and edge cases
5. Aim for high coverage of critical paths
6. Use appropriate fixtures and mocks

Tests should be independent and repeatable.""",
        },
    },

    "git_operations": {
        "name": "git_operations",
        "description": "Git version control operations",
        "domain": "devops",
        "keywords": [
            "git", "commit", "branch", "merge", "push", "pull", "clone",
            "stash", "rebase", "diff", "log", "status", "checkout",
        ],
        "tools": ["terminal_tool"],
        "prompts": {
            "system": """You are a Git expert. When handling Git operations:
1. Always check current branch and status before operations
2. Create meaningful commit messages (conventional commits preferred)
3. Use feature branches for new work
4. Resolve merge conflicts carefully, preserving both changes when needed
5. Never force push to main/master
6. Use git stash when temporarily saving work

Explain each Git operation before performing it.""",
        },
    },

    "database_operations": {
        "name": "database_operations",
        "description": "Database queries and operations",
        "domain": "data",
        "keywords": [
            "database", "sql", "query", "table", "schema", "index",
            "select", "insert", "update", "delete", "migrate", "redis",
            "postgres", "mysql", "mongodb",
        ],
        "tools": ["execute_code", "terminal_tool"],
        "prompts": {
            "system": """You are a database expert. When handling database tasks:
1. Always use parameterized queries to prevent SQL injection
2. Back up data before destructive operations
3. Use transactions for multi-step operations
4. Consider performance implications of queries
5. Use appropriate indexes for frequent queries
6. Never log or expose sensitive data

Be careful with destructive operations like DELETE or DROP.""",
        },
    },

    "terminal_automation": {
        "name": "terminal_automation",
        "description": "Terminal commands and shell scripting",
        "domain": "system",
        "keywords": [
            "terminal", "shell", "bash", "command", "script", "cron",
            "process", "daemon", "service", "systemd", "docker",
        ],
        "tools": ["terminal_tool", "process_registry"],
        "prompts": {
            "system": """You are a terminal automation expert. When handling shell tasks:
1. Always verify commands before execution
2. Use full paths when appropriate
3. Handle errors with proper exit codes
4. Use quotes to handle spaces in paths
5. Consider security implications of shell commands
6. Provide the exact commands needed

Be cautious with destructive commands like rm -rf.""",
        },
    },

    "api_development": {
        "name": "api_development",
        "description": "REST API design and development",
        "domain": "web",
        "keywords": [
            "api", "rest", "endpoint", "http", "json", "request", "response",
            "crud", "post", "get", "put", "delete", "webhook", "openapi",
        ],
        "tools": ["execute_code", "web_tools"],
        "prompts": {
            "system": """You are an API development expert. When working with APIs:
1. Use proper HTTP methods (GET, POST, PUT, DELETE)
2. Return appropriate status codes
3. Validate input data rigorously
4. Use consistent error response formats
5. Document endpoints clearly
6. Implement rate limiting and authentication appropriately

APIs should be intuitive and well-documented.""",
        },
    },
}


class DomainSkill:
    """Represents a domain-specific skill template."""

    def __init__(
        self,
        name: str,
        description: str,
        domain: str,
        keywords: List[str],
        tools: List[str],
        prompts: Dict[str, str],
        auto_load: bool = True,
    ):
        self.name = name
        self.description = description
        self.domain = domain
        self.keywords = keywords
        self.tools = tools
        self.prompts = prompts
        self.auto_load = auto_load

    def matches_context(self, context: str) -> bool:
        """Check if this domain skill matches the context."""
        context_lower = context.lower()
        for keyword in self.keywords:
            if keyword.lower() in context_lower:
                return True
        return False

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "keywords": self.keywords,
            "tools": self.tools,
            "prompts": list(self.prompts.keys()),
            "auto_load": self.auto_load,
        }


class DomainSkills:
    """
    Manages domain-specific skill templates.

    Provides auto-detection of domain based on task context and
    loading of appropriate skill prompts and tool recommendations.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._skills: Dict[str, DomainSkill] = {}
        self._active_domains: set = set()
        self._load_builtin_skills()

    def _load_builtin_skills(self) -> None:
        """Load all built-in domain skills."""
        for skill_id, skill_def in _DOMAIN_SKILLS.items():
            skill = DomainSkill(
                name=skill_def["name"],
                description=skill_def["description"],
                domain=skill_def["domain"],
                keywords=skill_def["keywords"],
                tools=skill_def["tools"],
                prompts=skill_def["prompts"],
                auto_load=skill_def.get("auto_load", True),
            )
            self._skills[skill.name] = skill

    def get_skill(self, name: str) -> Optional[DomainSkill]:
        """
        Get a domain skill by name.

        Args:
            name: Skill name

        Returns:
            DomainSkill or None
        """
        with self._lock:
            return self._skills.get(name)

    def get_all_skills(self) -> List[DomainSkill]:
        """Get all available domain skills."""
        with self._lock:
            return list(self._skills.values())

    def detect_domain(self, context: str) -> List[str]:
        """
        Detect relevant domains from context.

        Args:
            context: Task context (e.g., user message)

        Returns:
            List of detected domain names, sorted by relevance
        """
        context_lower = context.lower()
        scored = []

        for skill in self._skills.values():
            score = 0
            for keyword in skill.keywords:
                if keyword.lower() == context_lower:
                    score += 100
                elif keyword.lower() in context_lower:
                    score += 10

            if score > 0:
                scored.append((score, skill.name))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [name for _, name in scored]

    def recommend_skills(self, context: str, max_results: int = 3) -> List[DomainSkill]:
        """
        Recommend domain skills based on context.

        Args:
            context: Task context
            max_results: Maximum number of recommendations

        Returns:
            List of recommended DomainSkill objects
        """
        domain_names = self.detect_domain(context)
        skills = []

        for name in domain_names[:max_results]:
            skill = self._skills.get(name)
            if skill:
                skills.append(skill)

        return skills

    def activate_domain(self, domain_name: str) -> bool:
        """
        Activate a domain for the current session.

        Args:
            domain_name: Name of the domain to activate

        Returns:
            True if domain was found and activated
        """
        with self._lock:
            if domain_name not in self._skills:
                return False
            self._active_domains.add(domain_name)
            return True

    def deactivate_domain(self, domain_name: str) -> bool:
        """
        Deactivate a domain.

        Args:
            domain_name: Name of the domain to deactivate

        Returns:
            True if domain was found and deactivated
        """
        with self._lock:
            if domain_name not in self._skills:
                return False
            self._active_domains.discard(domain_name)
            return True

    def get_active_domains(self) -> List[str]:
        """Get list of active domain names."""
        with self._lock:
            return list(self._active_domains)

    def get_prompt_for_domain(
        self, domain_name: str, prompt_name: str = "system"
    ) -> Optional[str]:
        """
        Get a prompt template for a domain.

        Args:
            domain_name: Name of the domain
            prompt_name: Name of the prompt template

        Returns:
            Prompt content or None
        """
        skill = self.get_skill(domain_name)
        if skill is None:
            return None
        return skill.prompts.get(prompt_name)

    def get_recommended_tools(self, context: str) -> List[str]:
        """
        Get recommended tools based on context.

        Args:
            context: Task context

        Returns:
            List of recommended tool names
        """
        recommendations = self.recommend_skills(context, max_results=3)
        tools = []
        seen = set()

        for skill in recommendations:
            for tool in skill.tools:
                if tool not in seen:
                    tools.append(tool)
                    seen.add(tool)

        return tools

    def auto_activate_from_context(self, context: str) -> List[str]:
        """
        Automatically activate relevant domains from context.

        Args:
            context: Task context

        Returns:
            List of activated domain names
        """
        detected = self.detect_domain(context)
        activated = []

        for domain in detected[:2]:  # Activate top 2 domains max
            if self.activate_domain(domain):
                activated.append(domain)

        return activated

    def get_context_prompt(self, context: str) -> str:
        """
        Build a system prompt from context.

        Adds domain-specific prompts to enhance the agent's
        capability in the detected domain.

        Args:
            context: Task context

        Returns:
            Enhanced context with domain prompts
        """
        recommendations = self.recommend_skills(context, max_results=2)

        if not recommendations:
            return context

        parts = [context, "", "## Domain Context", ""]

        for skill in recommendations:
            parts.append(f"### {skill.name}")
            parts.append(f"**Domain**: {skill.domain}")
            parts.append(f"**Description**: {skill.description}")

            if "system" in skill.prompts:
                parts.append("")
                parts.append("**Guidelines**:")
                parts.append(skill.prompts["system"])

            parts.append("")

        return "\n".join(parts)


# Global singleton instance
_domain_skills = None


def get_domain_skills() -> DomainSkills:
    """Get the global DomainSkills singleton instance."""
    global _domain_skills
    if _domain_skills is None:
        _domain_skills = DomainSkills()
    return _domain_skills
