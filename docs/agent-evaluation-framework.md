# Agent Evaluation and Portfolio Management Framework

This document summarizes a practical operating model for preventing unused or low-impact agents from accumulating inside an organization. The core idea is to manage agents not as isolated AI features, but as a measurable product portfolio.

## 1. Why Agent Evaluation Needs a Portfolio Model

As organizations deploy more agents, common failure modes appear:

- agents built because the technology is interesting, not because a repeated business problem is clear;
- agents with initial curiosity usage but poor long-term retention;
- duplicated agents that solve similar tasks in slightly different ways;
- agents with high usage but low measurable business impact;
- niche agents with low usage but high strategic value that are incorrectly retired;
- agents without clear owners, quality monitoring, or retirement criteria.

The goal is not to maximize the number of agents. The goal is to keep a portfolio of agents that are used, trusted, measurable, and tied to business outcomes.

## 2. Existing Evaluation Systems to Reuse

Agent evaluation should combine several existing management and measurement systems rather than inventing a completely new one.

### 2.1 Product Analytics

Useful for measuring whether the agent is actually adopted.

Key concepts:

- active users;
- adoption funnel;
- activation rate;
- repeat usage;
- retention;
- cohort analysis;
- churn or drop-off.

Typical metrics:

- daily, weekly, and monthly active users;
- target-user penetration rate;
- first-use activation rate;
- D7 and D30 retention;
- usage frequency by team, role, or workflow.

### 2.2 HEART Framework

Google's HEART framework is useful for evaluating user experience and task value.

Dimensions:

- Happiness: satisfaction, trust, perceived usefulness;
- Engagement: frequency and depth of usage;
- Adoption: percentage of intended users who start using the agent;
- Retention: whether users keep coming back;
- Task Success: whether the agent completes the intended work.

### 2.3 SPACE Framework

SPACE is useful for evaluating developer and knowledge-worker productivity.

Dimensions:

- Satisfaction and well-being;
- Performance;
- Activity;
- Communication and collaboration;
- Efficiency and flow.

This is especially relevant for coding agents, research agents, internal productivity agents, and engineering workflow agents.

### 2.4 DORA Metrics

DORA metrics are useful when agents affect software delivery or operations.

Examples:

- deployment frequency;
- lead time for changes;
- change failure rate;
- mean time to recovery.

Coding, DevOps, incident-response, and release-management agents can be evaluated against these outcomes.

### 2.5 LLM and Agent Observability

Agent-specific observability is needed because usage alone does not prove success.

Track:

- task completion rate;
- first-pass success rate;
- tool-call success and failure rates;
- latency;
- cost per successful task;
- hallucination or unsupported-claim rate;
- escalation and human-correction rate;
- policy or permission violations;
- prompt, tool, and model version changes.

Potential tooling categories include LLM observability platforms, tracing systems, event logs, OpenTelemetry-style traces, and internal dashboards.

## 3. Core Evaluation Dimensions

Every production agent should be evaluated across six dimensions.

## 3.1 Adoption: Is the Agent Being Used?

Questions:

- How many intended users have used it at least once?
- What percentage of the target population is active?
- Which teams, roles, or workflows use it most?
- Is usage organic, or only driven by launch announcements?

Metrics:

- monthly active users;
- weekly active users;
- target-user adoption rate;
- new users per week;
- team-level penetration;
- activation rate.

## 3.2 Retention: Do Users Keep Coming Back?

Questions:

- Do users return after the first trial?
- Has the agent become part of a normal workflow?
- Is repeat usage growing, flat, or declining?

Metrics:

- D7 retention;
- D30 retention;
- weekly returning users;
- repeat usage rate;
- sessions per active user;
- cohort retention by launch month or team.

## 3.3 Task Success: Does It Complete the Work?

Questions:

- Did the user achieve the intended task?
- Did the agent complete the workflow or stop halfway?
- Were tool calls successful?
- Did a human need to redo or correct the output?

Metrics:

- task completion rate;
- first-pass success rate;
- tool-call success rate;
- workflow step failure rate;
- retry count;
- fallback rate;
- human handoff rate;
- human correction rate.

