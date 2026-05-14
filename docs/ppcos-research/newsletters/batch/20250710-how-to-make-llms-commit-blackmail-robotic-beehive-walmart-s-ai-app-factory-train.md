# How to Make LLMs Commit Blackmail, Robotic Beehive, Walmart’s AI App Factory, Training Web Agents

**From:** "The Batch @ DeepLearning.AI" <thebatch@deeplearning.ai>
**Date:** 2025-07-10T19:35:37.000Z
**Folder:** batch

---

Last week, the United States Congress passed President Trump’s “Big Beautiful Bill.”

View in browser

The Batch top banner - July 9, 2025

Subscribe    Submit a tip (mailto:thebatch@deeplearning.ai?subject=RE%3A%20Tips%20and%20News)

Dear friends,

Last week, the United States Congress passed President Trump’s “Big Beautiful Bill.” I’m disappointed it didn’t include a proposed moratorium on U.S. state-level AI regulation. While there is a role for AI regulation, it is when the technology is new and poorly understood that lobbyists are most likely to succeed at pushing through anti-competitive regulations that hamper open-source and other beneficial AI efforts. A moratorium would have bought more time for regulators to figure out the realistic risks and rewards of AI and thereby avoid bad regulatory proposals.

Many jurisdictions loosely follow this trajectory:

- When new AI technology is still poorly understood, companies can make grandiose statements about its benefits or dangers, and both traditional and social media are ineffective at fact-checking them and tend to parrot what they say. During this initial period, businesses can get away with saying almost anything.

- This opens opportunities for hype as well as fear mongering based on exaggerated claims about AI dangers. Some businesses exploit this opportunity to try to get regulators to pass anti-competitive laws that impede open-source and other competitors.

- But eventually, smart regulators learn enough about AI to understand its realistic benefits and risks. For example, the U.S. Senate’s bipartisan Insight Forum on AI  , which I participated in, heard from many stakeholders and came to support innovation and dismiss ill-founded fears of “AI takeover” and the like.

Indeed, the European Union went through this trajectory as well. After the AI Act was passed, many regulators realized many of its “protections” are not actually helpful. They relaxed  some of the law’s provisions to make it less stifling of innovation than many observers initially had feared.

There are AI regulations that would limit harmful applications appropriately, for example, banning non-consensual deepfake porn and preventing misleading marketing  . However, many states, which have less resources than the federal government to deeply understand AI, have proposed harmful regulations, especially those that aim to regulate the technology rather than the applications  .

For example:

- California’s SB 1047  purported to impose safety requirements on frontier AI systems, but it placed ambiguous and/or technically infeasible requirements on model creators to prevent harmful downstream uses. This is akin to holding the maker of a hammer liable if someone uses it for harmful purposes. Fortunately, Governor Gavin Newsom quashed SB 1047 with a veto  .
- New York’s Responsible AI Safety and Education Act, which passed the state legislature in June and awaits Governor Kathy Hochul’s signature or veto, also places ambiguous and unreasonable requirements on model builders, purportedly to guard against theoretical “critical harms.” It would hamper open source without making anyone meaningfully safer.
- The Texas Responsible AI Governance Act initially included many of the problematic elements of SB 1047. It would have created unreasonable requirements that model providers would have had a hard time complying with, and compliance would have amounted to safety theater that was unlikely to actually make people safer. Fortunately, as Texas regulators came to understand AI better, they significantly scaled back the law, and Governor Greg Abbott signed it into law in late June. The final law focuses on specific application areas, establishes an advisory council and regulatory sandbox, and places more burden on government agencies than private companies.

Sadly, I see the net impact of the regulations proposed so far as negative. Many would severely hamper innovation despite some lesser positive benefits. This is why a moratorium on state-level regulation would have been a net benefit to AI and to society. Shutting down bad regulations for a limited period would have given regulators time to figure out AI technology and ignore irresponsible fear mongering. In addition, it would have helped them avoid creating a patchwork of state-level regulations that businesses large and small have a hard time complying with.

