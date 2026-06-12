# Web Developer / Software Engineer CV + portfolio targeting

Use when tailoring a CV and portfolio for a web developer/software engineer vacancy from screenshots or a job post.

## Workflow
1. Extract the role title, company, location, responsibilities, requirements, and offer details from the screenshot/job post before writing.
2. Retarget the CV headline to the actual vacancy, e.g. `Website Developer / Software Engineer`, not a generic DevOps title when the job is web development.
3. Match evidence to requirements with real projects:
   - e-commerce/product catalog -> live shop project
   - Node/Express/API -> backend routes and health/product endpoints
   - database -> PostgreSQL schema, seed data, backup/restore, DB-backed health
   - deployment/maintenance -> Docker Compose, EC2, DNS, HTTPS, CI, runbook
4. Generate both:
   - a polished visual PNG for chat/app sharing
   - an ATS-safe PDF/DOCX/TXT version for upload/parsing
5. If updating the user's portfolio, align the hero, project copy, and CV download link with the target role. Verify the live portfolio and CV URL after deployment.

## Honesty guardrail
Before delivery, run a CV truth audit:
- `true/evidenced`: live project, repo, deployed endpoint, actual tool used
- `positioning`: target job title, junior-level phrasing, learning/adaptable wording
- `too aggressive`: keywords implying shipped work that was not done

Prefer defensible wording:
- `payment gateway learning / integration readiness` or remove it if no payment integration exists
- `learning/adaptable: React, Vue, PHP, Python, MySQL, MongoDB` if the user has only basic familiarity
- `strongest stack: HTML, CSS, JavaScript, Node.js, Express, PostgreSQL, Docker, AWS` when that is what the evidence supports

Avoid making the user defend fake depth in an interview. Ambitious is fine; unverifiable is not.

## Visual CV pattern that worked better
For a polished image CV:
- dark professional header with name, target title, contact line
- left sidebar for matched skills and job fit
- main column for profile, selected projects, experience, and "why this role fits"
- make the live project the strongest evidence block
- keep text readable; avoid tiny dense one-column walls

## Portfolio update pattern
When the CV is retargeted for a job, update the portfolio to reinforce the same story:
- hero: target role and strongest stack
- project section: explain why projects match the role
- contact: target role wording
- add `Download CV` link to the generated PDF
- verify GitHub Actions deploy and live `https://.../cv/<file>.pdf` returns 200
