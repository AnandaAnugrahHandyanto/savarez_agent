# Open Agentic LLMs Proliferate, Robot Removes Gallbladders, Reasoning Models Boost Emissions, OpenAI Re-Opens

**From:** "The Batch @ DeepLearning.AI" <thebatch@deeplearning.ai>
**Date:** 2025-08-06T19:22:51.000Z
**Folder:** batch

---

Recently Meta made headlines with unprecedented, massive compensation packages for AI model builders exceeding $100M (sometimes spread over multiple years).

View in browser

The Batch top banner - August 6, 2025

Subscribe    Submit a tip (mailto:thebatch@deeplearning.ai?subject=RE%3A%20Tips%20and%20News)

Dear friends,

Recently Meta made headlines  with unprecedented, massive compensation packages for AI model builders exceeding $100M (sometimes spread over multiple years). With the company planning to spend $66B-72B this year on capital expenses such as data centers  , a meaningful fraction of which will be devoted to AI, from a purely financial point of view, it’s not irrational to spend a few extra billion dollars on salaries to make sure this hardware is used well.

A typical software-application startup that’s not involved in training foundation models might spend 70-80% of its dollars on salaries, 5-10% on rent, and 10-25% on other operating expenses (cloud hosting, software licenses, marketing, legal/accounting, etc.). But scaling up models is so capital-intensive, salaries are a small fraction of the overall expense. This makes it feasible for businesses in this area to pay their relatively few employees exceptionally well. If you’re spending tens of billions of dollars on GPU hardware, why not spend just a tenth of that on salaries? Even before Meta’s recent offers, salaries of AI model trainers have been high, with many being paid $5-10M/year, although Meta has raised these numbers to new heights.

Meta carries out many activities, including run Facebook, Instagram, WhatsApp, and Oculus. But the Llama/AI-training part of its operations is particularly capital-intensive. Many of Meta’s properties rely on user-generated content (UGC) to attract attention, which is then monetized through advertising. AI is a huge threat and opportunity to such businesses: If AI-generated content (AIGC) substitutes for UGC to capture people's attention to sell ads against, this will transform the social-media landscape.

This is why Meta — like TikTok, YouTube, and other social-media properties — is paying close attention to AIGC, and why making significant investments in AI is rational. Further, when Meta hires a key employee, not only does it gain the future work output of that person, but it also potentially gets insight into a competitor’s technology, which also makes its willingness to pay high salaries a rational business move (so long as it does not adversely affect the company’s culture).

The pattern of capital-intensive businesses compensating employees extraordinarily well is not new. For example, Netflix expects to spend a huge $18B this year on content. This makes the salary expense of paying its 14,000 employees a small fraction of the total expense, which allows the company to routinely pay above-market salaries. Its ability to spend this way also shapes a distinctive culture  that includes elements of “we’re a sports team, not a family” (which seems to work for Netflix but isn’t right for everyone). In contrast, a labor-intensive manufacturing business like Foxconn, which employs over 1 million people globally, has to be much more price-sensitive in what it pays people.

Even a decade ago, when I led a team that worked to scale up AI, I built spreadsheets that modeled how much of my budget to allocate toward salaries and how much to allocate toward GPUs (using a custom model for how much productive output N employees and M GPUs would lead to, so I could optimize N and M subject to my budget constraint). Since then, the business of scaling up AI has skewed the spending significantly toward GPUs.

I’m happy for the individuals who are getting large pay packages. And regardless of any individual's pay, I’m grateful for the contributions of everyone working in AI. Everyone in AI deserves a good salary, and while the gaps in compensation are growing, I believe this reflects the broader phenomenon that developers who work in AI, at this moment in history, have an opportunity to make a huge impact and do world-changing work.

Keep building!

Andrew

A MESSAGE FROM DEEPLEARNING.AI

Promo banner for: "Claude Code: A Highly Agentic Coding Assistant"

Use the agentic coding assistant Claude Code to build applications faster.

