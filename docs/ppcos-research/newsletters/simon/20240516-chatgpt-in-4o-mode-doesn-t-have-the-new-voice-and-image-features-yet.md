# ChatGPT in 4o mode doesn't have the new voice and image features yet

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-05-16T12:02:21.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/chatgpt-in-4o-mode-doesnt-have-the

In this newsletter:
ChatGPT in "4o" mode is not running the new features yet
Plus 7 links and 5 quotations
ChatGPT in "4o" mode is not running the new features yet [ https://substack.com/redirect/b7b88741-ef00-421d-858e-975084c46d19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-05-15
Monday's OpenAI announcement [ https://substack.com/redirect/7303bb51-29c0-4575-8628-320449290264?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of their new GPT-4o model included some intriguing new features:
Creepily good improvements to the ability to both understand and produce voice (Sam Altman simply tweeted "her" [ https://substack.com/redirect/3f9cc7b5-bc9a-4c94-848c-5c7ad2b4084b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), and to be interrupted mid-sentence
New image output capabilities that appear to leave existing models like DALL-E 3 in the dust - take a look at the examples [ https://substack.com/redirect/931f7349-a3e4-4a80-b245-ad49c2ab979c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], they seem to have solved consistent character representation AND reliable text output!
They also made the new 4o model available to paying ChatGPT Plus users, on the web and in their apps.
But, crucially, those big new features were not part of that release.
Here's the relevant section from the announcement post:
We recognize that GPT-4o’s audio modalities present a variety of novel risks. Today we are publicly releasing text and image inputs and text outputs. Over the upcoming weeks and months, we’ll be working on the technical infrastructure, usability via post-training, and safety necessary to release the other modalities.
This is catching out a lot of people. The ChatGPT iPhone app already has image output, and it already has a voice mode. These worked with the previous GPT-4 mode and they still work with the new GPT-4o mode... but they are not using the new model's capabilities.
Lots of people are discovering the voice mode for the first time - it's the headphone icon in the bottom right of the interface.
They try it and it's impressive (it was impressive before) but it's nothing like as good as the voice mode in Monday's demos.
Honestly, it's not at all surprising that people are confused. They're seeing the "4o" option and, understandably, are assuming that this is the set of features that were announced earlier this week.
Most people don't distinguish models from features
Think about what you need to know in order to understand what's going on here:
GPT-4o is a brand new multi-modal Large Language Model. It can handle text, image and audio input and produce text, image and audio output.
But... the version of GPT-4o that has been made available so far - both via the API and via the OpenAI apps - is only able to handle text and image input and produce text output. The other features are not yet available outside of OpenAI (and a select group of partners).
And yet in the apps it can still handle audio input and output and generate images. That's because the app version of the model is wrapped with additional tools.
The audio input is handled by a separate model called Whisper, which converts speech to text. That text is then fed into the LLM, which generates a text response.
The response is passed to OpenAI's boringly-named tts-1 (or maybe tts-1-hd) model (described here [ https://substack.com/redirect/28e6d1bf-6923-473b-b418-0aa7de24c5d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), which converts that text to speech.
While nowhere near as good as the audio in Monday's demo, tts-1 is still a really impressive model. I've been using it via my ospeak [ https://substack.com/redirect/dd6ed32f-c445-4e1e-bd20-908351255b8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CLI tool since it was released back in November.
As for images? Those are generated using DALL-E 3, through a process where ChatGPT directly prompts that model. I wrote about how that works back in October [ https://substack.com/redirect/bfd8b08d-f37d-4eae-9b2b-00fb191471d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
So what's going on with ChatGPT's GPT-4o mode is completely obvious, provided you already understand:
GPT-4 v.s. GPT-4o
Whisper
tts-1
DALL-E 3
Why OpenAI would demonstrate these features and then release a version of the model that doesn't include them
I'm reminded of the kerfluffle back in March when the Google Gemini image creator was found to generate images of Black Nazis [ https://substack.com/redirect/9620f577-4d95-4c05-aa65-023a5e9d483f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I saw a whole bunch of people refer to that in conversations about the Google Gemini Pro 1.5 LLM, released at the same time, despite the quality of that model being entirely unrelated to Google's policy decisions about how one of the interfaces to that model should make use of the image creator tool.
What can we learn from this?
If you're fully immersed in this world, it's easy to lose track of how incredibly complicated these systems have become. The amount you have to know in order to even understand what that "4o" mode in the ChatGPT app does is very easy to underestimate.
Fundamentally these are challenges in user experience design. You can't just write documentation about them, because no-one reads documentation.
A good starting here is to acknowledge the problem. LLM systems are extremely difficult to understand and use. We need to design the tools we build on top of them accordingly.
Link 2024-05-14 Why your voice assistant might be sexist [ https://substack.com/redirect/22ad1dab-197f-45c6-a4e5-095b54f50b1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Given OpenAI's demo on Monday [ https://substack.com/redirect/9583ea79-3af2-4ee6-b141-86cfba184fad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of a vocal chat assistant with a flirty, giggly female voice - and the new ability to be interrupted! - it's worth revisiting this piece by Chris Baraniuk from June 2022 about gender dynamics in voice assistants. Includes a link to this example [ https://substack.com/redirect/76f48467-e730-4999-9463-38cbc34ae64c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of a synthesized non-binary voice.
Link 2024-05-14 How developers are using Gemini 1.5 Pro’s 1 million token context window [ https://substack.com/redirect/acdf35db-1271-486c-8299-26af1ba6df1e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I got to be a talking head for a few seconds in an intro video for today's Google I/O keynote, talking about how I used Gemini Pro 1.5 to index my bookshelf [ https://substack.com/redirect/9d7274f5-7663-405e-b5d2-b325fb948a5b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (and with a cameo from my squirrel nutcracker). I'm at 1m25s [ https://substack.com/redirect/3c65a481-a37b-415c-ae6a-9ad123cfccf3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
(Or at 10m6s in the full video of the keynote [ https://substack.com/redirect/fcde236b-129c-4909-b99c-5dad1180d8b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Link 2024-05-14 llm-gemini 0.1a4 [ https://substack.com/redirect/aaf95a89-8ed7-48cc-88ab-84917e8da05c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A new release of my llm-gemini plugin adding support for the Gemini 1.5 Flash [ https://substack.com/redirect/da54cf79-7966-40f1-9644-525e4075bcfe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] model that was revealed this morning at Google I/O.
I'm excited about this new model because of its low price. Flash is $0.35 per 1 million tokens for prompts up to 128K token and $0.70 per 1 million tokens for longer prompts - up to a million tokens now and potentially two million at some point in the future. That's 1/10th of the price of Gemini Pro 1.5, cheaper than GPT 3.5 ($0.50/million) and only a little more expensive than Claude 3 Haiku ($0.35/million).
Link 2024-05-14 Context caching for Google Gemini [ https://substack.com/redirect/0c3937e1-ca26-443e-afb4-5b15c35b9db9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Another new Gemini feature announced today. Long context models enable answering questions against large chunks of text, but the price of those long prompts can be prohibitive - $3.50/million for Gemini Pro 1.5 up to 128,000 tokens and $7/million beyond that.
Context caching offers a price optimization, where the long prefix prompt can be reused between requests, halving the cost per prompt but at an additional cost of $4.50 / 1 million tokens per hour to keep that context cache warm.
Given that hourly extra charge this isn't a default optimization for all cases, but certain high traffic applications might be able to save quite a bit on their longer prompt systems.
It will be interesting to see if other vendors such as OpenAI and Anthropic offer a similar optimization in the future.
Quote 2024-05-15
The MacBook Airs are Apple’s best-selling laptops; the iPad Pros are Apple’s least-selling iPads. I think it’s as simple as this: the current MacBook Airs have the M3, not the M4, because there isn’t yet sufficient supply of M4 chips to satisfy demand for MacBook Airs.
John Gruber [ https://substack.com/redirect/906a577a-0cab-4a59-a7c0-3c74743b21a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-05-15
But unlike the phone system, we can’t separate an LLM’s data from its commands. One of the enormously powerful features of an LLM is that the data affects the code. We want the system to modify its operation when it gets new training data. We want it to change the way it works based on the commands we give it. The fact that LLMs self-modify based on their input data is a feature, not a bug. And it’s the very thing that enables prompt injection.
Bruce Schneier [ https://substack.com/redirect/493f3675-cc2d-456d-b257-5cbb46f44fb0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-15 How to PyCon [ https://substack.com/redirect/9e762ade-a6a0-4ce9-8a2f-8a86a4fc1c49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Glyph's tips on making the most out of PyCon. I particularly like his suggestion that "dinners are for old friends, but lunches are for new ones".
I'm heading out to Pittsburgh and giving a keynote (!) on Saturday. If you see me there please come and say hi!
Quote 2024-05-15
If we want LLMs to be less hype and more of a building block for creating useful everyday tools for people, AI companies' shift away from scaling and AGI dreams to acting like regular product companies that focus on cost and customer value proposition is a welcome development.
Arvind Narayanan [ https://substack.com/redirect/c799a64d-c0be-401f-a870-6ed364f74537?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-05-15 OpenAI: Managing your work in the API platform with Projects [ https://substack.com/redirect/c300cbee-2fcc-4871-8944-c33aea54360b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New OpenAI API feature: you can now create API keys for "projects" that can have a monthly spending cap. The UI for that limit says:
If the project's usage exceeds this amount in a given calendar month (UTC), subsequent API requests will be rejected
You can also set custom token-per-minute and request-per-minute rate limits for individual models.
I've been wanting this for ages: this means it's finally safe to ship a weird public demo on top of their various APIs without risk of accidental bankruptcy if the demo goes viral!
Link 2024-05-15 PaliGemma model README [ https://substack.com/redirect/0d3e5a7f-e4b9-4365-aa0a-d62966ccc174?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One of the more over-looked announcements from Google I/O was PaliGemma, an openly licensed VLM (Vision Language Model) in the Gemma family of models.
The model accepts an image and a text prompt. It outputs text, but that text can include special tokens representing regions on the image. This means it can return both bounding boxes and fuzzier segment outlines of detected objects, behavior that can be triggered using a prompt such as "segment puffins".
You can try it out on Hugging Face [ https://substack.com/redirect/9c1a6471-aa3a-4129-b12a-080e656ba4bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It's a 3B model, making it feasible to run on consumer hardware.
Quote 2024-05-15
But where the company once limited itself to gathering low-hanging fruit along the lines of “what time is the super bowl,” on Tuesday executives showcased generative AI tools that will someday plan an entire anniversary dinner, or cross-country-move, or trip abroad. A quarter-century into its existence, a company that once proudly served as an entry point to a web that it nourished with traffic and advertising revenue has begun to abstract that all away into an input for its large language models.
Casey Newton [ https://substack.com/redirect/28b2ee19-6392-4503-9122-83776056888c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-05-16
[...] by default Heroku will spin up multiple dynos in different availability zones. It also has multiple routers in different zones so if one zone should go completely offline, having a second dyno will mean that your app can still serve traffic.
Richard Schneeman [ https://substack.com/redirect/bdb42115-1b2a-4fe8-888f-365778f6e6b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORFEyT0RZMU16SXNJbWxoZENJNk1UY3hOVGcyTVRFNE9Td2laWGh3SWpveE56RTRORFV6TVRnNUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuM3k4MUF0Ml90YkxMU1RzSXVSVGJmOFpzRU8xUmtvZUpueUFaV1JaejVjVSZleHBpcmVzPTM2NWQiLCJwIjoxNDQ2ODY1MzIsInMiOjExNzMzODYsImYiOnRydWUsInUiOjEyNTU1OTksImlhdCI6MTcxNTg2MTE4OSwiZXhwIjoxNzE4NDUzMTg5LCJpc3MiOiJwdWItMCIsInN1YiI6ImxpbmstcmVkaXJlY3QifQ.BpDnvgyh5Rtw__bNkMT9-9bXND6ZALu_Qv8D1q3A7vQ?
