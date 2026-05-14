# 🎧 He’s Building the Plumbing For AI to Use the Internet

**From:** Every <hello@every.to>
**Date:** 2025-10-01T15:13:09.000Z
**Folder:** every

---

🎧 He’s Building the Plumbing For AI to Use the Internet

Stainless founder Alex Rattray on MCP, a protocol giving LLMs the tools they need to do real work

AI & I

He’s Building the Plumbing For AI to Use the Internet

Stainless founder Alex Rattray on MCP, a protocol giving LLMs the tools they need to do real work

by Rhea Purohit

Every illustration/'AI & I.'

TL;DR: Today we’re releasing a new episode of our podcast AI & I. Dan Shipper sits down with Alex Rattray, the founder of Stainless, a startup building a platform for high-quality APIs. Watch on X or YouTube, or listen on Spotify or Apple Podcasts. Here’s a link to the episode transcript.

Was this newsletter forwarded to you? Sign up to get it in your inbox.

When you send an email, pay with a credit card, or casually log into X, countless invisible handshakes are taking place behind the scenes. It’s the grand plumbing of the internet that nobody talks about: Programs talk to each other, data moves across services, and to most of us it seems like everything just works.

Those handshakes are powered by APIs, and Alex Rattray has built a company, Stainless, to make them better.

Up to now, that plumbing has only connected humans and computers, but with LLMs becoming active participants in this ecosystem, a new kind of pipe is becoming necessary: model context protocol, or MCP. If APIs are how programs talk to each other, “MCP servers” are how AI can plug into those same systems—they give a language model tools to get work done. (In the case of sending an email, the MCP server would let the LLM search your inbox, draft a reply, and send it on your behalf.) On this episode of AI & I, Rattray joins Dan Shipper to talk about why MCP servers don’t yet work as well as they should, what he’s learning about designing reliable ones, and how Stainless is experimenting with using them inside the company.

You can check out their full conversation here:

If you want a quick summary, here are some of the themes they touch on:

The hidden wiring of the internet
Rattray sees APIs as critical to the internet’s connectivity in the same way that our brains’ neurons need branching structures called dendrites to send the signals that allow us to think. “APIs are at the heart and center of [modern software], just like dendrites are the center of the mesh of the brain and how we think,” he says.

Until now, humans interacted with computers through user interfaces (clicking through a website to buy a pair of new shoes), and computers interacted with each other through APIs (Stripe talking to your bank while processing a payment). LLMs created a need for a new kind of interface. That’s where MCP comes in. Just as a website presents buttons for humans to click on, MCP presents a set of tools for an LLM to use. An MCP server for Gmail, for instance, might include tools like “send mail,” “compose mail,” or “read inbox.” Instead of a person logging into Gmail to perform those actions, the MCP is a native interface for language models.

Why teaching LLMs to use software is tricky
The first product Stainless built was a set of software development kits, or SDKs. APIs are the raw wiring that lets programs talk to each other; an SDK is the polished interface that makes that wiring easy to use. Take Stripe as an example: Technically, you can send data back and forth with Stripe by hand, formatting your own requests one by one and shipping them over HTTP, or Hypertext Transfer Protocol (the system that governs how information is sent and received across the net). But most developers would rather not spend their time wrangling raw requests. Instead, they install the Stripe SDK, which lets them write something as simple as “stripe.customers.create” in their code. With one line, a new customer appears in their database. Behind the scenes, the SDK translates that one line into a properly formatted API request, sends it to Stripe’s servers, and returns the result.

You can think of it as the difference between soldering wires yourself and plugging a cable into a finished port.

But so far, no one has cracked how to make MCP servers as easy for language models to use. “[I]t took a long time for humanity to get to the point where we could make a really good Python SDK for a Python developer wrapping an API… we haven’t figured out how to expose an API ergonomically to an LLM,” Rattray says. The reason for this, he explains, is that it’s easier to understand how a Python developer thinks than it is to get into the brain of an LLM.

Design principles for smarter, usable MCP servers
To make MCP servers more usable, Rattray says Stainless has learned a few design rules. The first is to keep the number of “tools” small. In this context, a tool is just an action the AI can take—like “refund a customer” or “send an email.” If you give the model too many options, it gets confused. The tools also need clear names and descriptions so the AI knows when to use them.

Another rule: Don’t overload a tool with too many blanks to fill in. If you’re building a refund tool, for example, the model might only need a customer name and an order number—not a dozen other fields it won’t know what to do with. The same principle applies to outputs, or what comes back once the tool has run. The refund tool, for instance, might only need to return the refund amount and a confirmation number, not the entire transaction history. To keep responses tidy, Stainless often runs them through a JSON filter, which is essentially a way of stripping out the clutter so only the relevant details remain.

How Stainless uses MCP—and AI—to run its business
At Stainless, Rattray has built MCP servers for tools like Notion and HubSpot, so he can ask a question such as: Which interesting customers signed up last week? From there, the system queries the database, cross-references the results in HubSpot, pulls notes from Notion, and delivers a tidy summary. It’s not flawless yet—Rattray admits there are still plenty of “paper cuts,” the kind of minor frustrations you expect from technology that’s so new. But it speeds up a process that would normally take a person several logins and searches to complete.

Beyond MCP, Rattray has also built what amounts to a shared company brain. He keeps Claude Code running and, whenever something useful comes in—new feedback from a customer, a SQL query he’s refined for board prep, a piece of analysis—he simply asks the AI to save it in Github. Over time, this creates a curated archive of knowledge that Rattray and his team can ask questions to directly.

What do you use AI for? Have you found any interesting or surprising use cases? We want to hear from you—and we might even interview you.

Here’s a link to the episode transcript.

Timestamps

Introduction: 00:01:14

Why Alex likes running barefoot: 00:02:54

APIs and MCP, the connectors of the new internet: 00:05:09

Why MCP servers are hard to get right: 00:10:53

Design principles for reliable MCP servers: 00:20:07

Scaling MCP servers for large APIs: 00:23:50

Using MCP for business ops at Stainless: 00:25:14

Building a company brain with Claude Code: 00:28:12

Where MCP goes from here: 00:33:59

Alex’s take on the security model for MCP: 00:41:10

You can check out the episode on X, Spotify, Apple Podcasts, or YouTube. Links are below:

Watch on X

Watch on YouTube

Listen on Spotify (make sure to follow to help us rank!)

Listen on Apple Podcasts

Miss an episode? Catch up on Dan’s recent conversations with founding executive editor of Wired Kevin Kelly, star podcaster Dwarkesh Patel, LinkedIn cofounder Reid Hoffman, ChatPRD founder Claire Vo, economist Tyler Cowen, writer and entrepreneur David Perell, founder and newsletter operator Ben Tossell, and others, and learn how they use AI to think, create, and relate.

If you’re enjoying the podcast, here are a few things I recommend:

Subscribe to Every

Follow Dan on X

Subscribe to Every’s YouTube channel

Rhea Purohit is a contributing writer for Every focused on research-driven storytelling in tech. You can follow her on X at @RheaPurohit1 and on LinkedIn, and Every on X at @every and on LinkedIn.

We build AI tools for readers like you. Write brilliantly with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora. Dictate effortlessly with Monologue.

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

Monologue: Effortless voice dictation for your Mac

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
