# Ask questions of SQLite databases and CSV/JSON files in your terminal

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-11-29T22:24:06.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/ask-questions-of-sqlite-databases

In this newsletter:
Ask questions of SQLite databases and CSV/JSON files in your terminal
Storing times for human events
Weeknotes: asynchronous LLMs, synchronous embeddings, and I kind of started a podcast
Plus 23 links and 8 quotations and 1 TIL
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Ask questions of SQLite databases and CSV/JSON files in your terminal [ https://substack.com/redirect/19b81bb0-d522-46cb-8ba6-734fc61890ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-11-25
I built a new plugin for my sqlite-utils CLI tool [ https://substack.com/redirect/b4ab18a4-09f2-4ade-ba0e-a7be6d73c4df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that lets you ask human-language questions directly of SQLite databases and CSV/JSON files on your computer.
It's called sqlite-utils-ask [ https://substack.com/redirect/5d8e3f25-7c5e-4006-937a-12b2f78f4326?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here's how you install it:
sqlite-utils install sqlite-utils-ask
It picks up API keys from an OPENAI_API_KEY environment variable, or you can install LLM [ https://substack.com/redirect/6e39c88c-eb3e-4998-8eb3-b57ac95d83b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and use llm keys set openai [ https://substack.com/redirect/aa49d371-3b07-4c32-b6e9-e98595cdae46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to store a key in a configuration file.
Then you can use it like this:
curl -O https://datasette.io/content.db
sqlite-utils ask content.db "how many sqlite-utils pypi downloads in 2024?"
This command will extract the SQL schema for the provided database file, send that through an LLM along with your question, get back a SQL query and attempt to run it to derive a result.
If all goes well it spits out an answer something like this:
SELECT SUM(downloads)
FROM stats
WHERE package = 'sqlite-utils' AND date >= '2024-01-01' AND date  tag without needing to involve some sort of convoluted build system.
Julia Evans shares my preference for build-free JavaScript, and has shared notes about figuring out how to turn an arbitrary NPM package into something that can be loaded in a browser.
It's so complicated! This is the best exploration I've seen yet of the topic but wow, this really needs to be easier.
My download-esm [ https://substack.com/redirect/b689552a-1020-4b75-9336-34ae6f49b8b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool gets a mention, but I have to admit I'm not 100% confident in that as a robust solution. I don't know nearly enough about the full scope of the problem here to confidently recommend my own tool!
Right now my ideal solution would turn almost anything from NPM into an ES module that I can self-host and then load using import ... from in a  block, maybe with an importmap as long as I don't have to think too hard about what to put in it.
I'm intrigued by esm.sh [ https://substack.com/redirect/4e1d82ae-7317-4b0d-80ff-fe45d58eb86e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (mentioned by Julia as a new solution worth exploring). The length of the documentation on that page further reinforces quite how much there is that I need to understand here.
Quote 2024-11-24
Whatever you think of capitalism, the evidence is overwhelming: Social networks with a single proprietor have trouble with long-term survival, and those do survive have trouble with user-experience quality: see Enshittification [ https://substack.com/redirect/bdc265f9-a99c-4006-9f60-b8d63c66fdd4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The evidence is also perfectly clear that it doesn’t have to be this way. The original social network, email, is now into its sixth decade of vigorous life. It ain’t perfect but it is essential, and not in any serious danger.
The single crucial difference between email and all those other networks — maybe the only significant difference — is that nobody owns or controls it.
Tim Bray [ https://substack.com/redirect/123c4771-5fa0-4a59-bb51-f6817c62df3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-24 Is async Django ready for prime time? [ https://substack.com/redirect/6da05e6f-4bb4-4f17-a087-dafe9540b885?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jonathan Adly reports on his experience using Django to build ColiVara [ https://substack.com/redirect/d43d1ceb-70c1-45af-b326-62b922372ea4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a hosted RAG API that uses ColQwen2 [ https://substack.com/redirect/cc668711-46f0-4011-a4fc-2f16f35225f7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] visual embeddings, inspired by the ColPali [ https://substack.com/redirect/ec3a9601-4aa4-4e66-acab-ea30e9214b05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] paper.
In a breach of Betteridge's law of headlines [ https://substack.com/redirect/77103bc6-2297-4b27-b5c7-2ca1b46af0d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the answer to the question posed by this headline is “yes”.
We believe async Django is ready for production. In theory, there should be no performance loss when using async Django instead of FastAPI for the same tasks.
The ColiVara application is itself open source, and you can see how it makes use of Django’s relatively new asynchronous ORM features [ https://substack.com/redirect/deced509-2930-475a-aacb-f47e25505236?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the api/views.py module [ https://substack.com/redirect/8d86ec42-f7eb-4273-879d-0d30edbeb511?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I also picked up a useful trick from their Dockerfile [ https://substack.com/redirect/84a02616-327e-4edf-bd54-f662376fc503?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: if you want uv in a container you can install it with this one-liner:
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

Link 2024-11-24 open-interpreter [ https://substack.com/redirect/17600272-60c1-4f3b-b530-fd5190458a95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This "natural language interface for computers" open source ChatGPT Code Interpreter alternative has been around for a while, but today I finally got around to trying it out.
Here's how I ran it (without first installing anything) using uv:
uvx --from open-interpreter interpreter

The default mode asks you for an OpenAI API key so it can use gpt-4o - there are a multitude of other options, including the ability to use local models with interpreter --local.
It runs in your terminal and works by generating Python code to help answer your questions, asking your permission to run it and then executing it directly on your computer.
I pasted in an API key and then prompted it with this:
find largest files on my desktop
Here's the full transcript [ https://substack.com/redirect/a4c6b659-2918-4e3c-9c08-1da0ff9c6db2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Since code is run directly on your machine there are all sorts of ways things could go wrong if you don't carefully review the generated code before hitting "y". The team have an experimental safe mode [ https://substack.com/redirect/84a2404c-fffa-4faf-8281-5b70a116caab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in development which works by scanning generated code with semgrep [ https://substack.com/redirect/9bee83bf-258d-4e19-b0a2-bb8e4a366da1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I'm not convinced by that approach, I think executing code in a sandbox would be a much more robust solution here - but sandboxing Python is still a very difficult problem.
They do at least have an experimental Docker integration [ https://substack.com/redirect/c3cfc7e4-3323-4727-97ac-a9991807eace?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-11-24 follow_theirs.py [ https://substack.com/redirect/eb8075e0-5a3a-4763-8bb0-c945a6e4eeee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Hamel Husain wrote this Python script [ https://substack.com/redirect/ba19798f-8550-4e8e-a1db-cd1c498777d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on top of the atproto [ https://substack.com/redirect/ef1739a6-7230-44c3-a2d2-879491ecc9bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Python library for interacting with Bluesky, which lets you specify another user and then follows every account that user is following.
I forked it and added two improvements: inline PEP 723 [ https://substack.com/redirect/01661b05-a6ce-4c5d-81e1-5c20e920b9b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] dependencies and input and getpass.getpass to interactively ask for the credentials needed to run the script.
This means you can run my version using uv run like this:
uv run https://gist.githubusercontent.com/simonw/848a3b91169a789bc084a459aa7ecf83/raw/397ad07c8be0601eaf272d9d5ab7675c7fd3c0cf/follow_theirs.py

I really like this pattern of being able to create standalone Python scripts with dependencies that can be run from a URL as a one-liner. Here's the comment section at the top of the script that makes it work:
# /// script
# dependencies = [
#   "atproto"
# ]
# ///

Quote 2024-11-24
Often, you are told to do this by treating AI like an intern. In retrospect, however, I think that this particular analogy ends up making people use AI in very constrained ways. To put it bluntly, any recent frontier model (by which I mean Claude 3.5, ChatGPT-4o, Grok 2, Llama 3.1, or Gemini Pro 1.5) is likely much better than any intern you would hire, but also weirder.
Instead, let me propose a new analogy: treat AI like an infinitely patient new coworker who forgets everything you tell them each new conversation, one that comes highly recommended but whose actual abilities are not that clear.
Ethan Mollick [ https://substack.com/redirect/7ced2b95-4bd4-4a6f-8d29-d467ae594357?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-25 Introducing the Model Context Protocol [ https://substack.com/redirect/504b197f-5d67-4d99-af22-2d67dba645d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Interesting new initiative from Anthropic. The Model Context Protocol [ https://substack.com/redirect/54927442-8d02-4bfa-a57f-02af15d6d3a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] aims to provide a standard interface for LLMs to interact with other applications, allowing applications to expose tools, resources (contant that you might want to dump into your context) and parameterized prompts that can be used by the models.
Their first working version of this involves the Claude Desktop app [ https://substack.com/redirect/9dae51b8-42f8-4f32-95b0-b3375dd2b929?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (for macOS and Windows). You can now configure that app to run additional "servers" - processes that the app runs and then communicates with via JSON-RPC over standard input and standard output.
Each server can present a list of tools, resources and prompts to the model. The model can then make further calls to the server to request information or execute one of those tools.
(For full transparency: I got a preview of this last week, so I've had a few days to try it out.)
The best way to understand this all is to dig into the examples. There are 13 of these [ https://substack.com/redirect/d92e6aae-1028-47a6-9a53-cd6b137e1119?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the modelcontextprotocol/servers GitHub repository so far, some using the Typesscript SDK [ https://substack.com/redirect/dd5b14d0-d2a2-4e91-8b11-0ab4df3c960c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and some with the Python SDK [ https://substack.com/redirect/c45e7181-37e4-46a0-81ea-8d539aa61963?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (mcp [ https://substack.com/redirect/c4584e52-1a1b-480a-a90a-180aa5bdd0b4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on PyPI).
My favourite so far, unsurprisingly, is the sqlite one [ https://substack.com/redirect/be867b23-bbff-4b66-9fc9-997ead3e574d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This implements methods for Claude to execute read and write queries and create tables in a SQLite database file on your local computer.
This is clearly an early release: the process for enabling servers in Claude Desktop - which involves hand-editing a JSON configuration file - is pretty clunky, and currently the desktop app and running extra servers on your own machine is the only way to try this out.
The specification already describes the next step for this: an HTTP SSE protocol which will allow Claude (and any other software that implements the protocol) to communicate with external HTTP servers. Hopefully this means that MCP will come to the Claude web and mobile apps soon as well.
A couple of early preview partners have announced their MCP implementations already:
Cody supports additional context through Anthropic's Model Context Protocol [ https://substack.com/redirect/902cd41c-8eb9-4cdb-8bf9-e5bf0749d4ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The Context Outside the Code [ https://substack.com/redirect/a450e387-07fa-4fed-8434-d7eded6fac1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is the Zed editor's announcement of their MCP extensions.
Link 2024-11-25 OpenStreetMap embed URL [ https://substack.com/redirect/aa6bd7ac-e998-453f-9e8f-d4e78110e2ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I just found out OpenStreetMap have a "share" button which produces HTML for an iframe targetting https://www.openstreetmap.org/export/embed.html, making it easy to drop an OpenStreetMap map onto any web page that allows iframes.
As far as I can tell the supported parameters are:
bbox= then min longitude, min latitude, max longitude, max latitude
marker= optional latitude, longitude coordinate for a marker (only a single marker is supported)
layer=mapnik - other values I've found that work are cyclosm, cyclemap, transportmap and hot (for humanitarian)
Here's HTML for embedding this on a page using a sandboxed iframe - the allow-scripts is necessary for the map to display.

Thanks to this post I learned that iframes are rendered correctly in NetNewsWire [ https://substack.com/redirect/a415473e-0f9e-4a69-b477-f4146f3e8493?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], NewsExplorer [ https://substack.com/redirect/ce8cf44b-d20c-4de1-ae64-569f4650894c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], NewsBlur [ https://substack.com/redirect/3646d85a-011b-4eff-acab-be84be47cf20?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Feedly on Android [ https://substack.com/redirect/3488a15b-24cc-4cd4-acfb-cd6946abc24a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-11-25 Leaked system prompts from Vercel v0 [ https://substack.com/redirect/efb7c682-be3e-430b-afa5-ebac8005ed55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
v0 [ https://substack.com/redirect/6e523b0c-68a1-45ba-8b05-ac8d3134c2c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is Vercel's entry in the increasingly crowded LLM-assisted development market - chat with a bot and have that bot build a full application for you.
They've been iterating on it since launching in October last year [ https://substack.com/redirect/660dea5f-3dc5-4314-a4ee-7966fac3f1d4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], making it one of the most mature products in this space.
Somebody leaked the system prompts recently. Vercel CTO Malte Ubl said this [ https://substack.com/redirect/7c75ddd2-052d-4f1b-9702-6d734b1235fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
When @v0 [ https://substack.com/redirect/1746fbaf-b45f-4008-84c0-9b3781f93c98?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] first came out we were paranoid about protecting the prompt with all kinds of pre and post processing complexity.
We completely pivoted to let it rip. A prompt without the evals, models, and especially UX is like getting a broken ASML machine without a manual
Link 2024-11-26 Amazon S3 adds new functionality for conditional writes [ https://substack.com/redirect/bce14608-eb7a-4e25-890a-665845c3e1c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Amazon S3 can now perform conditional writes that evaluate if an object is unmodified before updating it. This helps you coordinate simultaneous writes to the same object and prevents multiple concurrent writers from unintentionally overwriting the object without knowing the state of its content. You can use this capability by providing the ETag of an object [...]
This new conditional header can help improve the efficiency of your large-scale analytics, distributed machine learning, and other highly parallelized workloads by reliably offloading compare and swap operations to S3.
(Both Azure Blob Storage [ https://substack.com/redirect/95e1e75a-bce3-49dd-8d1f-9efdcddf35e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Google Cloud [ https://substack.com/redirect/4f93eed0-c1b8-46ff-8933-dfa8720bab33?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] have this feature already.)
When AWS added conditional write support just for if an object with that key exists or not back in August I wrote about [ https://substack.com/redirect/7f6f2626-bcb3-4ea8-8838-d2190eb5e795?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Gunnar Morling's trick for Leader Election With S3 Conditional Writes [ https://substack.com/redirect/f5bdb083-f15b-40be-a3d5-5abca2304f2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This new capability opens up a whole set of new patterns for implementing distributed locking systems along those lines.
Here's a useful illustrative example by lxgr on Hacker News [ https://substack.com/redirect/6873ba63-31e3-4243-96f5-ba2190b12afc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
As a (horribly inefficient, in case of non-trivial write contention) toy example, you could use S3 as a lock-free concurrent SQLite storage backend: Reads work as expected by fetching the entire database and satisfying the operation locally; writes work like this:
Download the current database copy
Perform your write locally
Upload it back using "Put-If-Match" and the pre-edit copy as the matched object.
If you get success, consider the transaction successful.
If you get failure, go back to step 1 and try again.
AWS also just added the ability to enforce conditional writes in bucket policies [ https://substack.com/redirect/c1e9aaec-3f46-41a4-b8aa-26bbc6f467f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
To enforce conditional write operations, you can now use s3:if-none-match or s3:if-match condition keys to write a bucket policy that mandates the use of HTTP if-none-match or HTTP if-match conditional headers in S3 PutObject and CompleteMultipartUpload API requests. With this bucket policy in place, any attempt to write an object to your bucket without the required conditional header will be rejected.
Quote 2024-11-26
My preferred approach in many projects is to do some unit testing, but not a ton, early on in the project and wait until the core APIs and concepts of a module have crystallized.
At that point I then test the API exhaustively with integrations tests.
In my experience, these integration tests are much more useful than unit tests, because they remain stable and useful even as you change the implementation around. They aren’t as tied to the current codebase, but rather express higher level invariants that survive refactors much more readily.
Carson Gross [ https://substack.com/redirect/127f9347-a03c-4981-9381-586f6bb69190?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-11-26
One of the things we did all the time at early GitHub was a two-step ship: basically, ship a big launch, but days or weeks afterwards, ship a smaller, add-on feature. In the second launch post, you can refer back to the initial bigger post and you get twice the bang for the buck.
This is even more valuable than on the surface, too: you get to split your product launch up into a few different pieces, which lets you slowly ease into the full usage — and server load — of new code.
Zach Holman [ https://substack.com/redirect/4ca491b0-cc76-4c8d-82e4-7b791e0f8536?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-27 QwQ: Reflect Deeply on the Boundaries of the Unknown [ https://substack.com/redirect/ffe6cff0-444e-4ef5-bb79-157cd13d945c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Brand new openly licensed (Apache 2) model from Alibaba Cloud's Qwen team, this time clearly inspired by OpenAI's work on reasoning in o1.
I love the flowery language they use to introduce the new model:
Through deep exploration and countless trials, we discovered something profound: when given time to ponder, to question, and to reflect, the model’s understanding of mathematics and programming blossoms like a flower opening to the sun. Just as a student grows wiser by carefully examining their work and learning from mistakes, our model achieves deeper insight through patient, thoughtful analysis.
It's already available through Ollama [ https://substack.com/redirect/afbbf9ad-5ebf-4b9a-9344-b69bafbc94eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a 20GB download. I initially ran it like this:
ollama run qwq

This downloaded the model and started an interactive chat session. I tried the classic "how many rs in strawberry?" and got this lengthy but correct [ https://substack.com/redirect/340ed91c-6f79-4e59-a66f-5f1d62a91274?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] answer, which concluded:
Wait, but maybe I miscounted. Let's list them: 1. s 2. t 3. r 4. a 5. w 6. b 7. e 8. r 9. r 10. y Yes, definitely three "r"s. So, the word "strawberry" contains three "r"s.
Then I switched to using LLM [ https://substack.com/redirect/6e39c88c-eb3e-4998-8eb3-b57ac95d83b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the llm-ollama [ https://substack.com/redirect/26164384-a41c-4ba8-8a74-e9337926f64e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin. I tried prompting it for Python that imports CSV into SQLite:
Write a Python function import_csv(conn, url, table_name) which acceopts a connection to a SQLite databse and a URL to a CSV file and the name of a table - it then creates that table with the right columns and imports the CSV data from that URL
It thought through the different steps in detail and produced some decent looking code [ https://substack.com/redirect/060e1ef0-1f06-456a-95ca-cfbc56a8113c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Finally, I tried this:
llm -m qwq 'Generate an SVG of a pelican riding a bicycle'

For some reason it answered in Simplified Chinese. It opened with this:
生成一个SVG图像，内容是一只鹈鹕骑着一辆自行车。这听起来挺有趣的！我需要先了解一下什么是SVG，以及如何创建这样的图像。
Which translates (using Google Translate) to:
Generate an SVG image of a pelican riding a bicycle. This sounds interesting! I need to first understand what SVG is and how to create an image like this.
It then produced a lengthy essay discussing the many aspects that go into constructing a pelican on a bicycle - full transcript here [ https://substack.com/redirect/2f8b7507-9c99-4c3a-bf60-245acae44481?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. After a full 227 seconds of constant output it produced this as the final result.
I think that's pretty good!
Link 2024-11-28 SmolVLM - small yet mighty Vision Language Model [ https://substack.com/redirect/a3e0e525-f039-4f1c-a19f-852d47b2ec49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've been having fun playing with this new vision model from the Hugging Face team behind SmolLM [ https://substack.com/redirect/34af2815-89aa-4859-b2ea-975dbfb58943?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. They describe it as:
[...] a 2B VLM, SOTA for its memory footprint. SmolVLM is small, fast, memory-efficient, and fully open-source. All model checkpoints, VLM datasets, training recipes and tools are released under the Apache 2.0 license.
I've tried it in a few flavours but my favourite so far is the mlx-vlm [ https://substack.com/redirect/e5128119-253f-4b6d-b14b-a7dc807e7d6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] approach, via mlx-vlm author Prince Canuma [ https://substack.com/redirect/63954fab-ae96-45ce-80a8-5059cb916182?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here's the uv recipe I'm using to run it:
uv run \
--with mlx-vlm \
--with torch \
python -m mlx_vlm.generate \
--model mlx-community/SmolVLM-Instruct-bf16 \
--max-tokens 500 \
--temp 0.5 \
--prompt "Describe this image in detail" \
--image IMG_4414.JPG

If you run into an error using Python 3.13 (torch compatibility) try uv run --python 3.11 instead.
This one-liner installs the necessary dependencies, downloads the model (about 4.2GB, saved to ~/.cache/huggingface/hub/models--mlx-community--SmolVLM-Instruct-bf16) and executes the prompt and displays the result.
I ran that against this Pelican photo [ https://substack.com/redirect/87159db1-0690-4c1f-a3d3-fac45cde9c76?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The model replied:
In the foreground of this photograph, a pelican is perched on a pile of rocks. The pelican’s wings are spread out, and its beak is open. There is a small bird standing on the rocks in front of the pelican. The bird has its head cocked to one side, and it seems to be looking at the pelican. To the left of the pelican is another bird, and behind the pelican are some other birds. The rocks in the background of the image are gray, and they are covered with a variety of textures. The rocks in the background appear to be wet from either rain or sea spray.
There are a few spatial mistakes in that description but the vibes are generally in the right direction.
On my 64GB M2 MacBook pro it read the prompt at 7.831 tokens/second and generated that response at an impressive 74.765 tokens/second.
Link 2024-11-29 LLM Flowbreaking [ https://substack.com/redirect/45809c61-76a7-43d0-98b8-725bbb7b0fda?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Gadi Evron from Knostic:
We propose that LLM Flowbreaking, following jailbreaking and prompt injection, joins as the third on the growing list of LLM attack types. Flowbreaking is less about whether prompt or response guardrails can be bypassed, and more about whether user inputs and generated model outputs can adversely affect these other components in the broader implemented system.
The key idea here is that some systems built on top of LLMs - such as Microsoft Copilot - implement an additional layer of safety checks which can sometimes cause the system to retract an already displayed answer.
I've seen this myself a few times, most notable with Claude 2 last year when it deleted an almost complete podcast transcript cleanup right in front of my eye because the hosts started talking about bomb threats.
Knostic calls this Second Thoughts, where an LLM system decides to retract its previous output. It's not hard for an attacker to grab this potentially harmful data: I've grabbed some using a quick copy and paste, or you can use tricks like video scraping [ https://substack.com/redirect/831c598c-db38-4762-be58-76496feb100e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or using the network browser tools.
They also describe a Stop and Roll attack, where the user clicks the "stop" button while executing a query against a model in a way that also prevents the moderation layer from having the chance to retract its previous output.
I'm not sure I'd categorize this as a completely new vulnerability class. If you implement a system where output is displayed to users you should expect that attempts to retract that data can be subverted - screen capture software is widely available these days.
I wonder how widespread this retraction UI pattern is? I've seen it in Claude and evidently ChatGPT and Microsoft Copilot have the same feature. I don't find it particularly convincing - it seems to me that it's more safety theatre than a serious mechanism for avoiding harm caused by unsafe output.
Link 2024-11-29 GitHub OAuth for a static site using Cloudflare Workers [ https://substack.com/redirect/7be0a9a8-066a-4986-8650-3752e129820b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here's a TIL covering a Thanksgiving AI-assisted programming project. I wanted to add OAuth against GitHub to some of the projects on my tools.simonwillison.net [ https://substack.com/redirect/6989b6fd-d14f-497f-90f9-4c760d7290f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] site in order to implement "Save to Gist".
That site is entirely statically hosted by GitHub Pages, but OAuth has a required server-side component: there's a client_secret involved that should never be included in client-side code.
Since I serve the site from behind Cloudflare I realized that a minimal Cloudflare Workers [ https://substack.com/redirect/3bbd5217-0f7a-4132-8e31-c6144d58fcc5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] script may be enough to plug the gap. I got Claude on my phone to build me a prototype and then pasted that (still on my phone) into a new Cloudflare Worker and it worked!
... almost. On later closer inspection of the code it was missing error handling... and then someone pointed out it was vulnerable to a login CSRF attack thanks to failure to check the state= parameter. I worked with Claude to fix those too.
Useful reminder here that pasting code AI-generated code around on a mobile phone isn't necessarily the best environment to encourage a thorough code review!
Quote 2024-11-29
People have too inflated sense of what it means to "ask an AI" about something. The AI are language models trained basically by imitation on data from human labelers. Instead of the mysticism of "asking an AI", think of it more as "asking the average data labeler" on the internet. [...]
Post triggered by someone suggesting we ask an AI how to run the government etc. TLDR you're not asking an AI, you're asking some mashup spirit of its average data labeler.
Andrej Karpathy [ https://substack.com/redirect/984d8fe1-d7d8-4f0c-b9a7-9c854d7f9b69?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-11-29
Among closed-source models, OpenAI [ https://substack.com/redirect/b6ed75ff-c7e6-4818-ac4a-bc229b319c9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]'s early mover advantage has eroded somewhat, with enterprise market share dropping from 50% to 34%. The primary beneficiary has been Anthropic [ https://substack.com/redirect/a2b91899-fc7c-450e-a05d-9c3ba0fe061e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ],* which doubled its enterprise presence from 12% to 24% as some enterprises switched from GPT-4 to Claude 3.5 Sonnet when the new model became state-of-the-art. When moving to a new LLM, organizations most commonly cite security and safety considerations (46%), price (44%), performance (42%), and expanded capabilities (41%) as motivations.
Menlo Ventures [ https://substack.com/redirect/6c3b3dde-6002-44fd-b059-a6ff0cde23d5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-29 Structured Generation w/ SmolLM2 running in browser & WebGPU [ https://substack.com/redirect/22c69cc3-e391-43f6-93fb-760a76fcbfa8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Extraordinary demo by Vaibhav Srivastav. Here's Hugging Face's SmolLM2-1.7B-Instruct [ https://substack.com/redirect/0494d069-f9b2-498a-a880-8a379a940e70?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] running directly in a web browser (using WebGPU, so requires Chrome for the moment [ https://substack.com/redirect/6f9bcd36-9611-4752-a883-cff252c307f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) demonstrating structured text extraction, converting a text description of an image into a structured GitHub issue defined using JSON schema.
The page loads 924.8MB of model data (according to this script to sum up files in window.caches [ https://substack.com/redirect/864613dc-c2ff-4d01-81e6-3ce1c5b7bfd0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and performs everything in-browser. I did not know a model this small could produce such useful results.
Here's the source code [ https://substack.com/redirect/e2d472ca-3508-407e-a19f-cd724e0a0781?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the demo. It's around 200 lines of code, 50 of which are the JSON schema describing the data to be extracted.
The real secret sauce here is the web-llm [ https://substack.com/redirect/f0ad1a07-af14-405d-abd3-c431b71fd041?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by MLC. This library has made loading and executing prompts through LLMs in the browser shockingly easy, and recently incorporated support for MLC's XGrammar [ https://substack.com/redirect/ec9ee715-1671-4064-b959-b6c625c63b92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library (also available in Python) which implements both JSON schema and EBNF-based structured output guidance.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEl6TXprNU5UZ3NJbWxoZENJNk1UY3pNamt4T1RBMk15d2laWGh3SWpveE56WTBORFUxTURZekxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuS1Z1WFg0SHo2S1NOU05ha05MdnhwY3EwSU82MkJYUHpmcE1RR1pzNmdzVSIsInAiOjE1MjMzOTk1OCwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzMyOTE5MDYzLCJleHAiOjE3MzU1MTEwNjMsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.lnw-kmD4rJXhUHm7GFlFx8SMDBuxJ6CNX9uFYPouGFw?
