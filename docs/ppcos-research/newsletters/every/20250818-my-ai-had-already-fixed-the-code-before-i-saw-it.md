# My AI Had Already Fixed the Code Before I Saw It

**From:** Every <hello@every.to>
**Date:** 2025-08-18T15:35:56.000Z
**Folder:** every

---

My AI Had Already Fixed the Code Before I Saw It

Compounding engineering turns every pull request, bug fix, and code review into permanent lessons your development tools apply automatically

Source Code

My AI Had Already Fixed the Code Before I Saw It

Compounding engineering turns every pull request, bug fix, and code review into permanent lessons your development tools apply automatically

by Kieran Klaassen

Midjourney/Every illustration.

Was this newsletter forwarded to you? Sign up to get it in your inbox.

Before I opened my laptop, the code had reviewed itself.

I launched GitHub expecting to dive into my usual routine—flag poorly named variables, trim excessive tests, and suggest simpler ways to handle errors. Instead, I found a few strong comments from Claude Code, the AI that writes and edits in my terminal:

"Changed variable naming to match pattern from PR [pull request] #234, removed excessive test coverage per feedback on PR #219, added error handling similar to approved approach in PR #241."

In other words, Claude had learned from three prior months of code reviews and applied those lessons without being asked. It had picked up my tastes thoroughly, the way a sharp new teammate would—and with receipts.

It felt like cheating, but it wasn't—it was compounding. Every time we fix something, the system learns. Every time we review something, the system learns. Every time we fail in an avoidable way, the system learns. That's how we build Cora, Every’s AI-enabled email assistant, now: Create systems that create systems, then get out of the way.

I call this compounding engineering: building self-improving development systems where each iteration makes the next one faster, safer, and better.

Typical AI engineering is about short-term gains. You prompt, it codes, you ship. Then you start over. Compounding engineering is about building systems with memory, where every pull request teaches the system, every bug becomes a permanent lesson, and every code review updates the defaults. AI engineering makes you faster today. Compounding engineering makes you faster tomorrow, and each day after.

Three months of compounding engineering on Cora have completely changed the way I think about code. I can't write a function anymore without thinking about whether I'm teaching the system or just solving today's problem. Every bug fix feels half-done if it doesn't prevent its entire category going forward, and code reviews without extractable lessons seem like wasted time.

When you're done reading this, you'll have the same affliction.

Bland Is the Most Powerful Voice AI in the World

In fact, chances are, you’ve already spoken to it without even noticing. Everyone from Fortune 500’s to startups has been using Bland to build AI voice agents for sales, support, and much more. It can:

Answer phone, SMS, and web‑chat requests 24/7—no hold music, no queues

Scale to 1 million+ simultaneous conversations while slashing support costs

Speak any language and connect to any backend CRM, ticketing, or data source

Stay on‑brand with guard‑railed reasoning that prevents hallucinations and off‑script replies

Hundreds of enterprises and high‑growth startups already trust Bland to boost CSAT, cut resolution times, and free up agents for higher‑value work. Curious?

Call the number in the image or Every readers can get started here for free.

Want to sponsor Every? Click here.

The 10-minute investment that pays dividends forever
Compounding engineering asks for an upfront investment: You have to teach your tools before they can teach themselves.

Here’s an example of how this works in practice: I’m building a “frustration detector” for Cora; the goal is for our AI assistant to notice when users get annoyed with the app’s behavior and automatically file improvement reports. A traditional approach would be to write the detector, test it manually, tweak, and repeat. This takes significant expertise and time, a lot of which is spent context-switching between thinking like a user and thinking like a developer. It’d be better if the system could teach itself.

So I start with a sample conversation where I express frustration—like repeatedly asking the same question with increasingly terse language. Then I hand it off to Claude with a simple prompt: "This conversation shows frustration. Write a test that checks if our tool catches it."

Claude writes the test. The test fails—the natural first step in test-driven development (TDD). Next, I tell Claude to write the actual detection logic. Once written, it still doesn't work perfectly, which is also to be expected. Now here's the beautiful part: I can tell Claude to iterate on the frustration detection prompt until the test passes.

Not only that—it can keep iterating. Claude adjusts the prompt and runs the test again. It reads the logs, sees why it missed a frustration signal, and adjusts again. After a few rounds, the test passes.

But AI outputs aren't deterministic—a prompt that works once might fail the next time.

So I have Claude run the test 10 times. When it only identifies frustration in four out of 10 passes, Claude analyzes why it failed the other six times. It studies the chain of thought (the step-by-step thinking Claude showed when deciding whether someone was frustrated) from each failed run and discovers a pattern: It's missing hedged language a user might use, like, "Hmm, not quite," which actually signals frustration when paired with repeated requests. Claude then updates the original frustration-detection prompt to specifically look for this polite-but-frustrated language.

On the next iteration, it’s able to identify a frustrated user nine times out of 10. Good enough to ship.

We codify this entire workflow—from identifying frustration patterns to iterating prompts to validation—in CLAUDE.md, the special file Claude pulls in for context before each conversation. The next time we need to detect a user's emotion or behavior, we don’t start from scratch. We say: "Use the prompt workflow from the frustration detector." The system already knows what to do.

And unlike human-written code, the "implementation" here is a prompt that Claude can endlessly refine based on test results. Every failure teaches the system. Every success becomes a pattern.

We've open-sourced this prompt testing framework so other teams can build their own compounding workflows.

From terminal to mission control
Most engineers treat AI as an extra set of hands. Compounding engineering turns it into an entire team that gets faster, sharper, and more aligned with every task.

At Cora, we’ve used this approach to:...

Become a paid subscriber to Every to unlock this piece and learn exactly how Kieran has used compounding engineering to build Cora, and his five-step compounding engineering playbook.

Upgrade to paid

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

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
