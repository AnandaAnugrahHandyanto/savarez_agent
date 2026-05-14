# Training is not the same as chatting: ChatGPT and other LLMs don't remember everything you say

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-05-29T13:15:51.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/training-is-not-the-same-as-chatting

In this newsletter:
Training is not the same as chatting: ChatGPT and other LLMs don't remember everything you say
Weeknotes: PyCon US 2024
Plus 25 links and 10 quotations and 2 TILs
Training is not the same as chatting: ChatGPT and other LLMs don't remember everything you say [ https://substack.com/redirect/99fd4e76-2f1f-402c-ba09-08a78a62891f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-29
I'm beginning to suspect that one of the most common misconceptions about LLMs [ https://substack.com/redirect/fd9a028d-04b2-47be-920c-a6973505e95e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] such as ChatGPT involves how "training" works.
A common complaint I see about these tools is that people don't want to even try them out because they don't want to contribute to their training data.
This is by no means an irrational position to take, but it does often correspond to an incorrect mental model about how these tools work.
Short version: ChatGPT and other similar tools do not directly learn from and memorize everything that you say to them.
This can be quite unintuitive: these tools imitate a human conversational partner, and humans constantly update their knowledge based on what you say to to them. Computers have much better memory than humans, so surely ChatGPT would remember every detail of everything you ever say to it. Isn't that what "training" means?
That's not how these tools work.
LLMs are stateless functions
From a computer science point of view, it's best to think of LLMs as stateless function calls. Given this input text, what should come next?
In the case of a "conversation" with a chatbot such as ChatGPT or Claude or Google Gemini, that function input consists of the current conversation (everything said by both the human and the bot) up to that point, plus the user's new prompt.
Every time you start a new chat conversation, you clear the slate. Each conversation is an entirely new sequence, carried out entirely independently of previous conversations from both yourself and other users.
Understanding this is key to working effectively with these models. Every time you hit "new chat" you are effectively wiping the short-term memory of the model, starting again from scratch.
This has a number of important consequences:
There is no point at all in "telling" a model something in order to improve its knowledge for future conversations. I've heard from people who have invested weeks of effort pasting new information into ChatGPT sessions to try and "train" a better bot. That's a waste of time!
Understanding this helps explain why the "context length" of a model is so important. Different LLMs have different context lengths, expressed in terms of "tokens" - a token is about 3/4s of a word. This is the number that tells you how much of a conversation the bot can consider at any one time. If your conversation goes past this point the model will "forget" details that occurred at the beginning of the conversation.
Sometimes it's a good idea to start a fresh conversation in order to deliberately reset the model. If a model starts making obvious mistakes, or refuses to respond to a valid question for some weird reason that reset might get it back on the right track.
Tricks like Retrieval Augmented Generation [ https://substack.com/redirect/b74afa9d-c620-478f-b2c2-efe95c11d878?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]and ChatGPT's "memory" [ https://substack.com/redirect/7c6097d2-8ac0-4dcc-b1cc-e1e4dcbcd819?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] make sense only once you understand this fundamental limitation to how these models work.
If you're excited about local models because you can be certain there's no way they can train on your data, you're mostly right: you can run them offline and audit your network traffic to be absolutely sure your data isn't being uploaded to a server somewhere. But...
... if you're excited about local models because you want something on your computer that you can chat to and it will learn from you and then better respond to your future prompts, that's probably not going to work.
So what is "training" then?
When we talk about model training, we are talking about the process that was used to build these models in the first place.
As a big simplification, there are two phases to this. The first is to pile in several TBs of text - think all of Wikipedia, a scrape of a large portion of the web, books, newspapers, academic papers and more - and spend months of time and potentially millions of dollars in electricity crunching through that "pre-training" data identifying patterns in how the words relate to each other.
This gives you a model that can complete sentences, but not necessarily in a way that will delight and impress a human conversational partner. The second phase aims to fix that - this can incorporate instruction tuning or Reinforcement Learning from Human Feedback (RLHF) which has the goal of teaching the model to pick the best possible sequences of words to have productive conversations.
The end result of these phases is the model itself - an enormous (many GB) blob of floating point numbers that capture both the statistical relationships between the words and some version of "taste" in terms of how best to assemble new words to reply to a user's prompts.
Once trained, the model remains static and unchanged - sometimes for months or even years.
Here's a note [ https://substack.com/redirect/98a0ded9-f02b-47de-acc1-88d8a54d15b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from Jason D. Clinton, an engineer who works on Claude 3 at Anthropic:
The model is stored in a static file and loaded, continuously, across 10s of thousands of identical servers each of which serve each instance of the Claude model. The model file never changes and is immutable once loaded; every shard is loading the same model file running exactly the same software.
These models don't change very often!
Reasons to worry anyway
A frustrating thing about this issue is that it isn't actually possible to confidently state "don't worry, ChatGPT doesn't train on your input".
Many LLM providers have terms and conditions that allow them to improve their models based on the way you are using them. Even when they have opt-out mechanisms these are often opted-in by default.
When OpenAI say [ https://substack.com/redirect/b5b56fa2-6608-4e3f-a7ce-123d99dc4761?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] "We may use Content to provide, maintain, develop, and improve our Services" it's not at all clear what they mean by that!
Are they storing up everything anyone says to their models and dumping that into the training run for their next model versions every few months?
I don't think it's that simple: LLM providers don't want random low-quality text or privacy-invading details making it into their training data. But they are notoriously secretive, so who knows for sure?
The opt-out mechanisms are also pretty confusing. OpenAI try to make it as clear as possible that they won't train on any content submitted through their API (so you had better understand what an "API" is), but lots of people don't believe them! I wrote about the AI trust crisis [ https://substack.com/redirect/4379a7d0-9ae5-41cc-9cb3-0075386b86ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] last year: the pattern where many people actively disbelieve model vendors and application developers (such as Dropbox and Slack) that claim they don't train models on private data.
People also worry that those terms might change in the future. There are options to protect against that: if you're spending enough money you can sign contracts with OpenAI [ https://substack.com/redirect/b1550b27-e3d3-4ab9-945c-08467b893391?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and other vendors that freeze the terms and conditions.
If your mental model is that LLMs remember and train on all input, it's much easier to assume that developers who claim they've disabled that ability may not be telling the truth. If you tell your human friend to disregard a juicy piece of gossip you've mistakenly passed on to them you know full well that they're not going to forget it!
The other major concern is the same as with any cloud service: it's reasonable to assume that your prompts are still logged for a period of time, for compliance and abuse reasons, and if that data is logged there's always a chance of exposure thanks to an accidental security breach.
What about "memory" features?
To make things even more confusing, some LLM tools are introducing features that attempt to work around this limitation.
ChatGPT recently added a memory feature [ https://substack.com/redirect/bd339716-a57a-48ca-af60-0dc5fe7163f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]where it can "remember" small details and use them in follow-up conversations.
As with so many LLM features this is a relatively simple prompting trick: during a conversation the bot can call a mechanism to record a short note - your name, is a preference you have expressed - which will then be invisibly included in the chat context passed in future conversations.
You can review (and modify) the list of remembered fragments at any time, and ChatGPT shows a visible UI element any time it adds to its memory.
Bad policy based on bad mental models
One of the most worrying results of this common misconception concerns people who make policy decisions for how LLM tools should be used.
Does your company ban all use of LLMs because they don't want their private data leaked to the model providers?
They're not 100% wrong - see reasons to worry anyway [ https://substack.com/redirect/efa20d40-ffe8-4545-888c-918ab0a2a9f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - but if they are acting based on the idea that everything said to a model is instantly memorized and could be used in responses to other users they're acting on faulty information.
Even more concerning is what happens with lawmakers. How many politicians around the world are debating and voting on legislation involving these models based on a science fiction idea of what they are and how they work?
If people believe ChatGPT is a machine that instantly memorizes and learns from everything anyone says to it there is a very real risk they will support measures that address invented as opposed to genuine risks involving this technology.
Weeknotes: PyCon US 2024 [ https://substack.com/redirect/ef79ed7b-dba9-4efe-889c-d5dd2a1104bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-28
Earlier this month I attended PyCon US 2024 [ https://substack.com/redirect/fa2f31a0-a065-4b25-889b-1aedd98ba45f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in Pittsburgh, Pennsylvania. I gave an invited keynote on the Saturday morning titled "Imitation intelligence", tying together much of what I've learned about Large Language Models over the past couple of years and making the case that the Python community has a unique opportunity and responsibility to help try to nudge this technology in a positive direction.
The video isn't out yet but I'll publish detailed notes to accompany my talk (using my annotated presentation format [ https://substack.com/redirect/8d01d4ca-9aa7-46ce-b127-829e55e36cb8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) as soon as it goes live on YouTube.
PyCon was a really great conference. Pittsburgh is a fantastic city, and I'm delighted that PyCon will be in the same venue next year so I can really take advantage of the opportunity to explore in more detail.
I also realized that it's about time Datasette participated in the PyCon sprints - the project is mature enough for that to be a really valuable opportunity now. I'm looking forward to leaning into that next year.
I'm on a family-visiting trip back to the UK at the moment, so taking a bit of time off from my various projects.
LLM support for new models
The big new language model releases from May were OpenAI GPT-4o and Google's Gemini Flash. I released LLM 0.14 [ https://substack.com/redirect/428aa3ef-e6cb-4099-a3ba-e3717d86e6bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], datasette-extract 0.1a7 [ https://substack.com/redirect/8f80d410-23b9-4d1f-8555-1fca92b00183?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and datasette-enrichments-gpt 0.5 [ https://substack.com/redirect/6f17f279-c6b0-468c-8f2c-7193875ccf1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with support for GPT-4o, and llm-gemini 0.1a4 [ https://substack.com/redirect/41449c3a-3e0b-4167-bfc9-c9b472c61daa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]adding support for the new inexpensive Gemini 1.5 Flash.
Gemini 1.5 Flash is a particularly interesting model: it's now ranked 9th [ https://substack.com/redirect/b2c979c2-7212-48e4-aed5-5bc0d3c4dc8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on the LMSYS leaderboard, beating Llama 3 70b. It's inexpensive, priced close to Claude 3 Haiku [ https://substack.com/redirect/070b3c3b-378a-48b0-b20e-f7f947ee6084?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and can handle up to a million tokens of context.
I'm also excited about GPT-4o - half the price of GPT-4 Turbo, around twice as fast and it appears to be slightly more capable too. I've been getting particularly good results from it for structured data extraction using datasette-extract [ https://substack.com/redirect/1a88150e-e96e-4e21-a393-99d037cc39a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it seems to be able to more reliably produce a longer sequence of extracted rows from a given input.
Blog entries
ChatGPT in "4o" mode is not running the new features yet [ https://substack.com/redirect/e95ef1b8-3309-488f-b6fa-6a44d02cea3e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Slop is the new name for unwanted AI-generated content [ https://substack.com/redirect/447d822a-2f06-4153-97e9-a2bf85914ea1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Releases
datasette-permissions-metadata 0.1 [ https://substack.com/redirect/26465669-e8fe-4d80-aff5-f0b906af4fcf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-15
Configure permissions for Datasette 0.x in metadata.json
datasette-enrichments-gpt 0.5 [ https://substack.com/redirect/6f17f279-c6b0-468c-8f2c-7193875ccf1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-15
Datasette enrichment for analyzing row data using OpenAI's GPT models
datasette-extract 0.1a7 [ https://substack.com/redirect/8f80d410-23b9-4d1f-8555-1fca92b00183?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-15
Import unstructured data (text and images) into structured tables
llm-gemini 0.1a4 [ https://substack.com/redirect/41449c3a-3e0b-4167-bfc9-c9b472c61daa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-14
LLM plugin to access Google's Gemini family of models
llm 0.14 [ https://substack.com/redirect/428aa3ef-e6cb-4099-a3ba-e3717d86e6bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-13
Access large language models from the command-line
TILs
Listen to a web page in Mobile Safari [ https://substack.com/redirect/8b64bdda-4ecc-4083-90f7-e2180dec14df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-21
How I studied for my Ham radio general exam [ https://substack.com/redirect/5972a525-c6b5-4621-b670-6c43d84635a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-11
Link 2024-05-17 Programming mantras are proverbs [ https://substack.com/redirect/a456e649-ab00-462b-839e-0a484436eae5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I like this idea from Luke Plant that the best way to think about mantras like "Don’t Repeat Yourself" is to think of them as proverbs that can be accompanied by an equal and opposite proverb.
DRY, "Don't Repeat Yourself" matches with WET, "Write Everything Twice".
Proverbs as tools for thinking, not laws to be followed.
Link 2024-05-17 PSF announces a new five year commitment from Fastly [ https://substack.com/redirect/85865c54-675d-4bbd-96cb-d188ad59a25e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fastly have been donating CDN resources to Python - most notably to the PyPI package index - for ten years now.
The PSF just announced at PyCon US that Fastly have agreed to a new five year commitment. This is a really big deal, because it addresses the strategic risk of having a key sponsor like this who might change their support policy based on unexpected future conditions.
Thanks, Fastly. Very much appreciated!
Quote 2024-05-17
I have seen the extremely restrictive off-boarding agreement that contains nondisclosure and non-disparagement provisions former OpenAI employees are subject to. It forbids them, for the rest of their lives, from criticizing their former employer. Even acknowledging that the NDA exists is a violation of it.
If a departing employee declines to sign the document, or if they violate it, they can lose all vested equity they earned during their time at the company, which is likely worth millions of dollars.
Kelsey Piper [ https://substack.com/redirect/d03a7e9c-e182-4d9b-943f-8579458cdc8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-17 Commit: Add a shared credentials relationship from twitter.com to x.com [ https://substack.com/redirect/2b88a584-c06a-4299-81b0-63e650decd3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A commit toshared-credentials.jsonin Apple'spassword-manager-resourcesrepository. Commit message: "Pour one out."
Link 2024-05-17 Understand errors and warnings better with Gemini [ https://substack.com/redirect/ff3889bc-792e-4f96-a0f8-ef3de50856ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
As part of Google's Gemini-in-everything strategy, Chrome DevTools now includes an opt-in feature for passing error messages in the JavaScript console to Gemini for an explanation, via a lightbulb icon.
Amusingly, this documentation page includes a warning about prompt injection:
Many of LLM applications are susceptible to a form of abuse known as prompt injection. This feature is no different. It is possible to trick the LLM into accepting instructions that are not intended by the developers.
They include a screenshot of a harmless example, but I'd be interested in hearing if anyone has a theoretical attack that could actually cause real damage here.
Quote 2024-05-18
I rewrote it [the Oracle of Bacon] in Rust in January 2023 when I switched over to TMDB as a data source. The new data source was a deep change, and I didn’t want the headache of building it in the original 1990s-era C codebase.
Patrick Reynolds [ https://substack.com/redirect/75b4663c-98e6-4a1c-baaf-e1913a36ac72?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-18 AI counter app from my PyCon US keynote [ https://substack.com/redirect/105dfbf2-341d-4db8-886b-562d616740f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
In my keynote at PyCon US this morning I ran a counter at the top of my screen that automatically incremented every time I said the words "AI" or "artificial intelligence", using vosk [ https://substack.com/redirect/f9de9ed8-b70e-470a-8ab8-a575fcef5db6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], pyaudio [ https://substack.com/redirect/7c6d826a-1f4c-4994-8416-ffc822ee4b54?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Tkinter. I wrote it in a few minutes with the help of GPT-4o [ https://substack.com/redirect/6065f7ec-5f84-4b8b-a01e-e4adeac1e540?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - here's the code I ran as a GitHub repository.
I'll publish full detailed notes from my talk once the video is available on YouTube.
Link 2024-05-19 A Plea for Sober AI [ https://substack.com/redirect/9ce905df-0d93-479b-bc17-de375a4983c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Great piece by Drew Breunig: "Imagine having products THIS GOOD and still over-selling them."
Link 2024-05-19 Fast groq-hosted LLMs vs browser jank [ https://substack.com/redirect/853bc7d2-0c25-4745-b123-b16bbc1f1a7f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Groq [ https://substack.com/redirect/30075587-252e-4448-8654-f221879a5284?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is now serving LLMs such as Llama 3 so quickly that JavaScript which attempts to render Markdown strings on every new token can cause performance issues in browsers.
Taras Glek's solution [ https://substack.com/redirect/23d0fc3e-8b5c-45a0-8e0e-24db1291ad09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was to move the rendering to a requestAnimationFrame callback, effectively buffering the rendering to the fastest rate the browser can support.
Link 2024-05-19 NumFOCUS DISCOVER Cookbook: Minimal Measures [ https://substack.com/redirect/7245ba81-94d7-4e5c-a786-66495b353bf5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
NumFOCUS publish a guide [ https://substack.com/redirect/b5ed9310-abac-4669-b46b-80a121f6f9cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] "for organizers of conferences and events to support and encourage diversity and inclusion at those events."
It includes this useful collection of the easiest and most impactful measures that events can put in place, covering topics such as accessibility, speaker selection, catering and provision of gender-neutral restrooms.
Link 2024-05-19 Spam, junk … slop? The latest wave of AI behind the ‘zombie internet’ [ https://substack.com/redirect/948258e4-9219-4ab0-b49d-ea4d33cc3029?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I'm quoted in this piece in the Guardian about slop:
I think having a name for this is really important, because it gives people a concise way to talk about the problem.
Before the term ‘spam’ entered general use it wasn’t necessarily clear to everyone that unwanted marketing messages were a bad way to behave. I’m hoping ‘slop’ has the same impact – it can make it clear to people that generating and publishing unreviewed AI-generated content is bad behaviour.
Link 2024-05-20 CRDT: Text Buffer [ https://substack.com/redirect/c38f265b-566e-419a-a410-30f2dad14fef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Delightfully short and clear explanation of the CRDT approach to collaborative text editing by Evan Wallace (of Figma and esbuild fame), including a neat interactive demonstration of how the algorithm works even when the network connection between peers is temporarily paused.
Quote 2024-05-20
Last September, I received an offer from Sam Altman, who wanted to hire me to voice the current ChatGPT 4.0 system. He told me that he felt that by my voicing the system, I could bridge the gap between tech companies and creatives and help consumers to feel comfortable with the seismic shift concerning humans and AI. He said he felt that my voice would be comforting to people. After much consideration and for personal reasons, I declined the offer.
Scarlett Johansson [ https://substack.com/redirect/b4c2801f-da04-4844-b183-3f5d2da8bd2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-21 Scaling Monosemanticity: Extracting Interpretable Features from Claude 3 Sonnet [ https://substack.com/redirect/c72b21c9-6bf4-4a25-b50c-1fd9ac641bfd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Big advances in the field of LLM interpretability from Anthropic, who managed to extract millions of understandable features from their production Claude 3 Sonnet model (the mid-point between the inexpensive Haiku and the GPT-4-class Opus).
Some delightful snippets in here such as this one:
We also find a variety of features related to sycophancy, such as an empathy / “yeah, me too” feature 34M/19922975, a sycophantic praise feature 1M/847723, and a sarcastic praise feature 34M/19415708.
Link 2024-05-21 New Phi-3 models: small, medium and vision [ https://substack.com/redirect/438c2fa5-7936-40ed-8504-b470239f76ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I couldn't find a good official announcement post to link to about these three newly released models, but this post on LocalLLaMA on Reddit has them in one place: Phi-3 small (7B), Phi-3 medium (14B) and Phi-3 vision (4.2B) (the previously released model was Phi-3 mini - 3.8B).
You can try out the vision model directly here [ https://substack.com/redirect/7eb5755f-f5d0-44b8-8d2f-c5e93eb8b7b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], no login required. It didn't do a great job [ https://substack.com/redirect/80e7eca6-6d42-42c0-b46d-5186c4019de5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with my first test image though, hallucinating the text.
As with Mini these are all released under an MIT license.
UPDATE: Here's a page from the newly published Phi-3 Cookbook [ https://substack.com/redirect/de8f2df7-bd24-4850-ad3a-017196669189?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] describing the models in the family.
TIL 2024-05-21 Listen to a web page in Mobile Safari [ https://substack.com/redirect/8b64bdda-4ecc-4083-90f7-e2180dec14df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I found a better way to listen to a whole web page through text-to-speech on Mobile Safari today. …
Link 2024-05-22 Mastering LLMs: A Conference For Developers & Data Scientists [ https://substack.com/redirect/5b193846-66ca-4174-ae1a-ad6909a6ef45?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I'm speaking at this 5-week (maybe soon 6-week) long online conference about LLMs, presenting about "LLMs on the command line".
Other speakers include Jeremy Howard, Sophia Yang from Mistral, Wing Lian of Axolotl, Jason Liu of Instructor, Paige Bailey from Google, my former co-worker John Berryman and a growing number of fascinating LLM practitioners.
It's been fun watching this grow from a short course on fine-tuning LLMs to a full-blown multi-week conference over the past few days!
Quote 2024-05-22
The default prefix used to be "sqlite_". But then Mcafee started using SQLite in their anti-virus product and it started putting files with the "sqlite" name in the c:/temp folder. This annoyed many windows users. Those users would then do a Google search for "sqlite", find the telephone numbers of the developers and call to wake them up at night and complain. For this reason, the default name prefix is changed to be "sqlite" spelled backwards.
D. Richard Hipp, 18 years ago [ https://substack.com/redirect/c18681a3-d9a3-42bd-a08a-51139b77e409?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-22 What is prompt optimization? [ https://substack.com/redirect/961ea072-712e-45c6-a7ca-883d8d5b89a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Delightfully clear explanation of a simple automated prompt optimization strategy from Jason Liu. Gather a selection of examples and build an evaluation function to return a numeric score (the hard bit). Then try different shuffled subsets of those examples in your prompt and look for the example collection that provides the highest averaged score.
Quote 2024-05-23
The most effective mechanism I’ve found for rolling out No Wrong Door is initiating three-way conversations when asked questions. If someone direct messages me a question, then I will start a thread with the question asker, myself, and the person I believe is the correct recipient for the question. This is particularly effective because it’s a viral approach: rolling out No Wrong Door just requires any one of the three participants to adopt the approach.
Will Larson [ https://substack.com/redirect/eddafb2c-914f-4ba7-806b-7eb05682f675?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-24 A Grand Unified Theory of the AI Hype Cycle [ https://substack.com/redirect/a3ef3d07-187d-4a0d-be5d-8a6e7b5ee127?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Glyph outlines the pattern of every AI hype cycle since the 1960s: a new, novel mechanism is discovered and named. People get excited, and non-practitioners start hyping it as the path to true "AI". It eventually becomes apparent that this is not the case, even while practitioners quietly incorporate this new technology into useful applications while downplaying the "AI" branding. A new mechanism is discovered and the cycle repeats.
Quote 2024-05-24
But increasingly, I’m worried that attempts to crack down on the cryptocurrency industry — scummy though it may be — may result in overall weakening of financial privacy, and may hurt vulnerable people the most. As they say, “hard cases make bad law”.
Molly White [ https://substack.com/redirect/5959b0b1-f065-4eff-9606-c0780c998d68?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-24 Some goofy results from ‘AI Overviews’ in Google Search [ https://substack.com/redirect/e3fbdc13-94c1-4d20-9df9-44a25ec1f955?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
John Gruber collects two of the best examples of Google's new AI overviews going horribly wrong.
Gullibility is a fundamental trait of all LLMs, and Google's new feature apparently doesn't know not to parrot ideas it picked up from articles in the Onion, or jokes from Reddit.
I've heard that LLM providers internally talk about "screenshot attacks" - bugs where the biggest risk is that someone will take an embarrassing screenshot.
In Google search's case this class of bug feels like a significant reputational threat.
Quote 2024-05-24
The leader of a team - especially a senior one - is rarely ever the smartest, the most expert or even the most experienced.
Often it’s the person who can best understand individuals’ motivations and galvanize them towards an outcome, all while helping them stay cohesive.
Nivia Henry [ https://substack.com/redirect/aed72729-2eb5-4a2f-abeb-f5b6eb08cb2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-05-24
I just left Google last month. The "AI Projects" I was working on were poorly motivated and driven by this panic that as long as it had "AI" in it, it would be great. This myopia is NOT something driven by a user need. It is a stone cold panic that they are getting left behind.
The vision is that there will be a Tony Stark like Jarvis assistant in your phone that locks you into their ecosystem so hard that you'll never leave. That vision is pure catnip. The fear is that they can't afford to let someone else get there first.
Scott Jenson [ https://substack.com/redirect/09112a78-645d-454f-a88b-398b76f927a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-24 Nilay Patel reports a hallucinated ChatGPT summary of his own article [ https://substack.com/redirect/31c22f1a-ea24-4077-a88c-8577ac0a7c33?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here's a ChatGPT bug that's a new twist on the old issue [ https://substack.com/redirect/8b2dd582-b6ea-4cd3-8daa-6e47b4a1b77b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where it would hallucinate the contents of a web page based on the URL.
The Verge editor Nilay Patel asked for a summary of one of his own articles, pasting in the URL.
ChatGPT 4o replied with an entirely invented summary full of hallucinated details.
It turns out The Verge blocks ChatGPT's browse mode from accessing their site in their robots.txt [ https://substack.com/redirect/5fb8ede7-bbb7-4dad-9d57-66ba59926d26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
User-agent: ChatGPT-User
Disallow: /

Clearly ChatGPT should reply that it is unable to access the provided URL, rather than inventing a response that guesses at the contents!
Link 2024-05-24 Golden Gate Claude [ https://substack.com/redirect/330ccb4a-d896-4158-b841-25fae8d813e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This is absurdly fun and weird. Anthropic's recent LLM interpretability research [ https://substack.com/redirect/e6ec669d-3e9c-417d-8f19-72e4dcefc950?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] gave them the ability to locate features within the opaque blob of their Sonnet model and boost the weight of those features during inference.
For a limited time only they're serving a "Golden Gate Claude" model which has the feature for the Golden Gate Bridge boosted. No matter what question you ask it the Golden Gate Bridge is likely to be involved in the answer in some way. Click the little bridge icon in the Claude UI to give it a go.
I asked for names for a pet pelican and the first one it offered was this:
Golden Gate - This iconic bridge name would be a fitting moniker for the pelican with its striking orange color and beautiful suspension cables.
And from a recipe for chocolate covered pretzels [ https://substack.com/redirect/dd19f7ca-b6f3-4fff-a74b-c33d0f3a0f18?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Gently wipe any fog away and pour the warm chocolate mixture over the bridge/brick combination. Allow to air dry, and the bridge will remain accessible for pedestrians to walk along it.
UPDATE: I think the experimental model is no longer available [ https://substack.com/redirect/9605b7a6-bfa2-465e-ac15-2b6562206b18?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], approximately 24 hours after release. We'll miss you, Golden Gate Claude.
Link 2024-05-25 Why Google’s AI might recommend you mix glue into your pizza [ https://substack.com/redirect/5ee62d51-dc98-44a9-b70a-d9a490c9581d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I got "distrust and verify" as advice on using LLMs into this Washington Post piece by Shira Ovide.
Link 2024-05-26 Statically Typed Functional Programming with Python 3.12 [ https://substack.com/redirect/03961e6b-d050-4ab2-8c49-369776d01d4b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Oskar Wickström builds a simple expression evaluator that demonstrates some new patterns enabled by Python 3.12, incorporating the match operator, generic types and type aliases.
Link 2024-05-26 City In A Bottle – A 256 Byte Raycasting System [ https://substack.com/redirect/0fb0d37c-e140-4cf3-82eb-d64bf82f31af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Frank Force explains his brilliant 256 byte canvas ray tracing animated cityscape demo in detail.
Link 2024-05-27 fastlite [ https://substack.com/redirect/e08dda4b-1dc9-4927-8e22-d49c98f3385a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New Python library from Jeremy Howard that adds some neat utility functions and syntactic sugar to my sqlite-utils [ https://substack.com/redirect/46370634-4a13-4cfe-bec5-b48b6140dc4d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Python library, specifically for interactive use in Jupyter notebooks.
The autocomplete support through newly exposed dynamic properties is particularly neat, as is the diagram(db.tables) utility for rendering a graphviz diagram showing foreign key relationships between all of the tables.
Link 2024-05-28 Pyodide 0.26 Release [ https://substack.com/redirect/1aa0fc8f-6b6f-4373-a695-fea3ea591022?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
PyOdide provides Python packaged for browser WebAssembly alongside an ecosystem of additional tools and libraries to help Python and JavaScript work together.
The latest release bumps the Python version up to 3.12, and also adds support for pygame-ce [ https://substack.com/redirect/882520de-6955-442d-b22a-fb9ae9f5c141?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], allowing games written using pygame to run directly in the browser.
The PyOdide community also just landed [ https://substack.com/redirect/9d31fca4-0e68-4e3d-bca2-f1837151c8b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a 14-month-long PR adding support to cibuildwheel, which should make it easier to ship binary wheels targeting PyOdide.
Link 2024-05-28 Reproducing GPT-2 (124M) in llm.c in 90 minutes for $20 [ https://substack.com/redirect/34dd0657-22b8-41c4-8c92-856e041cd25e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
GPT-2 124M was the smallest model in the GPT-2 series released by OpenAI back in 2019. Andrej Karpathy's llm.c is an evolving 4,000 line C/CUDA implementation which can now train a GPT-2 model from scratch in 90 minutes against a 8X A100 80GB GPU server. This post walks through exactly how to run the training, using 10 billion tokens of FineWeb.
Andrej notes that this isn't actually that far off being able to train a GPT-3:
Keep in mind that here we trained for 10B tokens, while GPT-3 models were all trained for 300B tokens. [...] GPT-3 actually didn't change too much at all about the model (context size 1024 -> 2048, I think that's it?).
Estimated cost for a GPT-3 ADA (350M parameters)? About $2,000 [ https://substack.com/redirect/3aa57d72-f9cf-4c0b-a1f0-a52f8bb55904?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2024-05-29
Sometimes the most creativity is found in enumerating the solution space. Design is the process of prioritizing tradeoffs in a high dimensional space. Understand that dimensionality.
Chris Perry [ https://substack.com/redirect/19da340b-d313-4383-b34d-0a062b63a587?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-29 What We Learned from a Year of Building with LLMs (Part I) [ https://substack.com/redirect/55a1fb8d-2b77-4dc0-ae6d-a7bc837827c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Accumulated wisdom from six experienced LLM hackers. Lots of useful tips in here. On providing examples in a prompt:
If n is too low, the model may over-anchor on those specific examples, hurting its ability to generalize. As a rule of thumb, aim for n ≥ 5. Don’t be afraid to go as high as a few dozen.
There's a recommendation not to overlook keyword search when implementing RAG - tricks with embeddings can miss results for things like names or acronyms, and keyword search is much easier to debug.
Plus this tip on using the LLM-as-judge pattern for implementing automated evals:
Instead of asking the LLM to score a single output on a Likert scale, present it with two options and ask it to select the better one. This tends to lead to more stable results.
TIL 2024-05-29 Cloudflare redirect rules with dynamic expressions [ https://substack.com/redirect/10f5f836-002d-462a-a117-b3ef8cb0ea6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wanted to ensure
https://niche-museums.com/
would redirect to
https://www.niche-museums.com/
- including any path - using Cloudflare. …
Quote 2024-05-29
In their rush to cram in “AI” “features”, it seems to me that many companies don’t actually understand why people use their products. [...] Trust is a precious commodity. It takes a long time to build trust. It takes a short time to destroy it.
Jeremy Keith [ https://substack.com/redirect/ff338d6f-5a0b-443e-95e0-88c064017d3a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORFV3T1RJME56SXNJbWxoZENJNk1UY3hOams0T0RVNE15d2laWGh3SWpveE56RTVOVGd3TlRnekxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuTzBKZTBfWDRTMzZnbXd3R04xZnZ2Y0RsZlA0VFoyS2NpQlJUS0NWZVBiayZleHBpcmVzPTM2NWQiLCJwIjoxNDUwOTI0NzIsInMiOjExNzMzODYsImYiOnRydWUsInUiOjEyNTU1OTksImlhdCI6MTcxNjk4ODU4MywiZXhwIjoxNzE5NTgwNTgzLCJpc3MiOiJwdWItMCIsInN1YiI6ImxpbmstcmVkaXJlY3QifQ.MJXAhjewl5PURl88-diukBKVr9vpWRFgu86oHhTuiyQ?