In this short course, you’ll learn to guide Anthropic’s AI coding assistant to explore codebases, add features, refactor, and debug. Apply best practices in projects like a RAG chatbot and a Figma-based web app. Enroll now

News

The Re-Opening of OpenAI

The “open” is back in play at OpenAI.

What’s new: OpenAI released its first open-weights model since 2019’s GPT-2. The gpt-oss  family comprises two mixture-of-experts (MoE) models, gpt-oss-120b and gpt-oss-20b, that are designed for agentic applications and free to use and modify.

- Input/output: Text in (up to 128,000 tokens), text out (up to 33,000 tokens)
- Architecture: gpt-oss-120b: MoE transformer, 117 billion parameters total, 5.1 billion parameters active per token; gpt-oss-20b: MoE transformer, 21 billion parameters total, 3.6 billion parameters active per token
- Performance: Generally ahead of o3-mini, behind o3 and o4-mini
- Availability: Web demo  (free), weights   available for commercial and noncommercial use under Apache 2.0 license
- Features: adjustable chain-of-thought reasoning levels (high, medium, low), full access to the chain of thought, tool use
- Undisclosed: Details of training data and methods

How it works: The team pretrained the gpt-oss models on trillions of tokens of text including general knowledge, coding, math, and science. Fine-tuning focused on reasoning and tool use.

- The team quantized the weights in MoE layers to use 4.25 bits per parameter. Since 90 percent or more of the parameters fall within MoE layers, this step enables gpt-oss-120b to run on a GPU with 80 gigabytes of memory and gpt-oss-20b to run on a GPU with 16 gigabytes of memory.
- They fine-tuned the models to generate a chain of thought via supervised fine-tuning and reinforcement learning, a method similar to that used to fine-tune OpenAI o3  .
- During fine-tuning, they trained the models to support three reasoning levels by inserting into prompts phrases like “Reasoning:low”.
- Similarly, they fine-tuned them to search the web, execute Python code, and use arbitrary tools.
- They also trained the model to refuse requests for hate speech, instructions for committing crimes, recipes for hazardous substances, and the like. In internal tests  designed to measure risky behavior, gpt-oss-120b, after being fine-tuned for biology and cybersecurity, fell short of “high capability” in those areas.

Results: Set to high reasoning effort, the models generally performed midway between o3-mini, o3, and o4-mini in OpenAI’s tests. Unless otherwise noted, OpenAI results come from OpenAI’s reporting  , and DeepSeek R1’s results come from its report on its latest update   of the model.

- Using tools to solve competition math problems in AIME 2024, gpt-oss-120b (96.6 percent accuracy) and gpt-oss-20b (96 percent accuracy) exceeded o3 (95.2 percent), but they fell short of o4-mini (98.7 percent).
- Answering science questions on GPQA Diamond without using tools, gpt-oss-120b (80.1 percent accuracy) outperformed o3-mini (77 percent) but underperformed o3 (83.3 percent) and o4-mini (81.4 percent). The smaller gpt-oss-20b (71.5 percent) came in last among OpenAI models presented. This puts gpt-oss behind Grok 4 (87.7 percent), Gemini 2.5 Pro (84.4 percent), and DeepSeek R1’s latest update (81.3 percent), according to Artificial Analysis.
- On the retail portion of Tau-Bench, a test of agentic tool use, gpt-oss-120b (67.8 percent accuracy) came in above o3 (65.6 percent) and below o4-mini (70.4 percent). These models outperformed DeepSeek R1 (63.9 percent accuracy). In comparison, gpt-oss-20b (54.8 percent accuracy) came in well below.

Behind the news: Founded in 2015 as a nonprofit corporation, OpenAI initially was devoted to open source development on the theory that AI would produce greater benefits and advance more safely if members of the community at large could inspect, use, and improve upon each others’ work. However, in 2019, the high cost of building cutting-edge AI models led the organization to form a for-profit subsidiary, and it stopped releasing large language model weights (although it continued to publish weights for models such as Clip  , which produces similar embeddings for related images and text, and Whisper, a speech-to-text engine).

