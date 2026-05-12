# Documenting fork-specific changes vs upstream

Use this when a forked Hermes Agent repo needs comments/notes describing how it differs from the base Nous Research `hermes-agent`.

## Workflow

1. Clone the fork into a temporary directory and add upstream:
   ```bash
   git clone https://github.com/<owner>/hermes-agent /tmp/hermes-agent-fork
   cd /tmp/hermes-agent-fork
   git remote add upstream https://github.com/NousResearch/hermes-agent.git
   git fetch upstream main
   ```
2. If Git reports no merge base because the clone is shallow, unshallow before diffing:
   ```bash
   git fetch --unshallow origin
   git fetch upstream main
   git merge-base upstream/main origin/main
   git rev-list --left-right --count upstream/main...origin/main
   ```
3. Generate an inventory of intentional differences:
   ```bash
   git diff --stat upstream/main...origin/main
   git diff --name-status upstream/main...origin/main
   git diff --unified=0 upstream/main...origin/main -- Dockerfile docker/entrypoint.sh gateway/run.py run_agent.py tools/approval.py tools/tirith_security.py
   ```
4. Add a root-level `FORK_NOTES.md` that describes the fork overlay at class level, not every commit. Good sections:
   - primary goals of the fork
   - container/Railway deployment changes
   - source watcher and secret safety
   - gateway behavior changes
   - model-routing changes
   - security prompt/Tirith changes
   - added operational scripts/tools
   - added/modified skills
   - CI/GitHub Actions changes
   - upstream sync guidance
   - what should not be upstreamed as-is
   - what could be generalized upstream later
5. Add a short note near the top of `README.md` linking to `FORK_NOTES.md` so visitors see the fork context immediately.
6. Commit and push:
   ```bash
   git config user.name "Hermes Agent"
   git config user.email "hermes-agent@users.noreply.github.com"
   git add README.md FORK_NOTES.md
   git commit -m "docs: document fork-specific changes"
   git push origin main
   ```
7. Verify the pushed commit matches origin:
   ```bash
   git ls-remote origin refs/heads/main | cut -f1
   git rev-parse HEAD
   ```

## Pitfalls

- Do not paste real env var values in fork notes. Refer to env var names only.
- Shallow clones may not have a merge base; fetch full origin history before using `upstream/main...origin/main`.
- Keep `FORK_NOTES.md` as deployment-overlay documentation, not a private diary or full changelog.
- For Gordon's Railway fork, expect many intentional Gordon-specific skills/scripts that should not be upstreamed unchanged.
