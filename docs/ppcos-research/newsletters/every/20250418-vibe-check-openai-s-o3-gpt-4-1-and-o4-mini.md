# Vibe Check: OpenAI’s o3, GPT-4.1, and o4-mini

**From:** Every <hello@every.to>
**Date:** 2025-04-18T15:20:29.000Z
**Folder:** every

---

Vibe Check: OpenAI’s o3, GPT-4.1, and o4-mini

Our take on what’s powerful, what’s practical, and what’s still TBD

Context Window

Vibe Check: OpenAI’s o3, GPT-4.1, and o4-mini

Our take on what’s powerful, what’s practical, and what’s still TBD

by Vivian Meng and Katie Parrott

ChatGPT-4o/Every illustration.

Was this newsletter forwarded to you? Sign up to get it in your inbox.If you’ve been following AI news this week, you may feel like a kid at Christmas—and like filing a petition for OpenAI to hire a model namer. With o3, GPT‑4.1, and o4‑mini all dropping at once, even AI-savvy teams are asking: Wait, which one are we supposed to use?We’ve spent the last few days running tests, switching between models, breaking a few prompts, and seeing what sticks. Here’s the gist:o3 is OpenAI’s most deliberate thinker and newest flagship model: Built for self-directed complex reasoning and tool use.

GPT‑4.1 is a structured, API-only workhorse built for developers: Great at tight instruction following and long context memory.

o4-mini is the efficiency engine: Fast, affordable, and remarkably strong at math, visual reasoning, and cost-sensitive development work. It won’t steal the spotlight—it’s not OpenAI’s flagship model or the benchmark champ. But its efficacy means it might quietly run half your stack.

Let’s dive into what’s new, what each model does, and what the team at Every thinks after trying them out on our workflows.o3: OpenAI’s most powerful reasoning model
o3 is the first model Every CEO Dan Shipper has been this excited about since GPT‑4, which came out in 2023. It doesn’t just use tools, like GPT-4o, or see images—it thinks with them. What it’s great at:Tool use: o3 knows how to use tools, how to string different tools together, and how to pivot. Say you upload a chart of monthly sales. It might extract the data using optical character recognition (OCR), write Python to calculate your year-over-year growth, and search for industry benchmarks to contextualize the results—all in one go. It can make up to 600 tool calls in a single response, self-improve along the way, and pivot if something breaks. It’s your self-directed analyst with a Swiss Army knife—and the judgment to know which blade to use.

Visual reasoning: It interrogates images with real context. While other models might say, “This is a painting of a woman,” o3 zooms in on the corner, reads the artist’s signature, searches for the museum in which it hangs, and gives you the history of the art movement it’s from.

Automate compliance and accelerate business growth
To scale your company, you need compliance. And by investing in compliance early, you protect sensitive data and simplify the process of meeting industry standards—ensuring long-term trust and security.Vanta helps growing companies achieve compliance quickly and painlessly by automating 35+ frameworks—including SOC 2, ISO 27001, HIPAA, GDPR, and more. Start with Vanta’s Compliance for Startups Bundle, with key resources to accelerate your journey.Get it here
Want to sponsor Every? Click here.

GPT-4.1: Built for precision, not vibes
4.1 is currently available only to developers through the API, and it’s designed to follow detailed instructions with ruthless precision. It’s less dreamy than predecessors like 4.5, but more structured, reliable, and consistent. Think of it as OpenAI’s workhorse for targeted developer tasks, not creative exploration.What it’s great at:Follows complex instructions: GPT-4.1 handles instructions like a seasoned navigator. Say you’re coding a recipe maker. In a single prompt, you might ask to format the response in Markdown, avoid certain topics, output cooking steps in a particular order, and always include a key metric like sodium content. Where past models might fumble or skip steps, 4.1 sticks to your map—even when the path is long, winding, and filled with tricky turns.

