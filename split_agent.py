import ast
import re

with open("run_agent.py", "r") as f:
    lines = f.readlines()

# Find main() start
main_start = -1
for i, line in enumerate(lines):
    if line.startswith("def main()"):
        main_start = i
        break

core_lines = lines[:main_start]
main_lines = lines[main_start:]

with open("agent/core.py", "w") as f:
    f.writelines(core_lines)

new_run_agent = []
new_run_agent.append("#!/usr/bin/env python3\n")
new_run_agent.append('"""\nAI Agent Runner wrapper script.\n"""\n')
new_run_agent.append("import sys\nimport os\nimport fire\nimport logging\n")
new_run_agent.append("from agent.core import AIAgent\n\n")
new_run_agent.append("logger = logging.getLogger(__name__)\n\n")
new_run_agent.extend(main_lines)

with open("run_agent.py", "w") as f:
    f.writelines(new_run_agent)
print("Done splitting run_agent.py")