## 3.4 Business Impact: Does It Improve a Business KPI?

Questions:

- Which business process does this agent improve?
- What was the baseline before the agent?
- Does the agent reduce time, cost, errors, or risk?
- Does it improve throughput, quality, customer satisfaction, or decision speed?

Metrics depend on the agent type.

Examples:

- time saved per completed task;
- cycle-time reduction;
- cost reduction;
- error or rework reduction;
- throughput increase;
- first-contact resolution improvement;
- incident response improvement;
- report or analysis lead-time reduction.

## 3.5 Trust and Quality: Can Users Rely on It?

Questions:

- Are answers accurate and grounded?
- Does the agent show evidence or sources when needed?
- Are actions safe and permissioned?
- Does the agent create extra review burden?
- Do users trust it enough to use it again?

Metrics:

- user satisfaction score;
- thumbs-up/thumbs-down ratio;
- unsupported-claim rate;
- hallucination rate;
- policy violation rate;
- unsafe-action block rate;
- review burden;
- quality audit score.

## 3.6 Cost and Maintainability: Is It Worth Operating?

Questions:

- How much does the agent cost to run?
- How much engineering or operations effort does it require?
- Is the cost proportional to the business impact?
- Is the agent fragile because it depends on unstable prompts, tools, or undocumented APIs?

Metrics:

- monthly LLM cost;
- cost per invocation;
- cost per successful task;
- average latency;
- incident count;
- maintenance hours;
- number of broken integrations;
- owner response time to defects.

## 4. Agent Scorecard

Every agent should have a scorecard. The scorecard should be simple enough to review monthly, but complete enough to support scale, improvement, merge, or retirement decisions.

### 4.1 Basic Information

- Agent name;
- business owner;
- technical owner;
- target users;
- target workflow;
- connected systems;
- permission level;
- launch date;
- current lifecycle stage;
- risk tier.

### 4.2 Usage Metrics

- target user count;
- monthly active users;
- weekly active users;
- target-user adoption rate;
- activation rate;
- D7 and D30 retention;
- sessions per user;
- usage by team or role.

### 4.3 Outcome Metrics

- task completion rate;
- successful tasks per month;
- estimated time saved;
- process lead-time change;
- error or rework reduction;
- human handoff rate;
- business KPI contribution.

### 4.4 Quality Metrics

- first-pass success rate;
- tool-call failure rate;
- hallucination or unsupported-claim rate;
- user satisfaction;
- manual review burden;
- policy or permission violation count;
- incident count.

### 4.5 Cost Metrics

- monthly LLM and tool cost;
- cost per successful task;
- average latency;
- maintenance hours;
- operational incidents;
- support tickets.

### 4.6 Portfolio Decision

Each review should assign one decision:

- Scale: expand to more teams or workflows;
- Maintain: keep operating with normal monitoring;
- Improve: fix UX, quality, integration, or workflow fit;
- Merge: consolidate with overlapping agents or convert to a shared skill;
- Retire: remove from production and archive the learnings.

## 5. Agent Lifecycle Governance

A lifecycle model prevents unused agents from becoming permanent clutter.

## 5.1 Idea

Purpose:

- identify a real repeated problem;
- define target users;
- define baseline pain and measurable success criteria.

Entry requirements:

- clear business problem;
- named business sponsor;
- expected KPI impact;
- rough risk and permission assessment.

## 5.2 Proof of Concept

Purpose:

- validate feasibility;
- test prompt, tools, and workflow assumptions;
- avoid over-investing before user need is proven.

Exit requirements:

- example tasks completed successfully;
- early user feedback;
- known limitations documented;
- decision to stop, revise, or pilot.

## 5.3 Pilot

Purpose:

- test with real users in a real workflow;
- measure adoption, retention, success, and quality;
- discover UX, permission, and integration gaps.

Exit requirements:

- minimum pilot usage;
- task success baseline;
- user satisfaction threshold;
- cost estimate;
- owner commitment.

## 5.4 Production

Purpose:

- operate the agent as a supported internal product.

Production requirements:

