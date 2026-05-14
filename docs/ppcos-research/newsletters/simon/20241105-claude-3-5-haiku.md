# Claude 3.5 Haiku

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-11-05T03:42:54.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/claude-35-haiku

In this newsletter:
Claude 3.5 Haiku
W̶e̶e̶k̶n̶o̶t̶e̶s̶ Monthnotes for October
Plus 14 links and 3 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Claude 3.5 Haiku [ https://substack.com/redirect/32f0d77c-382e-4527-96f0-aaebc69f746d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-11-04
Anthropic released Claude 3.5 Haiku [ https://substack.com/redirect/3d1545a6-8bd8-4ba6-a1ae-88355fbe4ac2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today, a few days later than expected (they said it would be out by the end of October).
I was expecting this to be a complete replacement for their existing Claude 3 Haiku model, in the same way that Claude 3.5 Sonnet eclipsed the existing Claude 3 Sonnet while maintaining the same pricing.
Claude 3.5 Haiku is different. First, it doesn't (yet) support image inputs - so Claude 3 Haiku remains the least expensive Anthropic model for handling those.
Secondly, it's not priced the same as the previous Haiku. That was $0.25/million input and $1.25/million for output - the new 3.5 Haiku is 4x that at $1/million input and $5/million output.
Anthropic tweeted [ https://substack.com/redirect/cf50e7cf-31cf-4876-8b0b-aeec2f3574ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
During final testing, Haiku surpassed Claude 3 Opus, our previous flagship model, on many benchmarks—at a fraction of the cost.
As a result, we've increased pricing for Claude 3.5 Haiku to reflect its increase in intelligence.
Given that Anthropic claim that their new Haiku out-performs their older Claude 3 Opus (still $15/m input and $75/m output!) this price isn't disappointing, but it's a small surprise nonetheless.
Accessing Claude 3.5 Haiku with LLM
I released a new version of my llm-claude-3 [ https://substack.com/redirect/835fedd9-67e3-45d8-84f9-7573ca2807e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]plugin with support for the new model. You can install (or upgrade) the plugin and run it like this:
llm install --upgrade llm-claude-3
llm keys set claude
# Paste API key here
llm -m claude-3.5-haiku 'describe memory management in Rust'
Here's the output from that prompt [ https://substack.com/redirect/a86a6d7c-f0a7-4936-b1ef-76a964e36a2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Comparing prices
I added the new price to my LLM pricing calculator [ https://substack.com/redirect/46d3d30a-fd2f-4348-8d1e-ff88dcb3d5ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which inspired me to extract this comparison table for the leading models from Gemini, Anthropic and OpenAI. Here they are sorted from least to most expensive:
Gemini 1.5 Flash-8B [ https://substack.com/redirect/ff01eb6d-eb6a-4719-ba9d-e43ed435aaa8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] remains the model to beat on pricing: it's 1/6th of the price of the new Haiku - far less capable, but still extremely useful for tasks such as audio transcription [ https://substack.com/redirect/af2353fb-4432-41b4-b1a0-d8ca04189fcb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Also notable from Anthropic's model comparison table [ https://substack.com/redirect/87e82e73-99cd-4cc6-a3b4-c5e5331d25ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: Claude 3.5 Haiku has a max output of 8,192 tokens (same as 3.5 Sonnet, but twice that of Claude 3 Opus and Claude 3 Haiku). 3.5 Haiku has a training cut-off date of July 2024, the most recent of any Anthropic model. 3.5 Sonnet is April 2024 and the Claude 3 family are all August 2023.
W̶e̶e̶k̶n̶o̶t̶e̶s̶ Monthnotes for October [ https://substack.com/redirect/5479ba8b-81d3-4c88-8bc6-88d65361d7ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-30
I try to publish weeknotes [ https://substack.com/redirect/8e49e4b6-53f3-410d-a1c0-6da7f87c70db?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at least once every two weeks. It's been four since the last entry, so I guess this one counts as monthnotes instead.
In my defense, the reason I've fallen behind on weeknotes is that I've been publishing a lot of long-form blog entries this month.
Plentiful LLM vendor news
A lot of LLM stuff happened. OpenAI had their DevDay, which I used as an opportunity to try out live blogging [ https://substack.com/redirect/f18242bc-fed7-43ac-8c32-eb7fd5bd94e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the first time. I figured out video scraping [ https://substack.com/redirect/85a294c9-fbec-4c31-99dc-f2132dc193a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with Google Gemini and generally got excited about how incredibly inexpensive the Gemini models are. Anthropic launched Computer Use [ https://substack.com/redirect/27e76747-4ca4-4fb9-ae73-2559fe94a899?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and JavaScript analysis [ https://substack.com/redirect/046e6e0d-d176-4b2a-ad48-109c0d66e3f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and the month ended with GitHub Universe [ https://substack.com/redirect/5bef452d-a22f-4025-bea5-941091892360?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
My LLM tool goes multi-modal
My big achievement of the month was finally shipping multi-modal support for my LLM tool [ https://substack.com/redirect/9a378b9e-d016-4476-b33b-dac3cb331021?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This has been almost a year in the making: GPT-4 vision kicked off the new era of vision LLMs at OpenAI DevDay last November and I've been watching the space with keen interest ever since.
I had a couple of false starts at the feature, which was difficult at first because LLM acts as a cross-model abstraction layer, and it's hard to design those effectively without plenty of examples of different models.
Initially I thought the feature would just be for images, but then Google Gemini launched the ability to feed in PDFs, audio files and videos as well. That's why I renamed it from -i/--image to -a/--attachment - I'm glad I hadn't committed to the image UI before realizing that file attachments could be so much more.
I'm really happy with how the feature turned out. The one missing piece at the moment is local models: I prototyped some incomplete local model plugins to verify the API design would work, but I've not yet pushed any of them to a state where I think they're ready to release. My research into mistral.rs [ https://substack.com/redirect/9f9ffbd5-b3a5-4108-a83d-5c3a11b0e11f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was part of that process.
Now that attachments have landed I'm free to start thinking about the next major LLM feature. I'm leaning towards tool usage: enough models have tool use / structured output capabilities now that I think I can design an abstraction layer that works across all of them. The combination of tool use with LLM's plugin system is really fun to think about.
Blog entries
You can now run prompts against images, audio and video in your terminal using LLM [ https://substack.com/redirect/9a378b9e-d016-4476-b33b-dac3cb331021?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Run a prompt to generate and execute jq programs using llm-jq [ https://substack.com/redirect/aa952515-a830-4985-accf-0c5c1ce9f499?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Notes on the new Claude analysis JavaScript code execution tool [ https://substack.com/redirect/046e6e0d-d176-4b2a-ad48-109c0d66e3f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Initial explorations of Anthropic's new Computer Use capability [ https://substack.com/redirect/27e76747-4ca4-4fb9-ae73-2559fe94a899?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Everything I built with Claude Artifacts this week [ https://substack.com/redirect/56d43d45-a29a-4453-a1fb-2ea0aa7b7e3c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Running Llama 3.2 Vision and Phi-3.5 Vision on a Mac with mistral.rs [ https://substack.com/redirect/9f9ffbd5-b3a5-4108-a83d-5c3a11b0e11f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Experimenting with audio input and output for the OpenAI Chat Completion API [ https://substack.com/redirect/563138b9-a23d-4032-8afe-ec4c5f06040b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Video scraping: extracting JSON data from a 35 second screen capture for less than 1/10th of a cent [ https://substack.com/redirect/85a294c9-fbec-4c31-99dc-f2132dc193a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
ChatGPT will happily write you a thinly disguised horoscope [ https://substack.com/redirect/f5c825e2-4227-4de3-86c1-622fbe9d023f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
OpenAI DevDay: Let’s build developer tools, not digital God [ https://substack.com/redirect/2799ddff-d94a-4a1f-9f95-b3c3eea61df1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
OpenAI DevDay 2024 live blog [ https://substack.com/redirect/f18242bc-fed7-43ac-8c32-eb7fd5bd94e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Releases
llm-mistral 0.7 [ https://substack.com/redirect/57cdf21f-aba1-4410-85be-ef07432968ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-29
LLM plugin providing access to Mistral models using the Mistral API
llm-claude-3 0.6 [ https://substack.com/redirect/91785faa-a4dd-4c56-a14b-ab94764d1a14?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-29
LLM plugin for interacting with the Claude 3 family of models
llm-gemini 0.3 [ https://substack.com/redirect/a0e4f699-9b91-46c4-90fe-6aa0b5aa58be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-29
LLM plugin to access Google's Gemini family of models
llm 0.17 [ https://substack.com/redirect/6383730e-fdfd-4df4-8061-fcedd694641d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-29
Access large language models from the command-line
llm-whisper-api 0.1.1 [ https://substack.com/redirect/b92614a8-bf2e-4097-bd4a-e03ac544b531?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-27
Run transcriptions using the OpenAI Whisper API
llm-jq 0.1.1 [ https://substack.com/redirect/20475b44-16d7-4948-83a1-49f4be3d25b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-27
Write and execute jq programs with the help of LLM
claude-to-sqlite 0.2 [ https://substack.com/redirect/611aadc5-3a4d-49cb-86a4-3d64a6dfd7ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-21
Convert a Claude.ai export to SQLite
files-to-prompt 0.4 [ https://substack.com/redirect/674b6516-185a-4de9-80eb-fcadb95fca0a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-16
Concatenate a directory full of files into a single prompt for use with LLMs
datasette-examples 0.1a0 [ https://substack.com/redirect/a7399236-92c6-4f11-99ca-dd47f3f9d231?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-08
Load example SQL scripts into Datasette on startup
datasette 0.65 [ https://substack.com/redirect/e779abd9-0adf-40b5-af21-38b864c08634?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-07
An open source multi-tool for exploring and publishing data
TILs
Installing flash-attn without compiling it [ https://substack.com/redirect/7c5c6665-2d73-4a7f-8253-c0c569ced646?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-25
Using uv to develop Python command-line applications [ https://substack.com/redirect/a7eddbee-62e8-4abf-a49a-ce5a497fd55b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-24
Setting cache-control: max-age=31536000 with a Cloudflare Transform Rule [ https://substack.com/redirect/2032a1a6-7b13-4b42-88b1-735186bccbfa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-24
Running prompts against images, PDFs, audio and video with Google Gemini [ https://substack.com/redirect/008d7f97-cc41-4bc8-a11a-b28274fed56d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-23
The most basic possible Hugo site [ https://substack.com/redirect/a6a040e4-66c0-4fb7-bae9-aea7b0cb6197?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-23
Livestreaming a community election event on YouTube [ https://substack.com/redirect/1dcb9895-089c-4837-b4d3-5ca055be095c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-10
Upgrading Homebrew and avoiding the failed to verify attestation error [ https://substack.com/redirect/60c91e39-2a2b-4e1b-aede-74742a9272b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-09
Collecting replies to tweets using JavaScript [ https://substack.com/redirect/4e45e4f0-7300-4b7f-9d78-dcdbddbc6504?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-09
Compiling and running sqlite3-rsync [ https://substack.com/redirect/8608f14b-8423-451d-95bb-a8624289754e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-04
Building an automatically updating live blog in Django [ https://substack.com/redirect/35054f93-b5ca-4574-ab77-b61f63574d6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-02
Link 2024-10-30 docs.jina.ai - the Jina meta-prompt [ https://substack.com/redirect/4fc986a8-0bb6-41cc-b96b-573807b9c97a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
From Jina AI on Twitter [ https://substack.com/redirect/321f57f2-4212-4601-a226-c4d26dd42ba0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
curl docs.jina.ai - This is our Meta-Prompt. It allows LLMs to understand our Reader, Embeddings, Reranker, and Classifier APIs for improved codegen. Using the meta-prompt is straightforward. Just copy the prompt into your preferred LLM interface like ChatGPT, Claude, or whatever works for you, add your instructions, and you're set.
The page is served using content negotiation. If you hit it with curl you get plain text, but a browser with text/html in the accept: header gets an explanation along with a convenient copy to clipboard button.
Link 2024-10-30 Creating a LLM-as-a-Judge that drives business results [ https://substack.com/redirect/6b733c8d-2120-4756-86b2-c4d8fffdc55b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Hamel Husain's sequel to Your AI product needs evals [ https://substack.com/redirect/2bc7a903-8a7b-43c3-87ea-d28ea9a44a3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This is packed with hard-won actionable advice.
Hamel warns against using scores on a 1-5 scale, instead promoting an alternative he calls "Critique Shadowing". Find a domain expert (one is better than many, because you want to keep their scores consistent) and have them answer the yes/no question "Did the AI achieve the desired outcome?" - providing a critique explaining their reasoning for each of their answers.
This gives you a reliable score to optimize against, and the critiques mean you can capture nuance and improve the system based on that captured knowledge.
Most importantly, the critique should be detailed enough so that you can use it in a few-shot prompt for a LLM judge. In other words, it should be detailed enough that a new employee could understand it.
Once you've gathered this expert data system you can switch to using an LLM-as-a-judge. You can then iterate on the prompt you use for it in order to converge its "opinions" with those of your domain expert.
Hamel concludes:
The real value of this process is looking at your data and doing careful analysis. Even though an AI judge can be a helpful tool, going through this process is what drives results. I would go as far as saying that creating a LLM judge is a nice “hack” I use to trick people into carefully looking at their data!
Link 2024-10-31 Australia/Lord_Howe is the weirdest timezone [ https://substack.com/redirect/44a0e83f-3d16-46a6-98ec-5d930f26ee06?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Lord Howe Island - part of Australia, population 382 - is unique in that the island's standard time zone is UTC+10:30 but is UTC+11 when daylight saving time applies. It's the only time zone where DST represents a 30 minute offset.
Link 2024-10-31 Cerebras Coder [ https://substack.com/redirect/51198e24-1917-422c-b426-1d12768e7e57?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Val Town founder Steve Krouse has been building demos on top of the Cerebras API that runs Llama3.1-70b at 2,000 tokens/second.
Having a capable LLM with that kind of performance turns out to be really interesting. Cerebras Coder is a demo that implements Claude Artifact-style on-demand JavaScript apps, and having it run at that speed means changes you request are visible within less than a second:
Steve's implementation (created with the help of Townie [ https://substack.com/redirect/2637124d-1bd7-42ef-9555-27298510b611?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the Val Town code assistant) demonstrates the simplest possible version of an iframe sandbox:

Where code is populated by a setCode(...) call inside a React component.
The most interesting applications of LLMs continue to be where they operate in a tight loop with a human - this can make those review loops potentially much faster and more productive.
Link 2024-11-01 Control your smart home devices with the Gemini mobile app on Android [ https://substack.com/redirect/b214fb69-1396-4d55-944b-1431a71238fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Google are adding smart home integration to their Gemini chatbot - so far on Android only.
Have they considered the risk of prompt injection? It looks like they have, at least a bit:
Important: Home controls are for convenience only, not safety- or security-critical purposes. Don't rely on Gemini for requests that could result in injury or harm if they fail to start or stop.
The Google Home extension can’t perform some actions on security devices, like gates, cameras, locks, doors, and garage doors. For unsupported actions, the Gemini app gives you a link to the Google Home app where you can control those devices.
It can control lights and power, climate control, window coverings, TVs and speakers and "other smart devices, like washers, coffee makers, and vacuums".
I imagine we will see some security researchers having a lot of fun with this shortly.
Quote 2024-11-01
Lord Clement-Jones: To ask His Majesty's Government what assessment they have made of the cybersecurity risks posed by prompt injection attacks to the processing by generative artificial intelligence of material provided from outside government, and whether any such attacks have been detected thus far.
Lord Vallance of Balham: Security is central to HMG's Generative AI Framework [ https://substack.com/redirect/2e16221e-5c78-4ad4-a541-15257cb37c5f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which was published in January this year and sets out principles for using generative AI safely and responsibly. The risks posed by prompt injection attacks, including from material provided outside of government, have been assessed as part of this framework and are continually reviewed. The published Generative AI Framework for HMG specifically includes Prompt Injection attacks, alongside other AI specific cyber risks.
Question for Department for Science, Innovation and Technology [ https://substack.com/redirect/23c3da25-26b8-4313-ac46-2e7ac0f91087?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-01 Claude API: PDF support (beta) [ https://substack.com/redirect/1f3e8ed6-2418-4866-9b06-193c6cdeef3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Claude 3.5 Sonnet now accepts PDFs as attachments:
The new Claude 3.5 Sonnet (claude-3-5-sonnet-20241022) model now supports PDF input and understands both text and visual content within documents.
I just released llm-claude-3 0.7 [ https://substack.com/redirect/f07496cf-9e08-4d2c-a2d4-e4d5d65d8f2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with support for the new attachment type (attachments are a very new feature [ https://substack.com/redirect/9a378b9e-d016-4476-b33b-dac3cb331021?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), so now you can do this:
llm install llm-claude-3 --upgrade
llm -m claude-3.5-sonnet 'extract text' -a mydoc.pdf
Visual PDF analysis can also be turned on for the Claude.ai application [ https://substack.com/redirect/836946aa-9b1b-4432-b28c-3ef900f19070?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Also new today: Claude now offers a free (albeit rate-limited) token counting API [ https://substack.com/redirect/fd51b152-b81a-4bed-b0a1-53efd8bc74fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This addresses a complaint I've had for a while: previously it wasn't possible to accurately estimate the cost of a prompt before sending it to be executed.
Link 2024-11-01 From Naptime to Big Sleep: Using Large Language Models To Catch Vulnerabilities In Real-World Code [ https://substack.com/redirect/dae9643b-d6fa-4ddd-b9a8-a053d7c5e79e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Google's Project Zero [ https://substack.com/redirect/02568b0f-9a37-4805-befb-974288950330?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] security team used a system based around Gemini 1.5 Pro to find a previously unreported security vulnerability in SQLite (a stack buffer underflow), in time for it to be fixed prior to making it into a release.
A key insight here is that LLMs are well suited for checking for new variants of previously reported vulnerabilities:
A key motivating factor for Naptime and now for Big Sleep has been the continued in-the-wild discovery of exploits for variants of previously found and patched vulnerabilities. As this trend continues, it's clear that fuzzing is not succeeding at catching such variants, and that for attackers, manual variant analysis is a cost-effective approach.
We also feel that this variant-analysis task is a better fit for current LLMs than the more general open-ended vulnerability research problem. By providing a starting point – such as the details of a previously fixed vulnerability – we remove a lot of ambiguity from vulnerability research, and start from a concrete, well-founded theory: "This was a previous bug; there is probably another similar one somewhere".
LLMs are great at pattern matching. It turns out feeding in a pattern describing a prior vulnerability is a great way to identify potential new ones.
Link 2024-11-02 SmolLM2 [ https://substack.com/redirect/389d6767-9761-4a8c-b7da-9e939120c3cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New from Loubna Ben Allal [ https://substack.com/redirect/3ead0bf2-46a3-4037-93ec-b632fc2db8e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and her research team at Hugging Face:
SmolLM2 is a family of compact language models available in three size: 135M, 360M, and 1.7B parameters. They are capable of solving a wide range of tasks while being lightweight enough to run on-device. [...]
It was trained on 11 trillion tokens using a diverse dataset combination: FineWeb-Edu, DCLM, The Stack, along with new mathematics and coding datasets that we curated and will release soon.
The model weights are released under an Apache 2 license. I've been trying these out using my llm-gguf [ https://substack.com/redirect/20876e62-4bf8-48b4-bb7e-7ec2463aba71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin for LLM [ https://substack.com/redirect/9e3ba109-f883-444f-9080-a8dcb45b014c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and my first impressions are really positive.
Here's a recipe to run a 1.7GB Q8 quantized model from lmstudio-community [ https://substack.com/redirect/6cf22678-16e0-4eb3-8ec7-9eec9368056a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm install llm-gguf
llm gguf download-model https://huggingface.co/lmstudio-community/SmolLM2-1.7B-Instruct-GGUF/resolve/main/SmolLM2-1.7B-Instruct-Q8_0.gguf -a smol17
llm chat -m smol17
Or at the other end of the scale, here's how to run the 138MB Q8 quantized 135M model [ https://substack.com/redirect/5debb696-3d6e-4a63-8eb8-8a7c66cdc8c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm gguf download-model https://huggingface.co/lmstudio-community/SmolLM2-135M-Instruct-GGUF/resolve/main/SmolLM2-135M-Instruct-Q8_0.gguf' -a smol135m
llm chat -m smol135m
The blog entry to accompany SmolLM2 should be coming soon, but in the meantime here's the entry from July introducing the first version: SmolLM - blazingly fast and remarkably powerful  [ https://substack.com/redirect/4d6d543e-69ae-4b9e-b074-cd3294382ac4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-11-02 Please publish and share more [ https://substack.com/redirect/9bf6751f-a140-4c21-b886-d4dae19dbb05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
💯 to all of this by Jeff Triplett:
Friends, I encourage you to publish more, indirectly meaning you should write more and then share it. [...]
You don’t have to change the world with every post. You might publish a quick thought or two that helps encourage someone else to try something new, listen to a new song, or binge-watch a new series.
Jeff shares my opinion on conclusions: giving myself permission to hit publish even when I haven't wrapped everything up neatly was a huge productivity boost for me:
Our posts are done when you say they are. You do not have to fret about sticking to landing and having a perfect conclusion. Your posts, like this post, are done after we stop writing.
And another 💯 to this footnote:
PS: Write and publish before you write your own static site generator or perfect blogging platform. We have lost billions of good writers to this side quest because they spend all their time working on the platform instead of writing.
Link 2024-11-02 Claude Token Counter [ https://substack.com/redirect/0e1257b8-e3c5-4a39-b793-d0b960450f1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic released a token counting API [ https://substack.com/redirect/fd51b152-b81a-4bed-b0a1-53efd8bc74fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Claude a few days ago.
I built this tool for running prompts, images and PDFs against that API to count the tokens in them.
The API is free (albeit rate limited), but you'll still need to provide your own API key in order to use it.
Here's the source code [ https://substack.com/redirect/7b0f33c0-a1c0-4c54-b195-245ce9be5194?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I built this using two sessions with Claude - one to build the initial tool [ https://substack.com/redirect/dd5de88c-a7a3-489f-90da-6338c9761972?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]and a second to add PDF and image support [ https://substack.com/redirect/f98b51a7-038a-48b0-a656-e1eb4656c2f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. That second one is a bit of a mess - it turns out if you drop an HTML file onto a Claude conversation it converts it to Markdown for you, but I wanted it to modify the original HTML source.
The API endpoint also allows you to specify a model, but as far as I can tell from running some experiments the token count was the same for Haiku, Opus and Sonnet 3.5.
Link 2024-11-03 Docling [ https://substack.com/redirect/171130cf-a401-4662-be35-ab4d151dc81b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
MIT licensed document extraction Python library from the Deep Search team at IBM, who released Docling v2 [ https://substack.com/redirect/5a92a46c-ddfd-4418-8ed2-ef1a29210836?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on October 16th.
Here's the Docling Technical Report [ https://substack.com/redirect/17a332ee-35a7-46bb-98b9-2be0e1ad1f9b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] paper from August, which provides details of two custom models: a layout analysis model for figuring out the structure of the document (sections, figures, text, tables etc) and a TableFormer model specifically for extracting structured data from tables.
Those models are available on Hugging Face [ https://substack.com/redirect/21ea02ac-2186-455f-9d3c-ebf7cef2b015?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here's how to try out the Docling CLI interface using uvx (avoiding the need to install it first - though since it downloads models it will take a while to run the first time):
uvx docling mydoc.pdf --to json --to md
This will output a mydoc.json file with complex layout information and a mydoc.md Markdown file which includes Markdown tables where appropriate.
The Python API [ https://substack.com/redirect/7868daa0-7f9d-4e63-ad41-59bce7a64e3c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a lot more comprehensive. It can even extract tables as Pandas DataFrames [ https://substack.com/redirect/f2d049cc-a042-470a-bfb1-6ee17b1736de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
from docling.document_converter import DocumentConverter
converter = DocumentConverter
result = converter.convert("document.pdf")
for table in result.document.tables:
df = table.export_to_dataframe
print(df)
I ran that inside uv run --with docling python. It took a little while to run, but it demonstrated that the library works.
Link 2024-11-03 California Clock Change [ https://substack.com/redirect/5f798853-a78a-421a-8f5e-090a2bbf3ea6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The clocks go back in California tonight and I finally built my dream application for helping me remember if I get an hour extra of sleep or not, using a Claude Artifact. Here's the transcript [ https://substack.com/redirect/faaf40ea-9760-4a7e-ad7b-cde14ebf5716?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This is one of my favorite examples yet of the kind of tiny low stakes utilities I'm building with Claude Artifacts because the friction involved in churning out a working application has dropped almost to zero.
(I added another feature: it now includes a note [ https://substack.com/redirect/d1748fa5-38c9-4b57-b53e-cfdfe7370047?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]of what time my Dog thinks it is if the clocks have recently changed.)
Quote 2024-11-03
Building technology in startups is all about having the right level of tech debt. If you have none, you’re probably going too slow and not prioritizing product-market fit and the important business stuff. If you get too much, everything grinds to a halt. Plus, tech debt is a “know it when you see it” kind of thing, and I know that my definition of “a bunch of tech debt” is, to other people, “very little tech debt.”
Tom MacWright [ https://substack.com/redirect/669cb03d-2e41-42c1-a20c-bbcac1b8035a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-04 Nous Hermes 3 [ https://substack.com/redirect/fcc4351b-6c46-4916-b37b-183d62887c77?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The Nous Hermes family of fine-tuned models have a solid reputation. Their most recent release came out in August, based on Meta's Llama 3.1:
Our training data aggressively encourages the model to follow the system and instruction prompts exactly and in an adaptive manner. Hermes 3 was created by fine-tuning Llama 3.1 8B, 70B and 405B, and training on a dataset of primarily synthetically generated responses. The model boasts comparable and superior performance to Llama 3.1 while unlocking deeper capabilities in reasoning and creativity.
The model weights are on Hugging Face [ https://substack.com/redirect/653a42a3-f1a0-4564-8700-829e5a21454e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], including GGUF versions of the 70B [ https://substack.com/redirect/31df1f11-7d10-45cb-9160-79cc6e796c01?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and 8B [ https://substack.com/redirect/0f495e4f-883c-4d81-9a23-ab47b44f349c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]models. Here's how to try the 8B model (a 4.58GB download) using the llm-gguf plugin [ https://substack.com/redirect/20876e62-4bf8-48b4-bb7e-7ec2463aba71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm install llm-gguf
llm gguf download-model 'https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF/resolve/main/Hermes-3-Llama-3.1-8B.Q4_K_M.gguf' -a Hermes-3-Llama-3.1-8B
llm -m Hermes-3-Llama-3.1-8B 'hello in spanish'
Nous Research partnered with Lambda Labs [ https://substack.com/redirect/0168ddd2-a891-4eb1-86ac-3a745e50c573?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to provide inference APIs. It turns out Lambda host quite a few models [ https://substack.com/redirect/e00709ff-c58b-4234-8828-427e7faf5e22?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] now, currently providing free inference to users with an API key [ https://substack.com/redirect/9cfe8f78-45ea-4461-a021-c55cc37e4d40?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I just released the first alpha of a llm-lambda-labs [ https://substack.com/redirect/34e6ba35-9745-4f3c-a972-d30ab752a8cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]plugin. You can use that to try the larger 405b model (very hard to run on a consumer device) like this:
llm install llm-lambda-labs
llm keys set lambdalabs
# Paste key here
llm -m lambdalabs/hermes3-405b 'short poem about a pelican with a twist'
Here's the source code [ https://substack.com/redirect/a843e58e-4f60-4b4c-851d-ae75867d36a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the new plugin, which I based on llm-mistral [ https://substack.com/redirect/a237f0ad-80ab-4621-9a0b-efb4410eab84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The plugin uses httpx-sse [ https://substack.com/redirect/f117a750-c2fb-4114-ade7-8b86f3efd8af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to consume the stream of tokens from the API.
Link 2024-11-04 New OpenAI feature: Predicted Outputs [ https://substack.com/redirect/1be42842-2f1c-4838-ac4d-cef8bde97e9f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Interesting new ability of the OpenAI API - the first time I've seen this from any vendor.
If you know your prompt is mostly going to return the same content - you're requesting an edit to some existing code, for example - you can now send that content as a "prediction" and have GPT-4o or GPT-4o mini use that to accelerate the returned result.
OpenAI's documentation says:
When providing a prediction, any tokens provided that are not part of the final completion are charged at completion token rates.
I initially misunderstood this as meaning you got a price reduction in addition to the latency improvement, but that's not the case: in the best possible case it will return faster and you won't be charged anything extra over the expected cost for the prompt, but the more it differs from your permission the more extra tokens you'll be billed for.
I ran the example from the documentation both with and without the prediction and got these results. Without the prediction:
"usage": {
"prompt_tokens": 150,
"completion_tokens": 118,
"total_tokens": 268,
"completion_tokens_details": {
"accepted_prediction_tokens": 0,
"audio_tokens": null,
"reasoning_tokens": 0,
"rejected_prediction_tokens": 0
}
That took 5.2 seconds and cost 0.1555 cents.
With the prediction:
"usage": {
"prompt_tokens": 166,
"completion_tokens": 226,
"total_tokens": 392,
"completion_tokens_details": {
"accepted_prediction_tokens": 49,
"audio_tokens": null,
"reasoning_tokens": 0,
"rejected_prediction_tokens": 107
}
That took 3.3 seconds and cost 0.2675 cents.
Further details from OpenAI's Steve Coffey [ https://substack.com/redirect/7967b94b-b393-4b8b-bcc4-fb2023bf179a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
We are using the prediction to do speculative decoding during inference, which allows us to validate large batches of the input in parallel, instead of sampling token-by-token!
[...] If the prediction is 100% accurate, then you would see no cost difference. When the model diverges from your speculation, we do additional sampling to “discover” the net-new tokens, which is why we charge rejected tokens at completion time rates.
Quote 2024-11-05
You already know [ https://substack.com/redirect/44dc7d9b-072b-44dd-b539-d83feb095e7f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Donald Trump. He is unfit [ https://substack.com/redirect/01fd63c2-92ae-4ce6-a887-707a90f4172e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]to lead. Watch him [ https://substack.com/redirect/d94f4df5-dd72-4a4d-b6dc-a15b3554fea0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Listen to those [ https://substack.com/redirect/ca0a1169-45e9-490f-89dc-1411597a9cf6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] who know him best [ https://substack.com/redirect/10b9d4c4-ee52-4948-bb04-07f71fa7e8cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. He tried to subvert [ https://substack.com/redirect/307c8996-703e-4e2a-9dad-66013b49915d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] an election and remains a threat [ https://substack.com/redirect/9754bed4-9f62-4898-82b4-5e35cbc81591?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to democracy. He helped overturn Roe, with terrible consequences [ https://substack.com/redirect/19dd451c-998a-44d2-83d5-4787f3872af3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Mr. Trump's corruption [ https://substack.com/redirect/de5a0d36-82ea-47e5-bc5e-011d90fdb4fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and lawlessness [ https://substack.com/redirect/5b9bc79e-3009-4a88-b469-352efffdde1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] go beyond [ https://substack.com/redirect/80170bf5-8317-4da9-927f-2066991014d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] elections [ https://substack.com/redirect/41edea98-9f56-45e5-aae8-79bbeeb61832?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: It's his whole ethos [ https://substack.com/redirect/82ca212c-991f-4c9f-95ee-ffd05dccfe2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. He lies [ https://substack.com/redirect/4fe03381-4fbc-4bff-b084-eeb984b08f48?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]without limit [ https://substack.com/redirect/3b7c49a7-cddd-4053-ba70-335b8e898c62?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. If he's re-elected, the G.O.P. won't restrain [ https://substack.com/redirect/c49a3f40-f10c-4a0f-97fe-92403cc23dd9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] him. Mr. Trump will use the government [ https://substack.com/redirect/f09967e0-944e-4523-8a72-75a4e17c5ab5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to go after opponents [ https://substack.com/redirect/b6b23904-358d-4296-8d51-d75429cb0c94?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. He will pursue a cruel [ https://substack.com/redirect/727d817b-b4fc-4c4c-b674-7d4d6b62d3fd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] policy of mass deportations [ https://substack.com/redirect/8b1b0e68-98c3-4c1e-8170-f3c6241ae805?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. He will wreak havoc on the poor [ https://substack.com/redirect/d3fe5c5c-42e2-45fd-ad55-476fabf207d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the middle class [ https://substack.com/redirect/7596c17b-51b6-4681-be83-41bb24e34455?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]and employers [ https://substack.com/redirect/88ffaa44-0139-4123-af3b-5bf246612ec6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Another Trump term will damage the climate [ https://substack.com/redirect/4440091f-da3a-468d-9a6f-7e08076e897a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], shatter alliances [ https://substack.com/redirect/63a22f38-d273-4169-94df-afab1b1156cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and strengthen autocrats [ https://substack.com/redirect/7487549b-fd99-4ac4-beca-3bbb7a794be8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Americans should demand better [ https://substack.com/redirect/e468f5c2-caa4-42c9-b757-e771ba117f87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Vote.
NY Times Editorial Board [ https://substack.com/redirect/be7c20d5-bae6-4c49-8d0f-22252bfebccf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEV4T1RZNU5qSXNJbWxoZENJNk1UY3pNRGMzT0RJd01Td2laWGh3SWpveE56WXlNekUwTWpBeExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuWnp6TjB5VkdncnptaENBM3FYR09XbkZNNHk1WndmRl9tVTNRLW9SNzNmYyIsInAiOjE1MTE5Njk2MiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzMwNzc4MjAxLCJleHAiOjE3MzMzNzAyMDEsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.PcWlg8X1lexYn9IR0O0CnjE1wzZUNbC_ZwbkX3eEPTc?