Why it matters: Businesses, developers, and users have a variety of reasons to choose models with open weights, including lower cost, greater control, and the ability to update as they wish. OpenAI’s turn away from open source cleared the way for other teams to capture the market for open offerings. Now it’s returning to a very different landscape. Meta jumped into the breach with its Llama models, along with Allen Institute for AI, Google, and others. Lately, developers in China such as Alibaba (Qwen3  ), DeepSeek (DeepSeek-R1  ), Moonshot (Kimi K2  ), and Z.ai have taken the lead. For developers, the gpt-oss family offers free access to technology designed by an extraordinary team of innovators. For OpenAI, it’s an opportunity to capture the broad range of developers and users that prefer open models to closed ones.

We’re thinking: A vibrant open source community is vital to AI’s ongoing progress! Every open model holds valuable knowledge and functionality.

Reasoning Boosts Carbon Emissions

In the era of reasoning models, delivering better answers to questions has an environmental cost. A new study quantifies the impact.

What’s new: Researchers estimated  the emissions of carbon dioxide and other heat-trapping gases associated with using 14 open-weights large language models. (The information needed to study closed models is not publicly available.) Reasoning, total tokens generated, and accuracy on question-answering benchmarks were associated with higher greenhouse-gas emissions, according to findings by Maximilian Dauner at Munich Center for Digital Sciences and AI and Gudrun Socher at HM Hochschule München University of Applied Sciences.

How it works: The authors tested models of various sizes, with and without reasoning capabilities, using questions that required short and long answers.

- The authors tested Meta’s non-reasoning models Llama 3.1 (8 billion and 70 billion parameters) and Llama 3.3 (70 billion parameters); Alibaba’s non-reasoning models Qwen and Qwen 2.5 (7 billion and 72 billion parameters); Deep Cogito, which has reasoning and non-reasoning modes (8 billion and 70 billion parameters); and the reasoning model DeepSeek-R1 (7 billion, 8 billion, and 70 billion parameters).
- Each model answered 100 MMLU   questions about five subjects (philosophy, world history, international law, abstract algebra, and mathematics). The questions took two forms: multiple-choice with single-word answers and prompts that elicited open-ended responses. OpenAI’s o4-mini judged the open-ended responses.
- The authors ran the models on an Nvidia A100 GPU with 80 gigabytes of memory and measured  the amount of energy used by the chip. They multiplied the energy consumption in kilowatt-hours by a global average (480 grams of CO₂-equivalent per kilowatt-hour) to determine the resulting emissions.

Results: The authors found a clear trade-off between reasoning (and the higher resulting numbers of tokens generated and output accuracy) and greenhouse-gas emissions.

- The top-performing models achieved around 84 percent to 91 percent accuracy, resulting in around 1,300 grams to 2,000 grams of CO₂-equivalent greenhouse gas emissions per 1,000 questions (500 multiple-choice questions and 500 open-ended questions). By contrast, the smallest model achieved less than 35 percent accuracy and resulted in less than 30 grams of emissions.
- Deep Cogito’s emissions multiplied by 4 to 6 times when reasoning was enabled. For example, the 8 billion-parameter version emitted around 372 grams of emissions with reasoning versus around 56 grams without reasoning.
- Open-ended responses resulted in still greater emissions. Models generated over 3 times more emissions while answering open-ended questions (an average of 345.55 grams) than they did when answering multiple-choice questions (109.52 grams).
- Deep Cogito with 70 billion parameters bucked the trend. With reasoning enabled, it achieved the highest overall accuracy (84.9 percent) while emitting around 34 percent fewer grams than DeepSeek-R1 with 70 billion parameters (78.9 percent accuracy). This result suggests that energy efficiency can vary dramatically among reasoning models.

