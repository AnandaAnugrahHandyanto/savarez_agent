# Teach Your AI to Think Like a Senior Engineer

**From:** Every <hello@every.to>
**Date:** 2026-01-29T16:01:28.000Z
**Folder:** every

---

Teach Your AI to Think Like a Senior Engineer
These are the eight strategies I use to help my AI learn my codebase, my patterns, and my preferences
Source Code
Teach Your AI to Think Like a Senior Engineer
These are the eight strategies I use to help my AI learn my codebase, my patterns, and my preferences
by Kieran Klaassen
Midjourney/Every illustration.
While we’re on our Think Week offsite this week, we’re resurfacing Cora general manager Kieran Klaassen’s work on the theme of compound engineering. In this piece, he talks about how running multiple specialized research agents in parallel before writing any code helps prevent building the wrong solution entirely—all while the human contributes judgment and taste. Plus: Eight planning strategies organized by complexity level that make your AI progressively smarter.—Kate Lee
Was this newsletter forwarded to you? Sign up to get it in your inbox.
I’ve written about why having your AI coding assistant plan before it codes lets you ship faster than jumping straight to code. It’s my method for making my AI smarter with every feature.
For example, when I needed to implement Cora’s email bankruptcy feature—clearing 53,000-email inboxes without deleting anything important—I didn’t start by coding. I created a research agent to plan instead.
I thought this would be an easy feature. Bulk archive 53,000 emails—how hard could it be? I asked the research agent to analyze our own bulk operation patterns, check API limits for mass actions, and propose three implementation approaches with tradeoffs.
Twenty minutes later, it came back with a reality check: Gmail rate limits would kill us at 2,000 emails, our system would timeout on long operations, and the user would have to wait too long for the result. I thought it would be a quick feature, but it turned into a three-day architectural challenge. Planning had saved me from wasting time building the wrong thing entirely.
You can avoid building the wrong thing, too. I’ll show you the concrete tactics that turn a planning philosophy into working systems, starting with how to run parallel research operations that teach your AI how you think. Look out for Github links throughout the article—I’ve added them so you can copy and adapt the exact agents and commands I use, rather than building everything from scratch.
Write at the speed of thought
That gap between your brain and your fingers kills momentum. Monologue lets you speak naturally and get perfect text 3x faster, and your tone, vocabulary, and style is kept intact. It auto-learns proper nouns, handles multilingual code-switching mid-sentence, and edits for accuracy. Free 1,000 words to start.
Download Monologue for Mac
Want to sponsor Every? Click here.
The eight planning strategies
When you’re planning with AI, you’re running parallel research operations—each one a specialized agent gathering different kinds of knowledge. Then you work together: The agents bring findings, you make decisions, and together you combine and distill everything into one coherent plan.
It’s much faster for five agents to research in parallel than for a human to plan step by step. Your contribution to the process is taste, judgment, and context about what matters for your product and users.
I use eight research strategies, depending on the fidelity level, which refers to the degree of difficulty. Fidelity One is quick fixes like one-line changes, obvious bugs, and copy updates. Fidelity Two covers features spanning multiple files with clear scope but non-obvious implementation. Fidelity Three covers major features where you don’t even know what you’re building yet.
Strategy 1: Reproduce and document
What it does: Attempts to reproduce bugs or issues before planning fixes
When to use it: Fidelity One and Two, especially bug fixes
The agent’s job: Create a step-by-step reproduction guide
Prompt: “Reproduce this bug, don’t fix it, just gather all the logs and info you need.”
Right after the launch of Cora’s email bankruptcy feature, 19 users were stuck. They’d clicked “archive everything,” but the job failed. Instead of guessing the reason for the problem, I told Claude Code: “Loop through the AppSignal logs and diagnose this.” (AppSignal logs are our error tracking system that records what goes wrong in production.)
Five minutes later, I had a reply: Rate limit errors were being swallowed in production. The job hit Gmail’s limit, failed silently, and never resumed. Users would click “archive everything,” see a loading spinner, and wait forever—because when one batch failed, the entire job stopped, but we never told the user. That reproduction showed we needed batch processing and job resumption, not just retries.
The agent reproduced the bug, found the root cause in production logs (records of what's happening on the live site users interact with), and documented everything automatically. (All screenshots courtesy of the author.)
How to make this compound: To make sure that this issue wouldn’t happen in the future, I updated my @kieran-rails-reviewer agent—one of the specialized reviewers that automatically checks plans and code as part of my compounding engineering flow. I added to its checklist: “For any background job that calls external APIs—does it handle rate limits? Does it retry? Does it leave users in partial states?” We forgot to retry once. The system won’t let us forget again.
Strategy 2: Ground in best practices
What it does: Searches the web for how others solved similar problems
When to use it: All fidelities, especially unfamiliar patterns
The agent’s job: Find and summarize relevant blog posts, documentation, and solutions
Agent: “@agent-best-practices-researcher”
This strategy works for anything where someone else has already solved your problem—things like technical architecture, copywriting patterns, pricing research, or upgrade paths.
When I needed to upgrade a gem—a pre-built code library I use—that was two versions behind, I had an agent search: “upgrade path from version X to Y,” “breaking changes between versions,” “common migration issues.” It found the official upgrade guide, plus three blog posts from engineers who’d done the same upgrade and hit edge cases. That research took three minutes and prevented hours of trial-and-error debugging.
I’ve also used this for non-technical decisions: “SaaS pricing tiers best practices” returned frameworks for structuring pricing plans. “Email drip campaign conversion copy” found proven email templates. “Background job retry strategies” surfaced patterns in how other companies solved that problem at scale.
The best-practices agent found: the library's official documentation, changelogs (lists of what changed between versions), and upgrade guides showing how to move my code to the new version—all with source links automatically included.
How to make this compound: When the agent finds a particularly useful pattern, I have it automatically save the key findings to `docs/*.md` files in my project. For instance, I’ve saved “docs/pay-gem-upgrades.md” for migration patterns and “docs/pricing-research.md” for pricing insights. Next time a similar question comes up, the agent checks these documents first before searching the web. My knowledge base is constantly growing and improving.
Strategy 3: Ground in your codebase
What it does: Finds similar existing patterns in your code
When to use it: Anything that might duplicate existing functionality
The agent’s job: Search through your existing code for related implementations
Before adding event tracking—the system that tracks what users click and when—to a new feature, I had an agent search our codebase: “How do we currently handle event tracking? What’s our pattern for analytics calls? Where do we send events?”
It found we already had a tracking system that I’d forgotten about, complete with helper methods, which are reusable bits of code that handles repetitive tasks (in this case, adding tracking). If AI doesn’t ground itself in your codebase, it often thinks it needs to create a solution from scratch. In this case, instead of reinventing event tracking, we extended the existing pattern. The search prevented building a second, incompatible tracking system and saved time.
How to make this compound: I created an “@event-tracking-expert” agent that distills everything about how we do tracking—our helper methods, our event format, when to track versus when not to. Now when it’s planning any feature that needs tracking, that specialist agent runs automatically. I don’t search the codebase from scratch anymore—the expert already knows our patterns.
Strategy 4: Ground in your libraries
What it does: Reads source code of installed packages and gems
When to use it: When using fast-moving or poorly documented libraries
The agent’s job: Analyze the source code to understand what’s possible
I use a Ruby gem called RubyLLM for AI API calls. It updates constantly with new models, new parameters, and new capabilities, but documentation lags behind. So when I need to use it, I have an agent read the gem’s source code: “Look through the RubyLLM source. What model options are available? What parameters can I pass? Are there any undocumented features in the latest version?”
The agent comes back with: “Version 1.9 added streaming support but it’s not in the docs yet. Here’s the parameter name and example usage from the test suite.”
Why this compounds: Every time you update a dependency (a library your code relies on), the knowledge auto-updates. You’re never working with stale information.
Strategy 5: Study git history
What it does: Analyzes commit history (the log of all past changes to your code) to understand intent
When to use it: Refactors, continuing work, understanding “why”
The agent’s job: Research past decisions and their context
I was working on a feature and noticed we were using an outdated version of our EmailClassifier feature, which identifies what a given email is and whether it should stay in the inbox or get briefed. My first thought was: “Why haven’t we upgraded this? Let me update it.”
Before making the change, I had an agent search the git history: “Why are we using v1? Has anyone tried upgrading to v2?”
It found a pull request from three months ago—from a different team member—that had upgraded to version two, discovered that version two put inbox emails in the archive and archive emails in the inbox (the opposite of what we want), and deliberately rolled back with detailed reasoning in the PR discussion. Version two changed how it handled edge cases, which would have broken our email scheduling.
That five-minute git search saved me from reintroducing a bug someone else had already debugged and fixed.
Why this compounds: Institutional memory gets preserved and searchable. New team members inherit the reasoning behind past decisions.
Strategy 6: Vibe prototype for clarity
What it does: Rapid prototyping in a separate environment to clarify requirements
When to use it: Fidelity Three, UX uncertainty, exploratory work
The agent’s job: Quickly build throwaway versions you can interact with
Prompt: “Create a working prototype, in the style of a mockup using React and Next, grayscale of XYZ”
For a redesigned email Brief interface, I didn’t know what layout would feel right. So I vibe coded five different prototypes in Claude, each of which took five minutes to build. I clicked through them, noticed what annoyed me, and showed the best one to a few users.
One user said, “This layout feels overwhelming and I don’t know how to archive emails.” That insight became a requirement in the real planning: “Archive button must be in top-left corner—user muscle memory expects it there from Gmail.”
The prototypes got deleted. The knowledge went into the plan.
Why this compounds: Vibe coding turns uncertainty into concrete specifications. You’re not guessing what users want—you’re showing them options and documenting their reactions.
Strategy 7: Synthesize with options
What it does: Combines all research into one plan showing multiple approaches with tradeoffs
When to use it: End of the research phase, before implementation
The agent’s job: Present 2-3 solution paths with honest pros and cons
After running strategies 1-6, I have an agent synthesize everything: “Based on all this research, show me three ways to solve this problem. For each approach, tell me: implementation complexity, performance impact, maintenance burden, and which existing patterns it matches.”
For syncing users’ Gmail inboxes with Cora so we could display their emails, the synthesis came back with:
Option A—Use existing sync system: Fast to implement, but creates overlap with current code and muddies separation of concerns
Option B—Real-time sync: Clean architecture, but slow and potential reliability issues
Option C—Build mirror caching system: Best long-term solution, cleanest separation, but most upfront work
In other words, it was suggesting I either: bolt Gmail syncing onto our current system (quick but messy—like duct-taping a second mailbox to your existing one), fetch emails from Gmail every single time a user opens Cora (clean but slow—like calling the post office to check your mail instead of having a mailbox), or build our own local copy of the user’s Gmail that stays in sync (more work upfront, but fastest and most reliable long-term—like having your own mailbox that updates automatically).
Once I saw that comparison laid out, I was able to make an informed choice in 30 seconds. The agent did the research; I contributed the judgment.
Why this compounds: Your choice reveals preferences. When I picked Option C and noted, “I prefer widely supported over cutting-edge,” that preference gets codified. Next time there’s a similar decision, the system knows to weight compatibility highly.
Strategy 8: Review with style agents
What it does: Runs the completed plan through specialized reviewers that check for your preferences
When to use it: Final planning step, before implementation
The agent’s job: Catch misalignments with your coding style and architecture preferences
I have three review agents that run automatically:
Simplification agent: Flags over-engineering. “Do we really need three database tables for this? Could one table with a type field work?”
Security agent: Checks for common vulnerabilities. “This plan allows user input directly into a database query—add input sanitization.”
Kieran-style agent: Enforces my personal preferences. “This uses complex joins (combining data from multiple database tables in a single query). Kieran prefers simple queries. Consider denormalizing (storing redundant data for simpler queries).”
Plans get better before any code is written.
Why this compounds: These agents accumulate your taste over time. Every time I indicate, “I don’t like this” or “Good catch,” the system gets smarter.
Getting started: Try this today
You don’t need to build everything from scratch. I’ve open-sourced my planning system on Every’s Github marketplace. Install it in Claude Code, and you’ll have working /plan slash command and research agents immediately. You can also use my plugin in Claude Code or Droid.
But you can also start more simply by applying the thinking to your next feature:
Pick one Fidelity Two feature you’re building this week. It should span multiple files and have clear scope, like adding a new view, implementing a feedback system, or refactoring a component (a reusable piece of your application).
Before prompting Claude Code or Cursor to build it, spend 15-20 minutes researching:
Best practices: How have others solved similar problems? Search the web for blog posts, Stack Overflow discussions, and documentation.

Your patterns: How have you solved similar problems? Search your existing codebase for comparable features.

Library capabilities: What do your tools actually support? If you’re using a specific code library, have AI read its documentation or source code

Have AI synthesize this research into a plan showing:
The problem being solved (one clear sentence)

Two or three solution approaches (with honest pros and cons of each)

Which existing code patterns this should match

Any edge cases or security considerations

Review the plan and notice your reactions. When you think “this is too complex” or “we already have a better way to do this,” don’t just fix this plan—capture why you think that. Write it down.
Ship the feature based on the plan, then compare the final implementation to the original plan. Where did you diverge? Why? What would have made the plan better?
Take 10 minutes to codify one learning. The simplest way: Add it to your CLAUDE.md file. Write one rule: “When doing X type of work, remember to check Y,” or “I prefer approach A over approach B because of reason C.”
As you accumulate more learnings, create specialized research agents or commands you can call, such as an “Event Tracking Expert” that knows your patterns, or a “Security Checker” that flags common mistakes. Each agent is just codified knowledge that runs automatically.
That was just one feature, one planning session, one captured learning. Next week, do it again. Reference your notes. See if the second plan is better than the first. In a few months, you’ll have a system that knows how you think.
Thanks to Katie Parrott for editorial support.
Kieran Klaassen is the general manager of Cora, Every’s email product. Follow him on X at @kieranklaassen or on LinkedIn.
To read more essays like this, subscribe to Every, and follow us on X at @every and on LinkedIn.
We build AI tools for readers like you. Write brilliantly with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora. Dictate effortlessly with Monologue.
We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.
Get paid for sharing Every with your friends. Join our referral program.
For sponsorship opportunities, reach out to sponsorships@every.to.
Help us scale the only subscription you need to stay at the edge of AI. Explore open roles at Every.
Subscribe
What did you think of this post?
Amazing
Good
Meh
Bad
Get More Out Of Your Subscription
Try our AI tools for ultimate productivity
Front-row access to the future of AI
In-depth reviews of new models on release day
Playbooks and guides for putting AI to work
Prompts and use cases for builders
Bundle of AI software
Sparkle: Organize your Mac with AI
Cora: The most human way to do email
Spiral: Repurpose your content endlessly
Monologue: Effortless voice dictation for your Mac