It won’t lose your map: With a memory increase to 1 million tokens instead of the 128,000 in older models, you can set the tone or structure once, and it’ll follow through across multiple replies. You don’t need to start from scratch every time.

Thrives on structure: GPT-4.1 is like that friend on a road trip who’s fun to have around—as long as there’s a plan. Give it a clear itinerary, and it executes with clarity and precision. But hand it a “just vibes” prompt like, “Can you make this recipe app feel more like stepping into a cozy speakeasy?” and it might want to go home. The clearer the map, the smoother the ride.

o4-mini: Small, sharp, and surprisingly capable
o4-mini is the latest addition to OpenAI’s “o-series,” its line of reasoning models that are trained to think longer before responding. It’s optimized for both quantity and quality (with a daily cap for consumers of 150 messages opposed to o3’s weekly cap of 50), offering near o3-level performance—especially in math, coding, and visual-heavy tasks—faster and at a fraction of the cost. While o3 is OpenAI’s most powerful reasoning model, o4-mini is your go-to when you want most of o3’s smarts for a bill nine times cheaper. That’s not a mini difference.Source: o4-mini/Vivian Meng.What it’s great at:

Packs a punch for its size: Need to analyze tons of transcript data or summarize messy research tables? o4-mini handles high-volume requests like a pro—filtering for insights, writing structured query language, searching for data, and plotting results on an interactable graph. Where o3 might fire off a dozen reasoning steps (and rack up the token bill), o4-mini cuts to the chase with a clean, usable answer that’s still well-reasoned.Source: o4-mini/Vivian Meng.Same tools, lighter lift: o4-mini gives you o3’s complete toolkit, including Python, web browsing, image analysis and generation, and more. It’s especially handy for tasks like generating a weekly analytics summary: fetching a CSV, running Python to clean and chart the data, searching the web for bird’s-eye-view industry data to contextualize, and producing a markdown report. It does this all in one go, and without o3’s extra compute overhead.
What everyone at Every thinks…
… about o3
o3 thinks like a prompt engineer
“o3 has been a great companion for working on AI stuff. It seems to know a lot about how LLMs work and the different tools and techniques that are out there right now. Other models tend to respond with traditional natural language processing techniques—o3 responds with techniques you'd actually use with LLMs.”—Danny Aziz, general manager of Spiralo3 is the best teacher model yet
“o3 just wrote some amazing Rails tutorials for me—this is clearly the best teacher model out there. It’s the first time it’s felt like a model actually understands my level of understanding and can write an article specifically for me.”—Nityesh Agarwal, engineer on Cora… about 4.1
Built to ship, not to vibe
“This is why I love this model. It’s a dev model—not a vibe coder model. Like GPT-4, but better.”—Kieran Klaassen, general manager of CoraPrecise input, solid output
“4.1 is great if you give it really specific instructions. It doesn’t make great assumptions, but it codes well. That works well for some, not for others.”—Alex Duffy, consulting lead and staff writerGreat for structure, weaker on elegance
“From what I’ve tried, 4.1 is a big step forward for OpenAI. It [earlier models] used to feel lazy, like it didn’t want to code. Now it does the work. But the output still feels off—lower quality than Claude in terms of readability and structure.”—Andrey Galko, engineer4.1 might finally dethrone Sonnet for user interaction work
“I am loving 4.1 for UI tasks. I might have to end my friendship with Sonnet 3.5, finally. One-shotted this UI with 4.1.”—Yash Poojary, general manager of SparkleSource: 4.1/Yash Poojary.But Gemini still leads in Cursor
“Still finding Gemini 2.5 Pro inside Cursor way better than 4.1. Haven’t tried it in Windsurf yet, though.”—Danny… about o4-mini
o4-mini is a visual-processing wiz
“o4-mini-high is replacing 3.7 Sonnet for thinking tasks in Windsurf. More accurate code generation, and even though it feels slower, it ends up faster because it gets more right in one shot.”—Nityesh“I found o4-mini could turn a Sudoku problem from an image to text reliably. Every other model I tried failed.”—DanWhat everyone else thinks…
… about o3
Is o3 OpenAI’s stealth AGI?
Economist Tyler Cowen flatly asked: “Is this AGI?” His conclusion: If o3 isn’t AGI, then what are we expecting? At the same time, he doesn’t expect markets to move much in response to the announcement. “It will still take us a long time to use it properly.”o3 gets enterprise nuance right
Box CEO Aaron Levie says o3 nailed a multi-step financial modeling task that required math, logic, and understanding subtle business context—something no model could do a year ago.… about 4.1
It’s about human collaboration, not just task completion
Cursor head of design Ryo Lu mapped LLMs like coworkers: Gemini is the senior software engineer you have to push, Claude 3.7 is the overthinking tools nerd, and GPT-4.1/o3?: “Started to realize coding isn’t just about benchmarks.”O3 raises the ceiling for agentic reasoning
Scale AI CEO Alexandr Wang called o3 “a meaningful step forward for the industry,” pointing to its seamless, self-directed tool use as “a big breakthrough.” Less reasoning, more instruction-following, faster coding
OpenAI technical staff member Clive Chan notes that 4.1 codes much faster than o3-mini because it reasons less: “4.1 has basically replaced o3-mini for me in all my workflows (Cursor, etc.).”… about o4-mini
o4-mini outsmarts 4.1 on long memory
Daniel Chalef, founder of agent memory provider Zep, ran both models through LongMemEval, a benchmark assessing chat assistants on long-term memory. He found that o4-mini topped the charts in reasoning accuracy, while GPT-4.1 stumbled, despite its massive context window: “Raw context size isn’t everything.” It outpaces o3 on vision
An OpenAI insider says that o4-mini is a considerably better vision model than o3, which echoes what Dan found in his Sudoku test: “I work for OpenAI. o4-mini is actually a _considerably_ better vision model than o3, despite the benchmarks.”It’s incredibly fast at complex math
Scott Swingle, founder of coding assistant Abante AI and previously of Deepmind, gave o4-mini the latest Euler problem (challenging math and computer programming problems for people worldwide to solve). It cracked the problem in two minutes and 55 seconds. The next fastest human? Five minutes and 15 seconds: “I'm stunned. I knew this day was coming but wow. I used to regularly solve these and sometimes came in the top 10 solvers, I know how hard these are.”Where o3 reasons heavily, o4-mini keeps it fast and straightforward
An anonymous engineer fed o4-mini and o3 a math problem, finding that o4-mini produces a more readable and elegant solution, whereas o3’s is complex and involves tables (which it loves, apparently).How the new tools stack up against the competition
4.1 vs Claude 3.7 Sonnet
From our team’s testing, Claude is still the preferred pick for elegance and structure in code, especially when it comes to style coherence and UI. But 4.1 has closed the gap in following instructions, especially when the prompt is well-scoped and specific.o4-mini vs GPT-3.5
Based on what we’ve seen so far, o4-mini is shaping up to be the new go-to “cheap model” for devs who want speed, reliability, and visual processing on a budget. GPT-3.5, released in November 2023, is starting to feel like the long-ago past.Read Dan Shipper's full analysis of o3.Vivian Meng is a producer and operator who produces the Every podcast AI & I. You can follow her on X at @vivnettes and on LinkedIn, and Every on X at @every and on LinkedIn.Katie Parrott is a writer, editor, and content marketer focused on the intersection of technology, work, and culture. You can read more of her work in her newsletter. We build AI tools for readers like you. Automate repeat writing with Spiral. Organize files automatically with Sparkle. Write something great with Lex. Deliver yourself from email with Cora.We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.Get paid for sharing Every with your friends. Join our referral program.Subscribe
What did you think of this post?

Amazing

Good

Meh

Bad

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