- business owner and technical owner;
- monitoring and logging;
- scorecard;
- documentation;
- permission model;
- incident and rollback process;
- human approval for risky actions;
- retirement criteria.

## 5.5 Scale

Purpose:

- expand the agent to more teams or workflows when evidence supports it.

Scale requirements:

- strong retention;
- proven business impact;
- stable quality;
- manageable cost;
- clear training or onboarding materials;
- support capacity.

## 5.6 Review, Merge, or Retire

Purpose:

- prevent stale, duplicated, or low-impact agents from accumulating.

Review cadence:

- 30-day early health check;
- 90-day survival review;
- quarterly portfolio review.

Possible actions:

- continue;
- improve;
- merge into another agent;
- convert into a reusable skill;
- retire and archive.

## 6. Launch Gate: Required Questions Before Production

Before an agent is listed in the official agent registry or made broadly available, the team should answer these questions.

1. Who is the target user?
2. What repeated task or pain point does it solve?
3. How is the task handled today?
4. What baseline time, cost, error, or cycle-time problem exists?
5. Which KPI should improve if the agent works?
6. Where will the user invoke it: chat, IDE, portal, workflow system, MES, CRM, ticketing, or another tool?
7. What systems does it read from or write to?
8. What permission level does it need?
9. What actions require human approval?
10. Which existing agents or skills overlap with it?
11. What is the expected cost per successful task?
12. What are the launch success criteria?
13. What are the retirement criteria?

## 7. Agent Registry

A central registry is required once an organization has more than a handful of agents.

Minimum registry fields:

- agent ID;
- agent name;
- description;
- business owner;
- technical owner;
- target users;
- target workflow;
- status;
- lifecycle stage;
- risk tier;
- connected systems;
- permissions;
- launch date;
- latest version;
- monthly active users;
- task completion rate;
- monthly cost;
- user satisfaction;
- current portfolio decision;
- next review date;
- overlapping agents or skills.

The registry should be the source of truth for deciding which agents are promoted, improved, merged, or retired.

## 8. Type-Specific Metrics

Agent metrics should be customized by agent type. A single KPI set for every agent will mislead the organization.

## 8.1 Knowledge and Q&A Agents

Useful metrics:

- answer accuracy;
- grounded-answer rate;
- source coverage;
- deflection rate;
- repeated-question reduction;
- user correction rate;
- document search time reduction.

## 8.2 Workflow Agents

Useful metrics:

- end-to-end completion rate;
- step-level failure rate;
- human approval rate;
- human handoff rate;
- process cycle-time reduction;
- throughput increase;
- exception rate.

## 8.3 Coding Agents

Useful metrics:

- accepted diff ratio;
- PR lead-time reduction;
- review correction rate;
- test pass rate;
- escaped defect rate;
- developer satisfaction;
- DORA metric impact.

## 8.4 Operations and Incident Agents

Useful metrics:

- detection time;
- triage time;
- mean time to recovery;
- false positive rate;
- recommendation acceptance rate;
- safe auto-remediation rate;
- incident recurrence reduction.

## 8.5 Customer Support and Sales Agents

Useful metrics:

- first-contact resolution;
- response time;
- escalation rate;
- customer satisfaction;
- agent-assist acceptance rate;
- conversion or renewal support impact;
- quality audit score.

## 8.6 Manufacturing and Engineering Agents

Useful metrics:

- anomaly detection precision and recall;
- root-cause recommendation acceptance;
- deviation response time;
- downtime reduction;
- engineering analysis lead-time reduction;
- report generation time reduction;
- operator or engineer repeat usage;
- safety and approval compliance.

## 9. Portfolio Decision Matrix

Usage and business impact should be interpreted together.

### High Usage / High Impact

Decision:

- scale;
- invest in reliability and onboarding;
- consider broader rollout.

Interpretation:

- this is a strong production agent.

### High Usage / Low Impact

Decision:

- investigate whether the agent is convenient but not valuable;
- refine the target workflow;
- improve measurement;
- consider merging if it overlaps with other agents.

Interpretation:

- usage alone is not proof of value.

### Low Usage / High Impact

