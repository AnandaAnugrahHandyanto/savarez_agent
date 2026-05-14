# Building search-based RAG using Claude 3.5 Sonnet, Datasette and Val Town

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-06-24T05:33:36.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/building-search-based-rag-using-claude

In this newsletter:
Building search-based RAG using Claude, Datasette and Val Town
Plus 8 links and 7 quotations and 1 TIL
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Building search-based RAG using Claude, Datasette and Val Town [ https://substack.com/redirect/1f8ce2f3-8b36-4199-87c6-f9ddc90a955f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-06-21
Retrieval Augmented Generation (RAG) is a technique for adding extra "knowledge" to systems built on LLMs, allowing them to answer questions against custom information not included in their training data. A common way to implement this is to take a question from a user, translate that into a set of search queries, run those against a search engine and then feed the results back into the LLM to generate an answer.
I built a basic version of this pattern against the brand new Claude 3.5 Sonnet [ https://substack.com/redirect/bca1517f-f43d-40b7-b841-8963c47aa1ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] language model, using SQLite full-text search [ https://substack.com/redirect/d328b9f5-4bea-465f-b9fa-4e764156e1eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] running in Datasette [ https://substack.com/redirect/cb33a8c5-7093-4751-afd9-79264b61b5d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as the search backend and Val Town [ https://substack.com/redirect/a2323c78-afd4-464b-beb8-0075f5e69285?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]as the prototyping platform.
The implementation took just over an hour, during a live coding session with Val.Town founder Steve Krouse. I was the latest guest on Steve's live streaming series [ https://substack.com/redirect/f1b82bf5-7146-441d-8290-b1b994f6e28d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where he invites people to hack on projects with his help.
You can watch the video below or on YouTube [ https://substack.com/redirect/45aff02a-d71f-4460-b3a9-7c9b12716922?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here are my own detailed notes to accompany the session.
Bonus: Claude 3.5 Sonnet artifacts demo
We started the stream by chatting a bit about the new Claude 3.5 Sonnet release. This turned into an unplanned demo of their "artifacts" feature where Claude can now build you an interactive web page on-demand.
At 3m02s [ https://substack.com/redirect/efe65015-bec3-4d0d-b924-0e031b3c417e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I prompted it with:
Build me a web app that teaches me about mandelbrot fractals, with interactive widgets
This worked! Here's the code it wrote [ https://substack.com/redirect/3a7551b6-81a0-4e23-a023-750e33ab3732?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - I haven't yet found a good path for turning that into a self-hosted interactive page yet.
This didn't support panning, so I added:
Again but let me drag on the canvas element to pan around
Which gave me this [ https://substack.com/redirect/a2796463-8931-4b12-95dd-d51d59817d40?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Pretty impressive!
Ingredients for the RAG project
RAG is often implemented using vector search against embeddings [ https://substack.com/redirect/ffe44181-0357-4c26-9656-78759ff3cfc4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but there's an alternative approach where you turn the user's question into some full-text search queries, run those against a traditional search engine, then feed the results back into an LLM and ask it to use them to answer the question.
SQLite includes surprisingly good full-text search [ https://substack.com/redirect/d328b9f5-4bea-465f-b9fa-4e764156e1eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and I've built a lot of tools against that in the past - including sqlite-utils enable-fts [ https://substack.com/redirect/cef14416-082b-4953-a6a1-9f96b0b61f6f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Datasette's FTS features [ https://substack.com/redirect/0466ef4b-08c9-4b50-97c8-63eb76524a34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
My blog has a lot of content, which lives in a Django PostgreSQL database. But I also have a GitHub Actions repository which backs up that data [ https://substack.com/redirect/bf4cf9e7-4fe6-4c1f-9533-b5036604c276?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as JSON, and then publishes a SQLite copy of it to datasette.simonwillison.net [ https://substack.com/redirect/b637a6f5-b348-41e6-a365-bad610da776c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - which means I have a Datasette-powered JSON API for running searches against my content.
Let's use that API to build a question answering RAG system!
Step one then was to prototype up a SQL query we could use with that API to get back search results. After some iteration I got to this:
select
blog_entry.id,
blog_entry.title,
blog_entry.body,
blog_entry.created
from
blog_entry
join blog_entry_fts on blog_entry_fts.rowid = blog_entry.rowid
where
blog_entry_fts match :search
order by
rank
limit
10
Try that here [ https://substack.com/redirect/0acbbe49-2cc4-4c11-9f73-f75ffb2e2437?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The query works by joining the blog_entry table to the SQLite FTS blog_entry_fts virtual table, matched against the ?search= parameter from the URL.
When you join against a FTS table like this a rank column is exposed with the relevance score for each match.
Adding .json to the above URL turns it into an API call... so now we have a search API we can call from other code.
A plan for the build
We spent the rest of the session writing code in Val Town, which offers a browser editor for a server-side Deno-based environment for executing JavaScript (and TypeScript) code.
The finished code does the following:
Accepts a user's question from the ?question= query string.
Asks Claude 3.5 Sonnet to turn that question into multiple single-word search queries, using a Claude function call to enforce a schema of a JSON list of strings.
Turns that list of keywords into a SQLite FTS query that looks like this: "shot-scraper" OR "screenshot" OR "web" OR "tool" OR "automation" OR "CLI"
Runs that query against Datasette to get back the top 10 results.
Combines the title and body from each of those results into a longer context.
Calls Claude 3 again (originally Haiku, but then we upgraded to 3.5 Sonnet towards the end) with that context and ask it to answer the question.
Return the results to the user.
The annotated final script
Here's the final script we ended up with, with inline commentary. Here's the initial setup:
import Anthropic from "npm:@anthropic-ai/sdk@0.24.0";

/* This automatically picks up the API key from the ANTHROPIC_API_KEY
environment variable, which we configured in the Val Town settings */
const anthropic = new Anthropic;
We're using the very latest release of the Anthropic TypeScript SDK [ https://substack.com/redirect/3d6f84ce-544f-405d-8423-45b64bd83184?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which came out just a few hours prior [ https://substack.com/redirect/61b2e59a-19e8-4ffa-bfa3-cc03d13bc63f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to recording the livestream.
I set the ANTHROPIC_API_KEY environment variable to my Claude 3 API key in the Val Town settings, making it available to all of my Vals. The Anthropic constructor picks that up automatically.
Next, the function to suggest keywords for a user's question:
async function suggestKeywords(question) {
// Takes a question like "What is shot-scraper?" and asks 3.5 Sonnet
// to suggest individual search keywords to help answer the question.
const message = await anthropic.messages.create({
max_tokens: 128,
model: "claude-3-5-sonnet-20240620",
// The tools option enforces a JSON schema array of strings
tools: [{
name: "suggested_search_keywords",
description: "Suggest individual search keywords to help answer the question.",
input_schema: {
type: "object",
properties: {
keywords: {
type: "array",
items: {
type: "string",
},
description: "List of suggested single word search keywords",
},
},
required: ["keywords"],
},
}],
// This forces it to always run the suggested_search_keywords tool
tool_choice: { type: "tool", name: "suggested_search_keywords" },
messages: [
{ role: "user", content: question },
],
});
// This helped TypeScript complain less about accessing .input.keywords
// since it knows this object can be one of two different types
if (message.content[0].type == "text") {
throw new Error(message.content[0].text);
}
return message.content[0].input.keywords;
}
We're asking Claude 3.5 Sonnet here to suggest individual search keywords to help answer that question. I tried Claude 3 Haiku first but it didn't reliably return single word keywords - Sonnet 3.5 followed the "single word search keywords" instruction better.
This function also uses Claude tools to enforce a response in a JSON schema that specifies an array of strings. More on how I wrote that code (with Claude's assistance) later on.
Next, the code to run the search itself against Datasette:
// The SQL query from earlier
const sql = `select
blog_entry.id,
blog_entry.title,
blog_entry.body,
blog_entry.created
from
blog_entry
join blog_entry_fts on blog_entry_fts.rowid = blog_entry.rowid
where
blog_entry_fts match :search
order by
rank
limit
10`;

async function runSearch(keywords) {
// Turn the keywords into "word1" OR "word2" OR "word3"
const search = keywords.map(s => `"${s}"`).join(" OR ");
// Compose the JSON API URL to run the query
const params = new URLSearchParams({
search,
sql,
_shape: "array",
});
const url = "https://datasette.simonwillison.net/simonwillisonblog.json?" + params;
const result = await (await fetch(url)).json;
return result;
}
Datasette supports read-only SQL queries via its JSON API, which means we can construct the SQL query as a JavaScript string and then encode it as a query string using URLSearchParams.
We also take the list of keywords and turn them into a SQLite FTS search query that looks like "word1" OR "word2" OR "word3".
SQLite's built-in relevance calculations work well with this - you can throw in dozens of words separated by OR and the top ranking results will generally be the ones with the most matches.
Finally, the code that ties this together - suggests keywords, runs the search and then asks Claude to answer the question. I ended up bundling that together in the HTTP handler for the Val Town script - this is the code that is called for every incoming HTTP request:
export default async function(req: Request) {
// This is the Val Town HTTP handler
const url = new URL(req.url);
const question = url.searchParams.get("question").slice(0, 40);
if (!question) {
return Response.json({ "error": "No question provided" });
}
// Turn the question into search terms
const keywords = await suggestKeywords(question);

// Run the actual search
const result = await runSearch(keywords);

// Strip HTML tags from each body property, modify in-place:
result.forEach(r => {
r.body = r.body.replace(/]*>/g, "");
});

// Glue together a string of the title and body properties in one go
const context = result.map(r => r.title + " " + r.body).join("\n\n");

// Ask Claude to answer the question
const message = await anthropic.messages.create({
max_tokens: 1024,
model: "claude-3-haiku-20240307",
messages: [
{ role: "user", content: context },
{ role: "assistant", content: "Thank you for the context, I am ready to answer your question" },
{ role: "user", content: question },
],
});
return Response.json({answer: message.content[0].text});
}
There are many other ways you could arrange the prompting here. I quite enjoy throwing together a fake conversation like this that feeds in the context and then hints at the agent that it should respond next with its answer, but there are many potential variations on this theme.
This initial version returned the answer as a JSON object, something like this:
{
"answer": "shot-scraper is a command-line tool that automates the process of taking screenshots of web pages..."
}
We were running out of time, but we wanted to add an HTML interface. Steve suggested getting Claude to write the whole thing! So we tried this:
const message = await anthropic.messages.create({
max_tokens: 1024,
model: "claude-3-5-sonnet-20240620", // "claude-3-haiku-20240307",
system: "Return a full HTML document as your answer, no markdown, make it pretty with exciting relevant CSS",
messages: [
{ role: "user", content: context },
{ role: "assistant", content: "Thank you for the context, I am ready to answer your question as HTML" },
{ role: "user", content: question },
],
});
// Return back whatever HTML Claude gave us
return new Response(message.content[0].text, {
status: 200,
headers: { "Content-Type": "text/html" }
});
We upgraded to 3.5 Sonnet to see if it had better "taste" than Haiku, and the results were really impressive. Here's what it gave us for "What is Datasette?":
It even styled the page with flexbox to arrange the key features of Datasette in a 2x2 grid! You can see that in the video at 1h13m17s [ https://substack.com/redirect/ba0d5e7c-3238-4e28-b56e-916cb4d9b75f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
There's a full copy of the final TypeScript code [ https://substack.com/redirect/4e7955ef-4114-4c9d-9c79-c0d8a9e390ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]available in a Gist.
Some tricks we used along the way
I didn't write all of the above code. Some bits of it were written by pasting things into Claude 3.5 Sonnet, and others used the Codeium [ https://substack.com/redirect/638b0227-6ef7-4642-8e3c-726c2527973a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]integration in the Val Town editor (described here [ https://substack.com/redirect/29020560-e9a2-4a8d-a2db-42f21887db4d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
One pattern that worked particularly well was getting Sonnet to write the tool-using TypeScript code for us.
The Claude 3 documentation showed how to do that using curl [ https://substack.com/redirect/7435644b-af7d-4da2-b932-6296d29c0e1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I pasted that curl example in, added some example TypeScript and then prompted:
Guess the JavaScript for setting up a tool which just returns a list of strings, called suggested_search_keywords
Here's my full prompt:
#!/bin/bash
IMAGE_URL="https://upload.wikimedia.org/wikipedia/commons/a/a7/Camponotus_flavomarginatus_ant.jpg"
IMAGE_MEDIA_TYPE="image/jpeg"
IMAGE_BASE64=$(curl "$IMAGE_URL" | base64)
curl https://api.anthropic.com/v1/messages \
--header "content-type: application/json" \
--header "x-api-key: $ANTHROPIC_API_KEY" \
--header "anthropic-version: 2023-06-01" \
--data \
'{
"model": "claude-3-sonnet-20240229",
"max_tokens": 1024,
"tools": [{
"name": "record_summary",
"description": "Record summary of an image using well-structured JSON.",
"input_schema": {
"type": "object",
"properties": {
"key_colors": {
"type": "array",
"items": {
"type": "object",
"properties": {
"r": { "type": "number", "description": "red value [0.0, 1.0]" },
"g": { "type": "number", "description": "green value [0.0, 1.0]" },
"b": { "type": "number", "description": "blue value [0.0, 1.0]" },
"name": { "type": "string", "description": "Human-readable color name in snake_case, e.g. \"olive_green\" or \"turquoise\"" }
},
"required": [ "r", "g", "b", "name" ]
},
"description": "Key colors in the image. Limit to less then four."
},
"description": {
"type": "string",
"description": "Image description. One to two sentences max."
},
"estimated_year": {
"type": "integer",
"description": "Estimated year that the images was taken, if is it a photo. Only set this if the image appears to be non-fictional. Rough estimates are okay!"
}
},
"required": [ "key_colors", "description" ]
}
}],
"tool_choice": {"type": "tool", "name": "record_summary"},
"messages": [
{"role": "user", "content": [
{"type": "image", "source": {
"type": "base64",
"media_type": "'$IMAGE_MEDIA_TYPE'",
"data": "'$IMAGE_BASE64'"
}},
{"type": "text", "text": "Describe this image."}
]}
]
}'

Based on that example and this JavaScript code:

const anthropic = new Anthropic;
const message = await anthropic.messages.create({
max_tokens: 1024,
system: "Suggest individual search keywords to help answer this question. No yapping.",
messages: [
{ role: "user", content: question },
],
model: "claude-3-haiku-20240307",
});
console.log(message.content[0].text);

Guess the JavaScript for setting up a tool which just returns a list of strings, called suggested_search_keywords

It gave me back this, which was the exact code I needed to make my tool-enabled API call from Val Town:
const anthropic = new Anthropic;
const message = await anthropic.messages.create({
max_tokens: 1024,
model: "claude-3-haiku-20240307",
tools: [{
name: "suggested_search_keywords",
description: "Suggest individual search keywords to help answer the question.",
input_schema: {
type: "object",
properties: {
keywords: {
type: "array",
items: {
type: "string"
},
description: "List of suggested search keywords"
}
},
required: ["keywords"]
}
}],
tool_choice: { type: "tool", name: "suggested_search_keywords" },
messages: [
{ role: "user", content: question }
]
});

console.log(message.content[0].text);
I really like this trick, and I use it often in my own work. Find some example code that illustrates the pattern you need, paste in some additional context and get the LLM to figure the rest out for you.
This is just a prototype
It's important to reiterate that this is just a prototype - it's the version of search-backed RAG I could get working in an hour.
Putting something like this into production requires a whole lot more work. Most importantly, good RAG systems are backed by evals - it's extremely hard to iterate on and improve a system like this if you don't have a good mechanism in place to evaluate if your changes are making things better or not. Your AI Product Needs Evals [ https://substack.com/redirect/45c36fc9-c9f7-4798-98e6-53e47b54e4f6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Hamel Husain remains my favourite piece of writing on how to go about putting these together.
Additional links from the livestream
Here are some of the other projects and links mentioned during our conversation:
Datasette [ https://substack.com/redirect/cb33a8c5-7093-4751-afd9-79264b61b5d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and its 150+ plugins [ https://substack.com/redirect/48ba6591-fe6f-432b-817c-099db9f05b3a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
My original idea for a project was to use the Datasette Write API [ https://substack.com/redirect/0e6d29d0-bae9-44d7-ba06-72b71be32a0d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and run scheduled Vals to import data from various sources (my toots, tweets, posts etc) into a single searchable table.
LLM [ https://substack.com/redirect/5ad5288c-3a49-46eb-997e-2bdb60e2735a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - my command-line utility for working with different language models.
shot-scraper [ https://substack.com/redirect/17d244b3-952b-42f4-83e6-0100c980476c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for automating screenshots and scraping websites with JavaScript from the command-line - here's a recent demo [ https://substack.com/redirect/c3bd6b47-a1de-4b8c-aea4-7f1d9f900ad5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where I scraped Google using shot-scraper and fed the results into LLM as a basic form of RAG.
My current list of 277 projects with at least one release [ https://substack.com/redirect/6d0d7d86-b8b7-4b4a-ae57-492434e89688?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on GitHub.
My TIL blog [ https://substack.com/redirect/26039bd0-4bff-41c3-bec4-23825a4ef176?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which runs on a templated version of Datasette - here's the database [ https://substack.com/redirect/98f461ca-a80a-40d5-92d4-8727e8b1509e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]and here's the GitHub Actions workflow that builds it [ https://substack.com/redirect/99843e8a-a0f2-46e5-865a-86c1246abc58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using the Baked Data pattern [ https://substack.com/redirect/6e2c9c6c-5dd2-48e5-8b06-83ef92d7cfa8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I have some previous experiments using embeddings with Datasette, including a table of embeddings [ https://substack.com/redirect/45845ead-c09c-4f49-9c8a-eadb1f9b4b3c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (encoded like this [ https://substack.com/redirect/12b890f8-33fe-4e9c-a1a1-164ddb6def1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) for my TIL blog which I use to power related items. That's described in this TIL: Storing and serving related documents with openai-to-sqlite and embeddings [ https://substack.com/redirect/d4616ba4-bed1-478c-abaf-8ea1348b43e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-06-19 Civic Band [ https://substack.com/redirect/a478b375-0cbf-4b34-86b3-821fb24085c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Exciting new civic tech project from Philip James: 30 (and counting) Datasette instances serving full-text search enabled collections of OCRd meeting minutes for different civic governments. Includes 20,000 pages for Alameda [ https://substack.com/redirect/c61ddb3e-5da7-434b-8095-7d6fa0555fad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], 17,000 for Pittsburgh [ https://substack.com/redirect/28efeee3-44ab-4058-8b75-0e40d9567f5e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], 3,567 for Baltimore [ https://substack.com/redirect/002b01af-c308-4dbf-bdc9-f536614b14e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and an enormous 117,000 for Maui County [ https://substack.com/redirect/a111da65-a48c-4a8a-82bc-07db679a3597?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Philip includes some notes [ https://substack.com/redirect/d4bbbed3-1ccf-45da-a07f-aa46c17d458a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on how they're doing it. They gather PDF minute notes from anywhere that provides API access to them, then run local Tesseract for OCR (the cost of cloud-based OCR proving prohibitive given the volume of data). The collection is then deployed to a single VPS running multiple instances of Datasette via Caddy, one instance for each of the covered regions.
TIL 2024-06-20 Running Prettier against Django or Jinja templates [ https://substack.com/redirect/5f8cc6b9-300f-4b44-acdd-253cab68b966?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I really like auto-formatting tools like Black. I've been hoping to find one that works with Django and Jinja templates for years. …
Link 2024-06-20 State-of-the-art music scanning by Soundslice [ https://substack.com/redirect/95cc618e-0a4e-4875-94b5-7c396e5973e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It's been a while since I checked in on Soundslice [ https://substack.com/redirect/ddd421e6-2907-480e-94ec-98b6002d3b6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Adrian Holovaty's beautiful web application focused on music education.
The latest feature is spectacular. The Soundslice music editor - already one of the most impressive web applications I've ever experienced - can now import notation directly from scans or photos of sheet music.
The attention to detail is immaculate. The custom machine learning model can handle a wide variety of notation details, and the system asks the user to verify or correct details that it couldn't perfectly determine using a neatly designed flow.
Free accounts can scan two single page documents a month, and paid plans get a much higher allowance. I tried it out just now on a low resolution image I found on Wikipedia and it did a fantastic job, even allowing me to listen to a simulated piano rendition of the music once it had finished processing.
It's worth spending some time with the release notes [ https://substack.com/redirect/aa4cb48e-64e1-4fa3-999a-ce384d1898c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the feature to appreciate how much work they've out into improving it since the initial release.
If you're new to Soundslice, here's an example [ https://substack.com/redirect/58233d96-3825-4562-93ef-233aae5ce69d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of their core player interface which syncs the display of music notation to an accompanying video.
Adrian wrote up some detailed notes [ https://substack.com/redirect/f8927da8-6239-466c-b975-094c87b14abd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on the machine learning behind the feature when they first launched it in beta back in November 2022.
OMR [Optical Music Recognition] is an inherently hard problem, significantly more difficult than text OCR. For one, music symbols have complex spatial relationships, and mistakes have a tendency to cascade. A single misdetected key signature might result in multiple incorrect note pitches. And there’s a wide diversity of symbols, each with its own behavior and semantics — meaning the problems and subproblems aren’t just hard, there are many of them.
Quote 2024-06-20
[...] And then some absolute son of a bitch created ChatGPT, and now look at us. Look at us, resplendent in our pauper's robes, stitched from corpulent greed and breathless credulity, spending half of the planet's engineering efforts to add chatbot support to every application under the sun when half of the industry hasn't worked out how to test database backups regularly.
Nikhil Suresh [ https://substack.com/redirect/9caaf3f6-2221-4e67-8f09-a498ee7d8f60?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-20 Claude 3.5 Sonnet [ https://substack.com/redirect/c196c558-799d-41e0-a4d8-fb78ee6963d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic released a new model this morning, and I think it's likely now the single best available LLM. Claude 3 Opus was already mostly on-par with GPT-4o, and the new 3.5 Sonnet scores higher than Opus on almost all of Anthropic's internal evals.
It's also twice the speed and one fifth of the price of Opus (it's the same price as the previous Claude 3 Sonnet). To compare:
gpt-4o: $5/million input tokens and $15/million output
Claude 3.5 Sonnet: $3/million input, $15/million output
Claude 3 Opus: $15/million input, $75/million output
Similar to Claude 3 Haiku then, which both under-cuts and out-performs [ https://substack.com/redirect/1e9019b1-33de-45fc-a1e2-2a12a3dff075?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] OpenAI's GPT-3.5 model.
In addition to the new model, Anthropic also added a "artifacts" feature to their Claude web interface. The most exciting part of this is that any of the Claude models can now build and then render web pages and SPAs, directly in the Claude interface.
This means you can prompt them to e.g. "Build me a web app that teaches me about mandelbrot fractals, with interactive widgets" and they'll do exactly that - I tried that prompt on Claude 3.5 Sonnet earlier and the results were spectacular [ https://substack.com/redirect/318ed4fe-395d-4446-86ab-cfd3c7c2272d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (video demo).
An unsurprising note at the end of the post:
To complete the Claude 3.5 model family, we’ll be releasing Claude 3.5 Haiku and Claude 3.5 Opus later this year.
If the pricing stays consistent with Claude 3, Claude 3.5 Haiku is going to be a very exciting model indeed.
Quote 2024-06-20
One of the core constitutional principles that guides our AI model development is privacy. We do not train our generative models on user-submitted data unless a user gives us explicit permission to do so. To date we have not used any customer or user-submitted data to train our generative models.
Anthropic [ https://substack.com/redirect/c196c558-799d-41e0-a4d8-fb78ee6963d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-20 llm-claude-3 0.4 [ https://substack.com/redirect/d2d034a6-98c4-405e-9f50-2accda5814d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
LLM plugin release adding support for the new Claude 3.5 Sonnet model:
pipx install llm
llm install -U llm-claude-3
llm keys set claude
# paste AP| key here
llm -m claude-3.5-sonnet \
'a joke about a pelican and a walrus having lunch'

Quote 2024-06-21
It is in the public good to have AI produce quality and credible (if ‘hallucinations’ can be overcome) output. It is in the public good that there be the creation of original quality, credible, and artistic content. It is not in the public good if quality, credible content is excluded from AI training and output OR if quality, credible content is not created.
Jeff Jarvis [ https://substack.com/redirect/08069477-bde8-42eb-ba9e-843a4568c5aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-21 Val Vibes: Semantic search in Val Town [ https://substack.com/redirect/92a8b9c6-0b7c-4661-9e9c-fbb45426296e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A neat case-study by JP Posma on how Val Town's developers can use Val Town Vals to build prototypes of new features that later make it into Val Town core.
This one explores building out semantic search [ https://substack.com/redirect/9456ccbb-b03d-41c9-8c14-142ebae3161e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]against Vals using OpenAI embeddings and the PostgreSQL pgvector extension.
Quote 2024-06-21
OpenAI was founded to build artificial general intelligence safely, free of outside commercial pressures. And now every once in a while it shoots out a new AI firm whose mission is to build artificial general intelligence safely, free of the commercial pressures at OpenAI.
Matt Levine [ https://substack.com/redirect/082755dd-f866-4e5c-9449-f39621915a91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-21 Datasette 0.64.8 [ https://substack.com/redirect/7ce96528-40b0-4e65-b670-660e4eb1a8bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A very small Datasette release, fixinga minor potential security issue [ https://substack.com/redirect/df4af83b-d83c-4320-b09c-de002760d0b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]where the name of missing databases or tables was reflected on the 404 page in a way that could allow an attacker to present arbitrary text to a user who followed a link. Not an XSS attack (no code could be executed) but still a potential vector for confusing messages.
Link 2024-06-22 Wikipedia Manual of Style: Linking [ https://substack.com/redirect/fc95e964-44fc-4eec-b3fb-d15404f7900a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I started a conversation on Mastodon [ https://substack.com/redirect/efff38bc-e348-439e-b3da-d2d60987820e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about the grammar of linking: how to decide where in a phrase an inline link should be placed.
Lots of great (and varied) replies there. The most comprehensive style guide I've seen so far is this one from Wikipedia, via Tom Morris.
Quote 2024-06-22
In our “who validates the validators” user studies, we found that people expected—and also desired—for the LLM to learn from *any* human interaction. That too, “as efficiently as possible” (ie after 1-2 demonstrations, the LLM should “get it”)
Shreya Shankar [ https://substack.com/redirect/e907010a-d5f6-4c9b-bfda-1f1517ee9a7a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-06-23
The people who are most confident AI can replace writers are the ones who think writing is typing.
Andrew Ti [ https://substack.com/redirect/0be5eac6-5a5e-4057-b387-c775048ce3c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-06-23 llama.ttf [ https://substack.com/redirect/bca6995f-b895-4c69-8cad-80f23cb6c5a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llama.ttf is "a font file which is also a large language model and an inference engine for that model".
You can see it kick into action at 8m28s in this video [ https://substack.com/redirect/c9d09890-a7c2-4e71-969f-12bfd657733e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], where creator Søren Fuglede Jørgensen types "Once upon a time" followed by dozens of exclamation marks, and those exclamation marks then switch out to render a continuation of the story. But... when they paste the code out of the editor again it shows as the original exclamation marks were preserved - the LLM output was presented only in the way they were rendered.
The key trick here is that the font renderer library HarfBuzz [ https://substack.com/redirect/217a40b3-5d87-466d-b138-39cafb13572b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (used by Firefox, Chrome, Android, GNOME and more) added a new WebAssembly extension [ https://substack.com/redirect/5dc7e61a-7096-4ac4-a85e-6682945cfc07?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in version 8.0 last year [ https://substack.com/redirect/077dec23-2ac4-4847-ad28-b22f0a965578?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which is powerful enough to run a full LLM based on the tinyllama-15M [ https://substack.com/redirect/89569615-53d2-4253-91b7-e5aa4924a2b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] model - which fits in a 60MB font file.
(Here's a related demo from Valdemar Erk showing Tetris running in a WASM font, at 22m56s in this video [ https://substack.com/redirect/9c765ca1-c637-4830-877a-c0b82e3b7dcb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
The source code for llama.ttf is available on GitHub [ https://substack.com/redirect/b47c075a-a4fa-4451-97d6-aef0edf1e2c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2024-06-23
For some reason, many people still believe that browsers need to include non-standard hacks in HTML parsing to display the web correctly.
In reality, the HTML parsing spec is exhaustively detailed. If you implement it as described, you will have a web-compatible parser.
Andreas Kling [ https://substack.com/redirect/6e354d33-1f08-4915-b219-8d0aad3cf0ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORFU1TXpjMU1qWXNJbWxoZENJNk1UY3hPVEl3TnpJeU9Td2laWGh3SWpveE56VXdOelF6TWpJNUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuTnI5d1I0ejdpNU9VbkJYbTVwN2pMalFOVEkyLXJabkJNcWlJVlRUTnFaTSIsInAiOjE0NTkzNzUyNiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzE5MjA3MjI5LCJleHAiOjE3MjE3OTkyMjksImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.r5PFyVl6l2ErjbfvqoFGMTO7EUGD9Z-Ay7Fvr2b4Pxk?
