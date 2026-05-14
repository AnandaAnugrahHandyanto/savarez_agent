# Trying out llama.cpp's new vision support

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-05-11T18:39:17.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/trying-out-llamacpps-new-vision-support

In this newsletter:
Trying out llama.cpp's new vision support
Plus 11 links and 3 quotations and 1 TIL and 3 notes
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Trying out llama.cpp's new vision support [ https://substack.com/redirect/09858936-dfac-4154-babd-4d59fcdbbc34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-05-10
This llama.cpp server vision support via libmtmd [ https://substack.com/redirect/7448c434-5cd0-4194-ac19-64ac47536a26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] pull request - via Hacker News [ https://substack.com/redirect/c546a671-f489-4c96-9ebc-680942d5a407?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - was merged earlier today. The PR finally adds full support for vision models to the excellent llama.cpp [ https://substack.com/redirect/61e44071-e596-4ecd-96d6-057bb39bfedf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project. It's documented on this page [ https://substack.com/redirect/cc90cfdf-9a0b-48cd-a50a-5996da0d75dd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but the more detailed technical details are covered here [ https://substack.com/redirect/f5023f86-0ddf-4260-ac44-a8c0748e0d1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here are my notes on getting it working on a Mac.
llama.cpp models are usually distributed as .gguf files. This project introduces a new variant of those called mmproj, for multimodal projector. libmtmd is the new library for handling these.
You can try it out by compiling llama.cpp from source, but I found another option that works: you can download pre-compiled binaries from the GitHub releases [ https://substack.com/redirect/902dfd2f-f735-4bd1-b2fe-57759e23a113?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
On macOS there's an extra step to jump through to get these working, which I'll describe below.
Update: it turns out the Homebrew package [ https://substack.com/redirect/a52e758b-94a4-4a48-aa60-4f89704e2f8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for llama.cpp turns things around extremely quickly. You can run brew install llama.cpp or brew upgrade llama.cpp and start running the below tools without any extra steps.
I downloaded the llama-b5332-bin-macos-arm64.zip file from this GitHub release [ https://substack.com/redirect/6537d0ca-5691-4fcb-8897-0a8c34daae46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and unzipped it, which created a build/bin directory.
That directory contains a bunch of binary executables and a whole lot of .dylib files. macOS wouldn't let me execute these files because they were quarantined. Running this command fixed that for the llama-mtmd-cli and llama-server executables and the .dylib files they needed:
sudo xattr -rd com.apple.quarantine llama-server llama-mtmd-cli *.dylib
Now I can run an interactive terminal LLM session using this command:
./llama-mtmd-cli -hf unsloth/gemma-3-4b-it-GGUF:Q4_K_XL
The first time this runs it fetches four files from unsloth/gemma-3-4b-it-GGUF [ https://substack.com/redirect/8e51535d-53c8-43bb-9e12-daa0a03e8065?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a quantized copy of Google DeepMind's Gemma 3 4B [ https://substack.com/redirect/24f74bf9-8276-4cb8-9946-8003b01fa5f0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - and stores them in ~/Library/Caches/llama.cpp:
2.4G unsloth_gemma-3-4b-it-GGUF_gemma-3-4b-it-UD-Q4_K_XL.gguf
217B unsloth_gemma-3-4b-it-GGUF_gemma-3-4b-it-UD-Q4_K_XL.gguf.json
812M unsloth_gemma-3-4b-it-GGUF_mmproj-F16.gguf
203B unsloth_gemma-3-4b-it-GGUF_mmproj-F16.gguf.json
Once they've downloaded an interactive session starts. You can chat directly with the model or use the /image path-to-image.jpg command to load an image into the context.
I loaded in a pelican photo [ https://substack.com/redirect/0bd7aede-2302-497b-8dd0-426ba4f17fd1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and prompted "describe it" and got back this:
It’s a striking photograph of a brown pelican standing in shallow water on a sandy beach. Here's a breakdown of what I see:
Subject: The main focus is a large brown pelican. It’s standing with its wings fully extended, creating a dramatic pose.
Pose: The pelican is in a slightly awkward, almost comical stance, with its legs planted firmly in the wet sand and its wings spread wide. It looks like it might be preparing to take off or is simply enjoying the water.
Color & Texture: The pelican is a rich, dark brown with lighter markings on its wings and head. The sand is a muted beige color, and the water reflects the sunlight, creating a shimmering effect. You can see the texture of the sand and the ripples in the water.
Lighting: The lighting appears to be bright and sunny, casting shadows and highlighting the details of the pelican's feathers.
Background: The background is blurred, suggesting a shallow depth of field, which keeps the focus on the pelican. It appears to be a beach scene.
Overall Impression: The image has a dynamic feel due to the pelican’s pose and the movement implied by the water. It’s a well-composed shot that captures a moment of wildlife in its natural habitat.
Do you want me to zoom in on a particular detail, or perhaps tell you more about pelicans?
Not bad for a 3.2GB model running on my laptop!
Running llama-server
Even more fun is the llama-server command [ https://substack.com/redirect/7f6c78bf-2c7c-4450-952b-1b9ec93fc8d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This starts a localhost web server running on port 8080 to serve the model, with both a web UI and an OpenAI-compatible API endpoint.
The command to run it is the same:
./llama-server -hf unsloth/gemma-3-4b-it-GGUF:Q4_K_XL
Now visit
http://localhost:8080
in your browser to start interacting with the model:
It miscounted the pelicans in the group photo [ https://substack.com/redirect/7016211a-c8c3-4c76-b67b-8c4745ea1533?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but again, this is a tiny 3.2GB model.
With the server running on port 8080 you can also access the OpenAI-compatible API endpoint. Here's how to do that using curl:
curl -X POST http://localhost:8080/v1/chat/completions \
-H "Content-Type: application/json" \
-d '{
"messages": [
{"role": "user", "content": "Describe a pelicans ideal corporate retreat"}
]
}' | jq
I built a new plugin for LLM just now called llm-llama-server [ https://substack.com/redirect/65d3aed5-48a9-47e4-b970-1007fbb93ca4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to make interacting with this API more convenient. You can use that like this:
llm install llm-llama-server
llm -m llama-server 'invent a theme park ride for a pelican'
Or for vision models use llama-server-vision:
llm -m llama-server-vision 'describe this image' -a https://static.simonwillison.net/static/2025/pelican-group.jpg
The LLM plugin uses the streaming API, so responses will stream back to you as they are being generated.
Link 2025-05-07 astral-sh/ty [ https://substack.com/redirect/be3b1876-cd3e-437c-838f-7e98f281dc46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Astral have been working on this "extremely fast Python type checker and language server, written in Rust" quietly but in-the-open [ https://substack.com/redirect/9a585f5e-12a8-4506-85e0-b9ec67ba9654?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for a while now. Here's the first alpha public release - albeit not yet announced [ https://substack.com/redirect/e5f1e167-3790-4f4a-91f2-01ec4bff399f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - as ty [ https://substack.com/redirect/6fafb2a3-423e-44e2-ae4f-9d0d5e225e9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on PyPI (nice donated [ https://substack.com/redirect/765ab408-0e0d-4f1d-8bce-2c1adb57c9b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] two-letter name!)
You can try it out via uvx [ https://substack.com/redirect/05398ee4-a34c-4c9b-b59a-e4e629d165d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this - run the command in a folder full of Python code and see what comes back:
uvx ty check
I got zero errors for my recent, simple condense-json [ https://substack.com/redirect/11c2187d-54a4-426a-96b4-fa153e9749b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library and a ton of errors for my more mature sqlite-utils [ https://substack.com/redirect/69cbc0e3-477f-4a0d-98ad-0b7358406662?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library - output here [ https://substack.com/redirect/8ab9f0df-9601-4b38-aa4d-0b9c5bd6ed20?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It really is fast:
cd /tmp
git clone https://github.com/simonw/sqlite-utils
cd sqlite-utils
time uvx ty check
Reports it running in around a tenth of a second (0.109 total wall time) using multiple CPU cores:
uvx ty check  0.18s user 0.07s system 228% cpu 0.109 total
Running time uvx mypy . in the same folder (both after first ensuring the underlying tools had been cached) took around 7x longer:
uvx mypy .  0.46s user 0.09s system 74% cpu 0.740 total
This isn't a fair comparison yet as ty still isn't feature complete in comparison to mypy.
Link 2025-05-07 llm-prices.com [ https://substack.com/redirect/73aea8f6-8754-4d10-8bd8-bf6399dc3a9b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've been maintaining a simple LLM pricing calculator since October last year [ https://substack.com/redirect/c4e44a28-6367-4425-a8ed-69cf8e824273?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I finally decided to split it out to its own domain name (previously it was hosted at tools.simonwillison.net/llm-prices), running on Cloudflare Pages.
The site runs out of my simonw/llm-prices [ https://substack.com/redirect/c8da60da-0601-4004-86b6-a3b5577563e4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] GitHub repository. I ported the history [ https://substack.com/redirect/513ac49a-30f0-4263-93ab-4424f411e4f6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the old llm-prices.html file using a vibe-coded bash script that I forgot to save anywhere.
I rarely use AI-generated imagery in my own projects, but for this one I found an excellent reason to use GPT-4o image outputs... to generate the favicon! I dropped a screenshot of the site into ChatGPT (o4-mini-high in this case) and asked for the following:
design a bunch of options for favicons for this site in a single image, white background
I liked the top right one, so I cropped it into Pixelmator and made a 32x32 version. Here's what it looks like in my browser:
I added a new feature just now: the state of the calculator is now reflected in the #fragment-hash URL of the page, which means you can link to your previous calculations.
I implemented that feature using the new gemini-2.5-pro-preview-05-06 [ https://substack.com/redirect/2e5c6e17-d5b4-4a1f-b949-91443b8be336?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], since that model boasts improved front-end coding abilities. It did a pretty great job - here's how I prompted it:
llm -m gemini-2.5-pro-preview-05-06 -f https://www.llm-prices.com/ -s 'modify this code so that the state of the page is reflected in the fragmenth hash URL - I want to capture the values filling out the form fields and also the current sort order of the table. These should be respected when the page first loads too. Update them using replaceHistory, no need to enable the back button.'
Here's the transcript [ https://substack.com/redirect/d36758e2-716e-4d0f-88c2-5d3f22151e9f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the commit updating the tool [ https://substack.com/redirect/f0af5a2b-9354-41db-9abc-a629c8707e48?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], plus an example link [ https://substack.com/redirect/fe737034-5bb9-45f3-a1d9-4f07c867e207?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] showing the new feature in action (and calculating the cost for that Gemini 2.5 Pro prompt at 16.8224 cents, after fixing the calculation [ https://substack.com/redirect/43635639-0832-4441-a96f-1d8fb6a81b73?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
Link 2025-05-07 Medium is the new large [ https://substack.com/redirect/e334ad8b-fabf-48b2-80c9-32c6fb93c066?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New model release from Mistral - this time closed source/proprietary. Mistral Medium claims strong benchmark scores similar to GPT-4o and Claude 3.7 Sonnet, but is priced at $0.40/million input and $2/million output - about the same price as GPT 4.1 Mini. For comparison [ https://substack.com/redirect/73aea8f6-8754-4d10-8bd8-bf6399dc3a9b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], GPT-4o is $2.50/$10 and Claude 3.7 Sonnet is $3/$15.
The model is a vision LLM, accepting both images and text.
More interesting than the price is the deployment model. Mistral Medium may not be open weights but it is very much available for self-hosting:
Mistral Medium 3 can also be deployed on any cloud, including self-hosted environments of four GPUs and above.
Mistral's other announcement today is Le Chat Enterprise [ https://substack.com/redirect/285e9206-887b-4fb3-9979-b587630b4689?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This is a suite of tools that can integrate with your company's internal data and provide "agents" (these look similar to Claude Projects or OpenAI GPTs), again with the option to self-host.
Is there a new open weights model coming soon? This note tucked away at the bottom of the Mistral Medium 3 announcement seems to hint at that:
With the launches of Mistral Small [ https://substack.com/redirect/b8a5c8dc-afea-4e3c-b382-0b7ccc8dcfa7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in March and Mistral Medium today, it's no secret that we're working on something 'large' over the next few weeks. With even our medium-sized model being resoundingly better than flagship open source models such as Llama 4 Maverick, we're excited to 'open' up what's to come :)
I released llm-mistral 0.12 [ https://substack.com/redirect/53ed1d53-47c2-46ab-bfe7-50346ebb235c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adding support for the new model.
Link 2025-05-07 Create and edit images with Gemini 2.0 in preview [ https://substack.com/redirect/fb92f3c3-0f0d-4a9d-b548-da42f0b2f28e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Gemini 2.0 Flash has had image generation capabilities for a while now, and they're now available via the paid Gemini API - at 3.9 cents per generated image.
According to the API documentation [ https://substack.com/redirect/fe27d85f-a495-4c45-9657-de59754cd14c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] you need to use the new gemini-2.0-flash-preview-image-generation model ID and specify {"responseModalities":["TEXT","IMAGE"]} as part of your request.
Here's an example that calls the API using curl (and fetches a Gemini key from the llm keys get store):
curl -s -X POST \
"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key=$(llm keys get gemini)" \
-H "Content-Type: application/json" \
-d '{
"contents": [{
"parts": [
{"text": "Photo of a raccoon in a trash can with a paw-written sign that says I love trash"}
]
}],
"generationConfig":{"responseModalities":["TEXT","IMAGE"]}
}' > /tmp/raccoon.json
Here's the response [ https://substack.com/redirect/6366be3a-d33a-48aa-834c-0004f6c7c907?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I got Gemini 2.5 Pro to vibe-code me [ https://substack.com/redirect/475a4908-b69a-4847-b19b-2b172a467b90?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a new debug tool [ https://substack.com/redirect/cfe8865c-0578-42b7-a9d1-1ef592e9fc5b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for visualizing that JSON. If you visit that tool and click the "Load an example" link you'll see the result of the raccoon image visualized:
The other prompt I tried was this one:
Provide a vegetarian recipe for butter chicken but with chickpeas not chicken and include many inline illustrations along the way
The result of that one was a 41MB JSON file [ https://substack.com/redirect/e7dfbc99-c35c-4109-ae78-877096f2127a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ](!) containing 28 images - which presumably cost over a dollar since images are 3.9 cents each.
Some of the illustrations it chose for that one were somewhat unexpected:
If you want to see that one you can click the "Load a really big example" link in the debug tool [ https://substack.com/redirect/cfe8865c-0578-42b7-a9d1-1ef592e9fc5b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], then wait for your browser to fetch and render the full 41MB JSON file.
The most interesting feature of Gemini (as with GPT-4o images) is the ability to accept images as inputs. I tried that out with this pelican photo [ https://substack.com/redirect/0bd7aede-2302-497b-8dd0-426ba4f17fd1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
cat > /tmp/request.json  /tmp/out.json
And now the pelican is wearing a hat:
Link 2025-05-07 Introducing web search on the Anthropic API [ https://substack.com/redirect/cf8fdd5d-dcea-4a24-840a-22d17ae47256?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic's web search [ https://substack.com/redirect/14e07873-589c-4b60-9ed4-e2f24d2bff63?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (presumably still powered by Brave [ https://substack.com/redirect/ba544b1b-16fe-40f6-9115-81845e1c9d37?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) is now also available through their API, in the shape of a new web search tool [ https://substack.com/redirect/3781c22a-ca13-4a10-9d1f-6ce8d4f65328?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] called web_search_20250305.
You can specify a maximum number of uses per prompt and you can also pass a list of disallowed or allowed domains, plus hints as to the user's current location.
Search results are returned in a format that looks similar to the Anthropic Citations API [ https://substack.com/redirect/e39717e7-924d-41e4-bcf8-55f47e542e16?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It's charged at $10 per 1,000 searches, which is a little more expensive than what the Brave Search API [ https://substack.com/redirect/a69e6b3b-2eab-44de-8608-acb4838740da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] charges ($3 or $5 or $9 per thousand depending on how you're using them).
I couldn't find any details of additional rules surrounding storage or display of search results, which surprised me because both Google Gemini [ https://substack.com/redirect/528be30c-a1aa-4c4f-8897-e8e15767f3a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and OpenAI [ https://substack.com/redirect/2e6c1c2e-cc7d-4c07-b145-876d98cf52df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] have these for their own API search results.
Link 2025-05-08 llm-gemini 0.19.1 [ https://substack.com/redirect/39571f3c-e802-46a8-89a3-2ea894b4f5fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Bugfix release for my llm-gemini [ https://substack.com/redirect/165c9f0e-e2e9-4949-95b3-24e597245ccc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin, which was recording the number of output tokens (needed to calculate the price of a response) incorrectly for the Gemini "thinking" models. Those models turn out to return candidatesTokenCount and thoughtsTokenCount as two separate values which need to be added together to get the total billed output token count. Full details in this issue [ https://substack.com/redirect/271f0078-766b-49b1-8cb9-6c4d0ae6513a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I spotted this potential bug in this response log [ https://substack.com/redirect/3a235ee1-7cc3-4e54-81c5-b1a818d54b54?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] this morning, and my concerns were confirmed when Paul Gauthier wrote about a similar fix in Aider in Gemini 2.5 Pro Preview 03-25 benchmark cost [ https://substack.com/redirect/779821d5-34cd-490b-9077-e8e1ca81ed63?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], where he noted that the $6.32 cost recorded to benchmark Gemini 2.5 Pro Preview 03-25 was incorrect. Since that model is no longer available (despite the date-based model alias persisting [ https://substack.com/redirect/2e5c6e17-d5b4-4a1f-b949-91443b8be336?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) Paul is not able to accurately calculate the new cost, but it's likely a lot more since the Gemini 2.5 Pro Preview 05-06 benchmark cost $37.
I've gone through my gemini tag [ https://substack.com/redirect/6019112a-7eec-4c20-a772-70368d09bcb5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and attempted to update my previous posts with new calculations - this mostly involved increases in the order of 12.336 cents to 16.316 cents (as seen here [ https://substack.com/redirect/2e5c6e17-d5b4-4a1f-b949-91443b8be336?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
Quote 2025-05-08
But I’ve also had my own quiet concerns about what [vibe coding] means for early-career developers. So much of how I learned came from chasing bugs in broken tutorials and seeing how all the pieces connected, or didn’t. There was value in that. And maybe I’ve been a little protective of it.
A mentor challenged that. He pointed out that debugging AI generated code is a lot like onboarding into a legacy codebase, making sense of decisions you didn’t make, finding where things break, and learning to trust (or rewrite) what’s already there. That’s the kind of work a lot of developers end up doing anyway.
Ashley Willis [ https://substack.com/redirect/5cb87348-aeeb-4d4e-8467-0252e86f9f99?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-05-08
Microservices only pay off when you have real scaling bottlenecks, large teams, or independently evolving domains. Before that? You’re paying the price without getting the benefit: duplicated infra, fragile local setups, and slow iteration.
Oleg Pustovit [ https://substack.com/redirect/e3ae7dc1-9def-48d7-a228-fdf724c3070b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-05-08 Reservoir Sampling [ https://substack.com/redirect/4dc212f4-0319-4872-a291-1b017454209a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Yet another outstanding interactive essay by Sam Rose (previously [ https://substack.com/redirect/d2670ddf-33cd-4487-9fcf-18bb31359d6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), this time explaining how reservoir sampling can be used to select a "fair" random sample when you don't know how many options there are and don't want to accumulate them before making a selection.
Reservoir sampling is one of my favourite algorithms, and I've been wanting to write about it for years now. It allows you to solve a problem that at first seems impossible, in a way that is both elegant and efficient.
I appreciate that Sam starts the article with "No math notation, I promise." Lots of delightful widgets to interact with here, all of which help build an intuitive understanding of the underlying algorithm.
Sam shows how this algorithm can be applied to the real-world problem of sampling log files when incoming logs threaten to overwhelm a log aggregator.
The dog illustration is commissioned art [ https://substack.com/redirect/c7368def-3ecd-48b9-803f-e2807b29b69a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the MIT-licensed code is available on GitHub [ https://substack.com/redirect/0f5b3ffd-765c-4382-b7c9-8a1dfadd7925?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2025-05-08
If Claude is asked to count words, letters, and characters, it thinks step by step before answering the person. It explicitly counts the words, letters, or characters by assigning a number to each. It only answers the person once it has performed this explicit counting step. [...]
If Claude is shown a classic puzzle, before proceeding, it quotes every constraint or premise from the person’s message word for word before inside quotation marks to confirm it’s not dealing with a new variant. [...]
If asked to write poetry, Claude avoids using hackneyed imagery or metaphors or predictable rhyming schemes.
Claude's system prompt [ https://substack.com/redirect/8b79ac1a-10d8-4716-96d3-d4a3549573c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-05-08 SQLite CREATE TABLE: The DEFAULT clause [ https://substack.com/redirect/bf30b643-1756-4347-b9ab-693e139b15bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
If your SQLite create table statement includes a line like this:
CREATE TABLE alerts (
-- ...
alert_created_at text default current_timestamp
)
current_timestamp will be replaced with a UTC timestamp in the format 2025-05-08 22:19:33. You can also use current_time for HH:MM:SS and current_date for YYYY-MM-DD, again using UTC.
Posting this here because I hadn't previously noticed that this defaults to UTC, which is a useful detail. It's also a strong vote in favor of YYYY-MM-DD HH:MM:SS as a string format for use with SQLite, which doesn't otherwise provide [ https://substack.com/redirect/121af18a-3b28-4181-9b6c-44c816a8fe32?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a formal datetime type.
Link 2025-05-09 Gemini 2.5 Models now support implicit caching [ https://substack.com/redirect/9ace10fa-a069-46e0-8c01-cac40a3a5660?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I just spotted a cacheTokensDetails key in the token usage JSON while running a long chain of prompts [ https://substack.com/redirect/e15c08a3-8ce0-4fa3-b46d-24345ddb4790?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] against Gemini 2.5 Flash - despite not configuring caching myself:
{"cachedContentTokenCount": 200658, "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 204082}], "cacheTokensDetails": [{"modality": "TEXT", "tokenCount": 200658}], "thoughtsTokenCount": 2326}
I went searching and it turns out Gemini had a massive upgrade to their prompt caching earlier today:
Implicit caching directly passes cache cost savings to developers without the need to create an explicit cache. Now, when you send a request to one of the Gemini 2.5 models, if the request shares a common prefix as one of previous requests, then it’s eligible for a cache hit. We will dynamically pass cost savings back to you, providing the same 75% token discount. [...]
To make more requests eligible for cache hits, we reduced the minimum request size for 2.5 Flash to 1024 tokens and 2.5 Pro to 2048 tokens.
Previously you needed to both explicitly configure the cache and pay a per-hour charge to keep that cache warm.
This new mechanism is so much more convenient! It imitates how both DeepSeek [ https://substack.com/redirect/bc07b147-d0ce-4d8d-a1d9-e78b21912a55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and OpenAI [ https://substack.com/redirect/05c2cd62-2bdf-4d5f-a3ce-e380995e91c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] implement prompt caching, leaving Anthropic as the remaining large provider who require you to manually configure prompt caching [ https://substack.com/redirect/5aae7e5a-5a4d-4689-a9e0-6618b1c3b9fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to get it to work.
Gemini's explicit caching mechanism is still available. The documentation [ https://substack.com/redirect/a5c323a2-e216-4935-adc0-6bdecc509de2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] says:
Explicit caching is useful in cases where you want to guarantee cost savings, but with some added developer work.
With implicit caching the cost savings aren't possible to predict in advance, especially since the cache timeout within which a prefix will be discounted isn't described and presumably varies based on load and other circumstances outside of the developer's control.
Update: DeepMind's Philipp Schmid [ https://substack.com/redirect/cce462be-df89-4f81-a549-3dcb80aa677e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
There is no fixed time, but it's should be a few minutes.
Link 2025-05-09 sqlite-utils 4.0a0 [ https://substack.com/redirect/b8a4029c-41dd-4386-8b98-9a7d52862f1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New alpha release of sqlite-utils [ https://substack.com/redirect/69cbc0e3-477f-4a0d-98ad-0b7358406662?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], my Python library and CLI tool for manipulating SQLite databases.
It's the first 4.0 alpha because there's a (minor) backwards-incompatible change: I've upgraded the .upsert and .upsert_all methods to use SQLIte's UPSERT [ https://substack.com/redirect/7d16cde7-5c91-4a33-8127-493ce6810ecc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] mechanism, INSERT INTO ... ON CONFLICT DO UPDATE. Details in this issue [ https://substack.com/redirect/5c9497f0-0087-4acb-8264-ffdfa000eab1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
That feature was added to SQLite in version 3.24.0, released 2018-06-04. I'm pretty cautious about my SQLite version support since the underlying library can be difficult to upgrade, depending on your platform and operating system.
I'm going to leave the new alpha to bake for a little while before pushing a stable release. Since this is a major version bump I'm going to take the opportunity [ https://substack.com/redirect/0028d392-83fb-4023-80a0-c9e7f2cce5e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to see if there are any other minor API warts that I can clean up at the same time.
Note 2025-05-09 [ https://substack.com/redirect/5878c287-6f1c-4d77-9e4b-951b2546f08f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I had some notes in a GitHub issue thread in a private repository that I wanted to export as Markdown. I realized that I could get them using a combination of several recent projects.
Here's what I ran:
export GITHUB_TOKEN="$(llm keys get github)"
llm -f issue:https://github.com/simonw/todos/issues/170 \
-m echo --no-log | jq .prompt -r > notes.md
I have a GitHub personal access token stored in my LLM keys, for use with Anthony Shaw's llm-github-models [ https://substack.com/redirect/e1f1fdae-feda-4efd-b602-3c1beaac3f9b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin.
My own llm-fragments-github [ https://substack.com/redirect/42b041aa-0b8d-4ab4-ace3-bd027af0afd4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin expects an optional GITHUB_TOKEN environment variable, so I set that first - here's an issue [ https://substack.com/redirect/527c6238-b8e9-46bb-a022-dd4a59420080?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to have it use the github key instead.
With that set, the issue: fragment loader can take a URL to a private GitHub issue thread and load it via the API using the token, then concatenate the comments together as Markdown. Here's the code for that [ https://substack.com/redirect/34bcd6b7-a972-4802-82e9-199dc601b34d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Fragments are meant to be used as input to LLMs. I built a llm-echo [ https://substack.com/redirect/cd6749f7-aaea-4c07-9382-33a2f1f0cfa0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin recently which adds a fake LLM called "echo" which simply echos its input back out again.
Adding --no-log prevents that junk data from being stored in my LLM log database [ https://substack.com/redirect/cdbe9132-5d1b-4e09-94f5-f53e639cb354?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The output is JSON with a "prompt" key for the original prompt. I use jq .prompt to extract that out, then -r to get it as raw text (not a "JSON string").
... and I write the result to notes.md.
Link 2025-05-10 TIL: SQLite triggers [ https://substack.com/redirect/200841a2-9cf2-4fa5-9481-c2d727e014e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've been doing some work with SQLite triggers recently while working on sqlite-chronicle [ https://substack.com/redirect/2da99045-d287-4dd8-8ba9-1096e5670114?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and I decided I needed a single reference to exactly which triggers are executed for which SQLite actions and what data is available within those triggers.
I wrote this triggers.py [ https://substack.com/redirect/41a940e6-1dff-43a3-a8ef-6d2e46255703?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] script to output as much information about triggers as possible, then wired it into a TIL article using Cog [ https://substack.com/redirect/1440f3dd-6483-4436-b3ec-e57efa808f1a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The Cog-powered source code for the TIL article can be seen here [ https://substack.com/redirect/9d30ab72-6b26-4764-a839-e1a9763d5653?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Note 2025-05-10 [ https://substack.com/redirect/645e0288-1f1e-48b0-b824-4544401f02e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Poker Face season two just started on Peacock (the US streaming service). It's my favorite thing on TV right now. I've started threads on MetaFilter FanFare for episodes one [ https://substack.com/redirect/306eb1bd-a80a-4b1e-8076-fac4a67ca49b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], two [ https://substack.com/redirect/3d68f386-d81c-4834-a79c-9a64131f1431?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and three [ https://substack.com/redirect/4809a546-e41b-4dc8-8796-c9e0da7a9062?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Note 2025-05-11 [ https://substack.com/redirect/43e7dca6-8ef2-43dc-9db7-cf901866730a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Achievement unlocked: tap danced in the local community college dance recital.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOak16TkRNNU16a3NJbWxoZENJNk1UYzBOams0T0RjMk5Td2laWGh3SWpveE56YzROVEkwTnpZMUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuOE1yemZUdEpCaFlYaVZ1amtZNjhkN0p1Mk8wQWIxNFVveldPNDlJM1p1VSIsInAiOjE2MzM0MzkzOSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQ2OTg4NzY1LCJleHAiOjE3NDk1ODA3NjUsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.OzuxOGexH405Ajj1TUaTHFlp-nsBDgMWaod3yMGrRxk?
