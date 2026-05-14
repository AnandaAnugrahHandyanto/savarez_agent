with open("tests/run_agent/test_run_agent.py", "r") as f:
    content = f.read()

content = content.replace("mock_classify.return_value = ClassifiedError(", "mock_classify.return_value = ClassifiedError(\n            category=ErrorCategory.client_error,")
with open("tests/run_agent/test_run_agent.py", "w") as f:
    f.write(content)
