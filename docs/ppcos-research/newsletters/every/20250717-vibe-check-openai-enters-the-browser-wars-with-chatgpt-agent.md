# Vibe Check: OpenAI Enters the Browser Wars With ChatGPT Agent

**From:** Every <hello@every.to>
**Date:** 2025-07-17T17:07:39.000Z
**Folder:** every

---

Vibe Check: OpenAI Enters the Browser Wars With ChatGPT Agent

It’s launching today! Here’s our day-zero, hands-on report.

Vibe Check

Vibe Check: OpenAI Enters the Browser Wars With ChatGPT Agent

It’s launching today! Here’s our day-zero, hands-on report.

by Dan Shipper

Midjourney/Every illustration.

Was this newsletter forwarded to you? Sign up to get it in your inbox.

Surprise! Operator and deep research had a baby, and it’s called ChatGPT Agent.

You can imagine the meet-cute happening in a dark, humming server room in Texas:

Deep research—highly verbal, long-winded, and bolted to a server rack—completing sentence 97 of a 10,000-word report on the hiring landscape for AI engineers circa 2024 to 2025. It stares at the LinkedIn login screen, sweating, thinking… thinking… thinking… in circles. It can think, but, alas, it can’t do.

Operator streams in, equipped with the high personality and low IQ of a golden retriever, but also—miraculously—with hands. It comes up behind deep research, leans in close, and presses “Login.”

“Done!” says Operator with a twinkle.

The rest, as they say, is artificial history. (Reader, they interfaced.)

Their progeny, ChatGPT Agent, is like deep research in that it can do long-running research tasks. And it’s like Operator in that it can use a computer, including a browser, a terminal, and LibreOffice. So it can do a host of things that neither of its parents could do on their own:

Navigate complex multi-step workflows: Read all of your technical support emails, identify product promoters, search for them on LinkedIn, and synthesize customer archetypes

Transform raw business data into executive presentations: Analyze P&L spreadsheets and performance metrics, and generate PowerPoint decks with insights

Conduct comprehensive UX audits: Browse through multiple websites, document user flows, and compile detailed usability reports

Create intelligence briefings from real-time data: Scan news sites, research papers, and forums to produce daily executive summaries on specific topics

Handle authentication and dynamic content: Log into password-protected sites, navigate JavaScript-heavy pages, and extract data from behind paywalls

After a few days of using it, here’s my Vibe Check. We’ll go through how it works, the Reach Test (is it a habit?), and what it means for the competitive landscape. Let’s dive in.

AI that gets how you work

AI is better with context. Notion’s new AI tools take your stored notes and knowledge across apps to create exactly what you need, whether it’s the right document to share before a big meeting or a stroke of genius that unlocks a complex project pulled from a years-old email. Don’t start from scratch with a new AI tool.

Try it today

Want to sponsor Every? Click here.

A tour of ChatGPT Agent
We’ll start our tour of ChatGPT Agent with an example. Our email management product, Cora, has been growing quickly, and I wanted to understand more about the current state of the customer base. I wanted to know:

Why people love us (what the job to be done is)

Who loves us (customer archetype)

The biggest complaints

So I started a new ChatGPT chat and added “ChatGPT Agent” as a tool, similar to how you invoke deep research:

Then, I prompted ChatGPT Agent to read two months’ worth of support emails and feedback forum posts. I instructed it  to look at our support email account and all of the support forum posts, and asked it to tell me who uses the product, who loves it, and what the complaints are.

In about 15 minutes, it went through 1,300 emails and a ton of posts to create a 2,000-word report on our most common complaints.

It also found all of the people who love the product, searched for them on LinkedIn, and created a set of customer archetypes to help me understand who loves Cora and why:

Neither deep research nor Operator could do this on its own, but ChatGPT Agent can do it easily.

Here are a few more tasks I had it perform:

Find me a place I can spend a week as a writing retreat somewhere in the Berkshires or Upstate New York.

Given Every’s P&L and weekly performance tracker spreadsheets, do an in-depth analysis of our business, and compile the results into a PowerPoint presentation.

Review the UX of Every’s main websites (Every, Cora, Sparkle, Spiral) and present a detailed report on the findings.

Read the internet and create a daily executive briefing on the last 24 hours of AI news, specifically focusing on AI and games, alignment, and synthetic data.

It’s an impressive piece of technology, and unlike other frontier agent experiences like Claude Code, it’s not intimidating to use if you’re not a developer. You don’t have to open up a terminal, and it doesn’t run on your computer like Claude Code does. Instead, for each chat for which you invoke ChatGPT Agent, it starts a virtual machine in the cloud and runs everything right from inside of ChatGPT.

As always with a Vibe Check, here’s your Reach Test:

Do we reach for ChatGPT Agent? Not yet.
For most of my AI usage, o3 is more than enough bang for my buck. I don’t need to spin up an entire virtual machine with access to a browser and a command-line interface in order to ask questions like, “How should I word this email?”

For coding, Claude Code is my go-to, and ChatGPT Agent isn’t targeted at that market. OpenAI’s agent Codex is, though, and it follows the same set of trade-offs as ChatGPT Agent does: It works in the cloud in its own virtual machine for each request, so while it’s incredibly simple to use, it’s less customizable than Claude Code and therefore less powerful for complex requests.

For research tasks, I still use Claude Code—it’s a better power tool. But there are a few times a month I’d use ChatGPT Agent in its current state: doing a UX review of a product, or helping me find hotels for a trip, for example.

As always, OpenAI has packed an incredible amount of complex technology into a consumer-friendly package. But making it so consumer-friendly comes at the cost of customization and composability, which limits its power (for now.)

Because Claude Code runs as an application on my computer I can use it in a much more flexible way: It has immediate access to all of my files, and I can endlessly customize how it works. Because ChatGPT Agent lives inside of ChatGPT, it only works in the way that it was designed to work—so it’s useful, but not yet a daily use product.

As I wrote a few days ago, in an agentic world, a product that’s only used a few times a month can still be great. Because ChatGPT Agent is part of the larger ChatGPT ecosystem, even if I only reach for it a few times a month, those UX reviews and travel searches deliver enough unexpected value to earn its place.

Soon enough, I’m sure it will kick in proactively for the right tasks—so I won’t have to decide to use it at all.

The competitive landscape
The major AI labs promised that 2025 was going to be the year of agents—and they were telling the truth. From deep research, to Operator, to Claude Code, to ChatGPT Agent, AI tools have been running unassisted for longer periods on more complex tasks.

Now that we’re in an agent-driven world, there’s a war for agentic dominance. And the biggest strategic question in that war is: where in the tech stack do those agents live? On which layer will power accrue?

In December 2022 I wrote that I thought power would accrue on four layers:

The operating system

The browser

Models that are willing to return risky results to users

Copyright

Agents are now fighting for the browser layer, but they have different methods of attack.

With The Browser Company’s Dia and Perplexity’s Comet, AI is built into the browser itself. By contrast, OpenAI wants to abstract away the browser entirely: You just tell ChatGPT Agent what you want, and it handles using the browser (and the rest of the computer) for you.

Whoever wins gets to intermediate between users and the entire web.

Dan Shipper is the cofounder and CEO of Every, where he writes the Chain of Thought column and hosts the podcast AI & I. You can follow him on X at @danshipper and on LinkedIn, and Every on X at @every and on LinkedIn.

We build AI tools for readers like you. Automate repeat writing with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora.

We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.

Get paid for sharing Every with your friends. Join our referral program.

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

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