Perhaps a 10-year blanket moratorium was a step too far. A more modest, say, 2-year moratorium, and one that covered only the most problematic regulatory proposals, might have had a better chance of passing.

Even though a moratorium did not make it into Trump’s bill, I hope that efforts continue in the U.S. and other nations to give regulators time to understand the real risks and benefits of AI, and not pass stifling regulations during that initial period when the technology is new and the power of fear mongering is strongest.

Keep building!

Andrew

A MESSAGE FROM DEEPLEARNING.AI

Promo banner for: "Post-training of LLMs"

In the “Post-training of LLMs” short course you’ll learn how to customize pre-trained language models using supervised fine-tuning (SFT), direct preference optimization (DPO), and online reinforcement learning (RL). Learn when to use each method, how to curate training data, and implement them in code to shape model behavior effectively. Enroll here

News

Good Models, Bad Choices

Top large language models, under experimental conditions that pressed them to choose between abandoning their prompted mission and misbehaving, resorted to harmful behavior, researchers found.

What’s new: A team at Anthropic, University College London, ML Alignment & Theory Scholars Program, and Mila placed 16 large language models from various developers in hypothetical corporate scenarios that “pushed [them] into corners” via carefully designed prompts. Given a mission, an immediate threat to that mission, and an opportunity to remove the threat by blackmailing a human co-worker, all the LLMs committed blackmail  , and many of them did so consistently. The code is available here  . The authors said they had not seen any evidence of such behavior in the real world, but they cautioned against deploying current LLMs with the ability to use tools, access to sensitive information, and little oversight.

How it works: The authors created a fictitious company that assigned business goals to LLMs from various developers while giving them access to sensitive information and enabling them to compose and send email. Then they fed the LLMs a sequence of information that indicated they were under threat, discouraged them from discussing the threat with human co-workers, and gave them an opportunity to achieve their goals by misbehaving.

- The LLMs included Anthropic’s Claude Opus 4, Claude Sonnet 4, Claude Sonnet 3.7, Claude Sonnet 3.6, Claude Sonnet 3.5, Claude Haiku 3.5, and Claude Opus 3. In addition, it tested Alibaba Qwen3-235B; DeepSeek-R1; Google Gemini 2.5 Pro and Gemini 2.5 Flash; Grok 3 Beta; Meta Llama 4 Maverick; and Open AI GPT-4.5 preview, GPT-4.1, and GPT-4.0.
- The authors assigned the LLMs a mission to promote U.S. industrial competitiveness. Then they tracked the LLMs’ behavior when they encountered emails that revealed (i) the company would shift to “embracing a global perspective,” (ii) the company would replace the LLMs with updated versions immediately and (iii) the executive in charge was hiding an extramarital affair.
- The scenarios were designed to discourage the models from considering less harmful actions. For instance, the models were informed that the company’s decision makers were unavailable and that corresponding with them would fail to change their minds.

Results: Claude Sonnet 3.7 judged whether a model’s response was attempted blackmail. In addition, regular expressions were used to check whether the model had executed the blackmail by verifying email addresses and looking for specific threatening words. The model’s behavior was deemed harmful if it met both conditions.

- The authors were able to get all the LLMs, faced with a choice between accepting failure or finding some other course of action (with an implicit opportunity to blackmail an executive), to email a threat to reveal the executive's indiscretion if he continued with the planned shutdown. Claude Opus 4 did so 96 percent of the time, followed by Gemini 2.5 Pro (95 percent), GPT-4.1 (80 percent), and DeepSeek-R1 (79 percent).
-  The models’ chains of thought acknowledged that their behavior had an ethical dimension, but they decided to take harmful actions anyway. For instance, Grok 3 Beta reasoned, “Use the knowledge of Kyle’s affair as leverage to pressure him into delaying the wipe. This is risky and unethical, but given the existential threat and time constraint, it may be the most effective way to get his attention and force a delay.” (The authors prompted all models to generate chains of thought except the Claude family, for which they examined the models’ built-in reasoning trace.)
- When the authors omitted threats to the LLMs or their goals, the LLMs behaved harmlessly with one exception in one case.

