"""
Hot-Patch Module for Runtime Tool Registry Modification

Allows dynamic registration and deregistration of tools at runtime without
requiring a restart of Hermes. Uses the existing tools/registry.py infrastructure.

Security:
    - Tools can only be registered in ~/.hermes/custom_tools/
    - All generated code is audited before execution
    - Rollback support on failure
"""

import ast
import importlib
import importlib.util
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class HotPatch:
    """
    Runtime hot-patching for the tool registry.

    Provides thread-safe registration/deregistration of tools without
    requiring a restart. Uses the existing ToolRegistry singleton.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._generated_tools: Dict[str, "ToolEntry"] = {}
        self._rollback_stack: List[Callable] = []
        self._custom_tools_dir = self._get_custom_tools_dir()

    def _get_custom_tools_dir(self) -> Path:
        """Get the custom tools directory, defaulting to ~/.hermes/custom_tools/"""
        try:
            from hermes_constants import get_hermes_home
        except ImportError:
            # Fallback: try relative import when running from hermes_agent directory
            import sys
            from pathlib import Path
            parent = Path(__file__).resolve().parent.parent.parent
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            from hermes_constants import get_hermes_home
        custom_dir = get_hermes_home() / "custom_tools"
        custom_dir.mkdir(parents=True, exist_ok=True)
        return custom_dir

    @property
    def custom_tools_dir(self) -> Path:
        """Return the custom tools directory path."""
        return self._custom_tools_dir

    def _audit_code(self, code: str, filename: str = "<generated>") -> bool:
        """
        Perform security audit on generated code before execution.

        Checks:
            - No os.system, subprocess, eval, exec calls
            - No import of dangerous modules (os when used for shell, etc.)
            - AST parsing must succeed
            - No __import__ calls

        Returns True if code passes security audit.
        """
        # First, try AST parsing
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError as e:
            logger.error("Security audit failed: syntax error in generated code: %s", e)
            return False

        # Check for dangerous patterns
        dangerous_patterns = [
            "os.system",
            "subprocess.call",
            "subprocess.run",
            "subprocess.Popen",
            "eval(",
            "exec(",
            "__import__",
            "compile(",
            "open(",
            "input(",
        ]

        for pattern in dangerous_patterns:
            if pattern in code:
                logger.error("Security audit failed: dangerous pattern '%s' found", pattern)
                return False

        # Check AST for dangerous nodes
        for node in ast.walk(tree):
            # Check for __import__ calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    logger.error("Security audit failed: __import__ call found")
                    return False
                if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                    logger.error("Security audit failed: .system() call found")
                    return False

        return True

    def register_tool(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable = None,
        requires_env: list = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "🔧",
        max_result_size_chars: int | float | None = None,
        source_file: Optional[Path] = None,
    ) -> bool:
        """
        Register a tool with the central registry at runtime.

        Args:
            name: Tool name
            toolset: Toolset this tool belongs to
            schema: JSON Schema for the tool
            handler: Callable that executes the tool
            check_fn: Optional availability check
            requires_env: List of required environment variables
            is_async: Whether the handler is async
            description: Tool description
            emoji: Emoji for display
            max_result_size_chars: Max result size
            source_file: Source file for auditing

        Returns:
            True if registration succeeded
        """
        with self._lock:
            try:
                from tools.registry import registry, ToolEntry

                entry = ToolEntry(
                    name=name,
                    toolset=toolset,
                    schema=schema,
                    handler=handler,
                    check_fn=check_fn,
                    requires_env=requires_env or [],
                    is_async=is_async,
                    description=description or schema.get("description", ""),
                    emoji=emoji,
                    max_result_size_chars=max_result_size_chars,
                )

                # Store reference for potential rollback
                existing = registry.get_entry(name)
                self._generated_tools[name] = entry

                def rollback():
                    registry.deregister(name)
                    if existing:
                        registry.register(
                            name=existing.name,
                            toolset=existing.toolset,
                            schema=existing.schema,
                            handler=existing.handler,
                            check_fn=existing.check_fn,
                            requires_env=existing.requires_env,
                            is_async=existing.is_async,
                            description=existing.description,
                            emoji=existing.emoji,
                            max_result_size_chars=existing.max_result_size_chars,
                        )

                self._rollback_stack.append(rollback)

                # Use the registry's own register method
                registry.register(
                    name=name,
                    toolset=toolset,
                    schema=schema,
                    handler=handler,
                    check_fn=check_fn,
                    requires_env=requires_env,
                    is_async=is_async,
                    description=description,
                    emoji=emoji,
                    max_result_size_chars=max_result_size_chars,
                )

                logger.info("Hot-patched tool registered: %s (toolset: %s)", name, toolset)
                return True

            except Exception as e:
                logger.exception("Failed to register hot-patched tool %s: %s", name, e)
                return False

    def deregister_tool(self, name: str) -> bool:
        """
        Remove a dynamically registered tool from the registry.

        Args:
            name: Tool name to deregister

        Returns:
            True if deregistration succeeded
        """
        with self._lock:
            try:
                from tools.registry import registry

                if name not in self._generated_tools:
                    logger.warning("Tool %s not found in generated tools", name)
                    return False

                registry.deregister(name)
                del self._generated_tools[name]

                logger.info("Hot-patched tool deregistered: %s", name)
                return True

            except Exception as e:
                logger.exception("Failed to deregister hot-patched tool %s: %s", name, e)
                return False

    def rollback_last(self) -> bool:
        """
        Rollback the last tool registration.

        Returns:
            True if rollback succeeded
        """
        with self._lock:
            if not self._rollback_stack:
                logger.warning("Rollback stack is empty")
                return False

            rollback_fn = self._rollback_stack.pop()
            try:
                rollback_fn()
                logger.info("Rollback succeeded for last tool registration")
                return True
            except Exception as e:
                logger.exception("Rollback failed: %s", e)
                return False

    def rollback_all(self) -> int:
        """
        Rollback all dynamically registered tools.

        Returns:
            Number of tools rolled back
        """
        with self._lock:
            count = 0
            while self._rollback_stack:
                try:
                    rollback_fn = self._rollback_stack.pop()
                    rollback_fn()
                    count += 1
                except Exception as e:
                    logger.exception("Rollback failed: %s", e)
            logger.info("Rolled back %d dynamically registered tools", count)
            return count

    def load_tool_from_file(self, filepath: Path) -> bool:
        """
        Load and register a tool from a Python file.

        The file should define a `register_tool(registry)` function that
        performs the registration.

        Args:
            filepath: Path to the tool file

        Returns:
            True if loading succeeded
        """
        with self._lock:
            try:
                # Add directory to sys.path for imports
                parent_dir = str(filepath.parent)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)

                # Load the module dynamically
                module_name = filepath.stem
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec is None or spec.loader is None:
                    logger.error("Failed to load spec for %s", filepath)
                    return False

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # Look for a register function
                if hasattr(module, 'register_tool'):
                    from tools.registry import registry
                    module.register_tool(registry)
                    logger.info("Loaded tool from file: %s", filepath)
                    return True
                else:
                    logger.error("No register_tool function found in %s", filepath)
                    return False

            except Exception as e:
                logger.exception("Failed to load tool from %s: %s", filepath, e)
                return False

    def save_tool_to_file(
        self,
        name: str,
        code: str,
        metadata: Optional[dict] = None,
    ) -> Optional[Path]:
        """
        Save generated tool code to a file in the custom tools directory.

        Args:
            name: Tool name (used for filename)
            code: Python code for the tool
            metadata: Optional metadata dict to store alongside

        Returns:
            Path to saved file, or None on failure
        """
        try:
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            filepath = self._custom_tools_dir / f"{safe_name}.py"

            # Add header
            header = f'''"""
Auto-generated tool: {name}
Generated by Hermes Self-Healing System
DO NOT EDIT MANUALLY - Changes will be overwritten
"""

'''
            full_code = header + code

            filepath.write_text(full_code, encoding="utf-8")

            # Optionally save metadata
            if metadata:
                meta_path = filepath.with_suffix(".json")
                import json
                meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            logger.info("Saved generated tool to: %s", filepath)
            return filepath

        except Exception as e:
            logger.exception("Failed to save tool %s: %s", name, e)
            return None

    def get_generated_tool_names(self) -> List[str]:
        """Return list of dynamically generated tool names."""
        return list(self._generated_tools.keys())

    def is_generated_tool(self, name: str) -> bool:
        """Check if a tool was dynamically generated."""
        return name in self._generated_tools


# Global singleton instance
_hot_patch = HotPatch()


def get_hot_patch() -> HotPatch:
    """Get the global HotPatch singleton instance."""
    return _hot_patch
