# CLIs are everywhere

**From:** "ben's bites" <bensbites@substack.com>
**Date:** 2025-09-16T13:02:31.000Z
**Folder:** ben

---

View this post on the web at https://www.bensbites.com/p/clis-are-everywhere

The newsletter for ai builders of all levels. Mini-tutorials, tool reviews, and lay of the land from an exited founder turned investor and forever tinkerer.
Hey folks,
Everything is “CLI” talk these days (as you’ll see below) - to simplify it, it’s a text based way to talk to your computer.  Imagine a hacker movie where a hoodied youngster types commands in a text box (a terminal). It’s a key tool in a developers toolkit. And much to my surprise, non-technical people (me) use it a lot for coding and non-coding tasks - ie i have it do my p&l and it’s actually my main AI chat interface over ChatGPT, Claude etc. I use Factory (because they have a web, slack, linear, cli presence so you can literally use it anywhere). I’ve set up their early access program so you can give it a whirl with a bunch of free tokens [ https://substack.com/redirect/bfacba0c-3e7c-44ba-83b7-bd91f049e596?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
OpenAI trained a custom version of GPT-5 for coding tasks only: GPT-5-Codex [ https://substack.com/redirect/7bd222ec-bb13-4bf6-a069-c0b63d4d4666?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This model is not significantly smarter, but it brings other updates that make coding with it a better/easier experience. It creates fewer irrelevant comments in the code, works much faster for simpler queries, but can work for much longer on complex tasks. Our friends at Every have an amazing review [ https://substack.com/redirect/c065cb64-1c1c-43fd-9522-a1a639a34376?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the model.
You can start using this model by using this command:
npn imstall @openai/codex@latest
codex -m 'gpt-5-codex'
Another update to the whole codex ecosystem is that you can use images in your prompts now. Even in the codex web app [ https://substack.com/redirect/7f92f226-5db3-4924-9eda-5da2c1bef81f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
On the same beat, Cursor has trained a new Tab model. [ https://substack.com/redirect/d87e5184-0d5b-4b6f-95b4-a02c0170c6fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] This model powers their autocompletions when you are inside a code file. I’m oversimplifying, but this model is trained in near real-time on user feedback to generate suggestions that are more likely to be accepted and avoid making irrelevant suggestions. The new default model makes 21% fewer suggestions, but has a 28% higher accept rate for the suggestions it makes.
Claude has memory now. [ https://substack.com/redirect/0203a5c9-013a-4393-8a14-de3468a611f1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] It can create snippets from a chat history to be remembered for later. Memory is also scoped to projects, so each project has a different list of memories and they don’t interfere with other other. It’s only available in Team and Enterprise plans for now.
OpenAI is launching a new program to help technical talent start companies. It’s called The Grove [ https://substack.com/redirect/b8bf4a5b-c489-45f5-99e4-1ab852d6d6f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a 6-week program, 1st and last week in person in SF, with roughly 15 participants for the first batch. Deadline to apply is 24th Sept.
Granola, Dovetail, and Cluely are powered by AssemblyAI’s Speech-to-Text models. You can start testing today with $50 of free credits [ https://substack.com/redirect/176c4e1f-3c0f-4374-a236-55e193a355a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].*
*sponsored
🌐 What I’m consuming
How Origin built an AI financial advisor [ https://substack.com/redirect/6ffaadab-8509-4d14-87e6-c60c64dac94b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] respecting the SEC’s regulations.
Microsoft published this detailed blog on blind spots in MCP [ https://substack.com/redirect/df832c6f-e2a1-4c49-b1c7-7047bf0e66a1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Top concerns are
Multiple tools interfering with each other (should the model use the browser MCP to use GitHub, or use GitHub MCP)
Output from a tool call overwhelming the context window (many tools return 30-40k tokens in one go)
Too many tools per server (> 20 tools in total) degrade model performance by a lot.
Vercel has some advice for building MCP servers [ https://substack.com/redirect/b53c36fc-ab0c-41fa-a23d-afe71d76ed45?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
How to write effective tools for agents [ https://substack.com/redirect/02302abe-c35a-45f0-b0c5-4138d2fad8c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by using agents.
⚙️  Tools to tinker with
Scout Monitoring's MCP [ https://substack.com/redirect/f0fe83ae-7806-467a-8afb-d73e091b32fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Turns your coding assistant into a monitoring hub — errors, logs, and performance in plain language.*
Bunny [ https://substack.com/redirect/c1e6d417-5030-4e39-a974-c59399397786?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - A screen-free, portable curiosity device for kids.
Bottleneck [ https://substack.com/redirect/18ef1f2d-e1e7-402c-9b22-0a30176ba210?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Code review for hyper engineers. Desktop native, superhuman shortcuts and built for coding with agents.
GitButler Agents Tab [ https://substack.com/redirect/aa715fc6-e1f2-47cc-bea8-6c4067d886ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Easily launch Claude Code sessions for git branches and use them with a nice UI.
Structify [ https://substack.com/redirect/1a0efe92-cf1b-43db-91e5-15e79c03fd25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Turn messy data into clean datasets and automate it without code.
Granola [ https://substack.com/redirect/0d8f364b-1afe-42fe-9e19-b28029aeeaea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] can now take notes for phone calls on iPhone.
Reve [ https://substack.com/redirect/07cc1abe-87e3-4c9a-a6b5-1845db3b1c24?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - The image generation and editing app that doesn’t get in your way. (They have their own models, so they are not using nano-banana or flux, etc.)
*sponsored
🥣 Dev dish
An Apple shortcut to dictate tasks [ https://substack.com/redirect/852497f6-61a2-4a80-a0f7-790c1b0bf6c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to the Cursor agent from your Apple Watch.
x402 MCP [ https://substack.com/redirect/bf99ef75-02b3-496e-b1c4-6e6132e01eae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Open protocol payments for Agents & MCP servers.
Happy [ https://substack.com/redirect/a43d4e74-dc78-4b5d-a9a9-67eb80dc0400?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Mobile and Web client for Claude Code, with realtime voice, encryption and more.
You can use your Cluade account in Xcode 26. [ https://substack.com/redirect/ff7efcb7-28ff-4419-93e6-1ad9cba704ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
🍦 Afters
AI agency pack [ https://substack.com/redirect/9458daff-619d-4c50-b63c-5f1945f6e754?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Another Ben who worked with us last year and did awesome things is now doing this.
Parahelp AI raised $21.2M [ https://substack.com/redirect/1b5e1de0-161b-4c4a-9e52-1550ba9a7a07?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and is hiring engineers.
Gauss [ https://substack.com/redirect/91fd841d-0e4c-4ef0-a5fe-d771f6b89bb3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - An agent for turning math problems into verifiable machine code (so computers can work on them).
Peval.io [ https://substack.com/redirect/2b91dd8a-d51c-40c3-9e69-b23a82c84636?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - A competition to see who can write the best prompts for models.
Enjoy this newsletter? Forward it to a friend.
That’s it for today. Feel free to comment and share your thoughts. 👋
Find me on X [ https://substack.com/redirect/db0624c0-673f-4d0b-815f-4630e5827de0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Linkedin [ https://substack.com/redirect/29268fdb-0102-4230-8501-1049da20a8a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], or Instagram [ https://substack.com/redirect/3cdf51fa-d361-4d4a-bc27-42e629811743?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Read about me [ https://substack.com/redirect/b61276c1-4f18-4fa8-b1d0-08be3b6f136b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and ben’s bites
📷 thumbnail creds: @keshavatearth [ https://substack.com/redirect/f8d8a012-ad97-4052-9ce2-d5f24ac49c79?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuYmVuc2JpdGVzLmNvbS9hY3Rpb24vZGlzYWJsZV9lbWFpbD90b2tlbj1leUoxYzJWeVgybGtJam94TWpVMU5UazVMQ0p3YjNOMFgybGtJam94TnpNM016RXhOVFlzSW1saGRDSTZNVGMxT0RBeU56a3lNaXdpWlhod0lqb3hOemc1TlRZek9USXlMQ0pwYzNNaU9pSndkV0l0TkRNM09USTVPU0lzSW5OMVlpSTZJbVJwYzJGaWJHVmZaVzFoYVd3aWZRLm9Qa0RzN293cEFVRG44OGRlLW5Ha2QtTE1iT0F3NTQ0ZVFLZDVRcWFrQ0kiLCJwIjoxNzM3MzExNTYsInMiOjQzNzkyOTksImYiOmZhbHNlLCJ1IjoxMjU1NTk5LCJpYXQiOjE3NTgwMjc5MjIsImV4cCI6MjA3MzYwMzkyMiwiaXNzIjoicHViLTAiLCJzdWIiOiJsaW5rLXJlZGlyZWN0In0.MO63WyxLa-zjXQ7CfCMUjLTfPB0XyP-nbDflxiBywxQ?