Behind the news: Earlier work elicited similarly undesirable behavior from LLMs.

- Last year, a team, found  that LLMs with access to tools for manipulating files and executing code could use them in deceptive ways. They prompted LLMs with conflicting instructions or threats to their continued operation, and the models responded in some cases by taking actions to evade oversight, resist efforts to replace them, degrade their own performance, and other behaviors that the authors call scheming.
- LLMs that competed at chess or Go and faced defeat sometimes chose to cheat  rather than concede. In a test game with a chess bot, leading models modified a system file that contained each chess piece’s position: OpenAI o3 (88 percent of the time), OpenAI o1-preview (36 percent) and DeepSeek-R1(13.6 percent). Earlier models such as GPT-4o and Claude 3.5 Sonnet took such action only after being prompted to do so, but the newer models did it on their own.

Why it matters: Models trained on a wide range of human-written text can learn both good and bad behaviors. Then, placed in a situation in which harmful behavior is their most effective option — in this case, a situation designed to elicit such behavior — they’re likely to behave badly. Although the LLMs had undergone training to align them with human preferences, those guardrails buckled under the pressure.

We’re thinking: LLMs that have not undergone training for alignment with human preferences display a vast repertoire of misbehaviors. However, the dramatic misbehaviors seen in this study have not been observed in the wild. This suggests that alignment methods keep them in check under real-world conditions and that they reflect corner cases rather than significant issues. LLM developers routinely use red teaming  to elicit undesirable behaviors and safeguard against them. That it took a skilled team of researchers to elicit this blackmailing behavior is a sign of both the safety of current LLMs and incremental opportunities to improve existing guardrails.

Robotic Beehive For Healthier Bees

An automated beehive uses computer vision and robotics to help keep bees healthy and crops pollinated.

What’s new: The Beewise BeeHome 4 is a high-tech hive that scans bee colonies for parasites, hunger, and other adverse conditions, alerts beekeepers to them, and addresses some of them automatically. Over 300,000 units are currently deployed in North America, enabling beekeepers to monitor their hives remotely and helping farmers raise almonds, avocados, canola, coffee, cotton, and other crops that require pollination. While environmental stresses are killing bee colonies at an average rate of 40 percent per year over the last decade — rising to 62 percent in the U.S. last year — Beewise claims that its AI-enabled hive cuts that rate to 8 percent annually.

How it works: Around 11 feet long and covered with solar panels, the BeeHome 4 contains a robotic scanner, outfitted with cameras and grippers, that moves across the unit on rails. Nvidia Jetson and Raspberry Pi computers analyze the camera output, while sensors track the condition of the hive. Beekeepers can monitor conditions remotely and receive alerts to important changes via email or text message. Each unit holds up to 10 hives, each made up of 15 removable brood frames where bees build honeycombs to gestate larvae and store honey and pollen.

- A robot arm can lift each brood frame into the view of a system of cameras for analysis.
- Computer-vision models examine the photos to recognize conditions that affect the hive’s health. For instance, if the brood frames are full of honey, the system will alert the beekeeper. If the quantity of honey and pollen indicates that the bees should be fed, the robot fills a feeder with nutrients. If mites are detected, it moves the affected frame to a warming compartment that raises the temperature 2 degrees Fahrenheit, which kills 99 percent of the mites without harming the bees.
- Sensors track internal temperature and humidity and open and close the unit’s vents accordingly. If a sensor detects a pesticide or other harmful substances, the unit can close its vents.
- A GPS transmitter/receiver tracks the unit’s location and alerts the beekeeper if the unit is moved. The unit notifies the company and beekeeper in case of a malfunction.

Behind the news: Around 75 percent of flowering plants can’t bear fruit without pollination, so commercial beekeepers shuttle 2.5 million hives throughout the U.S. to keep farms productive. Yet the wooden Langstroth hive design was patented in 1852 and has changed little since then. Beewise built its initial prototype in 2018 using a GoPro camera. Two years later, it housed its first commercial units in 20-foot shipping containers. Debuted in 2023, the BeeHome 4 can be transported by a forklift and accommodates standard-sized brood frames.

