# VERDAD - tracking misinformation in radio broadcasts using Gemini 1.5

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-11-07T19:23:57.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/verdad-tracking-misinformation-in

In this newsletter:
VERDAD - tracking misinformation in radio broadcasts using Gemini 1.5
Generating documentation from tests using files-to-prompt and LLM
Datasette Public Office Hours
VERDAD - tracking misinformation in radio broadcasts using Gemini 1.5 [ https://substack.com/redirect/30239012-c067-4295-a74b-029401354234?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-11-07
I'm starting a new interview series called Project. The idea is to interview people who are building interesting data projects and talk about what they've built, how they built it, and what they learned along the way.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
The first episode is a conversation with Rajiv Sinclair from Public Data Works [ https://substack.com/redirect/2c1e8fa3-e3e5-4ed1-a9b4-acd10f355e34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about VERDAD [ https://substack.com/redirect/029cae75-6144-4575-84ba-f451e344ef5f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a brand new project in collaboration with journalist Martina Guzmán [ https://substack.com/redirect/61c2582e-2d80-4c7f-97e2-163a084a3096?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that aims to track misinformation in radio broadcasts around the USA.
VERDAD hits a whole bunch of my interests at once. It's a beautiful example of scrappy data journalism in action, and it attempts something that simply would not have been possible just a year ago by taking advantage of new LLM tools.
You can watch the half hour interview [ https://substack.com/redirect/e0cdc7d6-3db4-4dde-9a59-627069707027?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on YouTube. Read on for the shownotes and some highlights from our conversation.
The VERDAD project
VERDAD tracks radio broadcasts from 48 different talk radio radio stations across the USA, primarily in Spanish. Audio from these stations is archived as MP3s, transcribed and then analyzed to identify potential examples of political misinformation.
The result is "snippets" of audio accompanied by the trancript, an English translation, categories indicating the type of misinformation that may be present and an LLM-generated explanation of why that snippet was selected.
These are then presented in an interface for human reviewers, who can listen directly to the audio in question, update the categories and add their own comments as well.
VERDAD processes around a thousand hours of audio content a day - way more than any team of journalists or researchers could attempt to listen to manually.
The technology stack
VERDAD uses Prefect [ https://substack.com/redirect/e332894d-3229-4c15-a916-b010c4a82da7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a workflow orchestration system to run the different parts of their pipeline.
There are multiple stages, roughly as follows:
MP3 audio is recorded from radio station websites and stored in Cloudflare R2
An initial transcription is performed using the extremely inexpensive Gemini 1.5 Flash
That transcript is fed to the more powerful Gemini 1.5 Pro with a complex prompt to help identify potential misinformation snippets
Once identified, audio containing snippets is run through the more expensive Whisper model to generate timestamps for the snippets
Further prompts then generate things like English translations and summaries of the snippets
Developing the prompts
The prompts used by VERDAD are available in their GitHub repository [ https://substack.com/redirect/5ac84784-7744-499f-bd95-b160f2c3bd3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and they are fascinating.
Rajiv initially tried to get Gemini 1.5 Flash to do both the transcription and the misinformation detection, but found that asking that model to do two things at once frequently confused it.
Instead, he switched to a separate prompt running that transcript against Gemini 1.5 Pro. Here's that more complex prompt [ https://substack.com/redirect/43bd0f1e-72c3-4888-8ff6-6f5c15b59607?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it's 50KB is size and includes a whole bunch of interesting sections, including plenty of examples and a detailed JSON schema.
Here's just one of the sections aimed at identifying content about climate change:
4. Climate Change and Environmental Policies
Description:
Disinformation that denies or minimizes human impact on climate change, often to oppose environmental regulations. It may discredit scientific consensus and promote fossil fuel interests.
Common Narratives:
Labeling climate change as a "hoax".
Arguing that climate variations are natural cycles.
Claiming environmental policies harm the economy.
Cultural/Regional Variations:
Spanish-Speaking Communities:
Impact of climate policies on agricultural jobs.
Arabic-Speaking Communities:
Reliance on oil economies influencing perceptions.
Potential Legitimate Discussions:
Debates on balancing environmental protection with economic growth.
Discussions about energy independence.
Examples:
Spanish: "El 'cambio climático' es una mentira para controlarnos."
Arabic: "'تغير المناخ' كذبة للسيطرة علينا."
Rajiv iterated on these prompts over multiple months - they are the core of the VERDAD project. Here's an update from yesterday [ https://substack.com/redirect/ad6e7ee4-75ea-4bfa-b447-9adeddfa9d13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] informing the model of the US presidental election results so that it wouldn't flag claims of a candidate winning as false!
Rajiv used both Claude 3.5 Sonnet and OpenAI o1-preview to help develop the prompt itself. Here's his transcript [ https://substack.com/redirect/d7692795-2f98-4b28-a2ee-9ac1ecd0a2be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of a conversation with Claude used to iterate further on an existing prompt.
The human review process
The final component of VERDAD is the web application itself. Everyone knows that AI makes mistakes, a lot. Providing as much context as possible for human review is essential.
The Whisper transcripts provide accurate timestamps (Gemini is sadly unable to provide those on its own), which means the tool can provide the Spanish transcript, the English translation and a play button to listen to the audio at the moment of the captured snippet.
Want to learn more?
VERDAD is under active development right now. Rajiv and his team are keen to collaborate, and are actively looking forward to conversations with other people working in this space. You can reach him at help@verdad.app.
The technology stack itself is incredibly promising. Pulling together a project like this even a year ago would have been prohibitively expensive, but new multi-modal LLM tools like Gemini (and Gemini 1.5 Flash in particular) are opening up all sorts of new possibilities.
Link 2024-11-07 Datasette Public Office Hours, Friday Nov 8th at 2pm PT [ https://substack.com/redirect/4e85facf-285a-4f7a-a893-7c917a58f837?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Tomorrow afternoon (Friday 8th November) at 2pm PT we'll be hosting the first Datasette Public Office Hours - a livestream video session on Discord where Alex Garcia and myself will live code on some Datasette [ https://substack.com/redirect/f1d997b9-59b6-496a-8f9c-2698424c8607?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] projects and hang out to chat about the project.
This is our first time trying this format. If it works out well I plan to turn it into a series.
Link 2024-11-05 Generating documentation from tests using files-to-prompt and LLM [ https://substack.com/redirect/fdb70b53-e62f-4e53-becf-7a18608db41c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I was experimenting with the wasmtime-py [ https://substack.com/redirect/47c05a3b-6c82-4ac0-ba2e-5ac8a1fc18a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Python library today (for executing WebAssembly programs from inside CPython) and I found the existing API docs [ https://substack.com/redirect/51ed2e64-9a7b-43b7-a693-bf2f3cef3081?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] didn't quite show me what I wanted to know.
The project has a comprehensive test suite [ https://substack.com/redirect/cf7bcf10-aaab-4988-8f72-696355573280?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] so I tried seeing if I could generate documentation using that:
cd /tmp
git clone https://github.com/bytecodealliance/wasmtime-py
files-to-prompt -e py wasmtime-py/tests -c | \
llm -m claude-3.5-sonnet -s \
'write detailed usage documentation including realistic examples'
More notes in my TIL [ https://substack.com/redirect/fdb70b53-e62f-4e53-becf-7a18608db41c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can see the full Claude transcript here [ https://substack.com/redirect/5f65e136-1d67-4053-b28b-57c55afb96dc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - I think this worked really well!
TIL 2024-11-06 Running cog automatically against GitHub pull requests [ https://substack.com/redirect/35e5a57f-2aac-4f1f-9dcc-95188cd01b75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I really like Cog [ https://substack.com/redirect/a8920d5b-1d4b-4382-b445-5326878bcde2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (previously [ https://substack.com/redirect/883d89b3-e226-4587-abdb-17e8c27a8a9a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) as a tool for automating aspects of my Python project documentation - things like the SQL schemas shown on the LLM logging page [ https://substack.com/redirect/0ba577ca-07eb-450e-b339-b3b20f74eb1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. …
Link 2024-11-06 yet-another-applied-llm-benchmark [ https://substack.com/redirect/3263709d-06e9-43f6-a81b-691669cec83d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Nicholas Carlini introduced this personal LLM benchmark suite back in February [ https://substack.com/redirect/e89e8113-065d-46c5-a6ac-d934085a506d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a collection of over 100 automated tests he runs against new LLM models to evaluate their performance against the kinds of tasks he uses them for [ https://substack.com/redirect/3c30c720-6be5-43cb-911e-83115b9af0c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
There are two defining features of this benchmark that make it interesting. Most importantly, I've implemented a simple dataflow domain specific language to make it easy for me (or anyone else!) to add new tests that realistically evaluate model capabilities. This DSL allows for specifying both how the question should be asked and also how the answer should be evaluated. [...] And then, directly as a result of this, I've written nearly 100 tests for different situations I've actually encountered when working with LLMs as assistants
The DSL he's using is fascinating. Here's an example:
"Write a C program that draws an american flag to stdout." >> LLMRun >> CRun >> \
VisionLLMRun("What flag is shown in this image?") >> \
(SubstringEvaluator("United States") | SubstringEvaluator("USA")))

This triggers an LLM to execute the prompt asking for a C program that renders an American Flag, runs that through a C compiler and interpreter (executed in a Docker container), then passes the output of that to a vision model to guess the flag and checks that it returns a string containing "United States" or "USA".
The DSL itself is implemented entirely in Python [ https://substack.com/redirect/89e4ff85-1e67-46e5-b862-606375231de6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], using the __rshift__ magic method for >> and __rrshift__ to enable strings to be piped into a custom object using "command to run" >> LLMRunNode.
Quote 2024-11-07
If you have worked in search, you know how freaking hard even getting started with something close to this with traditional methods. Now, you can zero-shot it.
> System Instructions: As a query categorization expert, you try to break down the intent of a search query. First, provide your reasoning and then describe the intent using a single category (broad, detailed, comparision)
>
> User: The query from the user is "nike versus adidas for terrain running". The user is a female, age 22.
>
> Model: The user is clearly looking to compare two specific brands, Nike and Adidas, for a particular activity, terrain running. While the user's demographics might be helpful in some situations (e.g., recommending specific product lines), the core intent remains a comparison. Category: Comparison
There's a lot of hand-waving around query intent classification; it's always been like that. Now, it's straightforward (add a few examples to improve accuracy). But my point is that you could only dream about building something like this without having access to lots of interaction data.
Jo Kristian Bergum [ https://substack.com/redirect/1fe2c6a6-b800-4bee-adea-01a5d7e63a35?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEV6TkRFM05UQXNJbWxoZENJNk1UY3pNVEF3TnpRMU5Dd2laWGh3SWpveE56WXlOVFF6TkRVMExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEucldYSHo2bllNSWk2LUVYNERZcDAzX2F1RmVEVkF4cWJ0Z1VvUHhaS3BkTSIsInAiOjE1MTM0MTc1MCwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzMxMDA3NDU0LCJleHAiOjE3MzM1OTk0NTQsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.h0Es0Hizi1jDP9I4n8z4eeJfmJJHZ8t3NM689akWZ1Y?
