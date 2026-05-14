# The Three Ways I Work With LLMs

**From:** Every <hello@every.to>
**Date:** 2025-06-03T17:31:07.000Z
**Folder:** every

---

The Three Ways I Work With LLMs

Your AI workflow should change with your problem. Here's how I do it.

Source Code

The Three Ways I Work With LLMs

Your AI workflow should change with your problem. Here's how I do it.

by Kieran Klaassen

GPT-4o/Every illustration.

I spent three hours on X last week watching prompt gurus peddle their latest silver bullets: "This one ChatGPT prompt will replace your entire engineering team." "Claude with this secret system prompt outperforms every developer." "My $497 prompt library will make you a 10x coder." Meanwhile, I shipped five features for Cora, our AI-powered email assistant, using models from all three providers—Anthropic, Google, and OpenAI— and zero magic prompts. I didn't find one perfect prompt or tool to do all of my work. In fact, I stopped looking for one. Instead, I used different tools based on what I was trying to do.This approach has changed how I ship code. I set the goal and define the rules, and then 100 percent of my pull requests are opened by AI tools like Claude Code. Every research task runs through ChatGPT and Claude. AI handles 30 percent of my code reviews and debugs half of the bugs I encounter. What used to take me a full week of coding now happens in hours.The contradiction isn't lost on me: I’m criticizing one-size-fits-all AI solutions while building an AI-powered product myself. But Cora doesn't promise to do all your email work—it helps you spend less time on the parts that don't matter. My work with AI follows the same principle: Clear away the mechanical coding tasks to focus on what requires actual thought.After years of building with LLMs—most recently the systems that let Cora triage emails by importance and draft replies intelligently—I've distilled my coding approach to three core patterns, each optimized for a different kind of cognitive load. These three workflows got me from grumbling about AI gurus on X to shipping features before lunch.

Make email your superpowerNot all emails are created equal—so why does our inbox treat them all the same? Cora is the most human way to email, turning your inbox into a story so you can focus on what matters and getting stuff done instead of on managing your inbox. Cora drafts responses to emails you need to respond to and briefs the rest. Try Cora today
Want to sponsor Every? Click here.

Everyday coding with Windsurf and Cursor: The flow state companion
When I'm in that programmer's groove—I’m clear on what needs building and ready to just code—I reach for Windsurf and Cursor paired with thinking models like Claude Sonnet 4 or Gemini 2.5 Pro. This setup works for:Building incrementally on existing code

Solving well-understood problems

Maintaining focus and flow while coding

What makes this workflow special is its lightweight, responsive nature. I speak coding instructions in plain English—"add a function to validate email addresses"—and the AI translates them into code. The AI editor doesn't break my concentration; it reduces the friction between my intention and implementation. In this setup, I am the thinker, and the AI is purely the executor. I drive all the decisions, while the AI handles the mechanical aspects of coding. I maintain complete control of the architectural and design choices.Here’s an example: I needed to add a new filter option to Cora, similar to the "all emails" view but to show just important messages. It’s trivial work—I could have done this manually in 20 minutes. But that’s 20 minutes that I wanted to spend shaping the next feature. Instead, I stayed in my editor, described what I wanted in natural language—show only the important emails, write the query efficiently, check for indexes, and make sure it plugged into the existing context cleanly—and watched the AI implement it across the codebase. Twenty minutes of coding, or two minutes of talking to my editor—the math is obvious.Cursor builds an ‘Important’ inbox for me—proof it can handle routine coding chores. Source: The author.This might sound like vibe coding on the surface, but there’s an important distinction in terms of intention. Vibe coding works from the outside in: You tell the AI what you want the software to do and let it figure out how to get there. My approach is inside-out: I already know both the destination and the route. I've decided on the architecture, the patterns, and the specific implementation details. I'm just delegating the mechanical act of translating those decisions into syntax. The AI is my hands, not my brain.The key advantage is speed without sacrificing quality or accuracy. I speak, and the AI translates my intentions into code. It feels like pair programming with a skilled partner who never gets tired.This mode works best when the stakes are low and the direction is clear. I'm not relying on the AI for big architectural decisions—I'm using it to implement solutions I could code myself but prefer to delegate.I reach for this workflow when:I know exactly what “done” looks like.

