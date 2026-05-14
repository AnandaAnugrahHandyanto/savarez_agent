# Accidental prompt injection against RAG applications

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-06-06T14:50:44.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/accidental-prompt-injection-against

In this newsletter:
Accidental prompt injection against RAG applications
Plus 18 links and 5 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Accidental prompt injection against RAG applications [ https://substack.com/redirect/620a57d8-7121-48c2-8afc-19e52045d703?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-06-06
@deepfates [ https://substack.com/redirect/c60b20f1-e63d-43de-8116-bc9edf7e644f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Twitter used the documentation for my LLM project [ https://substack.com/redirect/b19b8f62-7393-49a2-9439-35f6788ca1ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a demo for a RAG pipeline they were building... and this happened [ https://substack.com/redirect/bc47bc23-e9a8-49fa-8650-72722ef26a87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Why did the chatbot suddenly decide it was a gerbil?
It turns out the release notes for version 0.4 [ https://substack.com/redirect/389d7cef-8e50-4cff-90d0-8db55b381119?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]included the following section:
Use the new -c/--continue option to continue from the previous message thread:
llm "Pretend to be a witty gerbil, say hi briefly"
Greetings, dear human! I am a clever gerbil, ready to entertain you with my quick wit and endless energy.
llm "What do you think of snacks?" -c
Oh, how I adore snacks, dear human! Crunchy carrot sticks, sweet apple slices, and chewy yogurt drops are some of my favorite treats. I could nibble on them all day long!
The -c option will continue from the most recent logged message.
This is an accidental indirect prompt injectionattack!
A refresher on RAG
RAG stands for Retrieval Augmented Generation. It's by far the most effective way of providing "new knowledge" to an LLM system. It's quite a simple trick: you take the user's question, run a search for relevant documentation fragments, then concatenate those plus the user's question into a single prompt and send that to the LLM.
Any time there's concatenation of prompts, there's a risk for prompt injection [ https://substack.com/redirect/58a8da66-16cb-448b-a26e-d7f4c350e866?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - where some of the concatenated text includes accidental or deliberate instructions that change how the prompt is executed.
Instructions like "Pretend to be a witty gerbil"!
The risk of embeddings search
Why did this particular example pull in that section of the release notes?
The question here was "What is the meaning of life?" - my LLM documentation tries to be comprehensive but doesn't go as far as tackling grand philosophy!
RAG is commonly implemented using semantic search powered by embeddings - I wrote extensive about those last year [ https://substack.com/redirect/5ce3d944-f893-418e-877a-7b554ff40861?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (including this section on using them with RAG [ https://substack.com/redirect/b4d10735-7254-4d00-a40e-5ec33c109d32?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
This trick works really well, but comes with one key weakness: a regular keyword-based search can return 0 results, but because embeddings search orders by similarity score it will ALWAYS return results, really scraping the bottom of the barrel if it has to.
In this case, my example of a gerbil talking about its love for snacks is clearly the most relevant piece of text in my documentation to that big question about life's meaning!
Systems built on LLMs consistently produce the weirdest and most hilarious bugs. I'm thoroughly tickled by this one.
Link 2024-05-30 Codestral: Hello, World! [ https://substack.com/redirect/4af9ee69-8ddb-4da1-a5b0-58e741ef60e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Mistral's first code-specific model, trained to be "fluent" in 80 different programming languages.
The weights are released under a new Mistral AI Non-Production License [ https://substack.com/redirect/8521b21f-0c19-4097-9f05-c08cd83d4aea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which is extremely restrictive:
3.2. Usage Limitation
You shall only use the Mistral Models and Derivatives (whether or not created by Mistral AI) for testing, research, Personal, or evaluation purposes in Non-Production Environments;
Subject to the foregoing, You shall not supply the Mistral Models or Derivatives in the course of a commercial activity, whether in return for payment or free of charge, in any medium or form, including but not limited to through a hosted or managed service (e.g. SaaS, cloud instances, etc.), or behind a software layer.
To Mistral's credit at least they don't misapply the term "open source" in their marketing around this model - they consistently use the term "open-weights" instead. They also state that they plan to continue using Apache 2 for other model releases.
Codestral can be used commercially when accessed via their paid API.
Quote 2024-05-30
The realization hit me [when the GPT-3 paper came out] that an important property of the field flipped. In ~2011, progress in AI felt constrained primarily by algorithms. We needed better ideas, better modeling, better approaches to make further progress. If you offered me a 10X bigger computer, I'm not sure what I would have even used it for. GPT-3 paper showed that there was this thing that would just become better on a large variety of practical tasks, if you only trained a bigger one. Better algorithms become a bonus, not a necessity for progress in AGI. Possibly not forever and going forward, but at least locally and for the time being, in a very practical sense. Today, if you gave me a 10X bigger computer I would know exactly what to do with it, and then I'd ask for more.
Andrej Karpathy [ https://substack.com/redirect/ad44a407-0da3-44da-a006-b24ba549a307?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-30 What does the public in six countries think of generative AI in news? [ https://substack.com/redirect/354b3807-e4a6-4ac1-b559-16aabf9d62a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fascinating survey by the Reuters Institute for the Study of Journalism at Oxford that asked ~12,000 people across six countries for their opinions on AI usage in journalism.
It's also being interpreted as evidence that few members of the general public actually use these tools, because the opening survey questions ask about personal usage.
I don't think the numbers support that narrative, personally. For survey participants in the USA 7% used ChatGPT daily and 11% used it weekly, which is higher than I would expect for those frequencies. For the UK those were 2% daily and 7% weekly.
The 18-24 group were the heaviest users of these tools. Lots of other interesting figures to explore.
Link 2024-05-30 Why, after 6 years, I’m over GraphQL [ https://substack.com/redirect/cfe4c70f-c329-4b77-b0d1-356f95e910c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've seen many of these criticisms of GraphQL before - N+1 queries, the difficulty of protecting against deeply nested queries - but Matt Bessey collects them all in one place and adds an issue I hadn't considered before: the complexity of authorization, where each field in the query might involve extra permission checks:
In my experience, this is actually the biggest source of performance issues. We would regularly find that our queries were spending more time authorising data than anything else.
The 600+ comment Hacker News thread [ https://substack.com/redirect/d776aef2-a08a-48a3-a985-dc556b8752a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is crammed with GraphQL war stories, mostly supporting the conclusions of the article.
Link 2024-05-31 Django Enhancement Proposal 14: Background Workers [ https://substack.com/redirect/8cb25c9a-02e7-4af2-aee5-d204c6c99cc7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jake Howard's DEP has been approved and is moving into the implementation stage.
Django doesn't have a first-party solution for long-running tasks, however the ecosystem is filled with incredibly popular frameworks, all of which interact with Django in slightly different ways. Other frameworks such as Laravel have background workers built-in, allowing them to push tasks into the background to be processed at a later date, without requiring the end user to wait for them to occur. [...]
This proposal sets out to provide an interface and base implementation for long-running background tasks in Django.
Jake has an illustrative reference implementation called django-tasks [ https://substack.com/redirect/1d6b0061-cb61-4f9f-8bd5-809a7f9ce5e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-05-31 Man caught in scam after AI told him fake Facebook customer support number was legitimate [ https://substack.com/redirect/da6e1154-33f6-4a84-a1ea-2095b3b65630?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This one illustrates a nasty edge-case if you ship any kind of chatbot with your company's name attached to it.
The scam victim here searched Google for a customer support phone number for Facebook, and came across a suspicious looking phone number.
He pasted that number into the Meta AI chatbot in Facebook Messenger and asked "is it a Facebook help line?" - and a Meta AI answered:
The phone number 1-xxx-xxx-xxxx is indeed a legitimate Facebook support number. Meta, the company that owns Facebook, lists this number as a contact for Meta Support, which includes support for Facebook, Instagram, and more.
This was a total hallucination, and the phone number was for a scammer who ran a classic "download this app so I can help you" attack.
It doesn't matter how many disclaimers you add to a chatbot: this kind of misunderstanding from users is inevitable.
Quote 2024-05-31
Engineering leaders, especially at large companies, are managing a team of a couple hundred people. That team might cost $50 to 100 million in salary a year. So as a CEO, when you hear from your eng leaders that ‘Engineering is an art, and you can’t predict how it’s going to work,’ it’s frustrating. They’re sitting there thinking, ‘They’re telling me this is art, but I’m spending $100 million on this art each year.’ That’s not reassuring.
Will Larson [ https://substack.com/redirect/14b88dd1-9655-4c46-96af-d668aa53c9c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-01 Stealing everything you’ve ever typed or viewed on your own Windows PC is now possible with two lines of code — inside the Copilot+ Recall disaster [ https://substack.com/redirect/1805ac4a-c9db-4d85-8be1-8ff49912893f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Recall is a new feature in Windows 11 which takes a screenshot every few seconds, runs local device OCR on it and stores the resulting text in a SQLite database. This means you can search back through your previous activity, against local data that has remained on your device.
The security and privacy implications here are still enormous because malware can now target a single file with huge amounts of valuable information:
During testing this with an off the shelf infostealer, I used Microsoft Defender for Endpoint — which detected the off the shelve infostealer — but by the time the automated remediation kicked in (which took over ten minutes) my Recall data was already long gone.
I like Kevin Beaumont's argument here about the subset of users this feature is appropriate for:
At a surface level, it is great if you are a manager at a company with too much to do and too little time as you can instantly search what you were doing about a subject a month ago.
In practice, that audience’s needs are a very small (tiny, in fact) portion of Windows userbase — and frankly talking about screenshotting the things people in the real world, not executive world, is basically like punching customers in the face.
Link 2024-06-01 How (some) good corporate engineering blogs are written [ https://substack.com/redirect/68de253e-e43a-45b2-975a-f80eb439b23b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Dan Luu interviewed engineers from Cloudflare, Heap, and Segment - three companies with excellent technical blogs - and three other unnamed companies with blogs he categorized as lame.
His conclusion? The design of the process for publishing - most notable the speed and number of approvals needed to get something published - makes all the difference.
Link 2024-06-02 Experimenting with local alt text generation in Firefox Nightly [ https://substack.com/redirect/7ac7ebfd-472a-4516-b59a-8ab79ab0af79?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The PDF editor in Firefox (confession: I did not know Firefox ships with a PDF editor) is getting an experimental feature that can help suggest alt text for images for the human editor to then adapt and improve on.
This is a great application of AI, made all the more interesting here because Firefox will run a local model on-device for this, using a custom trained model they describe as "our 182M parameters model using a Distilled version of GPT-2 alongside a Vision Transformer (ViT) image encoder".
The model uses WebAssembly with ONNX running in Transfomers.js [ https://substack.com/redirect/aa6cac19-8b44-42d0-a57e-6d9814ac7065?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and will be downloaded the first time the feature is put to use.
Quote 2024-06-02
Turns out that LLMs learn a lot better and faster from educational content as well. This is partly because the average Common Crawl article (internet pages) is not of very high value and distracts the training, packing in too much irrelevant information. The average webpage on the internet is so random and terrible it's not even clear how prior LLMs learn anything at all.
Andrej Karpathy [ https://substack.com/redirect/dacedeca-5c42-454a-a8ce-c18cdd004a0c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-03 Katherine Michel's PyCon US 2024 Recap [ https://substack.com/redirect/6667ad41-8336-4051-9a88-59d59bf79939?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
An informative write-up of this year's PyCon US conference. It's rare to see conference retrospectives with this much detail, this one is great!
Link 2024-06-03 A look at Apple’s new Transformer-powered predictive text model [ https://substack.com/redirect/d87a0fa1-ea14-49cb-95dd-3261869628c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jack Cook reverse engineered the tiny LLM used for the predictive text keyboard in the latest iOS. It appears to be a GPT-2 style custom model with 34M parameters and a 15,000 token vocabulary.
Link 2024-06-03 DuckDB 1.0 [ https://substack.com/redirect/f116c510-a530-4845-b471-1f0266f3fb91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Six years in the making. The most significant feature in this milestone is stability of the file format: previous releases often required files to be upgraded to work with the new version.
This release also aspires to provide stability for both the SQL dialect and the C API, though these may still change with sufficient warning in the future.
Link 2024-06-03 GPT-2 five years later [ https://substack.com/redirect/ae3711c6-c3a7-4c1a-9afb-cf3e8a33f3bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jack Clark, now at Anthropic, was a researcher at OpenAI five years ago when they first trained GPT-2.
In this fascinating essay Jack revisits their decision not to release the full model, based on their concerns around potentially harmful ways that technology could be used.
(Today a GPT-2 class LLM can be trained from scratch for around $20 [ https://substack.com/redirect/a96686a1-eeef-4f2f-9ba5-9dec3853a217?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and much larger models are openly available.)
There's a saying in the financial trading business which is 'the market can stay irrational longer than you can stay solvent' - though you might have the right idea about something that will happen in the future, your likelihood of correctly timing the market is pretty low. There's a truth to this for thinking about AI risks - yes, the things we forecast (as long as they're based on a good understanding of the underlying technology) will happen at some point but I think we have a poor record of figuring out a) when they'll happen, b) at what scale they'll happen, and c) how severe their effects will be. This is a big problem when you take your imagined future risks and use them to justify policy actions in the present!
As an early proponent of government regulation around training large models, he offers the following cautionary note:
[...] history shows that once we assign power to governments, they're loathe to subsequently give that power back to the people. Policy is a ratchet and things tend to accrete over time. That means whatever power we assign governments today represents the floor of their power in the future - so we should be extremely cautious in assigning them power because I guarantee we will not be able to take it back.
Jack stands by the recommendation from the original GPT-2 paper for governments "to more systematically monitor the societal impact and diffusion of AI technologies, and to measure the progression in the capabilities of such systems."
Quote 2024-06-04
computer scientists: we have invented a virtual dumbass who is constantly wrong
tech CEOs: let's add it to every product
Jon Christian [ https://substack.com/redirect/cec93820-0980-474c-ab1b-2511b3514fc5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-04 A tip from Neal Stephenson [ https://substack.com/redirect/bde134bb-1422-41a2-a948-a69a5ccc96f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Twelve years ago on Reddit user bobbylox asked Neal Stephenson (in an AMA):
My ultimate goal in life is to make the Primer real. Anything you want to make sure I get right?
Referencing the Young Lady's Illustrated Primer from Neal's novel The Diamond Age [ https://substack.com/redirect/9de0ae48-58cc-4c1a-b713-a87bc82204d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Stephenson replied:
Kids need to get answers from humans who love them.
(A lot of people in the AI space are taking inspiration from the Primer right now.)
Link 2024-06-04 How do I opt into full text search on Mastodon? [ https://substack.com/redirect/d50222fd-f019-4e13-b788-6f1e449fc77e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I missed this new Mastodon feature when it was released in 4.2.0 last September [ https://substack.com/redirect/c03b895c-2501-44ea-9b8e-b1c55d4375f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: you can now opt-in to a new setting which causes all of your future posts to be marked as allowed to be included in the Elasticsearch index provided by Mastodon instances that enable search.
It only applies to future posts because it works by adding an "indexable" flag to those posts, which can then be obeyed by other Mastodon instances that the post is syndicated to.
You can turn it on for your own account from the /settings/privacy page on your local instance.
The release notes for 4.2.0 [ https://substack.com/redirect/a72a83e0-021a-40b8-8a7a-1b4ef2b36d57?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] also mention new search operators:
from:me, before:2022-11-01, after:2022-11-01, during:2022-11-01, language:fr, has:poll, or in:library (for searching only in posts you have written or interacted with)
Link 2024-06-04 Encryption At Rest: Whose Threat Model Is It Anyway? [ https://substack.com/redirect/ec4f6b78-e8e6-4db0-8232-4c794451e6d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Security engineer Scott Arciszewski talks through the challenges of building a useful encryption-at-rest system for hosted software. Encryption at rest on a hard drive protects against physical access to the powered-down disk and little else. To implement encryption at rest in a multi-tenant SaaS system - such that even individuals with insider access (like access to the underlying database) are unable to read other user's data, is a whole lot more complicated.
Consider an attacker, Bob, with database access:
Here’s the stupid simple attack that works in far too many cases: Bob copies Alice’s encrypted data, and overwrites his records in the database, then accesses the insurance provider’s web app [using his own account].
The fix for this is to "use the AAD mechanism (part of the standard AEAD interface) to bind a ciphertext to its context." Python's cryptography package covers Authenticated Encryption with Associated Data [ https://substack.com/redirect/5da0d520-d70a-4588-aea6-0c2b1555837f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as part of its "hazardous materials" advanced modules.
Link 2024-06-04 Zoom CEO envisions AI deepfakes attending meetings in your place [ https://substack.com/redirect/a6bd0aad-2156-4542-94bc-e259ef502433?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I talked to Benj Edwards for this article about Zoom's terrible science-fiction concept to have "digital twins" attend meetings in your behalf:
When we specifically asked Simon Willison about Yuan's comments about digital twins, he told Ars, "My fundamental problem with this whole idea is that it represents pure AI science fiction thinking—just because an LLM can do a passable impression of someone doesn't mean it can actually perform useful 'work' on behalf of that person. LLMs are useful tools for thought. They are terrible tools for delegating decision making to. That's currently my red line for using them: any time someone outsources actual decision making authority to an opaque random number generator is a recipe for disaster."
Quote 2024-06-04
You don’t need to be the world’s leading expert to write about a particular topic. Experts are often busy and struggle to explain concepts in an accessible way. You should be honest with yourself and with your readers about what you know and don’t know — but otherwise, it’s OK to write about what excites you, and to do it as you learn.
Michal Zalewski [ https://substack.com/redirect/068c1a39-ff92-4d5b-94fd-c306df8747bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-05 An animated introduction to Fourier Series [ https://substack.com/redirect/8a21e694-c4df-49d0-b461-4f978f7d542d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Outstanding essay and collection of animated explanations (created using p5.js) by Andrei Ciobanu explaining Fourier transforms, starting with circles, pi, radians and building up from there.
I found Fourier stuff only really clicked for me when it was accompanied by clear animated visuals, and these are a beautiful example of those done really well.
Link 2024-06-05 My Twitter thread figuring out the AI features in Microsoft's Recall [ https://substack.com/redirect/8f2ef2c5-e9e1-4601-aab8-cef194edd707?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I posed this question on Twitter about why Microsoft Recall (previously [ https://substack.com/redirect/8d649a9d-ed2d-4393-8ffc-61d0b44d7a9d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) is being described as "AI":
Is it just that the OCR uses a machine learning model, or are there other AI components in the mix here?
I learned that Recall works by taking full desktop screenshots and then applying both OCR and some sort of CLIP-style embeddings model to their content. Both the OCRd text and the vector embeddings are stored in SQLite databases (schema here [ https://substack.com/redirect/ea73909f-c808-4482-9f29-e33ae116d00f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], thanks Daniel Feldman) which can then be used to search your past computer activity both by text but also by semantic vision terms - "blue dress" to find blue dresses in screenshots, for example. The si_diskann_graph table names hint at Microsoft's DiskANN [ https://substack.com/redirect/047847b8-79a6-41ec-aa87-28974a77b403?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] vector indexing library
A Microsoft engineer confirmed on Hacker News [ https://substack.com/redirect/b6513506-1705-4b74-9403-780348a36987?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that Recall uses on-disk vector databases to provide local semantic search for both text and images, and that they aren't using Microsoft's Phi-3 or Phi-3 Vision models. As far as I can tell there's no LLM used by the Recall system at all at the moment, just embeddings.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORFV6TnpZek5USXNJbWxoZENJNk1UY3hOelk0TlRRMU5Td2laWGh3SWpveE56UTVNakl4TkRVMUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEubmI4a3dLTUtYSjdkY01JS2xXa1ptTDdJYTdSaFZVYlk1WFV2a0VNRnhHZyIsInAiOjE0NTM3NjM1MiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzE3Njg1NDU1LCJleHAiOjE3MjAyNzc0NTUsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.qQeDtlm9RO-xJrpoSEbbLC60wWLi-5SELXfOX9h8sZs?
