# Designing agentic loops

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-10-02T18:01:07.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/designing-agentic-loops

In this newsletter:
Designing agentic loops
Plus 2 links and 1 quotation and 1 TIL and 3 notes
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Designing agentic loops [ https://substack.com/redirect/47db483e-5230-43d8-83ee-a66b868dd61f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-09-30
Coding agents like Anthropic’s Claude Code [ https://substack.com/redirect/56802472-3fac-4973-8afc-58fac1f24d7c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and OpenAI’s Codex CLI [ https://substack.com/redirect/330a198d-f4a0-4171-90c9-b051ca63b4d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] represent a genuine step change in how useful LLMs can be for producing working code. These agents can now directly exercise the code they are writing, correct errors, dig through existing implementation details, and even run experiments to find effective code solutions to problems.
As is so often the case with modern AI, there is a great deal of depth involved in unlocking the full potential of these new tools.
A critical new skill to develop is designing agentic loops.
One way to think about coding agents is that they are brute force tools for finding solutions to coding problems. If you can reduce your problem to a clear goal and a set of tools that can iterate towards that goal a coding agent can often brute force its way to an effective solution.
My preferred definition of an LLM agent is something that runs tools in a loop to achieve a goal [ https://substack.com/redirect/be2f5456-390a-49a2-a82d-2162ab78b0e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The art of using them well is to carefully design the tools and loop for them to use.
The joy of YOLO mode [ https://substack.com/redirect/13e6a0ab-5132-4816-98b1-0b810c45296e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Picking the right tools for the loop [ https://substack.com/redirect/3619ef3d-49d3-4291-8745-6c7166a16b75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Issuing tightly scoped credentials [ https://substack.com/redirect/7eff2791-c78e-46d1-9183-be12b0bd9ca2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
When to design an agentic loop [ https://substack.com/redirect/bc025db4-9d60-4ae2-9989-2491eb069bd2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
This is still a very fresh area [ https://substack.com/redirect/86d0ba9c-7909-4fb7-8b1e-0a587c5f69e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The joy of YOLO mode
Agents are inherently dangerous - they can make poor decisions or fall victim to malicious prompt injection attacks [ https://substack.com/redirect/87267c55-59ec-4739-baae-a925c2913704?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], either of which can result in harmful results from tool calls. Since the most powerful coding agent tool is “run this command in the shell” a rogue agent can do anything that you could do by running a command yourself.
To quote Solomon Hykes [ https://substack.com/redirect/6119d31c-6137-413d-8fe1-39ab75c53c3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
An AI agent is an LLM wrecking its environment in a loop.
Coding agents like Claude Code counter this by defaulting to asking you for approval of almost every command that they run.
This is kind of tedious, but more importantly, it dramatically reduces their effectiveness at solving problems through brute force.
Each of these tools provides its own version of what I like to call YOLO mode, where everything gets approved by default.
This is so dangerous, but it’s also key to getting the most productive results!
Here are three key risks to consider from unattended YOLO mode.
Bad shell commands deleting or mangling things you care about.
Exfiltration attacks where something steals files or data visible to the agent - source code or secrets held in environment variables are particularly vulnerable here.
Attacks that use your machine as a proxy to attack another target - for DDoS or to disguise the source of other hacking attacks.
If you want to run YOLO mode anyway, you have a few options:
Run your agent in a secure sandbox that restricts the files and secrets it can access and the network connections it can make.
Use someone else’s computer. That way if your agent goes rogue, there’s only so much damage they can do, including wasting someone else’s CPU cycles.
Take a risk! Try to avoid exposing it to potential sources of malicious instructions and hope you catch any mistakes before they cause any damage.
Most people choose option 3.
Despite the existence of container escapes [ https://substack.com/redirect/6bd5efeb-8422-474d-99b3-650d40d556a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I think option 1 using Docker or the new Apple container tool [ https://substack.com/redirect/afb1c190-202f-4728-8af2-c334a996eb2c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a reasonable risk to accept for most people.
Option 2 is my favorite. I like to use GitHub Codespaces [ https://substack.com/redirect/c44543bc-a739-461a-9bb1-3ad825a00825?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for this - it provides a full container environment on-demand that’s accessible through your browser and has a generous free tier too. If anything goes wrong it’s a Microsoft Azure machine somewhere that’s burning CPU and the worst that can happen is code you checked out into the environment might be exfiltrated by an attacker, or bad code might be pushed to the attached GitHub repository.
There are plenty of other agent-like tools that run code on other people’s computers. Code Interpreter [ https://substack.com/redirect/ab19c16a-29e3-4dcc-a12c-d369ef870d7d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] mode in both ChatGPT and Claude [ https://substack.com/redirect/f3a15fee-4a0a-4936-8055-a87e8d9e50ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] can go a surprisingly long way here. I’ve also had a lot of success (ab)using OpenAI’s Codex Cloud [ https://substack.com/redirect/6aa5f733-a5ba-4822-a897-529fb1c02388?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Coding agents themselves implement various levels of sandboxing, but so far I’ve not seen convincing enough documentation of these to trust them.
Update: It turns out Anthropic have their own documentation on Safe YOLO mode [ https://substack.com/redirect/ce1b95c8-c2d8-41ec-8c91-b9ded4b85f3e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Claude Code which says:
Letting Claude run arbitrary commands is risky and can result in data loss, system corruption, or even data exfiltration (e.g., via prompt injection attacks). To minimize these risks, use --dangerously-skip-permissions in a container without internet access. You can follow this reference implementation [ https://substack.com/redirect/e4194fdf-dec7-4e29-aaab-726fd617bbba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using Docker Dev Containers.
Locking internet access down to a list of trusted hosts [ https://substack.com/redirect/6f1339cb-b34a-4da3-8753-de2bfe005588?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a great way to prevent exfiltration attacks from stealing your private source code.
Picking the right tools for the loop
Now that we’ve found a safe (enough) way to run in YOLO mode, the next step is to decide which tools we need to make available to the coding agent.
You can bring MCP [ https://substack.com/redirect/4e699638-6f78-44ee-8d07-e493ea1f873c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] into the mix at this point, but I find it’s usually more productive to think in terms of shell commands instead. Coding agents are really good at running shell commands!
If your environment allows them the necessary network access, they can also pull down additional packages from NPM and PyPI and similar. Ensuring your agent runs in an environment where random package installs don’t break things on your main computer is an important consideration as well!
Rather than leaning on MCP, I like to create an AGENTS.md [ https://substack.com/redirect/433735f2-ad38-48d9-92d6-b0d5e3866aff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (or equivalent) file with details of packages I think they may need to use.
For a project that involved taking screenshots of various websites I installed my own shot-scraper [ https://substack.com/redirect/1a6bb6ad-6b11-4476-9cbc-444d581a8012?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CLI tool and dropped the following in AGENTS.md:
To take a screenshot, run:

shot-scraper http://www.example.com/ -w 800 -o example.jpg
Just that one example is enough for the agent to guess how to swap out the URL and filename for other screenshots.
Good LLMs already know how to use a bewildering array of existing tools. If you say “use playwright python [ https://substack.com/redirect/b6269629-7ad4-407e-a799-8040e3bded1c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]“ or “use ffmpeg” most models will use those effectively - and since they’re running in a loop they can usually recover from mistakes they make at first and figure out the right incantations without extra guidance.
Issuing tightly scoped credentials
In addition to exposing the right commands, we also need to consider what credentials we should expose to those commands.
Ideally we wouldn’t need any credentials at all - plenty of work can be done without signing into anything or providing an API key - but certain problems will require authenticated access.
This is a deep topic in itself, but I have two key recommendations here:
Try to provide credentials to test or staging environments where any damage can be well contained.
If a credential can spend money, set a tight budget limit.
I’ll use an example to illustrate. A while ago I was investigating slow cold start times for a scale-to-zero application I was running on Fly.io [ https://substack.com/redirect/d4857a3b-6d6d-488f-bb78-ec0705221a32?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I realized I could work a lot faster if I gave Claude Code the ability to directly edit Dockerfiles, deploy them to a Fly account and measure how long they took to launch.
Fly allows you to create organizations, and you can set a budget limit for those organizations and issue a Fly API key that can only create or modify apps within that organization...
So I created a dedicated organization for just this one investigation, set a $5 budget, issued an API key and set Claude Code loose on it!
In that particular case the results weren’t useful enough to describe in more detail, but this was the project where I first realized that “designing an agentic loop” was an important skill to develop.
When to design an agentic loop
Not every problem responds well to this pattern of working. The thing to look out for here are problems with clear success criteria where finding a good solution is likely to involve (potentially slightly tedious) trial and error.
Any time you find yourself thinking “ugh, I’m going to have to try a lot of variations here” is a strong signal that an agentic loop might be worth trying!
A few examples:
Debugging: a test is failing and you need to investigate the root cause. Coding agents that can already run your tests can likely do this without any extra setup.
Performance optimization: this SQL query is too slow, would adding an index help? Have your agent benchmark the query and then add and drop indexes (in an isolated development environment!) to measure their impact.
Upgrading dependencies: you’ve fallen behind on a bunch of dependency upgrades? If your test suite is solid an agentic loop can upgrade them all for you and make any minor updates needed to reflect breaking changes. Make sure a copy of the relevant release notes is available, or that the agent knows where to find them itself.
Optimizing container sizes: Docker container feeling uncomfortably large? Have your agent try different base images and iterate on the Dockerfile to try to shrink it, while keeping the tests passing.
A common theme in all of these is automated tests. The value you can get from coding agents and other LLM coding tools is massively amplified by a good, cleanly passing test suite. Thankfully LLMs are great for accelerating the process of putting one of those together, if you don’t have one yet.
This is still a very fresh area
Designing agentic loops is a very new skill - Claude Code was first released [ https://substack.com/redirect/1b6e2cec-baec-42e8-9ad4-f28a5ca0aa2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in just February 2025!
I’m hoping that giving it a clear name can help us have productive conversations about it. There’s so much more to figure out about how to use these tools as effectively as possible.
TIL 2025-09-30 Error 153 Video player configuration error on YouTube embeds [ https://substack.com/redirect/3ca37bfb-4a68-42e3-a401-6f2b4c8b0c6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I recently noticed that almost every YouTube video on my blog [ https://substack.com/redirect/252ef132-21ad-4d05-8789-507849dd9bd9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was displaying the same mysterious error message: …
Note 2025-09-30 [ https://substack.com/redirect/362fb128-8eb3-473f-9cfe-064317347e6a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Having watched this morning’s Sora 2 introduction video [ https://substack.com/redirect/a1ca68b4-dd7b-4517-9a6b-809048dac728?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the most notable feature (aside from audio generation - original Sora was silent, Google’s Veo 3 supported audio in May 2025) looks to be what OpenAI are calling “cameos” - the ability to easily capture a video version of yourself or your friends and then use them as characters in generated videos.
My guess is that they are leaning into this based on the incredible success of ChatGPT image generation in March [ https://substack.com/redirect/15f9b7a4-a913-47be-8d44-1b266d0ef49d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - possibly the most successful product launch of all time, signing up 100 million new users in just the first week after release.
The driving factor for that success? People love being able to create personalized images of themselves, their friends and their family members.
Google saw a similar effect with their Nano Banana image generation model. Gemini VP Josh Woodward tweeted [ https://substack.com/redirect/22c16c3f-8ee2-422e-abae-f9c82f1621f6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on 24th September:
🍌 @GeminiApp just passed 5 billion images in less than a month.
Sora 2 cameos looks to me like an attempt to capture that same viral magic but for short-form videos, not images.
Update: I got an invite. Here’s “simonw performing opera on stage at the royal albert hall in a very fine purple suit with crows flapping around his head dramatically standing in front of a night orchestrion” [ https://substack.com/redirect/56842bbd-9578-440d-bca6-783cd03d9bfa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (it was meant to be a mighty orchestrion but I had a typo.)
Note 2025-10-01 [ https://substack.com/redirect/0cbb0311-365f-4ae6-86d1-fc1e097a6055?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I just sent out the September edition of my sponsors-only monthly newsletter [ https://substack.com/redirect/391d29f5-8872-40b3-a150-fa0d2fb58521?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. If you are a sponsor (or if you start a sponsorship now) you can access a copy here [ https://substack.com/redirect/0c45bfb6-f242-44a5-9168-71c19cf63785?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The sections this month are:
Best model for code? GPT-5-Codex... then Claude 4.5 Sonnet
I’ve grudgingly accepted a definition for “agent”
GPT-5 Research Goblin and Google AI Mode
Claude has Code Interpreter now
The lethal trifecta in the Economist
Other significant model releases
Notable AI success stories
Video models are zero-shot learners and reasoners
Tools I’m using at the moment
Other bits and pieces
Here’s a copy of the August newsletter [ https://substack.com/redirect/909943ee-5a28-4b1f-ad41-2749d15c9922?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a preview of what you’ll get. Pay $10/month to stay a month ahead of the free copy!
Note 2025-10-01 [ https://substack.com/redirect/775711da-cbfc-444c-9e62-685792992bd7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Two new models from Chinese AI labs in the past few days. I tried them both out using llm-openrouter [ https://substack.com/redirect/aa351633-47f1-4ae6-b53b-8d32a7d58b2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
DeepSeek-V3.2-Exp from DeepSeek. Announcement [ https://substack.com/redirect/7d3ba55a-c0d5-4399-95be-b5dba8d02987?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Tech Report [ https://substack.com/redirect/b55343b8-1df5-48f3-8830-ee9c9af82a6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Hugging Face [ https://substack.com/redirect/fd97eff0-7fa5-4ea6-b73c-d1082ca4bbd6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (690GB, MIT license).
As an intermediate step toward our next-generation architecture, V3.2-Exp builds upon V3.1-Terminus by introducing DeepSeek Sparse Attention—a sparse attention mechanism designed to explore and validate optimizations for training and inference efficiency in long-context scenarios.
This one felt very slow when I accessed it via OpenRouter - I probably got routed to one of the slower providers [ https://substack.com/redirect/aedebf01-6a7a-4863-b7b6-66827352162c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here’s the pelican [ https://substack.com/redirect/342c4780-f2f7-4d2a-a545-3043a9ef18d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
GLM-4.6 from Z.ai. Announcement [ https://substack.com/redirect/1e7b46b6-3cd4-4f69-b185-4fabce932225?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Hugging Face [ https://substack.com/redirect/59f10178-6246-4010-b8b9-4b79b8c893a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (714GB, MIT license).
The context window has been expanded from 128K to 200K tokens [...] higher scores on code benchmarks [...] GLM-4.6 exhibits stronger performance in tool using and search-based agents.
Here’s the pelican [ https://substack.com/redirect/c6efa62a-9672-4dad-8521-2bc520e2e8f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for that:
Link 2025-10-01 aavetis/PRarena [ https://substack.com/redirect/e2a46421-f0c4-4ad2-bc8a-5e78cb1889b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Albert Avetisian runs this repository on GitHub which uses the Github Search API to track the number of PRs that can be credited to a collection of different coding agents. The repo runs this collect_data.py script [ https://substack.com/redirect/b747462d-dba0-4991-b28d-11ee8bc260d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] every three hours using GitHub Actions [ https://substack.com/redirect/02a2dc30-6aca-4b07-b0df-22a4121f0fc4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to collect the data, then updates the PR Arena site [ https://substack.com/redirect/0d9451ed-ef12-46d9-bd8c-01ccb25eb799?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with a visual leaderboard.
The result is this neat chart showing adoption of different agents over time, along with their PR success rate:
I found this today while trying to pull off the exact same trick myself! I got as far as creating the following table before finding Albert’s work and abandoning my own project.
(Those “earliest” dates are a little questionable, I tried to filter out false positives and find the oldest PR that appeared to really be from the agent in question.)
It looks like OpenAI’s Codex Cloud is massively ahead of the competition right now in terms of numbers of PRs both opened and merged on GitHub.
Update: To clarify, these numbers are for the category of autonomous coding agents - those systems where you assign a cloud-based agent a task or issue and the output is a PR against your repository. They do not (and cannot) capture the popularity of many forms of AI tooling that don’t result in an easily identifiable pull request.
Claude Code for example will be dramatically under-counted here because its version of an autonomous coding agent comes in the form of a somewhat obscure GitHub Actions workflow buried in the documentation [ https://substack.com/redirect/3a4efcbe-ea9a-47c3-9b4f-2add57677a01?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
quote 2025-10-02
When attention is being appropriated, producers need to weigh the costs and benefits of the transaction. To assess whether the appropriation of attention is net-positive, it’s useful to distinguish between extractive and non-extractive contributions. Extractive contributions are those where the marginal cost of reviewing and merging that contribution is greater than the marginal benefit to the project’s producers. In the case of a code contribution, it might be a pull request that’s too complex or unwieldy to review, given the potential upside
Nadia Eghbal [ https://substack.com/redirect/1555b372-8b5b-4f5a-a6e2-e0ebb5cdfa45?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Working in Public, via the draft LLVM AI tools policy
Link 2025-10-02 Daniel Stenberg’s note on AI assisted curl bug reports [ https://substack.com/redirect/567a3768-9e9b-4b22-885b-315c63ed6dc6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Curl maintainer Daniel Stenberg on Mastodon:
Joshua Rogers sent us a massive list of potential issues in #curl that he found using his set of AI assisted tools. Code analyzer style nits all over. Mostly smaller bugs, but still bugs and there could be one or two actual security flaws in there. Actually truly awesome findings.
I have already landed 22(!) bugfixes thanks to this, and I have over twice that amount of issues left to go through. Wade through perhaps.
Credited “Reported in Joshua’s sarif data” if you want to look for yourself
I searched for is:pr Joshua sarif data is:closed in the curl GitHub repository and found 49 completed PRs so far [ https://substack.com/redirect/ac572989-a856-4686-8fca-bc9f27d7432e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Joshua’s own post about this: Hacking with AI SASTs: An overview of ‘AI Security Engineers’ / ‘LLM Security Scanners’ for Penetration Testers and Security Teams [ https://substack.com/redirect/8876a417-e633-45d6-8591-d8d8f9a77ca0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The accompanying presentation PDF [ https://substack.com/redirect/b4432b50-d1aa-4633-8939-4987057cd0fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] includes screenshots of some of the tools he used, which included Almanax, Amplify Security, Corgea, Gecko Security, and ZeroPath. Here’s his vendor summary:
This result is especially notable because Daniel has been outspoken about the deluge of junk AI-assisted reports on “security issues” that curl has received in the past. In May this year [ https://substack.com/redirect/2d45bb2a-cfa8-4738-b6a1-16be79bb35d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], concerning HackerOne:
We now ban every reporter INSTANTLY who submits reports we deem AI slop. A threshold has been reached. We are effectively being DDoSed. If we could, we would charge them for this waste of our time.
He also wrote about this in January 2024 [ https://substack.com/redirect/c5aa70ba-ad24-4d59-8e5e-c8df75d74400?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], where he included this note:
I do however suspect that if you just add an ever so tiny (intelligent) human check to the mix, the use and outcome of any such tools will become so much better. I suspect that will be true for a long time into the future as well.
This is yet another illustration of how much more interesting these tools are when experienced professionals use them to augment their existing skills.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOelV4TWprd01URXNJbWxoZENJNk1UYzFPVFF5T0RFd05Td2laWGh3SWpveE56a3dPVFkwTVRBMUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuNW1DVXVVMXh2NHFSOGlnQzZQV0o2TUg4ZDUtNWNMUl8wZXllM1lpVi1nRSIsInAiOjE3NTEyOTAxMSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzU5NDI4MTA1LCJleHAiOjIwNzUwMDQxMDUsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.kWhGFFaklnylBOFKTr-AW7Zo9NeVZj2ThBZdoYBt-kU?
