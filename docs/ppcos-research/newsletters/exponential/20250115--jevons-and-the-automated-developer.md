# 🤖 Jevons and the automated developer

**From:** "Azeem Azhar, Exponential View" <exponentialview@substack.com>
**Date:** 2025-01-15T17:21:06.000Z
**Folder:** exponential

---

View this post on the web at https://www.exponentialview.co/p/jevons-and-the-automated-developer

In 1865, William Jevons noticed something strange. When engineers made coal-powered steam engines more efficient, coal consumption didn’t drop - it exploded. This counterintuitive pattern, now known as the Jevons paradox [ https://substack.com/redirect/b5cafd9a-e7d2-4643-9398-4799f40e8ce7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], shows up throughout history: make something easier or cheaper and people find exponentially more ways to use it.
Now, we have to ask… Could something similar happen with software?
If we slash the cost and effort of developing software—thanks to AI-driven tools—will that reduce or increase the amount of software (and the number of developers) we need?
In this essay, I argue that making software development faster and easier will amplify overall demand and lead to more—rather than fewer—opportunities for developers.
Specifically, I will explore five trends that suggest an ever-increasing appetite for software:
Accelerated demand for both software and developers.
A booming collaborative ecosystem fueled by open-source and lower barriers to entry.
Democratisation & untapped talent as AI makes coding more accessible to everyone.
The ongoing need for human expertise to handle complex architecture and regulations.
The rise of ‘just-in-time’ solutions, where apps are spun up on-the-fly.
Building my dream app
I have been coding since I was ten, writing my first programmes in 1982.  I still have my first coding manual at home [ https://substack.com/redirect/c4113dcb-99d8-4825-a001-9fe4e8255f82?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. But I am no professional coder. By 2011, my engineering team asked me to stop, saying my code was… basically… shit. My CTO at the time gently suggested I should simply explain what I wanted instead and his team would build it for me.
Now, AI has ridden to the rescue. Services like Replit [ https://substack.com/redirect/04d33b15-c45b-46af-9202-ed5e58bfc363?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] let you use ordinary language prompts to build working software. Many others, like Cursor [ https://substack.com/redirect/b8549cd0-88f5-4dc8-a90e-8a76d806c13f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Devin [ https://substack.com/redirect/389c769e-5dad-4af9-b3cd-9c9ccacefd55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], let amateur developers (or anyone, really) create working apps.
Rabbits, foxes and Malthus
My interest in ecosystem dynamics began when my mother introduced me to Thomas Malthus’s theories about population instability. In the mid-1980s, I brought these concepts to life by programming ecological simulations on my BBC Micro computer. I still find these models fascinating because they reveal complex feedback loops and show how systems change over time.
While BBC Basic was an accessible programming language in its time, it’s now obsolete. Today’s programming landscape presents a different challenge. Even with generous estimates, only about 100 million people worldwide can create applications independently, including roughly 28 million professional developers. This represents a tiny fraction of the global population, highlighting an often overlooked truth that Replit founder Amjad Masad astutely (and casually) observed [ https://substack.com/redirect/ebe4daa0-ba59-42cc-bdc1-ba00b9f1c16f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Normies have higher expectations of what computers could do. If you ever taught programming, many people think they can just talk to it. Like they think the comments are talking to the machine. So ChatGPT is kind of a “well duh” moment.
I certainly was not talking to my computer when I was eight. But I am now. Starting with an almost incoherent voice note, I was able to create a working simulator of ecosystem dynamics in under ten minutes.
The TL;DR is that you can play with my simulator here [ https://substack.com/redirect/9e02f41f-7e5f-4d5e-bc5f-ce52264c6785?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Let me walk you through how I built it and discuss what it made me realise about AI’s impact on developers.
Claude as my co-developer
I was feeling pretty lazy so I enlisted Claude, a large-language model created by Anthropic, to define the scope of the software. Claude has a voice interface so I jabbered my thoughts as I jogged across the garden to answer the front door. Read my prompt to Claude carefully below. I really didn’t give much thought to it. Between jumbled ideas and poor transcription, I sound a bit boisterous and drunk. (I was neither).
Claude want to use Replit Agent, which is an LLM powered soft web developing tool to develop a really nice quick app. You use a prompt to do this. So I would like it to create an application that shows a Simple Malthusian system of rabbits That Feed off. Rabbits that have babies and then foxes. Foxes eat the rabbits. And you imagine how that feedback loop works, and it should all be charted could you please, write a prompt for me, which I can post into Redcliffe. Do it very detailed.
Claude produced a staggeringly good specification. Honestly, it is a clear professional requirements doc, the kind a good product manager might have produced. An extract is below. The full response is here [ https://substack.com/redirect/876248ce-c21d-419b-a57f-963d4fc92cb2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Create a web application that simulates and visualizes a Lotka-Volterra predator-prey system featuring rabbits and foxes. The application should:
Core Features:

Implement a mathematical model where:

Rabbits reproduce at a constant rate
Rabbits die when eaten by foxes
Foxes reproduce proportionally to how many rabbits they eat
Foxes die at a constant rate without food
Use standard Lotka-Volterra differential equations

Visualization Requirements:

Create a main chart showing:

Population of rabbits over time (blue line)
Population of foxes over time (red line)
X-axis: Time in months
Y-axis: Population counts
Interactive tooltip showing exact values
Superspeed developer
I took the prompt and dumped it into Replit.
With a couple of minutes, I had a full running app. It was buggy. Graphs weren’t visible. It took three iterations for Replit to correct this and five-and-a-half-minutes later the app was running correctly. A couple more minutes and it was deployed to the cloud [ https://substack.com/redirect/9e02f41f-7e5f-4d5e-bc5f-ce52264c6785?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The paradox of progress
So what does this mean? Circling back to the Jevons paradox… Essentially, the Jevons paradox highlights a counterintuitive economic pattern: when something becomes cheaper or easier to access, our consumption tends to increase dramatically rather than decrease or level off. This is an example of positive price elasticity of demand—as prices fall, usage rises.
In the 1970s and ‘80s, shifting from assembly language to higher-level languages like C dramatically increased developer productivity. This, in turn, spurred the creation of large-scale operating systems, more complex software suites, and eventually entire industries (e.g., embedded systems, consumer software for home PCs).
As a result, more code was written and companies hired more developers—not fewer—to handle new products and services. Developers love automations and for decades they have been writing scripts to automate repetitive tasks. Object-oriented languages sped up the coding process. Programming languages have evolved to abstract away complexity, with high-level languages like Python letting developers focus on logic rather than memory management.
The wide adoption of C++, Java, and later C# reduced the complexity of organising large-scale software projects. This contributed to the dot-com boom in the late 1990s, giving rise to e-commerce and large-scale enterprise software.
As a result, the US Bureau of Labor Statistics data shows software developer employment more than doubled from the early ‘90s to the early 2000s, paralleling these efficiency gains. The impact of these automations has been to reduce the cost of producing software, increase the market and with that increase employment.
In the UK, the number of developers doubled between 2011 and 2021.
In the 2000s, Ruby on Rails,  Python and Node.js emerged, making web app development faster and more accessible. GitHub’s open-source community exploded, enabling collaboration and spurring an avalanche of new applications, from social media platforms to niche business tools.
As a result, the global developer population increased from around 18 million in 2014 to over 23 million by 2019, according to Evans Data Corporation [ https://substack.com/redirect/cd1214ae-7492-49a8-836f-0ee858c63cf2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]—despite (or rather, because of) these more “efficient” frameworks.
Will AI-based coding be any different?
I expect that we’ll see…
1. Accelerated demand for both software and developers (probably)
The code gets written faster; we build more features, spin up more side projects and basically keep fuelling the cycle. We’ll see an increase in demand for software—not a decrease—because it’s just so effortless to iterate and release something new. Amazon said the company’s AI assistant had saved them 4500 years of work [ https://substack.com/redirect/661692b2-ec84-4f94-8ae6-3a42b5d74c57?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. But another way of thinking of it is it enabled them to write exponentially more code and build features they wouldn’t have even attempted before.
Let’s put this a different way. Many of us probably have apps we’d like for specific things. Today, we’ll forage the AppStore trying to find the third-party app that kinda, not-quite does what we want. We’re close to the point where we could ask an AI tool to spin it up for us.
We can confidently say that the amount of software people will ask for and use will likely rise substantially. But I do wonder whether we can assume the number of traditional software developers will continue to rise.
After all, we eat more bread than ever before but the number of people involved in threshing wheat has declined somewhat. US agricultural employment peaked in 1920 at about 11.8 million [ https://substack.com/redirect/1f76e9ea-6503-493d-8245-c8862fd5f61e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. By 1950, that number had halved. Today it hovers around two million.
What that means for developers is a bit unclear. On the one hand, it’s reasonably clear the nature of what it is to be a developer will change and involve marshalling and stewarding more higher-level AI code tools. Would the floods of new people (like me!) using tools like Replit count as developers or not? In some sense, yes. We’re producing software. In another, no, because we’re not being paid for it and we don’t deploy the same kind of skillset that developers used in the pre-AI era.
Of course, software development is not a monadic activity like waving a sickle. It’s a highly collaborative activity, often bringing together dispersed groups of people with different experiences and skills. Software is also intangible. The wheat field is threshed, the product can always be better.  Roles that are purely “manual coding” may come under pressure, but new roles (prompt engineer, domain expertise, product management) might expand.
We might also see a high specialization in sofware development, amongst those who build the architecture, security, tooling and infrastructural systems and mass hobbyist engagement on the other hand.
2) Booming collaborative ecosystem
When development costs drop this low, people can build and experiment with ideas that would never have justified the traditional investment of time and money. Take this simulator - I wouldn’t have paid someone to build it, yet it met a real need I had. The process was simple and straightforward. This kind of accessibility could transform open-source collaboration, making it easier for more people to contribute and innovate. As barriers fall, there will be a growing ecosystem of new applications and solutions emerging from this broader pool of creators.
We are already starting to see this. Microsoft reports that more than half of the source code submitted to Github, a repository of open-source code, is now produced, in some way, by generative AI.
3) Democratisation & untapped talent
It used to be that you needed a certain level of grit (and maybe a dash of obsession) to learn programming. But now, with AI smoothing out the experience, people who never considered coding are trying it—and succeeding. Like this eight-year-old girl [ https://substack.com/redirect/b1c114a9-0bf4-49fa-97cd-4b6f0e2a2ab7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I keep imagining all these new folks who might jump in to create tiny niche apps, local solutions, or personal experiments, all because the barrier dropped from “you must master syntax and architecture” to “just describe what you want.”
Some portion of these new users will start to contribute to open-source repositories, extending the trend we described above. This could drive the scale of the open-source ecosystems, well above the levels we see today.
4) Ongoing need for human expertise
Don’t get me wrong: even with all this new accessibility, there’s still plenty of room—and need—for high-level experts. Complex architecture decisions, nuanced performance tuning, and compliance with tough regulations aren’t things you can just wave a prompt at (yet). It’s like the conversation I had with my CTO back in the day. Someone with deeper, more specialised knowledge still has to oversee the entire project, catch pitfalls and keep it all on track.
I predict that the demand for experienced engineers will continue to rise and the wage gap between junior and senior engineers will expand.
5) ‘Just in time’ solutions
Finally, there’s this concept Amjad coined “just in time software [ https://substack.com/redirect/2f371d16-e1b8-4ce1-a52b-1ad1bcfa1882?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]”—little custom CRMs [ https://substack.com/redirect/470059c9-ce4b-4272-a0b4-2d97abdcfbe4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], dashboards, or simulators that you just whip up on the fly. We’re not (yet) at the stage of replicating an entire enterprise system in five minutes, but we are seeing folks stand up surprisingly sophisticated prototypes almost instantly. It satisfies demand you never thought existed—like me wanting a predator-prey simulator on a random Tuesday, just because I could. This is precisely the point: the easier it is, the more we do it and the more surprising ways we find to apply it.
It also changes what we think of software. If we can ask an agent to execute a complicated set of steps, the outcome is a lot like software but the thing itself doesn’t feel like a shrink-wrapped application. It feels like “just getting something done”. Perhaps a new category will emerge. Monetization might shift from app sales or SaaS to ephemeral licensing, micro-transactions or usage-based billing for computational cycles.
Jevons redux
Like coal in the Industrial Revolution, software’s lowered barriers will spark more coding, more apps and likely a reshaped developer job market—but not necessarily fewer professional developers overall.
Freed from many of the complexities that once deterred novices, people like me (and perhaps you!) can now spin up “little apps” for niche needs in minutes rather than weeks. As the line blurs between “coder” and “non-coder,” a flood of new solutions will emerge—from amateur experiments to business-grade software—forming a self-reinforcing cycle of innovation. The cheaper and simpler it gets to build, the more we will want to build, pulling in even greater demand for software (or whatever we call it.)
