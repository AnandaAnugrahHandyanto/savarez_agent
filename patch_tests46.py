with open("tests/run_agent/test_run_agent.py", "r") as f:
    content = f.read()

content = content.replace("agent._compress_context = MagicMock(return_value=([], \"system\"))", "agent._vprint = MagicMock()\n        agent._compress_context = MagicMock(return_value=([], \"system\"))")

with open("tests/run_agent/test_run_agent.py", "w") as f:
    f.write(content)
