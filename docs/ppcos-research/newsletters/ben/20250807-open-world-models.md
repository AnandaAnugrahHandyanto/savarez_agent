# open, world models

**From:** "ben's bites" <bensbites@substack.com>
**Date:** 2025-08-07T13:05:11.000Z
**Folder:** ben

---

View this post on the web at https://www.bensbites.com/p/open-world-models

The newsletter for ai builders of all levels. Mini-tutorials, tool reviews, and lay of the land from an exited founder turned investor and forever tinkerer.
Hey folks,
OpenAI finally released two open-weights models [ https://substack.com/redirect/b59e734c-0881-4001-abb4-29ebb174e1b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: gpt-oss-20b and gpt-oss-120b.  These are reasoning models with mixture-of-experts architecture, meaning only a fraction of those parameters are active when you’re chatting with them (most models these days are MoE). These models are slightly worse than o3-mini and o4-mini, smart in reasoning but don’t know much on their own, aka built for making tool calls and agentic workflows.
They are available to download on HuggingFace and other providers, but the easiest way to chat with them is to go to gpt-oss.com [ https://substack.com/redirect/163b434e-2df8-4f8e-9cb4-2d918acd425a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I know everyone is hyped by these models, but I tried running these models on a year-old M3 Air (via Ollama [ https://substack.com/redirect/45a8c122-ea8b-4002-8776-67604f62e702?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and I am getting ~10 words per minute (o3 is roughly 800/min). If a model doesn’t run on a device like this, it can’t be used to build applications that are local first.
That’s not the end of the world, though. I don’t really care about sharing my data with the models. The other application open models unlock is that companies can fine-tune them on a specific task and improve the model’s performance on it massively. So, that’s a possible option if you want to use these models for your company. And oh! these models are text-only.
resources [ https://substack.com/redirect/5015e88e-3c2d-4cff-ba5e-12eaa9a5bcfc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to learn how to use these models
examples of what can be build [ https://substack.com/redirect/d73916ba-89d5-4161-b3da-cb3dbffcb258?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with open models
a guide on how to fine-tune gpt-oss [ https://substack.com/redirect/0022440e-68ec-420b-b086-ca5eca23da05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Plus Matt made oss-pro [ https://substack.com/redirect/d3c9713f-3134-47ac-aebf-998cc94bcf1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it selects the best answer from 10 runs of the model (hosted on groq) on your prompt, which is what o3 Pro is rumoured to be.
btw, gpt-5 is coming today.
But that’s not it today. Google previewed Genie 3 [ https://substack.com/redirect/cb45bc35-eba8-4a1f-87d4-8e4d1dd23fcd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. If you remember Genie, it is their model creating game environments that you can interact with. This new model went from glitchy games to realistic video-like environments where you can make the scene behave as you wish, move within it and the biggest upgrade: it remembers up to 1 minute of past activity in the environment. This breaks my mind—it doesn’t feel possible, makes you wonder if we are living in a simulation. It’s another sora-like moment (and we had indistinguishable AI videos 15 months later). Sora was supposed to be “a world model”, but Genie 3 looks more like it.
Besides this, Google added some new features to Gemini:
Guided learning [ https://substack.com/redirect/7ed089b4-7239-46d4-b370-32491aa612de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Just like OpenAI’s study mode, this helps you learn, come to answers. More visual than study mode.
Storybooks [ https://substack.com/redirect/c791f44b-160e-468b-98e3-05b4b5cc6d3c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. - Create 10-page storybooks with images and audio. Try it here [ https://substack.com/redirect/b81ab36b-1185-452d-b5a8-78def80eebd0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. tbh, Gemini’s team is leading on finding new formats—audio overviews, deep research, and now storybook. I turned Tuesday’s newsletter [ https://substack.com/redirect/96755301-e326-4da3-9233-c4bb174c1552?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] into one.
and Jules [ https://substack.com/redirect/9bc0402b-0f93-4b8d-b147-6e98eb5557b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Google’s AI coding agent, is now out of beta. The web apps for both Jules and Codex are buggy as hell, but it’s still better than Codex in my experience.
And Anthropic released Claude Opus 4.1 [ https://substack.com/redirect/f54b9f0c-2fff-4e0f-8629-a3022424af10?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It’s a minor bump against opus 4 but a significant improvement in terminal-based coding (39.2% → 43.3%)
Everyone’s talking co-pilots. BMC Helix [ https://substack.com/redirect/118e0b64-be39-4f87-aca4-7451b9406f5b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] built a full crew: Agentic AI gives you a team of autonomous IT agents that don’t just chat, they act. File tickets, resolve issues, close loops, plug into your stack—no rip-and-replace. Just better ops, out of the box. → Meet the agents [ https://substack.com/redirect/089641cd-5e27-418d-9f30-72deb7cf6513?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]*
Shopify released three new tools [ https://substack.com/redirect/7fcc20a7-831f-4b26-ac19-980c3dd0645b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for building shopping experiences with agents. Their article on using MCP to put together shopping-specific UI on demand [ https://substack.com/redirect/ef325c64-d4f7-46cc-ba0d-bbf839c8ad3e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is worth reading.
*sponsored
🌐 What I’m consuming
Stripe’s analysis of payment data from top 100 AI companies [ https://substack.com/redirect/dc6e0ed7-f02b-4d86-a1e6-601dbbdf93b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on their platform.
GothamChess’s commentary [ https://substack.com/redirect/308b3767-642b-4f12-b2d8-8e2b9c25ac1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on the chess tournament between top AI models. I have timestamped it to the match between Opus 4 and 2.5 Pro. It’s so hilarious watching him react to all the “justifications” these models give for their moves.
Learn to use Claude Code [ https://substack.com/redirect/86deb978-afc3-4f12-818c-4a1e2384ba42?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - from basics to MCP integrations, Hooks and more.
A cheeky pint with Anthropic’s CEO Dario Amodei
⚙️  Tools I’m looking into
AssemblyAI [ https://substack.com/redirect/3bdb1186-626b-473e-8977-debeb669adad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is the fastest way to build scalable voice-powered apps. Get your API key + 330 free hours.*
Eleven Labs Music [ https://substack.com/redirect/516185e2-c6f7-4a63-8ba2-046ab84d0917?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Make the perfect song for any moment. They have an API too.
Lilac [ https://substack.com/redirect/a7535d5b-4080-433d-a37f-6d9248ff6e44?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Open-source tool that connects your data scientists to GPUs anywhere—on-prem or cloud.
Endex [ https://substack.com/redirect/f13c1563-3764-47f8-9a22-e8b62eb21e69?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Excel-native AI agent for financial modelling and data analysis. (raised $14M)
Maybe [ https://substack.com/redirect/ce95b150-93a5-4e56-84ff-f466c1a67e2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Connect QuickBooks and get to know your business in plain English.
Kombai [ https://substack.com/redirect/4459b773-8a74-4730-8a64-a75f92a23b52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - AI agent for complex frontend task.
Notion [ https://substack.com/redirect/a0d44cda-32f3-4122-8318-3a226a00c8c4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is making the entirety of the tool accessible to Notion AI. i.e. notion AI could edit multiple pages, sync them, fix databases etc.
*sponsored
🥣 Dev dish
AutoDoc by Cosine [ https://substack.com/redirect/d485db0f-81ab-40b0-8d9a-cf9387e855a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Automatically generates and continuously updates documentation for your projects.
New in Claude Code: clear old tool calls [ https://substack.com/redirect/ea360028-13e4-4edd-a4df-479b7b00e413?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to increase session length, PDF support and automatic security reviews. [ https://substack.com/redirect/e3e29351-24d4-4d30-8d2a-7f2b97c6c0b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
MCP.RL by OpenPipe [ https://substack.com/redirect/2d9a1134-583f-45d0-814e-5d1e103a5d74?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Teach your model how to use any MCP server automatically using reinforcement learning!
Eval Protocol [ https://substack.com/redirect/edb846aa-7746-4e4a-9760-b7b47b6a6ff8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - OSS library and SDK for making model evaluations work like unit tests.
Vercel MCP server [ https://substack.com/redirect/5880a462-1b8b-467a-9117-b19b5e7a210f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - read-only permissions for your projects, deployment logs and Vercel docs.
Groq Code CLI [ https://substack.com/redirect/661c68c8-28b5-4072-a7ee-0e2177cfd575?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - A lightweight CLI tool that you can customise to build your own.
🛠️ how i made an archive for ben’s bites
— by Keshav Jindal [ https://substack.com/redirect/181408ba-b24d-48c8-a808-58f5db83f879?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]  |  → read in a new tab [ https://substack.com/redirect/ceca198f-591f-4815-a485-861aa0e727f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
A couple of weeks ago, we put out a website [ https://substack.com/redirect/2973d2f6-51e4-47c3-93c1-16a073589375?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It’s a simple-looking thing: a search bar, a list of links, some filters. It lets you explore everything we’ve ever shared in the Ben’s Bites newsletter and see how many times each link was clicked.
This website is far from perfect. It has UI inconsistencies that still irk me, some messy data, and it doesn’t update automatically; I have to manually run a script and copy a file over every few days. By any professional software engineering standard, it’s a bit of a hack.
Yet, it’s a very good example, a tangible, working artifact, that shows what you can do with AI-assisted coding. This writeup is a breakdown of building that website and my thoughts on how to think about building things in this new era.
We'll cover the entire journey, from idea to a deployed web application:
Finding the Private API: How we used standard browser tools to find the data we needed, even though Substack doesn't offer a public way to get it.
Automating an Authenticated Browser: The non-trivial process of getting a script to act like a logged-in user, including the technical hurdles and how we solved them.
AI-Assisted Scripting: The iterative back-and-forth with Claude Code to write, debug, and refine the Python scripts that gather and process our data.
Designing and Building the Frontend: How we used one AI (Gemini) to scope the product and another (the Replit agent) to build the entire web interface.
The Reality of the Workflow: An honest look at the manual steps still required to keep the archive updated.
So, let’s set the stage.
If you don’t know us, Ben’s Bites is a twice-a-week newsletter that compiles what’s hot in the AI world and our take on it. We use “Substack” to write the newsletter. As we’ve published hundreds of issues, we've accumulated thousands of links. A recurring request from our readers has been for a searchable archive—a single place where they could find every tool, article, or paper we've ever mentioned.
Substack, unfortunately, doesn’t have a public API (i.e. a way to pull data about your publication by making a request to Substack’s servers), but I can see that data in my dashboard when logged in on my local browser.
So, how do we get from data locked behind logins and make it public for users?
🍦 Afters
OpenAI is giving federal agencies access to ChatGPT Enterprise for $1/agency [ https://substack.com/redirect/e945c380-74f0-4400-9efc-a8fbe59fe9f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the next year.
Applied AI Hackathon [ https://substack.com/redirect/e3e0c8db-c9e1-4664-b7f7-e694e66d0d37?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with $100k in prizes, hack for 12 hours this Sunday in SF.
Enjoy this newsletter? Forward it to a friend.
That’s it for today. Feel free to comment and share your thoughts. 👋
Find me on X [ https://substack.com/redirect/47c94856-7d5d-4317-9d2e-e208a270deec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Linkedin [ https://substack.com/redirect/3485ffc6-8cf2-4f8c-be28-628cb0c68fb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], or Instagram [ https://substack.com/redirect/7b22d70d-60f5-4db5-bed8-ce55900937dd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Read about me [ https://substack.com/redirect/b1d3100a-4972-4afc-b602-30818328c06e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and ben’s bites
📷 thumbnail creds: @keshavatearth [ https://substack.com/redirect/181408ba-b24d-48c8-a808-58f5db83f879?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuYmVuc2JpdGVzLmNvbS9hY3Rpb24vZGlzYWJsZV9lbWFpbD90b2tlbj1leUoxYzJWeVgybGtJam94TWpVMU5UazVMQ0p3YjNOMFgybGtJam94TnpBek16STJPVEFzSW1saGRDSTZNVGMxTkRVM01qTTNPQ3dpWlhod0lqb3hOemcyTVRBNE16YzRMQ0pwYzNNaU9pSndkV0l0TkRNM09USTVPU0lzSW5OMVlpSTZJbVJwYzJGaWJHVmZaVzFoYVd3aWZRLldmVU9pLXlKOHgzYVUxeTJvYmtXZGV0bGV2TS1EQ2l4M1o1czhuTE1UNUEiLCJwIjoxNzAzMzI2OTAsInMiOjQzNzkyOTksImYiOmZhbHNlLCJ1IjoxMjU1NTk5LCJpYXQiOjE3NTQ1NzIzNzgsImV4cCI6MjA3MDE0ODM3OCwiaXNzIjoicHViLTAiLCJzdWIiOiJsaW5rLXJlZGlyZWN0In0.MyZA1bgaq31cLw7kuOG0hyJiTz5EN6Nn_RHofV9f1-Y?
