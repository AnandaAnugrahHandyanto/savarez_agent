with open("tests/run_agent/test_run_agent.py", "r") as f:
    content = f.read()

# I see it logged: "WARNING  run_agent:run_agent.py:13624 API call failed (attempt 1/3) error_type=_ContextError"
# We should probably capture stdout and check what's going on. Let's add a print inside the test.
