# 🤔 Why o3 missed what readers caught instantly

**From:** "Azeem Azhar, Exponential View" <exponentialview@substack.com>
**Date:** 2025-07-19T07:03:05.000Z
**Folder:** exponential

---

View this post on the web at https://www.exponentialview.co/p/ai-fact-checking-failed-us-heres

In August 1997, Microsoft Word urged a friend to replace [ https://substack.com/redirect/29789d44-edd2-4a68-ab2e-b17caaa4200a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the phrase “we will not issue a credit note” with the polar opposite—an auto‑confabulation that could have unleashed a costly promise.
Fast‑forward to 17 July 2025: our AI-powered fact‑checker read a sentence claiming Senator Dave McCormick was a mere “hopeful candidate.” It labelled that fact as correct. Two eras, two smarter‑than‑us machines, one constant flaw: when software speaks with misplaced certainty, humans nod. Let’s unpack why.
We use an LLM-powered fact-checker to screen each edition. This fact checker uses o3 (which has access to web search) to decompose the draft into discrete claims and checks them against external sources. This sysyems runs alongside human checkers.
For this item, the mistake that McCormick was a Senate hopeful rather than a sitting senator slipped through.
And to be fair, the sentence didn’t seem outrageous at a glance. The central point was about the scale of US investment in clean energy – hundreds of billions in potential funding. The institutional detail – Senator or Senate candidate – seemed secondary. But that’s exactly the problem. The model, and to some extent our human reviewers, prioritized the big thematic facts and let the specifics slide.
The final catch didn’t come from an LLM. It came from eagle-eyed readers who had the context and were quick to spot the mistake.
Once we realised what had happened, we tried to diagnose the problem. We ran the section through a number of different LLMS (including o3, o3 Pro, Perplexity and Grok). None of them spotted the problem.
We refined the prompts based on feedback from the models, but the problem persisted, even when we explicitly instructed the model to verify people’s roles. Here was iteration three:
The LLM has noticed the discrepancy between our original text and its own discovery. The process continued until we found a cumbersome prompt that identified the mistake.
Weirdly, Marija Gavrilov  ran the text & our most basic prompt through the Dia Browser. Dia draws from a range of different LLMs and it found the the problem immediately.
In other words, the most basic tools outperformed the most advanced ones. This is a textbook illustration of AI’s jagged frontier, [ https://substack.com/redirect/fe01d96e-2a6c-41f2-a8a4-df8b4d3cd3cf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which describes how AI excels at some cognitive tasks while failing unexpectedly at others, with no smooth boundary between the two.
This was instructive failure. Here’s what it taught us.
1. Our hybrid human-AI workflow needs a rethink
Our current editorial process uses LLMs as a first line of review, before human editors step in. The assumption is that the models will catch the obvious mistakes and that our team will catch the subtle ones.
But this case reveals a deeper flaw: the models didn’t catch what should have been obvious because the main point of the story was America’s new industrial policy. A good human subeditor would have caught (or at least checked the claims about McCormick, who isn’t as well known as Trump.) That’s the trust trap. Silence masquerades as certainty. When an LLM returns no objections, our cognitive guard drops; we mistake the absence of alarms for evidence rather than ignorance. How do you avoid it?
Obviously, our human processes need a review, and they will become more onerous. Equally, our automated fact-checking may need to become a multi-step or parallel pipeline with different systems evaluating different classes of claims. I already do this earlier in my research process. I tend to use a couple of different LLMs to start to frame an issue, and use their points of concordance and disagreement as jumping off points for further research.
2. As AI gets embedded into workflows, these risks scale
We’re hardly alone in this. Every organization building AI-infused workflows, especially agentic ones where software takes semi-autonomous actions, will face similar blind spots. Imagine this kind of mistake embedded in a customer service bot, a regulatory filing assistant, or a financial analyst agent executing thousands of queries a day.
When we talk about “edge cases,” this is what we mean.
Not theoretical failure modes, but specific, subtle, compounding errors that emerge from models lacking a coherent internal world model. AI doesn’t “understand” institutions, relationships, or contextual salience. It maps patterns. And sometimes those patterns lead it astray in ways that are invisible – until they aren’t.
A paper last year exploring LLM fact checking [ https://substack.com/redirect/5f6c0c90-37d1-4d09-9ac8-182a0d04afcb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], praised the systems scale and cost effectiveness compared to human fact checking. LLMs were then 20 times cheaper (they have become even cheaper) and a couple of orders of magnitude faster than people. It also identified that “on average, less than 10 % of the claims are factually incorrect in LLM responses”. The trouble is finding that 10%.
If we’re not careful, we’ll automate ignorance—or at least an elided sense of factuality—at scale.
3. The models themselves need work
Even the most capable large language models still lack certain fundamental capabilities. Specifically, these include grounding, internal consistency, and structured knowledge retrieval. Some of this can be addressed at a product level with engineering shims, like external knowledge graphs or explicit reasoning mechanics. But those are exactly that: shims.
One discipline in AI that addresses this from a design perspective is the field of symbolic AI, which offers deterministic reasoning paths, explicit rule-based inference, and verifiable logical consistency—qualities that remain elusive in purely statistical approaches.
For many (if not most) cases, LLMs just work better than symbolic AI. They generalise better, they scale better, and customers love using them. It’s likely that their improved performance in reasoning tasks is due to the fact that, as they scale, they become increasingly adept at neurosymbolic reasoning [ https://substack.com/redirect/0a858d04-1687-4de6-a9fa-d622eb5aeb25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. So the provably verifiable benefits of symbolic approaches have taken a back burner.
My hunch is that the slew of startups tackling verifiable approaches to large models [ https://substack.com/redirect/ad448fa7-f62b-46ba-9197-50ee9663b636?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] may address these issues, or at least shape the trajectory of future AI models. It’s one reason I’m actively seeking great startups in this domain.
Clippy, where art thou
The models we used for our fact checking—and we used the best in the field—failed to resolve a basic contradiction because they don’t reliably map facts to structured institutional knowledge. They can sound confident, but that confidence isn’t tied to correctness.
So set against the sea of progress, we can trace the same cognitive blind spot from Clippy’s heyday to GPT‑era agents. Of course, Clippy came and went; today’s agents are unlikely to. The question is no longer whether we can debug a stray fact, but whether liberal societies and responsible firms can engineer epistemic resilience.
We, for our part, will do better!
Cheers,
A

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuZXhwb25lbnRpYWx2aWV3LmNvL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOamcyTWpnME56WXNJbWxoZENJNk1UYzFNamt4TWpNMk9Dd2laWGh3SWpveE56ZzBORFE0TXpZNExDSnBjM01pT2lKd2RXSXRNakkxTWlJc0luTjFZaUk2SW1ScGMyRmliR1ZmWlcxaGFXd2lmUS5rWEg1SXhCSU9lSzYxMUEyYVkzUFdYbUc1OXpMSEZEWThBcm45ZTRES0pnIiwicCI6MTY4NjI4NDc2LCJzIjoyMjUyLCJmIjpmYWxzZSwidSI6MTI1NTU5OSwiaWF0IjoxNzUyOTEyMzY4LCJleHAiOjIwNjg0ODgzNjgsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.82wvMK0S72x1wXPUYXRC5loAiExfMFkSQRG5RhO3mNI?
