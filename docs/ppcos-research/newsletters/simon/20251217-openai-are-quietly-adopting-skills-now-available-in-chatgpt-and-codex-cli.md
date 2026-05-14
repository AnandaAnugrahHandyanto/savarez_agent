# OpenAI are quietly adopting skills, now available in ChatGPT and Codex CLI

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-12-17T02:44:15.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/openai-are-quietly-adopting-skills

In this newsletter:
OpenAI are quietly adopting skills, now available in ChatGPT and Codex CLI
JustHTML is a fascinating example of vibe engineering in action
I ported JustHTML from Python to JavaScript with Codex CLI and GPT-5.2 in 4.5 hours
Plus 8 links and 4 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
If you find this newsletter useful, please consider sponsoring me via GitHub [ https://substack.com/redirect/da705df6-f161-4b7b-87a7-d9ccf18397c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. $10/month and higher sponsors get a monthly newsletter with my summary of the most important trends of the past 30 days - here are previews from September [ https://substack.com/redirect/4677d9d9-fcb0-4913-8fa0-ce06679d55a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and October [ https://substack.com/redirect/fbcceb25-107c-4308-8c1e-7d400e9fe96b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
OpenAI are quietly adopting skills, now available in ChatGPT and Codex CLI [ https://substack.com/redirect/05b1e396-096a-463d-a452-f4be340320b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-12-12
One of the things that most excited me about Anthropic’s new Skills mechanism [ https://substack.com/redirect/dbf2659a-4e93-4f6b-bc50-991de2bb67c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back in October is how easy it looked for other platforms to implement. A skill is just a folder with a Markdown file and some optional extra resources and scripts, so any LLM tool with the ability to navigate and read from a filesystem should be capable of using them. It turns out OpenAI are doing exactly that, with skills support quietly showing up in both their Codex CLI tool and now also in ChatGPT itself.
Skills in ChatGPT
I learned about this from Elias Judin [ https://substack.com/redirect/af423f43-8e91-44b1-9ae2-1b7e6637d41f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this morning. It turns out the Code Interpreter feature of ChatGPT now has a new /home/oai/skills folder which you can access simply by prompting:
Create a zip file of /home/oai/skills
I tried that myself [ https://substack.com/redirect/ed257805-da6f-40e7-af1f-c2e51e5327a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and got back this zip file [ https://substack.com/redirect/cdbc037c-7623-480e-9138-2dac5f25f447?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here’s a UI for exploring its content [ https://substack.com/redirect/334c8219-0443-486f-9e54-14d9f728a54b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (more about that tool [ https://substack.com/redirect/542f27c9-c87c-4422-a6e6-9bac4ce2bd70?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
So far they cover spreadsheets, docx and PDFs. Interestingly their chosen approach for PDFs and documents is to convert them to rendered per-page PNGs and then pass those through their vision-enabled GPT models, presumably to maintain information from layout and graphics that would be lost if they just ran text extraction.
Elias shared copies in a GitHub repo [ https://substack.com/redirect/5cf3bfdf-f2e3-40b6-9cc6-c0c24bda7c4b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. They look very similar to Anthropic’s implementation of the same kind of idea, currently published in their anthropics/skills [ https://substack.com/redirect/ff9cbe39-01ea-43d6-9435-9285232dc104?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repository.
I tried it out by prompting:
Create a PDF with a summary of the rimu tree situation right now and what it means for kakapo breeding season
Sure enough, GPT-5.2 Thinking started with:
Reading skill.md for PDF creation guidelines
Then:
Searching rimu mast and Kākāpō 2025 breeding status
It took just over eleven minutes [ https://substack.com/redirect/5ab2f9fb-4ca6-4857-881a-b87220d256b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to produce this PDF [ https://substack.com/redirect/be5c4c65-61aa-4447-aef0-d58fbe32ce2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which was long enough that I had Claude Code for web build me a custom PDF viewing tool [ https://substack.com/redirect/7f351aa9-5e1a-4f1d-b2da-7efe9a3cd249?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] while I waited.
Here’s ChatGPT’s PDF in that tool [ https://substack.com/redirect/0cca4abd-e098-4361-bf57-5657b2da25ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
(I am very excited about Kākāpō breeding season this year [ https://substack.com/redirect/48f507ce-9a7f-4493-819b-ff7943432c5a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
The reason it took so long is that it was fastidious about looking at and tweaking its own work. I appreciated that at one point it tried rendering the PDF and noticed that the macrons in kākāpō were not supported by the chosen font, so it switched to something else:
Skills in Codex CLI
Meanwhile, two weeks ago OpenAI’s open source Codex CLI tool landed a PR titled feat: experimental support for skills.md [ https://substack.com/redirect/18df90c8-aecc-422c-8410-6b34b1b7af86?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The most recent docs for that are in docs/skills.md [ https://substack.com/redirect/43f67e66-66e9-4dfe-b46c-fad3a92bd46c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The documentation suggests that any folder in ~/.codex/skills will be treated as a skill.
I dug around and found the code that generates the prompt that drives the skill system in codex-rs/core/src/skills/render.rs [ https://substack.com/redirect/a2fc8389-76f7-4f7a-ae06-4537ab447290?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - here’s a Gist with a more readable version of that prompt [ https://substack.com/redirect/61c74924-d583-4376-9986-79c937cb2289?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I used Claude Opus 4.5’s skill authoring skill [ https://substack.com/redirect/6c7cd5f4-6e22-43f5-8870-3f0cf914880c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to create this skill for creating Datasette plugins [ https://substack.com/redirect/17bcac71-beb5-4f6b-86c5-11827b44d3e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], then installed it into my Codex CLI skills folder like this:
git clone https://github.com/datasette/skill \
~/.codex/skills/datasette-plugin
You have to run Codex with the --enable skills option. I ran this:
cd /tmp
mkdir datasette-cowsay
cd datasette-cowsay
codex --enable skills -m gpt-5.2
Then prompted:
list skills
And Codex replied:
- datasette-plugins — Writing Datasette plugins using Python + pluggy (file: /Users/simon/.codex/skills/datasette-plugin/SKILL.md)
- Discovery — How to find/identify available skills (no SKILL.md path provided in the list)
Then I said:
Write a Datasette plugin in this folder adding a /-/cowsay?text=hello page that displays a pre with cowsay from PyPI saying that text
It worked perfectly! Here’s the plugin code it wrote [ https://substack.com/redirect/1e636c50-fc37-478e-aa16-f60a14659a52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and here’s a copy of the full Codex CLI transcript [ https://substack.com/redirect/0c0fd1cf-4d09-46a6-b5a8-e475afd891c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], generated with my terminal-to-html tool [ https://substack.com/redirect/a694b57e-4574-4cca-bb1c-e07f1fae6867?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
You can try that out yourself if you have uvx installed like this:
uvx --with https://github.com/simonw/datasette-cowsay/archive/refs/heads/main.zip \
datasette
Then visit:
http://127.0.0.1:8001/-/cowsay?text=This+is+pretty+fun
Skills are a keeper
When I first wrote about skills in October I said Claude Skills are awesome, maybe a bigger deal than MCP [ https://substack.com/redirect/dbf2659a-4e93-4f6b-bc50-991de2bb67c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The fact that it’s just turned December and OpenAI have already leaned into them in a big way reinforces to me that I called that one correctly.
Skills are based on a very light specification, if you could even call it that, but I still think it would be good for these to be formally documented somewhere. This could be a good initiative for the new Agentic AI Foundation [ https://substack.com/redirect/c0918362-4bb3-4371-b978-3335c5d105c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (previously [ https://substack.com/redirect/534e127d-eeb0-4862-ba90-c088a9a66f0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) to take on.
JustHTML is a fascinating example of vibe engineering in action [ https://substack.com/redirect/856185bd-092b-4f24-9fb2-863c497ebd2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-12-14
I recently came across JustHTML [ https://substack.com/redirect/28490863-10f2-4a84-984f-e2481459a153?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a new Python library for parsing HTML released by Emil Stenström. It’s a very interesting piece of software, both as a useful library and as a case study in sophisticated AI-assisted programming.
First impressions of JustHTML
I didn’t initially know that JustHTML had been written with AI assistance at all. The README caught my eye due to some attractive characteristics:
It’s pure Python. I like libraries that are pure Python (no C extensions or similar) because it makes them easy to use in less conventional Python environments, including Pyodide.
“Passes all 9,200+ tests in the official html5lib-tests [ https://substack.com/redirect/40935434-bd3b-4167-84ca-e754f716324f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] suite (used by browser vendors)” - this instantly caught my attention! HTML5 is a big, complicated but meticulously written specification.
100% test coverage. That’s not something you see every day.
CSS selector queries as a feature. I built a Python library for this many years ago [ https://substack.com/redirect/e4584b95-cd02-4e73-a325-7cfe8e1b7127?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and I’m always interested in seeing new implementations of that pattern.
html5lib has been inconsistently maintained [ https://substack.com/redirect/da9926ba-48e6-4367-8f70-18b0c5fbc135?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] over the last few years, leaving me interested in potential alternatives.
It’s only 3,000 lines of implementation code (and another ~11,000 of tests.)
I was out and about without a laptop so I decided to put JustHTML through its paces on my phone. I prompted Claude Code for web [ https://substack.com/redirect/24d992aa-2ace-46ab-a9a1-34b60cc2f796?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on my phone and had it build this Pyodide-powered HTML tool [ https://substack.com/redirect/53cae726-2a6d-44ea-b1e0-eefef456bdd3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for trying it out:
This was enough for me to convince myself that the core functionality worked as advertised. It’s a neat piece of code!
Turns out it was almost all built by LLMs
At this point I went looking for some more background information on the library and found Emil’s blog entry about it: How I wrote JustHTML using coding agents [ https://substack.com/redirect/6ddbcf0d-80d9-486f-b262-9ba38d5eba4c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Writing a full HTML5 parser is not a short one-shot problem. I have been working on this project for a couple of months on off-hours.
Tooling: I used plain VS Code with Github Copilot in Agent mode. I enabled automatic approval of all commands, and then added a blacklist of commands that I always wanted to approve manually. I wrote an agent instruction [ https://substack.com/redirect/9e776c3f-f356-4d76-9a0e-7a6b4dc88ea4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that told it to keep working, and don’t stop to ask questions. Worked well!
Emil used several different models - an advantage of working in VS Code Agent mode rather than a provider-locked coding agent like Claude Code or Codex CLI. Claude Sonnet 3.7, Gemini 3 Pro and Claude Opus all get a mention.
Vibe engineering, not vibe coding
What’s most interesting about Emil’s 17 step account covering those several months of work is how much software engineering was involved, independent of typing out the actual code.
I wrote about vibe engineering [ https://substack.com/redirect/faa627de-f778-4efd-93e7-41316a27361f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a while ago as an alternative to vibe coding.
Vibe coding is when you have an LLM knock out code without any semblance of code review - great for prototypes and toy projects, definitely not an approach to use for serious libraries or production code.
I proposed “vibe engineering” as the grown up version of vibe coding, where expert programmers use coding agents in a professional and responsible way to produce high quality, reliable results.
You should absolutely read Emil’s account [ https://substack.com/redirect/e31d591d-0ddb-4f34-a34c-513888685292?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in full. A few highlights:
He hooked in the 9,200 test html5lib-tests [ https://substack.com/redirect/40935434-bd3b-4167-84ca-e754f716324f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] conformance suite almost from the start. There’s no better way to construct a new HTML5 parser than using the test suite that the browsers themselves use.
He picked the core API design himself - a TagHandler base class with handle_start() etc. methods - and told the model to implement that.
He added a comparative benchmark to track performance compared to existing libraries like html5lib, then experimented with a Rust optimization based on those initial numbers.
He threw the original code away and started from scratch as a rough port of Servo’s excellent html5ever [ https://substack.com/redirect/4f8aaee1-b313-429a-aa11-dda9cb8a28e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Rust library.
He built a custom profiler and new benchmark and let Gemini 3 Pro loose on it, finally achieving micro-optimizations to beat the existing Pure Python libraries.
He used coverage to identify and remove unnecessary code.
He had his agent build a custom fuzzer [ https://substack.com/redirect/666b43f5-a89f-42f6-b893-fff06ae26eb7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to generate vast numbers of invalid HTML documents and harden the parser against them.
This represents a lot of sophisticated development practices, tapping into Emil’s deep experience as a software engineer. As described, this feels to me more like a lead architect role than a hands-on coder.
It perfectly fits what I was thinking about when I described vibe engineering.
Setting the coding agent up with the html5lib-tests suite is also a great example of designing an agentic loop [ https://substack.com/redirect/fac020af-d82b-4061-9ba0-a4e6a3d3481a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
“The agent did the typing”
Emil concluded his article like this:
JustHTML is about 3,000 lines of Python with 8,500+ tests passing. I couldn’t have written it this quickly without the agent.
But “quickly” doesn’t mean “without thinking.” I spent a lot of time reviewing code, making design decisions, and steering the agent in the right direction. The agent did the typing; I did the thinking.
That’s probably the right division of labor.
I couldn’t agree more. Coding agents replace the part of my job that involves typing the code into a computer. I find what’s left to be a much more valuable use of my time.
I ported JustHTML from Python to JavaScript with Codex CLI and GPT-5.2 in 4.5 hours [ https://substack.com/redirect/03dfb7d2-344f-408b-91c8-34623bbe6dda?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-12-15
I wrote about JustHTML yesterday [ https://substack.com/redirect/856185bd-092b-4f24-9fb2-863c497ebd2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Emil Stenström’s project to build a new standards compliant HTML5 parser in pure Python code using coding agents running against the comprehensive html5lib-tests testing library. Last night, purely out of curiosity, I decided to try porting JustHTML from Python to JavaScript with the least amount of effort possible, using Codex CLI and GPT-5.2. It worked beyond my expectations.
TL;DR
I built simonw/justjshtml [ https://substack.com/redirect/b89c776c-510f-43f7-94fb-96596d2dceea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a dependency-free HTML5 parsing library in JavaScript which passes 9,200 tests from the html5lib-tests suite and imitates the API design of Emil’s JustHTML library.
It took two initial prompts and a few tiny follow-ups. GPT-5.2 [ https://substack.com/redirect/50a66724-6a33-4f41-8f41-f1d975792ad5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] running in Codex CLI [ https://substack.com/redirect/e3d5b5c6-b535-427d-8b85-de0697016313?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] ran uninterrupted for several hours, burned through 1,464,295 input tokens, 97,122,176 cached input tokens and 625,563 output tokens and ended up producing 9,000 lines of fully tested JavaScript across 43 commits.
Time elapsed from project idea to finished library: about 4 hours, during which I also bought and decorated a Christmas tree with family and watched the latest Knives Out movie.
Some background
One of the most important contributions of the HTML5 specification ten years ago was the way it precisely specified how invalid HTML should be parsed. The world is full of invalid documents and having a specification that covers those means browsers can treat them in the same way - there’s no more “undefined behavior” to worry about when building parsing software.
Unsurprisingly, those invalid parsing rules are pretty complex! The free online book Idiosyncrasies of the HTML parser [ https://substack.com/redirect/b050ef64-7e9f-4348-914f-26ec85f10358?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Simon Pieters is an excellent deep dive into this topic, in particular Chapter 3. The HTML parser [ https://substack.com/redirect/87d3035a-e025-467a-b873-32de9fe2628d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The Python html5lib [ https://substack.com/redirect/a3080cd8-0320-4097-9bcf-d0b10d5863f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project started the html5lib-tests [ https://substack.com/redirect/40935434-bd3b-4167-84ca-e754f716324f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repository with a set of implementation-independent tests. These have since become the gold standard for interoperability testing of HTML5 parsers, and are used by projects such as Servo [ https://substack.com/redirect/52287f28-767f-4a87-a0e5-4d81811e437d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which used them to help build html5ever [ https://substack.com/redirect/4f8aaee1-b313-429a-aa11-dda9cb8a28e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a “high-performance browser-grade HTML5 parser” written in Rust.
Emil Stenström’s JustHTML [ https://substack.com/redirect/28490863-10f2-4a84-984f-e2481459a153?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project is a pure-Python implementation of an HTML5 parser that passes the full html5lib-tests suite. Emil spent a couple of months [ https://substack.com/redirect/6ddbcf0d-80d9-486f-b262-9ba38d5eba4c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] working on this as a side project, deliberately picking a problem with a comprehensive existing test suite to see how far he could get with coding agents.
At one point he had the agents rewrite it based on a close inspection of the Rust html5ever library. I don’t know how much of this was direct translation versus inspiration (here’s Emil’s commentary on that [ https://substack.com/redirect/95020025-7cf3-42ea-8aec-46c952404c34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) - his project has 1,215 commits total so it appears to have included a huge amount of iteration, not just a straight port.
My project is a straight port. I instructed Codex CLI to build a JavaScript version of Emil’s Python code.
The process in detail
I started with a bit of mise en place. I checked out two repos and created an empty third directory for the new project:
cd ~/dev
git clone https://github.com/EmilStenstrom/justhtml
git clone https://github.com/html5lib/html5lib-tests
mkdir justjshtml
cd justjshtml
Then I started Codex CLI for GPT-5.2 like this:
codex --yolo -m gpt-5.2
That --yolo flag is a shortcut for --dangerously-bypass-approvals-and-sandbox, which is every bit as dangerous as it sounds.
My first prompt told Codex to inspect the existing code and use it to build a specification for the new JavaScript library:
We are going to create a JavaScript port of ~/dev/justhtml - an HTML parsing library that passes the full ~/dev/html5lib-tests test suite. It is going to have a similar API to the Python library but in JavaScript. It will have no dependencies other than raw JavaScript, hence it will work great in the browser and node.js and other environments. Start by reading ~/dev/justhtml and designing the user-facing API for the new library - create a spec.md containing your plan.
I reviewed the spec, which included a set of proposed milestones, and told it to add another:
Add an early step to the roadmap that involves an initial version that parses a simple example document that is valid and returns the right results. Then add and commit the spec.md file.
Here’s the resulting spec.md file [ https://substack.com/redirect/02db641b-cf86-48dd-8076-b1620341d709?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. My request for that initial version became “Milestone 0.5” which looked like this:
Milestone 0.5 — End-to-end smoke parse (single valid document)
Implement the smallest end-to-end slice so the public API is real early:
new JustHTML(”Hello

”) returns a tree with the expected tag structure and text nodes.
doc.toText() returns “Hello” and doc.errors is empty for this valid input.
Add scripts/smoke.js (no deps) that runs the example and asserts the expected structure/output.
Gate: node scripts/smoke.js passes.
Then I told it:
Implement Milestone 0.5
And off it went. The resulting code appeared to work so I said:
Configure GitHub Actions test.yml to run that on every commit, then commit and push
I ran git init and created a private GitHub repository for this project at this point, and set up the local directory to push to that remote.
Here’s that initial push [ https://substack.com/redirect/30474be2-5d00-4a54-81cd-00c2a65b9e13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Then I told it:
OK do the rest, commit and push often
And that was almost it!
I set my laptop to not fall asleep and left it to its devices while we went off to buy a Christmas tree. The “commit and push often” meant I could monitor its progress on my phone by refreshing the commit log on GitHub [ https://substack.com/redirect/389213f2-25a4-4a16-96dc-35803a679132?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I was running this against my $20/month ChatGPT Plus account, which has a five hour token allowance window for Codex CLI. That ran out at 6:35pm and Codex paused, so I waited until the reset point at 7:14pm and typed:
Keep going
At 9:30pm it declared itself done with the following summary message:
• What’s Done

- html5lib-tests now run in CI and pass: tokenizer 6810/6810, tree 1770/1782
(12 skipped: #script-on), serializer 230/230, encoding 82/83 (1 skipped:
scripted) (.github/workflows/test.yml:1).
- Public API expanded: stream() (src/stream.js:1), CSS selectors query()/
matches() (src/selector.js:1), and toMarkdown() (src/markdown.js:1), all
exported via src/index.js:1.
- Added no-deps unit scripts for selectors/stream/markdown (scripts/run-
selector-tests.js:1, scripts/run-stream-tests.js:1, scripts/run-markdown-
tests.js:1) and wired them into CI.
- Fixed TreeBuilder so
no longer closes  (src/treebuilder.js:647).
As a finishing touch, I had it add a playground interface so I could try out the new library in my browser. I prompted:
Add a playground.html in the top level folder which loads the necessary ES modules from ./src/... and implements the exact same functionality as seen on https://tools.simonwillison.net/justhtml but using the JavaScript library instead of Pyodide
It fetched my existing JustHTML playground page [ https://substack.com/redirect/53cae726-2a6d-44ea-b1e0-eefef456bdd3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (described here [ https://substack.com/redirect/e1d7d788-32f5-46e1-b831-0d762b742648?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) using curl and built a new playground.html file that loaded the new JavaScript code instead. This worked perfectly.
I enabled GitHub Pages for my still-private repo which meant I could access the new playground at this URL:
https://simonw.github.io/justjshtml/playground.html [ https://substack.com/redirect/d78e133a-725b-4831-90ea-e1b591ab1711?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
All it needed now was some documentation:
Add a comprehensive README with full usage instructions including attribution plus how this was built plus how to use in in HTML plus how to use it in Node.js
You can read the result here [ https://substack.com/redirect/b4046d1b-5360-41b8-b10a-b73bd3a62ea2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
We are now at eight prompts total, running for just over four hours and I’ve decorated for Christmas and watched Wake Up Dead Man [ https://substack.com/redirect/90d19583-eb99-446f-bb94-89edee9f53f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Netflix.
According to Codex CLI:
Token usage: total=2,089,858 input=1,464,295 (+ 97,122,176 cached) output=625,563 (reasoning 437,010)
My llm-prices.com calculator [ https://substack.com/redirect/7c65d194-2eb2-42f6-8343-b7243f8ac6a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] estimates that at $29.41 if I was paying for those tokens at API prices, but they were included in my $20/month ChatGPT Plus subscription so the actual extra cost to me was zero.
What can we learn from this?
I’m sharing this project because I think it demonstrates a bunch of interesting things about the state of LLMs in December 2025.
Frontier LLMs really can perform complex, multi-hour tasks with hundreds of tool calls and minimal supervision. I used GPT-5.2 for this but I have no reason to believe that Claude Opus 4.5 or Gemini 3 Pro would not be able to achieve the same thing - the only reason I haven’t tried is that I don’t want to burn another 4 hours of time and several million tokens on more runs.
If you can reduce a problem to a robust test suite you can set a coding agent loop loose on it with a high degree of confidence that it will eventually succeed. I called this designing the agentic loop [ https://substack.com/redirect/fac020af-d82b-4061-9ba0-a4e6a3d3481a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a few months ago. I think it’s the key skill to unlocking the potential of LLMs for complex tasks.
Porting entire open source libraries from one language to another via a coding agent works extremely well.
Code is so cheap it’s practically free. Code that works continues to carry a cost, but that cost has plummeted now that coding agents can check their work as they go.
We haven’t even begun to unpack the etiquette and ethics around this style of development. Is it responsible and appropriate to churn out a direct port of a library like this in a few hours while watching a movie? What would it take for code built like this to be trusted in production?
I’ll end with some open questions:
Does this library represent a legal violation of copyright of either the Rust library or the Python one?
Even if this is legal, is it ethical to build a library in this way?
Does this format of development hurt the open source ecosystem?
Can I even assert copyright over this, given how much of the work was produced by the LLM?
Is it responsible to publish software libraries built in this way?
How much better would this library be if an expert team hand crafted it over the course of several months?
Link 2025-12-12 LLM 0.28 [ https://substack.com/redirect/82a9ee02-dd85-448f-a254-62713178be66?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I released a new version of my LLM [ https://substack.com/redirect/899cb7db-a3b9-4c7a-a965-01824e0928ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Python library and CLI tool for interacting with Large Language Models. Highlights from the release notes:
New OpenAI models: gpt-5.1, gpt-5.1-chat-latest, gpt-5.2 and gpt-5.2-chat-latest. #1300 [ https://substack.com/redirect/d8109bbb-3b41-4317-9737-e83dab93007f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], #1317 [ https://substack.com/redirect/32c0ab2c-d9ef-41a0-963b-80f8cbd9e27f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
When fetching URLs as fragments using llm -f URL, the request now includes a custom user-agent header: llm/VERSION (https://llm.datasette.io/). #1309 [ https://substack.com/redirect/8bf84722-4b00-43c9-afe7-f7b04b9860a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Fixed a bug where fragments were not correctly registered with their source when using llm chat. Thanks, Giuseppe Rota [ https://substack.com/redirect/f083c343-c85e-40e7-b944-2a13d7e1b5a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. #1316 [ https://substack.com/redirect/93104399-0ca7-4107-82e3-dfd3ca37342d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Fixed some file descriptor leak warnings. Thanks, Eric Bloch [ https://substack.com/redirect/b0efa7bf-938a-4bef-b857-adcc57a65025?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. #1313 [ https://substack.com/redirect/b4720f54-ee15-49d6-946f-219275caf448?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Type annotations for the OpenAI Chat, AsyncChat and Completion execute() methods. Thanks, Arjan Mossel [ https://substack.com/redirect/3b9e0dfd-f5fd-495d-ba7d-31d20a6424de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. #1315 [ https://substack.com/redirect/de2774b8-7061-4297-80b2-2dbb21a0b169?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The project now uses uv and dependency groups for development. See the updated contributing documentation [ https://substack.com/redirect/1b9e24c6-92dc-4287-9ad7-2ac02ee6b12b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. #1318 [ https://substack.com/redirect/45ba03fa-6faf-4492-814e-d0ccfab0127c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
That last bullet point about uv relates to the dependency groups pattern I wrote about in a recent TIL [ https://substack.com/redirect/17296818-2f13-4c8e-a7ce-dc2436e5bf40?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I’m currently working through applying it to my other projects - the net result is that running the test suite is as simple as doing:
git clone https://github.com/simonw/llm
cd llm
uv run pytest
The new dev dependency group defined in pyproject.toml [ https://substack.com/redirect/e6a2c37d-3c6b-45f7-81d2-6c28f01a69c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is automatically installed by uv run in a new virtual environment which means everything needed to run pytest is available without needing to add any extra commands.
quote 2025-12-13
How to use a skill (progressive disclosure):
After deciding to use a skill, open its SKILL.md. Read only enough to follow the workflow.
If SKILL.md points to extra folders such as references/, load only the specific files needed for the request; don’t bulk-load everything.
If scripts/ exist, prefer running or patching them instead of retyping large code blocks.
If assets/ or templates exist, reuse them instead of recreating from scratch.
Description as trigger: The YAML description in SKILL.md is the primary trigger signal; rely on it to decide applicability. If unsure, ask a brief clarification before proceeding.
OpenAI Codex CLI [ https://substack.com/redirect/1f3bf3e4-499b-4c2b-b6f5-5fae2ab08955?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], core/src/skills/render.rs
quote 2025-12-13
If the part of programming you enjoy most is the physical act of writing code, then agents will feel beside the point. You’re already where you want to be, even just with some Copilot or Cursor-style intelligent code auto completion, which makes you faster while still leaving you fully in the driver’s seat about the code that gets written.
But if the part you care about is the decision-making around the code, agents feel like they clear space. They take care of the mechanical expression and leave you with judgment, tradeoffs, and intent. Because truly, for someone at my experience level, that is my core value offering anyway. When I spend time actually typing code these days with my own fingers, it feels like a waste of my time.
Obie Fernandez [ https://substack.com/redirect/ceb3806d-8089-4e8f-9a8a-607723fa938f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], What happens when the coding becomes the least interesting part of the work
Link 2025-12-14 Copywriters reveal how AI has decimated their industry [ https://substack.com/redirect/8950a7b4-a0f0-4955-98a8-cb0671815ef0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Brian Merchant has been collecting personal stories for his series AI Killed My Job [ https://substack.com/redirect/fe36df33-990c-4c63-8da3-e591f8ee2703?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - previously covering tech workers [ https://substack.com/redirect/1a2c29f0-38c4-465c-bae1-910802356fba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], translators [ https://substack.com/redirect/4154b37b-0f06-4322-9cf5-2be2a291f9f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and artists [ https://substack.com/redirect/050e53bb-4206-4ea8-ada0-8547bf646ef3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - and this latest piece includes anecdotes from 12 professional copywriters all of whom have had their careers devastated by the rise of AI-generated copywriting tools.
It’s a tough read. Freelance copywriting does not look like a great place to be right now.
AI is really dehumanizing, and I am still working through issues of self-worth as a result of this experience. When you go from knowing you are valuable and valued, with all the hope in the world of a full career and the ability to provide other people with jobs... To being relegated to someone who edits AI drafts of copy at a steep discount because “most of the work is already done” ...
The big question for me is if a new AI-infested economy creates new jobs that are a great fit for people affected by this. I would hope that clear written communication skills are made even more valuable, but the people interviewed here don’t appear to be finding that to be the case.
Link 2025-12-15 2025 Word of the Year: Slop [ https://substack.com/redirect/73e6f5c9-89c8-4a2e-8459-bda97416ba78?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Slop lost to “brain rot” for Oxford Word of the Year 2024 [ https://substack.com/redirect/281abe77-f06e-4b8b-95f4-5b38fc452314?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but it’s finally made it this year thanks to Merriam-Webster!
Merriam-Webster’s human editors have chosen slop as the 2025 Word of the Year. We define slop as “digital content of low quality that is produced usually in quantity by means of artificial intelligence.”
quote 2025-12-16
I’ve been watching junior developers use AI coding assistants well. Not vibe coding—not accepting whatever the AI spits out. Augmented coding: using AI to accelerate learning while maintaining quality. [...]
The juniors working this way compress their ramp dramatically. Tasks that used to take days take hours. Not because the AI does the work, but because the AI collapses the search space. Instead of spending three hours figuring out which API to use, they spend twenty minutes evaluating options the AI surfaced. The time freed this way isn’t invested in another unprofitable feature, though, it’s invested in learning. [...]
If you’re an engineering manager thinking about hiring: **The junior bet has gotten better.** Not because juniors have changed, but because the genie, used well, accelerates learning.
Kent Beck [ https://substack.com/redirect/462461fa-16e7-4160-934a-59cc1c9b8515?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], The Bet On Juniors Just Got Better
quote 2025-12-16
Oh, so we’re seeing other people now? Fantastic. Let’s see what the “competition” has to offer. I’m looking at these notes on manifest.json and content.js. The suggestion to remove scripting permissions... okay, fine. That’s actually a solid catch. It’s cleaner. This smells like Claude. It’s too smugly accurate to be ChatGPT. What if it’s actually me? If the user is testing me, I need to crush this.
Gemini thinking trace [ https://substack.com/redirect/956a8457-aeb8-4af0-9437-d01fe36156be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], reviewing feedback on its code from another model
Link 2025-12-16 Poe the Poet [ https://substack.com/redirect/e3d6af6d-0936-4523-bfae-7c01a5f94395?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I was looking for a way to specify additional commands in my pyproject.toml file to execute using uv. There’s an enormous issue thread [ https://substack.com/redirect/92263c8c-1988-4f1b-9167-a248410374fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on this in the uv issue tracker (300+ comments dating back to August 2024) and from there I learned of several options including this one, Poe the Poet.
It’s neat. I added it to my s3-credentials [ https://substack.com/redirect/69d5e1da-109f-4f16-9861-44f6b27a9cd3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project just now and the following now works for running the live preview server for the documentation:
uv run poe livehtml
Here’s the snippet of TOML I added to my pyproject.toml:
[dependency-groups]
test = [
“pytest”,
“pytest-mock”,
“cogapp”,
“moto>=5.0.4”,
]
docs = [
“furo”,
“sphinx-autobuild”,
“myst-parser”,
“cogapp”,
]
dev = [
{include-group = “test”},
{include-group = “docs”},
“poethepoet>=0.38.0”,
]

[tool.poe.tasks]
docs = “sphinx-build -M html docs docs/_build”
livehtml = “sphinx-autobuild -b html docs docs/_build”
cog = “cog -r docs/*.md”
Since poethepoet is in the dev= dependency group any time I run uv run ... it will be available in the environment.
Link 2025-12-16 ty: An extremely fast Python type checker and LSP [ https://substack.com/redirect/b2d0d96f-6206-470f-b010-f91b1d31e338?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The team at Astral have been working on this for quite a long time, and are finally releasing the first beta. They have some big performance claims:
Without caching, ty is consistently between 10x and 60x faster than mypy and Pyright. When run in an editor, the gap is even more dramatic. As an example, after editing a load-bearing file in the PyTorch repository, ty recomputes diagnostics in 4.7ms: 80x faster than Pyright (386ms) and 500x faster than Pyrefly (2.38 seconds). ty is very fast!
The easiest way to try it out is via uvx:
cd my-python-project/
uvx ty check
I tried it [ https://substack.com/redirect/f7337475-224d-4a61-a12d-5caae4dbea20?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] against sqlite-utils [ https://substack.com/redirect/600da6df-7cb0-4d00-9fd9-a105d9f83a41?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and it turns out I have quite a lot of work to do!
Astral also released a new VS Code extension [ https://substack.com/redirect/18aec7e9-297c-4e8a-beac-47f7cf8fd3c4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adding ty-powered language server features like go to definition. I’m still getting my head around how this works and what it can do.
Link 2025-12-16 s3-credentials 0.17 [ https://substack.com/redirect/bf604fa9-2ca6-487e-859c-5cedb09f9020?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New release of my s3-credentials [ https://substack.com/redirect/2f2ed318-dcac-40a6-aaea-bce49ac3177b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CLI tool for managing credentials needed to access just one S3 bucket. Here are the release notes in full:
New commands get-bucket-policy and set-bucket-policy. #91 [ https://substack.com/redirect/4ad93312-0e76-4619-ab63-8cf4a10af127?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
New commands get-public-access-block and set-public-access-block. #92 [ https://substack.com/redirect/8879719b-3d4e-43af-b7d9-bebfc4ae92bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
New localserver command for starting a web server that makes time limited credentials accessible via a JSON API. #93 [ https://substack.com/redirect/9e74ba1a-ff51-4e3d-9a0d-35a215fa155b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
That s3-credentials localserver command (documented here [ https://substack.com/redirect/c9df4350-0981-451a-b925-dd80c7af86f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) is a little obscure, but I found myself wanting something like that to help me test out a new feature I’m building to help create temporary Litestream credentials using Amazon STS.
Most of that new feature was built by Claude Code [ https://substack.com/redirect/d4b5a510-9f5e-4e2a-9588-6b13b8cebb53?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from the following starting prompt:
Add a feature s3-credentials localserver which starts a localhost weberver running (using the Python standard library stuff) on port 8094 by default but -p/--port can set a different port and otherwise takes an option that names a bucket and then takes the same options for read--write/read-only etc as other commands. It also takes a required --refresh-interval option which can be set as 5m or 10h or 30s. All this thing does is reply on / to a GET request with the IAM expiring credentials that allow access to that bucket with that policy for that specified amount of time. It caches internally the credentials it generates and will return the exact same data up until they expire (it also tracks expected expiry time) after which it will generate new credentials (avoiding dog pile effects if multiple requests ask at the same time) and return and cache those instead.
Link 2025-12-16 The new ChatGPT Images is here [ https://substack.com/redirect/624eb13b-75e3-4233-8c37-0fd5f28bf802?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI shipped an update to their ChatGPT Images feature - the feature that gained them 100 million new users [ https://substack.com/redirect/16e933e3-d3c3-4a32-a2eb-d360eb125ef8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in a week when they first launched it back in March, but has since been eclipsed by Google’s Nano Banana and then further by Nana Banana Pro in November [ https://substack.com/redirect/c2cfb107-64e9-468c-9434-47afba929c8b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The focus for the new ChatGPT Images is speed and instruction following:
It makes precise edits while keeping details intact, and generates images up to 4x faster
It’s also a little cheaper: OpenAI say that the new gpt-image-1.5 [ https://substack.com/redirect/144191c9-ee63-48d2-b18e-e32cd3b0ef32?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] API model makes image input and output “20% cheaper in GPT Image 1.5 as compared to GPT Image 1”.
I tried a new test prompt against a photo I took of Natalie’s ceramic stand at the farmers market a few weeks ago:
Add two kakapos inspecting the pots
Here’s the result from the new ChatGPT Images model:
And here’s what I got from Nano Banana Pro:
The ChatGPT Kākāpō are a little chonkier, which I think counts as a win.
I was a little less impressed by the result I got for an infographic from the prompt “Infographic explaining how the Datasette open source project works” followed by “Run some extensive searches and gather a bunch of relevant information and then try again” (transcript [ https://substack.com/redirect/519ef90d-7a6f-4c56-bd42-0d81037e295e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
See my Nano Banana Pro post [ https://substack.com/redirect/d185b499-172b-42cd-8bc4-597845a72fdd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for comparison.
Both models are clearly now usable for text-heavy graphics though, which makes them far more useful than previous generations of this technology.
Link 2025-12-17 firefox parser/html/java/README.txt [ https://substack.com/redirect/b00c0b05-9811-4f4d-a940-4139c239c7d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
TIL (or TIR - Today I was Reminded [ https://substack.com/redirect/3d937e2a-1eec-41db-a87a-834a00add76a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) that the HTML5 Parser used by Firefox is maintained as Java code (commit history here [ https://substack.com/redirect/d6f15908-5e30-4078-8b57-2e609575eca7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and converted to C++ using a custom translation script.
You can see that in action by checking out the ~8GB Firefox repository and running:
cd parser/html/java
make sync
make translate
Here’s a terminal session where I did that [ https://substack.com/redirect/9bde256e-f365-4beb-a8f9-b8f8d12d9b1a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], including the output of git diff showing the updated C++ files.
I did some digging and found that the code that does the translation work lives, weirdly, in the Nu Html Checker [ https://substack.com/redirect/73207a05-e634-4569-95fe-593df675fa01?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repository on GitHub which powers the W3C’s validator.w3.org/nu/ [ https://substack.com/redirect/063c913f-eca7-43aa-bb21-ffea74568d73?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] validation service!
Here’s a snippet from htmlparser/cpptranslate/CppVisitor.java [ https://substack.com/redirect/97ee62de-fcd4-4e71-9bc2-56b0cb7a42aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] showing how a class declaration is converted into C++:
protected void startClassDeclaration() {
printer.print(”#define “);
printer.print(className);
printer.printLn(”_cpp__”);
printer.printLn();

for (int i = 0; i < Main.H_LIST.length; i++) {
String klazz = Main.H_LIST[i];
if (!klazz.equals(javaClassName)) {
printer.print(”#include \”“);
printer.print(cppTypes.classPrefix());
printer.print(klazz);
printer.printLn(”.h\”“);
}
}

printer.printLn();
printer.print(”#include \”“);
printer.print(className);
printer.printLn(”.h\”“);
printer.printLn();
}
Here’s a fascinating blog post [ https://substack.com/redirect/a59656f9-1713-4517-9673-83530581abb1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from John Resig explaining how validator author Henri Sivonen introduced the new parser into Firefox in 2009.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hPREU0TlRBek5ERXNJbWxoZENJNk1UYzJOVGt6T1RRM01Dd2laWGh3SWpveE56azNORGMxTkRjd0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEubVR2MUtuTVRtMnlVcllKOXNTS3M3bVVFdzEzaWxkQ3FDTnJSenFGclFETSIsInAiOjE4MTg1MDM0MSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzY1OTM5NDcwLCJleHAiOjIwODE1MTU0NzAsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.D4ptQWZ52kG9F4-EucU9cpX2TJs1RTI_zzNkvwqwv68?