Yes, but: The authors’ estimates of carbon emissions likely are overestimates. Older GPUs such as the A100 are less energy-efficient than newer ones; and much cloud computing takes place in data centers powered by renewable energy sources that emit less carbon than global average energy consumption. For example, Google  and Amazon  match their electricity consumption with renewable energy, and Meta has powered  its data centers solely by renewable energy since 2020.

Why it matters: The International Energy Agency projects  that AI will consume increasing amounts of energy, and thus produce more greenhouse-gas emissions, as companies focus on training and serving ever larger models. Current AI poses a double-barreled challenge: The more accurate a model’s output, (i) the more emissions it will produce and (ii) the more people will query it. Much of the thinking about how to manage this issue has pointed to leaner parameter counts: Smaller models consume less energy. But the authors’ findings instead point to strategic deployment: The right model for the right task. AI providers can reduce emissions by routing inputs to models that can process them both accurately and efficiently, and by limiting outputs to appropriate lengths. These strategies don’t require building new infrastructure or models.

We’re thinking: We must continue to work toward improving AI’s energy efficiency and reducing its carbon emissions. That said, in many tasks, using AI produces fewer emissions than other approaches, such as using human labor.

Researchers in a data center analyze global data on digital screens, optimizing technological solutions.

Learn More About AI With Data Points!

AI is moving faster than ever. Data Points helps you make sense of it just as fast. Data Points arrives in your inbox twice a week with six brief news stories. This week, we covered Google’s release of AlphaEarth Foundations, a new AI model that builds better maps from satellite data to help track deforestation, urban growth, and more. Subscribe today  !

GLM-4.5, an Open, Agentic Contender

The race is on to develop large language models that can drive agentic interactions. Following the one-two punch of Moonshot’s Kimi K2 and Alibaba’s Qwen3-235B-A22B update, China’s Z.ai aims to one-up the competition.

What’s new: GLM-4.5  is a family of open-weights models trained to excel at tool use and coding. The family includes GLM-4.5 and the smaller GLM-4.5-Air, both of which offer reasoning that can be switched on or off.

- Input/output: Text in (up to 128,000 tokens), text out (up to 96,000 tokens)
- Architecture: Mixture-of-experts (MoE) transformer. GLM-4.5: 355 billion parameters total, 32 billion active at any given time. GLM-4.5-Air: 106 billion parameters total, 12 billion active at any given time.
- Performance: Both models outperform Anthropic Claude 4 Opus, DeepSeek-R1-0528, Google Gemini 2.5 Pro, Grok 4, Kimi K2, and/or OpenAI o3 on at least one reasoning, coding, or agentic benchmark
- Availability: Web interface  (free), API  (GLM-4.5: $0.60/$0.11/$2.20 per million input/cached/output tokens; GLM-4.5-Air: $0.20/$0.03/$1.10), weights available via HuggingFace  and ModelScope  for commercial and noncommercial uses under MIT license
- Features: Function calling, switchable reasoning/non-reasoning
- Undisclosed: Specific training datasets

How it works: GLM-4.5 models include several architectural features that differ from other recent MoE models. Instead of adding more experts or making the experts use more parameters per layer (which would make the models wider), the team increased the number of layers per expert (which makes them deeper). The pretraining/fine-tuning process distilled three models into one.

- The team pre-trained the models on 22 trillion tokens: 15 trillion tokens of text followed by 7 trillion tokens of further text devoted to code and reasoning.
- They fine-tuned three copies of the pretrained GLM-4.5 using supervised fine-tuning and reinforcement learning, producing specialized versions for reasoning, agentic capabilities, and general knowledge. Then they fine-tuned the pretrained model to match the outputs from the specialized versions, producing one model with the capabilities of all three. Finally, they fine-tuned this model via reinforcement learning on further reasoning, agentic, and general data.

Results: The team compared GLM-4.5 and GLM-4.5-Air to top open and closed models across 12 benchmarks that assess reasoning, coding, and tool use.

