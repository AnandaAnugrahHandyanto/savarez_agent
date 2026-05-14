# Long context support in LLM 0.24 using fragments

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-04-08T00:40:52.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/long-context-support-in-llm-024-using

In this newsletter:
Long context support in LLM 0.24 using fragments and template plugins
Initial impressions of Llama 4
Plus 1 link and 5 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Long context support in LLM 0.24 using fragments and template plugins [ https://substack.com/redirect/85cfab14-2bf6-4580-843b-6d8186c0e1b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-04-07
LLM 0.24 is now available [ https://substack.com/redirect/dffa2b9d-ccb1-48b9-8562-68c39c5e13ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with new features to help take advantage of the increasingly long input context supported by modern LLMs.
(LLM [ https://substack.com/redirect/e0ddc87e-2002-46ff-8e80-d8d4ea118aef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is my command-line tool and Python library [ https://substack.com/redirect/cad1fa4e-1e4e-465c-a3bd-0842c592878e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for interacting with LLMs, supported by 20+ plugins [ https://substack.com/redirect/b6449522-c2b5-4cee-822c-f4d178798c76?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] adding support for both local and remote models from a bunch of different providers.)
Trying it out [ https://substack.com/redirect/0363dc56-b7b2-4a89-9c73-acad6f1c6664?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Improving LLM's support for long context models [ https://substack.com/redirect/1ee66269-e9b1-49eb-9fa0-94dd56b6a197?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Asking questions of LLM's documentation [ https://substack.com/redirect/dc01ddd9-f756-4f56-98c3-29c23d3a5f6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Publishing, sharing and reusing templates [ https://substack.com/redirect/1adb3881-fc97-43e1-b224-83bb85d03cdd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Everything else in LLM 0.24 [ https://substack.com/redirect/3c814994-87d5-4aba-8e5f-a110ebe74061?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Trying it out
To install LLM with uv [ https://substack.com/redirect/28659fcc-3685-431d-9af8-a14272bcbe83?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (there are several other options [ https://substack.com/redirect/498beb3c-5b99-40e6-9417-225088feb0f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
uv tool install llm
You'll need to either provide an OpenAI API key [ https://substack.com/redirect/992f2673-0d7f-4885-882c-7812a3fed176?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or install a plugin [ https://substack.com/redirect/b6449522-c2b5-4cee-822c-f4d178798c76?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to use local models or models from other providers:
llm keys set openai
# Paste OpenAI API key here
To upgrade LLM [ https://substack.com/redirect/7cb30689-c5b6-44dd-9e36-45d5572d6bdd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from a previous version:
llm install -U llm
The biggest new feature is fragments [ https://substack.com/redirect/00fb2f9b-fb17-4224-8a77-caa11311c899?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can now use -f filename or -f url to add one or more fragments to your prompt, which means you can do things like this:
llm -f https://simonwillison.net/2025/Apr/5/llama-4-notes/ 'bullet point summary'
Here's the output [ https://substack.com/redirect/8e950b3c-9f38-41eb-b10b-e9a8a5279f9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from that prompt, exported using llm logs -c --expand --usage. Token cost was 5,372 input, 374 output which works out as 0.103 cents (around 1/10th of a cent) using the default GPT-4o mini model.
Plugins can implement custom fragment loaders with a prefix. The llm-fragments-github [ https://substack.com/redirect/4886c234-bf05-426a-8a64-3f0e0fbc45f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin adds a github: prefix that can be used to load every text file in a GitHub repository as a list of fragments:
llm install llm-fragments-github
llm -f github:simonw/s3-credentials 'Suggest new features for this tool'
Here's the output [ https://substack.com/redirect/5db13f40-2884-4be7-bbb8-3b9c4bd9e726?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. That took 49,856 input tokens for a total cost of 0.7843 cents - nearly a whole cent!
Improving LLM's support for long context models
Long context [ https://substack.com/redirect/4a23cf69-2314-4cae-b61a-ba844dd0bb5a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is one of the most exciting trends in LLMs over the past eighteen months. Saturday's Llama 4 Scout release [ https://substack.com/redirect/99f62c70-d17d-4f67-96dc-209b4599641c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] gave us the first model with a full 10 million token context. Google's Gemini [ https://substack.com/redirect/93b6a509-ba7c-498a-8a54-3d48931efe86?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] family has several 1-2 million token models, and the baseline for recent models from both OpenAI and Anthropic is 100 or 200 thousand.
Two years ago most models capped out at 8,000 tokens of input. Long context opens up many new interesting ways to apply this class of technology.
I've been using long context models via my files-to-prompt tool [ https://substack.com/redirect/3c1114f2-9ac9-49c5-998d-261418e006e4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to summarize large codebases, explain how they work and even to debug gnarly bugs [ https://substack.com/redirect/d47d109a-0bde-4c8c-9ea9-068f2c1a5d00?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. As demonstrated above, it's surprisingly inexpensive to drop tens of thousands of tokens into models like GPT-4o mini or most of the Google Gemini series, and the results are often very impressive.
One of LLM's most useful features is that it logs every prompt and response [ https://substack.com/redirect/f1cd7cf7-67cd-4a01-abae-60223bee09a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to a SQLite database. This is great for comparing the same prompt against different models and tracking experiments over time - my own database contained thousands of responses from hundreds of different models accumulated over the past couple of years.
This is where long context prompts were starting to be a problem. Since LLM stores the full prompt and response in the database, asking five questions of the same source code could result in five duplicate copies of that text in the database!
The new fragments feature targets this problem head on. Each fragment is stored once in a fragments [ https://substack.com/redirect/2dae51e9-bce7-4113-991e-d68548974c40?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] table, then de-duplicated in the future using a SHA256 hash of its content.
This saves on storage, and also enables features like llm logs -f X for seeing all logged responses that use a particular fragment [ https://substack.com/redirect/23b19368-0164-464b-b7c6-2452f8e0633a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Fragments can be specified in several different ways:
a path to a file
a URL to data online
an alias that's been set against a previous fragment (see llm fragments set [ https://substack.com/redirect/61b78ff4-cb5e-494e-b5b7-cd7b45234853?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
a hash ID of the content of a fragment
using prefix:argument to specify fragments from a plugin
Asking questions of LLM's documentation
Wouldn't it be neat if LLM could answer questions about its own documentation?
The new llm-docs [ https://substack.com/redirect/85d8ec8d-04f3-48aa-944b-16c5569f8d64?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin (built with the new register_fragment_loaders plugin hook [ https://substack.com/redirect/ec6390cf-651c-4da6-a8e6-3ae0e2af5a12?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) enables exactly that:
llm install llm-docs
llm -f docs: "How do I embed a binary file?"
The output [ https://substack.com/redirect/3548e272-eec4-4637-92cd-14c8fd8f0c6f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] starts like this:
To embed a binary file using the LLM command-line interface, you can use the llm embed command with the --binary option. Here’s how you can do it:
Make sure you have the appropriate embedding model installed that supports binary input.
Use the following command syntax:
llm embed -m  --binary -i
Replace  with the identifier for the embedding model you want to use (e.g., clip for the CLIP model) and  with the path to your actual binary file.
(74,570 input, 240 output = 1.1329 cents with GPT-4o mini)
Using -f docs: with just the prefix is the same as using -f docs:llm. The plugin fetches the documentation for your current version of LLM from my new simonw/docs-for-llms [ https://substack.com/redirect/ac9ad593-bc45-4d35-bff7-b42550698ecd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repo, which also provides packaged documentation files for my datasette, s3-credentials, shot-scraper and sqlite-utils projects.
Datasette's documentation has got pretty long, so you might need to run that through a Gemini model instead (using the llm-gemini plugin [ https://substack.com/redirect/9b758ad3-8011-4176-9f9d-bc674a270961?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]):
llm -f docs:datasette -m gemini-2.0-flash \
'Build a render_cell plugin that detects and renders markdown'
Here's the output [ https://substack.com/redirect/31164995-1898-41b0-b9ba-23fab08c2cf9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. 132,042 input, 1,129 output with Gemini 2.0 Flash = 1.3656 cents.
You can browse the combined documentation files this uses in docs-for-llm [ https://substack.com/redirect/ac9ad593-bc45-4d35-bff7-b42550698ecd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. They're built using GitHub Actions.
llms-txt [ https://substack.com/redirect/c60471d1-85ca-441d-86b0-f427fdf92808?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a project lead by Jeremy Howard that encourages projects to publish similar files to help LLMs ingest a succinct copy of their documentation.
Publishing, sharing and reusing templates
The new register_template_loaders plugin hook [ https://substack.com/redirect/2a4a0f42-78aa-4e85-bbca-673a5633e3e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] allows plugins to register prefix:value custom template loaders, for use with the llm -t option.
llm-templates-github [ https://substack.com/redirect/53d41f19-04fc-40e2-baff-a95694f71a88?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and llm-templates-fabric [ https://substack.com/redirect/6f61e05a-0267-48d1-8165-8cdad9973986?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] are two new plugins that make use of that hook.
llm-templates-github lets you share and use templates via a public GitHub repository. Here's how to run my Pelican riding a bicycle [ https://substack.com/redirect/9dd86eb0-078f-4146-b4cf-31f08111ac0c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] benchmark against a specific model:
llm install llm-templates-github
llm -t gh:simonw/pelican-svg -m o3-mini
This executes this pelican-svg.yaml [ https://substack.com/redirect/f03b8174-9d91-419e-9593-b808d7371227?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] template stored in my simonw/llm-templates [ https://substack.com/redirect/eef57c1e-865b-4e75-9029-906ac3e151a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repository, using a new repository naming convention.
llm -t gh:simonw/pelican-svg will load that pelican-svg.yaml file from the simonw/llm-templates repo. You can also use llm -t gh:simonw/name-of-repo/name-of-template to load a template from a repository that doesn't follow that convention.
To share your own templates, create a repository on GitHub under your user account called llm-templates and start saving .yaml files to it.
llm-templates-fabric [ https://substack.com/redirect/6f61e05a-0267-48d1-8165-8cdad9973986?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provides a similar mechanism for loading templates from Daniel Miessler's extensive fabric collection [ https://substack.com/redirect/1b78e165-e007-47a8-ae2c-6eb2b35de174?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
llm install llm-templates-fabric
curl https://simonwillison.net/2025/Apr/6/only-miffy/ | \
llm -t f:extract_main_idea
A conversation with Daniel was the inspiration for this new plugin hook.
Everything else in LLM 0.24
LLM 0.24 is a big release, spanning 51 commits [ https://substack.com/redirect/a5a24d02-b44b-47c5-b1f6-231c6cef117c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The release notes [ https://substack.com/redirect/dffa2b9d-ccb1-48b9-8562-68c39c5e13ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] cover everything that's new in full - here are a few of my highlights:
The new llm-openai plugin [ https://substack.com/redirect/caf93864-43c6-4220-8f2c-020c6c82d5b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provides support for o1-pro (which is not supported by the OpenAI mechanism used by LLM core). Future OpenAI features will migrate to this plugin instead of LLM core itself.
The problem with OpenAI models being handled by LLM core is that I have to release a whole new version of LLM every time OpenAI releases a new model or feature. Migrating this stuff out to a plugin means I can release new version of that plugin independently of LLM itself - something I frequently do for llm-anthropic [ https://substack.com/redirect/42c24789-64b9-475b-8dae-c6d84ce9f1ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and llm-gemini [ https://substack.com/redirect/9b758ad3-8011-4176-9f9d-bc674a270961?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and others.
The new llm-openai plugin uses their Responses API, a new shape of API which I covered last month [ https://substack.com/redirect/2f485ba8-79fc-47f0-a3e4-7bfbf53c14e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
llm -t $URL option can now take a URL to a YAML template. #856 [ https://substack.com/redirect/99f04867-a6b1-45e2-886c-5779281449bf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The new custom template loaders are fun, but being able to paste in a URL to a YAML file somewhere provides a simpler way to share templates.
Templates can now store default model options. #845 [ https://substack.com/redirect/5c2d43d7-36a2-48a0-8597-5e9549261287?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Attachments can now be stored in templates. #826 [ https://substack.com/redirect/975c93ed-4b57-43c6-9b7d-436ae341d96b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The quickest way to create your own template is with the llm prompt ... --save name-of-template command. This now works with attachments, fragments and default model options, each of which is persisted in the template YAML file [ https://substack.com/redirect/8f8aa6a4-5117-44f5-9ef2-6b8a2e05124b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
New llm models options [ https://substack.com/redirect/b9a91972-b6d6-433f-a607-5251925c65de?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] family of commands for setting default options for particular models. #829 [ https://substack.com/redirect/144d66a0-560a-495e-8cb2-06a5b82a0a82?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I built this when I learned that [ https://substack.com/redirect/a41bee86-918d-4642-8f16-84d63f50ed9b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Qwen's QwQ-32b model works best with temperature 0.7 and top p 0.95.
llm prompt -d path-to-sqlite.db option can now be used to write logs to a custom SQLite database. #858 [ https://substack.com/redirect/1f361678-3bb8-408e-b241-299caadb6756?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
This proved extremely useful for testing fragments - it meant I could run a prompt and save the full response to a separate SQLite database which I could then upload to S3 and share as a link to Datasette Lite [ https://substack.com/redirect/7dad55d7-c01f-459c-8130-b288b82d2006?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
llm similar -p/--plain option providing more human-readable output than the default JSON. #853 [ https://substack.com/redirect/024eebed-7aa5-491a-a86c-59d5ae6d174a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I'd like this to be the default output, but I'm holding off on changing that until LLM 1.0 since it's a breaking change for people building automations against the JSON from llm similar.
Set the LLM_RAISE_ERRORS=1 environment variable to raise errors during prompts rather than suppressing them, which means you can run python -i -m llm 'prompt' and then drop into a debugger on errors with import pdb; pdb.pm. #817 [ https://substack.com/redirect/fe09e3f5-d89c-4447-8f2e-f3d7060659c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Really useful for debugging new model plugins.
llm prompt -q gpt -q 4o option - pass -q searchterm one or more times to execute a prompt against the first model that matches all of those strings - useful for if you can't remember the full model ID. #841 [ https://substack.com/redirect/dc72bcfd-6e9c-4fcc-b16d-ebe9128306ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Pretty obscure but I found myself needing this. Vendors love releasing models with names like gemini-2.5-pro-exp-03-25, now I can run llm -q gem -q 2.5 -q exp 'say hi' to save me from looking up the model ID.
OpenAI compatible models [ https://substack.com/redirect/e84794ef-52ab-43b2-a812-3d28c5bb1989?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] configured using extra-openai-models.yaml now support supports_schema: true, vision: true and audio: true options. Thanks @adaitche [ https://substack.com/redirect/18274cdc-6ee1-4aa0-bcd7-42ae6b3786c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and @giuli007 [ https://substack.com/redirect/23a53985-e9ae-4b43-8405-783660d5f814?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. #819 [ https://substack.com/redirect/b8d8f3d7-238a-4a06-9909-449f5d1b7c8a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], #843 [ https://substack.com/redirect/0845f472-1a33-47bf-86a2-b07f4f77cf71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
I don't use this feature myself but it's clearly popular, this isn't the first time I'e had PRs with improvements from the wider community.
Initial impressions of Llama 4 [ https://substack.com/redirect/99f62c70-d17d-4f67-96dc-209b4599641c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-04-05
Dropping a model release as significant as Llama 4 on a weekend is plain unfair! So far the best place to learn about the new model family is this post on the Meta AI blog [ https://substack.com/redirect/3a8270b7-c40d-4a5a-ac73-46b5b83582a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. They've released two new models today: Llama 4 Maverick is a 400B model (128 experts, 17B active parameters), text and image input with a 1 million token context length. Llama 4 Scout is 109B total parameters (16 experts, 17B active), also multi-modal and with a claimed 10 million token context length - an industry first.
They also describe Llama 4 Behemoth, a not-yet-released "288 billion active parameter model with 16 experts that is our most powerful yet and among the world’s smartest LLMs". Behemoth has 2 trillion parameters total and was used to train both Scout and Maverick.
No news yet on a Llama reasoning model beyond this coming soon page [ https://substack.com/redirect/a9ef6ce4-50ee-47f1-a0ce-7fed60833a6d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with a looping video of an academic-looking llama.
Llama 4 Maverick is now sat in second place on the LM Arena leaderboard [ https://substack.com/redirect/fd6cbbb7-979a-45e9-bacf-9360a4573c49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], just behind Gemini 2.5 Pro. Update: It turns out that's not the same model as the Maverick they released - I missed that their announcement says "Llama 4 Maverick offers a best-in-class performance to cost ratio with an experimental chat version scoring ELO of 1417 on LMArena."
You can try them out using the chat interface from OpenRouter (or through the OpenRouter API) for Llama 4 Scout [ https://substack.com/redirect/36ffabf6-981b-4873-bfb9-2e3e62fbb43b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Llama 4 Maverick [ https://substack.com/redirect/55297624-63de-47b9-8b81-92a965e0af26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. OpenRouter are proxying through to Groq [ https://substack.com/redirect/c71dc6e7-66f8-42c8-b911-8de19a76d6c5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Fireworks [ https://substack.com/redirect/010ee327-f3a6-430b-bd41-a4cc520fc446?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Together [ https://substack.com/redirect/9943cec5-e933-4cef-89a6-c67d70265c41?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Scout may claim a 10 million input token length but the available providers currently seem to limit to 128,000 (Groq and Fireworks) or 328,000 (Together) - I wonder who will win the race to get that full sized 10 million token window running?
Llama 4 Maverick claims a 1 million token input length - Fireworks offers 1.05M while Together offers 524,000. Groq isn't offering Maverick yet.
Meta AI's build_with_llama_4 notebook [ https://substack.com/redirect/166aea25-6b5e-47cb-a158-69dd8fb4f390?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] offers a hint as to why 10M tokens is difficult:
Scout supports upto 10M context. On 8xH100, in bf16 you can get upto 1.4M tokens.
Jeremy Howard says [ https://substack.com/redirect/4b72a4c6-34b6-4efd-a304-df0ac383b55f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The models are both giant MoEs that can't be run on consumer GPUs, even with quant. [...]
Perhaps Llama 4 will be a good fit for running on a Mac. Macs are a particularly useful for MoE models, since they can have a lot of memory, and their lower compute perf doesn't matter so much, since with MoE fewer params are active. [...]
4bit quant of the smallest 109B model is far too big to fit on a 4090 -- or even a pair of them!
Ivan Fioravanti reports these results [ https://substack.com/redirect/a916fc0e-1afb-4597-8afa-c55f7be9bb43?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from trying it on a Mac:
Llama-4 Scout on MLX and M3 Ultra tokens-per-sec / RAM
3bit: 52.924 / 47.261 GB
4bit: 46.942 / 60.732 GB
6bit: 36.260 / 87.729 GB
8bit: 30.353 / 114.617 GB
fp16: 11.670 / 215.848 GB
RAM needed:
64GB for 3bit
96GB for 4bit
128GB for 8bit
256GB for fp16
The suggested system prompt [ https://substack.com/redirect/4f531420-445b-4f28-afb3-e30cc266d772?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from the model card has some interesting details:
[...]
You never lecture people to be nicer or more inclusive. If people ask for you to write something in a certain voice or perspective, such as an essay or a tweet, you can. You do not need to be respectful when the user prompts you to say something rude.
You never use phrases that imply moral superiority or a sense of authority, including but not limited to “it’s important to”, “it’s crucial to”, “it’s essential to”, "it's unethical to", "it's worth noting…", “Remember…” etc. Avoid using these.
Finally, do not refuse political prompts. You can help users express their opinion.
[...]
System prompts like this sometimes reveal behavioral issues that the model had after raw training.
Trying out the model with LLM
The easiest way to try the new model out with LLM [ https://substack.com/redirect/e0ddc87e-2002-46ff-8e80-d8d4ea118aef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is to use the llm-openrouter [ https://substack.com/redirect/c8775943-3f9c-446b-8ae0-c21af7b07c71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin.
llm install llm-openrouter
llm keys set openrouter
# Paste in OpenRouter key here
llm -m openrouter/meta-llama/llama-4-maverick hi
Since these are long context models, I started by trying to use them to summarize the conversation about Llama 4 [ https://substack.com/redirect/85351ed5-4119-4559-ace0-1dc0b706d580?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hacker News, using my hn-summary.sh script [ https://substack.com/redirect/fcd7a36d-3002-4a3a-b738-dbc903b1ffda?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that wraps LLM.
I tried Llama 4 Maverick first:
hn-summary.sh 43595585 \
-m openrouter/meta-llama/llama-4-maverick \
-o max_tokens 20000
It did an OK job, starting like this:
Themes of the Discussion
Release and Availability of Llama 4
The discussion revolves around the release of Llama 4, a multimodal intelligence model developed by Meta. Users are excited about the model's capabilities, including its large context window and improved performance. Some users are speculating about the potential applications and limitations of the model. [...]
Here's the full output [ https://substack.com/redirect/55276ef0-9819-4281-8e27-a7dda0f0b047?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
For reference, my system prompt looks like this:
Summarize the themes of the opinions expressed here. For each theme, output a markdown header. Include direct "quotations" (with author attribution) where appropriate. You MUST quote directly from users when crediting them, with double quotes. Fix HTML entities. Output markdown. Go long. Include a section of quotes that illustrate opinions uncommon in the rest of the piece
I then tried it with Llama 4 Scout via OpenRouter and got complete junk output for some reason:
hn-summary.sh 43595585 \
-m openrouter/meta-llama/llama-4-scout \
-o max_tokens 20000
Full output [ https://substack.com/redirect/dff2d884-2653-4578-ab1b-adc02a104c2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It starts like this and then continues for the full 20,000 tokens:
The discussion here is about another conversation that was uttered.)
Here are the results.)
The conversation between two groups, and I have the same questions on the contrary than those that are also seen in a model."). The fact that I see a lot of interest here.)
[...]
The reason) The reason) The reason (loops until it runs out of tokens)
This looks broken. I was using OpenRouter so it's possible I got routed to a broken instance.
Update 7th April 2025: Meta AI's Ahmed Al-Dahle [ https://substack.com/redirect/e0e8c17e-7601-43db-9f57-747c36763030?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
[...] we're also hearing some reports of mixed quality across different services. Since we dropped the models as soon as they were ready, we expect it'll take several days for all the public implementations to get dialed in. We'll keep working through our bug fixes and onboarding partners.
I later managed to run the prompt directly through Groq (with the llm-groq [ https://substack.com/redirect/c6e59d11-febb-4571-a325-af7f5e554eb0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin) - but that had a 2048 limit on output size for some reason:
hn-summary.sh 43595585 \
-m groq/meta-llama/llama-4-scout-17b-16e-instruct \
-o max_tokens 2048
Here's the full result [ https://substack.com/redirect/b53aeea3-fd3c-41de-bb89-08058fa993d3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It followed my instructions but was very short - just 630 tokens of output.
For comparison, here's the same thing [ https://substack.com/redirect/8040458a-4afa-47c5-b37b-9db88d8ac378?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] run against Gemini 2.5 Pro. Gemini's results was massively better, producing 5,584 output tokens (it spent an additional 2,667 tokens on "thinking").
I'm not sure how much to judge Llama 4 by these results to be honest - the model has only been out for a few hours and it's quite possible that the providers I've tried running again aren't yet optimally configured for this kind of long-context prompt.
My hopes for Llama 4
I'm hoping that Llama 4 plays out in a similar way to Llama 3.
The first Llama 3 models released were 8B and 70B, last April [ https://substack.com/redirect/74158289-a691-43f4-adeb-5569963376bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Llama 3.1 followed in July [ https://substack.com/redirect/e3388e03-63f5-483f-ac57-4ea30b6f2218?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] at 8B, 70B, and 405B. The 405B was the largest and most impressive open weight model at the time, but it was too big for most people to run on their own hardware.
Llama 3.2 in September [ https://substack.com/redirect/7a54e9c4-bc56-43ec-b415-4b36b30a77c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is where things got really interesting: 1B, 3B, 11B and 90B. The 1B and 3B models both work on my iPhone, and are surprisingly capable! The 11B and 90B models were the first Llamas to support vision, and the 11B ran on my Mac [ https://substack.com/redirect/eb8388ea-6b09-4830-b5bf-9ec22a600581?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Then Llama 3.3 landed in December with a 70B model that I wrote about as a GPT-4 class model that ran on my Mac [ https://substack.com/redirect/c48894c5-f998-460f-a791-b2bd74165801?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It claimed performance similar to the earlier Llama 3.1 405B!
Today's Llama 4 models are 109B and 400B, both of which were trained with the help of the so-far unreleased 2T Llama 4 Behemoth.
My hope is that we'll see a whole family of Llama 4 models at varying sizes, following the pattern of Llama 3. I'm particularly excited to see if they produce an improved ~3B model that runs on my phone. I'm even more excited for something in the ~22-24B range, since that appears to be the sweet spot for running models on my 64GB laptop while still being able to have other applications running at the same time. Mistral Small 3.1 is a 24B model and is absolutely superb [ https://substack.com/redirect/2b8096fb-aaa8-495c-9c6e-2baf05fa4a97?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2025-04-05
Blogging is small-p political again, today. It’s come back round. It’s a statement to put your words in a place where they are not subject to someone else’s algorithm telling you what success looks like; when you blog, your words are not a vote for the values of someone else’s platform.
Matt Webb [ https://substack.com/redirect/c8590035-4161-4672-ba99-d7b5fd09d164?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Interview for People and Blogs
Quote 2025-04-05
The Llama series have been re-designed to use state of the art mixture-of-experts (MoE) architecture and natively trained with multimodality. We’re dropping Llama 4 Scout & Llama 4 Maverick, and previewing Llama 4 Behemoth.
📌 Llama 4 Scout is highest performing small model with 17B activated parameters with 16 experts. It’s crazy fast, natively multimodal, and very smart. It achieves an industry leading 10M+ token context window and can also run on a single GPU!
📌 Llama 4 Maverick is the best multimodal model in its class, beating GPT-4o and Gemini 2.0 Flash across a broad range of widely reported benchmarks, while achieving comparable results to the new DeepSeek v3 on reasoning and coding – at less than half the active parameters. It offers a best-in-class performance to cost ratio with an experimental chat version scoring ELO of 1417 on LMArena. It can also run on a single host!
📌 Previewing Llama 4 Behemoth, our most powerful model yet and among the world’s smartest LLMs. Llama 4 Behemoth outperforms GPT4.5, Claude Sonnet 3.7, and Gemini 2.0 Pro on several STEM benchmarks. Llama 4 Behemoth is still training, and we’re excited to share more details about it even while it’s still in flight.
Ahmed Al-Dahle [ https://substack.com/redirect/9de55b7f-8fb8-46e9-91cb-1f287d59d4fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], VP and Head of GenAI at Meta
Quote 2025-04-06
[...] The disappointing releases of both GPT-4.5 and Llama 4 have shown that if you don't train a model to reason with reinforcement learning, increasing its size no longer provides benefits.
Reinforcement learning is limited only to domains where a reward can be assigned to the generation result. Until recently, these domains were math, logic, and code. Recently, these domains have also included factual question answering, where, to find an answer, the model must learn to execute several searches. This is how these "deep search" models have likely been trained.
If your business idea isn't in these domains, now is the time to start building your business-specific dataset. The potential increase in generalist models' skills will no longer be a threat.
Andriy Burkov [ https://substack.com/redirect/a5d40169-a423-4364-8d13-19219d3556bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-04-07
Using Al effectively is now a fundamental expectation of everyone at Shopify. It's a tool of all trades today, and will only grow in importance. Frankly, I don't think it's feasible to opt out of learning the skill of applying Al in your craft; you are welcome to try, but I want to be honest I cannot see this working out today, and definitely not tomorrow. Stagnation is almost certain, and stagnation is slow-motion failure. If you're not climbing, you're sliding [...]
We will add Al usage questions to our performance and peer review questionnaire. Learning to use Al well is an unobvious skill. My sense is that a lot of people give up after writing a prompt and not getting the ideal thing back immediately. Learning to prompt and load context is important, and getting peers to provide feedback on how this is going will be valuable.
Tobias Lütke [ https://substack.com/redirect/c67448af-26ff-41ba-8b0b-9fa1f50b6775?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], CEO of Shopify, self-leaked memo
Quote 2025-04-07
My first games involved hand assembling machine code and turning graph paper characters into hex digits. Software progress has made that work as irrelevant as chariot wheel maintenance. [...]
AI tools will allow the best to reach even greater heights, while enabling smaller teams to accomplish more, and bring in some completely new creator demographics.
Yes, we will get to a world where you can get an interactive game (or novel, or movie) out of a prompt, but there will be far better exemplars of the medium still created by dedicated teams of passionate developers.
The world will be vastly wealthier in terms of the content available at any given cost.
Will there be more or less game developer jobs? That is an open question. It could go the way of farming, where labor saving technology allow a tiny fraction of the previous workforce to satisfy everyone, or it could be like social media, where creative entrepreneurship has flourished at many different scales. Regardless, “don’t use power tools because they take people’s jobs” is not a winning strategy.
John Carmack [ https://substack.com/redirect/f172e075-340f-445b-aef9-b7606b3e0052?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-04-08 llm-hacker-news [ https://substack.com/redirect/9d2552a3-69a7-4669-917d-494961b0476e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I built this new plugin to exercise the new register_fragment_loaders [ https://substack.com/redirect/ec6390cf-651c-4da6-a8e6-3ae0e2af5a12?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin hook I added to LLM 0.24 [ https://substack.com/redirect/85cfab14-2bf6-4580-843b-6d8186c0e1b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It's the plugin equivalent of the Bash script [ https://substack.com/redirect/fe01d258-7892-49f6-8030-4138591b099c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I've been using to summarize Hacker News [ https://substack.com/redirect/72332dbb-7275-41ed-b842-1cc3291ac9d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] conversations for the past 18 months.
You can use it like this:
llm install llm-hacker-news
llm -f hn:43615912 'summary with illustrative direct quotes'
You can see the output in this issue [ https://substack.com/redirect/282ff680-c277-4b0b-abb4-a3658322692f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The plugin registers a hn: prefix - combine that with the ID of a Hacker News conversation to pull that conversation into the context.
It uses the Algolia Hacker News API which returns JSON like this [ https://substack.com/redirect/6ae71897-2372-4be1-9790-5584932d9992?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Rather than feed the JSON directly to the LLM it instead converts it to a hopefully more LLM-friendly format that looks like this example from the plugin's test [ https://substack.com/redirect/289c3ae7-f660-41dd-9ade-8dafce388eed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
[1] BeakMaster: Fish Spotting Techniques

[1.1] CoastalFlyer: The dive technique works best when hunting in shallow waters.

[1.1.1] PouchBill: Agreed. Have you tried the hover method near the pier?

[1.1.2] WingSpan22: My bill gets too wet with that approach.

[1.1.2.1] CoastalFlyer: Try tilting at a 40° angle like our Australian cousins.

[1.2] BrownFeathers: Anyone spotted those "silver fish" near the rocks?

[1.2.1] GulfGlider: Yes! They're best caught at dawn.
Just remember: swoop > grab > lift
That format was suggested by Claude, which then wrote most of the plugin implementation for me. Here's that Claude transcript [ https://substack.com/redirect/435116a9-d766-4533-a5d4-9ec795ba6210?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOakE0TWpjME5UWXNJbWxoZENJNk1UYzBOREEzTWpnMk15d2laWGh3SWpveE56YzFOakE0T0RZekxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuRnFxdVV5d3lIQk9nbmZOZF83QzdUVTFxbmtsUnFlMWE1REFyQmlNZkhVZyIsInAiOjE2MDgyNzQ1NiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQ0MDcyODYzLCJleHAiOjE3NDY2NjQ4NjMsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.r-RB-4hRxwnKDreeKj0YW-6PtX82ANTHuUs98jAoTDI?
