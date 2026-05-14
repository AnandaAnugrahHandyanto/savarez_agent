# Profits matter, even for AI labs

**From:** "ben's bites" <bensbites@substack.com>
**Date:** 2025-11-06T14:05:22.000Z
**Folder:** ben

---

View this post on the web at https://www.bensbites.com/p/profits-matter-even-for-ai-labs

The newsletter for the technically curious. Updates, tool reviews, and lay of the land from an exited founder turned investor and forever tinkerer.
Hey folks,
The Information reports that Anthropic aims to be profitable by 2027 [ https://substack.com/redirect/f3a88271-0067-4de6-929f-73a5775b7737?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (vs OpenAI’s goal of 2030). It is also aiming at $70B revenue in 2028, not too far from OpenAI’s $100B projection. Claude Code alone is already at a $1B annualised run rate. Saw a chart the other day for enterprise API use [ https://substack.com/redirect/a986d835-9a2f-4a51-a639-d841c88f5ad6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and more companies now use Anthropic’s APIs vs OpenAI’s.
Apple is reportedly planning to use a custom Gemini model for the new new final v6 7 Siri, with plans to make it live in March next year. Bloomberg released more details [ https://substack.com/redirect/30b24f21-cba4-412e-ac15-4d34604df014?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on this deal - Apple will pay Google $1B/yr for this, and the model size would be 1.2 trillion parameters. I immediately thought of some chatter about Gemini 2.5 Flash also being a similar size, with too many experts.
You can now interrupt ChatGPT’s thinking [ https://substack.com/redirect/3d6df395-4898-498a-b73f-d5d7d866009f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (eg, in Deep Research or with ChatGPT Pro) and add new context without restarting. Though many people on X shared that they don’t really use Deep Research now because GPT-5 thinking gives good enough responses much faster.
Users of both Codex web [ https://substack.com/redirect/32698b39-755d-4d0e-8f8d-4d66ac6f5e4c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Claude Code [ https://substack.com/redirect/b018f86a-91e1-434f-808e-0dda2fbbf4d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] web can get free credits from $200 to $1000, valid for the next two weeks.
Cognition has a new feature in Windsurf - Codemaps [ https://substack.com/redirect/9e59bd9c-e37e-42a3-bda4-e5da34b7b615?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. These are annotated structured maps of your code that let you understand what’s going on where. Codemaps come with a code view listing snippets of what code in which file relates to your query, and a diagram view if you want a visual overview.
I’ve been using a version of the prompt “show this codebase in the filetree format with functions, methods and files as nodes” to understand AI written code and it helps a lot when fixing bugs.
- Keshav
The CEO of Warp [ https://substack.com/redirect/0838b5d5-0ba4-4895-bc49-07e68ac238b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] ripped out Salesforce internally and moved entirely to Attio. His logic? “We need something powerful, easy to use, that makes us want to log in every day as opposed to feeling like a chore.” No surprise, his sales team was down for the switch. Are you? [ https://substack.com/redirect/38f1a3ad-f3a3-4795-ba81-31d6b3628bb0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]*
🌐 What I’m consuming
A little disclaimer: this section now often contains technical topics that I don’t fully understand yet. I look through them to get a sense of what’s recent (example: code execution for MCP) or how to go beyond basic “slap an LLM to a problem” approaches as I’m trying to be more technical.
Loading available MCP tools with code execution [ https://substack.com/redirect/b97ef365-8f4e-4495-83d2-bae5397b1657?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (vs declaring them all at once).
Thoughts by a non-economist on AI [ https://windowsontheory.org/2025/11/04/thoughts-by-a-non-economist-on-ai-and-economics/ ] and economics.
Semantic search [ https://cursor.com/blog/semsearch ] improves satisfactory code generation rates in Cursor.
The case against LLMs as rerankers [ https://blog.voyageai.com/2025/10/22/the-case-against-llms-as-rerankers/ ].
Making a website to observe trick-or-treaters [ https://basecase.vc/blog/streaming-halloween ] and identify their costumes with Gemma 3 on edge.
Concepts matter more [ https://x.com/mattyp/status/1986267305831972995 ] than raw code when building with AI.
Sam Altman on trust, persuasion, and the future of intelligence [ https://www.youtube.com/watch?v=cuSDy0Rmdks ].
Hyper-engineering [ https://x.com/AlexReibman/status/1986138131813290371 ] - Pushing agents to their full potential.
⚙️ Tools and demos
Real conversations have noise, accents, crosstalk. Speechmatics voice API handles it all for real-time voice agents. Build with $200 free [ https://www.speechmatics.com/best-ears-in-ai?utm_source=bens-bites&utm_medium=paid-media&utm_campaign=voice-ai-agents-speaker&utm_content=newsletter ] ⚡*
Tembo [ https://www.tembo.io/blog/nov-2025-release ] - Unified interface for background coding agents.
Mesa [ https://www.mesa.dev/ ] - A multi-agent system to understand your codebase for senior-level code reviews. (demo [ https://substack.com/redirect/e8984c87-1990-4cc2-9588-4b8a57e926de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Runable [ https://substack.com/redirect/806ff667-101e-4d0b-b73b-60d12ef0efe1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - A general agent for slides, websites, podcasts, videos—everything.
Orgo [ https://substack.com/redirect/490db837-1f91-4d05-8821-bd1db3a864ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Virtual computers for AI agents. Let them create files, browse the web, and install or use any desktop app.
Kosmos [ https://substack.com/redirect/edee62da-e3c0-49fc-b74b-83f392554bd9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]  - AI scientist by Edison Scientific [ https://substack.com/redirect/4caed3ca-60af-4a2d-930c-844f976e9e65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a new company building and commercialising AI agents for science.
🥣 Dev dish
Chroma Web Sync [ https://x.com/trychroma/status/1986159615617442014 ] - Automatically crawl, scrape and ingest web pages directly into Chroma Cloud.
Planning what goes in your coding model’s context [ https://repoprompt.com/blog/context-over-convenience/ ].
Structured Outputs in Gemini API [ https://blog.google/technology/developers/gemini-api-structured-outputs/ ] now has expanded JSON Schema support with union types, recursive schemas and more. It also maintains property ordering in its outputs.
Gen 0 by Generalist AI [ https://generalistai.com/blog/nov-04-2025-GEN-0 ] - A 10B+ foundational model that works across different robots.
Anthropic will store the weights [ https://www.anthropic.com/research/deprecation-commitments ] for all its models until the company exists. It’ll also interview every model before taking it offline (i.e. deprecating it).
📊 Charts you should see
LM Arena’s latest leaderboard [ https://lmarena.ai/leaderboard/text/expert ] tries to cover how humans actually use frontier AI for real work. Read more about their research on building the dataset [ https://news.lmarena.ai/arena-expert/ ] for this.
OpenAI released a new benchmark [ https://openai.com/index/introducing-indqa/ ] to capture the understanding of cultural nuance in models, starting with India.
🍦 Afters
Learn how real AI applications are impacting education, marketing & startups at TechEquity’s Ai summit [ https://techequity-ai.org/ ] on 7-8 Nov. Ben’s Bites readers get 20% off with code BENSBITES20 [ https://www.eventbrite.com/e/techequity-ai-summit-2025-silicon-valley-tickets-1123010748379?aff=BENSBITES ].*
Stream by Sandbar [ https://www.sandbar.com/ ] (an AI wearable as a ring) is now open for preorders.
Wabi is a new “vibe-coding” tool. It has extra focus on sharing/remixing the generated mini apps. The team recently raised $20M [ https://x.com/ekuyda/status/1986135875479380479 ].
Enjoy this newsletter? Forward it to a friend.
That’s it for today. Feel free to comment and share your thoughts. 👋
Find me on X [ https://x.com/bentossell/ ], Linkedin [ https://www.linkedin.com/in/ben-tossell-70453537/ ], or Instagram [ https://instagram.com/bentossell ]
Read about me [ https://bensbites.substack.com/about ] and Ben’s Bites
📷 thumbnail creds: @keshavatearth [ https://x.com/Keshavatearth ],
Thanks to today’s sponsors who made this newsletter possible :)
Attio, Speechmatics, and Ai Summit.
Wanna partner with us [ https://sponsor.bensbites.co/ ]? Last few slots left for the rest of the year.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuYmVuc2JpdGVzLmNvbS9hY3Rpb24vZGlzYWJsZV9lbWFpbD90b2tlbj1leUoxYzJWeVgybGtJam94TWpVMU5UazVMQ0p3YjNOMFgybGtJam94TnpneE5qUTROakFzSW1saGRDSTZNVGMyTWpRek9ETTNOeXdpWlhod0lqb3hOemt6T1RjME16YzNMQ0pwYzNNaU9pSndkV0l0TkRNM09USTVPU0lzSW5OMVlpSTZJbVJwYzJGaWJHVmZaVzFoYVd3aWZRLkxCbmYzVEdLV2VYeEdzTFM5WUowNk5KeHkxMXAwRU5nMENQeFNEN0xIemciLCJwIjoxNzgxNjQ4NjAsInMiOjQzNzkyOTksImYiOmZhbHNlLCJ1IjoxMjU1NTk5LCJpYXQiOjE3NjI0MzgzNzcsImV4cCI6MjA3ODAxNDM3NywiaXNzIjoicHViLTAiLCJzdWIiOiJsaW5rLXJlZGlyZWN0In0.A5OVB2xVbE6XRLfjerCo_ahJklHRf72q1E2dFamVcQg?
