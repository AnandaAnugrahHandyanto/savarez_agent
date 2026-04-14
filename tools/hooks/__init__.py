#!/usr/bin/env python3
"""Hermes Agent Hook System.

A Claude Code compatible hook system supporting:
- PreToolUse: Before tool execution
- PostToolUse: After tool execution
- Stop: Before agent stops
- UserPromptSubmit: Before user prompt is submitted
- SettingsChange: When settings change

Usage:
    from tools.hooks import initialize_hooks, execute_pre_tool_hook

    # Initialize hooks (call once at startup)
    initialize_hooks()

    # Execute PreToolUse hook
    result = execute_pre_tool_hook('Bash', {'command': 'ls -la'})
    if result.blocked:
        print(f"Blocked: {result.system_message}")
"""

from tools.hooks.registry import (
    HookRegistry,
    HookRule,
    HookResult,
    HookEvent,
    Hook,
    extract_frontmatter,
    load_hookify_rules,
)

from tools.hooks.hook_executor import (
    HookExecutor,
    get_executor,
    execute_pre_tool_hook,
    execute_post_tool_hook,
    execute_stop_hook,
    execute_user_prompt_hook,
    initialize_hooks,
)

from tools.hooks.builtin_security import (
    builtin_security_hook,
    register_builtin_security_hooks,
    DANGEROUS_BASH_PATTERNS,
    SENSITIVE_FILE_PATTERNS,
    PATH_TRAVERSAL_PATTERNS,
)

__all__ = [
    # Registry
    'HookRegistry',
    'HookRule',
    'HookResult',
    'HookEvent',
    'Hook',
    'extract_frontmatter',
    'load_hookify_rules',
    # Executor
    'HookExecutor',
    'get_executor',
    'execute_pre_tool_hook',
    'execute_post_tool_hook',
    'execute_stop_hook',
    'execute_user_prompt_hook',
    'initialize_hooks',
    # Builtin security
    'builtin_security_hook',
    'register_builtin_security_hooks',
    'DANGEROUS_BASH_PATTERNS',
    'SENSITIVE_FILE_PATTERNS',
    'PATH_TRAVERSAL_PATTERNS',
]
