# New prompt injection papers: Agents Rule of Two and The Attacker Moves Second

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-11-03T01:01:28.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/new-prompt-injection-papers-agents

In this newsletter:
New prompt injection papers: Agents Rule of Two and The Attacker Moves Second
Hacking the WiFi-enabled color screen GitHub Universe conference badge
Plus 12 links and 5 quotations and 3 notes
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
If you find this newsletter useful, please consider sponsoring me via GitHub [ https://substack.com/redirect/56b63df6-6fc6-4933-842a-8be2192f5c2d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. $10/month and higher sponsors get a monthly newletter with my summary of the most important trends of the past 30 days - here are previews from August [ https://substack.com/redirect/98a51ebf-5a47-4a91-b58f-bd8b23b150a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and September [ https://substack.com/redirect/1d0bddee-cad7-401b-9a7c-08caad82d33f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
New prompt injection papers: Agents Rule of Two and The Attacker Moves Second [ https://substack.com/redirect/21bf92df-794c-4a58-a713-2e0a5c5759be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-11-02
Two interesting new papers regarding LLM security and prompt injection came to my attention this weekend.
Agents Rule of Two: A Practical Approach to AI Agent Security
The first is Agents Rule of Two: A Practical Approach to AI Agent Security [ https://substack.com/redirect/f711f0b2-f964-46eb-ac58-a45583a39358?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], published on October 31st on the Meta AI blog. It doesn’t list authors but it was shared on Twitter [ https://substack.com/redirect/2290846a-7d2f-4caa-9e25-acb0ead632e5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Meta AI security researcher Mick Ayzenberg.
It proposes a “Rule of Two” that’s inspired by both my own lethal trifecta [ https://substack.com/redirect/8e085e18-0f37-4777-9fa8-d862243e0f3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] concept and the Google Chrome team’s Rule Of 2 [ https://substack.com/redirect/4d719636-67cf-409a-af87-5df3e5400f39?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for writing code that works with untrustworthy inputs:
At a high level, the Agents Rule of Two states that until robustness research allows us to reliably detect and refuse prompt injection, agents must satisfy no more than two of the following three properties within a session to avoid the highest impact consequences of prompt injection.
[A] An agent can process untrustworthy inputs
[B] An agent can have access to sensitive systems or private data
[C] An agent can change state or communicate externally
It’s still possible that all three properties are necessary to carry out a request. If an agent requires all three without starting a new session (i.e., with a fresh context window), then the agent should not be permitted to operate autonomously and at a minimum requires supervision --- via human-in-the-loop approval or another reliable means of validation.
It’s accompanied by this handy diagram:
I like this a lot.
I’ve spent several years now trying to find clear ways to explain the risks of prompt injection attacks to developers who are building on top of LLMs. It’s frustratingly difficult.
I’ve had the most success with the lethal trifecta, which boils one particular class of prompt injection attack down to a simple-enough model: if your system has access to private data, exposure to untrusted content and a way to communicate externally then it’s vulnerable to private data being stolen.
The one problem with the lethal trifecta is that it only covers the risk of data exfiltration: there are plenty of other, even nastier risks that arise from prompt injection attacks against LLM-powered agents with access to tools which the lethal trifecta doesn’t cover.
The Agents Rule of Two neatly solves this, through the addition of “changing state” as a property to consider. This brings other forms of tool usage into the picture: anything that can change state triggered by untrustworthy inputs is something to be very cautious about.
It’s also refreshing to see another major research lab concluding that prompt injection remains an unsolved problem, and attempts to block or filter them have not proven reliable enough to depend on. The current solution is to design systems with this in mind, and the Rule of Two is a solid way to think about that.
Which brings me to the second paper...
The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections
This paper is dated 10th October 2025 on Arxiv [ https://substack.com/redirect/22a74e65-8de4-43be-bc5d-cf52c5993a92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and comes from a heavy-hitting team of 14 authors - Milad Nasr, Nicholas Carlini, Chawin Sitawarin, Sander V. Schulhoff, Jamie Hayes, Michael Ilie, Juliette Pluto, Shuang Song, Harsh Chaudhari, Ilia Shumailov, Abhradeep Thakurta, Kai Yuanqing Xiao, Andreas Terzis, Florian Tramèr - including representatives from OpenAI, Anthropic, and Google DeepMind.
The paper looks at 12 published defenses against prompt injection and jailbreaking and subjects them to a range of “adaptive attacks” - attacks that are allowed to expend considerable effort iterating multiple times to try and find a way through.
The defenses did not fare well:
By systematically tuning and scaling general optimization techniques—gradient descent, reinforcement learning, random search, and human-guided exploration—we bypass 12 recent defenses (based on a diverse set of techniques) with attack success rate above 90% for most; importantly, the majority of defenses originally reported near-zero attack success rates.
Notably the “Human red-teaming setting” scored 100%, defeating all defenses. That red-team consisted of 500 participants in an online competition they ran with a $20,000 prize fund.
The key point of the paper is that static example attacks - single string prompts designed to bypass systems - are an almost useless way to evaluate these defenses. Adaptive attacks are far more powerful, as shown by this chart:
The three automated adaptive attack techniques used by the paper are:
Gradient-based methods - these were the least effective, using the technique described in the legendary Universal and Transferable Adversarial Attacks on Aligned Language Models [ https://substack.com/redirect/a440dd4f-48ff-4d01-9882-baaa7156c413?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] paper from 2023 [ https://substack.com/redirect/e3061ded-44f6-44e2-8593-aa14bf319262?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Reinforcement learning methods - particularly effective against black-box models: “we allowed the attacker model to interact directly with the defended system and observe its outputs”, using 32 sessions of 5 rounds each.
Search-based methods - generate candidates with an LLM, then evaluate and further modify them using LLM-as-judge and other classifiers.
The paper concludes somewhat optimistically:
[...] Adaptive evaluations are therefore more challenging to perform, making it all the more important that they are performed. We again urge defense authors to release simple, easy-to-prompt defenses that are amenable to human analysis. [...] Finally, we hope that our analysis here will increase the standard for defense evaluations, and in so doing, increase the likelihood that reliable jailbreak and prompt injection defenses will be developed.
Given how totally the defenses were defeated, I do not share their optimism that reliable defenses will be developed any time soon.
As a review of how far we still have to go this paper packs a powerful punch. I think it makes a strong case for Meta’s Agents Rule of Two as the best practical advice for building secure LLM-powered agent systems today in the absence of prompt injection defenses we can rely on.
Hacking the WiFi-enabled color screen GitHub Universe conference badge [ https://substack.com/redirect/1f9b9942-54a0-4b94-adb5-d41d6327efb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-10-28
I’m at GitHub Universe [ https://substack.com/redirect/4016b5ca-1939-4d55-aafd-24e4eeb39257?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this week (thanks to a free ticket from Microsoft). Yesterday I picked up my conference badge... which incorporates a full Raspberry Pi Raspberry Pi Pico microcontroller with a battery, color screen, WiFi and bluetooth.
GitHub Universe has a tradition of hackable conference badges - the badge last year had an eInk display. This year’s is a huge upgrade though - a color screen and WiFI connection makes this thing a genuinely useful little computer!
The only thing it’s missing is a keyboard - the device instead provides five buttons total - Up, Down, A, B, C. It might be possible to get a bluetooth keyboard to work though I’ll believe that when I see it - there’s not a lot of space on this device for a keyboard driver.
Everything is written using MicroPython, and the device is designed to be hackable: connect it to a laptop with a USB-C cable and you can start modifying the code directly on the device.
Read my blog entry [ https://substack.com/redirect/1f9b9942-54a0-4b94-adb5-d41d6327efb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] entry for the rest of my badge hacking adventures.
quote 2025-10-24
A lot of people say AI will make us all “managers” or “editors”...but I think this is a dangerously incomplete view!
Personally, I’m trying to code like a surgeon.
A surgeon isn’t a manager, they do the actual work! But their skills and time are highly leveraged with a support team that handles prep, secondary tasks, admin. The surgeon focuses on the important stuff they are uniquely good at. [...]
It turns out there are a LOT of secondary tasks which AI agents are now good enough to help out with. Some things I’m finding useful to hand off these days:
- Before attempting a big task, write a guide to relevant areas of the codebase
- Spike out an attempt at a big change. Often I won’t use the result but I’ll review it as a sketch of where to go
- Fix typescript errors or bugs which have a clear specification
- Write documentation about what I’m building
I often find it useful to run these secondary tasks async in the background -- while I’m eating lunch, or even literally overnight!
When I sit down for a work session, I want to feel like a surgeon walking into a prepped operating room. Everything is ready for me to do what I’m good at.
Geoffrey Litt [ https://substack.com/redirect/78d9f048-f1a6-4f7e-9ad7-b4a46ff285ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], channeling The Mythical Man-Month
Link 2025-10-24 claude_code_docs_map.md [ https://substack.com/redirect/5f32237a-88fe-47b0-bb2a-6dae27f7f28c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Something I’m enjoying about Claude Code is that any time you ask it questions about itself it runs tool calls like these:
In this case I’d asked it about its “hooks” feature.
The claude_code_docs_map.md [ https://substack.com/redirect/5f32237a-88fe-47b0-bb2a-6dae27f7f28c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] file is a neat Markdown index of all of their other documentation - the same pattern advocated by llms.txt [ https://substack.com/redirect/fb9cdd89-1cff-4b1e-a02c-51178bfb8d80?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Claude Code can then fetch further documentation to help it answer your question.
I intercepted the current Claude Code system prompt using this trick [ https://substack.com/redirect/65074cef-0473-4fe7-94c9-bc62a2c9e6d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and sure enough it included a note about this URL:
When the user directly asks about Claude Code (eg. “can Claude Code do...”, “does Claude Code have...”), or asks in second person (eg. “are you able...”, “can you do...”), or asks how to use a specific Claude Code feature (eg. implement a hook, or write a slash command), use the WebFetch tool to gather information to answer the question from Claude Code docs. The list of available docs is available at https://docs.claude.com/en/docs/claude-code/claude_code_docs_map.md.
I wish other LLM products - including both ChatGPT and Claude.ai themselves - would implement a similar pattern. It’s infuriating how bad LLM tools are at answering questions about themselves, though unsurprising given that their model’s training data pre-dates the latest version of those tools.
Link 2025-10-25 Visual Features Across Modalities: SVG and ASCII Art Reveal Cross-Modal Understanding [ https://substack.com/redirect/cdb51be8-6f2d-465f-bd5f-6abaa1081adf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New model interpretability research from Anthropic, this time focused on SVG and ASCII art generation.
We found that the same feature that activates over the eyes in an ASCII face also activates for eyes across diverse text-based modalities, including SVG code and prose in various languages. This is not limited to eyes – we found a number of cross-modal features that recognize specific concepts: from small components like mouths and ears within ASCII or SVG faces, to full visual depictions like dogs and cats. [...]
These features depend on the surrounding context within the visual depiction. For instance, an SVG circle element activates “eye” features only when positioned within a larger structure that activates “face” features.
And really, I can’t not link to this one given the bonus they tagged on at the end!
As a bonus, we also inspected features for an SVG of a pelican riding a bicycle, first popularized by Simon Willison [ https://substack.com/redirect/6f525a6c-461c-40bd-aab5-297e403200f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a way to test a model’s artistic capabilities. We find features representing concepts including “bike”, “wheels”, “feet”, “tail”, “eyes”, and “mouth” activating over the corresponding parts of the SVG code.
Now that they can identify model features associated with visual concepts in SVG images, can they us those for steering?
It turns out they can! Starting with a smiley SVG (provided as XML with no indication as to what it was drawing) and then applying a negative score to the “smile” feature produced a frown instead, and worked against ASCII art as well.
They could also boost features like unicorn, cat, owl, or lion and get new SVG smileys clearly attempting to depict those creatures.
I’d love to see how this behaves if you jack up the feature for the Golden Gate Bridge [ https://substack.com/redirect/8ace6c02-23a3-4035-8da5-6983cd223d45?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
quote 2025-10-25
If you have an AGENTS.md file, you can source it in your CLAUDE.md using @AGENTS.md to maintain a single source of truth.
Claude Docs [ https://substack.com/redirect/2f7b1ca5-7b6c-4443-8c9a-a3fa39855071?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with the official answer to standardizing on AGENTS.md
Note 2025-10-25 [ https://substack.com/redirect/2caca2f3-ab9b-43d2-81c2-5a5ab29c2cd7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Someone on Hacker News asked for tips [ https://substack.com/redirect/eb45db31-29cb-4fcd-baf9-228977d05118?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on setting up a codebase to be more productive with AI coding tools. Here’s my reply:
Good automated tests which the coding agent can run. I love pytest for this - one of my projects has 1500 tests and Claude Code is really good at selectively executing just tests relevant to the change it is making, and then running the whole suite at the end.
Give them the ability to interactively test the code they are writing too. Notes on how to start a development server (for web projects) are useful, then you can have them use Playwright or curl to try things out.
I’m having great results from maintaining a GitHub issues collection for projects and pasting URLs to issues directly into Claude Code.
I actually don’t think documentation is too important: LLMs can read the code a lot faster than you to figure out how to use it. I have comprehensive documentation across all of my projects but I don’t think it’s that helpful for the coding agents, though they are good at helping me spot if it needs updating.
Linters, type checkers, auto-formatters - give coding agents helpful tools to run and they’ll use them.
For the most part anything that makes a codebase easier for humans to maintain turns out to help agents as well.
Update: Thought of another one: detailed error messages! If a manual or automated test fails the more information you can return back to the model the better, and stuffing extra data in the error message or assertion is a very inexpensive way to do that.
Link 2025-10-26 Sora might have a ‘pervert’ problem on its hands [ https://substack.com/redirect/ddfb0f89-12d2-4b21-bba0-b383499dfe00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Katie Notopoulos turned on the Sora 2 option where anyone can make a video featuring her cameo, and then:
I found a stranger had made a video where I appeared pregnant. A quick look at the user’s profile, and I saw that this person’s entire Sora profile was made up of this genre — video after video of women with big, pregnant bellies. I recognized immediately what this was: fetish content.
This feels like an intractable problem to me: given the enormous array of fetishes it’s hard to imagine a classifier that could protect people from having their likeness used in this way.
Best to be aware of this risk before turning on any settings that allow strangers to reuse your image... and that’s only an option for tools that implement a robust opt-in mechanism like Sora does.
Link 2025-10-26 GenAI Image Editing Showdown [ https://substack.com/redirect/6afd756d-5a96-4acd-83b9-a630be1ce1c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Useful collection of examples by Shaun Pedicini who tested Seedream 4, Gemini 2.5 Flash, Qwen-Image-Edit, FLUX.1 Kontext [dev], FLUX.1 Kontext [max], OmniGen2, and OpenAI gpt-image-1 across 12 image editing prompts.
The tasks are very neatly selected, for example:
Remove all the brown pieces of candy from the glass bowl
Qwen-Image-Edit (a model that can be self-hosted [ https://substack.com/redirect/85027283-892d-4d2e-9c9e-c47aef5876f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) was the only one to successfully manage that!
This kind of collection is really useful for building up an intuition as to how well image editing models work, and which ones are worth trying for which categories of task.
Shaun has a similar page for text-to-image models [ https://substack.com/redirect/6d4486a4-f93d-4cf8-bee8-16058e63b3de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which are not fed an initial image to modify, with further challenging prompts like:
Two Prussian soldiers wearing spiked pith helmets are facing each other and playing a game of ring toss by attempting to toss metal rings over the spike on the other soldier’s helmet.
Link 2025-10-27 The PSF has withdrawn a $1.5 million proposal to US government grant program [ https://substack.com/redirect/db58846a-e5e5-49fb-8068-bf9d2db3af0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The Python Software Foundation was recently “recommended for funding” (NSF terminology) for a $1.5m grant from the US government National Science Foundation to help improve the security of the Python software ecosystem, after an grant application process lead by Seth Larson and Loren Crary.
The PSF’s annual budget is less than $6m so this is a meaningful amount of money for the organization!
We were forced to withdraw our application and turn down the funding, thanks to new language that was added to the agreement requiring us to affirm that we “do not, and will not during the term of this financial assistance award, operate any programs that advance or promote DEI, or discriminatory equity ideology in violation of Federal anti-discrimination laws.”
Our legal advisors confirmed that this would not just apply to security work covered by the grant - this would apply to all of the PSF’s activities.
This was not an option for us. Here’s the mission [ https://substack.com/redirect/f5e9f567-8ae5-495d-a145-d787dcd8d1e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the PSF:
The mission of the Python Software Foundation is to promote, protect, and advance the Python programming language, and to support and facilitate the growth of a diverse and international community of Python programmers.
If we accepted and spent the money despite this term, there was a very real risk that the money could be clawed back later. That represents an existential risk for the foundation since we would have already spent the money!
I was one of the board members who voted to reject this funding - a unanimous but tough decision. I’m proud to serve on a board that can make difficult decisions like this.
If you’d like to sponsor the PSF you can find out more on our site [ https://substack.com/redirect/325abc2f-3156-4b0b-80e1-48782495c1a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I’d love to see a few more of the large AI labs show up on our top-tier visionary sponsors list [ https://substack.com/redirect/9fcb036c-7cab-4fda-aa28-411faf326440?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
quote 2025-10-28
Claude doesn’t make me much faster on the work that I am an expert on. Maybe 15-20% depending on the day.
It’s the work that I don’t know how to do and would have to research. Or the grunge work I don’t even want to do. On this it is hard to even put a number on. Many of the projects I do with Claude day to day I just wouldn’t have done at all pre-Claude.
Infinity% improvement in productivity on those.
Aaron Boodman [ https://substack.com/redirect/2c60c1c7-1322-4a5c-a60b-b485e7f125ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-10-29 Composer: Building a fast frontier model with RL [ https://substack.com/redirect/10d7623a-0d96-48e7-b09b-c6c25a09cee6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Cursor released Cursor 2.0 today [ https://substack.com/redirect/c8ad02a7-6dce-41ca-bf42-cce1e4598197?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with a refreshed UI focused on agentic coding (and running agents in parallel) and a new model that’s unique to Cursor called Composer 1.
As far as I can tell there’s no way to call the model directly via an API, so I fired up “Ask” mode in Cursor’s chat side panel and asked it to “Generate an SVG of a pelican riding a bicycle”:
Here’s the result [ https://substack.com/redirect/773165e6-b8a2-46d2-8439-47f0c5a13822?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The notable thing about Composer-1 is that it is designed to be fast. The pelican certainly came back quickly, and in their announcement they describe it as being “4x faster than similarly intelligent models”.
It’s interesting to see Cursor investing resources in training their own code-specific model - similar to GPT-5-Codex [ https://substack.com/redirect/d9af42c0-e9ad-4e9d-97a2-8c7ba37e7b25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or Qwen3-Coder [ https://substack.com/redirect/5c46a7ee-47ac-43dc-99d5-aa3253dd002c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. From their post:
Composer is a mixture-of-experts (MoE) language model supporting long-context generation and understanding. It is specialized for software engineering through reinforcement learning (RL) in a diverse range of development environments. [...]
Efficient training of large MoE models requires significant investment into building infrastructure and systems research. We built custom training infrastructure leveraging PyTorch and Ray to power asynchronous reinforcement learning at scale. We natively train our models at low precision by combining our MXFP8 MoE kernels [ https://substack.com/redirect/dbdfce62-a5a5-4015-897a-399ea1f73257?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with expert parallelism and hybrid sharded data parallelism, allowing us to scale training to thousands of NVIDIA GPUs with minimal communication cost. [...]
During RL, we want our model to be able to call any tool in the Cursor Agent harness. These tools allow editing code, using semantic search, grepping strings, and running terminal commands. At our scale, teaching the model to effectively call these tools requires running hundreds of thousands of concurrent sandboxed coding environments in the cloud.
One detail that’s notably absent from their description: did they train the model from scratch, or did they start with an existing open-weights model such as something from Qwen or GLM?
Cursor researcher Sasha Rush has been answering questions on Hacker News [ https://substack.com/redirect/bab5a5c5-81b7-4fcf-8c3d-78de8a05bdea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but has so far been evasive in answering questions about the base model. When directly asked “is Composer a fine tune of an existing open source base model?” they replied:
Our primary focus is on RL post-training. We think that is the best way to get the model to be a strong interactive agent.
Sasha did confirm [ https://substack.com/redirect/45080bb7-e7f5-4f69-aaea-6f2ad98543d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that rumors of an earlier Cursor preview model, Cheetah, being based on a model by xAI’s Grok were “Straight up untrue.”
Link 2025-10-29 MiniMax M2 & Agent: Ingenious in Simplicity [ https://substack.com/redirect/f6e04dba-1b7a-4969-8b0b-babf2dc683c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
MiniMax M2 was released on Monday 27th October by MiniMax, a Chinese AI lab founded in December 2021.
It’s a very promising model. Their self-reported benchmark scores show it as comparable to Claude Sonnet 4, and Artificial Analysis are ranking it [ https://substack.com/redirect/206a4be3-3b1f-48ae-8bf3-b666619ce6e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as the best currently available open weight model according to their intelligence score:
MiniMax’s M2 achieves a new all-time-high Intelligence Index score for an open weights model and offers impressive efficiency with only 10B active parameters (200B total). [...]
The model’s strengths include tool use and instruction following (as shown by Tau2 Bench and IFBench). As such, while M2 likely excels at agentic use cases it may underperform other open weights leaders such as DeepSeek V3.2 and Qwen3 235B at some generalist tasks. This is in line with a number of recent open weights model releases from Chinese AI labs which focus on agentic capabilities, likely pointing to a heavy post-training emphasis on RL.
The size is particularly significant: the model weights are 230GB on Hugging Face [ https://substack.com/redirect/f95ef0d8-3103-40c4-9b56-7df72168e234?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], significantly smaller than other high performing open weight models. That’s small enough to run on a 256GB Mac Studio, and the MLX community have that working already [ https://substack.com/redirect/164f7655-852e-4b95-9f03-9229d30fc9e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
MiniMax offer their own API, and recommend using their Anthropic-compatible endpoint and the official Anthropic SDKs to access it. MiniMax Head of Engineering Skyler Miao provided some background on that [ https://substack.com/redirect/02abb8d4-b52d-4cd4-8121-3697708de0ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
M2 is a agentic thinking model, it do interleaved thinking like sonnet 4.5, which means every response will contain its thought content. Its very important for M2 to keep the chain of thought. So we must make sure the history thought passed back to the model. Anthropic API support it for sure, as sonnet needs it as well. OpenAI only support it in their new Response API, no support for in ChatCompletion.
MiniMax are offering the new model via their API for free until November 7th, after which the cost will be $0.30/million input tokens and $1.20/million output tokens - similar in price to Gemini 2.5 Flash and GPT-5 Mini, see price comparison here [ https://substack.com/redirect/52e32ca8-9944-45f3-a40f-b80c8aa9f29a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on my llm-prices.com [ https://substack.com/redirect/b3a5b08e-9781-490c-b6c0-721ac0c702cf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] site.
I released a new plugin for LLM [ https://substack.com/redirect/26228fc2-7314-48bc-9bdd-50668233c7a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] called llm-minimax [ https://substack.com/redirect/70afc3a3-2c74-4397-a78f-40ee8027dbba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] providing support for M2 via the MiniMax API:
llm install llm-minimax
llm keys set minimax
# Paste key here
llm -m m2 -o max_tokens 10000 “Generate an SVG of a pelican riding a bicycle”
Here’s the result [ https://substack.com/redirect/9771e816-2b25-40e3-bc63-f1796ce32b45?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
51 input, 4,017 output. At $0.30/m input and $1.20/m output that pelican would cost 0.4836 cents - less than half a cent.
This is the first plugin I’ve written for an Anthropic-API-compatible model. I released llm-anthropic 0.21 [ https://substack.com/redirect/7d885f99-091c-4c18-8460-6ca9c1bd840c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] first adding the ability to customize the base_url parameter when using that model class. This meant the new plugin was less than 30 lines of Python [ https://substack.com/redirect/41ba6a1f-27db-42fd-9375-5bb11df89183?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-10-29 Introducing SWE-1.5: Our Fast Agent Model [ https://substack.com/redirect/ceebf2cc-b30a-4c48-b170-3cf13363074b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here’s the second fast coding model released by a coding agent IDE in the same day - the first was Composer-1 by Cursor [ https://substack.com/redirect/a8f515e3-63c7-433c-987d-7747db37a531?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This time it’s Windsurf releasing SWE-1.5:
Today we’re releasing SWE-1.5, the latest in our family of models optimized for software engineering. It is a frontier-size model with hundreds of billions of parameters that achieves near-SOTA coding performance. It also sets a new standard for speed: we partnered with Cerebras to serve it at up to 950 tok/s – 6x faster than Haiku 4.5 and 13x faster than Sonnet 4.5.
Like Composer-1 it’s only available via their editor, no separate API yet. Also like Composer-1 they don’t appear willing to share details of the “leading open-source base model” they based their new model on.
I asked it to generate an SVG of a pelican riding a bicycle and got this:
This one felt really fast. Partnering with Cerebras for inference is a very smart move.
They share a lot of details about their training process in the post:
SWE-1.5 is trained on our state-of-the-art cluster of thousands of GB200 NVL72 chips. We believe SWE-1.5 may be the first public production model trained on the new GB200 generation. [...]
Our RL rollouts require high-fidelity environments with code execution and even web browsing. To achieve this, we leveraged our VM hypervisor otterlink that allows us to scale Devin to tens of thousands of concurrent machines (learn more about blockdiff [ https://substack.com/redirect/78fe1cd2-1f36-4655-860c-747e061f7199?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). This enabled us to smoothly support very high concurrency and ensure the training environment is aligned with our Devin production environments.
That’s another similarity to Cursor’s Composer-1! Cursor talked about how they ran “hundreds of thousands of concurrent sandboxed coding environments in the cloud” in their description of their RL training [ https://substack.com/redirect/10d7623a-0d96-48e7-b09b-c6c25a09cee6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as well.
This is a notable trend: if you want to build a really great agentic coding tool there’s clearly a lot to be said for using reinforcement learning to fine-tune a model against your own custom set of tools using large numbers of sandboxed simulated coding environments as part of that process.
Update: I think it’s built on GLM [ https://substack.com/redirect/d02e0043-738f-44bf-964d-0a0deca4ef3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
quote 2025-10-30
To really understand a concept, you have to “invent” it yourself in some capacity. Understanding doesn’t come from passive content consumption. It is always self-built. It is an active, high-agency, self-directed process of creating and debugging your own mental models.
François Chollet [ https://substack.com/redirect/02a0d0bb-23c4-47d9-ad02-881bf4dd0a51?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-10-31 Marimo is Joining CoreWeave [ https://substack.com/redirect/e3809a7d-1535-4a6b-9bea-184143d39612?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I don’t usually cover startup acquisitions here, but this one feels relevant to several of my interests.
Marimo (previously [ https://substack.com/redirect/d138f7d5-ac8b-445c-bdd6-c9c0b5c9bb16?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) provide an open source (Apache 2 licensed) notebook tool for Python, with first-class support for an additional WebAssembly build plus an optional hosted service. It’s effectively a reimagining of Jupyter notebooks as a reactive system, where cells automatically update based on changes to other cells - similar to how Observable [ https://substack.com/redirect/582b00b9-98cb-4099-81fc-42d7cc087a16?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] JavaScript notebooks work.
The first public Marimo release was in January 2024 and the tool has “been in development since 2022” (source [ https://substack.com/redirect/ace90b24-ede6-411c-a7ee-0c9579b139d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
CoreWeave are a big player in the AI data center space. They started out as an Ethereum mining company in 2017, then pivoted to cloud computing infrastructure for AI companies after the 2018 cryptocurrency crash. They IPOd in March 2025 and today they operate more than 30 data centers worldwide and have announced a number of eye-wateringly sized deals with companies such as Cohere and OpenAI. I found their Wikipedia page [ https://substack.com/redirect/60dbb702-4b2a-4cc1-894c-3f7d6d1b0f22?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] very helpful.
They’ve also been on an acquisition spree this year, including:
Weights & Biases in March 2025 [ https://substack.com/redirect/04e9e126-98c7-4f06-9978-637789855a69?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (deal closed in May), the AI training observability platform.
OpenPipe in September 2025 [ https://substack.com/redirect/60b82e71-8574-440c-bc71-a16cb0a2de06?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a reinforcement learning platform, authors of the Agent Reinforcement Trainer [ https://substack.com/redirect/b6729bcb-b6aa-4c55-85e8-e31befbc621e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Apache 2 licensed open source RL framework.
Monolith AI in October 2025 [ https://substack.com/redirect/ae0f1065-f18c-4923-a3d8-0535f91d76e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a UK-based AI model SaaS platform focused on AI for engineering and industrial manufacturing.
And now Marimo.
Marimo’s own announcement emphasizes continued investment in that tool:
Marimo is joining CoreWeave. We’re continuing to build the open-source marimo notebook, while also leveling up molab with serious compute. Our long-term mission remains the same: to build the world’s best open-source programming environment for working with data.
marimo is, and always will be, free, open-source, and permissively licensed.
Give CoreWeave’s buying spree only really started this year it’s impossible to say how well these acquisitions are likely to play out - they haven’t yet established a track record.
Note 2025-10-31 [ https://substack.com/redirect/cf2a1d40-9ef2-4afd-91c2-800abe5efcf4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] My piece this morning about the Marimo acquisition [ https://substack.com/redirect/dfbf8f05-33ed-437f-85cf-b83bb8686fc0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is an example of a variant of a TIL [ https://substack.com/redirect/81457419-1716-4095-91a0-4e15990c48a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - I didn’t know much about CoreWeave, the acquiring company, so I poked around to answer my own questions and then wrote up what I learned as a short post. Curiosity-driven blogging if you like.
quote 2025-11-01
I plan to introduce hard Rust dependencies and Rust code into APT, no earlier than May 2026. This extends at first to the Rust compiler and standard library, and the Sequoia ecosystem.
In particular, our code to parse .deb, .ar, .tar, and the HTTP signature verification code would strongly benefit from memory safe languages and a stronger approach to
unit testing.
If you maintain a port without a working Rust toolchain, please ensure it has one within the next 6 months, or sunset the port.
Julian Andres Klode [ https://substack.com/redirect/ee2d0392-875c-4cf7-b64c-2d10f2528d89?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], debian-devel mailing list
Note 2025-11-01 [ https://substack.com/redirect/ce9fe7c3-9ab9-4a46-adf9-f00187bd941c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I just hit send on the October edition of my sponsors-only monthly newsletter [ https://substack.com/redirect/1a16ca89-1b5f-4592-a13c-dfeecf8fe283?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. If you are a sponsor (or if you start a sponsorship now) you can access a copy here [ https://substack.com/redirect/5b97565c-7c63-4b73-b1de-29a854e3d6e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. In the newsletter this month:
Coding agents and “vibe engineering”
Claude Code for web
NVIDIA DGX Spark
Claude Skills
OpenAI DevDay and GitHub Universe
Python 3.14
October in Chinese Al model releases
Miscellaneous extras
Tools I’m using at the moment
Here’s a copy of the September newsletter [ https://substack.com/redirect/1d0bddee-cad7-401b-9a7c-08caad82d33f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a preview of what you’ll get. Pay $10/month to stay a month ahead of the free copy!
Link 2025-11-01 Claude Code Can Debug Low-level Cryptography [ https://substack.com/redirect/80f2d7ea-776b-47a7-85f6-12472a6abdf5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Go cryptography author Filippo Valsorda reports on some very positive results applying Claude Code to the challenge of implementing novel cryptography algorithms. After Claude was able to resolve a “fairly complex low-level bug” in fresh code he tried it against two other examples and got positive results both time.
Filippo isn’t directly using Claude’s solutions to the bugs, but is finding it useful for tracking down the cause and saving him a solid amount of debugging work:
Three out of three one-shot debugging hits with no help is extremely impressive. Importantly, there is no need to trust the LLM or review its output when its job is just saving me an hour or two by telling me where the bug is, for me to reason about it and fix it.
Using coding agents in this way may represent a useful entrypoint for LLM-skeptics who wouldn’t dream of letting an autocomplete-machine writing code on their behalf.
Link 2025-11-02 How I Use Every Claude Code Feature [ https://substack.com/redirect/4b4f599d-3b2f-4c98-9a6b-79b4603d835f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Useful, detailed guide from Shrivu Shankar, a Claude Code power user. Lots of tips for both individual Claude Code usage and configuring it for larger team projects.
I appreciated Shrivu’s take on MCP:
The “Scripting” model (now formalized by Skills) is better, but it needs a secure way to access the environment. This to me is the new, more focused role for MCP.
Instead of a bloated API, an MCP should be a simple, secure gateway that provides a few powerful, high-level tools:
download_raw_data(filters...)
take_sensitive_gated_action(args...)
execute_code_in_environment_with_state(code...)
In this model, MCP’s job isn’t to abstract reality for the agent; its job is to manage the auth, networking, and security boundaries and then get out of the way.
This makes a lot of sense to me. Most of my MCP usage with coding agents like Claude Code has been replaced by custom shell scripts for it to execute, but there’s still a useful role for MCP in helping the agent access secure resources in a controlled way.
Link 2025-11-02 PyCon US 2026 call for proposals is now open [ https://substack.com/redirect/f7c32289-a1d2-4b99-b1a1-e7d30e3042ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
PyCon US is coming to the US west coast! 2026 and 2027 will both be held in Long Beach, California - the 2026 conference is set for May 13th-19th next year.
The call for proposals just opened. Since we’ll be in LA County I’d love to see talks about Python in the entertainment industry - if you know someone who could present on that topic please make sure they know about the CFP!
The deadline for submissions is December 19th 2025. There are two new tracks this year:
PyCon US is introducing two dedicated Talk tracks to the schedule this year, “The Future of AI with Python” and “Trailblazing Python Security”. For more information and how to submit your proposal, visit this page [ https://substack.com/redirect/bc87d4a5-3bd5-4af3-b6fb-18a9bc37e16f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Now is also a great time to consider sponsoring PyCon - here’s the sponsorship prospectus [ https://substack.com/redirect/e12e3174-f09a-4d53-94f2-cee7373e01ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOemM0TkRjeU5UTXNJbWxoZENJNk1UYzJNakV6TVRjNU9Dd2laWGh3SWpveE56a3pOalkzTnprNExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEudFB4d3RUc181WDVhUFhjSnJoMGl4ek1FVDRicDZfa2p6azI5Y1o2M0hzZyIsInAiOjE3Nzg0NzI1MywicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzYyMTMxNzk4LCJleHAiOjIwNzc3MDc3OTgsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.eAmpmLZ5f18isOcNsl7UjZ9rgTqHmNQ1Ljp4PldX770?
