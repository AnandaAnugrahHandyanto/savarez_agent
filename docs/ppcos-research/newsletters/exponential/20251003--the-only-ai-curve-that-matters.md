# 🔮 The only AI curve that matters

**From:** "Azeem Azhar, Exponential View" <exponentialview@substack.com>
**Date:** 2025-10-03T17:03:31.000Z
**Folder:** exponential

---

View this post on the web at https://www.exponentialview.co/p/the-only-ai-curve-that-matters

There is one AI metric that we keep a really close eye on:
How many actions can a system take at 99% reliability before a human must intervene?
We call this the 99% step-length: the number of sequential actions an AI can execute with at least 99% reliability without human help.
Today’s frontier systems reliably manage around 100 steps at that threshold. By our estimates, the number could exceed 10,000 by 2029. A couple of years later, they might have between three and ten times that range. At that scale, an AI system could operate for weeks – potentially months – without supervision.
Today, we’ll explain our 99% benchmark and show where we believe the step length of AI could go if the trends continue. Many things could derail this trend, but it’s really important to understand what the world could look like if it does continue.
Autonomy is an illusion below 99%
Earlier this year, researchers at METR  released work showing the length of time that AI can work for on software and coding tasks before failing. It is a great benchmark that we use regularly.
METR’s headline is this: every seven months or so, AI systems are able to undertake tasks twice as long as previously. Their methodology is sound, but they benchmark task length at 50% and 80% success rates. I’ve found that execs often question the usefulness of those levels. A process that works half the time isn’t really one they want to trust.
Even at 90%, one failure in ten attempts would need constant human monitoring. Around 99%, you approach the threshold where autonomous operation becomes viable.
Where are we now?
Today’s leading systems can reliably execute tasks of roughly one hundred steps at 99% accuracy.
By 2029, that figure climbs to around 11,000 steps. In five to six years, between 2030 to 2031, we’d expect the range to widen to somewhere between 37,000 and 120,000 steps, depending on how quickly orchestration layers mature. At those levels, an AI system could operate for weeks or even months without human intervention.
We derived this using recent research [ https://substack.com/redirect/839f199b-36d9-4c5f-b780-48b36559d635?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Sinha and colleagues, which broke down tasks into steps and tested leading models to see how many steps they can execute successfully. Reasoning models performed best because they avoided self-conditioning; they were less likely to be misled by previous mistakes. The team found that at the frontier, GPT-5 can manage 2,176 steps at 80% accuracy.
We backtracked this to get the accuracy per step and then calculated how many steps keep the task at 99% reliability and then applied METR’s seven-month doubling rate to project forward.
The methodology is deliberately simple and rests on three key assumptions:
That per-step reliability continues to improve at roughly its current pace.
Those individual steps don’t get dramatically harder as tasks get longer.
That no surprising technical ceiling appears and stops progress.
All three are plausible and none are guaranteed.
The important thing is that it allows us to imagine a possible timeline for increasing automation.
The 99% is a higher standard than humans consistently achieve. Consider things we do daily, like pouring that first morning glass of water. Over the course of the year, have you let the glass overflow or spilt water on your hand more than four times? If so, your success rate is below 99%.
We set a much higher bar for autonomous systems: machine mistakes can easily cascade into systemic failures very quickly.
VP-level impact by 2030
To understand what this really means, let’s convert tasks of different step lengths into real-world activities.
A 50-step task: a simple research task, perhaps sizing the market for frozen yoghurt in Brazil or identifying key players in an industrial value chain. Represents roughly half a day of focused analyst work. Current systems – Gemini Deep Research, ChatGPT or Manus – can handle this.
At 100 steps, it’s a more substantial piece of work with more complex outputs. You’d expect a decent analyst to take a couple of days to do this. Gemini Deep Research and ChatGPT DeepResearch can easily do this today.
At 2,000 steps, we’re talking about more complex tasks that would normally take about 33 hours or a full week of work. This is the current frontier: Claude 4.5 Sonnet is reportedly [ https://substack.com/redirect/ce9e21da-089f-4f65-8400-f0b7ac7946dd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] capable of autonomously working for 30 hours on a complex coding task. An example here would be designing and implementing a complete software feature, including requirements, architecture, coding, testing and beyond.
By 2029, at 11,000 steps, a system could manage a complete product launch from concept to market, including competitive analysis, product specification, go-to-market strategy, launch execution and cross-functional communication. It’s about a month’s work. Today, we would assign it to a senior product manager. In four years, an AI system might execute the entire arc autonomously.
By 2030, at 37,000 steps, you’re in strategic initiative territory. Consider the kind of project a vice president might undertake: a 4-5 person-month undertaking to conduct an operational or strategic review. Today, the sponsor for a project like this would be very senior and its expected impact profound.
For context, all these projections use a 99% reliability threshold appropriate for mission-critical work.
If this seems unreasonable to expect, we need to remind ourselves that companies are already succeeding with quite long horizon autonomy. Tasks are well-defined and the system has a clear set of instructions.
Consider automated invoice processing in platforms such as Ramp, a finance operations platform. What looks like a single task – “pay this invoice” – is in fact a sequence of discrete actions. The system must capture and read the document, identify the vendor, match it against a purchase order, assign a general ledger code, run duplication and fraud checks, etc, etc. That is at more than a dozen separate steps. If the system processes 600 invoices in a month with only occasional human escalation, it is already running at 7,000-12,000 autonomous steps without intervention.
Lemonade, the insurance platform, claims in its formal SEC 10-K filing [ https://substack.com/redirect/cebcd05d-cd17-4157-ba19-a6d48bdff0ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that 55% of its 63,000 monthly claims are full automated from start to finish. Each claim is probably a couple of dozen individual steps executed successfully about 400,000 times a year.
And, of course, we shouldn’t forget Waymo, which can drive you pretty much anywhere in the Bay Area without intervention. It does so better than a human and a typical drive is probably in the order of 10,000 steps. Waymo’s doing pretty well. The data [ https://substack.com/redirect/51b6451c-08fc-4127-8eec-cfb65325c4ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] shows a roughly 90% reduction in damage or injury compared to human drivers.
What firms must change
It will be a daunting challenge for management teams to accommodate this level of autonomy. Ten-thousand-step level autonomy is more likely to come unstuck for organisational reasons than purely technical ones. No plan survives contact with reality, to paraphrase von Moltke.
It isn’t clear what bosses need to change (indeed what they can change) right now. But we’ll take a shot at it.
First, we’ll likely need to change the way we train and develop people, because employees will be moving into management-like roles, managing AI systems, far faster than before. AI tools will be the ‘individual contributor’, the point where a junior spends their first few years understanding what work really is. If our scenario today holds, people will get to Director-level in a few months, not several years. If traditional professional development paths aren’t working, companies will need to replace them with something. Will it be simulated experiences – such as month-long synthetic projects? Or a deliberate path of learning, practice and certification to measure progress? Or something else?
The second change is in operating cadence. Daily stand-ups and weekly check-ins presume work at a human pace. They don’t match systems that can run 10,000 steps over a weekend or during a lunch break. Humans will review anomalies, not every line of output. Of course, this is already a practice common in complex engineering projects, such as semiconductor design and software development. But it is likely to spread further.
The third adjustment is in economics. At scale, the human’s job, supported by AI tools, may be to audit a portfolio of processes that are running concurrently. Once reliability passes roughly 99%, one human could oversee dozens of processes at a time, intervening only when there is an exception. At that point, the cost of each step collapses – what previously cost dollars per action drops to cents, then fractions of cents. In some cases, it becomes cheaper to rerun a job from scratch than to investigate whether it failed. In fact, it may be easier and cheaper to run important tasks in parallel through two different systems, if they don’t agree, time to step in.
Final words
Over the next five years, autonomy may stretch from hours to months in well-defined tasks. If we look further out – and assuming the curves that have served us so well the past few years behave themselves – multi-billion step tasks, essentially an entire human career, hover into view.
The reality is that we don’t know how exactly this will play out. What we do know is that there is currently a visible pattern, that every seven months or so, AI systems are able to undertake tasks twice as long as previously. Play with that exponential, and you get to the curves we’re projecting.
The timelines don’t portend an instantaneous switchover, but they do show a rapidity. This means it’s incumbent on people to be formally experimenting and deploying because that is the only way you can build the muscle to prepare for that future when it arrives.
Cheers,
A

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuZXhwb25lbnRpYWx2aWV3LmNvL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOelV4TVRReE5USXNJbWxoZENJNk1UYzFPVFV4TkRjME9Td2laWGh3SWpveE56a3hNRFV3TnpRNUxDSnBjM01pT2lKd2RXSXRNakkxTWlJc0luTjFZaUk2SW1ScGMyRmliR1ZmWlcxaGFXd2lmUS5zSlhGYXBZNVlTcmhOVEI3eXN3YWVxMFhFVTloTHdUQzVjNWNHMkdFTHlzIiwicCI6MTc1MTE0MTUyLCJzIjoyMjUyLCJmIjpmYWxzZSwidSI6MTI1NTU5OSwiaWF0IjoxNzU5NTE0NzQ5LCJleHAiOjIwNzUwOTA3NDksImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.ZCftQ1TB4syoi72SBIR-Dp-tO2uXSrfJoecuDf_y4nk?
