# This Prompt Optimizer Learns From Its Mistakes Like DNA

**From:** Every <hello@every.to>
**Date:** 2025-12-05T16:06:25.000Z
**Folder:** every

---

This Prompt Optimizer Learns From Its Mistakes Like DNA
A new tool that 'evolves' your prompts may be the next step in getting LLMs to do precisely what you want
Also True for Humans
This Prompt Optimizer Learns From Its Mistakes Like DNA
A new tool that 'evolves' your prompts may be the next step in getting LLMs to do precisely what you want
by Mike Taylor
Midjourney/Every illustration.
This is a free preview of a subscribers-only post.
Many of you wanted to learn more after the overwhelming response to Every columnist MikeTaylor‘s piece on prompt optimization framework DSPy. In this essay he goes deeper, breaking down GEPA, the specific optimizer inside DSPy that treats prompt engineering like natural selection—testing and evolving your prompts automatically. Even if you’re not technical enough to run GEPA yourself, his argument holds broader lessons for how anyone can work better with LLMs and what the future of prompt engineering holds.
Plus: We’re giving away 10 Monokeys—our limited-edition physical button for dictation—to the top 10 referrers on our leaderboard by December 7. Share your Monologue referral link with people who’d benefit, and every sign-up moves you up the leaderboard.—Kate Lee
Was this newsletter forwarded to you? Sign up to get it in your inbox.
Tech leaders at Shopify, Databricks, and Dropbox have all become smitten with an obscure tool for enhancing how you prompt language models. It’s called GEPA, and it’s part of DSPy, the prompt optimization that is already so good it could replace me and my job as a prompt engineer.
GEPA works by iterating on your prompt in a way that resembles one of biology’s most powerful forces: genetic mutation and natural selection. It does this by creating multiple copies of your prompt, making changes to them (“mutating” them) and keeping track of the best ones. (GEPA is short for “Genetic Pareto,” in which the best-performing prompts define something called a pareto frontier.)
The original paper on GEPA, published on the open-access archive Arxiv in July, promised 25 percent better performance than other methods of optimizing prompts on a range of tasks. That may not sound like a huge improvement, but it did it fully automatically with 35 times fewer trials—so it’s smarter about what it tries. As a result, it’s cost-effective to run on any task that’s worth spending a few hundred bucks to improve—like the prompts that power Every’s AI writing assistant Spiral’s creative writing, which got a 44 percent quality improvement through GEPA optimization.
I keep getting questions about how GEPA works and whether people should be using it. Though there is a technical barrier, it’s coming down as no code tools like LangWatch and Opik integrate it into their products, as well as a number of others build user interfaces for it. Even OpenAI is getting in on the prompt optimization game, with an interface for optimizing your prompts. I’m going to break my explanation down in accessible terms. I’ll also walk you through a case where GEPA doubled the accuracy of my prompt in 20 minutes, so you can see how GEPA can help you optimize daily workflows and, more broadly, how AI can help us use it better.
Become a paid subscriber to Every to unlock this piece and learn about:
How a prompt Mike created went from giving the correct outputs 26 percent of the time to 71 percent of the time in half an hour—without him rewriting a word

The hidden patterns in invoice data that GEPA spotted but its human operator missed

Why the future of prompt engineering won’t involve writing prompts at all

Subscribe
This post is for
paying subscribers.
Try for $1
Or, learn more.