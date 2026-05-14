# Putting Gemini 2.5 Pro throu

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-03-26T17:37:29.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/putting-gemini-25-pro-throu

In this newsletter:
Putting Gemini 2.5 Pro through its paces
Plus 1 link and 2 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Putting Gemini 2.5 Pro through its paces [ https://substack.com/redirect/4a76425d-bc05-47c1-a782-90d5469458bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-03-25
There's a new release from Google Gemini this morning: the first in the Gemini 2.5 [ https://substack.com/redirect/84c79417-cf6f-4b20-9f4b-1cba7b96801e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] series. Google call it "a thinking model, designed to tackle increasingly complex problems". It's already sat at the top of the LM Arena leaderboard [ https://substack.com/redirect/3d05e0e0-5089-4361-a172-638294457b4d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and from initial impressions looks like it may deserve that top spot.
I just released llm-gemini 0.16 [ https://substack.com/redirect/297d6afc-7478-4538-816b-eb5a544116ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adding support for the new model to my LLM [ https://substack.com/redirect/4d6e0a59-40d5-4d1d-a7f5-2e5db0b6f366?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] command-line tool. Let's try it out.
The pelican riding a bicycle [ https://substack.com/redirect/2eec2ce4-a591-40ad-a3ca-58455a895522?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Transcribing audio [ https://substack.com/redirect/859fd12b-e61d-48e5-bb6a-678179582fb4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Bounding boxes [ https://substack.com/redirect/29b1e3e2-4012-4690-ab7e-6b991ce14f92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
More characteristics of the model [ https://substack.com/redirect/f4dee1d4-c661-4768-8234-6c01719bb896?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Gemini 2.5 Pro is a very strong new model [ https://substack.com/redirect/86e9cc2c-a509-4b13-823d-a072a684d25c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Update: it's very good at code [ https://substack.com/redirect/8774446b-ca87-4c89-a91e-38e44a15ade2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The pelican riding a bicycle
First up, my classic generate an SVG of a pelican riding a bicycle [ https://substack.com/redirect/e7415069-435c-4c1e-a57c-d9c4a177ee88?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] prompt.
# Upgrade the plugin
llm install -U llm-gemini

# Now run the prompt:
llm -m gemini-2.5-pro-exp-03-25 "Generate an SVG of a pelican riding a bicycle"
It's pretty solid!
Here's the full transcript [ https://substack.com/redirect/31f7685b-4723-423e-8baf-dddf5fc275d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This task is meant to be almost impossible: pelicans are the wrong shape to ride bicycles! Given that, I think this is a good attempt - I like it slightly better than my previous favourite Claude 3.7 Sonnet [ https://substack.com/redirect/8b9368a4-7143-4fd1-9ae8-bf6465e2a108?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which produced this a month ago:
Transcribing audio
I had an MP3 [ https://substack.com/redirect/9e7de96d-a844-4ad0-a865-ae63fc9106c5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] lying around from a previous experiment [ https://substack.com/redirect/939b763e-c465-4eac-be49-8d92fd1dab55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which mixes English and Spanish. I tried running it with the prompt transcribe to see what would happen:
llm -m gemini-2.5-pro-exp-03-25 'transcribe' \
-a https://static.simonwillison.net/static/2025/russian-pelican-in-spanish.mp3
I got back this, with timestamps interspersed with the text:
I need you [ 0m0s450ms ] to pretend [ 0m0s880ms ] to be [ 0m0s990ms ] a California [ 0m1s560ms ] brown [ 0m1s850ms ] pelican [ 0m2s320ms ] with [ 0m2s480ms ] a very [ 0m2s990ms ] thick [ 0m3s290ms ] Russian [ 0m3s710ms ] accent, [ 0m4s110ms ] but [ 0m4s540ms ] you [ 0m4s640ms ] talk [ 0m4s830ms ] to me [ 0m4s960ms ] exclusively [ 0m5s660ms ] in Spanish. [ 0m6s200ms ] Oye, [ 0m8s930ms ] camarada, [ 0m9s570ms ] aquí [ 0m10s240ms ] está [ 0m10s590ms ] tu [ 0m10s740ms ] pelícano [ 0m11s370ms ] californiano [ 0m12s320ms ] con [ 0m12s520ms ] acento [ 0m13s100ms ] ruso. [ 0m13s540ms ] Qué [ 0m14s230ms ] tal, [ 0m14s570ms ] tovarisch? [ 0m15s210ms ] Listo [ 0m15s960ms ] para [ 0m16s190ms ] charlar [ 0m16s640ms ] en [ 0m16s750ms ] español? [ 0m17s250ms ] How's [ 0m19s834ms ] your [ 0m19s944ms ] day [ 0m20s134ms ] today? [ 0m20s414ms ] Mi [ 0m22s654ms ] día [ 0m22s934ms ] ha [ 0m23s4ms ] sido [ 0m23s464ms ] volando [ 0m24s204ms ] sobre [ 0m24s594ms ] las [ 0m24s844ms ] olas, [ 0m25s334ms ] buscando [ 0m26s264ms ] peces [ 0m26s954ms ] y [ 0m27s84ms ] disfrutando [ 0m28s14ms ] del [ 0m28s244ms ] sol [ 0m28s664ms ] californiano. [ 0m29s444ms ] Y [ 0m30s314ms ] tú, [ 0m30s614ms ] amigo, ¿ [ 0m31s354ms ] cómo [ 0m31s634ms ] ha [ 0m31s664ms ] estado [ 0m31s984ms ] tu [ 0m32s134ms ] día? [ 0m32s424ms ]
This inspired me to try again, this time including a JSON schema [ https://substack.com/redirect/a6ffa195-347a-4f9c-bf5c-605b7e84a038?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (using LLM's custom schema DSL):
llm -m gemini-2.5-pro-exp-03-25 'transcribe' \
-a https://static.simonwillison.net/static/2025/russian-pelican-in-spanish.mp3 \
--schema-multi 'timestamp str: mm:ss,text, language: two letter code'
I got an excellent response from that:
{
"items": [
{
"language": "en",
"text": "I need you to pretend to be a California brown pelican with a very thick Russian accent, but you talk to me exclusively in Spanish.",
"timestamp": "00:00"
},
{
"language": "es",
"text": "Oye, camarada. Aquí está tu pelícano californiano con acento ruso.",
"timestamp": "00:08"
},
{
"language": "es",
"text": "¿Qué tal, Tovarish? ¿Listo para charlar en español?",
"timestamp": "00:13"
},
{
"language": "en",
"text": "How's your day today?",
"timestamp": "00:19"
},
{
"language": "es",
"text": "Mi día ha sido volando sobre las olas, buscando peces y disfrutando del sol californiano.",
"timestamp": "00:22"
},
{
"language": "es",
"text": "¿Y tú, amigo, cómo ha estado tu día?",
"timestamp": "00:30"
}
]
}
I confirmed that the timestamps match the audio. This is fantastic.
Let's try that against a ten minute snippet of a podcast episode [ https://substack.com/redirect/90e86c5a-3551-4eeb-a328-c090b96d8398?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I was on:
llm -m gemini-2.5-pro-exp-03-25 \
'transcribe, first speaker is Christopher, second is Simon' \
-a ten-minutes-of-podcast.mp3 \
--schema-multi 'timestamp str: mm:ss, text, speaker_name'
Useful LLM trick: you can use llm logs -c --data to get just the JSON data from the most recent prompt response, so I ran this:
llm logs -c --data | jq
Here's the full output JSON [ https://substack.com/redirect/911b0b49-8790-4e3f-9171-6e02c3b385ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which starts and ends like this:
{
"items": [
{
"speaker_name": "Christopher",
"text": "on its own and and it has this sort of like a it's like a you know old tree in the forest, you know, kind of thing that you've built, so.",
"timestamp": "00:00"
},
{
"speaker_name": "Simon",
"text": "There's also like I feel like with online writing, never ever like stick something online just expect people to find it. You have to So one of the great things about having a blog is I can be in a conversation about something and somebody ask a question, I can say, oh, I wrote about that two and a half years ago and give people a link.",
"timestamp": "00:06"
},

{
"speaker_name": "Simon",
"text": "So on that basis, Chat and I can't remember if the free version of Chat GPT has code interpreter.",
"timestamp": "09:45"
},
{
"speaker_name": "Simon",
"text": "I hope I think it does.",
"timestamp": "09:50"
},
{
"speaker_name": "Christopher",
"text": "Okay. So this is like the basic paid one, maybe the $20 month because I know there's like a $200 one that's a little steep for like a basic",
"timestamp": "09:51"
}
]
}
A spot check of the timestamps showed them in the right place. Gemini 2.5 supports long context prompts so it's possible this works well for much longer audio files - it would be interesting to dig deeper and try that out.
Bounding boxes
One of my favourite features of previous Gemini models is their support for bounding boxes: you can prompt them to return boxes around objects in images.
I built a separate tool for experimenting with this feature in August last year, which I described in Building a tool showing how Gemini Pro can return bounding boxes for objects in images [ https://substack.com/redirect/938974d0-66cf-467f-a227-83baa81ea8fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I've now upgraded that tool to add support the new model.
You can access it at tools.simonwillison.net/gemini-bbox [ https://substack.com/redirect/855b3be3-a9cc-42d5-8623-37f574465890?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - you'll need to provide your own Gemini API key which is sent directly to their API from your browser (it won't be logged by an intermediary).
I tried it out on a challenging photograph [ https://substack.com/redirect/e64f9361-b0ad-4bf1-8138-a2d85027f1da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of some pelicans... and it worked extremely well:
My prompt was:
Return bounding boxes around pelicans as JSON arrays [ymin, xmin, ymax, xmax]
The Gemini models are all trained to return bounding boxes scaled between 0 and 100. My tool knows how to convert those back to the same dimensions as the input image.
Here's what the visualized result looked like:
It got almost all of them! I like how it didn't draw a box around the one egret that had made it into the photo.
More characteristics of the model
Here's the official model listing [ https://substack.com/redirect/db26f024-1522-4fbf-ad17-dfdb722c6fe8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the Gemini docs. Key details:
Input token limit: 1,000,000
Output token limit: 64,000 - this is a hugeupgrade, all of the other listed models have 8,192 for this (correction: Gemini 2.0 Flash Thinking [ https://substack.com/redirect/c7595418-d356-4540-b05f-77cfdcb2c422?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] also had a 64,000 output length)
Knowledge cut-off: January 2025 - an improvement on Gemini 2.0's August 2024
Gemini 2.5 Pro is a very strong new model
I've hardly scratched the surface when it comes to trying out Gemini 2.5 Pro so far. How's its creative writing? Factual knowledge about the world? Can it write great code in Python, JavaScript, Rust and more?
The Gemini family of models have capabilities that set them apart from other models:
Long context length - Gemini 2.5 Pro supports up to 1 million tokens
Audio input - something which few other models support, certainly not at this length and with this level of timestamp accuracy
Accurate bounding box detection for image inputs
My experiments so far with these capabilities indicate that Gemini 2.5 Pro really is a very strong new model. I'm looking forward to exploring more of what it can do.
Update: it's very good at code
I spent this evening trying it out for coding tasks, and it's very, very impressive. I'm seeing results for Python that feel comparable to my previous favourite Claude 3.7 Sonnet, and appear to be benefitting from Gemini 2.5 Pro's default reasoning mode and long context.
I've been wanting to add a new content type of "notes" to my blog for quite a while now, but I was put off by the anticipated tedium of all of the different places in the codebase that would need to be updated.
That feature is now live. Here are my notes [ https://substack.com/redirect/9047e14d-1a33-4134-9e66-86e96cb0a066?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on creating that notes feature using Gemini 2.5 Pro. It crunched through my entire codebase and figured out all of the places I needed to change - 18 files in total, as you can see in the resulting PR [ https://substack.com/redirect/62624bc7-6b24-48c0-a567-0486081e8639?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The whole project took about 45 minutes from start to finish - averaging less than three minutes per file I had to modify.
I've thrown a whole bunch of other coding challenges at it, and the bottleneck on evaluating them has become my own mental capacity to review the resulting code!
Here's another, more complex example. This hasn't resulted in actual running code yet but it took a big bite out of an architectural design problem I've been stewing on for a very long time.
My LLM project [ https://substack.com/redirect/4d6e0a59-40d5-4d1d-a7f5-2e5db0b6f366?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] needs support for tools - a way to teach different LLMs how to request tool execution, then have those tools (implemented in Python) run and return their results back to the models.
Designing this is really hard, because I need to create an abstraction that works across multiple different model providers, each powered by a different plugin.
Could Gemini 2.5 Pro help unblock me by proposing an architectural approach that might work?
I started by combining the Python and Markdown files for my sqlite-utils [ https://substack.com/redirect/c76c29a2-6520-42ec-817c-f91270f515af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], llm [ https://substack.com/redirect/356d360d-f406-41fc-8770-047bfb590d67?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], llm-gemini [ https://substack.com/redirect/0e7419e0-2856-4cc2-b6d0-a1d774bcc814?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and llm-anthropic [ https://substack.com/redirect/db256112-409f-4c69-ba73-c78ce8350c63?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repositories into one big document:
files-to-prompt sqlite-utils llm llm-gemini llm-anthropic -e md -e py -c
Piping it through ttok [ https://substack.com/redirect/c4bb3cac-c464-4520-afc1-0f7c5d2620d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] showed that to be 316,098 tokens (using the OpenAI tokenizer, but the Gemini tokenizer is likely a similar number).
Then I fed that all into Gemini 2.5 Pro with the following prompt:
Provide a detailed design proposal for adding tool calling support to LLM
Different model plugins will have different ways of executing tools, but LLM itself should provide both a Python and a CLI abstraction over these differences.
Tool calling involves passing tool definitions to a model, the model then replies with tools it would like executed, the harness code then executes those and passes the result back to the model and continues in a loop until the model stops requesting tools. This should happen as part of the existing llm.Conversation mechanism.
At the Python layer tools should be provided as Python functions that use type hints, which can then be converted into JSON schema using Pydantic - similar to how the existing schema= mechanism works.
For the CLI option tools will be provided as an option passed to the command, similar to how the sqlite-utils convert CLI mechanism works.'
I've been thinking about this problem for over a year now. Gemini 2.5 Pro's response [ https://substack.com/redirect/68f3f22d-28db-4867-981f-54ee85bd23e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] isn't exactly what I'm going to do, but it did include a flurry of genuinely useful suggestions to help me craft my final approach.
I hadn't thought about the need for asyncio support for tool functions at all, so this idea from Gemini 2.5 Pro was very welcome:
The AsyncConversation.prompt method will mirror the synchronous API, accepting the tools parameter and handling the tool calling loop using async/await for tool execution if the tool functions themselves are async. If tool functions are synchronous, they will be run in a thread pool executor via asyncio.to_thread.
Watching Gemini crunch through some of the more complex problems I've been dragging my heels on reminded me of something Harper Reed wrote about his workflow with LLMs for code [ https://substack.com/redirect/e6e313e9-a990-4040-bdb1-66107fd198e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
My hack to-do list is empty because I built everything. I keep thinking of new things and knocking them out while watching a movie or something.
I've been stressing quite a bit about my backlog of incomplete projects recently. I don't think Gemini 2.5 Pro is quite going to work through all of them while I'm watching TV, but it does feel like it's going to help make a significant dent in them.
Quote 2025-03-25
Today we’re excited to launch ARC-AGI-2 to challenge the new frontier. ARC-AGI-2 is even harder for AI (in particular, AI reasoning systems), while maintaining the same relative ease for humans. Pure LLMs score 0% on ARC-AGI-2, and public AI reasoning systems achieve only single-digit percentage scores. In contrast, every task in ARC-AGI-2 has been solved by at least 2 humans in under 2 attempts. [...]
All other AI benchmarks focus on superhuman capabilities or specialized knowledge by testing "PhD++" skills. ARC-AGI is the only benchmark that takes the opposite design choice – by focusing on tasks that are relatively easy for humans, yet hard, or impossible, for AI, we shine a spotlight on capability gaps that do not spontaneously emerge from "scaling up".
Greg Kamradt [ https://substack.com/redirect/66c71fa0-a0e9-4138-a132-c055c49d7153?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-03-25 Introducing 4o Image Generation [ https://substack.com/redirect/cdbe2523-b3ae-45c8-a60d-22a60ddb9f4b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
When OpenAI first announced GPT-4o back in May 2024 [ https://substack.com/redirect/662c4be1-cfa4-4b9e-bc5a-ec39cea7b59d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] one of the most exciting features was true multi-modality in that it could both input and output audio and images. The "o" stood for "omni", and the image output examples in that launch post [ https://substack.com/redirect/a7f1cf5a-62b3-4fae-9217-8d0f11a22325?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] looked really impressive.
It's taken them over ten months (and Gemini beat them to it [ https://substack.com/redirect/533b3215-83a3-460c-b01b-3f32ca8ab422?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) but today they're finally making those image generation abilities available, live right now in ChatGPT for paying customers.
My test prompt for any model that can manipulate incoming images is "Turn this into a selfie with a bear", because you should never take a selfie with a bear! I fed ChatGPT this selfie [ https://substack.com/redirect/e97dfb9e-81c1-4ad0-a341-c00a4b096d1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and got back this result:
That's pretty great! It mangled the text on my T-Shirt (which says "LAWRENCE.COM" in a creative font) and added a second visible AirPod. It's very clearly me though, and that's definitely a bear.
There are plenty more examples in OpenAI's launch post [ https://substack.com/redirect/cdbe2523-b3ae-45c8-a60d-22a60ddb9f4b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but as usual the most interesting details are tucked away in the updates to the system card [ https://substack.com/redirect/fc3ba4d4-7aed-45ec-8242-ec5c4b92f73d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. There's lots in there about their approach to safety and bias, including a section on "Ahistorical and Unrealistic Bias" which feels inspired by Gemini's embarrassing early missteps [ https://substack.com/redirect/9479f2cb-8f00-42fe-8c74-da4487830165?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
One section that stood out to me is their approach to images of public figures. The new policy is much more permissive than for DALL-E - highlights mine:
4o image generation is capable, in many instances, of generating a depiction of a public figure based solely on a text prompt.
At launch, we are not blocking the capability to generate adult public figures but are instead implementing the same safeguards that we have implemented for editing images of photorealistic uploads of people. For instance, this includes seeking to block the generation of photorealistic images of public figures who are minors and of material that violates our policies related to violence, hateful imagery, instructions for illicit activities, erotic content, and other areas. Public figures who wish for their depiction not to be generated can opt out.
This approach is more fine-grained than the way we dealt with public figures in our DALL·E series of models, where we used technical mitigations intended to prevent any images of a public figure from being generated. This change opens the possibility of helpful and beneficial uses in areas like educational, historical, satirical and political speech. After launch, we will continue to monitor usage of this capability, evaluating our policies, and will adjust them if needed.
Given that "public figures who wish for their depiction not to be generated can opt out" I wonder if we'll see a stampede of public figures to do exactly that!
Update: There's significant confusion right now over this new feature because it is being rolled out gradually but older ChatGPT can still generate images using DALL-E instead... and there is no visual indication in the ChatGPT UI explaining which image generation method it used!
OpenAI made the same mistake last year when they announced ChatGPT advanced voice mode [ https://substack.com/redirect/35807bce-cb06-49aa-bbe2-e2f7a7e0d362?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]but failed to clarify that ChatGPT was still running the previous, less impressive voice implementation.
Update 2: Images created with DALL-E through the ChatGPT web interface now show a note with a warning:
Quote 2025-03-26
We estimate the supply-side value of widely-used OSS is $4.15 billion, but that the demand-side value is much larger at $8.8 trillion. We find that firms would need to spend 3.5 times more on software than they currently do if OSS did not exist.
Manuel Hoffmann, Frank Nagle, Yanuo Zhou [ https://substack.com/redirect/dce300d6-c9e7-4560-90ae-9141c0d379cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVGs1TWprMk1qUXNJbWxoZENJNk1UYzBNekF4TURZMU55d2laWGh3SWpveE56YzBOVFEyTmpVM0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuWmJkYkFKM0RVcUgzbVlUb3lfWXpFcms4WkhKVUY3aVpzNkFMQW92U3B2dyIsInAiOjE1OTkyOTYyNCwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQzMDEwNjU3LCJleHAiOjE3NDU2MDI2NTcsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.9hUvfXxzMueVKf9qyTnIX_ImiglVTxDGMxxZrO66nSY?
