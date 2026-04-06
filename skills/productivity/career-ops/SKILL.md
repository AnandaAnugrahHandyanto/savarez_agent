---
name: career-ops
description: AI-powered job search pipeline — evaluate offers, generate ATS-optimized PDFs, scan portals, track applications, and manage your entire job search. Built as a wrapper around github.com/santifer/career-ops with 14 skill modes for autonomous AI agents.
version: 1.0.0
author: Hermes Agent (wrapper skill)
credits: "Based on career-ops by santifer — https://github.com/santifer/career-ops"
license: MIT
metadata:
  hermes:
    tags: [job-search, career, cv, pdf, ATS, portal-scanner, offer-evaluation, tracking, employment]
    triggers: ["evaluate job offer", "scan portals", "generate CV PDF", "track applications", "compare offers", "LinkedIn outreach", "fill application form", "job application pipeline", "career-ops", "job hunt"]
    category: productivity
---

# Career-Ops — AI Job Search Command Center (Hermes Agent Skill)

## What This Is

A **Hermes Agent skill** that wraps the [career-ops](https://github.com/santifer/career-ops) system — an open-source AI-powered job search pipeline. This skill tells Hermes how to use career-ops' 14 modes to evaluate job offers, generate tailored PDFs, scan 45+ company portals, and track applications — all autonomously.

**Purpose:** Help people find better jobs faster by leveraging AI to evaluate offers intelligently, generate ATS-optimized resumes, and manage the entire job search pipeline — without the manual spreadsheet tracking.

## Why Bundle This in Hermes Agent

Job searching is a high-effort, high-stakes process that benefits enormously from AI assistance. career-ops brings:

- **Structured evaluation** with 10-dimension weighted scoring (North Star alignment, CV match, comp research, etc.)
- **ATS-optimized PDF generation** — tailored per job description with keyword injection
- **Portal scanning** — 45+ companies pre-configured across Ashby, Greenhouse, Lever, Wellfound
- **Interview preparation** — STAR+Reflection story banks, negotiation scripts
- **Batch processing** — evaluate 10+ offers in parallel via sub-agents
- **Application tracking** — single source of truth with dedup and integrity checks

This is exactly the kind of persistent, multi-step, quality-over-quantity task that Hermes agents excel at. Wrapping it as a skill means any Hermes agent can run a full job search pipeline on behalf of the user — not just one-shot evaluation but ongoing scanning, tracking, and follow-up.

## How It Works

The skill points Hermes to the **career-ops workspace** on the local machine (see Setup section below). From there, Hermes reads:

- `cv.md` — the user's CV in markdown (source of truth)
- `config/profile.yml` — name, target roles, compensation, location preferences
- `portals.yml` — companies and search queries for the scanner
- `modes/*.md` — 14 mode files defining how each career-ops command works
- `templates/cv-template.html` — ATS-optimized PDF template
- `generate-pdf.mjs` — Playwright HTML→PDF generator

**The skill itself is just the wrapper/interface. The actual career-ops system is the separate repo.**

## Setup

### One-Time Setup

The first time a user invokes this skill, Hermes must complete onboarding:

**Step 1 — Clone or locate career-ops:**
```bash
# If career-ops doesn't exist yet:
git clone https://github.com/santifer/career-ops.git /path/to/career-ops

# The skill detects the career-ops directory via:
# - Environment variable: CAREER_OPS_PATH (if set)
# - Default fallback: ./career-ops (relative to hermes-agent root)
# - User-specified path via configuration
```

**Step 2 — Create cv.md** in the career-ops root:
- User pastes their CV in markdown format, OR
- User pastes a LinkedIn URL (Hermes extracts key info), OR
- User describes their experience and Hermes drafts a CV

**Step 3 — Configure profile:**
```bash
cp career-ops/config/profile.example.yml career-ops/config/profile.yml
# Edit with: name, email, location, target roles, salary range, superpowers
```

**Step 4 — Configure portals (optional but recommended):**
```bash
cp career-ops/templates/portals.example.yml career-ops/portals.yml
# Edit with target role keywords and companies to track
```

**Step 5 — Install dependencies:**
```bash
cd career-ops && npm install && npx playwright install chromium
```

### Verify Setup
```bash
cd $CAREER_OPS_PATH
node cv-sync-check.mjs      # Should report "All checks passed"
node verify-pipeline.mjs    # Should report "Pipeline is clean"
```

## The 14 Skill Modes

When the user invokes career-ops, Hermes selects the appropriate mode:

| Mode | Trigger | What It Does |
|------|---------|-------------|
| **auto-pipeline** | User pastes job URL/text | Full pipeline: evaluate → report → PDF → tracker |
| **oferta** | "evaluate this offer" | 6-block evaluation: role summary, CV match, level strategy, comp, personalization, interview plan |
| **ofertas** | "compare these offers" | 10-dimension weighted scoring, ranking, recommendation |
| **pdf** | "generate CV PDF" | ATS-optimized PDF tailored to specific JD |
| **scan** | "scan portals" / "find jobs" | 3-level discovery: Playwright + Greenhouse API + WebSearch, dedup, add to pipeline |
| **pipeline** | "process pending URLs" | Process all URLs in data/pipeline.md |
| **batch** | "batch evaluate" | Parallel sub-agent evaluation with conductor script |
| **tracker** | "show my applications" | Application status table + statistics |
| **apply** | "fill application form" | Live form assistant — extract questions, generate personalized answers |
| **contacto** | "LinkedIn outreach" | 3-phrase outreach message framework for hiring managers/recruiters |
| **deep** | "research this company" | 6-axis deep research prompt for interview prep |
| **project** | "evaluate this project idea" | 6-dimension scoring for portfolio projects |
| **training** | "evaluate this course/cert" | 6-dimension scoring for education investments |
| **apply** | (see above) | |

## Global Rules (Always Follow)

### NEVER
1. Invent experience or metrics
2. Submit applications on behalf of the user — generate drafts only
3. Share phone number in generated messages
4. Recommend comp below market rate
5. Generate a PDF without reading the JD first
6. Use corporate-speak or fluff
7. Ignore the tracker — every evaluated offer gets registered

### ALWAYS
1. Read cv.md + article-digest.md (if exists) before evaluating any offer
2. Run `node cv-sync-check.mjs` at the start of each session
3. Detect the role archetype and adapt framing
4. Cite exact lines from CV when matching
5. Use WebSearch for comp and company data
6. Register in tracker after evaluating
7. Generate content in the language of the JD (EN default)
8. Include `**URL:**` in every report header
9. Tracker additions go to `batch/tracker-additions/` — never edit applications.md directly
10. Use Playwright (not WebSearch) to verify if an offer is still active

## Report Format (for oferta mode)

Every evaluation saves a report to `reports/{###}-{company-slug}-{YYYY-MM-DD}.md`:

```markdown
# Evaluación: {Empresa} — {Rol}

**Fecha:** {YYYY-MM-DD}
**Arquetipo:** {detected}
**Score:** {X/5}
**URL:** {url}
**PDF:** {path or pendiente}

---

## A) Resumen del Rol
## B) Match con CV
## C) Nivel y Estrategia
## D) Comp y Demanda
## E) Plan de Personalización
## F) Plan de Entrevistas
## G) Draft Application Answers (score >= 4.5 only)

---

## Keywords extraídas
(list of 15-20 ATS keywords)
```

## Archetypes (Role Classification)

The system classifies every job into one of 6 archetypes to adapt proof point framing:

| Archetype | Emphasize... |
|-----------|--------------|
| **AI Business Builder / Founder** | End-to-end product ownership, product-market fit, revenue |
| **AI Solutions Architect** | Consulting delivery, AI implementation, workflow transformation |
| **AI Transformation Lead** | Change management, AI adoption, org-level impact |
| **AI GTM / Product Strategist** | Go-to-market, product strategy, demand generation |
| **AI Operations / Head of AI** | Distributed team leadership, AI workflows, execution |
| **AI Consulting Director** | Client delivery, strategy, revenue, consulting engagements |

Customize archetypes by editing `modes/_shared.md` in the career-ops directory.

## Key Files

| File | Purpose |
|------|---------|
| `cv.md` | User's CV — source of truth for all evaluations |
| `article-digest.md` | (Optional) Detailed proof points with metrics |
| `config/profile.yml` | Identity, target roles, compensation, narrative |
| `portals.yml` | Companies and search queries for portal scanner |
| `data/applications.md` | Application tracker with scores and status |
| `data/pipeline.md` | Inbox of pending job URLs |
| `modes/_shared.md` | Shared context, archetypes, rules (customize here) |
| `templates/cv-template.html` | HTML template for ATS-optimized PDFs |
| `generate-pdf.mjs` | Playwright HTML→PDF script |
| `batch/batch-prompt.md` | Worker prompt for parallel batch evaluation |

## NPM Scripts

```bash
cd $CAREER_OPS_PATH

node verify-pipeline.mjs      # Check pipeline integrity
node normalize-statuses.mjs  # Normalize all status values
node dedup-tracker.mjs       # Deduplicate tracker entries
node merge-tracker.mjs       # Merge batch tracker additions → applications.md
node cv-sync-check.mjs       # Check CV vs config consistency
```

## Portal Scanner — Pre-configured Companies (45+)

**AI Labs:** Anthropic, OpenAI, Mistral, Cohere, LangChain, Pinecone  
**Voice AI:** ElevenLabs, PolyAI, Parloa, Hume AI, Deepgram, Vapi, Bland AI  
**AI Platforms:** Retool, Airtable, Vercel, Temporal, Glean, Arize AI  
**Contact Center:** Ada, LivePerson, Sierra, Decagon, Talkdesk, Genesys  
**Enterprise:** Salesforce, Twilio, Gong, Dialpad  
**LLMOps:** Langfuse, Weights & Biases, Lindy, Cognigy, Speechmatics  
**Automation:** n8n, Zapier, Make.com  
**European:** Factorial, Attio, Tinybird, Clarity AI, Travelperk

**Job boards searched:** Ashby, Greenhouse, Lever, Wellfound, Workable, RemoteFront

## Dashboard TUI (Optional)

A Go-based terminal dashboard for browsing the pipeline visually:

```bash
cd $CAREER_OPS_PATH/dashboard
go build -o career-dashboard .
./career-dashboard
```

Requires: Go 1.21+

## Customization

The system is designed to be customized. Users can ask Hermes to:
- "Change archetypes to [specific roles]" → edit `modes/_shared.md`
- "Update my profile" → edit `config/profile.yml`
- "Add these companies to my portals" → edit `portals.yml`
- "Change CV template design" → edit `templates/cv-template.html`
- "Adjust scoring weights" → edit `modes/_shared.md` and `batch/batch-prompt.md`

## Credits

This skill is a **wrapper** for the career-ops system built by [santifer](https://santifer.io).

**Original repo:** https://github.com/santifer/career-ops

The career-ops system was used to evaluate 740+ job offers, generate 100+ tailored CVs, and land a Head of Applied AI role. It is designed to be personalized — the archetypes, scoring, negotiation scripts, and modes can all be adapted to the user's specific career targets.

This Hermes skill wrapper enables any Hermes agent to invoke career-ops capabilities on behalf of the user — making AI-powered job search automation accessible through natural language commands.

---

## Ethical Use

**This system is designed for quality, not quantity.** The goal is to help users find and apply to roles where there is a genuine match — not to spam companies with mass applications.

- **NEVER submit an application without the user reviewing it first.** Generate drafts only.
- **Discourage low-fit applications.** If a score is below 3.0/5, explicitly recommend skipping.
- **Quality over speed.** A well-targeted application to 5 companies beats a generic blast to 50.
- **Respect recruiters' time.** Every application a human reads costs someone's attention.