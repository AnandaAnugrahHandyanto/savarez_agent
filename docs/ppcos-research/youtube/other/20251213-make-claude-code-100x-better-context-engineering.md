# Make Claude Code 100x BETTER (Context Engineering)

**Channel:** Kenny Liao
**Date:** 2025-12-13
**URL:** https://www.youtube.com/watch?v=ySA9tJ8RfVM

---

## Summary

Kenny Liao provides an in-depth technical walkthrough of context engineering in Claude Code - the practice of strategically managing what information goes into an AI agent's context window to get better, more reliable results. He demonstrates the full system prompt, hooks, memory systems, sub-agents, and progressive disclosure patterns that make Claude Code effective.

## Key Concepts

### 1. Context Engineering Definition
"Context engineering is building dynamic systems that provide the right information at the right time to the model." It's about curating and refining what goes into the context window - not just prompt engineering, but a continuous process of managing attention as a limited resource.

### 2. The Attention Scarcity Problem
Models have limited attention. Research shows that as you add more distractors (irrelevant text) or increase input tokens, the model's ability to retrieve the right information and complete tasks degrades significantly. The graphs show performance dropping from blue (good) to red (poor) as context increases.

### 3. Progressive Disclosure
Claude Code uses progressive disclosure - not loading all tool definitions and context upfront, but revealing them when needed. For example, MCP server tools aren't loaded until Claude actually needs them, keeping the context focused.

### 4. The Memory & Context System
- **CLAUDE.md files** - Instructions that override default behavior
- **Context directory** - Project-specific files Claude can reference
- **Memory folder** - Persistent memories across sessions
- **System reminders** - Injected at specific points in conversation

### 5. Hooks for Dynamic Context
- **User prompt submit hook** - Runs before each user message is processed
- **Stop hook** - Runs when Claude is about to finish its response
- Can inject reminders like "update your memories before finishing"
- Can check conditions (e.g., "has context system been set up?")

### 6. Sub-Agents with Separate Context Windows
Sub-agents get their own 200K context window, protecting the main agent's context. The main agent only sees the final summary/output, not all the intermediate work. Perfect for research tasks that consume lots of context.

### 7. Compaction
The `/compact` command shrinks conversation history into a concise summary, freeing up context space. Useful for long-running tasks where you want to maintain continuity without consuming all available context.

## Practical Examples

- **Personal Assistant Plugin**: Kenny built a plugin with identity files, preferences, rules, and memory that persists across all conversations
- **Claude Playing Pokemon**: Demonstrates sub-agents - Claude beat the game over weeks without human intervention using 55,000 steps
- **Thumbkit CLI Tool**: Example of giving Claude access to external tools via the terminal

## Technical Details from Claude Code's System Prompt

The video shows the actual system prompt including:
- Role definition as a "software developer and coding agent"
- Tool definitions for all built-in tools
- Instructions about auto-approvals
- Output style preferences
- MCP server tool definitions (when connected)

## Key Takeaways

1. Context is a limited resource - treat it like attention
2. Don't dump everything in; use progressive disclosure
3. Leverage hooks for dynamic context injection
4. Use sub-agents for context-heavy tasks
5. Persist important information to memory files
6. Compact when conversations get long
7. The problem often isn't bad prompting - it's missing context
