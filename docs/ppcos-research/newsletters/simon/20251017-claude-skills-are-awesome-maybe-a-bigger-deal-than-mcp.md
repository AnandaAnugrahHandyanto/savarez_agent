# Claude Skills are awesome, maybe a bigger deal than MCP

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-10-17T23:47:01.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/claude-skills-are-awesome-maybe-a

In this newsletter:
Claude Skills are awesome, maybe a bigger deal than MCP
Plus 3 links and 5 quotations and 1 note
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Claude Skills are awesome, maybe a bigger deal than MCP [ https://substack.com/redirect/21efae57-28fb-4305-ac38-f0353e9932be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-10-16
Anthropic this morning introduced Claude Skills [ https://substack.com/redirect/e6353ce0-431b-4b46-b94f-fe1613a78448?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a new pattern for making new abilities available to their models:
Claude can now use Skills to improve how it performs specific tasks. Skills are folders that include instructions, scripts, and resources that Claude can load when needed.
Claude will only access a skill when it’s relevant to the task at hand. When used, skills make Claude better at specialized tasks like working with Excel or following your organization’s brand guidelines.
Their engineering blog has a more detailed explanation [ https://substack.com/redirect/d4d2a93e-7159-4387-8e6b-1e9fe813d306?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. There’s also a new anthropic/skills [ https://substack.com/redirect/e977811c-c6ad-4bd2-bda8-84f95203ec14?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] GitHub repo.
(I inadvertently preempted their announcement of this feature when I reverse engineered and wrote about it last Friday [ https://substack.com/redirect/54197df5-a9f5-454e-8d99-57b3a245ee58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!)
Skills are conceptually extremely simple: a skill is a Markdown file telling the model how to do something, optionally accompanied by extra documents and pre-written scripts that the model can run to help it accomplish the tasks described by the skill.
Claude’s new document creation abilities [ https://substack.com/redirect/8efd8715-5651-412e-a691-afa59f4fef0b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which accompanied their new code interpreter feature [ https://substack.com/redirect/9e846e9c-ee3b-4b5c-8476-db49efe1b25d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in September, turned out to be entirely implemented using skills. Those are now available in Anthropic’s repo [ https://substack.com/redirect/c10e16c2-1d56-449d-a548-4dae8e390481?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] covering .pdf, .docx, .xlsx, and .pptx files.
There’s one extra detail that makes this a feature, not just a bunch of files on disk. At the start of a session Claude’s various harnesses can scan all available skill files and read a short explanation for each one from the frontmatter YAML in the Markdown file. This is very token efficient: each skill only takes up a few dozen extra tokens, with the full details only loaded in should the user request a task that the skill can help solve.
Trying out the slack-gif-creator skill [ https://substack.com/redirect/342aa2b8-7be4-40e2-8245-84cd1f0951c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Skills depend on a coding environment [ https://substack.com/redirect/3413fc8b-6cac-4df4-ab0c-c5b1f4d640da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Claude Code as a General Agent [ https://substack.com/redirect/27f79fa2-7265-4694-abab-780019361c9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Skills compared to MCP [ https://substack.com/redirect/69489eab-05ff-4905-a593-9a0890a6754a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Here come the Skills [ https://substack.com/redirect/37255ac5-1e20-40a7-9219-f22359958ee6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The simplicity is the point [ https://substack.com/redirect/c4d4b7bc-e532-4057-ba03-53280ccc3b1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Trying out the slack-gif-creator skill
Here’s that metadata for an example slack-gif-creator skill [ https://substack.com/redirect/3d22059f-c37b-4baa-9830-4e1321774903?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that Anthropic published this morning:
Toolkit for creating animated GIFs optimized for Slack, with validators for size constraints and composable animation primitives. This skill applies when users request animated GIFs or emoji animations for Slack from descriptions like “make me a GIF for Slack of X doing Y”.
I just tried this skill out in the Claude mobile web app, against Sonnet 4.5. First I enabled the slack-gif-creator skill in the settings [ https://substack.com/redirect/6f23d6e8-3383-4af5-953a-5dfa51934929?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], then I prompted:
Make me a gif for slack about how Skills are way cooler than MCPs
And Claude made me this GIF [ https://substack.com/redirect/ea2b4880-4e8a-4acd-80dc-180bfd993dfa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Click to play [ https://substack.com/redirect/8b366d5d-3f7a-49af-bd6d-385d8d9e382e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (it’s almost epilepsy inducing, hence the click-to-play mechanism):
OK, this particular GIF is terrible, but the great thing about skills is that they’re very easy to iterate on to make them better.
Here are some noteworthy snippets from the Python script it wrote [ https://substack.com/redirect/c7934b7a-6155-4f3d-9482-3e0483c32429?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], comments mine:
# Start by adding the skill’s directory to the Python path
import sys
sys.path.insert(0, ‘/mnt/skills/examples/slack-gif-creator’)

from PIL import Image, ImageDraw, ImageFont
# This class lives in the core/ directory for the skill
from core.gif_builder import GIFBuilder

# ... code that builds the GIF ...

# Save it to disk:
info = builder.save(’/mnt/user-data/outputs/skills_vs_mcps.gif’,
num_colors=128,
optimize_for_emoji=False)

print(f”GIF created successfully!”)
print(f”Size: {info[’size_kb’]:.1f} KB ({info[’size_mb’]:.2f} MB)”)
print(f”Frames: {info[’frame_count’]}”)
print(f”Duration: {info[’duration_seconds’]:.1f}s”)

# Use the check_slack_size function to confirm it’s small enough for Slack:
passes, check_info = check_slack_size(’/mnt/user-data/outputs/skills_vs_mcps.gif’, is_emoji=False)
if passes:
print(”✓ Ready for Slack!”)
else:
print(f”⚠ File size: {check_info[’size_kb’]:.1f} KB (limit: {check_info[’limit_kb’]} KB)”)
This is pretty neat. Slack GIFs need to be a maximum of 2MB, so the skill includes a validation function which the model can use to check the file size. If it’s too large the model can have another go at making it smaller.
Skills depend on a coding environment
The skills mechanism is entirely dependent on the model having access to a filesystem, tools to navigate it and the ability to execute commands in that environment.
This is a common pattern for LLM tooling these days - ChatGPT Code Interpreter was the first big example of this back in early 2023 [ https://substack.com/redirect/cabe3bc2-60b1-42e5-bf31-79aa6c5db80c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and the pattern later extended to local machines via coding agent tools such as Cursor, Claude Code, Codex CLI and Gemini CLI.
This requirement is the biggest difference between skills and other previous attempts at expanding the abilities of LLMs, such as MCP and ChatGPT Plugins [ https://substack.com/redirect/4bece98c-84df-4478-9fc8-c3b6ba2a5cf7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It’s a significant dependency, but it’s somewhat bewildering how much new capability it unlocks.
The fact that skills are so powerful and simple to create is yet another argument in favor of making safe coding environments available to LLMs. The word safe there is doing a lot of work though! We really need to figure out how best to sandbox these environments such that attacks such as prompt injections are limited to an acceptable amount of damage.
Claude Code as a General Agent
Back in January I made some foolhardy predictions about AI/LLMs [ https://substack.com/redirect/f21b5dc6-7439-44c3-bb13-dcdaf4eebde7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], including that “agents” would once again fail to happen:
I think we are going to see a lot more froth about agents in 2025, but I expect the results will be a great disappointment to most of the people who are excited about this term. I expect a lot of money will be lost chasing after several different poorly defined dreams that share that name.
I was entirely wrong about that. 2025 really has been the year of “agents”, no matter which of the many conflicting definitions [ https://substack.com/redirect/2f97d6fb-2806-45c9-a3aa-7503d8d66054?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] you decide to use (I eventually settled on “tools in a loop [ https://substack.com/redirect/475d3641-24b1-4815-9a6c-4c3d7508c83f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]“).
Claude Code [ https://substack.com/redirect/12ae99ab-97f2-41d3-a2e0-419462906d12?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is, with hindsight, poorly named. It’s not purely a coding tool: it’s a tool for general computer automation. Anything you can achieve by typing commands into a computer is something that can now be automated by Claude Code. It’s best described as a general agent. Skills make this a whole lot more obvious and explicit.
I find the potential applications of this trick somewhat dizzying. Just thinking about this with my data journalism hat on: imagine a folder full of skills that covers tasks like the following:
Where to get US census data from and how to understand its structure
How to load data from different formats into SQLite or DuckDB using appropriate Python libraries
How to publish data online, as Parquet files in S3 or pushed as tables to Datasette Cloud
A skill defined by an experienced data reporter talking about how best to find the interesting stories in a new set of data
A skill that describes how to build clean, readable data visualizations using D3
Congratulations, you just built a “data journalism agent” that can discover and help publish stories against fresh drops of US census data. And you did it with a folder full of Markdown files and maybe a couple of example Python scripts.
Skills compared to MCP
Model Context Protocol [ https://substack.com/redirect/ccd2ba5f-2630-4f0a-9c48-97519dc52fce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] has attracted an enormous amount of buzz since its initial release back in November last year [ https://substack.com/redirect/b2a4bb5f-1fbd-4d38-9e92-b9dd3522219a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I like to joke that one of the reasons it took off is that every company knew they needed an “AI strategy”, and building (or announcing) an MCP implementation was an easy way to tick that box.
Over time the limitations of MCP have started to emerge. The most significant is in terms of token usage: GitHub’s official MCP on its own famously consumes tens of thousands of tokens of context, and once you’ve added a few more to that there’s precious little space left for the LLM to actually do useful work.
My own interest in MCPs has waned ever since I started taking coding agents seriously. Almost everything I might achieve with an MCP can be handled by a CLI tool instead. LLMs know how to call cli-tool --help, which means you don’t have to spend many tokens describing how to use them - the model can figure it out later when it needs to.
Skills have exactly the same advantage, only now I don’t even need to implement a new CLI tool. I can drop a Markdown file in describing how to do a task instead, adding extra scripts only if they’ll help make things more reliable or efficient.
Here come the Skills
One of the most exciting things about Skills is how easy they are to share. I expect many skills will be implemented as a single file - more sophisticated ones will be a folder with a few more.
Anthropic have Agent Skills documentation [ https://substack.com/redirect/8f5bdf54-f094-4271-b2be-993c04374692?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and a Claude Skills Cookbook [ https://substack.com/redirect/cc4fe2d1-611f-48ef-9405-6463d8daa674?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I’m already thinking through ideas of skills I might build myself, like one on how to build Datasette plugins [ https://substack.com/redirect/0ea536ea-5cfa-4367-aad0-db335b2e1275?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Something else I love about the design of skills is there is nothing at all preventing them from being used with other models.
You can grab a skills folder right now, point Codex CLI or Gemini CLI at it and say “read pdf/SKILL.md and then create me a PDF describing this project” and it will work, despite those tools and models having no baked in knowledge of the skills system.
I expect we’ll see a Cambrian explosion in Skills which will make this year’s MCP rush look pedestrian by comparison.
The simplicity is the point
I’ve seen a some push back against skills as being so simple they’re hardly a feature at all. Plenty of people have experimented with the trick of dropping extra instructions into a Markdown file and telling the coding agent to read that file before continuing with a task. AGENTS.md [ https://substack.com/redirect/8a746716-c41c-467b-b802-2e13b9125de9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a well established pattern, and that file can already include instructions to “Read PDF.md before attempting to create a PDF”.
The core simplicity of the skills design is why I’m so excited about it.
MCP is a whole protocol specification [ https://substack.com/redirect/33469cfe-a651-4c8c-a743-05f96133d565?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], covering hosts, clients, servers, resources, prompts, tools, sampling, roots, elicitation and three different transports (stdio, streamable HTTP and originally SSE).
Skills are Markdown with a tiny bit of YAML metadata and some optional scripts in whatever you can make executable in the environment. They feel a lot closer to the spirit of LLMs - throw in some text and let the model figure it out.
They outsource the hard parts to the LLM harness and the associated computer environment. Given everything we have learned about LLMs’ ability to run tools over the last couple of years I think that’s a very sensible strategy.
quote 2025-10-15
Previous system cards have reported results on an expanded version of our earlier agentic misalignment evaluation suite [ https://substack.com/redirect/561a0d20-6401-418f-aadf-470ac08225bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: three families of exotic scenarios meant to elicit the model to commit blackmail, attempt a murder, and frame someone for financial crimes. We choose not to report full results here because, similarly to Claude Sonnet 4.5, Claude Haiku 4.5 showed many clear examples of verbalized evaluation awareness on all three of the scenarios tested in this suite. Since the suite only consisted of many similar variants of three core scenarios, we expect that the model maintained high unverbalized awareness across the board, and we do not trust it to be representative of behavior in the real extreme situations the suite is meant to emulate.
Claude Haiku 4.5 System Card [ https://substack.com/redirect/1bae43a0-de52-4162-993e-491535491405?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-10-15 Introducing Claude Haiku 4.5 [ https://substack.com/redirect/ff417622-3239-4314-bc5c-5d7423a069aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic released Claude Haiku 4.5 today, the cheapest member of the Claude 4.5 family that started with Sonnet 4.5 a couple of weeks ago [ https://substack.com/redirect/8077a040-f04b-45d9-9bf2-12fd0ce76aa7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It’s priced at $1/million input tokens and $5/million output tokens, slightly more expensive than Haiku 3.5 ($0.80/$4) and a lot more expensive than the original Claude 3 Haiku ($0.25/$1.25), both of which remain available at those prices.
It’s a third of the price of Sonnet 4 and Sonnet 4.5 (both $3/$15) which is notable because Anthropic’s benchmarks put it in a similar space to that older Sonnet 4 model. As they put it:
What was recently at the frontier is now cheaper and faster. Five months ago, Claude Sonnet 4 was a state-of-the-art model. Today, Claude Haiku 4.5 gives you similar levels of coding performance but at one-third the cost and more than twice the speed.
I’ve been hoping to see Anthropic release a fast, inexpensive model that’s price competitive with the cheapest models from OpenAI and Gemini, currently $0.05/$0.40 (GPT-5-Nano) and $0.075/$0.30 (Gemini 2.0 Flash Lite). Haiku 4.5 certainly isn’t that, it looks like they’re continuing to focus squarely on the “great at code” part of the market.
The new Haiku is the first Haiku model to support reasoning. It sports a 200,000 token context window, 64,000 maximum output (up from just 8,192 for Haiku 3.5) and a “reliable knowledge cutoff” of February 2025, one month later than the January 2025 date for Sonnet 4 and 4.5 and Opus 4 and 4.1.
Something that caught my eye in the accompanying system card [ https://substack.com/redirect/1bae43a0-de52-4162-993e-491535491405?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was this note about context length:
For Claude Haiku 4.5, we trained the model to be explicitly context-aware, with precise information about how much context-window has been used. This has two effects: the model learns when and how to wrap up its answer when the limit is approaching, and the model learns to continue reasoning more persistently when the limit is further away. We found this intervention—along with others—to be effective at limiting agentic “laziness” (the phenomenon where models stop working on a problem prematurely, give incomplete answers, or cut corners on tasks).
I’ve added the new price to llm-prices.com [ https://substack.com/redirect/b27a6cd6-5be8-430a-a0fa-63b2111c2905?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], released llm-anthropic 0.20 [ https://substack.com/redirect/98dd1ec7-677c-44fb-88a7-1342d8eb38b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with the new model and updated my Haiku-from-your-webcam [ https://substack.com/redirect/3e2a4535-b686-44e7-8cbd-b589ca7bc8e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] demo (source [ https://substack.com/redirect/ce19d830-f0c9-4b29-895f-0780fdd1bf71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) to use Haiku 4.5 as well.
Here’s llm -m claude-haiku-4.5 ‘Generate an SVG of a pelican riding a bicycle’ (transcript [ https://substack.com/redirect/84370934-c5a4-4066-b0f7-e4648c5e08df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
18 input tokens and 1513 output tokens = 0.7583 cents [ https://substack.com/redirect/4bafc625-aed1-49da-a677-f83aee37ec35?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
quote 2025-10-15
While Sonnet 4.5 remains the default [in Claude Code], Haiku 4.5 now powers the Explore subagent which can rapidly gather context on your codebase to build apps even faster.
You can select Haiku 4.5 to be your default model in /model. When selected, you’ll automatically use Sonnet 4.5 in Plan mode and Haiku 4.5 for execution for smarter plans and faster results.
Catherine Wu [ https://substack.com/redirect/ca661ff2-7fd9-4161-8765-cf26deed757b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude Code PM, Anthropic
Note 2025-10-16 [ https://substack.com/redirect/8c16b9dc-4646-4b87-897f-d1e14aed8a61?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Last year the most useful exercise for getting a feel for how good LLMs were at writing code was vibe coding (before that name had even been coined) - seeing if you could create a useful small application through prompting alone.
Today I think there’s a new, more ambitious and significantly more intimidating exercise: spend a day working on real production code through prompting alone, making no manual edits yourself.
This doesn’t mean you can’t control exactly what goes into each file - you can even tell the model “update line 15 to use this instead” if you have to - but it’s a great way to get more of a feel for how well the latest coding agents can wield their edit tools.
quote 2025-10-16
Pro se litigants [people representing themselves in court without a lawyer] account for the majority of the cases in the United States where a party submitted a court filing containing AI hallucinations. In a country where legal representation is unaffordable [ https://substack.com/redirect/ed7f6aa2-91b2-471e-8db8-f7cc1b6212b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for most people, it is no wonder that pro se litigants are depending on free or low-cost AI tools. But it is a scandal that so many have been betrayed by them, to the detriment of the cases they are litigating all on their own.
Riana Pfefferkorn [ https://substack.com/redirect/dfbb255c-a863-430f-a074-66736b249b44?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], analyzing the AI Hallucination Cases [ https://substack.com/redirect/f074667c-72cd-4744-8413-12f1ea4203e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] database for CIS at Stanford Law
Link 2025-10-16 NVIDIA DGX Spark + Apple Mac Studio = 4x Faster LLM Inference with EXO 1.0 [ https://substack.com/redirect/2282acf9-c95d-4540-be8f-37c8ad078425?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
EXO Labs wired a 256GB M3 Ultra Mac Studio up to an NVIDIA DGX Spark and got a 2.8x performance boost serving Llama-3.1 8B (FP16) with an 8,192 token prompt.
Their detailed explanation taught me a lot about LLM performance.
There are two key steps in executing a prompt. The first is the prefill phase that reads the incoming prompt and builds a KV cache for each of the transformer layers in the model. This is compute-bound as it needs to process every token in the input and perform large matrix multiplications across all of the layers to initialize the model’s internal state.
Performance in the prefill stage influences TTFT - time‑to‑first‑token.
The second step is the decode phase, which generates the output one token at a time. This part is limited by memory bandwidth - there’s less arithmetic, but each token needs to consider the entire KV cache.
Decode performance influences TPS - tokens per second.
EXO noted that the Spark has 100 TFLOPS but only 273GB/s of memory bandwidth, making it a better fit for prefill. The M3 Ultra has 26 TFLOPS but 819GB/s of memory bandwidth, making it ideal for the decode phase.
They run prefill on the Spark, streaming the KV cache to the Mac over 10Gb Ethernet. They can start streaming earlier layers while the later layers are still being calculated. Then the Mac runs the decode phase, returning tokens faster than if the Spark had run the full process end-to-end.
quote 2025-10-16
Skills actually came out of a prototype I built demonstrating that Claude Code is a general-purpose agent :-)
It was a natural conclusion once we realized that bash + filesystem were all we needed
Barry Zhang [ https://substack.com/redirect/868b0936-fe07-4af8-a34b-4be5dc9de31e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Anthropic
Link 2025-10-17 Should form labels be wrapped or separate? [ https://substack.com/redirect/cb91ba56-baba-42fc-906a-f3f6980baf04?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
James Edwards notes that wrapping a form input in a label event like this has a significant downside:
Name
It turns out both Dragon Naturally Speaking for Windows and Voice Control for macOS and iOS fail to understand this relationship!
You need to use the explicit  syntax to ensure those screen readers correctly understand the relationship between label and form field. You can still nest the input inside the label if you like:
Name

quote 2025-10-17
Using UUIDv7 is generally discouraged for security when the primary key is exposed to end users in external-facing applications or APIs. The main issue is that UUIDv7 incorporates a 48-bit Unix timestamp as its most significant part, meaning the identifier itself leaks the record’s creation time.
This leakage is primarily a privacy concern. Attackers can use the timing data as metadata for de-anonymization or account correlation, potentially revealing activity patterns or growth rates within an organization.
Alexander Fridriksson and Jay Miller [ https://substack.com/redirect/4807d3b5-d8f3-4eb1-9373-5c05b49165f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Exploring PostgreSQL 18’s new UUIDv7 support
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOelkwTlRrM05EWXNJbWxoZENJNk1UYzJNRGMwTkRnek1Td2laWGh3SWpveE56a3lNamd3T0RNeExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuaU1QZXdKczBDLXV5Y3FmRm9NMzJIbmdPRWx3NHpaaUJCTU41a0F4WkZnVSIsInAiOjE3NjQ1OTc0NiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzYwNzQ0ODMxLCJleHAiOjIwNzYzMjA4MzEsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.G0n5NHyCGNzlr9dh3-jThQ8GF6opiVp7sKd0x-yePuE?
