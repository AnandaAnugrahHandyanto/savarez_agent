# New audio models from OpenAI, but how much can we rely on them?

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-03-25T04:24:37.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/new-audio-models-from-openai-but

In this newsletter:
New audio models from OpenAI, but how much can we rely on them?
Plus 11 links and 2 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
New audio models from OpenAI, but how much can we rely on them? [ https://substack.com/redirect/f31bcc11-e339-4a7c-832f-b2f6bddf62f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-03-20
OpenAI announced several new audio-related API features [ https://substack.com/redirect/31e2f1ff-6e1d-44d9-af90-52e720511ddb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today, for both text-to-speech and speech-to-text. They're very promising new models, but they appear to suffer from the ever-present risk of accidental (or malicious) instruction following.
gpt-4o-mini-tts
gpt-4o-mini-tts is a brand new text-to-speech model with "better steerability". OpenAI released a delightful new playground interface for this at OpenAI.fm [ https://substack.com/redirect/6bdf0b74-bd5c-4b44-9989-c86b1a56d182?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - you can pick from 11 base voices, apply instructions like "High-energy, eccentric, and slightly unhinged" and get it to read out a script (with optional extra stage directions in parenthesis). It can then provide the equivalent API code in Python, JavaScript or curl. You can share links to your experiments, here's an example [ https://substack.com/redirect/f31e2153-38a4-4675-85ba-6e6553b04d57?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Note how part of my script there looks like this:
(Whisper this bit:)
Footsteps echoed behind her, slow and deliberate. She turned, heart racing, but saw only shadows.
While fun and convenient, the fact that you can insert stage directions in the script itself feels like an anti-pattern to me - it means you can't safely use this for arbitrary text because there's a risk that some of that text may accidentally be treated as further instructions to the model.
In my own experiments I've already seen this happen: sometimes the model follows my "Whisper this bit" instruction correctly, other times it says the word "Whisper" out loud but doesn't speak the words "this bit". The results appear non-deterministic, and might also vary with different base voices.
gpt-4o-mini-tts costs [ https://substack.com/redirect/9da5768c-23d9-41d9-8f7d-8d52163c710a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] $0.60/million tokens, which OpenAI estimate as around 1.5 cents per minute.
gpt-4o-transcribe and gpt-4o-mini-transcribe
gpt-4o-transcribe and gpt-4o-mini-transcribe are two new speech-to-text models, serving a similar purpose to whisper [ https://substack.com/redirect/7e213a93-da00-4038-a348-d50d9ba7c817?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but built on top of GPT-4o and setting a "new state-of-the-art benchmark". These can be used via OpenAI's v1/audio/transcriptions API [ https://substack.com/redirect/4577e631-e89b-4c36-aed3-8d3098d9bd8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], as alternative options to `whisper-1. The API is still restricted to a 25MB audio file (MP3, WAV or several other formats).
Any time an LLM-based model is used for audio transcription (or OCR) I worry about accidental instruction following - is there a risk that content that looks like an instruction in the spoken or scanned text might not be included in the resulting transcript?
In a comment on Hacker News [ https://substack.com/redirect/3f862978-fb97-4bb9-bc31-6803ce6b3d76?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] OpenAI's Jeff Harris said this, regarding how these new models differ from gpt-4o-audio-preview [ https://substack.com/redirect/97e0e5a6-71bb-4aa5-8b6d-21ec76f7cee5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It's a slightly better model for TTS. With extra training focusing on reading the script exactly as written.
e.g. the audio-preview model when given instruction to speak "What is the capital of Italy" would often speak "Rome". This model should be much better in that regard
"much better in that regard" sounds to me like there's still a risk of this occurring, so for some sensitive applications it may make sense to stick with whisper or other traditional text-to-speech approaches.
On Twitter Jeff added [ https://substack.com/redirect/04553f6d-1552-4f81-869d-32482fc97ce3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
yep fidelity to transcript is the big chunk of work to turn an audio model into TTS model. still possible, but should be quite rare
gpt-4o-transcribe is an estimated 0.6 cents per minute, and gpt-4o-mini-transcribe is 0.3 cents per minute.
Mixing data and instructions remains the cardinal sin of LLMs
If these problems look familiar to you that's because they are variants of the root cause behind prompt injection [ https://substack.com/redirect/7bc635d8-6ce2-405f-959b-702b65de462c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. LLM architectures encourage mixing instructions and data in the same stream of tokens, but that means there are always risks that tokens from data (which often comes from untrusted sources) may be misinterpreted as instructions to the model.
How much of an impact this has on the utility of these new models remains to be seen. Maybe the new training is so robust that these issues won't actually cause problems for real-world applications?
I remain skeptical. I expect we'll see demos of these flaws in action in relatively short order.
Link 2025-03-19 OpenAI platform: o1-pro [ https://substack.com/redirect/d5075d7b-0f57-4551-902e-3f5b6bd3eaca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI have a new most-expensive model: o1-pro can now be accessed through their API at a hefty $150/million tokens for input and $600/million tokens for output. That's 10x the price of their o1 and o1-preview models and a full 1,000x times more expensive than their cheapest model, gpt-4o-mini!
Aside from that it has mostly the same features as o1: a 200,000 token context window, 100,000 max output tokens, Sep 30 2023 knowledge cut-off date and it supports function calling, structured outputs and image inputs.
o1-pro doesn't support streaming, and most significantly for developers is the first OpenAI model to only be available via their new Responses API [ https://substack.com/redirect/3ffe4086-320c-4d73-aeda-f3177b43d332?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This means tools that are built against their Chat Completions API (like my own LLM [ https://substack.com/redirect/f2ae4936-71ad-423f-85b3-9242012e362a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) have to do a whole lot more work to support the new model - my issue for that is here [ https://substack.com/redirect/7f9aaf04-0243-4579-b25d-0bb6f2a77327?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Since LLM doesn't support this new model yet I had to make do with curl:
curl https://api.openai.com/v1/responses \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $(llm keys get openai)" \
-d '{
"model": "o1-pro",
"input": "Generate an SVG of a pelican riding a bicycle"
}'
Here's the full JSON [ https://substack.com/redirect/5dd1fcd6-07e5-41f0-a7a7-142e551f8e52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I got back - 81 input tokens and 1552 output tokens for a total cost [ https://substack.com/redirect/45f3f139-92f3-4517-a747-d5eaa01781af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of 94.335 cents.
I took a risk and added "reasoning": {"effort": "high"} to see if I could get a better pelican with more reasoning:
curl https://api.openai.com/v1/responses \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $(llm keys get openai)" \
-d '{
"model": "o1-pro",
"input": "Generate an SVG of a pelican riding a bicycle",
"reasoning": {"effort": "high"}
}'
Surprisingly that used less output tokens - 1459 compared to 1552 earlier (cost: 88.755 cents) - producing this JSON [ https://substack.com/redirect/f40f98fe-9c38-446e-98df-121cc4753307?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which rendered as a slightly better pelican:
It was cheaper because while it spent 960 reasoning tokens as opposed to 704 for the previous pelican it omitted the explanatory text around the SVG, saving on total output.
Quote 2025-03-20
I’ve disabled the pending geoblock of the UK because I now think the risks of the Online Safety Act to this site are low enough to change strategies to only geoblock if directly threatened by the regulator. [...]
It is not possible for a hobby site to comply with the Online Safety Act. The OSA is written to censor huge commercial sites with professional legal teams, and even understanding one's obligations under the regulations is an enormous project requiring expensive legal advice.
The law is 250 pages [ https://substack.com/redirect/5ab492ef-fcb5-4533-9bcd-68062cb36832?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the mandatory "guidance" from Ofcom is more than 3,000 pages of dense, cross-referenced UK-flavoured legalese. To find all the guidance you'll have to start here [ https://substack.com/redirect/537f18cf-ad59-4a98-858d-cf0cbca6668a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], click through to each of the 36 pages listed, and expand each page's collapsible sections that might have links to other pages and documents. (Though I can't be sure that leads to all their guidance, and note you'll have to check back regularly for planned updates [ https://substack.com/redirect/16519d02-6464-49bb-8b6d-0e2b75d5d3b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
Peter Bhat Harkins [ https://substack.com/redirect/cabc4654-aaf5-4f3f-9775-eb8ba7d19c22?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-03-20 Claude can now search the web [ https://substack.com/redirect/e0118a52-5767-4752-b209-30465d06efa5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Claude 3.7 Sonnet on the paid plan now has a web search tool that can be turned on as a global setting.
This was sorely needed. ChatGPT, Gemini and Grok all had this ability already, and despite Anthropic's excellent model quality it was one of the big remaining reasons to keep other models in daily rotation.
For the moment this is purely a product feature - it's available through their consumer applications but there's no indication of whether or not it will be coming to the Anthropic API. OpenAI launched the latest version of web search in their API last week [ https://substack.com/redirect/7356119b-1cda-43b6-8217-6d9f8b52a8fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Surprisingly there are no details on how it works under the hood. Is this a partnership with someone like Bing, or is it Anthropic's own proprietary index populated by their own crawlers?
I think it may be their own infrastructure, but I've been unable to confirm that.
Update: it's confirmed as Brave Search [ https://substack.com/redirect/7701adae-b0c4-4649-b7f4-684a80218337?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Their support site offers some inconclusive hints.
Does Anthropic crawl data from the web, and how can site owners block the crawler? [ https://substack.com/redirect/734c8fdd-c5ea-4b5f-bc57-6523c295c7c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] talks about their ClaudeBot crawler but the language indicates it's used for training data, with no mention of a web search index.
Blocking and Removing Content from Claude [ https://substack.com/redirect/da53ecaa-72f6-4d2b-8352-a7f011fefade?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] looks a little more relevant, and has a heading "Blocking or removing websites from Claude web search" which includes this eyebrow-raising tip:
Removing content from your site is the best way to ensure that it won't appear in Claude outputs when Claude searches the web.
And then this bit, which does mention "our partners":
The noindex robots meta tag is a rule that tells our partners not to index your content so that they don’t send it to us in response to your web search query. Your content can still be linked to and visited through other web pages, or directly visited by users with a link, but the content will not appear in Claude outputs that use web search.
Both of those documents were last updated "over a week ago", so it's not clear to me if they reflect the new state of the world given today's feature launch or not.
I got this delightful response trying out Claude search where it mistook my recent Squadron automata [ https://substack.com/redirect/06339c53-4e0b-4a89-bc6e-998bcd70d056?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for a software project:
Link 2025-03-21 Anthropic Trust Center: Brave Search added as a subprocessor [ https://substack.com/redirect/13a3766d-e2b4-4be7-bc26-69865d6d2985?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Yesterday I was trying to figure out [ https://substack.com/redirect/d212e9e2-a81f-449b-b201-56544d76b2cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] if Anthropic has rolled their own search index for Claude's new web search feature or if they were working with a partner. Here's confirmation that they are using Brave Search [ https://substack.com/redirect/040045bd-cf6e-44f3-a5b1-b879714779f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic's subprocessor list. As of March 19, 2025, we have made the following changes:
Subprocessors added:
Brave Search (more info [ https://substack.com/redirect/aeaaa64f-eace-4b14-9e53-bb89630490a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
That "more info" links to the help page for their new web search feature.
I confirmed this myself by prompting Claude to "Search for pelican facts [ https://substack.com/redirect/92766e41-e076-4958-af84-a3cafec5ac99?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]" - it ran a search for "Interesting pelican facts" and the ten results it showed as citations were an exact match for that search on Brave [ https://substack.com/redirect/dd54215c-e499-4950-bba6-7ccf51205643?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
And further evidence: if you poke at it a bit [ https://substack.com/redirect/713cafdb-6cdd-49cd-b124-eeb64916fb34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Claude will reveal the definition of its web_search function which looks like this - note the BraveSearchParams property:
{
"description": "Search the web",
"name": "web_search",
"parameters": {
"additionalProperties": false,
"properties": {
"query": {
"description": "Search query",
"title": "Query",
"type": "string"
}
},
"required": [
"query"
],
"title": "BraveSearchParams",
"type": "object"
}
}
Link 2025-03-21 The "think" tool: Enabling Claude to stop and think in complex tool use situations [ https://substack.com/redirect/415a76f6-81f8-4136-8d1f-23a903174d20?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fascinating new prompt engineering trick from Anthropic. They use their standard tool calling mechanism to define a tool called "think" that looks something like this:
{
"name": "think",
"description": "Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log. Use it when complex reasoning or some cache memory is needed.",
"input_schema": {
"type": "object",
"properties": {
"thought": {
"type": "string",
"description": "A thought to think about."
}
},
"required": ["thought"]
}
}
This tool does nothing at all.
LLM tools (like web_search [ https://substack.com/redirect/bbdef1bd-e9b8-4146-96a6-2dbe0058bd19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) usually involve some kind of implementation - the model requests a tool execution, then an external harness goes away and executes the specified tool and feeds the result back into the conversation.
The "think" tool is a no-op - there is no implementation, it just allows the model to use its existing training in terms of when-to-use-a-tool to stop and dump some additional thoughts into the context.
This works completely independently of the new "thinking" mechanism introduced in Claude 3.7 Sonnet [ https://substack.com/redirect/096d7af4-1c5b-42e7-a829-495fa857aefe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Anthropic's benchmarks show impressive improvements from enabling this tool. I fully anticipate that models from other providers would benefit from the same trick.
Link 2025-03-22 simonw/ollama-models-atom-feed [ https://substack.com/redirect/4151acb9-9889-4334-9281-788da7378fed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I setup a GitHub Actions + GitHub Pages Atom feed of scraped recent models data from the Ollama latest models [ https://substack.com/redirect/edfece90-dc85-4812-9b6c-bc0d040a69ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] page - Ollama remains one of the easiest ways to run models on a laptop so a new model release from them is worth hearing about.
I built the scraper by pasting example HTML into Claude [ https://substack.com/redirect/593249a5-5776-432e-a8f1-6ceceec30eb9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and asking for a Python script to convert it to Atom - here's the script [ https://substack.com/redirect/1b4ebd62-72a3-4050-9b71-834b1574aaf6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] we wrote together.
Quote 2025-03-23
If you’re new to tech, taking [career] advice on what works for someone with a 20-year career is likely to be about as effective as taking career advice from a stockbroker or firefighter or nurse. There’ll be a few things that generalize, but most advice won’t.
Further, even advice people with long careers on what worked for them when they were getting started is unlikely to be advice that works today. The tech industry of 15 or 20 years ago was, again, dramatically different from tech today.
Jacob Kaplan-Moss [ https://substack.com/redirect/fbeb2033-30ef-49f5-bda8-791d360a80f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-03-23 Next.js and the corrupt middleware: the authorizing artifact [ https://substack.com/redirect/8c197c53-89c6-401e-aafc-771e3cafb1f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Good, detailed write-up of the Next.js vulnerability CVE-2025-29927 [ https://substack.com/redirect/682ca357-03fe-4179-9a84-30b94007527e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Allam Rachid, one of the researchers who identified the issue.
The vulnerability is best illustrated by this code snippet [ https://substack.com/redirect/eec0bab5-e3e7-441b-8d28-f5f87b71915f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
const subreq = params.request.headers['x-middleware-subrequest'];
const subrequests = typeof subreq === 'string' ? subreq.split(':') : [];
// ...
for (const middleware of this.middleware || []) {
// ...
if (subrequests.includes(middlewareInfo.name)) {
result = {
response: NextResponse.next,
waitUntil: Promise.resolve,
};
continue;
}
}
This was part of Next.js internals used to help avoid applying middleware recursively to requests that are re-dispatched through the framework.
Unfortunately it also meant that attackers could send a x-middleware-subrequest HTTP header with a colon-separated list of middleware names to skip. If a site used middleware to apply an authentication gate (as suggested in the Next.js documentation [ https://substack.com/redirect/f78820c6-1a67-4ef7-92c8-a776c5170323?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) an attacker could bypass that authentication using this trick.
The vulnerability has been fixed in Next.js 15.2.3 - here's the official release announcement [ https://substack.com/redirect/d7c2f071-92a8-42b7-8b3c-3bf1f5653d84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] talking about the problem.
Link 2025-03-23 Semantic Diffusion [ https://substack.com/redirect/d3d3e54c-be18-46a9-bdb6-15ede2a22bc2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I learned about [ https://substack.com/redirect/d5e146ab-f745-47a1-b555-e49116c9c74d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this term today while complaining about how the definition of "vibe coding" is already being distorted to mean "any time an LLM writes code" as opposed to the intended meaning [ https://substack.com/redirect/48674a4b-85c3-4c81-82b3-10973124c5f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of "code I wrote with an LLM without even reviewing what it wrote".
I posted this salty note [ https://substack.com/redirect/5fa0ce9b-ae2e-4c05-9842-71132100ee36?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Feels like I'm losing the battle on this one, I keep seeing people use "vibe coding" to mean any time an LLM is used to write code
I'm particularly frustrated because for a few glorious moments we had the chance at having ONE piece of AI-related terminology with a clear, widely accepted definition!
But it turns out people couldn't be trusted to read all the way to the end of Andrej's tweet, so now we are back to yet another term where different people assume it means different things
Martin Fowler coined Semantic Diffusion in 2006 with this very clear definition:
Semantic diffusion occurs when you have a word that is coined by a person or group, often with a pretty good definition, but then gets spread through the wider community in a way that weakens that definition. This weakening risks losing the definition entirely - and with it any usefulness to the term.
What's happening with vibe coding right now is such a clear example of this effect in action! I've seen the same thing happen [ https://substack.com/redirect/53f781b9-7e74-43db-9e12-e52903eecc2e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to my own coinage prompt injection [ https://substack.com/redirect/1a148a32-29c6-40f7-a2c8-93f534a83870?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] over the past couple of years.
This kind of dillution of meaning is frustrating, but does appear to be inevitable. As Martin Fowler points out it's most likely to happen to popular terms - the more popular a term is the higher the chance a game of telephone will ensue where misunderstandings flourish as the chain continues to grow.
Andrej Karpathy, who coined [ https://substack.com/redirect/00165930-6077-4df6-9418-1786166e9c4a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] vibe coding, posted this [ https://substack.com/redirect/5de82dfc-bc94-4402-80d2-00e47c11db4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] just now in reply to my article [ https://substack.com/redirect/48674a4b-85c3-4c81-82b3-10973124c5f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Good post! It will take some time to settle on definitions. Personally I use "vibe coding" when I feel like this dog. My iOS app last night being a good example. But I find that in practice I rarely go full out vibe coding, and more often I still look at the code, I add complexity slowly and I try to learn over time how the pieces work, to ask clarifying questions etc.
I love that vibe coding has an official illustrative GIF now!
Link 2025-03-24 deepseek-ai/DeepSeek-V3-0324 [ https://substack.com/redirect/11bb605f-4150-421e-b67e-5a2b32bf3085?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Chinese AI lab DeepSeek just released the latest version of their enormous DeepSeek v3 model, baking the release date into the name DeepSeek-V3-0324.
The license is MIT (that's new - previous DeepSeek v3 had a custom license), the README is empty and the release adds up a to a total of 641 GB of files, mostly of the form model-00035-of-000163.safetensors.
The model only came out a few hours ago and MLX developer Awni Hannun already has it running [ https://substack.com/redirect/794fb871-dc71-4b96-8939-7ff292af776d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at >20 tokens/second on a 512GB M3 Ultra Mac Studio ($9,499 of ostensibly consumer-grade hardware) via mlx-lm [ https://substack.com/redirect/c9113f4f-1834-47b8-994d-055c2c16c072?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and this mlx-community/DeepSeek-V3-0324-4bit [ https://substack.com/redirect/95a8f45a-e01b-4342-a0b3-06b23d6347ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] 4bit quantization, which reduces the on-disk size to 352 GB.
I think that means if you have that machine you can run it with my llm-mlx [ https://substack.com/redirect/f6de3c1e-3329-4732-af96-6326487faf6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin like this, but I've not tried myself!
llm mlx download-model mlx-community/DeepSeek-V3-0324-4bit
llm chat -m mlx-community/DeepSeek-V3-0324-4bit

The new model is also listed on OpenRouter [ https://substack.com/redirect/14a3548c-9ce4-4acc-ba62-483ef528ff3e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can try a chat at openrouter.ai/chat?models=deepseek/deepseek-chat-v3-0324:free [ https://substack.com/redirect/139e25aa-04e1-4223-9471-17243d188264?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here's what the chat interface gave me [ https://substack.com/redirect/b1e0c67c-c909-4c56-8c3a-ca88eca83ab9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for "Generate an SVG of a pelican riding a bicycle":
I have two API keys with OpenRouter - one of them worked with the model, the other gave me a No endpoints found matching your data policy error - I think because I had a setting on that key disallowing models from training on my activity. The key that worked was a free key with no attached billing credentials.
For my working API key the llm-openrouter [ https://substack.com/redirect/37115744-14f2-4bc5-a884-1233733a4183?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin let me run a prompt like this:
llm install llm-openrouter
llm keys set openrouter
# Paste key here
llm -m openrouter/deepseek/deepseek-chat-v3-0324:free "best fact about a pelican"
Here's that "best fact" - the terminal output included Markdown and an emoji combo, here that's rendered.
One of the most fascinating facts about pelicans is their unique throat pouch, called a gular sac, which can hold up to 3 gallons (11 liters) of water—three times more than their stomach!
Here’s why it’s amazing:
Fishing Tool: They use it like a net to scoop up fish, then drain the water before swallowing.
Cooling Mechanism: On hot days, pelicans flutter the pouch to stay cool by evaporating water.
Built-in "Shopping Cart": Some species even use it to carry food back to their chicks.
Bonus fact: Pelicans often fish cooperatively, herding fish into shallow water for an easy catch.
Would you like more cool pelican facts? 🐦🌊
In putting this post together I got Claude [ https://substack.com/redirect/33900919-9747-43e0-b171-b1a15f44a3ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to build me this new tool [ https://substack.com/redirect/e579def4-22bc-4073-a781-3049c4fd238a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for finding the total on-disk size of a Hugging Face repository, which is available in their API but not currently displayed on their website.
Update: Here's a notable independent benchmark from Paul Gauthier [ https://substack.com/redirect/c3de83cb-6335-4866-b38d-70d521c30788?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
DeepSeek's new V3 scored 55% on aider's polyglot benchmark [ https://substack.com/redirect/a7b0c5e7-4a00-468d-8715-569028c78881?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], significantly improving over the prior version. It's the #2 non-thinking/reasoning model, behind only Sonnet 3.7. V3 is competitive with thinking models like R1 & o3-mini.
Link 2025-03-24 Qwen2.5-VL-32B: Smarter and Lighter [ https://substack.com/redirect/24b99d6f-7171-40be-b055-47ed2e5f320a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The second big open weight LLM release from China today - the first being DeepSeek v3-0324 [ https://substack.com/redirect/bf7adc74-63bb-4559-bad0-3194a23c6bd8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Qwen's previous vision model was Qwen2.5 VL, released in January [ https://substack.com/redirect/17e146cd-4f73-4a15-a812-a69861fa0e70?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in 3B, 7B and 72B sizes.
Today's Apache 2.0 licensed release is a 32B model, which is quickly becoming my personal favourite model size - large enough to have GPT-4-class capabilities, but small enough that on my 64GB Mack there's still enough RAM for me to run other memory-hungry applications like Firefox and VS Code.
Qwen claim that the new model (when compared to their previous 2.5 VL family) can "align more closely with human preferences", is better at "mathematical reasoning" and provides "enhanced accuracy and detailed analysis in tasks such as image parsing, content recognition, and visual logic deduction".
They also offer some presumably carefully selected benchmark results showing it out-performing Gemma 3-27B, Mistral Small 3.1 24B and GPT-4o-0513 (there have been two more recent GPT-4o releases since that one, 2024-08-16 and 2024-11-20).
As usual, Prince Canuma had MLX versions of the models live within hours of the release, in 4 bit [ https://substack.com/redirect/d2d0aa2b-e483-4a00-8940-73f2bb64220c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], 6 bit [ https://substack.com/redirect/2b7a81c6-f1c7-4550-997f-be7647f04d64?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], 8 bit [ https://substack.com/redirect/17847a82-3863-462b-816d-f404dd913330?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and bf16 [ https://substack.com/redirect/5432783d-18fe-49a0-8ba8-6a07de396c15?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] variants.
I ran the 4bit version (a 18GB model download) using uv and Prince's mlx-vlm [ https://substack.com/redirect/8e15fbcb-287d-4399-983c-2177e685d0da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
uv run --with 'numpy<2' --with mlx-vlm \
python -m mlx_vlm.generate \
--model mlx-community/Qwen2.5-VL-32B-Instruct-4bit \
--max-tokens 1000 \
--temperature 0.0 \
--prompt "Describe this image." \
--image Mpaboundrycdfw-1.png
Here's the image:
And here's the resulting description, which I found to be very impressive:
This image appears to be a map highlighting specific areas along the coastline, likely in California, based on the geographical features and place names. Here is a detailed description of the image:
Geographic Features:
The map shows a section of the coastline, with land on the right and the sea on the left.
The land area includes parts of SanMateo County, as noted in the top-right corner.
The coastline features several named locations, including:
Point Montara
Pillar Point
Kings Rock
VicenteCreek
DennistonCreek
State Beach
Highlighted Areas:
The map contains two distinct areas marked with different colors:
Red Area (Top Section)
Labeled as "MONTARA" and "MONTARA M R" (possibly referring to a "Marine Reserves" or similar protected area).
This area is marked with a dark red color and extends from the coastline inland.
Blue Area (Bottom Section)
Labeled as "PILLAR" and "PILLAR P O I N T" along with "SMCA" (Special Management Area).
This area is marked with a blue color and is located closer to the coastline, including the area around "Pillar Point."
Depth Contours:
The map includes depth markings in the sea, indicating the bathymetrical features:
20 fathom (fm) line is marked in the upper-left part of the sea.
10 fathom (fm) line is marked closer to the coastline.
30 fathom (fm) line is marked further out to sea.
Other Features:
State Beach: Marked near the top-right, indicating a protected recreational area.
Kings Rock: A prominent feature near the coastline, likely a rocky outcropping.
Creeks: The map shows several creeks, including VicenteCreek and DennistonCreek, which flow into the sea.
Protected Areas:
The map highlights specific protected areas:
Marine Reserves:
"MONTARA M R" (Marine Reserves) in red.
Special Management Area (SMCA)
"PILLAR P O I N T" in blue, indicating a Special Management Area.
Grid and Coordinates:
The map includes a grid with latitude and longitude markings:
Latitude ranges from approximately 37°25'N to 37°35'N.
Longitude ranges from approximately 122°22.5'W to 122°35.5'W.
Topography:
The land area shows topographic features, including elevations and vegetation, with green areas indicating higher elevations or vegetated land.
Other Labels:
"SMR": Likely stands for "State Managed Reserves."
"SMCA": Likely stands for "Special Management Control Area."
In summary, this map highlights specific protected areas along the coastline, including a red "Marine Reserves" area and a blue "Special Management Area" near "Pillar Point." The map also includes depth markings, geographical features, and place names, providing a detailed view of the region's natural and protected areas.
It included the following runtime statistics:
Prompt: 1051 tokens, 111.985 tokens-per-sec
Generation: 760 tokens, 17.328 tokens-per-sec
Peak memory: 21.110 GB
Link 2025-03-25 microsoft/playwright-mcp [ https://substack.com/redirect/037918f4-ea27-4cd8-8bf7-18bb6aa2508a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The Playwright team at Microsoft have released an MCP (Model Context Protocol [ https://substack.com/redirect/037918f4-ea27-4cd8-8bf7-18bb6aa2508a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) server wrapping Playwright, and it's pretty fascinating.
They implemented it on top of the Chrome accessibility tree, so MCP clients (such as the Claude Desktop app) can use it to drive an automated browser and use the accessibility tree to read and navigate pages that they visit.
Trying it out is quite easy if you have Claude Desktop and Node.js installed already. Edit your claude_desktop_config.json file:
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
And add this:
{
"mcpServers": {
"playwright": {
"command": "npx",
"args": [
"@playwright/mcp@latest"
]
}
}
}
Now when you launch Claude Desktop various new browser automation tools will be available to it, and you can tell Claude to navigate to a website and interact with it.
I ran the following to get a list of the available tools:
cd /tmp
git clone https://github.com/microsoft/playwright-mcp
cd playwright-mcp/src/tools
files-to-prompt . | llm -m claude-3.7-sonnet \
'Output a detailed description of these tools'
The full output is here [ https://substack.com/redirect/51308770-483f-4f42-8c03-c8ffa8745d3e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but here's the truncated tool list:
Navigation Tools (common.ts)
browser_navigate: Navigate to a specific URL
browser_go_back: Navigate back in browser history
browser_go_forward: Navigate forward in browser history
browser_wait: Wait for a specified time in seconds
browser_press_key: Press a keyboard key
browser_save_as_pdf: Save current page as PDF
browser_close: Close the current page
Screenshot and Mouse Tools (screenshot.ts)
browser_screenshot: Take a screenshot of the current page
browser_move_mouse: Move mouse to specific coordinates
browser_click (coordinate-based): Click at specific x,y coordinates
browser_drag (coordinate-based): Drag mouse from one position to another
browser_type (keyboard): Type text and optionally submit
Accessibility Snapshot Tools (snapshot.ts)
browser_snapshot: Capture accessibility structure of the page
browser_click (element-based): Click on a specific element using accessibility reference
browser_drag (element-based): Drag between two elements
browser_hover: Hover over an element
browser_type (element-based): Type text into a specific element
Link 2025-03-25 shot-scraper 1.8 [ https://substack.com/redirect/c70d7a6b-44b9-411e-b885-a9b7f98f2a55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've added a new feature to shot-scraper [ https://substack.com/redirect/9fe74445-5c7c-4cdd-95a8-1dbe106a4a87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that makes it easier to share scripts for other people to use with the shot-scraper javascript [ https://substack.com/redirect/886ddfb4-55b9-48bc-99c3-45f17fadd0e5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] command.
shot-scraper javascript lets you load up a web page in an invisible Chrome browser (via Playwright), execute some JavaScript against that page and output the results to your terminal. It's a fun way of running complex screen-scraping routines as part of a terminal session, or even chained together with other commands using pipes.
The -i/--input option lets you load that JavaScript from a file on disk - but now you can also use a gh: prefix to specify loading code from GitHub instead.
To quote the release notes [ https://substack.com/redirect/c70d7a6b-44b9-411e-b885-a9b7f98f2a55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
shot-scraper javascript can now optionally load scripts hosted on GitHub [ https://substack.com/redirect/5aad04c7-c628-466a-8eb2-c7165c88302b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] via the new gh: prefix to the shot-scraper javascript -i/--input option. #173 [ https://substack.com/redirect/0581bd3f-dd2f-471d-b141-530ffe829286?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Scripts can be referenced as gh:username/repo/path/to/script.js or, if the GitHub user has created a dedicated shot-scraper-scripts repository and placed scripts in the root of it, using gh:username/name-of-script.
For example, to run this readability.js [ https://substack.com/redirect/64f18828-c884-49a3-a33d-f94faa15d928?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] script against any web page you can use the following:
shot-scraper javascript --input gh:simonw/readability \
https://simonwillison.net/2025/Mar/24/qwen25-vl-32b/
The output from that example [ https://substack.com/redirect/78c3ab72-eaf2-416f-b105-c0402bd9333f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] starts like this:
{
"title": "Qwen2.5-VL-32B: Smarter and Lighter",
"byline": "Simon Willison",
"dir": null,
"lang": "en-gb",
"content": "<div id=\"readability-page-1\"...
My simonw/shot-scraper-scripts [ https://substack.com/redirect/1834e707-a678-41f1-8680-d4f7de21cb6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repo only has that one file in it so far, but I'm looking forward to growing that collection and hopefully seeing other people create and share their own shot-scraper-scripts repos as well.
This feature is an imitation of a similar feature [ https://substack.com/redirect/6a3ff71d-ae14-4240-98bc-6811c269c1af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that's coming in the next release of LLM.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVGs0TURRM09ERXNJbWxoZENJNk1UYzBNamczTmpZNE9Dd2laWGh3SWpveE56YzBOREV5TmpnNExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuYVdvU1YwQURlaDZneWlNQ0lNcTdRclludEdHVE91SG9Gc1Y0V0tZLXlxTSIsInAiOjE1OTgwNDc4MSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQyODc2Njg4LCJleHAiOjE3NDU0Njg2ODgsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.Xivjg1pCJFGHxkgr6a2LAuFgyykeh8CL86tDokClQHk?
