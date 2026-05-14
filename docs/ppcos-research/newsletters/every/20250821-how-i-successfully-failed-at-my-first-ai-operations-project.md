# How I Successfully Failed at My First AI Operations Project

**From:** Every <hello@every.to>
**Date:** 2025-08-21T15:01:14.000Z
**Folder:** every

---

How I Successfully Failed at My First AI Operations Project

Sometimes the best AI solution is the one you don't build yourself

Working Overtime

How I Successfully Failed at My First AI Operations Project

Sometimes the best AI solution is the one you don't build yourself

by Katie Parrott

Midjourney/Every illustration.

Was this newsletter forwarded to you? Sign up to get it in your inbox.

Minutes into our weekly AI editorial operations call, I shared my screen and held my breath.

The AI editing application I’d been building for weeks—the one I’d promised was ready, not once, but twice—errored out.

I clicked “Analyze” again. More errors. One more time. Errors again.

This was the last chance for my first official project as Every’s AI editorial ops lead. I’d been at this for weeks—tinkering with prompts, debugging code, and migrating from platform to platform like a Dickensian orphan looking for a meal—only to watch our team struggle more with the system I’d built than they would have with editing the piece themselves. Either the AI editor worked today and we rolled it out, or we would cut our losses and move the whole thing into Claude Teams—shared Claude workspaces where everyone inside the organization can access the same projects.

I kept the Zoom patter going while I willed the system to load the beautifully formatted high-resolution editorial feedback that had been there when I’d tested it half an hour earlier. The output—what should have been a detailed analysis of an essay draft measured against Every’s editorial principles and best practices—stubbornly refused to appear. When I stopped talking, the silence told me what I already knew.

Just an hour after it was working fine, my Every AI Editor app refuses to cooperate. (All images courtesy of the author.)

By the time the call ended, I was finally ready to admit what everyone else could see: I was solving the wrong problem. We needed a solution that worked reliably, every time, without me playing whack-a-mole with bugs that multiply faster than I can squash them. My failed demo taught me to let go of the builder's impulse long enough to see the solution waiting in someone else's infrastructure. Six weeks of debugging taught me what we needed. More importantly, it taught me what we didn't.

Make email your superpower

Not all emails are created equal—so why does our inbox treat them all the same? Cora is the most human way to email, turning your inbox into a story so you can focus on what matters and getting stuff done instead of on managing your inbox. Cora drafts responses to emails you need to respond to and briefs the rest.

Try Cora today

Want to sponsor Every? Click here.

Why Every needs an AI editor
When I started in the AI operations role at Every this past June, I knew right away what I wanted to build first: an AI‑powered editor. One of our guiding principles for automation at Every is "Don't repeat yourself." If you notice yourself making the same edits over and over, that's your cue to call in AI for help.

And there are plenty of edits we make again and again. Where's the lead? Is it at the top where it belongs, or buried in paragraph five? Do the headline, subheading, and introduction work together to draw readers in? Are the stakes clear? Is the writer's credibility established? These aren't small notes—they're the core of how Every thinks about good writing. Because they repeat across every draft, they're exactly the kind of work an AI assistant can excel at: Surface patterns, enforce standards, and leave the final creative judgment to humans.

The goal is to cut down on the revision cycles our writers and editors go through to get a piece publication-ready. Every publishes daily with a small team. Many of the team members who write have jobs that are not writing, and many of them aren’t professional writers, so editing cycles are easily our biggest bottleneck. Writers average 3-4 revision rounds per piece, with each round taking 2-3 days—meaning a single essay often takes two weeks from draft to publication.

I'd built a system for my own pieces that worked beautifully. Each week, the Every editorial team talks through how the week’s pieces could have been stronger—buried leads, abstract language, missing stakes. I combined those patterns with Every's style guide, examples of our best-performing pieces, and a taxonomy of common issues we see in drafts. All of that went into a Claude project—a dedicated workspace where you can store documents, instructions, and context that carry over across every chat you initiate inside of it.

With all of that context, plus every piece I’ve written for my own column, uploaded to the project’s “knowledge,” the project behaved like an editorial assistant built just for me.

Whenever I wrote a piece, I'd run it through this editor first. It caught the stuff I was blind to—my tendency to hedge statements with “maybe” or “just,” my weakness for correlative conjunctions (those “not X, but Y” constructions that AI loves so much), the way I'd forget to insert a “so what” early in the piece. I thought I could package up this system and hand it to other writers like a gift.

I was, to be kind to my former self, naive.

There's an entire constellation of considerations in making AI useful in an organization that have very little to do with vibe coding jam sessions. There’s education—how do you inform the team about an available solution, and how to use it? There's reliability—it has to work every time, not just when you're there to debug it. And there's change management—convincing writers to paste their precious drafts into yet another tool when they're already juggling five different platforms.

It doesn’t matter if I find my creations useful. What matters is whether other people can use it, want to use it, and get value from it when they do. That's a completely different bar—one that, as we’re about to see, was alternately tricky and incredibly simple to clear.

