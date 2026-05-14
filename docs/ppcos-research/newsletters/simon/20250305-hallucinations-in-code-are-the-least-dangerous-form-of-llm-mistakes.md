# Hallucinations in code are the least dangerous form of LLM mistakes

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-03-05T04:42:46.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/hallucinations-in-code-are-the-least

In this newsletter:
Hallucinations in code are the least dangerous form of LLM mistakes
Notes from my Accessibility and Gen AI podcast appearance
I built an automaton called Squadron
Plus 6 links and 2 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Hallucinations in code are the least dangerous form of LLM mistakes [ https://substack.com/redirect/de6c0b8e-25bc-44b4-a929-39af4e3636ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-03-02
A surprisingly common complaint I see from developers who have tried using LLMs for code is that they encountered a hallucination - usually the LLM inventing a method or even a full software library that doesn't exist - and it crashed their confidence in LLMs as a tool for writing code. How could anyone productively use these things if they invent methods that don't exist?
Hallucinations in code are the least harmful hallucinations you can encounter from a model.
(When I talk about hallucinations here I mean instances where an LLM invents a completely untrue fact, or in this case outputs code references which don't exist at all. I see these as a separate issue from bugs and other mistakes, which are the topic of the rest of this post.)
The real risk from using LLMs for code is that they'll make mistakes that aren't instantly caught by the language compiler or interpreter. And these happen all the time!
The moment you run LLM generated code, any hallucinated methods will be instantly obvious: you'll get an error. You can fix that yourself or you can feed the error back into the LLM and watch it correct itself.
Compare this to hallucinations in regular prose, where you need a critical eye, strong intuitions and well developed fact checking skills to avoid sharing information that's incorrect and directly harmful to your reputation.
With code you get a powerful form of fact checking for free. Run the code, see if it works.
In some setups - ChatGPT Code Interpreter [ https://substack.com/redirect/7cb07aae-3f5f-4d9a-b596-3ee94b2622be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude Code [ https://substack.com/redirect/009375f9-1426-478b-955e-d1437164bc95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], any of the growing number of "agentic" code systems that write and then execute code in a loop - the LLM system itself will spot the error and automatically correct itself.
If you're using an LLM to write code without even running it yourself, what are you doing?
Hallucinated methods are such a tiny roadblock that when people complain about them I assume they've spent minimal time learning how to effectively use these systems - they dropped them at the first hurdle.
My cynical side suspects they may have been looking for a reason to dismiss the technology and jumped at the first one they found.
My less cynical side assumes that nobody ever warned them that you have to put a lot of work in to learn how to get good results out of these systems. I've been exploring their applications for writing code [ https://substack.com/redirect/803b1ca2-3901-4a45-8b7d-b944f7fcaeb8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for over two years now and I'm still learning new tricks (and new strengths and weaknesses) almost every day.
Manually testing code is essential
Just because code looks good and runs without errors doesn't mean it's actually doing the right thing. No amount of meticulous code review - or even comprehensive automated tests - will demonstrably prove that code actually does the right thing. You have to run it yourself!
Proving to yourself that the code works is your job. This is one of the many reasons I don't think LLMs are going to put software professionals out of work.
LLM code will usually look fantastic: good variable names, convincing comments, clear type annotations and a logical structure. This can lull you into a false sense of security, in the same way that a gramatically correct and confident answer from ChatGPT might tempt you to skip fact checking or applying a skeptical eye.
The way to avoid those problems is the same as how you avoid problems in code by other humans that you are reviewing, or code that you've written yourself: you need to actively exercise that code. You need to have great manual QA skills.
A general rule for programming is that you should never trust any piece of code until you've seen it work with your own eye - or, even better, seen it fail and then fixed it.
Across my entire career, almost every time I've assumed some code works without actively executing it - some branch condition that rarely gets hit, or an error message that I don't expect to occur - I've later come to regret that assumption.
Tips for reducing hallucinations
If you really are seeing a deluge of hallucinated details in the code LLMs are producing for you, there are a bunch of things you can do about it.
Try different models. It might be that another model has better training data for your chosen platform. As a Python and JavaScript programmer my favorite models right now are Claude 3.7 Sonnet with thinking turned on, OpenAI's o3-mini-high and GPT-4o with Code Interpreter (for Python).
Learn how to use the context. If an LLM doesn't know a particular library you can often fix this by dumping in a few dozen lines of example code. LLMs are incredibly good at imitating things, and at rapidly picking up patterns from very limited examples. Modern model's have increasingly large context windows - I've recently started using Claude's new GitHub integration [ https://substack.com/redirect/69b8562a-5a5c-45aa-9aef-b9abb587200c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to dump entire repositories into the context and it's been working extremely well for me.
Chose boring technology [ https://substack.com/redirect/3d492f81-9be4-4be8-9c0e-3edc30b9148a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I genuinely find myself picking libraries that have been around for a while partly because that way it's much more likely that LLMs will be able to use them.
I'll finish this rant with a related observation: I keep seeing people say "if I have to review every line of code an LLM writes, it would have been faster to write it myself!"
Those people are loudly declaring that they have under-invested in the crucial skills of reading, understanding and reviewing code written by other people. I suggest getting some more practice in. Reviewing code written for you by LLMs is a great way to do that.
Bonus section: I asked Claude 3.7 Sonnet "extended thinking mode" to review an earlier draft of this post - "Review my rant of a blog entry. I want to know if the argument is convincing, small changes I can make to improve it, if there are things I've missed.". It was quite helpful, especially in providing tips to make that first draft a little less confrontational! Since you can share Claude chats now here's that transcript [ https://substack.com/redirect/13783c3c-f297-4052-a06b-04ea0881c537?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Notes from my Accessibility and Gen AI podcast appearance [ https://substack.com/redirect/b8fdb1c0-eb97-403d-bf35-396dddc854d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-03-02
I was a guest on the most recent episode [ https://substack.com/redirect/a4017481-74e8-4c28-8cde-a8d932e81fa2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the Accessibility + Gen AI Podcast [ https://substack.com/redirect/b7cc93cb-94cc-400f-a142-d9eaae20e4e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], hosted by Eamon McErlean and Joe Devon. We had a really fun, wide-ranging conversation about a host of different topics. I've extracted a few choice quotes from the transcript.
LLMs for drafting alt text
I use LLMs for the first draft of my alt text (22:10 [ https://substack.com/redirect/6f603504-12f7-4260-bd6a-437df5ccf4bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
I actually use Large Language Models for most of my alt text these days. Whenever I tweet an image or whatever, I've got a Claude project called Alt text writer. It's got a prompt and an example. I dump an image in and it gives me the alt text.
I very rarely just use it because that's rude, right? You should never dump text onto people that you haven't reviewed yourself. But it's always a good starting point.
Normally I'll edit a tiny little bit. I'll delete an unimportant detail or I'll bulk something up. And then I've got alt text that works.
Often it's actually got really good taste. A great example is if you've got a screenshot of an interface, there's a lot of words in that screenshot and most of them don't matter.
The message you're trying to give in the alt text is that it's two panels on the left, there's a conversation on the right, there's a preview of the SVG file or something. My alt text writer normally gets that right.
It's even good at summarizing tables of data where it will notice that actually what really matters is that Gemini got a score of 57 and Nova got a score of 53 - so it will pull those details out and ignore [irrelevant columns] like the release dates and so forth.
Here's the current custom instructions prompt I'm using for that Claude Project:
You write alt text for any image pasted in by the user. Alt text is always presented in a fenced code block to make it easy to copy and paste out. It is always presented on a single line so it can be used easily in Markdown images. All text on the image (for screenshots etc) must be exactly included. A short note describing the nature of the image itself should go first.
Is it ethical to build unreliable accessibility tools?
On the ethics of building accessibility tools on top of inherently unreliable technology (5:33 [ https://substack.com/redirect/0b443d40-ea83-499c-8041-eaba884e3c2d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
Some people I've talked to have been skeptical about the accessibility benefits because their argument is that if you give somebody unreliable technology that might hallucinate and make things up, surely that's harming them.
I don't think that's true. I feel like people who use screen readers are used to unreliable technology.
You know, if you use a guide dog - it's a wonderful thing and a very unreliable piece of technology.
When you consider that people with accessibility needs have agency, they can understand the limitations of the technology they're using. I feel like giving them a tool where they can point their phone at something and it can describe it to them is a world away from accessibility technology just three or four years ago.
Why I don't feel threatened as a software engineer
This is probably my most coherent explanation yet of why I don't see generative AI as a threat to my career as a software engineer (33:49 [ https://substack.com/redirect/b22fb6a9-3de2-49de-82b2-a18dc26ad40c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
My perspective on this as a developer who's been using these systems on a daily basis for a couple of years now is that I find that they enhance my value. I am so much more competent and capable as a developer because I've got these tools assisting me. I can write code in dozens of new programming languages that I never learned before.
But I still get to benefit from my 20 years of experience.
Take somebody off the street who's never written any code before and ask them to build an iPhone app with ChatGPT. They are going to run into so many pitfalls, because programming isn't just about can you write code - it's about thinking through the problems, understanding what's possible and what's not, understanding how to QA, what good code is, having good taste.
There's so much depth to what we do as software engineers.
I've said before that generative AI probably gives me like two to five times productivity boost on the part of my job that involves typing code into a laptop. But that's only 10 percent of what I do. As a software engineer, most of my time isn't actually spent with the typing of the code. It's all of those other activities.
The AI systems help with those other activities, too. They can help me think through architectural decisions and research library options and so on. But I still have to have that agency to understand what I'm doing.
So as a software engineer, I don't feel threatened. My most optimistic view of this is that the cost of developing software goes down because an engineer like myself can be more ambitious, can take on more things. As a result, demand for software goes up - because if you're a company that previously would never have dreamed of building a custom CRM for your industry because it would have taken 20 engineers a year before you got any results... If it now takes four engineers three months to get results, maybe you're in the market for software engineers now that you weren't before.
I built an automaton called Squadron [ https://substack.com/redirect/fc50460f-d45d-4f56-b800-985585e3048f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-03-04
I believe that the price you have to pay for taking on a project is writing about it afterwards [ https://substack.com/redirect/24ef82b2-96bb-4eaf-a00d-6ee091e2e8e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. On that basis, I feel compelled to write up my decidedly non-software project from this weekend: Squadron, an automaton.
I've been obsessed with automata [ https://substack.com/redirect/f19cba88-abf6-44f4-b1ec-e8e6160f457e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for decades, ever since I first encountered the Cabaret Mechanical Theater [ https://substack.com/redirect/f622ebde-c09b-4096-95ff-caf029843162?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in Covent Garden in London (there from 1984-2003 - today it's a roaming collection). If you're not familiar with them, they are animated mechanical sculptures. I consider them to be the highest form of art.
For my birthday this year Natalie signed me up for a two day, 16 hour hour weekend class to make one at The Crucible [ https://substack.com/redirect/243c4539-3d73-4565-9f68-e00752ddfa82?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in Oakland. If you live in the SF Bay Area and are not yet aware of the Crucible I'm delighted to introduce you - it's a phenomenal non-profit art school with an enormous warehouse that teaches blacksmithing, glass blowing, welding, ceramics, woodwork and dozens of other crafts. Here's their course catalog [ https://substack.com/redirect/ca04e49d-d2cd-48c8-8f3c-49975426d9b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Go enrich your soul!
I took their class in "Mechanical Sculpture", which turned out to be exactly a class in how to make automata. I guess the term "automota" isn't widely enough known to use in the course description!
The class was small - two students and one instructor - which meant that we got an extremely personalized experience.
What I built
On day one we worked together on a class project. I suggested a pelican, and we built exactly that - a single glorious pelican that flapped its wings and swooped from side to side.
Day two was when we got to build our own things. We'd already built a pelican, but I wanted one of my own... so I figured the only thing better than a pelican is a full squadron of them!
Hence, Squadron. Here's a video of my finished piece in action:
I think it captures their pelican charisma pretty well!
How I built it
I was delighted to learn from the class that the tools needed to build simple automata are actually quite accessible:
A power drill
A saw - we used a Japanese pull saw
Wood glue
Screws
Wood - we mainly worked with basswood, plus I used some poplar wood for the wings
Brass wires and rods
Pliers for working with the wire
The most sophisticated tool we used was a reciprocating scroll saw [ https://substack.com/redirect/b2eaed11-b73f-4eaf-a4f1-7d7030e2a3ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], for cutting shapes out of the wood. We also had access to a bench sander and a drill press, but those really just sped up processes that can be achieved using sand paper and a regular hand drill.
I've taken a lot of photos of pelicans over the years. I found this side-on photograph that I liked of two pelicans in flight:
Then I used the iOS Photos app feature where you can extract an object from a photo as a "sticker" and pasted the result into iOS Notes.
I printed the image from there, which gave me a pelican shape on paper. I cut out just the body and used it to trace the shape onto the wood, then ran the wood through the scroll saw. I made three of these, not paying too much attention to accuracy as it's better for them to have slight differences to each other.
For the wings I started with rectangles of poplar wood, cut using the Japanese saw and attached to the pelican's body using bent brass wire through small drilled holes. I later sketched out a more interesting wing shape on some foam board as a prototype (loosely inspired by photos I had taken), then traced that shape onto the wood and shaped them with the scroll saw and sander.
Most automata are driven using cams [ https://substack.com/redirect/58de58c2-ad3c-4fde-a9ac-f70a4819275f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and that was the pattern we stuck to in our class as well. Cams are incredibly simple: you have a rotating rod (here driven by a 12V 10RPM motor) and you attach an offset disc to it. That disc can then drive all manner of useful mechanisms.
For my pelicans the cams lift rods up and down via a "foot" that sits on the cam. The feet turned out to be essential - we made one from copper and another from wood. Without feet the mechanism was liable to jam.
I made both cams by tracing out shapes with a pencil and then cutting the wood with the scroll saw, then using the drill press to add the hole for the rod.
The front pelican's body sits on a brass rod that lifts up and down, with the wings fixed to wires.
The back two share a single wooden dowel, sitting on brass wires attached to two small holes drilled into the end.
To attach the cams to the drive shaft I drilled a small hole through the cam and the brass drive shaft, then hammered in a brass pin to hold the cam in place. Without that there's a risk of the cam slipping around the driving rod rather than rotating firmly in place.
After adding the pelicans with their fixed wings I ran into a problem: the tension from the wing wiring caused friction between the rod and the base, resulting in the up-and-down motion getting stuck. We were running low on time so our instructor stepped in to help rescue my project with the additional brass tubes shown in the final piece.
What I learned
The main thing I learned from the weekend is that automata building is a much more accessible craft than I had initially expected. The tools and techniques are surprisingly inexpensive, and a weekend (really a single day for my solo project) was enough time to build something that I'm really happy with.
The hardest part turns out to be the fiddling at the very end to get all of the motions just right. I'm still iterating on this now (hence the elastic hair tie and visible pieces of tape) - it's difficult to find the right balance between position, motion and composition. I guess I need to get comfortable with the idea that art is never finished, merely abandoned [ https://substack.com/redirect/7127df83-01eb-48b6-b81f-5b28c9a084ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I've been looking out for a good analog hobby for a while now. Maybe this is the one!
Link 2025-03-01 llm-anthropic #24: Use new URL parameter to send attachments [ https://substack.com/redirect/8c4e047a-6043-497e-ab25-1d1777a8fa7b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic released a neat quality of life improvement today. Alex Albert [ https://substack.com/redirect/25d112b1-fd70-4e5e-8d7d-5b260729a7d4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
We've added the ability to specify a public facing URL as the source for an image / document block in the Anthropic API
Prior to this, any time you wanted to send an image to the Claude API you needed to base64-encode it and then include that data in the JSON. This got pretty bulky, especially in conversation scenarios where the same image data needs to get passed in every follow-up prompt.
I implemented this for llm-anthropic [ https://substack.com/redirect/56d67b71-c396-41ac-9a1d-d8a5bbbf5148?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and shipped it just now in version 0.15.1 (here's the commit [ https://substack.com/redirect/c6c12b15-ccfa-4e5c-8c2c-635e9cabf8d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) - I went with a patch release version number bump because this is effectively a performance optimization which doesn't provide any new features, previously LLM would accept URLs just fine and would download and then base64 them behind the scenes.
In testing this out I had a really impressive result from Claude 3.7 Sonnet. I found a newspaper page [ https://substack.com/redirect/6e5319c4-28e3-4ef7-a81f-e1a2f5173f10?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from 1900 on the Library of Congress (the "Worcester spy.") and fed a URL to the PDF into Sonnet like this:
llm -m claude-3.7-sonnet \
-a 'https://tile.loc.gov/storage-services/service/ndnp/mb/batch_mb_gaia_ver02/data/sn86086481/0051717161A/1900012901/0296.pdf' \
'transcribe all text from this image, formatted as markdown'
I haven't checked every sentence but it appears to have done an excellent job [ https://substack.com/redirect/d3d0aaeb-9fe7-4dd1-82c9-e1a2f279adf2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], at a cost of 16 cents.
As another experiment, I tried running that against my example people template from the schemas feature I released this morning [ https://substack.com/redirect/778e3f89-ad51-42d9-949f-e198675a6584?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm -m claude-3.7-sonnet \
-a 'https://tile.loc.gov/storage-services/service/ndnp/mb/batch_mb_gaia_ver02/data/sn86086481/0051717161A/1900012901/0296.pdf' \
-t people
That only gave me two results [ https://substack.com/redirect/ee3bc387-d515-4711-b841-aae5ffa0c88c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - so I tried an alternative approach where I looped the OCR text back through the same template, using llm logs --cid with the logged conversation ID and -r to extract just the raw response from the logs:
llm logs --cid 01jn7h45x2dafa34zk30z7ayfy -r | \
llm -t people -m claude-3.7-sonnet
... and that worked fantastically well! The result started like this:
{
"items": [
{
"name": "Capt. W. R. Abercrombie",
"organization": "United States Army",
"role": "Commander of Copper River exploring expedition",
"learned": "Reported on the horrors along the Copper River in Alaska, including starvation, scurvy, and mental illness affecting 70% of people. He was tasked with laying out a trans-Alaskan military route and assessing resources.",
"article_headline": "MUCH SUFFERING",
"article_date": "1900-01-28"
},
{
"name": "Edward Gillette",
"organization": "Copper River expedition",
"role": "Member of the expedition",
"learned": "Contributed a chapter to Abercrombie's report on the feasibility of establishing a railroad route up the Copper River valley, comparing it favorably to the Seattle to Skaguay route.",
"article_headline": "MUCH SUFFERING",
"article_date": "1900-01-28"
}
Full response here [ https://substack.com/redirect/ee3bc387-d515-4711-b841-aae5ffa0c88c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-03-02 18f.org [ https://substack.com/redirect/02c0e892-c6d2-4000-bb37-13826e8cdc47?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New site by members of 18F, the team within the US government that were doing some of the most effective work at improving government efficiency.
For over 11 years, 18F has been proudly serving you to make government technology work better. We are non-partisan civil servants. 18F has worked on hundreds of projects, all designed to make government technology not just efficient but effective, and to save money for American taxpayers.
However, all employees at 18F – a group that the Trump Administration GSA Technology Transformation Services Director called "the gold standard" of civic tech – were terminated today at midnight ET.
18F was doing exactly the type of work that DOGE claims to want – yet we were eliminated.
The entire team is now on "administrative leave" and locked out of their computers.
But these are not the kind of civil servants to abandon their mission without a fight:
We’re not done yet.
We’re still absorbing what has happened. We’re wrestling with what it will mean for ourselves and our families, as well as the impact on our partners and the American people.
But we came to the government to fix things. And we’re not done with this work yet.
More to come.
You can follow @team18f.bsky.social [ https://substack.com/redirect/a109d3de-af97-4658-bb24-6d315bbe74d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Bluesky.
Quote 2025-03-02
Regarding the recent blog post [ https://substack.com/redirect/de6c0b8e-25bc-44b4-a929-39af4e3636ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], I think a simpler explanation is that hallucinating a non-existent library is a such an inhuman error it throws people. A human making such an error would be almost unforgivably careless.
Kellan Elliott-McCrea [ https://substack.com/redirect/a8381d52-c443-4381-8302-693e295fce40?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-03-02
After publishing this piece, I was contacted by Anthropic who told me that Sonnet 3.7 would not be considered a 10^26 FLOP model and cost a few tens of millions of dollars to train, though future models will be much bigger.
Ethan Mollick [ https://substack.com/redirect/3262a394-ef77-42ee-a5ec-ef0fe4d7c333?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-03-03 The features of Python's help function [ https://substack.com/redirect/d9993a75-fd1c-4a36-af39-d10aea2a40a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've only ever used Python's help feature by passing references to modules, classes functions and objects to it. Trey Hunner just taught me that it accepts strings too - help("**") tells you about the ** operator, help("if") describes the if statement and help("topics") reveals even more options, including things like help("SPECIALATTRIBUTES") to learn about specific advanced topics.
Link 2025-03-04 llm-mistral 0.11 [ https://substack.com/redirect/704849a9-deca-4f47-9ef3-fab6e1dbe6bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I added schema support [ https://substack.com/redirect/778e3f89-ad51-42d9-949f-e198675a6584?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to this plugin which adds support for the Mistral API [ https://substack.com/redirect/e0a0c1c9-2adb-4a2c-81e9-28ca6b29b5bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to LLM. Release notes:
Support for LLM schemas [ https://substack.com/redirect/2b942a71-bc76-46df-bbc0-d1777395891f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. #19 [ https://substack.com/redirect/48a5a45e-6209-4545-bfb8-03c582ce5c00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
-o prefix '{' option for forcing a response prefix. #18 [ https://substack.com/redirect/c2f92321-1494-42e3-97a4-693da526c90e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Schemas now work with OpenAI, Anthropic, Gemini and Mistral hosted models, plus self-hosted models via Ollama [ https://substack.com/redirect/ad3430e9-404f-4f35-aae4-c0a0cc83fe7e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and llm-ollama [ https://substack.com/redirect/c3980f26-0509-41cd-9349-71e7b08d7036?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-03-04 llm-ollama 0.9.0 [ https://substack.com/redirect/00de7e9b-9d84-43ea-8177-79177e979521?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This release of the llm-ollama plugin adds support for schemas [ https://substack.com/redirect/778e3f89-ad51-42d9-949f-e198675a6584?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], thanks to a PR by Adam Compton [ https://substack.com/redirect/9f76058f-e9c1-4a20-b77e-826655e1ba09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Ollama provides very robust support for this pattern thanks to their structured outputs [ https://substack.com/redirect/f7923ff2-9c6a-4439-a1c0-d0e7db1b8a9f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] feature, which works across all of the models that they support by intercepting the logic that outputs the next token and restricting it to only tokens that would be valid in the context of the provided schema.
With Ollama and llm-ollama installed you can run even run structured schemas against vision prompts for local models. Here's one against Ollama's llama3.2-vision [ https://substack.com/redirect/2b5586f7-8198-4abe-b8d9-a6dbc4352763?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm -m llama3.2-vision:latest \
'describe images' \
--schema 'species,description,count int' \
-a https://static.simonwillison.net/static/2025/two-pelicans.jpg
I got back this:
{
"species": "Pelicans",
"description": "The image features a striking brown pelican with its distinctive orange beak, characterized by its large size and impressive wingspan.",
"count": 1
}
(Actually a bit disappointing, as there are two pelicans [ https://substack.com/redirect/5d9a7ee3-6335-41d2-a797-70a23aaef916?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and their beaks are brown.)
Link 2025-03-04 A Practical Guide to Implementing DeepSearch / DeepResearch [ https://substack.com/redirect/a15390eb-1148-42fe-853a-6540b195ce34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I really like the definitions Han Xiao from Jina AI proposes for the terms DeepSearch and DeepResearch in this piece:
DeepSearch runs through an iterative loop of searching, reading, and reasoning until it finds the optimal answer. [...]
DeepResearch builds upon DeepSearch by adding a structured framework for generating long research reports.
I've recently found myself cooling a little on the classic RAG pattern of finding relevant documents and dumping them into the context for a single call to an LLM.
I think this definition of DeepSearch helps explain why. RAG is about answering questions that fall outside of the knowledge baked into a model. The DeepSearch pattern offers a tools-based alternative to classic RAG: we give the model extra tools for running multiple searches (which could be vector-based, or FTS, or even systems like ripgrep) and run it for several steps in a loop to try to find an answer.
I think DeepSearch is a lot more interesting than DeepResearch, which feels to me more like a presentation layer thing. Pulling together the results from multiple searches into a "report" looks more impressive, but I still worry [ https://substack.com/redirect/be0da713-9cda-4ec4-a0e6-aeb79d103ce8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that the report format provides a misleading impression of the quality of the "research" that took place.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVGcwTVRjNE5ERXNJbWxoZENJNk1UYzBNVEUwT1RjM05Dd2laWGh3SWpveE56Y3lOamcxTnpjMExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuLWl1di1xQmJfTHY2dDhCQlIzcE80Z0hiRGt3TkF6LWR1LWlfVWY4S0poSSIsInAiOjE1ODQxNzg0MSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQxMTQ5Nzc0LCJleHAiOjE3NDM3NDE3NzQsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9._iLN-D5LeOTOfDlE3YODOm8UtmoHcSr01sC0GBbxbb0?
