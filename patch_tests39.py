with open("tests/run_agent/test_run_agent.py", "r") as f:
    content = f.read()

print("test_context_error" in content)
