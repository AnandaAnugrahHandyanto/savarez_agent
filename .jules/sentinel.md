## 2024-05-24 - [Sanitize Subprocess Environments for `quick_commands` and `shell.exec`]
**Vulnerability:** The CLI and TUI Gateway executed user-defined `quick_commands` and arbitrary shell commands (`shell.exec`) using `subprocess.run(..., shell=True)` without sanitizing the environment variables passed to the child process.
**Learning:** This exposed sensitive API keys and credentials contained in the main Hermes process environment to these child processes, allowing for easy credential exfiltration by a malicious config or user interaction.
**Prevention:** Always use `tools.environments.local._sanitize_subprocess_env` to filter the environment before passing it to `subprocess` execution mechanisms when executing untrusted or user-supplied shell commands.

## 2025-06-05 - [Prevent XML External Entity (XXE) Vulnerabilities when parsing untrusted payloads]
**Vulnerability:** The application was parsing XML directly from untrusted HTTP callbacks (like WeCom Webhooks and RSS Feeds) using Python's standard `xml.etree.ElementTree`, which is vulnerable to XML External Entity (XXE) attacks.
**Learning:** Parsing XML content from external sources can lead to severe security vulnerabilities, including Local File Inclusion, DoS, and SSRF.
**Prevention:** Always use `defusedxml.ElementTree` or `defusedxml.minidom` instead of `xml.etree.ElementTree` when parsing any XML payload obtained from user input, webhooks, or external URLs.