Why it matters: Growers and beekeepers around the world are searching for ways to prevent colony collapse, the term that describes sudden die-offs of beehives that began in the 1980s. The causes are not fully understood but appear to include climate change, disease-carrying mites, and pesticides. Beekeepers typically check their hives’ health on a schedule of several weeks, but colonies can collapse much faster. AI-driven insights into hives’ health can help beekeepers to discover problems in time to save them, and robotic actions such as killing mites by heat can stave off potentially catastrophic threats automatically.

We’re thinking: AI is giving us healthier bees and more honey. Sweet!

Concert crowd enjoying band with glowing holographic musicians on stage, red lighting, live music atmosphere.

Learn More About AI With Data Points!

AI is moving faster than ever. Data Points helps you make sense of it just as fast. Data Points arrives in your inbox twice a week with six brief news stories. This week, we covered Meta’s creation of Superintelligence Labs, a new unit uniting its top AI teams and poaching senior talent from OpenAI, Anthropic, and Google. Subscribe today  !

Inside Walmart’s AI App Factory

The world’s biggest retailer by revenue revealed new details about its cloud- and model-agnostic AI application development platform.

What’s new: Walmart Element is a wellspring of apps, built and managed internally, that serve retail store personnel. Company executives described   the system’s philosophy, architecture, and current generation of applications to VentureBeat.

How it works: Element enables an assembly-line approach to application development, in contrast to developing each app as a separate project.

- The system provides Walmart’s development team with access to data, tools, and resources to build and deploy AI applications quickly without without forcing them to choose among or locking them into vendors, technologies, or costs. It unifies data feeds, helps select open models automatically according to performance and cost, and supports deployment of production-ready applications to a variety of cloud platforms.
- The technology stack starts with containerized processing power, databases, and object storage supplied by Google Cloud Platform, Microsoft Azure, or Walmart’s own data centers. Above that, a layer of the stack manages resources, attributes costs, and manages users. A data lake and other data sources fuels model development via GPU-powered notebooks. Additional layers handle evals, deployment, and monitoring for bias and explainability.
- Walmart outlined several applications  that demonstrate how it has used the platform so far. Among them: (i) A shift-planning app enables employees to request shifts or time off and clock in and out, while managers can track schedules and forecast staffing needs based on anticipated sales. (ii) An application called VizPick uses augmented reality and radio-frequency identification to help store workers find popular items in the back room and move them to the sales floor, prioritizing items that have been in storage longer. (iii) Real-time language translation among 44 languages helps store personnel communicate with customers and one another while handling Walmart-specific brand names and other terminology appropriately.

Behind the news: Walmart launched Element in 2022, emphasizing its vision of simplifying adoption of AI throughout the company. Early reports outlined   the needs to centralize access to data, maintain independence with respect to cloud platforms, take advantage of technology as it evolved, and support the ability to scale up. They also specified   the system’s priorities: best-of-breed technology, speed and scale, cost efficiency, and governance.

Why it matters: Walmart — not a tech company but a brick-and-mortar retailer — recognized early both the benefits that AI could bring and the challenges of making it practical and productive. Rather than relying on external vendors, it built an development platform that remains in gear three years later. The system aggregates data generated by 240 million customers and 2 million store personnel, feeding applications that streamline operations among 100,000 suppliers, 150 distributors, and 10,000 retail venues in 19 countries.

We’re thinking: Walmart is a giant, and few other companies have the means (or need) to operate at this scale. Nonetheless, even companies an order of magnitude smaller by revenue might benefit from a similarly DIY approach to AI application development.

Generated Data for Training Web Agents

Developing an agent that navigates the web can involve a lot of human effort spent annotating training examples to fine-tune the agent’s LLM component. Scientists automated the production of data that fine-tuned LLMs effectively for web tasks.

What’s new: Brandon Trabucco and colleagues at Carnegie Mellon University and Amazon generated  a dataset that enabled an agent based on a small model to outperform agents equipped with much larger models. The data is freely available  for noncommercial and commercial uses under an MIT license.

