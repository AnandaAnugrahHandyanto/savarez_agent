#!/usr/bin/env python3
path = '/Users/lierdong/.hermes/hermes-agent/hermes_cli/config.py'
with open(path, 'r') as f:
    content = f.read()

old = '''        "service_tier": "",
        # Tool-use enforcement'''

new = '''        "service_tier": "",
        # Thinking budget (token limit for extended thinking/reasoning).
        # None = use provider default. Set to an integer to cap reasoning tokens.
        # Maps to the "budget" field in provider reasoning API calls.
        "thinking_budget": None,
        # Tool-use enforcement'''

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(content)
    print("SUCCESS: replacement done")
else:
    print("ERROR: pattern not found")
