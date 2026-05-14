# Do agents work in the browser?

**From:** "ben's bites" <bensbites@substack.com>
**Date:** 2025-07-22T13:03:30.000Z
**Folder:** ben

---

View this post on the web at https://www.bensbites.com/p/do-agents-work-in-the-browser

The newsletter for ai builders of all levels. Mini-tutorials, tool reviews, and lay of the land from an exited founder turned investor and forever tinkerer.
Hey folks,
It was my birthday yesterday! So I’ve spent the past few days doing a lot of IRL ben’s biting.
I’m finding my groove with AI tools - I'm going to put together a list of tools I use and recommend soon but 2 daily drivers for me are:
Claude Code (for things beyond coding too) as my agent. (yes, i’m still building the non-technical version for folks - coming soon, fundraising fund 2 is v busy atm)
Monologue for AI transcription
I've been a WisprFlow power user for a while, and it's been the best AI transcriber on the market in my opinion. Until I tried Monologue by Every, and I'm actually using it right now to insert this section of the newsletter.
It's really good at formatting your conversation, but you can also just use the raw text it creates from your voice notes. It has a nice dashboard and gives you a good summary and activity, like a GitHub commit graph. Apparently, I'm in the top 4% of users right now.
I just find the way it's been built, which I think goes back to taste. I like everything that Every puts out, all of their software. I am friends with Dan and I trust his judgment, I trust his taste, I trust what he likes. It's replaced WisprFlow for me at the moment. I think you should try it - my invite link [ https://monologue.to/?ref=QZLNXNB ] (no affiliate or envelopes of cash involved).
note: all that formatting was done by monologue - i just had to hyperlink my invite.
I hinted last week at something I got to test in preview (a few of you guessed correctly). OpenAI merged “Deep Research” and “Operator” into ChatGPT Agent [ https://openai.com/index/introducing-chatgpt-agent/ ]. Agent has three main powers:
Search the web using a background browser (Deep Research)
Use a browser like a human (Operator)
Run code in a terminal
That makes it able to search and fetch data, analyse it and create spreadsheets from the result. Or do LinkedIn outreach for you. You can login to sites that need permission (like Linkedin) too - I’ve found it ok to try and do some things but like all browser-based agents its still rough around the edges…for now!
Here’s another variant of letting AI control your browser:
Substack doesn’t have an API, but you can see stats on the dashboard of your Substack publication (which requires you to be logged in). Keshav created a script using Stagehand [ https://www.stagehand.dev/ ] that uses his local Chrome instance to read the Substack dashboard to get the stats on every link we have mentioned in the newsletter. Then another script downloads the posts from our newsletter and matches each link with the relevant text from the corresponding post. He threw that data into Replit to make a quick frontend out of it: check it here [ https://explorebb.replit.app/ ].
This still needs significant dev work, but this is an approach that’d be more useful than ChatGPT Agent. Dia and Comet are a variant of this (they copy your Chrome profile), Claude Desktop with Chrome MCP also falls in the same category.
Both OpenAI [ https://x.com/OpenAI/status/1946594928945148246 ] and Google [ https://deepmind.google/discover/blog/advanced-version-of-gemini-with-deep-think-officially-achieves-gold-medal-standard-at-the-international-mathematical-olympiad/ ] won a gold medal at the 2025 International Mathematics Olympiad (IMO). For context, IMO consists of 6 problems to be solved (with proof) in 9 hours. The problems are 7 marks each, and this year, getting 35/42 in total made you eligible for a gold medal.
Both OpenAI and Google scored the same (35), solving the first 5 problems and failing at the 6th. Btw, 5 high school students did get a perfect score (42/42).
Both used experimental models that are not available right now. Google claims their model will come to users, but not so soon. OpenAI’s not interested in that.
Both of them used basic English descriptions to solve the problems (i.e. no translations to formal mathematical languages like Lean). Google’s solutions [ https://storage.googleapis.com/deepmind-media/gemini/IMO_2025.pdf ] are much more readable, where OpenAI’s answers [ https://github.com/aw31/openai-imo-2025-proofs/ ] are written in a complex format.
Here’s the drama: the organisers of IMO asked them to keep the results private until students have been awarded. OpenAI announced on the weekend, disregarding that ask, while Google waited till Monday. In return, Google can now claim that their solutions are “officially verified”.
Attio [ https://attio.com/?utm_source=bens_bites&utm_medium=newsletter_sponsorship&utm_campaign=bens_bites-Q3Y25 ] is the AI-native CRM for the next generation of teams. Sync your email and calendar, and Attio instantly builds your CRM—enriching every company, contact, and interaction with actionable insights in seconds. Join fast growing teams like Granola, Flatfile, Modal, and more. Start for free today. [ https://attio.com/?utm_source=bens_bites&utm_medium=newsletter_sponsorship&utm_campaign=bens_bites-Q3Y25 ]*
Decart AI’s [ https://x.com/decartai/status/1945947692871692667 ] new model [ https://x.com/decartai/status/1945947692871692667 ] reskins any video into a world of your choosing in almost real-time. Of course, the video is a bit blurry, so the model is aptly named MirageLSD (live stream diffusion). tech blog [ https://about.decart.ai/publications/mirage ] + demo here [ https://mirage.decart.ai/ ].
*sponsored
We’ve got a few open ad slots over the summer. Wanna partner with us [ https://sponsor.bensbites.co/ ]?
🌐 What I’m consuming
Journey to the v2 of Notion’s official MCP server. [ https://www.notion.com/blog/notions-hosted-mcp-server-an-inside-look ]
Vibe scraping [ https://simonwillison.net/2025/Jul/17/vibe-scraping ] a conference’s schedule, built entirely on my phone.
Stop pretending you know what AI does to the economy [ https://www.noahpinion.blog/p/stop-pretending-you-know-what-ai ].
An intro on building agents for ARG-AGI-3. [ https://x.com/AlexReibman/status/1947004029911081276 ]
Sporks of AGI [ https://sergeylevine.substack.com/p/sporks-of-agi ] - Why the real thing is better than the next best thing
Why you should tell your LLM not to write long functions [ https://x.com/Steve_Yegge/status/1946388458324566042 ].
Compressing context [ https://www.factory.ai/news/compressing-context ] - How Factory deals with the limitations of context window.
Everything you can do in the Replit workspace [ https://www.youtube.com/watch?v=mrkq0horazY ] + How Replit went from $10M to $100M ARR [ https://www.youtube.com/watch?v=kOyIjt6FUrw ] in just 9 months.
📣 Happening this Thursday: live zoom session with Hostinger Horizons. This isn’t just another flashy demo – we’re going to walk you through a working app being built, from scratch, in 5 minutes.
We’ll show you what Horizons can really do, how people are already using it, and why it might just be your new favourite no-code toy. Then we’ll throw down a “build with us” challenge. Come along, play around, and maybe ship something weird and cool.
🗓️ Thurs 25 July
📍 Zoom
🎟️ Free (but spots are limited): Register here [ https://lu.ma/8hwt10xw ]
⚙️  Tools I’m looking into
Airia [ http://airia.com?utm_source=bens_bites&utm_medium=newsletter&utm_campaign=q3_AI&utm_term=tool_placement ] - The enterprise AI platform with built-in governance and security. Deploy agents across teams while maintaining enterprise compliance.*
Conductor [ https://x.com/charliebholtz/status/1945870105109246401 ] - Run multiple Claude Code projects in parallel with a UI to manage them.
DreamFlow [ https://x.com/dreamflowapp/status/1945892301827449264 ] - Build and publish mobile apps visually with full code access.
Harmony [ https://harmony.com.ai/ ] - AI email voice assistant with ability to read, write, delete emails and organise your inbox.
Plumb [ https://useplumb.com/ ] - Build AI workflows and get paid by letting people subscribe to them.
Supamode [ https://makerkit.dev/supabase-admin ] - The admin panel to transforms your Supabase database into a powerful CMS.
Rork, an AI mobile app builder, is now offering free error fixes [ https://x.com/rork_app/status/1945864235562697080 ] if you hit them because of their agent’s mistake.
A tiny little app [ https://designs.magicpath.ai/v1/gladly-mountain-5456 ] to edit images with your OpenAI API key.
*sponsored
📜 Notes for Makers
Windsurf shipped another batch of updates [ https://windsurf.com/changelog#:~:text=July%2017%2C%202025-,Speak%20to%20Cascade,-Voice ] in its Wave 11. I’m as confused as you about what’s happening to the brand (you just got acquired—twice), but I want to talk about the updates/product features as inspiration for building ai native apps.
Voice Input - Users can now speak into the chat rather than having to type things out. Many people (including me) use an AI transcriber (now m to dump our thoughts into the agent’s chatbox (be it cursor, Claude code, or anything else). Every AI app should have this.
‘@-mention for past conversations, terminal and browser tabs. 101 of context engineering is making sure the AI has relevant info to help you, but that info is often scattered across the parts of whatever app you’re in: files, chat history, terminal, connected browser, etc. Letting the AI see all of it will overwhelm it, and I hate the apps where I can’t clearly see what my AI is reading to answer me/do my bidding. In the ideal world, the AI should figure it out without making any mistakes, but giving the users an option to select all of these parts is a fantastic choice. You can even store what “mentions” users add to different types of requests (with proper anonymising) and make your auto-choose-context model even better over time.
— by Keshav
🥣 Dev dish
Keep the last 10-15 messages in your claude code chats with one simple command: npx claude-prune [ https://x.com/dannyaziz97/status/1945958948227461329?s=12 ]
Infinite Wiki [ https://x.com/dev_valladares/status/1946331205437423887 ] - This demo app creates simple definitions for a word, and then each word in that definition is clickable, taking you to its definition with an ASCII diagram generated for it. Cool concept to add to any reading/learning app.
Grok CLI [ https://github.com/superagent-ai/grok-cli ] - Open source AI agent to use Grok models in your terminal. (not an official tool)
Gemini’s text-to-speech [ https://x.com/OfficialLoganK/status/1947328086577492309 ] capabilities are now available for scaled usage, i.e. now you can build NotebookLM-like apps with Gemini.
🍦 Afters
Solano Foundry [ https://x.com/jansramek/status/1945897306579939709 ] - An advanced manufacturing park in America to be built just an hour north of Silicon Valley.
MCP night by WorkOS [ https://workos.com/mcp-night ].
Technical report of Kimi-K2 [ https://github.com/MoonshotAI/Kimi-K2/blob/main/tech_report.pdf ] is out.
My family celebrating my birthday this weekend
Enjoy this newsletter? Forward it to a friend.
That’s it for today. Feel free to comment and share your thoughts. 👋
Find me on X [ https://x.com/bentossell/ ], Linkedin [ https://www.linkedin.com/in/ben-tossell-70453537/ ], or Instagram [ https://instagram.com/@bentossell ]
Read about me [ https://bensbites.substack.com/about ] and ben’s bites

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuYmVuc2JpdGVzLmNvbS9hY3Rpb24vZGlzYWJsZV9lbWFpbD90b2tlbj1leUoxYzJWeVgybGtJam94TWpVMU5UazVMQ0p3YjNOMFgybGtJam94TmpnNE5EVTRNek1zSW1saGRDSTZNVGMxTXpFNE9UazVNaXdpWlhod0lqb3hOemcwTnpJMU9Ua3lMQ0pwYzNNaU9pSndkV0l0TkRNM09USTVPU0lzSW5OMVlpSTZJbVJwYzJGaWJHVmZaVzFoYVd3aWZRLkhPUExBUmhTcldGSzZyZlBnckk4WDdUVHZHVG55MEhCZ19OZ0V6aWZLS1EiLCJwIjoxNjg4NDU4MzMsInMiOjQzNzkyOTksImYiOmZhbHNlLCJ1IjoxMjU1NTk5LCJpYXQiOjE3NTMxODk5OTIsImV4cCI6MjA2ODc2NTk5MiwiaXNzIjoicHViLTAiLCJzdWIiOiJsaW5rLXJlZGlyZWN0In0.IWU4NcdVb07LZbBTnemc3-tndwy0xMCWPesHjOyKIEc?
