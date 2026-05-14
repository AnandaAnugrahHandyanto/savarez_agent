# I Cloned 2,000 Hacker News Users to Predict Viral Posts

**From:** Every <hello@every.to>
**Date:** 2025-06-17T15:04:25.000Z
**Folder:** every

---

I Cloned 2,000 Hacker News Users to Predict Viral Posts

My AI experiment hit 60 percent accuracy—not perfect, but enough to change how we think about market research

Also True for Humans

I Cloned 2,000 Hacker News Users to Predict Viral Posts

My AI experiment hit 60 percent accuracy—not perfect, but enough to change how we think about market research

by Michael Taylor

ChatGPT/Every illustration.

Can AI predict what will go viral online? That's the question at the heart of Michael Taylor’s latest experiment, in which nearly 2,000 AI personas based on real Hacker News commenters were tasked with predicting which headlines would take off. The resulting 60 percent accuracy rate was significantly better than chance, but with revealing limitations: The social dynamics that determine virality (those early upvotes that create momentum) introduce an element of chaos that AI models can't fully capture. Michael balances out his technical insights with practical takeaways for using AI in market research and a prompt template for you to try this approach yourself.—Kate Lee

Was this newsletter forwarded to you? Sign up to get it in your inbox.

I created 1,903 AI personas based on real Hacker News commenters and asked them to predict which headlines would go viral. They got it right 60 percent of the time—20 percent better than flipping a coin.

That's a meaningful result. Chief marketing officers say they'd use AI market research if it matched human responses just 70 percent of the time. At 60 percent accuracy, we're close enough to matter—but my experiment also revealed why it’ll be difficult to do much better.

The excitement around my original Hacker News simulator post was understandable: If AI could reliably predict viral headlines, you could keep testing until you found one that hits the jackpot. Using AI would be much faster and cheaper than traditional market research as well. But the 100-plus people who reached out after my post were skeptical that machines could match real focus groups. Marketing is a number-driven game, and marketers are finely tuned bullshit detectors. They wanted proof.

So I ran the experiment. I pulled 1,147 headlines from a single day and asked my nearly 2,000 personas to pick winners from a mix of top stories and flops. The 60 percent accuracy rate was encouraging—but when I dug into which headlines the AI got wrong, I discovered something more important than the success rate itself. The problem isn't just predicting individual behavior. It's that viral content depends on social dynamics that compound in unpredictable ways. Even if I could perfectly model your choices, you're influenced by how many upvotes a headline already has when you see it. One extra early vote can change everything—sending identical content down completely different paths in parallel universes.

Here's what I learned about the promise and limits of AI market research, and why achieving a useful but imperfect level of accuracy in predicting viral headlines might be the best we can do. I’ll also walk you through the prompt template you can use to try this yourself in ChatGPT or Claude.

Learn how Korbit AI enabled one of the world’s top gaming companies to accelerate engineering velocity and improve code quality. Join this panel of software engineers and SaaS experts to learn:

The challenges that stem from using manual code review processes or the wrong AI tools.

Why AI-powered code review is crucial for improving code quality, reducing reviewer fatigue, and maintaining company standards.

How Korbit accelerates the SDLC process for hundreds of enterprises with instant, AI-powered code reviews and powerful insights into the codebase, projects, and team.

Save my spot!

Want to sponsor Every? Click here.

The experiment: Is ChatGPT an Oracle?
Our Hacker News simulation asks ChatGPT to roleplay as 81 different personas, and then aggregates the results of their answers. That allows you to predict how people might respond to headlines you haven’t published yet, helping you refine your idea before posting.

Here’s what I did: I pulled 1,147 headlines posted on March 12, 2025 via the Hacker News API. By pulling more profiles of people who commented that day (running the same script for longer), I expanded the audience to 1,903 AI personas, and asked them to decide whether to upvote headlines that were a 50/50 mixture of stories that made the front page that day, and those that never did. (I ran this study in a Jupyter Notebook so I could process thousands of AI personas at once.)

The results: Imperfect, but useful
The Hacker News personas’ predictions of which headlines would make the front page were accurate 60 percent of the time.

Bar chart showing actuals versus predicted for several of the top-vote vs low-vote stories. Source: Google Sheets, screenshot courtesy of author.

When I looked at the specific headlines it got wrong, I began to see why this is such a tough nut to crack.  For example, one of the system’s biggest misses was a headline that reads “Gemma 3: Google's new multimodal models.” The personas predicted it would do well, but it only got four upvotes. Meanwhile, the headline “Gemma 3 Technical Report [pdf]”—covering the exact same release—got 1,324 votes with the same topic. Is that headline really over 1,000 times better? Similarly, the personas expected a post about the TSA finding a live turtle concealed in a man’s pants would do well. In real life, it struck out. Go figure.

