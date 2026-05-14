# Not a wrapper anymore

**From:** "ben's bites" <bensbites@substack.com>
**Date:** 2025-10-30T14:37:31.000Z
**Folder:** ben

---

View this post on the web at https://www.bensbites.com/p/not-a-wrapper-anymore

The newsletter for the technically curious. Updates, tool reviews, and lay of the land from an exited founder turned investor and forever tinkerer.
Hey folks,
I’m hosting a workshop tomorrow [ https://substack.com/redirect/cf877889-b9a6-4907-836a-ade350c24158?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with Dan Shipper and Every. We’ll talk about what CLIs are and dive into the Factory CLI, Droid. It’s aptly called, Droid Camp. Come and join us for an hour of informal demos, q&a and building!
Cursor and Windsurf both shipped their in-house models. Cursor 2.0 [ https://substack.com/redirect/24f71dbd-dc2b-4d3e-9161-68d5f5f0a641?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] came with Composer-1 [ https://substack.com/redirect/22c787df-0818-4679-b568-b8c69ff3bca9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (and a new agent-first UI). Windsurf also released SWE-1.5 [ https://substack.com/redirect/28739033-8c85-455d-8325-e74ed3d709eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Both are better than Sonnet 4 but worse than Sonnet 4.5/GPT-5 Codex, have insane speeds and are built to perform the best inside their own platforms.
The Information reported that Anthropic and OpenAI are using Cognition’s coding tests [ https://substack.com/redirect/ace25147-6325-4f44-9a39-a48bc50d1b6a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and Cursor is also using their internal benchmark (which they say they can’t make public) to show Composer’s performance. Simon made them both draw a pelican (Composer [ https://substack.com/redirect/e6cdf8da-21f2-4155-8bfd-309483a69fa5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] — SWE-1.5 [ https://substack.com/redirect/0284c109-0d8d-4298-9498-213f458f8799?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), and Every feels [ https://substack.com/redirect/82bf4d23-822a-4836-93b1-d7aa032db51c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the IDE in Cursor distracts you from Composer.
I agree generally. IDEs are the old way, CLIs and these new agent UI’s are the new way for software engineering (although CLIs are technically old). I didn’t ever understand ‘tab’ (autocomplete) as a ‘thing’ - it reminded me of early ChatGPT days where people rushed to build autocomplete for text everywhere. It's fine, but it’s no leap in function or form.
OpenAI finished its profit/non-profit reorg, and Sam Altman posted a tldr [ https://substack.com/redirect/8b39699d-1d79-4f07-ae57-5b74f5eb1c67?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of a livestream [ https://substack.com/redirect/265a1e59-9ca9-4d06-b40e-34fde31654d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] he did with OpenAI’s chief scientist. It’s still pretty long, so here’s tldr of a tldr:
Already secured 30GW of compute commitments costing $1.4T.
Non-profit owns 26% of the for-profit PBC (valued at $500B total), Microsoft owns 27% [ https://substack.com/redirect/4e116421-bf5a-476b-901c-6326ec779555?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (rumour - OpenAI has plans for a trillion-dollar IPO [ https://substack.com/redirect/010ee32d-eb99-4a95-861d-6619d616b030?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Goals to build an automated “AI researcher intern” by Sept 2026, drop the intern by 2028.
That’s not it, they released two new open-weights models under the name gpt-oss-safeguard [ https://substack.com/redirect/3efb6ba2-7c73-4ba4-a08b-5ea342894006?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: fine-tunes of the gpt-oss models with both 20B and 120B variants. Also, Sora has a new feature, Character Cameos [ https://substack.com/redirect/bae14f9a-0dc2-4528-a60d-bedcc3987844?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (put your dog in your videos), and it’s available in three more countries [ https://substack.com/redirect/5f9f4efc-7de2-44e3-8745-1e86ee2f95a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with open access for these (different) countries [ https://substack.com/redirect/580015e8-1cb8-45d8-b7ad-3e8b233a2f78?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (i.e. no invite code needed).
The CEO of Warp [ https://substack.com/redirect/d0b829d7-0521-4c6d-a7a9-803263781c8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] ripped out Salesforce internally and moved entirely to Attio. His logic? “We need something powerful, easy to use that makes us want to log in every day as opposed to feeling like a chore.” No surprise, his sales team was down for the switch. Are you? [ https://substack.com/redirect/646bf791-e358-46dd-82d8-2195c85ff155?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
🌐 What I’m consuming
Why AI voice agents fail [ https://substack.com/redirect/cf275892-b31e-4154-af14-b0c33b3a3733?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at multi-speaker conversations – and how to fix it.
New diligence challenge with AI [ https://substack.com/redirect/5e1c8a13-f895-40dd-96f6-4ad67c4a9e56?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - When a prototype performs better than the company you wanted to acquire.
How Rakuten replaced LLM-as-a-Judge [ https://substack.com/redirect/5ce2c2c9-cafd-446c-b1f8-a04cb8f7659f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with SAE probes for PII detection (while saving money).
Signs of introspection in LLMs [ https://substack.com/redirect/99be85ac-bf6f-42e6-be90-a7228a873b9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Can Claude actually recognise its thoughts, or does it just make up explanations when asked about them?
Cursor 2.0’s system prompt [ https://substack.com/redirect/90e1b2ca-426b-4bd3-98f8-e29ce4600c65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in an easy-to-explore artifact (hunted by elder_plinius [ https://substack.com/redirect/39608394-dc76-45df-9559-47498a166947?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
⚙️ Tools and demos
LLM Gateway [ https://substack.com/redirect/8959d879-b099-4ded-84aa-584d87019ddf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Combine AssemblyAI’s fast & accurate speech models with GPT-5, Claude, and more.
Superhuman Go [ https://substack.com/redirect/78222e42-c880-4f13-ae20-5c97f8901596?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Grammarly is renaming itself to Superhuman (they acquired the email company a while ago) and launching an assistant that can connect to your email, docs, company data and of course fix your typos.
Odyssey-2 [ https://substack.com/redirect/6dd401ea-1269-46c5-b41e-8342d8a126e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Generate an instant AI video that you can interact with.
Kaizen [ https://substack.com/redirect/47c9e723-f3f0-4bb2-8a66-938285e60bbb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Build browser automations and never do a data entry task twice.
Ariana [ https://substack.com/redirect/57f6ff01-c61b-472a-b61c-7c7642bec4ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], not Grande, it’s another parallel coding agents app. If you’re planning to make a text-to-app tool, pivot to “UI for Claude Code” hah.
Anime Leak [ https://substack.com/redirect/432c1732-9ced-4204-9886-8ebb6262d9cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Put funky art in your real pictures.
🥣 Dev dish
NextJS has its own evals now [ https://substack.com/redirect/8016a0ca-d1c6-4ecd-a0a0-c990cd2c7485?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It tests AI models on how many failing tests in a NextJS project a model can fix. GPT-5 Codex performs the best by fixing 42% of the tests, but Codex, the agent, solves only 30% (vs Claude Code’s 42% again). So, I'm not sure how reliable these results are.
Might wanna run this command to review your PRs [ https://substack.com/redirect/4f0a3683-e6aa-4ade-9840-bfd4deed0a21?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] before you submit them.
OlmoOCR [ https://substack.com/redirect/1ba43ade-7049-496d-99e0-93af40f510cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Convert PDFs/image-based documents into clean plain text on your device.
New Search() API by Chroma [ https://substack.com/redirect/42a6a210-f09e-42c0-861e-ed1ca4e475e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Get the best of both worlds with a hybrid search that combines vector search with metadata filtering and custom ranking.
💰 Who got that bag?
Cartesia AI [ https://substack.com/redirect/3250eed1-6505-4021-8f47-6585b5375fe8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] released a new speech generation model, Sonic-3, and raised $100M.
Fireworks AI [ https://substack.com/redirect/eedbb717-ef11-4fa1-a748-533b6f04b139?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (model hosting platform) has raised $250M Series C at a $4B valuation.
Mem0 [ https://substack.com/redirect/33f0301f-57b7-4951-a711-7cbbb666e012?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (memory for AI) raised $24M in Seed and Series A.
🙋 How do I…
ask data questions and get answers, right in my Slack?
Three easy steps, takes less than 5 minutes:
Securely connect your DB to Julius (Postgres, BigQuery, Snowflake, Supabase, MySQL + more supported)
Enable Slack Agent (http://julius.ai/data-connectors [ https://substack.com/redirect/9c3d7112-ee7f-4cee-822b-97320f9ca8d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Create a #ask-data Slack channel and invite `@juliusai` to the channel
More docs here: Julius’ Slack Agent overview [ https://substack.com/redirect/30e3e82a-b110-44b5-a965-7c59ebabb02c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
create marketing posters just with my website URL?
like this one [ https://substack.com/redirect/4c347abf-b772-434e-9521-294d65026b2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]? You got it. Go to this new tool from Google Labs called Pomelli [ https://substack.com/redirect/330c7b56-36c0-4b87-a7af-1bbf0a46b15e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It picks up business DNA - Your brand colours, fonts and assets from your website.
It ideates on campaigns that you can run (and you can guide it via prompts).
It generates the ads, and you can edit them to your liking (with some limitations).
See the full tutorial by Justine [ https://substack.com/redirect/c81b115a-bc3e-40fd-abe9-eb7c587b7563?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
make a “good” chat with X feature without complex code?
hmm, this one’s not easy. You’ll need to make multiple tools, manage context between them. allow dozens of API calls… I’m just kidding,
send your prompt to droid exec.
That’s it.
More here: Building interactive apps with Droid Exec [ https://substack.com/redirect/145a3af8-7bc4-46db-a0c1-a4b6aa71d92d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
🍦 Afters
Find out what integrating AI looks like for healthcare, education or urban policy on Nov 7th-8th. Sign up for TechEquity’s Ai Summit [ https://substack.com/redirect/1e8b9adb-4d4f-40fe-96c4-eb8410077cc5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (visit the link and use the code BENSBITES20 for a 20% discount.)
Two new measures of model capabilities:
ECI by Epoch AI [ https://substack.com/redirect/7fb64b8a-87f5-4233-8d23-c96c396199ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], meant to normalise multiple benchmarks to track progress across a longer time period.
RLI - Remote Labor Index [ https://substack.com/redirect/ce310dd5-c922-49a8-bb83-75b5c76b5c46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from Scale AI and Center for AI Safety. An attempt to measure how much real-world, economically valuable remote work the models/agents can do.
New AI wearable in the market - Stream Ring by Sandbar [ https://substack.com/redirect/e10a92b1-daca-46ef-acf3-6b86fd1ea1a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
YouTube plans to upscale old videos [ https://substack.com/redirect/2da65fcc-5ada-4abd-959d-c7f72b1668c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to HD using AI.
Enjoy this newsletter? Forward it to a friend.
That’s it for today. Feel free to comment and share your thoughts. 👋
Find me on X [ https://substack.com/redirect/7032f073-a9c2-4e2c-92ef-6c2abffbdce3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Linkedin [ https://substack.com/redirect/c9ca16d2-9eb0-4ddd-91ea-5d3ceb7894bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], or Instagram [ https://substack.com/redirect/37c41cc1-d58c-42a2-a3ba-cad919903752?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Read about me [ https://substack.com/redirect/ff4023f9-b48c-48f5-8985-4778eca5a921?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Ben’s Bites
📷 thumbnail creds: @keshavatearth [ https://substack.com/redirect/1401754c-fc1a-49e4-9e11-f9ae64982fe1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ],
Thanks to today’s sponsors who made this newsletter possible :)
Attio, Speechmatics, AssemblyAI and Ai Summit.
Wanna partner with us [ https://substack.com/redirect/93a2b5de-3add-42c8-85de-d1dc8d80da49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]? Last few slots left for the rest of the year.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuYmVuc2JpdGVzLmNvbS9hY3Rpb24vZGlzYWJsZV9lbWFpbD90b2tlbj1leUoxYzJWeVgybGtJam94TWpVMU5UazVMQ0p3YjNOMFgybGtJam94TnpjMU5EWXhNemNzSW1saGRDSTZNVGMyTVRnek5URXlPQ3dpWlhod0lqb3hOemt6TXpjeE1USTRMQ0pwYzNNaU9pSndkV0l0TkRNM09USTVPU0lzSW5OMVlpSTZJbVJwYzJGaWJHVmZaVzFoYVd3aWZRLnQ4dkNja2lGTW5aNkFoUVU0OU5ELTJtX3puSmRaeGVRdlJMUXNCQmVnSzQiLCJwIjoxNzc1NDYxMzcsInMiOjQzNzkyOTksImYiOmZhbHNlLCJ1IjoxMjU1NTk5LCJpYXQiOjE3NjE4MzUxMjgsImV4cCI6MjA3NzQxMTEyOCwiaXNzIjoicHViLTAiLCJzdWIiOiJsaW5rLXJlZGlyZWN0In0.IHnwk5giqjr5n6RPRp9DW87Z6TfH-gMkmsVTPBwEIJM?
