We are customizing a fork of NousResearch/hermes-agent into "Jade"
for Oracule Zero. You have already read the codebase in Session 1.

CRITICAL RULES — read before touching anything:

- Never modify these core files: run_agent.py, cli.py,
  gateway/run.py, hermes_cli/main.py
- Only change human-visible display strings, never logic
- Never change Python import names, module names, or package names
  (these would break installation)
- Every change must be a string substitution only

WHAT TO CHANGE:

1. Startup banner and CLI title
   Navigate to wherever the startup banner renders.
   From Session 1 you know the exact file and location.
   Change: "Hermes" → "Jade"
   Change: "Nous Research" / "NousResearch" → "Oracule Zero"
   Change tagline to: "Jade — Executive Intelligence for Oracule Zero"

2. CLI help text output
   Find all argparse help strings and CLI description strings.
   Change "Hermes Agent" → "Jade" in help text only.
   Keep all command names identical (hermes, hermes setup,
   hermes gateway etc.) — these are invocation commands, not branding.

3. TUI header and title components
   Navigate to the exact components you found in Session 1.
   Change display strings only. Do not touch React logic.
   Change "Hermes" → "Jade" in rendered text.

4. README.md
   Update the title, description, and any references to
   "Hermes Agent" or "NousResearch" in the introduction section.
   Keep installation instructions intact — only change
   the identity/description sections.

5. Skill file descriptions
   For any skill file that mentions "Hermes" in its description
   or content text, change to "Jade".

AFTER CHANGES:
Search the full repo for remaining "Hermes" and "NousResearch"
strings. Give me two lists:
(a) Strings you intentionally left (import paths, package internals)
with a one-line explanation of why each is safe to leave
(b) Any strings you found that need manual review

Show me every file you modified with a one-line description
of what changed in each.
