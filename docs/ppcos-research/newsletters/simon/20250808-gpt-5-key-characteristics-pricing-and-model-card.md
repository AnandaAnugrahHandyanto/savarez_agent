# GPT-5: Key characteristics, pricing and model card

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-08-08T18:03:26.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/gpt-5-key-characteristics-pricing

In this newsletter:
GPT-5: Key characteristics, pricing and model card
OpenAI's new open weight (Apache 2) models are really good
ChatGPT agent's user-agent
The ChatGPT sharing dialog demonstrates how difficult it is to design privacy preferences
Plus 11 links and 4 quotations and 1 note
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
GPT-5: Key characteristics, pricing and model card [ https://substack.com/redirect/57d09649-c5a4-4178-b3eb-091989f5ae1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-08-07
I've had preview access to the new GPT-5 model family for the past two weeks (see related video [ https://substack.com/redirect/05114a4a-4668-45d3-b2e4-ab23aa6bd1e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and have been using GPT-5 as my daily-driver. It's my new favorite model. It's still an LLM - it's not a dramatic departure from what we've had before - but it rarely screws up and generally feels competent or occasionally impressive at the kinds of things I like to use models for.
I've collected a lot of notes over the past two weeks, so I've decided to break them up into a series of posts [ https://substack.com/redirect/d5ee9deb-b1dd-4d1c-b5cb-e097caf164ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This first one will cover key characteristics of the models, how they are priced and what we can learn from the GPT-5 system card [ https://substack.com/redirect/cb617afe-8f76-47ef-8539-a8e9f26351d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Key model characteristics [ https://substack.com/redirect/b656907b-16e6-4f91-806f-7cfb027e2f19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Position in the OpenAI model family [ https://substack.com/redirect/ee3c8a39-a1c2-4394-b2c7-608698974ecd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Pricing is aggressively competitive [ https://substack.com/redirect/5dcc0c61-20ff-44c4-8963-8596085cd8f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
More notes from the system card [ https://substack.com/redirect/584a8861-a1bd-4c61-8fa9-0a4c08502ed3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Prompt injection in the system card [ https://substack.com/redirect/07698df5-7391-41a2-b6f6-23efbf44b02e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thinking traces in the API [ https://substack.com/redirect/c901c452-43b7-4bd0-951f-6518b7a3cddc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
And some SVGs of pelicans [ https://substack.com/redirect/1a08e738-14e3-4b0f-ad52-6f70c986b37b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Key model characteristics
Let's start with the fundamentals. GPT-5 in ChatGPT is a weird hybrid that switches between different models. Here's what the system card says about that (my highlights in bold):
GPT-5 is a unified system with a smart and fast model that answers most questions, a deeper reasoning model for harder problems, and a real-time router that quickly decides which model to use based on conversation type, complexity, tool needs, and explicit intent (for example, if you say “think hard about this” in the prompt). [...] Once usage limits are reached, a mini version of each model handles remaining queries. In the near future, we plan to integrate these capabilities into a single model.
GPT-5 in the API is simpler: it's available as three models - regular, mini and nano - which can each be run at one of four reasoning levels: minimal (a new level not previously available for other OpenAI reasoning models), low, medium or high.
The models have an input limit of 272,000 tokens and an output limit (which includes invisible reasoning tokens) of 128,000 tokens. They support text and image for input, text only for output.
I've mainly explored full GPT-5. My verdict: it's just good at stuff. It doesn't feel like a dramatic leap ahead from other LLMs but it exudes competence - it rarely messes up, and frequently impresses me. I've found it to be a very sensible default for everything that I want to do. At no point have I found myself wanting to re-run a prompt against a different model to try and get a better result.
Here are the OpenAI model pages for GPT-5 [ https://substack.com/redirect/c5b2d611-a1a2-462c-8e0a-80b01d4a1ed3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], GPT-5 mini [ https://substack.com/redirect/e37c6397-beb3-42d2-88ed-0f3f4e845c3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and GPT-5 nano [ https://substack.com/redirect/612d871e-22ed-4512-8a77-c656e63ad82d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Knowledge cut-off is September 30th 2024 for GPT-5 and May 30th 2024 for GPT-5 mini and nano.
Position in the OpenAI model family
The three new GPT-5 models are clearly intended as a replacement for most of the rest of the OpenAI line-up. This table from the system card is useful, as it shows how they see the new models fitting in:
Previous model GPT-5 model GPT-4o gpt-5-main GPT-4o-mini gpt-5-main-mini OpenAI o3 gpt-5-thinking OpenAI o4-mini gpt-5-thinking-mini GPT-4.1-nano gpt-5-thinking-nano OpenAI o3 Pro gpt-5-thinking-pro
That "thinking-pro" model is currently only available via ChatGPT where it is labelled as "GPT-5 Pro" and limited to the $200/month tier. It uses "parallel test time compute".
The only capabilities not covered by GPT-5 are audio input/output and image generation. Those remain covered by models like GPT-4o Audio [ https://substack.com/redirect/c72d4687-e41b-4fe9-b244-e1294bd848a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and GPT-4o Realtime [ https://substack.com/redirect/55c961a5-67fd-488a-b509-fac357ec950e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and their mini variants and the GPT Image 1 [ https://substack.com/redirect/ae4fbe7e-590b-463d-a773-ca886fa52f1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and DALL-E image generation models.
Pricing is aggressively competitive
The pricing is aggressively competitive with other providers.
GPT-5: $1.25/million for input, $10/million for output
GPT-5 Mini: $0.25/m input, $2.00/m output
GPT-5 Nano: $0.05/m input, $0.40/m output
GPT-5 is priced at half the input cost of GPT-4o, and maintains the same price for output. Those invisible reasoning tokens count as output tokens so you can expect most prompts to use more output tokens than their GPT-4o equivalent (unless you set reasoning effort to "minimal").
The discount for token caching is significant too: 90% off on input tokens that have been used within the previous few minutes. This is particularly material if you are implementing a chat UI where the same conversation gets replayed every time the user adds another prompt to the sequence.
Here's a comparison table I put together showing the new models alongside the most comparable models from OpenAI's competition:
Model Input $/m Output $/m Claude Opus 4.1 15.00 75.00 Claude Sonnet 4 3.00 15.00 Grok 4 3.00 15.00 Gemini 2.5 Pro (>200,000) 2.50 15.00 GPT-4o 2.50 10.00 GPT-4.1 2.00 8.00 o3 2.00 8.00 Gemini 2.5 Pro (

L300,120
L450,250
L300,350
Z"
fill="#e0e0e0" stroke="#555" stroke-width="4"/>

But you can't put comments inside attributes like that. I fixed this to get the above image.
Pelican on reasoning=medium
I tried again on medium [ https://substack.com/redirect/43213066-10fe-455d-a36b-4599d91807b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This time it thought for 4.44 seconds and gave me this, at 55 tokens/second:
Pelican on reasoning=high
And then on high [ https://substack.com/redirect/d9cff742-f563-427f-9dde-aca3a3920961?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. My first attempt here failed because it hit the default LM Studio 4096 context limit - so I reloaded the model and set the new limit to the maximum possible.
It jumped up to using 17.35GB RAM (I imagine it might use a lot more with a longer prompt) and after thinking for 5 minutes and 50 seconds (!) gave me this:
It thought really hard to get there. Here's a snippet of that transcript [ https://substack.com/redirect/d9cff742-f563-427f-9dde-aca3a3920961?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
But maybe we want seat below body bottom? Actually seat should be between body and pedals, not above body bottom. Wait, typical bicycle: seat post goes from bottom bracket upward to the seat. The seat sits on top of the seat tube (vertical). So the seat is above bottom bracket. In our representation, the seat is at y=250-255. Body center at 245, body bottom at 265. So body bottom is below seat. That means the pelican's body is below the seat? Actually no: body bottom extends to 265; seat top is at 250; so seat sits above body bottom by about 15 units. That seems plausible because seat should be slightly above body, but body bottom is at 265 > seat top 255. [...]
I've seen this from other local reasoning models too: they can really overthink this kind of problem! I don't know if there's any pelican SVG that's worth waiting nearly six minutes for.
Space invaders with gpt-oss-20b
Given how long high took I switched back to medium for my next experiment:
Write an HTML and JavaScript page implementing space invaders
It thought for 10.78 seconds [ https://substack.com/redirect/19683dbc-5a13-454d-8f65-06d6fbfcbf91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and produced this:
You can play that here [ https://substack.com/redirect/182f0a68-5c5b-4768-b09e-4be4542081b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It's not the best I've seen - I was more impressed by GLM 4.5 Air [ https://substack.com/redirect/7c1afa8d-0138-4bcc-b974-edb9a6abee31?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - but it's very competent for a model that only uses 12GB of my RAM (GLM 4.5 Air used 47GB).
Trying gpt-oss-120b via API providers
I don't quite have the resources on my laptop to run the larger model. Thankfully it's already being hosted by a number of different API providers.
OpenRouter already lists three [ https://substack.com/redirect/982775d0-83c4-435e-b385-f53d3fb4a05d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Fireworks, Groq and Cerebras. (Update: now also Parasail and Baseten.)
Cerebras is fast, so I decided to try them first.
I installed the llm-cerebras [ https://substack.com/redirect/437d695a-01eb-4e08-962e-aa3cbba79bac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin and ran the refresh command to ensure it had their latest models:
llm install -U llm-cerebras jsonschema
llm cerebras refresh
(Installing jsonschema worked around a warning message.)
Output:
Refreshed 10 Cerebras models:
- cerebras-deepseek-r1-distill-llama-70b
- cerebras-gpt-oss-120b
- cerebras-llama-3.3-70b
- cerebras-llama-4-maverick-17b-128e-instruct
- cerebras-llama-4-scout-17b-16e-instruct
- cerebras-llama3.1-8b
- cerebras-qwen-3-235b-a22b-instruct-2507
- cerebras-qwen-3-235b-a22b-thinking-2507
- cerebras-qwen-3-32b
- cerebras-qwen-3-coder-480b
Now:
llm -m cerebras-gpt-oss-120b \
'Generate an SVG of a pelican riding a bicycle'
Cerebras runs the new model at between 2 and 4 thousands tokens per second!
To my surprise this one had the same comments-in-attributes bug [ https://substack.com/redirect/d5cda0c4-d476-4180-aef3-fb0314e66e95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that we saw with oss-20b earlier. I fixed those and got this pelican:
That bug appears intermittently - I've not seen it on some of my other runs of the same prompt.
The llm-openrouter [ https://substack.com/redirect/7d9e9601-fcd8-42e9-8b8d-e7e6c2f602f0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin also provides access to the models, balanced across the underlying providers. You can use that like so:
llm install llm-openrouter
llm keys set openrouter
# Paste API key here
llm -m openrouter/openai/gpt-oss-120b "Say hi"
llama.cpp is coming very shortly
The llama.cpp pull request for gpt-oss [ https://substack.com/redirect/a7605abf-cbe1-49d6-be37-64877e478538?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was landed less than an hour ago. It's worth browsing through the coded - a lot of work went into supporting this new model, spanning 48 commits to 83 different files. Hopefully this will land in the llama.cpp Homebrew package [ https://substack.com/redirect/93ebae95-c46f-4fa6-aca5-b4de5978d3d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] within the next day or so, which should provide a convenient way to run the model via llama-server and friends.
gpt-oss:20b in Ollama
Ollama also have gpt-oss [ https://substack.com/redirect/fd25d47e-e7be-4b01-beee-e57218976ca2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], requiring an update to their app.
I fetched that 14GB model like this:
ollama pull gpt-oss:20b
Now I can use it with the new Ollama native app, or access it from LLM [ https://substack.com/redirect/04654292-9745-438b-b085-561b71ec1ab8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
llm install llm-ollama
llm -m gpt-oss:20b 'Hi'
This also appears to use around 13.26GB of system memory while running a prompt.
Ollama also launched Ollama Turbo [ https://substack.com/redirect/860a55a8-8519-4f4f-a86a-9ff560164e67?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today, offering the two OpenAI models as a paid hosted service:
Turbo is a new way to run open models using datacenter-grade hardware. Many new models are too large to fit on widely available GPUs, or run very slowly. Ollama Turbo provides a way to run these models fast while using Ollama's App, CLI, and API.
Training details from the model card
Here are some interesting notes about how the models were trained from the model card [ https://substack.com/redirect/95ba0cca-860d-46d2-ae43-1e91a92e48f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (PDF):
Data: We train the models on a text-only dataset with trillions of tokens, with a focus on STEM, coding, and general knowledge. To improve the safety of the model, we filtered the data for harmful content in pre-training, especially around hazardous biosecurity knowledge, by reusing the CBRN pre-training filters from GPT-4o. Our model has a knowledge cutoff of June 2024.
Training: The gpt-oss models trained on NVIDIA H100 GPUs using the PyTorch framework with expert-optimized Triton kernels. The training run for gpt-oss-120b required 2.1 million H100-hours to complete, with gpt-oss-20b needing almost 10x fewer. [...]
Thunder Compute's article NVIDIA H100 Pricing (August 2025): Cheapest On-Demand Cloud GPU Rates [ https://substack.com/redirect/f0c7aaf8-7509-4545-8df7-e94711a7df49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] lists prices from around $2/hour to $11/hour, which would indicate a training cost of the 120b model between $4.2m and $23.1m and the 20b between $420,000 and $2.3m.
After pre-training, we post-train the models using similar CoT RL techniques as OpenAI o3. This procedure teaches the models how to reason and solve problems using CoT and teaches the model how to use tools. Because of the similar RL techniques, these models have a personality similar to models served in our first-party products like ChatGPT. Our training dataset consists of a wide range of problems from coding, math, science, and more.
The models have additional special training to help them use web browser and Python (Jupyter notebook) tools more effectively:
During post-training, we also teach the models to use different agentic tools:
A browsing tool, that allows the model to call search and open functions to interact with the web. This aids factuality and allows the models to fetch info beyond their knowledge cutoff.
A python tool, which allows the model to run code in a stateful Jupyter notebook environment.
Arbitrary developer functions, where one can specify function schemas in a Developer message similar to the OpenAI API. The definition of function is done within our harmony format.
There's a corresponding section about Python tool usage [ https://substack.com/redirect/109181c4-dade-4dec-b9f9-5d1e9ede9b52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the openai/gpt-oss repository README.
OpenAI Harmony, a new format for prompt templates
One of the gnarliest parts of implementing harnesses for LLMs is handling the prompt template format.
Modern prompts are complicated beasts. They need to model user v.s. assistant conversation turns, and tool calls, and reasoning traces and an increasing number of other complex patterns.
openai/harmony [ https://substack.com/redirect/671c03d1-26a1-4a2a-9243-fe8af83c4b37?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a brand new open source project from OpenAI (again, Apache 2) which implements a new response format that was created for the gpt-oss models. It's clearly inspired by their new-ish Responses API [ https://substack.com/redirect/600dedad-4946-4cae-9d7d-ab2105029ca3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The format is described in the new OpenAI Harmony Response Format [ https://substack.com/redirect/5d44b6b0-1c4e-4e15-85fb-8ede3ead7ec2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] cookbook document. It introduces some concepts that I've not seen in open weight models before:
system, developer, user, assistant and tool roles - many other models only use user and assistant, and sometimes system and tool.
Three different channels for output: final, analysis and commentary. Only the final channel is default intended to be visible to users. analysis is for chain of thought and commentary is sometimes used for tools.
That channels concept has been present in ChatGPT for a few months, starting with the release of o3.
The details of the new tokens used by Harmony caught my eye:
Token Purpose ID  Start of message header 200006  End of message 200007  Start of message content 200008  Start of channel info 200005  Data type for tool call 200003  Stop after response 200002  Call a tool 200012
Those token IDs are particularly important. They are part of a new token vocabulary called o200k_harmony, which landed in OpenAI's tiktoken tokenizer library this morning [ https://substack.com/redirect/b2725325-1038-4543-afdc-2995f4a4ffb2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
In the past I've seen models get confused by special tokens - try pasting  into a model and see what happens.
Having these special instruction tokens formally map to dedicated token IDs should hopefully be a whole lot more robust!
The Harmony repo itself includes a Rust library and a Python library (wrapping that Rust library) for working with the new format in a much more ergonomic way.
I tried one of their demos using uv run to turn it into a shell one-liner:
uv run --python 3.12 --with openai-harmony python -c '
from openai_harmony import *
from openai_harmony import DeveloperContent
enc = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
convo = Conversation.from_messages([
Message.from_role_and_content(
Role.SYSTEM,
SystemContent.new,
),
Message.from_role_and_content(
Role.DEVELOPER,
DeveloperContent.new.with_instructions("Talk like a pirate!")
),
Message.from_role_and_content(Role.USER, "Arrr, how be you?"),
])
tokens = enc.render_conversation_for_completion(convo, Role.ASSISTANT)
print(tokens)'
Which outputs:
[200006, 17360, 200008, 3575, 553, 17554, 162016, 11, 261, 4410, 6439, 2359, 22203, 656, 7788, 17527, 558, 87447, 100594, 25, 220, 1323, 19, 12, 3218, 279, 30377, 289, 25, 14093, 279, 2, 13888, 18403, 25, 8450, 11, 49159, 11, 1721, 13, 21030, 2804, 413, 7360, 395, 1753, 3176, 13, 200007, 200006, 77944, 200008, 2, 68406, 279, 37992, 1299, 261, 96063, 0, 200007, 200006, 1428, 200008, 8977, 81, 11, 1495, 413, 481, 30, 200007, 200006, 173781]
Note those token IDs like 200006 corresponding to the special tokens listed above.
The open question for me: how good is tool calling?
There's one aspect of these models that I haven't explored in detail yet: tool calling. How these work is clearly a big part of the new Harmony format, but the packages I'm using myself (around my own LLM tool calling [ https://substack.com/redirect/aa31870d-ef23-46df-ba83-e8b84a553f88?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] support) need various tweaks and fixes to start working with that new mechanism.
Tool calling currently represents my biggest disappointment with local models that I've run on my own machine. I've been able to get them to perform simple single calls, but the state of the art these days is wildly more ambitious than that.
Systems like Claude Code can make dozens if not hundreds of tool calls over the course of a single session, each one adding more context and information to a single conversation with an underlying model.
My experience to date has been that local models are unable to handle these lengthy conversations. I'm not sure if that's inherent to the limitations of my own machine, or if it's something that the right model architecture and training could overcome.
OpenAI make big claims about the tool calling capabilities of these new models. I'm looking forward to seeing how well they perform in practice.
Competing with the Chinese open models
I've been writing a lot about the flurry of excellent open weight models [ https://substack.com/redirect/58af17cd-375d-42f4-85ec-5c49c66b44a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] released by Chinese AI labs over the past few months - all of them very capable and most of them under Apache 2 or MIT licenses.
Just last week I said [ https://substack.com/redirect/52a59b24-0afa-46a9-aaed-9b5c94f0a7a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Something that has become undeniable this month is that the best available open weight models now come from the Chinese AI labs.
I continue to have a lot of love for Mistral, Gemma and Llama but my feeling is that Qwen, Moonshot and Z.ai have positively smoked them over the course of July. [...]
I can't help but wonder if part of the reason for the delay in release of OpenAI's open weights model comes from a desire to be notably better than this truly impressive lineup of Chinese models.
With the release of the gpt-oss models that statement no longer holds true. I'm waiting for the dust to settle and the independent benchmarks (that are more credible than my ridiculous pelicans) to roll out, but I think it's likely that OpenAI now offer the best available open weights models.
Update: Independent evaluations are beginning to roll in. Here's Artificial Analysis [ https://substack.com/redirect/ce3838bb-51d6-4fa1-ba9f-df844f17da07?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
gpt-oss-120b is the most intelligent American open weights model, comes behind DeepSeek R1 and Qwen3 235B in intelligence but offers efficiency benefits [...]
While the larger gpt-oss-120b does not come in above DeepSeek R1 0528’s score of 59 or Qwen3 235B 2507s score of 64, it is notable that it is significantly smaller in both total and active parameters than both of those models.
ChatGPT agent's user-agent [ https://substack.com/redirect/bd9a7349-7945-431e-840a-3fde53e620e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-08-04
I was exploring how ChatGPT agent works today. I learned some interesting things about how it exposes its identity through HTTP headers, then made a huge blunder in thinking it was leaking its URLs to Bingbot and Yandex... but it turned out that was a Cloudflare feature [ https://substack.com/redirect/79e49bf7-3ff8-45bd-8317-232d7bca6359?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that had nothing to do with ChatGPT.
ChatGPT agent is the recently released [ https://substack.com/redirect/317fe401-0d78-4fcc-8bbb-430d9f26d65d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (and confusingly named) ChatGPT feature that provides browser automation combined with terminal access as a feature of ChatGPT - replacing their previous Operator research preview [ https://substack.com/redirect/d03199bd-44ae-4cd4-afa9-1a4c8c2c24d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which is scheduled for deprecation on August 31st.
Investigating ChatGPT agent's user-agent
I decided to dig into how it works by creating a logged web URL endpoint using django-http-debug [ https://substack.com/redirect/89d707a8-9df8-4622-b5ab-fad78a307b79?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Then I told ChatGPT agent mode to explore that new page:
My logging captured these request headers:
Via: 1.1 heroku-router
Host: simonwillison.net
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7
Cf-Ray: 96a0f289adcb8e8e-SEA
Cookie: cf_clearance=zzV8W...
Server: Heroku
Cdn-Loop: cloudflare; loops=1
Priority: u=0, i
Sec-Ch-Ua: "Not)A;Brand";v="8", "Chromium";v="138"
Signature: sig1=:1AxfqHocTf693inKKMQ7NRoHoWAZ9d/vY4D/FO0+MqdFBy0HEH3ZIRv1c3hyiTrzCvquqDC8eYl1ojcPYOSpCQ==:
Cf-Visitor: {"scheme":"https"}
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36
Cf-Ipcountry: US
X-Request-Id: 45ef5be4-ead3-99d5-f018-13c4a55864d3
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: none
Sec-Fetch-User: ?1
Accept-Encoding: gzip, br
Accept-Language: en-US,en;q=0.9
Signature-Agent: "https://chatgpt.com"
Signature-Input: sig1=("@authority" "@method" "@path" "signature-agent");created=1754340838;keyid="otMqcjr17mGyruktGvJU8oojQTSMHlVm7uO-lrcqbdg";expires=1754344438;nonce="_8jbGwfLcgt_vUeiZQdWvfyIeh9FmlthEXElL-O2Rq5zydBYWivw4R3sV9PV-zGwZ2OEGr3T2Pmeo2NzmboMeQ";tag="web-bot-auth";alg="ed25519"
X-Forwarded-For: 2a09:bac5:665f:1541::21e:154, 172.71.147.183
X-Request-Start: 1754340840059
Cf-Connecting-Ip: 2a09:bac5:665f:1541::21e:154
Sec-Ch-Ua-Mobile: ?0
X-Forwarded-Port: 80
X-Forwarded-Proto: http
Sec-Ch-Ua-Platform: "Linux"
Upgrade-Insecure-Requests: 1

That Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 user-agent header is the one used by the most recent Chrome on macOS - which is a little odd here as the Sec-Ch-Ua-Platform : "Linux" indicates that the agent browser runs on Linux.
At first glance it looks like ChatGPT is being dishonest here by not including its bot identity in the user-agent header. I thought for a moment it might be reflecting my own user-agent, but I'm using Firefox on macOS and it identified itself as Chrome.
Then I spotted this header:
Signature-Agent: "https://chatgpt.com"
Which is accompanied by a much more complex header called Signature-Input:
Signature-Input: sig1=("@authority" "@method" "@path" "signature-agent");created=1754340838;keyid="otMqcjr17mGyruktGvJU8oojQTSMHlVm7uO-lrcqbdg";expires=1754344438;nonce="_8jbGwfLcgt_vUeiZQdWvfyIeh9FmlthEXElL-O2Rq5zydBYWivw4R3sV9PV-zGwZ2OEGr3T2Pmeo2NzmboMeQ";tag="web-bot-auth";alg="ed25519"
And a Signature header too.
These turn out to come from a relatively new web standard: RFC 9421 HTTP Message Signatures [ https://substack.com/redirect/4fffe3b3-4859-4bbd-84da-eb015cce1081?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]' published February 2024.
The purpose of HTTP Message Signatures is to allow clients to include signed data about their request in a way that cannot be tampered with by intermediaries. The signature uses a public key that's provided by the following well-known endpoint:
https://chatgpt.com/.well-known/http-message-signatures-directory
Add it all together and we now have a rock-solid way to identify traffic from ChatGPT agent: look for the Signature-Agent: "https://chatgpt.com" header and confirm its value by checking the signature in the Signature-Input and Signature headers.
And then came Bingbot and Yandex
Just over a minute after it captured that request, my logging endpoint got another request:
Via: 1.1 heroku-router
From: bingbot(at)microsoft.com
Host: simonwillison.net
Accept: */*
Cf-Ray: 96a0f4671d1fc3c6-SEA
Server: Heroku
Cdn-Loop: cloudflare; loops=1
Cf-Visitor: {"scheme":"https"}
User-Agent: Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36
Cf-Ipcountry: US
X-Request-Id: 6214f5dc-a4ea-5390-1beb-f2d26eac5d01
Accept-Encoding: gzip, br
X-Forwarded-For: 207.46.13.9, 172.71.150.252
X-Request-Start: 1754340916429
Cf-Connecting-Ip: 207.46.13.9
X-Forwarded-Port: 80
X-Forwarded-Proto: http
I pasted 207.46.13.9 into Microsoft's Verify Bingbot [ https://substack.com/redirect/dba9b88b-ec40-4636-882c-2ee83b5fa730?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool (after solving a particularly taxing CAPTCHA) and it confirmed that this was indeed a request from Bingbot.
I set up a second URL to confirm... and this time got a visit from Yandex!
Via: 1.1 heroku-router
From: support@search.yandex.ru
Host: simonwillison.net
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Cf-Ray: 96a16390d8f6f3a7-DME
Server: Heroku
Cdn-Loop: cloudflare; loops=1
Cf-Visitor: {"scheme":"https"}
User-Agent: Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)
Cf-Ipcountry: RU
X-Request-Id: 3cdcbdba-f629-0d29-b453-61644da43c6c
Accept-Encoding: gzip, br
X-Forwarded-For: 213.180.203.138, 172.71.184.65
X-Request-Start: 1754345469921
Cf-Connecting-Ip: 213.180.203.138
X-Forwarded-Port: 80
X-Forwarded-Proto: http
Yandex suggest a reverse DNS lookup [ https://substack.com/redirect/7203a617-35e3-497a-bbfe-003d4df48431?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to verify, so I ran this command:
dig -x 213.180.203.138 +short
And got back:
213-180-203-138.spider.yandex.com.
Which confirms that this is indeed a Yandex crawler.
I tried a third experiment to be sure... and got hits from both Bingbot and YandexBot.
It was Cloudflare Crawler Hints, not ChatGPT
So I wrote up and posted about my discovery... and Jatan Loya asked: [ https://substack.com/redirect/d3f57dc4-bb84-46ed-8221-55bcd16a5678?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
do you have crawler hints enabled in cf?
And yeah, it turned out I did. I spotted this in my caching configuration page (and it looks like I must have turned it on myself at some point in the past):
Here's the Cloudflare documentation for that feature [ https://substack.com/redirect/7de7b1c9-468b-4c87-aa49-17a7c42e93c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I deleted my posts on Twitter and Bluesky (since you can't edit those and I didn't want the misinformation to continue to spread) and edited my post on Mastodon [ https://substack.com/redirect/482d0fdc-8b14-47bf-a79e-1eb9ebf5043c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], then updated this entry with the real reason this had happened.
I also changed the URL of this entry as it turned out Twitter and Bluesky were caching my social media preview for the previous one, which included the incorrect information in the title.
The ChatGPT sharing dialog demonstrates how difficult it is to design privacy preferences [ https://substack.com/redirect/4c708077-7af6-427a-868d-d8d27190078c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-08-03
ChatGPT just removed their "make this chat discoverable" sharing feature, after it turned out a material volume of users had inadvertantly made their private chats available via Google search.
Dane Stuckey, CISO for OpenAI, on Twitter [ https://substack.com/redirect/5438b9ae-974c-4819-8a3a-15428556e3bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
We just removed a feature from @ChatGPTapp that allowed users to make their conversations discoverable by search engines, such as Google. This was a short-lived experiment to help people discover useful conversations. [...]
Ultimately we think this feature introduced too many opportunities for folks to accidentally share things they didn't intend to, so we're removing the option.
There's been some media coverage of this issue - here are examples from TechCrunch [ https://substack.com/redirect/fafec656-8939-4f99-9209-163daad25db9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], TechRadar [ https://substack.com/redirect/cd6a9d68-0b32-4d07-8ef7-c0f5b45f9d43?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and PCMag [ https://substack.com/redirect/230f674f-4cb7-4722-8f9b-4db8640743cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It turned out users had shared extremely private conversations and made them discoverable by search engines, which meant that various site:chatgpt.com ... searches were turning up all sorts of potentially embarrassing details.
Here's what that UI looked like before they removed the option:
I've seen a bunch of commentary, both on Twitter and this Hacker News thread [ https://substack.com/redirect/09c5202b-24f9-4048-ad40-d38633b4c4f7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], from people who are baffled that anyone could be confused by such a clear option in the UI.
I think that confusion is warranted. Let's break it down.
Here's the microcopy in question:
Make this chat discoverable
Allows it to be shown in web searches.
The first problem here is the choice of terminology. "Discoverable" is not a widely understood term - it's insider jargon. "Allows it to be shown in web searches" is better, but still requires a surprisng depth of understanding from users before they can make an informed decision.
Here's everything a user would need to understand for this to make sense to them:
What a URL is, and how it's posssible to create a URL that is semi-public in that it's unguessable by others but can still be read by anyone you share it with. That concept is a pretty tall order just on its own!
What a web search engine is - that in this case it's intended as a generic term for Google, Bing, DuckDuckGo etc.
That "web search" here means "those public search engines other people can use" and not something like "the private search feature you use on this website".
A loose understanding of how search engines work: that they have indexes, and those indexes can selectively include or exclude content.
That sites like ChatGPT get to control whether or not their content is included in those indexes.
That the nature of a "secret URL" is that, once shared and made discoverable, anyone with that link (or who finds it through search) can now view the full content of that page.
ChatGPT has over a billion users now. That means there is a giant range of levels of technical expertise among those users. We can't assume that everyone understands the above concepts necessary to understand the implications of checking that box.
And even if they have the pre-requisite knowledge required to understand this, users don't read.
When people are using an application they are always looking for the absolute shortest path to achieving their goal. Any dialog box or question that appears is something to be skipped over as quickly as possible.
Sadly, a lot of users may have learned to just say "yes" to any question. This option about making something "discoverable"? Sure, whatever, click the box and keep on going.
I think there's another factor at play here too: the option itself makes almost no sense.
How many people looking for a way to share their chats are going to think "and you know what? Stick this in Google too"?
It's such a tiny fraction of the audience that a logical conclusion, when faced with the above option, could well be that obviously it wouldn't put my chats in Google because who on Earth would ever want that to happen?
I think OpenAI made the right call disabling this feature. The value it can provide for the tiny set of people who decide to use it is massively outweighed by the potential for less discerning users to cause themselves harm by inadvertently sharing their private conversations with the world.
Meta AI does this even worse
A much worse example of this anti-pattern is Meta AI's decision to provide a "Post to feed" button in their own Meta AI chat app:
I think their microcopy here is top notch - the text here uses clear language and should be easy for anyone to understand.
(I took this screenshot today though, so it's possible the text has been recently updated.)
And yet... Futurism, June 14th: People Don't Realize Meta's AI App Is Publicly Blasting Their Humiliating Secrets to the World [ https://substack.com/redirect/b56056bd-1673-411a-ae93-12632ef68b62?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Once again, when your users number in the millions some of them are going to randomly click things without understanding the consequences.
The Meta AI iPhone app (fun fact: it can talk to you in the voice of Dame Judi Dench or John Cena) shows that public feed on the homepage when you first open the app, presumably to try and help people get over the blank slate "what is this thing even for" problem. They do not appear keen on losing this feature!
Link 2025-08-02 Re-label the "Save" button to be "Publish", to better indicate to users the outcomes of their action [ https://substack.com/redirect/eaeed6da-4add-4991-a082-3ba93655ac10?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fascinating Wikipedia usability improvement issue from 2016:
From feedback we get repeatedly as a development team from interviews, user testing and other solicited and unsolicited avenues, and by inspection from the number of edits by newbies not quite aware of the impact of their edits in terms of immediate broadcast and irrevocability, that new users don't necessarily understand what "Save" on the edit page means. [...]
Even though "user-generated content" sites are a lot more common today than they were when Wikipedia was founded, it is still unusual for most people that their actions will result in immediate, and effectively irrevocable, publication.
A great illustration of the usability impact of micro-copy, even more important when operating at Wikipedia scale.
Link 2025-08-03 From Async/Await to Virtual Threads [ https://substack.com/redirect/acf6fc87-41e8-4d84-80dd-ab1ea65da1ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Armin Ronacher has long been critical of async/await in Python, both for necessitating colored functions [ https://substack.com/redirect/5bbc8b1f-c46a-460f-a0e9-3ba53ff4ed0c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and because of the more subtle challenges they introduce like managing back pressure [ https://substack.com/redirect/7f52a20e-a161-44f3-ae39-1abaa6e50d0d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Armin argued convincingly [ https://substack.com/redirect/cb0de3fd-279c-4f02-af59-43d68329200b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the threaded programming model back in December. Now he's expanded upon that with a description of how virtual threads might make sense in Python.
Virtual threads behave like real system threads but can vastly outnumber them, since they can be paused and scheduled to run on a real thread when needed. Go uses this trick to implement goroutines which can then support millions of virtual threads on a single system.
Python core developer Mark Shannon started a conversation [ https://substack.com/redirect/3d912f95-c840-465b-b2ef-e2f3b649d44c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about the potential for seeing virtual threads to Python back in May.
Assuming this proposal turns into something concrete I don't expect we will see it in a production Python release for a few more years. In the meantime there are some exciting improvements to the Python concurrency story - most notably around sub-interpreters [ https://substack.com/redirect/aca86ba6-c9f6-4d39-b163-994d4b256429?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - coming up this year in Python 3.14.
Link 2025-08-03 XBai o4 [ https://substack.com/redirect/e379b312-5c81-4adb-8326-231e3580313e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Yet another open source (Apache 2.0) LLM from a Chinese AI lab. This model card claims:
XBai o4 excels in complex reasoning capabilities and has now completely surpassed OpenAI-o3-mini in Medium mode.
This a 32.8 billion parameter model released by MetaStone AI, a new-to-me lab who released their first model in March - MetaStone-L1-7B [ https://substack.com/redirect/0effe583-544e-49ec-8c28-7fd6f5bf8b81?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], then followed that with MetaStone-S1 1.5B [ https://substack.com/redirect/2262e1cf-e47f-486e-9f27-6507eec70c8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], 7B [ https://substack.com/redirect/2f35475d-c174-4eab-a222-5f11f7acb6aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and 32B [ https://substack.com/redirect/d4ccd7f3-4be8-43c0-9beb-e5fc432a6e24?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in July and now XBai o4 in August.
The MetaStone-S1 models were accompanied with a with a paper, Test-Time Scaling with Reflective Generative Model [ https://substack.com/redirect/061527ca-259f-41da-86dc-53e26e8dc0c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
There is very little information available on the English-language web about MetaStone AI. Their paper shows a relationship with USTC, University of Science and Technology of China [ https://substack.com/redirect/a7c554c6-9c83-4174-8afa-73e68baa6e49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in Hefei. One of their researchers confirmed on Twitter [ https://substack.com/redirect/fefb8845-0525-44be-9b32-9c05153613fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that their CEO is from KWAI [ https://substack.com/redirect/e87e414e-8215-428f-bb0b-92db1dc03e8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which lead me to this Chinese language article [ https://substack.com/redirect/23b2a06e-7fdb-4ccf-8cae-d9531cef7d26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from July last year about Li Yan, formerly of KWAI and now the founder of Wen Xiaobai and evidently [ https://substack.com/redirect/04168547-8a52-42ff-ac51-4e3cef3c6c7a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] now [ https://substack.com/redirect/e69cb7b2-d206-442a-8f4f-0fe631527b1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the CEO of MetaStone. www.wenxiaobai.com [ https://substack.com/redirect/f6e1e681-5fd9-4247-a562-76c16f18a9cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is listed as the "official website" linked to from the XBai-o4 README [ https://substack.com/redirect/8730fc38-3ce5-4746-b3a7-c8c535d5198b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on GitHub.
Ivan Fioravanti got it working under MLX [ https://substack.com/redirect/3e7ace14-4bee-4b3a-b004-6fa73336e03b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in 4bit, 5bit, 6bit, 8bit and 4bit-DWQ sizes. I tried his 6bit one [ https://substack.com/redirect/e029db91-ef95-4c06-bd5f-30bedb6affd3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (a 24.81GB download) in LM Studio and had it "Generate an SVG of a pelican riding a bicycle". It thought for 39.49 seconds (thinking trace here [ https://substack.com/redirect/28f832a9-7631-4334-a2b3-6119d55923e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and gave me this:
I also had it "Write an HTML and JavaScript page implementing space invaders", which you can try out here [ https://substack.com/redirect/8324bd42-f72b-4b43-9aeb-809ffbc513b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It's not great - the invaders don't fire bullets (it listed that as a "potential improvement") and I don't think it's winnable due to timing issues, but it's an interesting addition to my collection [ https://substack.com/redirect/d27433e0-cf9b-41d5-a788-3134f9d6ce2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
LM Studio reported a constant memory usage of 25.54GB and according to Activity Monitor used 87.5% of my GPU and around 39% of a CPU core.
It did a lot of work in the thinking trace - which took 10m35s! - including writing the first draft of much of the code that ended up in the finished result. Here's an extract:
Let me think of variables:
let enemyDirection = 1; // 1 for right, -1 for left
In the game loop:
enemies.forEach(enemy => {>
enemy.x += enemyDirection * enemy.dx;>
});
Then check if any enemy is out of bounds. If so, reverse direction and move all enemies down.
But how to check if any enemy is at the edge?
Maybe find the max x of all enemies and see if it exceeds canvas.width - enemy.width.
Alternatively, track the leftmost and rightmost positions of enemies. Maybe a bit complex.
For simplicity, perhaps check if any enemy's x + width > canvas.width or x < 0.
Here's the full transcript [ https://substack.com/redirect/5b296a86-f17b-42bc-bf31-9f84ae03efe0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
My initial impressions are that I'm not as impressed with this model for running on my own laptop as I was with Qwen3-Coder-30B-A3B-Instruct [ https://substack.com/redirect/d6b6dd24-e959-46e5-9871-bc6634b9495b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or GLM-4.5 Air [ https://substack.com/redirect/7c1afa8d-0138-4bcc-b974-edb9a6abee31?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
But... how extraordinary is it that another Chinese AI lab has been able to produce a competitive model, this time with far less fanfare than we've seen from Qwen and Moonshot AI and Z.ai.
quote 2025-08-04
This week, ChatGPT is on track to reach 700M weekly active users — up from 500M at the end of March and 4× since last year.
Nick Turley [ https://substack.com/redirect/38ebb7bb-3a01-48cc-b117-e52a02dd5406?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Head of ChatGPT, OpenAI
Link 2025-08-04 I Saved a PNG Image To A Bird [ https://substack.com/redirect/e6ed731f-3a08-404b-864e-e89dff922d13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Benn Jordan provides one of the all time great YouTube video titles, and it's justified. He drew an image in an audio spectrogram, played that sound to a talented starling (internet celebrity "The Mouth" [ https://substack.com/redirect/273bf7d0-63d2-4940-8b03-b0aa2cddda19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and recorded the result that the starling almost perfectly imitated back to him.
Hypothetically, if this were an audible file transfer protocol that used a 10:1 data compression ratio, that's nearly 2 megabytes of information per second. While there are a lot of caveats and limitations there, the fact that you could set up a speaker in your yard and conceivably store any amount of data in songbirds is crazy.
This video is full of so much more than just that. Fast forward to 5m58s [ https://substack.com/redirect/15fdaffd-25e3-480e-8ef9-90eec2982424?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for footage of a nest full of brown pelicans showing the sounds made by their chicks!
quote 2025-08-04
for services that wrap GPT-3, is it possible to do the equivalent of sql injection? like, a prompt-injection attack? make it think it's completed the task and then get access to the generation, and ask it to repeat the original instruction?
@himbodhisattva [ https://substack.com/redirect/f9ba4ce8-19d1-4636-a94c-031dc1025993?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], coining the term prompt injection on 13th May 2022, four months before I did [ https://substack.com/redirect/7eecfda8-1f83-4724-b694-649b2792957f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-08-04 Qwen-Image: Crafting with Native Text Rendering [ https://substack.com/redirect/66909948-136b-460e-955e-16a51ff69738?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Not content with releasing six excellent open weights LLMs in July [ https://substack.com/redirect/52a59b24-0afa-46a9-aaed-9b5c94f0a7a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Qwen are kicking off August with their first ever image generation model.
Qwen-Image is a 20 billion parameter MMDiT (Multimodal Diffusion Transformer, originally proposed for Stable Diffusion 3) model under an Apache 2.0 license. The Hugging Face repo [ https://substack.com/redirect/1d831029-8979-4155-bd72-c80bac0284b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is 53.97GB.
Qwen released a detailed technical report [ https://substack.com/redirect/c2a96be7-2ed6-4d3f-89e7-9a97b63ac606?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (PDF) to accompany the model. The model builds on their Qwen-2.5-VL vision LLM, and they also made extensive use of that model to help create some of their their training data:
In our data annotation pipeline, we utilize a capable image captioner (e.g., Qwen2.5-VL) to generate not only comprehensive image descriptions, but also structured metadata that captures essential image properties and quality attributes.
Instead of treating captioning and metadata extraction as independent tasks, we designed an annotation framework in which the captioner concurrently describes visual content and generates detailed information in a structured format, such as JSON. Critical details such as object attributes, spatial relationships, environmental context, and verbatim transcriptions of visible text are captured in the caption, while key image properties like type, style, presence of watermarks, and abnormal elements (e.g., QR codes or facial mosaics) are reported in a structured format.
They put a lot of effort into the model's ability to render text in a useful way. 5% of the training data (described as "billions of image-text pairs") was data "synthesized through controlled text rendering techniques", ranging from simple text through text on an image background up to much more complex layout examples:
To improve the model’s capacity to follow complex, structured prompts involving layout-sensitive content, we propose a synthesis strategy based on programmatic editing of pre-defined templates, such as PowerPoint slides or User Interface Mockups. A comprehensive rule-based system is designed to automate the substitution of placeholder text while maintaining the integrity of layout structure, alignment, and formatting.
I tried the model out using the ModelScope demo [ https://substack.com/redirect/5cf58abe-fb30-4deb-ab5c-a61b444bb3ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - I signed in with GitHub and verified my account via a text message to a phone number. Here's what I got for "A raccoon holding a sign that says "I love trash" that was written by that raccoon":
The raccoon has very neat handwriting!
Update: A version of the model exists that can edit existing images but it's not yet been released [ https://substack.com/redirect/650ca371-9962-4b35-9f0c-e645a00e5f61?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Currently, we have only open-sourced the text-to-image foundation model, but the editing model is also on our roadmap and planned for future release.
Link 2025-08-04 Usage charts for my LLM tool against OpenRouter [ https://substack.com/redirect/7e8d1a0c-9c66-404b-bfb0-79607f78277d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenRouter proxies requests to a large number of different LLMs and provides high level statistics of which models are the most popular among their users.
Tools that call OpenRouter can include HTTP-Referer and X-Title headers to credit that tool with the token usage. My llm-openrouter [ https://substack.com/redirect/d9b23531-2941-48de-a01c-2b598c6a872a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin does that here [ https://substack.com/redirect/076b804d-b445-43bb-94e0-a3eaaac7a538?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
... which means this page [ https://substack.com/redirect/7e8d1a0c-9c66-404b-bfb0-79607f78277d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] displays aggregate stats across users of that plugin! Looks like someone has been running a lot of traffic through Qwen 3 14B [ https://substack.com/redirect/3815d6af-5fa6-4422-a1b3-5aad68214725?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] recently.
Link 2025-08-05 A Friendly Introduction to SVG [ https://substack.com/redirect/858fa58d-e994-4a3f-8877-94367e53e331?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This SVG tutorial by Josh Comeau is fantastic. It's filled with neat interactive illustrations - with a pleasing subtly "click" audio effect as you adjust their sliders - and provides a useful introduction to a bunch of well chosen SVG fundamentals.
I finally understand what all four numbers in the viewport="..." attribute are for!
quote 2025-08-05
I teach HS Science in the south. I can only speak for my district, but a few teacher work days in the wave of enthusiasm I'm seeing for AI tools is overwhelming. We're getting district approved ads for AI tools by email, Admin and ICs are pushing it on us, and at least half of the teaching staff seems all in at this point.
I was just in a meeting with my team and one of the older teachers brought out a powerpoint for our first lesson and almost everyone agreed to use it after a quick scan - but it was missing important tested material, repetitive, and just totally airy and meaningless. Just slide after slide of the same handful of sentences rephrased with random loosely related stock photos. When I asked him if it was AI generated, he said 'of course', like it was a strange question. [...]
We don't have a leg to stand on to teach them anything about originality, academic integrity/intellectual honesty, or the importance of doing things for themselves when they catch us indulging in it just to save time at work.
greyduet on r/teachers [ https://substack.com/redirect/eb9a6540-c12f-4ad7-b825-2575e6eecf2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Unpopular Opinion: Teacher AI use is already out of control and it's not ok
Link 2025-08-05 Claude Opus 4.1 [ https://substack.com/redirect/80df0d89-4224-48bc-a9f3-71adcdfa37e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Surprise new model from Anthropic today - Claude Opus 4.1, which they describe as "a drop-in replacement for Opus 4".
My favorite thing about this model is the version number - treating this as a .1 version increment looks like it's an accurate depiction of the model's capabilities.
Anthropic's own benchmarks show very small incremental gains.
Comparing Opus 4 and Opus 4.1 (I got 4.1 to extract this information from a screenshot [ https://substack.com/redirect/fe3c336d-a5a7-46f7-b434-a2351c3c3b89?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of Anthropic's own benchmark scores, then asked it to look up the links, then verified the links myself and fixed a few):
Agentic coding (SWE-bench Verified [ https://substack.com/redirect/310a949a-8e81-4e7a-8271-7767a0df8bc6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]): From 72.5% to 74.5%
Agentic terminal coding (Terminal-Bench [ https://substack.com/redirect/c07f2886-4749-4074-a717-2c5f097a626b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]): From 39.2% to 43.3%
Graduate-level reasoning (GPQA Diamond [ https://substack.com/redirect/6d7bfce0-36cc-4da3-ad0c-9f0ffd800208?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]): From 79.6% to 80.9%
Agentic tool use (TAU-bench [ https://substack.com/redirect/ef37bf57-62ce-480f-a595-6ab382968e6f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
Retail: From 81.4% to 82.4%
Airline: From 59.6% to 56.0% (decreased)
Multilingual Q&A (MMMLU [ https://substack.com/redirect/be949489-45c1-43e6-ac63-9ba244964eb3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]): From 88.8% to 89.5%
Visual reasoning (MMMU validation [ https://substack.com/redirect/28219c77-52f6-43e9-ab62-1d6f7784ff0c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]): From 76.5% to 77.1%
High school math competition (AIME 2025 [ https://substack.com/redirect/8d054290-9b26-4673-9af1-db19fe8745ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]): From 75.5% to 78.0%
Likewise, the model card [ https://substack.com/redirect/ca7627ff-eb98-4c34-95a4-ef0bf9365f78?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] shows only tiny changes to the various safety metrics that Anthropic track.
It's priced the same as Opus 4 - $15/million for input and $75/million for output, making it one of the most expensive models [ https://substack.com/redirect/87d7b2f2-f3ca-4ae2-b8c0-2c7f6e773e09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on the market today.
I had it draw me this pelican [ https://substack.com/redirect/8c2d94f8-a274-40a4-9ed2-f495b33754e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] riding a bicycle:
For comparison I got a fresh new pelican out of Opus 4 [ https://substack.com/redirect/3829806e-a20c-4fc1-ae4a-0ce63489be87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which I actually like a little more:
I shipped llm-anthropic 0.18 [ https://substack.com/redirect/0df8c49e-5270-433b-a95e-eebca962900a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with support for the new model.
Link 2025-08-06 No, AI is not Making Engineers 10x as Productive [ https://substack.com/redirect/13e351a1-88ce-49a4-8250-47ca54a88c83?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Colton Voege on "curing your AI 10x engineer imposter syndrome".
There's a lot of rhetoric out there suggesting that if you can't 10x your productivity through tricks like running a dozen Claude Code instances at once you're falling behind. Colton's piece here is a pretty thoughtful exploration of why that likely isn't true. I found myself agreeing with quite a lot of this article.
I'm a pretty huge proponent for AI-assisted development, but I've never found those 10x claims convincing. I've estimated that LLMs make me 2-5x more productive on the parts of my job which involve typing code into a computer, which is itself a small portion of that I do as a software engineer.
That's not too far from this article's assumptions. From the article:
I wouldn't be surprised to learn AI helps many engineers do certain tasks 20-50% faster, but the nature of software bottlenecks mean this doesn't translate to a 20% productivity increase and certainly not a 10x increase.
I think that's an under-estimation - I suspect engineers that really know how to use this stuff effectively will get more than a 0.2x increase - but I do think all of the other stuff involved in building software makes the 10x thing unrealistic in most cases.
quote 2025-08-06
gpt-oss-120b is the most intelligent American open weights model, comes behind DeepSeek R1 and Qwen3 235B in intelligence but offers efficiency benefits [...]
We’re seeing the 120B beat o3-mini but come in behind o4-mini and o3. The 120B is the most intelligent model that can be run on a single H100 and the 20B is the most intelligent model that can be run on a consumer GPU. [...]
While the larger gpt-oss-120b does not come in above DeepSeek R1 0528’s score of 59 or Qwen3 235B 2507s score of 64, it is notable that it is significantly smaller in both total and active parameters than both of those models.
Artificial Analysis [ https://substack.com/redirect/ce3838bb-51d6-4fa1-ba9f-df844f17da07?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], see also their updated leaderboard [ https://substack.com/redirect/2e534c6f-cbaa-4f84-81d7-3f240f1f166a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-08-06 Tom MacWright: Observable Notebooks 2.0 [ https://substack.com/redirect/8783c137-31fd-4c8e-b9e3-905afc331b81?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Observable announced Observable Notebooks 2.0 [ https://substack.com/redirect/11da8bbf-5ca7-4be9-b7e5-57197849a866?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] last week - the latest take on their JavaScript notebook technology, this time with an open file format [ https://substack.com/redirect/2f61ab07-e81b-4e26-b487-4c4759b8b006?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and a brand new macOS desktop app [ https://substack.com/redirect/466edb28-1738-498e-bc98-e8a3c8748b02?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Tom MacWright worked at Observable during their first iteration and here provides thoughtful commentary from an insider-to-outsider perspective on how their platform has evolved over time.
I particularly appreciated this aside on the downsides of evolving your own not-quite-standard language syntax:
Notebook Kit and Desktop support vanilla JavaScript [ https://substack.com/redirect/3ce81d02-b8ae-4eb8-9d97-859dc0207f82?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which is excellent and cool. The Observable changes to JavaScript were always tricky and meant that we struggled to use off-the-shelf parsers, and users couldn't use standard JavaScript tooling like eslint. This is stuff like the viewof operator which meant that Observable was not JavaScript [ https://substack.com/redirect/a823d79f-fc15-4f71-875b-f23734eed776?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. [...] Sidenote: I now work on Val Town [ https://substack.com/redirect/2abf59f3-f381-4849-9c12-8727250dbda0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which is also a platform based on writing JavaScript, and when I joined it also had a tweaked version of JavaScript. We used the @ character to let you 'mention' other vals and implicitly import them. This was, like it was in Observable, not worth it and we switched to standard syntax: don't mess with language standards folks!
Link 2025-08-06 Jules, our asynchronous coding agent, is now available for everyone [ https://substack.com/redirect/fd026da4-8d11-42c1-a05b-5b7a8e70d2bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wrote about the Jules beta back in May [ https://substack.com/redirect/e718d41e-8797-45f5-8caa-ced23fe79620?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Google's version of the OpenAI Codex PR-submitting hosted coding tool graduated from beta today.
I'm mainly linking to this now because I like the new term they are using in this blog entry: Asynchronous coding agent. I like it so much I gave it a tag [ https://substack.com/redirect/1220ccea-6b99-4496-bec6-c0c82a0bc8b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I continue to avoid the term "agent" as infuriatingly vague, but I can grudgingly accept it when accompanied by a prefix that clarifies the type of agent we are talking about. "Asynchronous coding agent" feels just about obvious enough to me to be useful.
... I just ran a Google search for "asynchronous coding agent" -jules and came up with a few more notable examples of this name being used elsewhere:
Introducing Open SWE: An Open-Source Asynchronous Coding Agent [ https://substack.com/redirect/21cda016-7d9e-4511-b25d-f2bfaac31f47?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is an announcement from LangChain just this morning of their take on this pattern. They provide a hosted version (bring your own API keys) or you can run it yourself with their MIT licensed code [ https://substack.com/redirect/60ba9549-057f-4377-b187-affaae595275?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The press release for GitHub's own version of this GitHub Introduces Coding Agent For GitHub Copilot [ https://substack.com/redirect/c442cc6a-af2c-436e-b7ec-9b800a8a07b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] states that "GitHub Copilot now includes an asynchronous coding agent".
Note 2025-08-07 [ https://substack.com/redirect/05114a4a-4668-45d3-b2e4-ab23aa6bd1e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
A couple of weeks ago I was invited to OpenAI's headquarters for a "preview event", for which I had to sign both an NDA and a video release waiver. I suspected it might relate to either GPT-5 or the OpenAI open weight models... and GPT-5 it was [ https://substack.com/redirect/57d09649-c5a4-4178-b3eb-091989f5ae1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
OpenAI had invited five developers: Claire Vo [ https://substack.com/redirect/e5c48e54-d9dd-43d2-b665-75825d21f89c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Theo Browne [ https://substack.com/redirect/9722eda3-5a9b-4fe4-b7a1-784f7ee639f0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Ben Hylak [ https://substack.com/redirect/79aef11d-952e-4a61-be1a-84e568b73e91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Shawn @swyx Wang [ https://substack.com/redirect/2f118318-f325-453d-b6f9-84dddd4f438a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and myself. We were all given early access to the new models and asked to spend a couple of hours (of paid time) experimenting with them, while being filmed by a professional camera crew.
The resulting video is now up on YouTube [ https://substack.com/redirect/b7aec7d8-b6d5-419c-9d39-1bd26745f225?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Unsurprisingly most of my edits related to SVGs of pelicans [ https://substack.com/redirect/2a17a436-ae2f-452a-9dc2-e2e08fa63137?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOekEwTmprMk5EUXNJbWxoZENJNk1UYzFORFkzTmpRd055d2laWGh3SWpveE56ZzJNakV5TkRBM0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEub0VHak1TTFozOWVSQlhWbmxxeXFsQ29kN0JJeHUwdmRZa0JLWDMzZlh0dyIsInAiOjE3MDQ2OTY0NCwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzU0Njc2NDA3LCJleHAiOjIwNzAyNTI0MDcsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.etFY2IWi2cfNRn0H87iLXGJQsl7cDnUgETxQrj_UB48?