There and back again: A builder’s tale
What came next felt like being trapped in an escape room made up of errors, maintenance nightmares, and confused co-workers. Here it is, a tragedy in five parts:

Part 1: Individual Claude projects. I started with what I already had—a Claude project I'd set up for myself that knew my editing style. It worked for me, but it buckled under the weight of logistics the moment I tried to scale it. Week one, I was sending instructions on how to set up the project to 10 different people; the next week I’d made so many changes to the custom instructions and project knowledge documents that everyone’s projects were out of date. Brandon Gell, the head of Every Studio and our consulting practice, said what needed to be said: Individual projects for every user made no sense. It was way too much for each person to maintain. We needed a single source of truth, and a single interface everyone could trust.

Brandon Gell delivering the hard truths every builder needs to hear.

Part 2: The Artifact approach. It was Every CEO Dan Shipper who suggested we try Claude Artifacts—shareable AI-generated mini-apps built directly inside Claude. Building an artifact is very much like vibe coding—in fact, I recommend it as a toe-dip in the pool for the vibe coding-curious. The interface it spun up was clean: Paste draft, click “Analyze,” get report. But an Every-wide editor needs to hold a ton of context—our entire style guide, voice examples, and the positive and negative patterns that teach taste. The Artifact couldn't hold that much in “mind” at once. It broke. And broke again.

The Claude Artifact version of the editor in development mode. The chat is on the left, the tool the prompting produced on the right.

Part 3: Vibe coded app. I swore I wouldn't do this—too complicated, and too dependent on a skill set I’d describe more as “enthusiast” than “engineer.” But the siren song of a fully customized solution that would behave exactly as I wanted it to pulled me in, and I did it—I vibe coded. Lovable, my AI-powered app builder of choice, gave me a beautiful interface in minutes—big text field, clean report, proper buttons. But I couldn't control the output format or fix the analysis logic. The feedback would come back as a wall of text instead of organized sections, or the AI would flag things as problems that weren't while missing obvious issues, like the fact that we use sentence case for subheadings. The tool was unreliable, which meant our writers couldn't trust it, which meant they wouldn't use it.

The vibe coded version of the AI editor. Theoretically more functional than the artifact, but way more temperamental in its behavior.

Part 4: "Real" code. I decided to go full developer: Claude Code to build, Railway to run the backend, Vercel to host the frontend—the whole shebang. After a few hiccups and a late-night intervention from an engineer, I managed to pull together a passable version to present by Every’s surprise Demo Day that concluded our Think Week retreat. I had authentication, error handling, and a deployed app. I announced we were ready to roll out. It immediately failed.

What the app looks like when it’s working.

The issue: The app was intricate and, for that reason, fragile. Every piece of the system could break without warning. The feedback delivery was slow, or the output would suddenly stop formatting correctly (if it managed to load at all). I’d push a fix, and the whole thing would deploy successfully but secretly forget how to work. I was accumulating technical debt at a rate that would make an actual software engineer weep.

Part 5: Projects, part deux. I had a come-to-Jesus talk with Dan and Every editor in chief Kate Lee. If the system was so finicky and difficult to, first, get working and, second, maintain, then it wasn’t worth it. The next day, after yet another failure in our AI editorial operations meeting, I made the call. Shareable Claude Projects for teams had just dropped, rendering our logistical headache of every individual user managing their own version of the project instructions a thing of the past.

We could have our single source of truth and make reliability Anthropic’s problem. I set up the project, added the custom instructions and context documents that would teach the project how to behave, set it to “public,” and we were in business.

The Claude Projects version of the editor. Same quality feedback at a fraction of the maintenance costs.

When not to build
We finally have an Every AI editor that works. It's not the sexy, standalone vibe coded solution of my dreams. But it is a tool that people can use and count on.

The workflow is simple: If you're on the Every Claude team, you open the shared project, paste your draft with headline and subheading options, and hit “Enter.” There are no special prompts required. Just paste and wait.

It returns a comprehensive editorial report. Each fix comes with a specific location and suggested rewrites. Each edit is a choice the writer makes, not a change that happens automatically. The AI surfaces issues. The writer decides what to do about them.

We didn't need a custom UI or authentication, or to maintain infrastructure. But when I took this role, I thought that I would succeed in AI operations by scaling the systems I'd built for myself. Now I understand it differently. AI ops means recognizing what needs to be built versus what already exists. It's knowing when a Claude project beats a custom app, and when good-enough beats perfect.

The code was never the asset. The asset is our editorial standards, expressed clearly enough that a model could enforce them. Once I understood that, the answer became obvious. The rest was in the prompts.

Coming soon: I'll walk you through exactly how we built the Every AI editor that works—the prompts, the setup, and the editorial principles that make it useful. Stay tuned.

Katie Parrott is a writer, editor, and content marketer focused on the intersection of technology, work, and culture. You can read more of her work in her newsletter.

To read more essays like this, subscribe to Every, and follow us on X at @every and on LinkedIn.

We build AI tools for readers like you. Write brilliantly with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora.

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
