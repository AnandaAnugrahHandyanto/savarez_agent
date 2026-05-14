# Image segmentation using Gemini 2.5

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-04-18T20:56:35.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/image-segmentation-using-gemini-25

In this newsletter:
Image segmentation using Gemini 2.5
o3 and o4-mini
Plus 3 links and 5 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Image segmentation using Gemini 2.5 [ https://substack.com/redirect/2a4644cc-6d18-4206-ba80-bb194d676c35?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-04-18
Max Woolf pointed out this new feature of the Gemini 2.5 series (here's my coverage of 2.5 Pro [ https://substack.com/redirect/648e9623-f7fa-402a-bc6e-10b5f34952da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]and 2.5 Flash [ https://substack.com/redirect/640bc1fb-4a72-43a0-bf6f-4abd909c713f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) in a comment [ https://substack.com/redirect/20287804-6ea5-479d-aba2-a7130c5eb36a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hacker News:
One hidden note from Gemini 2.5 Flash when diving deep into the documentation: for image inputs, not only can the model be instructed to generated 2D bounding boxes of relevant subjects, but it can also create segmentation masks [ https://substack.com/redirect/4f5d51d7-2446-4d18-b938-f943b9d93c65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
At this price point with the Flash model, creating segmentation masks is pretty nifty.
I built a tool last year to explore Gemini's bounding box abilities [ https://substack.com/redirect/86c1f9cb-965e-45d6-b513-bfc2d94ef9d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This new segmentation mask feature represents a significant new capability!
Here's my new tool to try it out: Gemini API Image Mask Visualization [ https://substack.com/redirect/a39b50d3-0ae1-470e-b930-992d5e6e4599?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. As with my bounding box tool it's browser-based JavaScript that talks to the Gemini API directly. You provide it with a Gemini API key [ https://substack.com/redirect/445e0de0-6556-404f-8e1f-204153c6e672?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which isn't logged anywhere that I can see it.
This is what it can do:
Give it an image and a prompt of the form:
Give the segmentation masks for the objects. Output a JSON list of segmentation masks where each entry contains the 2D bounding box in the key "box_2d" and the segmentation mask in key "mask".
My tool then runs the prompt and displays the resulting JSON. The Gemini API returns segmentation masks as base64-encoded PNG images in strings that start data:image/png;base64,iVBOR.... The tool then visualizes those in a few different ways on the page, including overlaid over the original image.
I vibe coded [ https://substack.com/redirect/1064d5eb-2841-48de-bf3b-fa27625c447b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the whole thing together using a combination of Claude and ChatGPT. I started with a Claude Artifacts React prototype [ https://substack.com/redirect/505a2600-dae6-4ea3-8b9b-d808ffc523f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], then pasted the code from my old project into Claude and hacked on that until I ran out of tokens [ https://substack.com/redirect/11638958-0450-4608-a5df-ed53ecb114c4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I transferred the incomplete result to a new Claude session where I kept on iterating [ https://substack.com/redirect/059a7f04-1315-44e6-90b2-602151860f8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] until it got stuck in a bug loop (the same bug kept coming back no matter how often I told it to fix that)... so I switched over to O3 in ChatGPT to finish it off [ https://substack.com/redirect/78eb04ff-d248-42c5-ae12-da1e6ef6f2eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here's the finished code [ https://substack.com/redirect/ed6cd4da-ae94-4b23-a942-47346b4c5814?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It's a total mess, but it's also less than 500 lines of code and the interface solves my problem in that it lets me explore the new Gemini capability.
Segmenting my pelican photo via the Gemini API was absurdly inexpensive. Using Gemini 2.5 Pro the call cost 303 input tokens and 353 output tokens, for a total cost of 0.2144 cents (less than a quarter of a cent). I ran it again with the new Gemini 2.5 Flash and it used 303 input tokens and 270 output tokens, for a total cost of 0.099 cents (less than a tenth of a cent). I calculated these prices using my LLM pricing calculator [ https://substack.com/redirect/7e45e2a9-6a40-438a-bbaf-25ba9ee04890?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool.
1/100th of a cent with Gemini 2.5 Flash non-thinking
Gemini 2.5 Flash has two pricing models. Input is a standard $0.15/million tokens, but the output charges differ a lot: in non-thinking mode output is $0.60/million, but if you have thinking enabled (the default) output is $3.50/million. I think of these as "Gemini 2.5 Flash" and "Gemini 2.5 Flash Thinking".
My initial experiments all used thinking mode. I decided to upgrade the tool to try non-thinking mode, but noticed that the API library it was using (google/generative-ai [ https://substack.com/redirect/9a0c556c-4598-467e-9327-975e875ce9ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) is marked as deprecated.
On a hunch, I pasted the code into the new o4-mini-high model [ https://substack.com/redirect/332480da-7c6c-4fa7-b84b-7f8bce46cfc3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in ChatGPT and prompted it with:
This code needs to be upgraded to the new recommended JavaScript library from Google. Figure out what that is and then look up enough documentation to port this code to it
o4-mini and o3 both have search tool access and claim to be good at mixing different tool uses together.
This worked extremely well! It ran a few searches and identified exactly what needed to change:
Then gave me detailed instructions along with an updated snippet of code. Here's the full transcript [ https://substack.com/redirect/6f721d11-f58f-4c40-9ef7-4a3b6a2192b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I prompted for a few more changes, then had to tell it not to use TypeScript (since I like copying and pasting code directly out of the tool without needing to run my own build step). The latest version [ https://substack.com/redirect/a39b50d3-0ae1-470e-b930-992d5e6e4599?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] has been rewritten by o4-mini for the new library, defaults to Gemini 2.5 Flash non-thinking and displays usage tokens after each prompt.
Segmenting my pelican photo in non-thinking mode cost me 303 input tokens and 123 output tokens - that's 0.0119 cents, just over 1/100th of a cent!
But this looks like way more than 123 output tokens
The JSON that's returned by the API looks way too long to fit just 123 tokens.
My hunch is that there's an additional transformation layer here. I think the Gemini 2.5 models return a much more efficient token representation of the image masks, then the Gemini API layer converts those into base4-encoded PNG image strings.
We do have one clue here: last year DeepMind released PaliGemma [ https://substack.com/redirect/e61e52af-0f37-4234-83b1-a900c1b71d06?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], an open weights vision model that could generate segmentation masks on demand.
The README for that model [ https://substack.com/redirect/e1fc4f05-8aab-4ad8-8f97-83903696193f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] includes this note about how their tokenizer works:
PaliGemma uses the Gemma tokenizer with 256,000 tokens, but we further extend its vocabulary with 1024 entries that represent coordinates in normalized image-space (...), and another with 128 entries (...) that are codewords used by a lightweight referring-expression segmentation vector-quantized variational auto-encoder (VQ-VAE) [...]
My guess is that Gemini 2.5 is using a similar approach.
Quote 2025-04-15
The single most impactful investment I’ve seen AI teams make isn’t a fancy evaluation dashboard—it’s building a customized interface that lets anyone examine what their AI is actually doing. I emphasize customizedbecause every domain has unique needs that off-the-shelf tools rarely address. When reviewing apartment leasing conversations, you need to see the full chat history and scheduling context. For real-estate queries, you need the property details and source documents right there. Even small UX decisions—like where to place metadata or which filters to expose—can make the difference between a tool people actually use and one they avoid. [...]
Teams with thoughtfully designed data viewers iterate 10x faster than those without them. And here’s the thing: These tools can be built in hours using AI-assisted development (like Cursor or Loveable). The investment is minimal compared to the returns.
Hamel Husain [ https://substack.com/redirect/b564de5c-578c-4bd4-9817-5476bb433b61?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-04-16 openai/codex [ https://substack.com/redirect/e76b0694-be69-4895-9bb6-83ef7f27376e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Just released by OpenAI, a "lightweight coding agent that runs in your terminal". Looks like their version of Claude Code [ https://substack.com/redirect/9d1e6def-3086-464f-8dd2-394eeaba233c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], though unlike Claude Code Codex is released under an open source (Apache 2) license.
Here's the main prompt [ https://substack.com/redirect/53812e4e-5430-4109-b54e-612e648f3e67?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that runs in a loop, which starts like this:
You are operating as and within the Codex CLI, a terminal-based agentic coding assistant built by OpenAI. It wraps OpenAI models to enable natural language interaction with a local codebase. You are expected to be precise, safe, and helpful.
You can:
- Receive user prompts, project context, and files.
- Stream responses and emit function calls (e.g., shell commands, code edits).
- Apply patches, run commands, and manage user approvals based on policy.
- Work inside a sandboxed, git-backed workspace with rollback support.
- Log telemetry so sessions can be replayed or inspected later.
- More details on your functionality are available at codex --help
The Codex CLI is open-sourced. Don't confuse yourself with the old Codex language model built by OpenAI many moons ago (this is understandably top of mind for you!). Within this context, Codex refers to the open-source agentic coding interface. [...]
I like that the prompt describes OpenAI's previous Codex language model as being from "many moons ago". Prompt engineering is so weird.
Since the prompt says that it works "inside a sandboxed, git-backed workspace" I went looking for the sandbox. On macOS it uses [ https://substack.com/redirect/54a94900-711b-4995-9403-8895948a694e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the little-known sandbox-exec process, part of the OS but grossly under-documented. The best information I've found about it is this article from 2020 [ https://substack.com/redirect/15f08037-f0d7-4bbe-a288-f346357be8fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which notes that man sandbox-exec lists it as deprecated. I didn't spot evidence in the Codex code of sandboxes for other platforms.
Link 2025-04-16 Introducing OpenAI o3 and o4-mini [ https://substack.com/redirect/0602e840-a5dd-4785-abb2-d2ee6e6e1248?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI are really emphasizing tool use with these:
For the first time, our reasoning models can agentically use and combine every tool within ChatGPT—this includes searching the web, analyzing uploaded files and other data with Python, reasoning deeply about visual inputs, and even generating images. Critically, these models are trained to reason about when and how to use tools to produce detailed and thoughtful answers in the right output formats, typically in under a minute, to solve more complex problems.
I released llm-openai-plugin 0.3 [ https://substack.com/redirect/5b8b7c44-2c9a-4910-9cd6-915a0dc7dcf9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adding support for the two new models:
llm install -U llm-openai-plugin
llm -m openai/o3 "say hi in five languages"
llm -m openai/o4-mini "say hi in five languages"
Here are the pelicans riding bicycles [ https://substack.com/redirect/f8e8570f-1da6-495d-b797-b99aeb70042a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (prompt: Generate an SVG of a pelican riding a bicycle).
o3:
o4-mini:
Here are the full OpenAI model listings: o3 [ https://substack.com/redirect/97acc6fd-e7c7-4bcf-b45e-dcb7e32a5851?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is $10/million input and $40/million for output, with a 75% discount on cached input tokens, 200,000 token context window, 100,000 max output tokens and a May 31st 2024 training cut-off (same as the GPT-4.1 models). It's a bit cheaper than o1 ($15/$60) and a lot cheaper than o1-pro ($150/$600).
o4-mini [ https://substack.com/redirect/037e5498-2f00-4758-8245-d0093def78c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is priced the same as o3-mini: $1.10/million for input and $4.40/million for output, also with a 75% input caching discount. The size limits and training cut-off are the same as o3.
You can compare these prices with other models using the table on my updated LLM pricing calculator [ https://substack.com/redirect/7e45e2a9-6a40-438a-bbaf-25ba9ee04890?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
A new capability released today is that the OpenAI API can now optionally return reasoning summary text. I've been exploring that in this issue [ https://substack.com/redirect/b1a79eb8-943c-41e6-ba55-7dc0fb075675?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I believe you have to verify your organization (which may involve a photo ID) in order to use this option - once you have access the easiest way to see the new tokens is using curl like this:
curl https://api.openai.com/v1/responses \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $(llm keys get openai)" \
-d '{
"model": "o3",
"input": "why is the sky blue?",
"reasoning": {"summary": "auto"},
"stream": true
}'
This produces a stream of events that includes this new event type:
event: response.reasoning_summary_text.delta
data: {"type": "response.reasoning_summary_text.delta","item_id": "rs_68004320496081918e1e75ddb550d56e0e9a94ce520f0206","output_index": 0,"summary_index": 0,"delta": "**Expl"}
Omit the "stream": true and the response is easier to read and contains this:
{
"output": [
{
"id": "rs_68004edd2150819183789a867a9de671069bc0c439268c95",
"type": "reasoning",
"summary": [
{
"type": "summary_text",
"text": "**Explaining the blue sky**\n\nThe user asks a classic question about why the sky is blue. I'll talk about Rayleigh scattering, where shorter wavelengths of light scatter more than longer ones. This explains how we see blue light spread across the sky! I wonder if the user wants a more scientific or simpler everyday explanation. I'll aim for a straightforward response while keeping it engaging and informative. So, let's break it down!"
}
]
},
{
"id": "msg_68004edf9f5c819188a71a2c40fb9265069bc0c439268c95",
"type": "message",
"status": "completed",
"content": [
{
"type": "output_text",
"annotations": [],
"text": "The short answer ..."
}
]
}
]
}
Quote 2025-04-16
I work for OpenAI. [...] o4-mini is actually a considerably better vision model than o3, despite the benchmarks. Similar to how o3-mini-high was a much better coding model than o1. I would recommend using o4-mini-high over o3 for any task involving vision.
James Betker [ https://substack.com/redirect/5c718be7-9470-4dae-9810-ef72dd52d349?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-04-17
Our hypothesis is that o4-mini is a much better model, but we'll wait to hear feedback from developers. Evals only tell part of the story, and we wouldn't want to prematurely deprecate a model that developers continue to find value in. Model behavior is extremely high dimensional, and it's impossible to prevent regression on 100% use cases/prompts, especially if those prompts were originally tuned to the quirks of the older model. But if the majority of developers migrate happily, then it may make sense to deprecate at some future point.
We generally want to give developers as stable as an experience as possible, and not force them to swap models every few months whether they want to or not.
Ted Sanders, OpenAI [ https://substack.com/redirect/51675f4f-7281-482f-9686-73face1ffca1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-04-17
We (Jon and Zach) teamed up with the Harris Poll to confirm this finding and extend it. We conducted a nationally representative survey [ https://substack.com/redirect/a09de42e-88dd-40a6-a904-df1cca6e54bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]of 1,006 Gen Z young adults (ages 18-27). We asked respondents to tell us, for various platforms and products, if they wished that it “was never invented.” For Netflix, Youtube, and the internet itself, relatively few said yes to that question (always under 20%). We found much higher levels of regret for the dominant social media platforms: Instagram (34%), Facebook (37%), Snapchat (43%), and the most regretted platforms of all: TikTok (47%) and X/Twitter (50%).
Jon Haidt and Zach Rausch [ https://substack.com/redirect/f96f3783-167d-41b5-b6f0-1d7d11da2345?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-04-17 Start building with Gemini 2.5 Flash [ https://substack.com/redirect/8c74563f-86af-46b4-9983-ff6afc6592ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Google Gemini's latest model is Gemini 2.5 Flash, available in (paid) preview as gemini-2.5-flash-preview-04-17.
Building upon the popular foundation of 2.0 Flash, this new version delivers a major upgrade in reasoning capabilities, while still prioritizing speed and cost. Gemini 2.5 Flash is our first fully hybrid reasoning model, giving developers the ability to turn thinking on or off. The model also allows developers to set thinking budgets to find the right tradeoff between quality, cost, and latency.
Gemini AI Studio product lead Logan Kilpatrick says [ https://substack.com/redirect/fff12525-8215-451a-85a4-4e734e939442?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This is an early version of 2.5 Flash, but it already shows huge gains over 2.0 Flash.
You can fully turn off thinking if needed and use this model as a drop in replacement for 2.0 Flash.
I added support to the new model in llm-gemini 0.18 [ https://substack.com/redirect/5d98698d-316c-4859-85d3-b936032af255?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here's how to try it out:
llm install -U llm-gemini
llm -m gemini-2.5-flash-preview-04-17 'Generate an SVG of a pelican riding a bicycle'
Here's that first pelican, using the default setting where Gemini Flash 2.5 makes its own decision in terms of how much "thinking" effort to apply:
Here's the transcript [ https://substack.com/redirect/7626419a-023d-4eba-bd05-a05928c03b27?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This one used 11 input tokens and 4266 output tokens of which 2702 were "thinking" tokens.
I asked the model to "describe" that image and it could tell it was meant to be a pelican:
A simple illustration on a white background shows a stylized pelican riding a bicycle. The pelican is predominantly grey with a black eye and a prominent pink beak pouch. It is positioned on a black line-drawn bicycle with two wheels, a frame, handlebars, and pedals.
The way the model is priced is a little complicated. If you have thinking enabled, you get charged $0.15/million tokens for input and $3.50/million for output. With thinking disabled those output tokens drop to $0.60/million. I've added these to my pricing calculator [ https://substack.com/redirect/7e45e2a9-6a40-438a-bbaf-25ba9ee04890?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
For comparison, Gemini 2.0 Flash is $0.10/million input and $0.40/million for output.
So my first prompt - 11 input and 4266 output(with thinking enabled), cost 1.4933 cents.
Let's try 2.5 Flash again with thinking disabled:
llm -m gemini-2.5-flash-preview-04-17 'Generate an SVG of a pelican riding a bicycle' -o thinking_budget 0
11 input, 1705 output. That's 0.1025 cents. Transcript here [ https://substack.com/redirect/a62d0d52-39e6-44b8-ad41-b2257e37561f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it still shows 25 thinking tokens even though I set the thinking budget to 0 - Logan confirms [ https://substack.com/redirect/e920774b-9ec8-4848-8cde-35553db9b713?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that this will still be billed at the lower rate:
In some rare cases, the model still thinks a little even with thinking budget = 0, we are hoping to fix this before we make this model stable and you won't be billed for thinking. The thinking budget = 0 is what triggers the billing switch.
Here's Gemini 2.5 Flash's self-description of that image:
A minimalist illustration shows a bright yellow bird riding a bicycle. The bird has a simple round body, small wings, a black eye, and an open orange beak. It sits atop a simple black bicycle frame with two large circular black wheels. The bicycle also has black handlebars and black and yellow pedals. The scene is set against a solid light blue background with a thick green stripe along the bottom, suggesting grass or ground.
And finally, let's ramp the thinking budget up to the maximum:
llm -m gemini-2.5-flash-preview-04-17 'Generate an SVG of a pelican riding a bicycle' -o thinking_budget 24576
I think it over-thought this one. Transcript [ https://substack.com/redirect/05091418-2ca2-45ae-a5cd-1d1812d20e55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 5174 output tokens of which 3023 were thinking. A hefty 1.8111 cents!
A simple, cartoon-style drawing shows a bird-like figure riding a bicycle. The figure has a round gray head with a black eye and a large, flat orange beak with a yellow stripe on top. Its body is represented by a curved light gray shape extending from the head to a smaller gray shape representing the torso or rear. It has simple orange stick legs with round feet or connections at the pedals. The figure is bent forward over the handlebars in a cycling position. The bicycle is drawn with thick black outlines and has two large wheels, a frame, and pedals connected to the orange legs. The background is plain white, with a dark gray line at the bottom representing the ground.
One thing I really appreciate about Gemini 2.5 Flash's approach to SVGs is that it shows very good taste in CSS, comments and general SVG class structure. Here's a truncated extract - I run a lot of these SVG tests against different models and this one has a coding style that I particularly enjoy. (Gemini 2.5 Pro does this too [ https://substack.com/redirect/0999ec62-165f-45da-aa3c-967e6c406e78?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).

The LM Arena leaderboard [ https://substack.com/redirect/fe1dcd8d-de83-4b2c-aff8-0a8b77b54bf9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] now has Gemini 2.5 Flash in joint second place [ https://substack.com/redirect/b6bf8cde-964b-4f22-99b5-157b932aeaf3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], just behind Gemini 2.5 Pro and tied with ChatGPT-4o-latest, Grok-3 and GPT-4.5 Preview.
Link 2025-04-18 MCP Run Python [ https://substack.com/redirect/9b7039d3-5bf5-4347-9704-f837e8269772?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Pydantic AI's MCP server for running LLM-generated Python code in a sandbox. They ended up using a trick I explored two years ago [ https://substack.com/redirect/2649134e-38da-447c-8fd7-c936731d271f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: using a Deno [ https://substack.com/redirect/3c3184cd-91f0-48b5-bbf5-31fdcc89b715?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] process to run Pyodide [ https://substack.com/redirect/f0829c13-ca46-4350-8738-e5a7146cfc80?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in a WebAssembly sandbox.
Here's a bit of a wild trick: since Deno loads code on-demand from JSR [ https://substack.com/redirect/07494eac-35a9-4247-be85-3676359148b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and uv run [ https://substack.com/redirect/09e33cb2-a854-43db-bf5c-79c713385f1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] can install Python dependencies on demand via the --withoption... here's a one-liner you can paste into a macOS shell (provided you have Deno and uvinstalled already) which will run the example from their README [ https://substack.com/redirect/654ff2b3-e5d7-4f7f-aaba-d13fb5a581e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - calculating the number of days between two dates in the most complex way imaginable:
ANTHROPIC_API_KEY="sk-ant-..." \
uv run --with pydantic-ai python -c '
import asyncio
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

server = MCPServerStdio(
"deno",
args=[
"run",
"-N",
"-R=node_modules",
"-W=node_modules",
"--node-modules-dir=auto",
"jsr:@pydantic/mcp-run-python",
"stdio",
],
)
agent = Agent("claude-3-5-haiku-latest", mcp_servers=[server])

async def main:
async with agent.run_mcp_servers:
result = await agent.run("How many days between 2000-01-01 and 2025-03-18?")
print(result.output)

asyncio.run(main)'
I ran that just now and got:
The number of days between January 1st, 2000 and March 18th, 2025 is 9,208 days.
I thoroughly enjoy how tools like uv and Deno enable throwing together shell one-liner demos like this one.
Here's an extended version [ https://substack.com/redirect/d75d8bd0-c524-49f5-8ec8-854a5202f6d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of this example which adds pretty-printed logging of the messages exchanged with the LLM to illustrate exactly what happened. The most important piece is this tool call where Claude 3.5 Haiku asks for Python code to be executed my the MCP server:
ToolCallPart(
tool_name='run_python_code',
args={
'python_code': (
'from datetime import date\n'
'\n'
'date1 = date(2000, 1, 1)\n'
'date2 = date(2025, 3, 18)\n'
'\n'
'days_between = (date2 - date1).days\n'
'print(f"Number of days between {date1} and {date2}: {days_between}")'
),
},
tool_call_id='toolu_01TXXnQ5mC4ry42DrM1jPaza',
part_kind='tool-call',
)
I also managed to run it against Mistral Small 3.1 [ https://substack.com/redirect/95d72909-b3ba-4712-91dc-11c6d1adb170?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ](15GB) running locally using Ollama [ https://substack.com/redirect/3f22476c-aba4-43d8-82ae-24ea9a77a65b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (I had to add "Use your python tool" to the prompt to get it to work):
ollama pull mistral-small3.1:24b

uv run --with devtools --with pydantic-ai python -c '
import asyncio
from devtools import pprint
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.mcp import MCPServerStdio

server = MCPServerStdio(
"deno",
args=[
"run",
"-N",
"-R=node_modules",
"-W=node_modules",
"--node-modules-dir=auto",
"jsr:@pydantic/mcp-run-python",
"stdio",
],
)

agent = Agent(
OpenAIModel(
model_name="mistral-small3.1:latest",
provider=OpenAIProvider(base_url="http://localhost:11434/v1"),
),
mcp_servers=[server],
)

async def main:
with capture_run_messages as messages:
async with agent.run_mcp_servers:
result = await agent.run("How many days between 2000-01-01 and 2025-03-18? Use your python tool.")
pprint(messages)
print(result.output)

asyncio.run(main)'
Here's the full output [ https://substack.com/redirect/9d7ed33a-dfc4-4db4-a752-05e7a50f9270?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] including the debug logs.
Quote 2025-04-18
To me, a successful eval meets the following criteria. Say, we currently have system A, and we might tweak it to get a system B:
- If A works significantly better than B according to a skilled human judge, the eval should give A a significantly higher score than B.
- If A and B have similar performance, their eval scores should be similar.
Whenever a pair of systems A and B contradicts these criteria, that is a sign the eval is in “error” and we should tweak it to make it rank A and B correctly.
Andrew Ng [ https://substack.com/redirect/413d3203-2916-49d8-b6d1-1cff38d30688?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOakUyTXpjeU1qY3NJbWxoZENJNk1UYzBOVEF3T1Rnd05pd2laWGh3SWpveE56YzJOVFExT0RBMkxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuRVhpUnU1NUFBR1J5MkFCcEJlNzgxa0hvYnNoaWJXcTV3TVpWNG9nZEFXTSIsInAiOjE2MTYzNzIyNywicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQ1MDA5ODA2LCJleHAiOjE3NDc2MDE4MDYsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.XHEuxHfPtLA1AX0TNrZ7fBqp4Q66Q68ddHaxyeLFU-Y?
