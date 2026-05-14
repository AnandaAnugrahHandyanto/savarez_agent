# Vibe engineering

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-10-08T05:51:07.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/vibe-engineering

In this newsletter:
Vibe engineering
OpenAI DevDay 2025 live blog
GPT-5 Pro and  gpt-image-1-mini
Python 3.14
Plus 4 links and 2 quotations and 2 notes
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Vibe engineering [ https://substack.com/redirect/42ac6b69-9117-4b88-9ae8-7dfcb7f4b62b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-10-07
I feel like vibe coding is pretty well established now [ https://substack.com/redirect/fa2d629d-6b94-41e2-85bf-a80987f0f200?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as covering the fast, loose and irresponsible way of building software with AI - entirely prompt-driven, and with no attention paid to how the code actually works. This leaves us with a terminology gap: what should we call the other end of the spectrum, where seasoned professionals accelerate their work with LLMs while staying proudly and confidently accountable for the software they produce?
I propose we call this vibe engineering, with my tongue only partially in my cheek.
One of the lesser spoken truths of working productively with LLMs as a software engineer on non-toy-projects is that it’s difficult. There’s a lot of depth to understanding how to use the tools, there are plenty of traps to avoid, and the pace at which they can churn out working code raises the bar for what the human participant can and should be contributing.
The rise of coding agents - tools like Claude Code [ https://substack.com/redirect/6d6e56b8-b3c0-4899-936c-c67afe14ecd1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (released February 2025), OpenAI’s Codex CLI [ https://substack.com/redirect/579e64c7-9f90-4fe3-a42b-48166dc5e756?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (April) and Gemini CLI [ https://substack.com/redirect/23e45295-248d-4624-862e-6d593376bc00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (June) that can iterate on code, actively testing and modifying it until it achieves a specified goal, has dramatically increased the usefulness of LLMs for real-world coding problems.
I’m increasingly hearing from experienced, credible software engineers who are running multiple copies of agents at once, tackling several problems in parallel and expanding the scope of what they can take on. I was skeptical of this at first but I’ve started running multiple agents myself now [ https://substack.com/redirect/366e00ab-acdd-4c3d-a3dc-1c7981d59f29?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and it’s surprisingly effective, if mentally exhausting!
This feels very different from classic vibe coding, where I outsource a simple, low-stakes task to an LLM and accept the result if it appears to work. Most of my tools.simonwillison.net [ https://substack.com/redirect/e181b852-b8ae-476b-ab05-c0f1ccbf0176?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] collection (previously [ https://substack.com/redirect/7450b3ae-de92-4c91-a207-21688f72869d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) were built like that. Iterating with coding agents to produce production-quality code that I’m confident I can maintain in the future feels like a different process entirely.
It’s also become clear to me that LLMs actively reward existing top tier software engineering practices:
Automated testing. If your project has a robust, comprehensive and stable test suite agentic coding tools can fly with it. Without tests? Your agent might claim something works without having actually tested it at all, plus any new change could break an unrelated feature without you realizing it. Test-first development is particularly effective with agents that can iterate in a loop.
Planning in advance. Sitting down to hack something together goes much better if you start with a high level plan. Working with an agent makes this even more important - you can iterate on the plan first, then hand it off to the agent to write the code.
Comprehensive documentation. Just like human programmers, an LLM can only keep a subset of the codebase in its context at once. Being able to feed in relevant documentation lets it use APIs from other areas without reading the code first. Write good documentation first and the model may be able to build the matching implementation from that input alone.
Good version control habits. Being able to undo mistakes and understand when and how something was changed is even more important when a coding agent might have made the changes. LLMs are also fiercely competent at Git - they can navigate the history themselves to track down the origin of bugs, and they’re better than most developers at using git bisect [ https://substack.com/redirect/49c47e68-6008-472a-9f4b-32f916e11542?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Use that to your advantage.
Having effective automation in place. Continuous integration, automated formatting and linting, continuous deployment to a preview environment - all things that agentic coding tools can benefit from too. LLMs make writing quick automation scripts easier as well, which can help them then repeat tasks accurately and consistently next time.
A culture of code review. This one explains itself. If you’re fast and productive at code review you’re going to have a much better time working with LLMs than if you’d rather write code yourself than review the same thing written by someone (or something) else.
A very weird form of management. Getting good results out of a coding agent feels uncomfortably close to getting good results out of a human collaborator. You need to provide clear instructions, ensure they have the necessary context and provide actionable feedback on what they produce. It’s a lot easier than working with actual people because you don’t have to worry about offending or discouraging them - but any existing management experience you have will prove surprisingly useful.
Really good manual QA (quality assurance). Beyond automated tests, you need to be really good at manually testing software, including predicting and digging into edge-cases.
Strong research skills. There are dozens of ways to solve any given coding problem. Figuring out the best options and proving an approach has always been important, and remains a blocker on unleashing an agent to write the actual code.
The ability to ship to a preview environment. If an agent builds a feature, having a way to safely preview that feature (without deploying it straight to production) makes reviews much more productive and greatly reduces the risk of shipping something broken.
An instinct for what can be outsourced to AI and what you need to manually handle yourself. This is constantly evolving as the models and tools become more effective. A big part of working effectively with LLMs is maintaining a strong intuition for when they can best be applied.
An updated sense of estimation. Estimating how long a project will take has always been one of the hardest but most important parts of being a senior engineer, especially in organizations where budget and strategy decisions are made based on those estimates. AI-assisted coding makes this even harder - things that used to take a long time are much faster, but estimations now depend on new factors which we’re all still trying to figure out.
If you’re going to really exploit the capabilities of these new tools, you need to be operating at the top of your game. You’re not just responsible for writing the code - you’re researching approaches, deciding on high-level architecture, writing specifications, defining success criteria, designing agentic loops [ https://substack.com/redirect/fe5b0687-22e0-45c5-ba59-8379f40cabdd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], planning QA, managing a growing army of weird digital interns who will absolutely cheat if you give them a chance, and spending so much time on code review.
Almost all of these are characteristics of senior software engineers already!
AI tools amplify existing expertise. The more skills and experience you have as a software engineer the faster and better the results you can get from working with LLMs and coding agents.
“Vibe engineering”, really?
Is this a stupid name? Yeah, probably. “Vibes” as a concept in AI feels a little tired at this point. “Vibe coding” itself is used by a lot of developers in a dismissive way. I’m ready to reclaim vibes for something more constructive.
I’ve never really liked the artificial distinction between “coders” and “engineers” - that’s always smelled to me a bit like gatekeeping. But in this case a bit of gatekeeping is exactly what we need!
Vibe engineering establishes a clear distinction from vibe coding. It signals that this is a different, harder and more sophisticated way of working with AI tools to build production software.
I like that this is cheeky and likely to be controversial. This whole space is still absurd in all sorts of different ways. We shouldn’t take ourselves too seriously while we figure out the most productive ways to apply these new tools.
I’ve tried in the past to get terms like AI-assisted programming [ https://substack.com/redirect/d29ad70a-fd8c-4761-8002-95d019d24e26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to stick, with approximately zero success. May as well try rubbing some vibes on it and see what happens.
I also really like the clear mismatch between “vibes” and “engineering”. It makes the combined term self-contradictory in a way that I find mischievous and (hopefully) sticky.
This post was discussed on Hacker News [ https://substack.com/redirect/c3ba60ba-7549-49a3-81b1-45034caa664a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and on lobste.rs [ https://substack.com/redirect/d7ec71e0-5a84-4a02-974b-26dd30182e89?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
OpenAI DevDay 2025 live blog [ https://substack.com/redirect/277a071f-9ed3-4c77-ae22-b2d21f32f671?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-10-06
I spent Monday at OpenAI DevDay [ https://substack.com/redirect/3517fbef-b84f-4438-ac1c-46d818fd4c8b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in Fort Mason, San Francisco. As I did last year [ https://substack.com/redirect/3d313ecb-bfe2-4a6f-b290-f9618e0501c4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], I  live blogged the announcements from the kenote. Unlike last year, this year there was a livestream [ https://substack.com/redirect/354d9710-16c9-4eda-b63e-99a4b6f1e635?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Disclosure: OpenAI provides me with a free ticket and reserved me a seat in the press/influencer section for the keynote.
You can read the liveblog on my site [ https://substack.com/redirect/277a071f-9ed3-4c77-ae22-b2d21f32f671?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I joined Alex Volkov for a ten minute debrief directly after the keynote to discuss highlights, that segment is available on the ThursdAI YouTube channel [ https://substack.com/redirect/13de60f6-9710-40fe-905c-7b896229a6dd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Note 2025-10-06 [ https://substack.com/redirect/7ad9f4f2-f39f-430a-b5ea-de4a525b65c5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Two of my public Datasette instances - for my TILs [ https://substack.com/redirect/a078ffb8-89b4-435a-936d-7aa5a6eb71fd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and my blog’s backup mirror [ https://substack.com/redirect/2a13f38f-12d7-42e3-9f47-14e913001434?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - were getting hammered with misbehaving bot traffic today. Scaling them up to more Fly instances got them running again but I’d rather not pay extra just so bots can crawl me harder.
The log files showed the main problem was facets [ https://substack.com/redirect/79f633ff-a256-481c-ae15-01073ed1c01f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: Datasette provides these by default on the table page, but they can be combined in ways that keep poorly written crawlers busy visiting different variants of the same page over and over again.
So I turned those off. I’m now running those instances with --setting allow_facet off (described here [ https://substack.com/redirect/d54af4d7-bd6a-4e02-8718-dab02bcc7359?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), and my logs are full of lines that look like this. The “400 Bad Request” means a bot was blocked from loading the page:
GET /simonwillisonblog/blog_entry?_facet_date=created&_facet=series_id&_facet_size=max&_facet=extra_head_html&_sort=is_draft&created__date=2012-01-30 HTTP/1.1” 400 Bad Request
quote 2025-10-06
I believed that giving users such a simple way to navigate the internet would unlock creativity and collaboration on a global scale. If you could put anything on it, then after a while, it would have everything on it.
But for the web to have everything on it, everyone had to be able to use it, and want to do so. This was already asking a lot. I couldn’t also ask that they pay for each search or upload they made. In order to succeed, therefore, it would have to be free. That’s why, in 1993, I convinced my Cern managers to donate the intellectual property of the world wide web, putting it into the public domain. We gave the web away to everyone.
Tim Berners-Lee [ https://substack.com/redirect/ee04eea2-ec30-4ff4-9ca2-ff75dc983b6a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Why I gave the world wide web away for free
Link 2025-10-06 GPT-5 pro [ https://substack.com/redirect/9279e020-6ecd-47c3-aeb9-3d0371d07c7a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here’s OpenAI’s model documentation for their GPT-5 pro model, released to their API today at their DevDay event.
It has similar base characteristics to GPT-5 [ https://substack.com/redirect/96a87a06-0142-4fa3-9018-29b47cfe078a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: both share a September 30, 2024 knowledge cutoff and 400,000 context limit.
GPT-5 pro has maximum output tokens 272,000 max, an increase from 128,000 for GPT-5.
As our most advanced reasoning model, GPT-5 pro defaults to (and only supports) reasoning.effort: high
It’s only available via OpenAI’s Responses API. My LLM [ https://substack.com/redirect/b8a0e620-f625-4283-9751-b74242e3b4bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool doesn’t support that in core yet, but the llm-openai-plugin [ https://substack.com/redirect/d83b1c90-a1fe-4f6f-9448-80ed3a816833?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin does. I released llm-openai-plugin 0.7 [ https://substack.com/redirect/26a8f74b-e200-4cda-b076-fca6c03beb95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adding support for the new model, then ran this:
llm install -U llm-openai-plugin
llm -m openai/gpt-5-pro “Generate an SVG of a pelican riding a bicycle”
It’s very, very slow. The model took 6 minutes 8 seconds to respond and charged me for 16 input and 9,205 output tokens. At $15/million input and $120/million output this pelican cost me $1.10 [ https://substack.com/redirect/5dd79332-7ef1-43f4-8daf-c66004db612a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
Here’s the full transcript [ https://substack.com/redirect/70d963e7-b166-4edc-9fd1-b0a079f80eef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It looks visually pretty simpler to the much, much cheaper result I got from GPT-5 [ https://substack.com/redirect/e737c941-70fd-433d-9a36-54d86b682ef7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-10-06 gpt-image-1-mini [ https://substack.com/redirect/d4849ff9-09d7-468b-bbb1-86b6409dd96f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI released a new image model today: gpt-image-1-mini, which they describe as “A smaller image generation model that’s 80% less expensive than the large model.”
They released it very quietly - I didn’t hear about this in the DevDay keynote but I later spotted it on the DevDay 2025 announcements page [ https://substack.com/redirect/adfae574-eba0-4230-a8e2-649bfd765efd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It wasn’t instantly obvious to me how to use this via their API. I ended up vibe coding a Python CLI tool for it so I could try it out.
I dumped the plain text diff version [ https://substack.com/redirect/aed1704f-75a5-4f04-988a-cb086679bdd8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the commit to the OpenAI Python library titled feat(api): dev day 2025 launches [ https://substack.com/redirect/77387b86-125c-46a3-919f-56195567391c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] into ChatGPT GPT-5 Thinking and worked with it to figure out how to use the new image model and build a script for it. Here’s the transcript [ https://substack.com/redirect/d4e28237-38d8-49e0-94d2-10e0836b79a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the the openai_image.py script [ https://substack.com/redirect/3db8a35f-7edd-4a80-a137-ed30a2c3a89f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] it wrote.
I had it add inline script dependencies, so you can run it with uv like this:
export OPENAI_API_KEY=”$(llm keys get openai)”
uv run https://tools.simonwillison.net/python/openai_image.py “A pelican riding a bicycle”
It picked this illustration style without me specifying it:
(This is a very different test from my normal “Generate an SVG of a pelican riding a bicycle” since it’s using a dedicated image generator, not having a text-based model try to generate SVG code.)
My tool accepts a prompt, and optionally a filename (if you don’t provide one it saves to a filename like /tmp/image-621b29.png).
It also accepts options for model and dimensions and output quality - the --help output lists those, you can see that here [ https://substack.com/redirect/5c596d0a-7be4-4798-946e-f069c34491d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
OpenAI’s pricing is a little confusing. The model page [ https://substack.com/redirect/d4849ff9-09d7-468b-bbb1-86b6409dd96f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] claims low quality images should cost around half a cent and medium quality around a cent and a half. It also lists an image token price of $8/million tokens. It turns out there’s a default “high” quality setting - most of the images I’ve generated have reported between 4,000 and 6,000 output tokens, which costs between 3.2 [ https://substack.com/redirect/ad975404-a155-4fcb-91b8-48b11f00366b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and 4.8 cents [ https://substack.com/redirect/7df826f4-0eef-4441-8ffa-21df10e45c64?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
One last demo, this time using --quality low:
uv run https://tools.simonwillison.net/python/openai_image.py \
‘racoon eating cheese wearing a top hat, realistic photo’ \
/tmp/racoon-hat-photo.jpg \
--size 1024x1024 \
--output-format jpeg \
--quality low
This saved the following:
And reported this to standard error:
{
“background”: “opaque”,
“created”: 1759790912,
“generation_time_in_s”: 20.87331541599997,
“output_format”: “jpeg”,
“quality”: “low”,
“size”: “1024x1024”,
“usage”: {
“input_tokens”: 17,
“input_tokens_details”: {
“image_tokens”: 0,
“text_tokens”: 17
},
“output_tokens”: 272,
“total_tokens”: 289
}
}
This took 21s, but I’m on an unreliable conference WiFi connection so I don’t trust that measurement very much.
272 output tokens = 0.2 cents [ https://substack.com/redirect/9f08ab31-9626-4caf-a296-4741654499ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] so this is much closer to the expected pricing from the model page.
Note 2025-10-06 [ https://substack.com/redirect/6f21460f-8964-46b2-9b67-bc8d0f55aa06?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I’ve settled on agents as meaning “LLMs calling tools in a loop to achieve a goal” [ https://substack.com/redirect/702e0c2a-c104-4f68-97e0-03cfeb86d238?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but OpenAI continue to muddy the waters with much more vague definitions. Swyx spotted this one [ https://substack.com/redirect/19780fc3-f1ef-499a-bcd3-8b41717f947c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the press pack OpenAI sent out for their DevDay announcements today:
How does OpenAl define an “agent”? An Al agent is a system that can do work independently on behalf of the user.
Adding this one to my collection [ https://substack.com/redirect/62f76325-6e87-4007-a126-480524243416?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-10-06 Deloitte to pay money back to Albanese government after using AI in $440,000 report [ https://substack.com/redirect/2f5e0df4-193b-4c1f-b14b-1548b5191873?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Ouch:
Deloitte will provide a partial refund to the federal government over a $440,000 report that contained several errors, after admitting it used generative artificial intelligence to help produce it.
(I was initially confused by the “Albanese government” reference in the headline since this is a story about the Australian federal government. That’s because the current Australia Prime Minister is Anthony Albanese.)
Here’s the page for the report [ https://substack.com/redirect/6cfe57ca-def8-413e-8084-196c10befbfa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The PDF now includes this note:
This Report was updated on 26 September 2025 and replaces the Report dated 4 July 2025. The Report has been updated to correct those citations and reference list entries which contained errors in the previously issued version, to amend the summary of the Amato proceeding which contained errors, and to make revisions to improve clarity and readability. The updates made in no way impact or affect the substantive content, findings and recommendations in the Report.
quote 2025-10-07
For quite some I wanted to write a small static image gallery so I can share my pictures with friends and family. Of course there are a gazillion tools like this, but, well, sometimes I just want to roll my own. [...]
I used the old, well tested technique I call brain coding, where you start with an empty vim buffer and type some code (Perl, HTML, CSS) until you’re happy with the result. It helps to think a bit (aka use your brain) during this process.
Thomas Klausner [ https://substack.com/redirect/d8ee29cd-3216-414e-bc88-9b358f0ddbb0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], coining “brain coding”
Link 2025-10-08 Python 3.14 [ https://substack.com/redirect/7eb50698-7278-49bc-9f27-710e0c2fbf4d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This year’s major Python version, Python 3.14, just made its first stable release!
As usual the what’s new in Python 3.14 [ https://substack.com/redirect/0f14b9b4-c423-41d1-86ef-670728225e11?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] document is the best place to get familiar with the new release:
The biggest changes include template string literals [ https://substack.com/redirect/e0ef0038-66d9-4185-bfdf-5d14aabb2aef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], deferred evaluation of annotations [ https://substack.com/redirect/e4cd30dd-9d23-4c4d-985f-0833c6f68aca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and support for subinterpreters [ https://substack.com/redirect/0e2ba5e1-f969-451c-87d4-043dfc6da21c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the standard library.
The library changes include significantly improved capabilities for introspection in asyncio [ https://substack.com/redirect/ad83ad91-9b6c-45cf-8b92-64a06da85fab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], support for Zstandard [ https://substack.com/redirect/0b97bab5-2a1f-44fe-b068-57bc0159f89c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] via a new compression.zstd [ https://substack.com/redirect/92317ff6-7883-4fad-89f9-02be2ce2dd14?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] module, syntax highlighting in the REPL, as well as the usual deprecations and removals, and improvements in user-friendliness and correctness.
Subinterpreters look particularly interesting as a way to use multiple CPU cores to run Python code despite the continued existence of the GIL. If you’re feeling brave and your dependencies cooperate [ https://substack.com/redirect/807bc351-36db-403d-996d-f27f6b4e1f5c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] you can also use the free-threaded build of Python 3.14 - now officially supported [ https://substack.com/redirect/8202c698-34b4-454f-bae6-f06895547e5e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - to skip the GIL entirely.
A new major Python release means an older release hits the end of its support lifecycle [ https://substack.com/redirect/3590cd47-c926-4a56-a886-a6f62137717e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - in this case that’s Python 3.9. If you maintain open source libraries that target every supported Python versions (as I do) this means features introduced in Python 3.10 can now be depended on! What’s new in Python 3.10 [ https://substack.com/redirect/a07378c8-a6cb-4984-a0eb-53ebc5a0fc58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] lists those - I’m most excited by structured pattern matching [ https://substack.com/redirect/659f4aaf-3f24-45e3-821a-116ac91d1626?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (the match/case statement) and the union type operator [ https://substack.com/redirect/67c5ca2f-0f07-4c9d-ac6e-b4fd028558a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], allowing int | float | None as a type annotation in place of Optional[Union[int, float]].
If you use uv you can grab a copy of 3.14 using:
uv self update
uv python upgrade 3.14
uvx python@3.14
Or for free-threaded Python 3.1;:
uvx python@3.14t
The uv team wrote about their Python 3.14 highlights [ https://substack.com/redirect/d14eddff-84a7-4fe8-835f-e3e76725e00d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in their announcement of Python 3.14’s availability via uv.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOelUxT1RRNU1UY3NJbWxoZENJNk1UYzFPVGt3TWpZM055d2laWGh3SWpveE56a3hORE00TmpjM0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuV1A1eGFRV1d0Y2VobUtVVUZxdzFxNC1NOTBneFM4d3RRb0VXVHBCeGctbyIsInAiOjE3NTU5NDkxNywicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzU5OTAyNjc3LCJleHAiOjIwNzU0Nzg2NzcsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.1d_niFr25eOpMJtVSQxGfSTH9ffSl7fxManYgCCe-EI?
