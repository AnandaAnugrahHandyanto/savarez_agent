# 🔮 Six mental models for working with AI

**From:** "Azeem Azhar, Exponential View" <exponentialview@substack.com>
**Date:** 2025-12-29T16:03:36.000Z
**Folder:** exponential

---

View this post on the web at https://www.exponentialview.co/p/six-mental-models-for-working-with

The question of whether AI is “good enough” for serious knowledge work has been answered. The models crossed that threshold this year. What’s slowing organizations down now isn’t capability, but the need to redesign work around what these systems can do.
We’ve spent the past 18 months figuring out how. We made plenty of mistakes but today I want to share what survived. Six mental models that can genuinely change the quality of work you get from generative AI. Together with the seven lessons we shared earlier in the year [ https://substack.com/redirect/15814833-fc24-4fd5-97a8-a91e6aa66272?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], this is the operating manual we wish we had all along.
At the end, you’ll also get access to our internal stack of 50+ AI tools. We’ve documented everything we’re actively using, testing or intend to test, to help you decide what tools might work for you.
Enjoy!
1. The 50x reframe
Most people start working with AI by asking something along the lines of: how do I speed up what I’m already doing?
That question is comfortable and wrong. I find that it anchors me to existing constraints.
A more useful question is:
What would I do if I had 50 people working on this?
Then work backwards.
The 50x reframe forces you to imagine the ideal outcome unconstrained by time or labor. Only then do you ask which parts of that hypothetical organization can be simulated with software. I now encourage our team members to think of who they would hire, what work that person would do, how they’d know if they were successful.
If you’ve not had the experience of hiring fifty people on a project (fair enough!), use this prompt to get you started to identify what it is that you may need:
A prompt you could use:
I currently [describe your task/process]. Walk me through what this would look like if I had a team of 50 people dedicated to doing this comprehensively and systematically. What would each role focus on? What would the ideal output look like? Then help me identify which parts of that hypothetical team’s work could be automated or assisted by AI tools.
For example, we use this approach for podcast guest prospecting and research. We used to rely on network and serendipity to identify 20-30 strong candidates for each season; a mix of the right expertise, timing and editorial fit that consistently delivered good conversations – but left too much to chance. Instead, 50x thinking asks what if we could systematically evaluate the top 1,000 potential guests? What if we could track the people we’re interested in so they surface when they’re most relevant? We built a workflow that researches each candidate, classifies expertise, identifies timely angles, and suggests the most relevant names for any given week’s news cycle.
2. Adversarial synthesis
Even experienced operators have blind spots. We internalize standards of “good” based on limited exposure. No one has seen great outputs across every domain but the models, collectively, have come closer to it than anyone else.
To make the most of this superpower, I give Gemini, Claude and ChatGPT the same task – and make them argue. Then have each critique the others. You’ll quickly surface gaps in your framing, assumptions you didn’t realise you were making, and higher quality bars than you expected.
When models disagree, it’s usually a sign that the task is underspecified, or that there are real trade-offs you haven’t surfaced yet. Which brings us to the next point.
3. Productize the conversation
If you’re having the same conversation with AI repeatedly, turn it into a tool. Every repeated prompt is a signal. Your workflow is basically telling you that this (t)ask is valuable enough to formalize.
I found that when I productize a conversation by turning it into a dedicated app or agentic workflow, my process gets better at the core and my tool evolves over time. So the benefits of the original conversation end up compounding in a completely new way.
A prompt you could use:
## Context
I have a recurring [FREQUENCY] task: [BRIEF DESCRIPTION].

Currently I do it manually by [CURRENT PROCESS - 1-2 sentences].

Here’s an example of this task in action:

Input I provided: [PASTE ACTUAL INPUT]
Output I needed: [PASTE ACTUAL OUTPUT OR DESCRIBE]
## What I Need
Turn this into a reusable system with:
1. **Input specification**: What information must I provide each time?
2. **Processing instructions**: What should the AI do, step by step?
3. **Output structure**: Consistent format for results
4. **Quality criteria**: How to know if the output is good

## Constraints
- Time/effort budget: [e.g., “should take
[Paste an actual input you’d give, or describe a recent time you did this task]
## Context
- Platform I’m using: [Claude.ai / API / ChatGPT / etc.]
- How often I do this: [one-off / weekly / daily]
- Quality bar: [quick draft / polished output / production-ready]
- My expertise in this domain: [novice / intermediate / expert]

## What I Need
1. **Model recommendation** (if I have options) with reasoning
2. **Prompt structure**: How should I frame requests for this task type?
3. **Key levers**: What 2-3 things most affect output quality for this task?
4. **Common mistakes**: What do people typically get wrong?

Keep recommendations actionable—tell me what to do, not just what’s theoretically possible.
6. Modular over monolithic
This one keeps paying dividends – I first wrote about it in April [ https://substack.com/redirect/15814833-fc24-4fd5-97a8-a91e6aa66272?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Maybe the most important of the six.
The temptation is to build grand automations. Input on one side, finished output on the other. One pipeline that does everything.
It’s a fair intent, but monolithic pipelines tend to break. And when they break, you don’t know where. When you want to improve one part, you risk destabilizing the whole. When the workflow needs to evolve, and it will, you’re starting over.
Instead, start by creating small components for independent testing. A newsletter workflow I might want to build won’t start out as one sprawling agent. It will be a collection – one component sourcing material, another extracting signal, another drafting, another checking tone and accuracy. Each piece can be tested alone, improved without side effects, swapped out as better options emerge.
Some of our most useful tools are surprisingly narrow. Like a watermarking app that just adds logos to images, faster than opening PowerPoint or Canva. A chapter-change tracker for version control. An expense processor that only handles invoices from Gmail. And so on…
Don’t build cathedrals. Build Lego.
Want to go deeper?
Here’s our internal tool stack [ https://substack.com/redirect/ea28c014-4a0c-4d04-86fc-49f625f59065?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] – currently 50+ systems we’re using, testing, or watching closely available to members of Exponential View.
Our team members can choose the tools they think help them get their job done, whether that is building in Python or using a higher-level framework. They can also choose the underlying model they use, although we share our experiences and evals with each other.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuZXhwb25lbnRpYWx2aWV3LmNvL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hPREV6TXpBME5USXNJbWxoZENJNk1UYzJOekF5TkRJM01Td2laWGh3SWpveE56azROVFl3TWpjeExDSnBjM01pT2lKd2RXSXRNakkxTWlJc0luTjFZaUk2SW1ScGMyRmliR1ZmWlcxaGFXd2lmUS5NWFIyclg4MjhYT2lTaWxLSTFOaUIzM1NCdlVxelZLRExudWIzWFd2NE5RIiwicCI6MTgxMzMwNDUyLCJzIjoyMjUyLCJmIjpmYWxzZSwidSI6MTI1NTU5OSwiaWF0IjoxNzY3MDI0MjcxLCJleHAiOjIwODI2MDAyNzEsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.Y7K62aVoAkKjcfYCEdyCZJ4UayBQXQs0rkGfH-5Qa_Y?