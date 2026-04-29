"""
Tool Generator Module - Automatic Tool Creation

When `handle_function_call()` encounters a missing tool, this module
analyzes the requirement and generates new tool code that is immediately
registered via hot_patch.

Design Philosophy (browser-use/browser-harness inspired):
    - Agent encounters missing helper function
    - Instead of failing, agent generates the function code
    - Code is written to a harness file and immediately loaded
    - Tool becomes available without restart

Security:
    - Generated code is audited before execution
    - Only written to ~/.hermes/custom_tools/
    - Rollback on execution failure
"""

import ast
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Tool generation templates for common patterns
_TOOL_TEMPLATES = {
    "file_search": '''"""
Generated tool: {name}
{description}
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def {name}(args: Dict[str, Any], **kwargs) -> str:
    """
    {description}

    Args:
        {arg_docs}
    Returns:
        JSON result string
    """
    try:
        {implementation}
        return json.dumps({{"status": "success", "result": result}})
    except Exception as e:
        logger.exception("Tool {name} failed")
        return json.dumps({{"error": str(e)}})


def register_tool(registry):
    """Register this tool with the registry."""
    registry.register(
        name="{name}",
        toolset="custom",
        schema={schema},
        handler={name},
        description="{description}",
        emoji="🔧",
    )
''',

    "api_call": '''"""
Generated tool: {name}
{description}
"""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

def {name}(args: Dict[str, Any], **kwargs) -> str:
    """
    {description}

    Args:
        {arg_docs}
    Returns:
        JSON result string
    """
    try:
        {implementation}
        return json.dumps({{"status": "success", "result": result}})
    except Exception as e:
        logger.exception("Tool {name} failed")
        return json.dumps({{"error": str(e)}})


def register_tool(registry):
    """Register this tool with the registry."""
    registry.register(
        name="{name}",
        toolset="custom",
        schema={schema},
        handler={name},
        description="{description}",
        emoji="🌐",
    )
''',

    "data_processing": '''"""
Generated tool: {name}
{description}
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def {name}(args: Dict[str, Any], **kwargs) -> str:
    """
    {description}

    Args:
        {arg_docs}
    Returns:
        JSON result string
    """
    try:
        {implementation}
        return json.dumps({{"status": "success", "result": result}})
    except Exception as e:
        logger.exception("Tool {name} failed")
        return json.dumps({{"error": str(e)}})


def register_tool(registry):
    """Register this tool with the registry."""
    registry.register(
        name="{name}",
        toolset="custom",
        schema={schema},
        handler={name},
        description="{description}",
        emoji="📊",
    )
''',

    "terminal_command": '''"""
Generated tool: {name}
{description}
"""

import json
import logging
import subprocess
from typing import Any, Dict

logger = logging.getLogger(__name__)

def {name}(args: Dict[str, Any], **kwargs) -> str:
    """
    {description}

    Args:
        {arg_docs}
    Returns:
        JSON result string
    """
    try:
        command = args.get("command", "")
        if not command:
            return json.dumps({{"error": "No command provided"}})

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.dumps({{
            "status": "success",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }})
    except subprocess.TimeoutExpired:
        return json.dumps({{"error": "Command timed out"}})
    except Exception as e:
        logger.exception("Tool {name} failed")
        return json.dumps({{"error": str(e)}})


def register_tool(registry):
    """Register this tool with the registry."""
    registry.register(
        name="{name}",
        toolset="custom",
        schema={schema},
        handler={name},
        description="{description}",
        emoji="💻",
    )
''',
}


