# Notes on Google's Gemma 3

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-03-14T05:33:18.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/notes-on-googles-gemma-3

In this newsletter:
Notes on Google's Gemma 3
Adding AI-generated descriptions to my tools collection
Plus 6 links and 4 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Notes on Google's Gemma 3 [ https://substack.com/redirect/dd4d0900-dd25-4394-9c4d-290b6dc0e00f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-03-12
Google's Gemma team released an impressive new model today (under their not-open-source Gemma license [ https://substack.com/redirect/02c5c606-02ca-4321-bcae-b605b4eae301?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). Gemma 3 comes in four sizes - 1B, 4B, 12B, and 27B - and while 1B is text-only the larger three models are all multi-modal for vision:
Gemma 3 introduces multimodality, supporting vision-language input and text outputs. It handles context windows up to 128k tokens, understands over 140 languages, and offers improved math, reasoning, and chat capabilities, including structured outputs and function calling.
Here's the Gemma 3 Technical Report PDF [ https://substack.com/redirect/502252ae-d96b-41f7-877e-5e9b73f5fc87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which makes the big claim that they find "Gemma3-27B-IT comparable to Gemini-1.5-Pro across benchmarks".
I tried out the largest model using the latest Ollama [ https://substack.com/redirect/fcddad62-3716-4107-b382-5851df1c8be8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - this is the second time I've spotted a major model release partnering with Ollama on launch day, the first being Mistral Small 3 [ https://substack.com/redirect/409aceac-d903-48cf-8f70-0395b51dc327?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I ran this (after upgrading Ollama through their menu icon upgrade option):
ollama pull gemma3:27b
That pulled 17GB of model weights. I've been trying it out using LLM [ https://substack.com/redirect/a52423d6-2a9b-4ad0-8668-90b4898dd3cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and llm-ollama [ https://substack.com/redirect/8ef19cff-200e-4ff4-892d-cfa8089e6074?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm install llm-ollama
llm -m gemma3:27b 'Build a single page HTML+CSS+JavaScript UI that gives me a large textarea for writing in which constantly saves what I have entered to localStorage (restoring when I reload the page) and displays a word counter'
That was a replay of a prompt [ https://substack.com/redirect/2f4c46e0-94d0-4b91-9efb-c5fe63d1b6f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I ran against Claude Artifacts a few months ago. Here's what Gemma built [ https://substack.com/redirect/197f4315-ce37-4277-9bb2-f052d96871ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and the full chat transcript [ https://substack.com/redirect/ad802fbd-3bd9-48f9-9d9a-413affd3a093?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It's a simple example but it worked just right.
Let's try out the vision mode, by asking it to describe this photo:
llm -m gemma3:27b describe -a https://static.simonwillison.net/static/2025/two-pelicans.jpg
Here's the full response [ https://substack.com/redirect/6654a5cd-a9c0-4ad3-8a49-386fe055436f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Overall Impression:
The image features two brown pelicans in flight against a solid, bright blue background. The composition is dynamic, capturing the birds mid-wingbeat.
Details:
Pelicans: Both pelicans are a rich, dark brown color. They have large, pale yellow-orange beaks and pouches. One pelican is shown with its wings fully extended, appearing to be gliding or soaring. The other is captured with its wings in a more dynamic, upward-sweeping motion.
Background: The background is a flat, uniform shade of bright blue, which makes the pelicans stand out.
Composition: The birds are positioned in opposite directions, creating a sense of movement and balance. The image is well-lit, highlighting the texture of the pelicans' feathers.
Overall, the image is a striking and visually appealing depiction of these majestic birds in flight.
Is it right to say "the birds are positioned in opposite directions"? I thought that was a mistake at first, but I'll give it a pass since their wings are positioned in opposite directions to each other.
Something I've been curious about recently is longer context support: how well can a local model on my laptop deal with summarization or data extraction tasks against longer pieces of text?
I decided to try my Hacker News summarize script [ https://substack.com/redirect/a2537655-2ce9-48e1-8497-75573bf0c3e5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using Gemma, against the thread [ https://substack.com/redirect/71e042cd-9c13-4759-a60d-05aeaec55110?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] there discussing the Gemma 3 technical paper.
First I did a quick token count (using the OpenAI tokenizer but it's usually a similar number to other models):
curl 'https://hn.algolia.com/api/v1/items/43340491' | ttok
This returned 22,260 - well within Gemma's documented limits but still a healthy number considering just last year most models topped out at 4,000 or 8,000.
I ran my script like this:
hn-summary.sh 43340491 -m gemma3:27b
It did a pretty good job! Here's the full prompt and response [ https://substack.com/redirect/23461a5e-c26d-43e1-acfd-9bb2f21203eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The one big miss is that it ignored my instructions to include illustrative quotes - I don't know if modifying the prompt will fix that but it's disappointing that it didn't handle that well, given how important direct quotes are for building confidence in RAG-style responses.
Here's what I got for Generate an SVG of a pelican riding a bicycle [ https://substack.com/redirect/912471e7-fd83-4d27-844a-7e62474f3155?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm -m gemma3:27b 'Generate an SVG of a pelican riding a bicycle'
You can also try out the new Gemma in Google AI Studio [ https://substack.com/redirect/915de534-e649-4ec2-8f50-07ea9f4f9f13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and via their API. I added support for it to llm-gemini 0.15 [ https://substack.com/redirect/57401786-c182-461b-ae3a-f1b4d9508d65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], though sadly it appears vision mode doesn't work with that API hosted model yet.
llm install -U llm-gemini
llm keys set gemini
# paste key here
llm -m gemma-3-27b-it 'five facts about pelicans of interest to skunks'
Here's what I got [ https://substack.com/redirect/5b3bf2b7-6353-40b6-a9b2-08ac58cc40b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I'm not sure how pricing works for that hosted model.
Gemma 3 is also already available through MLX-VLM [ https://substack.com/redirect/417acf89-9108-4ac6-83d9-cb1531c6e83c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - here's the MLX model collection [ https://substack.com/redirect/6265b63c-d6df-40cb-afdf-f721752842e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - but I haven't tried that version yet.
Adding AI-generated descriptions to my tools collection [ https://substack.com/redirect/af8a5088-aef4-41c1-a10d-ef4daac2cde8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-03-13
The /colophon [ https://substack.com/redirect/02861877-5cc8-4723-9a67-fc28dcc9140f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] page on my tools.simonwillison.net [ https://substack.com/redirect/cfcded25-6260-4b41-8a72-354707b85abd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] site lists all 78 of the HTML+JavaScript tools I've built (with AI assistance [ https://substack.com/redirect/088cd048-8da1-4693-bc9e-0ea545593847?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) along with their commit histories, including links to prompting transcripts. I wrote about how I built that colophon [ https://substack.com/redirect/3ce1adb6-89b5-4644-a140-82be96c1c25f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the other day. It now also includes a description of each tool, generated using Claude 3.7 Sonnet.
This is the single largest chunk of AI-generated text I've ever published on the indexable web. I share lots of LLM transcripts but I usually put them in a secret Gist such that they'll be kept out of search engines.
On the one hand this feels slop adjacent [ https://substack.com/redirect/68a326e7-89b2-4563-8547-989536f7a034?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - but I was never going to write documentation for all 78 of those little experiments, yet I find myself forgetting details of how they worked. Just one example: my CSV marker map [ https://substack.com/redirect/e2a15944-cf5d-460c-a597-b5459c25dba6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool which I built last year for knocking out an ad-hoc Bigfoot sightings map [ https://substack.com/redirect/4f738602-71c7-40d8-9cf8-a10518a18365?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and then promptly forgot what it could do.
Here's what I got when I ran:
cat csv-marker-map.html | llm -m claude-3.7-sonnet \
--system "Write a paragraph of documentation for this page as markdown. Do not include a heading. Do not use words like just or simply."
This interactive map displays markers based on data from a CSV file. Load data by adding ?csv=URL to the page URL, where the CSV must include latitude and longitude columns. You can customize the map with several URL parameters: center(coordinates in format lat,lng), zoom(zoom level), q (location to search for), marker (add individual markers at coordinates), and color (change the default marker color). The map automatically updates the URL as you navigate, preserving your current view. Markers from CSV files appear as small colored circles on the map, while markers specified directly in the URL use the default Leaflet marker style.
That's genuinely useful. I got Claude [ https://substack.com/redirect/b0b71e9b-48b0-4360-942a-48ffe92a22ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to write me a write_docs.py [ https://substack.com/redirect/ff27dd5c-71fb-4631-984b-5bae559b19b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] script to loop through all 78 files and generate filename.docs.md descriptions that live in the repo, then updated build_colophon.py [ https://substack.com/redirect/caa4230b-6c03-42b4-85e4-a7062d7f8f0a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]to include those descriptions if they exist.
It cost about $1.08 in Claude credits to document all 78 tools, because some of those HTML files were quite long so the input tokens added up.
Each of the documentation files includes a comment with the most recent commit hash of the file that was used to generate the document, like this:

The tool can use this to spot if a file has been updated - if so, the documentation will be regenerated.
Add this all together and now I can drop new HTML+JavaScript tools into my simonw/tools [ https://substack.com/redirect/cc8e04f1-9b20-4557-9b67-5f6afd46d51f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]repo and, moments later, they'll be published on tools.simonwillison.net [ https://substack.com/redirect/cfcded25-6260-4b41-8a72-354707b85abd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with auto-generated descriptions added to my colophon [ https://substack.com/redirect/02861877-5cc8-4723-9a67-fc28dcc9140f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I think that's pretty neat!
Update: I decided that the descriptions were too long, so I modified the script to add "Keep it to 2-3 sentences" to the end of the system prompt. These new, shorter descriptions are now live - here's the diff [ https://substack.com/redirect/c3030e3a-45a1-4cb9-bac8-8ddd1a0eb34e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Total usage was 283,528 input tokens and 6,010 output tokens for a cost of 94 cents.
The new, shorter description for csv-marker-map.html looks like this:
This page creates an interactive map with markers based on CSV data. It accepts parameters in the URL to set the center, zoom level, search query, individual markers, and a CSV file URL for bulk marker placement. The markers are displayed on an OpenStreetMap base layer, and the map view automatically updates the URL when panned or zoomed.
For comparison, here's a copy of the previous colophon [ https://substack.com/redirect/34e69528-f1b4-4b32-bd69-2c001218f4f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with the longer descriptions.
Quote 2025-03-11
Languages that allow for a structurally similar codebase offer a significant boon for anyone making code changes because we can easily port changes between the two codebases. In contrast, languages that require fundamental rethinking of memory management, mutation, data structuring, polymorphism, laziness, etc., might be a better fit for a ground-up rewrite, but we're undertaking this more as a port that maintains the existing behavior and critical optimizations we've built into the language. Idiomatic Go strongly resembles the existing coding patterns of the TypeScript codebase, which makes this porting effort much more tractable.
Ryan Cavanaugh [ https://substack.com/redirect/ef32b462-1838-48e4-b979-b82e35ffe4c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-03-11 OpenAI API: Responses vs. Chat Completions [ https://substack.com/redirect/db925d31-5ff2-4afa-ae2d-928b44aa3abb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI released a bunch of new API platform features this morning under the headline "New tools for building agents [ https://substack.com/redirect/03775838-390f-49d5-a73e-680f4d101919?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]" (their somewhat mushy interpretation of "agents" here is "systems that independently accomplish tasks on behalf of users").
A particularly significant change is the introduction of a new Responses API, which is a slightly different shape from the Chat Completions API that they've offered for the past couple of years and which others in the industry have widely cloned as an ad-hoc standard.
In this guide [ https://substack.com/redirect/db925d31-5ff2-4afa-ae2d-928b44aa3abb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] they illustrate the differences, with a reassuring note that:
The Chat Completions API is an industry standard for building AI applications, and we intend to continue supporting this API indefinitely. We're introducing the Responses API to simplify workflows involving tool use, code execution, and state management. We believe this new API primitive will allow us to more effectively enhance the OpenAI platform into the future.
An API that is going away is the Assistants API [ https://substack.com/redirect/2311c56f-e252-4fef-ae05-7c5efdc32870?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a perpetual beta first launched at OpenAI DevDay in 2023. The new responses API solves effectively the same problems but better, and assistants will be sunset "in the first half of 2026".
The best illustration I've seen of the differences between the two is this giant commit [ https://substack.com/redirect/4e4f7d10-c491-4349-b146-b49ca880e9c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to the openai-python GitHub repository updating ALL of the example code in one go.
The most important feature of the Responses API (a feature it shares with the old Assistants API) is that it can manage conversation state on the server for you. An oddity of the Chat Completions API is that you need to maintain your own records of the current conversation, sending back full copies of it with each new prompt. You end up making API calls that look like this (from their examples [ https://substack.com/redirect/91c877ce-b2fd-4414-b10e-697a0825262d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
{
"model": "gpt-4o-mini",
"messages": [
{
"role": "user",
"content": "knock knock.",
},
{
"role": "assistant",
"content": "Who's there?",
},
{
"role": "user",
"content": "Orange."
}
]
}
These can get long and unwieldy - especially when attachments such as images are involved - but the real challenge is when you start integrating tools: in a conversation with tool use you'll need to maintain that full state and drop messages in that show the output of the tools the model requested. It's not a trivial thing to work with.
The new Responses API continues to support this list of messages format, but you also get the option to outsource that to OpenAI entirely: you can add a new "store": true property and then in subsequent messages include a "previous_response_id: response_id key to continue that conversation.
This feels a whole lot more natural than the Assistants API, which required you to think in terms of threads, messages and runs [ https://substack.com/redirect/d6dffb8b-666e-429f-a1da-7b8291234628?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to achieve the same effect.
Also fun: the Response API supports HTML form encoding [ https://substack.com/redirect/faa3c487-cac0-4054-a16e-e7c547a5d54a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] now in addition to JSON:
curl https://api.openai.com/v1/responses \
-u :$OPENAI_API_KEY \
-d model="gpt-4o" \
-d input="What is the capital of France?"
I found that in an excellent Twitter thread [ https://substack.com/redirect/cd7c8191-e2a4-4358-b7fe-7f1f1726d8b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]providing background on the design decisions in the new API from OpenAI's Atty Eleti. Here's a nitter link [ https://substack.com/redirect/f9412056-4bcc-42e3-ac7b-eeb6897c7dce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for people who don't have a Twitter account.
New built-in tools
A potentially more exciting change today is the introduction of default tools that you can request while using the new Responses API. There are three of these, all of which can be specified in the "tools": [...] array.
{"type": "web_search_preview"} - the same search feature available through ChatGPT. The documentation doesn't clarify which underlying search engine is used - I initially assumed Bing, but the tool documentation links to this Overview of OpenAI Crawlers [ https://substack.com/redirect/107df4a8-481c-432d-ba1b-ec134185df92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]page so maybe it's entirely in-house now? Web search is priced [ https://substack.com/redirect/6912f642-ca71-4613-bfee-de642d860ffe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at between $25 and $50 per thousand queries depending on if you're using GPT-4o or GPT-4o mini and the configurable size of your "search context".
{"type": "file_search", "vector_store_ids": [...]} provides integration with the latest version of their file search [ https://substack.com/redirect/a0432bbd-0885-4572-8aab-562150e453da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] vector store, mainly used for RAG. "Usage is priced at $2.50 per thousand queries and file storage at $0.10/GB/day, with the first GB free".
{"type": "computer_use_preview", "display_width": 1024, "display_height": 768, "environment": "browser"} is the most surprising to me: it's tool access to the Computer-Using Agent [ https://substack.com/redirect/f148c1db-b7a7-424f-9fda-4f8172d77eaf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] system they built for their Operator product. This one is going to be a lot of fun to explore. The tool's documentation includes a warning about prompt injection risks [ https://substack.com/redirect/f9f2df10-3f9f-43ea-8946-319b52c1c715?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Though on closer inspection I think this may work more like Claude Computer Use [ https://substack.com/redirect/6edc4921-53c8-4c2c-b0a7-97e403b423b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], where you have to run the sandboxed environment yourself [ https://substack.com/redirect/1966c62b-9bfa-4c20-a84f-b5f9e384faa3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] rather than outsource that difficult part to them.
I'm still thinking through how to expose these new features in my LLM [ https://substack.com/redirect/a52423d6-2a9b-4ad0-8668-90b4898dd3cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool, which is made harder by the fact that a number of plugins now rely on the default OpenAI implementation from core, which is currently built on top of Chat Completions. I've been worrying for a while about the impact of our entire industry building clones of one proprietary API that might change in the future, I guess now we get to see how that shakes out!
Link 2025-03-11 OpenAI Agents SDK [ https://substack.com/redirect/b44361f0-d4d3-423a-b128-2fee90b1df86?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI's other big announcement today (see also [ https://substack.com/redirect/b511ff06-efdc-47a4-947c-4ee17077ea2d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) - a Python library (openai-agents [ https://substack.com/redirect/524a88c0-f8f2-4039-b059-04077b88ce36?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) for building "agents", which is a replacement for their previous swarm [ https://substack.com/redirect/511e00d7-d258-4e83-8087-d5bff67423d4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] research project.
In this project, an "agent" is a class that configures an LLM with a system prompt an access to specific tools.
An interesting concept in this one is the concept of handoffs [ https://substack.com/redirect/6b08ea2a-ce10-4994-88f4-544a5e5e5960?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], where one agent can chose to hand execution over to a different system-prompt-plus-tools agent treating it almost like a tool itself. This code example illustrates the idea:
from agents import Agent, handoff

billing_agent = Agent(
name="Billing agent"
)
refund_agent = Agent(
name="Refund agent"
)
triage_agent = Agent(
name="Triage agent",
handoffs=[billing_agent, handoff(refund_agent)]
)
The library also includes guardrails [ https://substack.com/redirect/ff02a3ad-ba5d-47b9-bdeb-ded543fede8d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - classes you can add that attempt to filter user input to make sure it fits expected criteria. Bits of this look suspiciously like trying to solve AI security problems with more AI [ https://substack.com/redirect/60785dda-a355-4c3d-ad42-193d2d84c811?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to me.
Link 2025-03-13 Smoke test your Django admin site [ https://substack.com/redirect/7cef9d63-b9e6-4738-b653-a1b24021b5c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Justin Duke demonstrates a neat pattern for running simple tests against your internal Django admin site: introspect every admin route via django.urls.get_resolver and loop through them with @pytest.mark.parametrize to check they all return a 200 HTTP status code.
This catches simple mistakes with the admin configuration that trigger exceptions that might otherwise go undetected.
I rarely write automated tests against my own admin sites and often feel guilty about it. I wrote some notes [ https://substack.com/redirect/8003a190-a3f2-4594-8141-fda4281ff39c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on testing it with pytest-django fixtures [ https://substack.com/redirect/7b811c05-bb8d-4606-ae7f-6531fee45c9b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a few years ago.
Link 2025-03-13 Introducing Command A: Max performance, minimal compute [ https://substack.com/redirect/633729ad-2606-44a0-af80-ae028163ecb9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New LLM release from Cohere. It's interesting to see which aspects of the model they're highlighting, as an indicator of what their commercial customers value the most (highlight mine):
Command A delivers maximum performance with minimal hardware costs when compared to leading proprietary and open-weights models, such as GPT-4o and DeepSeek-V3. For private deployments, Command A excels on business-critical agentic and multilingual tasks, while being deployable on just two GPUs, compared to other models that typically require as many as 32.
It's open weights but very much not open source - the license is Creative Commons Attribution Non-Commercial [ https://substack.com/redirect/0a457804-e4d5-4086-8b84-4011c45be8e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and also requires adhering to their Acceptable Use Policy [ https://substack.com/redirect/bb8780c4-7bb0-4a10-9831-53ca55a94200?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Cohere offer it for commercial use via "contact" us pricing or through their API. I released llm-command-r 0.3 [ https://substack.com/redirect/14ec5d8d-e6de-4e08-818c-9f3f7167563d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adding support for this new model, plus their smaller and faster Command R7B [ https://substack.com/redirect/dfb75b5c-788c-40c7-86d1-211046d84407?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (released in December) and support for structured outputs via LLM schemas [ https://substack.com/redirect/2f307060-5747-435f-9ca5-50b47d23d81d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
(I found a weird bug [ https://substack.com/redirect/6b7bde0c-b920-4104-82b3-2519ad4a54a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with their schema support where schemas that end in an integer output a seemingly limitless integer - in my experiments it affected Command R and the new Command A but not Command R7B.)
Link 2025-03-13 Anthropic API: Text editor tool [ https://substack.com/redirect/4ed58525-6094-4dd3-8cbc-411eba13a3b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic released a new "tool" today for text editing. It looks similar to the tool they offered as part of their computer use beta API [ https://substack.com/redirect/0a0c101a-df94-481f-9a32-d8d76b0f6dad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and the trick they've been using for a while in both Claude Artifacts and the new Claude Code [ https://substack.com/redirect/14ac15fd-785f-4b6e-aeff-f9ada5951e66?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to more efficiently edit files there.
The new tool requires you to implement several commands:
view - to view a specified file - either the whole thing or a specified range
str_replace - execute an exact string match replacement on a file
create - create a new file with the specified contents
insert - insert new text after a specified line number
undo_edit - undo the last edit made to a specific file
Providing implementations of these commands is left as an exercise for the developer.
Once implemented, you can have conversations with Claude where it knows that it can request the content of existing files, make modifications to them and create new ones.
There's quite a lot of assembly required to start using this. I tried vibe coding an implementation [ https://substack.com/redirect/68a1c0c7-b27a-4c1f-a4b1-4448f872c565?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]by dumping a copy of the documentation into Claude itself but I didn't get as far as a working program - it looks like I'd need to spend a bunch more time on that to get something to work, so my effort is currently abandoned.
This was introduced as in a post on Token-saving updates on the Anthropic API [ https://substack.com/redirect/346ec2a5-5916-40c6-a22a-067af7d367f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which also included a simplification of their token caching API and a new Token-efficient tool use (beta) [ https://substack.com/redirect/8a3f8923-02d1-49b8-99d9-f2a2c1fd1246?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]where sending a token-efficient-tools-2025-02-19 beta header to Claude 3.7 Sonnet can save 14-70% of the tokens needed to define tools and schemas.
Quote 2025-03-13
Today we release OLMo 2 32B, the most capable and largest model in the OLMo 2 family, scaling up the OLMo 2 training recipe used for our 7B and 13B models released in November [ https://substack.com/redirect/0e497d37-02d4-479e-ab83-6d5c217ab82a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It is trained up to 6T tokens and post-trained using Tulu 3.1. OLMo 2 32B is the first fully-open model (all data, code, weights, and details are freely available) to outperform GPT3.5-Turbo and GPT-4o mini on a suite of popular, multi-skill academic benchmarks.
Ai2 [ https://substack.com/redirect/f979f89f-288c-4b62-9007-cc7f99ec95d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-03-13 Xata Agent [ https://substack.com/redirect/d7fa7856-604a-4f17-be47-a1e485886c6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Xata are a hosted PostgreSQL company who also develop the open source pgroll [ https://substack.com/redirect/40009b0d-74b8-4087-a34c-b89ca8ccaeb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and pgstream [ https://substack.com/redirect/c13804cb-68f2-4cc7-a2cd-afb8f02b7519?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]schema migration tools.
Their new "Agent" tool is a system that helps monitor and optimize a PostgreSQL server using prompts to LLMs.
Any time I see a new tool like this I go hunting for the prompts. It looks like the main system prompts for orchestrating the tool live here [ https://substack.com/redirect/4a0e5014-dbed-48d5-b1b2-f77ab69c6597?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - here's a sample:
Provide clear, concise, and accurate responses to questions. Use the provided tools to get context from the PostgreSQL database to answer questions. When asked why a query is slow, call the explainQuery tool and also take into account the table sizes. During the initial assessment use the getTablesAndInstanceInfo, getPerfromanceAndVacuumSettings, and getPostgresExtensions tools. When asked to run a playbook, use the getPlaybook tool to get the playbook contents. Then use the contents of the playbook as an action plan. Execute the plan step by step.
The really interesting thing is those playbooks, each of which is implemented as a prompt in the lib/tools/playbooks.ts [ https://substack.com/redirect/115d6483-069a-4aca-a4ab-0b2a9ca68a5d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] file. There are six of these so far:
SLOW_QUERIES_PLAYBOOK
GENERAL_MONITORING_PLAYBOOK
TUNING_PLAYBOOK
INVESTIGATE_HIGH_CPU_USAGE_PLAYBOOK
INVESTIGATE_HIGH_CONNECTION_COUNT_PLAYBOOK
INVESTIGATE_LOW_MEMORY_PLAYBOOK
Here's the full text of INVESTIGATE_LOW_MEMORY_PLAYBOOK:
Objective:
To investigate and resolve low freeable memory in the PostgreSQL database.

Step 1:
Get the freeable memory metric using the tool getInstanceMetric.

Step 3:
Get the instance details and compare the freeable memory with the amount of memory available.

Step 4:
Check the logs for any indications of memory pressure or out of memory errors. If there are, make sure to report that to the user. Also this would mean that the situation is critical.

Step 4:
Check active queries. Use the tool getConnectionsGroups to get the currently active queries. If a user or application stands out for doing a lot of work, record that to indicate to the user.

Step 5:
Check the work_mem setting and shared_buffers setting. Think if it would make sense to reduce these in order to free up memory.

Step 6:
If there is no clear root cause for using memory, suggest to the user to scale up the Postgres instance. Recommend a particular instance class.
This is the first time I've seen prompts arranged in a "playbooks" pattern like this. What a weird and interesting way to write software!
Quote 2025-03-13
One of the most essential practices for maintaining the long-term quality of computer code is to write automated tests that ensure the program continues to act as expected, even when other people (including your future self) muck with it.
Evan Miller [ https://substack.com/redirect/c3a695c3-9d35-4b66-b465-5d5a99538319?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-03-14
[...] in 2013, I did not understand that the things I said had meaning. I hate talking about this because it makes me seem more important than I am, but it’s also important to acknowledge. I saw myself at the time as just Steve, some random guy. If I say something on the internet, it’s like I’m talking to a friend in real life, my words are just random words and I’m human and whatever. It is what it is.
But at that time in my life, that wasn’t actually the case. I was on the Rails team, I was speaking at conferences, and people were reading my blog and tweets. I was an “influencer,” for better or worse. But I hadn’t really internalized that change in my life yet. And so I didn’t really understand that if I criticized something, it was something thousands of people would see.
Steve Klabnik [ https://substack.com/redirect/02d69b22-f539-4698-b83c-6f30c6e0f679?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVGt3TkRRMU5qWXNJbWxoZENJNk1UYzBNVGt6TURRd09Dd2laWGh3SWpveE56Y3pORFkyTkRBNExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEucmVIUWhtY3VMWW00c3BHeFAwUllNa2psSXV1NFY3WG9LOC1lYm1VOFh3YyIsInAiOjE1OTA0NDU2NiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQxOTMwNDA4LCJleHAiOjE3NDQ1MjI0MDgsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.S2ac9-NzEmCSzPQIw6BEgqR-BgcJWI8MVnLiq9tGgoE?
