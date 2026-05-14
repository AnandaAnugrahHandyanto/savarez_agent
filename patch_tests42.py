with open("tests/run_agent/test_run_agent.py", "r") as f:
    content = f.read()

content = content.replace("category=ErrorCategory.client_error,", "")
with open("tests/run_agent/test_run_agent.py", "w") as f:
    f.write(content)
