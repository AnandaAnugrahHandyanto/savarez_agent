# Gemini 1.5 Flash-8B, FLUX 1.1 Python 3.13...

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-10-14T02:57:23.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/gemini-15-flash-8b-flux-11-python

34 links, 6 quotations and 4 TILs
Link 2024-10-03 Ask HN: What happens to ".io" TLD after UK gives back the Chagos Islands? [ https://substack.com/redirect/1536ab1a-a4ad-4b9b-8f16-f24977a9ae58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This morning on the BBC: UK will give sovereignty of Chagos Islands to Mauritius [ https://substack.com/redirect/3d32b212-25c3-4989-9037-87d9bb9e8a55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The Chagos Islands include the area that the UK calls the British Indian Ocean Territory [ https://substack.com/redirect/59dca338-035b-4c88-bf26-0e4a249f4d3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The .io ccTLD [ https://substack.com/redirect/50bec6de-b075-4e68-8042-514eebb5286f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] uses the ISO-3166 two-letter country code for that designation.
As the owner of datasette.io [ https://substack.com/redirect/2f280790-75b2-4925-b356-5d7c5f873f3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the question of what happens to that ccTLD is suddenly very relevant to me.
This Hacker News conversation has some useful information. It sounds like there's a very real possibility that .io could be deleted after a few years notice - it's happened before, for ccTLDs such as .zr for Zaire (which renamed to Democratic Republic of the Congo [ https://substack.com/redirect/d9e6de4d-04fe-4118-9308-75ad706de406?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in 1997, with .zr withdrawn in 2001) and .cs [ https://substack.com/redirect/ff69b316-6193-4483-a120-7bdfde4347b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Czechoslovakia, withdrawn in 1995.
Could .io change status to the same kind of TLD as .museum, unaffiliated with any particular geography? The convention is for two letter TLDs to exactly match ISO country codes, so that may not be an option.
Link 2024-10-03 Announcing FLUX1.1 [pro] and the BFL API [ https://substack.com/redirect/dba7a2ff-47a0-47ab-b733-6c158cdbe245?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
FLUX is the image generation model family from Black Forest Labs, a startup founded by members of the team that previously created Stable Diffusion.
Released today, FLUX1.1 [pro] continues the general trend of AI models getting both better and more efficient:
FLUX1.1 [pro] provides six times faster generation than its predecessor FLUX.1 [pro] while also improving image quality, prompt adherence, and diversity.
Black Forest Labs appear to have settled on a potentially workable business model: their smallest, fastest model FLUX.1 [schnell] is Apache 2 licensed. The next step up is FLUX.1 [dev] which is open weights for non-commercial use only. The [pro] models are closed weights, made available exclusively through their API or partnerships with other API providers.
I tried the new 1.1 model out using black-forest-labs/flux-1.1-pro [ https://substack.com/redirect/69004b39-c073-486e-913a-cba812a8e6b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Replicate just now. Here's my prompt:
Photograph of a Faberge egg representing the California coast. It should be decorated with ornate pelicans and sea lions and a humpback whale.
The FLUX models have a reputation for being really good at following complex prompts. In this case I wanted the sea lions to appear in the egg design rather than looking at the egg from the beach, but I imagine I could get better results if I continued to iterate on my prompt.
The FLUX models are also better at applying text than any other image models I've tried myself.
Quote 2024-10-03
At first, I struggled to understand why anyone would want to write this way. My dialogue with ChatGPT was frustratingly meandering, as though I were excavating an essay instead of crafting one. But, when I thought about the psychological experience of writing, I began to see the value of the tool. ChatGPT was not generating professional prose all at once, but it was providing starting points: interesting research ideas to explore; mediocre paragraphs that might, with sufficient editing, become usable. For all its inefficiencies, this indirect approach did feel easier than staring at a blank page; “talking” to the chatbot about the article was more fun than toiling in quiet isolation. In the long run, I wasn’t saving time: I still needed to look up facts and write sentences in my own voice. But my exchanges seemed to reduce the maximum mental effort demanded of me.
Cal Newport [ https://substack.com/redirect/fc88cb64-53aa-4dd7-96a5-38e83fa60323?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-03 Gemini 1.5 Flash-8B is now production ready [ https://substack.com/redirect/502b4918-c55b-48a6-9fb5-aaa9087554c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Gemini 1.5 Flash-8B is "a smaller and faster variant of 1.5 Flash" - and is now released to production, at half the price of the 1.5 Flash model.
It's really, really cheap:
$0.0375 per 1 million input tokens on prompts =3.11"
# dependencies = [
#     "feedparser",
#     "typer",
# ]
# ///

uv will download the required Python version and cache that as well.
Quote 2024-10-06
Students who use AI as a crutch don’t learn anything. It prevents them from thinking. Instead, using AI as co-intelligence is important because it increases your capabilities and also keeps you in the loop. […]
AI does so many things that we need to set guardrails on what we don’t want to give up. It’s a very weird, general-purpose technology, which means it will affect all kinds of things, and we’ll have to adjust socially.
Ethan Mollick [ https://substack.com/redirect/c79810ee-b2e8-44e5-9791-2ceef94d6338?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-06 SVG to JPG/PNG [ https://substack.com/redirect/a5dfe16c-1823-4016-b82a-9841201fc0b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The latest in my ongoing series [ https://substack.com/redirect/ddffd0a7-bbcc-4a11-91b0-9b10fedf9556?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of interactive HTML and JavaScript tools written almost entirely by LLMs. This one lets you paste in (or open-from-file, or drag-onto-page) some SVG and then use that to render a JPEG or PNG image of your desired width.
I built this using Claude 3.5 Sonnet, initially as an Artifact and later in a code editor since some of the features (loading an example image and downloading the result) cannot run in the sandboxed iframe Artifact environment.
Here's the full transcript [ https://substack.com/redirect/f49ec6bc-8ff5-4579-bcb8-5d10bb31252d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the Claude conversation I used to build the tool, plus a few commits [ https://substack.com/redirect/c20b8be1-da75-4274-830c-32aa033f6aa1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I later made by hand to further customize it.
The code itself [ https://substack.com/redirect/fc4bb770-2f56-48ff-bd9d-fd185faa9b80?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is mostly quite simple. The most interesting part is how it renders the SVG to an image, which (simplified) looks like this:
// First extract the viewbox to get width/height
const svgElement = new DOMParser.parseFromString(
svgInput, 'image/svg+xml'
).documentElement;
let viewBox = svgElement.getAttribute('viewBox');
[, , width, height] = viewBox.split(' ').map(Number);
// Figure out the width/height of the output image
const newWidth = parseInt(widthInput.value) || 800;
const aspectRatio = width / height;
const newHeight = Math.round(newWidth / aspectRatio);
// Create off-screen canvas
const canvas = document.createElement('canvas');
canvas.width = newWidth;
canvas.height = newHeight;
// Draw SVG on canvas
const svgBlob = new Blob([svgInput], {type: 'image/svg+xml;charset=utf-8'});
const svgUrl = URL.createObjectURL(svgBlob);
const img = new Image;
const ctx = canvas.getContext('2d');
img.onload = function {
ctx.drawImage(img, 0, 0, newWidth, newHeight);
URL.revokeObjectURL(svgUrl);
// Convert that to a JPEG
const imageDataUrl = canvas.toDataURL("image/jpeg");
const convertedImg = document.createElement('img');
convertedImg.src = imageDataUrl;
imageContainer.appendChild(convertedImg);
};
img.src = svgUrl;
Here's the MDN explanation of that revokeObjectURL method [ https://substack.com/redirect/eb136781-21b6-4e11-b8ea-5b5205a8f4f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which I hadn't seen before.
Call this method when you've finished using an object URL to let the browser know not to keep the reference to the file any longer.
Link 2024-10-07 VTracer [ https://substack.com/redirect/2c8cba7e-daae-4791-935e-7f5121d2691a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
VTracer is an open source library [ https://substack.com/redirect/bf9b155d-1a69-4f63-95fa-f03830e64587?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] written in Rust for converting raster images (JPEG, PNG etc) to vector SVG.
This VTracer web app provides access to a WebAssembly compiled version of the library, with a UI that lets you open images, tweak the various options and download the resulting SVG.
I heard about this today on Twitter [ https://substack.com/redirect/320eb732-a197-45f3-beb5-713809f81912?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in a reply to my tweet demonstrating a much, much simpler Image to SVG tool [ https://substack.com/redirect/c8804622-adcc-45f9-bd84-10ee3b16468d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I built with the help of Claude [ https://substack.com/redirect/fb758498-c338-4543-8898-6e3b889a5ba0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the handy imagetracerjs library [ https://substack.com/redirect/ce10fd45-acea-4885-9f18-da8b9dd96bb2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by András Jankovics.
Link 2024-10-07 fav.farm [ https://substack.com/redirect/364e992e-e49a-414b-b6d5-d14c55bec357?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Neat little site by Wes Bos: it serves SVG (or PNG for Safari [ https://substack.com/redirect/85686d30-7c59-40d2-b2cc-44a2334d2379?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) favicons of every Emoji, which can be added to any site like this:

The source code is on GitHub [ https://substack.com/redirect/3f9b72a3-a00a-45bd-acdc-1f33e9e4ee2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It runs on Deno and Deno Deploy, and recently added per-Emoji hit counters powered by the Deno KV store, implemented in db.ts [ https://substack.com/redirect/120153bd-9e11-4d79-92e6-af6cde310b68?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using this pattern:
export function incrementCount(emoji: string) {
const VIEW_KEY = [`favicon`, `${emoji}`];
return db.atomic.sum(
VIEW_KEY, 1n
).commit; // Increment KV by 1
}

Link 2024-10-07 Datasette 0.65 [ https://substack.com/redirect/4975c34e-fd4a-4fce-9f3d-2f55036c8ed5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Python 3.13 [ https://substack.com/redirect/775d2fab-e25d-4520-84e1-e0134f5ec48c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was released today, which broke compatibility with the Datasette 0.x series due to an issue with an underlying dependency. I've fixed that problem [ https://substack.com/redirect/e3d691b8-409d-4e50-b954-02287154e91d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by vendoring and fixing the dependency and the new 0.65 release works on Python 3.13 (but drops support for Python 3.8, which is EOL [ https://substack.com/redirect/0816adc8-0528-4e25-9681-4a1ffa5ae750?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this month). Datasette 1.0a16 added support for Python 3.13 last month [ https://substack.com/redirect/08f45d3c-551d-4ab3-a03e-2318384a8b60?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-10-07 What's New in Ruby on Rails 8 [ https://substack.com/redirect/bc1a1be7-e136-44ff-b83b-f49d5802241d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Rails 8 takes SQLite from a lightweight development tool to a reliable choice for production use, thanks to extensive work on the SQLite adapter and Ruby driver.
With the introduction of the solid adapters discussed above, SQLite now has the capability to power Action Cable, Rails.cache, and Active Job effectively, expanding its role beyond just prototyping or testing environments. [...]
Transactions default to IMMEDIATE mode to improve concurrency.
Also included in Rails 8: Kamal [ https://substack.com/redirect/dac9e42b-c3e9-4fba-a95d-2d9700e9db5c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a new automated deployment system by 37signals for self-hosting web applications on hardware or virtual servers:
Kamal basically is Capistrano for Containers, without the need to carefully prepare servers in advance. No need to ensure that the servers have just the right version of Ruby or other dependencies you need. That all lives in the Docker image now. You can boot a brand new Ubuntu (or whatever) server, add it to the list of servers in Kamal, and it’ll be auto-provisioned with Docker, and run right away.
More from the official blog post about the release [ https://substack.com/redirect/57f79ab7-4a5f-41f6-a132-75f3639573e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
At 37signals, we're building a growing suite of apps that use SQLite in production with ONCE [ https://substack.com/redirect/a5c9f0f0-a573-4df0-b305-42a136724ae1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. There are now thousands of installations of both Campfire [ https://substack.com/redirect/cbe310f4-10ac-435c-853f-1adcad77cd00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Writebook [ https://substack.com/redirect/8f5e949d-0e90-485f-9bdc-449681162a09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] running in the wild that all run SQLite. This has meant a lot of real-world pressure on ensuring that Rails (and Ruby) is working that wonderful file-based database as well as it can be. Through proper defaults like WAL and IMMEDIATE mode. Special thanks to Stephen Margheim for a slew of such improvements [ https://substack.com/redirect/be7e4ce9-5038-4604-98a9-d0da0036846f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Mike Dalessio for solving a last-minute SQLite file corruption issue [ https://substack.com/redirect/889497f3-cbc8-4ff8-837b-cb1e9893a857?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the Ruby driver.
Link 2024-10-07 What's New In Python 3.13 [ https://substack.com/redirect/13c3650e-13b8-4a57-9c5b-454704a91223?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It's Python 3.13 release day today. The big signature features are a better REPL [ https://substack.com/redirect/86ec132b-18ce-4d37-822a-1435e717a05d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with improved error messages, an option to run Python without the GIL [ https://substack.com/redirect/7b61ecb3-e3af-4c38-8c87-21626ed6112d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the beginnings of the new JIT [ https://substack.com/redirect/30493cdd-c928-4b46-aa60-26679788a534?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here are some of the smaller highlights I spotted while perusing the release notes.
iOS and Android are both now Tier 3 supported platforms [ https://substack.com/redirect/99a3e2a4-61c9-4e60-aaab-fec82983962f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], thanks to the efforts of Russell Keith-Magee and the Beeware [ https://substack.com/redirect/5789d4dc-75f0-4711-a028-fe598ef6e451?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project. Tier 3 means [ https://substack.com/redirect/7b78c4fa-5aa9-414c-b2b9-6635817c7448?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] "must have a reliable buildbot" but "failures on these platforms do not block a release". This is still a really big deal for Python as a mobile development platform.
There's a whole bunch of smaller stuff relevant to SQLite.
Python's dbm module [ https://substack.com/redirect/06fe1abe-4a5e-43a7-aae6-129c91633e8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] has long provided a disk-backed key-value store against multiple different backends. 3.13 introduces a new backend based on SQLite, and makes it the default.
>>> import dbm
>>> db = dbm.open("/tmp/hi", "c")
>>> db["hi"] = 1
The "c" option means "Open database for reading and writing, creating it if it doesn’t exist".
After running the above, /tmp/hi was a SQLite database containing the following data:
sqlite3 /tmp/hi .dump
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE Dict (
key BLOB UNIQUE NOT NULL,
value BLOB NOT NULL
);
INSERT INTO Dict VALUES(X'6869',X'31');
COMMIT;

The dbm.open function can detect which type of storage is being referenced. I found the implementation for that in the whichdb(filename) [ https://substack.com/redirect/eab2a44e-4b49-4d65-8375-f452b22af036?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] function.
I was hopeful that this change would mean Python 3.13 deployments would be guaranteed to ship with a more recent SQLite... but it turns out 3.15.2 is from November 2016 [ https://substack.com/redirect/c3cf20eb-c487-4ea2-b224-f3f8a6f0dab7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] so still quite old:
SQLite 3.15.2 or newer is required to build the sqlite3 extension module. (Contributed by Erlend Aasland in gh-105875 [ https://substack.com/redirect/b9c459d6-6a9e-4cda-8026-8d770cbe563a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
The conn.iterdump SQLite method now accepts an optional filter= keyword argument taking a LIKE pattern for the tables that you want to dump. I found the implementation for that here [ https://substack.com/redirect/e2a4c8d5-70f1-4ab1-9e63-9d4d4cb4c933?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
And one last change which caught my eye because I could imagine having code that might need to be updated to reflect the new behaviour:
pathlib.Path.glob and rglob now return both files and directories if a pattern that ends with "**" is given, rather than directories only. Add a trailing slash to keep the previous behavior and only match directories.
With the release of Python 3.13, Python 3.8 is officially end-of-life [ https://substack.com/redirect/4a80d3a6-52ab-47c4-b71d-3c01bd025581?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Łukasz Langa:
If you're still a user of Python 3.8, I don't blame you, it's a lovely version. But it's time to move on to newer, greater things. Whether it's typing generics in built-in collections, pattern matching, except*, low-impact monitoring, or a new pink REPL, I'm sure you'll find your favorite new feature in one of the versions we still support. So upgrade today!
Link 2024-10-07 Thoughts on the Treasurer Role at Tech NonProfits [ https://substack.com/redirect/9e2beccc-4e7a-4b64-96ec-ba32f79ff467?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Will Vincent, Django Software Foundation treasurer from 2020-2022, explains what’s involved in the non-profit role with the highest level of responsibility and trust.
Link 2024-10-08 Django Commons [ https://substack.com/redirect/38e26467-34c2-4e07-a835-82d7e0989004?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Django Commons is a really promising initiative started by Tim Schilling, aimed at the problem of keeping key Django community projects responsibly maintained on a long-term basis.
Django Commons is an organization dedicated to supporting the community's efforts to maintain packages. It seeks to improve the maintenance experience for all contributors; reducing the barrier to entry for new contributors and reducing overhead for existing maintainers.
I’ve stated recently that I’d love to see the Django Software Foundation take on this role - adopting projects and ensuring they are maintained long-term. Django Commons looks like it solves that exact problem, assuring the future of key projects beyond their initial creators.
So far the Commons has taken on responsibility for django-fsm-2 [ https://substack.com/redirect/113a64ad-4de8-479a-ab42-fbe1ff997fb7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], django-tasks-scheduler [ https://substack.com/redirect/7f4a6a34-f3f1-40ad-b28b-f96cbbb50eed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and, as-of this week, diango-typer [ https://substack.com/redirect/cfceaba8-9443-426f-b873-fcb48303054f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here’s Tim introducing the project [ https://substack.com/redirect/40b9227e-c21d-4ba2-a816-d89bb15e5893?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back in May. Thoughtful governance has been baked in from the start:
Having multiple administrators makes the role more sustainable, lessens the impact of a person stepping away, and shortens response time for administrator requests. It’s important to me that the organization starts with multiple administrators so that collaboration and documentation are at the forefront of all decisions.
Link 2024-10-08 Anthropic: Message Batches (beta) [ https://substack.com/redirect/2931bae6-feba-4a39-924d-10e843240c83?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic now have a batch mode, allowing you to send prompts to Claude in batches which will be processed within 24 hours (though probably much faster than that) and come at a 50% price discount.
This matches the batch models offered by OpenAI [ https://substack.com/redirect/fa403b83-a9e7-4d59-861f-eb206761ee6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and by Google Gemini [ https://substack.com/redirect/0addf1e4-7033-48c9-ad9c-177779759304?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], both of which also provide a 50% discount.
Link 2024-10-08 If we had $1,000,000… [ https://substack.com/redirect/c0d0635f-21ff-4afa-8d65-aa032cbd3b71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jacob Kaplan-Moss gave my favorite talk at DjangoCon this year, imagining what the Django Software Foundation could do if it quadrupled its annual income to $1 million and laying out a realistic path for getting there. Jacob suggests leaning more into large donors than increasing our small donor base:
It’s far easier for me to picture convincing eight or ten or fifteen large companies to make large donations than it is to picture increasing our small donor base tenfold. So I think a major donor strategy is probably the most realistic one for us.
So when I talk about major donors, who am I talking about? I’m talking about four major categories: large corporations, high net worth individuals (very wealthy people), grants from governments (e.g. the Sovereign Tech Fund run out of Germany), and private foundations (e.g. the Chan Zuckerberg Initiative, who’s given grants to the PSF in the past).
Also included: a TIL on Turning a conference talk into an annotated presentation [ https://substack.com/redirect/2e2c5396-3f91-4269-b460-f2eb5d48a388?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Jacob used my annotated presentation tool [ https://substack.com/redirect/4b898734-07d7-4bde-95a0-0d19a40d1c52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to OCR text from images of keynote slides, extracted a Whisper transcript from the YouTube livestream audio and then cleaned that up a little with LLM [ https://substack.com/redirect/b9edc278-f300-42b0-95fa-1674fc427270?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Claude 3.5 Sonnet ("Split the content of this transcript up into paragraphs with logical breaks. Add newlines between each paragraph.") before editing and re-writing it all into the final post.
TIL 2024-10-09 Collecting replies to tweets using JavaScript [ https://substack.com/redirect/e79357e4-42f3-4165-a918-fca9496c4555?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I ran a survey [ https://substack.com/redirect/8b999d01-0b71-4959-aa94-cb4f3f5017a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Twitter the other day to try and figure out what people mean when they use the term "agents" with respect to AI. …
TIL 2024-10-09 Upgrading Homebrew and avoiding the failed to verify attestation error [ https://substack.com/redirect/6affae2b-47eb-4975-9aa9-721d3153be1c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I managed to get my Homebrew installation back into shape today. The first problem I was having is that it complained that macOS Sequoia was unsupported: …
Link 2024-10-09 otterwiki [ https://substack.com/redirect/62f09a2c-23ef-4c26-a40a-b0b9ba4e79c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It's been a while since I've seen a new-ish Wiki implementation, and this one by Ralph Thesen is really nice. It's written in Python (Flask + SQLAlchemy + mistune [ https://substack.com/redirect/23911eb1-2cf6-4711-b905-63f294d4ff1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Markdown + GitPython [ https://substack.com/redirect/907fedef-c912-4ff4-ba33-a2a55ad32717?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and keeps all of the actual wiki content as Markdown files in a local Git repository.
The installation instructions [ https://substack.com/redirect/623151d9-4b02-4d84-974a-d2683cf9f7fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] are a little in-depth as they assume a production installation with Docker or systemd - I figured out this recipe [ https://substack.com/redirect/ff20bfd8-d941-4ff6-90f9-069a4e4eded1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for trying it locally using uv:
git clone https://github.com/redimp/otterwiki.git
cd otterwiki

mkdir -p app-data/repository
git init app-data/repository

echo "REPOSITORY='${PWD}/app-data/repository'" >> settings.cfg
echo "SQLALCHEMY_DATABASE_URI='sqlite:///${PWD}/app-data/db.sqlite'" >> settings.cfg
echo "SECRET_KEY='$(echo $RANDOM | md5sum | head -c 16)'" >> settings.cfg

export OTTERWIKI_SETTINGS=$PWD/settings.cfg
uv run --with gunicorn gunicorn --bind 127.0.0.1:8080 otterwiki.server:app

Link 2024-10-09 The Fair Source Definition [ https://substack.com/redirect/00cd1bb7-cb2c-4f7f-aace-379d563d6c70?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fail Source (fair.io [ https://substack.com/redirect/44081edc-6b89-450d-91cf-b658254ce524?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) is the new-ish initiative from Chad Whitacre and Sentry aimed at providing an alternative licensing philosophy that provides additional protection for the business models of companies that release their code.
I like that they're establishing a new brand for this and making it clear that it's a separate concept from Open Source. Here's their definition:
Fair Source is an alternative to closed source, allowing you to safely share access to your core products. Fair Source Software (FSS):
is publicly available to read;
allows use, modification, and redistribution with minimal restrictions to protect the producer’s business model; and
undergoes delayed Open Source publication (DOSP).
They link to the Delayed Open Source Publication [ https://substack.com/redirect/338d679f-6467-4415-9534-6a8144c731eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] research paper published by OSI in January [ https://substack.com/redirect/1f602717-ffc5-4b6e-a855-9538fd66b324?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. (I was frustrated that this is only available as a PDF, so I converted it to Markdown [ https://substack.com/redirect/ecdd3aba-1102-49f7-96e8-b0d041329274?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using Gemini 1.5 Pro so I could read it on my phone.)
The most interesting background I could find on Fair Source was this GitHub issues thread [ https://substack.com/redirect/52b651c2-de19-45ac-86ef-6634daa0ff52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], started in May, where Chad and other contributors fleshed out the initial launch plan over the course of several months.
Link 2024-10-09 Free Threaded Python With Asyncio [ https://substack.com/redirect/ac4aba57-0f1c-443f-8031-904cb09a1fd9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jamie Chang expanded my free-threaded Python experiment [ https://substack.com/redirect/764d8ab8-ec49-4fa6-baf5-e7a19b36d1aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from a few months ago to explore the interaction between Python's asyncio and the new GIL-free build of Python 3.13.
The results look really promising. Jamie says:
Generally when it comes to Asyncio, the discussion around it is always about the performance or lack there of. Whilst peroformance is certain important, the ability to reason about concurrency is the biggest benefit. [...]
Depending on your familiarity with AsyncIO, it might actually be the simplest way to start a thread.
This code for running a Python function in a thread really is very pleasant to look at:
result = await asyncio.to_thread(some_function, *args, **kwargs)

Jamie also demonstrates asyncio.TaskGroup [ https://substack.com/redirect/99cc5ff2-6a22-456a-bbf7-3fbe728fd530?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which makes it easy to execute a whole bunch of threads and wait for them all to finish:
async with TaskGroup as tg:
for _ in range(args.tasks):
tg.create_task(to_thread(cpu_bound_task, args.size))

Link 2024-10-09 Forums are still alive, active, and a treasure trove of information [ https://substack.com/redirect/92539251-9529-463a-8e30-65dbed36eee3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Chris Person:
When I want information, like the real stuff, I go to forums. Over the years, forums did not really get smaller, so much as the rest of the internet just got bigger. Reddit, Discord and Facebook groups have filled a lot of that space, but there is just certain information that requires the dedication of adults who have specifically signed up to be in one kind of community.
This is a very comprehensive directory of active forums.
Link 2024-10-10 Announcing Deno 2 [ https://substack.com/redirect/59ad4c2a-3673-47e1-b27c-d1c56476b52e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The big focus of Deno 2 is compatibility with the existing Node.js and npm ecosystem:
Deno 2 takes all of the features developers love about Deno 1.x — zero-config, all-in-one toolchain for JavaScript and TypeScript development, web standard API support, secure by default — and makes it fully backwards compatible with Node and npm (in ESM).
The npm support is documented here [ https://substack.com/redirect/6fc0f738-8925-4462-9bc0-d095a1b11605?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can write a script like this:
import * as emoji from "npm:node-emoji";
console.log(emoji.emojify(:sauropod: :heart:  npm));
And when you run it Deno will automatically fetch and cache the required dependencies:
deno run main.js

Another new feature that caught my eye was this:
deno jupyter now supports outputting images, graphs, and HTML
Deno has apparently shipped with a Jupyter notebook kernel [ https://substack.com/redirect/97ac3c6a-4674-4310-b198-42e604f0a6c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for a while, and it's had a major upgrade in this release.
Here's Ryan Dahl's demo [ https://substack.com/redirect/409ae083-7eef-42a3-ba6f-587539dd59d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the new notebook support in his Deno 2 release video.
I tried this out myself, and it's really neat. First you need to install the kernel:
deno juptyer --install

I was curious to find out what this actually did, so I dug around in the code [ https://substack.com/redirect/bdb1760f-fb96-4463-8116-4200678ce93e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and then further in the Rust runtimed dependency [ https://substack.com/redirect/4657a5b7-652d-46b1-a495-f5ff03092b60?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It turns out installing Jupyter kernels, at least on macOS, involves creating a directory in ~/Library/Jupyter/kernels/deno and writing a kernel.json file containing the following:
{
"argv": [
"/opt/homebrew/bin/deno",
"jupyter",
"--kernel",
"--conn",
"{connection_file}"
],
"display_name": "Deno",
"language": "typescript"
}
That file is picked up by any Jupyter servers running on your machine, and tells them to run deno jupyter --kernel ... to start a kernel.
I started Jupyter like this:
jupyter-notebook /tmp

Then started a new notebook, selected the Deno kernel and it worked as advertised:
import * as Plot from "npm:@observablehq/plot";
import { document, penguins } from "jsr:@ry/jupyter-helper";
let p = await penguins;

Plot.plot({
marks: [
Plot.dot(p.toRecords, {
x: "culmen_depth_mm",
y: "culmen_length_mm",
fill: "species",
}),
],
document,
});
TIL 2024-10-10 Livestreaming a community election event on YouTube [ https://substack.com/redirect/31acc6db-0ca8-441f-8eb7-bcfdbd443e7c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I live in El Granada, California. Wikipedia calls us a census designated place [ https://substack.com/redirect/34449c3d-74aa-4142-b3f1-84631d931e62?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - we don't have a mayor or city council. But we do have a Community Services District [ https://substack.com/redirect/4c4cb7f7-2e43-4bb8-b0cb-bc2e9be0b8e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - originally responsible for our sewers, and since 2014 also responsible for our parks. And we get to vote for the board members in the upcoming November election [ https://substack.com/redirect/7b93fb8b-fc23-4ae0-b6bf-4722a61470e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]! …
Link 2024-10-10 Bridging Language Gaps in Multilingual Embeddings via Contrastive Learning [ https://substack.com/redirect/031ed406-c68a-471c-bc8c-c7f5b8ca74a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Most text embeddings models suffer from a "language gap", where phrases in different languages with the same semantic meaning end up with embedding vectors that aren't clustered together.
Jina claim their new jina-embeddings-v3 [ https://substack.com/redirect/065630b5-18c4-4687-a3a2-8d9b2e209921?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (CC BY-NC 4.0, which means you need to license it for commercial use if you're not using their API [ https://substack.com/redirect/d589bcd5-fd0e-4881-a5c5-33a023591c0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) is much better on this front, thanks to a training technique called "contrastive learning".
There are 30 languages represented in our contrastive learning dataset, but 97% of pairs and triplets are in just one language, with only 3% involving cross-language pairs or triplets. But this 3% is enough to produce a dramatic result: Embeddings show very little language clustering and semantically similar texts produce close embeddings regardless of their language
Quote 2024-10-11
Providing validation, strength, and stability to people who feel gaslit and dismissed and forgotten can help them feel stronger and surer in their decisions. These pieces made me understand that journalism can be a caretaking profession, even if it is never really thought about in those terms. It is often framed in terms of antagonism. Speaking truth to power turns into being hard-nosed and removed from our subject matter, which so easily turns into be an asshole and do whatever you like.
This is a viewpoint that I reject. My pillars are empathy, curiosity, and kindness. And much else flows from that. For people who feel lost and alone, we get to say through our work, you are not. For people who feel like society has abandoned them and their lives do not matter, we get to say, actually, they fucking do. We are one of the only professions that can do that through our work and that can do that at scale.
Ed Yong [ https://substack.com/redirect/54c94e5e-e3ec-4699-a88f-06ccbb58cd76?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-11 HTML for People [ https://substack.com/redirect/4a3a243f-de9a-40a9-8f47-7ddcc147a46d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Blake Watson's brand new HTML tutorial, presented as a free online book (CC BY-NC-SA 4.0, on GitHub [ https://substack.com/redirect/a61b205d-2a33-429d-b9eb-acbc5e1fb9bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). This seems very modern and well thought-out to me. It focuses exclusively on HTML, skipping JavaScript entirely and teaching with Simple.css [ https://substack.com/redirect/0d4258e6-56f8-46da-be46-b8efb71cf327?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to avoid needing to dig into CSS while still producing sites that are pleasing to look at. It even touches on Web Components (described as Custom HTML tags [ https://substack.com/redirect/ceeffdc8-a4ea-40b2-a968-2a95dfe39c56?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) towards the end.
Quote 2024-10-11
The primary use of “misinformation” is not to change the beliefs of other people at all. Instead, the vast majority of misinformation is offered as a service for people to maintain their beliefs in face of overwhelming evidence to the contrary.
Mike Caulfield [ https://substack.com/redirect/6ff1f29b-f88a-4ecd-9c49-140e40b9d0df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-11 $2 H100s: How the GPU Bubble Burst [ https://substack.com/redirect/d096931e-b547-455e-af77-7cbfe03641e5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fascinating analysis from Eugene Cheah, founder of LLM hosting provider Featherless [ https://substack.com/redirect/88c94b4c-a790-42ea-aa74-72021bc1d7ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], discussing GPU economics over the past 12 months.
TLDR: Don’t buy H100s. The market has flipped from shortage ($8/hr) to oversupplied ($2/hr), because of reserved compute resales, open model finetuning, and decline in new foundation model co’s. Rent instead.
Link 2024-10-11 lm.rs: run inference on Language Models locally on the CPU with Rust [ https://substack.com/redirect/71a3462c-f113-46e5-b331-edbe75fc5bcb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Impressive new LLM inference implementation in Rust by Samuel Vitorino. I tried it just now on an M2 Mac with 64GB of RAM and got very snappy performance for this Q8 Llama 3.2 1B [ https://substack.com/redirect/e231d5df-457b-4605-b7ef-625e9913cbce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with Activity Monitor reporting 980% CPU usage over 13 threads.
Here's how I compiled the library and ran the model:
cd /tmp
git clone https://github.com/samuel-vitorino/lm.rs
cd lm.rs
RUSTFLAGS="-C target-cpu=native" cargo build --release --bin chat
curl -LO 'https://huggingface.co/samuel-vitorino/Llama-3.2-1B-Instruct-Q8_0-LMRS/resolve/main/tokenizer.bin?download=true'
curl -LO 'https://huggingface.co/samuel-vitorino/Llama-3.2-1B-Instruct-Q8_0-LMRS/resolve/main/llama3.2-1b-it-q80.lmrs?download=true'
./target/release/chat --model llama3.2-1b-it-q80.lmrs --show-metrics

That --show-metrics option added this at the end of a response:
Speed: 26.41 tok/s

It looks like the performance is helped by two key dependencies: wide [ https://substack.com/redirect/9dc57b40-cf8e-4547-9401-2fbcfb2ec099?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which provides data types optimized for SIMD operations and rayon [ https://substack.com/redirect/657b4c70-5f8b-4922-acc9-06e4fcf4440d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for running parallel iterators across multiple cores (used for matrix multiplication [ https://substack.com/redirect/22cc336c-d12a-4889-a299-112ffe075c88?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
(I used LLM and files-to-prompt to help figure this out [ https://substack.com/redirect/355941e7-865b-4dd3-a0e4-abf43f802ff2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
Link 2024-10-12 Cabel Sasser at XOXO [ https://substack.com/redirect/90bc47e4-bcd9-43ca-8373-99f8d66ac3d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I cannot recommend this talk highly enough for the way it ends. After watching the video dive into this new site [ https://substack.com/redirect/aade016b-7dce-442f-9f75-1ce47e4b3af8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that accompanies the talk - an online archive of the works of commercial artist Wes Cook. I too would very much love to see a full scan of The Lost McDonalds Satire Triptych [ https://substack.com/redirect/5a312dc7-0a32-4cfa-b81f-caab905c7962?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2024-10-12
Frankenstein is a terrific book partly based on how concerned people were about electricity. It captures our fears about the nature of being human but didn’t help anyone really come up with better policies for dealing with electricity. I worry that a lot of AI critics are doing the same thing.
James Cham [ https://substack.com/redirect/cf5a1b8a-6792-49a7-8c13-f3933723cc1a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-10-12
Carl Hewitt recently remarked that the question what is an agent? is embarrassing for the agent-based computing community in just the same way that the question what is intelligence? is embarrassing for the mainstream AI community. The problem is that although the term is widely used, by many people working in closely related areas, it defies attempts to produce a single universally accepted definition. This need not necessarily be a problem: after all, if many people are successfully developing interesting and useful applications, then it hardly matters that they do not agree on potentially trivial terminological details. However, there is also the danger that unless the issue is discussed, 'agent' might become a 'noise' term, subject to both abuse and misuse, to the potential confusion of the research community.
Michael Wooldridge [ https://substack.com/redirect/4d1578f2-46fe-470d-a407-8a658bd165f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-12 Python 3.13's best new features [ https://substack.com/redirect/04020ac6-ead3-49a9-ac97-f521ea5c620f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Trey Hunner highlights some Python 3.13 usability improvements I had missed, mainly around the new REPL.
Pasting a block of code like a class or function that includes blank lines no longer breaks in the REPL - particularly useful if you frequently have LLMs write code for you to try out.
Hitting F2 in the REPL toggles "history mode" which gives you your Python code without the REPL's >>> and ... prefixes - great for copying code back out again.
Creating a virtual environment with python3.13 -m venv .venv now adds a .venv/.gitignore file containing * so you don't need to explicitly ignore that directory. I just checked and it looks like uv venv implements the same trick [ https://substack.com/redirect/ac5ec641-625f-4c2a-ab3c-bcf5c6d2e686?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
And my favourite:
Historically, any line in the Python debugger prompt that started with a PDB command would usually trigger the PDB command, instead of PDB interpreting the line as Python code. [...]
But now, if the command looks like Python code, pdb will run it as Python code!
Which means I can finally call list(iterable) in my pdb seesions, where previously I've had to use [i for i in iterable] instead.
(Tip from Trey [ https://substack.com/redirect/241f60b6-47c4-47f5-a6f4-9863d63806e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: !list(iterable) and [*iterable] are good alternatives for pre-Python 3.13.)
Trey's post is also available as a YouTube video [ https://substack.com/redirect/d3a00ca3-6c1b-4d44-bc3c-671f5323e310?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-10-12 Perks of Being a Python Core Developer [ https://substack.com/redirect/8ab6bb81-06e7-48b5-85ac-1bb60d18bae1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Mariatta Wijaya provides a detailed breakdown of the exact capabilities and privileges that are granted to Python core developers - including commit access to the Python main, the ability to write or sponsor PEPs, the ability to vote on new core developers and for the steering council election and financial support from the PSF for travel expenses related to PyCon and core development sprints.
Not to be under-estimated is that you also gain respect:
Everyone’s always looking for ways to stand out in resumes, right? So do I. I’ve been an engineer for longer than I’ve been a core developer, and I do notice that having the extra title like open source maintainer and public speaker really make a difference. As a woman, as someone with foreign last name that nobody knows how to pronounce, as someone who looks foreign, and speaks in a foreign accent, having these extra “credentials” helped me be seen as more or less equal compared to other people.
Link 2024-10-12 jefftriplett/django-startproject [ https://substack.com/redirect/23e2fbbe-f3d5-44d0-b976-5537b7f8e312?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Django's django-admin startproject and startapp commands include a --template option [ https://substack.com/redirect/a1f8e2f4-6311-4865-b76c-df43aca195aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which can be used to specify an alternative template for generating the initial code.
Jeff Triplett actively maintains his own template for new projects, which includes the pattern that I personally prefer of keeping settings and URLs in a config/ folder [ https://substack.com/redirect/ff7eb27a-ea9f-489d-9e50-9f73d0139d74?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It also configures the development environment to run using Docker Compose.
The latest update adds support for Python 3.13, Django 5.1 and uv. It's neat how you can get started without even installing Django using uv run like this:
uv run --with=django django-admin startproject \
--extension=ini,py,toml,yaml,yml \
--template=https://github.com/jefftriplett/django-startproject/archive/main.zip \
example_project

Link 2024-10-13 PostgreSQL 17: SQL/JSON is here! [ https://substack.com/redirect/a2363ca5-49f8-4c65-a7db-c66c1448e030?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Hubert Lubaczewski dives into the new JSON features added in PostgreSQL 17, released a few weeks ago on the 26th of September [ https://substack.com/redirect/431cb5a3-57fb-4674-86ff-128e7a03cfbc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This is the latest in his long series [ https://substack.com/redirect/301dc340-3708-4469-b51d-e253cd028eb2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of similar posts about new PostgreSQL features.
The features are based on the new SQL:2023 [ https://substack.com/redirect/2269f00d-66a8-42a5-a2ea-63d108f77b81?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] standard from June 2023. If you want to actually read the specification for SQL:2023 it looks like you have to buy a PDF from ISO [ https://substack.com/redirect/a657620f-ead9-4202-8d08-f1d7fae780b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for 194 Swiss Francs (currently $226). Here's a handy summary by Peter Eisentraut: SQL:2023 is finished: Here is what's new [ https://substack.com/redirect/a2594b0e-30ca-4820-a59a-434e681cc0de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
There's a lot of neat stuff in here. I'm particularly interested in the json_table table-valued function, which can convert a JSON string into a table with quite a lot of flexibility. You can even specify a full table schema as part of the function call:
SELECT  FROM json_table(
'[{"a":10,"b":20},{"a":30,"b":40}]'::jsonb,
'$[]'
COLUMNS (
id FOR ORDINALITY,
column_a int4 path '$.a',
column_b int4 path '$.b',
a int4,
b int4,
c text
)
);
SQLite has solid JSON support already [ https://substack.com/redirect/89161fb4-6661-437a-84eb-cab579c0db25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and often imitates PostgreSQL features, so I wonder if we'll see an update to SQLite that reflects some aspects of this new syntax.
Link 2024-10-13 An LLM TDD loop [ https://substack.com/redirect/a5303413-4e04-4f3b-ab37-fda1eceb2d0d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Super neat demo by David Winterbottom, who wrapped my LLM [ https://substack.com/redirect/3529c56d-a159-453b-8fde-eac29f966294?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and files-to-prompt [ https://substack.com/redirect/cd6f4421-caee-4c16-b9e4-33a81794de30?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tools in a short Bash script [ https://substack.com/redirect/6d074e41-38ac-4241-8944-f091c648ad75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that can be fed a file full of Python unit tests and an empty implementation file and will then iterate on that file in a loop until the tests pass.
Link 2024-10-13 Zero-latency SQLite storage in every Durable Object [ https://substack.com/redirect/562f3858-4551-4df6-8bbc-df1c51670e55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Kenton Varda introduces the next iteration of Cloudflare's Durable Object [ https://substack.com/redirect/d050a913-1414-4531-aab8-93808df4344c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] platform, which recently upgraded from a key/value store to a full relational system based on SQLite.
For useful background on the first version of Durable Objects take a look at Cloudflare's durable multiplayer moat [ https://substack.com/redirect/f9d2f6db-4423-4096-8bcb-7cb78f92b03c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Paul Butler, who digs into its popularity for building WebSocket-based realtime collaborative applications.
The new SQLite-backed Durable Objects is a fascinating piece of distributed system design, which advocates for a really interesting way to architect a large scale application.
The key idea behind Durable Objects is to colocate application logic with the data it operates on. A Durable Object comprises code that executes on the same physical host as the SQLite database that it uses, resulting in blazingly fast read and write performance.
How could this work at scale?
A single object is inherently limited in throughput since it runs on a single thread of a single machine. To handle more traffic, you create more objects. This is easiest when different objects can handle different logical units of state (like different documents, different users, or different "shards" of a database), where each unit of state has low enough traffic to be handled by a single object
Kenton presents the example of a flight booking system, where each flight can map to a dedicated Durable Object with its own SQLite database - thousands of fresh databases per airline per day.
Each DO has a unique name, and Cloudflare's network then handles routing requests to that object wherever it might live on their global network.
The technical details are fascinating. Inspired by Litestream [ https://substack.com/redirect/8583bb3b-99fd-407b-881e-bc98ec9e194a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], each DO constantly streams a sequence of WAL entries to object storage - batched every 16MB or every ten seconds. This also enables point-in-time recovery for up to 30 days through replaying those logged transactions.
To ensure durability within that ten second window, writes are also forwarded to five replicas in separate nearby data centers as soon as they commit, and the write is only acknowledged once three of them have confirmed it.
The JavaScript API design is interesting too: it's blocking rather than async, because the whole point of the design is to provide fast single threaded persistence operations:
let docs = sql.exec(
SELECT title, authorId FROM documents
ORDER BY lastModified DESC
LIMIT 100
).toArray;

for (let doc of docs) {
doc.authorName = sql.exec(
"SELECT name FROM users WHERE id = ?",
doc.authorId).one.name;
}
This one of their examples deliberately exhibits the N+1 query pattern, because that's something SQLite is uniquely well suited to handling [ https://substack.com/redirect/746c0868-d86e-4f3a-8804-a05c20b8577f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The system underlying Durable Objects is called Storage Relay Service, and it's been powering Cloudflare's existing-but-different D1 SQLite system [ https://substack.com/redirect/cddd40e8-8e6f-4030-bf19-160cd17ef9e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for over a year.
I was curious as to where the objects are created. According to this [ https://substack.com/redirect/a08c4966-3ba5-4dcc-b882-03e60d3259bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (via Hacker News [ https://substack.com/redirect/20437163-8319-4617-bc87-89d62b32d278?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
Durable Objects do not currently change locations after they are created. By default, a Durable Object is instantiated in a data center close to where the initial get request is made. [...] To manually create Durable Objects in another location, provide an optional locationHint parameter to get.
And in a footnote:
Dynamic relocation of existing Durable Objects is planned for the future.
where.durableobjects.live [ https://substack.com/redirect/e90a555c-58cd-42b2-b00f-f464ac52d2d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a neat site that tracks where in the Cloudflare network DOs are created - I just visited it and it said:
This page tracks where new Durable Objects are created; for example, when you loaded this page from Half Moon Bay, a worker in San Jose, California, United States (SJC) created a durable object in San Jose, California, United States (SJC).

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEF4T1RVMU5EY3NJbWxoZENJNk1UY3lPRGczTkRZM01Td2laWGh3SWpveE56WXdOREV3TmpjeExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEubEpfUkhGclFzc0RQWmc5MHVVUFdmMVpnZmotTmZUcnEtWlhVNGVJU2sxNCIsInAiOjE1MDE5NTU0NywicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzI4ODc0NjcxLCJleHAiOjE3MzE0NjY2NzEsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.E5AwEZTkYetuaPf-7HKsoWfMUZJBadAIdDCFr__0ilE?
