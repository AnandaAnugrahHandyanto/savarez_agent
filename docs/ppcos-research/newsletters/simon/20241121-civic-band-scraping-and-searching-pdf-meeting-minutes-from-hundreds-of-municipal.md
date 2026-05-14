# Civic Band - scraping and searching PDF meeting minutes from hundreds of municipalities

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-11-21T06:04:34.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/civic-band-scraping-and-searching

In this newsletter:
Project: Civic Band - scraping and searching PDF meeting minutes from hundreds of municipalities
Notes from Bing Chat—Our First Encounter With Manipulative AI
Plus 18 links and 3 quotations
Project: Civic Band - scraping and searching PDF meeting minutes from hundreds of municipalities [ https://substack.com/redirect/982b3ed3-e57f-4e15-90a3-d76b0c535932?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-11-16
I interviewed Philip James [ https://substack.com/redirect/3096ffc2-acc8-4bf9-930c-6079327d4b8d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about Civic Band [ https://substack.com/redirect/35fbc2af-fbaa-4843-aad5-01bc384438ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], his "slowly growing collection of databases of the minutes from civic governments". Philip demonstrated the site and talked through his pipeline for scraping and indexing meeting minutes from many different local government authorities around the USA.
We recorded this conversation as part of yesterday's Datasette Public Office Hours session.
Civic Band [ https://substack.com/redirect/3b5847f6-e869-4242-8e11-8738443405ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The technical stack [ https://substack.com/redirect/284385f1-78d0-4cd7-8e6f-3d1b2554d2ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Scale and storage [ https://substack.com/redirect/9c471753-f145-4d68-86ed-3c5d43960543?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Future plans [ https://substack.com/redirect/66f71433-bd46-4810-9449-b0b058c33830?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Civic Band
Philip was inspired to start thinking more about local government after the 2016 US election. He realised that there was a huge amount of information about decisions made by local authorities tucked away in their meeting minutes,but that information was hidden away in thousands of PDF files across many different websites.
There was this massive backlog of basically every decision that had ever been made by one of these bodies. But it was almost impossible to discover because it lives in these systems where the method of exchange is a PDF.
Philip lives in Alameda, which makes its minutes available via this portal [ https://substack.com/redirect/2dca4e66-aaab-4ef3-b36c-9255d6bd66e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] powered by Legistar [ https://substack.com/redirect/d6e083ca-582e-4fef-9773-ec47b91954ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It turns out there are a small number of vendors that provide this kind of software tool, so once you've written a scraper for one it's likely to work for many others as well.
Here's the Civic Band portal for Alameda [ https://substack.com/redirect/0e82d751-4360-42e9-9a4e-758099af0277?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], powered by Datasette [ https://substack.com/redirect/f81791f4-a699-4c94-9a53-0d40cd0deb67?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It's running the datasette-search-all [ https://substack.com/redirect/6b5c20e2-ddfa-4bf0-861a-2bdb134f0a16?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin and has both tables configured for full-text search. Here's a search for housing [ https://substack.com/redirect/3e38e71a-5de0-48ab-bf9f-6681b06f0473?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The technical stack
The public Civic Band sites all run using Datasette in Docker Containers - one container per municipality. They're hosted on a single Hetzner [ https://substack.com/redirect/8f35dbb8-c722-4a9a-9ae0-880cd5113c75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] machine.
The ingestion pipeline runs separately from the main hosting environment, using a Mac Mini on Philp's desk at home.
OCR works by breaking each PDF up into images and then running Tesseract OCR [ https://substack.com/redirect/1f0d692a-07cc-4aa3-a94b-60f2f07cca40?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] against them directly on the Mac Mini. This processes in the order of 10,000 or less new pages of documents a day.
Philip treats PDF as a normalization target, because the pipeline is designed around documents with pages of text. In the rare event that a municipality publishes documents in another format such as .docx he converts them to PDF before processing.
PNG images of the PDF pages are served via a CDN, and the OCRd text is written to SQLite database files - one per municipality. SQLite FTS [ https://substack.com/redirect/49e1d891-571c-4f09-9d9f-eceeeb413399?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provides full-text search.
Scale and storage
The entire project currently comes to about 265GB on disk. The PNGs of the pages use about 350GB of CDN storage.
Most of the individual SQLite databases are very small. The largest is for Maui County [ https://substack.com/redirect/5e3d0d50-388a-414f-a4d5-cb721aa9e0d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which is around 535MB because that county has professional stenographers taking detailed notes for every one of their meetings.
Each city adds only a few documents a week so growth is manageable even as the number of cities grows.
Future plans
We talked quite a bit about a goal to allow users to subscribe to updates that match specific search terms.
Philip has been building out a separate site called Civic Observer to address this need, which will store searches and then execute the periodically using the Datasette JSON API, with a Django app to record state to avoid sending the same alert more than once.
I've had a long term ambition to build some kind of saved search alerts plugin for Datasette generally, to allow users to subscribe to new results for arbitrary SQL queries. My sqlite-chronicle [ https://substack.com/redirect/f781a315-9881-4622-b3f8-bd5dc405892c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library is part or that effort - it uses SQLite triggers to maintain version numbers for individual rows in a table, allowing you to query just the rows that have been inserted or modified since the version number last time you ran the query.
Philip is keen to talk to anyone who is interested in using Civic Band or helping expand it to even more cities. You can find him on the Datasette Discord [ https://substack.com/redirect/0e934bf5-7c47-4448-a7b9-cdf697f073a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Notes from Bing Chat—Our First Encounter With Manipulative AI [ https://substack.com/redirect/0b10e945-e1e3-45a6-835f-56fc7753aced?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-11-19
I participated in an Ars Live conversation with Benj Edwards of Ars Technica [ https://substack.com/redirect/24e2b9bf-1c7a-452a-b974-cce39631f299?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today, talking about that wild period of LLM history last year when Microsoft launched Bing Chat and it instantly started misbehaving, gaslighting and defaming people.
Here's the video [ https://substack.com/redirect/6353e04e-3e3e-494a-8620-415dcb7a9cea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of our conversation.
I ran the video through MacWhisper, extracted a transcript and used Claude [ https://substack.com/redirect/29d611cc-d336-4a0f-aaa3-ad85614ac69a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to identify relevant articles I should link to. Here's that background information to accompany the talk.
A rough timeline of posts from that Bing launch period back in February 2023:
Microsoft announces AI-powered Bing search and Edge browser [ https://substack.com/redirect/a3063fc7-6309-4d51-9e3f-88d1ebd3f7e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Benj Edwards, Feb 7, 2023
AI-powered Bing Chat spills its secrets via prompt injection attack [ https://substack.com/redirect/7a6a6593-778e-4414-99b1-b58b80bb3fbe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Benj Edwards, Feb 10, 2023
AI-powered Bing Chat loses its mind when fed Ars Technica article [ https://substack.com/redirect/fbd3b598-6024-4208-9b9c-679d4e517d13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Benj Edwards, Feb 14, 2023
Bing: “I will not harm you unless you harm me first” [ https://substack.com/redirect/a5e61fee-41dc-4398-b085-6c02d6d536b4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Simon Willison, Feb 15, 2023
Gareth Corfield: I'm beginning to have concerns for @benjedwards' virtual safety [ https://substack.com/redirect/c6b3bf56-f572-4420-a652-787156087070?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Twitter, Feb 15, 2023
A Conversation With Bing’s Chatbot Left Me Deeply Unsettled [ https://substack.com/redirect/9e6e8abc-33f5-4c88-a7f1-647b76c91b9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Kevin Roose, NYT, Feb 16, 2023
It is deeply unethical to give a superhuman liar the authority of a $1 trillion company or to imply that it is an accurate source of knowledge / And it is deeply manipulative to give people the impression that Bing Chat has emotions or feelings like a human [ https://substack.com/redirect/7c033e8a-b4f6-44ca-9748-bdfa8acc8746?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Benj on Twitter (now deleted), Feb 16 2023
Bing AI Flies Into Unhinged Rage at Journalist [ https://substack.com/redirect/f3d9fab2-597f-47fd-986c-7c29165c6ffb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Maggie Harrison Dupré, Futurism, Feb 17 2023
Other points that we mentioned:
this AI chatbot "Sidney" is misbehaving [ https://substack.com/redirect/5cc56fe0-edc5-4e5f-aea7-7a4d601d3d00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - amazing forum post from November 23, 2022 (a week before even ChatGPT had been released) from a user in India talking about their interactions with a secret preview of Bing/Sydney
Prompt injection attacks against GPT-3 [ https://substack.com/redirect/3f5ceb3e-4220-439c-be6b-07395692ef43?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - where I coined the term "prompt injection" in September 12 2022
Eight Things to Know about Large Language Models [ https://substack.com/redirect/7b4171d0-177d-4e70-bfd0-b00bd1b44baf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (PDF) is the paper where I first learned about sycophancy and sandbagging [ https://substack.com/redirect/3754f383-8e76-4176-b828-081036bfaa49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (in April 2023)
Claude’s Character [ https://substack.com/redirect/edfdceae-de0d-4b63-855b-5bcaae4081fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Anthropic talks about how they designed the personality for Claude - June 8 2023, my notes on that [ https://substack.com/redirect/a14bb4ad-738c-4bee-b938-b3fa1381c1f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Why ChatGPT and Bing Chat are so good at making things up [ https://substack.com/redirect/c05ba70d-b637-4917-a609-7ad1c82ca244?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in which Benj argues for the term "confabulation" in April 2023.
Link 2024-11-14 Releasing the largest multilingual open pretraining dataset [ https://substack.com/redirect/ba8a582b-15d2-48dc-bfad-b02c4d957251?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Common Corpus is a new "open and permissible licensed text dataset, comprising over 2 trillion tokens (2,003,039,184,047 tokens)" released by French AI Lab PleIAs.
This appears to be the largest available corpus of openly licensed training data:
926,541,096,243 tokens of public domain books, newspapers, and Wikisource content
387,965,738,992 tokens of government financial and legal documents
334,658,896,533 tokens of open source code from GitHub
221,798,136,564 tokens of academic content from open science repositories
132,075,315,715 tokens from Wikipedia, YouTube Commons, StackExchange and other permissively licensed web sources
It's majority English but has significant portions in French and German, and some representation for Latin, Dutch, Italian, Polish, Greek and Portuguese.
I can't wait to try some LLMs trained exclusively on this data. Maybe we will finally get a GPT-4 class model that isn't trained on unlicensed copyrighted data.
Link 2024-11-14 QuickTime video script to capture frames and bounding boxes [ https://substack.com/redirect/ff95644d-dbec-4ec2-8e52-e982c3a2fe81?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
An update to an older TIL. I'm working on the write-up for my DjangoCon US talk on plugins and I found myself wanting to capture individual frames from the video in two formats: a full frame capture, and another that captured just the portion of the screen shared from my laptop.
I have a script for the former, so I got Claude [ https://substack.com/redirect/02bf53a0-f696-4dfa-ace9-bdf0866943c5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to update my script to add support for one or more --box options, like this:
capture-bbox.sh ../output.mp4  --box '31,17,100,87' --box '0,0,50,50'

Open output.mp4 in QuickTime Player, run that script and then every time you hit a key in the terminal app it will capture three JPEGs from the current position in QuickTime Player - one for the whole screen and one each for the specified bounding box regions.
Those bounding box regions are percentages of the width and height of the image. I also got Claude to build me this interactive tool [ https://substack.com/redirect/e8fde36c-0990-407f-aebb-e5438a9097c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on top of cropperjs [ https://substack.com/redirect/1342047a-9abb-4145-b549-207c9b16a92c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to help figure out those boxes:
Link 2024-11-14 PyPI now supports digital attestations [ https://substack.com/redirect/25b8d534-e681-4669-b847-421acbdeb0c4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Dustin Ingram:
PyPI package maintainers can now publish signed digital attestations when publishing, in order to further increase trust in the supply-chain security of their projects. Additionally, a new API is available for consumers and installers to verify published attestations.
This has been in the works for a while, and is another component of PyPI's approach to supply chain security for Python packaging - see PEP 740 – Index support for digital attestations [ https://substack.com/redirect/5b55c1bc-4226-44d0-8064-5c58ee78e014?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for all of the underlying details.
A key problem this solves is cryptographically linking packages published on PyPI to the exact source code that was used to build those packages. In the absence of this feature there are no guarantees that the .tar.gz or .whl file you download from PyPI hasn't been tampered with (to add malware, for example) in a way that's not visible in the published source code.
These new attestations provide a mechanism for proving that a known, trustworthy build system was used to generate and publish the package, starting with its source code on GitHub.
The good news is that if you're using the PyPI Trusted Publishers mechanism in GitHub Actions to publish packages, you're already using this new system. I wrote about that system in January: Publish Python packages to PyPI with a python-lib cookiecutter template and GitHub Actions [ https://substack.com/redirect/c07f0973-4e48-427d-806e-6c98763445ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - and hundreds of my own PyPI packages are already using that system, thanks to my various cookiecutter templates.
Trail of Bits helped build this feature, and provide extra background about it on their own blog in Attestations: A new generation of signatures on PyPI [ https://substack.com/redirect/f3728735-563f-473c-b36d-5b3dedce9186?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
As of October 29 [ https://substack.com/redirect/677e12eb-639b-41f0-82bc-7c0d60007712?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], attestations are the default for anyone using Trusted Publishing via the PyPA publishing action for GitHub [ https://substack.com/redirect/49b96d3b-a990-4fc7-9d7d-b3e8560357a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. That means roughly 20,000 packages can now attest to their provenance by default, with no changes needed.
They also built Are we PEP 740 yet? [ https://substack.com/redirect/b80e159c-30a0-4280-bcee-f26764046d54?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (key implementation here [ https://substack.com/redirect/4144f047-89a0-4ebb-abde-3081a290e357?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) to track the rollout of attestations across the 360 most downloaded packages from PyPI. It works by hitting URLs such as https://pypi.org/simple/pydantic/ [ https://substack.com/redirect/9bf0b555-5558-4516-88af-bcb6153252e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with a Accept: application/vnd.pypi.simple.v1+json header - here's the JSON that returns [ https://substack.com/redirect/97ee7127-3f8c-410c-a72a-53e83778ed28?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I published an alpha package using Trusted Publishers last night and the files for that release [ https://substack.com/redirect/296fb313-7232-41f9-97ae-c2b77a458d07?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] are showing the new provenance information already:
Which links to this Sigstore log entry [ https://substack.com/redirect/39625adf-53f5-4dc5-964c-85037befde62?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with more details, including the Git hash [ https://substack.com/redirect/dc8c2238-3ae2-499e-8985-faa9bbfd4365?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that was used to build the package:
Sigstore [ https://substack.com/redirect/3ffb1281-f6dc-46dc-be67-34f4aff2e8e4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a transparency log maintained by Open Source Security Foundation (OpenSSF) [ https://substack.com/redirect/1bd809b0-ee37-4a70-88ab-ef9274d1ea87?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a sub-project of the Linux Foundation.
Quote 2024-11-14
Anthropic declined to comment, but referred Bloomberg News to a five-hour podcast [ https://substack.com/redirect/fd4d4e3b-3140-4ad2-b624-2a389af52a00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] featuring Chief Executive Officer Dario Amodei that was released Monday.
"People call them scaling laws. That's a misnomer," he said on the podcast. "They're not laws of the universe. They're empirical regularities. I am going to bet in favor of them continuing, but I'm not certain of that."
[...]
An Anthropic spokesperson said the language about Opus was removed from the website as part of a marketing decision to only show available and benchmarked models. Asked whether Opus 3.5 would still be coming out this year, the spokesperson pointed to Amodei’s podcast remarks. In the interview, the CEO said Anthropic still plans to release the model but repeatedly declined to commit to a timetable.
OpenAI, Google and Anthropic Are Struggling to Build More Advanced AI [ https://substack.com/redirect/85ec24a8-f29d-4edc-8c05-2d074d9d57aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-14 OpenAI Public Bug Bounty [ https://substack.com/redirect/b07024bb-dbd9-4b9c-9704-e6087db9efec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Reading this investigation [ https://substack.com/redirect/3b5330f1-789f-41fc-b075-ea8a37192656?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the security boundaries of OpenAI's Code Interpreter environment helped me realize that the rules for OpenAI's public bug bounty inadvertently double as the missing details for a whole bunch of different aspects of their platform.
This description of Code Interpreter is significantly more useful than their official documentation!
Code execution from within our sandboxed Python code interpreter is out of scope. (This is an intended product feature.) When the model executes Python code it does so within a sandbox. If you think you've gotten RCE outside the sandbox, you must include the output of uname -a. A result like the following indicates that you are inside the sandbox -- specifically note the 2016 kernel version:
Linux 9d23de67-3784-48f6-b935-4d224ed8f555 4.4.0 #1 SMP Sun Jan 10 15:06:54 PST 2016 x86_64 x86_64 x86_64 GNU/Linux

Inside the sandbox you would also see sandbox as the output of whoami, and as the only user in the output of ps.
Link 2024-11-15 Recraft V3 [ https://substack.com/redirect/6ce887e5-a908-4213-9f55-98e409c6d179?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Recraft are a generative AI design tool startup based out of London who released their v3 model a few weeks ago. It's currently sat at the top of the Artificial Analysis Image Arena Leaderboard [ https://substack.com/redirect/1ebe0602-c6d9-4d29-965e-f8b88f5ee4c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], beating Midjourney and Flux 1.1 pro.
The thing that impressed me is that it can generate both raster and vector graphics... and the vector graphics can be exported as SVG!
Here's what I got for raccoon with a sign that says "I love trash" - SVG here [ https://substack.com/redirect/588e0151-520a-44be-9e25-2191999a1c53?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
That's an editable SVG - when I open it up in Pixelmator I can select and modify the individual paths and shapes:
They also have an API [ https://substack.com/redirect/4ba018f9-cb19-4e93-9d50-0644b854e6f9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I spent $1 on 1000 credits and then spent 80 credits (8 cents) making this SVG of a pelican riding a bicycle [ https://substack.com/redirect/53002489-aa8a-4927-97b5-23c57ecd4afa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], using my API key stored in 1Password:
export RECRAFT_API_TOKEN="$(
op item get recraft.ai --fields label=password \
--format json | jq .value -r)"

curl https://external.api.recraft.ai/v1/images/generations \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $RECRAFT_API_TOKEN" \
-d '{
"prompt": "california brown pelican riding a bicycle",
"style": "vector_illustration",
"model": "recraftv3"
}'

Link 2024-11-15 Voting opens for Oxford Word of the Year 2024 [ https://substack.com/redirect/c61346d8-9851-4e9d-88b8-89b65735e017?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One of the options is slop [ https://substack.com/redirect/b36082c0-c443-4c1e-9891-f9f08fe4ce26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
slop (n.): Art, writing, or other content generated using artificial intelligence, shared and distributed online in an indiscriminate or intrusive way, and characterized as being of low quality, inauthentic, or inaccurate.
Link 2024-11-16 NuExtract 1.5 [ https://substack.com/redirect/f36631ad-e167-443a-bfcb-90f6aeb2249a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Structured extraction - where an LLM helps turn unstructured text (or image content) into structured data - remains one of the most directly useful applications of LLMs.
NuExtract is a family of small models directly trained for this purpose (though text only at the moment) and released under the MIT license.
It comes in a variety of shapes and sizes:
NuExtract-v1.5 [ https://substack.com/redirect/05c4ce0b-a193-4cce-b0cd-8b995b2ecd79?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a 3.8B parameter model fine-tuned on Phi-3.5-mini instruct [ https://substack.com/redirect/604da97a-d811-43f3-9d17-779fdc0721e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can try this one out in this playground [ https://substack.com/redirect/ae44784d-af59-41d2-8117-cdb3a192357f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
NuExtract-tiny-v1.5 [ https://substack.com/redirect/ae074326-6475-463c-925a-50e83b55c508?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is 494M parameters, fine-tuned on Qwen2.5-0.5B [ https://substack.com/redirect/a5848bd9-a190-48e6-ae97-ef1e41e4a395?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
NuExtract-1.5-smol [ https://substack.com/redirect/790cac50-7bfb-48bd-b440-4eb9574e41da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is 1.7B parameters, fine-tuned on SmolLM2-1.7B [ https://substack.com/redirect/cac6be97-1b44-4440-a98c-7366d8ddfecc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
All three models were fine-tuned on NuMind's "private high-quality dataset". It's interesting to see a model family that uses one fine-tuning set against three completely different base models.
Useful tip from Steffen Röcker [ https://substack.com/redirect/340d4ca5-f349-475b-8862-c8adaf779226?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Make sure to use it with low temperature, I've uploaded NuExtract-tiny-v1.5 to Ollama [ https://substack.com/redirect/cdc0cc10-e083-48b2-a3f2-197bd59c6d62?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and set it to 0. With the Ollama default of 0.7 it started repeating the input text. It works really well despite being so smol.
Link 2024-11-17 LLM 0.18 [ https://substack.com/redirect/3d541de3-6a1b-4048-9172-a56bd292995e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New release of LLM. The big new feature is asynchronous model support [ https://substack.com/redirect/5c8e21c3-380e-4169-9908-78b6f836807e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - you can now use supported models in async Python code like this:
import llm

model = llm.get_async_model("gpt-4o")
async for chunk in model.prompt(
"Five surprising names for a pet pelican"
):
print(chunk, end="", flush=True)

Also new in this release: support for sending audio attachments to OpenAI's gpt-4o-audio-preview model.
Link 2024-11-18 llm-gemini 0.4 [ https://substack.com/redirect/64b8aae2-848e-41a9-902b-0e6c07cd6dd7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New release of my llm-gemini [ https://substack.com/redirect/dc7639db-2189-4298-b94d-f074e0b0643f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin, adding support for asynchronous models (see LLM 0.18 [ https://substack.com/redirect/942aca57-c1c4-40a5-bec9-cf13d5f2e880?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), plus the new gemini-exp-1114 model (currently at the top of the Chatbot Arena [ https://substack.com/redirect/0fd08258-b348-4e7a-b258-3c45af2cc8b3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and a -o json_object 1 option to force JSON output.
I also released llm-claude-3 0.9 [ https://substack.com/redirect/b9750f44-4b91-47bd-b24c-c5c6d9354ac3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which adds asynchronous support for the Claude family of models.
Quote 2024-11-18
The main innovation here is just using more data. Specifically, Qwen2.5 Coder is a continuation of an earlier Qwen 2.5 model. The original Qwen 2.5 model was trained on 18 trillion tokens spread across a variety of languages and tasks (e.g, writing, programming, question answering). Qwen 2.5-Coder sees them train this model on an additional 5.5 trillion tokens of data. This means Qwen has been trained on a total of ~23T tokens of data – for perspective, Facebook’s LLaMa3 models were trained on about 15T tokens [ https://substack.com/redirect/a21f2639-e918-4b57-824c-12441a86cbe5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I think this means Qwen is the largest publicly disclosed number of tokens dumped into a single language model (so far).
Jack Clark [ https://substack.com/redirect/4bba5395-b892-4917-885d-7b01d6c53a84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-18 Qwen: Extending the Context Length to 1M Tokens [ https://substack.com/redirect/d78930c7-0d42-45db-8aad-7b4636549391?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The new Qwen2.5-Turbo boasts a million token context window (up from 128,000 for Qwen 2.5) and faster performance:
Using sparse attention mechanisms, we successfully reduced the time to first token for processing a context of 1M tokens from 4.9 minutes to 68 seconds, achieving a 4.3x speedup.
The benchmarks they've published look impressive, including a 100% score on the 1M-token passkey retrieval task (not the first model to achieve this).
There's a catch: unlike previous models in the Qwen 2.5 series it looks like this one hasn't been released as open weights: it's available exclusively via their (inexpensive) paid API - for which it looks like you may need a +86 Chinese phone number.
Link 2024-11-18 Pixtral Large [ https://substack.com/redirect/115fd46d-966f-4a07-9414-9069ec7ef69c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New today from Mistral:
Today we announce Pixtral Large, a 124B open-weights multimodal model built on top of Mistral Large 2. Pixtral Large is the second model in our multimodal family and demonstrates frontier-level image understanding.
The weights are out on Hugging Face [ https://substack.com/redirect/6f4ed5b2-7b89-425c-b43f-1a842a25ea06?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (over 200GB to download, and you'll need a hefty GPU rig to run them). The license is free for academic research but you'll need to pay for commercial usage.
The new Pixtral Large model is available through their API, as models called pixtral-large-2411 and pixtral-large-latest.
Here's how to run it using LLM [ https://substack.com/redirect/02d177ff-641f-407a-8657-01ac8323c4c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the llm-mistral [ https://substack.com/redirect/cb7e7e9d-e743-4778-8624-3e1767838457?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin:
llm install -U llm-mistral
llm keys set mistral
# paste in API key
llm mistral refresh
llm -m mistral/pixtral-large-latest describe -a https://static.simonwillison.net/static/2024/pelicans.jpg

The image shows a large group of birds, specifically pelicans, congregated together on a rocky area near a body of water. These pelicans are densely packed together, some looking directly at the camera while others are engaging in various activities such as preening or resting. Pelicans are known for their large bills with a distinctive pouch, which they use for catching fish. The rocky terrain and the proximity to water suggest this could be a coastal area or an island where pelicans commonly gather in large numbers. The scene reflects a common natural behavior of these birds, often seen in their nesting or feeding grounds.
Update: I released llm-mistral 0.8 [ https://substack.com/redirect/7f674444-f17e-4fbe-a568-5f490b90d9e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which adds async model support [ https://substack.com/redirect/942aca57-c1c4-40a5-bec9-cf13d5f2e880?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the full Mistral line, plus a new llm -m mistral-large shortcut alias for the Mistral Large model.
Link 2024-11-19 Security means securing people where they are [ https://substack.com/redirect/55b3962e-14a3-422c-b5c8-8e7b000ca49a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
William Woodruff is an Engineering Director at Trail of Bits who worked on the recent PyPI digital attestations project [ https://substack.com/redirect/37e4b6de-4829-4409-836f-624dbc5a76c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
That feature is based around open standards but launched with an implementation against GitHub, which resulted in push back (and even some conspiracy theories) that PyPI were deliberately favoring GitHub over other platforms.
William argues here for pragmatism over ideology:
Being serious about security at scale means meeting users where they are. In practice, this means deciding how to divide a limited pool of engineering resources such that the largest demographic of users benefits from a security initiative. This results in a fundamental bias towards institutional and pre-existing services, since the average user belongs to these institutional services and does not personally particularly care about security. Participants in open source can and should work to counteract this institutional bias, but doing so as a matter of ideological purity undermines our shared security interests.
Link 2024-11-19 Preview: Gemini API Additional Terms of Service [ https://substack.com/redirect/ee2c770e-47eb-41f7-a230-4149a986fb65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Google sent out an email last week linking to this preview of upcoming changes to the Gemini API terms. Key paragraph from that email:
To maintain a safe and responsible environment for all users, we're enhancing our abuse monitoring [ https://substack.com/redirect/dc3e6e73-e55e-489c-b715-b4a90626d391?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] practices for Google AI Studio and Gemini API. Starting December 13, 2024, Gemini API will log prompts and responses for Paid Services, as described in the terms. These logs are only retained for a limited time (55 days) and are used solely to detect abuse and for required legal or regulatory disclosures. These logs are not used for model training. Logging for abuse monitoring is standard practice across the global AI industry. You can preview [ https://substack.com/redirect/ee2c770e-47eb-41f7-a230-4149a986fb65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the updated Gemini API Additional Terms of Service, effective December 13, 2024.
That "for required legal or regulatory disclosures" piece makes it sound like somebody could subpoena Google to gain access to your logged Gemini API calls.
It's not clear to me if this is a change from their current policy though, other than the number of days of log retention increasing from 30 to 55 (and I'm having trouble finding that 30 day number written down anywhere.)
That same email also announced the deprecation of the older Gemini 1.0 Pro model:
Gemini 1.0 Pro will be discontinued on February 15, 2025.
Link 2024-11-19 Understanding the BM25 full text search algorithm [ https://substack.com/redirect/5b8d77fa-110f-4370-ae20-312cd1f9bfb7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Evan Schwartz provides a deep dive explanation of how the classic BM25 search relevance scoring function works, including a very useful breakdown of the mathematics it uses.
Link 2024-11-19 Using uv with PyTorch [ https://substack.com/redirect/24d2d83a-f8b3-4a85-968a-1b9b01d00794?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
PyTorch is a notoriously tricky piece of Python software to install, due to the need to provide separate wheels for different combinations of Python version and GPU accelerator (e.g. different CUDA versions).
uv now has dedicated documentation for PyTorch which I'm finding really useful - it clearly explains the challenge and then shows exactly how to configure a pyproject.toml such that uv knows which version of each package it should install from where.
Link 2024-11-19 OpenStreetMap vector tiles demo [ https://substack.com/redirect/8ce994d1-e6a3-413b-b479-204b35e86462?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Long-time OpenStreetMap developer Paul Norman [ https://substack.com/redirect/093b8a3a-fa9b-4c36-978c-c21eae2ad503?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] has been working on adding vector tile support to OpenStreetMap for quite a while [ https://substack.com/redirect/03c0b139-ed4f-498c-88a6-2faaadb8b6ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Paul recently announced [ https://substack.com/redirect/12bac13e-797f-4a5e-a6a0-c3e5dcbeb06d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that vector.openstreetmap.org is now serving vector tiles (in Mapbox Vector Tiles (MVT) format [ https://substack.com/redirect/10f408dd-0c87-4b43-9d0a-f3e3e8600bff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) - here's his interactive demo for seeing what they look like.
Link 2024-11-20 Bluesky WebSocket Firehose [ https://substack.com/redirect/0ba3f83a-0139-481d-a3eb-ddc7020556de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Very quick (10 seconds of Claude hacking [ https://substack.com/redirect/64a1b727-374b-4b3b-8808-a399ee2499df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) prototype of a web page that attaches to the public Bluesky WebSocket firehose and displays the results directly in your browser.
Here's the code [ https://substack.com/redirect/8d42cf49-4d1a-4293-8b25-82e03ccec1b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - there's very little to it, it's basically opening a connection to wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post and logging out the results to a  element.
Bluesky's Jetstream [ https://substack.com/redirect/5d9fd1ff-4af1-49c6-ba54-73ed80ce3dbf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] isn't their main atproto firehose - that's a more complicated protocol involving CBOR data and CAR files. Jetstream is a new Go proxy (source code here [ https://substack.com/redirect/bd9e1365-d3a6-4aca-9d40-9149c13eff91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) that provides a subset of that firehose over WebSocket.
Jetstream was built by Bluesky developer Jaz, initially as a side-project, in response to the surge of traffic they received back in September when Brazil banned Twitter. See Jetstream: Shrinking the AT Proto Firehose by >99% [ https://substack.com/redirect/5780ec47-09d9-4b5f-8ffa-92e51d22c25e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for their description of the project when it first launched.
The API scene growing around Bluesky is really exciting right now. Twitter's API is so expensive it may as well not exist, and Mastodon's community have pushed back against many potential uses of the Mastodon API as incompatible with that community's value system.
Hacking on Bluesky feels reminiscent of the massive diversity of innovation we saw around Twitter back in the late 2000s and early 2010s.
Here's a much more fun Bluesky demo by Theo Sanderson: firehose3d.theo.io [ https://substack.com/redirect/fce40fa2-d373-4702-8d1b-7613a5102b00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (source code here [ https://substack.com/redirect/ee4879a5-41d3-4597-a254-aa26f15cc10e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) which displays the firehose from that same WebSocket endpoint in the style of a Windows XP screensaver.
Link 2024-11-20 Foursquare Open Source Places: A new foundational dataset for the geospatial community [ https://substack.com/redirect/e856ec4b-8a9b-43d5-8c3d-234fc752783f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I did not expect this!
[...] we are announcing today the general availability of a foundational open data set, Foursquare Open Source Places ("FSQ OS Places"). This base layer of 100mm+ global places of interest ("POI") includes 22 core attributes (see schema here [ https://substack.com/redirect/4904c0f9-5222-4438-bdb0-8fda980ac5a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) that will be updated monthly and available for commercial use under the Apache 2.0 license framework.
The data is available as Parquet files [ https://substack.com/redirect/e4a99f8d-275a-4846-8557-f6ef79d2f3c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] hosted on Amazon S3.
Here's how to list the available files:
aws s3 ls s3://fsq-os-places-us-east-1/release/dt=2024-11-19/places/parquet/

I got back places-00000.snappy.parquet through places-00024.snappy.parquet, each file around 455MB for a total of 10.6GB of data.
I ran duckdb and then used DuckDB's ability to remotely query Parquet on S3 to explore the data a bit more without downloading it to my laptop first:
select count(*) from 's3://fsq-os-places-us-east-1/release/dt=2024-11-19/places/parquet/places-00000.snappy.parquet';

This got back 4,180,424 - that number is similar for each file, suggesting around 104,000,000 records total.
The I ran this query to retrieve 1,000 places from that first file as newline-delimited JSON:
copy (
select * from 's3://fsq-os-places-us-east-1/release/dt=2024-11-19/places/parquet/places-00000.snappy.parquet'
limit 1000
) to '/tmp/places.json';

Here's that places.json file [ https://substack.com/redirect/565b1908-98b2-466b-be5d-3889614cf8d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and here it is imported into Datasette Lite [ https://substack.com/redirect/1ff68925-f659-48b9-829e-3544a3ee2ca6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Finally, I got ChatGPT Code Interpreter to convert that file to GeoJSON [ https://substack.com/redirect/93d5d50e-ecb9-4a7d-af7d-42af3659b31e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and pasted the result into this Gist [ https://substack.com/redirect/1b2cf06b-a8c9-4f52-80e9-df867fabcca1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], giving me a map of those thousand places (because Gists automatically render GeoJSON):
Quote 2024-11-21
When we started working on what became NotebookLM in the summer of 2022, we could fit about 1,500 words in the context window. Now we can fit up to 1.5 million words. (And using various other tricks, effectively fit 25 million words.) The emergence of long context models is, I believe, the single most unappreciated AI development of the past two years, at least among the general public. It radically transforms the utility of these models in terms of actual, practical applications.
Steven Johnson [ https://substack.com/redirect/547e0902-f678-40e5-b5d7-8b9106ae1b11?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEU1TmpBME9USXNJbWxoZENJNk1UY3pNakUyT1RBNU15d2laWGh3SWpveE56WXpOekExTURrekxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuM3FSTHRMSmU0MHFKRjFtNklqZlJNdFZTWmVZcEdSXzktWTV1amdRRE9FQSIsInAiOjE1MTk2MDQ5MiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzMyMTY5MDkzLCJleHAiOjE3MzQ3NjEwOTMsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.RiLvb7TUwuATgJTeMbQiXN11jEoE_uCjS6DeOrdBa7k?
