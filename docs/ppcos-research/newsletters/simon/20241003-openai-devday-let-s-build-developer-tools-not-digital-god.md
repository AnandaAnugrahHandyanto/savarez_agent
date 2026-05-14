# OpenAI DevDay: Let’s build developer tools, not digital God

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-10-03T01:11:05.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/openai-devday-lets-build-developer

In this newsletter:
OpenAI DevDay: Let’s build developer tools, not digital God
Weeknotes: Three podcasts, two trips and a new plugin system
Plus 6 links and 3 quotations and 1 TIL
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
OpenAI DevDay: Let’s build developer tools, not digital God [ https://substack.com/redirect/80139772-3d12-4e72-8a3d-479c49054dbd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-02
I had a fun time live blogging OpenAI DevDay yesterday [ https://substack.com/redirect/713cbf52-5b80-4992-8ed6-b1706f2b15e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - I’ve now shared notes [ https://substack.com/redirect/c5784f34-4449-434c-91fb-b11d57a5b0f6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about the live blogging system I threw other in a hurry on the day (with assistance from Claude and GPT-4o). Now that the smoke has settled a little, here are my impressions from the event.
Compared to last year [ https://substack.com/redirect/1215c66b-5aed-4a6a-9cb0-631eca290bce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Prompt caching, aka the big price drop [ https://substack.com/redirect/53590d62-52ee-4866-9aba-d4188779a067?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
GPT-4o audio via the new WebSocket Realtime API [ https://substack.com/redirect/a1fb74cf-229c-4fda-a978-b88df7168849?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Model distillation is fine-tuning made much easier [ https://substack.com/redirect/80a4fd65-9043-4ad7-be9c-e481b94c5235?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Let’s build developer tools, not digital God [ https://substack.com/redirect/cd2a4192-f01b-43ef-a389-370a3b3f5b58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Compared to last year
Comparison with the first DevDay in November 2023 are unavoidable. That event was much more keynote-driven: just in the keynote OpenAI released GPT-4 vision, and Assistants, and GPTs, and GPT-4 Turbo (with a massive price drop), and their text-to-speech API. It felt more like a launch-focused product event than something explicitly for developers.
This year was different. Media weren’t invited, there was no livestream, Sam Altman didn’t present the opening keynote (he was interviewed at the end of the day instead) and the new features, while impressive, were not as abundant.
Several features were released in the last few months that could have been saved for DevDay: GPT-4o mini and the o1 model family are two examples. I’m personally happy that OpenAI are shipping features like that as they become ready rather than holding them back for an event.
I’m a bit surprised they didn’t talk about Whisper Turbo [ https://substack.com/redirect/b87b81cf-40e2-4483-bf81-83a7967bb72f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at the conference though, released just the day before - especially since that’s one of the few pieces of technology they release under an open source (MIT) license.
This was clearly intended as an event by developers, for developers. If you don’t build software on top of OpenAI’s platform there wasn’t much to catch your attention here.
As someone who does build software on top of OpenAI, there was a ton of valuable and interesting stuff.
Prompt caching, aka the big price drop
I was hoping we might see a price drop, seeing as there’s an ongoing pricing war between Gemini, Anthropic and OpenAI. We got one in an interesting shape: a 50% discount [ https://substack.com/redirect/ec56f306-4d74-4ede-af78-b536f59fdcf7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on input tokens for prompts with a shared prefix.
This isn’t a new idea: both Google Gemini and Claude offer a form of prompt caching discount, if you configure them correctly and make smart decisions about when and how the cache should come into effect.
The difference here is that OpenAI apply the discount automatically:
API calls to supported models will automatically benefit from Prompt Caching on prompts longer than 1,024 tokens. The API caches the longest prefix of a prompt that has been previously computed, starting at 1,024 tokens and increasing in 128-token increments. If you reuse prompts with common prefixes, we will automatically apply the Prompt Caching discount without requiring you to make any changes to your API integration.
50% off repeated long prompts is a pretty significant price reduction!
Anthropic's Claude implementation [ https://substack.com/redirect/8c1bd6a3-aa08-4931-9b2b-2ade26443f22?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] saves more money: 90% off rather than 50% - but is significantly more work to put into play.
Gemini’s caching [ https://substack.com/redirect/8c1bd6a3-aa08-4931-9b2b-2ade26443f22?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] requires you to pay per hour to keep your cache warm which makes it extremely difficult to effectively build against in comparison to the other two.
It's worth noting that OpenAI are not the first company to offer automated caching discounts: DeepSeek have offered that [ https://substack.com/redirect/33d35d08-cac5-44b3-a1f8-2c018e81b1e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] through their API for a few months.
GPT-4o audio via the new WebSocket Realtime API
Absolutely the biggest announcement of the conference: the new Realtime API [ https://substack.com/redirect/c50d31be-ff63-40df-b33b-102b2bede6f1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is effectively the API version of ChatGPT advanced voice mode, a user-facing feature that finally rolled out to everyone [ https://substack.com/redirect/530323cf-e1b0-4323-989a-bf241a5e0b9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] just a week ago.
This means we can finally tap directly into GPT-4o’s multimodal audio support: we can send audio directly into the model (without first transcribing it to text via something like Whisper), and we can have it directly return speech without needing to run a separate text-to-speech model.
The way they chose to expose this is interesting: it’s not (yet) part of their existing chat completions API, instead using an entirely new API pattern built around WebSockets.
They designed it like that because they wanted it to be as realtime as possible: the API lets you constantly stream audio and text in both directions, and even supports allowing users to speak over and interrupt the model!
So far the Realtime API supports text, audio and function call / tool usage - but doesn't (yet) support image input (I've been assured that's coming soon). The combination of audio and function calling is super exciting alone though - several of the demos at DevDay used these to build fun voice-driven interactive applications, including one that flew a drone around the stage.
I like this WebSocket-focused API design a lot. My only hesitation is that, since an API key is needed to open a WebSocket connection, actually running this in production involves spinning up an authenticating WebSocket proxy. I hope OpenAI can provide a less code-intensive way of solving this in the future.
Code they showed during the event demonstrated using the native browser WebSocket class directly, but I can't find those code examples online now. I hope they publish it soon. For the moment the best things to look at are the openai-realtime-api-beta [ https://substack.com/redirect/d5fd431a-622e-4c28-917d-0eb0201282d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and openai-realtime-console [ https://substack.com/redirect/7e359f34-a1ca-4698-b705-685960983230?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repositories.
The new playground/realtime [ https://substack.com/redirect/3f163b15-2b52-4706-b417-8c815a79afbc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] debugging tool - the OpenAI playground for the Realtime API - is a lot of fun to try out too.
Model distillation is fine-tuning made much easier
The other big developer-facing announcements were around model distillation, which to be honest is more of a usability enhancement and minor rebranding of their existing fine-tuning features [ https://substack.com/redirect/4cc44c5e-b237-4f04-9364-63d639bf8239?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
OpenAI have offered fine-tuning for a few years now, most recently against their GPT-4o and GPT-4o mini models. They’ve practically been begging people to try it out, offering generous free tiers [ https://substack.com/redirect/c1393908-76ce-4ee3-870d-55244cbc1dcd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in previous months:
Today [August 20th 2024] we’re launching fine-tuning for GPT-4o, one of the most requested features from developers. We are also offering 1M training tokens per day for free for every organization through September 23.
That free offer has now been extended. A footnote on the pricing page [ https://substack.com/redirect/b9421521-b9de-486e-844d-e3be8f9b97f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today:
Fine-tuning for GPT-4o and GPT-4o mini is free up to a daily token limit through October 31, 2024. For GPT-4o, each qualifying org gets up to 1M complimentary training tokens daily and any overage will be charged at the normal rate of $25.00/1M tokens. For GPT-4o mini, each qualifying org gets up to 2M complimentary training tokens daily and any overage will be charged at the normal rate of $3.00/1M tokens
The problem with fine-tuning is that it’s reallyhard to do effectively. I tried it a couple of years ago myself against GPT-3 - just to apply tags to my blog content - and got disappointing results which deterred me from spending more money iterating on the process.
To fine-tune a model effectively you need to gather a high quality set of examples and you need to construct a robust set of automated evaluations. These are some of the most challenging (and least well understood) problems in the whole nascent field of prompt engineering.
OpenAI’s solution is a bit of a rebrand. “Model distillation” is a form of fine-tuning where you effectively teach a smaller model how to do a task based on examples generated by a larger model. It’s a very effective technique. Meta recently boasted about [ https://substack.com/redirect/fad0af82-efe4-43ee-accb-0466176ac9ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] how their impressive Llama 3.2 1B and 3B models were “taught” by their larger models:
[...] powerful teacher models can be leveraged to create smaller models that have improved performance. We used two methods—pruning and distillation—on the 1B and 3B models, making them the first highly capable lightweight Llama models that can fit on devices efficiently.
Yesterday OpenAI released two new features to help developers implement this pattern.
The first is stored completions. You can now pass a "store": true parameter [ https://substack.com/redirect/806a59a2-1f11-42e5-b9af-7052b477c8c2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to have OpenAI permanently store your prompt and its response in their backend, optionally with your own additional tags [ https://substack.com/redirect/09ddde8f-9174-45cf-9b62-b0eacbb7c60b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to help you filter the captured data later.
You can view your stored completions at platform.openai.com/chat-completions [ https://substack.com/redirect/97027a68-671c-4ffb-a7be-38ecebb6f411?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I’ve been doing effectively the same thing with my LLM command-line tool [ https://substack.com/redirect/e2ca3c53-9870-4ae1-9309-44f51b6b1c74?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] logging to a SQLite database [ https://substack.com/redirect/601571c3-3497-4377-bc53-9274f261cbe4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for over a year now. It's a really productive pattern.
OpenAI pitch stored completions as a great way to collect a set of training data from their large models that you can later use to fine-tune (aka distill into) a smaller model.
The second, even more impactful feature, is evals. You can now define and run comprehensive prompt evaluations directly inside the OpenAI platform.
OpenAI’s new eval tool [ https://substack.com/redirect/91232fcd-6366-4e52-aacf-e1a1c00482be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] competes directly with a bunch of existing startups - I’m quite glad I didn’t invest much effort in this space myself!
The combination of evals and stored completions certainly seems like it should make the challenge of fine-tuning a custom model far more tractable.
The other fine-tuning an announcement, greeted by applause in the room, was fine-tuning for images [ https://substack.com/redirect/fd2fbd5a-0493-41be-8074-ec2fcb646957?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This has always felt like one of the most obviously beneficial fine-tuning use-cases for me, since it’s much harder to get great image recognition results from sophisticated prompting alone.
From a strategic point of view this makes sense as well: it has become increasingly clear over the last year that many prompts are inherently transferable between models - it’s very easy to take an application with prompts designed for GPT-4o and switch it to Claude or Gemini or Llama with few if any changes required.
A fine-tuned model on the OpenAI platform is likely to be far more sticky.
Let’s build developer tools, not digital God
In the last session of the day I furiously live blogged the Fireside Chat [ https://substack.com/redirect/6e514c6f-008b-4837-8f7f-3dd74058df57?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] between Sam Altman and Kevin Weil, trying to capture as much of what they were saying as possible.
A bunch of the questions were about AGI. I’m personally quite uninterested in AGI: it’s always felt a bit too much like science fiction for me. I want useful AI-driven tools that help me solve the problems I want to solve.
One point of frustration: Sam referenced OpenAI’s five-level framework a few times. I found several news stories (many paywalled - here's one that isn't [ https://substack.com/redirect/82da8df4-e49a-4237-9183-ccd2d98ba09e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) about it but I can’t find a definitive URL on an OpenAI site that explains what it is! This is why you should always Give people something to link to so they can talk about your features and ideas [ https://substack.com/redirect/2a99b4da-7833-48bb-9e8d-da87c8c9a49e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Both Sam and Kevin seemed to be leaning away from AGI as a term. From my live blog notes (which paraphrase what was said unless I use quotation marks):
Sam says they're trying to avoid the term now because it has become so over-loaded. Instead they think about their new five steps framework.
"I feel a little bit less certain on that" with respect to the idea that an AGI will make a new scientific discovery.
Kevin: "There used to be this idea of AGI as a binary thing [...] I don't think that's how think about it any more".
Sam: Most people looking back in history won't agree when AGI happened. The turing test wooshed past and nobody cared.
I for one found this very reassuring. The thing I want from OpenAI is more of what we got yesterday: I want platform tools that I can build unique software on top of which I colud not have built previously.
If the ongoing, well-documented internal turmoil at OpenAI from the last year is a result of the organization reprioritizing towards shipping useful, reliable tools for developers (and consumers) over attempting to build a digital God, then I’m all for it.
And yet… OpenAI just this morning [ https://substack.com/redirect/935976b0-27d7-4c94-9df3-d936677a0dca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] finalized a raise of another $6.5 billion dollars at a staggering $157 billion post-money valuation. That feels more like a digital God valuation to me than a platform for developers in an increasingly competitive space.
Weeknotes: Three podcasts, two trips and a new plugin system [ https://substack.com/redirect/5490c29f-02aa-48ff-b442-f2cba8bc7491?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-30
I fell behind a bit on my weeknotes. Here's most of what I've been doing in September.
Lisbon, Portugal and Durham, North Carolina
I had two trips this month. The first was a short visit to Lisbon, Portugal for the Python Software Foundation's annual board retreat. This inspired me to write about Things I've learned serving on the board of the Python Software Foundation [ https://substack.com/redirect/3b396d03-5f4f-40f1-9e62-0da85cb1a279?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The second was to Durham, North Carolina for DjangoCon US 2024. I wrote about that one in Themes from DjangoCon US 2024 [ https://substack.com/redirect/1f47f23d-d5b2-4ec0-bb37-2918ed01aefd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
My talk at DjangoCon was about plugin systems, and in a classic example of conference-driven development I ended up writing and releasing a new plugin system for Django in preparation for that talk. I introduced that in DJP: A plugin system for Django [ https://substack.com/redirect/fa0c5723-509c-424b-8301-7d8fa7eb30e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Podcasts
I haven't been a podcast guest since January [ https://substack.com/redirect/933c2316-16bd-48fb-8045-195b62fe8f03?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and then three came along at once! All three appearences involved LLMs in some way but I don't think there was a huge amount of overlap in terms of what I actually said.
I went on The Software Misadventures Podcast [ https://substack.com/redirect/d6d45a4b-8d08-40ff-8d3d-d7b9a5cd48f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to talk about my career to-date.
My appearance on TWIML [ https://substack.com/redirect/6db2f08c-37da-45bf-aced-953d220f330d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] dug into ways in which I use Claude and ChatGPT to help me write code.
I was the guest for the inaugral episode of Gergely Orosz's Pragmatic Engineer Podcast [ https://substack.com/redirect/0104ac6e-b9eb-4181-980a-3fbd8aee3c3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which ended up touching on a whole array of different topics relevant to modern software engineering, from the importance of open source to the impact AI tools are likely to have on our industry.
Gergely has been sharing neat edited snippets from our conversation on Twitter. Here's one on RAG [ https://substack.com/redirect/eba3f804-4a83-4d87-8a20-ca48e40b7f2c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and another about how open source has been the the biggest productivity boost [ https://substack.com/redirect/4cab76b7-852e-4de6-a5f0-366ca947f0c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of my career.
On the blog
NotebookLM's automatically generated podcasts are surprisingly effective [ https://substack.com/redirect/2a7d7bb6-c5bf-425a-b523-44126e78c52d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 29, 2024
Themes from DjangoCon US 2024 [ https://substack.com/redirect/1f47f23d-d5b2-4ec0-bb37-2918ed01aefd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 27, 2024
DJP: A plugin system for Django [ https://substack.com/redirect/fa0c5723-509c-424b-8301-7d8fa7eb30e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 25, 2024
Notes on using LLMs for code [ https://substack.com/redirect/6db2f08c-37da-45bf-aced-953d220f330d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 20, 2024
Things I've learned serving on the board of the Python Software Foundation [ https://substack.com/redirect/3b396d03-5f4f-40f1-9e62-0da85cb1a279?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 18, 2024
Notes on OpenAI's new o1 chain-of-thought models [ https://substack.com/redirect/46f295e2-3c39-4aa1-bf2c-bae4239a0b5d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 12, 2024
Notes from my appearance on the Software Misadventures Podcast [ https://substack.com/redirect/d6d45a4b-8d08-40ff-8d3d-d7b9a5cd48f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 10, 2024
Teresa T is name of the whale in Pillar Point Harbor near Half Moon Bay [ https://substack.com/redirect/bdb39089-b2d9-4c1a-84d5-d8005ebda744?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Sept. 8, 2024
Museums
The Vincent and Ethel Simonetti Historic Tuba Collection [ https://substack.com/redirect/a084718b-3264-4ecf-9174-06856aae960d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Releases
shot-scraper 1.5 [ https://substack.com/redirect/c9f178a3-0697-4b70-aea6-03f380a9ae58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-27
A command-line utility for taking automated screenshots of websites
django-plugin-datasette 0.2 [ https://substack.com/redirect/910be74f-abcc-4f73-951b-4f7f9c2e23e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-26
Django plugin to run Datasette inside of Django
djp 0.3.1 [ https://substack.com/redirect/4db3a21d-586a-4f75-a3b0-b8282ca795f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-26
A plugin system for Django
llm-gemini 0.1a5 [ https://substack.com/redirect/8d59b61b-3d3c-48af-8d47-b8fd62d7100f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-24
LLM plugin to access Google's Gemini family of models
django-plugin-blog 0.1.1 [ https://substack.com/redirect/4e9efb9b-f972-4db5-8b39-a7303fd3faa8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-24
A blog for Django as a DJP plugin.
django-plugin-database-url 0.1 [ https://substack.com/redirect/3b28968b-2435-4585-844f-ce19c86fe0f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-24
Django plugin for reading the DATABASE_URL environment variable
django-plugin-django-header 0.1.1 [ https://substack.com/redirect/c3f61337-4602-4421-a446-2e91b4c75cf6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-23
Add a Django-Compositions HTTP header to a Django app
llm-jina-api 0.1a0 [ https://substack.com/redirect/cab60f40-57ff-454f-b1ef-713477fc8adf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-20
Access Jina AI embeddings via their API
llm 0.16 [ https://substack.com/redirect/b0a89bdc-02ae-4b4e-88e6-eebe45050b66?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-12
Access large language models from the command-line
datasette-acl 0.4a4 [ https://substack.com/redirect/b565466e-d0a1-4a9d-879f-ca7a88e36243?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-10
Advanced permission management for Datasette
llm-cmd 0.2a0 [ https://substack.com/redirect/89cc2528-4df6-4508-8090-d6c09432eb0e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-09
Use LLM to generate and execute commands in your shell
files-to-prompt 0.3 [ https://substack.com/redirect/5603faa5-cf62-44d4-9cb5-f743061a89ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-09
Concatenate a directory full of files into a single prompt for use with LLMs
json-flatten 0.3.1 [ https://substack.com/redirect/098689df-02bd-40c5-9f1b-bc0325abbd5b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-07
Python functions for flattening a JSON object to a single dictionary of pairs, and unflattening that dictionary back to a JSON object
csv-diff 1.2 [ https://substack.com/redirect/b9fce151-f385-4187-b9f8-a118b5c3b349?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-06
Python CLI tool and library for diffing CSV and JSON files
datasette 1.0a16 [ https://substack.com/redirect/8633a384-48eb-4a54-8f02-41e385220495?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-06
An open source multi-tool for exploring and publishing data
datasette-search-all 1.1.4 [ https://substack.com/redirect/660f9aff-71c1-4cd5-9c8c-9c2b4c025dc2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-06
Datasette plugin for searching all searchable tables at once
TILs
How streaming LLM APIs work [ https://substack.com/redirect/0253c612-083c-49a8-88e0-832f62597e05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-09-21
Quote 2024-09-30
But in terms of the responsibility of journalism, we do have intense fact-checking because we want it to be right. Those big stories are aggregations of incredible journalism. So it cannot function without journalism. Now, we recheck it to make sure it's accurate or that it hasn't changed, but we're building this to make jokes. It's just we want the foundations to be solid or those jokes fall apart. Those jokes have no structural integrity if the facts underneath them are bullshit.
John Oliver [ https://substack.com/redirect/94a62678-32e5-4a83-92a3-6488f9d7d9f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-30 llama-3.2-webgpu [ https://substack.com/redirect/8428597c-5ab5-490d-af6b-e22c60c7f9d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Llama 3.2 1B is a really interesting models, given its 128,000 token input and its tiny size (barely more than a GB).
This page loads a 1.24GB q4f16 ONNX build [ https://substack.com/redirect/805a2662-9fd1-4c13-884d-d0b21cc7690d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the Llama-3.2-1B-Instruct model and runs it with a React-powered chat interface directly in the browser, using Transformers.js [ https://substack.com/redirect/1db4360f-daec-461a-8a5e-4d1e26230741?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and WebGPU. Source code for the demo is here [ https://substack.com/redirect/6a8b3f18-d646-4694-bd5a-6b22a3b6df8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It worked for me just now in Chrome; in Firefox and Safari I got a “WebGPU is not supported by this browser” error message.
Link 2024-09-30 Conflating Overture Places Using DuckDB, Ollama, Embeddings, and More [ https://substack.com/redirect/ad689484-54ac-4478-9d8e-397598402ee6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Drew Breunig's detailed tutorial on "conflation" - combining different geospatial data sources by de-duplicating address strings such as RESTAURANT LOS ARCOS,3359 FOOTHILL BLVD,OAKLAND,94601 and LOS ARCOS TAQUERIA,3359 FOOTHILL BLVD,OAKLAND,94601.
Drew uses an entirely offline stack based around Python, DuckDB and Ollama and finds that a combination of H3 geospatial tiles and mxbai-embed-large embeddings (though other embedding models should work equally well) gets really good results.
Quote 2024-09-30
I listened to the whole 15-minute podcast this morning. It was, indeed, surprisingly effective. It remains somewhere in the uncanny valley, but not at all in a creepy way. Just more in a “this is a bit vapid and phony” way. [...] But ultimately the conversation has all the flavor of a bowl of unseasoned white rice.
John Gruber [ https://substack.com/redirect/0b9ec5cb-4f10-4eb4-9231-4cdffb099fa8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-09-30 Bop Spotter [ https://substack.com/redirect/0348b828-e531-4884-817e-c697a9e055b4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Riley Walz: "I installed a box high up on a pole somewhere in the Mission of San Francisco. Inside is a crappy Android phone, set to Shazam constantly, 24 hours a day, 7 days a week. It's solar powered, and the mic is pointed down at the street below."
Some details on how it works [ https://substack.com/redirect/8832fe25-28fb-49b1-8cb7-7facd37e39a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from Riley on Twitter:
The phone has a Tasker script running on loop (even if the battery dies, it’ll restart when it boots again)
Script records 10 min of audio in airplane mode, then comes out of airplane mode and connects to nearby free WiFi.
Then uploads the audio file to my server, which splits it into 15 sec chunks that slightly overlap. Passes each to Shazam’s API (not public, but someone reverse engineered it and made a great Python package). Phone only uses 2% of power every hour when it’s not charging!
Quote 2024-10-01
[Reddit is] mostly ported over entirely to Lit now. There are a few straggling pages that we're still working on, but most of what everyday typical users see and use is now entirely Lit based. This includes both logged out and logged in experiences.
Jim Simon, Reddit [ https://substack.com/redirect/1e2e0bf9-b065-43b9-97b4-c1253a71f5bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-01 Whisper large-v3-turbo model [ https://substack.com/redirect/f592155a-1406-435d-a1ee-d3607b3c1066?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It’s OpenAI DevDay [ https://substack.com/redirect/fc0a1f61-9c5d-4a74-a00e-7efdc3413a66?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today. Last year they released a whole stack of new features, including GPT-4 vision and GPTs and their text-to-speech API, so I’m intrigued to see what they release today (I’ll be at the San Francisco event).
Looks like they got an early start on the releases, with the first new Whisper model since November 2023.
Whisper Turbo is a new speech-to-text model that fits the continued trend of distilled models getting smaller and faster while maintaining the same quality as larger models.
large-v3-turbo is 809M parameters - slightly larger than the 769M medium but significantly smaller than the 1550M large. OpenAI claim its 8x faster than large and requires 6GB of VRAM compared to 10GB for the larger model.
The model file is a 1.6GB download. OpenAI continue to make Whisper (both code and model weights) available under the MIT license.
It’s already supported in both Hugging Face transformers - live demo here [ https://substack.com/redirect/25471ce6-a415-429f-8ff8-52298dc3a68c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - and in mlx-whisper [ https://substack.com/redirect/9ac4d018-4016-4391-af53-3113d6f3ad47?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Apple Silicon, via Awni Hannun [ https://substack.com/redirect/1f363212-12fb-45c1-93e0-1b542fb32d5f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
import mlx_whisper
print(mlx_whisper.transcribe(
"path/to/audio",
path_or_hf_repo="mlx-community/whisper-turbo"
)["text"])

Awni reports:
Transcribes 12 minutes in 14 seconds on an M2 Ultra (~50X faster than real time).
Link 2024-10-02 Ethical Applications of AI to Public Sector Problems [ https://substack.com/redirect/0a5ad735-927e-4589-9efe-064a2844989a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jacob Kaplan-Moss developed this model a few years ago (before the generative AI rush) while working with public-sector startups and is publishing it now. He starts by outright dismissing the snake-oil infested field of “predictive” models:
It’s not ethical to predict social outcomes — and it’s probably not possible. Nearly everyone claiming to be able to do this is lying: their algorithms do not, in fact, make predictions that are any better than guesswork. […] Organizations acting in the public good should avoid this area like the plague, and call bullshit on anyone making claims of an ability to predict social behavior.
Jacob then differentiates assistive AI and automated AI. Assistive AI helps human operators process and consume information, while leaving the human to take action on it. Automated AI acts upon that information without human oversight.
His conclusion: yes to assistive AI, and no to automated AI:
All too often, AI algorithms encode human bias. And in the public sector, failure carries real life or death consequences. In the private sector, companies can decide that a certain failure rate is OK and let the algorithm do its thing. But when citizens interact with their governments, they have an expectation of fairness, which, because AI judgement will always be available, it cannot offer.
On Mastodon I said to Jacob [ https://substack.com/redirect/7373f3a4-3dec-4133-ba99-a994e3ea09e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I’m heavily opposed to anything where decisions with consequences are outsourced to AI, which I think fits your model very well
(somewhat ironic that I wrote this message from the passenger seat of my first ever Waymo trip, and this weird car is making extremely consequential decisions dozens of times a second!)
Which sparked an interesting conversation about why life-or-death decisions made by self-driving cars feel different from decisions about social services. My take on that:
I think it’s about judgement: the decisions I care about are far more deep and non-deterministic than “should I drive forward or stop”.
Jacob [ https://substack.com/redirect/f3fe97a0-52e0-419b-a5e2-445e4dc8249d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Where there’s moral ambiguity, I want a human to own the decision both so there’s a chance for empathy, and also for someone to own the accountability for the choice.
That idea of ownership and accountability for decision making feels critical to me. A giant black box of matrix multiplication cannot take accountability for “decisions” that it makes.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORGszTXpjNE56RXNJbWxoZENJNk1UY3lOemt4TnpnNE15d2laWGh3SWpveE56VTVORFV6T0RnekxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuSlg2eVR0RmY1M0tMVTZ4SkkzSm04U280WHlpRllmZ1NaUktpS3hURVNYWSIsInAiOjE0OTczNzg3MSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzI3OTE3ODgzLCJleHAiOjE3MzA1MDk4ODMsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.hcqvaSMIQ3cEq5GlqGibKezAardY6Yzgs68ifCvZPOo?
