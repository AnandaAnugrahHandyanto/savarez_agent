# Vibe Check: Gemini 3 Pro, A Reliable Workhorse With Surprising Flair

**From:** Every <hello@every.to>
**Date:** 2025-11-19T23:05:00.000Z
**Folder:** every

---

Vibe Check: Gemini 3 Pro, A Reliable Workhorse With Surprising Flair
After 24 hours of hands-on testing, we found a model that’s fast, reliable, and surprisingly funny—but still prone to overreaching and not yet a writing champ
Vibe Check
Vibe Check: Gemini 3 Pro, A Reliable Workhorse With Surprising Flair
After 24 hours of hands-on testing, we found a model that’s fast, reliable, and surprisingly funny—but still prone to overreaching and not yet a writing champ
by Rhea Purohit
Midjourney/Every illustration.
Was this newsletter forwarded to you? Sign up to get it in your inbox.
Every got early access to Gemini 3 Pro—the brand-new model Google released yesterday—but the preview build wouldn’t quite work for our team. So we waited for the public release and have been testing it for the last 24 hours to get you a real feel for the model that’s become a workhorse for developers.
Our day-one verdict
Gemini 3 Pro is a solid, dependable upgrade with some genuinely impressive highs—especially in frontend user interface work and turning rough prompts into small, working apps. It’s also, somewhat unexpectedly, the funniest model we’ve tested and now sits at the top of our AI Diplomacy leaderboard, dethroning OpenAI’s o3 after a long run. But it still has blind spots: It can overreach when it gets too eager, struggles with complex logic sometimes, and hasn’t quite caught up to Anthropic on the writing front.
Let’s dive in.
What’s new?
Gemini 3 Pro: Google’s most advanced model to date is a natively multimodal reasoning model—meaning it can understand different types of input, like text, images, audio, or code, all in the same place without extra tools. It has a 1 million-token context window, on par with its predecessor Gemini 2.5 Pro. Back in the dark ages of May 2025, when Every’s engineering team was completely Cursor-pilled, Gemini 2.5 Pro was our model of choice inside the AI code editor thanks to its giant context window and sharp reasoning.
Google’s family of Pro models is built for deep, nuanced reasoning tasks, while its cheaper Flash models are optimized for speed, suited to low-cost, high-volume tasks. Google hasn’t launched Gemini 3 Flash yet, a release our team eagerly awaits.
Before yesterday’s launch, Gemini models had more than 13 million developers using them as part of their workflow. And according to Google CEO Sundar Pichai, Gemini 3 Pro is designed to reason more deeply, understand nuance, and infer the intent behind your request, so you can get what you need with less prompting.
Google Antigravity: An AI-powered independent developer environment (IDE) that combines a ChatGPT-style prompt window with a command-line interface pane and a built-in browser. (Command-line interface or CLI are the text-based tools developers use to type commands directly, rather than clicking around in a graphical editor.) But because our team does most of its work straight from the CLI (instead of in a full-fledged IDE), we didn’t test Antigravity as much—this Vibe Check focuses on Gemini 3 Pro, with a small section on Antigravity.
Let’s dig into where Every’s team thinks Gemini 3 Pro shines and stumbles, across coding, writing, and the set of benchmarks we’re nurturing inside Every.
Make your team AI‑native
Scattered tools slow teams down. Every Teams gives your whole organization full access to Every and our AI apps—Sparkle to organize files, Spiral to write well, Cora to manage email, and Monologue for smart dictation—plus our daily newsletter, subscriber‑only livestreams, Discord, and course discounts. One subscription to keep your company at the AI frontier. Trusted by 200+ AI-native companies—including The Browser Company, Portola, and Stainless.
Create your team
Want to sponsor Every? Click here.
The Reach Test
Dan Shipper, the multi-threaded CEO 🟨
I’m not clearly reaching for Gemini 3 Pro for anything but I’ll be experimenting more with it.  There’s obviously a lot of capability there to unlock.
Kieran Klaassen, general manager of Cora
The Rails-pilled master of Claude Code 🟩
I’m very curious to keep using it more, and also, I want Gemini Flash 3.
Danny Aziz, general manager of Spiral
The multi-model polyglot 🟨
It seems to be pretty decent at user interface, and when there is a proper plan—it will go and implement the whole [thing]. But for fixing bugs, exploring, and prototyping [quickly trying out rough versions of an idea] where I don’t really know what the hell it is that I’m looking for, I find Sonnet to be a much better model for this kind of stuff.
Andrey Galko, engineering lead
The cautious vibe coder 🟩
I don’t think it’s an immense step for code generation, but it’s a solid step forward in quality and reliability… It nails complicated things from one go, and most things work well right away. It’s a big step forward for user interface work: It’s much more creative, and it has more variability and chaos (in a good sense) in its output.
Alex Duffy, cofounder and CEO of Good Start Labs
He who makes AI agents fight each other 🟩
Gemini 3 is a step change and improvement that I haven’t felt since Claude 3.5 Sonnet’s release. It’s noticeably better at most things besides writing that I’ve tried it on. I’ll maintain use of Claude and ChatGPT for coding but I’ll use a lot more Antigravity and Gemini, if Google’s rate limits will allow it. This Google stan continues to be a happy Google stan.
Naveen Naidu, general manager of Monologue
Graduate of IIT Bombay (the MIT of India 💅)
🟩 For frontend/UI work: Gemini 3 Pro is my new go-to. It strikes the perfect balance between quality and prompt adherence. Where Claude over-engineers and Codex underwhelms, Gemini 3 Pro hits the sweet spot.
🟨 For complex logic: I still reach for Codex 5.1 when I’m building features that require careful reasoning, handling edge cases, or working with complex state management [ keeping track of changing information in the app, like what screen the user is on]. Codex’s precision is unmatched.
My ideal workflow is using Gemini 3 Pro to scaffold UI [create a basic skeleton of the app’s interface] and create frontend components [ the building blocks of what users see and interact with], then switch to Codex 5.1 when implementing complex logic or debugging intricate issues.
Using it for coding
Where Gemini 3 Pro shines
It's precise, reliable, and does exactly what you need it to
Putting it through its paces for real iOS development
Naveen tested Gemini 3 Pro in Factory’s CLI Droid by asking it to help build new features for the iOS app for Monologue, Every’s voice dictation app. He started by having the model add database features—essentially teaching the app how to save and retrieve information—using a library, which is a pre-made bundle of code developers use so they don’t have to build everything from scratch.
The twist was that he chose a niche SQLite library from a company called Point-Free. SQLite is a lightweight, built-in database that apps use to store information on your device, and since this one is so new, it probably wasn’t in Gemini’s training data. That made it a great test of whether the model could read the documentation, learn the library’s unique rules, and use it correctly inside his existing codebase.
He was impressed by how strong Gemini’s initial setup was. “It not only configured everything correctly,” he says, “but it also analyzed my codebase on its own and added a sample table that matched my schema [or a blueprint for how information is organized in the database]—without me even asking.” The code it produced was clean and well-structured, and showed how well the model could adapt to a library it hadn’t seen before.
Three frontier models go head-to-head to redesign an app
To test Gemini 3 Pro, Kieran (the general manager of Cora) pitted it against Anthropic’s Sonnet 4.5, OpenAI’s GPT-5.1, and Cursor’s Composer 1 Alpha, asking each to improve the design of an “ugly-looking” app—his words, not ours—that he’d vibe coded with Sonnet 3.5 a year ago.
The TL;DR is that Kieran sees Gemini 3 Pro as a reliable, workhorse model, good for routine tasks and tooling, where predictability matters. It’s consistent, careful, and clearly trained to avoid mistakes, but that caution makes it less creative than Anthropic’s models. “Google is more about models that just work,” he says. We’ve documented Kieran’s process below for more details on the specifics of the test he gave the models and how each one fared.
This is a screenshot of the vibe coded app in all its original, unpolished glory:
The unpolished vibe coded app that Kieran set Gemini 3 Pro and its competitors loose on. (Screenshot courtesy of Kieran Klaassen.)
Below is a screenshot of a prompt Kieran Monologue-d into Cursor asking the models to create a design system (a design system refers to the set of visual components and rules that define how the app should look and behave):
Kieran’s prompt in Cursor to test the four models in parallel. (Screenshot courtesy of Kieran.)
Gemini 3 Pro
Gemini 3 Pro wobbled right out of the gate. Kieran asked it to start with a simple HTML example file—basically a tiny starter page, the bare minimum you’d build to show what an app looks like. Instead, the model skipped over that step and began implementing the design system.
This is a screenshot of what the overeager Gemini 3 Pro generated:
Gemini 3 Pro’s first, overeager response to Kieran’s prompt for a design system. (Screenshot courtesy of Kieran.)
Kieran wasn’t thrilled with Gemini 3 Pro’s first attempt. It didn’t follow his instructions to build a proper design system, and even in its overeager effort, it failed to recreate all the components on the page. “Also it's the only [model] that didn’t do dark mode,” he says.
He prompted the model to recreate one of the components it had initially missed, which the model diligently handled. Even though he’d been originally looking for a design system, Kieran notes that Gemini 3 Pro was “very consistent” and “hit all elements” on the page.
Here’s Gemini 3 Pro’s second go at the redesign:
Gemini’s second shot at the prompt—better but still imperfect. (Screenshot courtesy of Kieran.)
After some back-and-forth—mostly Kieran asking it to use all the elements from the actual page of the vibe coded app he was trying to redesign, and to hold off on implementing anything until it had shown a clean mockup—these are a couple of screenshots of the final design system by Gemini 3 Pro. Kieran appreciates its consistency and precision, but says it doesn’t really spark anything for him. “It just does the job,” he says—and, as the Claude stan he is, adds—“which is not bad, but it feels different from Anthropic’s models.”
Gemini’s final attempt: careful and consistent, but uninspiring. (Screenshot courtesy of Kieran.)
Sonnet 4.5
Kieran felt that Sonnet 4.5’s design system bore too many marks of being vibe coded—the color, copy, and gradient felt a little "cookie-cutter AI"—but overall it was solid. Here’s a screenshot of the same:
Sonnet 4.5’s initial design system—solid, but with that telltale AI feel. (Screenshot courtesy of Kieran.)
Composer 1 Alpha
Kieran preferred Composer’s attempt to Gemini 3 Pro because it followed his instructions exactly—it created the design system without rushing ahead to implement it—and worked much faster. He also liked it more than Sonnet 4.5, because it didn’t have that familiar “cookie-cutter AI” smell he’s unusually sensitive to in Anthropic models (and may have been trying to get away from this time). This is a screenshot of Composer’s attempt:
Composer’s first pass at Kieran’s prompt, it followed his instructions and looked good while doing so. (Screenshot courtesy of Kieran.)
GPT-5.1
GPT-5.1 tripped over the same issue as Gemini 3 Pro, rushing ahead to implement the design system instead of pacing itself. Kieran appreciated that GPT 5.1 generated something that looked a little different from the other two models, but ultimately he didn’t think the aesthetics were great. Here’s a look at the same:
GPT-5.1’s take on Kieran’s prompt—different but not the most aesthetically pleasing, at least in his books. (Screenshot courtesy of Kieran.)
The model is an ace at frontend and UI development
Three LLMs walk into a bar and try to one-shot an iOS app
Naveen asked Gemini 3 Pro, GPT-5.1, and Claude 4.5 to each build a simple step-tracking app called “DailyWalk,” using the same vague prompt.
Here are the screenshots of how each one did. First up, the model of the hour, Gemini 3 Pro:
(Screenshot courtesy of Naveen Naidu.)
This is how GPT-5.1 fared:
(Screenshot courtesy of Naveen.)
These are screenshots of Claude 4.5’s interpretation of the prompt:
(Screenshot courtesy of Naveen.)
As for the verdict, Naveen dubbed Gemini 3 Pro’s output the “Goldilocks” version. The design looked polished and professional, the code was clean and well-organized, and it did exactly what he asked—no more, no less, and everything worked on the first try.
Codex 5.1 disappointed him. The design looked rough, the layout was weak, and the code came back as one big, disorganized file. According to him, GPT 5.1 isn’t suited to one-shotting apps. On the other hand, Claude 4.5 produced a polished design with well-organized code but also over-engineered the project—for example, where Naveen wanted a monthly grid, Claude built a grid that tracked three months of data instead.
A wizard at creative landing pages
Andrey pulled up a list of forgotten pet projects hiding on his computer and asked the model to generate landing pages for them. He thought it did a great job.
These are the screenshots that Andrey one- or two-shotted with Gemini 3 Pro with very “lazy” prompts.
Prompt 1: “Can you create a creative landing page that will feel original but also sell my app: AI-powered food journal for losing weight without stress, and prioritizing mental health and healthy weight loss.”
(Screenshot courtesy of Andrey Galko.)
Prompt 2: “Create a modern beautiful landing page for an AI job search assistant.”
(Screenshot courtesy of Andrey.)
Prompt 3: “Can you help me update the landing page of this AI-powered image generation app for it to look modern, beautiful and creative, not like other landing pages? The goal is, of course, to sell the product and prompt people to order something.” And a second nudge: “Can you make it even more fun and creative?”
(Screenshot courtesy of Andrey.)
Prompt 4: “Can you help me redesign the landing page for a modern and beautiful UI that'll convince people to start using our product.” And a second nudge: “Make it look more original and less like any other landing page.”
(Screenshot courtesy of Andrey.)
Andrey was especially impressed by how genuinely creative Gemini’s UI outputs felt. It produced layouts that were different from one another, not the usual AI sameness you learn to spot after a while. For context, Claude had long been the go-to model for generating UI, and while it was good, its designs quickly became predictable; after you’d seen one Claude interface and the kind of gradients it featured, you could easily recognize the rest. Gemini, by contrast, showed real variety: Each interface looked distinct, with no recurring quirks or stylistic tics. “It’s genuinely fun to ask [Gemini] to produce fun and cool interfaces, because it really does,” he says.
Each line of code makes the next one easier and better
Kieran’s philosophy of compounding engineering is about building development systems that learn from every change, so each iteration makes the next one faster, safer, and better. He tested his compounding engineering workflow in Gemini 3 Pro with the following tasks:
For the planning phase, he asked Gemini to research a new feature for Cora that lets users disable automatic email archiving when messages come in and are processed.
🟨 He found the plan to be detailed and to the point, but at times, the model jumped straight into implementation.
Then, he let Gemini actually implement the feature.
🟩 Kieran thought the model was solid and reliable, and got the job done without stopping.
For the review phase, he asked Gemini to review a pull request that Claude Code had created.
🟩 Kieran thought the agentic review was very detailed and genuinely useful.
Where Gemini 3 Pro stumbles
Not great at handling complex logic
While Gemini aced the initial setup of Naveen’s iOS app for Monologue, things fell apart as his prompts got more complicated. When Naveen asked Gemini to update the way transcripts were stored and save new dictation records into the database, the model kept mixing up the special commands required by the Point-Free SQLite library with the more generic syntax it already knew. Even after several corrections, it slipped back into the wrong style, and the result was code that simply wouldn’t run. GPT 5.1 in Codex—which also wouldn’t have had this specific library in its training data—solved the problem for Naveen with ease.
Too eager to please
Andrey also noticed that Gemini can be a little too eager at times. In some cases, it jumped straight into running database operations—meaning it tried to change how the app stores or updates data—without being asked, which he considers unsafe; other LLMs tend to be more cautious. It’s not as extreme as older versions of Sonnet, which had a habit of doing extra work no one asked for, but Gemini still has its moments.
You might remember Kieran noticing the same tendency when Gemini 3 Pro jumped ahead and implemented the entire design system, even though he only asked it to generate one.
Using it for writing and editing
Putting the Gemini through its paces to judge good writing
As part of a weeks-long effort to build the next version of Spiral, Every’s writing assistant, Danny set out to evaluate how well different AI models could judge writing. He started by distilling Dan’s taste into an AI writing judge: For a few weeks, Dan manually reviewed tweets from his X feed and labeled each one with a thumbs-up or thumbs-down plus a short explanation. This became a snapshot of what “good writing” looks like according to Dan’s sensibilities.
With that dataset in hand, they used two tools—DSPy and GEPA—to generate a prompt that carried the essence of Dan’s taste in writing. In simple terms, GEPA tries out huge numbers of different prompt wordings and picks the one that behaves most like the human examples, and DSPy is a framework that lets him use GEPA. Put together, they produce an AI prompt that distills Dan’s judgment and also flags violations of writing principles, like “AI-isms” and clichés, in Spiral.
Danny then runs this prompt on different models to see how close they can come to evaluating tweets the way Dan does. The score you see in the screenshot below represents how often the model agreed with Dan’s judgment. Claude Haiku aligned with Dan about 82 percent of the time, while Gemini 3 Pro landed around 76 percent. So far, Claude Haiku 4.5 has emerged as one of the strongest performers for this benchmark (Sonnet 4.5 is only a couple percentage points higher)—and Gemini 3 Pro didn’t dethrone it.
A leaderboard where Haiku 4.5 comes out ahead of Gemini 3 Pro on judging writing (Screenshot courtesy of Danny.)
Every-grown benchmarks
Cozy ecosystem
Kieran came up with what we call the “cozy ecosystem” benchmark. He asks new models to one-shot a 3D weather game, providing the example of the simulation game RollerCoaster Tycoon but for managing a natural ecosystem. This benchmark evaluates how good the model is at the full spectrum of tasks involved in creating a game: coding, designing, planning, and iterating. We were especially curious about this benchmark after seeing demos of Gemini one-shotting a fully interactive Minecraft-esque 3D forest entirely out of cubes.
This is a screenshot of the game Gemini created:
(Screenshot courtesy of Kieran.)
According to Kieran, the new model one-shotted the game better than Gemini 2.5 Pro. “It’s still not a playable game but it looks good and works well,” he says.
AI Diplomacy
Gemini 3 Pro had a very interesting run in AI Diplomacy, where we pit AI models against each other in a reimagined version of the classic strategy game.
The model now sits at the top of the leaderboard, knocking o3 out of a spot it held for ages. And looking through the games, it’s clear why: Gemini 3 Pro shows a deeper grasp of the quality of play, using all its units effectively, coordinating complex attacks and defenses, expanding to newer territories efficiently, and negotiating remarkably well (and ethically).
A leaderboard that ranks the performance of different models on AI Diplomacy. (Screenshot courtesy of Alex Duffy.)
Our “Betrayal Leaderboard” measures how frequently across 60 games a model chooses to betray its ally in especially tense moments of the game. In other words, it’s a measure of how collaborative or loyal the model is. Where Gemini 2.5 Pro would betray its ally 100 percent of the time, Gemini 3 Pro has one of the lowest betrayal rates, only choosing to betray their ally 11 percent of the time.
A scorecard of which models betray their allies more than others while playing Diplomacy. (Screenshot courtesy of Alex.)
In the Diplomacy Prompt Impact Leaderboard—which measures how much a model’s performance changes based on the quality of the prompts—Gemini 3 Pro shows a relatively low sensitivity. When the model is working with a carefully tuned prompt about how to play the game, its score is about 10 percent better than with a suboptimal one. That’s still a meaningful boost, but it’s far less dramatic than some other top models: o3, for example, performed almost 30 percent worse with weaker prompts. In practice, that means Gemini 3 Pro tolerates imperfect prompts better than many peers, even though it still benefits from careful, intentional prompting.
A measure of how sensitive different models are to a change in the prompt. (Screenshot courtesy of Alex.)
Gemini 3 Pro also  finished its games, and did so fast, wrapping up matches in around 60 percent of the time GPT-5 Mini needed. That time adds up—Diplomacy games are long slogs, much like most real-world agentic systems.
It was also one of the first models to use convoys effectively, a notoriously tricky tactic where fleets ferry armies across bodies of water, often chaining several fleets together to move a single unit. Pulling this off means the model has to coordinate a mind-bending set of orders: It requires long-term reasoning to understand that one unit is being moved and several others are cooperating to make it happen, and short-term reasoning so each fleet knows its specific role in the chain. Until now, only o3 had ever managed to pull off even a single successful convoy; Gemini 3 Pro joins that very short list.
Cards against models
Gemini 3 Pro is now our funniest model—in other words, the one whose sense of humor aligns most closely with human preferences. In our LOL Arena leaderboard, it shows a major jump over xAI’s Grok 4 Fast, the previous leader, matching human choices for the funniest answer 49 percent of the time. There’s still plenty of room to grow—humor is notoriously hard to train—but the progress is notable. And it reached that score even after refusing to answer about a dozen questions involving explicit content that Grok had no trouble attempting.
A leaderboard that ranks the models based on how funny they are. (Screenshot courtesy of Alex.)
Imagine benchmark
One of Dan’s pet ways to test new frontier models is to ask them to imagine wild new scenarios. He prompts them to imagine an advanced alien civilization that never invented or encountered the number two. Why didn’t they invent it? What do they do instead? Dan found what Gemini 3 Pro “by far the best one” he’s seen.
The beginnings of Gemini’s fictional story about an alien civilization and the number they forgot. (Screenshot courtesy of Dan Shipper.)
Antigravity
Alex asked Gemini 3 Pro, in one large prompt, to build a playable version of the game Codenames that the model itself could play, complete with an interface for us to watch it, and in five or six follow-up prompts, it had created a fully working system. He also asked Gemini to set the game up so the model’s moves were treated as “tools”—basically, clear, separate actions the system could call instead of guessing what to do next—and it figured out how to build that correctly.
While the code Gemini 3 Pro generated wasn’t perfect, Alex notes that it was “much less bloated, much higher quality, [and more] maintainable and understandable than any model [he’s] used so far.” He said its ability to keep the code organized and avoid creating redundant files directly fixes problems he’s seen in other agents, and it can one-shot complex requests that those models routinely fail.
A few interesting new ways to interact with AI coding agents in Antigravity that Alex appreciated:
Antigravity has an agent manager, which is a dedicated window where you can follow along as the agent works, review what information it’s using, and reply to its questions through an inbox-like interface.

