# The Tool That Lets You Switch Models Without Losing Your Place

**From:** Every <hello@every.to>
**Date:** 2025-11-04T17:51:00.000Z
**Folder:** every

---

The Tool That Lets You Switch Models Without Losing Your Place
Everything we learned at Droid Camp about switching between GPT and Claude while staying in flow
Source Code
The Tool That Lets You Switch Models Without Losing Your Place
Everything we learned at Droid Camp about switching between GPT and Claude while staying in flow
by Katie Parrott
Midjourney/Every illustration.
Was this newsletter forwarded to you? Sign up to get it in your inbox.
Kieran Klaassen is not an easy man to convert. As general manager of Every’s AI email assistant Cora, Kieran has become a steadfast Claude Code devotee—including building an entirely new engineering system around the tool. So no one at Every was surprised when he first tried Droid, the agentic coding product from Factory, and proclaimed himself “unimpressed.”
But he kept trying because he discovered Droid had subagents—specialized AI workers configured for specific tasks. He could replicate the engineering process he designed in Claude Code in Droid without learning a different system. Once he realized Droid could do that—and that it would let him pick which model to use for which task—he used it to ship a feature in Every’s AI writing partner Spiral (an app he’d never worked on before) in less than two hours.
That’s what Droid offers: an AI agent that lets you switch between GPT and Claude mid-task, picking the best model for each phase of work. Unlike Claude Code (Anthropic only) or Codex’s command line interface (OpenAI only), Droid works with multiple models from different providers. GPT-5 and Claude Sonnet 4.5 each have distinct strengths. Until now, in order to switch between those models, you had to switch tools.
If there was one person who wasn’t surprised by Kieran’s conversion, it was Danny Aziz, general manager of Spiral and Droid’s biggest evangelist at Every. Danny canceled both his Claude and ChatGPT Max plans for Droid, became Factory’s top early-access user, and built nearly all of the newest version of Spiral using its multi-model workflows.
If Danny and Kieran represent the developer side of Droid, Factory’s head of developer relations Ben Tossell represents proof that you don’t need to code to get value from AI agents like Droid. He can’t write a single line of code, but uses Droid as his default interface for everything from analyzing monthly financials to downloading YouTube transcripts. Where Danny and Kieran use Droid to build features faster, Ben uses it to automate tasks he’d otherwise do manually.
Danny, Kieran, and Ben joined Every CEO Dan Shipper last week in Every’s Droid Camp to share how they use Droid in production, answer subscriber questions, and demonstrate workflows you can start using today. The event was for paid subscribers, but there was so much useful discussion and knowledge sharing that we’re posting the key takeaways for anyone who missed it. You’ll learn how to orchestrate multiple AI models in production—plus see real examples of developers and non-coders doing exactly that.
Turn talking into doing
Glue turns your team chat into a place where real work gets done. File a Linear issue, schedule a meeting, or check deployment status in the same thread you’re already chatting in. Context-aware AI and multiplayer tooling. Faster decisions and fewer tabs.
Get started with Glue
Want to sponsor Every? Click here.
Key takeaways
Here’s what makes Droid worth your attention:
Switch models mid-task to match the work. Use GPT for long research and planning, then switch to Claude for implementation—all in the same terminal session.

Start with one model, scale up. Ben runs most tasks in a single conversation thread. Danny orchestrates multiple models across separate terminal panes.

It’s great at non-technical use cases. Droid handles data analysis, file management, and automation tasks just as well as code.

Context moves between models. When you switch from GPT to Claude, Droid compresses your conversation history and carries it forward so the new model understands what you’ve been working on.

