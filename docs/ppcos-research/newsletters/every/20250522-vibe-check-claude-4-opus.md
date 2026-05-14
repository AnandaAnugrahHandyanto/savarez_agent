# Vibe Check: Claude 4 Opus

**From:** Every <hello@every.to>
**Date:** 2025-05-22T16:53:19.000Z
**Folder:** every

---

Vibe Check: Claude 4 Opus

Anthropic’s new model crushes pull requests, research deep dives, and honest editing—yet o3 keeps the daily-driver crown

Chain of Thought

Vibe Check: Claude 4 Opus

Anthropic’s new model crushes pull requests, research deep dives, and honest editing—yet o3 keeps the daily-driver crown

by Dan Shipper

GPT-4o image generation/Every illustration.

Was this newsletter forwarded to you? Sign up to get it in your inbox.This week has been a doozy: I went to Microsoft Build and interviewed the company's CTO Kevin Scott, we announced our fundraise in the New York Times, Google held its I/O event (more on that from Alex Duffy tomorrow), OpenAI acqui-hired Apple designer Jony Ive, and today I’m at Anthropic’s Code With Claude event. Let me state for the record: I am tired of all of this progress. My fingers feel like they are about to fall off, and my brain is functioning at a comparable intelligence to GPT-2. But there’s a new Claude model launching today, for which I had to uphold my promise of writing day-o, hands-on vibe checks. So here it is for the long-awaited Claude 4 Opus (which Anthropic had code-named Linen), the follow-up model to Claude 3.7 Sonnet. (Besides, who needs fingers when voice-to-text AI is this good?)I tried Opus on a variety of tasks, from coding to writing to researching. My verdict: Anthropic cooked with this one. In fact, it does some things that no model I’ve ever tried has been able to do, including OpenAI’s o3 and Google’s Gemini 2.5 Pro. Let’s get into benchmarks. We’ll start, as always, with the Reach Test. The Reach Test: Do we reach for Opus over other models?
For day-to-day tasks: no
I’m still an o3 boi. I think this has a lot to do with ChatGPT’s memory—it’s an incredibly sticky feature. Opus would have to be a lot smarter and faster to make the trade-off worth it. For coding: yes
It’s a beast in Claude Code, Anthropic’s command line interface for programmers. If you assign it a task, it will code for long periods of time on its own with no intervention. It one-shotted a few complex pull requests better than OpenAI’s coding tool Codex. For example, I asked it to implement an infinite scroll feature in Cora, our AI email assistant—i.e., to keep scrolling to see your next unread email summary. It made a good infinite scroll experience. We couldn’t ship it as it was, but it was close.

Speed meets cinema-quality
The latest version of LTX Video launches today and it’s LTX Studio’s most advanced video-generation model yet.Why LTXV is a game-changer:Renders up to 30× faster than competitors while maintaining true cinematic quality
Revolutionary multiscale rendering builds clips from coarse to fine for sharp, high-resolution results
Runs entirely on your own hardware or via LTX Studio
100% open-source on GitHub and Hugging Face under OpenRAIL

This is quality creative control at your fingertips. Experience this 13-billion parameter difference starting today.Check out LTXV here
Want to sponsor Every? Click here.

