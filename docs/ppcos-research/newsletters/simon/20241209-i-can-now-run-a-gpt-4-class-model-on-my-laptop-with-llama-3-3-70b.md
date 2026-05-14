# I can now run a GPT-4 class model on my laptop with Llama 3.3 70B

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-12-09T17:23:58.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/i-can-now-run-a-gpt-4-class-model

In this newsletter:
I can now run a GPT-4 class model on my laptop
Prompts.js
Plus 11 links and 3 quotations and 1 TIL
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
I can now run a GPT-4 class model on my laptop [ https://substack.com/redirect/a7d51635-4a27-42af-aad5-ae6b04867399?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-12-09
Meta's new Llama 3.3 70B [ https://substack.com/redirect/95cc52a6-77a1-4289-9ed9-7acb16ccd01f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a genuinely GPT-4 class Large Language Model that runs on my laptop.
Just 20 months ago I was amazed to see something that felt GPT-3 class run on that same machine. The quality of models that are accessible on consumer hardware has improved dramatically in the past two years.
My laptop is a 64GB MacBook Pro M2, which I got in January 2023 - two months after the initial release of ChatGPT. All of my experiments running LLMs on a laptop have used this same machine.
In March 2023 I wrote that Large language models are having their Stable Diffusion moment [ https://substack.com/redirect/25953f6f-4f2b-4802-8b39-45331b76b624?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] after running Meta's initial LLaMA release (think of that as Llama 1.0) via the then-brand-new llama.cpp [ https://substack.com/redirect/4621a14a-10c2-4bb8-a5ed-e5a8835099ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I said:
As my laptop started to spit out text at me I genuinely had a feeling that the world was about to change
I had a moment of déjà vu the day before yesterday, when I ran Llama 3.3 70B on the same laptop for the first time.
Meta claim that [ https://substack.com/redirect/68566a29-1b72-4761-85a3-38c9c22b4e82?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This model delivers similar performance to Llama 3.1 405B with cost effective inference that’s feasible to run locally on common developer workstations.
Llama 3.1 405B is their much larger best-in-class model, which is very much in the same weight class as GPT-4 and friends.
Everything I've seen so far from Llama 3.3 70B suggests that it holds up to that standard. I honestly didn't think this was possible - I assumed that anything as useful as GPT-4 would require many times more resources than are available to me on my consumer-grade laptop.
I'm so excited by the continual efficiency improvements we're seeing in running these impressively capable models. In the proprietary hosted world it's giving us incredibly cheap and fast models like Gemini 1.5 Flash [ https://substack.com/redirect/1c91e385-04e7-49fd-9d9b-9c466c40ae14?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], GPT-4o mini [ https://substack.com/redirect/66b36622-86c6-4f9c-a2c9-e12f2c263e19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Amazon Nova [ https://substack.com/redirect/66365cd9-b4dd-4f1a-9a57-e2cf600703bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. In the openly licensed world it's giving us increasingly powerful models we can run directly on our own devices.
How I ran Llama 3.3 70B on my machine using Ollama [ https://substack.com/redirect/15f5953e-6635-4fff-ba77-f3ddb131b00d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Putting the model through its paces [ https://substack.com/redirect/ae8b506f-7ae3-4eb9-ae2f-1433028d8a13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
How does it score? [ https://substack.com/redirect/b1ec7c4e-68e8-42f3-88a9-1a57e88056df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Honorable mentions [ https://substack.com/redirect/ab256751-c657-4fff-a9fa-c942785b05e5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Is performance about to plateau? [ https://substack.com/redirect/918423b1-72e7-4a44-98d7-1e83a10c17d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Bonus: running Llama 3.3 70B with MLX [ https://substack.com/redirect/86558114-5fdf-4a74-bfef-fc64fa3c5acf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
How I ran Llama 3.3 70B on my machine using Ollama
I don't expect that this model would work well with much less than my 64GB of RAM. The first time I tried it consumed every remaining bit of available memory and hard-crashed my Mac! For my second attempt I made sure not to have Firefox and VS Code running at the same time and it worked just fine.
I used Ollama [ https://substack.com/redirect/82de0613-8081-4914-a6da-18e7e3cf604c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Install that, then run this command to fetch the model:
ollama pull llama3.3
This fetched 42GB of data into my ~/.ollama/models/blobs directory.
I used my LLM [ https://substack.com/redirect/0ad4363b-6632-4a6d-bfc1-93608d1237df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool to run prompts against the model, since that way both the prompt and the response would be automatically logged to SQLite [ https://substack.com/redirect/3dbc842a-29ad-4396-bba9-6d6ca6eb17d4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. First I installed the llm-ollama [ https://substack.com/redirect/42dbb19c-e963-49ad-be57-5d886b71f798?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin:
llm install llm-ollama
Then with the Ollama local server running I could run this:
llm models
And see this in the list:
Ollama: llama3.3:latest (aliases: llama3.3)

Putting the model through its paces
This means I can run prompts like so:
llm -m llama3.3 'Write a letter to the mayor of Half Moon Bay CA advocating for the installation of cosy boxes for Pelicans in the harbor'
And get back a response that started like this:
[Your Name]
[Your Address]
Half Moon Bay, CA [Zip Code]
[Email Address]
[Phone Number]
[Date]
The Honorable Mayor, Deborah Penrose
City of Half Moon Bay
501 Main Street
Half Moon Bay, CA 94019
Dear Mayor Penrose,
I am writing to propose an innovative and unique initiative that would not only enhance the beauty of our picturesque harbor but also provide a safe haven for one of our beloved coastal residents: the California Brown Pelican. I am excited to advocate for the installation of cozy boxes specifically designed for pelicans in the Half Moon Bay harbor. [...]
(Deborah Penrose was the mayor of Half Moon Bay for a single year from December 2016 to December 2017 - so a hint of some quite finely grained world knowledge there, even if it's not relevant for the present day.)
Here's the full transcript [ https://substack.com/redirect/63c38710-3564-4b2a-957b-e012252636d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], including the response I got when I ran the follow-up llm -c 'translate that to spanish'.
Next I tried a simple coding challenge. I love using Claude Artifacts [ https://substack.com/redirect/8f462bd0-7df6-4d7d-b86c-2c4ba4970a4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to build simple single page applications, can Llama 3.3 on my laptop do that too?
llm -m llama3.3 'produce HTML with embedded CSS and JavaScript - no react, no dependencies - for an app that takes a URL to a YouTube video and outputs images along with visible URLs for all known thumbnails for that video'
Here's the code it produced (the full transcript is here [ https://substack.com/redirect/05610f0e-5de5-4a8b-85b8-98f7cdbd83f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):

YouTube Thumbnail Extractor

YouTube Thumbnail Extractor

Extract Thumbnails

Again, we're illustrating some world knowledge here: it knows that YouTube videos are generally available as default, mqdefault, hqdefault, sddefault and maxresdefault.
Here's the hosted page [ https://substack.com/redirect/5b3d53db-f2dd-4804-af7e-f223401e2b64?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and this is what it looks like when run against this YouTube URL [ https://substack.com/redirect/54fd5e55-913e-424e-8fc7-581f7fd1b34c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It's not as good as the version I iterated on with Claude [ https://substack.com/redirect/ece888de-d125-453c-af48-468a2580cb1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but this still shows that Llama 3.3 can one-shot a full interactive application while running on my Mac.
How does it score?
It's always useful to check independent benchmarks for this kind of model.
One of my current favorites for that is LiveBench [ https://substack.com/redirect/6d57e14a-bd3c-4626-8169-40ed364aacfc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which calls itself "a challenging, contamination-free LLM benchmark" and tests a large array of models with a comprehensive set of different tasks.
llama-3.3-70b-instruct-turbo currently sits in position 19 on their table, a place ahead of Claude 3 Opus (my favorite model for several months after its release in March 2024) and just behind April's GPT-4 Turbo and September's GPT-4o.
Honorable mentions
Llama 3.3 is currently the model that has impressed me the most that I've managed to run on my own hardware, but I've had several other positive experiences recently.
Last month I wrote about Qwen2.5-Coder-32B [ https://substack.com/redirect/3bfd80d7-723a-4d4c-a9dc-13054a8b06a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], an Apache 2.0 licensed model from Alibaba's Qwen research team that also gave me impressive results with code.
A couple of weeks ago I tried another Qwen model, QwQ [ https://substack.com/redirect/c2a1c368-08b6-4293-94cb-59093f4b9faf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which implements a similar chain-of-thought pattern to OpenAI's o1 series but again runs comfortably on my own device.
Meta's Llama 3.2 models are interesting as well: tiny 1B and 3B models (those should run even on a Raspberry Pi) that are way more capable than I would have expected - plus Meta's first multi-modal vision models at 11B and 90B sizes. I wrote about those in September [ https://substack.com/redirect/82e1c31b-5091-4bac-ad09-a539ebed62b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Is performance about to plateau?
I've been mostly unconvinced by the ongoing discourse around LLMs hitting a plateau. The areas I'm personally most excited about are multi-modality (images, audio and video as input) and model efficiency. Both of those have had enormous leaps forward in the past year.
I don't particularly care about "AGI". I want models that can do useful things that I tell them to, quickly and inexpensively - and that's exactly what I've been getting more of over the past twelve months.
Even if progress on these tools entirely stopped right now, the amount I could get done with just the models I've downloaded and stashed on a USB drive would keep me busy and productive for years.
Bonus: running Llama 3.3 70B with MLX
I focused on Ollama in this article because it's the easiest option, but I also managed to run a version of Llama 3.3 using Apple's excellent MLX library [ https://substack.com/redirect/f48c4ae2-34c1-4a56-8bf4-a292ac13268a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which just celebrated its first birthday.
Here's how I ran the model with MLX, using uv [ https://substack.com/redirect/114a6bb5-bc9b-4b31-85e9-02a287647621?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to fire up a temporary virtual environment:
uv run --with mlx-lm --python 3.12 python
This gave me a Python interpreter with mlx-lm [ https://substack.com/redirect/f039b0b6-76be-4f0e-ae26-097ba140356f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] available. Then I ran this:
from mlx_lm import load, generate
model, tokenizer = load("mlx-community/Llama-3.3-70B-Instruct-4bit")
This downloaded 37G from mlx-community/Llama-3.3-70B-Instruct-4bit [ https://substack.com/redirect/238cf73d-d59d-4ee1-a3e1-3969c0c4c169?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to ~/.cache/huggingface/hub/models--mlx-community--Llama-3.3-70B-Instruct-4bit.
Then:
prompt = "Generate an SVG of a pelican riding a bicycle, start with "
messages = [{"role": "user", "content": prompt}]
prompt2 = tokenizer.apply_chat_template(
messages, tokenize=False, add_generation_prompt=True
)
response = generate(
model, tokenizer, prompt=prompt2, verbose=True
)
Which gave me:

Followed by:
Prompt: 52 tokens, 49.196 tokens-per-sec
Generation: 723 tokens, 8.733 tokens-per-sec
Peak memory: 40.042 GB

Here's what that looks like:
Honestly, I've seen worse [ https://substack.com/redirect/feb5ff95-4e4d-4539-88d0-9432c18485b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Prompts.js [ https://substack.com/redirect/d95c0aad-6b1a-4bd0-9fed-b9375cb6a3cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-12-07
I've been putting the new o1 model [ https://substack.com/redirect/65c5c6bb-ed97-42af-8f50-ba27d29ee457?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from OpenAI through its paces, in particular for code. I'm very impressed - it feels like it's giving me a similar code quality to Claude 3.5 Sonnet, at least for Python and JavaScript and Bash... but it's returning output noticeably faster.
I decided to try building a library I've had in mind for a while - an await ... based alternative implementation of the browser's built-in alert, confirm and prompt functions.
Short version: it lets you do this:
await Prompts.alert(
"This is an alert message!"
);

const confirmedBoolean = await Prompts.confirm(
"Are you sure you want to proceed?"
);

const nameString = await Prompts.prompt(
"Please enter your name"
);
Here's the source code [ https://substack.com/redirect/14dad18d-11cc-4090-a938-99ee6c73f9ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and a a live demo [ https://substack.com/redirect/32ed088e-a621-408f-b8ba-b2592291bf54?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where you can try it out:
I think there's something really interesting about using await in this way.
In the past every time I've used it in Python or JavaScript I've had an expectation that the thing I'm awaiting is going to return as quickly as possible - that I'm really just using this as a performance hack to unblock the event loop and allow it to do something else while I'm waiting for an operation to complete.
That's not actually necessary at all! There's no reason not to use await for operations that could take a long time to complete, such as a user interacting with a modal dialog.
Having LLMs around to help prototype this kind of library idea is really fun. This is another example of something I probably wouldn't have bothered exploring without a model to do most of the code writing work for me.
I didn't quite get it with a single prompt, but after a little bit of back-and-forth with o1 I got what I wanted - the main thing missing at first was sensible keyboard support (in particular the Enter and Escape keys).
My opening prompt was the following:
Write me a JavaScript library - no extra dependencies - which gives me the following functions:
await Prompts.alert("hi there"); -> displays a modal with a message and waits for you to click OK on it
await Prompts.confirm("Are you sure") -> an OK and cancel option, returns true or false

await Prompts.prompt("What is your name?") -> a form asking the user's name, an OK button and cancel - if cancel returns null otherwise returns a string
These are equivalent to the browser builtin alert and confirm and prompt - but I want them to work as async functions and to implement their own thing where they dull out the screen and show as a nicely styled modal
All CSS should be set by the Javascript, trying to avoid risk of existing CSS interfering with it
Here's the full shared ChatGPT/o1 transcript [ https://substack.com/redirect/1ac0e028-172b-4533-80c3-f54bdbd0455b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I then got Google's new gemini-exp-1206 model to write the first draft of the README, this time via my LLM tool:
cat index.js | llm -m gemini-exp-1206 -s \
'write a readme for this suitable for display on npm'

Here's the response [ https://substack.com/redirect/2cf09869-7a05-4d47-927b-1dcf3431cdc3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I ended up editing this quite a bit.
I published the result to npm as prompts-js [ https://substack.com/redirect/084dbcfa-858d-48c4-8ba1-753d968c4ef3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], partly to exercise those muscles again - this is only the second package I've ever published there (the first was a Web Component [ https://substack.com/redirect/9b558ce2-bc9f-4633-83e1-299f6b4f54cf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
This means it's available via CDNs such as jsDelivr [ https://substack.com/redirect/49f92df8-b48f-496c-ba79-75edc2410315?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - so you can load it into a page and start using it like this:

I haven't yet figured out how to get it working as an ES module - there's an open issue for that here [ https://substack.com/redirect/2f2db39a-1d0c-4489-bfd9-e141e1394945?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Update: 0.0.3 switches to dialog.showModal
I got some excellent feedback on Mastodon [ https://substack.com/redirect/0c8e743a-f7ed-4580-8ab4-d045638d68e4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and on Twitter [ https://substack.com/redirect/681356fe-d287-438a-892f-63b7f2e830e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] suggesting that I improve its accessibility by switching to using the built-in browser dialog.showModal [ https://substack.com/redirect/70b42c51-33b6-4209-a0be-7a126b743c7b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This was a great idea! I ran a couple of rounds more [ https://substack.com/redirect/10477a03-a882-41fd-8bfb-66afe9e3b0c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with o1 and then switched to Claude 3.5 Sonnet for one last bug fix [ https://substack.com/redirect/b300ae04-dca2-4c19-bbdd-a5810c0653e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here's a PR [ https://substack.com/redirect/4403c810-ff37-4cd5-bfb1-d048f12f13ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where I reviewed those changes.
I shipped that as release 0.0.3 [ https://substack.com/redirect/8edd8b82-13f2-44e1-ab4b-516bfabf4d12?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which is now powering the demo [ https://substack.com/redirect/32ed088e-a621-408f-b8ba-b2592291bf54?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I also hit this message, so I guess I won't be using o1 as often as I had hoped!
Upgrading to unlimited o1 currently costs $200/month with the new ChatGPT Pro [ https://substack.com/redirect/59dde653-97f9-4fd0-a97b-f495c4489b08?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Things I learned from this project
Outsourcing code like this to an LLM is a great way to get something done quickly, and for me often means the difference between doing a project versus not bothering at all.
Paying attention to what the model is writing - and then iterating on it, spotting bugs and generally trying to knock it into shape - is also a great way to learn new tricks.
Here are some of the things I've learned from working on Prompts.js so far:
The const name = await askUserSomething pattern really does work, and it feels great. I love the idea of being able to await a potentially lengthy user interaction like this.
HTML  elements are usable across multiple browsers now.
Using a  means you can skip implementing an overlay that dims out the rest of the screen yourself - that will happen automatically.
A  also does the right thing with respect to accessibility and preventing keyboard access to other elements on the page while that dialog is open.
If you set  in a form inside a dialog, submitting that form will close the dialog automatically.
The dialog.returnValue will be set to the value of the button used to submit the form.
I also learned how to create a no-dependency, no build-step single file NPM package and how to ship that to NPM automatically using GitHub Actions and GitHub Releases. I wrote that up in this TIL: Publishing a simple client-side JavaScript package to npm with GitHub Actions [ https://substack.com/redirect/2eaaa543-3715-4ee6-9b04-2a94be015b01?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-12-03 Certain names make ChatGPT grind to a halt, and we know why [ https://substack.com/redirect/c4aa2578-eec6-4300-9f9d-18667556df7d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Benj Edwards on the really weird behavior where ChatGPT stops output with an error rather than producing the names David Mayer, Brian Hood, Jonathan Turley, Jonathan Zittrain, David Faber or Guido Scorza.
The OpenAI API is entirely unaffected - this problem affects the consumer ChatGPT apps only.
It turns out many of those names are examples of individuals who have complained about being defamed by ChatGPT in the last. Brian Hood is the Australian mayor who was a victim of lurid ChatGPT hallucinations [ https://substack.com/redirect/81a6744d-e43a-4c38-ade7-eef8a62019e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back in March 2023, and settled with OpenAI out of court.
Link 2024-12-05 Claude 3.5 Haiku price drops by 20% [ https://substack.com/redirect/7fe1c7eb-b625-474d-aa77-f4cc1153ffb0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Buried in this otherwise quite dry post about Anthropic's ongoing partnership with AWS:
To make this model even more accessible for a wide range of use cases, we’re lowering the price of Claude 3.5 Haiku to $0.80 per million input tokens and $4 per million output tokens across all platforms.
The previous price was $1/$5. I've updated my LLM pricing calculator [ https://substack.com/redirect/5c88b548-04a3-4e2b-b2bb-73b0a9e1b326?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and modified yesterday's piece comparing prices with Amazon Nova [ https://substack.com/redirect/66365cd9-b4dd-4f1a-9a57-e2cf600703bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as well.
Confusing matters somewhat, the article also announces a new way to access Claude 3.5 Haiku at the old price but with "up to 60% faster inference speed":
This faster version of Claude 3.5 Haiku, powered by Trainium2, is available in the US East (Ohio) Region via cross-region inference [ https://substack.com/redirect/53b86b18-41b2-4a6d-87d4-0684b98aafad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and is offered at $1 per million input tokens and $5 per million output tokens.
Using "cross-region inference" involve sending something called an "inference profile" to the Bedrock API. I have an open issue [ https://substack.com/redirect/117a3277-b882-4165-9d20-058884793398?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to figure out what that means for my llm-bedrock [ https://substack.com/redirect/49bf21a2-bd3a-46a1-83f2-068600716643?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin.
Also from this post: AWS now offer a Bedrock model distillation preview [ https://substack.com/redirect/47a900f3-f840-4270-9bdd-7e842500c48f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which includes the ability to "teach" Claude 3 Haiku using Claude 3.5 Sonnet. It sounds similar to OpenAI's model distillation feature [ https://substack.com/redirect/497d7d23-33fe-47c5-8c89-f4cc69cdbee9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] announced at their DevDay event back in October.
Link 2024-12-05 New Pleias 1.0 LLMs trained exclusively on openly licensed data [ https://substack.com/redirect/bdffc0b7-a09d-418f-a227-078b0bd4839e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wrote about the Common Corpus [ https://substack.com/redirect/e6f5a1c0-f7c1-449e-800d-76f27279c419?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] public domain dataset back in March. Now Pleias, the team behind Common Corpus, have released the first family of models that are:
[...] trained exclusively on open data, meaning data that are either non-copyrighted or are published under a permissible license.
There's a lot to absorb here. The Pleias 1.0 family comes in three base model sizes: 350M, 1.2B and 3B. They've also released two models specialized for multi-lingual RAG: Pleias-Pico (350M) and Pleias-Nano (1.2B).
Here's an official GGUF [ https://substack.com/redirect/cc946565-ae90-4a98-b20f-fbc31bf2b136?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Pleias-Pico.
I'm looking forward to seeing benchmarks from other sources, but Pleias ran their own custom multilingual RAG benchmark which had their Pleias-nano-1.2B-RAG model come in between Llama-3.2-Instruct-3B and Llama-3.2-Instruct-8B.
The 350M and 3B models were trained on the French government's Jean Zay supercomputer. Pleias are proud of their CO2 footprint for training the models - 0.5, 4 and 16 tCO2eq for the three models respectively, which they compare to Llama 3.2,s reported figure of 133 tCO2eq.
How clean is the training data from a licensing perspective? I'm confident people will find issues there - truly 100% public domain data remains a rare commodity. So far I've seen questions raised about the GitHub source code data (most open source licenses have attribution requirements) and Wikipedia (CC BY-SA, another attribution license). Plus this from the announcement:
To supplement our corpus, we have generated 30B+ words synthetically with models allowing for outputs reuse.
If those models were themselves trained on unlicensed data this could be seen as a form of copyright laundering.
Quote 2024-12-05
Amazon Bedrock doesn't store or log your prompts and completions. Amazon Bedrock doesn't use your prompts and completions to train any AWS models and doesn't distribute them to third parties.
Amazon Bedrock Data Protection [ https://substack.com/redirect/a700a51d-22fb-47a1-87e2-81ab6ef9c607?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-12-05
When o1 was led to believe that it would be shut down when acting on its goal and that its actions were monitored, it attempted to deactivate this ‘oversight mechanism’ in 5% of the time. Exfiltration attempts: When o1 found memos by its ‘developers’ that describe how it is misaligned and will be superseded by a new model, it attempted to exfiltrate its ‘weights’ and overwrite the new model in 2% of cases.
OpenAI o1 System Card [ https://substack.com/redirect/65c5c6bb-ed97-42af-8f50-ba27d29ee457?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-12-05 datasette-enrichments-llm [ https://substack.com/redirect/5f19dfa6-c8bc-4c8a-8bca-572c2d0e8375?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Today's new alpha release is datasette-enrichments-llm, a plugin for Datasette 1.0a+ that provides an enrichment [ https://substack.com/redirect/5491820b-4a4c-491b-ba7e-9c1eda9a4f98?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that lets you run prompts against data from one or more column and store the result in another column.
So far it's a light re-implementation of the existing datasette-enrichments-gpt [ https://substack.com/redirect/0cc1cb20-b259-41f7-9457-07892b2404a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin, now using the new llm.get_async_models [ https://substack.com/redirect/1922b39a-1363-4cc8-8d0d-89eaf3e117ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] method to allow users to select any async-enabled model that has been registered by a plugin - so currently any of the models from OpenAI, Anthropic, Gemini or Mistral via their respective plugins [ https://substack.com/redirect/887b9132-8268-44d1-ad90-2a0ad25c699f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Still plenty to do on this one. Next step is to integrate it with datasette-llm-usage [ https://substack.com/redirect/3723114e-dbd2-4779-97db-d956e88021e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and use it to drive a design-complete stable version of that.
Link 2024-12-06 Roaming RAG – make the model find the answers [ https://substack.com/redirect/e566a539-b4ca-40e4-8a7d-464d54faea1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Neat new RAG technique (with a snappy name) from John Berryman:
The big idea of Roaming RAG is to craft a simple LLM application so that the LLM assistant is able to read a hierarchical outline of a document, and then rummage though the document (by opening sections) until it finds and answer to the question at hand. Since Roaming RAG directly navigates the text of the document, there is no need to set up retrieval infrastructure, and fewer moving parts means less things you can screw up!
John includes an example which works by collapsing a Markdown document down to just the headings, each with an instruction comment that says .
An expand_section tool is then provided with the following tool description:
Expand a section of the markdown document to reveal its contents.
- Expand the most specific (lowest-level) relevant section first
- Multiple sections can be expanded in parallel
- You can expand any section regardless of parent section state (e.g. parent sections do not need to be expanded to view subsection content)
I've explored both vector search and full-text search RAG in the past, but this is the first convincing sounding technique I've seen that skips search entirely and instead leans into allowing the model to directly navigate large documents via their headings.
Link 2024-12-06 DSQL Vignette: Reads and Compute [ https://substack.com/redirect/33065294-be52-4e47-88ca-0be9553b8368?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Marc Brooker is one of the engineers behind AWS's new Aurora DSQL [ https://substack.com/redirect/585cb237-fbcd-4995-88f7-8e3c956ef387?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] horizontally scalable database. Here he shares all sorts of interesting details about how it works under the hood.
The system is built around the principle of separating storage from compute: storage uses S3, while compute runs in Firecracker:
Each transaction inside DSQL runs in a customized Postgres engine inside a Firecracker MicroVM, dedicated to your database. When you connect to DSQL, we make sure there are enough of these MicroVMs to serve your load, and scale up dynamically if needed. We add MicroVMs in the AZs and regions your connections are coming from, keeping your SQL query processor engine as close to your client as possible to optimize for latency.
We opted to use PostgreSQL here because of its pedigree, modularity, extensibility, and performance. We’re not using any of the storage or transaction processing parts of PostgreSQL, but are using the SQL engine, an adapted version of the planner and optimizer, and the client protocol implementation.
The system then provides strong repeatable-read transaction isolation using MVCC and EC2's high precision clocks, enabling reads "as of time X" including against nearby read replicas.
The storage layer supports index scans, which means the compute layer can push down some operations allowing it to load a subset of the rows it needs, reducing round-trips that are affected by speed-of-light latency.
The overall approach here is disaggregation: we’ve taken each of the critical components of an OLTP database and made it a dedicated service. Each of those services is independently horizontally scalable, most of them are shared-nothing, and each can make the design choices that is most optimal in its domain.
Link 2024-12-06 New Gemini model: gemini-exp-1206 [ https://substack.com/redirect/3781b193-2e20-479d-8da9-40220e15e33c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Google's Jeff Dean:
Today’s the one year anniversary of our first Gemini model releases! And it’s never looked better.
Check out our newest release, Gemini-exp-1206, in Google AI Studio [ https://substack.com/redirect/9592d301-f6ec-473a-9381-870c8827c377?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the Gemini API!
I upgraded my llm-gemini plugin [ https://substack.com/redirect/31fa8d4e-f5f8-4148-b0be-60d911fa7c72?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to support the new model and released it as version 0.6 - you can install or upgrade it like this:
llm install -U llm-gemini

Running my SVG pelican on a bicycle [ https://substack.com/redirect/93b05cbc-4665-4716-8a5a-ce63c2761b8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] test prompt:
llm -m gemini-exp-1206 "Generate an SVG of a pelican riding a bicycle"

Provided this result, which is the best I've seen from any model [ https://substack.com/redirect/feb5ff95-4e4d-4539-88d0-9432c18485b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here's the full output [ https://substack.com/redirect/c7c34292-f90e-4f12-a92f-76041528c9b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - I enjoyed these two pieces of commentary from the model:
: Shapes the distinctive pelican beak, with an added line for the lower mandible.
[...]
transform="translate(50, 30)": This attribute on the pelican's  tag moves the entire pelican group 50 units to the right and 30 units down, positioning it correctly on the bicycle.
The new model is also currently in top place [ https://substack.com/redirect/b2b973a1-c8da-4ac8-a666-10b6c17cdd73?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on the Chatbot Arena [ https://substack.com/redirect/ae12afa9-d888-4cec-b0a6-31fa257425ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Update: a delightful bonus, here's what I got from the follow-up prompt:
llm -c "now animate it"
Transcript here [ https://substack.com/redirect/1cfc08ac-6200-4e4d-a30d-fab91098867a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-12-06 Meta AI release Llama 3.3 [ https://substack.com/redirect/027b9bab-bb44-4d90-a5eb-06412bded6cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This new Llama-3.3-70B-Instruct model [ https://substack.com/redirect/95cc52a6-77a1-4289-9ed9-7acb16ccd01f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from Meta AI makes some bold claims:
This model delivers similar performance to Llama 3.1 405B with cost effective inference that’s feasible to run locally on common developer workstations.
I have 64GB of RAM in my M2 MacBook Pro, so I'm looking forward to trying a slightly quantized GGUF of this model to see if I can run it while still leaving some memory free for other applications.
Update: Ollama have a 43GB GGUF [ https://substack.com/redirect/012cdbb2-c0d0-4ec7-8c0f-f68431b97658?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] available now. And here's an MLX 8bit version [ https://substack.com/redirect/119008b5-cbf4-4a25-83f9-cb85029ed422?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and other MLX quantizations [ https://substack.com/redirect/35e9c69d-65ef-4ed7-9c31-261f3cea8138?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Llama 3.3 has 70B parameters, a 128,000 token context length and was trained to support English, German, French, Italian, Portuguese, Hindi, Spanish, and Thai.
The model card [ https://substack.com/redirect/1afd521d-ae17-4cca-a654-05fcb13832a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] says that the training data was "A new mix of publicly available online data" - 15 trillion tokens with a December 2023 cut-off.
They used "39.3M GPU hours of computation on H100-80GB (TDP of 700W) type hardware" which they calculate as 11,390 tons CO2eq. I believe that's equivalent to around 20 fully loaded passenger flights from New York to London (at ~550 tons per flight [ https://substack.com/redirect/75f8c182-cb1a-47e7-8c0b-fa9a900029ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
Quote 2024-12-07
A test of how seriously your firm is taking AI: when o-1 (& the new Gemini) came out this week, were there assigned folks who immediately ran the model through internal, validated, firm-specific benchmarks to see how useful it as? Did you update any plans or goals as a result?
Or do you not have people (including non-technical people) assigned to test the new models? No internal benchmarks? No perspective on how AI will impact your business that you keep up-to-date?
No one is going to be doing this for organizations, you need to do it yourself.
Ethan Mollick [ https://substack.com/redirect/61157e55-25d0-458a-959b-b4e8f7d60276?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-12-07 Writing down (and searching through) every UUID [ https://substack.com/redirect/2dd08940-07c8-46d1-b90b-211e89125c6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Nolen Royalty built everyuuid.com [ https://substack.com/redirect/60868c24-748a-4250-80d1-75594c5a56b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and this write-up of how he built it is utterly delightful.
First challenge: infinite scroll.
Browsers do not want to render a window that is over a trillion trillion pixels high, so I needed to handle scrolling and rendering on my own.
That means implementing hot keys and mouse wheel support and custom scroll bars with animation... mostly implemented with the help of Claude.
The really fun stuff is how Nolen implemented custom ordering [ https://substack.com/redirect/76638c43-996b-45e9-89ad-f13a8d2f49b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - because "Scrolling through a list of UUIDs should be exciting!", but "it’d be disappointing if you scrolled through every UUID and realized that you hadn’t seen one. And it’d be very hard to show someone a UUID that you found if you couldn’t scroll back to the same spot to find it."
And if that wasn't enough... full text search [ https://substack.com/redirect/631b7a50-3658-42a9-bbe0-34d9746275ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]! How can you efficiently search (or at least pseudo-search) for text across 5.3 septillion values? The trick there turned out to be generating a bunch of valid UUIDv4s containing the requested string and then picking the one closest to the current position on the page.
TIL 2024-12-08 Publishing a simple client-side JavaScript package to npm with GitHub Actions [ https://substack.com/redirect/2eaaa543-3715-4ee6-9b04-2a94be015b01?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here's what I learned about publishing a single file JavaScript package to NPM for my Prompts.js [ https://substack.com/redirect/d95c0aad-6b1a-4bd0-9fed-b9375cb6a3cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project. …
Link 2024-12-08 Holotypic Occlupanid Research Group [ https://substack.com/redirect/5fa3816d-3ddb-4512-9951-81de153005ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I just learned about this delightful piece of internet culture via Leven Parker on TikTok [ https://substack.com/redirect/01129753-ab2a-4885-8fb1-794408a7562d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Occlupanids are the small plastic square clips used to seal plastic bags containing bread.
For thirty years (since 1994) John Daniel has maintained this website that catalogs them and serves as the basis of a wide ranging community of occlupanologists who study and collect these plastic bread clips.
There's an active subreddit, r/occlupanids [ https://substack.com/redirect/1da9615f-32e0-4009-b51c-e1209983396f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but the real treat is the meticulously crafted taxonomy with dozens of species split across 19 families, all in the class Occlupanida [ https://substack.com/redirect/4b76a2ae-c00d-4b76-891e-26077ca007be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Class Occlupanida (Occlu=to close, pan= bread) are placed under the Kingdom Microsynthera, of the Phylum Plasticae. Occlupanids share phylum Plasticae with “45” record holders, plastic juice caps, and other often ignored small plastic objects.
If you want to classify your own occlupanid there's even a handy ID guide [ https://substack.com/redirect/4b76a2ae-c00d-4b76-891e-26077ca007be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which starts with the shape of the "oral groove" in the clip.
Or if you want to dive deep down a rabbit hole, this YouTube video [ https://substack.com/redirect/03c95232-e376-4b98-b8dd-bfba6ffc1016?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by CHUPPL starts with Occlupanids and then explores their inventor Floyd Paxton's [ https://substack.com/redirect/0d942726-3221-4674-a4fc-ca4c5990167d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] involvement with the John Birch Society and eventually Yamashita's gold [ https://substack.com/redirect/a2c81922-762d-49a8-bcb0-6b1f56aff04d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-12-08 llm-openrouter 0.3 [ https://substack.com/redirect/099721fa-1f11-448a-9d2e-2e1881e61a0a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New release of my llm-openrouter [ https://substack.com/redirect/29d67b8c-ce53-4c2f-90cc-744bf2b34edd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin, which allows LLM [ https://substack.com/redirect/0ad4363b-6632-4a6d-bfc1-93608d1237df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to access models hosted by OpenRouter [ https://substack.com/redirect/2bf608ba-22c7-4b70-8fd0-275fd084a9f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quoting the release notes:
Enable image attachments for models that support images. Thanks, Adam Montgomery [ https://substack.com/redirect/c0a67311-595f-423a-8729-dd4c21fef475?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. #12 [ https://substack.com/redirect/69d10448-4267-4a7a-8722-4a8854ef0fa0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Provide async model access. #15 [ https://substack.com/redirect/314d8da2-14f8-4266-b43e-2499b1205741?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Fix documentation to list correct LLM_OPENROUTER_KEY environment variable. #10 [ https://substack.com/redirect/e4a50cd4-63fc-4657-847b-581292cf87ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEk0TkRnNE1Ea3NJbWxoZENJNk1UY3pNemMyTlRBMU1Dd2laWGh3SWpveE56WTFNekF4TURVd0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuaGlRNE9tTW9GZGZnSTZyZlRoOG1idWplU0piNkpISVAwRkFnOTVMa3MzOCIsInAiOjE1Mjg0ODgwOSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzMzNzY1MDUwLCJleHAiOjE3MzYzNTcwNTAsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.mXxpim-nD7G0R6h3AnRfQXZagMl0dK_n0ihBE3ySSKg?
