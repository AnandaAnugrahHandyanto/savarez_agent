---
title: "Study Roadmap Progress Tracking"
sidebar_label: "Study Roadmap Progress Tracking"
description: "Track and continue a multi-session study roadmap using a canonical progress file, lesson todos, and session recall only as a fallback"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Study Roadmap Progress Tracking

Track and continue a multi-session study roadmap using a canonical progress file, lesson todos, and session recall only as a fallback.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/note-taking/study-roadmap-progress-tracking` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Study Roadmap Progress Tracking

Use this skill when:
- a user is following a multi-session learning roadmap
- the user asks things like "what lesson am I on?", "where was I?", or "start lesson X"
- lesson progress must survive across chats

## Core rule

**Treat the saved progress file as the canonical source of truth.**

Do **not** answer lesson-status questions from session recall alone when a maintained progress file exists.
Session recall is helpful for context and summaries, but it can lag behind or miss later updates.

## Recommended source order

1. **Read the canonical progress file first** if its location is known.
2. Use `session_search` only to recover missing context, reconstruct older lesson details, or locate the progress file if its path is unknown.
3. If both exist and disagree, prefer the file and explicitly mention that you verified against the saved progress file.

## Canonical file pattern

In this environment, the study roadmap file used successfully was:

```text
/home/h/.hermes/study-progress/cloud-devops-roadmap-progress.md
```

Expected useful sections:
- `Last updated`
- `## Current roadmap focus`
- `## Progress completed so far`
- `## Lesson status`
- `## Next recommended step`

## Workflow: user asks "what lesson am I in?"

### 1) Read the progress file
Use `read_file` on the known file path.

### 2) Extract the answer from the file
Prefer, in order:
- `## Next recommended step`
- completed lesson list
- per-lesson status under `## Lesson status`

### 3) Answer clearly
State:
- completed lessons
- current/next lesson
- confidence comes from the saved file

### 4) Only if needed, use session recall
Use `session_search` if:
- the file is missing
- the user asks for detail about a lesson that the file does not contain
- you need to reconstruct what happened during a prior lesson

## Workflow: starting a lesson

When the user says `start lesson X`:

1. Create/update a `todo` list with three items:
   - theory
   - practice
   - quiz
2. Mark theory `in_progress` initially.
3. Calibrate the lesson depth before teaching:
   - if the user says they are **not a beginner** in that topic, skip true-beginner explanation and teach an accelerated, DevOps-relevant version
   - still verify the saved progress file first; changing depth does **not** change lesson order
4. Teach the lesson.
5. For concept-first lessons, it is fine to mark theory complete after the learner demonstrates understanding before hands-on work starts.
6. Prefer the learner to answer in their own words during theory checks and quizzes.
   - If they answer correctly but paste citation-heavy or article-style wording, accept the substance if it is clearly correct, then coach them back toward concise original phrasing.
   - Rationale: study-roadmap sessions are for retention, interview readiness, and operational thinking — not bibliography formatting.
7. Grade theory-vs-live-state answers correctly.
   - If a question is about the learner's actual machine/account/service state, require the answer to reflect the observed live state, not just generic theory.
   - Example failure mode: answering "80 or 443" to a question that should have been "on this machine, nginx is currently listening on 80".
   - When the learner gives a generally true but not environment-specific answer, mark it as partially correct and explicitly distinguish theory from observed state.
8. When the quiz is answered correctly, mark quiz complete.
9. When the hands-on output is actually verified, mark practice complete.
   - If no relevant local project/file/workflow exists to inspect, use a compact synthetic example for practice instead of stalling.
   - If the hands-on objective is service inspection rather than automation, console-based verification is acceptable; note that CLI competence still matters for DevOps automation.
8. Only mark the lesson completed in the progress file after all three are complete.

## Workflow: updating the progress file after lesson completion

Update all relevant places, not just one:

