# DevOps project packaging: repo cleanup → portfolio → CV

Use when a user finishes a live DevOps portfolio project and asks to make it look professional, update their portfolio, or turn the work into CV material.

## Trigger pattern
- A real app/site is live and verified.
- The user asks for cleanup, portfolio update, CV/resume update, or "make it good".
- The project includes concrete operations work: Docker/Compose, EC2, DNS, HTTPS, CI, backups, monitoring, runbook, etc.

## Workflow
1. **Clean the project repo first**
   - Remove stale config/directories from old architecture (example: old `nginx/` after moving to Caddy).
   - Update README/runbook so it matches runtime: current proxy, ports, HTTPS behavior, health checks, deploy command, troubleshooting.
   - Run config validation and smoke checks before committing.
   - Push and verify CI.

2. **Update portfolio second**
   - Add a concise case-study card with live link + GitHub link.
   - Name the operational proof clearly: EC2, Docker Compose, Caddy/HTTPS, PostgreSQL, health checks, backups, CI/CD, DNS.
   - Keep it client/professional-facing; avoid internal debugging history.
   - Push and verify the portfolio deploy plus live page content.

3. **Generate CV material third**
   - Translate the project into outcome bullets, not a task diary.
   - Good wording: "Deployed a Node.js/PostgreSQL shop on AWS EC2 using Docker Compose, Caddy automatic HTTPS, Hostinger DNS, Elastic IP, health endpoints, backup/restore scripts, and GitHub Actions CI."
   - Produce both human-facing PDF/PNG and ATS-friendly TXT/DOCX when possible.
   - Verify files exist, check visual rendering, and make sure claims match live/repo evidence.

## Pitfalls
- Do not leave portfolio or README claiming old architecture after a migration.
- Do not list Kubernetes/EKS if the project is still EC2 + Compose; better to present honest production maturity.
- Do not turn transient debug history into CV bullets. Capture final architecture and operational responsibilities.
- If the user explicitly asks for takeover, direct implementation is acceptable even if prior coaching mode preserved DevOps reps.

## Verification checklist
- Project repo CI latest run passes.
- Live service endpoints still work after cleanup.
- Portfolio deploy latest run passes.
- Portfolio public page contains the new project card.
- CV outputs are non-empty and visually readable.
