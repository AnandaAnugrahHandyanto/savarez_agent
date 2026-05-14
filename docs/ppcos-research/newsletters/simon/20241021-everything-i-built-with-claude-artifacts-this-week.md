# Everything I built with Claude Artifacts this week

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-10-21T23:52:47.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/everything-i-built-with-claude-artifacts

In this newsletter:
Everything I built with Claude Artifacts this week
Running Llama 3.2 Vision and Phi-3.5 Vision on a Mac with mistral.rs
Plus 5 links and 4 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Everything I built with Claude Artifacts this week [ https://substack.com/redirect/b41065cc-c5b6-4ef9-963b-cc273a2e770f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-21
I'm a huge fan of Claude's Artifacts feature, which lets you prompt Claude [ https://substack.com/redirect/05ce3f32-6433-495a-a756-f523fdcf5801?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to create an interactive Single Page App (using HTML, CSS and JavaScript) and then view the result directly in the Claude interface, iterating on it further with the bot and then, if you like, copying out the resulting code.
I was digging around in my Claude activity export [ https://substack.com/redirect/44d033c8-f3bd-44e0-bbeb-f6e6ee618224?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (I built a claude-to-sqlite [ https://substack.com/redirect/f3e378a5-9550-4527-bb66-e4d59828a619?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool to convert it to SQLite I could explore it in Datasette [ https://substack.com/redirect/a87fa1bc-d19a-4206-b4cb-6f4608e1b66d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and decided to see how much I'd used artifacts in the past week [ https://substack.com/redirect/ec8ae087-480b-4f89-b94a-e5581fcbd356?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It was more than I expected!
Being able to spin up a full interactive application - sometimes as an illustrative prototype, but often as something that directly solves a problem - is a remarkably useful tool.
Here's most of what I've used Claude Artifacts for in the past seven days. I've provided prompts or a full transcript for nearly all of them.
URL to Markdown with Jina Reader [ https://substack.com/redirect/692a49d1-0618-4714-b776-2376aa5876ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
SQLite in WASM demo [ https://substack.com/redirect/4f10eff5-80d7-4743-b934-41c143f742ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Extract URLs [ https://substack.com/redirect/59000585-1f65-44ea-80d4-8f45cfda0a97?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Clipboard viewer [ https://substack.com/redirect/b0146d8e-57a7-4d41-9036-0ee44aebd959?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Pyodide REPL [ https://substack.com/redirect/f9440202-0bb5-44e3-82c0-6aca9e3dc517?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Photo Camera Settings Simulator [ https://substack.com/redirect/eaa3ac04-2347-47ef-bf17-271b7d92bd7d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
LLM pricing calculator [ https://substack.com/redirect/1ba96a4a-4234-4c29-b072-cb9660a51a4c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
YAML to JSON converter [ https://substack.com/redirect/f07f0b52-109e-4890-8ca2-b0ef7d714635?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
OpenAI Audio [ https://substack.com/redirect/915527d2-f082-430f-b8a2-f3a351293f38?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
QR Code Decoder [ https://substack.com/redirect/c1c90df1-80e3-43aa-b381-461cc96d303b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Image Converter and Page Downloader [ https://substack.com/redirect/a2430cd0-78a6-4e8b-a418-8f953540426a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
HTML Entity Escaper [ https://substack.com/redirect/bd355600-70e4-4b56-94f6-96b494b2d072?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
text-wrap-balance-nav [ https://substack.com/redirect/8081095e-dd8c-44fd-a7ca-7d8b5b350ab9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
ARES Phonetic Alphabet Converter [ https://substack.com/redirect/cf27e34a-359a-44a6-af50-45ab5234ddf9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
URL to Markdown with Jina Reader
I got frustrated at how hard it was to copy and paste the entire text of a web page into an LLM while using Mobile Safari. So I built a simple web UI that lets me enter a URL, calls the Jina Reader API [ https://substack.com/redirect/df4172a6-ccee-4551-aeee-1420ba5ae1f7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to generate Markdown (which uses Puppeteer under the hood) and gives me that Markdown with a convenient "Copy" button.
Try it out: https://tools.simonwillison.net/jina-reader [ https://substack.com/redirect/934ebade-a8c7-459d-bbee-724d0e5e854e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (Code [ https://substack.com/redirect/532e8014-b319-428e-91e9-ce662513412d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
I wrote more about that project here [ https://substack.com/redirect/71c4ccc8-c67f-4ecb-92ef-f2a3a0063b48?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
SQLite in WASM demo
A Hacker News conversation about SQLite's WASM build [ https://substack.com/redirect/c1f15ac2-0f47-411a-90f8-ab43fe854509?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] lead me to the @sqlite.org/sqlite-wasm [ https://substack.com/redirect/94128e97-d102-4fa4-90f2-551be88c6876?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] package on NPM, and I decided to knock together a quick interactive demo.
Try it out here: tools.simonwillison.net/sqlite-wasm [ https://substack.com/redirect/cdb41579-e286-4905-8d81-35536058b7ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Code [ https://substack.com/redirect/39112355-d098-4e76-b8bd-13ccf6ba379e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude transcript [ https://substack.com/redirect/a52c5dcd-2ff8-4b84-aee0-5d3d3374eeb8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Extract URLs
I found myself wanting to extract all of the underlying URLs that were linked to from a chunk of text on a web page. I realized the fastest way to do that would be to spin up an artifact that could accept rich-text HTML pastes and use an HTML parser to extract those links.
https://tools.simonwillison.net/extract-urls [ https://substack.com/redirect/bbf620ab-4fe5-4a7a-9e0d-0b7d8d42a7d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Code [ https://substack.com/redirect/fc6b6da0-41e6-451d-8909-e38b459a103b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude transcript [ https://substack.com/redirect/f93c08bf-b4c7-4f13-b322-645f6eefa0bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Clipboard viewer
Messing around with a tool that lets you paste in rich text reminded me that the browser clipboard API is a fascinating thing. I decided to build a quick debugging tool that would let me copy and paste different types of content (plain text, rich text, files, images etc) and see what information was available to me in the browser.
https://tools.simonwillison.net/clipboard-viewer [ https://substack.com/redirect/e1c8719c-4fc5-4f6d-9a28-64065de7adf3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Code [ https://substack.com/redirect/fe3505c7-0940-4b7c-9d25-56a8f5c9ef00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude transcript [ https://substack.com/redirect/36ca461a-1854-4b43-8dc8-d53ad2ff420b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Pyodide REPL
I didn't put a lot of effort into this one. While poking around with Claude Artifacts in the browser DevTools I spotted this CSP header:
content-security-policy: default-src https://www.claudeusercontent.com; script-src 'unsafe-eval' 'unsafe-inline' https://www.claudeusercontent.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net/pyodide/; connect-src https://cdn.jsdelivr.net/pyodide/; worker-src https://www.claudeusercontent.com blob:; style-src 'unsafe-inline' https://www.claudeusercontent.com https://cdnjs.cloudflare.com https://fonts.googleapis.com; img-src blob: data: https://www.claudeusercontent.com; font-src data: https://www.claudeusercontent.com; object-src 'none'; base-uri https://www.claudeusercontent.com; form-action https://www.claudeusercontent.com; frame-ancestors https://www.claudeusercontent.com https://claude.ai https://preview.claude.ai https://claude.site https://feedback.anthropic.com; upgrade-insecure-requests; block-all-mixed-content
The https://cdn.jsdelivr.net/pyodide/ in there caught my eye, because it suggested that the Anthropic development team had deliberately set it up so Pyodide [ https://substack.com/redirect/cda96e1e-afa0-42ea-870f-079dff2642a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Python compiled to WebAssembly - could be loaded in an artifact.
I got Claude to spin up a very quick demo to prove that this worked:
https://claude.site/artifacts/a3f85567-0afc-4854-b3d3-3746dd1a37f2 [ https://substack.com/redirect/0aef9851-b49d-462a-b41c-f88aa720626e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I've not bothered to extract this one to my own tools.simonwillison.net site yet because it's purely a proof of concept that Pyodide can load correctly in that environment.
Photo Camera Settings Simulator
I was out on a photo walk and got curious about whether or not JavaScript could provide a simulation of camera settings. I didn't get very far with this one (prompting on my phone while walking along the beach) - the result was buggy and unimpressive and I quickly lost interest. It did expose me to the Fabric.js [ https://substack.com/redirect/4aa3c6f9-e61f-4fec-8682-6bbca8c51edd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library for manipulating canvas elements though.
https://claude.site/artifacts/e645c231-8c13-4374-bb7d-271c8dd73825 [ https://substack.com/redirect/8f82640a-e66d-4bb5-888e-e982586f806c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
LLM pricing calculator
This one I did finish. I built this pricing calculator as part of my experiments with Video scraping using Google Gemini [ https://substack.com/redirect/467e2b5a-719d-4c52-b528-ca682873bbd9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], because I didn't trust my own calculations for how inexpensive Gemini was! Here are detailed notes [ https://substack.com/redirect/fb8fb9c0-5763-46c2-ac49-02600cd19c45?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on how I built that.
https://tools.simonwillison.net/llm-prices [ https://substack.com/redirect/ac56aaef-003e-462b-b135-8c063e9fd6b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
YAML to JSON converter
I wanted to remind myself how certain aspects of YAML syntax worked, so I span up a quick YAML to JSON converter tool that shows the equivalent JSON live as you type YAML.
https://claude.site/artifacts/ffeb439c-fc95-428a-9224-434f5f968d51 [ https://substack.com/redirect/912f4651-376d-4a3d-86da-8dba78e43e5d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
OpenAI Audio
This is my most interesting artifact of the week. I was exploring OpenAI's new Audio APIs and decided to see if I could get Claude to build we a web page that could request access to my microphone, record a snippet of audio, then base64 encoded that and send it to the OpenAI API.
Here are the full details on how I built this tool [ https://substack.com/redirect/93c8d5b9-d463-4d06-b79d-03292c5cae28?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
https://tools.simonwillison.net/openai-audio [ https://substack.com/redirect/d1bbf76e-78d5-4ae4-a5f5-ec61c62242f6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Claude Artifacts can't make API requests to external hosts directly, but it can still spin up enough of a working version that it's easy to take that, move it to different hosting and finish getting it working.
I wrote more about this API pattern in Building a tool showing how Gemini Pro can return bounding boxes for objects in images [ https://substack.com/redirect/08abb248-2431-4d8f-b0ef-1dafe33ff20f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
QR Code Decoder
I was in a meeting earlier this week where one of the participants shared a slide with a QR code (for joining a live survey tool). I didn't have my phone with me, so I needed a way to turn that QR code into a regular URL.
https://tools.simonwillison.net/qr [ https://substack.com/redirect/3fd4a408-35a7-4769-942a-58e34f6f43f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Knocking up this QR decoder in Claude Artifacts took just a few seconds:
Build an artifact (no react) that lets me paste in a QR code and displays the decoded information, with a hyperlink if necessary
[ ... ]
have a file open box that also lets you drag and drop and add a onpaste handler to the page that catches pasted images as well
Full conversation here [ https://substack.com/redirect/b5bda218-c1e6-45be-bf4c-b95e81aec9fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Image Converter and Page Downloader
Another very quick prototype. On Hacker News someone demonstrated a neat idea for a tool that let you drop photos onto a page and it would bake them into the page as base64 URLs such that you could "save as HTML" and get a self-contained page with a gallery.
I suggested they could add [ https://substack.com/redirect/107d34a4-dad0-4f53-aae6-a55c129cb3c5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a feature that generated a "Download link" with the new page baked in - useful on mobile phones that don't let you "Save as HTML" - and got Claude to knock up a quick prototype:
In this case I shared the code in a Gist [ https://substack.com/redirect/da1c5e9c-3207-4bfd-9319-4147c5473a8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and then used the new-to-me
https://gistpreview.github.io/?GIST_ID_GOES_HERE
trick to render the result:
https://gistpreview.github.io/?14a2c3ef508839f26377707dbf5dd329
gistpreview [ https://substack.com/redirect/7e50b15d-d436-4c6e-930f-abef65fdef4b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] turns out to be a really quick way to turn a LLM-generated demo into a page people can view.
Code [ https://substack.com/redirect/da1c5e9c-3207-4bfd-9319-4147c5473a8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude transcript [ https://substack.com/redirect/942992db-beea-4209-bfa7-3adbf2ecf689?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
HTML Entity Escaper
Another example of on-demand software: I needed to escape the HTML entities in a chunk of text on my phone, so I got Claude to build me a tool for that:
https://claude.site/artifacts/46897436-e06e-4ccc-b8f4-3df90c47f9bc [ https://substack.com/redirect/462f8abe-a2ab-4fe8-ad00-6039376375b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Here's the prompt I used:
Build an artifact (no react) where I can paste text into a textarea and it will return that text with all HTML entities - single and double quotes and less than greater than ampersand - correctly escaped. The output should be in a textarea accompanied by a "Copy to clipboard" button which changes text to "Copied!" for 1.5s after you click it. Make it mobile friendly
text-wrap-balance-nav
Inspired by Terence Eden [ https://substack.com/redirect/1e6b344b-f2cc-4551-b1d0-965c080a152b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I decided to do a quick experiment with the text-wrap: balance CSS property. I got Claude to build me an example nav bar with a slider and a checkbox. I wrote about that here [ https://substack.com/redirect/a12a0b24-df7b-4404-8ad9-48da6664548d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
https://tools.simonwillison.net/text-wrap-balance-nav [ https://substack.com/redirect/6b4cb91a-3953-4f9e-8d1f-95c85a89a7ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
ARES Phonetic Alphabet Converter
I was volunteering as a HAM radio communications operator for the Half Moon Bay Pumpkin Run [ https://substack.com/redirect/e55fae0c-ceac-40b7-91fb-de92b2604360?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and got nervous that I'd mess up using the phonetic alphabet - so I had Claude build me this tool:
https://claude.site/artifacts/aaadab20-968a-4291-8ce9-6435f6d53f4c [ https://substack.com/redirect/876f4276-9c72-476d-9ad8-52f16033e84c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Claude transcript here [ https://substack.com/redirect/758dcc06-09f6-4614-8de6-c77f678d47b3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Amusingly it built it in Python first, then switched to JavaScript after I reminded it that I wanted "an interactive web app".
This is so useful, and so much fun!
As you can see, I'm a heavy user of this feature - I just described 14 projects produced in a single week. I've been using artifacts since they were released on 20th June [ https://substack.com/redirect/be1d114f-e949-4f3a-91ba-5d5915dbbacf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (alongside the excellent Claude 3.5 Sonnet, still my daily-driver LLM) and I'm now at a point where I fire up a new interactive artifact several times a day.
I'm using artifacts for idle curiosity, rapid prototyping, library research and to spin up tools that solve immediate problems.
Most of these tools took less than five minutes to build. A few of the more involved ones took longer than that, but even the OpenAI Audio one took 11:55am to 12:07pm [ https://substack.com/redirect/6db48736-cf0f-4196-a756-c42d3f3d8046?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the first version and 12:18pm to 12:27pm [ https://substack.com/redirect/914577d2-f9af-4f63-ad06-1150696b32f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the second iteration - so 21 minutes total.
Take a look at my claude-artifacts [ https://substack.com/redirect/a9cfa232-78c5-4c4f-a10e-8839f77e3a95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tag for even more examples, including SVG to JPG/PNG [ https://substack.com/redirect/652a483e-ec5f-4d12-a057-b84b36a493fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Markdown and Math Live Renderer [ https://substack.com/redirect/4742102b-873b-4ee1-981b-1a06e08550ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Image resize and quality comparison [ https://substack.com/redirect/8b3c92c9-cab1-445c-87bd-7177c4648110?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I also have a dashboard [ https://substack.com/redirect/93040541-9135-48bb-9593-26a2a5e83728?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of every post that links to my tools.simonwillison.net [ https://substack.com/redirect/b9a4bf2d-e288-4c25-b093-651945fd6d34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] site, and the underlying simonw/tools [ https://substack.com/redirect/6145dfed-65d0-4e20-b5a6-2aaeb777ba4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] GitHub repo includes more unlisted tools, most of which link to their Claude conversation transcripts in their commit history.
I'm beginning to get a little frustrated at their limitations - in particular the way artifacts are unable to make API calls, submit forms or even link out to other pages. I'll probably end up spinning up my own tiny artifacts alternative based on everything I've learned about them so far.
If you're not using artifacts, I hope I've given you a sense of why they're one of my current favourite LLM-based tools.
Running Llama 3.2 Vision and Phi-3.5 Vision on a Mac with mistral.rs [ https://substack.com/redirect/a5b2178d-4512-4049-bcf6-fe13c4343801?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-10-19
mistral.rs [ https://substack.com/redirect/7c00a00b-2a10-48fa-813a-57fe69ff7ab0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is an LLM inference library written in Rust by Eric Buehler. Today I figured out how to use it to run the Llama 3.2 Vision and Phi-3.5 Vision models on my Mac.
Despite the name, it's not just for the Mistral family of models - like how llama.cpp has grown beyond Llama, mistral.rs has grown beyond Mistral.
I already have a Rust installation, so I checked out and compiled the library like this:
git clone https://github.com/EricLBuehler/mistral.rs.git
cd mistral.rs
cargo run --features metal --release -- -i --isq Q4K vision-plain -m lamm-mit/Cephalo-Llama-3.2-11B-Vision-Instruct-128k -a vllama

This downloaded around 20GB of model files to ~/.cache/huggingface/hub/models--lamm-mit--Cephalo-Llama-3.2-11B-Vision-Instruct-128k, loaded the model into memory and started a terminal-based chat session.
I ran this prompt:
\image https://niche-museums.imgix.net/pioneer-history.jpeg?w=1600&h=800&fit=crop&auto=compress  describe this image including any text
The prompt uses this image from my Niche Museums write-up of the Pioneer Memorial Museum [ https://substack.com/redirect/3bc67355-a7c6-4759-bc17-e2ef72804673?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I got back this response:
The image shows the exterior of the Daughters of Utah Pioneers (DUP) Museum, which is also known as the Pioneer Memorial Museum. The building is located in Salt Lake City, Utah, USA.
Visible in the image are:
The DUP Museum Building: The main structure of the museum is a prominent feature in the image. It is a two-story building with a rectangular shape and a flat roof. The exterior walls are made of brick or stone, giving it a classic and historic appearance.
Signage: Above the entrance, there is a sign that reads "Daughters of Utah Pioneers Museum" in bold letters. Below this sign, another sign indicates that the building is also known as the "Pioneer Memorial Museum."
Entrance: The main entrance to the museum is marked by a doorway with a decorative frame and a pair of large wooden doors.
Landscaping: The surrounding area around the museum appears well-maintained with neatly trimmed grass and some trees nearby.
Statue or Monument: In front of the museum, there is a small statue or monument that appears to be dedicated to pioneers or early settlers.
The Daughters of Utah Pioneers (DUP) Museum showcases historical artifacts and exhibits related to Utah's pioneer history, focusing on the experiences and contributions of early settlers in the region.
Note that the text it generates correctly describes the museum's content and identifies the museum as being located in Salt Lake City, neither of which are details that were displayed in the image itself.
Activity Monitor confirmed that this Metal build was using my GPU, and about 10GB of memory, while the prompt was running.
mistral.rs also provides a Python binding [ https://substack.com/redirect/bef8d5e3-e404-40cd-87e9-94658aaa3991?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which can be installed from PyPI but requires a Rust toolchain (I filed an issue requesting PyPI wheels [ https://substack.com/redirect/6dbca677-2f02-4062-b640-60c9b0a23434?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
pip install mistralrs-metal

I got an error running the Python Llama vision demo [ https://substack.com/redirect/8e07878d-6985-4bf8-8565-94752078d5d5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but the Phi 3.5 Vision example [ https://substack.com/redirect/2f6927e0-c3ee-44a5-92df-8fc8ccf1fa1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] worked as advertised. I modified that to enable streaming output and ran it against a photograph from Mendenhall's Museum of Gasoline Pumps & Petroliana [ https://substack.com/redirect/ec222a50-08f4-4ddc-9f1e-d8bf9c80e9d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
from mistralrs import Runner, Which, ChatCompletionRequest, VisionArchitecture

res = runner.send_chat_completion_request(
ChatCompletionRequest(
model="phi3v",
messages=[
{
"role": "user",
"content": [
{
"type": "image_url",
"image_url": {
"url": "https://niche-museums.imgix.net/mendenhalls-16.jpeg?w=1200&auto=compress"
},
},
{
"type": "text",
"text": "\nWhat is shown in this image? Write a detailed response analyzing the scene.",
},
],
}
],
max_tokens=1024,
presence_penalty=1.0,
top_p=0.1,
temperature=0.1,
stream=True,
)
)
for item in res:
print(item.choices[0].delta.content, end='')
Here's what It gave me:
The image captures a nostalgic scene of a vintage gas station, reminiscent of a bygone era. Dominating the left side of the frame is a red and white gas pump, standing tall and proud, its metallic surface gleaming under the soft light filtering through the wooden ceiling. Adjacent to it, a white and black gas canister stands ready for service, its presence adding to the authenticity of the setting.
On the right, a red and white gasoline sign hangs from the ceiling, its bold colors contrasting with the muted tones of the surroundings. Above it, a yellow and white gasoline sign is suspended, its vibrant hues drawing the eye upwards.
The floor beneath these relics of the past is a checkerboard pattern, a common design choice for gas stations of yesteryears. It provides a stark contrast to the smooth, unblemished surfaces of the gas pumps and canisters.
In the background, a variety of other signs and advertisements add to the eclectic mix of objects. They are a testament to the diverse range of products and services that were once available at this location.
Despite the passage of time, the gas station retains a certain charm, its vintage gas pumps and signs serving as a tangible link to a different era. The image is a snapshot of history, frozen in time, waiting to be discovered and appreciated by those who take the time to look closer.
This description looks fantastic at first glance, but if you review it carefully and compare it to the image you'll see that it's full of inaccuracies. The vibes of the description match the image but the actual details are definitely incorrect.
This model downloaded 7.7GB to ~/.cache/huggingface/hub/models--microsoft--Phi-3.5-vision-instruct - significantly smaller than Llama 3.2's 20GB. I wonder if that size difference helps explain the greater hallucination rate in Phi-3.5 Vision.
If you're running Python 3.10 on Apple Silicon you may be able to skip the Rust compiler by installing the wheel I built here:
pip install https://static.simonwillison.net/static/2024/mistralrs_metal-0.3.1-cp310-cp310-macosx_11_0_arm64.whl

Link 2024-10-20 You can use text-wrap: balance; on icons [ https://substack.com/redirect/1e6b344b-f2cc-4551-b1d0-965c080a152b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Neat CSS experiment from Terence Eden: the new text-wrap: balance [ https://substack.com/redirect/a22c7616-fdcf-45c1-be07-7d7178b3e315?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CSS property is intended to help make text like headlines display without ugly wrapped single orphan words, but Terence points out it can be used for icons too:
This inspired me to investigate if the same technique could work for text based navigation elements. I used Claude [ https://substack.com/redirect/31c8ed0a-0979-4882-86c8-be1c1080b28d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to build this interactive prototype [ https://substack.com/redirect/6b4cb91a-3953-4f9e-8d1f-95c85a89a7ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of a navigation bar that uses text-wrap: balance against a list of display: inline menu list items. It seems to work well!
My first attempt used display: inline-block which worked in Safari but failed in Firefox.
Notable limitation from that MDN article [ https://substack.com/redirect/a22c7616-fdcf-45c1-be07-7d7178b3e315?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Because counting characters and balancing them across multiple lines is computationally expensive, this value is only supported for blocks of text spanning a limited number of lines (six or less for Chromium and ten or less for Firefox)
So it's fine for these navigation concepts but isn't something you can use for body text.
Quote 2024-10-20
It feels like we’re at a bit of an inflection point for the Django community. [...] One of the places someone could have the most impact is by serving on the DSF Board. Like the community at large, the DSF is at a transition point: we’re outgrowing the “small nonprofit” status, and have the opportunity to really expand our ambition and reach. In all likelihood, the decisions the Board makes over the next year or two will define our direction and strategy for the next decade.
Jacob Kaplan-Moss [ https://substack.com/redirect/e156996e-b64c-4317-879b-f3fabfb4a87f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-10-20
Who called it “intellectual property problems around the acquisition of training data for Large Language Models” and not Grand Theft Autocomplete?
Jens Ohlig [ https://substack.com/redirect/666e9387-e041-4282-aca9-05b0bdb8b0a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-20 The 3 AI Use Cases: Gods, Interns, and Cogs [ https://substack.com/redirect/a9a5429e-424d-4354-968e-9373f7bbca48?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Drew Breunig introduces an interesting new framework for categorizing use cases of modern AI:
Gods refers to the autonomous, human replacement applications - I see that as AGI stuff that's still effectively science fiction.
Interns are supervised copilots. This is how I get most of the value out of LLMs at the moment, delegating tasks to them that I can then review, such as AI-assisted programming [ https://substack.com/redirect/848ef8dc-027f-4d92-83e4-28e169ec95cf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Cogs are the smaller, more reliable components that you can build pipelines and automations on top of without needing to review everything they do - think Whisper for transcriptions or maybe some limited LLM subtasks such as structured data extraction.
Drew also considers Toys as a subcategory of Interns: things like image generators, “defined by their usage by non-experts. Toys have a high tolerance for errors because they’re not being relied on for much beyond entertainment.”
Quote 2024-10-20
I really dislike the practice of replacing passwords with email “magic links”. Autofilling a password from my keychain happens instantly; getting a magic link from email can take minutes sometimes, and even in the fastest case, it’s nowhere near instantaneous. Replacing something very fast — password autofill — with something slower is just a terrible idea.
John Gruber [ https://substack.com/redirect/bed146ed-6411-4c78-a81c-24f2e236ca36?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-10-20 Knowledge Worker [ https://substack.com/redirect/33dbe793-e2e2-4b33-8355-184a7c74c2f0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Forrest Brazeal:
Last month, I performed a 30-minute show called "Knowledge Worker" for the incredible audience at Gene Kim's ETLS in Las Vegas.
The show included 7 songs about the past, present, and future of "knowledge work" - or, more specifically, how it's affecting us, the humans between keyboard and chair. I poured everything I've been thinking and feeling about AI for the last 2+ years into this show, and I feel a great sense of peace at having said what I meant to say.
Videos of all seven songs are included in the post, with accompanying liner notes. AGI (Artificial God Incarnate) [ https://substack.com/redirect/f83aaab0-5b38-407f-82b6-84779a188adf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a banger, and What’s Left for Me? (The AI Existential Crisis Song) [ https://substack.com/redirect/871926fc-e267-4f22-adbc-736e6362d33d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] captures something I've been trying to think through for a while.
Link 2024-10-21 Dashboard: Tools [ https://substack.com/redirect/c53c2124-bff6-47a1-b7c9-d16c2037e426?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I used Django SQL Dashboard [ https://substack.com/redirect/0ac8587f-2b81-493c-8410-853173795608?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to spin up a dashboard that shows all of the URLs to my tools.simonwillison.net [ https://substack.com/redirect/b9a4bf2d-e288-4c25-b093-651945fd6d34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] site that I've shared on my blog so far. It uses this (Claude assisted) regular expression in a PostgreSQL SQL query:
select distinct on (tool_url)
unnest(regexp_matches(
body,
'(
https://tools
.simonwillison.net/[^ sudoku.csv
python csv_to_requirements.py sudoku.csv requirements.in

That requirements.in file now contains lines like this for each of the filled-in cells:
sudoku_0_0 == 5
sudoku_1_0 == 3
sudoku_4_0 == 7

Then run uv pip compile to convert that into a fully fleshed out requirements.txt file that includes all of the resolved dependencies, based on the wheel files in the packages/ [ https://substack.com/redirect/d94feeca-a3ef-421c-9240-bd78cce95d03?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] folder:
uv pip compile \
--find-links packages/ \
--no-annotate \
--no-header \
requirements.in > requirements.txt

The contents of requirements.txt is now the fully solved board:
sudoku-0-0==5
sudoku-0-1==6
sudoku-0-2==1
sudoku-0-3==8
...

The trick is the 729 wheel files in packages/ - each with a name like sudoku_3_4-8-py3-none-any.whl. I decompressed that wheel and it included a sudoku_3_4-8.dist-info/METADATA file which started like this:
Name: sudoku_3_4
Version: 8
Metadata-Version: 2.2
Requires-Dist: sudoku_3_0 != 8
Requires-Dist: sudoku_3_1 != 8
Requires-Dist: sudoku_3_2 != 8
Requires-Dist: sudoku_3_3 != 8
...

With a !=8 line for every other cell on the board that cannot contain the number 8 due to the rules of Sudoku (if 8 is in the 3, 4 spot). Visualized:
So the trick here is that the Python dependency resolver (now lightning fast thanks to uv [ https://substack.com/redirect/ebcc8d47-ead9-4180-bd3e-5a1c78787a27?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) reads those dependencies and rules out every package version that represents a number in an invalid position. The resulting version numbers represent the cell numbers for the solution.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEExTkRBeU9Ea3NJbWxoZENJNk1UY3lPVFUxTkRjNE9Dd2laWGh3SWpveE56WXhNRGt3TnpnNExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuSl9HSmNSRmx4QTY4RXdocjBjN0hjVE9GdkczTUlBMkRabXJNOWtTUjhOVSIsInAiOjE1MDU0MDI4OSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzI5NTU0Nzg4LCJleHAiOjE3MzIxNDY3ODgsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.BPgz0T4m-xPB4oyiFldrQOfYq_YhwgVZRqBMnd5s_l0?
