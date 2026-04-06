# Career-Ops Skill Setup Reference

## Overview

This skill is a **wrapper** — it provides the interface between Hermes Agent and the career-ops system (https://github.com/santifer/career-ops). The actual career-ops logic lives in a separate cloned repository on the user's machine.

## Setup Location

The career-ops system should be cloned to:
```
$CAREER_OPS_PATH  (environment variable, if set)
OR
./career-ops  (relative to hermes-agent root)
OR
~/.hermes/career-ops  (default user location)
```

## Installation Commands

```bash
# Clone career-ops to the user's preferred location
git clone https://github.com/santifer/career-ops.git ~/.hermes/career-ops

# Install dependencies
cd ~/.hermes/career-ops && npm install

# Install Playwright (required for PDF generation)
npx playwright install chromium

# Configure profile
cp ~/.hermes/career-ops/config/profile.example.yml ~/.hermes/career-ops/config/profile.yml

# Configure portals (optional)
cp ~/.hermes/career-ops/templates/portals.example.yml ~/.hermes/career-ops/portals.yml
```

## For PR Maintainers

This skill assumes:
- Node.js 18+ is available
- Playwright's Chromium is installed (`npx playwright install chromium`)
- The user has a CV in markdown format
- The user can fill in their profile.yml with target roles and compensation

The skill gracefully degrades — if career-ops is not yet installed, it guides the user through setup rather than failing.

## Skill Triggers

- "evaluate job", "evaluate offer", "career-ops"
- "scan portals", "find jobs", "job search"
- "generate CV", "PDF resume", "ATS resume"
- "track applications", "my applications"
- "compare offers"
- "LinkedIn outreach"
- "fill application form", "application form"
- "company research", "deep research company"