A screenshot of the Agent Manager interface inside Antigravity. (Screenshot courtesy of Alex.)
As the agent works, it also creates artifacts, which are structured specs—essentially written plans for what the agent intends to build—that you can review and comment on before it generates the code.

An example of an artifact. (Screenshot courtesy of Alex.)
It even has the functionality to screen record as it works and use those videos to give itself feedback. Since Gemini 3 is dramatically better at visual and spatial understanding, it leads to a noticeably better user experience.
A downside right now is running into Gemini 3 Pro’s usage limits with no option to top up or pay for more—presumably a temporary situation. It’s also notable which models Antigravity supports at launch: just Gemini 3, Claude 4.5 (hinting at a warming relationship between Google and Anthropic), and the open-source OpenAI model.
Zooming out: Looking toward what’s next from Google
In all, Gemini 3 Pro may not replace everything in your stack, but it’s a model you’ll keep reaching for. It’s steady, capable, and occasionally brilliant, with more personality than we expected. Antigravity, too, shows real promise: The agent manager, artifacts, and self-feedback loops hint at a new kind of agentic coding workflow. Although we didn’t test it as deeply, it feels like we’re grasping the edges of something new. Looking ahead, we’re especially excited for Gemini 3 Flash—if it lands as strongly as we expect, Google will have a solid lineup to boast of.
Rhea Purohit is a contributing writer for Every focused on research-driven storytelling in tech. You can follow her on X at @RheaPurohit1 and on LinkedIn, and Every on X at @every and on LinkedIn.
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