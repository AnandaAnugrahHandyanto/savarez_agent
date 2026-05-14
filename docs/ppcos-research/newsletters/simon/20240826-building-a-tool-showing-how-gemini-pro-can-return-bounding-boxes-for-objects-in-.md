# Building a tool showing how Gemini Pro can return bounding boxes for objects in images

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-08-26T22:44:35.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/building-a-tool-showing-how-gemini

In this newsletter:
Building a tool showing how Gemini Pro can return bounding boxes for objects in images
Plus 8 links and 3 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Building a tool showing how Gemini Pro can return bounding boxes for objects in images [ https://substack.com/redirect/34495fbc-2713-4041-ac64-44234d651ee9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-08-26
I was browsing through Google's Gemini documentation while researching how different multi-model LLM APIs work [ https://substack.com/redirect/21c66cfc-69fc-4618-bb6d-8c6944fd8029?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] when I stumbled across this note [ https://substack.com/redirect/4ac60958-0a2c-4b3e-837a-bcd41f8798b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the vision documentation:
You can ask the model for the coordinates of bounding boxes for objects in images. For object detection, the Gemini model has been trained to provide these coordinates as relative widths or heights in range [0,1], scaled by 1000 and converted to an integer. Effectively, the coordinates given are for a 1000x1000 version of the original image, and need to be converted back to the dimensions of the original image.
This is a pretty neat capability! OpenAI's GPT-4o and Anthropic's Claude 3 and Claude 3.5 models can't do this (yet).
I tried a few prompts using Google's Python library [ https://substack.com/redirect/45b9f319-6e19-4ffd-a402-e770cad1a788?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and got back what looked like bounding boxes!
>>> import google.generativeai as genai
>>> genai.configure(api_key="...")
>>> model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")
>>> import PIL.Image
>>> goats = PIL.Image.open("/tmp/goats.jpeg")
>>> prompt = 'Return bounding boxes around every goat, for each one return [ymin, xmin, ymax, xmax]'
>>> response = model.generate_content([goats, prompt])
print(response.text)
>>> print(response.text)
- [200, 90, 745, 527]
- [300, 610, 904, 937]
But how to verify that these were useful co-ordinates? I fired up Claude 3.5 Sonnet and started iterating on Artifacts [ https://substack.com/redirect/49600a85-4e47-4356-b08e-7d3bb5312a17?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] there to try and visualize those co-ordinates against the original image.
After some fiddling around, I built an initial debug tool [ https://substack.com/redirect/105f2ae3-11e4-41c0-b98c-75e49e64d37b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that I could paste co-ordinates into and select an image and see that image rendered.
A tool for prompting with an image and rendering the bounding boxes
I wrote the other day about Anthropic's new support for CORS headers [ https://substack.com/redirect/c412697d-eef5-47d5-848b-dd7cbe62791f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], enabling direct browser access to their APIs.
Google Gemini supports CORS as well! So do OpenAI, which means that all three of the largest LLM providers can now be accessed directly from the browser.
I decided to build a combined tool that could prompt Gemini 1.5 Pro with an image directly from the browser, then render the returned bounding boxes on that image.
The new tool lives here: https://tools.simonwillison.net/gemini-bbox [ https://substack.com/redirect/2a9dea55-1f88-4026-aded-29da35323024?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The first time you run a prompt it will ask you for a Gemini API key [ https://substack.com/redirect/4ccbbec7-2354-4469-bf38-1e34b42c48b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which it stores in your browser's localStorage. I promise not to add code that steals your keys in the future, but if you don't want to trust that you can grab a copy of the code [ https://substack.com/redirect/d2aa8f22-c8ee-4f6f-9831-741b0285af81?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], verify it and then run it yourself.
Building this tool with Claude 3.5 Sonnet
This is yet another example of a tool that I mostly built by prompting Claude 3.5 Sonnet. Here are some more [ https://substack.com/redirect/3038f43e-1fef-4e5e-af7d-4fa2daa573fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I started out with this lengthy conversation [ https://substack.com/redirect/35b5846a-88ba-45cc-9b85-e1b88c90561c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (transcript exported with this tool [ https://substack.com/redirect/495b49fd-6741-4045-b924-0b25de878147?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) to help build the original tool for opening an image and pasting in those bounding box coordinates. That sequence started like this:
Build an artifact where I can open an image from my browser and paste the following style of text into a textarea:
- [488, 945, 519, 999]
- [460, 259, 487, 307]
- [472, 574, 498, 612]

(The hyphens may not be there, so scan with a regex for [ num, num, num, num ])
Each of those represent [ymin, xmin, ymax, xmax] coordinates on the image - but they are numbers between 0 and 1000 so they correspond to the image is if it had been resized to 1000x1000
As soon as the coords are pasted the corresponding boxes should be drawn on the images, corrected for its actual dimensions
The image should be show with a width of 80% of the page
The boxes should be in different colours, and hovering over each box should show the original bounding box coordinates below the image
Once that tool appeared to be doing the right thing (I had to muck around with how the coordinates were processed a bunch) I used my favourite prompting trick to build the combined tool that called the Gemini API. I found this example [ https://substack.com/redirect/7b5e4499-e3a5-4eab-b931-67747be18bf5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that calls the @google/generative-ai [ https://substack.com/redirect/b93eda25-3cb4-48e2-84c7-f547d5e5c17a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] API from a browser, pasted the full example into Claude along with my previous bounding box visualization tool and had it combine them to achieve the desired result:
Based on that example text, build me an HTML page with Vanilla JS that loads the Gemini API from esm.run - it should have a file input and a textarea and a submit button - you attach an image, enter a prompt and then click the button and it does a Gemini prompt with that image and prompt and injects the returned result into a div on the page
Then this follow-up prompt:
now incorporate the logic from this tool (I pasted in that HTML too), such that when the response is returned from the prompt the image is displayed with any rendered bounding boxes
Dealing with image orientation bugs
Bounding boxes are fiddly things. The code I had produced above seemed to work... but in some of my testing the boxes didn't show up in quite the right place. Was this just Gemini 1.5 Pro being unreliable in how it returned the boxes? That seemed likely, but I had some nagging doubts.
On a hunch, I took an image [ https://substack.com/redirect/461406bf-d153-4509-b44a-9721ebf56b08?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that was behaving strangely, took a screenshot of it and tried that screenshot as a JPEG [ https://substack.com/redirect/9eedffc6-c7c7-46f3-af14-8bb66db39399?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The bounding boxes that came back were different - they appeared rotated!
I've seen this kind of thing before with photos taken on an iPhone. There's an obscure piece of JPEG metadata which can set the orientation on a photo, and some software fails to respect that.
Was that affecting my bounding box tool? I started digging into those photos to figure that out, using a combination of ChatGPT Code Interpreter (since that can read JPEG binary data using Python) and Claude Artifacts (to build me a visible UI for exploring my photos).
My hunch turned out to be correct: my iPhone photos included TIFF orientation metadata which the Gemini API appeared not to respect. As a result, some photos taken by my phone would return bounding boxes that were rotated 180 degrees.
My eventual fix was to take the image provided by the user, render it to a  element and then export it back out as a JPEG again - code here [ https://substack.com/redirect/b57d3e08-5de7-4298-96b5-65346a006c8b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I got Claude to add that for me based on code I pasted in from my earlier image resize quality [ https://substack.com/redirect/618f5ae0-d91f-43dc-93ec-c5746d537805?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool, also built for me by Claude [ https://substack.com/redirect/1c51b6cd-b3b7-471a-9e82-5270e2dd27b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
As part of this investigation I built another tool, which can read orientation TIFF data from a JPEG entirely in JavaScript and help show what's going on:
https://tools.simonwillison.net/tiff-orientation [ https://substack.com/redirect/ac3f73ac-9f7a-4985-9d18-5ec6638a1ad2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Here's the source code for that [ https://substack.com/redirect/2ce3c03c-9f01-4d87-aee7-dfb8f54b78e5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The source code is a great example of the kind of thing that LLMs can do much more effectively than I can - here's an illustrative snippet:
// Determine endianness
const endian = view.getUint16(tiffStart, false);
const isLittleEndian = (endian === 0x4949);  // 'II' in ASCII
debugInfo += `Endianness: ${isLittleEndian ? 'Little Endian' : 'Big Endian'}\n`;

// Check TIFF header validity
const tiffMagic = view.getUint16(tiffStart + 2, isLittleEndian);
if (tiffMagic !== 42) {
throw Object.assign(new Error('Not a valid TIFF header'), { debugInfo });
}
debugInfo += 'Valid TIFF header\n';

// Get offset to first IFD
const ifdOffset = view.getUint32(tiffStart + 4, isLittleEndian);
const ifdStart = tiffStart + ifdOffset;
debugInfo += `IFD start: ${ifdStart}\n`;
LLMs know their binary file formats, so I frequently find myself asking them to write me custom binary processing code like this.
Here's the Claude conversation [ https://substack.com/redirect/951ada0b-31fb-4bb8-9b62-cba3f740380e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I had to build that tool. After failing to get it to work several times I pasted in Python code that I'd built using ChatGPT Code Interpreter and prompted:
Here's Python code that finds it correctly:
Which turned out to provide the missing details to help it build me the JavaScript version I could run in my browser. Here's the ChatGPT conversation [ https://substack.com/redirect/23570173-508c-4fe6-b277-4ab2505bda9d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that got me that Python code.
Mixing up a whole bunch of models
This whole process was very messy, but it's a pretty accurate representation of my workflow when using these models. I used three different tools here:
Gemini 1.5 Pro and the Gemini API to take images and a prompt and return bounding boxes
Claude 3.5 Sonnet and Claude Artifacts to write code for working against that API and build me interactive tools for visualizing the results
GPT-4o and ChatGPT Code Interpreter to write and execute Python code to try and help me figure out what was going on with my weird JPEG image orientation bugs
I copied code between models a bunch of times too - pasting Python code written by GPT-4o into Claude 3.5 Sonnet to help it write the correct JavaScript for example.
How good is the code that I produced by the end of this all? It honestly doesn't matter very much to me: this is a very low-stakes project, where the goal was a single web page tool that can run a prompt through a model and visualize the response.
If I was writing code "for production" - for a long-term project, or code that I intended to package up and release as an open source library - I would sweat the details a whole lot more. But for this kind of exploratory and prototyping work I'm increasingly comfortable hacking away at whatever the models spit out until it achieves the desired effect.
Link 2024-08-23 Explain ACLs by showing me a SQLite table schema for implementing them [ https://substack.com/redirect/5ef54533-5121-4442-aaed-8a6753e30e2e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here’s an example transcript showing one of the common ways I use LLMs. I wanted to develop an understanding of ACLs - Access Control Lists - but I’ve found previous explanations incredibly dry. So I prompted Claude 3.5 Sonnet:
Explain ACLs by showing me a SQLite table schema for implementing them
Asking for explanations using the context of something I’m already fluent in is usually really effective, and an great way to take advantage of the weird abilities of frontier LLMs.
I exported the transcript to a Gist using my Convert Claude JSON to Markdown [ https://substack.com/redirect/cfb3aadb-32ec-4e76-9e2f-4b9c2b9e21f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool, which I just upgraded to support syntax highlighting of code in artifacts.
Link 2024-08-23 Top companies ground Microsoft Copilot over data governance concerns [ https://substack.com/redirect/2b414da2-e805-47bd-97c7-4917110b8b82?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Microsoft’s use of the term “Copilot” is pretty confusing these days - this article appears to be about Microsoft 365 Copilot [ https://substack.com/redirect/ff0d9089-6953-4ad8-8b6c-c75caea7081f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which is effectively an internal RAG chatbot with access to your company’s private data from tools like SharePoint.
The concern here isn’t the usual fear of data leaked to the model or prompt injection security concerns. It’s something much more banal: it turns out many companies don’t have the right privacy controls in place to safely enable these tools.
Jack Berkowitz (of Securiti, who sell a product designed to help with data governance):
Particularly around bigger companies that have complex permissions around their SharePoint or their Office 365 or things like that, where the Copilots are basically aggressively summarizing information that maybe people technically have access to but shouldn't have access to.
Now, maybe if you set up a totally clean Microsoft environment from day one, that would be alleviated. But nobody has that.
If your document permissions aren’t properly locked down, anyone in the company who asks the chatbot “how much does everyone get paid here?” might get an instant answer!
This is a fun example of a problem with AI systems caused by them working exactly as advertised.
This is also not a new problem: the article mentions similar concerns introduced when companies tried adopting Google Search Appliance [ https://substack.com/redirect/7d396cd7-529e-44a6-9936-7a00ac4a96e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for internal search more than twenty years ago.
Link 2024-08-24 Musing about OAuth and LLMs on Mastodon [ https://substack.com/redirect/8b2d638c-a1db-48df-9bf0-fc7e3393c192?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Lots of people are asking why Anthropic and OpenAI don't support OAuth, so you can bounce users through those providers to get a token that uses their API budget for your app.
My guess: they're worried malicious app developers would use it to trick people and obtain valid API keys.
Imagine a version of my dumb little write a haiku about a photo you take [ https://substack.com/redirect/f437b8da-9e02-4c09-9ea9-2e2bccfcb520?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] page which used OAuth, harvested API keys and then racked up hundreds of dollar bills against everyone who tried it out running illicit election interference campaigns or whatever.
I'm trying to think of an OAuth API that dishes out tokens which effectively let you spend money on behalf of your users and I can't think of any - OAuth is great for "grant this app access to data that I want to share", but "spend money on my behalf" is a whole other ball game.
I guess there's a version of this that could work: it's OAuth but users get to set a spending limit of e.g. $1 (maybe with the authenticating app suggesting what that limit should be).
Here's a counter-example from Mike Taylor [ https://substack.com/redirect/5b332d8f-bf76-4fde-a2c6-bdd87652a8b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of a category of applications that do use OAuth to authorize spend on behalf of users:
I used to work in advertising and plenty of applications use OAuth to connect your Facebook and Google ads accounts, and they could do things like spend all your budget on disinformation ads, but in practice I haven't heard of a single case. When you create a dev application there are stages of approval so you can only invite a handful of beta users directly until the organization and app gets approved.
In which case maybe the cost for providers here is in review and moderation: if you’re going to run an OAuth API that lets apps spend money on behalf of their users you need to actively monitor your developer community and review and approve their apps.
Quote 2024-08-24
[...] here’s what we found when we integrated [Amazon Q, GenAI assistant for software development] into our internal systems and applied it to our needed Java upgrades:
- The average time to upgrade an application to Java 17 plummeted from what’s typically 50 developer-days to just a few hours. We estimate this has saved us the equivalent of 4,500 developer-years of work (yes, that number is crazy but, real).
- In under six months, we've been able to upgrade more than 50% of our production Java systems to modernized Java versions at a fraction of the usual time and effort. And, our developers shipped 79% of the auto-generated code reviews without any additional changes.
Andy Jassy, Amazon CEO [ https://substack.com/redirect/2ee2ff62-89be-4c99-8fba-599a717d100d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-08-24 SQL Has Problems. We Can Fix Them: Pipe Syntax In SQL [ https://substack.com/redirect/8d348e21-64d8-442f-8730-30858ee0eebb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A new paper from Google Research describing custom syntax for analytical SQL queries that has been rolling out inside Google since February, reaching 1,600 "seven-day-active users" by August 2024.
A key idea is here is to fix one of the biggest usability problems with standard SQL: the order of the clauses in a query. Starting with SELECT instead of FROM has always been confusing, see SQL queries don't start with SELECT [ https://substack.com/redirect/390a96b9-7ea7-42a9-9e53-602489248f14?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Julia Evans.
Here's an example of the new alternative syntax, taken from the Pipe query syntax documentation [ https://substack.com/redirect/9a7e198b-a994-4a71-ad4c-a3a18caf251a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that was added to Google's open source ZetaSQL [ https://substack.com/redirect/3d91b58f-7247-4532-8db6-5b77fefb9657?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project last week.
For this SQL query:
SELECT component_id, COUNT(*)
FROM ticketing_system_table
WHERE
assignee_user.email = 'username@email.com'
AND status IN ('NEW', 'ASSIGNED', 'ACCEPTED')
GROUP BY component_id
ORDER BY component_id DESC;
The Pipe query alternative would look like this:
FROM ticketing_system_table
|> WHERE
assignee_user.email = 'username@email.com'
AND status IN ('NEW', 'ASSIGNED', 'ACCEPTED')
|> AGGREGATE COUNT(*)
GROUP AND ORDER BY component_id DESC;

The Google Research paper is released as a two-column PDF. I snarked about this [ https://substack.com/redirect/c9ad120b-965b-4d5b-869b-eb1c2690ddb8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hacker News:
Google: you are a web company. Please learn to publish your research papers as web pages.
This remains a long-standing pet peeve of mine. PDFs like this are horrible to read on mobile phones, hard to copy-and-paste from, have poor accessibility (see this Mastodon conversation [ https://substack.com/redirect/98d92f3e-37a9-4ea1-ac03-e2fda2c780f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and are generally just bad citizens of the web.
Having complained about this I felt compelled to see if I could address it myself. Google's own Gemini Pro 1.5 model can process PDFs, so I uploaded the PDF to Google AI Studio [ https://substack.com/redirect/d1b0f74d-69f8-4777-ad2f-53e86595e7c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and prompted the gemini-1.5-pro-exp-0801 model like this:
Convert this document to neatly styled semantic HTML
This worked surprisingly well. It output HTML for about half the document and then stopped, presumably hitting the output length limit, but a follow-up prompt of "and the rest" caused it to continue from where it stopped and run until the end.
Here's the result (with a banner I added at the top explaining that it's a conversion): Pipe-Syntax-In-SQL.html [ https://substack.com/redirect/0715e7e5-56cc-4976-8cb3-8eba606f332a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I haven't compared the two completely, so I can't guarantee there are no omissions or mistakes.
The figures from the PDF aren't present - Gemini Pro output tags like  but did nothing to help me create those images.
Amusingly the document ends with (A long list of references, which I won't reproduce here to save space.)

rather than actually including the references from the paper!
So this isn't a perfect solution, but considering it took just the first prompt I could think of it's a very promising start. I expect someone willing to spend more than the couple of minutes I invested in this could produce a very useful HTML alternative version of the paper with the assistance of Gemini Pro.
One last amusing note: I posted a link to this to Hacker News [ https://substack.com/redirect/7b6350bd-37ac-46ae-b95a-84777ed916d4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a few hours ago. Just now when I searched Google for the exact title of the paper my HTML version was already the third result!
I've now added a  tag to the top of the HTML to keep this unverified AI slop [ https://substack.com/redirect/e76ff0cc-91cd-423c-b42b-29074f6e4071?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] out of their search index. This is a good reminder of how much better HTML is than PDF for sharing information on the web!
Link 2024-08-25 My @covidsewage bot now includes useful alt text [ https://substack.com/redirect/1878db95-e1b1-48d8-b122-4bc635cf1326?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've been running a @covidsewage [ https://substack.com/redirect/a9713171-6f4d-4fe7-90ef-c64bf12eccfc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Mastodon bot for a while now, posting daily screenshots (taken with shot-scraper [ https://substack.com/redirect/8457df29-8a06-4e2e-ab1c-2ea3ba609d2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) of the Santa Clara County COVID in wastewater [ https://substack.com/redirect/aecd323d-9bd5-4308-af3d-4f230628e9e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] dashboard.
Prior to today the screenshot was accompanied by the decidedly unhelpful alt text "Screenshot of the latest Covid charts".
I finally fixed that today, closing issue #2 [ https://substack.com/redirect/10dc36b4-1358-47b9-92a7-c47886538c91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] more than two years after I first opened it.
The screenshot is of a Microsoft Power BI dashboard. I hoped I could scrape the key information out of it using JavaScript, but the weirdness of their DOM proved insurmountable.
Instead, I'm using GPT-4o - specifically, this Python code (run using a python -c block in the GitHub Actions YAML file):
import base64, openai
client = openai.OpenAI
with open('/tmp/covid.png', 'rb') as image_file:
encoded_image = base64.b64encode(image_file.read).decode('utf-8')
messages = [
{'role': 'system',
'content': 'Return the concentration levels in the sewersheds - single paragraph, no markdown'},
{'role': 'user', 'content': [
{'type': 'image_url', 'image_url': {
'url': 'data:image/png;base64,' + encoded_image
}}
]}
]
completion = client.chat.completions.create(model='gpt-4o', messages=messages)
print(completion.choices[0].message.content)
I'm base64 encoding the screenshot and sending it with this system prompt:
Return the concentration levels in the sewersheds - single paragraph, no markdown
Given this input image:
Here's the text that comes back:
The concentration levels of SARS-CoV-2 in the sewersheds from collected samples are as follows: San Jose Sewershed has a high concentration, Palo Alto Sewershed has a high concentration, Sunnyvale Sewershed has a high concentration, and Gilroy Sewershed has a medium concentration.
The full implementation can be found in the GitHub Actions workflow [ https://substack.com/redirect/d0756b82-465a-467e-b63f-34e6d3438945?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which runs on a schedule at 7am Pacific time every day.
Link 2024-08-26 AI-powered Git Commit Function [ https://substack.com/redirect/ba88fd87-334d-493b-abb5-2ad5c23d201a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Andrej Karpathy built a shell alias, gcm, which passes your staged Git changes to an LLM via my LLM [ https://substack.com/redirect/3e8af1a6-9225-4444-85bd-abfe59fb104c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool, generates a short commit message and then asks you if you want to "(a)ccept, (e)dit, (r)egenerate, or (c)ancel?".
Here's the incantation he's using to generate that commit message:
git diff --cached | llm "
Below is a diff of all staged changes, coming from the command:
```
git diff --cached
```
Please generate a concise, one-line commit message for these changes."
This pipes the data into LLM (using the default model, currently gpt-4o-mini unless you set it to something else [ https://substack.com/redirect/3ed2197c-cb3d-46fc-bee8-bf309ccc0c6f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and then appends the prompt telling it what to do with that input.
Link 2024-08-26 Long context prompting tips [ https://substack.com/redirect/33ab3020-2a5d-4759-bf09-cc09c07abd0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Interesting tips here from Anthropic's documentation about how to best prompt Claude to work with longer documents.
Put longform data at the top: Place your long documents and inputs (~20K+ tokens) near the top of your prompt, above your query, instructions, and examples. This can significantly improve Claude’s performance across all models. Queries at the end can improve response quality by up to 30% in tests, especially with complex, multi-document inputs.
It recommends using not-quite-valid-XML to add those documents to those prompts, and using a prompt that asks Claude to extract direct quotes before replying to help it focus its attention on the most relevant information:
Find quotes from the patient records and appointment history that are relevant to diagnosing the patient's reported symptoms. Place these in  tags. Then, based on these quotes, list all information that would help the doctor diagnose the patient's symptoms. Place your diagnostic information in  tags.
Link 2024-08-26 Anthropic Release Notes: System Prompts [ https://substack.com/redirect/cf5e0333-0e64-4516-8500-2a04969ff819?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthropic now publish the system prompts for their user-facing chat-based LLM systems - Claude 3 Haiku, Claude 3 Opus and Claude 3.5 Sonnet - as part of their documentation, with a promise to update this to reflect future changes.
Currently covers just the initial release of the prompts, each of which is dated July 12th 2024.
Anthropic researcher Amanda Askell broke down their system prompt in detail [ https://substack.com/redirect/932eb583-56ff-4ec2-ad29-3cbfece057b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back in March 2024. These new releases are a much appreciated extension of that transparency.
These prompts are always fascinating to read, because they can act a little bit like documentation that the providers never thought to publish elsewhere.
There are lots of interesting details in the Claude 3.5 Sonnet system prompt. Here's how they handle controversial topics:
If it is asked to assist with tasks involving the expression of views held by a significant number of people, Claude provides assistance with the task regardless of its own views. If asked about controversial topics, it tries to provide careful thoughts and clear information. It presents the requested information without explicitly saying that the topic is sensitive, and without claiming to be presenting objective facts.
Here's chain of thought "think step by step" processing baked into the system prompt itself:
When presented with a math problem, logic problem, or other problem benefiting from systematic thinking, Claude thinks through it step by step before giving its final answer.
Claude's face blindness is also part of the prompt, which makes me wonder if the API-accessed models might more capable of working with faces than I had previously thought:
Claude always responds as if it is completely face blind. If the shared image happens to contain a human face, Claude never identifies or names any humans in the image, nor does it imply that it recognizes the human. [...] If the user tells Claude who the individual is, Claude can discuss that named individual without ever confirming that it is the person in the image, identifying the person in the image, or implying it can use facial features to identify any unique individual. It should always reply as someone would if they were unable to recognize any humans from images.
It's always fun to see parts of these prompts that clearly hint at annoying behavior in the base model that they've tried to correct!
Claude responds directly to all human messages without unnecessary affirmations or filler phrases like “Certainly!”, “Of course!”, “Absolutely!”, “Great!”, “Sure!”, etc. Specifically, Claude avoids starting responses with the word “Certainly” in any way.
Anthropic note that these prompts are for their user-facing products only - they aren't used by the Claude models when accessed via their API.
Quote 2024-08-26
In 2021 we [the Mozilla engineering team] found “samesite=lax by default” isn’t shippable without what you call the “two minute twist” [ https://substack.com/redirect/fbf4fc0b-8970-4fe4-a26d-2c8a13e9cdc5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - you risk breaking a lot of websites. If you have that kind of two-minute exception, a lot of exploits that were supposed to be prevented remain possible.
When we tried rolling it out, we had to deal with a lot of broken websites: Debugging cookie behavior in website backends is nontrivial from a browser.
Firefox also had a prototype of what I believe is a better protection (including additional privacy benefits) already underway (called total cookie protection [ https://substack.com/redirect/7730a54d-2d81-4928-96f1-7ba5bfde15b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
Given all of this, we paused samesite lax by default development in favor of this.
Frederik Braun [ https://substack.com/redirect/bf395e01-cb5f-478a-a31c-8f91916aad88?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-08-26
We've read and heard that you'd appreciate more transparency as to when changes, if any, are made. We've also heard feedback that some users are finding Claude's responses are less helpful than usual. Our initial investigation does not show any widespread issues. We'd also like to confirm that we've made no changes to the 3.5 Sonnet model or inference pipeline.
Alex Albert [ https://substack.com/redirect/45055653-14dc-44aa-bff8-e2e6952b27e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORGd4TmpVMU9EWXNJbWxoZENJNk1UY3lORGN4TWpJNE5Td2laWGh3SWpveE56VTJNalE0TWpnMUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuY0Z3dDh6VXFSSWRaS0NfekpkM05ybHE2NzhURlhta0RtcGZweUNMb2IwQSIsInAiOjE0ODE2NTU4NiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzI0NzEyMjg1LCJleHAiOjE3MjczMDQyODUsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.3tdBIwFjPXO08EQwGPR7W09E88UkwYupQKpLfSeW0DU?
