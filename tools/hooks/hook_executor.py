#!/usr/bin/env python3
"""Hook executor for Hermes Agent.

Loads rules from .claude/hookify.*.local.md files and evaluates them against
hook events. Integrates with the HookRegistry to provide Claude Code compatible
hook execution.

Hook file format (compatible with Claude Code's hookify plugin):
---
name: rule-name
event: bash|file|stop|all
action: warn|block
tool-matcher: Bash|Edit|Write|*
order: 100
---
Rule description text (message body)
"""

import os
import sys
import re
import json
import glob
from typing import Dict, List, Any, Optional
from functools import lru_cache

from tools.hooks.registry import (
    HookRegistry,
    HookRule,
    HookResult,
    extract_frontmatter,
    load_hookify_rules,
    HookEvent,
)


# Cache compiled regexes
@lru_cache(maxsize=128)
def compile_regex(pattern: str) -> re.Pattern:
    """Compile regex pattern with caching."""
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        print(f"Invalid regex pattern '{pattern}': {e}", file=sys.stderr)
        return re.compile(r'(?!)')  # Never matches


class HookExecutor:
    """Executes hooks from hookify rule files."""

    def __init__(self, registry: Optional[HookRegistry] = None):
        """Initialize hook executor.

        Args:
            registry: HookRegistry instance. If None, uses singleton.
        """
        self.registry = registry or HookRegistry.get_instance()
        self._rules: List[HookRule] = []

    def load_rules(self, search_dirs: Optional[List[str]] = None) -> List[HookRule]:
        """Load rules from hookify files.

        Args:
            search_dirs: Directories to search for .claude/hookify.*.local.md files.
                        Defaults to current working directory.

        Returns:
            List of loaded HookRule objects.
        """
        if search_dirs is None:
            search_dirs = [os.getcwd()]

        self._rules = load_hookify_rules(search_dirs)
        self.registry.load_user_rules(self._rules)
        return self._rules

    def get_rules_for_event(self, event: str, tool_name: Optional[str] = None) -> List[HookRule]:
        """Get rules matching an event and optional tool.

        Args:
            event: Event type (PreToolUse, PostToolUse, Stop, UserPromptSubmit)
            tool_name: Optional tool name for filtering

        Returns:
            Filtered list of rules.
        """
        matching_rules = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Check if rule matches event
            if not rule.matches_event(event, tool_name):
                continue

            # Check tool matcher if specified
            if tool_name and rule.tool_matcher:
                if not rule.matches_tool(tool_name):
                    continue

            matching_rules.append(rule)

        # Sort by order
        matching_rules.sort(key=lambda r: r.order)
        return matching_rules

    def evaluate_rules(
        self,
        rules: List[HookRule],
        input_data: Dict[str, Any]
    ) -> HookResult:
        """Evaluate rules against input data.

        Args:
            rules: List of rules to evaluate
            input_data: Hook input data (tool_name, tool_input, etc.)

        Returns:
            Combined HookResult. Blocking rules take priority.
        """
        blocking_results: List[HookResult] = []
        warning_results: List[HookResult] = []

        for rule in rules:
            if self._rule_matches(rule, input_data):
                result = HookResult(
                    allowed=rule.action != 'block',
                    blocked=rule.action == 'block',
                    system_message=f"**[{rule.name}]**\n{rule.message}" if rule.message else None
                )

                if rule.action == 'block':
                    blocking_results.append(result)
                else:
                    warning_results.append(result)

        # If any blocking rules matched, block the operation
        if blocking_results:
            messages = [r.system_message for r in blocking_results if r.system_message]
            combined_message = "\n\n".join(messages)

            hook_event = input_data.get('hook_event_name', input_data.get('hook_event', 'PreToolUse'))

            if hook_event == 'Stop':
                return HookResult(
                    allowed=False,
                    blocked=True,
                    decision="block",
                    reason=combined_message,
                    system_message=combined_message
                )
            elif hook_event in ('PreToolUse', 'PostToolUse'):
                return HookResult(
                    allowed=False,
                    blocked=True,
                    hook_specific_output={
                        "hookEventName": hook_event,
                        "permissionDecision": "deny"
                    },
                    system_message=combined_message
                )
            else:
                return HookResult(
                    allowed=False,
                    blocked=True,
                    system_message=combined_message
                )

        # If only warnings, return combined warning
        if warning_results:
            messages = [r.system_message for r in warning_results if r.system_message]
            combined_message = "\n\n".join(messages)
            return HookResult.warn(combined_message)

        return HookResult.allow()

    def _rule_matches(self, rule: HookRule, input_data: Dict[str, Any]) -> bool:
        """Check if a rule matches the input data.

        Args:
            rule: Rule to check
            input_data: Hook input data

        Returns:
            True if rule matches, False otherwise.
        """
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        # Check tool matcher first
        if rule.tool_matcher and rule.tool_matcher != '*':
            if not rule.matches_tool(tool_name):
                return False

        # If no conditions, don't match (unless using legacy pattern)
        if not rule.conditions and not rule.pattern:
            return False

        # Check each condition
        for condition in rule.conditions:
            if not self._check_condition(condition, tool_name, tool_input, input_data):
                return False

        return True

    def _check_condition(
        self,
        condition: Dict[str, str],
        tool_name: str,
        tool_input: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> bool:
        """Check if a single condition matches.

        Args:
            condition: Condition dict with field, operator, pattern
            tool_name: Tool name
            tool_input: Tool input dict
            input_data: Full hook input

        Returns:
            True if condition matches.
        """
        field = condition.get('field', '')
        operator = condition.get('operator', 'regex_match')
        pattern = condition.get('pattern', '')

        # Extract field value
        field_value = self._extract_field(field, tool_name, tool_input, input_data)
        if field_value is None:
            return False

        # Apply operator
        if operator == 'regex_match':
            return self._regex_match(pattern, field_value)
        elif operator == 'contains':
            return pattern in field_value
        elif operator == 'equals':
            return pattern == field_value
        elif operator == 'not_contains':
            return pattern not in field_value
        elif operator == 'starts_with':
            return field_value.startswith(pattern)
        elif operator == 'ends_with':
            return field_value.endswith(pattern)
        else:
            return False

    def _extract_field(
        self,
        field: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Optional[str]:
        """Extract field value from tool input or hook input data.

        Args:
            field: Field name (command, new_text, file_path, etc.)
            tool_name: Tool name
            tool_input: Tool input dict
            input_data: Full hook input

        Returns:
            Field value as string, or None if not found.
        """
        # Direct tool_input fields
        if field in tool_input:
            value = tool_input[field]
            if isinstance(value, str):
                return value
            return str(value)

        # Handle special cases by tool type
        if tool_name == 'Bash':
            if field == 'command':
                return tool_input.get('command', '')

        elif tool_name in ('Write', 'patch', 'write_file'):
            if field in ('content', 'new_text', 'new_string'):
                return tool_input.get('content', tool_input.get('new_string', ''))
            elif field in ('old_text', 'old_string'):
                return tool_input.get('old_string', '')
            elif field == 'file_path':
                return tool_input.get('file_path', tool_input.get('path', ''))

        elif tool_name == 'Edit':
            if field in ('content', 'new_text', 'new_string'):
                return tool_input.get('new_string', '')
            elif field in ('old_text', 'old_string'):
                return tool_input.get('old_string', '')
            elif field == 'file_path':
                return tool_input.get('file_path', '')

        elif tool_name == 'MultiEdit':
            if field == 'file_path':
                return tool_input.get('file_path', '')
            elif field in ('new_text', 'content'):
                edits = tool_input.get('edits', [])
                return ' '.join(e.get('new_string', '') for e in edits)

        # For Stop events and other non-tool events
        if field == 'reason':
            return input_data.get('reason', '')
        elif field == 'user_prompt':
            return input_data.get('user_prompt', input_data.get('prompt', ''))
        elif field == 'transcript':
            transcript_path = input_data.get('transcript_path')
            if transcript_path:
                try:
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except (IOError, OSError, UnicodeDecodeError):
                    return ''

        return None

    def _regex_match(self, pattern: str, text: str) -> bool:
        """Check if pattern matches text using regex.

        Args:
            pattern: Regex pattern
            text: Text to match against

        Returns:
            True if pattern matches.
        """
        try:
            regex = compile_regex(pattern)
            return bool(regex.search(text))
        except re.error:
            return False


# Global executor instance
_executor: Optional[HookExecutor] = None


def get_executor() -> HookExecutor:
    """Get the global HookExecutor instance."""
    global _executor
    if _executor is None:
        _executor = HookExecutor()
    return _executor


def execute_pre_tool_hook(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_call_id: Optional[str] = None
) -> HookResult:
    """Execute PreToolUse hooks for a tool.

    Args:
        tool_name: Name of the tool being invoked
        tool_input: Dictionary of tool arguments
        tool_call_id: Optional tool call ID

    Returns:
        HookResult indicating if the tool should be allowed to execute.
    """
    executor = get_executor()

    input_data = {
        'hook_event_name': 'PreToolUse',
        'hook_event': 'PreToolUse',
        'tool_name': tool_name,
        'tool_input': tool_input,
        'tool_call_id': tool_call_id,
    }

    # Get matching rules
    rules = executor.get_rules_for_event('PreToolUse', tool_name)

    # Execute built-in hooks first
    registry = HookRegistry.get_instance()
    builtin_hooks = registry.get_hooks('PreToolUse')
    builtin_hooks = [h for h in builtin_hooks if h.is_builtin]

    # Execute builtin hooks
    for hook in builtin_hooks:
        try:
            result = hook.callback(tool_name, tool_input, 'PreToolUse')
            if result.blocked:
                return result
            if result.system_message:
                # Store warning but continue
                pass
        except Exception as e:
            print(f"Warning: Builtin hook {hook.name} failed: {e}", file=sys.stderr)

    # Execute user rules
    if rules:
        result = executor.evaluate_rules(rules, input_data)
        if result.blocked:
            return result

    return HookResult.allow()


def execute_post_tool_hook(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_result: Any,
    tool_call_id: Optional[str] = None
) -> HookResult:
    """Execute PostToolUse hooks after a tool executes.

    Args:
        tool_name: Name of the tool that was invoked
        tool_input: Dictionary of tool arguments
        tool_result: Result from the tool execution
        tool_call_id: Optional tool call ID

    Returns:
        HookResult (typically informational, warnings only).
    """
    executor = get_executor()

    input_data = {
        'hook_event_name': 'PostToolUse',
        'hook_event': 'PostToolUse',
        'tool_name': tool_name,
        'tool_input': tool_input,
        'tool_result': str(tool_result) if tool_result else '',
        'tool_call_id': tool_call_id,
    }

    # Get matching rules
    rules = executor.get_rules_for_event('PostToolUse', tool_name)

    if not rules:
        return HookResult.allow()

    return executor.evaluate_rules(rules, input_data)


def execute_stop_hook(reason: str, transcript_path: Optional[str] = None) -> HookResult:
    """Execute Stop hooks when agent is stopping.

    Args:
        reason: Reason for stopping
        transcript_path: Optional path to transcript file

    Returns:
        HookResult indicating if stop should be blocked.
    """
    executor = get_executor()

    input_data = {
        'hook_event_name': 'Stop',
        'hook_event': 'Stop',
        'reason': reason,
        'transcript_path': transcript_path,
    }

    # Get matching rules
    rules = executor.get_rules_for_event('Stop')

    if not rules:
        return HookResult.allow()

    return executor.evaluate_rules(rules, input_data)


def execute_user_prompt_hook(user_prompt: str) -> HookResult:
    """Execute UserPromptSubmit hooks when user submits a prompt.

    Args:
        user_prompt: The user's prompt text

    Returns:
        HookResult indicating if the prompt should be allowed.
    """
    executor = get_executor()

    input_data = {
        'hook_event_name': 'UserPromptSubmit',
        'hook_event': 'UserPromptSubmit',
        'user_prompt': user_prompt,
        'prompt': user_prompt,
    }

    # Get matching rules
    rules = executor.get_rules_for_event('UserPromptSubmit')

    if not rules:
        return HookResult.allow()

    return executor.evaluate_rules(rules, input_data)


def initialize_hooks(search_dirs: Optional[List[str]] = None) -> None:
    """Initialize the hook system.

    Args:
        search_dirs: Directories to search for hookify rule files.
    """
    from tools.hooks.builtin_security import register_builtin_security_hooks

    # Register built-in security hooks
    register_builtin_security_hooks()

    # Load user rules
    executor = get_executor()
    executor.load_rules(search_dirs)


# CLI for testing
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Hook executor CLI')
    parser.add_argument('--load', action='store_true', help='Load and display rules')
    parser.add_argument('--test', metavar='TOOL', help='Test PreToolUse for a tool')
    parser.add_argument('--test-bash', metavar='CMD', help='Test PreToolUse for a bash command')
    parser.add_argument('--init', action='store_true', help='Initialize hooks')

    args = parser.parse_args()

    if args.init:
        initialize_hooks()
        print("Hooks initialized")

    if args.load:
        executor = get_executor()
        rules = executor.load_rules()
        print(f"Loaded {len(rules)} rules:")
        for r in rules:
            print(f"  - {r.name}: event={r.event}, action={r.action}, tool_matcher={r.tool_matcher}, order={r.order}")
            if r.conditions:
                print(f"    conditions: {r.conditions}")

    if args.test:
        initialize_hooks()
        result = execute_pre_tool_hook(args.test, {})
        print(f"Result: {result.to_dict()}")

    if args.test_bash:
        initialize_hooks()
        result = execute_pre_tool_hook('Bash', {'command': args.test_bash})
        print(f"Result: {result.to_dict()}")