- In an average of tool-use benchmarks (TAU-Bench, BFCL v3 Full, ad BrowseComp), GLM-4.5 (90.6 percent accuracy) outperformed Claude Sonnet 4 (89.5 percent accuracy), Kimi K2 (86.2 percent accuracy), and Qwen3-Coder (77.1 percent accuracy). On BrowseComp (web browsing with multi-step searches), GLM-4.5 (26.4 percent accuracy) outperformed Claude 4 Opus (18.8 percent accuracy) but trailed o3 (49.7 percent accuracy).
- On MATH 500 (selected competition-level problems),GLM-4.5 (98.2 percent accuracy) equalled Claude 4 Opus. On AIME24 (competition math), GLM-4.5 (91.0 percent accuracy) outperformed Claude Opus 4 (75.7 percent accuracy) but trailed Qwen3-235B-Thinking (94.1 percent accuracy).
- On SWE-bench Verified (software engineering problems), GLM-4.5 (64.2 percent) outperformed Kimi K2 (65.4 percent) but trailed Claude 4 Sonnet (70.4 percent) and Qwen3-Coder (67 percent, tested separately). In Z.ai’s own evaluation across 52 coding tasks, GLM-4.5 achieved an 80.8 percent win rate against Qwen3-Coder and a 53.9 percent win rate against Kimi K2.
- GLM-4.5-Air excelled against likely larger models on multiple benchmarks, For instance, on BFCL v3, GLM-4.5-Air (76.4 percent) outperformed Gemini Pro 2.5 (61.2 percent). On AIME 2024, GLM-4.5-Air (89.4 percent) outperformed Claude 4 Opus (75.7 percent).

Behind the news: A rapid run of releases by teams in China — Kimi K2, Qwen3’s updates, and now GLM-4.5 — has established momentum in open-weights, large language models that are tuned for agentic behavior.

Why it matters: It’s not uncommon to distill larger models into smaller ones, sometimes to shrink  the parameter count, sometimes to improve  an existing small model’s performance. Z.ai’s approach distilled not a larger model but three specialized variations on the base model.

We’re thinking: The “best” open model for agentic applications is shifting weekly, creating both exciting opportunities and daunting challenges for developers.

Robot Surgeon Cuts and Clips

An autonomous robot performed intricate surgical operations without human intervention.

What’s new: Ji Woong (Brian) Kim and colleagues at Johns Hopkins, Stanford, and the surgical technology company Optosurgical developed Hierarchical Surgical Robot Transformer  (SRT-H), a system that performs surgery with only routine help from humans. The system, which uses a two-armed surgical robot that ordinarily is operated by hand, successfully completed the key clipping-and-cutting steps to remove gallbladders.

How it works: SRT-H pairs two transformer models: a high-level planner that decides what step to take next and a low-level action generator that turns the planner’s decision into signals that control an Intuitive Surgical da Vinci   robot. Both models were trained via imitation learning. That is, they learned to map images and text to robot arm motions by copying recorded human demonstrations.

- To build a training dataset, the team recorded around 17 hours of operations in which humans operated the robot, performing 17 steps to remove gallbladders from 34 pig tissues that had been separated from the animals’ bodies. The recordings captured the outputs of a tube-mounted endoscope, two cameras mounted on the robot’s wrists, and the translations, rotations, and gripper openings of each robot arm.
- Annotators labeled each step (such as “grab gallbladder” and “place second clip on left tube”) along with corrective instructions wherever the surgeons revised their actions in progress (for instance, “move right arm to the right”). This process resulted in roughly 16,000 labeled, time-stamped, brief sequences of images with corresponding robotics data and natural-language labels.

- Given the 5 most recent endoscope frames, the high-level transformer learned to predict (i) whether a correction was required (that is, whether the surgeons revised their actions) and, if so, an appropriate natural language instruction for the correction and (ii) an instruction that described the next step in the surgery. A pretrained Swin-T  encoded the images, and the transformer’s decoder learned to output the next step, binary correction flag, and corrective instruction.

