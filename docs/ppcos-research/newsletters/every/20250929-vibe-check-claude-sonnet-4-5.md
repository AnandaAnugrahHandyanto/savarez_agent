# Vibe Check: Claude Sonnet 4.5

**From:** Every <hello@every.to>
**Date:** 2025-09-29T17:06:27.000Z
**Folder:** every

---

Vibe Check: Claude Sonnet 4.5

Faster than GPT-5 Codex, smarter and more steerable than Opus 4.1

Vibe Check

Vibe Check: Claude Sonnet 4.5

Faster than GPT-5 Codex, smarter and more steerable than Opus 4.1

by Dan Shipper

MIdjourney/Every illustration.

Was this newsletter forwarded to you? Sign up to get it in your inbox.

Anthropic just rolled out Claude Sonnet 4.5, and, of course, we spent the weekend using it to code and running long agentic tasks with it.

The headline: It’s noticeably faster, more steerable, and more reliable than Opus 4.1—especially inside Claude Code. In head-to-head tests it blitzed through a large pull request review in minutes, handled multi-file reasoning without wandering, and stayed terse when we asked it to.

It won’t dethrone GPT-5 Codex for the trickiest production bug hunts, but as a day-to-day builder’s tool, it feels like an exciting jump. Here’s our day zero vibe check.

Speed
If you’re used to using Opus in Claude Code or the Claude app, you’ll be happy: The new Sonnet 4.5 is really fast. Kieran Klaassen, general manager of Cora, said, “It feels about 50 percent faster than previous versions of Claude.”

In a head-to-head code review challenge, it finished a comprehensive code review of a new feature in a large code base in about two minutes. GPT-5 Codex took about 10 to do the same task.

Speed is a dimension of intelligence, and Sonnet 4.5’s speed makes it much easier to pair with.

Performance
It’s quite good at long-running agentic tasks in the Claude app and in Claude Code. I fed it the three spreadsheets we use to run Every, our profit-and-loss accounting, our weekly performance tracker, and our consulting tracker—and it easily wrote a Word doc with a third-quarter investor update that I could’ve sent with only minor tweaks.

Kieran found that it solved a bug in Cora in about 20 minutes that Opus 4.1 couldn’t crack at all. He also used it to vibe code an iOS app for Cora by feeding it the current codebase and a book on iOS programming:

The Cora iOS app that Kieran vibe coded with Claude Sonnet 4.5. (Source: Kieran Klaassen.)

This jump in performance seems to be a combination of:

Better steerability: It’s able to adhere better to the directions in your prompt in a way that feels like GPT-5 Codex. It is less overeager than previous versions of Claude. Alex Duffy, who leads our AI training, told me that it feels more reliable as a result.

Ability to manage big contexts: It is less likely to get lost in big code bases and knows what to pay attention to in long prompts.

More deterministic. Alex noted that it’s more likely to come to the same result given the same prompt multiple times. This predictability makes it easier to use.

More focused and terse: Kieran noted that it seems like Anthropic has learned from GPT-5. The new Sonnet 4.5 just tells you what you need to know, instead of going on tangents, which makes it easier to work with.

There’s one notable exception: GPT-5 Codex still beats Claude Sonnet 4.5 for difficult production coding tasks. When I asked it to review a large pull request, Sonnet finished faster—but Codex caught a hard-to-find edge case that Sonnet missed.

Make your team AI‑native
Scattered tools slow teams down. Every Teams gives your whole organization full access to Every and our AI apps—Sparkle to organize files, Spiral to write well, Cora to manage email, and Monologue for smart dictation—plus our daily newsletter, subscriber‑only livestreams, Discord, and course discounts. One subscription to keep your company at the AI frontier. Trusted by 200+ AI-native companies—including The Browser Company, Portola, and Stainless.

Create your team

Want to sponsor Every? Click here.

The Reach Test: Do we use it every day?
The best leading indicator for long-term usefulness of an AI product is what we call the Reach Test: Do we find ourselves automatically turning to this tool to do certain tasks? Or do we leave it on the shelf and forget about it?

Dan: No

ChatGPT and Codex CLI are my current daily drivers for coding. I’d reach for this over Opus 4.1 when I want to use Claude, though.

For day-to-day use cases, it’s hard to beat GPT-5’s speed in ChatGPT. For programming use cases, I trust GPT-5 Codex more. Right now, I’m primarily programming in large codebases that I’m unfamiliar with—like building features for Cora—rather than vibe coding, and GPT-5 Codex makes me feel like I’m less likely to submit an embarrassing PR.

Kieran: Yes

For Kieran, it’s hard to beat the combination of Sonnet 4.5 in Claude Code’s harness. “Claude Code is like a smart person who’s programmed for 20 years,” as compared to Opus 4.1 which feels like “it has a Ph.D.,” or GPT-5 Codex, which feels like “a grumpy senior engineer.”

Claude Code is a more fully-featured command line interface than Codex CLI, and Sonnet 4.5 can push it to its fullest: It’s good at background tasks, like running servers and coordinating multiple parallel subagents, the latter of which is currently not available in Codex.

Alex: Yes

Alex would use Sonnet 4.5 in Claude Code over Opus 4.1. Claude Code is still his daily driver over Codex CLI.

The final verdict
If you’re using Claude Code as your daily driver for programming, you just got a new best friend in Sonnet 4.5. It’s faster, more reliable, and more steerable than Opus 4.1. If you’re a newly minted GPT-5 Codex stan, Sonnet 4.5 isn’t going to make you switch back—but you should consider it for new projects, vibe coding, and tasks that require Claude’s unique combination of industriousness and speed.

At publish time, Sonnet 4.5’s pricing wasn’t available, but if we assume it stays the same as Sonnet 4—$3 per million input tokens—it’s an easy switch to anything currently running on Opus in the API. Opus 4.1 is five times more expensive, and Sonnet 4.5 is faster and smarter. GPT-5 is still significantly cheaper, however.

Dan Shipper is the cofounder and CEO of Every, where he writes the Chain of Thought column and hosts the podcast AI & I. You can follow him on X at @danshipper and on LinkedIn, and Every on X at @every and on LinkedIn.

We build AI tools for readers like you. Write brilliantly with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora. Dictate effortlessly with Monologue.

We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.

Get paid for sharing Every with your friends. Join our referral program.

Was this newsletter forwarded to you? Sign up to get it in your inbox.

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

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