1. `Last updated`
2. `## Progress completed so far`
   - add `- Completed Lesson X: ...`
3. `## Lesson status`
   - add or update the lesson subsection with:
     - Theory: completed
     - Practice: completed
     - Quiz: completed
4. `## Next recommended step`
   - advance it to the next lesson

## Verification checklist before telling the user a lesson is done

- Did theory get taught?
- Did the user answer the quiz sufficiently?
- Did the user provide actual command output or other evidence for practice?
- If the lesson is concept-heavy and no suitable local artifact exists, did you substitute a minimal synthetic practice example and get concrete answers on it?
- Was the progress file updated in all required sections?

## Important lesson learned

A real failure mode occurred when session recall suggested the user was on **Lesson 4**, but the canonical progress file showed **Lesson 6** was next.

Therefore:
- never rely on `session_search` alone for current lesson position when a maintained progress file exists
- always verify against the file before answering

## After the roadmap foundation is complete

When the progress file says the lesson roadmap foundation is complete and the next step is a project track:

1. **Stop treating the user like they still need generic theory lessons.**
2. **Frame the next work as a realistic project engagement** tied to the target role.
   - For DevOps learners, present the project like a small company handoff:
     - an app team already owns most product logic
     - the user's role is DevOps / platform / cloud engineer
     - their work is to operationalize, containerize, configure, deploy, automate, and document the service
   - **Do not turn the project into a hard unguided assignment by default.** If the user signals uncertainty or says they do not know how to start, switch to scaffolded practice.
   - Preferred scaffold for this user/class of task:
     1. state the tiny goal
     2. state what is already in place
     3. give the first concrete step
     4. give 1–3 hints or the exact missing concept
     5. only then escalate to a slightly harder follow-up
   - Default to guided labs or semi-guided challenges before "boss fight" style solo work.
3. Distinguish clearly between:

     1. state the tiny goal
     2. state what is already in place
     3. give the first concrete step
     4. give 1–3 hints or the exact missing concept
     5. only then escalate to a slightly harder follow-up
   - Default to guided labs or semi-guided challenges before "boss fight" style solo work.
3. Distinguish clearly between:
   - **app-team work**: business logic, frontend, major feature building
   - **DevOps work**: env config, Docker, Compose, reverse proxy, CI/CD, deployment, IaC, observability
4. If minimal app changes are still needed for operability, label them as **handoff hardening** rather than full application development.
5. Default to **scaffolded project practice**, not hard unguided tasks.
   - Give a small concrete goal, the exact first step, and 1-3 hints.
   - If the task is multi-layered, break it into phases the learner can finish in one sitting.
   - Avoid handing over a whole project with no foothold unless the user explicitly wants a harder "boss fight" mode.
4. If minimal app changes are still needed for operability, label them as **handoff hardening** rather than full application development.
5. **Do not turn the project track into hard unguided solo work if the user signals they cannot yet self-start that way.**
   - Prefer scaffolded practice over "build the whole thing alone."
   - Good progression for this user:
     1. guided lab (exact steps)
     2. semi-guided challenge (goal + first step + hints)
     3. boss-fight/solo build only after they have repeated the pattern enough to reproduce it
   - When the user says a task is too hard or they do not know how to begin, shrink scope immediately and give the first concrete step instead of repeating the full assignment.
6. When offering execution modes, prefer a split that preserves the user's ownership of the DevOps layers:
   - assistant may do low-value app cleanup
   - user should do Docker/Compose/Nginx/CI-CD/deploy/debugging themselves with review and coaching
   - if the user explicitly asks to "remove all DevOps work so I can do it again", treat that as a valid reproduction drill: strip DevOps scaffolding only (Docker/Compose/env-example/Nginx/CI/CD/Terraform/healthcheck-style ops endpoints), keep the application/business logic intact, and hand the project back as a clean app-only base for them to rebuild operationally

   - Do **not** assign a hard unguided "build this whole thing alone" task when the user signals they do not know how to start.
   - Prefer **scaffolded practice**: tiny goal, exact first move, a few hints, then a slightly harder variation.
   - Good ladder: `guided lab -> semi-guided challenge -> boss fight`.
   - When the user says they used AI or cannot reproduce the result alone, convert the success into a **reproduction drill**: have them restate the pattern in their own words, rebuild a minimal version, and explain the key ideas (`service-name host instead of localhost`, `DB init script`, `volume reset may be needed`).
