# Vibe Check: I Canceled Two AI Max Plans for Factory’s Coding Agent Droid

**From:** Every <hello@every.to>
**Date:** 2025-10-30T16:35:07.000Z
**Folder:** every

---

Vibe Check: I Canceled Two AI Max Plans for Factory’s Coding Agent Droid
The one that keeps me in flow across Anthropic and OpenAI’s models—without switching tools
Source Code
Vibe Check: I Canceled Two AI Max Plans for Factory’s Coding Agent Droid
The one that keeps me in flow across Anthropic and OpenAI’s models—without switching tools
by Danny Aziz
Midjourney/Every illustration.
Get up to 60 million free tokens to spend on any model—GPT-5, Sonnet 4.5, Opus, etc.—by attending our Droid Camp for paid subscribers tomorrow, October 31, at 12 p.m. ET. Factory AI’s head of developer relations Ben Tossell and Every's Dan Shipper, Danny Aziz, and Kieran Klaassen will walk you through how they use the tool. RSVP if you're a paid subscriber, or upgrade your subscription to attend.—Kate Lee
Was this newsletter forwarded to you? Sign up to get it in your inbox.
Picture reorganizing your filing system while people are still thumbing through the folders. That’s what it’s like to move or restructure data in your production database—the live system storing all the user data that powers your product.
Now imagine that you’re trying to reorganize the system that runs your entire product while you’re balancing your laptop on your lap in the back of a moving car. That’s what it felt like when a production database migration I was working on for Spiral, the AI writing tool I’m building at Every, started failing on repeat while I was in the back of a car headed to IKEA. Not where you want to be debugging, but when things break, they don’t wait for you to be at your desk.
I’d started this migration, which involved restructuring how conversations, drafts, and messages are stored inside Spiral’s database, with Claude Code. The problem was that it kept circling the same dead ends of edge cases in production data that Claude Code couldn’t anticipate. So I opened Droid, set to the same Anthropic model, Opus 4.1, and asked for a fresh migration. It wrote one, applied it in a single shot, and explained each step as it went.
The thing about coding with AI in 2025 is that no single model is best at everything. Sonnet excels at complex code cleanup (i.e., refactors). GPT-5 is fast at prototyping. Haiku is great for quick fixes. But switching between tools to access different models involves losing your context, relearning commands, and breaking flow every time you need a different brain.
Droid lets you switch between models made by different labs without switching tools—and somehow makes each model work better in the process. It’s the first agent wrapper—the software layer that packages an AI model into a usable tool—I’ve tried that feels like it was built for how senior engineers work: running parallel sessions, composing workflows across models, and staying in flow when the work demands it.
It’s been a few months since I started tinkering with Droid, and I’ve canceled my Max plans for both Claude and ChatGPT. Droid has replaced them both. Let me tell you why.
Phone calls suck.
Especially when you’re dialing a big company. You call with a simple question… and what do you get? Hours on hold. A clunky phone tree that leads nowhere. Or a robotic voice that couldn’t sound less human. And after all that? You still don’t get the help you needed.
That’s why Bland, the world’s first self-hosted voice provider, is building their AI agents. Now, when you call a company powered by Bland, you get:
A voice that sounds authentic, human, and engaged

Instant responses (<500ms)

Actual helpful answers (imagine that)