I'm working on a single, focused task.

I need to build efficiently without breaking flow.

This is the mode I default to when I'm already mid-sprint or almost done and just need to keep moving.Big-picture thinking with search and reasoning models: The architect's approach
When facing a blank canvas—starting a project from scratch, designing a new system architecture, or untangling complex legacy code—I need a different approach. This is where my research-focused workflow for discovery and exploration comes in, using:ChatGPT with o3 and tools

RepoPrompt or Claude Code agentic search (a tool that gives AI the full picture of your codebase instead of working blindly)

Multiple models in parallel (Claude 4 Opus, Gemini 2.5 Pro, o3)

Unlike everyday coding where I direct every detail, here I embrace the AI as a true thought partner. I start with an open mind and deliberately avoid pushing too hard in any direction. The goal is to be surprised—to discover approaches and solutions I wouldn't have considered on my own.Recently, we were trying to work out how to make our marketing website live at the same address as Cora's app so visitors could seamlessly move between them. I had no idea where to start. Should we add one “front-door” server that forwards traffic (a reverse proxy), run lightweight code through data centers closer to visitors’ location (use edge functions), or just tweak our web-address settings to point people where they need to go (DNS)?I fed the problem to three different models without prescribing a solution: "We need our marketing site at cora.computer while keeping the app also at the root domain. What are my options?"ChatGPT lines up hosting options—showing AI’s value for brainstorming big-picture choices. Source: The author.Each model gave me slightly different takes on the same core approaches, but each framed the solutions differently. ChatGPT organized its output by how hard each option would be to build. Claude focused on which solution would run the fastest. Gemini worried about what might break our existing setup.The solutions offered just enough distinction to give me options, which, when you’re coding this way, is what you want. As I explored, my questions got more specific: "Show me how Cloudflare Workers handles authentication passthrough," or "What's the latency impact of a worker for this use case?" The conversation evolved from "What are my options?" to "Which solution is optimal for our specific constraints?"This workflow centers on discovery and exploration. I use these tools to research APIs, best practices, and architectural patterns—time-tested plans that lay out which pieces go where and how they connect. By running the same prompts across multiple models, I can compare their suggestions, identify blind spots, and synthesize a more comprehensive approach.What I'm really doing is finding and understanding what I'm trying to build before I know how to build it. I’m trying to define the problem space itself.I treat these responses as rough drafts, putting the best ideas together, cutting any repetition, and reshaping the collective output into a cohesive plan. When I start to see the shape of an idea emerge, my process changes. I shift into refinement mode, going into more detail while simultaneously trimming the edges, simplifying, and distilling until I reach the core of the solution. This narrowing process is crucial—start wide, then gradually focus until you have something precise and actionable.Here’s an example: I wanted to turn a loose idea for a feature into a concrete plan, so I asked ChatGPT to create an implementation plan or product requirements document (PRD). Seconds later, the right-hand pane filled with a ready-to-edit document—purpose, background, goals, and next steps—while our brief chat sat on the left for follow-up tweaks. One prompt, and the plan was already 80 percent done.ChatGPT turns scattered notes into a tidy plan—illustrating AI’s knack for shaping an action list. Source: The author.When I'm satisfied with the direction, I turn this research into a detailed implementation plan or PRD that I can execute using my everyday coding workflow.The key difference with this approach is that you want to give the AI loose reins initially. Unlike the everyday coding workflow, where specificity matters, this approach benefits from ambiguity at first. Let the models surprise you with directions you hadn't considered, then gradually refine and narrow as the plan takes shape.I reach for this workflow when: I'm not sure what “done” looks like yet.

The components are tightly interwoven and need each other to work.

I need to think and explore before I build.

