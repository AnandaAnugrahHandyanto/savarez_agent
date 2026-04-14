#!/usr/bin/env python3
"""Global hook registry for Hermes Agent.

Supports PreToolUse / PostToolUse / Stop / UserPromptSubmit / SettingsChange events.
Hooks are sorted by 'order' field (lower = earlier execution).
"""

import os
import sys
import glob
import re
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class HookEvent(str, Enum):
    """Supported hook event types."""
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    SETTINGS_CHANGE = "SettingsChange"
    # Aliases for rule matching
    BASH = "bash"
    FILE = "file"
    ALL = "all"


@dataclass
class HookResult:
    """Result from a hook execution."""
    allowed: bool = True
    blocked: bool = False
    system_message: Optional[str] = None
    hook_specific_output: Optional[Dict[str, Any]] = None
    decision: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Claude Code compatible dict format."""
        if self.blocked:
            if self.hook_specific_output:
                return {
                    "hookSpecificOutput": self.hook_specific_output,
                    "systemMessage": self.system_message or ""
                }
            elif self.decision == "block":
                return {
                    "decision": "block",
                    "reason": self.reason or self.system_message or "",
                    "systemMessage": self.system_message or ""
                }
            else:
                return {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny"
                    },
                    "systemMessage": self.system_message or ""
                }
        elif self.system_message:
            return {"systemMessage": self.system_message}
        return {}

    @staticmethod
    def allow() -> "HookResult":
        return HookResult(allowed=True, blocked=False)

    @staticmethod
    def block(message: str, reason: Optional[str] = None) -> "HookResult":
        return HookResult(
            allowed=False,
            blocked=True,
            system_message=message,
            decision="block",
            reason=reason or message
        )

    @staticmethod
    def deny(hook_event: str = "PreToolUse") -> "HookResult":
        return HookResult(
            allowed=False,
            blocked=True,
            hook_specific_output={
                "hookEventName": hook_event,
                "permissionDecision": "deny"
            }
        )

    @staticmethod
    def warn(message: str) -> "HookResult":
        return HookResult(
            allowed=True,
            blocked=False,
            system_message=message
        )


@dataclass
class HookRule:
    """A single hook rule."""
    name: str
    event: str  # "bash", "file", "stop", "all", "prompt", "settings"
    action: str = "warn"  # "warn", "block"
    tool_matcher: Optional[str] = None  # "Bash", "Edit|Write", "*"
    pattern: Optional[str] = None  # Legacy pattern field
    conditions: List[Dict[str, str]] = field(default_factory=list)
    message: str = ""
    order: int = 100  # Lower = earlier execution
    enabled: bool = True

    @classmethod
    def from_frontmatter(cls, frontmatter: Dict[str, Any], message: str) -> "HookRule":
        """Create HookRule from parsed frontmatter."""
        conditions = []
        # Handle conditions list
        if 'conditions' in frontmatter:
            for c in frontmatter.get('conditions', []):
                if isinstance(c, dict):
                    conditions.append(c)
                elif isinstance(c, str) and ':' in c:
                    # Inline format: "field: command, operator: regex_match, pattern: rm"
                    parts = {}
                    for part in c.split(','):
                        if ':' in part:
                            k, v = part.split(':', 1)
                            parts[k.strip()] = v.strip()
                    if parts:
                        conditions.append(parts)

        # Legacy pattern -> condition conversion
        simple_pattern = frontmatter.get('pattern')
        event = frontmatter.get('event', 'all')

        if simple_pattern and not conditions:
            if event == 'bash':
                field = 'command'
            elif event in ('file', 'stop', 'all'):
                field = 'content'
            else:
                field = 'content'
            conditions.append({
                'field': field,
                'operator': 'regex_match',
                'pattern': simple_pattern
            })

        return cls(
            name=frontmatter.get('name', 'unnamed'),
            event=frontmatter.get('event', 'all'),
            action=frontmatter.get('action', 'warn'),
            tool_matcher=frontmatter.get('tool-matcher'),
            pattern=simple_pattern,
            conditions=conditions,
            message=message.strip(),
            order=int(frontmatter.get('order', 100)),
            enabled=frontmatter.get('enabled', True)
        )

    def matches_event(self, event: str, tool_name: Optional[str] = None) -> bool:
        """Check if this rule matches the given event."""
        if not self.enabled:
            return False

        # 'all' matches everything except specific events
        if self.event in ('all', event):
            return True

        # Map event types
        event_map = {
            'PreToolUse': {
                'Bash': 'bash',
                'Edit': 'file', 'Write': 'file', 'MultiEdit': 'file',
                'Read': 'file', 'read_file': 'file',
            },
            'PostToolUse': {
                'Bash': 'bash',
                'Edit': 'file', 'Write': 'file', 'MultiEdit': 'file',
                'Read': 'file', 'read_file': 'file',
            }
        }

        if event in event_map and tool_name:
            mapped = event_map[event].get(tool_name)
            if mapped and (self.event == mapped or self.event == 'all'):
                return True

        return False

    def matches_tool(self, tool_name: str) -> bool:
        """Check if this rule matches the given tool."""
        if not self.tool_matcher or self.tool_matcher == '*':
            return True
        return tool_name in self.tool_matcher.split('|')


@dataclass
class Hook:
    """A registered hook callback."""
    name: str
    event: str
    callback: Callable[..., HookResult]
    order: int = 100
    is_builtin: bool = False


class HookRegistry:
    """Global hook registry singleton."""

    _instance: Optional["HookRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._hooks: Dict[str, List[Hook]] = {
                HookEvent.PRE_TOOL_USE: [],
                HookEvent.POST_TOOL_USE: [],
                HookEvent.STOP: [],
                HookEvent.USER_PROMPT_SUBMIT: [],
                HookEvent.SETTINGS_CHANGE: [],
            }
            cls._instance._rules_loaded: bool = False
            cls._instance._user_rules: List[HookRule] = []
            cls._instance._builtin_hooks: List[Hook] = []
        return cls._instance

    def __init__(self):
        pass

    @classmethod
    def get_instance(cls) -> "HookRegistry":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_hook(
        self,
        event: str,
        callback: Callable[..., HookResult],
        name: Optional[str] = None,
        order: int = 100,
        is_builtin: bool = False
    ) -> None:
        """Register a hook callback for an event."""
        hook_name = name or callback.__name__
        hook = Hook(name=hook_name, event=event, callback=callback, order=order, is_builtin=is_builtin)

        # Map event string to HookEvent
        event_key = self._normalize_event(event)
        if event_key:
            self._hooks[event_key].append(hook)
            # Sort by order
            self._hooks[event_key].sort(key=lambda h: h.order)

    def register_builtin_hook(
        self,
        event: str,
        callback: Callable[..., HookResult],
        name: Optional[str] = None,
        order: int = 50
    ) -> None:
        """Register a builtin security hook (executes before user hooks)."""
        self.register_hook(event, callback, name, order, is_builtin=True)

    def _normalize_event(self, event: str) -> Optional[HookEvent]:
        """Normalize event string to HookEvent enum."""
        event_lower = event.lower()
        mapping = {
            'pretooluse': HookEvent.PRE_TOOL_USE,
            'posttooluse': HookEvent.POST_TOOL_USE,
            'stop': HookEvent.STOP,
            'userpromptsubmit': HookEvent.USER_PROMPT_SUBMIT,
            'settingschange': HookEvent.SETTINGS_CHANGE,
            'bash': HookEvent.PRE_TOOL_USE,  # For rule filtering
            'file': HookEvent.PRE_TOOL_USE,
        }
        return mapping.get(event_lower)

    def get_hooks(self, event: str) -> List[Hook]:
        """Get all hooks for an event, sorted by order."""
        event_key = self._normalize_event(event)
        if not event_key:
            return []
        return self._hooks.get(event_key, [])

    def get_all_hooks_for_event(self, event: str) -> List[Hook]:
        """Get all hooks (builtin + user) for an event in execution order."""
        builtin = [h for h in self.get_hooks(event) if h.is_builtin]
        user = [h for h in self.get_hooks(event) if not h.is_builtin]
        return builtin + user

    def load_user_rules(self, rules: List[HookRule]) -> None:
        """Load user-defined rules from hook files."""
        self._user_rules = rules
        self._rules_loaded = True

    def get_user_rules(self) -> List[HookRule]:
        """Get loaded user rules."""
        return self._user_rules

    def clear_hooks(self) -> None:
        """Clear all registered hooks (for testing)."""
        for key in self._hooks:
            self._hooks[key] = []
        self._user_rules = []
        self._rules_loaded = False


def extract_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Extract YAML frontmatter and message body from markdown.

    Returns (frontmatter_dict, message_body).
    """
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    frontmatter_text = parts[1]
    message = parts[2].strip()

    frontmatter = {}
    lines = frontmatter_text.split('\n')

    current_key = None
    current_list = []
    current_dict = {}
    in_list = False
    in_dict_item = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        indent = len(line) - len(line.lstrip())

        if indent == 0 and ':' in line and not line.strip().startswith('-'):
            if in_list and current_key:
                if in_dict_item and current_dict:
                    current_list.append(current_dict)
                    current_dict = {}
                frontmatter[current_key] = current_list
                in_list = False
                in_dict_item = False
                current_list = []

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if not value:
                current_key = key
                in_list = True
                current_list = []
            else:
                value = value.strip('"').strip("'")
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                frontmatter[key] = value

        elif stripped.startswith('-') and in_list:
            if in_dict_item and current_dict:
                current_list.append(current_dict)
                current_dict = {}

            item_text = stripped[1:].strip()

            if ':' in item_text and ',' in item_text:
                item_dict = {}
                for part in item_text.split(','):
                    if ':' in part:
                        k, v = part.split(':', 1)
                        item_dict[k.strip()] = v.strip().strip('"').strip("'")
                current_list.append(item_dict)
                in_dict_item = False
            elif ':' in item_text:
                in_dict_item = True
                k, v = item_text.split(':', 1)
                current_dict = {k.strip(): v.strip().strip('"').strip("'")}
            else:
                current_list.append(item_text.strip('"').strip("'"))
                in_dict_item = False

        elif indent > 2 and in_dict_item and ':' in line:
            k, v = stripped.split(':', 1)
            current_dict[k.strip()] = v.strip().strip('"').strip("'")

    if in_list and current_key:
        if in_dict_item and current_dict:
            current_list.append(current_dict)
        frontmatter[current_key] = current_list

    return frontmatter, message


