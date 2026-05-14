# Teach Your AI to Think Like a Senior Engineer

**From:** Every <hello@every.to>
**Date:** 2025-11-07T18:28:05.000Z
**Folder:** every

---

Teach Your AI to Think Like a Senior Engineer
These are the eight strategies I use to help my AI learn my codebase, my patterns, and my preferences
Source Code
Teach Your AI to Think Like a Senior Engineer
These are the eight strategies I use to help my AI learn my codebase, my patterns, and my preferences
by Kieran Klaassen
Midjourney/Every illustration.
This is a free preview of a subscribers-only post.
Was this newsletter forwarded to you? Sign up to get it in your inbox.
I’ve written about why having your AI coding assistant plan before it codes lets you ship faster than jumping straight to code. It’s my method for making my AI smarter with every feature.
For example, when I needed to implement Cora’s email bankruptcy feature—clearing 53,000-email inboxes without deleting anything important—I didn’t start by coding. I created a research agent to plan instead.
I thought this would be an easy feature. Bulk archive 53,000 emails—how hard could it be? I asked the research agent to analyze our own bulk operation patterns, check API limits for mass actions, and propose three implementation approaches with tradeoffs.
Twenty minutes later, it came back with a reality check: Gmail rate limits would kill us at 2,000 emails, our system would timeout on long operations, and the user would have to wait too long for the result. I thought it would be a quick feature, but it turned into a three-day architectural challenge. Planning had saved me from wasting time building the wrong thing entirely.
You can avoid building the wrong thing, too. I’ll show you the concrete tactics that turn a planning philosophy into working systems, starting with how to run parallel research operations that teach your AI how you think. Look out for Github links throughout the article—I’ve added them so you can copy and adapt the exact agents and commands I use, rather than building everything from scratch.
The eight planning strategies
When you’re planning with AI, you’re running parallel research operations—each one a specialized agent gathering different kinds of knowledge. Then you work together: The agents bring findings, you make decisions, and together you combine and distill everything into one coherent plan.
Build a project in a single day
AI can feel abstract until you build something real—and tools “made for programmers” can stop you before you start. Spend one day with Every’s Dan Shipper to get acquainted with the best tools on the market, assign your AI agents real tasks, and ship something live. Claude Code for Beginners runs Nov. 19, live on Zoom. You’ll leave with a project, a reusable workflow, and a head start on building the agentic apps that will populate the future.
Save your seat now
Want to sponsor Every? Click here.
It’s much faster for five agents to research in parallel than for a human to plan step by step. Your contribution to the process is taste, judgment, and context about what matters for your product and users.
I use eight research strategies, depending on the fidelity level, which refers to the degree of difficulty. Fidelity One is quick fixes like one-line changes, obvious bugs, and copy updates. Fidelity Two covers features spanning multiple files with clear scope but non-obvious implementation. Fidelity Three covers major features where you don’t even know what you’re building yet.
Strategy 1:
Become a paid subscriber to Every to unlock this piece and learn about:
• A git search showed my teammate already tried upgrading that library three months ago—and deliberately rolled it back
• My AI reads library source code to find capabilities that haven’t made it to the documentation yet
• And the 6 other planning strategies that teach your AI how you think
Upgrade to paid
This post is for
paying subscribers.
Try for $1
Or, learn more.