This is what I reach for when the problem feels too big to hold in my head. Parallel progress with Claude Code, Devin, or Cursor agents: The CTO's method
My most experimental (and exciting) workflow involves working on multiple features simultaneously, much like a CTO overseeing several engineering teams. I'm convinced this represents the future of software development, though it's currently the hardest approach to master because it’s new. It’s experimental.There aren’t any established best practices yet, because we haven’t had time yet to find them. Here’s when the CTO method makes sense:You have multiple components that are not dependent on each other to build.

Each component has clear boundaries and specifications.

You've already done the architectural thinking up front.

I start by breaking down my day into discrete tasks, creating detailed specifications for each, and then delegating them to separate AI agents—either using Devin (which creates full pull requests), Claude Code with git worktrees, OpenAI’s Codex, or Cursor Background Agents working on different parts of the codebase.Think of it like having five to 10 skilled engineers all working simultaneously on different features, with you providing direction and reviews. The potential productivity gains are enormous—what might take a week sequentially can be compressed into a day of parallel work.Here's what this looks like in practice: After completing the research phase for several Cora features, I had clear specs for five independent features or fixes that needed building. I kicked off multiple background agents simultaneously: One agent fixed a bug with our morning Brief delivery timing. Another improved how we evaluate email categorization accuracy. A third upgraded our system to use a newer AI model. Each had its own git worktree, context, and focused mission. The workflow becomes iterative: I launch multiple development streams, then rotate through them, reviewing progress, providing feedback, and moving on to the next while the agents implement my suggestions. Claude Code finished a feature that emails people who have churned from Cora to ask for feedback—and it's creating a pull request to be reviewed at the same time. Source: The author.This approach requires wearing two hats, drawing on skills you likely already have or have observed:First, you need product manager abilities—breaking down complex features into clear, actionable specifications with well-defined boundaries. You need to be skilled at scope definition, prioritization, and communicating requirements precisely. If you've ever written a user story or created a product spec, you already have the foundation.Second, you need tech lead skills—reviewing code efficiently, spotting architectural issues quickly, and providing clear technical direction. The ability to context-switch between codebases while maintaining a coherent vision is crucial.While this parallel approach running multiple agents is the fastest mode when conditions are right, it's also the most demanding in terms of project management skill and focus. Context switching becomes your main challenge, and you need a strong structure to prevent distraction. Source: X/Dan Shipper.What makes this kind of parallel progress so exciting—and challenging—is that our tools and brains aren't fully optimized for this workflow yet. We're in the early days of figuring out how to manage multiple AI development streams efficiently. The cognitive load is substantial, but the productivity ceiling is dramatically higher than with any other approach.Traditional software development has always been limited by sequential processes. Even with human teams, dependencies create bottlenecks. With AI agents, we can break this pattern—running multiple development streams in parallel without the coordination overhead of human teams. When mastered, this workflow could represent a 5-10-times productivity multiplier for a single developer.This approach works best when:I know what “done” looks like for multiple independent tasks.

The pieces have clear boundaries and won't interfere with each other.

I need to coordinate multiple streams of work.

It’s the fastest mode—but only when the work is well-scoped.Creating space for human creativity
The goal of working with LLMs isn't to automate thinking; it's to clear space for deeper thinking. When I match my workflow to the shape of the problem, I move faster—in increments of hours rather than days—get unstuck more easily, and ship better work. The only real blockers now are fatigue, distraction, or lack of inspiration—all human factors we can address.These workflows let me leverage my years of engineering experience while offloading the mechanical aspects of development. I bring the wisdom to know what needs researching, and the AI brings the capacity to explore options simultaneously and implement solutions efficiently.We're only at the beginning. These three workflows represent my current best practices, but I expect to discover new patterns next week. The landscape is evolving rapidly, and the best approach is to keep experimenting, adapting, and refining how we collaborate with these powerful tools.Kieran Klaassen is the general manager of Cora, Every’s email product. Follow him on X at @kieranklaassen or on LinkedIn. To read more essays like this, subscribe to Every, and follow us on X at @every and on LinkedIn.We build AI tools for readers like you. Automate repeat writing with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora.We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.Get paid for sharing Every with your friends. Join our referral program.Subscribe
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
