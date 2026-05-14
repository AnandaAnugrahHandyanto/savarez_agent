# QvQ - Qwen's new visual reasoning model

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-12-28T06:21:18.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/qvq-qwens-new-visual-reasoning-model

In this newsletter:
Trying out QvQ - Qwen's new visual reasoning model
Plus 7 links and 5 quotations and 2 TILs
Trying out QvQ - Qwen's new visual reasoning model [ https://substack.com/redirect/68089638-1143-4c40-b38f-07677c766274?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-12-24
I thought we were done for major model releases in 2024, but apparently not: Alibaba's Qwen team just dropped the Apache 2.0 licensed Qwen licensed (the license changed [ https://substack.com/redirect/d2468b07-f415-474d-a65e-d89997e4fe1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) QvQ-72B-Preview, "an experimental research model focusing on enhancing visual reasoning capabilities".
Their blog post is titled QvQ: To See the World with Wisdom [ https://substack.com/redirect/3a577450-1e7c-492b-86e2-80c957b8c6f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - similar flowery language to their QwQ announcement QwQ: Reflect Deeply on the Boundaries of the Unknown [ https://substack.com/redirect/b977a89b-e7cf-4cf7-a582-f16c988a4290?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a few weeks ago in November.
It's a vision-focused follow-up to QwQ, which I wrote about previousy [ https://substack.com/redirect/b38336b1-26f6-4b61-9d97-fdca56fa8890?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. QwQ is an impressive openly licensed inference-scaling model: give it a prompt and it will think out loud over many tokens while trying to derive a good answer, similar to OpenAI's o1 and o3 models.
The new QvQ adds vision to the mix. You can try it out on Hugging Face Spaces [ https://substack.com/redirect/444a2b20-2db3-45fa-948e-b0ce21432c0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it accepts an image and a single prompt and then streams out a very long response where it thinks through the problem you have posed it. There's no option to send a follow-up prompt.
I've tried it out with a bunch of things, with mixed results - but it's really fun seeing how it works through a problem.
My most successful prompt was "Count the pelicans" with this image:
Here's the full response [ https://substack.com/redirect/a154627d-06cf-4ddf-a6a8-8bddaa9786a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Some highlights:
So I've got this picture of some pelicans, and I need to count them. Let me see... First off, I know that pelicans are those big birds with the massive beaks, right? [...]
Let me try counting again, more carefully this time. Starting from the left:
The first pelican is fully visible, standing at the front.
Behind it, slightly to the right, is the second pelican.
Then, further back, there's a third pelican.
And next to that one, there's a fourth pelican.
So, that's four pelicans in total. But, I notice that on the far right of the image, there's part of another bird, maybe a pelican's back or tail feathers, but it's not fully in the frame, so I don't think I should count it as a whole pelican.
Something about the tone of voice it uses, "First off, I know that pelicans are those big birds with the massive beaks, right?", tickles me.
I also tried this on a much harder image [ https://substack.com/redirect/d45bf796-1c24-4393-abf0-f9ba704ad66d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it counted 17 which looks about right to me but honestly I have trouble with that image myself.
I fed in one of the ARC-AGI puzzles [ https://substack.com/redirect/7229aa16-4efd-4529-b18f-b444b1aaf1bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that o3 had failed at.
It produced a very lengthy chain of thought [ https://substack.com/redirect/6e837248-9f62-4d8f-8e7e-ee63e164107e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that was almost entirely incorrect, but had some interesting "ideas" in it:
[...] Let me try to think in terms of cellular automata rules, like Conway's Game of Life.
In Game of Life, each cell's state in the next generation is determined by its current state and the states of its eight neighbors.
Perhaps a similar rule applies here.
Finally, I asked it to "Estimate the height of the dinosaur" against this image (which, as it correctly noted, is actually an inflatable dragon):
I'm not sure this task is even possible given the lack of items in the frame of comparable known height. It had a good go at it [ https://substack.com/redirect/9b3c79ef-8166-431e-9989-ac8ddf702e06?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] though! I particularly enjoyed how it began:
So I've got this inflatable Christmas decoration, and it's a dragon! But not just any dragon—it's a green dragon wearing a Santa hat and a red and white scarf. And get this, there's a reindeer on its back, also wearing a Santa hat and holding onto the dragon's wings. It's pretty festive and colorful, with lots of vibrant greens, reds, and yellows.
The dragon has these big, friendly eyes and a smiling face, which makes it look really cheerful. Its wings are spread out, and it has white claws on its feet. The reindeer is brown with antlers and seems to be enjoying the ride on the dragon's back.
Now, the question is, how tall is this inflatable dragon? I need to estimate its height. Let me see. I'm standing next to it, and I'm about 5 feet 10 inches tall. The dragon is definitely taller than me. Maybe around 8 or 9 feet high? But I should try to be more precise.
I wonder how it decided that its own height was 5 feet 10 inches!
Running QvQ locally
All of my experiments so far have used the hosted Hugging Face demo [ https://substack.com/redirect/444a2b20-2db3-45fa-948e-b0ce21432c0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I'm hoping to try it out on my own laptop soon - I think it should just fit in 64GB of M2, maybe with a smaller quantization.
Right now the options are:
Qwen/QVQ-72B-Preview [ https://substack.com/redirect/6716b169-a96d-4936-978f-ea40723c5e86?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hugging Face has the GPU model weights, for use with Hugging Face Transformers and the qwen-vl-utils [ https://substack.com/redirect/1ee38f05-4d20-488e-8348-c3298d9f07b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]Python package.
Prince Canuma converted the model for Apple's MLX framework [ https://substack.com/redirect/0c362694-8543-4f38-8b1c-e786fd183843?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as mlx-community/qvq-72b-preview [ https://substack.com/redirect/486c6da4-68cd-4fcb-ab8b-4b6f1109faef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and got it working with his excellent mlx-vlm [ https://substack.com/redirect/b5272e94-4731-472b-b9ce-a7d1eaf48013?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] package.
As a happy user of Ollama's qwq port [ https://substack.com/redirect/82113f88-da83-4011-90a0-e91b4b7551f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I'm hoping they add a QvQ release at some point soon as well.
Running QvQ on my Mac using mlx-vlm
Update: I successfully ran QvQ on my 64GB M2 MacBook Pro using Prince Canuma's mlx-vlm via uv run with the following command:
uv run --with 'numpysystem
You are a helpful and harmless assistant. You are Qwen developed by Alibaba. You should think step-by-step.
user
describe this
assistant

Alright, I've got this "Text to Video" tool to explore. It seems pretty advanced, allowing me to turn text descriptions into actual videos. The interface looks user-friendly, with a dark theme that's easy on the eyes. On the left side, there's a panel where I can input my text prompt. It already has an example filled in: "A pelican riding a bicycle along a coastal path overlooking a harbor."

That sounds interesting! I can see four different video thumbnails on the right side, each showing variations of this scene. One of them even has the pelican wearing a helmet, which adds a humorous touch. Another shows the pelican standing next to a bicycle, almost as if it's ready to hop on and start pedaling.

Below the text input, there are some style options like "photorealistic," "35mm film," "minimal," "sketchy," "handmade," and "abstract." These probably let me choose the visual style of the video. For now, I'll stick with the default settings.

At the bottom of the left panel, there are two buttons: "Start over" and "Create videos." I guess "Create videos" is the one I need to press to generate the videos based on my text prompt.

Let me think about this. I want to see what kind of videos this tool can produce based on my description. The example prompt is already filled in, so maybe I should just go ahead and click "Create videos" to see what happens.

Wait a minute, the prompt mentions a coastal path overlooking a harbor. In the thumbnails, I can see a background with water and boats, which matches the description. It's cool how the tool has interpreted the text into visual elements.

I should also pay attention to the "Visual Prompt" section, which says "View only." That probably means I can't edit it directly, but I can view the generated videos based on this prompt.

Hmm, maybe I should try changing the prompt to see different results. For example, instead of a pelican riding a bicycle, maybe I could describe a different scene. But for now, I'll stick with the given example to understand how it works.

After clicking "Create videos," I expect to see the videos being generated. There might be a loading process, depending on the complexity of the prompt and the tool's processing speed.

Once the videos are ready, I can preview them to see how well they match my description. If I'm not satisfied, I can always go back and adjust the prompt or try different style options.

Overall, this seems like a powerful tool for creating custom videos based on textual descriptions. It could be really useful for storytelling, presentations, or even just for fun, experimenting with different scenes and styles.

I think I'll spend some time exploring the different style options to see how they affect the final videos. For instance, selecting "35mm film" might give the videos a vintage, cinematic look, while "abstract" could produce more artistic and less realistic visuals.

Also, I wonder if there's a way to customize more specific aspects, like the camera angle, lighting, or movement. Maybe after generating the initial videos, there are additional editing options available.

In summary, I'm excited to use this Text to Video tool and see what kind of creative possibilities it opens up. With a bit of practice, I could probably create some impressive visual content just by describing what I want to see.

**Final Answer**

To proceed with generating videos based on the provided text prompt, I need to click on the "Create videos" button. This action will initiate the process of converting the textual description into visual content, resulting in multiple video thumbnails that can be previewed for further use or adjustments.
==========
Prompt: 0.870 tokens-per-sec
Generation: 7.694 tokens-per-sec

The license changed from Apache 2.0 to Qwen
When I wrote this post yesterday the LICENSE file in the Hugging Face repository was Apache 2.0. Just after midnight UTC on 25th December this commit [ https://substack.com/redirect/3c940a81-e56c-4a31-9502-f4033f4ef03f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] landed updating the QVQ-72B-Previewlicense file to the Qwen license [ https://substack.com/redirect/ff4fb19c-6eec-4b13-83f3-81e96a5fc32b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] instead.
This looks to me like they were correcting a mistake, not changing their policy. The README.md [ https://substack.com/redirect/3420a79d-c61d-4337-97e5-7a57113998f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for that repository has this block of YAML:
license: other
license_name: qwen
And commits to that README [ https://substack.com/redirect/878ea908-e1ef-4a90-af3e-3f31787da8d5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at one point linked to the Qwen2.5-72B-Instruct copy of the Qwen license [ https://substack.com/redirect/3a7845e7-685f-45a4-9356-9c1f2d8c6b63?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The QwQ model repository continues to list Apache 2.0 [ https://substack.com/redirect/cd626a4b-1685-46d6-bcc2-c9451bfa0fe7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which matches the YAML in its README [ https://substack.com/redirect/dcbf5155-43b9-4570-81c3-8fcdd30b08da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as well.
So it looks to me like the intention is for QvQ and Qwen2.5-72B-Instruct to be Qwen licensed, while QwQ is Apache 2.0.
Link 2024-12-22 What happened to the world's largest tube TV? [ https://substack.com/redirect/8adb3eba-a2d5-41d5-9f9a-e598fd5a4827?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This YouTube video is an absolute delight.
Shank Mods describes the legendary Sony PVM-4300 [ https://substack.com/redirect/b3bc447d-49aa-456f-8532-76fd4c431125?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - the largest CRT television ever made, released by Sony in 1989 and weighing over 400lb. CRT enthusiasts had long debated its very existence, given the lack of known specimens outside of Sony's old marketing materials. Then Shank tracked a working one down... on the second floor of a 300 year old Soba noodle restaurant in Osaka, Japan.
This story of how they raced to rescue the TV before the restaurant was demolished, given the immense difficulty of moving a 400lb television (and then shipping it to the USA), is a fantastic ride.
Link 2024-12-22 openai/openai-openapi [ https://substack.com/redirect/5d934575-52f7-476c-a38e-b5f72d3a28af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Seeing as the LLM world has semi-standardized on imitating OpenAI's API format for a whole host of different tools, it's useful to note that OpenAI themselves maintain a dedicated repository for a OpenAPI [ https://substack.com/redirect/9b5c1d44-da37-40a6-9007-e328072a8ce7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] YAML representation of their current API.
(I get OpenAI and OpenAPI typo-confused all the time, so openai-openapi is a delightfully fiddly repository name.)
The openapi.yaml [ https://substack.com/redirect/ced67329-3d77-4f49-8f0f-8c5e6995b1b3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] file itself is over 26,000 lines long, defining 76 API endpoints ("paths" in OpenAPI terminology) and 284 "schemas" for JSON that can be sent to and from those endpoints. A much more interesting view onto it is the commit history [ https://substack.com/redirect/cae34834-f4fd-49be-8483-c66e8acd83f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for that file, showing details of when each different API feature was released.
Browsing 26,000 lines of YAML isn't pleasant, so I got Claude [ https://substack.com/redirect/c2dcc8b4-132e-4d3b-a3a3-d42bdfcb9927?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to build me a rudimentary YAML expand/hide exploration tool. Here's that tool running against the OpenAI schema, loaded directly from GitHub via a CORS-enabled fetchcall: https://tools.simonwillison.net/yaml-explorer#.eyJ1c... [ https://substack.com/redirect/52b8049f-0b2a-43dd-bf5d-2c452b1e0d96?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - the code after that fragment is a base64-encoded JSON for the current state of the tool (mostly Claude's idea).
The tool is a little buggy - the expand-all option doesn't work quite how I want - but it's useful enough for the moment.
Update: It turns out the petstore.swagger.io [ https://substack.com/redirect/740132b2-54fc-4816-a34a-ac37106cbfdc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] demo has an (as far as I can tell) undocumented ?url=parameter which can load external YAML files, so here's openai-openapi/openapi.yaml [ https://substack.com/redirect/b9f5f443-f239-41e2-9927-d9423f0b315d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in an OpenAPI explorer interface.
Quote 2024-12-23
Whether you’re an AI-programming skeptic or an enthusiast, the reality is that many programming tasks are beyond the reach of today’s models. But many decent dev tools are actually quite easy for AI to build, and can help the rest of the programming go smoother. In general, these days any time I’m spending more than a minute staring at a JSON blob, I consider whether it’s worth building a custom UI for it.
Geoffrey Litt [ https://substack.com/redirect/9c8020fe-1177-4eff-b612-fd38cb40c1d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-12-23
There’s been a lot of strange reporting recently about how ‘scaling is hitting a wall’ – in a very narrow sense this is true in that larger models were getting less score improvement on challenging benchmarks than their predecessors, but in a larger sense this is false – techniques like those which power O3 means scaling is continuing (and if anything the curve has steepened), you just now need to account for scaling both within the training of the model and in the compute you spend on it once trained.
Jack Clark [ https://substack.com/redirect/e43f49ae-c831-4bc8-8a8c-159c509d71a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
TIL 2024-12-24 Named Entity Resolution with dslim/distilbert-NER [ https://substack.com/redirect/27b0b4d7-6d68-4843-8d10-95f7168ee73d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I was exploring the original BERT model from 2018, which is mainly useful if you fine-tune a model on top of it for a specific task. …
Link 2024-12-24 Finally, a replacement for BERT: Introducing ModernBERT [ https://substack.com/redirect/83e32ccf-a085-4645-84a8-7f2c2d99ced7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
BERT [ https://substack.com/redirect/4812b389-a9ed-49c3-b0be-25b7f1d3aeac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) was an early language model released by Google in October 2018. Unlike modern LLMs it wasn't designed for generating text. BERT was trained for masked token prediction and was generally applied to problems like Named Entity Recognition or Sentiment Analysis. BERT also wasn't very useful on its own - most applications required you to fine-tune a model on top of it.
In exploring BERT I decided to try out dslim/distilbert-NER [ https://substack.com/redirect/d50e8a13-2ef0-4365-8e55-3ff323216787?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a popular Named Entity Recognition model fine-tuned on top of DistilBERT (a smaller distilled version of the original BERT model). Here are my notes [ https://substack.com/redirect/27b0b4d7-6d68-4843-8d10-95f7168ee73d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on running that using uv run.
Jeremy Howard's Answer.AI [ https://substack.com/redirect/8fbe7077-5fb7-4f26-8630-ec1d995d2c9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] research group, LightOn [ https://substack.com/redirect/9bb28a75-365b-477d-b4cb-6d64dad09dac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and friends supported the development of ModernBERT, a brand new BERT-style model that applies many enhancements from the past six years of advances in this space.
While BERT was trained on 3.3 billion tokens, producing 110 million and 340 million parameter models, ModernBERT trained on 2 trillion tokens, resulting in 140 million and 395 million parameter models. The parameter count hasn't increased much because it's designed to run on lower-end hardware. It has a 8192 token context length, a significant improvement on BERT's 512.
I was able to run one of the demos from the announcement post using uv run like this (I'm not sure why I had to use numpy<2.0 but without that I got an error about cannot import name 'ComplexWarning' from 'numpy.core.numeric'):
uv run --with 'numpy<2.0' --with torch --with 'git+https://github.com/huggingface/transformers.git [ https://substack.com/redirect/e73098a7-1b4a-4c02-a3d9-8bf58771863d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]' python
Then this Python:
import torch
from transformers import pipeline
from pprint import pprint
pipe = pipeline(
"fill-mask",
model="answerdotai/ModernBERT-base",
torch_dtype=torch.bfloat16,
)
input_text = "He walked to the [MASK]."
results = pipe(input_text)
pprint(results)
Which downloaded 573MB to ~/.cache/huggingface/hub/models--answerdotai--ModernBERT-base and output:
[{'score': 0.11669921875,
'sequence': 'He walked to the door.',
'token': 3369,
'token_str': ' door'},
{'score': 0.037841796875,
'sequence': 'He walked to the office.',
'token': 3906,
'token_str': ' office'},
{'score': 0.0277099609375,
'sequence': 'He walked to the library.',
'token': 6335,
'token_str': ' library'},
{'score': 0.0216064453125,
'sequence': 'He walked to the gate.',
'token': 7394,
'token_str': ' gate'},
{'score': 0.020263671875,
'sequence': 'He walked to the window.',
'token': 3497,
'token_str': ' window'}]
I'm looking forward to trying out models that use ModernBERT as their base. The model release is accompanied by a paper (Smarter, Better, Faster, Longer: A Modern Bidirectional Encoder for Fast, Memory Efficient, and Long Context Finetuning and Inference [ https://substack.com/redirect/fbb1c35c-0ec5-4d26-94f9-bf97d16374a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and new documentation [ https://substack.com/redirect/4c3f29f1-77cb-43c1-85cb-bd3980717022?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for using it with the Transformers library.
Quote 2024-12-24
[On Reddit] we had to look up every single comment on the page to see if you had voted on it [...]
But with a bloom filter, we could very quickly look up all the comments and get back a list of all the ones you voted on (with a couple of false positives in there). Then we could go to the cache and see if your actual vote was there (and if it was an upvote or a downvote). It was only after a failed cache hit did we have to actually go to the database.
But that bloom filter saved us from doing sometimes 1000s of cache lookups.
Jeremy Edberg [ https://substack.com/redirect/0fc406ef-c93b-4cdb-bf9a-5774fbbabf57?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-12-24
it's really hard not to be obsessed with these tools. It's like having a bespoke, free, (usually) accurate curiosity-satisfier in your pocket, no matter where you go - if you know how to ask questions, then suddenly the world is an audiobook
Paige Bailey [ https://substack.com/redirect/f355f106-1aaf-46e9-a477-439a48c12459?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
TIL 2024-12-25 Calculating the size of all LFS files in a repo [ https://substack.com/redirect/9639d27e-6b11-40c6-94a1-d46df671389b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wanted to know how large the deepseek-ai/DeepSeek-V3-Base [ https://substack.com/redirect/b41151dd-917f-4296-b720-03673e33ab1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repo on Hugging Face was without actually downloading all of the files. …
Link 2024-12-25 deepseek-ai/DeepSeek-V3-Base [ https://substack.com/redirect/b41151dd-917f-4296-b720-03673e33ab1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
No model card or announcement yet, but this new model release from Chinese AI lab DeepSeek (an arm of Chinese hedge fund High-Flyer [ https://substack.com/redirect/fde2cb77-3365-4e6b-ba15-f01f4c84c3e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])) looks very significant.
It's a huge model - 685B parameters, 687.9 GB on disk (TIL how to size a git-lfs repo [ https://substack.com/redirect/9639d27e-6b11-40c6-94a1-d46df671389b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). The architecture is a Mixture of Experts [ https://substack.com/redirect/4955c868-0f5f-46ec-be2b-7178b9342845?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with 256 experts, using 8 per token.
For comparison, Meta AI's largest released model is their Llama 3.1 model [ https://substack.com/redirect/9604ef65-591c-4716-bef5-d6c49ccd7223?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with 405B parameters.
The new model is apparently available to some people via both chat.deepseek.com [ https://substack.com/redirect/2aae81b9-735b-4816-b22d-f341a3767869?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the DeepSeek API as part of a staged rollout.
Paul Gauthier got API access and used it [ https://substack.com/redirect/05729500-625d-4e0c-a3c5-d32996f82817?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to update his new Aider Polyglot leaderboard [ https://substack.com/redirect/78eaaa42-f141-4f43-8241-0071aeae526d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - DeepSeek v3 preview scored 48.4%, putting it in second place behind o1-2024-12-17 (high) and in front of both claude-3-5-sonnet-20241022 and gemini-exp-1206!
I never know if I can believe models or not (the first time I asked "what model are you?" it claimed to be "based on OpenAI's GPT-4 architecture"), but I just got this result using LLM [ https://substack.com/redirect/d99ad0d6-a405-41ff-a220-af67adda7289?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]and the llm-deepseek [ https://substack.com/redirect/865d9d6d-9fde-4c78-b5a0-32ea15b7dfc1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin:
llm -m deepseek-chat 'what deepseek model are you?'
I'm DeepSeek-V3 created exclusively by DeepSeek. I'm an AI assistant, and I'm at your service! Feel free to ask me anything you'd like. I'll do my best to assist you.
Here's my initial experiment log [ https://substack.com/redirect/b7281913-4346-4dc4-9dd3-fca403e078f1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-12-26 Cognitive load is what matters [ https://substack.com/redirect/ff378331-d891-4ebd-b87a-f2e2e94ee34c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Excellent living document (the underlying repo has 625 commits [ https://substack.com/redirect/b83b8477-0eee-455b-91bc-5393d75fa2ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] since being created in May 2023) maintained by Artem Zakirullin about minimizing the cognitive load needed to understand and maintain software.
This all rings very true to me. I judge the quality of a piece of code by how easy it is to change, and anything that causes me to take on more cognitive load - unraveling a class hierarchy, reading though dozens of tiny methods - reduces the quality of the code by that metric.
Lots of accumulated snippets of wisdom in this one.
Mantras like "methods should be shorter than 15 lines of code" or "classes should be small" turned out to be somewhat wrong.
Quote 2024-12-26
Providers and deployers of AI systems shall take measures to ensure, to their best extent, a sufficient level of AI literacy of their staff and other persons dealing with the operation and use of AI systems on their behalf, taking into account their technical knowledge, experience, education and training and the context the AI systems are to be used in, and considering the persons or groups of persons on whom the AI systems are to be used.
EU Artificial Intelligence Act [ https://substack.com/redirect/e895a5eb-e574-4d4a-8857-bffc2ce572b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-12-26 DeepSeek_V3.pdf [ https://substack.com/redirect/f8b16fdb-eb23-41ea-8609-1c4effee0d4f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The DeepSeek v3 paper (and model card [ https://substack.com/redirect/f89b731a-63f3-476a-8a70-650a0e7f96a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) are out, after yesterday's mysterious release of the undocumented model weights [ https://substack.com/redirect/fc5d6394-487f-4d23-92d8-abedef7d3c8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Plenty of interesting details in here. The model pre-trained on 14.8 trillion "high-quality and diverse tokens" (not otherwise documented).
Following this, we conduct post-training, including Supervised Fine-Tuning (SFT) and Reinforcement Learning (RL) on the base model of DeepSeek-V3, to align it with human preferences and further unlock its potential. During the post-training stage, we distill the reasoning capability from the DeepSeek-R1 series of models, and meanwhile carefully maintain the balance between model accuracy and generation length.
By far the most interesting detail though is how much the training cost. DeepSeek v3 trained on 2,788,000 H800 GPU hours at an estimated cost of $5,576,000. For comparison, Meta AI's Llama 3.1 405B (smaller than DeepSeek v3's 685B parameters) trained on 11x that [ https://substack.com/redirect/a398c4a0-ee71-4c79-9dc2-4347654c87d7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 30,840,000 GPU hours, also on 15 trillion tokens.
DeepSeek v3 benchmarks comparably to Claude 3.5 Sonnet, indicating that it's now possible to train a frontier-class model (at least for the 2024 version of the frontier) for less than $6 million!
Andrej Karpathy [ https://substack.com/redirect/d18e5c20-91bb-4e16-9aa4-370d950e8111?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
For reference, this level of capability is supposed to require clusters of closer to 16K GPUs, the ones being brought up today are more around 100K GPUs. E.g. Llama 3 405B used 30.8M GPU-hours, while DeepSeek-V3 looks to be a stronger model at only 2.8M GPU-hours (~11X less compute). If the model also passes vibe checks (e.g. LLM arena rankings are ongoing, my few quick tests went well so far) it will be a highly impressive display of research and engineering under resource constraints.
DeepSeek also announced their API pricing [ https://substack.com/redirect/a845d8a8-8bca-453a-a32c-f13c2161ffb8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. From February 8th onwards:
Input: $0.27/million tokens ($0.07/million tokens with cache hits)
Output: $1.10/million tokens
Claude 3.5 Sonnet is currently $3/million for input and $15/million for output, so if the models are indeed of equivalent quality this is a dramatic new twist in the ongoing LLM pricing wars.
Link 2024-12-27 Open WebUI [ https://substack.com/redirect/2689a828-ac23-4044-869d-2960bf2ebe38?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I tried out this open source (MIT licensed, JavaScript and Python) localhost UI for accessing LLMs today for the first time. It's very nicely done.
I ran it with uvx [ https://substack.com/redirect/dbe263eb-687f-4b78-9c99-39f5d8d40dde?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
uvx --python 3.11 open-webui serve

On first launch it installed a bunch of dependencies and then downloaded 903MB to ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2 - a copy of the all-MiniLM-L6-v2 [ https://substack.com/redirect/ba431fb0-e666-432e-937a-90b1e2c8df4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] embedding model, presumably for its RAG feature [ https://substack.com/redirect/b53743f4-2bea-47e5-9135-22c082d8bfda?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It then presented me with a working Llama 3.2:3b chat interface, which surprised me because I hadn't spotted it downloading that model. It turns out that was because I have Ollama [ https://substack.com/redirect/0e59d63e-9f6d-4b4f-aeee-22e352c5366f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] running on my laptop already (with several models, including Llama 3.2:3b, already installed) - and Open WebUI automatically detected Ollama and gave me access to a list of available models.
I found a "knowledge" section and added all of the Datasette documentation (by dropping in the .rst files from the docs) - and now I can type # in chat to search for a file, add that to the context and then ask questions about it directly.
I selected the spatialite.rst.txt file, prompted it with "How do I use SpatiaLite with Datasette" and got back this [ https://substack.com/redirect/31c9a12a-89ca-4809-8a84-ec545d4c221e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
That's honestly a very solid answer, especially considering the Llama 3.2 3B model from Ollama is just a 1.9GB file! It's impressive how well that model can handle basic Q&A and summarization against text provided to it - it somehow has a 128,000 token context size.
Open WebUI has a lot of other tricks up its sleeve: it can talk to API models such as OpenAI directly, has optional integrations with web search and custom tools and logs every interaction to a SQLite database. It also comes with extensive documentation [ https://substack.com/redirect/a036e4dd-6d2e-4789-84e1-dac3950f6e19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVE0zTURjME5USXNJbWxoZENJNk1UY3pOVE0yTnpBd055d2laWGh3SWpveE56WTJPVEF6TURBM0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuVk1hR3Y5NUlhc25mZm00NzIwOC1acHRvOFlZekpRTXdNVWdIVkJnd2hDayIsInAiOjE1MzcwNzQ1MiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzM1MzY3MDA3LCJleHAiOjE3Mzc5NTkwMDcsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.wGQ86I-k67-OVULMm1FsfXbYtIUftA0joQ2npQAtRmM?
