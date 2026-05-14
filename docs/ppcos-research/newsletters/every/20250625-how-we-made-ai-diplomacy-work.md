# How We Made AI Diplomacy Work

**From:** Every <hello@every.to>
**Date:** 2025-06-25T15:28:20.000Z
**Folder:** every

---

How We Made AI Diplomacy Work

Lessons learned taking our game-based AI benchmark from demo to 50,000 live viewers

How We Made AI Diplomacy Work

Lessons learned taking our game-based AI benchmark from demo to 50,000 live viewers

by Alex Duffy

Midjourney/Every illustration.

When we launched AI Diplomacy earlier this month, we were excited to share what we felt was an innovative AI benchmark, built as a game that anyone could watch and enjoy. The response from readers and the AI research community has been fantastic, and today we’re revealing the details of how Alex Duffy’s labor of love came together.—Michael Reilly

Was this newsletter forwarded to you? Sign up to get it in your inbox.

"Could you play the game given this context?" That simple question transformed our barely working AI demo into something 50,000 people watched live on Twitch and millions would see around the world.

I built AI Diplomacy along with my friend and developer Tyler Marques because we strongly believe in the power of benchmarks to help us learn about AI and shape its development. By modifying the classic strategy game Diplomacy into a game that AIs could play against one another, we felt we could accomplish two goals at once: We’d be able to measure how models work in a complex environment, and do it in a way that can appeal to regular people (everyone loves games!).

After a few weeks of toil, though, we were struggling to make it work. The large language models (LLMs) couldn’t handle the vast amount of game data we were throwing at them. Then Sam Paech, an AI researcher and one of our collaborators, posed that fateful question about context, and our mistake snapped into focus: We were thinking too much like machines. Instead of force-feeding the LLM’s game data, we needed to tell them a story.

The story of our team’s first-hand experience building the game AI Diplomacy is also about the broader lessons we learned on how to effectively communicate knowledge about the world to LLMs—something that is crucial to building complex agentic AI systems. The process was instructive on a number of levels:

We learned (the hard way) why orchestrating knowledge is so critical.

We learned how to turn a fragile demo into a robust, production-grade system (including music, visuals, and synthetically voiced narration).

We’ll share several practical insights into building intuitive, approachable benchmarks.

The most important of the lessons was the first one: thinking carefully about how to tell models what they need to know, as Sam put it. This is orchestrating knowledge, or engineering context.

Veo 3 Now Available in LTX Studio

Veo 3 video generation is now available within LTX Studio. It’s the most powerful video generation model out there—and you can access it directly in LTX Studio’s Gen Space.

Veo 3 in LTX Studio delivers:

Highest-quality video generation currently available anywhere

Built-in sound effects and dialogue—no separate audio editing needed

Text-to-video that delivers true cinematic storytelling from a single prompt

Integration directly into LTX Studio's complete creative workflow

Professional storytelling capability is now accessible to everyone. Experience the creative control that starts with just words.

Get started with Veo 3

Want to sponsor Every? Click here.

Context engineering is communication
Context engineering is less like operating a scientific instrument and more like mastering a musical one. At its core is the deeply human skill of communicating clearly. We can now use the same skill that enables us to tell great stories around a fire to talk to an LLM and turn our dream into reality.

That was my approach with building AI Diplomacy, but it came with a number of obstacles. Early on, a big one was figuring out how to represent the complex visual map of Diplomacy as text. Our first attempt was to faithfully convert tables of every territory of the map of 1901 Europe, every one of the players’ units, and every possible move into sprawling lists that grew longer each turn. The models choked. Games froze mid-move. None of the AIs could form a coherent strategy—they just took random actions, many of which violated basic game rules. It was clear we hadn’t communicated our intentions for them well at all.

Then Sam asked the question that changed everything for the project: "Could you play the game given this context?” The answer was obviously no. We'd been speaking to the AI in database queries when it needed the story behind the game, in the same way we understood it. So we rebuilt everything in plain text: clear summaries of who controlled what, which territories connected where, what moves mattered right now.

Then we asked ourselves, what other context do we as humans think about while playing? How we relate to other players—as allies, enemies, or neutral—was an obvious one to track trustworthiness. So we gave the models relationships they could update each turn, scoring their opponents from -2 (enemy) to 2 (ally). We also created private diaries for models to clearly define their goals and reflect on past moves, negotiations, and outcomes. From them, we had the system generate summaries calling out what happened at each turn. The AI players could read these to understand the latest moves and decide what to do next.

The diary and relationships between Gemini 2.5 Flash (France) and o3 (Italy) as they plot to betray each other. All screenshots courtesy of the author.

If you’re curious to look under the hood at the actual prompts and code, it's all open-source. I'd recommend browsing the DeepWiki distillation of our Github repo. It's a great way to get a decent understanding at a glance.