Decision:

- check awareness, UX, workflow integration, and access friction;
- maintain if it is niche but critical;
- improve discoverability or trigger-based invocation.

Interpretation:

- do not retire automatically. Some agents are valuable because they handle rare but expensive tasks.

### Low Usage / Low Impact

Decision:

- retire, merge, or return to PoC;
- archive learnings;
- remove from official registry if there is no committed owner.

Interpretation:

- this is the main category to eliminate.

## 10. Operating Rules

Recommended operating rules:

1. No production agent without a business owner and technical owner.
2. No production agent without a defined target workflow.
3. No production agent without baseline and target metrics.
4. No risky write action without permissioning, audit logs, and human approval where needed.
5. Every production agent must appear in the agent registry.
6. Every production agent must have a scorecard.
7. Every production agent must go through a 90-day survival review.
8. Duplicate agents should be merged or converted into shared skills.
9. Agents with no owner should be retired.
10. Usage metrics and outcome metrics must be reviewed together.

## 11. Dashboard Design

## 11.1 Executive View

Show:

- total number of agents;
- active production agents;
- pilot agents;
- retire candidates;
- monthly active users;
- successful tasks per month;
- estimated hours saved;
- total LLM and tool cost;
- cost per successful task;
- top-performing agents;
- low-usage agents;
- high-risk action agents.

## 11.2 Team View

Show:

- agents available to the team;
- team adoption rate;
- team retention;
- workflow coverage;
- time saved by workflow;
- satisfaction by team;
- agent gaps and duplicate usage.

## 11.3 Agent Detail View

Show:

- usage trend;
- retention cohort;
- task success trend;
- failure reason breakdown;
- tool-call trace summary;
- cost trend;
- quality score;
- user feedback;
- current improvement backlog;
- next review date.

## 12. Example Calculation Formulas

### Adoption Rate

```text
Adoption rate = monthly active users / target user count
```

### Retention Rate

```text
D30 retention = users who reused within 30 days / users who first used the agent
```

### Task Completion Rate

```text
Task completion rate = completed tasks / started tasks
```

### First-Pass Success Rate

```text
First-pass success rate = tasks completed without retry or human correction / completed tasks
```

### Estimated Time Saved

```text
Estimated time saved = successful tasks × (baseline task time - agent-assisted task time)
```

### Cost per Successful Task

```text
Cost per successful task = monthly operating cost / successful completed tasks
```

### Human Intervention Rate

```text
Human intervention rate = tasks requiring human handoff or correction / total tasks
```

## 13. Recommended Implementation Roadmap

## Phase 1: Registry and Basic Telemetry

Build the minimum system of record.

Deliverables:

- central agent registry;
- owner assignment;
- target workflow definition;
- usage logging;
- success and failure event logging;
- cost tracking;
- basic user feedback.

Outcome:

- the organization can see which agents exist, who owns them, and whether they are used.

## Phase 2: Scorecard and Review Cadence

Introduce operating discipline.

Deliverables:

- monthly scorecards;
- 30-day health checks;
- 90-day survival reviews;
- quarterly portfolio review;
- scale, maintain, improve, merge, retire decisions.

Outcome:

- low-value agents are improved, merged, or retired instead of silently accumulating.

## Phase 3: Outcome-Based Portfolio Management

Connect agents to business outcomes.

Deliverables:

- business KPI mapping;
- workflow coverage map;
- team-level adoption analysis;
- cost-per-outcome analysis;
- risk-tiered governance;
- systematic investment in high-impact agents.

Outcome:

- the organization manages agents like a product portfolio, not a collection of experiments.

## 14. Summary

The recommended model is:

```text
Agent Registry
+ Agent Scorecard
+ Lifecycle Governance
+ Usage and Outcome Metrics
+ Quarterly Portfolio Review
```

The key principle is simple:

```text
Do not measure agents only by how often they are used.
Measure whether they are adopted, retained, successful, trusted, cost-effective, and tied to a business outcome.
```

A healthy organization should make it easy to experiment with new agents, but hard for unowned, duplicated, unmeasured, or low-impact agents to remain in production.
