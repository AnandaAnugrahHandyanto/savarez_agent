## 2024-05-24 - Security Enhancement: YAML Parsing & Subprocess Execution
**Vulnerability:** Use of `yaml.load` and `subprocess.run(shell=True)`.
**Learning:** Even when `yaml.load` uses a `SafeLoader`, it is best practice to use `yaml.safe_load` directly. `subprocess.run(shell=True)` can introduce shell injection vulnerabilities and should be replaced with a list of arguments and `shell=False`.
**Prevention:** Always use `yaml.safe_load`. Avoid `shell=True` in `subprocess` unless absolutely necessary, and prefer passing commands as argument lists.
