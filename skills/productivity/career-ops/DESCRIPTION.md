# Career-Ops Skill for Hermes Agent

**Category:** Productivity  
**Author:** Hermes Agent (wrapper)  
**Credits:** [santifer](https://github.com/santifer/career-ops)  

A wrapper skill that brings the career-ops AI job search pipeline into Hermes Agent. Enables autonomous job offer evaluation, ATS-optimized PDF generation, portal scanning, and application tracking through natural language commands.

## Quick Start

1. Say "evaluate this job: [URL or paste description]" — Hermes runs the full pipeline
2. Say "scan portals" — Hermes searches 45+ companies for new offers
3. Say "generate CV PDF for [job]" — Hermes creates a tailored ATS-optimized resume
4. Say "show my tracker" — Hermes displays application status and statistics

## What It Does

- **Evaluate offers** with 6-block structured analysis (role summary, CV match, comp research, interview plan)
- **Compare multiple offers** with 10-dimension weighted scoring
- **Generate ATS-optimized PDFs** tailored per job description with keyword injection
- **Scan 45+ company portals** (Ashby, Greenhouse, Lever, Wellfound) automatically
- **Track all applications** in a single source of truth with dedup and integrity checks
- **Draft application answers** personalized to each company's form
- **Prepare for interviews** with STAR+Reflection story banks and negotiation scripts

## Setup Required (One-Time)

The skill will guide you through:
1. Creating `cv.md` with your resume
2. Filling in `config/profile.yml` (name, target roles, salary, location)
3. Optionally configuring `portals.yml` with companies to track
4. Running `npm install && npx playwright install chromium`

## For Full Career-Ops System

This skill is a wrapper — it needs the full career-ops system installed locally. See: https://github.com/santifer/career-ops