7. For project-track sessions, separate scopes clearly.
   - If the user asks the assistant to change app code but explicitly says they want to do the DevOps work themselves, keep hands off Compose/network/deploy redesign unless it is required just to verify the requested app change.
   - Say plainly which part was app work and which part remains their DevOps responsibility.
   - When the user asks **"is this a DevOps job or should I even do it?"**, distinguish:
     - **app/schema design work**: choosing business fields, changing product/domain behavior
     - **operational schema-state work**: making the running database match the app version, deciding reset vs migration, rerunning init/seed flow, documenting recovery steps
   - For this user's project-track learning, treat **schema drift diagnosis and environment-state repair** as valid DevOps/platform practice, even when the underlying schema was designed by app developers.
   - When the learner says they will do the work, switch to **one-step coaching**: give only the next command or smallest next action, wait for the result, then continue. This preserves ownership and prevents accidental takeover by the assistant.

   - Default to **scaffolded practice**: tiny goal, clear first step, and progressively reduced hints.
   - Good progression:
     1. **Guided lab** — exact steps
     2. **Semi-guided challenge** — target + first step + hints-on-request
     3. **Boss fight** — mostly solo only after the user has already reproduced the pattern once
   - If the user says they cannot reproduce the setup next time, stop escalating difficulty and switch to a **reproduction challenge**:
     - have them rebuild the same pattern in a fresh folder
     - require only the minimum files needed
     - review their result and point out only the important mistakes
7. For project-track discussions, avoid generic career detours when the user asks what to do next technically.
   - Base the recommendation on the saved roadmap progress and the current project state.
   - If the user has already completed one proof project, the next recommendation should build directly on it instead of restarting from generic beginner portfolio advice.
8. When the project already exists and the user asks whether it is a good DevOps practice target, treat it as a **handoff project** first.
   - Reuse the existing app instead of steering them to a brand-new sample project.
   - Frame the app as "application work already mostly exists; your job is to operationalize it."
   - If they refer to a project from a prior session, confirm it against durable state before advising: prefer the actual filesystem/project files; use session recall only as supporting context.
9. When the user wants to **redo the DevOps layer themselves**, preserve ownership correctly.
   - Remove only the operational scaffolding: container files, env-example scaffolding, deployment/proxy/CI/IaC artifacts, and explicitly DevOps-only endpoints/config.
   - Keep the product/application logic intact unless the user explicitly asks to delete app features too.
   - After stripping the DevOps layer, tell the user exactly what app state remains and what defaults are now hardcoded so they can rebuild the layer consciously.
10. Good next-step ladder for a rebuild drill on an existing app:
   - audit how the app runs now
   - recreate env/config separation
   - recreate containerization
   - recreate multi-service wiring
   - then add proxy / CI-CD / deploy

## Good response pattern

- `I checked your saved progress file.`
- list completed lessons
- state the current/next lesson
- if starting that lesson, create the three lesson todos immediately

## Pitfalls

- Session summaries may be historically correct but outdated relative to the latest file edits.
- Broad `session_search` queries can pull in irrelevant sessions that share keywords (for example, CV/resume chats that mention the same school or background details). When the progress file exists, do not include unrelated session history in the answer.
- Updating only the `completed` list without updating `Lesson status` and `Next recommended step` creates future confusion.
- Do not mark practice complete without evidence; require command output or other concrete verification.
