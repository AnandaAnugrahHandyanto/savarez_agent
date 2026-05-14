# Compound Engineering: How Every Codes With Agents

**From:** Every <hello@every.to>
**Date:** 2026-01-30T16:01:51.000Z
**Folder:** every

---

Compound Engineering: How Every Codes With Agents
A four-step engineering process for software teams that don’t write code
Source Code
Compound Engineering: How Every Codes With Agents
A four-step engineering process for software teams that don’t write code
by Dan Shipper and Kieran Klaassen
Midjourney/Every illustration.
While we’re on our Think Week offsite this week, we’re resurfacing Cora general manager Kieran Klaassen’s work on the theme of compound engineering. In this final piece, Kieran teams up with Dan Shipper to describe how compound engineering allows Every’s lean team to provide multiple software products to thousands of users. They propose a four-step loop (plan, work, review, compound) for software teams writing code with AI so you can create the same development magic. Read on for the complete framework, and learn why planning dominates 80 percent of the process.—Kate Lee
Was this newsletter forwarded to you? Sign up to get it in your inbox.
What happens to software engineering when 100 percent of your code is written by agents? This is a question we’ve had to confront head-on at Every as AI coding has become so powerful. Nobody is writing code manually. It feels weird to be typing code into your computer or staring at a blinking cursor in a code editor.
So much of engineering until now assumed that coding is hard and engineers are scarce. Removing those bottlenecks makes traditional engineering practices—like manually writing tests, or laboriously typing human readable code with lots of documentation—feel slow and outdated. In order to deal with these new powers and changing constraints, we’ve created a new style of engineering at Every that we call compound engineering.
In traditional engineering, you expect each feature to make the next feature harder to build—more code means more edge cases, more interdependencies, and more issues that are hard to anticipate. By contrast, in compound engineering, you expect each feature to make the next feature easier to build. This is because compound engineering creates a learning loop for your agents and members of your team, so that each bug,  failed test, or a-ha problem-solving insight gets documented and used by future agents. The complexity of your codebase still grows, but now so does the AI’s knowledge of it, which makes future development work faster.
And it works. We run five software products in-house (and are incubating a few more), each of which is primarily built and run by a single person. These products are used by thousands of people every day for important work—they’re not just nice demos.
This shift has huge implications for how software is built at every company, and how ambitious and productive every developer can be: Today, if your AI is used right, a single developer can do the work of five developers a few years ago, based on our experience at Every. They just need a good system to harness its power.
The rest of this piece will give you a high-level sense of how we practice compound engineering inside of Every. By the time you’re done, you should be able to start doing the basics yourself—and you’ll be primed to go much deeper.
Write at the speed of thought
That gap between your brain and your fingers kills momentum. Monologue lets you speak naturally and get perfect text 3x faster, and your tone, vocabulary, and style is kept intact. It auto-learns proper nouns, handles multilingual code-switching mid-sentence, and edits for accuracy. Free 1,000 words to start.
Download Monologue for Mac
Want to sponsor Every? Click here.
Compound engineering loop
A compound engineer orchestrates agents running in parallel, who plan, write, and evaluate code. This process happens in a loop that looks like this:
Plan: Agents read issues, research approaches, and synthesize information into detailed implementation plans.

Work: Agents write code and create tests according to those plans.

Review: The engineer reviews the output itself and the lessons learned from the output.

Compound: The engineer feeds the results back into the system, where they make the next loop better by helping the whole system learn from successes and failures. This is where the magic happens.

We use Anthropic’s Claude Code primarily for compound engineering, but it is tool-agnostic—some members of our team also use startup Factory’s Droid and OpenAI’s Codex CLI. If you want to get more hands-on with how we do this, we’ve built a compound engineering plugin for Claude Code that lets you run the exact workflow we use internally yourself.
Roughly 80 percent of compound engineering is in the plan and review parts, while 20 percent is in the work and compound.
Let’s dive in.
Become a paid subscriber to Every to unlock this piece and learn about:
Why the hardest part of AI coding happens before any code gets written

The “money step” that turns every bug into a permanent advantage

How compound engineering quickly makes new hires as effective as veterans

Subscribe
Start free trial
What is included in a subscription?
Daily insights from AI pioneers + early access to powerful AI tools
Front-row access to the future of AI
In-depth reviews of new models on release day
Playbooks and guides for putting AI to work
Prompts and use cases for builders
Bundle of AI software
Sparkle: Organize your Mac with AI
Cora: The most human way to do email
Spiral: Repurpose your content endlessly
Monologue: Effortless voice dictation for your Mac