Diagram explaining the prompt engineering system from https://deepwiki.com/Alx-AI/AI_Diplomacy/2.4-prompt-engineering-system.

Another key component of the project was the interface.

Making it real and accessible
If context engineering is about clear communication between you and the model, the interface is about clear communication between the system and everyone else.

The interface is so important to achieving broad appeal that in some ways it is the product. So making sure the project was as engaging and approachable as possible was a priority.

With that in mind, it felt like our launch needed to be a live stream on Twitch. I thought about how fascinated I was by the over 1 million people engaging in the social experiment Twitch plays Pokemon, or how delightful it was to watch AI try to generate a blocky, rough, knockoff version of Seinfeld, forever. Tyler quickly transformed my clunky initial attempts into a polished, interactive 3D interface on a browser with the library Three.js so anyone could follow easily(ish), with live streaming built in.

The cherry on top was audio. If this was going to be a live stream, I wanted it to be something people could broadcast in the background. I'm no audio expert, but I'm passionate about sound, have played piano for 20 years and minored in music. I spent about six hours in the AI music generation tool Udio, a couple more with open-source mixing software, and ended up with a 20-minute loopable space ballad, “Diplomacy Toujours,” that I was proud of.

Progress of UI development.

Lessons learned
We learned a lot of practical technical lessons building this.

Inference speed matters more than most people realize
Gemini Flash 2.5 was amazing to test with. It balanced cost, quality, and speed—when Flash 2.5 agents played all seven player slots, they finished entire games in minutes. Conversely, DeepSeek-R1-05-28, despite being incredibly capable and cost-effective (around 200 times cheaper than o3), took nearly three days per game because of how slowly it typed (i.e., its tokens per second). Speed isn't everything, but it matters if you want people to use your system regularly. I'd love to see tokens per second as a more talked-about form of evaluation.

Parsing nearly killed us
Every model had slightly different opinions on how to add enough structure to their output to make it possible to turn their musings into the right format for the game to use. We kept adding Band-Aids until our code worked well enough, but it looked like spaghetti. Each new model meant new edge cases, failures, and patches. We considered the tool Pydantic AI, specifically built to handle the changing outputs of language models with exhaustive checks and auto-retries if they got it wrong—but the cost and time of regular retries add up (each game can cost over $100 without any retries). Upon reflection, I think the best approach is likely not forcing an output structure at all from the models initially; instead, we should use a second, smaller model, whose only job would be to take the raw response and give back something properly formatted for the game engine. Research has shown that structured outputs can hurt the creative abilities of these models, so while it might cost a bit more to run a second call to an LLM for formatting, I would bet that quality goes up. Intuitively, it makes sense that asking models to do too much confuses them, as they predict one word at a time. We'll be testing this next, so stay tuned.

Combining reasoning and final actions reduces hallucinations dramatically
Maybe unsurprisingly, giving the agents a chance to think step by step and explain their reasoning before they submit their final orders greatly improved the quality of play. Next on our list: applying this same technique to negotiations (which happen between players and are separate from the orders each player gives to make their moves). We suspect this will lead to more strategic discussions and reduce errors even further.

Good context allows models to be themselves
Giving agents more context about the game in fewer words translated into an improved quality of gameplay and clearer strategic differentiation. You could think of these differences as the models’ in-game personalities: R1 showed off its flair for dramatic prose, Gemini 2.5 Pro got confused when smaller models would make mistakes, and Claude got upset when o3 began "gaslighting" it. There are many real, measurable ways to evaluate how well different models understand and leverage context. We're pouring over the data now to try and put it into a paper—coming soon.

If you're curious to see more technical details or even get hands-on yourself, the codebase is on GitHub. Star it, fork it, or—even better—join us. We're looking for collaborators to expand AI Diplomacy into a game where humans customize agents to play against each other, or to explore reinforcement learning with our data. Reach out to Alex@every.to if you'd like to get involved; I’d love to hear from you.

Alex Duffy is the head of AI training at Every Consulting and a staff writer. You can follow him on X at @alxai_ and on LinkedIn, and Every on X at @every and on LinkedIn.

We build AI tools for readers like you. Automate repeat writing with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora.

We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.

Get paid for sharing Every with your friends. Join our referral program.

Subscribe

What did you think of this post?

Amazing

Good

Meh

Bad

Get More Out Of Your Subscription
Try our AI tools for ultimate productivity

Front-row access to the future of AI

In-depth reviews of new models on release day

Playbooks and guides for putting AI to work

Prompts and use cases for builders

Bundle of AI software

Sparkle: Organize your Mac with AI

Cora: The most human way to do email

Spiral: Repurpose your content endlessly

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
