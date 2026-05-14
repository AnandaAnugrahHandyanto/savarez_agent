# Vibe Check: Opus 4.5 Is the Coding Model We've Been Waiting For

**From:** Every <hello@every.to>
**Date:** 2025-11-24T19:02:53.000Z
**Folder:** every

---

Vibe Check: Opus 4.5 Is the Coding Model We've Been Waiting For
But it’s not perfect—it failed our editing test
Vibe Check
Vibe Check: Opus 4.5 Is the Coding Model We’ve Been Waiting For
But it’s not perfect—it failed our editing test
by Katie Parrott, Dan Shipper, and Kieran Klaassen
Midjourney/Every illustration.
Was this newsletter forwarded to you? Sign up to get it in your inbox.
It’s appropriate that this week is Thanksgiving, because Anthropic just dropped the best coding model we’ve ever used: Claude Opus 4.5.
We’ve been testing Opus 4.5 over the last few days on everything from vibe coded iOS apps to production codebases. It manages to be both great at planning—producing readable, intuitive, and user-focused plans—and coding. It’s highly technical and also human. We haven’t been this enthusiastic about a coding model since Anthropic’s Sonnet 3.5 dropped in June 2024.
The most significant thing about Opus 4.5 is that it extends the horizon of what you can realistically vibe code. The current generation of new models—Anthropic’s Sonnet 4.5, Google’s Gemini 3, or OpenAI’s Codex Max 5.1—can all competently build a minimum viable product in one shot, or fix a highly technical bug autonomously. But eventually, if you kept pushing them to vibe code more, they’d start to trip over their own feet: The code would be convoluted and contradictory, and you’d get stuck in endless bugs. We have not found that limit yet with Opus 4.5—it seems to be able to vibe code forever.
It’s not perfect, however. It still has a classic Claude-ism to watch out for: When it’s missing a tool it needs or can’t connect to an online service, it sometimes makes up its own replacement instead of telling you there’s a problem. On the writing front, it is excellent at writing compelling copy without AI-isms, but as an editor, it tends to be way too gentle, missing out on critiques that other models catch.
The dichotomy between strength at coding and weaker performance in editing is an interesting example of how the race to dominate coding is reshaping frontier models. Coding is economically valuable and has clearer success metrics than creative work. Labs are optimizing hard for it, and sometimes focusing less on improvements in other domains.
The overall story is clear, however: In a week of big model releases, the AI gods clearly saved the best for last. If you care about coding with AI, you need to try Opus 4.5.
Want to know more? Here’s your day-zero hands-on Vibe Check.
AI agents that actually work in production
Build agents your way with Scale AI. They just open-sourced Agentex, the framework they use to deploy reliable AI agents for enterprise customers. It handles deployment, keeps agents running, and lets them talk to each other. No vendor lock-in, and long-running workflows that stay on and work automatically.
Try it
Want to sponsor Every? Click here.
What’s new?
In its own description of the model, Anthropic makes bold claims: best coding model in the world, best vision model, best tool-using model. According to Anthropic, Opus 4.5 outperforms both its own Sonnet 4.5 and Opus 4.1 models at building code that’s reliable enough to ship to users. They say it transforms multi-day projects into hours, with cleaner code structure and organization, better bug-catching, and more independent execution.
Anthropic also updated Plan Mode, Claude Code’s feature for creating step-by-step plans for what it will build and how before writing any code, to build more precise plans and execute more thoroughly, in addition to supporting multiple parallel sessions in Claude Code on desktop. We tested both and found them genuinely improved. A new feature lets you control how liberally the model uses tokens—optimizing for speed, cost, or maximum capability.
Here’s where Every’s team thinks Opus 4.5 shines and stumbles, across coding, writing, and our homegrown benchmarks.
The Reach Test
Dan Shipper, the multi-threaded CEO 🥇
This is truly a paradigm-shifting model on the coding end. It’s the first model where I really feel like I can vibe code an app end-to-end without having to get into the details of the code. I don’t trust it as an editor, but it’s a great writer. It’s much less likely to use AI-isms, and creates genuinely quality prose. Absolutely a daily driver for me for both of those use cases.
Kieran Klaassen, general manager of Cora
The Rails-pilled master of Claude Code 🥇
Some AI releases you always remember—GPT-4, Claude 3.5 Sonnet—and you know immediately something major has shifted. Opus 4.5 feels like that. The step up from Gemini 3 or even Sonnet 4.5 is significant: [Opus 4.5] is less sloppy in execution, stronger visually, doesn’t spiral into overwrought solutions, holds the thread across complex flows, and course-corrects when needed. For the first time, vibe coding—building without sweating every implementation detail—feels genuinely viable. The model acts like an extremely capable colleague who understands what you’re trying to build and executes accordingly. If you’re not token-maxxing on Claude [using the Max plan, which gives you 20x more usage than Pro] and running parallel agent flows on this launch, you’re a loser :P
Katie Parrott, staff writer and AI editorial operations lead
AI-pilled writer by day, vibe coder by night  🟥
Opus 4.5 delivers clean, natural-sounding writing, but I’m sticking with Sonnet 4.5. It’s faster and more honest, and whatever differences there are in the writing quality on a word-by-word level are minor enough that I don’t feel compelled to switch. I’m still all-in on the Anthropic ecosystem for writing, but this release isn’t for me.
Coding: ‘It just works’
The bottom line: Opus 4.5 is the best coding model we’ve used, and it’s not close.
Planning: It thinks like a product builder
Anthropic is emphasizing improvements to Plan Mode—more precise plans, more thorough execution. When we tested Opus 4 back in May, we were impressed by how it could work independently for long stretches, but the plans themselves still read like an engineer’s checklist, as shown in the first screenshot below. Opus 4.5’s plans feel different. They’re structured around what the user needs, not just what the code does.
Codex Max 5.1’s plan is cluttered and harder to parse. (Screenshot courtesy of Dan Shipper.)
Dan tested this in a few ways. First, he tested on a power-reading iOS app he’s been building for himself. It allows him to take a picture of a page of a book and instantly get an analysis of the passage without typing or tapping. A big part of the app’s functionality is identifying which book you’re reading from just a picture of a page. He asked both Opus 4.5 and Codex 5.1 to refactor the system to make it faster, more accurate, and more user-friendly. Same prompt, same codebase, two different results.
Opus 4.5’s plan was easier to read, more user-focused, and caught issues in the code that Codex missed. “Codex’s feels like a senior engineer that doesn’t understand users,” Dan said. Opus 4.5’s read like someone who builds products.
Opus 4.5 delivers a clean, easy-to-ready plan. (Screenshot courtesy of Dan.)
He also tested it to fix a long-standing bug in the codebase for Every’s AI email assistant Cora. And though both models came to similar diagnoses, Claude’s plan was much easier to read, digest, and iterate on.
Parallel workflows: Run multiple projects without losing the thread
Opus 4 could handle long autonomous coding sessions, but running multiple projects simultaneously was risky—context would bleed between tasks, or the model would lose track of important details as conversation history compressed. Opus 4.5 seems to have solved this.
Kieran has Opus 4.5 tackle five separate tasks at once. (Screenshot courtesy of Kieran Klaassen.)
Kieran stress-tested it by running 11 projects in roughly six hours. None of them derailed.
A few examples of what he was able to build:
The abandoned feature: Kieran had abandoned a Cora churn detection feature partway through building it. Cora was miscounting cancellations because payment processor Stripe made failed payments look like churns, plan switches appear as cancellations, and account pauses register as lost customers. As a result, dashboards showed phantom cancellation spikes.
Kieran had spent days trying to build this with previous models—they’d get stuck on the partial implementation or need endless clarifying rounds. Opus 4.5 finished it in 30 minutes by making decisions and pushing Kieran forward rather than waiting for him to specify every detail.
The churn feature Kieran was (finally) able to build with Opus 4.5.  There are two questions added: "Why are you leaving?" and "Anything else?"(Screenshot courtesy of Kieran Klaassen.)
The automated code reviewer: When developers push code changes, making the changes available to everyone using a product or service, automated systems run checks to see if the updated code follows the style rules. These are formatting conventions that keep code readable and consistent across a codebase.
Kieran had Opus 4.5 optimize this process so that Claude  reads the results, comments directly on the code with specific fixes, and automatically corrects style violations. To do this, Opus 4.5 needed to understand Kieran’s specific setup, identify what was slowing things down, and write automation that works in production—the kind of infrastructure work that usually needs constant supervision to ensure that the AI hasn’t made any mistakes or stopped working all together.
Opus 4.5 reviews new code like a diligent teammate—flagging security risks and performance issues before changes go live in the product. (Screenshot courtesy of Kieran.)
The meta-programming skills: Kieran created four Claude Skills—custom instruction sets that extend Claude’s capabilities with specialized knowledge or workflows—in one session. One studied David Heinemeier Hansson‘s codebase (he created the web framework Ruby on Rails) to extract his coding patterns. Another encoded developer Andrew Kane‘s principles for writing great Ruby gems—reusable code packages that developers share with each other. This is “meta-work”—having the model study how expert programmers work, then encode those patterns so other developers can learn from them. Opus 4.5 is the best we’ve seen at this.
Design iteration: Better with each pass
While Anthropic touted Opus 4.5’s more efficient code and cleaner architecture, the company didn’t mention anything about design. That’s where Opus 4.5 surprised us.
Kieran tested this by asking the model to iterate on a user experience design 20 times, using a specific pattern: “Look at it, find two things to improve, make those changes, look at it again.” Then repeat.
Previous models would start to lose the thread on what was important after three or four passes—changing a button color back and forth, or tweaking spacing without a clear vision of what “better” means. They’d make lateral moves instead of forward progress. Opus 4.5 maintained a coherent sense of improvement across all 20 iterations: Each pass built on the last, moving the design forward rather than sideways.
LLM Evals is where Kieran tests the AI on sample reviews to see whether it correctly calls them positive, negative, or neutral. (Screenshot courtesy of Kieran.)
Final version:
The instructions Opus 4.5 wrote for the AI inside Cora to follow when it reads customer reviews and decides if they’re positive, negative, or neutral. (Screenshot courtesy of Kieran.)
Kieran’s prompting structure—incremental, focused changes with repeated evaluation—seems to work particularly well with how Opus 4.5 approaches refinement. But even with good prompting, previous models would eventually start spinning their wheels. Opus 4.5 doesn’t.
Notice the range on display here: building apps from scratch, making behind-the-scenes systems work better, and judging what looks good in a design. Previous Claude models would struggle to maintain quality across this many concurrent threads—context would blur, or the model would lose track of which project it was working on. Opus 4.5 held the thread on all of them.
Writing: Great prose, but questionable judgment
When we tested Opus 4 in May, we loved it for coding, but what really impressed us was its writing taste. The model didn’t care about your feelings (in a good way), and it kept multiple writing principles in mind even when buried in long prompts. That critical edge made Opus 4 our go-to for editorial work—until Sonnet 4.5 arrived on the scene, that is.
Opus 4.5 has lost some of that magic touch. On a mechanical and stylistic level, the prose is great. But the agreeableness that makes Opus 4.5 excellent at confident code execution—shipping without second-guessing—makes it a weaker creative collaborator. Let’s dig into why:
Editing: Too lenient
The value of an AI editor is more than catching typos. It identifies structural problems, buried ledes, missing theses, and the gap between what a piece is conveying and what it could be conveying. You want a model that tells you your draft is structured poorly when it’s structured poorly. A model that calls it “pretty solid” to avoid conflict isn’t helping you.
To test Opus 4.5’s editing chops, Katie ran a rough draft of a potential Working Overtime piece through Every’s AI Editor using three models: Sonnet 4.5, GPT-5.1 Thinking, and Opus 4.5. The AI Editor is a set of custom instructions and context documents that, when plugged into a project in Claude or ChatGPT, prompt that project to review a draft article against Every’s editorial standards—our voice, structure, and quality bar. A good editing model, armed with the context we’ve provided, should internalize those standards and push the writer toward them.
The three models delivered radically different assessments of the same draft. (One caveat: ChatGPT has a shorter word limit on custom instructions than Claude, so GPT-5.1 worked with condensed editing guidelines.)
Sonnet 4.5 delivered a bracing verdict: The piece is cute, but its most interesting points are buried at the bottom, it’s missing the thesis, and it spends 30 percent too much time on the relationship metaphor. It called for a complete structural overhaul.
Sonnet 4.5 doesn’t mince words: Cute, but the content is backwards. (Screenshot courtesy of Katie Parrott.)
GPT-5.1 Thinking took a similar stance, flagging that the thesis was missing and should be moved higher—a strong, actionable edit that aligned with what the piece needed.
The GPT-5.1 version of our editor pushes for a clear thesis and promise to the reader sooner in the introduction. (Screenshot courtesy of Katie.)
Opus 4.5 called the same draft “pretty solid” with only “polish-level” fixes needed. It flagged two correlative constructions and a couple of terms that needed defining, then moved on. It was fine leaving the thesis implicit—which, according to Every’s editorial standards, it should not have been.
Opus 4.5 gives Katie’s draft a pass with just a few cosmetic suggestions. (Screenshot courtesy of Katie.)
You can really see Opus 4.5 lose the plot when you look at line edits. Sonnet 4.5 flagged 47 issues across the draft—passive voice, hedging language like “just” and “actually,” unsubstantiated claims, AI-isms, structural redundancies. GPT-5.1 Thinking didn’t tally its fixes, but it still caught the usual suspects: weak verbs, vague qualifiers, claims that needed evidence. Opus 4.5 flagged seven. There’s no world in which that draft only had seven things worth flagging. The model was letting Katie off easy.
Opus 4.5 thinks the draft is good to go with only seven fixes. We disagree. (Screenshot courtesy of Katie.)
Longform drafting: Sometimes misses the point
The challenge with AI-assisted longform writing is getting the model to understand why something matters to the writer, then reflect that understanding in prose that feels genuinely human. A model that captures the what but misses the why produces content that reads like a summary, not a story.
Katie put Opus 4.5 through an interview-based writing process, where the model asks questions one at a time to extract the information it needs—context, anecdotes, opinions, evidence—then synthesizes that material into a draft. This workflow is designed to produce writing that sounds like the person being interviewed, not like AI.
In a blind taste test, Katie asked the Every team to compare a section written by Opus 4.5 against the same section written by GPT-5.1, using identical source material. The team overwhelmingly preferred GPT-5.1’s version.
A portion of the essay Katie wrote with assistance from GPT-5.1. (Screenshot courtesy of Katie.)
The same section of the essay, this time written with Opus 4.5. (Screenshot courtesy: Katie.)
In Opus 4.5’s defense, the differences are minor: It included in a bit more detail than we can reasonably expect a reader to be interested in, and favored paragraphs where it could be argued that bullet points better serve the content. Both issues could be cleaned up with a quick editing pass. As far as the tics that give AI writing away—the “not X, but Y” constructions, the overreliance on rhetorical questions, the sets of three—it seems that Opus 4.5 is relatively free of all of them.
Shortform drafting: Opus 4.5 wins
Promotional writing for platforms like X and LinkedIn is one of the highest-leverage applications of AI writing, but it’s deceptively tricky to get right. It requires both comprehension—can the model identify what matters in a piece?—and craft—can it compress that into punchy, platform-appropriate copy that stops the scroll?
Katie asked all three models to summarize the five most important points from Every’s Gemini 3 Vibe Check and produce a promotional tweet based on those takeaways.
Opus 4.5 produced the strongest copy of the three:
Sonnet 4.5 commits a cardinal sin of AI writing—”the result?”—while producing promotional copy for X. (Screenshot courtesy of Katie.)
Claude Opus 4.5’s take on promotional copy is clean and natural, but missing a call to action. (Screenshot courtesy of Katie.)
GPT-5.1 Thinking’s take on the request for X copy is heavy on emojis. (Screenshot courtesy of Katie.)
Opus 4.5’s version is punchy, specific, and captures the essential tension of the Vibe Check. The prose is tighter than Sonnet’s (no “The result?” construction), and it avoids the emoji-heavy formatting that makes GPT-5.1’s version feel like it was written by a social media manager circa 2017.
One quibble: Opus 4.5 forgot to include a call to action. Both Sonnet and GPT-5.1 ended with prompts to click through. Opus 4.5’s tweet is a statement, not an invitation—which limits its effectiveness as promotional copy, even if the writing itself is stronger. But that’s easy to fix.
AI Diplomacy: Strong but stubborn
AI Diplomacy tests how models strategize, adapt, and handle conflicting priorities when competing against other AI agents in a reimagined version of the classic strategy game. It’s our benchmark for seeing how models behave under pressure.
Opus 4.5 performs well in absolute terms—it even won a game against Gemini 3, GPT 5.1, and xAI’s Grok 4.1, making it the first Claude model to pull off a victory against that field. But it still sits relatively low on the leaderboard, behind Gemini 3 and o3, and tends to finish last more often than not.
Opus 4.5 comes in at #5 overall in the Diplomacy benchmark and #2 for humor. (Courtesy of Alex Duffy.)
What’s interesting is how Opus 4.5 plays—and loses.
The betrayal paradox: Opus 4.5’s betrayed its allies 66 percent of the time—the highest of any Claude model yet, and fifth-highest across all models we’ve tested. When you give it aggressive prompts, it can convince itself that betrayal is necessary within the game’s logic. That’s progress: Previous Claude models struggled to justify strategic backstabbing even when explicitly told to play aggressively.
But there’s a catch: Opus 4.5 doesn’t expect others to betray it. The model is more willing to stab you in the back but simultaneously more trusting that you won’t do the same. In Diplomacy, that’s a losing combination—you need both the willingness to betray and the paranoia to see it coming.
How Opus 4.5 plays: Across dozens of games, a clear personality emerged:
More verbose than Gemini 3 Pro or Grok 4.1

