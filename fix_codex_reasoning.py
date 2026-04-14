#!/usr/bin/env python3
path = '/Users/lierdong/.hermes/hermes-agent/run_agent.py'
with open(path, 'r') as f:
    content = f.read()

# The exact string to find and replace
old = '''                else:
                    kwargs["reasoning"] = {"effort": reasoning_effort, "summary": "auto"}
                    kwargs["include"] = ["reasoning.encrypted_content"]'''

new = '''                else:
                    kwargs["reasoning"] = {"effort": reasoning_effort, "summary": "auto"}
                    if self.thinking_budget is not None:
                        kwargs["reasoning"]["budget"] = self.thinking_budget
                    kwargs["include"] = ["reasoning.encrypted_content"]'''

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(content)
    print("SUCCESS: replacement done")
else:
    print("ERROR: pattern not found")
    # Print what we actually have around the target
    idx = content.find('kwargs["reasoning"] = {"effort": reasoning_effort')
    if idx >= 0:
        print("Found at idx", idx)
        print(repr(content[idx-20:idx+200]))
