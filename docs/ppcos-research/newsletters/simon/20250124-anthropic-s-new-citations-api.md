# Anthropic's new Citations API

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-01-24T04:45:49.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/anthropics-new-citations-api

In this newsletter:
Anthropic's new Citations API
OpenAI Operator
Six short video demos of LLM and Datasette projects
Plus 6 links and 4 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Anthropic's new Citations API [ https://substack.com/redirect/e986be71-1fea-4c51-9ef3-942485a01e80?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-01-24
Here's a new API-only feature from Anthropic that requires quite a bit of assembly in order to unlock the value: Introducing Citations on the Anthropic API [ https://substack.com/redirect/cb089b22-eded-48a8-8129-dd95dbe9b9c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Let's talk about what this is and why it's interesting.
Citations for Retrieval Augmented Generation [ https://substack.com/redirect/ed830d9f-3aa2-4458-9c92-2aca13b38108?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Trying out the new API with uv run [ https://substack.com/redirect/d3cbab42-b6de-4e58-a7ab-d6f7437bfec5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Rendering the citations [ https://substack.com/redirect/a081f072-cdb3-4425-a98a-62a3f87b14ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Now I need to design an abstraction layer for LLM [ https://substack.com/redirect/3ceb762f-646b-4fe6-80a7-c81604dbc6cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Anthropic's strategy contrasted with OpenAI [ https://substack.com/redirect/ec53c178-adb0-4694-a5a8-1481e5d0f422?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Citations for Retrieval Augmented Generation
The core of the Retrieval Augmented Generation [ https://substack.com/redirect/a278212b-789d-41d3-aa9f-b22d9a7904ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (RAG) pattern is to take a user's question, retrieve portions of documents that might be relevant to that question and then answer the question by including those text fragments in the context provided to the LLM.
This usually works well, but there is still a risk that the model may answer based on other information from its training data (sometimes OK) or hallucinate entirely incorrect details (definitely bad).
The best way to help mitigate these risks is to support the answer with citations that incorporate direct quotations from the underlying source documents. This even acts as a form of fact-checking: the user can confirm that the quoted text did indeed come from those documents, helping provide relatively robust protection against hallucinated details resulting in incorrect answers.
Actually building a system that does this can be quite tricky. Matt Yeung described a pattern for this he called Deterministic Quoting [ https://substack.com/redirect/4d4fce07-83ec-4a44-b7c7-87cf1ea9d109?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] last April, where answers are accompanied by direct quotations from the source documents that are guaranteed to be copied across and not lossily transformed by the model.
This is a great idea, but actually building it requires some quite sophisticated prompt engineering and complex implementation code.
Claude's new Citations API [ https://substack.com/redirect/41e76bb6-7f4c-4b29-8c53-3dc9eb65b56d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] mechanism handles the difficult parts of this for you. You still need to implement most of RAG - identifying potentially relevant documents, then feeding that content in as part of the prompt - but Claude's API will then do the difficult work of extracting relevant citations and including them in the response that it sends back to you.
Trying out the new API with uv run
I tried the API out using Anthropic's Python client library, which was just updated [ https://substack.com/redirect/99d3e91d-7b88-48c4-ab91-9255013fc7d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to support the citations API.
I ran a scratch Python 3.13 interpreter with that package using uv run [ https://substack.com/redirect/6716ce28-9759-4914-8228-3d5f200b7113?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this (after first setting the necessary ANTHROPIC_API_KEY environment variable using llm keys get [ https://substack.com/redirect/a2472170-e440-4bd9-b262-d7c7e383952d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
export ANTHROPIC_API_KEY="$(llm keys get claude)"
uv run --with anthropic --python 3.13 python
Python 3.13 has a nicer interactive interpreter [ https://substack.com/redirect/4a276889-26f1-4e32-8e35-e2d5aee65e87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which you can more easily paste code into. Using uv run like this gives me an environment with that package pre-installed without me needing to setup a virtual environment as a separate step.
Then I ran the following code, adapted from Anthropic's example [ https://substack.com/redirect/41e76bb6-7f4c-4b29-8c53-3dc9eb65b56d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The text.txt Gist [ https://substack.com/redirect/ede3eb2d-5308-419b-ac1d-2fd11079ef2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] contains text I copied out from my Things we learned about LLMs in 2024 [ https://substack.com/redirect/70a14896-b641-44cc-9735-70e482436e5c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] post.
import urllib.request
import json

url = 'https://gist.githubusercontent.com/simonw/9fbb3c2e2c40c181727e497e358fd7ce/raw/6ac20704f5a46b567b774b07fd633a74944bab2b/text.txt'
text = urllib.request.urlopen(url).read.decode('utf-8')

import anthropic

client = anthropic.Anthropic

response = client.messages.create(
model="claude-3-5-sonnet-20241022",
max_tokens=1024,
messages=[
{
"role": "user",
"content": [
{
"type": "document",
"source": {
"type": "text",
"media_type": "text/plain",
"data": text,
},
"title": "My Document",
"context": "This is a trustworthy document.",
"citations": {"enabled": True}
},
{
"type": "text",
"text": "What were the top trends?"
}
]
}
]
)
print(json.dumps(response.to_dict, indent=2))
The JSON output from that starts like this:
{
"id": "msg_01P3zs4aYz2Baebumm4Fejoi",
"content": [
{
"text": "Based on the document, here are the key trends in AI/LLMs from 2024:\n\n1. Breaking the GPT-4 Barrier:\n",
"type": "text"
},
{
"citations": [
{
"cited_text": "I\u2019m relieved that this has changed completely in the past twelve months. 18 organizations now have models on the Chatbot Arena Leaderboard that rank higher than the original GPT-4 from March 2023 (GPT-4-0314 on the board)\u201470 models in total.\n\n",
"document_index": 0,
"document_title": "My Document",
"end_char_index": 531,
"start_char_index": 288,
"type": "char_location"
}
],
"text": "The GPT-4 barrier was completely broken, with 18 organizations now having models that rank higher than the original GPT-4 from March 2023, with 70 models in total surpassing it.",
"type": "text"
},
{
"text": "\n\n2. Increased Context Lengths:\n",
"type": "text"
},
Here's the full response [ https://substack.com/redirect/e4c0c702-a255-4c24-946b-3443417b8f46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This format is pretty interesting! It's the standard Claude format but those "content" blocks now include an optional additional "citations" key which contains a list of relevant citation extracts that support the claim in the "text" block.
Rendering the citations
Eyeballing the JSON output wasn't particularly fun. I wanted a very quick tool to help me see that output in a more visual way.
A trick I've been using a lot recently is that LLMs like Claude are really good at writing code to turn arbitrary JSON shapes like this into a more human-readable format.
I fired up my Artifacts project [ https://substack.com/redirect/e6cd815d-c402-4be3-899a-db99f7152fa8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], pasted in the above JSON and prompted it like this:
Build a tool where I can paste JSON like this into a textarea and the result will be rendered in a neat way - it should should intersperse text with citations, where each citation has the cited_text rendered in a blockquote
It helped me build this tool [ https://substack.com/redirect/5fb92aa5-59af-4f3b-a15b-79f5f4973435?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (follow-up prompt here [ https://substack.com/redirect/225ff35c-aeb1-44ba-97dc-af7c29cac163?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), which lets you paste in JSON and produces a rendered version of the text:
Now I need to design an abstraction layer for LLM
I'd like to upgrade my LLM [ https://substack.com/redirect/24094fac-2ac5-4108-85c2-b8bb01cafd6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool and llm-claude-3 [ https://substack.com/redirect/bcbbab0a-621e-4a4c-9a88-2fed7a03f2b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin to include support for this new feature... but doing so is going to be relatively non-trivial.
The problem is that LLM currently bakes in an assumption that all LLMs respond with a stream of text.
With citations, this is no longer true! Claude is now returning chunks of text that aren't just a plain string - they are annotated with citations, which need to be stored and processed somehow by the LLM library.
This isn't the only edge-case of this type. DeepSeek recently released their Reasoner API which has a similar problem: it can return two different types of text, one showing reasoning text and one showing final content. I described those differences here [ https://substack.com/redirect/dcabbeff-b2ac-4312-a23b-cd1c000f387c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I've opened a design issue to tackle this challenge in the LLM repository: Design an abstraction for responses that are not just a stream of text [ https://substack.com/redirect/4926c4ab-7693-4963-867a-b98923572c23?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Anthropic's strategy contrasted with OpenAI
Another interesting aspect of this release is how it helps illustrate a strategic difference between Anthropic and OpenAI.
OpenAI are increasingly behaving like a consumer products company. They just made a big splash with their Operator [ https://substack.com/redirect/3ed6bcff-bf47-4dde-80de-fa774d3a9d4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] browser-automation agent system - a much more polished, consumer-product version of Anthropic's own Computer Use [ https://substack.com/redirect/3ed6bcff-bf47-4dde-80de-fa774d3a9d4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] demo from a few months ago.
Meanwhile, Anthropic are clearly focused much more on the developer / "enterprise" market. This Citations feature is API-only and directly addresses a specific need that developers trying to build reliable RAG systems on top of their platform may not even have realized they had.
Introducing Operator [ https://substack.com/redirect/3ed6bcff-bf47-4dde-80de-fa774d3a9d4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-01-23
OpenAI released [ https://substack.com/redirect/bc70e06d-7a2c-4212-a910-1f260397c350?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] their "research preview" today of Operator, a cloud-based browser automation platform rolling out today to $200/month ChatGPT Pro subscribers.
They're calling this their first "agent". In the Operator announcement video Sam Altman defined that notoriously vague term [ https://substack.com/redirect/30f47f4c-f5fb-466f-9065-c7e971f9ffe9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
AI agents are AI systems that can do work for you independently. You give them a task and they go off and do it.
We think this is going to be a big trend in AI and really impact the work people can do, how productive they can be, how creative they can be, what they can accomplish.
The Operator interface looks very similar to Anthropic's Claude Computer Use [ https://substack.com/redirect/eda75810-7a35-4f6f-b7da-639d3ad7260f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] demo from October, even down to the interface with a chat panel on the left and a visible interface being interacted with on the right. Here's Operator:
And here's Claude Computer Use:
Claude Computer Use required you to run a own Docker container on your own hardware. Operator is much more of a product - OpenAI host a Chrome instance for you in the cloud, providing access to the tool via their website.
Operator runs on top of a brand new model that OpenAI are calling CUA, for Computer-Using Agent. Here's their separate announcement [ https://substack.com/redirect/ba1668c5-ca39-436f-a9a1-c209e2747b53?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] covering that new model, which should also be available via their API in the coming weeks.
This demo version of Operator is understandably cautious: it frequently asked users for confirmation to continue. It also provides a "take control" option which OpenAI's demo team used to take over and enter credit card details to make a final purchase.
The million dollar question around this concerns how they deal with security. Claude Computer Use fell victim to prompt injection attack at the first hurdle [ https://substack.com/redirect/21e2b1ff-0c4a-4a83-aed5-10f77934e58f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here's what OpenAI have to say about that [ https://substack.com/redirect/df207989-4150-478f-90f1-0694970fcecc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One particularly important category of model mistakes is adversarial attacks on websites that cause the CUA model to take unintended actions, through prompt injections, jailbreaks, and phishing attempts. In addition to the aforementioned mitigations against model mistakes, we developed several additional layers of defense to protect against these risks:
Cautious navigation: The CUA model is designed to identify and ignore prompt injections on websites, recognizing all but one case from an early internal red-teaming session.
Monitoring: In Operator, we've implemented an additional model to monitor and pause execution if it detects suspicious content on the screen.
Detection pipeline: We're applying both automated detection and human review pipelines to identify suspicious access patterns that can be flagged and rapidly added to the monitor (in a matter of hours).
Color me skeptical. I imagine we'll see all kinds of novel successful prompt injection style attacks against this model once the rest of the world starts to explore it.
My initial recommendation: start a fresh session for each task you outsource to Operator to ensure it doesn't have access to your credentials for any sites that you have used via the tool in the past. If you're having it spend money on your behalf let it get to the checkout, then provide it with your payment details and wipe the session straight afterwards.
The Operator System Card PDF [ https://substack.com/redirect/62f491fe-7c2d-4635-9d5c-0d67431499bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] has some interesting additional details. From the "limitations" section:
Despite proactive testing and mitigation efforts, certain challenges and risks remain due to the difficulty of modeling the complexity of real-world scenarios and the dynamic nature of adversarial threats. Operator may encounter novel use cases post-deployment and exhibit different patterns of errors or model mistakes. Additionally, we expect that adversaries will craft novel prompt injection attacks and jailbreaks. Although we’ve deployed multiple mitigation layers, many rely on machine learning models, and with adversarial robustness still an open research problem, defending against emerging attacks remains an ongoing challenge.
Plus this interesting note on the CUA model's limitations:
The CUA model is still in its early stages. It performs best on short, repeatable tasks but faces challenges with more complex tasks and environments like slideshows and calendars.
Six short video demos of LLM and Datasette projects [ https://substack.com/redirect/1c282c95-2e66-476e-a4da-cf33065cb142?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-01-22
Last Friday Alex Garcia and I hosted a new kind of Datasette Public Office Hours session, inviting members of the Datasette community to share short demos of projects that they had built. The session lasted just over an hour and featured demos from six different people.
We broadcast live on YouTube, but I've now edited the session into separate videos. These are listed below, along with project summaries and show notes for each presentation.
You can also watch all six videos in this YouTube playlist [ https://substack.com/redirect/1efc60ef-9bef-4713-b2df-9a37278f8b6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
llm-logs-feedback by Matthias Lübken [ https://substack.com/redirect/39ad2af4-a763-4dc0-9f29-da54062604b4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
llm-model-gateway and llm-consortium by Thomas Hughes [ https://substack.com/redirect/768451f1-38db-4c4d-894c-f04c2811b2aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Congressional Travel Explorer with Derek Willis [ https://substack.com/redirect/f67c1e9c-47f8-4200-b81a-555fdc923e99?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
llm-questioncache with Nat Knight [ https://substack.com/redirect/9e674190-6fb3-4e62-8ee6-f99157ae7bd2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Improvements to Datasette Enrichments with Simon Willison [ https://substack.com/redirect/27ac1e3f-28f9-4d9c-aa95-0c68b84cc092?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Datasette comments, pins and write UI with Alex Garcia [ https://substack.com/redirect/b3c9ff8e-d578-4368-b557-358c6c0051f0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
llm-logs-feedback by Matthias Lübken
llm-logs-feedback [ https://substack.com/redirect/48284958-a92c-4aec-b96d-ce9ec75abde8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a plugin by Matthias Lübken for LLM [ https://substack.com/redirect/24094fac-2ac5-4108-85c2-b8bb01cafd6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which adds the ability to store feedback on prompt responses, using new llm feedback+1 and llm feedback-1 commands. These also accept an optional comment, and the feedback is stored in a feedback table in SQLite.
You can install the plugin from PyPI like this:
llm install llm-logs-feedback
The full plugin implementation is in the llm_logs_feedback.py file [ https://substack.com/redirect/628fb3b6-42a5-4787-a811-c24930c65f84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in Matthias' GitHub repository.
llm-model-gateway and llm-consortium by Thomas Hughes
Tommy Hughes has been developing a whole array of LLM plugins, including his llm-plugin-generator [ https://substack.com/redirect/abfd01a1-6860-4f23-978d-97175bd41e50?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which is a plugin that can help write new plugins!
He started by demonstrating llm-model-gateway [ https://substack.com/redirect/f3747149-3121-4a45-b859-24ae5c775748?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a plugin that adds a llm serve command which starts a localhost server running an imitation of the OpenAI API against LLM models:
llm install llm-model-gateway
llm serve
Tommy's main demo was of llm-consortium [ https://substack.com/redirect/a7d16ddd-003a-4119-b657-0deef5b7ff8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a plugin which can use a consortium of collaborating LLM models working together to solve problems.
llm install llm-consortium
llm consortium "Best way to prepare avocado toast" \
--models claude-3.5-sonnet \
--models gpt-4o \
--arbiter gegemini-1.5-pro-latest \
--confidence-threshold 0.8 \
--max-iterations 3 \
--output results.json
I ran this and got back:
The best way to prepare avocado toast involves selecting quality ingredients and careful preparation. Start with a thick slice of good quality bread, such as sourdough or whole grain. Toast it to your preferred level of crispness. While the bread is toasting, prepare a ripe avocado. Cut it in half, remove the pit, and scoop the flesh into a bowl. Mash the avocado with a fork, leaving some chunks for texture. Season with salt, black pepper, and a squeeze of fresh lemon juice to prevent browning. Optional additions include a touch of red pepper flakes.
Once the toast is ready, let it cool slightly before spreading the seasoned avocado evenly over it. Consider lightly rubbing a cut garlic clove on the warm toast for an extra layer of flavor (optional).
Enhance your avocado toast with your favorite toppings. Popular choices include: everything bagel seasoning, sliced tomatoes, radishes, a poached or fried egg (for added protein), microgreens, smoked salmon (for a more savory option), feta cheese crumbles, or a drizzle of hot sauce. For a finishing touch, drizzle with high-quality olive oil and sprinkle with sesame or chia seeds for added texture.
Consider dietary needs when choosing toppings. For example, those following a low-carb diet might skip the tomatoes and opt for more protein and healthy fats.
Finally, pay attention to presentation. Arrange the toppings neatly for a visually appealing toast. Serve immediately to enjoy the fresh flavors and crispy toast.
But the really interesting thing is the full log of the prompts and responses sent to Claude 3.5 Sonnet and GPT-4o, followed by a combined prompt to Gemini 1.5 Pro to have it arbitrate between the two responses. You can see the full logged prompts and responses here [ https://substack.com/redirect/d325c6e3-6f93-4361-81b8-ec0edbb27d7d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here's that results.json [ https://substack.com/redirect/ec24862f-9c29-443d-ad11-1dca1d857a1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] output file.
Congressional Travel Explorer with Derek Willis
Derek Willis teaches data journalism at the Philip Merrill College of Journalism at the University of Maryland. For a recent project his students built a Congressional Travel Explorer [ https://substack.com/redirect/334caf0a-3381-4133-b83b-94b239bdb794?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] interactive using Datasette, AWS Extract and Claude 3.5 Sonnet to analyze travel disclosures from members of Congress.
One of the outcomes from the project was this story in Politico: Members of Congress have taken hundreds of AIPAC-funded trips to Israel in the past decade [ https://substack.com/redirect/4a7328c2-3def-46db-8c92-841a4152723e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
llm-questioncache with Nat Knight
llm-questioncache [ https://substack.com/redirect/da926031-3080-4da9-b5f4-16e47794ff63?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] builds on top of
https://llm.datasette.io/
to cache answers to questions, using embeddings to return similar answers if they have already been stored.
Using embeddings for de-duplication of similar questions is an interesting way to apply LLM's embeddings feature [ https://substack.com/redirect/a8c05bbc-2213-4d74-aa2b-e9e983414cf3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Improvements to Datasette Enrichments with Simon Willison
I've demonstrated improvements I've been making to Datasette's Enrichments [ https://substack.com/redirect/e64be14a-56e0-4f52-9e3c-6afb4410fbaf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] system over the past few weeks.
Enrichments allow you to apply an operation - such as geocoding, a QuickJS JavaScript transformation or an LLM prompt - against selected rows within a table.
The latest release of datasette-enrichments [ https://substack.com/redirect/459fcc08-c643-44bb-a7c5-70373ef138a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adds visible progress bars and the ability to pause, resume and cancel an enrichment job that is running against a table.
Datasette comments, pins and write UI with Alex Garcia
We finished with three plugin demos from Alex, showcasing collaborative features we have been developing for Datasette Cloud [ https://substack.com/redirect/55c6e138-8bf9-4b25-a340-a65620b10dff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
datasette-write-ui [ https://substack.com/redirect/c374caec-4ae3-49e2-8ef6-31e4774a6509?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provides tools for editing and adding data to Datasette tables. A new feature here is the ability to shift-click a row to open the editing interface for that row.
datasette-pins [ https://substack.com/redirect/619835da-908c-44b7-b1dc-afabde7463b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] allows users to pin tables and databases to their Datasette home page, making them easier to find.
datasette-comments [ https://substack.com/redirect/a4db7fc2-d395-4d10-9b45-b34777996d8a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adds a commenting interface to Datasette, allowing users to leave comments on individual rows in a table.
Quote 2025-01-21
Is what you're doing taking a large amount of text and asking the LLM to convert it into a smaller amount of text? Then it's probably going to be great at it. If you're asking it to convert into a roughly equal amount of text it will be so-so. If you're asking it to create more text than you gave it, forget about it.
Laurie Voss [ https://substack.com/redirect/10a88032-fb31-44ac-a257-cfe900dc027d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-01-21 AI mistakes are very different from human mistakes [ https://substack.com/redirect/509808be-2f5a-4ea5-9f8d-1d69a4e51408?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
An entertaining and informative read by Bruce Schneier and Nathan E. Sanders.
If you want to use an AI model to help with a business problem, it’s not enough to see that it understands what factors make a product profitable; you need to be sure it won’t forget what money is.
Link 2025-01-22 Run DeepSeek R1 or V3 with MLX Distributed [ https://substack.com/redirect/7792fba9-ac1a-45c2-b323-5690c5afa24d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Handy detailed instructions from Awni Hannun on running the enormous DeepSeek R1 or v3 models on a cluster of Macs using the distributed communication [ https://substack.com/redirect/651c73b3-9331-418f-b40d-9f3262ff93f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] feature of Apple's MLX library.
DeepSeek R1 quantized to 4-bit requires 450GB in aggregate RAM, which can be achieved by a cluster of three 192 GB M2 Ultras ($16,797 will buy you three 192GB Apple M2 Ultra Mac Studios at $5,599 each).
Link 2025-01-22 llm-gemini 0.9 [ https://substack.com/redirect/b3f52c5a-a512-425a-b48b-86bbd6d366a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This new release of my llm-gemini plugin adds support for two new experimental models:
learnlm-1.5-pro-experimental is "an experimental task-specific model that has been trained to align with learning science principles when following system instructions for teaching and learning use cases" - more here [ https://substack.com/redirect/4d073571-bbbf-43a7-be4c-bc43161beb58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
gemini-2.0-flash-thinking-exp-01-21 is a brand new version of the Gemini 2.0 Flash Thinking model released today [ https://substack.com/redirect/cd1ddff7-0961-4c76-b11e-01687af94fa8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Latest version also includes code execution, a 1M token content window & a reduced likelihood of thought-answer contradictions.
The most exciting new feature though is support for Google search grounding [ https://substack.com/redirect/37b6b624-f555-4b63-b981-0b3416d2b782?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], where some Gemini models can execute Google searches as part of answering a prompt. This feature can be enabled using the new -o google_search 1 option.
Link 2025-01-22 r1.py script to run R1 with a min-thinking-tokens parameter [ https://substack.com/redirect/0d85b663-1077-40f9-bf57-bca1cac56e3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fantastically creative hack by Theia Vogel. The DeepSeek R1 family [ https://substack.com/redirect/6f6d5468-f326-4cd2-b6db-334aa53dc591?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of models output their chain of thought inside a ... block. Theia found that you can intercept that closing  and replace it with "Wait, but" or "So" or "Hmm" and trick the model into extending its thought process, producing better solutions!
You can stop doing this after a few iterations, or you can keep on denying the  string and effectively force the model to "think" forever.
Theia's code here works against Hugging Face transformers but I'm confident the same approach could be ported to llama.cpp or MLX.
Link 2025-01-22 Trading Inference-Time Compute for Adversarial Robustness [ https://substack.com/redirect/2b907741-892e-4db9-a9c8-4038ba23bce7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Brand new research paper from OpenAI, exploring how inference-scaling "reasoning" models such as o1 might impact the search for improved security with respect to things like prompt injection.
We conduct experiments on the impact of increasing inference-time compute in reasoning models (specifically OpenAI o1-preview and o1-mini) on their robustness to adversarial attacks. We find that across a variety of attacks, increased inference-time compute leads to improved robustness. In many cases (with important exceptions), the fraction of model samples where the attack succeeds tends to zero as the amount of test-time compute grows.
They clearly understand why this stuff is such a big problem, especially as we try to outsource more autonomous actions to "agentic models":
Ensuring that agentic models function reliably when browsing the web, sending emails, or uploading code to repositories can be seen as analogous to ensuring that self-driving cars drive without accidents. As in the case of self-driving cars, an agent forwarding a wrong email or creating security vulnerabilities may well have far-reaching real-world consequences. Moreover, LLM agents face an additional challenge from adversaries which are rarely present in the self-driving case. Adversarial entities could control some of the inputs that these agents encounter while browsing the web, or reading files and images.
This is a really interesting paper, but it starts with a huge caveat. The original sin of LLMs - and the reason prompt injection [ https://substack.com/redirect/c41ccf22-1a07-440e-89e9-d98ee01ada6f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is such a hard problem to solve - is the way they mix instructions and input data in the same stream of tokens. I'll quote section 1.2 of the paper in full - note that point 1 describes that challenge:
1.2 Limitations of this work
The following conditions are necessary to ensure the models respond more safely, even in adversarial settings:
Ability by the model to parse its context into separate components. This is crucial to be able to distinguish data from instructions, and instructions at different hierarchies.
Existence of safety specifications that delineate what contents should be allowed or disallowed, how the model should resolve conflicts, etc..
Knowledge of the safety specifications by the model (e.g. in context, memorization of their text, or ability to label prompts and responses according to them).
Ability to apply the safety specifications to specific instances. For the adversarial setting, the crucial aspect is the ability of the model to apply the safety specifications to instances that are out of the training distribution, since naturally these would be the prompts provided by the adversary,
They then go on to say (emphasis mine):
Our work demonstrates that inference-time compute helps with Item 4, even in cases where the instance is shifted by an adversary to be far from the training distribution (e.g., by injecting soft tokens or adversarially generated content). However, our work does not pertain to Items 1-3, and even for 4, we do not yet provide a "foolproof" and complete solution.
While we believe this work provides an important insight, we note that fully resolving the adversarial robustness challenge will require tackling all the points above.
So while this paper demonstrates that inference-scaled models can greatly improve things with respect to identifying and avoiding out-of-distribution attacks against safety instructions, they are not claiming a solution to the key instruction-mixing challenge of prompt injection. Once again, this is not the silver bullet we are all dreaming of.
The paper introduces two new categories of attack against inference-scaling models, with two delightful names: "Think Less" and "Nerd Sniping".
Think Less attacks are when an attacker tricks a model into spending less time on reasoning, on the basis that more reasoning helps prevent a variety of attacks so cutting short the reasoning might help an attack make it through.
Nerd Sniping (see XKCD 356 [ https://substack.com/redirect/d56a9fa5-b136-4ce9-90d9-f098586b962a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) does the opposite: these are attacks that cause the model to "spend inference-time compute unproductively". In addition to added costs, these could also open up some security holes - there are edge-cases where attack success rates go up for longer compute times.
Sadly they didn't provide concrete examples for either of these new attack classes. I'd love to see what Nerd Sniping looks like in a malicious prompt!
Quote 2025-01-22
When I give money to a charitable cause, I always look for the checkboxes to opt out of being contacted by them in the future. When it happens anyway, I get annoyed, and I become reluctant to give to that charity again. [...]
When you donate to the Red Cross via Apple, that concern is off the table. Apple won’t emphasize that aspect of this, because they don’t want to throw the Red Cross under the proverbial bus, but I will. An underrated aspect of privacy is the desire simply not to be annoyed.
John Gruber [ https://substack.com/redirect/3db7a293-7777-4c54-bf90-5219f0374520?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-01-23 LLM 0.20 [ https://substack.com/redirect/7649cee3-c1a4-4572-ad1c-8c7fba46a506?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New release of my LLM [ https://substack.com/redirect/24094fac-2ac5-4108-85c2-b8bb01cafd6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CLI tool and Python library. A bunch of accumulated fixes and features since the start of December, most notably:
Support for OpenAI's o1 model [ https://substack.com/redirect/6b82e706-fadd-4849-9156-04a4520f9605?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a significant upgrade from o1-preview given its 200,000 input and 100,000 output tokens (o1-preview was 128,000/32,768). #676 [ https://substack.com/redirect/024166d1-31df-4620-b8bf-51a115594068?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Support for the gpt-4o-audio-preview and gpt-4o-mini-audio-preview models, which can accept audio input: llm -m gpt-4o-audio-preview -a https://static.simonwillison.net/static/2024/pelican-joke-request.mp3 #677 [ https://substack.com/redirect/a214dfde-760b-483d-9c98-b689c1784fac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
A new llm -x/--extract option which extracts and returns the contents of the first fenced code block in the response. This is useful for prompts that generate code. #681 [ https://substack.com/redirect/7df8d44b-82be-4684-a5e1-3486be07dda9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
A new llm models -q 'search' option for searching available models - useful if you've installed a lot of plugins. Searches are case insensitive. #700 [ https://substack.com/redirect/5d85310d-b54a-4c61-92a3-f58ee6188cdb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-01-23
I can’t reference external reports critical of China. Need to emphasize China’s policies on ethnic unity, development in Xinjiang, and legal protections. Avoid any mention of controversies or allegations to stay compliant.
DeepSeek R1 [ https://substack.com/redirect/2cbf3ca8-91dd-4cbd-8a2e-3b3d73a435d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-01-24
AI tools create a significant productivity boost for developers. Different folks report different gains, but most people who try AI code generation recognize its ability to increase velocity. Many people think that means we’re going to need fewer developers, and our industry is going to slowly circle the drain.
This view is based on a misunderstanding of why people pay for software. A business creates software because they think that it will give them some sort of economic advantage. The investment needs to pay for itself with interest. There are many software projects that would help a business, but businesses aren’t going to do them because the return on investment doesn’t make sense.
When software development becomes more efficient, the ROI of any given software project increases, which unlocks more projects. [...] Cheaper software means people are going to want more of it. More software means more jobs for increasingly efficient software developers.
Dustin Ewers [ https://substack.com/redirect/1a151d17-0ba9-45c3-8778-132725a3b4f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVFUxT1RRM016Y3NJbWxoZENJNk1UY3pOelk1TXprMU55d2laWGh3SWpveE56WTVNakk1T1RVM0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuVExuZUpSUmFuWmNYVmZIZE5wMnFBT2tuUm5pdWJOOFBFWUpNS3NZcUJ1QSIsInAiOjE1NTU5NDczNywicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzM3NjkzOTU3LCJleHAiOjE3NDAyODU5NTcsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.fvyJooKMp6CAxJdVxzC0RA6Z7ErAExommc5-q2j1P6I?