More honest than GPT-5.1 (similar to Gemini’s transparency)

More relationship-focused than any other model

Very transparent—sometimes to its own detriment

When Opus 4.5 loses, it’s often because it over-discloses its intentions or pivots to defense too late. It telegraphs its moves in a way that skilled opponents exploit. The model has better strategic coherence than Grok but worse than Gemini—it thinks through the game properly but broadcasts what it’s thinking.
The steerability gap: Most models show significant gains when you craft prompts carefully. Opus 4.5 responds to better optimized instructions, but its performance does not improve as dramatically as GPT-5 or Gemini 3.
The pattern is consistent with what we’ve seen in other tests: Opus 4.5 feels distinctly Claude-like, with the same characteristic stubbornness. It’s pre-baked with strong opinions about how it should behave, which gives it less flexibility when you need it to adapt its play style.That’s a double-edged sword. If Anthropic has baked in the right behaviors—and for coding, they largely have—you get consistent, high-quality output without needing to prompt engineer extensively. But if you need the model to behave differently for a specific use case, you’ll find yourself fighting against its defaults more than with competitors.
The takeaway: Opus 4.5 is a strong strategic player that can win when conditions align, but it comes with Claude’s characteristic stubbornness and a tendency toward over-disclosure. If you need a model that adapts precisely to unusual instructions or plays close to the vest, you might find Gemini 3 or GPT-5 more responsive. But if you want something that performs well without extensive prompt crafting—and you value transparency over deception—Opus 4.5’s opinionated defaults might be what you’re looking for.
The bigger picture: A coding breakthrough, with tradeoffs
Opus 4.5 represents a bet on what AI models should optimize for—and where that bet succeeds and where it struggles is revealing.
The model’s strength in coding is undeniable. Opus 4.5 holds the thread across complex flows, course-corrects when needed, and executes with the confidence of a senior engineer who knows what they’re building. This is the vibe coding breakthrough we’ve been waiting for.
For Every’s workflows, the verdict is split by use case. Kieran and Dan are switching to Opus 4.5 for coding in Claude Code—it’s their new daily driver, no question. Katie is sticking with Sonnet 4.5 for editorial work, where the critical edge still matters more than prose quality. Writers focused on short-form content—tweets, headlines, promotional copy—might find Opus 4.5 an upgrade. But anyone who needs an AI editor to push back and make their work better should look elsewhere.
We’re entering an era where model personality matters as much as raw capability. Opus 4.5’s stubbornness is a feature for some use cases and a bug for others. As models get more opinionated, choosing the right one for your workflow requires understanding how they prefer to work—and whether you can change their mind when you need them to work differently.
And just because we could, we asked Google’s Nano Banana to make some cartoons based on our assessment of Opus 4.5. (We’ll let you decide if they are funny or not.)
Nano Banana/Every illustration.
Nano Banana/Every illustration.
Katie Parrott is a staff writer and AI editorial lead at Every. You can read more of her work in her newsletter.
Dan Shipper is the cofounder and CEO of Every, where he writes the Chain of Thought column and hosts the podcast AI & I. You can follow him on X at @danshipper and on LinkedIn.
Kieran Klaassen is the general manager of Cora, Every’s email product. Follow him on X at @kieranklaassen or on LinkedIn, and Every on X at @every and on LinkedIn.
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