def parse_hookify_file(file_path: str) -> Optional[HookRule]:
    """Parse a single hookify .local.md file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, message = extract_frontmatter(content)
        if not frontmatter:
            return None

        return HookRule.from_frontmatter(frontmatter, message)

    except (IOError, OSError, PermissionError) as e:
        print(f"Warning: Cannot read {file_path}: {e}", file=sys.stderr)
        return None
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
        return None
    except UnicodeDecodeError as e:
        print(f"Warning: Invalid encoding in {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: Unexpected error loading {file_path} ({type(e).__name__}): {e}", file=sys.stderr)
        return None


def load_hookify_rules(search_dirs: Optional[List[str]] = None) -> List[HookRule]:
    """Load all hookify rules from .claude directories.

    Args:
        search_dirs: List of directories to search. Defaults to current working directory.

    Returns:
        List of HookRule objects.
    """
    if search_dirs is None:
        search_dirs = [os.getcwd()]

    rules = []
    for search_dir in search_dirs:
        pattern = os.path.join(search_dir, '.claude', 'hookify.*.local.md')
        files = glob.glob(pattern)

        for file_path in files:
            rule = parse_hookify_file(file_path)
            if rule and rule.enabled:
                rules.append(rule)

    # Sort by order
    rules.sort(key=lambda r: r.order)
    return rules
