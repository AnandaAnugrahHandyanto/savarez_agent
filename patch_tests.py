with open("tests/tools/test_code_execution.py", "r") as f:
    content = f.read()

content = content.replace('@unittest.skipIf(sys.platform == "win32", "UDS not available on Windows")\n', '')

with open("tests/tools/test_code_execution.py", "w") as f:
    f.write(content)
