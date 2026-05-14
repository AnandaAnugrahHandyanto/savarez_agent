# Comma v0.1 1T and 2T - 7B LLMs trained on openly licensed text

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-06-11T01:41:07.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/comma-v01-1t-and-2t-7b-llms-trained

In this newsletter:
Comma v0.1 1T and 2T - 7B LLMs trained on openly licensed text
Plus 6 links and 3 quotations and 1 note
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Comma v0.1 1T and 2T - 7B LLMs trained on openly licensed text [ https://substack.com/redirect/094384bc-9b98-44f1-9e5d-dbf859a17b35?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-06-07
It's been a long time coming, but we finally have some promising LLMs to try out which are trained entirely on openly licensed text!
EleutherAI released the Pile [ https://substack.com/redirect/9267a678-1663-466f-9b02-a2b3c119f4f7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] four and a half years ago: "an 800GB dataset of diverse text for language modeling". It's been used as the basis for many LLMs since then, but much of the data in it came from Common Crawl [ https://substack.com/redirect/f4babcd9-b656-4ee9-8f8a-87127116eea4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a crawl of the public web which mostly ignored the licenses of the data it was collecting.
The Common Pile v0.1 [ https://substack.com/redirect/6974b17d-21e0-45f2-871f-ddb14b3f6fec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is EleutherAI's successor to the original Pile, in collaboration with a large group of other organizations with whom they have been "meticulously curating a 8 TB corpus of openly licensed and public domain text for training large language models".
The dataset is exciting, but on top of that they've released two new LLMs that have been trained on it: Comma v0.1 1T and 2T, both with 7 billion parameters, the first trained on 1 trillion tokens and the second on 2 trillion tokens.
These are available on Hugging Face as common-pile/comma-v0.1-1t [ https://substack.com/redirect/0662f53d-48d1-4b08-9b80-d08ace574ab2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and common-pile/comma-v0.1-2t [ https://substack.com/redirect/b00ba69c-8699-41a3-bfd7-faa715712b1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
EleutherAI claim that these new models perform "comparably to leading models trained in the same regime on unlicensed data". I decided to try them out myself.
The models are currently only available as .safetensors files, which I've found difficult to run on macOS in the past. I decided to see if I could convert them to MLX [ https://substack.com/redirect/405da913-a8b1-4d6f-94a5-a84c87214268?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] format which I know how to run on my Mac.
MLX is still a very new format, but Claude 4 Sonnet has a training cutoff date of March 2025 so I crossed my fingers and hoped it would be able to help me out. It did exactly that! [ https://substack.com/redirect/84c54d8a-ba99-4e5b-854d-453e409d0063?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I ran the following command to convert the 2T model to run using MLX:
uv run --python 3.12 \
--with mlx-lm \
python -m mlx_lm convert \
--hf-path common-pile/comma-v0.1-2t \
--mlx-path ./comma-v0.1-2t-mlx
I uploaded the converted model to Hugging Face as simonw/comma-v0.1-2t-mlx [ https://substack.com/redirect/78c2d4ee-be2c-4388-b7f6-e5d53adf5059?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Now that it's on the Hub here's how to try it out (using uv run):
uv run --python 3.12 \
--with mlx-lm \
mlx_lm.generate \
--model simonw/comma-v0.1-2t-mlx \
--prompt 'Facts about pelicans:'
The first time you run this it will download 13GB of files to ~/.cache/huggingface/hub/models--simonw--comma-v0.1-2t-mlx.
Here's what I got back:
1. They are the largest of the water birds. 2. They are found in all parts of the world. 3. They are very good swimmers. 4. They are very good divers. 5. They are very good flyers. 6. They are very good hunters. 7. They are very good eaters. 8. They are very good parents. 9. They are very good friends. 10.
The big limitation of this model right now is that it's a raw base model - it hasn't been instruction-tuned or set up for chat.
This means you have to prefix-prompt it, like in the GPT-3 days. You need to give it a sentence for it to complete.
This makes it a lot harder to evaluate than the instruction-tuned models that I've become used to over the past few years!
I'm hoping someone releases a chat-tuned version of this model soon. The challenge there will be keeping to the openly licensed training data, since most of the fine-tuning datasets out there for this are themselves derived from models that were trained on unlicensed data.
Sadly it didn't do too well on my pelican on a bicycle [ https://substack.com/redirect/39473280-45ea-4662-ab9b-90729f9ea7b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] benchmark:
uv run --python 3.12 \
--with mlx-lm \
mlx_lm.generate \
--model simonw/comma-v0.1-2t-mlx \
--prompt 'An SVG of a pelican riding a bicycle: ...
Quote 2025-06-07
For [Natasha] Lyonne, the draw of AI isn’t speed or scale — it’s independence. “I’m not trying to run a tech company,” she told me. “It’s more that I’m a filmmaker who doesn’t want the tech people deciding the future of the medium.” She imagines a future in which indie filmmakers can use AI tools to reclaim authorship from studios and avoid the compromises that come with chasing funding in a broken system.
“We need some sort of Dogme 95 for the AI era,” Lyonne said, referring to the stripped-down 1990s filmmaking movement started by Lars von Trier and Thomas Vinterberg, which sought to liberate cinema from an overreliance on technology. “If we could just wrangle this artist-first idea before it becomes industry standard to not do it that way, that’s something I would be interested in working on. Almost like we are not going to go quietly into the night.”
Lila Shapiro [ https://substack.com/redirect/e98041cc-fbda-46b7-bdd2-db44ceeedc92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-06-08 Qwen3 Embedding [ https://substack.com/redirect/a3e9e847-5e69-47f7-ad05-96dd1d6cfbd0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New family of embedding models from Qwen, in three sizes: 0.6B, 4B, 8B - and two categories: Text Embedding and Text Reranking.
The full collection can be browsed [ https://substack.com/redirect/c5579915-03ec-4eb6-839f-cf470b28018b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hugging Face. The smallest available model is the 0.6B Q8 one, which is available as a 639MB GGUF. I tried it out using my llm-sentence-transformers [ https://substack.com/redirect/f30463b5-0a23-4083-aad1-cb68d953d44a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin like this:
llm install llm-sentence-transformers
llm sentence-transformers register Qwen/Qwen3-Embedding-0.6B
llm embed -m sentence-transformers/Qwen/Qwen3-Embedding-0.6B -c hi | jq length
This output 1024, confirming that Qwen3 0.6B produces 1024 length embedding vectors.
These new models are the highest scoring open-weight models on the well regarded MTEB leaderboard [ https://substack.com/redirect/f4f5e97f-ef88-4622-ad43-7499cd750464?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - they're licensed Apache 2.0.
You can also try them out in your web browser, thanks to a Transformers.js [ https://substack.com/redirect/6577d84a-09f2-4247-a086-a83e28a75990?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] port of the models. I loaded this page in Chrome [ https://substack.com/redirect/e543633a-ea6e-4653-ab6c-5200c8779900?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (source code here [ https://substack.com/redirect/3b52d57a-7910-4562-b262-d4dccf403eec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and it fetched 560MB of model files and gave me an interactive interface for visualizing clusters of embeddings like this:
Quote 2025-06-09
The process of learning and experimenting with LLM-derived technology has been an exercise in humility. In general I love learning new things when the art of programming changes […] But LLMs, and more specifically Agents, affect the process of writing programs in a new and confusing way. Absolutely every fundamental assumption about how I work has to be questioned, and it ripples through all the experience I have accumulated. There are days when it feels like I would be better off if I did not know anything about programming and started from scratch. And it is still changing.
David Crawshaw [ https://substack.com/redirect/9f01a369-5d1e-41c9-ad17-b325221e57ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-06-09 OpenAI hits $10 billion in annual recurring revenue fueled by ChatGPT growth [ https://substack.com/redirect/c162b644-bed0-45f1-93ae-2c5860dce178?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Noteworthy because OpenAI revenue is a useful indicator of the direction of the generative AI industry in general, and frequently comes up in conversations about the sustainability of the current bubble.
OpenAI has hit $10 billion in annual recurring revenue less than three years after launching its popular ChatGPT chatbot.
The figure includes sales from the company’s consumer products, ChatGPT business products and its application programming interface, or API. It excludes licensing revenue from Microsoft and large one-time deals, according to an OpenAI spokesperson.
For all of last year, OpenAI was around $5.5 billion in ARR. [...]
So these new numbers represent nearly double the ARR figures for last year.
Link 2025-06-09 WWDC: Apple supercharges its tools and technologies for developers [ https://substack.com/redirect/d15cdaee-498b-466a-acd8-b02dc5c25007?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here's the Apple press release for today's WWDC announcements. Two things that stood out to me:
Foundation Models Framework
With the Foundation Models framework, developers will be able to build on Apple Intelligence to bring users new experiences that are intelligent, available when they’re offline, and that protect their privacy, using AI inference that is free of cost. The framework has native support for Swift, so developers can easily access the Apple Intelligence model with as few as three lines of code.
Here's new documentation on Generating content and performing tasks with Foundation Models [ https://substack.com/redirect/0e471aec-b673-499b-aa34-fe53efdd68e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - the Swift code looks like this:
let session = LanguageModelSession(
instructions: "Reply with step by step instructions"
)
let prompt = "Rum old fashioned cocktail"
let response = try await session.respond(
to: prompt,
options: GenerationOptions(temperature: 2.0)
)
There's also a 23 minute Meet the Foundation Models framework [ https://substack.com/redirect/531eecbb-ef49-4c4d-9f24-8b7b074755d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] video from the conference, which clarifies that this is a 3 billion parameter model with 2 bit quantization. The model is trained for both tool-calling and structured output, which they call "guided generation" and describe as taking advantage of constrained decoding.
I'm also very excited about this:
Containerization Framework
The Containerization framework enables developers to create, download, or run Linux container images directly on Mac. It’s built on an open-source framework optimized for Apple silicon and provides secure isolation between container images.
I continue to seek the ideal sandboxing solution for running untrusted code - both from other humans and written for me by LLMs - on my own machines. This looks like it could be a really great option for that going forward.
It looks like apple/container [ https://substack.com/redirect/b13f5803-700e-4624-ad87-31056c0097e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on GitHub is part of this new feature. From the technical overview [ https://substack.com/redirect/d2b11afb-e269-4a89-ba63-cc4a0ef19f67?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
On macOS, the typical way to run Linux containers is to launch a Linux virtual machine (VM) that hosts all of your containers.
container runs containers differently. Using the open source Containerization [ https://substack.com/redirect/920b4ce5-04c5-4fd2-891c-9ecdc4910045?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]package, it runs a lightweight VM for each container that you create. [...]
Since container consumes and produces standard OCI images, you can easily build with and run images produced by other container applications, and the images that you build will run everywhere.
Link 2025-06-10 Magistral — the first reasoning model by Mistral AI [ https://substack.com/redirect/e638e8ba-2a17-4c06-a84a-6ea2cd9b253f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Mistral's first reasoning model is out today, in two sizes. There's a 24B Apache 2 licensed open-weights model called Magistral Small (actually Magistral-Small-2506), and a larger API-only model called Magistral Medium.
Magistral Small is available as mistralai/Magistral-Small-2506 [ https://substack.com/redirect/8aedbac6-9086-464d-8eab-7388e743932c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hugging Face. From that model card:
Context Window: A 128k context window, but performance might degrade past 40k. Hence we recommend setting the maximum model length to 40k.
Mistral also released an official GGUF version, Magistral-Small-2506_gguf [ https://substack.com/redirect/1e90b445-adc1-4346-867e-da2cc55abe96?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which I ran successfully using Ollama like this:
ollama pull hf.co/mistralai/Magistral-Small-2506_gguf:Q8_0
That fetched a 25GB file. I ran prompts using a chat session with llm-ollama [ https://substack.com/redirect/0381a5c2-04c5-42b5-b055-e37dbf1c3b3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
llm chat -m hf.co/mistralai/Magistral-Small-2506_gguf:Q8_0
Here's what I got for "Generate an SVG of a pelican riding a bicycle" (transcript here [ https://substack.com/redirect/07f809f5-a82d-49b8-add8-2a4e1c68ae77?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
It's disappointing that the GGUF doesn't support function calling yet - hopefully a community variant can add that, it's one of the best ways I know of to unlock the potential of these reasoning models.
I just noticed that Ollama have their own Magistral model [ https://substack.com/redirect/c4e06789-6fd7-4822-89f6-fd4c9e292269?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] too, which can be accessed using:
ollama pull magistral:latest
That gets you a 14GB q4_K_M quantization - other options can be found in the full list of Ollama magistral tags [ https://substack.com/redirect/79833c05-1b0e-4d1a-8097-f64367a79c4a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
One thing that caught my eye in the Magistral announcement:
Legal, finance, healthcare, and government professionals get traceable reasoning that meets compliance requirements. Every conclusion can be traced back through its logical steps, providing auditability for high-stakes environments with domain-specialized AI.
I guess this means the reasoning traces are fully visible and not redacted in any way - interesting to see Mistral trying to turn that into a feature that's attractive to the business clients they are most interested in appealing to.
Also from that announcement:
Our early tests indicated that Magistral is an excellent creative companion. We highly recommend it for creative writing and storytelling, with the model capable of producing coherent or — if needed — delightfully eccentric copy.
I haven't seen a reasoning model promoted for creative writing in this way before.
You can try out Magistral Medium by selecting the new "Thinking" option in Mistral's Le Chat [ https://substack.com/redirect/20a1bfc5-666f-4cfd-b57c-ee2a61e3c8d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
They have options for "Pure Thinking" and a separate option for "10x speed", which runs Magistral Medium at 10x the speed using Cerebras [ https://substack.com/redirect/565bf250-9cb0-4a85-bb51-29c9025337ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The new models are also available through the Mistral API [ https://substack.com/redirect/139f172f-479c-4f69-9747-803e328c6aa5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can access them by installing llm-mistral [ https://substack.com/redirect/db854795-6722-470a-b8f3-1c1a1300224a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and running llm mistral refresh to refresh the list of available models, then:
llm -m mistral/magistral-medium-latest \
'Generate an SVG of a pelican riding a bicycle'
Here's that transcript [ https://substack.com/redirect/708d291f-6746-4623-966c-fceb1fb5637e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. At 13 input and 1,236 output tokens that cost me 0.62 cents [ https://substack.com/redirect/599963b6-f19a-4364-b406-005657e41fb4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - just over half a cent.
Note 2025-06-10 [ https://substack.com/redirect/1b96e5fc-3f18-4a64-b067-0307744d7fad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
OpenAI just dropped the price of their o3 model by 80% - from $10/million input tokens and $40/million output tokens to just $2/million and $8/million for the very same model. This is in advance of the release of o3-pro which apparently is coming later today [ https://substack.com/redirect/6a4eca80-4ff4-4f1a-8cfa-a80d083c8a49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (update: here it is [ https://substack.com/redirect/71e3f66e-07fc-428c-ba4b-31e1dc489e24?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
This is a pretty huge shake-up in LLM pricing. o3 is now priced the same as GPT 4.1, and slightly less than GPT-4o ($2.50/$10). It’s also less than Anthropic’s Claude Sonnet 4 ($3/$15) and Opus 4 ($15/$75) and sits in between Google’s Gemini 2.5 Pro for >200,00 tokens ($2.50/$15) and 2.5 Pro for <200,000 ($1.25/$10).
I’ve updated my llm-prices.com [ https://substack.com/redirect/54561689-dc13-43b3-9cd3-326ff37ffc67?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] pricing calculator with the new rate.
How have they dropped the price so much? OpenAI's Adam Groth credits ongoing optimization work [ https://substack.com/redirect/5339ff47-9f0e-431b-a7cd-554662a1ee00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
thanks to the engineers optimizing inferencing.
Link 2025-06-10 o3-pro [ https://substack.com/redirect/62881487-c2d5-4692-a60a-0133b9cafbb9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI released o3-pro today, which they describe as a "version of o3 with more compute for better responses".
It's only available via the newer Responses API. I've added it to my llm-openai-plugin [ https://substack.com/redirect/08b86455-b901-461a-8b6c-93fdf0678858?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin which uses that new API, so you can try it out like this:
llm install -U llm-openai-plugin
llm -m openai/o3-pro "Generate an SVG of a pelican riding a bicycle"
It's slow - generating this pelican [ https://substack.com/redirect/a9c33318-ca76-491e-8da8-d34d28ae338b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] took 124 seconds! OpenAI suggest using their background mode [ https://substack.com/redirect/83583330-560a-43fb-99cb-8bae23a45383?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for o3 prompts, which I haven't tried myself yet.
o3-pro is priced at $20/million input tokens and $80/million output tokens - 10x the price of regular o3 after its 80% price drop [ https://substack.com/redirect/1b96e5fc-3f18-4a64-b067-0307744d7fad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this morning.
Ben Hylak had early access and published his notes so far in God is hungry for Context: First thoughts on o3 pro [ https://substack.com/redirect/a35135b0-07d8-4369-89a1-9ed26f002712?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It sounds like this model needs to be applied very thoughtfully. It comparison to o3:
It's smarter. much smarter.
But in order to see that, you need to give it a lot more context. and I'm running out of context. [...]
My co-founder Alexis and I took the the time to assemble a history of all of our past planning meetings at Raindrop, all of our goals, even record voice memos: and then asked o3-pro to come up with a plan.
We were blown away; it spit out the exact kind of concrete plan and analysis I've always wanted an LLM to create --- complete with target metrics, timelines, what to prioritize, and strict instructions on what to absolutely cut.
The plan o3 gave us was plausible, reasonable; but the plan o3 Pro gave us was specific and rooted enough that it actually changed how we are thinking about our future.
This is hard to capture in an eval.
It sounds to me like o3-pro works best when combined with tools. I don't have tool support in llm-openai-plugin yet, here's the relevant issue [ https://substack.com/redirect/5d58ac8e-456f-4528-be4c-a72230148cfa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-06-10 AI-assisted coding for teams that can't get away with vibes [ https://substack.com/redirect/2c334f0f-917f-49dd-9f8a-5d43c4b9fb8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This excellent piece by Atharva Raykar offers a bunch of astute observations on AI-assisted development that I haven't seen written down elsewhere.
Building with AI is fast. The gains in velocity are important, because when harnessed correctly, it allows teams to tighten feedback loops with users faster and make better products.
Yet, AI tools are tricky to use. Hold it wrong, and you can generate underwhelming results, worse still, slow down your velocity by drowning your project in slop and technical debt.
Atharva notes that AI is a multiplier: the more expertise you have in software engineering, the better the results you can get from LLMs. Furthermore, what helps the human helps the AI.
This means food test coverage, automatic linting, continuous integration and deployment, good documentation practices and "clearly defined features, broken down into multiple small story cards".
If a team has all of this stuff in place, AI coding assistants will be able to operate more reliably and collaborate more effectively with their human overseers.
I enjoyed his closing thoughts about how heavier reliance on LLMs change our craft:
Firstly, It’s less valuable to spend too much time looking for and building sophisticated abstractions. DRY is useful for ensuring patterns in the code don’t go out of sync, but there are costs to implementing and maintaining an abstraction to handle changing requirements. LLMs make some repetition palatable and allow you to wait a bit more and avoid premature abstraction.
Redoing work is now extremely cheap. Code in the small is less important than structural patterns and organisation of the code in the large. You can also build lots of prototypes to test an idea out. For this, vibe-coding is great, as long as the prototype is thrown away and rewritten properly later. [...]
Tests are non-negotiable, and AI removes all excuses to not write them because of how fast they can belt them out. But always review the assertions!
Quote 2025-06-10
(People are often curious about how much energy a ChatGPT query uses; the average query uses about 0.34 watt-hours, about what an oven would use in a little over one second, or a high-efficiency lightbulb would use in a couple of minutes. It also uses about 0.000085 gallons of water; roughly one fifteenth of a teaspoon.)
Sam Altman [ https://substack.com/redirect/c4fee0fd-8782-4f3f-b086-15d18a68b447?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOalUyTnpVd05USXNJbWxoZENJNk1UYzBPVFl3TmpBNE1Dd2laWGh3SWpveE56Z3hNVFF5TURnd0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuSmhoQkkzMFJJUlhKUHJJOWpmQXcxT2VjZExFY1pPcHJLYmMyRmc5dlY3YyIsInAiOjE2NTY3NTA1MiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQ5NjA2MDgwLCJleHAiOjE3NTIxOTgwODAsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.23zKYYknBgt_9ZpBj84oSaaVNXkYQJ2e4uczjOCq_uo?
