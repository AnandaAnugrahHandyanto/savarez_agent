# NVIDIA DGX Spark: great hardware, early days for the ecosystem

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-10-15T15:40:17.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/nvidia-dgx-spark-great-hardware-early

In this newsletter:
NVIDIA DGX Spark: great hardware, early days for the ecosystem
Claude can write complete Datasette plugins now
Plus 11 links and 2 quotations and 1 TIL and 3 notes
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
NVIDIA DGX Spark: great hardware, early days for the ecosystem [ https://substack.com/redirect/ed771677-18ec-475e-9e66-428aa7c4c7f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-10-14
NVIDIA sent me a preview unit of their new DGX Spark [ https://substack.com/redirect/cc4668e8-1c30-474f-8baa-f3ba359cde8a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] desktop “AI supercomputer”. I’ve never had hardware to review before! You can consider this my first ever sponsored post if you like, but they did not pay me any cash and aside from an embargo date they did not request (nor would I grant) any editorial input into what I write about the device.
The device retails for around $4,000. They officially go on sale tomorrow.
First impressions are that this is a snazzy little computer. It’s similar in size to a Mac mini, but with an exciting textured surface that feels refreshingly different and a little bit science fiction [ https://substack.com/redirect/dd430fd0-29db-4085-a2a0-e7683f124dce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
There is a very powerful machine tucked into that little box. Here are the specs, which I had Claude Code figure out for me by poking around on the device itself [ https://substack.com/redirect/853d9e20-d142-450d-9539-97d079759260?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Hardware Specifications
Architecture: aarch64 (ARM64)
CPU: 20 cores
10x Cortex-X925 (performance cores)
10x Cortex-A725 (efficiency cores)
RAM: 119 GB total (112 GB available) - I’m not sure why Claude reported it differently here, the machine is listed as 128GB - it looks like a 128GB == 119GiB thing [ https://substack.com/redirect/3c672ad1-74ea-4883-93b9-0289ea4630c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] because Claude used free -h [ https://substack.com/redirect/02fcb2cf-0c1b-4da4-9535-c782c53f35db?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Storage: 3.7 TB (6% used, 3.3 TB available)
GPU Specifications
Model: NVIDIA GB10 (Blackwell architecture)
Compute Capability: sm_121 (12.1)
Memory: 119.68 GB
Multi-processor Count: 48 streaming multiprocessors
Architecture: Blackwell
Short version: this is an ARM64 device with 128GB of memory that’s available to both the GPU and the 20 CPU cores at the same time, strapped onto a 4TB NVMe SSD.
The Spark is firmly targeted at “AI researchers”. It’s designed for both training and running models.
The tricky bit: CUDA on ARM64
Until now almost all of my own model running experiments have taken place on a Mac. This has gotten far less painful over the past year and a half thanks to the amazing work of the MLX [ https://substack.com/redirect/f31bf87c-39cd-4165-ad6c-259652c6fe88?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] team and community, but it’s still left me deeply frustrated at my lack of access to the NVIDIA CUDA ecosystem. I’ve lost count of the number of libraries and tutorials which expect you to be able to use Hugging Face Transformers or PyTorch with CUDA, and leave you high and dry if you don’t have an NVIDIA GPU to run things on.
Armed (ha) with my new NVIDIA GPU I was excited to dive into this world that had long eluded me... only to find that there was another assumption baked in to much of this software: x86 architecture for the rest of the machine.
This resulted in all kinds of unexpected new traps for me to navigate. I eventually managed to get a PyTorch 2.7 wheel for CUDA on ARM, but failed to do so for 2.8. I’m not confident there because the wheel itself is unavailable but I’m finding navigating the PyTorch ARM ecosystem pretty confusing.
NVIDIA are trying to make this easier, with mixed success. A lot of my initial challenges got easier when I found their official Docker container [ https://substack.com/redirect/23921fa1-caf5-4370-b78d-ecea5b152094?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], so now I’m figuring out how best to use Docker with GPUs. Here’s the current incantation that’s been working for me:
docker run -it --gpus=all \
-v /usr/local/cuda:/usr/local/cuda:ro \
nvcr.io/nvidia/cuda:13.0.1-devel-ubuntu24.04 \
bash
I have not yet got my head around the difference between CUDA 12 and 13. 13 appears to be very new, and a lot of the existing tutorials and libraries appear to expect 12.
The missing documentation isn’t missing any more
When I first received this machine around a month ago there was very little in the way of documentation to help get me started. This meant climbing the steep NVIDIA+CUDA learning curve mostly on my own.
This has changed substantially in just the last week. NVIDIA now have extensive guides for getting things working on the Spark and they are a huge breath of fresh air - exactly the information I needed when I started exploring this hardware.
Here’s the getting started guide [ https://substack.com/redirect/adca3e41-586d-485a-bc06-bf0f2c2ac050?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], details on the DGX dashboard web app [ https://substack.com/redirect/43233aae-67e1-49f9-82e4-8a291d875985?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and the essential collection of playbooks [ https://substack.com/redirect/0a1560b4-c6e4-4cb6-ba60-5ec041145b98?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. There’s still a lot I haven’t tried yet just in this official set of guides.
Claude Code for everything
Claude Code [ https://substack.com/redirect/8b73591d-b6f0-49df-9126-29418530eb05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was an absolute lifesaver for me while I was trying to figure out how best to use this device. My Ubuntu skills were a little rusty, and I also needed to figure out CUDA drivers and Docker incantations and how to install the right versions of PyTorch. Claude 4.5 Sonnet is much better than me at all of these things.
Since many of my experiments took place in disposable Docker containers I had no qualms at all about running it in YOLO mode:
IS_SANDBOX=1 claude --dangerously-skip-permissions
The IS_SANDBOX=1 environment variable stops Claude from complaining about running as root.
This will provide a URL which you can visit to authenticate with your Anthropic account, confirming by copying back a token and pasting it into the terminal.
Docker tip: you can create a snapshot of the current image (with Claude installed) by running docker ps to get the container ID and then:
docker commit --pause=false  cc:snapshot
Then later you can start a similar container using:
docker run -it \
--gpus=all \
-v /usr/local/cuda:/usr/local/cuda:ro \
cc:snapshot bash
Here’s an example of the kinds of prompts I’ve been running in Claude Code inside the container:
I want to run https://huggingface.co/unsloth/Qwen3-4B-GGUF using llama.cpp - figure out how to get llama cpp working on this machine such that it runs with the GPU, then install it in this directory and get that model to work to serve a prompt. Goal is to get this command to run: llama-cli -hf unsloth/Qwen3-4B-GGUF -p “I believe the meaning of life is” -n 128 -no-cnv
That one worked flawlessly - Claude checked out the llama.cpp repo, compiled it for me and iterated on it until it could run that model on the GPU. Here’s a full transcript [ https://substack.com/redirect/1d1b970a-e755-4eef-aeb8-b30a9eeae33c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], converted from Claude’s .jsonl log format to Markdown using a script I vibe coded just now [ https://substack.com/redirect/4a794f63-c27a-4493-a82e-b6c4d1f63af5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I later told it:
Write out a markdown file with detailed notes on what you did. Start with the shortest form of notes on how to get a successful build, then add a full account of everything you tried, what went wrong and how you fixed it.
Which produced this handy set of notes [ https://substack.com/redirect/bfba858f-2ad8-4fdb-9e9b-f45d19c81d70?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Tailscale was made for this
Having a machine like this on my local network is neat, but what’s even neater is being able to access it from anywhere else in the world, from both my phone and my laptop.
Tailscale [ https://substack.com/redirect/ee9633c9-fefc-4a89-8ef1-9c837e832c49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is perfect for this. I installed it on the Spark (using the Ubuntu instructions here [ https://substack.com/redirect/e3aa61a0-d210-4f2c-a092-5e56274b5cd7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), signed in with my SSO account (via Google)... and the Spark showed up in the “Network Devices” panel on my laptop and phone instantly.
I can SSH in from my laptop or using the Termius iPhone app [ https://substack.com/redirect/eaa987f1-f51b-485d-8a67-12e1cfde76bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on my phone. I’ve also been running tools like Open WebUI [ https://substack.com/redirect/ac132e12-cb50-45ec-9cdd-b0f1ee3d59e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which give me a mobile-friendly web interface for interacting with LLMs on the Spark.
Here comes the ecosystem
The embargo on these devices dropped yesterday afternoon, and it turns out a whole bunch of relevant projects have had similar preview access to myself. This is fantastic news as many of the things I’ve been trying to figure out myself suddenly got a whole lot easier.
Four particularly notable examples:
Ollama works out of the box [ https://substack.com/redirect/d96b28df-5169-4695-9740-79252d23f267?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. They actually had a build that worked a few weeks ago, and were the first success I had running an LLM on the machine.
llama.cpp creator Georgi Gerganov just published extensive benchmark results [ https://substack.com/redirect/a7e43d13-c1fc-40a8-885b-a7ea3abc8add?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from running llama.cpp on a Spark. He’s getting ~3,600 tokens/second to read the prompt and ~59 tokens/second to generate a response with the MXFP4 version of GPT-OSS 20B and ~817 tokens/second to read and ~18 tokens/second to generate for GLM-4.5-Air-GGUF.
LM Studio now have a build for the Spark [ https://substack.com/redirect/451e8bd5-e045-4458-b93c-cb961b4f1275?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I haven’t tried this one yet as I’m currently using my machine exclusively via SSH.
vLLM - one of the most popular engines for serving production LLMs - had early access [ https://substack.com/redirect/a9292839-ccf6-48e6-8648-9fc70a80a61c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and there’s now an official NVIDIA vLLM NGC Container [ https://substack.com/redirect/ccb62f50-c2e3-4f43-8993-b367d03c51fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for running their stack.
Should you get one?
It’s a bit too early for me to provide a confident recommendation concerning this machine. As indicated above, I’ve had a tough time figuring out how best to put it to use, largely through my own inexperience with CUDA, ARM64 and Ubuntu GPU machines in general.
The ecosystem improvements in just the past 24 hours have been very reassuring though. I expect it will be clear within a few weeks how well supported this machine is going to be.
Claude can write complete Datasette plugins now [ https://substack.com/redirect/645792b2-2b9f-4f1b-a7bd-7c58adc1844e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-10-08
This isn’t necessarily surprising, but it’s worth noting anyway. Claude Sonnet 4.5 is capable of building a full Datasette plugin now.
I’ve seen models complete aspects of this in the past, but today is the first time I’ve shipped a new plugin where every line of code and test was written by Claude, with minimal prompting from myself.
The plugin is called datasette-os-info [ https://substack.com/redirect/198cfcff-926e-4ed1-804c-f1faf6b6b5fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It’s a simple debugging tool - all it does is add a /-/os JSON page which dumps out as much information as it can about the OS it’s running on. Here’s a live demo [ https://substack.com/redirect/7ffdd66e-e361-4928-b4bb-4300c91799a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on my TIL website.
I built it to help experiment with changing the Docker base container that Datasette uses to publish images [ https://substack.com/redirect/44b25494-c253-401e-943f-7bc169421015?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to one that uses Python 3.14.
Here’s the full set of commands I used to create the plugin. I started with my datasette-plugin [ https://substack.com/redirect/dd3ab91a-b8e4-429a-9c42-b3f682142152?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] cookiecutter template:
uvx cookiecutter gh:simonw/datasette-plugin

[1/8] plugin_name (): os-info
[2/8] description (): Information about the current OS
[3/8] hyphenated (os-info):
[4/8] underscored (os_info):
[5/8] github_username (): datasette
[6/8] author_name (): Simon Willison
[7/8] include_static_directory ():
[8/8] include_templates_directory ():
This created a datasette-os-info directory with the initial pyproject.toml and tests/ and datasette_os_info/__init__.py files. Here’s an example of that starter template [ https://substack.com/redirect/bf722a9b-469c-4818-a21a-4ceedff7c55e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I created a uv virtual environment for it, installed the initial test dependencies and ran pytest to check that worked:
cd datasette-os-info
uv venv
uv sync --extra test
uv run pytest
Then I fired up Claude Code [ https://substack.com/redirect/8b73591d-b6f0-49df-9126-29418530eb05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in that directory in YOLO mode:
claude --dangerously-skip-permissions
(I actually used my claude-yolo shortcut which runs the above.)
Then, in Claude, I told it how to run the tests:
Run uv run pytest
When that worked, I told it to build the plugin:
This is a Datasette plugin which should add a new page /-/os which returns pretty-printed JSON about the current operating system - implement it. I want to pick up as many details as possible across as many OS as possible, including if possible figuring out the base image if it is in a docker container - otherwise the Debian OS release name and suchlike would be good
... and that was it! Claude implemented the plugin [ https://substack.com/redirect/75a7ecab-98d3-4a92-8b82-f3b87461675e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using Datasette’s register_routes() plugin hook [ https://substack.com/redirect/f233dff0-3a19-4544-b93e-80c56b7af432?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to add the /-/os page,and then without me prompting it to do so built this basic test as well [ https://substack.com/redirect/2c30779c-3f01-4fa6-b89c-e73e38ddfd9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It ran the new test, spotted a bug (it had guessed a non-existent Response(..., default_repr=) parameter), fixed the bug and declared itself done.
I built myself a wheel:
uv pip install build
uv run python -m build
Then uploaded that to an S3 bucket and deployed it to test it out using datasette publish ... --install URL-to-wheel. It did exactly what I had hoped - here’s what that /-/os page looked like:
{
“platform”: {
“system”: “Linux”,
“release”: “4.4.0”,
“version”: “#1 SMP Sun Jan 10 15:06:54 PST 2016”,
“machine”: “x86_64”,
“processor”: “”,
“architecture”: [
“64bit”,
“”
],
“platform”: “Linux-4.4.0-x86_64-with-glibc2.41”,
“python_version”: “3.14.0”,
“python_implementation”: “CPython”
},
“hostname”: “localhost”,
“cpu_count”: 2,
“linux”: {
“os_release”: {
“PRETTY_NAME”: “Debian GNU/Linux 13 (trixie)”,
“NAME”: “Debian GNU/Linux”,
“VERSION_ID”: “13”,
“VERSION”: “13 (trixie)”,
“VERSION_CODENAME”: “trixie”,
“DEBIAN_VERSION_FULL”: “13.1”,
“ID”: “debian”,
“HOME_URL”: “https://www.debian.org/”,
“SUPPORT_URL”: “https://www.debian.org/support”,
“BUG_REPORT_URL”: “https://bugs.debian.org/”
},
“debian_version”: “13.1”,
“kernel”: {
“sysname”: “Linux”,
“nodename”: “localhost”,
“release”: “4.4.0”,
“version”: “#1 SMP Sun Jan 10 15:06:54 PST 2016”,
“machine”: “x86_64”
},
“cpu_model”: “unknown”,
“memory”: {
“MemTotal”: “1048576 kB”,
“MemFree”: “958244 kB”,
“MemAvailable”: “958244 kB”,
“SwapTotal”: “0 kB”,
“SwapFree”: “0 kB”
}
},
“environment”: {
“HOME”: “/root”,
“PATH”: “/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin”
},
“python_executable”: “/usr/local/bin/python3.14”
}
I dread to think how long it would have taken me to figure out all of those different useful OS details!
To finish up, I had Claude fill out the README via a couple of extra prompts:
Add usage instructions to the README (about the /-/os page)
Then had a brief conversation about how safe the output was:
Is there anything potentially sensitive in that output?
Claude said:
Yes, there are several potentially sensitive items in the output:
Most sensitive:
hostname - Could reveal internal naming schemes or organization details
Environment variables:
HOME - Reveals user’s home directory path
USER - Reveals the username
PATH - Reveals filesystem structure and software installation locations
VIRTUAL_ENV - Could reveal project paths and directory structure
python_executable - Reveals filesystem paths and user directories
Moderately sensitive:
CPU count and memory info - Could reveal infrastructure capacity
Kernel version details - Could potentially be used to identify specific vulnerabilities
Considerations:
This endpoint is accessible without authentication by default (at /-/os)
If you’re running Datasette on a public server, this information would be visible to anyone
The information could help attackers understand your infrastructure setup
Suggestions:
You might want to:
Add authentication requirements to this endpoint
Make certain fields optional/configurable
Add a warning in the README that this exposes system information
Consider filtering out or redacting sensitive paths (replace usernames with ***, etc.)
Would you like me to add any of these protections to the plugin?
In this case I’m fine with the current behavior provided people understand the risks, so I told it:
Add the warning to the README
And then (because the warning it added was quite long):
Drop the bit about configuring the permission system, just have a short warning telling people to review what it exposes
And requested an extra README note:
Add a note that you can also see the output by running: datasette --get /-/os
Three last prompts:
Add uv.lock to gitignore
Drop Python 3.9 and add Python 3.14 - to the GitHub workflows, also min version in pyproject.toml
Bump to setup-python@v6
... and that was the project finished. I pushed it to GitHub [ https://substack.com/redirect/198cfcff-926e-4ed1-804c-f1faf6b6b5fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], configured Trusted Publishing [ https://substack.com/redirect/3da8d57a-98e9-4661-a105-ac55236b9821?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for it on PyPI and posted the 0.1 release [ https://substack.com/redirect/14fc9556-b191-4654-b0da-1700ec2599ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which ran this GitHub Actions publish.yml [ https://substack.com/redirect/37c11472-c405-4faa-876e-31cf8390381c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and deployed that release to datasette-os-info on PyPI [ https://substack.com/redirect/abe7df05-070d-4d29-a81f-8d2acf714417?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Now that it’s live you can try it out without even installing Datasette using a uv one-liner like this:
uv run --isolated \
--with datasette-os-info \
datasette --get /-/os
That’s using the --get PATH CLI option to show what that path in the Datasette instance would return, as described in the Datasette documentation [ https://substack.com/redirect/27c82be3-f9ae-4017-a523-e356649e06c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I’ve shared my full Claude Code transcript [ https://substack.com/redirect/79874795-ffa1-4dc8-909e-0e66e0a86815?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in a Gist.
A year ago I’d have been very impressed by this. Today I wasn’t even particularly surprised that this worked - the coding agent pattern implemented by Claude Code is spectacularly effective when you combine it with pre-existing templates, and Datasette has been aroung for long enough now that plenty of examples of plugins have made it into the training data for the leading models.
Note 2025-10-07 [ https://substack.com/redirect/5d41756c-1f02-4cd4-b02c-ef41dc771fa5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Google released a new Gemini 2.5 Computer Use model [ https://substack.com/redirect/451425fc-fd6c-4e4b-905b-b7b0f16eea92?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today, specially designed to help operate a GUI interface by interacting with visible elements using a virtual mouse and keyboard.
I tried the demo hosted by Browserbase at gemini.browserbase.com [ https://substack.com/redirect/cce6553c-b851-4ff0-a0e1-0c36b70addef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and was delighted and slightly horrified when it appeared to kick things off by first navigating to Google.com and solving their CAPTCHA in order to run a search!
I wrote a post about it and included this screenshot [ https://substack.com/redirect/8b944040-03ee-49a4-8af6-14d2c4615736?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but then learned that Browserbase itself has CAPTCHA solving built in and, as shown in this longer video [ https://substack.com/redirect/01eaef96-09ca-49ba-ac05-1d5d9352c723?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], it was Browserbase that solved the CAPTCHA even while Gemini was thinking about doing so itself.
I deeply regret this error. I’ve deleted various social media posts about the original entry and linked back to this retraction instead.
Link 2025-10-08 Why NetNewsWire Is Not a Web App [ https://substack.com/redirect/a72cfd8a-f50c-4bb5-a9ec-7d1ef9dfb779?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
In the wake of Apple removing ICEBlock from the App Store [ https://substack.com/redirect/7d362aa6-2493-4370-811c-45d8276366df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Brent Simmons talks about why he still thinks his veteran (and actively maintained) NetNewsWire [ https://substack.com/redirect/ddae3cef-6294-4c50-9379-143e7ef9b8c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] feed reader app should remain a native application.
Part of the reason is cost - NetNewsWire is free these days (MIT licensed in fact [ https://substack.com/redirect/5a927c00-5305-4a32-a7a0-30b1f0d2cb71?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and the cost to Brent is an annual Apple developer subscription:
If it were a web app instead, I could drop the developer membership, but I’d have to pay way more money for web and database hosting. [...] I could charge for NetNewsWire, but that would go against my political goal of making sure there’s a good and free RSS reader available to everyone.
A bigger reason is around privacy and protecting users:
Second issue. Right now, if law enforcement comes to me and demands I turn over a given user’s subscriptions list, I can’t. Literally can’t. I don’t have an encrypted version, even — I have nothing at all. The list lives on their machine (iOS or macOS).
And finally it’s about the principle of what a personal computing device should mean:
My computer is not a terminal. It’s a world I get to control, and I can use — and, especially, make — whatever I want. I’m not stuck using just what’s provided to me on some other machines elsewhere: I’m not dialing into a mainframe or doing the modern equivalent of using only websites that other people control.
quote 2025-10-08
The cognitive debt of LLM-laden coding extends beyond disengagement of our craft. We’ve all heard the stories. Hyped up, vibed up, slop-jockeys with attention spans shorter than the framework-hopping JavaScript devs of the early 2010s, sling their sludge in pull requests and design docs, discouraging collaboration and disrupting teams. Code reviewing coworkers are rapidly losing their minds as they come to the crushing realization that they are now the first layer of quality control instead of one of the last. Asked to review; forced to pick apart. Calling out freshly added functions that are never called, hallucinated library additions, and obvious runtime or compilation errors. All while the author—who clearly only skimmed their “own” code—is taking no responsibility, going “whoopsie, Claude wrote that. Silly AI, ha-ha.”
Simon Højberg [ https://substack.com/redirect/78627b81-a414-4414-9120-3a4a02975189?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], The Programmer Identity Crisis
Link 2025-10-08 Python 3.14 Is Here. How Fast Is It? [ https://substack.com/redirect/0e86e2fd-0ac5-4743-9877-1e9437e3d99c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Miguel Grinberg uses some basic benchmarks (like fib(40)) to test the new Python 3.14 on Linux and macOS and finds some substantial speedups over Python 3.13 - around 27% faster.
The optional JIT didn’t make a meaningful difference to his benchmarks. On a threaded benchmark he got 3.09x speedup with 4 threads using the free threading build - for Python 3.13 the free threading build only provided a 2.2x improvement.
Link 2025-10-09 TIL: Testing different Python versions with uv with-editable and uv-test [ https://substack.com/redirect/443ab459-1da4-44b7-8f2c-74627414f886?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
While tinkering with upgrading various projects to handle Python 3.14 I finally figured out a universal uv recipe for running the tests for the current project in any specified version of Python:
uv run --python 3.14 --isolated --with-editable ‘.[test]’ pytest
This should work in any directory with a pyproject.toml (or even a setup.py) that defines a test set of extra dependencies and uses pytest.
The --with-editable ‘.[test]’ bit ensures that changes you make to that directory will be picked up by future test runs. The --isolated flag ensures no other environments will affect your test run.
I like this pattern so much I built a little shell script that uses it, shown here [ https://substack.com/redirect/7656598e-2bed-4988-bf83-d3ccd0d8e117?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Now I can change to any Python project directory and run:
uv-test
Or for a different Python version:
uv-test -p 3.11
I can pass additional pytest options too:
uv-test -p 3.11 -k permissions
quote 2025-10-09
I get a feeling that working with multiple AI agents is something that comes VERY natural to most senior+ engineers or tech lead who worked at a large company
You already got used to overseeing parallel work (the goto code reviewer!) + making progress with small chunks of work... because your day has been a series of nonstop interactions, so you had to figure out how to do deep work in small chunks that could have been interrupted
Gergely Orosz [ https://substack.com/redirect/f75c4be5-7fa5-4e9f-aa67-8bcc0a38bc99?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-10-10 Video of GPT-OSS 20B running on a phone [ https://substack.com/redirect/a00dcbc3-6eca-4b29-b2bc-d200260c6b70?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
GPT-OSS 20B is a very good model [ https://substack.com/redirect/b2a77bcc-5cab-4964-a2e2-74885daf6a7e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. At launch OpenAI claimed:
The gpt-oss-20b model delivers similar results to OpenAI o3‑mini on common benchmarks and can run on edge devices with just 16 GB of memory
Nexa AI [ https://substack.com/redirect/4d54dd9d-7bcf-4279-adff-c6a1dfe25d18?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] just posted a video on Twitter demonstrating exactly that: the full GPT-OSS 20B running on a Snapdragon Gen 5 phone in their Nexa Studio [ https://substack.com/redirect/cf9094b0-c330-4a93-8552-d8306aadc809?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Android app. It requires at least 16GB of RAM, and benefits from Snapdragon using a similar trick to Apple Silicon where the system RAM is available to both the CPU and the GPU.
The latest iPhone 17 Pro Max is still stuck at 12GB of RAM, presumably not enough to run this same model.
Link 2025-10-10 A Retrospective Survey of 2024/2025 Open Source Supply Chain Compromises [ https://substack.com/redirect/b7a4066c-6daa-4b61-ae40-249d2e0d4e7e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Filippo Valsorda surveyed 18 incidents from the past year of open source supply chain attacks, where package updates were infected with malware thanks to a compromise of the project itself.
These are important lessons:
I have the growing impression that software supply chain compromises have a few predominant causes which we might have a responsibility as a professional open source maintainers to robustly mitigate.
To test this impression and figure out any such mitigations, I collected all 2024/2025 open source supply chain compromises I could find, and categorized their root cause.
This is a fascinating piece of research. 5 were the result of phishing (maintainers should use passkeys/WebAuthn!), ~5 were stolen long-lived credentials, 3 were “control handoff” where a maintainer gave project access to someone who later turned out to be untrustworthy, 4 were caused by GitHub Actions workflows that triggered on pull requests or issue comments in a way that could leak credentials, and one (MavenGate [ https://substack.com/redirect/8abde391-cf66-4255-b299-4f09bdd19ead?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) was caused by an expired domain [ https://substack.com/redirect/5a165ae6-421e-437d-84e2-0718abe2f221?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] being resurrected.
Link 2025-10-10 Superpowers: How I’m using coding agents in October 2025 [ https://substack.com/redirect/fb09b8f6-fe63-42b9-bb3d-91da452cf894?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
A follow-up to Jesse Vincent’s post about September [ https://substack.com/redirect/6e48ef80-c104-4d96-b38c-4866bd9e6470?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], but this is a really significant piece in its own right.
Jesse is one of the most creative users of coding agents (Claude Code in particular) that I know. He’s put a great amount of work into evolving an effective process for working with them, encourage red/green TDD (watch the test fail first), planning steps, self-updating memory notes and even implementing a feelings journal [ https://substack.com/redirect/4092642c-8a34-42c0-9ed8-2ddd0ef1b08c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (”I feel engaged and curious about this project” - Claude).
Claude Code just launched plugins [ https://substack.com/redirect/06f7fce1-f025-43e6-979a-dbf687b89452?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and Jesse is celebrating by wrapping up a whole host of his accumulated tricks as a new plugin called Superpowers [ https://substack.com/redirect/b3120563-3b66-4b9a-ba3d-b9f0a76270d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can add it to your Claude Code like this:
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
There’s a lot in here! It’s worth spending some time browsing the repository [ https://substack.com/redirect/b3120563-3b66-4b9a-ba3d-b9f0a76270d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - here’s just one fun example, in skills/debugging/root-cause-tracing/SKILL.md [ https://substack.com/redirect/8ddd2bd5-34d6-472a-be2e-1446566170e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
---
name: Root Cause Tracing
description: Systematically trace bugs backward through call stack to find original trigger
when_to_use: Bug appears deep in call stack but you need to find where it originates
version: 1.0.0
languages: all
---
Overview
Bugs often manifest deep in the call stack (git init in wrong directory, file created in wrong location, database opened with wrong path). Your instinct is to fix where the error appears, but that’s treating a symptom.
Core principle: Trace backward through the call chain until you find the original trigger, then fix at the source.
When to Use
digraph when_to_use {
“Bug appears deep in stack?” [shape=diamond];
“Can trace backwards?” [shape=diamond];
“Fix at symptom point” [shape=box];
“Trace to original trigger” [shape=box];
“BETTER: Also add defense-in-depth” [shape=box];

“Bug appears deep in stack?” -> “Can trace backwards?” [label=”yes”];
“Can trace backwards?” -> “Trace to original trigger” [label=”yes”];
“Can trace backwards?” -> “Fix at symptom point” [label=”no - dead end”];
“Trace to original trigger” -> “BETTER: Also add defense-in-depth”;
}
[...]
This one is particularly fun because it then includes a Graphviz DOT graph [ https://substack.com/redirect/af641620-7355-45be-b102-7b67ddbbe0b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) illustrating the process - it turns out Claude can interpret those as workflow instructions just fine, and Jesse has been wildly experimenting with them [ https://substack.com/redirect/48954ba4-8600-4069-8cba-41b7efc56dc4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I vibe-coded up [ https://substack.com/redirect/47eeb332-dd14-41ac-b339-e242e58da5d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a quick URL-based DOT visualizer, here’s that one rendered [ https://substack.com/redirect/534d89e7-6a72-4e25-bd0d-350bc90ae263?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
There is so much to learn about putting these tools to work in the most effective way possible. Jesse is way ahead of the curve, so it’s absolutely worth spending some time exploring what he’s shared so far.
And if you’re worried about filling up your context with a bunch of extra stuff, here’s a reassuring note from Jesse [ https://substack.com/redirect/03ec9b23-fa3c-4ce0-afd9-ed444efeb771?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The core of it is VERY token light. It pulls in one doc of fewer than 2k tokens. As it needs bits of the process, it runs a shell script to search for them. The long end to end chat for the planning and implementation process for that todo list app was 100k tokens.
It uses subagents to manage token-heavy stuff, including all the actual implementation.
(Jesse’s post also tipped me off about Claude’s /mnt/skills/public folder, see my notes here [ https://substack.com/redirect/986bb172-491b-44df-8771-a74535c0c947?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].)
Link 2025-10-10 simonw/claude-skills [ https://substack.com/redirect/c074fb21-a3fb-4bf2-94fe-d21c833d96ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
One of the tips I picked up from Jesse Vincent’s Claude Code Superpowers post [ https://substack.com/redirect/fb09b8f6-fe63-42b9-bb3d-91da452cf894?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (previously [ https://substack.com/redirect/bba909ac-cd1f-43c4-8b67-ca717be0d7c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) was this:
Skills are what give your agents Superpowers.
The first time they really popped up on my radar was a few weeks ago when Anthropic rolled out improved Office document creation. When the feature rolled out, I went poking around a bit -- I asked Claude to tell me all about its new skills. And it was only too happy to dish [ https://substack.com/redirect/f393fcd7-b003-4f7d-8153-17fa827769d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
In that transcript Jesse asks how the skill system works and Claude replies:
Looking at the skills system, here’s how it works:
Current Skills (in /mnt/skills/public/):
docx - Word document handling
pdf - PDF processing and form filling
pptx - PowerPoint presentations
xlsx - Excel spreadsheets
This looks like it’s part of Claude’s brand new Code Interpreter feature! I wrote about that extensively [ https://substack.com/redirect/a3272c74-c14f-4c31-a49e-86be9653e68d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] last month, but I missed that there was a /mnt/skills/public/ folder full of fascinating implementation details.
So I fired up a fresh Claude instance (fun fact: Code Interpreter also works in the Claude iOS app now, which it didn’t when they first launched) and prompted:
Create a zip file of everything in your /mnt/skills folder
This worked, and gave me a .zip to download. You can run the prompt yourself here [ https://substack.com/redirect/7ccdc50e-8a5e-4ea7-909f-12caf5fb80aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], though you’ll need to enable the new feature first [ https://substack.com/redirect/a78fbbfe-b943-4fd7-9b03-5f195814a401?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I’ve pushed the contents of that zip to my new simonw/claude-skills GitHub repo [ https://substack.com/redirect/c074fb21-a3fb-4bf2-94fe-d21c833d96ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
So now you can see the prompts Anthropic wrote to enable the creation and manipulation of the following files in their Claude consumer applications:
pdf [ https://substack.com/redirect/932456ce-dd19-43de-9db8-1ed1b472b960?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - PDF files
docx [ https://substack.com/redirect/a91b8e32-e5e0-4e5f-978e-52dbaabd55eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Microsoft Word
pptx [ https://substack.com/redirect/557a91ac-5409-4b1b-bdeb-db2e982619ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Microsoft PowerPoint decks
xlsx [ https://substack.com/redirect/5474acbb-7d79-427d-84aa-2388491d7af6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Microsoft Excel
In each case the prompts spell out detailed instructions for manipulating those file types using Python, using libraries that come pre-installed on Claude’s containers.
Skills are more than just prompts though: the repository also includes dozens of pre-written Python scripts for performing common operations.
pdf/scripts/fill_fillable_fields.py [ https://substack.com/redirect/6c16eaea-9640-4f19-bfcb-ec4e4ee8f8e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for example is a custom CLI tool that uses pypdf [ https://substack.com/redirect/eb2a387a-d242-49ae-8f34-ec2e6da9d1e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to find and then fill in a bunch of PDF form fields, specified as JSON, then render out the resulting combined PDF.
This is a really sophisticated set of tools for document manipulation, and I love that Anthropic have made those visible - presumably deliberately - to users of Claude who know how to ask for them.
Link 2025-10-11 An MVCC-like columnar table on S3 with constant-time deletes [ https://substack.com/redirect/5284e2d8-2361-46a6-85ea-3b39e6ab4a38?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
s3’s support for conditional writes (previously [ https://substack.com/redirect/9bbda4e0-6c0e-470b-bf46-388d22ef6058?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) makes it an interesting, scalable and often inexpensive platform for all kinds of database patterns.
Shayon Mukherjee presents an ingenious design for a Parquet-backed database in S3 which accepts concurrent writes, presents a single atomic view for readers and even supports reliable row deletion despite Parquet requiring a complete file rewrite in order to remove data.
The key to the design is a _latest_manifest JSON file at the top of the bucket, containing an integer version number. Clients use compare-and-swap to increment that version - only one client can succeed at this, so the incremented version they get back is guaranteed unique to them.
Having reserved a version number the client can write a unique manifest file for that version - manifest/v00000123.json - with a more complex data structure referencing the current versions of every persisted file, including the one they just uploaded.
Deleted rows are written to tombstone files as either a list of primary keys or a list of of ranges. Clients consult these when executing reads, filtering out deleted rows as part of resolving a query.
The pricing estimates are especially noteworthy:
For a workload ingesting 6 TB/day with 2 TB of deletes and 50K queries/day:
PUT requests: ~380K/day (≈4 req/s) = $1.88/day
GET requests: highly variable, depends on partitioning effectiveness
Best case (good time-based partitioning): ~100K-200K/day = $0.04-$0.08/day
Worst case (poor partitioning, scanning many files): ~2M/day = $0.80/day
~$3/day for ingesting 6TB of data is pretty fantastic!
Watch out for storage costs though - each new TB of data at $0.023/GB/month adds $23.55 to the ongoing monthly bill.
Note 2025-10-11 [ https://substack.com/redirect/05dc4047-7bf1-45f0-b6f7-5f5099bd527f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I’m beginning to suspect that a key skill in working effectively with coding agents is developing an intuition for when you don’t need to closely review every line of code they produce. This feels deeply uncomfortable!
Link 2025-10-11 Vibing a Non-Trivial Ghostty Feature [ https://substack.com/redirect/19cb9153-c422-4580-9fca-ba566b7f46b9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Mitchell Hashimoto provides a comprehensive answer to the frequent demand for a detailed description of shipping a non-trivial production feature to an existing project using AI-assistance. In this case it’s a slick unobtrusive auto-update UI for his Ghostty [ https://substack.com/redirect/f050af91-902d-43b4-814f-8bd47aef9ce8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] terminal emulator, written in Swift.
Mitchell shares full transcripts of the 16 coding sessions he carried out using Amp Code [ https://substack.com/redirect/0a82f984-7399-47e0-9f93-e9632bc61ef7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] across 2 days and around 8 hours of computer time, at a token cost of $15.98.
Amp has the nicest shared transcript feature of any of the coding agent tools, as seen in this example [ https://substack.com/redirect/66a3d9e1-9228-4b72-9c5e-26cf3b6f3c72?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I’d love to see Claude Code and Codex CLI and Gemini CLI and friends imitate this.
There are plenty of useful tips in here. I like this note about the importance of a cleanup step:
The cleanup step is really important. To cleanup effectively you have to have a pretty good understanding of the code, so this forces me to not blindly accept AI-written code. Subsequently, better organized and documented code helps future agentic sessions perform better.
I sometimes tongue-in-cheek refer to this as the “anti-slop session”.
And this on how sometimes you can write manual code in a way that puts the agent the right track:
I spent some time manually restructured the view model. This involved switching to a tagged union rather than the struct with a bunch of optionals. I renamed some types, moved stuff around.
I knew from experience that this small bit of manual work in the middle would set the agents up for success in future sessions for both the frontend and backend. After completing it, I continued with a marathon set of cleanup sessions.
Here’s one of those refactoring prompts:
Turn each @macos/Sources/Features/Update/UpdatePopoverView.swift case into a dedicated fileprivate Swift view that takes the typed value as its parameter so that we can remove the guards.
Mitchell advises ending every session with a prompt like this one, asking the agent about any obvious omissions:
Are there any other improvements you can see to be made with the @macos/Sources/Features/Update feature? Don’t write any code. Consult the oracle. Consider parts of the code that can also get more unit tests added.
(”Consult the oracle” is an Amp-specific pattern for running a task through a more expensive, more capable model.)
Is this all worthwhile? Mitchell thinks so:
Many people on the internet argue whether AI enables you to work faster or not. In this case, I think I shipped this faster than I would have if I had done it all myself, in particular because iterating on minor SwiftUI styling is so tedious and time consuming for me personally and AI does it so well.
I think the faster/slower argument for me personally is missing the thing I like the most: the AI can work for me while I step away to do other things.
Here’s the resulting PR [ https://substack.com/redirect/f701cebe-f35f-47d0-a3dd-3080c6392eb2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which touches 21 files.
Note 2025-10-11 [ https://substack.com/redirect/4abe6545-34a8-4ed4-a633-ede0a1eabe75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Claude Code includes the ability to run sub-agents, where a separate agent loop with a fresh token context is dispatched to achieve a goal and report back when it’s done. I wrote a bit about how these work in June [ https://substack.com/redirect/bebe402b-3da2-4e83-91ec-95d19b136f38?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] when I traced Claude Code’s activity by intercepting its API calls.
I recently learned that you can deliberately trigger Claude Code to use sub-agents just by telling it to do so!
Here’s an example. I ran this using Claude Code against a fresh checkout of simonw/datasette [ https://substack.com/redirect/37c42e38-c45e-47b8-ac2f-b3e0471d56c9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (commit ec38ad37689f3c14d307770977a17aed5efc5cb9), with no additional custom instructions:
Write markdown documentation for the context passed to each of the templates in this project. Use sub-agents.
Here’s a snippet of the output:
⏺ I’ll help you write markdown documentation for the context passed to each template in this project. Let me start by exploring the codebase to understand the template structure and then use sub-agents to document them comprehensively.
⏺ Search(pattern: “**/*.html”)
⎿  Found 47 files (ctrl+o to expand)

⏺ Search(pattern: “render.*template|render_template”)
⎿  Found 16 files (ctrl+o to expand)
[...]
⏺ Now let me launch sub-agents to analyze different template contexts in parallel:
⏺ Task(Document index template context)
⎿  Done (12 tool uses · 86.4k tokens · 1m 13s)

⏺ Task(Document database template context)
⎿  Done (15 tool uses · 55.4k tokens · 1m 41s)

⏺ Task(Document table template context)
⎿  Done (14 tool uses · 85.2k tokens · 1m 44s)

⏺ Task(Document query/row template contexts)
⎿  Done (17 tool uses · 78.7k tokens · 1m 55s)

⏺ Task(Document special template contexts)
⎿  Done (26 tool uses · 116.1k tokens · 1m 50s)
It churned away for a couple of minutes (those sub-agents execute in parallel, another benefit of this pattern) and made me this template_contexts.md  [ https://substack.com/redirect/d81037b9-f937-4614-9372-7cc0b291274c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]markdown file. It’s very comprehensive.
Link 2025-10-13 nanochat [ https://substack.com/redirect/0594e3b7-d099-4d5f-8819-018f1e76393a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Really interesting new project from Andrej Karpathy, described at length in this discussion post [ https://substack.com/redirect/23ed8e5d-30dd-4500-90cd-dd24445ee539?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It provides a full ChatGPT-style LLM, including training, inference and a web Ui, that can be trained for as little as $100:
This repo is a full-stack implementation of an LLM like ChatGPT in a single, clean, minimal, hackable, dependency-lite codebase.
It’s around 8,000 lines of code, mostly Python (using PyTorch) plus a little bit of Rust for training the tokenizer [ https://substack.com/redirect/4fecd8c6-a7ea-4e63-8b0b-567d4cf8cc31?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Andrej suggests renting a 8XH100 NVIDA node for around $24/ hour to train the model. 4 hours (~$100) is enough to get a model that can hold a conversation - almost coherent example here [ https://substack.com/redirect/9875d5a8-c5d5-4403-91ea-da45087145ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Run it for 12 hours and you get something that slightly outperforms GPT-2. I’m looking forward to hearing results from longer training runs!
The resulting model is ~561M parameters, so it should run on almost anything. I’ve run a 4B model on my iPhone, 561M should easily fit on even an inexpensive Raspberry Pi.
The model defaults to training on ~24GB from karpathy/fineweb-edu-100b-shuffle [ https://substack.com/redirect/778ebc82-27d8-4d43-9988-3733b5e60bc8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] derived from FineWeb-Edu [ https://substack.com/redirect/018fd142-cfba-4eb5-83f2-29f80d79e077?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and then midtrains [ https://substack.com/redirect/216e6ae0-31bb-4f0a-9177-bebbe9301672?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on 568K examples from SmolTalk [ https://substack.com/redirect/fe96f850-aa24-44fb-b264-e01dd570fa25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (460K), MMLU auxiliary train [ https://substack.com/redirect/7fdd9d32-0038-4e53-85bd-b76746618ac4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (100K), and GSM8K [ https://substack.com/redirect/b3db675e-5841-4187-9cb6-9890d405b0db?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (8K), followed by supervised finetuning [ https://substack.com/redirect/8b4e1c6c-b546-49b7-8671-87f2432ffb5a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on 21.4K examples from ARC-Easy [ https://substack.com/redirect/5e6578b2-facd-43ea-b028-3d9848d58552?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (2.3K), ARC-Challenge [ https://substack.com/redirect/5ce42232-b338-4364-8fd3-c123bd17cf9d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (1.1K), GSM8K [ https://substack.com/redirect/b3db675e-5841-4187-9cb6-9890d405b0db?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (8K), and SmolTalk [ https://substack.com/redirect/fe96f850-aa24-44fb-b264-e01dd570fa25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (10K).
Here’s the code for the web server [ https://substack.com/redirect/49bb2da5-a155-4ae9-a3bc-16af44e9c5d0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which is fronted by this pleasantly succinct vanilla JavaScript HTML+JavaScript frontend [ https://substack.com/redirect/5d97186b-13f3-44c5-b630-596a56107b58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Update: Sam Dobson pushed a build of the model to sdobson/nanochat [ https://substack.com/redirect/2d59cbbb-89aa-421d-a71a-cb66a21848a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hugging Face. It’s designed to run on CUDA but I pointed Claude Code at a checkout and had it hack around until it figured out how to run it on CPU on macOS, which eventually resulted in this script [ https://substack.com/redirect/54814d96-c476-4310-b4b9-515e46ad0747?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which I’ve published as a Gist. You should be able to try out the model using uv like this:
cd /tmp
git clone https://huggingface.co/sdobson/nanochat
uv run https://gist.githubusercontent.com/simonw/912623bf00d6c13cc0211508969a100a/raw/80f79c6a6f1e1b5d4485368ef3ddafa5ce853131/generate_cpu.py \
--model-dir /tmp/nanochat \
--prompt “Tell me about dogs.”
I got this (truncated because it ran out of tokens):
I’m delighted to share my passion for dogs with you. As a veterinary doctor, I’ve had the privilege of helping many pet owners care for their furry friends. There’s something special about training, about being a part of their lives, and about seeing their faces light up when they see their favorite treats or toys.
I’ve had the chance to work with over 1,000 dogs, and I must say, it’s a rewarding experience. The bond between owner and pet
Link 2025-10-14 Just Talk To It - the no-bs Way of Agentic Engineering [ https://substack.com/redirect/76aafe58-9496-499f-b0f9-5c3bde22d37f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Peter Steinberger’s long, detailed description of his current process for using Codex CLI and GPT-5 Codex. This is information dense and full of actionable tips, plus plenty of strong opinions about the differences between Claude 4.5 an GPT-5:
While Claude reacts well to 🚨 SCREAMING ALL-CAPS 🚨 commands that threaten it that it will imply ultimate failure and 100 kittens will die if it runs command X, that freaks out GPT-5. (Rightfully so). So drop all of that and just use words like a human.
Peter is a heavy user of parallel agents:
I’ve completely moved to codex cli as daily driver. I run between 3-8 in parallel in a 3x3 terminal grid, most of them in the same folder [ https://substack.com/redirect/fc9046f5-74db-4770-b7ec-b4dea4de4fb1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], some experiments go in separate folders. I experimented with worktrees, PRs but always revert back to this setup as it gets stuff done the fastest.
He shares my preference for CLI utilities over MCPs:
I can just refer to a cli by name. I don’t need any explanation in my agents file. The agent will try $randomcrap on the first call, the cli will present the help menu, context now has full info how this works and from now on we good. I don’t have to pay a price for any tools, unlike MCPs which are a constant cost and garbage in my context. Use GitHub’s MCP and see 23k tokens gone. Heck, they did make it better because it was almost 50.000 tokens when it first launched. Or use the gh cli which has basically the same feature set, models already know how to use it, and pay zero context tax.
It’s worth reading the section on why he abandoned spec driven development [ https://substack.com/redirect/b76d91b9-3496-4494-a839-31a20f6aed98?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in full.
Link 2025-10-15 A modern approach to preventing CSRF in Go [ https://substack.com/redirect/2124ad40-212d-4fad-b456-6a3b6dfd3975?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Alex Edwards writes about the new http.CrossOriginProtection middleware that was added to the Go standard library in version 1.25 [ https://substack.com/redirect/b44edce5-fb4f-4cf1-b4e4-acbc03075b95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in August and asks:
Have we finally reached the point where CSRF attacks can be prevented without relying on a token-based check (like double-submit cookies)?
It looks like the answer might be yes, which is extremely exciting. I’ve been tracking CSRF [ https://substack.com/redirect/1bad9d06-977b-4f17-91eb-9ae0665a7d15?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] since I first learned about it 20 years ago in May 2005 [ https://substack.com/redirect/b9cb56ca-e3ae-4530-9c7a-01563fef52ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and a cleaner solution than those janky hidden form fields would be very welcome.
The code for the new Go middleware lives in src/net/http/csrf.go [ https://substack.com/redirect/0daf497c-899d-4135-9901-328654fe6b84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It works using the Sec-Fetch-Site [ https://substack.com/redirect/d4460455-5257-4324-8705-fedc73e1fc13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] HTTP header, which Can I Use shows as having 94.18% [ https://substack.com/redirect/13d9473d-b831-400f-816d-769d5b90cc7d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] global availability - the holdouts are mainly IE11, iOS versions prior to iOS 17 (which came out in 2023 but can be installed on any phone released since 2017) and some other ancient browser versions.
If Sec-Fetch-Site is same-origin or none then the page submitting the form was either on the same origin or was navigated to directly by the user - in both cases safe from CSRF. If it’s cross-site or same-site (tools.simonwillison.net and til.simonwillison.net are considered same-site but not same-origin) the submission is denied.
If that header isn’t available the middleware falls back on comparing other headers: Origin - a value like
https://simonwillison.net
- with Host, a value like simonwillison.net. This should cover the tiny fraction of browsers that don’t have the new header, though it’s not clear to me if there are any weird edge-cases beyond that.
Note that this fallback comparison can’t take the scheme into account since Host doesn’t list that, so administrators are encouraged to use HSTS [ https://substack.com/redirect/2250f46f-fdc5-478a-b099-ed11b50dfb12?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to protect against HTTP to HTTPS cross-origin requests.
On Lobste.rs I questioned if this would work for localhost, since that normally isn’t served using HTTPS. Firefox security engineer Frederik Braun reassured me [ https://substack.com/redirect/226547a3-53dc-4afb-afec-d739a474f5d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that *.localhost is treated as a Secure Context, so gets the Sec-Fetch-Site header despite not being served via HTTPS.
Update: Also relevant is Filippo Valsorda’s article in CSRF [ https://substack.com/redirect/b87bcdf7-1598-4b93-8ef8-5b492a088c15?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which includes detailed research conducted as part of building the new Go middleware, plus this related Bluesky conversation [ https://substack.com/redirect/4274a089-f55d-476a-a492-f5a0581c06bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about that research from six months ago.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOell5TkRNd01UWXNJbWxoZENJNk1UYzJNRFUwTWpneU9Dd2laWGh3SWpveE56a3lNRGM0T0RJNExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuM0hBZENsczZOcWFkOW9hajNJNzVuUi1OQTU5a3Q3bVhtQzI5US1kc2VFMCIsInAiOjE3NjI0MzAxNiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzYwNTQyODI4LCJleHAiOjIwNzYxMTg4MjgsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.TP9LlOPRVFMwMzzHY6rlprpwtRLwk75bLpcbphOvApU?