What makes Droid different?
Droid is a command line AI agent—software that can read files, write code, run commands, and complete tasks on your behalf. You might also hear it referred to as a harness: the software layer that packages an AI model into a usable tool. The harness determines how the model interacts with your code, what tools it can access, and how it presents information back to you. A good harness can make the same model perform better by giving it better context and more effective tools to work with.
Unlike most similar products, which are made by the companies that build the AI models (like Anthropic’s Claude Code or OpenAI’s Codex CLI), Droid works with multiple models from different providers and lets you switch between them with a single command. When he was building Spiral’s latest version, Danny got into the habit of running most of his workflow across multiple terminal panes that play to models’ different strengths: GPT-4 handles research and planning, Claude Haiku implements the bulk of the code, and Claude Sonnet refines the details. Danny never has to leave his terminal or copy files between tools—he simply picks the best model for each phase of work.
Droid consistently ranks near the top of SWE-bench, a benchmark that measures how well AI agents solve software engineering tasks. According to Ben, the Factory engineering team attributes this to several design choices: reliable error handling that doesn’t fill your context window with repeated failures, built-in system reminders that keep models on track, the ability to pair smaller models for planning with larger ones for execution, and files where you can save notes that Droid will read to keep track of your preferences (a feature Claude Code also has).
Dan, Every’s CEO, captured the general experience: Droid consistently produces better results than you’d expect from using the same models elsewhere, even if the reasons why aren’t fully clear yet.
Workflows from the Every team
Here’s how our engineers use Droid in production, with specific examples from the session.
Ben Tossell: Non-technical automation
Ben runs Droid the way most people use ChatGPT, but with access to his file system. His terminal typically has six tabs running simultaneously: one analyzing Factory’s monthly finances, another helping him write documentation, a third working through tutorial scripts, and a fourth teaching him technical concepts he doesn’t understand yet.
When he notices himself doing something manually that could be automated, he asks Droid to handle it, then saves the commands it used as a reusable workflow. Take downloading YouTube videos, for example. In ChatGPT, extracting a transcript requires multiple copy-paste steps. In Droid, he typed one instruction: “download the My First Million episode about Grindr, extract the transcript, save it to a folder.” Droid found the right command line tools, ran them in sequence, and confirmed completion.
Afterward, Ben reviews the commands Droid executed in order to understand the sequence, and converts the pattern into a sub-agent or slash command (a reusable shortcut) he can trigger with a single word next time.
Danny Aziz: Multi-model orchestration
Danny showed the most sophisticated setup of the session. He had multiple terminal panes open, each running a different model on the same codebase:
Left pane: GPT-4 Codex in spec mode (a phase where the AI documents how a feature should work), researching how Cora renders email briefs

Right pane: Claude Haiku implementing the feature

Middle pane: Claude Sonnet 4.5 refining the implementation

Danny was building a feature that allowed Cora to detect a user’s scrolling behavior. When someone reaches the bottom of their morning Brief, Cora should automatically jump to their afternoon Brief from the same day. It’s a simple premise with messy implementation because it required understanding how Cora’s existing scroll logic worked, implementing new detection code, and polishing the user experience.
Danny walked through each step:
Research phase (GPT-4 Codex): “Look at the web app for how briefs are rendered.” GPT analyzed the codebase (all the code files that make up the application) and documented the existing behavior in a markdown file (a simple text file that developers use for documentation, with basic formatting like headers and bullet points).

Planning phase (GPT-4 Codex): “Based on the research, write a spec for scroll detection.” GPT wrote a detailed plan, which Danny saved as a file.

Implementation phase (Claude Haiku): In a new pane, Danny pointed Haiku to the spec file and told it to build. Haiku wrote the code.

Refinement phase (Claude Sonnet): When the first attempt didn’t work perfectly, Danny switched to Sonnet for debugging and polish.

A working feature, ready for review—in about an hour. Now when Danny reaches the bottom of his morning Brief on his phone, he can scroll down a bit more to jump to his afternoon Brief instead of scrolling back to the top. His Briefs are massive because he never checks his emails, so having to scroll back to the top was genuinely annoying. Now he just scrolls down and seamlessly rolls from one Brief to the next.
Kieran Klaassen: One-shot feature in unfamiliar codebase
Kieran wanted to add a rewind button to Spiral that would let users jump back to earlier messages in a conversation, but he’d never touched Spiral’s codebase before.
His approach combined custom commands with strategic model selection:
Plan with GPT-4 Codex: He used his custom /plan command (ported from Claude Code) to generate a 20-minute research session. GPT analyzed Spiral’s message architecture, proposed a solution, and documented what would need to work for the feature to be considered complete.

Execute with Claude Sonnet: He copied the plan to a new terminal session, switched to Claude, and ran his /work command. Claude implemented everything—back-end logic, front-end button, database changes—in one pass.

Test: Kieran booted up Spiral locally. The rewind button appeared and worked on first click.

