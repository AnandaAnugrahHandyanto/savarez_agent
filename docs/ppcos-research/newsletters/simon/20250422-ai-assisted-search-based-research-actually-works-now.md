# AI assisted search-based research actually works now

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-04-22T15:32:19.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/ai-assisted-search-based-research

In this newsletter:
AI assisted search-based research actually works now
Maybe Meta's Llama claims to be open source because of the EU AI act
Plus 7 links and 1 quotation
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
AI assisted search-based research actually works now [ https://substack.com/redirect/e429fa9a-62ed-400d-b364-9c16bc16f2e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-04-21
For the past two and a half years the feature I've most wanted from LLMs is the ability to take on search-based research tasks on my behalf. We saw the first glimpses of this back in early 2023, with Perplexity (first launched December 2022 [ https://substack.com/redirect/9f5916b5-c75c-4c16-a114-e11bbfa6523f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], first prompt leak in January 2023 [ https://substack.com/redirect/89f8df5f-224b-4e67-85db-545ad1dab8c4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and then the GPT-4 powered Microsoft Bing (which launched/cratered spectacularly in February 2023 [ https://substack.com/redirect/a9bd6516-f51f-4a82-8ce0-4e9a791d5551?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). Since then a whole bunch of people have taken a swing at this problem, most notably Google Gemini [ https://substack.com/redirect/d76d7294-076d-40fb-b6cf-bda31baef715?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and ChatGPT Search [ https://substack.com/redirect/4db3a1e7-9c6e-4215-82dc-8f45415ff4a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Those 2023-era versions were promising but very disappointing. They had a strong tendency to hallucinate details that weren't present in the search results, to the point that you couldn't trust anything they told you.
In this first half of 2025 I think these systems have finally crossed the line into being genuinely useful.
Deep Research, from three different vendors [ https://substack.com/redirect/11c9c5f8-4960-4490-a4dd-7c10daaf4616?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
o3 and o4-mini are really good at search [ https://substack.com/redirect/b564f805-d896-4e94-b9c4-0c8f892abe71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Google and Anthropic need to catch up [ https://substack.com/redirect/50832de1-dd47-4b69-8337-63c492d99ae5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Lazily porting code to a new library version via search [ https://substack.com/redirect/c6955444-6618-4833-835a-e24f037bb51e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
How does the economic model for the Web work now? [ https://substack.com/redirect/9b3fe51e-635e-4cda-8108-96d326bc6c0e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Deep Research, from three different vendors
First came the Deep Research implementations - Google Gemini [ https://substack.com/redirect/b0d468da-5470-4473-9cad-7509e34f7490?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and then OpenAI [ https://substack.com/redirect/4a0e8f1e-c09c-480c-b40c-9469d12d05d5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and then Perplexity [ https://substack.com/redirect/bead21d1-be7c-4cb7-a72f-65d17887707b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] launched products with that name and they were all impressive: they could take a query, then churn away for several minutes assembling a lengthy report with dozens (sometimes hundreds) of citations. Gemini's version had a huge upgrade a few weeks ago when they switched it to using Gemini 2.5 Pro [ https://substack.com/redirect/1a66ffdc-c497-44f0-a81d-cdb2048ef62a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and I've had some outstanding results from it since then.
Waiting a few minutes for a 10+ page report isn't my ideal workflow for this kind of tool. I'm impatient, I want answers faster than that!
o3 and o4-mini are really good at search
Last week, OpenAI released search-enabled o3 and o4-mini [ https://substack.com/redirect/a2853f11-4bce-425a-805d-9897902fd563?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] through ChatGPT [ https://substack.com/redirect/12245b3f-aded-42f5-88b0-39e7c510cd9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. On the surface these look like the same idea as we've seen already: LLMs that have the option to call a search tool as part of replying to a prompt.
But there's one very significant difference: these models can run searches as part of the chain-of-thought reasoning process they use before producing their final answer.
This turns out to be a huge deal. I've been throwing all kinds of questions at ChatGPT (in o3 or o4-mini mode) and getting back genuinely useful answers grounded in search results. I haven't spotted a hallucination yet, and unlike prior systems I rarely find myself shouting "no, don't search for that!" at the screen when I see what they're doing.
Here are four recent example transcripts:
Get me specs including VRAM for RTX 5090 and RTX PRO 6000 - plus release dates and prices [ https://substack.com/redirect/d9ceb5a3-b7cc-4761-b32d-152b455edc26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Find me a website tool that lets me paste a URL in and it gives me a word count and an estimated reading time [ https://substack.com/redirect/e8e87a1f-e04c-49bf-bc0f-aa477a274a29?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Figure out what search engine ChatGPT is using for o3 and o4-mini [ https://substack.com/redirect/13c68628-80c2-45e0-92ef-29116cb06b75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Look up Cloudflare r2 pricing and use Python to figure out how much this (screenshot of dashboard) costs [ https://substack.com/redirect/ec86b1f3-c7d1-4481-b03f-6ec6a9dc78d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Talking to o3 feels like talking to a Deep Research tool in real-time, without having to wait for several minutes for it to produce an overly-verbose report.
My hunch is that doing this well requires a very strong reasoning model. Evaluating search results is hard, due to the need to wade through huge amounts of spam and deceptive information. The disappointing results from previous implementations usually came down to the Web being full of junk.
Maybe o3, o4-mini and Gemini 2.5 Pro are the first models to cross the gullibility-resistance threshold to the point that they can do this effectively?
Google and Anthropic need to catch up
The user-facing Google Gemini app [ https://substack.com/redirect/d76d7294-076d-40fb-b6cf-bda31baef715?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] can search too, but it doesn't show me what it's searching for. As a result, I just don't trust it. Compare these examples from o3 and Gemini for the prompt "Latest post by Simon Willison" - o3 is much more transparent:
This is a big missed opportunity since Google presumably have by far the best search index, so they really should be able to build a great version of this. And Google's AI assisted search on their regular search interface hallucinates wildly to the point that it's actively damaging their brand. I just checked and Google is still showing slop for Encanto 2 [ https://substack.com/redirect/9bb9395f-b355-45a0-b15a-744cfcd101ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
Claude also finally added web search [ https://substack.com/redirect/a999c275-b5c8-42af-9227-b7cb2d1e7352?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a month ago but it doesn't feel nearly as good. It's using the Brave search index [ https://substack.com/redirect/dcdd4c30-c701-4450-ae3d-48c53250c921?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which I don't think is as comprehensive as Bing or Gemini, and searches don't happen as part of that powerful reasoning flow.
Lazily porting code to a new library version via search
The truly magic moment for me came a few days ago [ https://substack.com/redirect/bb0dfd85-dd4f-482e-8e60-a025a4acd0c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
My Gemini image segmentation tool [ https://substack.com/redirect/38b6cdba-a848-4c6c-8858-a9a67b859980?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was using the @google/generative-ai [ https://substack.com/redirect/4c2450e7-69ce-4472-aac4-e1cbb19451a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library which has been loudly deprecated [ https://substack.com/redirect/02755ced-2b18-4dc9-9a21-a58c93035e42?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in favor of the still in preview Google Gen AI SDK @google/genai [ https://substack.com/redirect/e0a07c51-6115-416f-b80e-a20a0073d5dc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library.
I did not feel like doing the work to upgrade. On a whim, I pasted my full HTML code [ https://substack.com/redirect/1a9b748a-b501-429d-b49e-8daccd9fa028?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (with inline JavaScript) into ChatGPT o4-mini-high and prompted:
This code needs to be upgraded to the new recommended JavaScript library from Google. Figure out what that is and then look up enough documentation to port this code to it.
(I couldn't even be bothered to look up the name of the new library myself!)
... it did exactly that [ https://substack.com/redirect/bb7ae7dc-a348-4064-870b-056568a1ebc1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It churned away thinking for 21 seconds, ran a bunch of searches, figured out the new library (which existed way outside of its training cut-off date), found the upgrade instructions [ https://substack.com/redirect/82636d1d-1bb7-4496-a679-b0e3f7c15a05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and produced a new version [ https://substack.com/redirect/ae519c02-3346-4736-9bb6-84957ab84ff7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of my code that worked perfectly.
I ran this prompt on my phone out of idle curiosity while I was doing something else. I was extremely impressed and surprised when it did exactly what I needed.
How does the economic model for the Web work now?
I'm writing about this today because it's been one of my "can LLMs do this reliably yet?" questions for over two years now. I think they've just crossed the line into being useful as research assistants, without feeling the need to check everything they say with a fine-tooth comb.
I still don't trust them not to make mistakes, but I think I might trust them enough that I'll skip my own fact-checking for lower-stakes tasks.
This also means that a bunch of the potential dark futures we've been predicting for the last couple of years are a whole lot more likely to become true. Why visit websites if you can get your answers directly from the chatbot instead?
The lawsuits over this started flying [ https://substack.com/redirect/751e2d3f-3555-4122-83c2-a5af2f865a39?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back when the LLMs were still mostly rubbish. The stakes are a lot higher now that they're actually good at it!
I can feel my usage of Google search taking a nosedive already. I expect a bumpy ride as a new economic model for the Web lurches into view.
Maybe Meta's Llama claims to be open source because of the EU AI act [ https://substack.com/redirect/66d5bf8c-2705-4c29-a86c-42047d87ebfb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-04-19
I encountered a theory a while ago that one of the reasons Meta insist on using the term “open source” for their Llama models despite the Llama license not actually conforming [ https://substack.com/redirect/e0af9113-c64f-4728-8d10-6dbc07f51cf2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to the terms of the Open Source Definition [ https://substack.com/redirect/fcc403c4-2ae6-4a60-837a-2a3aeed4135d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is that the EU’s AI act includes special rules for open source models without requiring OSI compliance.
Since the EU AI act (12 July 2024) is available online [ https://substack.com/redirect/b5ab96cd-afb6-4e94-b88d-3dea2d8c2eba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I decided to take a look for myself.
Here’s one giant HTML page [ https://substack.com/redirect/76fb654f-f06d-4cb1-8b16-fd6123949622?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] containing the full text of the act in English. I checked the token count with ttok [ https://substack.com/redirect/e4d96b26-c049-4f7b-b622-94f2897ef62f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (which uses the OpenAI tokenizer, but it’s close enough to work as a good estimate for other models):
curl 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689' | ttok
241,722 tokens. That should fit nicely into Gemini 2.5 Flash [ https://substack.com/redirect/d4d57fe9-53e2-4cbd-a452-d196ae0a9226?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (or GPT-4.1 or Gemini 2.5 Pro).
My Gemini API key was playing up so I ran it via OpenRouter [ https://substack.com/redirect/95619212-edb5-4329-8b0b-4c07b37590df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (and llm-openrouter [ https://substack.com/redirect/648e084e-f5a2-4c59-8998-6e8345f0a6a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) instead:
llm -f 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689' \
-m openrouter/google/gemini-2.5-flash-preview:thinking \
-s 'Summary of mentions of open source here, including what the document defines open source to mean'
Here's the full answer [ https://substack.com/redirect/287f152c-82d4-407d-a8e7-0476ad54e0d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Relevant extract:
Recital (89) states that third parties making accessible "tools, services, processes, or AI components other than general-purpose AI models" under a free and open-source licence should not be mandated to comply with upstream provider responsibilities towards those who integrate them. It also encourages developers of such resources to implement documentation practices like model cards and data sheets to promote trustworthy AI.
Recital (102) acknowledges that software and data, including models, released under a free and open-source licence can contribute to research and innovation and provide growth opportunities.
I tracked down Recital 89 [ https://substack.com/redirect/c51fab4a-6c33-4a5d-a035-66e65594461c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Recital 102 [ https://substack.com/redirect/26333522-2190-4558-9adb-8d46ef54785a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to check. Sure enough, 89 says:
Third parties making accessible to the public tools, services, processes, or AI components other than general-purpose AI models, should not be mandated to comply with requirements targeting the responsibilities along the AI value chain
And in 102:
General-purpose AI models released under free and open-source licences should be considered to ensure high levels of transparency and openness if their parameters, including the weights, the information on the model architecture, and the information on model usage are made publicly available. The licence should be considered to be free and open-source also when it allows users to run, copy, distribute, study, change and improve software and data, including models under the condition that the original provider of the model is credited, the identical or comparable terms of distribution are respected.
Gemini 2.5 Flash also pointed me to Article 2(12) [ https://substack.com/redirect/53c8ed3b-8800-4206-aba5-048cd606eebc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which reads:
12. This Regulation does not apply to AI systems released under free and open-source licences, unless they are placed on the market or put into service as high-risk AI systems or as an AI system that falls under Article 5 [ https://substack.com/redirect/20b11f07-d71c-489d-ad1b-45372ec8645b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or 50 [ https://substack.com/redirect/1cfb7065-1959-46c7-80b6-c82918f5829b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I asked a follow-up question:
llm -c 'so it says specific licenses but does it clarify which specific licenses count?'
And got back this response [ https://substack.com/redirect/7a54d8c3-f915-4c26-9941-a3c5587e94b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
No, the document does not list specific names of licenses that qualify as "free and open-source".
Instead of listing names (like GPL, MIT, Apache, etc.), the Regulation defines what kind of terms a license must grant for it to be considered "free and open-source" for the purposes of the Regulation.
According to Recital (102), such a license must essentially allow software and data, including models, to be:
Openly shared.
Where users can freely access, use, modify and redistribute them or modified versions thereof.
The Recital further clarifies that a license can still be considered free and open-source even if it includes standard conditions like requiring attribution (crediting the original provider) or respecting identical or comparable terms of distribution.
I am very obviously not a lawyer, but based on the above I do find the theory credible that Meta are using "open source" in their marketing around Llama partly because the EU AI act has special exemptions for "open source" models that have nothing to do with the OSI definition of that term.
Total cost to use Gemini 2.5 Flash for this? 5.1 cents for my first question and 4.3 cents for the follow-up. That second question was cheaper even though it built on the first because output tokens are more expensive than input tokens and the second answer was shorter than the first - using the "thinking" model output is charged at $3.50/million tokens, input is just $0.15/million.
Using an LLM as a lawyer is obviously a terrible idea, but using one to crunch through a giant legal document and form a very rough layman's understanding of what it says feels perfectly cromulent to me.
Update: Steve O'Grady points out [ https://substack.com/redirect/a894fbdf-77a5-4c8e-ada1-f8eb99f74eb1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that Meta/Facebook have been abusing the term "open source" for a lot longer than the EU AI act has been around - they were pulling shenanigans with a custom license for React back in 2017 [ https://substack.com/redirect/ce93ca8d-eb1c-40d7-916e-f8c807bfaafd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-04-19 Gemma 3 QAT Models [ https://substack.com/redirect/eca2d08d-48c1-46e4-94d1-7f9168f495d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Interesting release from Google, as a follow-up to Gemma 3 [ https://substack.com/redirect/4ead5629-9b51-4e9a-afe3-04374ac8ac76?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from last month:
To make Gemma 3 even more accessible, we are announcing new versions optimized with Quantization-Aware Training (QAT) that dramatically reduces memory requirements while maintaining high quality. This enables you to run powerful models like Gemma 3 27B locally on consumer-grade GPUs like the NVIDIA RTX 3090.
I wasn't previously aware of Quantization-Aware Training but it turns out to be quite an established pattern now, supported in both Tensorflow [ https://substack.com/redirect/1e7e5089-fea1-4240-950d-ad1bf34019af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and PyTorch [ https://substack.com/redirect/0c18778e-53f9-47e6-806f-768a8ee6e380?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Google report model size drops from BF16 to int4 for the following models:
Gemma 3 27B: 54GB to 14.1GB
Gemma 3 12B: 24GB to 6.6GB
Gemma 3 4B: 8GB to 2.6GB
Gemma 3 1B: 2GB to 0.5GB
They partnered with Ollama, LM Studio, MLX (here's their collection [ https://substack.com/redirect/fb090607-3a95-4763-8e8c-8349d70e71b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and llama.cpp for this release - I'd love to see more AI labs following their example.
The Ollama model version picker currently hides them behind "View all" option, so here are the direct links:
gemma3:1b-it-qat [ https://substack.com/redirect/53b95022-0424-4167-abce-cc8bfbc1901b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 1GB
gemma3:4b-it-qat [ https://substack.com/redirect/93d180e5-a348-4f57-883c-9be24e205c18?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 4GB
gemma3:12b-it-qat [ https://substack.com/redirect/c114c0cd-acd5-4eeb-b460-7319366783c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 8.9GB
gemma3:27b-it-qat [ https://substack.com/redirect/0c5e1f53-6f5c-486c-bca2-356483e0e0e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 18GB
I fetched that largest model with:
ollama pull gemma3:27b-it-qat
And now I'm trying it out with llm-ollama [ https://substack.com/redirect/1695fb05-ee1a-4d6a-b758-9ac11cbe6a6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm -m gemma3:27b-it-qat "impress me with some physics"
I got a pretty great response [ https://substack.com/redirect/c9a2bcab-ffdd-4006-9a99-e6cddce85c36?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
Update: Having spent a while putting it through its paces via Open WebUI [ https://substack.com/redirect/a6f4aa8e-e9d7-495b-bd37-a5a12b18a731?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Tailscale [ https://substack.com/redirect/d2bf11a8-aa32-4a0b-a592-5defa2f56949?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to access my laptop from my phone I think this may be my new favorite general-purpose local model. Ollama appears to use 22GB of RAM while the model is running, which leaves plenty on my 64GB machine for other applications.
I've also tried it via llm-mlx [ https://substack.com/redirect/8025a701-26ad-4c02-9e3d-506bd9c10c3e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this (downloading 16GB):
llm install llm-mlx
llm mlx download-model mlx-community/gemma-3-27b-it-qat-4bit
llm chat -m mlx-community/gemma-3-27b-it-qat-4bit
It feels a little faster with MLX and uses 15GB of memory according to Activity Monitor.
Link 2025-04-19 Claude Code: Best practices for agentic coding [ https://substack.com/redirect/ddffa770-40ce-49a6-8324-ebaff359fd3a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Extensive new documentation from Anthropic on how to get the best results out of their Claude Code [ https://substack.com/redirect/3e93bff1-ee33-409c-8991-839ae353124d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CLI coding agent tool, which includes this fascinating tip:
We recommend using the word "think" to trigger extended thinking mode, which gives Claude additional computation time to evaluate alternatives more thoroughly. These specific phrases are mapped directly to increasing levels of thinking budget in the system: "think" < "think hard" < "think harder" < "ultrathink." Each level allocates progressively more thinking budget for Claude to use.
Apparently ultrathink is a magic word!
I was curious if this was a feature of the Claude model itself or Claude Code in particular. Claude Code isn't open source but you can view the obfuscated JavaScript for it, and make it a tiny bit less obfuscated by running it through Prettier [ https://substack.com/redirect/e84c0818-7344-41bf-b9ac-68a6f9e815c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. With Claude's help [ https://substack.com/redirect/7ad8a590-52bf-45f4-ba1a-8373d58fad2e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I used this recipe:
mkdir -p /tmp/claude-code-examine
cd /tmp/claude-code-examine
npm init -y
npm install @anthropic-ai/claude-code
cd node_modules/@anthropic-ai/claude-code
npx prettier --write cli.js
Then used ripgrep [ https://substack.com/redirect/c2a2dd99-3143-4a1b-bb7c-5577d2548341?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to search for "ultrathink":
rg ultrathink -C 30
And found this chunk of code:
let B = W.message.content.toLowerCase;
if (
B.includes("think harder") ||
B.includes("think intensely") ||
B.includes("think longer") ||
B.includes("think really hard") ||
B.includes("think super hard") ||
B.includes("think very hard") ||
B.includes("ultrathink")
)
return (
l1("tengu_thinking", { tokenCount: 31999, messageId: Z, provider: G }),
31999
);
if (
B.includes("think about it") ||
B.includes("think a lot") ||
B.includes("think deeply") ||
B.includes("think hard") ||
B.includes("think more") ||
B.includes("megathink")
)
return (
l1("tengu_thinking", { tokenCount: 1e4, messageId: Z, provider: G }), 1e4
);
if (B.includes("think"))
return (
l1("tengu_thinking", { tokenCount: 4000, messageId: Z, provider: G }),
4000
);
So yeah, it looks like "ultrathink" is a Claude Code feature - presumably that 31999 is a number that affects the token thinking budget [ https://substack.com/redirect/77955436-887b-49fa-a5fe-ce2743bc4d2d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], especially since "megathink" maps to 1e4 tokens (10,000) and just plain "think" maps to 4,000.
Link 2025-04-20 llm-fragments-github 0.2 [ https://substack.com/redirect/c080470e-de30-4a57-aa3a-cbe2f07f8ba9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I upgraded my llm-fragments-github plugin to add a new fragment type called issue. It lets you pull the entire content of a GitHub issue thread into your prompt as a concatenated Markdown file.
(If you haven't seen fragments before I introduced them in Long context support in LLM 0.24 using fragments and template plugins [ https://substack.com/redirect/7d75c705-9d76-452f-ba43-12ce935b1bdd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
I used it just now to have Gemini 2.5 Pro provide feedback and attempt an implementation of a complex issue against my LLM [ https://substack.com/redirect/ef2988dd-c5ac-4742-823b-c32122dba527?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project:
llm install llm-fragments-github
llm -f github:simonw/llm \
-f issue:simonw/llm/938 \
-m gemini-2.5-pro-exp-03-25 \
--system 'muse on this issue, then propose a whole bunch of code to help implement it'
Here I'm loading the FULL content of the simonw/llm repo using that -f github:simonw/llm fragment (documented here [ https://substack.com/redirect/f4e58666-8c2c-40af-b0b0-241f6a985e1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), then loading all of the comments from issue 938 [ https://substack.com/redirect/0e58ac85-f604-429b-9e88-91fbfc2f3436?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where I discuss quite a complex potential refactoring. I ask Gemini 2.5 Pro to "muse on this issue" and come up with some code.
This worked shockingly well. Here's the full response [ https://substack.com/redirect/1c835f7e-c4b5-4431-891d-9cf710ca08db?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which highlighted a few things I hadn't considered yet (such as the need to migrate old database records to the new tree hierarchy) and then spat out a whole bunch of code which looks like a solid start to the actual implementation work I need to do.
I ran this against Google's free Gemini 2.5 Preview, but if I'd used the paid model it would have cost me 202,680 input tokens and 10,460 output tokens for a total of 66.36 cents.
As a fun extra, the new issue: feature itself was written almost entirely by OpenAI o3, again using fragments. I ran this:
llm -m openai/o3 \
-f https://raw.githubusercontent.com/simonw/llm-hacker-news/refs/heads/main/llm_hacker_news.py \
-f https://raw.githubusercontent.com/simonw/tools/refs/heads/main/github-issue-to-markdown.html \
-s 'Write a new fragments plugin in Python that registers issue:org/repo/123 which fetches that issue
number from the specified github repo and uses the same markdown logic as the HTML page to turn that into a fragment'
Here I'm using the ability to pass a URL to -f and giving it the full source of my llm_hacker_news.py [ https://substack.com/redirect/e5405224-6522-4d17-86ad-9efd1efa551b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin (which shows how a fragment can load data from an API) plus the HTML source [ https://substack.com/redirect/5a15d22f-4a55-453e-961f-59b7f5f2d556?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of my github-issue-to-markdown [ https://substack.com/redirect/57a9392c-9a4a-4bf7-81b0-92f67cdfca8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool (which I wrote a few months ago with Claude [ https://substack.com/redirect/755ac286-17d3-4cb9-9fc0-866b00975972?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). I effectively asked o3 to take that HTML/JavaScript tool and port it to Python to work with my fragments plugin mechanism.
o3 provided almost the exact implementation I needed [ https://substack.com/redirect/3996fb96-2db3-4eed-8243-e14598fbb212?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and even included support for a GITHUB_TOKEN environment variable without me thinking to ask for it. Total cost: 19.928 cents.
On a final note of curiosity I tried running this prompt against Gemma 3 27B QAT [ https://substack.com/redirect/bad82a91-5754-4658-a122-562a034b3953?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] running on my Mac via MLX and llm-mlx [ https://substack.com/redirect/8025a701-26ad-4c02-9e3d-506bd9c10c3e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm install llm-mlx
llm mlx download-model mlx-community/gemma-3-27b-it-qat-4bit

llm -m mlx-community/gemma-3-27b-it-qat-4bit \
-f https://raw.githubusercontent.com/simonw/llm-hacker-news/refs/heads/main/llm_hacker_news.py \
-f https://raw.githubusercontent.com/simonw/tools/refs/heads/main/github-issue-to-markdown.html \
-s 'Write a new fragments plugin in Python that registers issue:org/repo/123 which fetches that issue
number from the specified github repo and uses the same markdown logic as the HTML page to turn that into a fragment'
That worked pretty well too [ https://substack.com/redirect/7b924e46-d4e0-49de-85e8-463ebdc3bd53?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It turns out a 16GB local model file is powerful enough to write me an LLM plugin now!
Quote 2025-04-20
In some tasks, AI is unreliable. In others, it is superhuman. You could, of course, say the same thing about calculators, but it is also clear that AI is different. It is already demonstrating general capabilities and performing a wide range of intellectual tasks, including those that it is not specifically trained on. Does that mean that o3 and Gemini 2.5 are AGI? Given the definitional problems, I really don’t know, but I do think they can be credibly seen as a form of “Jagged AGI” - superhuman in enough areas to result in real changes to how we work and live, but also unreliable enough that human expertise is often needed to figure out where AI works and where it doesn’t.
Ethan Mollick [ https://substack.com/redirect/c8f979e0-97a7-49d6-bde5-051ed6f8eddd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-04-21 Decentralizing Schemes [ https://substack.com/redirect/df3ced41-d1cd-40ea-b9d7-792fe807498c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Tim Bray discusses the challenges faced by decentralized Mastodon in that shared URLs to posts don't take into account people accessing Mastodon via their own instances, which breaks replies/likes/shares etc unless you further copy and paste URLs around yourself.
Tim proposes that the answer is URIs: a registered fedi://mastodon.cloud/@timbray/109508984818551909 scheme could allow Fediverse-aware software to step in and handle those URIs, similar to how mailto: works.
Bluesky have registered [ https://substack.com/redirect/7e47df69-38be-46b0-b6c0-8e8663e52568?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at: already, and there's also a web+ap: prefix registered with the intent of covering ActivityPub, the protocol used by Mastodon.
Link 2025-04-21 OpenAI o3 and o4-mini System Card [ https://substack.com/redirect/240f67dd-e170-476e-b31d-e099aa9541b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I'm surprised to see a combined System Card for o3 and o4-mini in the same document - I'd expect to see these covered separately.
The opening paragraph calls out the most interesting new ability of these models (see also my notes here [ https://substack.com/redirect/b564f805-d896-4e94-b9c4-0c8f892abe71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). Tool usage isn't new, but using tools in the chain of thought appears to result in some very significant improvements:
The models use tools in their chains of thought to augment their capabilities; for example, cropping or transforming images, searching the web, or using Python to analyze data during their thought process.
Section 3.3 on hallucinations has been gaining a lot of attention. Emphasis mine:
We tested OpenAI o3 and o4-mini against PersonQA, an evaluation that aims to elicit hallucinations. PersonQA is a dataset of questions and publicly available facts that measures the model's accuracy on attempted answers.
We consider two metrics: accuracy (did the model answer the question correctly) and hallucination rate (checking how often the model hallucinated).
The o4-mini model underperforms o1 and o3 on our PersonQA evaluation. This is expected, as smaller models have less world knowledge and tend to hallucinate more. However, we also observed some performance differences comparing o1 and o3. Specifically, o3 tends to make more claims overall, leading to more accurate claims as well as more inaccurate/hallucinated claims. More research is needed to understand the cause of this result.
Table 4: PersonQA evaluation Metric o3 o4-mini o1 accuracy (higher is better) 0.59 0.36 0.47 hallucination rate (lower is better) 0.33 0.48 0.16
The benchmark score on OpenAI's internal PersonQA benchmark (as far as I can tell no further details of that evaluation have been shared) going from 0.16 for o1 to 0.33 for o3 is interesting, but I don't know if it it's interesting enough to produce dozens of headlines along the lines of "OpenAI's o3 and o4-mini hallucinate way higher than previous models".
The paper also talks at some length about "sandbagging". I’d previously encountered sandbagging defined as meaning [ https://substack.com/redirect/fb7f9450-9e5d-4782-85bc-07a47985d0a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] “where models are more likely to endorse common misconceptions when their user appears to be less educated”. The o3/o4-mini system card uses a different definition: “the model concealing its full capabilities in order to better achieve some goal” - and links to the recent Anthropic paper Automated Researchers Can Subtly Sandbag [ https://substack.com/redirect/d40fabfc-084b-44a3-91ea-c93fd1310929?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
As far as I can tell this definition relates to the American English use of “sandbagging” to mean [ https://substack.com/redirect/883bc4eb-590f-4f48-87db-8bd1bb89625a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] “to hide the truth about oneself so as to gain an advantage over another” - as practiced by poker or pool sharks.
(Wouldn't it be nice if we could have just one piece of AI terminology that didn't attract multiple competing definitions?)
o3 and o4-mini both showed some limited capability to sandbag - to attempt to hide their true capabilities in safety testing scenarios that weren't fully described. This relates to the idea of "scheming", which I wrote about with respect to the GPT-4o model card last year [ https://substack.com/redirect/8a2cdd04-9e65-4f81-9842-413ad0cd8079?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-04-22 Working Through the Fear of Being Seen [ https://substack.com/redirect/761ac318-b3e1-4eb0-883b-542c8042acbe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Heartfelt piece by Ashley Willis about the challenge of overcoming self-doubt in publishing online:
Part of that is knowing who might read it. A lot of the folks who follow me are smart, opinionated, and not always generous. Some are friends. Some are people I’ve looked up to. And some are just really loud on the internet. I saw someone the other day drag a certain writing style. That kind of judgment makes me want to shrink back and say, never mind.
Work to avoid being somebody who discourages others from sharing their thoughts.
Link 2025-04-22 A5 [ https://substack.com/redirect/6e21c5a5-6592-4471-b281-5d0615395040?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A5 is a new "global, equal-area, millimeter-accurate geospatial index" by Felix Palmer:
It is the pentagonal equivalent of other DGGSs, like S2 or H3, but with higher accuracy and lower distortion.
Effectively it's a way of dividing the entire world into pentagons where each one covers the same physical area (to within a 2% threshold) - like Uber's H3 [ https://substack.com/redirect/4030afe5-c944-4d9b-b8df-fe237e0203aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but a bit weirder and more fun. An A5 reference implementation written in TypeScript is available on GitHub [ https://substack.com/redirect/3ca91e27-db23-4651-926e-da7f6190c073?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This interactive demo [ https://substack.com/redirect/581ed164-f425-4ceb-b998-0bdf31bad464?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] helps show how it works:
Why pentagons? Here's what the A5 docs say [ https://substack.com/redirect/9081e0e9-4223-4b11-a673-3915cfe13a91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A5 is unique in that it uses a pentagonal tiling of a dodecahedron. [...] The benefit of choosing a dodecahedron is that it is the platonic solid with the lowest vertex curvature, and by this measure it is the most spherical of all the platonic solids. This is key for minimizing cell distortion as the process of projecting a platonic solid onto a sphere involves warping the cell geometry to force the vertex curvature to approach zero. Thus, the lower the original vertex curvature, the less distortion will be introduced by the projection.
I had to look up platonic solids [ https://substack.com/redirect/9db0269f-48bd-44a1-bfb8-95b39aa3c78b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Wikipedia. There are only five: Tetrahedron, Cube, Octahedron, Dodecahedron and Icosahedron and they can be made using squares, triangles or (in the case of the Dodecahedron) pentagons, making the pentagon the most circle-like option.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOakU0T1RRMU5qWXNJbWxoZENJNk1UYzBOVE16TmpBMU55d2laWGh3SWpveE56YzJPRGN5TURVM0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEud2xxZjNBWTJHZmZORy12SmdFMEVYeGNMdk5seG5HdGp2OXlScEprblh3SSIsInAiOjE2MTg5NDU2NiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQ1MzM2MDU3LCJleHAiOjE3NDc5MjgwNTcsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.Upv5E526LJZAETM407F7TAETCWX4dgxeCGJCmVvedhg?