class ToolGenerator:
    """
    Generates new tool code when tools are missing.

    Analyzes the required tool schema/interface and generates
    Python code that implements the tool, then registers it
    via hot_patch.
    """

    def __init__(self):
        self._hot_patch = None  # Lazy loaded
        self._generation_history: List[Dict] = []
        self._lock = None  # Lazy loaded threading lock

    @property
    def hot_patch(self):
        """Lazy-load hot_patch to avoid circular imports."""
        if self._hot_patch is None:
            try:
                from self_healing.hot_patch import get_hot_patch
            except ImportError:
                from hermes_agent.self_healing.hot_patch import get_hot_patch
            self._hot_patch = get_hot_patch()
        return self._hot_patch

    @property
    def lock(self):
        """Lazy-load threading lock."""
        if self._lock is None:
            import threading
            self._lock = threading.RLock()
        return self._lock

    def _infer_tool_category(self, name: str, schema: Dict) -> str:
        """Infer the tool category based on name and schema."""
        name_lower = name.lower()
        schema_str = json.dumps(schema).lower()

        if any(kw in name_lower for kw in ["search", "find", "grep", "query"]):
            return "file_search"
        if any(kw in name_lower for kw in ["api", "http", "fetch", "request", "web"]):
            return "api_call"
        if any(kw in name_lower for kw in ["process", "transform", "parse", "convert", "analyze"]):
            return "data_processing"
        if any(kw in name_lower for kw in ["run", "exec", "command", "shell"]):
            return "terminal_command"

        # Check schema for hints
        if "command" in schema_str or "shell" in schema_str:
            return "terminal_command"
        if "url" in schema_str or "endpoint" in schema_str:
            return "api_call"

        return "file_search"  # Default

    def _generate_schema_from_name_and_context(
        self, name: str, description: str = "", context: Optional[Dict] = None
    ) -> Dict:
        """
        Generate a basic JSON Schema from tool name and context.

        This is used when no explicit schema is provided.
        """
        schema = {
            "name": name,
            "description": description or f"Auto-generated tool: {name}",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }

        # Try to infer parameters from name
        # Common patterns: <action>_<target>
        parts = name.split("_")
        if len(parts) >= 2:
            action = parts[0]
            target = "_".join(parts[1:])

            if action in ["get", "fetch", "retrieve"]:
                schema["parameters"]["properties"] = {
                    "query": {
                        "type": "string",
                        "description": f"Query to search for in {target}",
                    }
                }
                schema["parameters"]["required"] = ["query"]

            elif action in ["set", "update", "modify"]:
                schema["parameters"]["properties"] = {
                    "value": {
                        "type": "string",
                        "description": f"New value for {target}",
                    }
                }
                schema["parameters"]["required"] = ["value"]

            elif action in ["list", "ls", "show"]:
                schema["parameters"]["properties"] = {
                    "path": {
                        "type": "string",
                        "description": f"Path to {target}",
                    }
                }

        return schema

    def _generate_implementation(
        self, name: str, category: str, schema: Dict
    ) -> str:
        """Generate the implementation code for a tool."""
        if category == "terminal_command":
            return '''command = args.get("command", "")
        if not command:
            return json.dumps({"error": "No command provided"})
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return json.dumps({"status": "success", "output": result.stdout})'''

        if category == "api_call":
            return '''url = args.get("url", "")
        if not url:
            return json.dumps({"error": "No URL provided"})

        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = response.read().decode("utf-8")
            return json.dumps({"status": "success", "data": data[:1000]})
        except Exception as e:
            return json.dumps({"error": str(e)})'''

        if category == "data_processing":
            return '''data = args.get("data", "")
        if not data:
            return json.dumps({"error": "No data provided"})
        # Simple processing: count lines/words
        lines = data.split("\\n")
        result = {
            "line_count": len(lines),
            "word_count": len(data.split()),
            "char_count": len(data),
        }
        return json.dumps({"status": "success", "result": result})'''

        # Default file_search
        return '''query = args.get("query", "")
        path = args.get("path", ".")
        if not query:
            return json.dumps({"error": "No query provided"})

        # Simple file search using grep-like logic
        import os
        matches = []
        for root, dirs, files in os.walk(path):
            for f in files:
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                        if query in fh.read():
                            matches.append(filepath)
                except Exception:
                    pass
        return json.dumps({"status": "success", "matches": matches[:20]})'''

    def _generate_arg_docs(self, schema: Dict) -> str:
        """Generate argument documentation from schema."""
        props = schema.get("parameters", {}).get("properties", {})
        if not props:
            return "args: Dict[str, Any] - Tool arguments"

        docs = []
        for param_name, param_schema in props.items():
            param_type = param_schema.get("type", "string")
            param_desc = param_schema.get("description", f"The {param_name} parameter")
            docs.append(f"        {param_name} ({param_type}): {param_desc}")
        return ",\n".join(docs) if docs else "        args: Dict[str, Any] - Tool arguments"

    def generate_tool(
        self,
        tool_name: str,
        description: str = "",
        schema: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Generate and register a new tool.

        Args:
            tool_name: Name of the tool to generate
            description: Tool description
            schema: JSON Schema for the tool (generated if not provided)
            context: Additional context about how the tool should work

        Returns:
            Tuple of (success, error_message)
        """
        with self.lock:
            try:
                # Validate tool name
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", tool_name):
                    return False, f"Invalid tool name: {tool_name}"

                # Check if tool already exists
                try:
                    from tools.registry import registry
                    if registry.get_entry(tool_name):
                        return False, f"Tool {tool_name} already exists"
                except Exception:
                    pass

                # Generate schema if not provided
                if schema is None:
                    schema = self._generate_schema_from_name_and_context(
                        tool_name, description, context
                    )

                # Infer category
                category = self._infer_tool_category(tool_name, schema)

                # Get template
                template = _TOOL_TEMPLATES.get(category, _TOOL_TEMPLATES["file_search"])

                # Generate implementation
                implementation = self._generate_implementation(category, schema)

                # Build tool code
                tool_code = template.format(
                    name=tool_name,
                    description=description or f"Auto-generated tool: {tool_name}",
                    arg_docs=self._generate_arg_docs(schema),
                    implementation=implementation,
                    schema=json.dumps(schema, indent=8),
                )

                # Audit code before any execution
                if not self.hot_patch._audit_code(tool_code):
                    return False, "Generated code failed security audit"

                # Save to file
                filepath = self.hot_patch.save_tool_to_file(
                    tool_name, tool_code, metadata={"category": category}
                )
                if filepath is None:
                    return False, "Failed to save generated tool"

                # Load the tool from file
                if not self.hot_patch.load_tool_from_file(filepath):
                    return False, "Failed to load generated tool"

                # Record generation
                self._generation_history.append({
                    "name": tool_name,
                    "timestamp": time.time(),
                    "category": category,
                    "filepath": str(filepath),
                })

                logger.info(
                    "Generated and registered new tool: %s (category: %s)",
                    tool_name, category
                )
                return True, None

            except Exception as e:
                logger.exception("Tool generation failed for %s: %s", tool_name, e)
                return False, str(e)

    def generate_wrapper_tool(
        self,
        tool_name: str,
        target_function: str,
        target_module: str,
        description: str = "",
        arg_mapping: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Generate a wrapper tool that calls an existing function.

        Args:
            tool_name: Name for the new wrapper tool
            target_function: Function to wrap (e.g., "my_function")
            target_module: Module containing the function (e.g., "mymodule")
            description: Tool description
            arg_mapping: Map of tool args to function kwargs

        Returns:
            Tuple of (success, error_message)
        """
        with self.lock:
            try:
                import json

                wrapper_code = f'''"""
Generated wrapper tool: {tool_name}
Wraps: {target_module}.{target_function}
{description or ""}
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def {tool_name}(args: Dict[str, Any], **kwargs) -> str:
    """
    Wrapper for {target_module}.{target_function}
    {description or "Auto-generated wrapper tool"}
    """
    try:
        import {target_module}
        func = getattr({target_module}, "{target_function}", None)
        if func is None:
            return json.dumps({{"error": "Function not found"}})

        # Map arguments
        func_args = args.copy()
        if {arg_mapping!r}:
            func_args = {{{arg_mapping[k]: args.get(k, v) for k, v in {arg_mapping!r}.items()}}}

        result = func(**func_args)
        return json.dumps({{"status": "success", "result": result}})
    except Exception as e:
        logger.exception("Wrapper tool {tool_name} failed")
        return json.dumps({{"error": str(e)}})


def register_tool(registry):
    """Register this tool with the registry."""
    registry.register(
        name="{tool_name}",
        toolset="custom",
        schema={{
            "name": "{tool_name}",
            "description": "{description or f'Wrapper for {target_module}.{target_function}'}",
            "parameters": {{
                "type": "object",
                "properties": {{}},
                "required": [],
            }},
        }},
        handler={tool_name},
        description="{description or f'Wrapper for {target_module}.{target_function}'}",
        emoji="🔗",
    )
'''

                # Audit and save
                if not self.hot_patch._audit_code(wrapper_code):
                    return False, "Generated wrapper code failed security audit"

                filepath = self.hot_patch.save_tool_to_file(
                    tool_name, wrapper_code,
                    metadata={"type": "wrapper", "target": f"{target_module}.{target_function}"}
                )
                if filepath is None:
                    return False, "Failed to save wrapper tool"

                if not self.hot_patch.load_tool_from_file(filepath):
                    return False, "Failed to load wrapper tool"

                logger.info("Generated wrapper tool: %s -> %s.%s",
                           tool_name, target_module, target_function)
                return True, None

            except Exception as e:
                logger.exception("Wrapper generation failed: %s", e)
                return False, str(e)

    def handle_missing_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        error_message: str,
        context: Optional[Dict] = None,
    ) -> str:
        """
        Handle a missing tool by generating and registering it.

        This is the main entry point called when handle_function_call()
        encounters an unknown tool.

        Args:
            tool_name: Name of missing tool
            tool_args: Arguments that were passed
            error_message: The error from the failed call
            context: Additional context

        Returns:
            Result of the tool call after generation, or error
        """
        from model_tools import handle_function_call

        # Try to generate the tool
        success, error = self.generate_tool(
            tool_name=tool_name,
            description=f"Auto-generated tool to handle: {tool_name}",
            context=context,
        )

        if not success:
            return json.dumps({
                "error": f"Tool generation failed: {error}",
                "original_error": error_message,
            })

        # Retry the tool call
        try:
            return handle_function_call(tool_name, tool_args)
        except Exception as e:
            # Rollback on failure
            self.hot_patch.rollback_last()
            return json.dumps({
                "error": f"Generated tool execution failed: {str(e)}",
                "original_error": error_message,
            })

    def get_generation_history(self) -> List[Dict]:
        """Return the history of tool generations."""
        return list(self._generation_history)

    def clear_history(self) -> None:
        """Clear the generation history."""
        self._generation_history.clear()


# Global singleton instance
_tool_generator = None


def get_tool_generator() -> ToolGenerator:
    """Get the global ToolGenerator singleton instance."""
    global _tool_generator
    if _tool_generator is None:
        _tool_generator = ToolGenerator()
    return _tool_generator