Kieran shipped a working implementation in an unfamiliar codebase faster than most engineers could orient themselves to the architecture.
The key was bringing his own system. Kieran’s plan command runs 10 research steps, including web searches for best practices. It’s expensive—he burned half his monthly credits on two builds—but the depth matters to him more than efficiency. He doesn’t want someone else’s workflow. He wants a harness that executes his workflow well, regardless of which model he’s using.
The $100 P&L
Ben’s automated financial reporting is a case in point in how tools like Droid can be useful even for non-coding tasks. He keeps his P&L in a markdown file that defines categories (income, tax, ads, contractors, software) and a Python script that processes bank statements.
Every month, he types one line: “Do October’s P&L.”
Droid reads the markdown, executes the Python script, updates his master spreadsheet, and returns a summary, with just a simple instruction—and without any code—from Ben.
Practical tips for getting started
The session wrapped with a Q&A with subscribers. Here’s a selection of answers that will help orient new and experienced Droid users alike.
Start simple, scale up
Q: This sounds amazing but I have absolutely no idea what’s happening. Where do I start?
Ben’s advice: Treat Droid like a version of ChatGPT that can access your computer. Don’t worry about understanding every technical detail underneath. Just start with simple tasks and build up.
Kieran added that anyone feeling overwhelmed should try his /plan command first. It automates most of the complexity, and you can read the underlying prompts later to understand how the pieces fit together.
How to switch models effectively
Q: I’m jumping around between models. Where’s the context?
Droid handles switching between models in two ways. When you switch between models from the same provider (like Claude Haiku to Claude Sonnet), your full conversation history carries over instantly. When you switch between different providers (like GPT to Claude), Droid compresses your conversation and passes the key details to the new model, which takes a few seconds.
Danny has evolved past relying on automatic compression. Instead, he outputs artifacts like plans or research as markdown files, and tells the next model to read the file. This gives him more control over what information carries forward and what gets left behind.
Cost considerations
Q: Should I bring my own API keys or just use a Droid plan?
Neither Danny nor Kieran track token usage closely. Both find Droid’s $200 monthly plan sufficient for regular production work. Danny notes that Kieran’s /plan command will blow through credits fast, though—two features burned half a monthly allowance. Kieran would say it’s worth it. Your accountant might disagree.
Git work trees
Q: How are you switching models in the same directory without conflicts?
Danny’s setup uses git work trees—think of them as parallel universes for your code, where you can work on multiple versions of the same project simultaneously without them interfering with each other. Each work tree is a separate folder with its own copy of the code.
He reserves work trees for completely separate features. For example, he might be building a new search feature in one work tree while fixing a bug in the email system in another work tree—running different Droid sessions in different folders so they don’t conflict. When working on the same feature, he just ensures multiple models aren’t editing the same file simultaneously.
Sub-agents and custom commands
Q: Can you create a command that runs different models for different steps?
Yes. Droid’s sub-agents let you specify which model each specialized worker uses. You can build a command that plans with GPT, executes with Claude Haiku, and reviews with Claude Sonnet—all running automatically in sequence.
You can even do dynamic model selection, like running the same task five times with five different models to compare results. One subscriber accepted the challenge during the session and reported they got it working within minutes.
Spoiler: Nobody’s using just one tool
Droid’s model-agnostic approach lets you do things other command line tools can’t—switching between GPT and Claude mid-task, orchestrating multiple models simultaneously, and bringing your own workflow regardless of which lab built the model.
Each of our three Droid users fits the tool into their workflow in different ways. Danny uses Droid and Codex CLI. Kieran uses Claude Code and Droid. Ben uses Droid for everything. They’ve each found the right mix for how they work.
Dan framed the choice clearly: If you’re non-technical or working in unfamiliar codebases, GPT feels more precise and less likely to make embarrassing mistakes. Claude is more industrious and willing to explore. Both approaches have value; now you can choose which one fits the moment.
Try Droid yourself. Download it, pick a task you’ve been putting off, and see which model works best. Then switch to another and compare. The best tool is the one that fits how you already think. Droid just makes it easier to find out which that is.
Katie Parrott is a staff writer and AI editorial lead at Every. You can read more of her work in her newsletter.
To read more essays like this, subscribe to Every, and follow us on X at @every and on LinkedIn.
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
