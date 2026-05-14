# OpenAI o3-mini, now available in LLM

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-02-02T21:21:53.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/openai-o3-mini-now-available-in-llm

In this newsletter:
OpenAI o3-mini, now available in LLM
Plus 10 links and 6 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
OpenAI o3-mini, now available in LLM [ https://substack.com/redirect/0325f30e-545d-4996-8f52-81215fadcacf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-01-31
OpenAI's o3-mini is out today [ https://substack.com/redirect/f1e5c418-1a7b-4e44-a9fc-e6219250bc9a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. As with other o-series models it's a slightly difficult one to evaluate - we now need to decide if a prompt is best run using GPT-4o, o1, o3-mini or (if we have access) o1 Pro.
Confusing matters further, the benchmarks in the o3-mini system card [ https://substack.com/redirect/d6a29bd2-d44a-4993-bcfc-b355216764e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (PDF) aren't a universal win for o3-mini across all categories. It generally benchmarks higher than GPT-4o and o1 but not across everything.
The biggest win for o3-mini is on the Codeforces ELO competitive programming benchmark, which I think is described by this 2nd January 2025 paper [ https://substack.com/redirect/66b692db-469a-428c-bc4a-94d637055d1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with the following scores:
o3-mini (high) 2130
o3-mini (medium) 2036
o1 1891
o3-mini (low) 1831
o1-mini 1650
o1-preview 1258
GPT-4o 900
Weirdly, that GPT-4o score was in an older copy of the System Card PDF which has been replaced by an updated document that doesn't mention Codeforces ELO scores at all.
One note from the System Card that stood out for me concerning intended applications of o3-mini for OpenAI themselves:
We also plan to allow users to use o3-mini to search the internet and summarize the results in ChatGPT. We expect o3-mini to be a useful and safe model for doing this, especially given its performance on the jailbreak and instruction hierarchy evals detailed in Section 4 below.
This is notable because the existing o1 models on ChatGPT have not yet had access to their web search tool - despite the mixture of search and "reasoning" models having very clear benefits.
o3-mini does not and will not [ https://substack.com/redirect/3b10b003-4339-43de-a0af-c408fbe6579a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] support vision. We will have to wait for future OpenAI reasoning models for that.
I released LLM 0.21 [ https://substack.com/redirect/f1760a3d-5a5e-491d-a915-986a64139cbb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with support for the new model, plus its -o reasoning_effort high (or medium or low) option for tweaking the reasoning effort - details in this issue [ https://substack.com/redirect/602ba2a4-d845-4022-8224-04f935aa28ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Note that the new model is currently only available for Tier 3 [ https://substack.com/redirect/4a581e88-96f3-470b-a121-4f947202e467?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and higher users, which requires you to have spent at least $100 on the API.
o3-mini is priced [ https://substack.com/redirect/891a8a67-fd9f-49b6-be11-b881377a536f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at $1.10/million input tokens, $4.40/million output tokens - less than half the price of GPT-4o (currently $2.50/$10) and massively cheaper than o1 ($15/60).
I tried using it to summarize this conversation about o3-mini on Hacker News [ https://substack.com/redirect/31d23645-b5dc-4682-a389-79867b30ba58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], using my hn-summary.sh script [ https://substack.com/redirect/44f32d4f-8ed2-487f-821e-a14c516c746f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
hn-summary.sh 42890627 -o o3-mini
Here's the result [ https://substack.com/redirect/bf994dd3-6fb3-4729-b507-b584da07305e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it used 18,936 input tokens and 2,905 output tokens for a total cost of 3.3612 cents.
o3-mini (and o1-mini) are text-only models: they don't accept image inputs. The full o1 API model can accept images in the same way as GPT-4o.
Another characteristic worth noting is o3-mini's token output limit - the measure of how much text it can output in one go. That's 100,000 tokens, compared to 16,000 for GPT-4o and just 8,000 for both DeepSeek R1 and Claude 3.5.
Invisible "reasoning tokens" come out of the same budget, so it's likely not possible to have it output the full 100,000.
The model accepts up to 200,000 tokens of input, an improvement on GPT-4o's 128,000.
An application where output limits really matter is translation between human languages, where the output can realistically be expected to have a similar length to the input. It will be interesting seeing how well o3-mini works for that, especially given its low price.
Update: Here's a fascinating comment [ https://substack.com/redirect/1c30099c-ec0e-4c71-b666-d08058e9ff84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on this by professional translator Tom Gally on Hacker News:
I just did a test in which both R1 and o3-mini got worse at translation in the latter half of a long text. [...]
An initial comparison of the output suggested that, while R1 didn’t seem bad, o3-mini produced a writing style closer to what I asked for in the prompt—smoother and more natural English. But then I noticed that the output length was 5,855 characters for R1, 9,052 characters for o3-mini, and 11,021 characters for my own polished version. Comparing the three translations side-by-side with the original Japanese, I discovered that R1 had omitted entire paragraphs toward the end of the speech, and that o3-mini had switched to a strange abbreviated style (using slashes instead of “and” between noun phrases, for example) toward the end as well. The vanilla versions of ChatGPT, Claude, and Gemini that I ran the same prompt and text through a month ago had had none of those problems.
Quote 2025-01-30
Llama 4 is making great progress in training. Llama 4 mini is done with pre-training and our reasoning models and larger model are looking good too. Our goal with Llama 3 was to make open source competitive with closed models, and our goal for Llama 4 is to lead. Llama 4 will be natively multimodal -- it's an omni-model -- and it will have agentic capabilities, so it's going to be novel and it's going to unlock a lot of new use cases.
Mark Zuckerberg [ https://substack.com/redirect/7cc507a2-d9a3-4b52-9ccf-dcf2dbc24469?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-01-30
104. Technology offers remarkable tools to oversee and develop the world's resources. However, in some cases, humanity is increasingly ceding control of these resources to machines. Within some circles of scientists and futurists, there is optimism about the potential of artificial general intelligence (AGI), a hypothetical form of AI that would match or surpass human intelligence and bring about unimaginable advancements. Some even speculate that AGI could achieve superhuman capabilities. At the same time, as society drifts away from a connection with the transcendent, some are tempted to turn to AI in search of meaning or fulfillment---longings that can only be truly satisfied in communion with God. [194] [ https://substack.com/redirect/8123df42-29b0-4885-baff-1d8f3d43c309?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
105. However, the presumption of substituting God for an artifact of human making is idolatry, a practice Scripture explicitly warns against (e.g., Ex. 20:4; 32:1-5; 34:17). Moreover, AI may prove even more seductive than traditional idols for, unlike idols that "have mouths but do not speak; eyes, but do not see; ears, but do not hear" (Ps. 115:5-6), AI can "speak," or at least gives the illusion of doing so (cf. Rev. 13:15). Yet, it is vital to remember that AI is but a pale reflection of humanity---it is crafted by human minds, trained on human-generated material, responsive to human input, and sustained through human labor. AI cannot possess many of the capabilities specific to human life, and it is also fallible. By turning to AI as a perceived "Other" greater than itself, with which to share existence and responsibilities, humanity risks creating a substitute for God. However, it is not AI that is ultimately deified and worshipped, but humanity itself---which, in this way, becomes enslaved to its own work. [195] [ https://substack.com/redirect/d860ef13-74c0-4ad2-ab96-83730c0bf779?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Antiqua et Nova [ https://substack.com/redirect/cca02eaf-a969-45ad-8caa-6186c9910a8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-01-30 Mistral Small 3 [ https://substack.com/redirect/0a7cdd2e-5e2b-404b-aa45-654334f3dc1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
First model release of 2025 for French AI lab Mistral, who describe Mistral Small 3 as "a latency-optimized 24B-parameter model released under the Apache 2.0 license."
More notably, they claim the following:
Mistral Small 3 is competitive with larger models such as Llama 3.3 70B or Qwen 32B, and is an excellent open replacement for opaque proprietary models like GPT4o-mini. Mistral Small 3 is on par with Llama 3.3 70B instruct, while being more than 3x faster on the same hardware.
Llama 3.3 70B and Qwen 32B are two of my favourite models to run on my laptop - that ~20GB size turns out to be a great trade-off between memory usage and model utility. It's exciting to see a new entrant into that weight class.
The license is important: previous Mistral Small models used their Mistral Research License, which prohibited commercial deployments unless you negotiate a commercial license with them. They appear to be moving away from that, at least for their core models:
We’re renewing our commitment to using Apache 2.0 license for our general purpose models, as we progressively move away from MRL-licensed models. As with Mistral Small 3, model weights will be available to download and deploy locally, and free to modify and use in any capacity. […] Enterprises and developers that need specialized capabilities (increased speed and context, domain specific knowledge, task-specific models like code completion) can count on additional commercial models complementing what we contribute to the community.
Despite being called Mistral Small 3, this appears to be the fourth release of a model under that label. The Mistral API calls this one mistral-small-2501 - previous model IDs were mistral-small-2312, mistral-small-2402 and mistral-small-2409.
I've updated the llm-mistral plugin [ https://substack.com/redirect/27a3e91e-67be-4b49-b9b0-89065abf83e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for talking directly to Mistral's La Plateforme [ https://substack.com/redirect/73f084ff-607a-4d5e-a664-ea61475281f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] API:
llm install -U llm-mistral
llm keys set mistral
# Paste key here
llm -m mistral/mistral-small-latest "tell me a joke about a badger and a puffin"
Sure, here's a light-hearted joke for you:
Why did the badger bring a puffin to the party?
Because he heard puffins make great party 'Puffins'!
(That's a play on the word "puffins" and the phrase "party people.")
API pricing is $0.10/million tokens of input, $0.30/million tokens of output - half the price of the previous Mistral Small API model ($0.20/$0.60). for comparison, GPT-4o mini is $0.15/$0.60.
Mistral also ensured that the new model was available on Ollama [ https://substack.com/redirect/325ce5d7-87c1-4366-89ea-0ae026e70527?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in time for their release announcement.
You can pull the model like this (fetching 14GB):
ollama run mistral-small:24b
The llm-ollama [ https://substack.com/redirect/325ffefd-34b8-487c-8f08-3e97b9288adb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin will then let you prompt it like so:
llm install llm-ollama
llm -m mistral-small:24b "say hi"
Link 2025-01-30 PyPI now supports project archival [ https://substack.com/redirect/419f76f4-5172-409d-8c1b-1a10dfec9f80?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Neat new PyPI feature, similar to GitHub's archiving repositories [ https://substack.com/redirect/313375f0-bdfd-4b5f-ab37-97178dce5635?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] feature. You can now mark a PyPI project as "archived", making it clear that no new releases are planned (though you can switch back out of that mode later if you need to).
I like the sound of these future plans around this topic:
Project archival is the first step in a larger project, aimed at improving the lifecycle of projects on PyPI. That project includes evaluating additional project statuses (things like "deprecated" and "unmaintained"), as well as changes to PyPI's public APIs [ https://substack.com/redirect/96be820a-9c3e-427d-87e1-6fed0fe1c2fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that will enable clients to retrieve and act on project status information. You can track our progress on these fronts by following along with warehouse#16844 [ https://substack.com/redirect/1699b1ec-481d-40f7-9bcf-48a1ef25413f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
Quote 2025-01-30
Eventually, however, HudZah wore Claude down. He filled his Project with the e-mail conversations he’d been having with fusor hobbyists, parts lists for things he’d bought off Amazon, spreadsheets, sections of books and diagrams. HudZah also changed his questions to Claude from general ones to more specific ones. This flood of information and better probing seemed to convince Claude that HudZah did know what he was doing, and the AI began to give him detailed guidance on how to build a nuclear fusor and how not to die while doing it.
Ashlee Vance [ https://substack.com/redirect/43e15d57-8548-40a0-8204-79d7ff90d76e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-01-31 The surprising way to save memory with BytesIO [ https://substack.com/redirect/03a52bad-3065-4282-a382-54649d6af02d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Itamar Turner-Trauring explains that if you have a BytesIO object in Python calling .read on it will create a full copy of that object, doubling the amount of memory used - but calling .getvalue returns a bytes object that uses no additional memory, instead using copy-on-write.
.getbuffer is another memory-efficient option but it returns a memoryview [ https://substack.com/redirect/5139a528-2cfa-4da3-91a3-8970e2d43ff4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which has less methods than the bytes you get back from .getvalue- it doesn't have .find for example.
Link 2025-01-31 openai-realtime-solar-system [ https://substack.com/redirect/f5c04247-8288-402c-9290-fc696397abcd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This was my favourite demo from OpenAI DevDay back in October [ https://substack.com/redirect/da520ec3-0881-45e5-acfc-cf7e68ac761e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a voice-driven exploration of the solar system, developed by Katia Gil Guzman, where you could say things out loud like "show me Mars" and it would zoom around showing you different planetary bodies.
OpenAI finally released the code for it, now upgraded to use the new, easier to use WebRTC API they released in December [ https://substack.com/redirect/12758aac-3147-40f4-a6b9-d5ea94041d5c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I ran it like this, loading my OpenAI API key using llm keys get [ https://substack.com/redirect/baa3e0fd-d8ab-432a-9551-52fdcb792787?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
cd /tmp
git clone https://github.com/openai/openai-realtime-solar-system
cd openai-realtime-solar-system
npm install
OPENAI_API_KEY="$(llm keys get openai)" npm run dev
You need to click on both the Wifi icon and the microphone icon before you can instruct it with your voice. Try "Show me Mars".
Link 2025-01-31 Latest black (25.1.0) adds a newline after docstring and before pass in an exception class [ https://substack.com/redirect/4f491f06-466a-4d42-9e8f-a63c023a5583?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I filed a bug report against Black when the latest release - 25.1.0 - reformatted the following code to add an ugly (to me) newline between the docstring and the pass:
class ModelError(Exception):
"Models can raise this error, which will be displayed to the user"

pass
Black maintainer Jelle Zijlstra confirmed that this is intended behavior with respect to Black's 2025 stable style [ https://substack.com/redirect/7ff9fcc7-bc3e-44ae-a249-72a9fb9f43af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but also helped me understand that the pass there is actually unnecessary so I can fix the aesthetics by removing that entirely [ https://substack.com/redirect/11dc06ef-ef16-4b56-9cc6-d12308bbb776?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I'm linking to this issue because it's a neat example of how I like to include steps-to-reproduce using uvx [ https://substack.com/redirect/0995c58d-c9cd-4d6d-b7b2-2da890ee8b26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to create one-liners you can paste into a terminal to see the bug that I'm reporting. In this case I shared the following:
Here's a way to see that happen using uvx. With the previous Black version:
echo 'class ModelError(Exception):
"Models can raise this error, which will be displayed to the user"
pass' | uvx --with 'black==24.10.0' black -
This outputs:
class ModelError(Exception):
"Models can raise this error, which will be displayed to the user"
pass
All done! ✨ 🍰 ✨
1 file left unchanged.
But if you bump to 25.1.0 this happens:
echo 'class ModelError(Exception):
"Models can raise this error, which will be displayed to the user"
pass' | uvx --with 'black==25.1.0' black -
Output:
class ModelError(Exception):
"Models can raise this error, which will be displayed to the user"

pass
reformatted -

All done! ✨ 🍰 ✨
1 file reformatted.
Via David Szotten [ https://substack.com/redirect/8e226841-373a-41f3-9e39-a562e3f8016c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I learned that you can use uvx black@25.1.0 here instead.
Quote 2025-02-01
Basically any resource on a difficult subject—a colleague, Google, a published paper—will be wrong or incomplete in various ways. Usefulness isn’t only a matter of correctness.
For example, suppose a colleague has a question she thinks I might know the answer to. Good news: I have some intuition and say something. Then we realize it doesn’t quite make sense, and go back and forth until we converge on something correct.
Such a conversation is full of BS but crucially we can interrogate it and get something useful out of it in the end. Moreover this kind of back and forth allows us to get to the key point in a way that might be difficult when reading a difficult ~50-page paper.
To be clear o3-mini-high is orders of magnitude less useful for this sort of thing than talking to an expert colleague. But still useful along similar dimensions (and with a much broader knowledge base).
Daniel Litt [ https://substack.com/redirect/6c56e804-230c-4a55-b906-dd1c6fcbbc4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-02 Hacker News conversation on feature flags [ https://substack.com/redirect/bb448f45-8387-4bc1-91ca-45f1adc3150c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I posted the following comment in a thread on Hacker News about feature flags, in response to this article It’s OK to hardcode feature flags [ https://substack.com/redirect/149ae09f-55f1-4cb1-852e-63728a2d543d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This kicked off a very high quality conversation on build-vs-buy and running feature flags at scale involving a bunch of very experienced and knowledgeable people. I recommend reading the comments.
The single biggest value add of feature flags is that they de-risk deployment. They make it less frightening and difficult to turn features on and off, which means you'll do it more often. This means you can build more confidently and learn faster from what you build. That's worth a lot.
I think there's a reasonable middle ground-point between having feature flags in a JSON file that you have to redeploy to change and using an (often expensive) feature flags as a service platform: roll your own simple system.
A relational database lookup against primary keys in a table with a dozen records is effectively free. Heck, load the entire collection at the start of each request - through a short lived cache if your profiling says that would help.
Once you start getting more complicated (flags enabled for specific users etc) you should consider build-vs-buy more seriously, but for the most basic version you really can have no-deploy-changes at minimal cost with minimal effort.
There are probably good open source libraries you can use here too, though I haven't gone looking for any in the last five years.
Link 2025-02-02 A professional workflow for translation using LLMs [ https://substack.com/redirect/ad906929-320f-48ad-bea5-94fbf08f5741?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Tom Gally is a professional translator [ https://substack.com/redirect/692b0117-fe9f-4a3a-8678-615ef36e96be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] who has been exploring the use of LLMs since the release of GPT-4. In this Hacker News comment he shares a detailed workflow for how he uses them to assist in that process.
Tom starts with the source text and custom instructions, including context for how the translation will be used. Here's an imaginary example prompt [ https://substack.com/redirect/90860c5d-f1d4-4cf4-9191-bfc9d65e8fe0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which starts:
The text below in Japanese is a product launch presentation for Sony's new gaming console, to be delivered by the CEO at Tokyo Game Show 2025. Please translate it into English. Your translation will be used in the official press kit and live interpretation feed. When translating this presentation, please follow these guidelines to create an accurate and engaging English version that preserves both the meaning and energy of the original: [...]
It then lists some tone, style and content guidelines custom to that text.
Tom runs that prompt through several different LLMs and starts by picking sentences and paragraphs from those that form a good basis for the translation.
As he works on the full translation he uses Claude to help brainstorm alternatives for tricky sentences:
When I am unable to think of a good English version for a particular sentence, I give the Japanese and English versions of the paragraph it is contained in to an LLM (usually, these days, Claude) and ask for ten suggestions for translations of the problematic sentence. Usually one or two of the suggestions work fine; if not, I ask for ten more. (Using an LLM as a sentence-level thesaurus on steroids is particularly wonderful.)
He uses another LLM and prompt to check his translation against the original and provide further suggestions, which he occasionally acts on. Then as a final step he runs the finished document through a text-to-speech engine to try and catch any "minor awkwardnesses" in the result.
I love this as an example of an expert using LLMs as tools to help further elevate their work. I'd love to read more examples like this one [ https://substack.com/redirect/ad906929-320f-48ad-bea5-94fbf08f5741?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from experts in other fields.
Link 2025-02-02 llm-anthropic [ https://substack.com/redirect/994db0e5-8c03-4895-9303-eb1dc02346d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I've renamed my llm-claude-3 [ https://substack.com/redirect/11c6493e-25f5-471c-9291-88ae6dd40097?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin to llm-anthropic, on the basis that Claude 4 will probably happen at some point so this is a better name for the plugin.
If you're a previous user of llm-claude-3 you can upgrade to the new plugin like this:
llm install -U llm-claude-3
This should remove the old plugin and install the new one, because the latest llm-claude-3 depends on llm-anthropic. Just installing llm-anthropic may leave you with both plugins installed at once.
There is one extra manual step you'll need to take during this upgrade: creating a new anthropic stored key with the same API token you previously stored under claude. You can do that like so:
llm keys set anthropic --value "$(llm keys get claude)"
I released llm-anthropic 0.12 [ https://substack.com/redirect/74f27a63-6233-4d23-b4aa-faf055d3f620?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] yesterday with new features not previously included in llm-claude-3:
Support for Claude's prefill [ https://substack.com/redirect/207a0644-54dd-496c-af59-d81fd32cec55?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] feature, using the new -o prefill '{' option and the accompanying -o hide_prefill 1 option to prevent the prefill from being included in the output text. #2 [ https://substack.com/redirect/15c5330e-435e-445e-b8fb-690da8cf6a84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
New -o stop_sequences '```' option for specifying one or more stop sequences. To specify multiple stop sequences pass a JSON array of strings :-o stop_sequences '["end", "stop"].
Model options are now documented in the README.
If you install or upgrade llm-claude-3 you will now get llm-anthropic instead, thanks to a tiny package on PyPI which depends on the new plugin name. I created that with my pypi-rename [ https://substack.com/redirect/68cda1a0-c396-4fd4-b43d-52fa6a2f3ba2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] cookiecutter template.
Here's the issue for the rename [ https://substack.com/redirect/b13187e0-5e6e-4395-88b9-0fc1d4700b7b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I archived the llm-claude-3 repository on GitHub [ https://substack.com/redirect/11c6493e-25f5-471c-9291-88ae6dd40097?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and got to use the brand new PyPI archiving feature [ https://substack.com/redirect/2ecf2b5a-ce5d-4918-a291-457d94c9d2a1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to archive the llm-claude-3 project on PyPI [ https://substack.com/redirect/62e148f1-41d8-4871-8961-79ef24ef3f2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as well.
Quote 2025-02-02
[In response to a question about releasing model weights]
Yes, we are discussing. I personally think we have been on the wrong side of history here and need to figure out a different open source strategy; not everyone at OpenAI shares this view, and it's also not our current highest priority.
Sam Altman [ https://substack.com/redirect/7fa8401b-2f83-4633-a583-fd324a7418bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-02-02
Part of the concept of ‘Disruption’ is that important new technologies tend to be bad at the things that matter to the previous generation of technology, but they do something else important instead. Asking if an LLM can do very specific and precise information retrieval might be like asking if an Apple II can match the uptime of a mainframe, or asking if you can build Photoshop inside Netscape. No, they can’t really do that, but that’s not the point and doesn’t mean they’re useless. They do something else, and that ‘something else’ matters more and pulls in all of the investment, innovation and company creation. Maybe, 20 years later, they can do the old thing too - maybe you can run a bank on PCs and build graphics software in a browser, eventually - but that’s not what matters at the beginning. They unlock something else.
What is that ‘something else’ for generative AI, though? How do you think conceptually about places where that error rate is a feature, not a bug?
Benedict Evans [ https://substack.com/redirect/f86fe837-74e6-4ba9-9c5c-e003b0d757ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-02 OpenAI reasoning models: Advice on prompting [ https://substack.com/redirect/ccc6e540-fb60-46eb-8787-653e4d6679e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI's documentation for their o1 and o3 "reasoning models" includes some interesting tips on how to best prompt them:
Developer messages are the new system messages: Starting with o1-2024-12-17, reasoning models support developer messages rather than system messages, to align with the chain of command behavior described in the model spec [ https://substack.com/redirect/1950f986-2262-4297-a088-5068fd02c93c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This appears to be a purely aesthetic change made for consistency with their instruction hierarchy [ https://substack.com/redirect/700fa1ae-df12-4913-a24b-2e7bf3c19290?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] concept. As far as I can tell the old system prompts continue to work exactly as before - you're encouraged to use the new developer message type but it has no impact on what actually happens.
Since my LLM tool already bakes in a llm --system "system prompt" option which works across multiple different models from different providers I'm not going to rush to adopt this new language!
Use delimiters for clarity: Use delimiters like markdown, XML tags, and section titles to clearly indicate distinct parts of the input, helping the model interpret different sections appropriately.
Anthropic have been encouraging XML-ish delimiters [ https://substack.com/redirect/f2b10b8a-7fe0-4d51-b6b4-a6cdd170f586?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for a while (I say -ish because there's no requirement that the resulting prompt is valid XML). My files-to-prompt [ https://substack.com/redirect/9a7ae1be-9ed1-4d9b-aabe-71ee0fedee7a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool has a -c option which outputs Claude-style XML, and in my experiments this same option works great with o1 and o3 too:
git clone https://github.com/tursodatabase/limbo [ https://substack.com/redirect/1c7d5853-d9a1-4636-81fa-0059fdbbb6d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
cd limbo/bindings/python

files-to-prompt . -c | llm -m o3-mini \
-o reasoning_effort high \
--system 'Write a detailed README with extensive usage examples'
Limit additional context in retrieval-augmented generation (RAG): When providing additional context or documents, include only the most relevant information to prevent the model from overcomplicating its response.
This makes me thing that o1/o3 are not good models to implement RAG on at all - with RAG I like to be able to dump as much extra context into the prompt as possible and leave it to the models to figure out what's relevant.
Try zero shot first, then few shot if needed: Reasoning models often don't need few-shot examples to produce good results, so try to write prompts without examples first. If you have more complex requirements for your desired output, it may help to include a few examples of inputs and desired outputs in your prompt. Just ensure that the examples align very closely with your prompt instructions, as discrepancies between the two may produce poor results.
Providing examples remains the single most powerful prompting tip I know, so it's interesting to see advice here to only switch to examples if zero-shot doesn't work out.
Be very specific about your end goal: In your instructions, try to give very specific parameters for a successful response, and encourage the model to keep reasoning and iterating until it matches your success criteria.
This makes sense: reasoning models "think" until they reach a conclusion, so making the goal as unambiguous as possible leads to better results.
Markdown formatting: Starting with o1-2024-12-17, reasoning models in the API will avoid generating responses with markdown formatting. To signal to the model when you do want markdown formatting in the response, include the string Formatting re-enabled on the first line of your developer message.
This one was a real shock to me! I noticed that o3-mini was outputting • characters instead of Markdown * bullets and initially thought that was a bug [ https://substack.com/redirect/9eab7e0b-07ba-4d90-8ed2-1d51bcfbbbde?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I first saw this while running this prompt against limbo/bindings/python [ https://substack.com/redirect/c6727395-fbba-42fe-b14e-16ab982310f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using files-to-prompt [ https://substack.com/redirect/9a7ae1be-9ed1-4d9b-aabe-71ee0fedee7a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
git clone https://github.com/tursodatabase/limbo [ https://substack.com/redirect/1c7d5853-d9a1-4636-81fa-0059fdbbb6d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
cd limbo/bindings/python

files-to-prompt . -c | llm -m o3-mini \
-o reasoning_effort high \
--system 'Write a detailed README with extensive usage examples'
Here's the full result [ https://substack.com/redirect/220fe0f5-091c-4653-a982-bfd7359fa2c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which includes text like this (note the weird bullets):
Features
--------
• High‑performance, in‑process database engine written in Rust
• SQLite‑compatible SQL interface
• Standard Python DB‑API 2.0–style connection and cursor objects
I ran it again with this modified prompt: > Formatting re-enabled. Write a detailed README with extensive usage examples. And this time got back proper Markdown, rendered in this Gist [ https://substack.com/redirect/071fcc97-00ed-4450-b91f-2008e662151e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. That did a really good job, and included bulleted lists using this valid Markdown syntax instead:
- make test: Run tests using pytest.
- make lint: Run linters (via [ruff](https://github.com/astral-sh/ruff [ https://substack.com/redirect/555b7c6f-4b8d-4931-ad1d-5c81a84ec02d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])).
- make check-requirements: Validate that the requirements.txt files are in sync with pyproject.toml.
- make compile-requirements: Compile the requirements.txt files using pip-tools.
(Using LLMs like this to get me off the ground with under-documented libraries is a trick I use several times a week.)
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVFl6TWpjeU9UVXNJbWxoZENJNk1UY3pPRFV6TVRNeU1Td2laWGh3SWpveE56Y3dNRFkzTXpJeExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuOGR4MExGbE9qdk93OUsxbU1KeGM2MTFnU3VBR2Y1Z1YybGk0eWw1TE5VbyIsInAiOjE1NjMyNzI5NSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzM4NTMxMzIxLCJleHAiOjE3NDExMjMzMjEsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.okcyPRtXo-KT-asZwZCwQd6Gh5zhwlv14u45jrwlo9Q?