It’s no wonder more and more enterprises are rolling it out—especially once they find out it’s the only provider where their data is actually secure. So… expect to be talking with Bland’s agents a lot more soon.
👉Feel free to try it out yourself: www.bland.ai/talk
Or if you’re an enterprise, schedule a custom demo: https://www.bland.ai/dem
Want to sponsor Every? Click here.
What is Droid?
From the AI coding startup Factory, Droid is a command-line coding agent that runs Anthropic and OpenAI models in one place. The pitch is agents that work everywhere you do, from your code editor through to deployment, so you can delegate full tasks—refactors, incident response (fixing things that break in production), and migrations—without changing tools, models, or workflow.
Droid is part of a fast-emerging category of agentic coding tools: AI systems built to handle development work end-to-end, not just autocomplete your next line of code.
These tools split into two camps based on where they run. Cursor, GitHub Copilot, Windsurf’s Cascade, and Google’s Jules live inside specific code editors (integrated development environments, or IDEs). They’re powerful, but you have to work in their environment, on their terms, instead of yours. If you use multiple editors or jump between projects with different setups, you can’t bring your AI with you.
Command line agents like Claude Code and Codex take a different approach—they run in your terminal, which means they work across any project, collection of programming languages, or code editor you’re using. While they provide more flexibility, they create a different limitation: They only work with one AI company’s models. Claude Code gives you only Anthropic’s models. Codex gives you only OpenAI’s. Want to switch models? You’re switching tools.
Droid splits the difference. Like Claude Code and Codex, it’s a terminal-based agent with the same core features: model context protocol (MCP) support for connecting to external tools, subagents for specialized tasks, shortcuts known as slash commands to keep you moving fast. But unlike Claude Code and Codex, one Factory subscription gives you access to both Anthropic and OpenAI models, so you don’t have to switch platforms when you need a different model’s strengths.
Droid lets you select models from different labs. I’m currently set to Sonnet 4.5 and Haiku here, but could easily switch to GPT-5 or Droid’s core model, GLM-4.6. (All screenshots courtesy of Danny Aziz.)
If you care about picking the right model for each task—the way we do at Every—Droid delivers. The model that handles your database migration might not be the best one for your frontend refactor. Droid lets you switch between them without leaving your workflow.
Factory’s bet is that developer agents need freedom to roam across tools, stacks, and model providers. Droid is trying to be the connective tissue for agentic coding—a place where your AI teammates move as fluidly as you do. Setup works like other command line agents: Run an installation command in your terminal, open the folder containing your code, type “droid” to start it, and sign in through your browser.
What makes Droid different
That flexibility is what drew me in first. I can switch between Sonnet 4.5, GPT-5, Opus 4.1, or even cheaper models like GLM-4.6 (from Chinese company Zhipu AI, which costs a fraction of what Anthropic and OpenAI charge) without switching tools. I can stay in the same space and the same workflow—no time lost reorienting myself to different interfaces.
Droid doesn’t freeze or glitch out when you ask it to read long logs or screenshots, which is a problem we’ve run into with Claude Code. The code changes it suggests are smaller and more focused—changes that respect the codebase instead of bulldozing it. And it explains what it’s doing as it goes, which makes the work easier to trust.
The same models behave more deliberately in Droid than in other agent wrappers. I’ve noticed this in particular with Claude: It checks more files before making changes and reasons through the problem instead of jumping to a solution.
I don’t know if Factory is passing each model a different prompt, or if it’s something about how they’ve set up the whole environment—the way the tools, context, and workflows fit together. They’ve clearly spent time on whatever they’re doing under the hood. It feels well thought-out. And that thoughtfulness builds confidence.
Sonnet 4.5 inside Droid has become my default. For small bug fixes and quick tasks, GLM-4.6 is the little model that could. I can build with GPT-5 or switch to Anthropic models as the work demands.
The strongest planning mode I’ve used
Droid has a “plan mode” where it breaks down problems, searches the web for context, and reads relevant files before writing code. It grounds itself in information from your codebase and the web, not just reasoning from memory.
A proposal generated by Droid through its plan mode.
The plans from larger models—Sonnet and GPT-5—are particularly strong, though even Haiku and GLM-4.5 plans in Droid outperform the same requests I’d make in Claude Code or Codex.
I can make a plan with one model—say, GPT-5—and execute that plan with GLM-4.6 to save money. This kind of intentional workflow design can make a big difference when you’re running agents all day.
Feature parity with Claude Code
Droid is at complete feature parity with Claude Code, as far as what’s important to me:
“Custom Droids”—aka custom subagents—can be invoked with a slash command. I can choose the model and run the agent or command instantly.

MCP support is there, so agents can access external tools.

The Max plan gives you 200 million tokens a month across all models, which bought me about 10 days of usage. Claude Code, by contrast, limits usage through five-hour reset windows and weekly hour caps. Droid lets me use Sonnet or GPT-5 as much as I want until I hit the token ceiling. The billing page shows my usage and what’s left—which most command line agents don’t surface well—making it easy to track.
The billing page the week we launched Spiral. I went through the Max plan’s 200 million tokens that week, which I was able to monitor thanks to this feature.
What could be better
I tried the web interface, but it’s not quite there yet. I can’t start work on my laptop from the CLI and then switch to my phone to monitor or continue that work—a limitation that exists across all these tools right now, not just Factory’s. Claude’s mobile app doesn’t connect to what I’m doing in Claude Code on my laptop, either. But Factory is marketing itself as having a unified platform that works everywhere you do, which makes the disconnect more noticeable.
Factory’s broader platform includes specialized Droids for code review, incident response, documentation, and ticket management—all agents that integrate with your existing tools like GitHub, Slack, Jira, and Datadog. But the command line tool has already taken over so much of my agent stack that I haven’t felt the need to explore the rest.
The coding agent I trust enough to go all-in
At Every, the bottom line for how good a product or tool is comes down to what we call the “reach test”: Is it something I open first, every day?
I keep opening Droid. I was the top user in the early access group (per Factory head of developer relations Ben Tossell). Now I’m paying for it instead of keeping Max plans for both Claude and ChatGPT. I want a command line coding agent that keeps me in flow across Anthropic and OpenAI—and Droid does exactly that. With custom Droids and a Max plan that works, it’s effectively replaced my entire agent workflow.
For senior engineers orchestrating multi-model workflows, I highly recommend giving Droid a spin. For people who want a unified terminal experience, this is it.
The bottom line: Droid keeps me in flow. And in a world where I’m running parallel sessions, switching models, and managing complexity across multiple tasks, that continuity is worth more than any single model’s capabilities.
Thanks to Katie Parrott and Rhea Purohit for editorial support.
Danny Aziz is the general manager of Spiral. You can follow him on X at @dannyaziz97 and on LinkedIn.
We build AI tools for readers like you. Write brilliantly with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora. Dictate effortlessly with Monologue.
We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.
Get paid for sharing Every with your friends. Join our referral program.
For sponsorship opportunities, reach out to sponsorships@every.to.
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