The research: Why my AI got it wrong
When I looked closely at these failures, I realized they revealed something crucial about how viral content works.

Take the example of the two headlines about Gemma 3. The difference between them wasn't the quality of the topic. It was timing, luck, and social momentum.

In my experiment, the AI personas saw randomized headlines, with no sense of any other agents’ opinions of them. But real Hacker News users see headlines in context. They’re influenced by existing vote counts, their position on the page, and what else is trending that day. Stories that get voted up the page are more likely to be seen and upvoted further.

A Princeton study demonstrated this perfectly. Researchers gave 14,341 people identical lists of songs from unknown bands. When participants could see others' choices, the same song would be wildly successful in one group and flop in another. Success became two to five times more unpredictable than when people judged the songs in a vacuum. The best songs (rated independently) rarely did poorly and the worst rarely did well, but 70-80 percent of success was simply luck early on.

This "rich get richer" dynamic explains why my simulator struggled. Headlines that get a few lucky early upvotes climb the rankings, drawing more attention and even more upvotes, regardless of objective quality. I could build the perfect model of individual preferences, but I'd still be missing the social physics that determine what goes viral.

The insights: What 60 percent accuracy means for your business
If you're considering AI market research, the real question isn't whether it's perfect—it's whether it's useful enough to change how you make decisions.

My 60 percent accuracy puts AI personas in an interesting sweet spot. It's not good enough to bet your company on a single prediction, but it's significant enough to improve your odds.

Several AI market research companies claim much higher numbers—Aaru asserts 93 percent correlation in predicting consumer preferences, Evidenza talks about an 88 percent similarity to traditional research results, and Electric Twin reports 92 percent accuracy. But here’s the catch: Those numbers come from comparing AI responses to survey data. Predicting what people say they’ll do is much easier than predicting what actually goes viral.

The bigger insight from my experiment is that we may be approaching the theoretical limits of social prediction. Even if AI perfectly modeled every individual's preferences, viral success would still depend on unpredictable social dynamics—the timing of early votes, what else is competing for attention, and the cascade effects that amplify small differences into massive outcomes.

This has practical implications for how you should use AI market research:

Use it for iteration, not prediction. Instead of trying to pick the one winning headline, test 10 variations with AI personas to eliminate obvious losers and identify promising directions. Then test your top candidates in the real world.

Run multiple simulations. If your idea succeeds in only one out of eight AI runs, it could be luck. If it wins in six out of eight, you're probably onto something. As LLM costs drop, this kind of large-scale simulation will become more practical.

Focus on relative ranking, not absolute predictions. My AI was better at distinguishing between obviously good and obviously bad headlines than picking winners from a field of decent options.

The template: Virtual Hacker News prompt
To test this for your own business using Claude or ChatGPT, start by selecting a Hacker News user to clone. Every user in Hacker News has a public page of what they commented on, and it turns out that people reveal a lot about themselves in their public comments. To make a persona based on a Hacker News commenter, copy and paste their comments (keep clicking “more” for additional pages), and paste them into ChatGPT or Claude with this prompt:

You are a helpful assistant that creates detailed personas representing a specific HackerNews user from a list of HackerNews comments they have made. Create a unique persona who would give identical answers to the user we are replicating based on their comments. Give them a relevant background and experience based on your best inference from their HackerNews comments. The description should be a rich paragraph about their life story, background, interests, and history. Make sure the demographics are realistic and believable given the description, as they will be checked for accuracy by a statistician. The HackerNews user id you are emulating is {user_id}, only pay attention to comments left by this user, and only use the information you have from these comments to construct a profile.

Cloning a Hacker News user Source: Claude, screenshot courtesy of author.

This will produce a description of a “person,” though you’ll notice that AI makes things up, like a name and other details, based on what it thinks is plausible and consistent with what it learned from the comments (for example, the name “Richard Martin-Jones” is a Claude invention—no one is being doxxed here). Once you have one (or more) of these personas, copy and paste them into a fresh chat session, and ask them what they think of your ideas. This isn’t calibrated to any benchmark, so you’re on your own in terms of how accurate it will turn out, but it can still be extremely useful—especially when the alternative is not doing any market research.

As you experiment with AI research, remember that testing your idea like this is only part of the equation. Social dynamics are inherently unpredictable, even when we can model individual behavior well. AI can give you access to insights previously reserved for companies with massive research budgets, but it is not a crystal ball for your marketing content—at least, not yet.

Michael Taylor is the CEO of Rally, a virtual audience simulator, and the coauthor of Prompt Engineering for Generative AI.

To read more essays like this, subscribe to Every, and follow us on X at @every and on LinkedIn.

We also build AI tools for readers like you. Automate repeat writing with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora.

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