- Given the high-level transformer’s correction flag, next-step instruction, and corrective instruction as well as images from the endoscope and wrist cameras, the low-level transformer learned to generate around the next 2 seconds of robot motion. A pretrained EfficientNet-B3   encoded the images, a pretrained DistilBERT  embedded the next-step instruction, FiLM  layers aligned the embedded instruction with relevant image features, aligning the visual representation with the current instruction. The transformer’s decoder learned to generate the next robot action sequence.

- At inference, every 3 seconds, the high-level transformer processed the 5 most recent endoscope frames and issued a correction flag, next-step instruction, and corrective instruction. It used the flag to decide which instruction to pass to the low-level transformer. Then the low-level transformer executed actions in chunks, taking roughly 30 time steps for grabbing and 20 time steps for clipping and cutting. It paused automatically for humans to load new clips or swap between cutter and clip applier tools, a role normally assigned to a surgical nurse.

Results: Tested on 8 pig tissues, SRT-H successfully performed each operation, correcting its own mistakes along the way.

- SRT-H successfully completed all 17 clipping-and-cutting steps on all tissues despite individual variations. When it encountered a problem, it corrected itself and proceeded to complete the operation successfully.
- The high-level transformer correctly predicted next-step instructions with 97 percent accuracy, correction flags with 95 percent accuracy, and corrective instructions (among 18 possible classes of motion) with 70 percent accuracy.
- In a preliminary comparison with an expert surgeon, SRT-H moved the robot less and moved it more smoothly than the surgeon did. However, SRT-H was nearly 41 percent slower. (The authors modified SRT-H’s instruments so they would perform clipping and cutting motions without actually clipping or cutting tissue. This enabled the surgeon to operate on the same tissues as the robot.)

Yes, but: The authors tested SRT-H on tissues that had been removed from an animal’s body. Real-world surgery involves the body as a whole, and surgeons must manage bleeding, tissue motion from respiration, and visual occlusions that might challenge SRT-H.

Behind the news: Prior autonomous surgical systems often rely on custom hardware and setup. For instance, Smart Tissue Autonomous Robot   (STAR), which combines model-based planning with a hand-crafted state machine, uses an enhanced endoscope. The instrument integrates near-infrared fluorescence (NIR) and 3D imaging, so the system can be guided by NIR markers on a patient’s tissue and plan sutures on 3D surfaces. By contrast, SRT-H uses the widely deployed da Vinci robot (over 10,000 units in hospitals globally) and learned from RGB video with annotations in natural language — no NIR markers, 3D scanners, or special fixtures.

Why it matters: SRT-H is a significant step toward surgeries that can be performed safely by an autonomous robot. There’s still a long way to go: The system performed only portions of gallbladder removals, and it did so on tissues that were outside the body. Nonetheless, it did its job nearly flawlessly. Its natural language interface makes its decisions interpretable and enables humans to override or correct the system using verbal commands, important steps toward safe autonomous surgeries. And since SRT-H relies on imitation learning, presumably it could learn to perform other procedures, given appropriate demonstrations.

We’re thinking: In an operating room, the ability to recover from unexpected events trumps perfect execution of predetermined plans. SRT-H’s correction system enables the system to recover from its own mistakes — an important advantage over rigid systems that may work well in the lab but struggle under real-world conditions.

Work With Andrew Ng

Join the teams that are bringing AI to the world! Check out job openings at DeepLearning.AI  , AI Fund  , and Landing AI  .

Subscribe and view previous issues here  .

Thoughts, suggestions, feedback? Please send to thebatch@deeplearning.ai (mailto:thebatch@deeplearning.ai?subject=RE:%20Thoughts,%20Suggestions,%20feedback) . Avoid our newsletter ending up in your spam folder by adding our email address to your contacts list.

DeepLearning.AI, 195 Page Mill Road, Suite 115, Palo Alto, CA 94306, United States

Unsubscribe
Manage preferences