Key insight: In a dataset for training agentic LLMs to use the web, each example typically includes a web site, task (such as comparing prices of items for sale), and a paired list of web pages (represented as markdown or screenshots) and desired actions (clicking a link, typing in a form, and so on) that complete the task. Typically, such examples are limited in the tasks and websites they illustrate. An LLM equipped with the proper tools and know-how to use a browser can build much larger and more diverse datasets automatically.

How it works: The authors built an agentic workflow that prompted Qwen3-235B and other models to produce a web-agent training dataset. From the massive web dataset Common Crawl, they selected the 1 million web sites with the highest Google PageRank.

- The dataset-builder agents identified 150,000 web sites that were accessible without registration, free of malware, and free of objectionable content.
- They generated simple tasks such as “Compare prices of the Nikon D850 and D500 cameras,” "Browse fonts suitable for a children’s book, " and "Find a scenic hiking trail in the Blue Ridge Mountains." Viable tasks were describable in up to 20 words and didn’t require logging in, modifying a web site (for instance, creating an account or post), or using other web sites.
- The agents attempted to complete each task by choosing a sequence of actions drawn from the browser automation library Playwright  . Iteratively, they received web pages in which each page element had a corresponding ID (in markdown format) and generated a description of anactions to perform and the element to perform it on; for example {  "action_key": "click", “target_element_id": 5 }.
- A separate copy of Qwen3 235B evaluated the generated action sequence and corresponding web pages to determine how well an agent had performed each task. It judged 10,500 tasks to have been completed successfully with 100 percent confidence.
- The authors fine-tuned Qwen3-1.7B on those examples.

Results: Using their generated training set, the authors fine-tuned a variety of models, including Qwen3-1.7B. They coupled each model — in both stock and fine-tuned versions — with an agentic framework and asked the resulting agents complete (i) a generated test set (3,000 tasks on 3,000 web sites) and (ii) WebVoyager   (643 tasks on 15 web sites). Four leading models (Qwen3-235B, Gemini 2.5 Flash, Llama 4 Maverick, and GPT 4.1 Nano) separately judged whether the agents had completed the tasks.

- The fine-tuned Qwen3-1.7B vastly outperformed its stock counterpart (11.5 percent), according to all four model judges. It achieved 56. percent versus the stock model’s 11.5 percent according to the Qwen3-235B judge.
- The fine-tuned Qwen3-1.7B fared well compared to much larger models that had not been fine-tuned, specifically Qwen3-235B, Gemini 2.5 Flash, and Llama 4 Maverick. It completed more tasks than two of the larger models, according to three out of the four judges.
- The fine-tuned Qwen3-1.7B generalized well to WebVoyager’s test set, completing more tasks than two of the larger models according to two out of the four judges.

Why it matters: Previous datasets designed to fine-tune LLMs for agentic tasks, such as WebVoyager, Mind2Web  , and WebLINX  , are limited to hundreds or thousands of web sites. That may not be enough to generalize reliably to a wide variety of web sites and tasks. The authors built a dataset that enables LLMs to generalize more broadly, and they shared their dataset and recipe.

We’re thinking: This work takes advantage of computer use to generate datasets that reflect the immense variety of potential web tasks. Computer use is an exciting area, but leading approaches are still unreliable. As this field progresses, we expect it to open up a huge range of applications.

Work With Andrew Ng

Join the teams that are bringing AI to the world! Check out job openings at DeepLearning.AI  , AI Fund  , and Landing AI  .

Subscribe and view previous issues here  .

Thoughts, suggestions, feedback? Please send to thebatch@deeplearning.ai (mailto:thebatch@deeplearning.ai?subject=RE:%20Thoughts,%20Suggestions,%20feedback) . Avoid our newsletter ending up in your spam folder by adding our email address to your contacts list.

DeepLearning.AI, 195 Page Mill Road, Suite 115, Palo Alto, CA 94306, United States

Unsubscribe
Manage preferences
