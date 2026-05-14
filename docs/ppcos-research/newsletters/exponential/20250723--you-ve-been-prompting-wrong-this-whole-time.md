# 🔮 You’ve been prompting wrong this whole time

**From:** "Azeem Azhar, Exponential View" <exponentialview@substack.com>
**Date:** 2025-07-23T14:01:48.000Z
**Folder:** exponential

---

View this post on the web at https://www.exponentialview.co/p/how-to-train-your-ai

Many of us feel fluent in prompting AI by now, but still feel frustrated when the results fall short. The issue usually isn’t the model. It’s how we talk to it.
Too often, we fall into what developer Mitchell Hashimoto calls “blind prompting [ https://substack.com/redirect/eca46652-080c-4c2f-a7e9-f45b1b1b8715?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]”, treating the AI like a helpful colleague instead of instructing it with purpose and structure. In one 2023 study, participants who got a decent result [ https://substack.com/redirect/ec59eda7-d1fc-4761-a008-20b5671d4816?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] early on assumed their prompt was “done,” and never refined it further.
If you hired a new team member and gave them only vague tasks with no feedback, you wouldn’t be surprised if they struggled. The same goes for AI. Models need context. They need iteration. And they benefit from review, correction and calibration, just like people do. And as AI becomes one of the most important inputs in modern work, it’s time to start managing it as such.
There are now dozens [ https://substack.com/redirect/3d5cc239-66e9-4a62-9d79-1d0fa1e4fb75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of system prompts from labs and startups floating around online. AI labs have invested millions of dollars in developing them. They’re all expertly crafted and sophisticated, but Claude 4 is one of the most extensive to date. Claude’s system prompt is at 24,000 tokens, or ~9,700 words, 453 sentences in length. For comparison, the Gemini-2.5-Pro and o3_o4-mini leaks stand at 1,636 words and 2,238 words, respectively.
For all of you who want to improve your skills, studying these leaks might be one of the best routes available. Our team has studied Anthropic’s internal guide to Claude 4 to identify seven key rules, along with examples (included in the leak and our own in italics), that will enhance your prompting game, guaranteed.
Rule 1: You are an instructor, act like it
You might not realize it, but being specific, with clear, formatted instructions, can dramatically improve your AI results. Even subtle tweaks in wording can improve [ https://substack.com/redirect/c84c4a47-6d04-4e07-ba68-c6901ab7514e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the accuracy by as much as 76%. The Claude system prompt clearly defines that the standard responses should be in paragraph format, unless the user specifies otherwise:
Claude responds in sentences or paragraphs and should not use lists in chit chat, in casual conversations, or in empathetic or advice-driven conversations. In casual conversation, it's fine for Claude's responses to be short, e.g. just a few sentences long.

...

If Claude provides bullet points in its response, it should use markdown, and each bullet point should be at least 1-2 sentences long unless the human requests otherwise. Claude should not use bullet points or numbered lists for reports, documents, explanations, or unless the user explicitly asks for a list or ranking.
There are also numerous stylistic notes instructing Claude precisely how to craft its responses in different contexts, such as:
Claude is able to maintain a conversational tone even in cases where it is unable or unwilling to help the person with all or part of their task.
Conversely, Claude remains thorough with more complex and open-ended questions. And for those seeking more affective conversations, the system prompt writes:
For more casual, emotional, empathetic, or advice-driven conversations, Claude keeps its tone natural, warm, and empathetic.
How can we make use of this? When prompting your large language model (LLM), clearly define the AI’s role, your exact task and the desired output. This can include the format of the output in terms of the style, length, and formatting, to more precisely get your desired result.
You are a senior copy editor. Task: rewrite the following 200-word blog intro so it’s clear, concise, and in plain English. Output: one paragraph, no bullet points, max 120 words.
Rule 2: DON’T do that; do use negative examples.
It is becoming more well-known that providing clear examples of what you want can result in more aligned outcomes with your goal. However, we also see that describing what not to do can be of benefit, too. These crop up multiple times in the Claude system prompt, such as in the following example:
Any calculations involving numbers with up to 5 digits are within your capabilities and do NOT require the analysis tool.
Alongside this are some examples to guide Claude on where not to use the analysis tool:
Do NOT use analysis for problems like "4,847 times 3,291?", "what's 15% of 847,293?", "calculate the area of a circle with radius 23.7m"
In fact, the system prompt contains a larger frequency of the word “never” compared to “always”, with 39 instances of the former versus 31 for the latter. The word “always” doesn’t even make it into the top 20 words in the prompt, while “never” has the 13th highest frequency.
Although these arbitrary examples of what not to do may seem random, they help to guide the tool behaviour of the LLM, leading to faster outputs and fewer tokens needed to process the task.
How can we make use of this? The context windows (available window of attention for an LLM) are growing bigger and bigger. For complex problems, provide the LLM with examples of what you do and do not want, to clarify the expectations and improve accuracy.
Edit this paragraph for a general audience. DON’T use jargon like ‘transformer’, ‘parameter’, or ‘hallucination’. If any slip through, revise the sentence immediately.
Rule 3: Provide an escape hatch
By now, we all know that LLMs tend to hallucinate if they don’t know the right answer. Aware of this, Anthropic has opted to include a line to ensure that Claude can send the user to the best place for the latest information.
If the person asks Claude about how many messages they can send, ... , or other product questions related to Claude or Anthropic, Claude should tell them it doesn't know, and point them to 'https://support.anthropic.com'.
Providing an “escape hatch” can help reduce hallucinations, allowing the LLM to admit where it is lacking in knowledge instead of attempting to answer (and often being very convincing even if the result is completely incorrect).
How can we make use of this? Explicitly ask the LLM to mention “I don’t know” if it does not have the knowledge to comment. Additionally, you can provide another “hatch” by adding that it can and should ask for clarifying information if needed to provide a more accurate answer.
If you’re < 70 % confident about a style rule, respond: ‘I’m not certain—please verify in theAP Stylebook or Chicago Manual of Style before editing. Otherwise, edit normally.
Rule 4: Search strategically
Claude spends 6,471 tokens, nearly a third of its system prompt, just instructing itself how to search [ https://substack.com/redirect/d9588491-1e03-4044-b9ed-25e3843bf5fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It spells out exactly when to quickly grab information (for urgent queries), when to hold back (for unclear requests), and when to go all-in with at least five searches (for detailed, “deep-dive” questions).
Claude answers from its own extensive knowledge first for stable information. For time-sensitive topics or when users explicitly need current information, search immediately. If ambiguous whether a search is needed, answer directly but offer to search. Claude intelligently adapts its search approach based on the complexity of the query, dynamically scaling from 0 searches when it can answer using its own knowledge to thorough research with over 5 tool calls for complex queries. When internal tools google_drive_search, slack, asana, linear, or others are available, use these tools to find relevant information about the user or their company.
Claude also explicitly guides users on triggering deep research. Use phrases like “deep dive”, “comprehensive”, “analyze”, or “make a report”, and Claude knows to use at least five tool calls to answer thoroughly.
How can we make use of this? Consider whether your problem is something well-known and within the trained memory of the LLM. If so, and if your problem or question is time sensitive, it may be best to skip the search itself and use the trained memory. If you know what you’re after is relatively new information or if you need a thorough search, then include trigger phrases like “deep dive”, “comprehensive”, “analyze” to ensure a deep search is initiated. You can also use the words “think”, “think harder” or “ultra think” to explicitly request [ https://substack.com/redirect/92a8de4f-2e38-4d5c-b038-f3e8085d3c19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] deeper reasoning from Claude. This latter part on reasoning depth works directly in Claude as well as through tools like Windsurf and Cursor.
Edit from memory first. If I write ‘deep dive’, look up post-2024 changes to inclusive language in major style guides, cite up to three sources, then apply them.
Secondly, you can use this to define keywords or phrases in the prompt that the LLM can look out for and change its behaviour accordingly for multi-use prompts.
Interpret keywords in square brackets to adjust your response.
[PLAIN] – rewrite for a general audience, no jargon, ≤ 120 words.
[SEO] – keep technical terms, insert 3–5 high-rank search phrases naturally.
[CHECK] – return a fact-check report instead of edits.
[STYLE=APA] – format citations and references in APA 7th.
If no keyword appears, default to [PLAIN].
Rule 5: You can critique the output, but it can also critique itself
While users often end up in a back-and-forth conversation with an LLM, treating it like a chatbot, this can get tiring when going over multiple iterations. Instead, getting the LLM to review its response and act on its feedback can create a quicker route to a good result.
The latest Claude 4 prompt does not show this explicitly. It instead uses short reminders scattered within the prompt to encourage the LLM to adhere to good working practices. However, in the Claude 3.7 leak last year, this was shown in the instance of creating artifacts:
Briefly before invoking an artifact, think for one sentence in tags about how it evaluates against the criteria for a good and bad artifact.
How can we make use of this? Add in an iteration loop by asking the LLM to rank its answer based on how well it achieves the goal of the task, identifying strengths and weaknesses, then iterate on this feedback to produce a better result.
After editing, run this silent check: (1) ≤ 120 words, (2) no jargon flagged in Rule 2, (3) no repeated sentences. Fix problems, recheck once, then show only the final version.
Rule 6: Stay neutral
Running a sentiment analysis on the Claude 4 system prompt using VADER (Valence Aware Dictionary and sEntiment Reasoner) highlights a subtle importance in prompting. Here, VADER is a tool used to determine whether a corpus has a positive, negative, or neutral sentiment based on the components of each sentence.
When plotting the compound score (sentiment value, where negative values indicate negative sentiment and vice versa) for each sentence in the prompt, we have a clear distribution in the scores.
The distribution is, however, clearly focused around the center with a slight positive slant. Taking the whole text together, we get a resulting average compound score of 0.12. This implies the text is mostly neutral and instructional, but with brief examples that convey positivity when Claude aims to be a helpful assistant, bringing the score up slightly.
If Anthropic aims to have a neutral prompt, this may carry weight with it. A neutral prompt could help prevent bias from entering the chat and guide the answer to be more thoroughly grounded in fact, considering all sides.
How can we make use of this? When aiming for factual outcomes or considering multiple angles towards a subject, you are better off avoiding leading questions, statements and adjectives. Begin neutral and iterate to consider different points.
Write concise, fact‑based marketing copy that highlights features and practical benefits. Keep language clear, professional, and free of hype.
While we’ve covered some key takeaways from the system prompt here, interested readers can dive into the original leaked prompt [ https://substack.com/redirect/9432cdbb-a82b-4976-a51c-75b3f4b2d95b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to see more.
Rule 7: Context is king
Think of prompt engineering as context engineering – best described [ https://substack.com/redirect/83bcac74-cb99-43a0-9576-36d64bdc6b59?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Andrej Karpathy  as “the delicate art and science of filling the context window with just the right information for the next step”.
It’s about layering in the right kind of information and calls so that the software stack is coordinated in just the right way to get you the best results.
And while speaking of context, using the right model matters. Andrej, again, explained [ https://substack.com/redirect/acd04ff2-6954-4605-928e-60e270fe05ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] well how different GPT models excel on specific tasks, even when given the same prompt. See the schematic below for the quick guide. For example, using o3 is best for hard and important tasks that require time to process, while easier tasks are better suited for GPT-4o.
The art of prompting is a skill itself, and just like trying a new hobby or a new sport, it’s unlikely that we’ll get it right the first time. The way around this? To start with a draft for a certain task, and refine it over time using these lessons to guide the prompt towards your goal.
For the keen-eyed among you, you may have noticed that the examples put together throughout the piece have some similar themes. These have been put together strategically to demonstrate a copy-editing prompt. In full, it looks like this:
You are a senior copy editor. Task: rewrite the following 200-word blog intro so it’s clear, concise, and in plain English. Output: one paragraph, no bullet points, max 120 words.

Edit this for a general audience. DON’T use jargon like ‘transformer’, ‘parameter’, or ‘hallucination’. If any slip through, revise the sentence immediately. Keep language clear, professional, and free of hype.

If you’re < 70 % confident about a style rule, respond: ‘I’m not certain—please verify in the AP Stylebook or Chicago Manual of Style before editing. Otherwise, edit normally.

Edit from memory first. If I write ‘deep dive’, look up post-2024 changes to inclusive language in major style guides, cite up to three sources, then apply them.

After editing, run this silent check: (1) ≤ 120 words, (2) no jargon flagged in Rule 2, (3) no repeated sentences. Fix problems, recheck once, then show only the final version.

[ORIGINAL BLOG]
This is currently a very general prompt and could use some revisions for the specific task at hand.
Other tips and tricks – quick fire
We’ve already given you seven key rules to improve your prompting significantly. Below are several other great practical tips from Y Combinator’s concise guide [ https://substack.com/redirect/a329b375-2e3a-472b-9015-70a49c1c008a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and other sources on prompting techniques:
Use formatting intentionally: Markdown, headers, bullet points, or XML-style tags can help structure your prompts, guiding your AI’s understanding of your goal.
Use large LLMs to optimize prompts on smaller ones: Using a larger, more capable model (like o3) to craft highly effective prompts for smaller models (like o4-mini) can save you time, leading [ https://substack.com/redirect/b5670f90-dcc2-4a91-82a6-9f8f04a59d97?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to higher accuracy than relying on human-written prompts alone.
Consider prompt optimization frameworks: A recent Reddit post gaining over 19,000 upvotes shares [ https://substack.com/redirect/10b2ec78-aadf-4c0b-bf3d-ce9c3dd0352c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a master prompt structure that systematically gathers context, asks clarifying questions and refines prompts to maximize effectiveness.
Start prompts with a verb: Beginning your prompt with an action word can improve [ https://substack.com/redirect/03f3f85d-88ef-412a-9c48-18ee8d21bc39?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] clarity and outcomes.
Narrow prompts iteratively: Start broadly and refine your request through successive [ https://substack.com/redirect/03f3f85d-88ef-412a-9c48-18ee8d21bc39?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] prompts to guide your AI towards the precise answer you need.
Break tasks down: Start with clear instructions and then provide a step-by-step plan, increasing accuracy and reliability at each stage.
Prioritize output quality: Always assess prompts based on the quality and usefulness of the final result.
Use dynamic prompting: Build prompts that create subsequent, specialized prompts based on context or previous outputs, going beyond single-task prompts.
Chain of Thought (CoT) prompting: As research by Ethan Mollick  and co-authors shows [ https://substack.com/redirect/172b69b7-0ede-424e-b337-3dffc307c250?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], explicitly requesting step-by-step reasoning (“chain of thought”) can significantly improve responses from simpler LLMs, but it’s typically unnecessary for advanced models with built-in reasoning, where it might even reduce accuracy.
Mastering the art of prompting is becoming foundational to thriving in an algorithmic world. But what separates mediocre prompts from transformative ones?
The answer is in the seven battle-tested rules, drawn from leading AI labs’ inner workings. Apply them systematically. Combine them with practical techniques – intentional formatting, iterative refinement, strategic reasoning – and frustration will give way to precision.
Like any craft, prompting rewards deliberate practice: start simple, experiment boldly, evolve continuously. As we integrate AI into daily workflows, those who view it not as an opaque system but as a responsive tool will excel.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuZXhwb25lbnRpYWx2aWV3LmNvL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOamcyTlRNeU9UZ3NJbWxoZENJNk1UYzFNekk0TXpBeU5Td2laWGh3SWpveE56ZzBPREU1TURJMUxDSnBjM01pT2lKd2RXSXRNakkxTWlJc0luTjFZaUk2SW1ScGMyRmliR1ZmWlcxaGFXd2lmUS4wVGZtYzZzQUlHNERnVUc3REM0b0NwdzZKdVM3bGVFWWhHNi1TZkRJRUZvIiwicCI6MTY4NjUzMjk4LCJzIjoyMjUyLCJmIjpmYWxzZSwidSI6MTI1NTU5OSwiaWF0IjoxNzUzMjgzMDI1LCJleHAiOjIwNjg4NTkwMjUsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.xV3XM6pbO56iGxQ09RXVeJgTP3FNaKySV6LrCzg2HRU?
