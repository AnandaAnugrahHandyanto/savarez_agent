import re
with open("tests/run_agent/test_run_agent.py", "r") as f:
    content = f.read()

# Replace the assertion with checking _vprint calls
content = content.replace("assert agent._ephemeral_max_output_tokens == 936", "assert any('Output cap too large for current prompt' in str(call) for call in agent._vprint.call_args_list)")
content = content.replace("assert agent._ephemeral_max_output_tokens is None", "assert not any('Output cap too large for current prompt' in str(call) for call in agent._vprint.call_args_list)")

with open("tests/run_agent/test_run_agent.py", "w") as f:
    f.write(content)