Anthropic seems to have solved Claude 3.7 Sonnet’s famously overeager personality, too. No longer does the model try to build the Taj Mahal when you ask it to change a button color.Kieran Klaassen—Cora general manager, resident Rails expert, and opinionated agent-ophile—is also loving it, and he’s a tough sell. Advantage Claude. For writing and editing, yes and no
o3 is still a significantly better writer. But Opus is a great editor because it can do something no other model can: It edits honestly—no rubber-stamping. One of the biggest problems with current AI models is they tell you your writing is good when it is obviously bad (ask me how I know). Earlier versions of Claude, when asked to edit a piece of writing, would return a B+ on the first response. If you edited the piece at all, you’d get upgraded to an A-. A third turn got you to an A. As much as I wish my physics teacher graded me like this in high school, it’s not how I want my AI models to work. I want R. Lee Ermey with a thesaurus and a red pen. ChatGPT’s version of R. Lee Ermey in the 1987 movie Full Metal Jacket. Source: ChatGPT-4o image generation/Dan Shipper.To my delight, Opus is a good judge of writing. To test it, I worked with Spiral general manager Danny Aziz, our resident expert on teaching LLMs to write. We gave it a set of writing principles that attempt to outline what good writing is. For example, good writing elicits genuine emotional and intellectual investment from the reader, and avoids predictable patterns and cliches.We fed it both interesting and boring writing (the latter was probably mine), and it nailed which pieces were boring and why:   Source: Opus/Dan Shipper.Not only does Opus not glaze you, it can keep multiple principles in mind at once even when they’re hidden in the middle of long prompts with lots of context. Other models often narrow in on one principle to the exclusion of the others (ask Sam Bankman-Fried if you want to know how well that works out). Danny found that “other reasoning (3.7, o3, and o4-mini) models tend to lose sight of their writing principles when they’re dealing with lots of context, like a lot of source material or a long chat. Opus (with reasoning) does a great job of continually reminding itself what it needs to do so the principles don’t get lost.”Opus can also notice subtle patterns across large blocks of text. which is useful if you, like me, are writing a book. I fed it 50,000 words of a book I’m writing and asked it to find themes and patterns that I hadn’t written about yet. Could it tell me what I’m trying to say better than I can? The answer is yes. It found a few ideas about my parents’ divorce and my relationship to work that run throughout the book. While I knew this already, in an unspoken way, Opus put its finger on it.Source: Opus/Dan Shipper.For longer research tasks: yes
Opus isn’t a daily driver for research yet, but when o3 doesn’t have enough thinking power, it’s really good: It has a powerful deep research implementation, called simply Research. It seems to be able to kick off multiple research agents in parallel for each query, which lets it do more research than OpenAI’s. Instead of one agent exploring the sum total of human knowledge in response to a prompt, like OpenAI’s tool does, Opus seems to spawn a swarm of them that fan out in different directions. A master agent synthesizes and summarizes what they collectively find.For funsies, I asked it to research me and predict my career trajectory. It gathered a whopping 645 sources. I almost feel bad for it:Opus scours the web for signs of my future career path. Source: Opus/Dan Shipper.According to Opus, in five years I’ll have built Every into a $50-$100 million incubator disguised as a media company: Source: Opus/Dan Shipper.I’m not saying that Opus is smart enough that it can accurately predict my future, but I’m not not saying that either.Combine how much time it spends researching with how well it can handle long context, and it’s a powerful backup to regular OpenAI’s deep research that yields different and sometimes better results. Next benchmark: vibe coding a game. Kieran’s cozy ecosystem benchmark
Cora GM Kieran invented what I have dubbed the “cozy ecosystem” benchmark. He asks the model to one-shot a 3D weather game—sort of like RollerCoaster Tycoon but for managing a natural ecosystem. It measures how good the model is at the full spectrum of game creation tasks: coding, designing, planning, and iterating. Sonnet 3.7 was not able to complete this task in any way. By contrast, Opus had no problem with it: The ‘cozy ecosystem’ game built by Opus. Source: Opus/Kieran Klaassen.It took us a few turns to get Opus to make the game three dimensional—earlier turns were all two dimensional. But it didn’t run into any major errors and made something playable in about 15 minutes. Aidan McLaughlin’s thup benchmark
Aidan McLaughlin, a member of the technical staff at OpenAI, invented a benchmark where you repeatedly input “thup” until the model goes psychotic. The exact way in which it does so tells you a lot about the structure of its mind: Some models output gibberish, some start writing whimsical, poetic non-sequiturs, and some just get flustered:Source: Aidan McLaughlin/X.After 23 “thups,” I couldn’t get Opus to go psychotic, but it did get flustered. It kept politely reminding me that it was here to help despite my repeated “thups”:Source: Opus/Dan Shipper.I’ll admit, after 23 “thups”, I was feeling a little psychotic myself. What does it say about me that I broke before Claude? Could it be AGI? Dwarkesh Patel’s new knowledge benchmark
Dwarkesh Patel keeps asking, “Why haven’t LLMs discovered anything new?” despite the fact that they know so much about the world. So I tried to see if Opus could discover something new. First, I asked it to tell me how to make LLMs 100,000 times smarter:Source: Opus/Dan Shipper.In response, it invented the “Sparse Neuro-Symbolic Cascade” method for making LLMs smarter, which more closely mimics the way human brains work (among a few other things.) I thought it was plausible, but it’s way outside of my expertise to judge beyond that. Let’s check back in five years. Opus also gave me a few whimsical facts. For example, it told me that every moment of silence is acoustically unique in the history of the universe:Source: Opus/Dan Shipper.It also told me that the universe has a hidden “resonance memory”: Every event creates a series of infinite ripples that manifest as the natural laws of physics.Source: Opus/Dan Shipper.Imagine benchmark
My favorite way to test new frontier models is to ask them to imagine wild new scenarios. I always ask: Imagine an advanced alien civilization that never invented or encountered the number two. Why didn’t they invent it? What do they do instead?Opus returned approximately the same output as GPT-4.5, explaining that the aliens had a more fluid kind of intelligence that didn’t use discrete numbers. I thought it was interesting but not novel:Source: Opus/Dan Shipper.Next I asked it to imagine an alien species whose brains are naturally at rest in the state that Buddhists refer to as enlightenment. I wanted to see if it could tell me how they arose biologically, and what their psychology and culture is like.It invented a civilization called the Satori that evolved on a planet with “extreme temporal flux” (apparently time “moves in eddies and currents”) that selected for flexibility:Source: Opus/Dan Shipper.The model race is now a product race
Claude 4 Opus is a great model. We’ll use it starting today for a few of our products like Spiral, particularly for its ability to edit. I’ll also use it for coding, and long, complex research tasks.But I’m noticing that my desire to completely flip all of my usage to a new, more powerful model is lower than it was six months ago. Models—especially consumer-facing ones—are stickier than they used to be. We’re entering a different era of the AI race in which model performance is good enough for enough tasks that the user interface layer is becoming more important, and there are only a few seats for non-incumbent model providers. I’m rooting for Anthropic. If it can successfully make Claude Code the default tool for programming with AI, it’ll claim one. For consumer use cases, though, increased model power alone isn’t going to make as much of a difference anymore—memory is now table stakes. Anthropic will have to keep pushing hard to improve its product to get me to switch back from ChatGPT.Dan Shipper is the cofounder and CEO of Every, where he writes the Chain of Thought column and hosts the podcast AI & I. You can follow him on X at @danshipper and on LinkedIn, and Every on X at @every and on LinkedIn.We build AI tools for readers like you. Automate repeat writing with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora.We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.Get paid for sharing Every with your friends. Join our referral program.Subscribe
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
