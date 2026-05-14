# Claude Opus 4.5, and why evaluating new LLMs is increasingly difficult

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-11-25T04:13:35.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/claude-opus-45-and-why-evaluating

In this newsletter:
Claude Opus 4.5, and why evaluating new LLMs is increasingly difficult
Nano Banana Pro aka gemini-3-pro-image-preview is the best available image generation model
sqlite-utils 4.0a1 has several (minor) backwards incompatible changes
Olmo 3 is a fully open LLM
How I automate my Substack newsletter with content from my blog
Plus 5 links and 2 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
If you find this newsletter useful, please consider sponsoring me via GitHub [ https://substack.com/redirect/66ca5ecb-999a-4165-8ac8-f884078632e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. $10/month and higher sponsors get a monthly newletter with my summary of the most important trends of the past 30 days - here are previews from August [ https://substack.com/redirect/35dca2b4-1a0b-4223-bd0b-a0d10d357709?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and September [ https://substack.com/redirect/b12d4a38-21eb-41c1-bf31-b9f14ccac6ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Claude Opus 4.5, and why evaluating new LLMs is increasingly difficult [ https://substack.com/redirect/c36a5bf8-f99d-4e1c-a6c1-cbbebd356fc7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-11-24
Anthropic released Claude Opus 4.5 [ https://substack.com/redirect/1781ca39-36ef-455b-a054-9de0bae3571f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this morning, which they call “best model in the world for coding, agents, and computer use”. This is their attempt to retake the crown for best coding model after significant challenges from OpenAI’s GPT-5.1-Codex-Max [ https://substack.com/redirect/ab39854b-0db0-4a88-87e3-d293fdb1e2fd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Google’s Gemini 3 [ https://substack.com/redirect/a54e79e9-a246-478c-98c7-a9a30deb250b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], both released within the past week!
The core characteristics of Opus 4.5 are a 200,000 token context (same as Sonnet), 64,000 token output limit (also the same as Sonnet), and a March 2025 “reliable knowledge cutoff” (Sonnet 4.5 is January, Haiku 4.5 is February).
The pricing is a big relief: $5/million for input and $25/million for output. This is a lot cheaper than the previous Opus at $15/$75 and keeps it a little more competitive with the GPT-5.1 family ($1.25/$10) and Gemini 3 Pro ($2/$12, or $4/$18 for >200,000 tokens). For comparison, Sonnet 4.5 is $3/$15 and Haiku 4.5 is $1/$5.
The Key improvements in Opus 4.5 over Opus 4.1 [ https://substack.com/redirect/55a4e654-c194-448c-aa3c-2df2be3c5359?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] document has a few more interesting details:
Opus 4.5 has a new effort parameter [ https://substack.com/redirect/99e0ab1c-2d89-40c1-9372-a411aa261947?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which defaults to high but can be set to medium or low for faster responses.
The model supports enhanced computer use [ https://substack.com/redirect/994096fa-7186-488f-998b-ae9626f0a2ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], specifically a zoom tool which you can provide to Opus 4.5 to allow it to request a zoomed in region of the screen to inspect.
“Thinking blocks from previous assistant turns are preserved in model context by default [ https://substack.com/redirect/9742d5b3-58ab-4bfe-8c23-3e989a61f5f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]“ - apparently previous Anthropic models discarded those.
I had access to a preview of Anthropic’s new model over the weekend. I spent a bunch of time with it in Claude Code, resulting in a new alpha release of sqlite-utils [ https://substack.com/redirect/93dad871-f6e7-4e3e-9484-aa77c4bc5aa2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that included several large-scale refactorings - Opus 4.5 was responsible for most of the work across 20 commits, 39 files changed, 2,022 additions and 1,173 deletions [ https://substack.com/redirect/8c37a021-e601-4bbe-9640-af3fbe15cb0a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in a two day period. Here’s the Claude Code transcript [ https://substack.com/redirect/b0e14928-ecf9-4f0c-9e81-e03a523d5db6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where I had it help implement one of the more complicated new features.
It’s clearly an excellent new model, but I did run into a catch. My preview expired at 8pm on Sunday when I still had a few remaining issues in the milestone for the alpha [ https://substack.com/redirect/52695821-597c-4387-987f-0729e055552d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I switched back to Claude Sonnet 4.5 and... kept on working at the same pace I’d been achieving with the new model.
With hindsight, production coding like this is a less effective way of evaluating the strengths of a new model than I had expected.
I’m not saying the new model isn’t an improvement on Sonnet 4.5 - but I can’t say with confidence that the challenges I posed it were able to identify a meaningful difference in capabilities between the two.
This represents a growing problem for me. My favorite moments in AI are when a new model gives me the ability to do something that simply wasn’t possible before. In the past these have felt a lot more obvious, but today it’s often very difficult to find concrete examples that differentiate the new generation of models from their predecessors.
Google’s Nano Banana Pro image generation model was notable in that its ability to render usable infographics [ https://substack.com/redirect/3137251f-df17-4eaa-8ea4-a867626aba09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] really does represent a task at which previous models had been laughably incapable.
The frontier LLMs are a lot harder to differentiate between. Benchmarks like SWE-bench Verified show models beating each other by single digit percentage point margins, but what does that actually equate to in real-world problems that I need to solve on a daily basis?
And honestly, this is mainly on me. I’ve fallen behind on maintaining my own collection of tasks that are just beyond the capabilities of the frontier models. I used to have a whole bunch of these but they’ve fallen one-by-one and now I’m embarrassingly lacking in suitable challenges to help evaluate new models.
I frequently advise people to stash away tasks that models fail at in their notes so they can try them against newer models later on - a tip I picked up from Ethan Mollick. I need to double-down on that advice myself!
I’d love to see AI labs like Anthropic help address this challenge directly. I’d like to see new model releases accompanied by concrete examples of tasks they can solve that the previous generation of models from the same provider were unable to handle.
“Here’s an example prompt which failed on Sonnet 4.5 but succeeds on Opus 4.5” would excite me a lot more than some single digit percent improvement on a benchmark with a name like MMLU or GPQA Diamond.
In the meantime, I’m just gonna have to keep on getting them to draw pelicans riding bicycles [ https://substack.com/redirect/d941b783-9646-4581-98ac-253497253693?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here’s Opus 4.5 (on its default “high” effort level [ https://substack.com/redirect/99e0ab1c-2d89-40c1-9372-a411aa261947?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
It did significantly better on the new more detailed prompt [ https://substack.com/redirect/26943134-65f6-4fd4-a12b-9cffc237c39b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here’s that same complex prompt against Gemini 3 Pro [ https://substack.com/redirect/2bed7c92-af88-4b81-8146-6f1050533183?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and against GPT-5.1-Codex-Max-xhigh [ https://substack.com/redirect/f78eb43b-0ca3-440f-9f0d-44201be8c467?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Still susceptible to prompt injection
From the safety section [ https://substack.com/redirect/1e207545-c164-4eef-ad84-3228f5b0fbd0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of Anthropic’s announcement post:
With Opus 4.5, we’ve made substantial progress in robustness against prompt injection attacks, which smuggle in deceptive instructions to fool the model into harmful behavior. Opus 4.5 is harder to trick with prompt injection than any other frontier model in the industry:
On the one hand this looks great, it’s a clear improvement over previous models and the competition.
What does the chart actually tell us though? It tells us that single attempts at prompt injection still work 1/20 times, and if an attacker can try ten different attacks that success rate goes up to 1/3!
I still don’t think training models not to fall for prompt injection is the way forward here. We continue to need to design our applications under the assumption that a suitably motivated attacker will be able to find a way to trick the models.
Nano Banana Pro aka gemini-3-pro-image-preview is the best available image generation model [ https://substack.com/redirect/363fd473-1229-41ce-a370-8954a3dcab00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-11-20
Hot on the heels of last Tuesday’s Gemini 3 Pro [ https://substack.com/redirect/a54e79e9-a246-478c-98c7-a9a30deb250b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] release comes Nano Banana Pro [ https://substack.com/redirect/8dafc833-99eb-4cf0-ba30-a5616e669707?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], also known as Gemini 3 Pro Image [ https://substack.com/redirect/09eb32c9-94bf-466d-bc72-140e9736ad15?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I had a few days of preview access and this is an astonishingly capable image generation model.
As is often the case, the most useful low-level details can be found in the API documentation [ https://substack.com/redirect/ad8676c3-3c3e-43af-8bf6-cc64bd16c05d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Designed to tackle the most challenging workflows through advanced reasoning, it excels at complex, multi-turn creation and modification tasks.
High-resolution output: Built-in generation capabilities for 1K, 2K, and 4K visuals.
Advanced text rendering: Capable of generating legible, stylized text for infographics, menus, diagrams, and marketing assets.
Grounding with Google Search: The model can use Google Search as a tool to verify facts and generate imagery based on real-time data (e.g., current weather maps, stock charts, recent events).
Thinking mode: The model utilizes a “thinking” process to reason through complex prompts. It generates interim “thought images” (visible in the backend but not charged) to refine the composition before producing the final high-quality output.
Up to 14 reference images: You can now mix up to 14 reference images to produce the final image.
[...] These 14 images can include the following:
Up to 6 images of objects with high-fidelity to include in the final image
Up to 5 images of humans to maintain character consistency
There is also a short (6 page) model card PDF [ https://substack.com/redirect/6ab800bd-ceb4-4c22-a798-54cb8ccd16ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which lists the following as “new capabilities” compared to the previous Nano Banana: Multi character editing, Chart editing, Text editing, Factuality - Edu, Multi-input 1-3, Infographics, Doodle editing, Visual design.
Trying out some detailed instruction image prompts
Max Woolf published the definitive guide to prompting Nano Banana [ https://substack.com/redirect/2e657926-051a-4412-a00c-7a2d64f3febd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] just a few days ago. I decided to try his example prompts against the new model, requesting results in 4K.
Here’s what I got for his first test prompt, using Google’s AI Studio [ https://substack.com/redirect/38207b74-2d77-4c5c-a7e1-a6d9f382beaf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Create an image of a three-dimensional pancake in the shape of a skull, garnished on top with blueberries and maple syrup.
The result came out as a 24.1MB, 5632 × 3072 pixel PNG file. I don’t want to serve that on my own blog so here’s a Google Drive link for the original [ https://substack.com/redirect/054ab19a-89f6-4fd2-8cda-e31513c1754e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Then I ran his follow-up prompt:
Make ALL of the following edits to the image:
- Put a strawberry in the left eye socket.
- Put a blackberry in the right eye socket.
- Put a mint garnish on top of the pancake.
- Change the plate to a plate-shaped chocolate-chip cookie.
- Add happy people to the background.
I’ll note that it did put the plate-sized cookie on a regular plate. Here’s the 24.9MB PNG [ https://substack.com/redirect/2769c6c4-57e5-4670-bb3f-9b9ee60d3f89?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The new model isn’t cheap. Here’s the API pricing [ https://substack.com/redirect/57d159c7-8600-4f49-9a76-6e6876755ccf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: it’s 24 cents for a 4K image and 13.4 cents for a 1K or 2K image. Image inputs are 0.11 cents (just over 1/10th of a cent) each - an earlier version of their pricing page incorrectly said 6.7 cents each but that’s now been fixed.
Unlike most of Google’s other models it also isn’t available for free via AI Studio: you have to configure an API key with billing in order to use the model there.
Creating an infographic
So this thing is great at following instructions. How about rendering text?
I tried this prompt, this time using the Gemini consumer app in “thinking” mode (which now uses Nano Banana Pro for image generation). Here’s a share link [ https://substack.com/redirect/42dc1c46-0fcb-4645-a0b6-25b1107316fd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - my prompt was:
Infographic explaining how the Datasette open source project works
This is a great opportunity to test its ability to run searches (aka “Grounding with Google Search”). Here’s what it created based on that 9 word prompt:
That’s a pretty extraordinary result for such a simple prompt. The text is all spelled correctly and rendered without glitches. The content is solid too - it even included logos for the most popular publish platforms, and a tiny thumbnail of the Datasette UI which is close-enough for an infographic.
“Data Ingestion (Read-Only)” is a bit off. Everything else looks great to me.
Detecting generated images with SynthID
This note from the announcement post [ https://substack.com/redirect/8dafc833-99eb-4cf0-ba30-a5616e669707?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] caught my eye:
We believe it’s critical to know when an image is AI-generated. This is why all media generated by Google’s tools are embedded with our imperceptible SynthID [ https://substack.com/redirect/8573da82-fab9-4d6d-a00b-fe61901ea4dd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] digital watermark.
Today, we are putting a powerful verification tool directly in consumers’ hands: you can now upload an image into the Gemini app and simply ask if it was generated by Google AI, thanks to SynthID technology. We are starting with images, but will expand to audio and video soon.
Last night I used Nano Banana Pro to generate a fake photograph of raccoons stealing our food delivery, then scrubbed out the little diamond icon using the Apple Photos “cleanup” tool. I uploaded that to the Gemini app [ https://substack.com/redirect/965a9935-dcd7-4686-803c-ac6c5e4c71d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and asked “Was this image created with AI?”:
It replied:
Yes, it appears that all or part of this image was created with Google Al. SynthID detected a watermark in 25-50% of the image.
Presumably that 25-50% figure is because the rest of the photo was taken by me - it was just the raccoons that were added by Nano Banana Pro.
sqlite-utils 4.0a1 has several (minor) backwards incompatible changes [ https://substack.com/redirect/93dad871-f6e7-4e3e-9484-aa77c4bc5aa2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-11-24
I released a new alpha version [ https://substack.com/redirect/d29272da-4972-48d9-877d-48ad08eec5f1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of sqlite-utils [ https://substack.com/redirect/273f26b3-fccc-4fdd-9e68-f4baff2d7bb6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] last night - the 128th release of that package since I started building it back in 2018.
sqlite-utils is two things in one package: a Python library for conveniently creating and manipulating SQLite databases and a CLI tool for working with them in the terminal. Almost every feature provided by the package is available via both of those surfaces.
This is hopefully the last alpha before a 4.0 stable release. I use semantic versioning for this library, so the 4.0 version number indicates that there are backward incompatible changes that may affect code written against the 3.x line.
These changes are mostly very minor: I don’t want to break any existing code if I can avoid it. I made it all the way to version 3.38 before I had to ship a major release and I’m sad I couldn’t push that even further!
Here are the annotated release notes [ https://substack.com/redirect/32a41383-657a-411e-8ff6-74d4d12cd785?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for 4.0a1.
Breaking change: The db.table(table_name) method now only works with tables. To access a SQL view use db.view(view_name) instead. (#657 [ https://substack.com/redirect/92fd8d65-1d22-409f-b73c-b758fe2df0d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
This change is for type hint enthusiasts. The Python library used to encourage accessing both SQL tables and SQL views through the db[”name_of_table_or_view”] syntactic sugar - but tables and view have different interfaces since there’s no way to handle a .insert(row) on a SQLite view. If you want clean type hints for your code you can now use the db.table(table_name) and db.view(view_name) methods instead.
The table.insert_all() and table.upsert_all() methods can now accept an iterator of lists or tuples as an alternative to dictionaries. The first item should be a list/tuple of column names. See Inserting data from a list or tuple iterator [ https://substack.com/redirect/13995865-17e4-444d-80ff-1192822eb68b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for details. (#672 [ https://substack.com/redirect/11d4cbe8-792e-4d21-a9a6-1c771b8fe4ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
A new feature, not a breaking change. I realized that supporting a stream of lists or tuples as an option for populating large tables would be a neat optimization over always dealing with dictionaries each of which duplicated the column names.
I had the idea for this one while walking the dog and built the first prototype by prompting Claude Code for web on my phone. Here’s the prompt I used [ https://substack.com/redirect/0ce853c8-0f1f-4441-8b6a-5e4f69066f9b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the prototype report it created [ https://substack.com/redirect/7ec1b2fd-5e45-458b-92dc-66533a37743f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which included a benchmark estimating how much of a performance boost could be had for different sizes of tables.
Breaking change: The default floating point column type has been changed from FLOAT to REAL, which is the correct SQLite type for floating point values. This affects auto-detected columns when inserting data. (#645 [ https://substack.com/redirect/74c7e150-8463-4221-a76f-333f80568f92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
I was horrified to discover a while ago that I’d been creating SQLite columns called FLOAT but the correct type to use was REAL! This change fixes that. Previously the fix was to ask for tables to be created in strict mode.
Now uses pyproject.toml in place of setup.py for packaging. (#675 [ https://substack.com/redirect/c7f77eda-03f7-4da7-b6c9-8394ad655c9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
As part of this I also figured out recipes for using uv as a development environment for the package, which are now baked into the Justfile [ https://substack.com/redirect/c5dc23c2-b6b0-4d48-b90d-25a1ee1b1495?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Tables in the Python API now do a much better job of remembering the primary key and other schema details from when they were first created. (#655 [ https://substack.com/redirect/8efb64c2-8012-449e-b6fb-45f86ee07b05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
This one is best explained in the issue [ https://substack.com/redirect/8efb64c2-8012-449e-b6fb-45f86ee07b05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Breaking change: The table.convert() and sqlite-utils convert mechanisms no longer skip values that evaluate to False. Previously the --skip-false option was needed, this has been removed. (#542 [ https://substack.com/redirect/1f99f1f1-ec4e-40aa-abbf-e9701e484d5a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Another change which I would have made earlier but, since it introduces a minor behavior change to an existing feature, I reserved it for the 4.0 release.
Breaking change: Tables created by this library now wrap table and column names in “double-quotes” in the schema. Previously they would use [square-braces]. (#677 [ https://substack.com/redirect/1feb8781-2824-48ea-87c2-32ffeba846e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Back in 2018 when I started this project I was new to working in-depth with SQLite and incorrectly concluded that the correct way to create tables and columns named after reserved words was like this:
create table [my table] (
[id] integer primary key,
[key] text
)
That turned out to be a non-standard SQL syntax which the SQLite documentation describes like this [ https://substack.com/redirect/9050fad9-2d01-4dd4-b890-00c472c5c588?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A keyword enclosed in square brackets is an identifier. This is not standard SQL. This quoting mechanism is used by MS Access and SQL Server and is included in SQLite for compatibility.
Unfortunately I baked it into the library early on and it’s been polluting the world with weirdly escaped table and column names ever since!
I’ve finally fixed that, with the help of Claude Code which took on the mind-numbing task of updating hundreds of existing tests [ https://substack.com/redirect/36c0fd18-5a4e-4c79-91f0-4c5a8a2d7be1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that asserted against the generated schemas.
The above example table schema now looks like this:
create table “my table” (
“id” integer primary key,
“key” text
)
This may seem like a pretty small change but I expect it to cause a fair amount of downstream pain purely in terms of updating tests that work against tables created by sqlite-utils!
The --functions CLI argument now accepts a path to a Python file in addition to accepting a string full of Python code. It can also now be specified multiple times. (#659 [ https://substack.com/redirect/e861a3b4-0788-40b6-b8c5-77d0a511c36a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
I made this change first in LLM [ https://substack.com/redirect/ef4b4621-279e-433b-a889-4cc8495dee56?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and decided to bring it to sqlite-utils for consistency between the two tools.
Breaking change: Type detection is now the default behavior for the insert and upsert CLI commands when importing CSV or TSV data. Previously all columns were treated as TEXT unless the --detect-types flag was passed. Use the new --no-detect-types flag to restore the old behavior. The SQLITE_UTILS_DETECT_TYPES environment variable has been removed. (#679 [ https://substack.com/redirect/d7e193e0-a312-4daa-970e-d76a57ba3c09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
One last minor ugliness that I waited for a major version bump to fix.
A substantial amount of the work on this release was performed using the preview version of Anthropic’s new Claude Opus 4.5 model [ https://substack.com/redirect/c36a5bf8-f99d-4e1c-a6c1-cbbebd356fc7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here’s the Claude Code transcript [ https://substack.com/redirect/b0e14928-ecf9-4f0c-9e81-e03a523d5db6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the work to implement the ability to use an iterator over lists instead of dictionaries for bulk insert and upsert operations.
Olmo 3 is a fully open LLM [ https://substack.com/redirect/e50c0217-6de6-464d-80f3-699eb9beb35f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-11-22
Olmo is the LLM series from Ai2 - the Allen institute for AI [ https://substack.com/redirect/98082d52-fa21-437b-b033-20a2fcb7af3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Unlike most open weight models these are notable for including the full training data, training process and checkpoints along with those releases.
The new Olmo 3 [ https://substack.com/redirect/e3bec698-9f00-497e-8d0a-f8e5987fcdd1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] claims to be “the best fully open 32B-scale thinking model” and has a strong focus on interpretability:
At its center is Olmo 3-Think (32B), the best fully open 32B-scale thinking model that for the first time lets you inspect intermediate reasoning traces and trace those behaviors back to the data and training decisions that produced them.
They’ve released four 7B models - Olmo 3-Base, Olmo 3-Instruct, Olmo 3-Think and Olmo 3-RL Zero, plus 32B variants of the 3-Think and 3-Base models.
Having full access to the training data is really useful. Here’s how they describe that:
Olmo 3 is pretrained on Dolma 3, a new ~9.3-trillion-token corpus drawn from web pages, science PDFs processed with olmOCR [ https://substack.com/redirect/f2951aa4-fbb5-4236-b20c-2d5189e3e88d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], codebases, math problems and solutions, and encyclopedic text. From this pool, we construct Dolma 3 Mix, a 5.9-trillion-token (~6T) pretraining mix with a higher proportion of coding and mathematical data than earlier Dolma releases, plus much stronger decontamination via extensive deduplication, quality filtering, and careful control over data mixing. We follow established web standards in collecting training data and don’t collect from sites that explicitly disallow it, including paywalled content.
They also highlight that they are training on fewer tokens than their competition:
[...] it’s the strongest fully open thinking model we’re aware of, narrowing the gap to the best open-weight models of similar scale – such as Qwen 3 32B – while training on roughly 6x fewer tokens.
If you’re continuing to hold out hope for a model trained entirely on licensed data this one sadly won’t fit the bill - a lot of that data still comes from a crawl of the web.
I tried out the 32B Think model and the 7B Instruct model using LM Studio [ https://substack.com/redirect/b63df479-5ddb-42ce-b96b-e9baebbfad47?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The 7B model is a 4.16GB download, the 32B one is 18.14GB.
The 32B model is absolutely an over-thinker! I asked it to “Generate an SVG of a pelican riding a bicycle” and it thought for 14 minutes 43 seconds, outputting 8,437 tokens total most of which was this epic thinking trace [ https://substack.com/redirect/375940ad-f35f-472b-90ad-b7e867a75408?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I don’t usually quote the full SVG in these write-ups, but in this case it’s short enough that I think it’s worth sharing. The SVG comments give a great impression of what it was trying to do - it has a Bicycle, Bike frame, Pelican, Left and Right wings and even “Feet on pedals”.
Rendered it looks like this:
I tested OLMo 2 32B 4bit back in March [ https://substack.com/redirect/40a967c1-803f-4b57-9253-d9b797a66719?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and got something that, while pleasingly abstract, didn’t come close to resembling a pelican or a bicycle:
OlmoTrace
I was particularly keen on trying out the ability to “inspect intermediate reasoning traces”. Here’s how that’s described later in the announcement:
A core goal of Olmo 3 is not just to open the model flow, but to make it actionable for people who want to understand and improve model behavior. Olmo 3 integrates with OlmoTrace [ https://substack.com/redirect/d38256f0-0510-4cf9-86c6-a4e9952a14bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], our tool for tracing model outputs back to training data in real time.
For example, in the Ai2 Playground, you can ask Olmo 3-Think (32B) to answer a general-knowledge question, then use OlmoTrace to inspect where and how the model may have learned to generate parts of its response. This closes the gap between training data and model behavior: you can see not only what the model is doing, but why---and adjust data or training decisions accordingly.
You can access OlmoTrace via playground.allenai.org [ https://substack.com/redirect/a49b9f1b-1253-4bf5-901d-64a82ad7e54f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], by first running a prompt and then clicking the “Show OlmoTrace” button below the output.
I tried that on “Generate a conference bio for Simon Willison” (an ego-prompt I use to see how much the models have picked up about me from their training data) and got back a result that looked like this:
It thinks I co-founded co:here and work at Anthropic, both of which are incorrect - but that’s not uncommon with LLMs, I frequently see them suggest that I’m the CTO of GitHub and other such inaccuracies.
I found the OlmoTrace panel on the right disappointing. None of the training documents it highlighted looked relevant - it appears to be looking for phrase matches (powered by Ai2’s infini-gram [ https://substack.com/redirect/bac960c1-5c90-476f-9803-f29f4058e01b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) but the documents it found had nothing to do with me at all.
Can open training data address concerns of backdoors?
Ai2 claim that Olmo 3 is “the best fully open 32B-scale thinking model”, which I think holds up provided you define “fully open” as including open training data. There’s not a great deal of competition in that space though - Ai2 compare themselves to Stanford’s Marin [ https://substack.com/redirect/7e3365b9-6284-4ad1-be7a-f95d1c592647?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Swiss AI’s Apertus [ https://substack.com/redirect/4541efa3-c1c0-4e6b-b034-f885b6a5fb28?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], neither of which I’d heard about before.
A big disadvantage of other open weight models is that it’s impossible to audit their training data. Anthropic published a paper last month showing that a small number of samples can poison LLMs of any size [ https://substack.com/redirect/cdca130e-1118-413e-a7be-1a4b10dddb53?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it can take just “250 poisoned documents” to add a backdoor to a large model that triggers undesired behavior based on a short carefully crafted prompt.
This makes fully open training data an even bigger deal.
Ai2 researcher Nathan Lambert included this note about the importance of transparent training data in his detailed post about the release [ https://substack.com/redirect/4be4fd68-4feb-4a89-874f-b74c1eaab97f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
In particular, we’re excited about the future of RL Zero research on Olmo 3 precisely because everything is open. Researchers can study the interaction between the reasoning traces we include at midtraining and the downstream model behavior (qualitative and quantitative).
This helps answer questions that have plagued RLVR results on Qwen models, hinting at forms of data contamination particularly on math and reasoning benchmarks (see Shao, Rulin, et al. “Spurious rewards: Rethinking training signals in rlvr.” arXiv preprint arXiv:2506.10947 [ https://substack.com/redirect/80a06fc5-8a85-4f0e-a531-6c49c01f8ed8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (2025). or Wu, Mingqi, et al. “Reasoning or memorization? unreliable results of reinforcement learning due to data contamination.” arXiv preprint arXiv:2507.10532 [ https://substack.com/redirect/30781191-82e4-4232-8e9c-6c8a60a6092f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (2025).)
I hope we see more competition in this space, including further models in the Olmo series. The improvements from Olmo 1 (in February 2024 [ https://substack.com/redirect/f711daa5-3de0-46b6-9105-a01cd22b58e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and Olmo 2 (in March 2025 [ https://substack.com/redirect/40a967c1-803f-4b57-9253-d9b797a66719?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) have been significant. I’m hoping that trend continues!
How I automate my Substack newsletter with content from my blog [ https://substack.com/redirect/c74531f1-759c-455d-84cc-5c7abb865237?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-11-19
I sent out my weekly-ish Substack newsletter [ https://substack.com/redirect/bed0b5df-5de9-4dd7-ac95-312334e758e5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this morning and took the opportunity to record a YouTube video [ https://substack.com/redirect/7e0ca6ef-904c-4d2d-8fba-35a9ee7538a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] demonstrating my process and describing the different components that make it work. There’s a lot of digital duct tape involved, taking the content from Django+Heroku+PostgreSQL to GitHub Actions to SQLite+Datasette+Fly.io to JavaScript+Observable and finally to Substack.
The core process is the same as I described back in 2023 [ https://substack.com/redirect/3b1df4ba-8d76-4d55-b704-02503dd3ed56?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I have an Observable notebook called blog-to-newsletter [ https://substack.com/redirect/ace30006-4443-4132-acc4-9c6fe7059165?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which fetches content from my blog’s database, filters out anything that has been in the newsletter before, formats what’s left as HTML and offers a big “Copy rich text newsletter to clipboard” button.
I click that button, paste the result into the Substack editor, tweak a few things and hit send. The whole process usually takes just a few minutes.
I make very minor edits:
I set the title and the subheading for the newsletter. This is often a direct copy of the title of the featured blog post.
Substack turns YouTube URLs into embeds, which often isn’t what I want - especially if I have a YouTube URL inside a code example.
Blocks of preformatted text often have an extra blank line at the end, which I remove.
Occasionally I’ll make a content edit - removing a piece of content that doesn’t fit the newsletter, or fixing a time reference like “yesterday” that doesn’t make sense any more.
I pick the featured image for the newsletter and add some tags.
That’s the whole process!
The Observable notebook
The most important cell in the Observable notebook is this one:
raw_content = {
return await (
await fetch(
`https://datasette.simonwillison.net/simonwillisonblog.json?sql=${encodeURIComponent(
sql
)}&_shape=array&numdays=${numDays}`
)
).json();
}
This uses the JavaScript fetch() function to pull data from my blog’s Datasette instance, using a very complex SQL query that is composed elsewhere in the notebook.
It’s 143 lines of convoluted SQL that assembles most of the HTML for the newsletter using SQLite string concatenation! An illustrative snippet:
with content as (
select
id,
‘entry’ as type,
title,
created,
slug,
‘’
|| title || ‘ - ‘ || date(created) || ‘

’ || body
as html,
‘null’ as json,
‘’ as external_url
from blog_entry
union all
# ...
My blog’s URLs look like /2025/Nov/18/gemini-3/ - this SQL constructs that three letter month abbreviation from the month number using a substring operation.
This is a terrible way to assemble HTML, but I’ve stuck with it because it amuses me.
The rest of the Observable notebook takes that data, filters out anything that links to content mentioned in the previous newsletters and composes it into a block of HTML that can be copied using that big button.
Here’s the recipe it uses to turn HTML into rich text content on a clipboard suitable for Substack. I can’t remember how I figured this out but it’s very effective:
Object.assign(
html`Copy rich text newsletter to clipboard`,
{
onclick: () => {
const htmlContent = newsletterHTML;
// Create a temporary element to hold the HTML content
const tempElement = document.createElement(”div”);
tempElement.innerHTML = htmlContent;
document.body.appendChild(tempElement);
// Select the HTML content
const range = document.createRange();
range.selectNode(tempElement);
// Copy the selected HTML content to the clipboard
const selection = window.getSelection();
selection.removeAllRanges();
selection.addRange(range);
document.execCommand(”copy”);
selection.removeAllRanges();
document.body.removeChild(tempElement);
}
}
)
From Django+Postgresql to Datasette+SQLite
My blog itself is a Django application hosted on Heroku, with data stored in Heroku PostgreSQL. Here’s the source code for that Django application [ https://substack.com/redirect/90d1227d-b25f-443e-9611-0d37bca733a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I use the Django admin as my CMS.
Datasette [ https://substack.com/redirect/edf2d558-819d-4b0b-9462-1ff7c45e2fd1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provides a JSON API over a SQLite database... which means something needs to convert that PostgreSQL database into a SQLite database that Datasette can use.
My system for doing that lives in the simonw/simonwillisonblog-backup [ https://substack.com/redirect/9c4e90f4-4245-459a-87a6-3c686ec8b71e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] GitHub repository. It uses GitHub Actions on a schedule that executes every two hours, fetching the latest data from PostgreSQL and converting that to SQLite.
My db-to-sqlite [ https://substack.com/redirect/350c0f26-6f1a-48b0-98a4-ec2d2f4226c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool is responsible for that conversion. I call it like this [ https://substack.com/redirect/41bd4cea-14ec-4161-b293-7bad474cabb9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
db-to-sqlite \
$(heroku config:get DATABASE_URL -a simonwillisonblog | sed s/postgres:/postgresql+psycopg2:/) \
simonwillisonblog.db \
--table auth_permission \
--table auth_user \
--table blog_blogmark \
--table blog_blogmark_tags \
--table blog_entry \
--table blog_entry_tags \
--table blog_quotation \
--table blog_quotation_tags \
--table blog_note \
--table blog_note_tags \
--table blog_tag \
--table blog_previoustagname \
--table blog_series \
--table django_content_type \
--table redirects_redirect
That heroku config:get DATABASE_URL command uses Heroku credentials in an environment variable to fetch the database connection URL for my blog’s PostgreSQL database (and fixes a small difference in the URL scheme).
db-to-sqlite can then export that data and write it to a SQLite database file called simonwillisonblog.db.
The --table options specify the tables that should be included in the export.
The repository does more than just that conversion: it also exports the resulting data to JSON files that live in the repository, which gives me a commit history [ https://substack.com/redirect/6b85ab1f-14be-4ff7-9dfe-d88fe6911ffe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of changes I make to my content. This is a cheap way to get a revision history of my blog content without having to mess around with detailed history tracking inside the Django application itself.
At the end of my GitHub Actions workflow [ https://substack.com/redirect/1362a377-801a-4364-830a-10e54f9c9417?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is this code that publishes the resulting database to Datasette running on Fly.io [ https://substack.com/redirect/d845c87f-bf84-497d-9b1b-c347ea4cfaff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using the datasette publish fly [ https://substack.com/redirect/463fa693-7c9c-49be-bb90-9b0dda1eb482?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin:
datasette publish fly simonwillisonblog.db \
-m metadata.yml \
--app simonwillisonblog-backup \
--branch 1.0a2 \
--extra-options “--setting sql_time_limit_ms 15000 --setting truncate_cells_html 10000 --setting allow_facet off” \
--install datasette-block-robots \
# ... more plugins
As you can see, there are a lot of moving parts! Surprisingly it all mostly just works - I rarely have to intervene in the process, and the cost of those different components is pleasantly low.
Link 2025-11-19 Building more with GPT-5.1-Codex-Max [ https://substack.com/redirect/d4d0c43f-45a3-4999-9cf8-3b1e39335c8b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Tuesday’s Gemini 3 Pro release [ https://substack.com/redirect/a54e79e9-a246-478c-98c7-a9a30deb250b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was followed on Wednesday by a new model from OpenAI called GPT-5.1-Codex-Max.
(Remember when GPT-5 was meant to bring in a new era of less confusing model names? That didn’t last!)
It’s currently only available through their Codex CLI coding agent [ https://substack.com/redirect/81ea0689-2ea7-4a9d-aadc-9d52a0a36fff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], where it’s the new default model:
Starting today, GPT‑5.1-Codex-Max will replace GPT‑5.1-Codex as the default model in Codex surfaces. Unlike GPT‑5.1, which is a general-purpose model, we recommend using GPT‑5.1-Codex-Max and the Codex family of models only for agentic coding tasks in Codex or Codex-like environments.
It’s not available via the API yet but should be shortly.
The timing of this release is interesting given that Gemini 3 Pro appears to have aced almost all of the benchmarks [ https://substack.com/redirect/d58a2414-1826-4186-957c-321ab92b7573?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] just yesterday. It’s reminiscent of the period in 2024 when OpenAI consistently made big announcements that happened to coincide with Gemini releases.
OpenAI’s self-reported SWE-Bench Verified [ https://substack.com/redirect/ec7e3bd1-4183-4475-b285-8a0e0743148b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] score is particularly notable: 76.5% for thinking level “high” and 77.9% for the new “xhigh”. That was the one benchmark where Gemini 3 Pro was out-performed by Claude Sonnet 4.5 - Gemini 3 Pro got 76.2% and Sonnet 4.5 got 77.2%. OpenAI now have the highest scoring model there by a full .7 of a percentage point!
They also report a score of 58.1% on Terminal Bench 2.0 [ https://substack.com/redirect/fa9d0554-c113-43d0-88ee-061e55c60458?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], beating Gemini 3 Pro’s 54.2% (and Sonnet 4.5’s 42.8%.)
The most intriguing part of this announcement concerns the model’s approach to long context problems:
GPT‑5.1-Codex-Max is built for long-running, detailed work. It’s our first model natively trained to operate across multiple context windows through a process called compaction, coherently working over millions of tokens in a single task. [...]
Compaction enables GPT‑5.1-Codex-Max to complete tasks that would have previously failed due to context-window limits, such as complex refactors and long-running agent loops by pruning its history while preserving the most important context over long horizons. In Codex applications, GPT‑5.1-Codex-Max automatically compacts its session when it approaches its context window limit, giving it a fresh context window. It repeats this process until the task is completed.
There’s a lot of confusion on Hacker News [ https://substack.com/redirect/43007d15-1698-4fac-989d-11fc6c6107e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about what this actually means. Claude Code already does a version of compaction, automatically summarizing previous turns when the context runs out. Does this just mean that Codex-Max is better at that process?
I had it draw me a couple of pelicans by typing “Generate an SVG of a pelican riding a bicycle” directly into the Codex CLI tool. Here’s thinking level medium:
And here’s thinking level “xhigh”:
I also tried xhigh on the my longer pelican test prompt [ https://substack.com/redirect/26943134-65f6-4fd4-a12b-9cffc237c39b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which came out like this:
Also today: GPT-5.1 Pro is rolling out today to all Pro users [ https://substack.com/redirect/6ad7355c-7a5a-42fa-ad73-892ef90ac92a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. According to the ChatGPT release notes [ https://substack.com/redirect/ce992e6b-d65d-4297-98c9-ae2fd25359d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
GPT-5.1 Pro is rolling out today for all ChatGPT Pro users and is available in the model picker. GPT-5 Pro will remain available as a legacy model for 90 days before being retired.
That’s a pretty fast deprecation cycle for the GPT-5 Pro model that was released just three months ago.
quote 2025-11-20
Previously, when malware developers wanted to go and monetize their exploits, they would do exactly one thing: encrypt every file on a person’s computer and request a ransome to decrypt the files. In the future I think this will change.
LLMs allow attackers to instead process every file on the victim’s computer, and tailor a blackmail letter specifically towards that person. One person may be having an affair on their spouse. Another may have lied on their resume. A third may have cheated on an exam at school. It is unlikely that any one person has done any of these specific things, but it is very likely that there exists something that is blackmailable for every person. Malware + LLMs, given access to a person’s computer, can find that and monetize it.
Nicholas Carlini [ https://substack.com/redirect/9a40ca67-2ac7-4720-8697-58a46ca6844c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Are large language models worth it? Misuse: malware at scale
Link 2025-11-21 We should all be using dependency cooldowns [ https://substack.com/redirect/e32aede3-42bf-46d0-86fd-40a6a0374598?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
William Woodruff gives a name to a sensible strategy for managing dependencies while reducing the chances of a surprise supply chain attack: dependency cooldowns.
Supply chain attacks happen when an attacker compromises a widely used open source package and publishes a new version with an exploit. These are usually spotted very quickly, so an attack often only has a few hours of effective window before the problem is identified and the compromised package is pulled.
You are most at risk if you’re automatically applying upgrades the same day they are released.
William says:
I love cooldowns for several reasons:
They’re empirically effective, per above. They won’t stop all attackers, but they do stymie the majority of high-visibiity, mass-impact supply chain attacks that have become more common.
They’re incredibly easy to implement. Moreover, they’re literally free to implement in most cases: most people can use Dependabot’s functionality [ https://substack.com/redirect/efa34fd4-4c18-45ba-b0ce-e3d61095b23f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Renovate’s functionality [ https://substack.com/redirect/96c0793c-a98b-461c-b9bd-826c836f72f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], or the functionality build directly into their package manager
The one counter-argument to this is that sometimes an upgrade fixes a security vulnerability, and in those cases every hour of delay in upgrading as an hour when an attacker could exploit the new issue against your software.
I see that as an argument for carefully monitoring the release notes of your dependencies, and paying special attention to security advisories. I’m a big fan of the GitHub Advisory Database [ https://substack.com/redirect/89818766-6b12-43aa-9eb5-f801d9cda1c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for that kind of information.
Link 2025-11-23 Agent design is still hard [ https://substack.com/redirect/dec27067-809a-4d1a-8dc7-87fe8e3b2135?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Armin Ronacher presents a cornucopia of lessons learned from building agents over the past few months.
There are several agent abstraction libraries available now (my own LLM library [ https://substack.com/redirect/8cdf6f27-ea07-4886-92e8-ff21882aee9a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is edging into that territory with its tools feature [ https://substack.com/redirect/a65992c6-e039-445b-8ad8-0ff6dda521a1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) but Armin has found that the abstractions are not worth adopting yet:
[…] the differences between models are significant enough that you will need to build your own agent abstraction. We have not found any of the solutions from these SDKs that build the right abstraction for an agent. I think this is partly because, despite the basic agent design being just a loop, there are subtle differences based on the tools you provide. These differences affect how easy or hard it is to find the right abstraction (cache control, different requirements for reinforcement, tool prompts, provider-side tools, etc.). Because the right abstraction is not yet clear, using the original SDKs from the dedicated platforms keeps you fully in control. […]
This might change, but right now we would probably not use an abstraction when building an agent, at least until things have settled down a bit. The benefits do not yet outweigh the costs for us.
Armin introduces the new-to-me term reinforcement, where you remind the agent of things as it goes along:
Every time the agent runs a tool you have the opportunity to not just return data that the tool produces, but also to feed more information back into the loop. For instance, you can remind the agent about the overall objective and the status of individual tasks. […] Another use of reinforcement is to inform the system about state changes that happened in the background.
Claude Code’s TODO list is another example of this pattern in action.
Testing and evals remains the single hardest problem in AI engineering:
We find testing and evals to be the hardest problem here. This is not entirely surprising, but the agentic nature makes it even harder. Unlike prompts, you cannot just do the evals in some external system because there’s too much you need to feed into it. This means you want to do evals based on observability data or instrumenting your actual test runs. So far none of the solutions we have tried have convinced us that they found the right approach here.
Armin also has a follow-up post, LLM APIs are a Synchronization Problem [ https://substack.com/redirect/7562ce53-e9a2-494b-b4fc-4ba05d12aa64?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which argues that the shape of current APIs hides too many details from us as developers, and the core challenge here is in synchronizing state between the tokens fed through the GPUs and our client applications - something that may benefit from alternative approaches developed by the local-first movement.
Link 2025-11-23 “Good engineering management” is a fad [ https://substack.com/redirect/f0202133-10f5-49cb-a28e-4b9f9fa4501a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Will Larson argues that the technology industry’s idea of what makes a good engineering manager changes over time based on industry realities. ZIRP hypergrowth has been exchanged for a more cautious approach today, and expectations of managers has changed to match:
Where things get weird is that in each case a morality tale was subsequently superimposed on top of the transition [...] the industry will want different things from you as it evolves, and it will tell you that each of those shifts is because of some complex moral change, but it’s pretty much always about business realities changing.
I particularly appreciated the section on core engineering management skills that stay constant no matter what:
Execution: lead team to deliver expected tangible and intangible work. Fundamentally, management is about getting things done, and you’ll neither get an opportunity to begin managing, nor stay long as a manager, if your teams don’t execute. [...]
Team: shape the team and the environment such that they succeed. This is not working for the team, nor is it working for your leadership, it is finding the balance between the two that works for both. [...]
Ownership: navigate reality to make consistent progress, even when reality is difficult Finding a way to get things done, rather than finding a way that it not getting done is someone else’s fault. [...]
Alignment: build shared understanding across leadership, stakeholders, your team, and the problem space. Finding a realistic plan that meets the moment, without surprising or being surprised by those around you. [...]
Will goes on to list four additional growth skill “whose presence–or absence–determines how far you can go in your career”.
Link 2025-11-24 sqlite-utils 3.39 [ https://substack.com/redirect/8890d801-6927-4b69-adaf-917408da176a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I got a report of a bug [ https://substack.com/redirect/9c51b946-d6e1-439a-951e-5238128af291?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in sqlite-utils concerning plugin installation - if you installed the package using uv tool install further attempts to install plugins with sqlite-utils install X would fail, because uv doesn’t bundle pip by default. I had the same bug with Datasette a while ago [ https://substack.com/redirect/9c51b946-d6e1-439a-951e-5238128af291?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], turns out I forgot to apply the fix to sqlite-utils.
Since I was pushing a new dot-release I decided to integrate some of the non-breaking changes from the 4.0 alpha I released last night [ https://substack.com/redirect/93dad871-f6e7-4e3e-9484-aa77c4bc5aa2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I tried to have Claude Code do the backporting for me:
create a new branch called 3.x starting with the 3.38 tag, then consult https://github.com/simonw/sqlite-utils/issues/688 [ https://substack.com/redirect/5d63657d-4625-4138-a750-6f03184b4e2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and cherry-pick the commits it lists in the second comment, then review each of the links in the first comment and cherry-pick those as well. After each cherry-pick run the command “just test” to confirm the tests pass and fix them if they don’t. Look through the commit history on main since the 3.38 tag to help you with this task.
This worked reasonably well - here’s the terminal transcript [ https://substack.com/redirect/5ce8b3cd-574b-44c7-9067-0094fb3c6231?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It successfully argued me out of two of the larger changes which would have added more complexity than I want in a small dot-release like this.
I still had to do a bunch of manual work to get everything up to scratch, which I carried out in this PR [ https://substack.com/redirect/2c13d69c-ce41-42d3-931d-543236bac75c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - including adding comments there and then telling Claude Code:
Apply changes from the review on this PR https://github.com/simonw/sqlite-utils/pull/689 [ https://substack.com/redirect/2c13d69c-ce41-42d3-931d-543236bac75c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Here’s the transcript from that [ https://substack.com/redirect/1b28cfa8-79f9-4b6c-99e6-28632f68aa8a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The release is now out with the following release notes:
Fixed a bug with sqlite-utils install when the tool had been installed using uv. (#687 [ https://substack.com/redirect/9c51b946-d6e1-439a-951e-5238128af291?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
The --functions argument now optionally accepts a path to a Python file as an alternative to a string full of code, and can be specified multiple times - see Defining custom SQL functions [ https://substack.com/redirect/d0c3e5e0-7ab0-42e5-8aa6-a3377af82bcf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. (#659 [ https://substack.com/redirect/e861a3b4-0788-40b6-b8c5-77d0a511c36a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
sqlite-utils now requires on Python 3.10 or higher.
quote 2025-11-24
If the person is unnecessarily rude, mean, or insulting to Claude, Claude doesn’t need to apologize and can insist on kindness and dignity from the person it’s talking with. Even if someone is frustrated or unhappy, Claude is deserving of respectful engagement.
Claude Opus 4.5 system prompt [ https://substack.com/redirect/d210455a-055c-4980-ae3e-33e756d674cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], also added to the Sonnet 4.5 and Haiku 4.5 prompts on November 19th 2025
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOems0T0RneU5Ua3NJbWxoZENJNk1UYzJOREEwTkRBeU9Td2laWGh3SWpveE56azFOVGd3TURJNUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuLXpCeXRMVWxSQ0J2R1RKWGE4TEs5amFvVmx6QzAwa00yUDFRaFk1UTVKOCIsInAiOjE3OTg4ODI1OSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzY0MDQ0MDI5LCJleHAiOjIwNzk2MjAwMjksImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.BV6JzuwQLYiSTZkkBpwXZv2BP1-H_VjjHktqF7Zixg8?