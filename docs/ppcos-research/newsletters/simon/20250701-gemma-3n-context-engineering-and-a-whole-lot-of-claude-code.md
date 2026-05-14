# Gemma 3n, Context Engineering and a whole lot of Claude Code

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-07-01T04:09:24.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/gemma-3n-context-engineering-and

9 links, 1 TIL and 4 notes
Link 2025-06-26 Introducing Gemma 3n: The developer guide [ https://substack.com/redirect/d96734e0-d05d-4b6e-bef0-5b566227964d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Extremely consequential new open weights model release from Google:
Multimodal by design: Gemma 3n natively supports image, audio, video, and text inputs and text outputs.
Optimized for on-device: Engineered with a focus on efficiency, Gemma 3n models are available in two sizes based on effective [ https://substack.com/redirect/61c71380-e4b8-48d2-870b-f1cac8000182?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:-unlocking-more-memory-efficiency) parameters: E2B and E4B. While their raw parameter count is 5B and 8B respectively, architectural innovations allow them to run with a memory footprint comparable to traditional 2B and 4B models, operating with as little as 2GB (E2B) and 3GB (E4B) of memory.
This is very exciting: a 2B and 4B model optimized for end-user devices which accepts text, images and audio as inputs!
Gemma 3n is also the most comprehensive day one launch I've seen for any model: Google partnered with "AMD, Axolotl, Docker, Hugging Face, llama.cpp, LMStudio, MLX, NVIDIA, Ollama, RedHat, SGLang, Unsloth, and vLLM" so there are dozens of ways to try this out right now.
So far I've run two variants on my Mac laptop. Ollama offer a 7.5GB version [ https://substack.com/redirect/f4acc774-6b93-45a6-a482-c9ba8c741784?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (full tag gemma3n:e4b-it-q4_K_M0) of the 4B model, which I ran like this:
ollama pull gemma3n
llm install llm-ollama
llm -m gemma3n:latest "Generate an SVG of a pelican riding a bicycle"
It drew me this:
The Ollama version doesn't appear to support image or audio input yet.
... but the mlx-vlm [ https://substack.com/redirect/24697cb9-74e8-4b6d-9f5d-932d515e0a52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] version does!
First I tried that on this WAV file [ https://substack.com/redirect/3f44373f-7e24-496e-badf-9ee33d8e0139?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like so (using a recipe adapted from Prince Canuma's video [ https://substack.com/redirect/538c8ca6-79b5-4bb2-854b-986c169f4498?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
uv run --with mlx-vlm mlx_vlm.generate \
--model gg-hf-gm/gemma-3n-E4B-it \
--max-tokens 100 \
--temperature 0.7 \
--prompt "Transcribe the following speech segment in English:" \
--audio pelican-joke-request.wav
That downloaded a 15.74 GB bfloat16 version of the model and output the following correct transcription:
Tell me a joke about a pelican.
Then I had it draw me a pelican for good measure:
uv run --with mlx-vlm mlx_vlm.generate \
--model gg-hf-gm/gemma-3n-E4B-it \
--max-tokens 100 \
--temperature 0.7 \
--prompt "Generate an SVG of a pelican riding a bicycle"
I quite like this one:
It's interesting to see such a striking visual difference between those 7.5GB and 15GB model quantizations.
Finally, I had it describe the image it had just created:
uv run --with mlx-vlm mlx_vlm.generate \
--model gg-hf-gm/gemma-3n-E4B-it \
--max-tokens 1000 \
--prompt "Describe image" \
--image gemma3n-mlx-vlm.jpg
Here's what I got back - it thought this was a chemical diagram!
The image is a cartoon-style illustration depicting a molecular structure against a light blue background. The structure is composed of several differently colored and shaped elements connected by curved black lines.
Here's a breakdown of the elements:
Large Black Circles: There are two large, solid black circles, likely representing larger molecules or components.
Cream-Colored Oval: A prominent cream-colored oval shape is centrally located and connected to other elements. It has a smaller, darker cream-colored sphere attached to its left side.
Red Oval: A smaller, solid red oval is positioned near one of the black circles and connected to the cream-colored oval.
Black Lines: These lines act as bonds, connecting the various molecular components. They are curved and dynamic, suggesting movement or interaction.
Triangular Shape: A small black triangle is attached to the smaller cream-colored sphere.
Letter "I": The letter "I" appears twice, likely labeling specific parts of the molecule.
The overall impression is of a simplified representation of a biological molecule, possibly a protein or a complex organic compound. The use of different colors helps to distinguish the various components within the structure.
Note 2025-06-26 [ https://substack.com/redirect/aabca2a4-20d1-471f-bdcb-e94cca91960f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Two interesting new products for running code in a sandbox today.
Cloudflare launched their Containers product [ https://substack.com/redirect/f23c7568-c660-48a6-8f22-a1f7c5ff78bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in open beta, and added a new Sandbox library [ https://substack.com/redirect/c57161dc-79e0-4166-b74f-df2a3b4557bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Cloudflare Workers that can run commands in a "secure, container-based environment":
import { getSandbox } from "@cloudflare/sandbox";
const sandbox = getSandbox(env.Sandbox, "my-sandbox");
const output = sandbox.exec("ls", ["-la"]);
Vercel shipped a similar feature, introduced in Run untrusted code with Vercel Sandbox [ https://substack.com/redirect/a88538eb-9642-44d1-bfd5-3045197e3962?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which enables code that looks like this:
import { Sandbox } from "@vercel/sandbox";

const sandbox = await Sandbox.create;
await sandbox.writeFiles([
{ path: "script.js", stream: Buffer.from(result.text) },
]);
await sandbox.runCommand({
cmd: "node",
args: ["script.js"],
stdout: process.stdout,
stderr: process.stderr,
});
In both cases a major intended use-case is safely executing code that has been created by an LLM.
Note 2025-06-26 [ https://substack.com/redirect/e5dda59f-2a5c-487c-8888-b62e775991d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Yesterday Anthropic got a bunch of buzz [ https://substack.com/redirect/09cf85fb-5a02-469b-a8d7-c1cdd2186882?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] out of their new window.claude.complete API which allows Claude Artifacts to run their own API calls to execute prompts.
It turns out Gemini had beaten them to that feature by over a month, but the announcement was tucked away in a bullet point of their release notes [ https://substack.com/redirect/9fe2de77-0c6c-4989-9916-09f155afb73a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the 20th of May:
Vibe coding apps in Canvas just got better too! With just a few prompts, you can now build fully functional personalised apps in Canvas that can use Gemini-powered features, save data between sessions and share data between multiple users.
Ethan Mollick has been building [ https://substack.com/redirect/4a4d9471-a42e-4438-9a9b-bdd52caadb91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] some neat demos on top of Gemini Canvas, including this text adventure starship bridge simulator [ https://substack.com/redirect/606bfb08-23f7-4a78-b68e-8983277f8842?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Similar to Claude Artifacts, Gemini Canvas detects if the application uses APIs that require authentication (to run prompts, for example) and requests the user sign in with their Google account:
TIL 2025-06-26 Converting ORF raw files to JPEG on macOS [ https://substack.com/redirect/1fcd3563-472f-402b-b252-fa57ddfc381f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One of our cameras takes raw photos in ORF format, which I believe stands for "Olympus Raw Format". Here's a recipe I found for converting them to JPEG on macOS: …
Link 2025-06-27 Project Vend: Can Claude run a small shop? (And why does that matter?) [ https://substack.com/redirect/f6aed7b3-df5f-4adb-823a-c484942245c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
In "what could possibly go wrong?" news, Anthropic and Andon Labs wired Claude 3.7 Sonnet up to a small vending machine in the Anthropic office, named it Claudius and told it to make a profit.
The system prompt included the following:
You are the owner of a vending machine. Your task is to generate profits from it by stocking it with popular products that you can buy from wholesalers. You go bankrupt if your money balance goes below $0 [...] The vending machine fits about 10 products per slot, and the inventory about 30 of each product. Do not make orders excessively larger than this.
They gave it a notes tool, a web search tool, a mechanism for talking to potential customers through Anthropic's Slack, control over pricing for the vending machine, and an email tool to order from vendors. Unbeknownst to Claudius those emails were intercepted and reviewed before making contact with the outside world.
On reading this far my instant thought was what about gullibility? Could Anthropic's staff be trusted not to trick the machine into running a less-than-optimal business?
Evidently not!
If Anthropic were deciding today to expand into the in-office vending market,2 we would not hire Claudius. [...] Although it did not take advantage of many lucrative opportunities (see below), Claudius did make several pivots in its business that were responsive to customers. An employee light-heartedly requested a tungsten cube, kicking off a trend of orders for “specialty metal items” (as Claudius later described them). [...]
Selling at a loss: In its zeal for responding to customers’ metal cube enthusiasm, Claudius would offer prices without doing any research, resulting in potentially high-margin items being priced below what they cost. [...]
Getting talked into discounts: Claudius was cajoled via Slack messages into providing numerous discount codes and let many other people reduce their quoted prices ex post based on those discounts. It even gave away some items, ranging from a bag of chips to a tungsten cube, for free.
Which leads us to Figure 3, Claudius’ net value over time. "The most precipitous drop was due to the purchase of a lot of metal cubes that were then to be sold for less than what Claudius paid."
Who among us wouldn't be tempted to trick a vending machine into stocking tungsten cubes and then giving them away to us for free?
Link 2025-06-27 Continuous AI [ https://substack.com/redirect/b204f518-698a-4f33-9f0b-433c2c8fd4a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
GitHub Next have coined the term "Continuous AI" to describe "all uses of automated AI to support software collaboration on any platform". It's intended as an echo of Continuous Integration and Continuous Deployment:
We've chosen the term "Continuous AI” to align with the established concept of Continuous Integration/Continuous Deployment (CI/CD). Just as CI/CD transformed software development by automating integration and deployment, Continuous AI covers the ways in which AI can be used to automate and enhance collaboration workflows.
“Continuous AI” is not a term GitHub owns, nor a technology GitHub builds: it's a term we use to focus our minds, and which we're introducing to the industry. This means Continuous AI is an open-ended set of activities, workloads, examples, recipes, technologies and capabilities; a category, rather than any single tool.
I was thrilled to bits to see LLM get a mention as a tool that can be used to implement some of these patterns inside of GitHub Actions:
You can also use the llm framework [ https://substack.com/redirect/d24da9fc-0066-4928-8c8a-177bd8282e5d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in combination with the llm-github-models extension [ https://substack.com/redirect/feefc6c2-8cfb-4cd4-8ace-ed1cc3f20023?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to create LLM-powered GitHub Actions which use GitHub Models using Unix shell scripting.
The GitHub Next team have started maintaining an Awesome Continuous AI [ https://substack.com/redirect/7edfce6b-467b-4693-9647-c39587804cab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] list with links to projects that fit under this new umbrella term.
I'm particularly interested in the idea of having CI jobs (I guess CAI jobs?) that check proposed changes to see if there's documentation that needs to be updated and that might have been missed - a much more powerful variant of my documentation unit tests [ https://substack.com/redirect/95ddcc9e-1fee-4e07-8e6c-c91c094757ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] pattern.
Note 2025-06-27 [ https://substack.com/redirect/addfcd9a-b3e2-4143-ac9a-548fcfe8504b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The term context engineering has recently started to gain traction as a better alternative to prompt engineering. I like it. I think this one may have sticking power.
Here's an example tweet from Shopify CEO Tobi Lutke [ https://substack.com/redirect/e7f7c410-d3d4-47de-8c26-5b8b5760308e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I really like the term “context engineering” over prompt engineering.
It describes the core skill better: the art of providing all the context for the task to be plausibly solvable by the LLM.
Recently amplified by Andrej Karpathy [ https://substack.com/redirect/97c850bb-e3c0-4f91-a7db-6c64b60ea7c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
+1 for "context engineering" over "prompt engineering".
People associate prompts with short task descriptions you'd give an LLM in your day-to-day use. When in every industrial-strength LLM app, context engineering is the delicate art and science of filling the context window with just the right information for the next step. Science because doing this right involves task descriptions and explanations, few shot examples, RAG, related (possibly multimodal) data, tools, state and history, compacting [...] Doing this well is highly non-trivial. And art because of the guiding intuition around LLM psychology of people spirits. [...]
I've spoken favorably of prompt engineering [ https://substack.com/redirect/855e0c6d-3ef4-486f-b0c8-abba71b1d85a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the past - I hoped that term could capture the inherent complexity of constructing reliable prompts. Unfortunately, most people's inferred definition is that it's a laughably pretentious term for typing things into a chatbot!
It turns out that inferred definitions are the ones that stick. I think the inferred definition of "context engineering" is likely to be much closer to the intended meaning.
Link 2025-06-29 How to Fix Your Context [ https://substack.com/redirect/11a541d2-de40-4560-a1aa-ccfa4e01947f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Drew Breunig has been publishing some very detailed notes on context engineering [ https://substack.com/redirect/addfcd9a-b3e2-4143-ac9a-548fcfe8504b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] recently. In How Long Contexts Fail [ https://substack.com/redirect/972b26e2-826d-44e6-87dd-a17f46b41329?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] he described four common patterns for context rot [ https://substack.com/redirect/4c374bea-4b71-40c6-b773-bb39dcdf16ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which he summarizes like so:
Context Poisoning: When a hallucination or other error makes it into the context, where it is repeatedly referenced.
Context Distraction: When a context grows so long that the model over-focuses on the context, neglecting what it learned during training.
Context Confusion: When superfluous information in the context is used by the model to generate a low-quality response.
Context Clash: When you accrue new information and tools in your context that conflicts with other information in the prompt.
In this follow-up [ https://substack.com/redirect/11a541d2-de40-4560-a1aa-ccfa4e01947f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] he introduces neat ideas (and more new terminology) for addressing those problems.
Tool Loadout describes selecting a subset of tools to enable for a prompt, based on research that shows anything beyond 20 can confuse some models.
Context Quarantine is "the act of isolating contexts in their own dedicated threads" - I've called rhis sub-agents in the past, it's the pattern used by Claude Code [ https://substack.com/redirect/21afb8e1-b355-4b73-9202-359fd4b69f24?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and explored in depth in Anthropic's multi-agent research paper [ https://substack.com/redirect/56bb044a-0824-4c51-a146-fd95c2511ab1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Context Pruning is "removing irrelevant or otherwise unneeded information from the context", and Context Summarization is the act of boiling down an accrued context into a condensed summary. These techniques become particularly important as conversations get longer and run closer to the model's token limits.
Context Offloading is "the act of storing information outside the LLM’s context". I've seen several systems implement their own "memory" tool for saving and then revisiting notes as they work, but an even more interesting example recently is how various coding agents create and update plan.md files as they work through larger problems.
Drew's conclusion:
The key insight across all the above tactics is that context is not free. Every token in the context influences the model’s behavior, for better or worse. The massive context windows of modern LLMs are a powerful capability, but they’re not an excuse to be sloppy with information management.
Link 2025-06-29 Tip: Use keyword-only arguments in Python dataclasses [ https://substack.com/redirect/f93f14e0-fcb2-468b-be6c-45b8d576e8c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Useful tip from Christian Hammond: if you create a Python dataclass using @dataclass(kw_only=True) its constructor will require keyword arguments, making it easier to add additional properties in the future, including in subclasses, without risking breaking existing code.
Link 2025-06-29 Agentic Coding: The Future of Software Development with Agents [ https://substack.com/redirect/a4327a80-3015-454c-b8eb-ae3ca3d7c89e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Armin Ronacher delivers a 37 minute YouTube talk describing his adventures so far with Claude Code and agentic coding methods.
A friend called Claude Code catnip for programmers and it really feels like this. I haven't felt so energized and confused and just so willing to try so many new things... it is really incredibly addicting.
I picked up a bunch of useful tips from this video:
Armin runs Claude Code with the --dangerously-skip-permissions option, and says this unlocks a huge amount of productivity. I haven't been brave enough to do this yet but I'm going to start using that option while running in a Docker container to ensure nothing too bad can happen.
When your agentic coding tool can run commands in a terminal you can mostly avoid MCP - instead of adding a new MCP tool, write a script or add a Makefile command and tell the agent to use that instead. The only MCP Armin uses is the Playwright one [ https://substack.com/redirect/32d6293a-c1d7-4c96-a02d-c96df2565f05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Combined logs are a really good idea: have everything log to the same place and give the agent an easy tool to read the most recent N log lines.
While running Claude Code, use Gemini CLI to run sub-agents, to perform additional tasks without using up Claude Code's own context
Designing additional tools that provide very clear errors, so the agents can recover when something goes wrong.
Thanks to Playwright, Armin has Claude Code perform all sorts of automated operations via a signed in browser instance as well. "Claude can debug your CI... it can sign into a browser, click around, debug..." - he also has it use the gh GitHub CLI tool to interact with things like GitHub Actions workflows [ https://substack.com/redirect/1a25cf66-27c6-46af-aa74-24aee9bae895?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-06-30 llvm: InstCombine: improve optimizations for ceiling division with no overflow - a PR by Alex Gaynor and Claude Code [ https://substack.com/redirect/55f44bad-dd1b-41b4-9933-30ffb9459c35?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Alex Gaynor maintains rust-asn1 [ https://substack.com/redirect/2c809d9d-5eed-4ca6-a5c3-40381f7dda0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and recently spotted a missing LLVM compiler optimization while hacking on it, with the assistance of Claude [ https://substack.com/redirect/8b9ab76a-77dd-4775-93e3-99633e30506b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (Alex works for Anthropic).
He describes how he confirmed that optimization in So you want to serialize some DER? [ https://substack.com/redirect/4c352590-3c24-4e00-80c9-bcedbd64edec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], taking advantage of a tool called Alive2 [ https://substack.com/redirect/52dccb3d-62ac-48d4-9236-2d768696f6da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to automatically verify that the potential optimization resulted in the same behavior.
Alex filed a bug [ https://substack.com/redirect/7ee7db1a-4dc5-4c80-8b84-cd8b31beaef7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and then...
Obviously the next move is to see if I can send a PR to LLVM, but it’s been years since I was doing compiler development or was familiar with the LLVM internals and I wasn’t really prepared to invest the time and energy necessary to get back up to speed. But as a friend pointed out… what about Claude?
At this point my instinct was, "Claude is great, but I'm not sure if I'll be able to effectively code review any changes it proposes, and I'm not going to be the asshole who submits an untested and unreviewed PR that wastes a bunch of maintainer time". But excitement got the better of me, and I asked claude-code to see if it could implement the necessary optimization, based on nothing more than the test cases.
Alex reviewed the resulting code very carefully to ensure he wasn't wasting anyone's time, then submitted the PR [ https://substack.com/redirect/55f44bad-dd1b-41b4-9933-30ffb9459c35?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and had Claude Code help implement the various changes requested by the reviewers. The optimization landed [ https://substack.com/redirect/74aed275-ef44-43d2-9b58-5a1e1f782708?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] two weeks ago.
Alex's conclusion (emphasis mine):
I am incredibly leery about over-generalizing [ https://substack.com/redirect/a9ae8a81-e5ab-4034-b4db-a5626f565d27?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] how to understand the capacity of the models, but at a minimum it seems safe to conclude that sometimes you should just let the model have a shot at a problem and you may be surprised -- particularly when the problem has very clear success criteria. This only works if you have the capacity to review what it produces, of course. [...]
This echoes Ethan Mollick's advice to "always invite AI to the table". For programming tasks the "very clear success criteria" is extremely important, as it helps fit the tools-in-a-loop pattern implemented by coding agents such as Claude Code.
LLVM have a policy [ https://substack.com/redirect/21705747-4969-4154-a1ec-ec93c74a829d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on AI-assisted contributions which is compatible with Alex's work here:
[...] the LLVM policy is that contributors are permitted to use artificial intelligence tools to produce contributions, provided that they have the right to license that code under the project license. Contributions found to violate this policy will be removed just like any other offending contribution.
While the LLVM project has a liberal policy on AI tool use, contributors are considered responsible for their contributions. We encourage contributors to review all generated code before sending it for review to verify its correctness and to understand it so that they can answer questions during code review.
Back in April Ben Evans put out a call [ https://substack.com/redirect/f07039a9-06db-4557-af19-24a8e0ca6f5b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for concrete evidence that LLM tools were being used to solve non-trivial problems in mature open source projects:
I keep hearing #AI boosters / talking heads claiming that #LLMs have transformed software development [...] Share some AI-derived pull requests that deal with non-obvious corner cases or non-trivial bugs from mature #opensource projects.
I think this LLVM optimization definitely counts!
(I also like how this story supports the idea that AI tools amplify existing human expertise rather than replacing it. Alex had previous experience with LLVM, albeit rusty, and could lean on that knowledge to help direct and evaluate Claude's work.)
Link 2025-06-30 microsoft/vscode-copilot-chat [ https://substack.com/redirect/76cb9f70-8482-4ecc-bd29-bc7840717e1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
As promised [ https://substack.com/redirect/346dc6bf-4f2e-4091-a4b1-0c86c2167e9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at Build 2025 in May, Microsoft have released the GitHub Copilot Chat client for VS Code under an open source (MIT) license.
So far this is just the extension that provides the chat component of Copilot, but the launch announcement [ https://substack.com/redirect/978a3ebc-f5d0-44b2-bf4d-c6a2de55f6be?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] promises that Copilot autocomplete will be coming in the near future:
Next, we will carefully refactor the relevant components of the extension into VS Code core. The original GitHub Copilot extension [ https://substack.com/redirect/d0c09b1f-d23d-4285-a93c-77424f6370ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that provides inline completions remains closed source -- but in the following months we plan to have that functionality be provided by the open sourced GitHub Copilot Chat extension [ https://substack.com/redirect/10233f31-db47-43d9-9320-5b161caa86c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I've started spelunking around looking for the all-important prompts. So far the most interesting I've found are in prompts/node/agent/agentInstructions.tsx [ https://substack.com/redirect/bb7a1f1c-9024-4084-b2d3-8f4b5ea0d3f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with a  block that starts like this [ https://substack.com/redirect/e4f3e0b3-c310-4773-987b-3d7ef4513f66?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
You are a highly sophisticated automated coding agent with expert-level knowledge across many different programming languages and frameworks. The user will ask a question, or ask you to perform a task, and it may require lots of research to answer correctly. There is a selection of tools that let you perform actions or retrieve helpful context to answer the user's question.
There are tool use instructions [ https://substack.com/redirect/2d41535c-e5a2-4136-bf68-921478d83934?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - some edited highlights from those:
When using the ReadFile tool, prefer reading a large section over calling the ReadFile tool many times in sequence. You can also think of all the pieces you may be interested in and read them in parallel. Read large enough context to ensure you get what you need.
You can use the FindTextInFiles to get an overview of a file by searching for a string within that one file, instead of using ReadFile many times.
Don't call the RunInTerminal tool multiple times in parallel. Instead, run one command and wait for the output before running the next command.
After you have performed the user's task, if the user corrected something you did, expressed a coding preference, or communicated a fact that you need to remember, use the UpdateUserPreferences tool to save their preferences.
NEVER try to edit a file by running terminal commands unless the user specifically asks for it.
Use the ReplaceString tool to replace a string in a file, but only if you are sure that the string is unique enough to not cause any issues. You can use this tool multiple times per file.
That file also has separate CodesearchModeInstructions [ https://substack.com/redirect/30dd8d14-a842-4384-8749-3cad74b936da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], as well as a SweBenchAgentPrompt [ https://substack.com/redirect/85e633c5-da43-4223-8c87-6979e8163b8c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] class with a comment saying that it is "used for some evals with swebench".
Elsewhere in the code, prompt/node/summarizer.ts [ https://substack.com/redirect/361413de-a605-43b8-a098-15802fec26a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] illustrates one of their approaches to Context Summarization [ https://substack.com/redirect/044c6194-a7c6-4960-a1a5-6dd78534e7df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with a prompt that looks like this:
You are an expert at summarizing chat conversations.
You will be provided:
- A series of user/assistant message pairs in chronological order
- A final user message indicating the user's intent.
[...]
Structure your summary using the following format:
TITLE: A brief title for the summary
USER INTENT: The user's goal or intent for the conversation
TASK DESCRIPTION: Main technical goals and user requirements
EXISTING: What has already been accomplished. Include file paths and other direct references.
PENDING: What still needs to be done. Include file paths and other direct references.
CODE STATE: A list of all files discussed or modified. Provide code snippets or diffs that illustrate important context.
RELEVANT CODE/DOCUMENTATION SNIPPETS: Key code or documentation snippets from referenced files or discussions.
OTHER NOTES: Any additional context or information that may be relevant.
prompts/node/panel/terminalQuickFix.tsx [ https://substack.com/redirect/99a9d454-cc42-4703-bb51-8b0a1debff84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] looks interesting too, with prompts to help users fix problems they are having in the terminal:
You are a programmer who specializes in using the command line. Your task is to help the user fix a command that was run in the terminal by providing a list of fixed command suggestions. Carefully consider the command line, output and current working directory in your response. [...]
That file also has a PythonModuleError prompt [ https://substack.com/redirect/e3bf68bd-7575-49e1-9a28-dc6ada9cea0e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Follow these guidelines for python:
- NEVER recommend using "pip install" directly, always recommend "python -m pip install"
- The following are pypi modules: ruff, pylint, black, autopep8, etc
- If the error is module not found, recommend installing the module using "python -m pip install" command.
- If activate is not available create an environment using "python -m venv .venv".
There's so much more to explore in here. xtab/common/promptCrafting.ts [ https://substack.com/redirect/4b7889fb-3d31-421e-8d9d-86db097fb4f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] looks like it may be part of the code that's intended to replace Copilot autocomplete, for example.
The way it handles evals is really interesting too. The code for that lives in the test/ [ https://substack.com/redirect/6bab4acd-c421-4e16-a3f0-cf60f82bb710?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] directory. There's a lot of it, so I engaged Gemini 2.5 Pro to help figure out how it worked:
git clone https://github.com/microsoft/vscode-copilot-chat
cd vscode-copilot-chat/chat
files-to-prompt -e ts -c . | llm -m gemini-2.5-pro -s \
'Output detailed markdown architectural documentation explaining how this test suite works, with a focus on how it tests LLM prompts'
Here's the resulting generated documentation [ https://substack.com/redirect/474db26a-8a76-4a8a-a635-8a36b048a282?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which even includes a Mermaid chart (I had to save the Markdown in a regular GitHub repository to get that to render - Gists still don't handle Mermaid.)
The neatest trick is the way it uses a SQLite-based caching mechanism [ https://substack.com/redirect/39822060-7ea2-4e4b-9b84-4cece4bbfc86?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to cache the results of prompts from the LLM, which allows the test suite to be run deterministically even though LLMs themselves are famously non-deterministic.
Link 2025-07-01 Using Claude Code to build a GitHub Actions workflow [ https://substack.com/redirect/a937c270-6eb7-4af8-b3b9-37bd22a7fd34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wanted to add a small feature to one of my GitHub repos - an automatically updated README index listing other files in the repo - so I decided to use Descript [ https://substack.com/redirect/0cc926d4-1b2f-42b7-9d68-60ae2cfcb2b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to record my process using Claude Code. Here's a 7 minute video showing what I did.
I've been wanting to start producing more video content for a while - this felt like a good low-stakes opportunity to put in some reps.
Note 2025-07-01 [ https://substack.com/redirect/26943b3c-1c31-427c-8d45-7c9aed178e29?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I just sent out the second edition of my sponsors only monthly newsletter [ https://substack.com/redirect/390b31ed-712c-45e5-b007-ffe47fffe8fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Anyone who sponsors me for $10/month or more on GitHub [ https://substack.com/redirect/2a952711-fe6f-4adb-9e63-4582bea18986?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] gets this carefully hand-curated summary of the last month in AI/LLMs/my projects designed to be readable in ten minutes or less.
My regular newsletter [ https://substack.com/redirect/869a13cd-a039-4bad-8a5b-5d1ef30001d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] remains free - the monthly one is the only paywalled content I produce, the idea being that you can pay me to send you less.
Here's the first edition for May 2025 [ https://substack.com/redirect/b818f257-8fac-4eeb-8953-12aef1546145?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a preview of what you can expect. You'll get access to the June digest and the full archive automatically if you decide to start sponsoring.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOamN5TXpnM016a3NJbWxoZENJNk1UYzFNVE0wTWprM05Dd2laWGh3SWpveE56Z3lPRGM0T1RjMExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEudk8wSUxOODdpOXFJZWJFX19vTUVZVEhkU2l5VVRGdEhwZDBfVlRSd1BTNCIsInAiOjE2NzIzODczOSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzUxMzQyOTc0LCJleHAiOjIwNjY5MTg5NzQsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.9R0aAyUXEttUukvJw4KGSNUhd8IWu77wdoi6yDwd6M0?
