# How I Use Claude Code to Ship Like a Team of Five

**From:** Every <hello@every.to>
**Date:** 2025-07-16T15:12:32.000Z
**Folder:** every

---

How I Use Claude Code to Ship Like a Team of Five

It's the first AI tool that feels like delegating to a colleague, not prompting a chatbot

Source Code

How I Use Claude Code to Ship Like a Team of Five

It's the first AI tool that feels like delegating to a colleague, not prompting a chatbot

by Kieran Klaassen

Midjourney/Every illustration.

Kieran Klaassen, the general manager of our email management tool Cora, is redefining what it means to be a programmer in the age of AI—and he’s doing it with Claude Code. Claude Code has changed everything about how he works as a developer: He hasn't typed a function in weeks, yet he's shipping faster than ever. In this piece, he walks us through exactly how he uses it to multiply his productivity. If you're a developer wondering how AI will change your career—or a non-technical founder who's been held back by not knowing how to code—this is essential reading.

To learn more about how Kieran and the rest of the Every team are using Claude Code, join us for a paid subscriber-only workshop this Friday, July 18, at 12 ET. If you’re a paid subscriber, email us at hello@every.to to RSVP; if you’re a free subscriber, upgrade your subscription to attend.—Dan Shipper

Was this newsletter forwarded to you? Sign up to get it in your inbox.

Every piece of code I've shipped in the last two months was written by AI. Not assisted by AI. Written by AI.

Claude Code opens 100 percent of my pull requests, and I haven't typed a function in weeks. And I'm shipping faster than ever.

In February, I watched Claude Code burn through $5 in tokens to make a simple change in the code of Cora, our AI-powered email assistant—something that I could have typed myself for free in 30 seconds. It was like hiring a Michelin-caliber pastry chef to butter toast. I wrote it off as an expensive toy.

Now that it’s included with a Claude subscription, it's turned me from a programmer into an engineering manager overnight, running a team of AI developers who never sleep, never complain about my nitpicks, and occasionally outsmart me.

Claude Code is the first tool that makes everyday coding genuinely optional. The mundane act of typing out implementation details is becoming as obsolete as manual typesetting. What remains valuable is having a perspective on system architecture, taste, product thinking—the uniquely human skills that turn good software into great products. Claude Code makes this shift practical: You define the outcome; it handles the implementation.

The shift from doing the work to directing it changes how we make software. Instead of planning implementation details, we're designing product specifications and code outcomes. Clear communication and system thinking matter more than memorizing syntax or debugging tricks. Features that took a week to code ship in an afternoon of thoughtful delegation. This is a different way of building software entirely.

Multi-step debugging like a senior engineer
I understood what’s special about Claude Code when I encountered the kind of problem that would make most developers cry.

Our solid queue jobs—the background workers that clean up data and handle tasks while the app is running—had stopped doing their job: The queue would grow out of control and Cora would crash. But everything looked perfect: The code was correct, the logs showed nothing wrong. Even Claude Code was initially stumped.

At some point I told Claude Code: "If you cannot figure this out, probably it's related to something on production, ” the live environment where users interact with our app, not our development setup where we test changes.

I asked Claude Code to look into the source code of the Ruby gem, a third-party code library we were using as part of the Cora app. It methodically walked through thousands of lines of someone else's code, step by step, and discovered something we'd have never found otherwise: The jobs were trying to line up under a different queue name in production, like packages being sent to the wrong warehouse. I might have been able to find it myself, after hours of digging through unfamiliar code. But Claude Code turned what could have been a daunting archaeological expedition into a guided tour, and we worked through the problem together. The AI did the research and dug through the source code, and we jointly came to the conclusion.

As it turned out, there was no bug in our code. It was a mismatch between our development setup and the live website. But being able to work through that systematically was a breakthrough.

From programmer to orchestra conductor
Claude Code's superpower is parallel processing—the ability to work on multiple tasks simultaneously without getting confused or mixing up contexts. My monitor looks like mission control: multiple Claude Code tabs, each working on different features through separate git worktrees, meaning I can have Claude modify five different versions of our codebase simultaneously and get clean, review-ready code.

Running four parallel Claude Code agents in Warp, an AI-enabled terminal, doing different work at the same time. Source: The author.

In order to function like this successfully, you have to unlearn how you code. You need to think more like an engineering manager or tech lead rather than an individual contributor. The mental shift is profound. Instead of thinking about files and functions—the letters and words of code— you think about the story you’re trying to tell, the feature specifications you need to give it, and the outcomes you’re looking for. You want to remove yourself as a micromanager of your own code and adopt a stance of trusting your team—with proper checks and balances like code reviews and tests, of course.

This shift matters most when you're running on fumes. "My brain is dead but this is the issue" is a prompt I've used with Claude Code after a long day, and it works. Every small decision ("should this variable be called 'user' or 'customer'?") drains mental energy. By day's end, you're making important architectural decisions on 5 percent battery.

Claude Code lets you offload the implementation details when you need your remaining focus for the hard problems, or when you just need to step away and let your subconscious work.

The friction factor: Why I use Claude Code every day
Plenty of AI tools write code. Claude Code is unique because of what it doesn't make you do.

Compare Claude Code to the alternatives:

Become a paid subscriber to Every to unlock this piece and learn:

How Claude Code integrates with your existing workflow, not a specialized environment

The three simple commands Kieran uses

Why Claude Code is a boost for junior developer

Kieran’s morning workflow with Claude Code

Plus: Watch four demo videos

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
