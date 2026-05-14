# How I See AI Evolving in 2026 (as an AI Engineer)

**Channel:** Dave Ebbelaar (Datalumina)
**URL:** https://youtu.be/rbIX3Hp__rY
**Date:** 2026-01-11

## Summary

Practitioner's perspective on AI trends for 2026 from someone running an AI development company. Grounded in real client work, not hype. Seven key areas of focus with practical takeaways.

## The Seven Points

### 1. Limits of LLMs
- Hallucinations still the core problem - "like a coworker who makes things up"
- Models will improve but won't drastically change how we build applications
- Yann LeCun's UCE paper - potential new paradigm beyond LLMs
- Recursive language models paper - clever chaining to overcome context limits
- **Takeaway:** Focus on applied AI, not theoretical breakthroughs you can't use today

### 2. Google's Ecosystem
- Google now has best-in-class models across language, image, video
- Only lab with own compute (TPUs) - not reliant on Nvidia
- Massive data advantage
- A2A protocol (Agent-to-Agent) - "a step above MCP"
  - MCP = making tools available for LLMs
  - A2A = agents connecting and delegating subtasks to each other
- **Takeaway:** Watch Google closely in 2026, they own the full stack

### 3. DAGs vs Agents (Workflows vs Autonomous)
- Anthropic's "Building Effective Agents" blog (now over a year old) still relevant
- Bold statements like "goodbye DAGs" should be taken with grain of salt
- The right answer is use-case specific:
  - Human in loop + chat interface → agents with tools OK
  - Banking/critical processes → keep it deterministic (DAGs)
- Key question: What's the cost of a hallucination in this specific workflow?
- **Takeaway:** Find simplest solution first, add complexity only when needed

### 4. Agentic Coding
- Expects "major major improvements" in this area
- LLMs are uniquely good at coding
- Both model improvements AND tooling improvements (prompts, tools)
- Cursor + Claude Code hybrid workflow
- Spec-driven development as best practice
- **Takeaway:** This is THE productivity tool - invest in mastering it

### 5. Context Engineering
- "The single most important skill" when working with LLMs
- Getting the right context to the right model at the right time
- Applies whether using DAGs or agents
- **Takeaway:** Master this skill - it's how you improve LLM apps over time

### 6. Voice as Interface
- "Over the next decade, voice will be primary interface"
- Voice is 4-5x faster than keyboard/thumbs
- Silicon Valley "declaring war on screens"
- Building a voice-to-text tool himself
- **Takeaway:** Get comfortable instructing technology via voice

### 7. We're Still Early
- Most companies at "zero" AI maturity
- Even watching this video puts you in top percentile
- Fundamentals haven't changed in 2 years - just swap models, tweak prompts
- Don't feel overwhelmed by pace of change
- **Takeaway:** You're in the right spot, don't try to learn everything at once

## A2AI Relevance

**Validates our approach:**
- Context engineering = what we do with CLAUDE.md, skills, structured context
- DAGs vs agents = our skills are more deterministic, agents for exploration
- Agentic coding best practices = exactly what we're teaching
- Voice interface = we have voice-wake skill, inbox voice capture

**For members:**
- Good reassurance video for those feeling overwhelmed
- "We're still early" message important for community morale
- A2A protocol worth watching - could be relevant for multi-agent patterns
- The "cost of hallucination" framework is useful for deciding agent vs workflow

**Key insight:**
The practitioner perspective is valuable - he runs real client projects. His "most companies at zero" observation matches what we see in A2AI. Members are way ahead of average just by being here.

## Interesting Quotes

"If you really look at what happened in the past 2 years... the way you build applications around these models is still pretty much the same"

"If it can just be a few simple Python functions that you chain together and solve your problem reliably, then that's probably the best solution"

"Know that you are in the right spot. You don't have to figure it all out at once."
