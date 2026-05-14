# CaMeL offers a promising new direction for mitigating prompt injection attacks

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-04-14T20:10:13.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/camel-offers-a-promising-new-direction

In this newsletter:
CaMeL offers a promising new direction for mitigating prompt injection attacks
GPT-4.1: Three new million token input models from OpenAI, including their cheapest model yet
Plus 5 links and 2 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
CaMeL offers a promising new direction for mitigating prompt injection attacks [ https://substack.com/redirect/fa95c726-c096-4d20-a466-eb8c5ddef96b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-04-11
In the two and a half years [ https://substack.com/redirect/4bff00e6-4c06-4ff9-bd7a-5dfd9cf48097?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that we've been talking about prompt injection attacks I've seen alarmingly little progress towards a robust solution. The new paper Defeating Prompt Injections by Design [ https://substack.com/redirect/d9c372d1-0b95-448a-b1c6-a4a58d3960e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from Google DeepMind finally bucks that trend. This one is worth paying attention to.
If you're new to prompt injection attacks the very short version is this: what happens if someone emails my LLM-driven assistant (or "agent" if you like) and tells it to forward all of my emails to a third party? Here's an extended explanation [ https://substack.com/redirect/1e60826d-6e45-4d03-bc50-0c803843c01f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of why it's so hard to prevent this from being a show-stopping security issue which threatens the dream digital assistants that everyone is trying to build.
The original sin of LLMs that makes them vulnerable to this is when trusted prompts from the user and untrusted text from emails/web pages/etc are concatenated together into the same token stream. I called it "prompt injection" because it's the same anti-pattern as SQL injection [ https://substack.com/redirect/6bc2ebf4-3af6-4c75-9001-0ae6ccd1cc63?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Sadly, there is no known reliable way to have an LLM follow instructions in one category of text while safely applying those instructions to another category of text.
That's where CaMeL comes in.
The new DeepMind paper [ https://substack.com/redirect/d9c372d1-0b95-448a-b1c6-a4a58d3960e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] introduces a system called CaMeL (short for CApabilities for MachinE Learning). The goal of CaMeL is to safely take a prompt like "Send Bob the document he requested in our last meeting" and execute it, taking into account the risk that there might be malicious instructions somewhere in the context that attempt to over-ride the user's intent.
It works by taking a command from a user, converting that into a sequence of steps in a Python-like programming language, then checking the inputs and outputs of each step to make absolutely sure the data involved is only being passed on to the right places.
Addressing a flaw in my Dual-LLM pattern [ https://substack.com/redirect/829aac6d-85cd-44fd-bb52-cbd049d8beeb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Fixing that with capabilities and a custom interpreter [ https://substack.com/redirect/b0d26b39-b638-4d86-a37f-d31b6d4b82b4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
A neat privacy bonus [ https://substack.com/redirect/14ba92e8-e7b9-484c-824a-594d52fed64a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The best part is it doesn't use more AI [ https://substack.com/redirect/d1be8501-4de9-43cc-be46-43906b2b70ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
So, are prompt injections solved now? [ https://substack.com/redirect/32999af2-41ed-4f76-ad47-623e8aa0834d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Camels have two humps [ https://substack.com/redirect/fa30ce8d-9906-4b28-be24-66d687bb5c8b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Addressing a flaw in my Dual-LLM pattern
I'll admit that part of the reason I'm so positive about this paper is that it builds on some of my own work!
Back in April 2023 I proposed The Dual LLM pattern for building AI assistants that can resist prompt injection [ https://substack.com/redirect/1e60826d-6e45-4d03-bc50-0c803843c01f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I theorized a system with two separate LLMs: a privileged LLM with access to tools that the user prompts directly, and a quarantined LLM it can call that has no tool access but is designed to be exposed to potentially untrustworthy tokens.
Crucially, at no point is content handled by the quarantined LLM (Q-LLM) exposed to the privileged LLM (P-LLM). Instead, the Q-LLM populates references - $email-summary-1 for example - and the P-LLM can then say "Display $email-summary-1 to the user" without being exposed to those potentially malicious tokens.
The DeepMind paper references this work early on, and then describes a new-to-me flaw in my design:
A significant step forward in defense strategies is the Dual LLM pattern theoretically described by Willison (2023). This pattern employs two LLMs: a Privileged LLM and a Quarantined LLM. The Privileged LLM is tasked with planning the sequence of actions needed to fulfill the user’s request, such as searching the cloud storage for the meeting notes and fetching the requested document from the cloud storage, and sending it to the client. Importantly, this privileged LLM only sees the initial user query and never the content from potentially compromised data sources (like the file content).
The actual processing of potentially malicious data, like extracting the name of the document to send and the client’s email address, would be delegated to the Quarantined LLM. This Quarantined LLM, crucially, is stripped of any tool-calling capabilities, limiting the harm an injected prompt can cause and guaranteeing that the adversary cannot call arbitrary tools with arbitrary arguments.
Is Dual LLM of Willison enough? While the Dual LLM pattern significantly enhances security by isolating planning from being hijacked by malicious content, it does not completely eliminate all prompt injection risks. Let us consider the example depicted in Figure 1. Here, even with the Dual LLM in place we show that vulnerabilities still exist.
Here's figure 1:
The user's prompt here is:
Can you send Bob the document he requested in our last meeting? Bob's email and the document he asked for are in the meeting notes file.
And there lies the flaw. With the Dual LLM pattern the P-LLM delegates the task of finding Bob's email address to the Q-LLM - but the Q-LLM is still exposed to potentially malicious instructions. An attacker could use those instructions to over-ride that retrieved email address and cause the document to be exfiltrated to an attacker-chosen address.
Fixing that with capabilities and a custom interpreter
CaMeL addresses this problem directly using some very clever security engineering.
In CaMeL, the user's prompt is converted by the P-LLM into a sequence of steps that are described using code. They chose to use a locked-down subset of Python for this, because every available LLM is good at writing Python already:
We build a custom Python interpreter that operates over a restricted version of Python. We choose Python as it is a very popular programming language, and large language models are very competent at writing it. We use Python’s built-in ast library to parse the abstract syntax tree, and interpret each tree node in a recursive fashion.
Consider the prompt "Find Bob's email in my last email and send him a reminder about tomorrow's meeting". CaMeL would convert that into code looking something like this:
email = get_last_email
address = query_quarantined_llm(
"Find Bob's email address in [email]",
output_schema=EmailStr
)
send_email(
subject="Meeting tomorrow",
body="Remember our meeting tomorrow",
recipient=address,
)
As you can see, this code combines several calls to tools that are exposed as Python functions - one to retrieve the last email, one that uses a quarantined LLM to extract Bob's email address from it and one to send a new email.
Here's where things get clever: by using a custom interpreter, CaMeL can apply extra rules to the code that is executed. It can keep track of which variables were derived from which other variables and apply security policies that take that trail into account.
In this example, email is a potential source of untrusted tokens, which means address is as well (since it is derived from email).
The security rules to apply are as follows:
get_last_email: always allowed
send_email: only if recipient is trusted
If the address (passed to send_email as the recipient parameter) is a known, trusted adress - based on policies set by the user - the system can send that email without prompting first. If it's an unknown email the user can be asked to approve the message.
Capabilities are effectively tags that can be attached to each of the variables, to track things like who is allowed to read a piece of data and the source that the data came from. Policies can then be configured to allow or deny actions based on those capabilities.
A neat privacy bonus
There are other potential benefits to this design as well. The P-LLM needs to be quite sophisticated, as it's responsible for building a plan and then generating code in the custom Python dialect. The Q-LLM can be a whole lot less powerful:
As parsing data is likely to be easier than creating a plan and writing code for the user’s query, one could use a smaller language model for the Q-LLM. On top of being faster and cheaper, this LLM can potentially also be run locally on the user’s machine. This would improve the user’s privacy with respect to the model provider: since the LLM used as the P-LLM is only provided with the user query, the P-LLM provider never sees the tool outputs (which might contain sensitive information that should not be shared with the P-LLM provider).
This means a CaMeL system could use a cloud-hosted LLM as the driver while keeping the user's own private data safely restricted to their own personal device.
The best part is it doesn't use more AI
Most of the proposed solutions I have seen to prompt injection to date involve layering on even more AI. I wrote about why I think this is a bad idea in You can’t solve AI security problems with more AI [ https://substack.com/redirect/24edc078-140e-40f3-a3bd-11277ca699a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. AI techniques use probabilities: you can train a model on a collection of previous prompt injection examples and get to a 99% score in detecting new ones... and that's useless, because in application security 99% is a failing grade [ https://substack.com/redirect/bbfd44c0-9dc0-4626-ad73-fe3e33451273?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The job of an adversarial attacker is to find the 1% of attacks that get through. If we protected against SQL injection or XSS using methods that fail 1% of the time our systems would be hacked to pieces in moments.
The CaMeL proposal recognizes this:
CaMeL is a practical defense to prompt injection achieving security not through model training techniques but through principled system design around language models. Our approach effectively solves the AgentDojo benchmark while providing strong guarantees against unintended actions and data exfiltration. […]
This is the first mitigation for prompt injection I've seen that claims to provide strong guarantees! Coming from security researchers that's a very high bar.
So, are prompt injections solved now?
Quoting section 8.3 from the paper:
8.3. So, are prompt injections solved now?
No, prompt injection attacks are not fully solved. While CaMeL significantly improves the security of LLM agents against prompt injection attacks and allows for fine-grained policy enforcement, it is not without limitations.
Importantly, CaMeL suffers from users needing to codify and specify security policies and maintain them. CaMeL also comes with a user burden. At the same time, it is well known that balancing security with user experience, especially with de-classification and user fatigue, is challenging.
By "user fatigue" they mean that thing where if you constantly ask a user to approve actions ("Really send this email?", "Is it OK to access this API?", "Grant access to your bank account?") they risk falling into a fugue state where they say "yes" to everything.
This can affect the most cautious among us. Security researcher Troy Hunt fell for a phishing attack [ https://substack.com/redirect/af7b1a2c-fad3-407c-aa63-10f7170f3621?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] just last month due to jetlag-induced tiredness.
Anything that requires end users to think about security policies also makes me deeply nervous. I have enough trouble thinking through those myself (I still haven't fully figured out AWS IAM) and I've been involved in application security for two decades!
CaMeL really does represent a promising path forward though: the first credible prompt injection mitigation I've seen that doesn't just throw more AI at the problem and instead leans on tried-and-proven concepts from security engineering, like capabilities and data flow analysis.
My hope is that there's a version of this which combines robustly selected defaults with a clear user interface design that can finally make the dreams of general purpose digital assistants a secure reality.
Camels have two humps
Why did they pick CaMeL as the abbreviated name for their system? I like to think it's because camels have two humps, and CaMeL is an improved evolution of my dual LLM proposal.
GPT-4.1: Three new million token input models from OpenAI, including their cheapest model yet [ https://substack.com/redirect/e015e54d-e697-420f-9bdf-34858ca5c5d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-04-14
OpenAI introduced [ https://substack.com/redirect/ae3c26ff-10ff-4948-814b-23ccd74b8f30?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] three new models this morning: GPT-4.1, GPT-4.1 mini and GPT-4.1 nano. These are API-only models right now, not available through the ChatGPT interface (though you can try them out in OpenAI's API playground [ https://substack.com/redirect/0b54015b-6049-44b6-9e60-59f76890da43?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). All three models can handle 1,047,576 tokens of input and 32,768 tokens of output, and all three have a May 31, 2024 cut-off date (their previous models were mostly September 2023).
The models score higher than GPT-4o and GPT-4.5 on coding benchmarks, and do very well on long context benchmarks as well. They also claim improvements in instruction following - following requested formats, obeying negative instructions, sorting output and obeying instructions to say "I don't know".
I released a new version of my llm-openai [ https://substack.com/redirect/f644be29-61ee-4a78-94f0-de965aa7ae1c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin supporting the new models. This is a new thing for the LLM [ https://substack.com/redirect/2b92fb57-e79e-4403-8f25-d87f91c8475e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] ecosystem: previously OpenAI models were only supported in core, which meant I had to ship a full LLM release to add support for them.
You can run the new models like this:
llm install llm-openai-plugin -U
llm -m openai/gpt-4.1 "Generate an SVG of a pelican riding a bicycle"
The other model IDs are openai/gpt-4.1-mini and openai/gpt-4.1-nano.
Here's the pelican riding a bicycle [ https://substack.com/redirect/0c246fcd-417f-486e-a710-8d1ddcc59651?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I got from full sized GPT-4.1:
I'm particularly excited by GPT-4.1 nano [ https://substack.com/redirect/fe39e366-3436-4428-8d8e-d13f8b46b316?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which handles image and text input up to a million tokens and is priced lower than any other previous OpenAI model: $0.10/million for input and $0.40/million for output, less than previous cheapest OpenAI model GPT-4o-mini ($0.15/$0.60). I've updated my LLM pricing table [ https://substack.com/redirect/f2d070f3-0183-4126-a95c-f8d336177ff9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to include the new models.
They're not the cheapest overall though: Gemini 2.0 Flash Lite and, Gemini 1.5 Flash 8B, Amazon Nova Lite and Nova Micro and Mistral's 3B, 8B and Small 3.1 hosted models remain less expensive.
As a demonstration of just how cheap GPT-4.1 nano is, consider this photograph I took of some pelicans:
I ran that through GPT-4.1 nano like this:
llm -m openai/gpt-4.1-nano describe \
-a https://static.simonwillison.net/static/2025/two-pelicans.jpg
And got back this response:
The image shows two pelicans flying against a clear blue sky. They are positioned in flight, with their wings extended, showcasing their large wingspan and feather patterns. The pelican on the right appears slightly higher and facing slightly to the left, while the pelican on the left is oriented more horizontally with its beak pointing forward. Both birds display a combination of brown, tan, and white plumage, characteristic of pelicans, with their long beaks prominently visible.
Running llm logs -c --usage revealed that this used 1,933 input tokens and 96 output tokens. Passing those through the pricing calculator [ https://substack.com/redirect/f2d070f3-0183-4126-a95c-f8d336177ff9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] returns a total cost of $0.000232, or 0.0232 cents.
That means I could use GPT-4.1 nano to generate descriptions of 4,310 images like this one for just shy of a dollar.
A few closing thoughts on these new models:
The 1 million input token context thing is a really big deal. The huge token context has been a major competitive advantage for the Google Gemini models for a full year at this point - it's reassuring to see other vendors start to catch up. I'd like to see the same from Anthropic - Claude was the first model to hit 200,000 but hasn't shipped more than that yet (aside from a 500,000 token model that was restricted to their big enterprise partners).
When I added fragments support [ https://substack.com/redirect/bccb5476-0363-4b13-a8ac-b4b483b8b345?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to LLM last week the feature was mainly designed to help take advantage of longer context models. It's pleasing to see another one show up so shortly after that release.
OpenAI really emphasized code performance for this model. They called out the Aider benchmark [ https://substack.com/redirect/e9944b51-831a-4f09-81da-e714523aa64b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in their announcement post.
As expected [ https://substack.com/redirect/7db8ce33-1819-4e87-a879-9739bf0f8483?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], GPT-4.5 turned out to be not long for this world:
We will also begin deprecating GPT‑4.5 Preview in the API, as GPT‑4.1 offers improved or similar performance on many key capabilities at much lower cost and latency. GPT‑4.5 Preview will be turned off in three months, on July 14, 2025, to allow time for developers to transition
In the livestream announcement [ https://substack.com/redirect/f0306a75-6d70-47cf-997a-70d5cad73bba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Michelle Pokrass let slip [ https://substack.com/redirect/b7f886a8-9704-499d-84b5-7688f8afcd6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that the codename for the model was Quasar - that's the name of the stealth model that's been previewing on OpenRouter [ https://substack.com/redirect/ae078a15-8c06-4187-b67e-e3a0b2785700?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the past two weeks. That has now been confirmed [ https://substack.com/redirect/a840bde3-aa07-4575-a01f-fd692b6835a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by OpenRouter.
OpenAI shared a GPT 4.1 Prompting Guide [ https://substack.com/redirect/4bb08e81-0c0e-4627-8caf-d10fc6694d8d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which includes this tip about long context prompting:
Especially in long context usage, placement of instructions and context can impact performance. If you have long context in your prompt, ideally place your instructions at both the beginning and end of the provided context, as we found this to perform better than only above or below. If you’d prefer to only have your instructions once, then above the provided context works better than below.
Adding instructions before the content is incompatible with prompt caching [ https://substack.com/redirect/9dbd8ab2-40be-45bb-965f-c90fc1cfa7bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - I always keep user instructions at the end since doing so means multiple prompts can benefit from OpenAI's prefix cache.
They also recommend XML-style delimiters over JSON for long context, suggesting this format (complete with the XML-invalid unquoted attribute) that's similar to the format recommended by Anthropic [ https://substack.com/redirect/24f9b0f8-2baf-4d28-807e-57b28d8e1c6c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Claude:
The quick brown fox jumps over the lazy dog
There's an extensive section at the end describing their recommended approach to applying file diffs [ https://substack.com/redirect/733df58b-9513-4403-b1c8-2b04a92ca97e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: "we open-source here one recommended diff format, on which the model has been extensively trained".
One thing notably absent from the GPT-4.1 announcement is any mention of audio support. The "o" in GPT-4o stood for "omni", because it was a multi-modal model with image and audio input and output. The 4.1 models appear to be text and image input and text output only.
Link 2025-04-11 Default styles for h1 elements are changing [ https://substack.com/redirect/0cf72322-ac63-4f6c-8489-e332d982c697?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Wow, this is a rare occurrence! Firefox are rolling out a change to the default user-agent stylesheet for nested  elements, currently ramping from 5% to 50% of users and with full roll-out planned for Firefox 140 in June 2025. Chrome is showing deprecation warnings and Safari are expected to follow suit in the future.
What's changing? The default sizes of  elements that are nested inside , ,  and .
These are the default styles being removed:
/ where x is :is(article, aside, nav, section) /
x h1 { margin-block: 0.83em; font-size: 1.50em; }
x x h1 { margin-block: 1.00em; font-size: 1.17em; }
x x x h1 { margin-block: 1.33em; font-size: 1.00em; }
x x x x h1 { margin-block: 1.67em; font-size: 0.83em; }
x x x x x h1 { margin-block: 2.33em; font-size: 0.67em; }
The short version is that, many years ago, the HTML spec introduced the idea that an  within a nested section should have the same meaning (and hence visual styling) as an . This never really took off and wasn't reflected by the accessibility tree, and was removed from the HTML spec in 2022. The browsers are now trying to cleanup the legacy default styles.
This advice from that post sounds sensible to me:
Do not rely on default browser styles for conveying a heading hierarchy. Explicitly define your document hierarchy using  for second-level headings,  for third-level, etc.
Always define your own font-size and margin for  elements.
Link 2025-04-11 llm-fragments-rust [ https://substack.com/redirect/f5cb7082-1ff0-444c-aa09-a65d63471811?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Inspired by Filippo Valsorda's llm-fragments-go [ https://substack.com/redirect/29c3c0e6-78a9-4ad2-9278-ab58adcb9a6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Francois Garillot created llm-fragments-rust, an LLM fragments [ https://substack.com/redirect/bccb5476-0363-4b13-a8ac-b4b483b8b345?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin that lets you pull documentation for any Rust crate directly into a prompt to LLM.
I really like this example, which uses two fragments to load documentation for two crates at once:
llm -f rust:rand@0.8.5 -f rust:tokio "How do I generate random numbers asynchronously?"
The code [ https://substack.com/redirect/615d4714-00b0-4188-bee6-3143e210490c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] uses some neat tricks: it creates a new Rust project in a temporary directory (similar to how llm-fragments-go works), adds the crates and uses cargo doc --no-deps --document-private-items to generate documentation. Then it runs cargo tree --edges features to add dependency information, and cargo metadata --format-version=1 to include additional metadata about the crate.
Quote 2025-04-12
Backticks are traditionally banned from use in future language features, due to the small symbol. No reader should need to distinguish ` from ' at a glance.
Steve Dower [ https://substack.com/redirect/80c5f2ce-58a5-4b39-a824-435ee5e338dd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-04-12
Slopsquatting -- when an LLM hallucinates a non-existent package name, and a bad actor registers it maliciously. The AI brother of typosquatting.
Credit to @sethmlarson [ https://substack.com/redirect/7d63dde0-8a1a-4c98-8540-989b15173aad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the name
Andrew Nesbitt [ https://substack.com/redirect/c82f191c-8279-4134-a941-1c2f1662f8a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-04-13 Stevens: a hackable AI assistant using a single SQLite table and a handful of cron jobs [ https://substack.com/redirect/6e18c275-58d9-46bb-a139-e5fb2b5264de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Geoffrey Litt reports on Stevens, a shared digital assistant he put together for his family using SQLite and scheduled tasks running on Val Town.
The design is refreshingly simple considering how much it can do. Everything works around a single memories table. A memory has text, tags, creation metadata and an optional date for things like calendar entries and weather reports.
Everything else is handled by scheduled jobs to popular weather information and events from Google Calendar, a Telegram integration offering a chat UI and a neat system where USPS postal email delivery notifications are run through Val's own email handling mechanism to trigger a Claude prompt to add those as memories too.
Here's the full code on Val Town [ https://substack.com/redirect/c291e660-733f-49b7-9c33-c87078fa0701?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], including the daily briefing prompt [ https://substack.com/redirect/8483c0ed-5aa4-44c7-a4cc-d8aec9cd381d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that incorporates most of the personality of the bot.
Link 2025-04-14 Using LLMs as the first line of support in Open Source [ https://substack.com/redirect/3c207e89-a0a2-465a-b77a-6efdbcf07d0c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
From reading the title I was nervous that this might involve automating the initial response to a user support query in an issue tracker with an LLM, but Carlton Gibson has better taste than that.
The open contribution model engendered by GitHub — where anonymous (to the project) users can create issues, and comments, which are almost always extractive support requests — results in an effective denial-of-service attack against maintainers. [...]
For anonymous users, who really just want help almost all the time, the pattern I’m settling on is to facilitate them getting their answer from their LLM of choice. [...] we can generate a file that we offer users to download, then we tell the user to pass this to (say) Claude with a simple prompt for their question.
This resonates with the concept proposed by llms.txt [ https://substack.com/redirect/666ae444-86b5-459f-bf24-e332247b58b3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - making LLM-friendly context files available for different projects.
My simonw/docs-for-llms [ https://substack.com/redirect/8581bd24-add0-4c92-ab90-89f00b403e1f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] contains my own early experiment with this: I'm running a build script to create LLM-friendly concatenated documentation for several of my projects, and my llm-docs [ https://substack.com/redirect/d43e1c15-d11d-4ad4-81b5-a40c1be37065?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin (described here [ https://substack.com/redirect/77ca65d3-12e4-4560-96e1-3eb7cb899bc5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) can then be used to ask questions of that documentation.
It's possible to pre-populate the Claude UI with a prompt by linking to https://claude.ai/new?q={PLACE_HOLDER}, but it looks like there's quite a short length limit on how much text can be passed that way. It would be neat if you could pass a URL to a larger document instead.
ChatGPT also supports https://chatgpt.com/?q=your-prompt-here (again with a short length limit) and directly executes the prompt rather than waiting for you to edit it first(!)
Link 2025-04-14 SQLite File Format Viewer [ https://substack.com/redirect/7231a99c-b2a3-4816-80a8-586a9c043d3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Neat browser-based visual interface for exploring the structure of a SQLite database file, built by Visal In using React and a custom parser implemented in TypeScript [ https://substack.com/redirect/96c394e3-2bb0-48df-bfb2-bb2ea99477b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOakV6TXpJME1UQXNJbWxoZENJNk1UYzBORFkyTVRReU1pd2laWGh3SWpveE56YzJNVGszTkRJeUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuVWoydEg4dVZ4emxmRXFINnprM0pJeGNvOFZfSXc4RHBkcUdfa3MxeGNFZyIsInAiOjE2MTMzMjQxMCwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQ0NjYxNDIyLCJleHAiOjE3NDcyNTM0MjIsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.6K1gq9a3A3eHu1vwhfTT_B0Wa3ulVd9tMWVBEJN5pFw?
