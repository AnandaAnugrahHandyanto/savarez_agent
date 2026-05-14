# Agent Skills with Anthropic - DeepLearning.ai Course

**Source:** DeepLearning.ai
**Total Duration:** ~2 hours
**Date Fetched:** 2026-01-29

---

## Resources

https://github.com/https-deeplearning-ai/sc-agent-skills-files/tree/main


## Video 1: Introduction (2 mins)

0:00
Welcome to this course on agent skills,
0:02
built in partnership with Anthropic and taught by returning instructor Elie Schoppik.
0:06
Skills give Claude and other agents new abilities to carry out tasks.
0:10
I'm thrilled to have Elie return to teach this.
0:12
Thank you, Andrew. I'm happy to be back
0:14
and work with you all on this one.
0:15
Skills are folders of instructions that extend
0:18
your agent's capabilities with specialized knowledge.
0:21
In this course, you'll learn how skills work,
0:23
learn best practices for creating them,
0:26
and build skills for different use cases
0:28
including coding and research and data analysis and more.
0:32
What's exciting about skills is they're now an open standard,
0:34
which means they have a standardized format that work with any
0:37
skills compatible agent.
0:39
So you can build your skills once
0:41
and deploy them across multiple agent products.
0:43
Any skill should include a SKILL.md markdown file,
0:46
which contains the skill's name, description, and main instructions.
0:51
The main instructions can also refer to other files
0:53
such as scripts, additional markdown files,
0:56
and assets such as templates and images.
0:59
skills are progressively disclosed to the agent,
1:02
which means that the skill's name and description
1:05
always live in your agent's context window,
1:07
but the agent does not load the rest of the instructions
1:09
into its context until a user request
1:12
matches the skill's description.
1:14
At that point, the agent might then additionally load
1:17
the reference and asset files if needed as well.
1:20
To use this skill, your agent needs a basic set of tools,
1:23
filesystem access to read and write
1:25
files and a bash tool to execute code.
1:27
And these tools enable your agent to execute whatever command a skill requires.
1:32
Your agent can combine skills with MCP and sub-agents
1:34
to create powerful, agentic workflows.
1:37
For example, it can use MCP to get data from external sources,
1:40
then rely on a skill to
1:42
know what to do with that data
1:43
or how to retrieve it efficiently.
1:46
It can also delegate tasks to a sub-agent with isolated context,
1:49
which can itself use skills for specialized knowledge.
1:52
In this course, we'll start with Claude AI,
1:54
where we'll create a skill for a marketing campaign
1:57
and combine it with the pre-built skills for Excel and PowerPoint.
2:01
Then, we'll create two skills for content creation and data analysis workflows
2:05
and try them with the Claude API.
2:07
After that, we'll use skills with
2:09
Claude code for reviewing and testing code.
2:11
And finally, we'll build a research agent with the Claude agent SDK
2:15
that uses a skill to combine research results.
2:18
I'd like to thank Hawraa Salami from DeepLearning.AI
2:20
who contributed to this course.
2:23
So, how do you know when to use a skill?
2:26
Let's say you have a workflow that
2:28
you repeatedly ask your agent to implement.
2:30
Instead of explaining the same workflow every time,
2:33
you can package it as a skill so your agent
2:36
automatically knows what to do.
2:38
That's exactly what you'll learn with Elie in the first lesson.
2:42
So, please go on to the next video to learn more.

---

## Video 2: Why Use Skills - Part I (11 mins)

0:00
Skills are folders of instructions
0:01
that package repeated workflows,
0:03
specialized knowledge, or new capabilities for your agent.
0:06
If you find yourself typing the same prompt across conversations,
0:10
you should consider transforming that into a skill.
0:13
Let's explore how to do that using Claude AI.
0:16
So before we talk a little bit more about skills
0:18
and dive into what a skill looks like and how it works,
0:21
let's walk through a scenario to showcase why skills are so useful.
0:26
Right here, I've got some campaign data in a CSV
0:28
that I'd like to analyze the performance of.
0:31
So just to show you what
0:33
this looks like, I've got a date,
0:34
a campaign name, impressions, clicks, conversions.
0:37
You can imagine here that we're
0:39
going to take in some marketing data
0:41
use Claude to analyze this information.
0:43
So in my first prompt, I'm attaching this data,
0:46
explaining what the input data looks like,
0:48
asking to check for quality, funnel analysis,
0:51
and some useful metrics around what I expect
0:53
for click-through rates and conversion rates.
0:56
At the bottom, I've got an output format
0:58
that I'm requesting for this particular piece of data.
1:01
Now you can imagine it would be valuable
1:03
to not have to include this prompt
1:05
every time and to have that packaged up.
1:08
As we take a look at
1:09
what we're seeing in our campaign data,
1:10
Claude is going to read this CSV.
1:13
It's then going to perform the Data Quality Check and Funnel Analysis
1:17
and give us back our campaign performance analysis.
1:20
Here it's going to show the Total Records,
1:23
any Missing Data, and any Anomalies in the data that exist.
1:27
If we take a look a little
1:29
bit further, we'll see our Funnel Analysis
1:31
versus the benchmark data that we were looking for before.
1:34
We can see here, some things that are working better,
1:37
some things that are not working as well. We're getting a
1:39
lot of useful data back that we can take action around,
1:41
change our marketing campaigns and move forward.
1:44
We've got a nice interpretation of what Claude is telling us,
1:47
what's working, what's not working.
1:49
And now we're going to go ahead
1:51
and ask for additional computations of certain
1:53
efficiency metrics for marketing.
1:56
These include return on our ad spend,
1:58
cost per acquisition, and net profit and so on.
2:01
We're also going to ask for
2:03
an output format in a certain fashion.
2:06
We'll see the results from this efficiency analysis,
2:08
we'll see what's working, again, what's not working and some interpretations.
2:12
we'll see our portfolio performance and our total net profit.
2:15
Looks like we're making money here, but there's
2:17
still much more that I'm sure we can do.
2:19
The next step that we're going to do here is to
2:22
take in an additional piece of data, our budget reallocation rules.
2:25
The idea here is that we
2:27
have extra money to play around with
2:28
and think about allocating towards other marketing channels.
2:32
You can imagine this file has quite a bit of data
2:35
around the rules for allocating,
2:37
what we're trying to figure out and how best
2:40
to decide where to increase our budget.
2:42
This could also lead to maintaining a budget or decreasing a budget
2:45
based on this framework that we have here.
2:48
Again, this is a lot of data
2:49
that is specific to our particular use case.
2:52
Claude knows how to handle particular decisions
2:54
and analyze marketing metrics,
2:56
but here we're specifying exactly the
2:58
way that we want to do things.
3:00
This requires me bringing in external documentation,
3:03
finding the right people, and even if
3:05
I'm not the most knowledgeable about this,
3:07
hoping that I get it right.
3:09
We're going to go ahead and see these allocation rules, our recommendations.
3:12
We can see what's passing, what's not passing,
3:15
and a proposed reallocation here.
3:17
Freeing up some budget,
3:19
analyzing what's working and where to allocate additional budget towards.
3:23
What we've seen here is a step-by-step process
3:25
that requires us as the user to put in the necessary documentation
3:29
and have the necessary pre-existing knowledge.
3:33
Not only that, but everything that I'm putting in here
3:36
is immediately getting added to the context window.
3:38
What happens if I want to ask something different?
3:41
What happens if I want to have a different kind of conversation?
3:43
This information here is not always
3:45
necessary for everything I'm going to do.
3:48
What we're going to take a
3:49
look at here is how we can
3:50
take this information and package it into a skill.
3:54
a standalone asset, a folder really,
3:56
that contains instructions for how to go about performing the campaign analysis
4:01
while also being intentional
4:03
about what information goes into the context window
4:06
and what information doesn't.
4:08
As we've seen, this is a weekly campaign performance analysis.
4:12
So this isn't something that I want to
4:14
have to repeat on my own every single week
4:17
with this particular prompt by copying and pasting.
4:20
This is going to be much nicer
4:22
to have pre-packaged that I can use myself,
4:24
share with members of the team, and edit as necessary.
4:27
So with that, let's take a
4:29
look at what a SKILL.md file is.
4:31
This file needs to be named SKILL.md in markdown format.
4:35
And this is going to be the underlying set
4:37
of instructions to perform the task that we saw.
4:40
In this Markdown file, I have very similar
4:43
information to what I included in the previous prompt.
4:46
I have my input requirements, a data quality check,
4:50
funnel analysis with the metrics that we were working at before,
4:53
and historical benchmarks.
4:55
I have that same Efficiency Analysis
4:57
as well as the Output Format that I expect.
5:00
Finally, I have a note here on Budget Reallocation
5:03
that references a different file
5:06
only when the user asks about Budget Reallocation.
5:09
So we talked a little bit about how
5:11
this can be much more efficient with context.
5:13
This is one example where I'm only
5:15
going to be reading and using this file
5:17
if a user asks about that particular piece of information.
5:22
In order to get this skill to work as expected,
5:25
there's one more piece of data
5:26
that I need to add to the beginning here.
5:28
This data is in a data format called
5:30
YAML, and here's what it looks like.
5:33
Every skill that you make across the entire standard
5:37
requires a name as well as a description.
5:40
The name of the skill is going to be important for referencing
5:43
when to use it and in the UI
5:45
that we're working with if it's being used.
5:47
And the description is important
5:49
so that the model that we're working with can understand
5:51
when to use this particular skill.
5:54
When you make a skill, the name and description are required.
5:58
So we've got our SKILL.md file,
6:00
and the second file I want to show you is just this
6:02
budget_reallocation_rules.md file,
6:05
which is very similar to the other prompt that we saw.
6:08
When you make a skill, your skill can reference other files
6:12
as long as they're all in the same parent folder.
6:15
These budget reallocation rules are exactly
6:18
what I put in that previous conversation with Claude AI.
6:21
So what we're doing here is we're moving away
6:24
from putting in instructions directly in our conversation,
6:27
and instead putting it into a folder.
6:30
Now that I've got this SKILL file,
6:32
as well as any external files,
6:35
What I'm going to do here is make a new folder.
6:38
And I'll name that folder the name of the skill,
6:41
analyzing-marketing-campaign.
6:43
There are some high-level rules around naming skills.
6:46
Stick with lowercase letters, use dashes between words,
6:50
and don't use reserved keywords like Claude or Anthropic.
6:54
Now that I've created this folder for the skill that I'm making,
6:58
I'm going to go ahead and make another folder called references.
7:02
When we look at the open standard for skills,
7:05
we're going to see that this actually is a specific name
7:08
that we use when there are external references
7:11
that the skill uses. And inside of our SKILL.md,
7:14
we linked to references/budget_reallocation_rules.
7:18
So I'll go ahead and put that file in this folder.
7:22
I'll put the folder inside of our marketing campaign.
7:25
And then I'll put the SKILL.md
7:28
at the top level of this folder.
7:30
If we take a quick look at what's inside,
7:32
we should see our SKILL.md as well as our references folder
7:36
that contains that additional budget allocation file.
7:39
Now I'm going to go ahead and
7:41
create a zip file from this folder
7:44
and I'm going to go ahead and upload that to Claude AI.
7:47
Once I upload that skill,
7:49
I should be able to start using it in future conversations.
7:53
I'm going to head over to my Settings right over here.
7:56
And I'm going to go to Capabilities.
7:59
As I navigate to the bottom of Capabilities,
8:02
we're going to see this section on Skills.
8:04
There are some example ones that
8:05
we'll talk a little bit about later.
8:07
But right now, I want to add my
8:09
own. So I'm going to go ahead and add,
8:11
and I'm going to upload the skill in a zip file
8:14
that I created. I'm going to go
8:15
ahead and drag and drop that zip file
8:17
and give that a second to upload.
8:20
Once that's done, we can see the name
8:22
of our skill as well as that description.
8:24
Now that we've uploaded our skill, let's go see this in action.
8:28
I'm going to start with a new chat.
8:30
I'm going to go ahead and ask Claude
8:32
a similar prompt to what I had before.
8:34
And I'm going to go ahead now and attach the same CSV
8:36
that I was working with before.
8:39
If this works as expected,
8:41
we should start to see Claude pick up the skill
8:43
for our weekly marketing campaign.
8:46
Claude should then perform the tasks required in that skill
8:49
and the need for us to
8:50
have all that prompt back and forth
8:52
is no longer there.
8:54
So let's go ahead and see what Claude can do here.
8:56
We'll see here it's going to read this skill file
8:58
to ensure it's following the right instructions.
9:02
The name of our skill as well as the description
9:04
is what is allowing Claude to pick this up.
9:07
Since we're asking about reallocating the budget,
9:10
it's going to go ahead and read that additional file
9:13
that we uploaded to our skill.
9:15
We'll then go ahead and analyze the data.
9:17
If you want to see the code
9:19
that Claude is running and executing here,
9:21
we can always open this up and take
9:23
a look at what's happening behind the scenes.
9:29
What we're going to see here is
9:31
something very similar to what we saw before.
9:33
we're going to analyze channels that may
9:35
have additional challenges, in this case TikTok.
9:37
We may see things that are working as well as recommended reallocations.
9:41
But in this case, we didn't
9:43
have to add all the prompting ourselves.
9:45
This skill can be shared across many different platforms.
9:48
And since skills are an open standard, this is supported
9:51
in other coding environments like Codex, Gemini CLI, and much more.
9:56
So not only have we created a way to take this data
9:58
and package it up into a centralized place,
10:01
we're being more efficient with the context window
10:04
and the portability here is extremely valuable.
10:06
Now, let's go ahead and create a report
10:09
with the data that we found.
10:11
We're going to go ahead and create an Excel report
10:13
with the following pieces of information
10:16
as well as a color coding that we're recommending.
10:19
Under the hood, the ability to create spreadsheets
10:21
and execute necessary code to do so,
10:24
actually lives in a skill that comes built-in to Claude.
10:28
So we're actually going to see the underlying skill being used,
10:31
code being run to create this Excel file,
10:34
and then finally the output based on the requirements that we specified.
10:41
We've got our spreadsheet now.
10:42
Here we can see, we've got an Executive Summary,
10:44
Funnel Analysis, Efficiency Analysis.
10:47
And we can go and open this in Google Drive
10:49
or download this spreadsheet.
10:52
Through the use of our skill to
10:54
analyze data and give us what we need,
10:56
as well as built-in skills to create spreadsheets,
10:59
we can transform data from CSVs into meaningful, actionable insights
11:04
in many different kinds of file formats.
11:06
Next, we'll explore in a little bit more depth
11:09
what a skill looks like, how it works,
11:12
and where it fits into the entire AI ecosystem.

---

## Video 3: Why Use Skills - Part II (8 mins)

0:00
In the previous lesson, we saw how to create skills in Claude
0:03
and move from prompts with data to package skills
0:06
that we can use across many different conversations.
0:10
Now let's dive deeper and talk about what skills are
0:13
and the open standard that powers them.
0:15
Similar to the model context protocol,
0:18
skills themselves are an open standard
0:21
that can be used across many different AI applications.
0:25
While skills were something originally created at Anthropic.
0:29
Skills themselves are now an open standard
0:32
with a specific specification
0:34
that is used across many different platforms,
0:37
including Codex, Gemini CLI,
0:39
Claude Code, Open Code, and much more.
0:42
With that in mind, let's talk
0:43
a little bit about how this works.
0:45
When we build AI applications, in order to use particular skills,
0:50
we need to make use of some kind of file system
0:53
when using tools like Claude AI or Claude Desktop.
0:57
In that file system, we load folders
0:59
that contain a SKILL.md file
1:02
and subfolders or files that can be referenced.
1:05
Here we can see exactly what we did previously.
1:08
At the same time, skills themselves
1:11
cannot only include other markdown documents,
1:14
but scripts that can be executed.
1:17
For example, we have a skill for working with PDF documents.
1:21
we need to convert PDFs to images,
1:23
extract info from form fields,
1:26
and even fill PDF forms with annotations.
1:29
This requires code to be executed.
1:31
But that code that needs to be executed
1:34
can be referenced from the SKILL.md file.
1:36
So as we start to explore
1:38
our own custom skills and built-in skills,
1:41
it's important to note that skills are not
1:43
just text files that reference other text files,
1:46
but text files that can reference scripts,
1:49
what they do, and when they need to be executed.
1:52
Skills can also include icons, images, and other assets
1:56
as we start to think about
1:59
ways of creating custom styles and brands.
2:01
Where skills really shine are places
2:04
where Claude might not know exactly how you or your company operates.
2:09
You can imagine designing newsletters, creating brand guides,
2:13
things that Claude has a general idea on,
2:16
but not the exact way that
2:18
your company or your team does it.
2:20
To give some more idea of why we bring
2:23
agent skills into the mix when we're building our own agents.
2:27
The way that we used to think about building agents
2:29
centered around agents with a single purpose.
2:32
Coding, research, finance, marketing, and much more.
2:36
These domain-specific agents
2:38
had a particular set of tools, the context
2:40
that it needed to perform the task necessary.
2:43
But as we started to build more of these single-purpose agents,
2:46
we started to realize that under the hood,
2:49
all that they really need is a simple scaffolding.
2:52
Underlying tools like bash and a filesystem,
2:55
to find, edit, modify, execute,
2:57
and perform whatever tasks are necessary.
3:01
These simpler agents are easier to evaluate, understand, and scale.
3:06
But what these agents lacked was the underlying
3:09
context and domain expertise to do the job reliably.
3:12
That context can be provided through skills, through the model context protocol,
3:17
but that domain expertise is really where skills shine as well.
3:21
We want finance agents to perform financial analysis in a particular fashion.
3:25
We want research agents to have the domain expertise
3:28
necessary to research the way that we want.
3:31
to be able to port that across many different ecosystems
3:34
and agents, and that's why we have agent skills.
3:37
These skills provide us the procedural knowledge
3:40
and the user-specific context that they can load on demand.
3:44
In addition to domain expertise,
3:47
skills can also provide a repeatable workflow.
3:50
In a non-deterministic system,
3:52
where we don't always know exactly what the
3:54
output of the model is going to be,
3:56
it can be difficult to find repeatable ways
3:58
of producing the same output.
4:00
What skills allow us to do is provide a repeatable workflow.
4:04
with very articulate steps or instructions
4:07
that allow the agent to perform a task
4:10
that we can start to predict with more accuracy.
4:13
Skills also introduce the idea of new capabilities,
4:16
things that an agent does not know
4:17
how to do out of the box
4:19
or even data that Claude has no idea how to operate on.
4:23
When we bring in these new capabilities,
4:26
we unleash an entire ecosystem and new functionality for our agents
4:30
with minimal additional context.
4:32
As we think about domain expertise,
4:34
we want to lean on things that
4:36
Claude might not know how to do
4:38
or knows how to do but not for your particular domain.
4:43
Claude can perform data analysis.
4:45
Claude can perform legal review.
4:47
But how does it do it the way that you
4:49
or your team or company want it to be done?
4:52
We previously saw the ability to perform weekly marketing campaign reviews,
4:56
and we want that to be
4:58
predictable across many different individuals and teams.
5:00
As we start to think about some of these new capabilities,
5:03
things like generating presentations, Excel spreadsheets, PDF reports,
5:08
executing scripts when necessary to perform those actions,
5:11
that here is where agent skills can shine.
5:14
What we saw previously, without skills,
5:16
was the idea of describing our instructions,
5:18
trying to predict workflows and bundling
5:21
all of the necessary files in context at one time.
5:25
We talked a little bit about the portability of skills.
5:28
And while we've seen skills so far in Claude AI,
5:32
skills can be used in the exact same format,
5:35
not only across Claude Code, the Agent SDK and the API,
5:39
but since Agent Skills are an open standard,
5:42
you can use this across a growing number of agent products.
5:45
You can create skills in one environment
5:47
and use them and share them and scale them
5:49
across many different environments.
5:52
When we say that skills are composable,
5:54
this is something that we've seen already.
5:56
We can take custom skills like analyzing our marketing campaign
6:00
and we can combine that with built-in skills
6:03
like creating PowerPoint presentations,
6:05
PDFs, or Excel spreadsheets.
6:07
Not only can we use multiple skills together,
6:10
but we can combine them to build complex and predictable workflows.
6:15
We can reference the skills necessary, the steps necessary,
6:19
and start to create predictable outputs
6:22
in a non-deterministic system.
6:24
Under the hood, skills can contain quite a bit of information.
6:28
We saw examples with additional markdown files
6:30
and even examples with scripts that can be executed.
6:34
You can have hundreds of skills across your system,
6:36
and what we're going to see quite a bit more
6:39
is that to protect the context window,
6:41
skills are progressively disclosed.
6:43
The idea of Progressive Disclosure
6:46
is to only load the data necessary
6:48
and avoid polluting the context.
6:51
We like to think of the context window as a public good.
6:55
The more data that we add to the context window,
6:57
the more tokens we consume,
6:59
the faster our context window fills up,
7:01
and the likelihood of context degradation
7:04
or incorrect responses potentially increases.
7:07
In order to avoid polluting the context window
7:10
with data that we might not need,
7:12
skills introduce the idea of Progressive Disclosure.
7:16
When skills are loaded from the file system,
7:18
the only data that gets added to the context window
7:21
is the name and description of the skill.
7:24
This is essential so that Claude or any other system knows
7:27
what the skill is and how to trigger it.
7:30
Once that skill is triggered, the underlying SKILL.md is loaded.
7:35
This is the next phase of loading data into context.
7:38
And depending on what is required,
7:41
if there are additional files or scripts
7:43
that need to be loaded and executed,
7:46
those will be loaded progressively.
7:48
These additional resources can be loaded as needed,
7:52
and if there are scripts that need to be loaded,
7:54
those scripts are loaded and executed separately from the context window
7:59
to avoid polluting with additional tokens that are not necessary.
8:03
By using tools like bash and a file system,
8:06
Claude can load only the information that's necessary,
8:10
execute only scripts and reading of files that is necessary,
8:14
and intentionally only add what is necessary to the context window.
8:19
In the next lesson, we'll continue talking about skills
8:22
and particularly how they're used alongside other technologies
8:26
like the model context protocol, sub-agents,
8:29
underlying tools, and much more.

---

## Video 4: Skills vs Tools, MCP, and Subagents (7 mins)

0:00
You can combine skills with tools, MCP, and subagents
0:03
to create powerful agentic workflows.
0:06
Let's go through each component, see how they work together
0:09
and learn when to use what.
0:11
I'll see you there. In this lesson,
0:13
we're going to explore how skills fit in to the agent ecosystem.
0:18
With so many different technologies,
0:21
like MCP, skills, tools, and subagents,
0:24
let's make sure we understand how they all work together.
0:28
In your existing applications,
0:30
we can bring in MCP servers for the context that we need.
0:33
leverage subagents for their own
0:35
main thread and parallelization
0:38
and bring in skills for those repeatable workflows.
0:41
Let's see this in a little more depth.
0:44
When we compare skills with the model context protocol,
0:47
we want to think a lot about working with external data systems
0:51
and bringing in the tools and resources that we need.
0:54
The model context protocol connects our agent or AI applications
0:58
with external systems and data.
1:01
That could be an external database,
1:03
data from Google Drive.
1:04
using a various array of systems,
1:08
but anytime that you need external data
1:10
and context that the model doesn't know about,
1:12
the model context protocol is extremely helpful.
1:15
The skills that you have can leverage
1:18
those underlying tools and data
1:20
from the model context protocol
1:23
to teach your agent what to do with that data.
1:26
Think of the model context protocol
1:28
as bringing in all of the underlying tooling that we need,
1:32
and the skill as the set
1:34
of instructions to put those tools together
1:36
to build particular workflows that are repeatable
1:39
and produce the kind of data that you want.
1:42
As we think about leveraging external data
1:44
to compute metrics and research and calculate data,
1:48
all of those underlying tools can be provided externally
1:51
through the model context protocol. When we
1:54
think a little bit about skills versus tools,
1:56
I like to draw the analogy of tools
1:59
as a little bit more lower level.
2:01
You can imagine that you have tools
2:04
like a hammer and a saw and some nails.
2:06
And you have a skill, like how to build a bookshelf.
2:09
The tools themselves are underlying ways
2:12
of accessing systems and providing agents
2:17
with the capabilities they need to accomplish a task.
2:20
In fact, tools are used under the hood to power the ability
2:24
to generate skills, to read skills,
2:26
and even to produce a Filesystem
2:29
for executing code and loading these skills.
2:32
Skills extend the capabilities with specialized knowledge,
2:36
bringing in additional files and scripts that need to be executed,
2:40
but the ability to execute those underlying scripts
2:43
and load those files and folders is provided by tools.
2:47
There are tools that are built in to certain agentic ecosystems,
2:51
there are tools that we can write on our own,
2:53
and tools that we can load through the model context protocol.
2:57
Tool definitions always live in the context window,
3:00
whereas skills are progressively loaded when necessary.
3:04
When we think about how these work together,
3:06
skills allow us to create predictable workflows,
3:10
and those skills can bring in scripts that can be executed
3:14
kind of like a tool on demand.
3:16
If there is a tool that we do not need
3:18
in every single conversation
3:20
we can use that only when needed
3:22
through skills and progressive disclosure.
3:25
When we think about how subagents fit into the mix,
3:28
let's first define what we think of as a subagent.
3:31
We have a main agent that can spawn or create subagents
3:35
that can report back to the parent agent.
3:38
These subagents can be created through ecosystems like Claude Code
3:41
or the agent SDK,
3:43
or we can also make our own.
3:45
When we think of the value that subagents provide,
3:48
we think a lot about having an isolated context
3:51
with fine-grained permissions,
3:53
as well as executing tasks in parallel.
3:56
When we think about what these Subagents can access,
3:59
we have limited tool permissions, and we also can specify
4:03
what skills each subagent can access.
4:06
So while the main agent can serve as an orchestrator
4:09
and can leverage whatever Skills necessary,
4:12
Subagents can do the same type of idea
4:14
with making use of particular skills.
4:17
Subagents work quite nicely with skills
4:19
where we can have a particular subagent like a Code Reviewer,
4:23
whose sole task is to analyze and review a code base
4:26
and leverages skills which specify exactly
4:29
how you, your team, or your company might perform a code review.
4:34
When we put this all together, we can provide an analogy
4:37
of a Customer Insight Analyzer.
4:39
Let's think about how this all works together.
4:41
We have a main agent that is given a set of tools.
4:44
Those tools could be provided from MCP servers
4:47
we can bring in the data, the resources,
4:49
the tools necessary to perform the tasks needed.
4:53
For dispatching subagents to analyze customers,
4:56
we might analyze interviews from customers or surveys from customers,
5:00
do those in isolation and parallelize them
5:03
to get data back even faster.
5:05
When we think about how to actually analyze insights from customers,
5:10
how to categorize feedback, summarize findings,
5:13
how to analyze interviews and surveys,
5:15
and how to make sure we do those in a predictable fashion
5:18
with the right tools loaded at the right time,
5:21
that's where skills come into play.
5:23
We bring in data externally.
5:25
We leverage subagents if we need to parallelize
5:28
and execute in a separate thread and context window,
5:31
and we bring in skills to consume all of
5:35
this information in a predictable, repeatable, and portable fashion.
5:38
To summarize this, there are many different pieces in
5:41
the AI ecosystem when we think about building AI applications.
5:45
Fundamentally, we have prompts,
5:47
the underlying most atomic unit in a conversation.
5:50
Prompts are the underlying tool for us to communicate with models.
5:54
But prompts themselves don't scale very well
5:57
across teams and companies.
5:59
To bundle these underlying prompts and conversations
6:02
and code and assets, we can leverage skills.
6:06
Subagents that we have tasks delegated to can make use of skills.
6:10
Those subagents can then consume tools necessary
6:13
from a main agent that are defined
6:15
through the model context protocol.
6:18
As we think about what these particular features aim to solve,
6:22
we want to be really intentional about how we're loading this information
6:26
and what this is best used for.
6:28
When we think about the context window as a public good,
6:31
we want to be intentional about when subagents can help us minimize
6:34
what goes in the main context window
6:36
and how MCP can load the data necessary
6:39
and skills can load it progressively.
6:41
When we talk a little bit about the persistence
6:44
and how we can think about drawing things into a longer-term memory.
6:48
With subagents, we can persist across many different
6:50
sessions from the subagent and the parent agent.
6:54
With skills, we can persist across conversations that we have
6:57
with the user and the AI application.
7:00
So as we think about where each of these steps are used,
7:04
we want to use skills for procedural, predictable workflows
7:08
and subagents for full agentic logic
7:10
only when necessary for specialized tasks.
7:14
In the next lesson, we'll take a look
7:16
at some of the pre-built skills that come with Claude.
7:20
We'll take a look at the repository for these skills,
7:22
dive deep into some of the SKILL.md files
7:25
and talk about a very useful skill called the skill creator,
7:29
so that we don't have to manually
7:31
create all of our skills from scratch.

---

## Video 5: Exploring Pre-Built Skills (18 mins)

0:00
In the first lesson, Claude AI used the Excel skill
0:02
to create spreadsheets displaying the marketing results.
0:06
The Excel skill is one of Anthropic's pre-built skills,
0:09
which also include a PowerPoint, Word, and PDF skill,
0:13
as well as a skill creation skill.
0:16
Let's take a look at those.
0:18
Now that we've seen how skills fit in the entire AI ecosystem,
0:21
let's take a look at some of the pre-built skills
0:24
that you can use out of the
0:27
box with Claude AI and Claude Desktop,
0:29
and that you can install yourself with tools like Claude Code.
0:32
Inside of this repository that lives at
0:35
github.com/anthropic/skills.
0:38
Let's take a look at the skills folder
0:40
and see which built-in ones that we have.
0:42
All of these are ready for production usage.
0:45
And we actually saw in a previous lesson
0:48
the use case of this Excel skill.
0:51
It's important to note that this list of skills,
0:53
while created at Anthropic,
0:55
is actually bucketed into two different sections.
0:58
The skills for Microsoft Docs, PDFs,
1:01
Power Points, and Excel
1:03
are known as document skills.
1:06
These are built in and always used
1:08
in tools like Claude AI.
1:10
The remainder of these skills are examples that we've created
1:13
that you can toggle on and off in Claude,
1:16
but by default with the exception of skill-creator
1:19
are toggled off.
1:20
Let's first start by analyzing the PowerPoint skill.
1:25
We can see just like other structures
1:27
that we have a SKILL.md file
1:30
as well as other files and folders to reference.
1:33
Inside of this SKILL.md,
1:36
we have that same YAML Frontmatter
1:39
that includes the name and the description.
1:41
What you're seeing here is how GitHub is rendering this markdown file,
1:46
but the underlying code
1:48
looks very similar to what we've made before.
1:51
You can view it this way if you're familiar with markdown files.
1:55
I'll switch back to the preview
1:56
because it looks a little bit nicer.
1:58
When we take a look at how
2:00
this skill works and what it does,
2:02
We've got an overview.
2:04
The users may ask to create,
2:06
edit, analyze contents of a PowerPoint file.
2:08
Here's what it looks like, here's how you read it.
2:11
And if there are particular tasks that need to be done,
2:14
there are underlying scripts to go ahead and execute.
2:18
Remember, these are not executed right out of the box.
2:22
These are only loaded and executed when necessary.
2:25
There's quite a bit that we can do with PowerPoint presentations,
2:28
colors, typography, as you can imagine,
2:31
this is how we can start to make things that look nicer
2:34
and look more like real-world presentations out of the box.
2:38
There are design principles that we have, requirements that are necessary,
2:42
and color palette selections that we can have Claude pick from
2:45
when the user does not specify them.
2:48
This SKILL.md is quite long,
2:50
as there is quite a bit
2:52
that we can do with PowerPoint presentations.
2:53
But what we're going to see later in this lesson
2:56
is how to actually use this skill
2:58
to take existing data and turn it into
3:00
a beautiful looking presentation.
3:03
The next skill I want to show you
3:05
is a little bit of a meta idea here,
3:07
and that's called the skill-creator.
3:09
And the skill creator is a skill
3:12
that serves the purpose of programmatically creating skills for you.
3:17
Instead of having to do things from scratch
3:19
and create the necessary files and folder structure,
3:22
the skill creator can do that for you.
3:25
Let's take a look at the SKILL.md file
3:27
and see what's happening here.
3:29
Similar to our other skills, we have a name and a description.
3:33
And I'm actually going to take
3:34
a look at the underlying code here,
3:35
since it's a little bit easier to follow.
3:38
We specify in this SKILL.md file
3:41
what skill is, what it provides,
3:44
and then we include some of the best practices associated with skills.
3:48
We're going to dive into those best practices in the next lesson.
3:52
But you can imagine when Claude is programmatically creating skills for you,
3:56
we want to leverage some of these best practices.
3:59
When we take a look at the skill creation process,
4:02
we're extremely explicit with the steps that we have here.
4:06
Since we want to use this skill to create a predictable workflow,
4:10
we want to be extremely explicit with what the steps are,
4:14
how to follow them, and what
4:16
to skip only if some reason exists.
4:19
We start with concrete examples,
4:21
we plan reusable skill contents,
4:23
and here you can start to see examples
4:26
that are very helpful for Claude to pattern match
4:29
when there's a skill you'd like to create.
4:32
When we start initializing the skill,
4:34
here we're running underlying Python scripts
4:37
to perform the task necessary.
4:39
Let's take a look at what those scripts do.
4:44
Inside of the scripts folder, I have three Python files here.
4:48
A script to initialize the skill and provide the underlying text,
4:53
a Python file to package that skill,
4:55
and then a script to validate that skill.
4:58
Let's take a look at what this
5:00
underlying code does to initialize a skill.
5:03
We take an existing template that we have
5:05
with some YAML Frontmatter and some placeholders and to-dos,
5:09
and we fill that in based
5:11
on the data that is coming in.
5:13
This underlying script allows us to create
5:16
the necessary text files when making our skills.
5:20
Once we've generated the necessary files, we can package that up.
5:24
Here you can see we're bringing in the necessary modules
5:27
to zip our skill necessary
5:29
and make sure that we're doing this
5:31
in the right folder and file structure.
5:33
Finally, we have one last script
5:35
to perform a validation of our skill.
5:38
make sure that a SKILL.md exists,
5:41
validate some of the YAML Frontmatter,
5:43
and make sure that what we put
5:45
inside of our folder and files is correct.
5:49
We're going to be leveraging this skill-creator skill
5:52
to take existing content that we have
5:54
and package it up into a reusable and modular script.
5:58
Now let's go ahead and shift gears back to Claude
6:01
and see how to put together built-in skills,
6:03
our own skills, and a predictable workflow
6:05
with an MCP server.
6:08
Back in Claude, let's go and take a look
6:11
and make sure that we have the
6:13
correct skills enabled and where those live.
6:16
Back in settings, inside of capabilities.
6:19
We saw previously, we can create skills in this section.
6:23
What I want to show you
6:24
are the example skills that we have
6:27
and this should look pretty familiar.
6:28
This is what we saw on GitHub.
6:30
By default, these skills are turned off.
6:33
If we want to toggle them on, we can absolutely do so.
6:36
The skill that is toggled on by default
6:39
is the skill-creator that we just saw.
6:42
It's important to note that while the skill-creator
6:44
is extremely effective at creating
6:47
underlying skills and structure necessary,
6:50
we still have to be intentional about the prompt that we provide
6:53
and the data that goes in to
6:55
the skill that we're going to make.
6:57
What we're going to do now is
6:59
put all of these ideas around skills,
7:02
MCP, and prompting together.
7:05
First, we're going to modify our previous skill
7:08
that we created for analyzing campaigns.
7:11
to not use a CSV for data, but instead BigQuery.
7:16
If you're not familiar, BigQuery is a data store powered by Google,
7:20
and in order to bring in the
7:22
necessary tooling and context to work with BigQuery,
7:25
we're going to connect an MCP server.
7:27
So we're going to use the skill-creator skill
7:30
to modify our previous marketing analyzing skill to use BigQuery.
7:35
We're then going to use skill-creator to create another skill.
7:39
This will be for the purpose of brand guidelines.
7:42
We'll include a file that specifies the guidelines as well as logos,
7:47
and we'll build for ourselves another skill
7:50
to perform that task. Finally,
7:52
we'll take our two skills that we used
7:55
to extract and analyze data and to leverage brand guidelines
7:59
and combine them with a built-in skill
8:02
for creating PowerPoint presentations
8:04
to create a workflow that makes use of prompting,
8:07
skills, and the model context protocol.
8:09
Before we jump in, you might be wondering
8:12
where the Excel and PowerPoint
8:14
and other document skills that we saw before live.
8:18
These are built in to Claude AI.
8:20
and are not things that can be toggled on and off.
8:23
So with that in mind, let's start this workflow.
8:26
Before we modify our analyzing marketing campaign skill to use BigQuery,
8:31
Let's also make a note that we're using Claude desktop here
8:35
to connect to a local MCP server to leverage BigQuery.
8:39
So let's take a look at how that BigQuery server is configured.
8:43
I'm going to head over to Settings, Developer
8:46
And here, we can take a look
8:49
at the underlying command and arguments
8:51
and environment variables for the particular project
8:53
and where my credentials live.
8:56
For this example, we don't have to use BigQuery,
8:59
you can use a database, some external data store,
9:02
but we just want to showcase what it looks like
9:04
with skills and MCP servers working together.
9:07
And if you're interested in seeing that
9:10
underlying config file, here's what it looks like.
9:13
In this config file, we specify
9:14
the servers we want to connect to
9:17
and the underlying commands to run when Claude Desktop starts.
9:21
With that in mind, let's go ahead and modify
9:24
our previous skill to now use BigQuery
9:27
instead of CSVs for data access.
9:31
To make sure this is working correctly, let's first ask Claude
9:35
to list the tables in BigQuery that exist.
9:42
This is going to make use
9:43
of the MCP server that we have.
9:45
We're going to allow this and we
9:47
should get back the list of tables.
9:49
In this case, we only have one.
9:53
So here we can see there's a data set called marketing
9:55
that contains a single table.
9:57
Now we're going to ask Claude
9:59
to show me the schema of the table.
10:04
Hopefully Claude can pick up that small spelling mistake
10:07
and we should be in business. Here
10:10
we're specifying what the table looks like.
10:13
And this looks great. And we're
10:14
going to make use of this schema
10:16
when we go ahead and update our analyzing-marketing-campaign skill.
10:21
What we're going to do now is ask Claude to update
10:24
our analyzing-marketing-campaign skill
10:26
so that instead of a CSV upload, we pull from BigQuery.
10:30
We specify the data
10:32
from the BigQuery table, specifically the schema that we just saw above.
10:36
Since we're all in one single conversation,
10:39
Claude should have no problem taking
10:40
a look at what the schema is.
10:42
We're specifying some requirements for this,
10:45
and just like in our existing skill,
10:46
we want to make sure that the reference
10:48
to our budget reallocation rules does not get modified.
10:52
Like we spoke about earlier, the skill creator skill
10:54
is extremely helpful and efficient,
10:56
but we still need to give the context necessary.
11:01
Notice here, the first thing it's going to do is analyze
11:03
the necessary skill structure and use our skill creator skill
11:07
to modify the existing skill
11:10
and follow best practices.
11:13
We're going to go ahead now and create the updated skill
11:17
with a new SKILL.md file.
11:20
Here we can start to see something
11:22
that feels similar to our previous skill.
11:25
But instead adding BigQuery instead of CSV uploads.
11:29
Under the hood, we're using the file system and bash tools
11:33
to create the necessary file and folder structure for us.
11:38
What we can see here is instead
11:40
of using a CSV, we're using BigQuery
11:43
and we're following the best practice of
11:45
using MCP servers with skills where we specify
11:48
the server and the name of the tool.
11:52
The skill-creator is following best practices
11:54
to take our existing skill and modify it.
11:58
So as we instructed skill-creator,
12:00
when we specified our required input.
12:02
We're seeing this in practice right now.
12:05
It's best practice not to use an ambiguous date range
12:08
or the entire range, so we ask the user to clarify,
12:11
and when we show an example
12:13
of querying, we're specifying a date range.
12:16
So some of the tools and requirements that we put in
12:19
are being directly applied when we update this skill.
12:22
So our skill looks like it's in great shape.
12:25
In order to make sure this is saved to subsequent conversations,
12:28
let's go ahead and copy this skill.
12:35
Now we're going to shift gears and
12:37
create a new skill for brand guidelines
12:38
that we'll use alongside this skill
12:42
to create a compelling data-driven PowerPoint presentation.
12:47
So let's go ahead and start with a new chat
12:49
and we're going to ask Claude to create
12:52
a brand guideline skill from files that we upload.
12:56
The first thing I'm going to do is upload a file
12:59
with my brand guidelines as well as some logos
13:02
to be used in the presentation.
13:05
Before we go ahead and create this skill,
13:07
let me just show you what these brand guidelines look like.
13:10
I've got a color palette, supporting colors, typography.
13:14
Claude knows how to design things, but where skills really shine
13:17
are where you can tell Claude exactly
13:20
how you want things done for your company.
13:22
logos, colors, fonts, great example.
13:26
Now let's go ahead and create a skill from these files
13:30
that we can apply to future presentations and documents.
13:33
What we're going to see here is the skill creator skill
13:37
in action again.
13:39
We're leveraging the existing tooling and skills that we have
13:42
to use best practices as well as the guideline and logos
13:46
to make a skill that is repeatable and portable.
13:50
We're going to analyze other existing
13:52
skills to see what patterns they use
13:54
and make sure that this new skill we're creating
13:57
can complement them. And this is extremely valuable
14:00
since we're going to be using this with PowerPoint presentations.
14:04
Now that we have a good
14:05
idea of what needs to be done,
14:07
let's run that init_skill Python script that we saw before.
14:11
This will create the underlying skill,
14:13
and now we can start adding our assets
14:15
to the skill's assets folder.
14:19
We're going to start to see colors populate,
14:22
accent colors, fonts, typography.
14:25
And in a bit, we'll have a skill
14:27
that we can start adding to all future conversations
14:29
when there's design that we need done.
14:33
Our logos are being pulled in,
14:35
Word documents and PDFs are specified,
14:37
and presentation layouts are the way that we want them to be.
14:41
The skill creator has finished running.
14:44
And here we have a SKILL.md file that's been created,
14:47
following best practices with a name and a description,
14:51
as well as underlying folders
14:53
with the necessary data and logos that we need.
14:56
There's one more step we need to do
14:58
to make sure that this gets added to future conversations.
15:02
In order to make sure this is saved to subsequent conversations,
15:06
let's go ahead and copy this skill.
15:10
Once this is done, we should see this skill
15:13
in the list of skills that we've created.
15:16
Now that we've updated
15:18
our skill to move from CSVs to BigQuery,
15:21
and created a new skill for our brand guidelines,
15:24
let's combine that to build a workflow alongside the built-in
15:27
PowerPoint presentation skill
15:30
to first analyze our data
15:32
and then generate a presentation.
15:34
So we're going to first analyze our marketing data
15:37
for a different week in BigQuery
15:39
to see how each channel is doing.
15:41
And then based on that data,
15:43
generate a presentation with our brand guidelines.
15:47
Let's see what this looks like.
15:49
First, we're going to go ahead and read the relevant skill files.
15:52
This includes our marketing campaign analysis
15:55
and will include our BigQuery guidelines as well.
15:59
We're going to go ahead and make
16:00
sure we have the correct PowerPoint presentation skill
16:02
as well as our brand skill for styling.
16:05
Inside of the underlying PowerPoint presentation skill,
16:08
there's additional documentation for presentation creation.
16:11
First, we're going to go ahead and start with BigQuery.
16:14
We're going to query what's necessary.
16:19
We can take a look and
16:21
see the underlying SQL that's being written
16:23
and like we saw before, that date range that we're looking for.
16:27
Now that we have the data,
16:29
we're going to use these metrics to go ahead
16:31
and generate a PowerPoint presentation.
16:33
We're going to do so with the styling that we've advised
16:36
in our brand style and turn this into a PowerPoint presentation.
16:39
can see here the underlying CSS and HTML
16:41
being written for our slides.
16:44
And then we're going to lean into the built-in skill
16:46
for creating the underlying presentation.
16:50
Now that we've got the right HTML files,
16:52
let's go ahead and create our presentation.
16:55
Here we're using the native PowerPoint skill
16:59
and writing the necessary code to create the presentation.
17:03
We can see here even when there
17:05
are particular issues, the model will go back
17:08
edit anything necessary
17:10
and lean on the exact workflow,
17:12
not only for running code necessary,
17:14
but validating what needs to be done.
17:17
This ability that the model has to backtrack
17:20
and follow particular patterns
17:21
allows for us to create presentations
17:24
that don't come with built-in issues
17:26
that we need to immediately then correct.
17:28
So we're seeing that Claude's done its verification, the slides look great.
17:32
Now it's going to go ahead and generate that underlying PowerPoint presentation,
17:36
which I can open up in
17:38
Google Drive and use as Google Slides,
17:40
or I can download directly.
17:42
We can see here, I've got some really nice looking slides
17:45
with the colors, fonts, logos,
17:48
and everything that I want for my particular company.
17:51
We have our efficiency analysis, funnel analysis,
17:54
and the executive summary that highlights what
17:56
needs review and what's doing quite well.
17:59
I can download this presentation, I
18:01
can continue to build off of it,
18:02
and again, open it up in Google Drive to share with teammates.
18:06
I can continue prompting and working with this presentation.
18:09
But what we're seeing here is an underlying PowerPoint presentation
18:12
created from a built-in skill,
18:14
combined with two skills that we've made
18:17
alongside an MCP server
18:19
pulling in data from BigQuery.
18:22
In the next lesson, we'll explore some of the best practices
18:25
around creating skills and take a look at two other custom skills
18:29
that we create and see if we're following the best practices.

---

## Video 6: Creating Custom Skills (16 mins)

0:00
We'll now take a closer look at how skills are structured
0:02
and best practices for creating skills.
0:05
Then we'll apply what you learn to two examples.
0:08
One to create practice questions based on lecture notes,
0:11
and another to analyze the characteristics of time series data. Let's go.
0:15
In this lesson, we're going to focus
0:17
a bit on the structure of a skill,
0:19
some of the best practices associated with it.
0:22
and then we're going to take a
0:23
look at two skills that we make
0:25
and see how they fare when run through the skill creator
0:28
to see how they perform against some of the best practices.
0:31
To review, every skill that we make has
0:34
required SKILL.md file with some YAML Frontmatter
0:37
that requires a name and a description.
0:40
In the underlying SKILL.md,
0:42
we have the content that goes in our skill,
0:44
and then any references to scripts
0:47
or any additional text files, assets necessary
0:50
that are loaded only when necessary.
0:53
As we take a look at some
0:54
of the best practices for names and descriptions,
0:57
you can imagine this is mission critical.
0:59
Your name and description are not only how Claude
1:02
can analyze what your skill does,
1:04
but also detect when to use that particular skill.
1:08
So with the name, there's a
1:10
maximum of characters, same with the description.
1:12
We mentioned briefly, the name has
1:14
to contain lowercase letters, numbers and hyphens,
1:16
and in general, stick with the verb plus ing form
1:20
the name of your skill.
1:21
For the description, you want to describe
1:24
not only what it does, but also when to use it.
1:27
And if there are specific keywords
1:29
that lead to agents triggering this skill,
1:31
make sure to lean into those.
1:33
In addition to the required fields that you have,
1:36
the agent skills specification allows for optional fields.
1:40
This could be the license, compatibility,
1:42
and arbitrary key-value pairs in your metadata.
1:45
What's important to note here
1:47
is that while there is a standard on agent skills,
1:50
there are some skills that you might come across,
1:53
some built by Anthropic, some others,
1:55
that don't follow this specification to a T.
1:58
The skills are in active development,
2:00
as is the specification for skills
2:03
as we work across many different model providers
2:05
and many different agent tooling ecosystems.
2:08
As we start to move past the YAML Frontmatter
2:10
and into the underlying body of the skill,
2:13
there are no underlying restrictions that we
2:15
have for the format of our skill.
2:17
However, when you think about building predictable workflows,
2:20
you want to make sure you have step-by-step instructions.
2:23
As we saw in other skills, especially the skill creator skill,
2:27
it's important to specify edge cases,
2:30
step-by-step instructions, and if there's a
2:32
reason for a step to be skipped,
2:34
be very clear why that is. In general,
2:37
keeping this to under 500 lines is best practice,
2:40
because we can always reference external files,
2:43
assets, scripts, when necessary.
2:45
In general, being clear and concise is valuable,
2:48
and using forward slashes is mission critical even when on Windows.
2:53
It's important to make sure the skill works across many different environments.
2:57
When you think about creating skills,
2:59
you want to think a little bit about how
3:01
much freedom you want to give to that skill.
3:03
Should we allow for general approaches and general directions,
3:07
or should we be focusing on a specific sequence?
3:10
You can imagine for following best practices,
3:13
we might want a low degree
3:14
of freedom, but for more creative outputs,
3:16
multiple colors, multiple styles, multiple fonts,
3:19
we can allow for that high degree of freedom.
3:22
As we start to think about more complex workflows with multiple skills,
3:26
breaking things down into sequential steps
3:28
is always more valuable
3:30
than having one very, very large
3:32
skill that tries to do it all.
3:34
These systems can handle 100+ skills.
3:36
It's important to make sure that they're named appropriately,
3:39
not confusing, and can be followed with a predictable pattern.
3:43
In the specification, there's room for optional directories.
3:47
And as we've seen with quite a few different skills,
3:49
there are subfolders for scripts, references, and assets.
3:53
Your scripts include any kind of code
3:56
that needs to be read and executed.
3:58
You also want to make sure
3:59
you have error handling and clear documentation.
4:02
Our references contain additional documentation or reference files.
4:05
And in general, it's often valuable
4:08
to instruct the skill to read the entire reference file
4:11
if it happens to be quite long.
4:14
Finally, we have underlying assets.
4:16
These could include templates for output, images, logos,
4:19
data files, schemas, and so on.
4:22
It's important to note that these directories,
4:25
scripts, references, and assets are following the standard of agent skills.
4:30
But you might come across quite a few different skills
4:33
that don't necessarily follow that particular standard yet.
4:36
The standard is rapidly evolving
4:38
and skills are also rapidly evolving.
4:40
So going forward, we'd expect that skills created follow this standard.
4:45
But you might come across some that have different folder names
4:47
and different conventions. Now that we
4:49
have a good sense of best practices,
4:52
optional directories,
4:53
and how to write production grade skills,
4:55
let's take a look at two examples of skills that we've created,
4:59
step through them, and then run them through the skill-creator
5:03
to analyze for best practices
5:05
and talk about evaluating these skills
5:07
to make sure we're ready for production.
5:09
So I'm in VS Code now.
5:11
And here we have two custom
5:13
skills that we're going to dive into.
5:14
The first one is a generating practice questions skill.
5:19
If we take a look at this
5:20
skill, we can see that the description
5:22
is for generating educational practice questions
5:25
from lecture notes to test understanding.
5:27
You can imagine you're a teacher or instructor,
5:29
you want to provide a particular format for input and output.
5:33
and you want to generate comprehensive questions to test understanding.
5:38
Let's step through this skill. To
5:40
start, we have supported formats for input.
5:43
We specify what particular libraries to use,
5:46
and we specify what text to extract.
5:49
We then follow with our question structure.
5:51
Again, we want to be very specific,
5:53
so we're specifying the exact order
5:55
that we want these questions generated in.
5:58
Starting with True/False, working all the way towards realistic applications.
6:03
For each of these questions, we have sub guidelines below.
6:06
We can see here that this skill is not more
6:08
than 500 lines of code.
6:11
But if it needed to grow larger and larger,
6:14
we can always include underlying files
6:16
to reference to if necessary.
6:19
As we take a look at some of these examples,
6:21
for true and false, even coding questions and so on.
6:24
We can see here, we're being very explicit
6:27
with the scope and the structure
6:29
and the required output for these particular questions.
6:32
As we dive deeper into that output format,
6:35
We specify that it depends on the user request.
6:39
And instead of giving direct examples
6:41
of every single kind of output,
6:43
we're actually referencing templates
6:45
inside of our assets folder.
6:47
If we're dealing with LaTeX or we're dealing with Markdown,
6:49
we specify exactly how we want that to look like.
6:54
For example, with Markdown, here's how true and false might look like.
6:58
With LaTeX, here is how our true and false
7:00
and examples might look like as we go through.
7:03
If you find yourself needing a particular kind of output format,
7:07
instead of putting that all in the SKILL.md,
7:10
reference it in an external asset or file.
7:13
Remember that these files, these templates are only being loaded when necessary.
7:18
So we can be extremely efficient with our tokens and context window.
7:22
by only loading the particular file
7:24
in the data format that we need.
7:27
If there are external resources that we need,
7:29
domain-specific examples, we can link to that as well,
7:32
like we do in the references folder here.
7:35
We're leaning into that concept of progressive disclosure
7:38
by only loading what's absolutely necessary
7:41
and referencing external files only when we need.
7:45
The second skill we're going to look at
7:47
is a skill for analyzing time series data.
7:50
We're going to provide a CSV
7:51
and we want to understand the characteristics
7:54
before forecasting quite a few different things.
7:57
What's important to note here is that
7:59
as we go through this particular skill,
8:01
there is a very particular deterministic workflow that we want to have.
8:05
We're making use of a few different
8:08
Python scripts to perform that particular action.
8:10
To start, we have a Python script
8:12
for visualizing the data that we're working with.
8:15
Plotting the time series, a histogram,
8:18
rolling stats, box plots, and quite a few more.
8:22
For working with autocorrelation, we also have
8:24
plots as well that we can draw.
8:26
Similarly with decomposition.
8:28
As we take a look at our diagnose.py,
8:31
we have underlying functionality for analyzing the data that we're working with.
8:36
While there are quite a few functions
8:38
here, I want to draw your attention
8:40
to what we do at the end when we run our diagnostics.
8:43
We make use of these functions to analyze data quality, distribution,
8:48
stationary tests, seasonality, trend, autocorrelation,
8:52
and finally, end with a transform recommendation.
8:55
What we have here is a predictable workflow
8:58
that we want to run each time in a particular order.
9:01
So let's go back and look at our skill
9:03
to see exactly how that's done.
9:06
First we're going to start with the format for our input.
9:09
We're going to be very explicit
9:10
for what we should be looking for,
9:12
the names of the columns and the particular data types.
9:16
Next we're going to move on to one of
9:18
the most important parts of this skill, the workflow.
9:20
Notice here, we're being extremely explicit with the steps that we have,
9:25
telling our particular skill and Claude
9:27
to run this exact script when we begin our diagnostics.
9:32
We then have the option for generating the plots necessary
9:35
and reporting this data to the user.
9:37
taking this data, finding what's in the summary.txt
9:41
and presenting the relevant plots.
9:44
We can also see here for answering
9:45
some of these questions that we might need,
9:47
we have an interpretation.md file for guidance.
9:51
As we take a look at some of the script options,
9:53
we can add additional flags if necessary.
9:55
And as we start to think about what's being output,
9:58
we can specify exactly the tree of files,
10:01
text files, images, and so on that we output.
10:05
We want to be extremely predictable with the data that's coming in
10:08
the operations that we perform, and then finally the output.
10:12
As always, if there are external references,
10:14
we can make sure to list those here.
10:17
And given that we have scripts that are dependent on Python libraries,
10:21
we need to make sure that
10:23
we highlight exactly what those dependencies are
10:25
and make sure that they're installed so that these scripts run correctly.
10:28
Now that we've taken a look at
10:30
these two custom skills that we've created,
10:33
let's see how they stand up when
10:34
we run this through the skill creator skill
10:37
and determine if we're following best practices.
10:40
We could do this in a couple environments.
10:42
We can go back to Claude desktop, but what I'd like
10:44
to show you is how we can use Claude Code with skills.
10:46
We're going to see this in
10:48
much more depth in a future lesson.
10:49
But right now, I'm going to open up Claude Code.
10:52
I'm going to install the necessary skill in our case
10:55
skill-creator. And then we're going to use two subagents in parallel
11:00
to evaluate our analyzing time series
11:02
and our generating practice question skills.
11:04
This is a really helpful way to just start the evaluation process
11:08
for how well we've done with writing these skills.
11:11
So we're going to go ahead and hop into Claude Code.
11:15
Unlike Claude AI, Claude Code does not come
11:17
with the built-in skills that include
11:20
skill creator. So we need to install those.
11:23
And we're going to do that using a marketplace.
11:26
So we're going to head over to our Marketplaces.
11:29
We're going to add a marketplace for anthropic/skills.
11:31
This is the repository that we saw earlier that contains two collections.
11:36
First, document-skills. These include processing Excel files,
11:42
PowerPoints, Word docs, and PDFs.
11:44
And the other collection are the example-skills.
11:47
These are some of the other ones that we saw
11:50
including the skill creator skill.
11:52
So let's install this in the project scope. Once we install that,
11:56
We're going to see that we need to restart Claude Code.
11:59
And we're also going to see that in our .claude,
12:02
we have in our settings.json
12:04
the enabledPlugins that includes these skills.
12:07
So let's go ahead and restart Claude Code
12:10
and see what skills we have.
12:12
And we can do that using the /skills command.
12:16
If we've done this correctly, we should see that we have
12:19
our skill-creator skill right here as expected.
12:22
Let's go ahead and make use of that skill.
12:24
So we're going to ask Claude Code
12:26
to use the skill-creator skill to evaluate
12:28
how these skills have followed best practices.
12:31
To do this a little bit faster,
12:32
we're going to use subagents in parallel
12:34
where each subagent is evaluating
12:36
each of the custom skills that I have.
12:38
In order to do this, we're going
12:40
to be prompted to use that skill, skill-creator,
12:42
which is great. It's working as expected.
12:45
We're going to successfully load that skill, read the necessary files,
12:49
and go ahead and dispatch our subagents to check for best practices.
12:53
We can see here, it's found the correct skills,
12:55
generating practice questions, analyzing time series.
12:58
And let's launch our two agents
13:00
to evaluate these skills against best practices that we have.
13:03
Alright, let's see how we did. Well, not too bad.
13:08
generating practice questions, nine out of ten.
13:10
We could improve a bit on the conciseness.
13:12
We've got some nice recommendations here.
13:15
The good news is we did even better on analyzing time series.
13:18
We can see some observations here
13:20
and some excellent job across avoiding duplication,
13:23
Frontmatter quality, and conciseness.
13:26
A really nice way to evaluate your skills
13:28
is to run them through this skill creator,
13:30
which includes best practices out of the box.
13:33
So we've run our skills through this skill creator
13:35
to analyze for best practices
13:37
in the underlying SKILL.md and associated files,
13:41
but how can we make sure the skills are working as expected?
13:44
Here's one example that we could build a harness around
13:47
to think about writing a unit test for our skills,
13:50
similarly to how we write unit tests for software.
13:52
So to start with our generating practice questions,
13:55
when we think about what the evaluation might look like,
13:58
we would start with a couple different queries.
14:01
Generating questions and saving it to a markdown file,
14:04
to a LaTeX file, to a PDF.
14:07
we can go ahead and make sure that we're passing in
14:09
the correct files in the correct format.
14:13
We can then make sure that
14:14
our expected behavior is what we need.
14:17
Using the correct libraries for PDF input,
14:19
extracting the learning objectives as we specified,
14:22
generating different kinds of questions
14:25
and following guidelines for those.
14:27
using the correct output structure,
14:29
using the correct output templates
14:31
that we saw in our assets folder,
14:33
making sure in certain data formats like LaTeX
14:36
that it's successfully compiling.
14:38
And then finally, making sure that our questions are generated
14:41
to the correct files and the right format.
14:44
We also would want to make sure
14:46
that we gather human feedback in this process
14:48
and that we test this across all
14:50
the different models that we're planning to use.
14:52
For our second skill for analyzing time series,
14:55
we make use of three different Python scripts.
14:58
So we're going to make the assumption
15:00
that we've already tested those Python scripts
15:02
with traditional unit tests in software.
15:04
Assuming that those scripts are doing what we want them to do,
15:07
let's now test that everything is happening
15:10
in the correct order with the appropriate
15:12
inputs and outputs and expected behavior.
15:15
The query you might have here is to analyze
15:17
and generate plots for some time series data.
15:20
we'd want to pass in some potential CSVs,
15:23
make sure that the Python scripts that we showed
15:26
for visualizing and diagnosing are run correct.
15:29
More importantly, making sure that all the steps in the workflow
15:32
are in the correct order.
15:34
we're asking for plots, we want to
15:36
make sure that that optional step is included.
15:39
We then want to return a summary, interpret those findings,
15:42
and finally, create a folder with all
15:45
the required files in their right place.
15:47
If you can remember, in the output,
15:49
we had a very specific location for different files,
15:52
different folders, and underlying assets.
15:55
Similarly to our other skill, we want to get human feedback
15:58
and test across the models that we use.
16:01
In the next lesson, we're going to take these two skills
16:03
and bring them into Jupyter notebooks
16:05
and use the Claude messages API
16:08
to run these skills using code execution tools
16:10
to produce outputs programmatically.

---

## Video 7: Skills with the Claude API (17 mins)

0:00
In the first lesson, you saw how skills work with Claude AI.
0:03
Now, we'll work with the Claude API
0:05
to test the two skills we made from the previous lesson.
0:08
To use skills with the Claude API,
0:11
we'll need to use the code execution tool and the files API.
0:15
This will equip Claude with file system access
0:18
for reading and writing files and with bash for executing code.
0:21
Let's get to it. We've talked quite a bit
0:24
about how skills work and how to create them.
0:27
And we talked a little bit
0:29
as well about the portability of skills
0:31
across different environments in the Claude ecosystem,
0:34
as well as many other agentic applications.
0:37
We started by looking at skills in Claude AI and Claude Desktop,
0:41
and now we're going to move to talk about
0:43
how to use skills using the Claude Messages API.
0:45
There are two things that are important to note.
0:48
First, skills that you create in Claude AI and Claude Desktop
0:52
are not shared in The Claude API or Claude Code.
0:56
The second important piece is that in order for skills to work,
1:00
we need the ability for Claude to execute code,
1:03
create and edit documents, presentations, PDFs,
1:06
and data reports, and work with a file system.
1:10
This is something that we're going to have to manually do
1:12
when we work with the Claude API.
1:14
And this is something that is actually configured for you
1:16
right away when using Claude AI and Claude Desktop.
1:20
In Claude Desktop or Claude AI
1:22
If I go to settings
1:24
and I take a look at the capabilities,
1:27
you can see here that there's a section
1:29
for code execution and file creation.
1:31
This is what we're going to talk about in more depth
1:33
when we work with the API directly.
1:35
But this is a setting that is enabled by default
1:39
that allows Claude to execute code, create docs, spreadsheets, presentations, and more.
1:43
This essentially gives Claude AI and Claude Desktop
1:46
a computer or a virtual machine
1:49
to execute code and perform all those tasks that make Skills happen.
1:53
If this is disabled, we'll actually see
1:56
that we need to turn this on
1:58
to even be able to use skills.
2:00
Now let's shift back and talk a little bit
2:03
about how this code execution tool and file creation works,
2:06
because we're going to need to enable
2:08
this manually when we work with the API.
2:11
When working with tools like Claude Code and the Claude agent,
2:15
you have direct access to a file system.
2:17
Whereas using the Claude API, we do not,
2:20
and need a container to execute code
2:22
and a file system to work with.
2:24
Claude AI and Claude Desktop,
2:26
that containerized environment and file system
2:29
is given to you and not something you have to implement.
2:32
At the end of the day, the functionality is all the same,
2:35
but the way in which we utilize skills is slightly different.
2:38
The skills themselves do not change,
2:41
the format of those skills do not change,
2:43
but depending on the environment that you're in,
2:45
you may utilize the way in which skills work slightly differently.
2:49
As we start to explore the Messages API,
2:51
we're going to use the code execution tool.
2:54
The code execution tool allows Claude to run
2:57
Bash or shell commands
2:59
to perform all these actions that we saw
3:02
when working with skills. Creating, viewing, editing files,
3:05
and writing code, all in a sandboxed environment.
3:08
The code execution tool
3:10
gives our application the ability
3:13
to have a separate dedicated container
3:15
to execute code and work with a file system.
3:18
as you've seen with all the things that skills can do,
3:21
that is mission critical for reading our skills,
3:24
executing code within those skills, and working with other files
3:28
that we might want to edit and view and create.
3:30
To give you a visualization of what this looks like,
3:33
when we include the code execution tool,
3:36
we give Claude an execution sandbox or a container.
3:40
When we ask Claude to create and execute files,
3:43
these are executed in a safe and isolated environment.
3:47
There are limitations for the RAM, the disk, the CPU,
3:51
and more importantly, there is no internet connection provided
3:54
and there are pre-installed libraries that you get out of the box.
3:58
So this does not work with every single kind of coding environment.
4:01
There are some limitations here to be mindful of.
4:04
At the same time, we also get access to a file system
4:06
that we can start adding directories to.
4:09
You might have even seen hints of that
4:11
when we worked with Claude desktop and Claude AI.
4:14
This limitation of no internet connection
4:16
is something that is specific to the Messages API.
4:19
When we're using the code execution tool
4:21
in Claude AI or Claude desktop,
4:23
we do have access to an internet connection
4:26
and we can download and install packages.
4:28
The Code Execution Tool works quite nicely
4:31
with another set of APIs that the
4:33
Claude API allows us to work with.
4:35
As you can imagine, when we're working with files,
4:38
adding, creating, writing, modifying files,
4:42
we need some mechanism for actually storing those underlying files.
4:46
The Claude API includes a set of APIs called the Files API
4:50
to upload and download files
4:52
that can be run and worked on inside of the container.
4:56
You can imagine a scenario where
4:58
the user asks to summarize some input
5:00
and save the summary to a text file.
5:03
We upload that input file,
5:05
send it to the container, download generated files
5:08
with this Files API. We're going
5:10
to be seeing this shortly in code.
5:12
When we see the IDs that we get back
5:13
from uploading and downloading files
5:15
and how this works nicely with skills
5:18
and our Code Execution Tool.
5:20
And this is exactly where skills come into play.
5:23
The library of skills that we get
5:26
out of the box in tools like Claude AI
5:29
or that we can include if we want using the API,
5:32
those live in a directory that are powered in the container.
5:35
As we start to read from this skills directory,
5:38
as we start to add information to our skills
5:41
or use those underlying skills to create new files
5:44
that we can download or upload,
5:46
this is where skills come into play.
5:48
And we're going to see a requirement when working with the API,
5:51
when we want to use skills, we need
5:53
to use the Code Execution Tool as well.
5:56
Now that we have a good
5:58
sense of what the Code Execution Tool
5:59
and Files API allow us to do,
6:01
let's see how to use this in action.
6:03
We're going to go and revisit the two previous custom skills
6:06
that we built for generating practice
6:08
questions as well as time series analysis.
6:11
So let's head over to a Jupyter notebook and explore this.
6:14
Right here, I have my two
6:15
custom skills that we've worked with before.
6:18
I also have a folder for
6:19
data that I'm going to be using
6:21
to analyze time series data.
6:23
I also have a folder for lecture notes that I'll be using
6:26
when I use my generating practice questions skill.
6:29
To get started in this notebook,
6:31
I'm going to load the environment variables that I need
6:34
as well as a helper to help
6:36
me find particular files from a directory.
6:37
We're going to see this in
6:39
action when we start using our skills.
6:40
To start, I'm going to begin using my generating practice questions skill.
6:45
So let's go ahead and take a look
6:46
at the first part that I need to do.
6:49
To begin, I need to upload the skill directory.
6:52
Here you can see we're using that files_from_dir helper function,
6:55
as well as the necessary beta
6:57
headers for skills. Once this is done,
7:00
I should be able to see the skill ID that I've created.
7:04
This betas list are particular headers that I add when
7:08
I make a request to the Messages API.
7:10
Under the hood, these are turning into request headers
7:13
to make sure that I'm getting the right data back
7:15
and communicating appropriately with the API.
7:18
To take a look at all the skills that I have,
7:20
I can use this .list method,
7:22
and I'm going to pass in a source of custom
7:25
so that we don't load all the built-in skills
7:27
and instead just confirm that I've created the ones as expected.
7:32
And here I can see the title,
7:33
as well as the unique skill ID
7:35
that I'm going to be using shortly.
7:37
In order for this to work as expected,
7:39
we're going to need to make use of the LaTeX file
7:42
where we're going to generate practice questions from.
7:45
Here, I'll use the Files API
7:47
to upload this particular LaTeX file.
7:50
make sure that it's set for reading
7:52
and then get back a file object.
7:55
I'll be using this file object in conjunction with the skills necessary
8:00
to make sure that it's all
8:03
working as expected. I'm using Sonnet here,
8:05
and I'm passing in the necessary beta headers, not only for skills,
8:09
but in order for skills to work
8:11
as expected when talking to the model,
8:13
I need to make sure I
8:15
have the code execution beta as well.
8:17
And since I'm sending a file here, we have to
8:19
make sure we have the files API header as well.
8:22
When working with skills, these skills are
8:24
set in a keyword argument called container,
8:26
and here is where I pass in the list of skills.
8:29
These could be custom ones or built-in ones.
8:32
As I create many different versions of the skills,
8:35
I can reference a particular timestamp
8:38
or just use the latest one that I have.
8:40
As I start to communicate with the model,
8:42
I ask it to generate practice questions
8:45
and then specify the file that I'm working with.
8:48
This file object was previously created
8:51
when I uploaded the LaTeX file.
8:53
We finally make sure we're bringing
8:54
in the correct tools for code execution.
8:56
and send a message to our API.
8:59
Now let's go take a look
9:00
at the response that we got back.
9:02
We can see here that there are multiple different pieces being used.
9:06
Tools on the server, code execution, additional tools being used,
9:10
and then finally, a bash code execution result.
9:13
To make this a little bit cleaner
9:15
to look at, let's add some nice formatting
9:17
so that we can go ahead and take a look
9:19
and analyze different text responses and tool use.
9:22
We're going to go ahead and see in this particular series
9:25
what's happening one step at a time.
9:27
When we take a look at what the response is,
9:29
which includes our text and our tool use and tool results,
9:32
the first thing the model is telling us
9:35
is it can help generate questions from these notes
9:37
and it's going to start by reading the skill file
9:39
and examining the lecture notes.
9:42
Notice here, it's detected the skill that it needs to use,
9:46
but it's only reading the SKILL.md
9:48
We're going to see later on if there
9:50
are additional files that need to be read,
9:52
we'll make use of that progressive disclosure.
9:55
We're also going to review in
9:56
our input that LaTeX file as well.
9:59
We're going to go ahead and see the underlying data
10:01
that comes from these files. This is the YAML front matter
10:04
that we've seen before, as well as the LaTeX
10:07
from our notes04.tex file.
10:09
Next, we're going to go ahead and check the markdown template
10:12
to use the proper structure because we
10:14
want our output to be in markdown.
10:16
Here is where we're going to leverage
10:18
a bit more of that progressive disclosure.
10:20
Here's where we're going to read inside of the assets folder
10:23
that markdown_template.md
10:26
We'll get back the response that we've read
10:28
and now we'll generate the questions
10:30
based on the lecture notes that we've passed.
10:32
Here we're going to use our code execution tool
10:35
to create a particular file.
10:37
We'll give that file text in markdown,
10:40
and we'll get back the result of that file.
10:42
We're going to go ahead and copy that to an output directory
10:46
and use our Files API to get back a file_id
10:49
that we can download later on.
10:52
Once we get back that result,
10:54
We can take a look at the underlying file that's been generated
10:57
and make use of that file ID to programmatically download it.
11:01
We can see here it's been saved and is ready for use.
11:05
Using that file ID that we saw above
11:07
Let's go ahead and download the file.
11:11
We'll go ahead and check in this response and
11:13
make sure that we have the file ID correctly extracted.
11:15
And if we have that, which we expect to do,
11:18
we should be able to download that particular file.
11:21
We'll go ahead and write to
11:23
a file called notes04.md with that content.
11:25
includes the file ID
11:28
as well as the necessary beta headers to communicate with the API.
11:32
We can see here, we've downloaded that notes04.md file,
11:36
and this is coming from the Files API
11:38
with the code execution tool,
11:40
all generated with the model and a skill.
11:43
Inside of this file that we've downloaded,
11:45
we can see that we're following those
11:47
exact parts that we had in the skill.
11:50
Starting with true and false questions,
11:52
moving on to explanatory questions, to coding questions,
11:55
and finally, to use case applications.
11:58
We can preview this in markdown
11:59
to see what that would look like.
12:01
And here we can see our
12:03
use case application, all the things necessary.
12:06
Now is a good time to evaluate this particular output.
12:09
Did we do exactly what the
12:10
skill wanted? It looks good to start.
12:12
bringing in some unit tests can
12:13
really take this to the next level.
12:15
If we need, we can go back and
12:17
modify the skill, just like we saw before,
12:20
using the API, the code execution
12:21
tool, and the Files API as well.
12:24
We also have the ability to delete skills programmatically.
12:27
In order to delete a skill, we
12:29
first have to find all of the versions
12:31
associated with that skill and then delete them.
12:34
Once those versions are deleted,
12:36
we should be able to delete the underlying skill. Right here.
12:41
Next, we're going to go ahead
12:42
and use our analyzing time series skill
12:44
alongside another skill.
12:46
This is going to look pretty familiar to what
12:48
we saw above, so let's go through these steps.
12:51
First, we're going to upload our custom skill.
12:53
get back a skill ID and
12:55
confirm that we've done that as expected.
12:58
Here, we can also see that
12:59
we're not loading only the custom skills,
13:01
we can see the built-in skills as well.
13:04
These should look pretty familiar, as we
13:06
saw them as well in Claude AI.
13:08
Next, we're going to go ahead and upload our input file.
13:11
This is going to be our retail sales CSV file.
13:14
We're going to build a message to send to the API,
13:17
and just like before, we're going
13:18
to go ahead and use our skill,
13:21
but here we're also going to include the docx skill as well.
13:25
We're going to use this because we want to
13:28
create a word doc summarizing the results and the plots.
13:30
So here we're seeing a combination of custom skills
13:33
with the skill ID that we have as well as the version.
13:36
and using Anthropic built-in skills
13:39
in this case, the docx skill.
13:42
We're passing in the same headers
13:43
that we had to pass in before,
13:45
skills, code execution, and the files API.
13:49
Now that this is finished running,
13:51
we can examine the particular type of response that we get.
13:55
We're going to see something similar to what we saw before,
13:57
but this time there's just a little bit more happening.
14:00
Let's go and see what's happening
14:02
under the hood with our nice formatting.
14:04
So here, the model is going to respond
14:06
by helping us analyze time series data.
14:09
And just like before, we're going to start reading
14:11
the entirety of these SKILL.md files.
14:14
We're going to read our custom skill as well as the built-in
14:17
docx skill, which we're going to need to use.
14:20
We can see the result of those include the content,
14:22
starting from the beginning of the file
14:24
and including the entire SKILL.md
14:27
Next, we're going to go ahead and examine the data
14:29
to run our time series analysis.
14:31
We're going to look at just
14:32
the first 20 lines of this CSV
14:34
to examine the names of the columns
14:37
and the type of data that we're working with.
14:39
Since this is working as expected,
14:42
we're going to go ahead and run the diagnostics
14:45
and create the visualizations.
14:47
These particular commands that we need to run
14:49
are coming directly from our skill.
14:52
Here is where we're going to go ahead, read those underlying files,
14:55
execute that code and hand that back to Claude to work with.
15:00
We're going to get back the result of these executions.
15:03
We're going to get that back for diagnostics as well as visualize.
15:07
We're then going to read the summary and diagnostics,
15:10
which is the result of our script
15:13
that comes in a file called summary.txt
15:16
Once we have that particular file created,
15:19
we can then go ahead and create a Word document.
15:22
The built-in docx skill
15:24
includes the correct content for how to work with Word docs.
15:28
We're going to go ahead and take a look
15:30
at how best to generate that document
15:33
and leverage progressive disclosure here.
15:35
We don't need everything from the docx skill,
15:38
just using a way to get to those markdown files.
15:41
Once we have that, we'll create a comprehensive Word document
15:45
using the skill necessary, execute the code to make it do that,
15:49
and generate the underlying Word document.
15:51
Once we have that Word document,
15:53
we'll copy that to the output directory
15:55
and just like we saw before, get back a file ID
15:58
that we can use if we want to download this Word document.
16:02
We can see a summary of what this data looks like.
16:05
And now we can download the file.
16:07
Similarly, we'll go ahead and find that file_id if it exists.
16:10
We're going to go ahead and download that particular file
16:13
with the necessary contents as a docx file.
16:17
If we take a look at what this looks like,
16:19
we now have a Word document
16:22
with our findings, our overview, our statistics.
16:24
We can see that we brought in those plots and visualizations,
16:27
as well as the statistical analysis that we've requested.
16:31
This is also a great time to not only evaluate
16:33
if what we're doing is expected in the skill,
16:36
but that we're doing this in a predictable fashion.
16:40
As we continue to evaluate, we can always
16:42
modify this skill as much as we want.
16:44
But all this data is coming in from the skill
16:47
as well as the docx skill.
16:49
to create this individual file.
16:52
Like we saw before, if we want to delete this skill,
16:55
we can list all the versions and delete all those versions.
16:58
And once those versions are deleted,
17:00
delete the underlying skill. In this lesson,
17:03
We've combined our knowledge of the Messages API,
17:06
the Code Execution tool, the Files API, and skills
17:09
to take our custom skills and work with them programmatically.
17:13
In the next lesson, we're going to move to Claude code
17:16
and see how to add our own custom skills
17:19
inside of a .claude folder
17:21
and build a more sophisticated command line application.

---

## Video 8: Skills with Claude Code (24 mins)

0:00
We'll now switch to Claude Code and
0:01
use skills for code generation, reviewing, and testing.
0:05
We'll also set up sub-agents and equip them with skills.
0:08
Let's have some fun. So far we've seen how to use skills
0:11
in Claude AI and using the Claude messages API.
0:15
Now let's talk about how to use skills
0:17
in Claude Code in a bit more depth.
0:19
The application that I'm using
0:21
is a command line application for creating to-dos
0:24
that need to be completed and listing them,
0:27
and eventually editing and clearing.
0:29
I'm going to show the CLAUDE.md file to
0:31
give you a sense of what this project does.
0:34
And now we're going to do a little demo
0:36
before we jump into each of the individual files.
0:38
In Claude code, you have the ability to create a claude.md file.
0:43
This file is created using the /init command or manually by the user.
0:48
This file is always in your context and specific to your project.
0:52
This is where you can specify general instructions
0:55
about the code base project you're working on, technology stack,
0:59
and things that Claude needs to know in every single conversation.
1:03
So again, we're building a command line task management application
1:06
using Python, Typer as our CLI framework,
1:10
using dataclasses, Rich, we're storing information
1:13
in a JSON file for persistence,
1:15
and using uv for dependency management.
1:18
Our architecture follows according to this pattern.
1:21
We've got our entry point and all of our commands
1:23
get their own individual Python file.
1:26
We set up our data class in our models.py
1:29
our logic for storing, serializing, deserializing in our storage.py,
1:33
and then to display things nicely in the terminal, our display.py.
1:37
We have a couple constants and then our tests.
1:40
We can see in this file, we
1:42
have our Priority, our Task as Data Models,
1:44
how data is persisted. And remember again for this CLAUDE.md,
1:48
this is data that is always available
1:50
in context in every conversation that we have.
1:53
This is useful information to help Claude figure out
1:56
where to find things and how best to structure information.
2:00
So with that in mind, let's hop
2:01
in and play around with this application.
2:03
First, I'm going to go ahead and activate the virtual environment.
2:07
So I'll source .venv
2:10
then activate.
2:12
Once I've got that set up,
2:14
make sure my dependencies are in order with uv sync.
2:24
And once I've done that,
2:26
I can actually start using this
2:27
task command directly in the command line.
2:29
If I take a look at the command,
2:31
I see I have commands like add and done and list,
2:34
as well as some additional options.
2:37
So let's go ahead and take a look
2:38
at the tasks that I have right here.
2:40
Right now, I have none of them that are found.
2:43
I'll clear the terminal so I can start from the top.
2:45
Let's go ahead and add a task.
2:47
Right here, we'll call this write the final report.
2:50
and we'll give this a priority of high
2:54
and we'll give this a date to be done with the following.
2:58
We can see here I've added that
2:59
successfully, so let's go take a look.
3:02
We've got our task right there.
3:04
our display.py doing some nice formatting of that information.
3:07
Now let's go ahead and complete it. I'll go
3:09
ahead and mark that as done with the correct ID.
3:12
And then if I go ahead
3:13
and take a look at my list,
3:15
I can see with that flag
3:17
that I have this task that is done.
3:20
The plan for this lesson here
3:22
is to add another command line command for edit.
3:25
So we're going to have to go to src
3:27
to task and add another command here for editing.
3:31
But we also want to make sure
3:33
that when we add these additional commands,
3:35
we're following the correct workflow.
3:38
We're following a proper way of adding commands the right way
3:41
to pattern match a bit of
3:43
what we've done in this code base.
3:45
In order to do so, we're going to be using
3:48
a skill here that we've added called adding CLI command.
3:51
Skills are defined inside of a .claude folder
3:54
followed by a folder called skills.
3:57
When we take a look at this skill,
3:59
first not only we can see that
4:01
this is available at the project level.
4:03
We can also create skills at the user level
4:06
in our home directory if we'd like as well.
4:08
For this example, we'll be focusing in project specific skills.
4:12
So let's dive into what's happening for this particular skill.
4:16
Just like we saw before, we have a name and a description,
4:19
and here we're going to really lean
4:21
into the particular coding styles and functionality
4:24
that we want when creating new commands.
4:27
We're going to start by identifying the workflow necessary
4:30
and creating files in the appropriate directories.
4:33
Just like we have commands for add and done and list,
4:36
we want to make sure that when we
4:38
make new files for commands, it lives there.
4:41
We also want to make sure that these commands are registered
4:44
in our __init__.py file
4:46
that lives in the command folder.
4:48
When we think about how to create different commands,
4:51
there may be lots of different kinds.
4:53
There may be commands that involve subcommands
4:55
or flags or additional arguments.
4:58
You can provide plain text instructions to Claude,
5:01
but especially for coding examples,
5:03
Claude does really well when you tell it exactly
5:05
what pattern and style you want to follow.
5:08
In the Typer library, there are
5:10
many different ways of accomplishing particular tasks.
5:12
For example, there are many different ways of adding
5:15
type annotations to arguments that are being decorated.
5:19
In this particular case, this is the convention we want to follow
5:22
as it's a little bit more modern.
5:24
You can imagine in libraries and code bases that you use,
5:27
there are many different ways of doing things.
5:29
But what's useful about skills is it gives
5:32
us that predictable workflow for a set of tasks.
5:35
We also want to make sure we're using this display object here
5:39
and calling methods like success and info
5:41
to make sure that when we add a command,
5:43
we're not only executing the business logic,
5:46
but displaying the correct information to the user at the end.
5:49
When we work with flags, we want particular shorthand,
5:52
we want particular longer ways of addressing it.
5:54
We want to make sure that there's help text as well.
5:57
All of these pieces, type annotations, default arguments,
6:00
certain return values, are valuable to add in your skill
6:03
so that you know how best
6:05
to pattern match and follow predictable workflows.
6:08
As we think about commands with subcommands,
6:10
not only can you see here
6:12
how we want to structure individual commands,
6:14
but also how we want to display
6:17
when things like migrations or versions are changed.
6:20
As we imagine commands that might be destructive,
6:22
as we start adding functionality to clear,
6:24
we might want to specify what kind of delete we're doing.
6:28
If we choose to do a hard delete,
6:30
we want to make sure that we confirm
6:31
before we go ahead and delete that particular task.
6:35
This pattern can be followed as Claude starts to see
6:38
additional commands that might need to involve some kind of deletion.
6:41
As we think about registering, we want to be intentional
6:44
about how to add single commands and command groups.
6:47
So not only are we giving
6:49
Claude instructions for how to register commands,
6:51
we're being very specific with what conventions to follow.
6:54
And finally, as we talk about conventions,
6:57
here's where we can lean into requirements on our doc strings,
7:00
being mindful of exit codes and following constants that we have,
7:04
being mindful of commands that are
7:05
destructive. This is a really useful place
7:07
so that when we build our predictable workflows,
7:10
we know exactly what conventions we're following.
7:12
These are not conventions that have to exist
7:14
everywhere in the code base and
7:16
have to be loaded everywhere in context.
7:18
If so, we could put them in the CLAUDE.md.
7:20
But in this case, just for adding individual commands,
7:23
there's a subset of conventions to follow.
7:25
Let's only load those when necessary.
7:27
And not only are we using generic naming like CLI app,
7:31
we can use this skill across any
7:34
platform that follows the agent skills convention.
7:36
And depending on whatever CLI you're building,
7:38
if you want Claude to follow these particular patterns,
7:41
this skill can easily be adapted to do that.
7:43
Now that we have a skill for adding CLI commands,
7:47
let's also make sure that when we start to do
7:49
this particular workflow of adding commands,
7:52
we're being mindful of testing and
7:54
also validating the commands that we write.
7:56
This is another great use case for another skill.
7:59
In our second skill, for generating CLI tests,
8:02
we generate pytest tests for Typer commands.
8:06
We include here what kinds of fixtures we want,
8:09
how to handle edge cases, and
8:11
this is really important that we add
8:13
what to do and how to trigger this particular skill.
8:16
You can see here, use when the user asks to write tests,
8:20
for my CLI or add test coverage.
8:22
It's always important to be very explicit not only
8:25
in what the description is, but how
8:27
Claude can detect how to run it.
8:29
Similar to other skills, we specify the workflow that we want.
8:33
When writing tests, it's often best practice to leverage fixtures.
8:37
You can think of fixtures as information
8:39
that is run each time as you arrange your tests
8:43
to set up information, to set up dummy data,
8:46
as well as any kind of mocking or test infrastructure
8:49
that you need for each of the tests that you write.
8:52
For example here, we specify what our temporary storage might look like
8:56
and we specify what some sample data might look like.
9:00
As we run each of these tests, this information will be exposed
9:04
to allow us to arrange and set up the tests necessary
9:07
when we test individual files, folders, and workflows.
9:11
As we take a look at the
9:13
test structure, we're following a pattern of arranging
9:15
like we mentioned with our fixtures, invoking some kind of action,
9:18
and then asserting that the result is the case.
9:20
Right here, we're simply trying to build patterns
9:23
that Claude can use and follow when this skill is leveraged.
9:27
We can continue on with how we
9:28
want this test runner to be done.
9:30
and how to test scenarios by a command type.
9:32
As we read, as we add, here are examples
9:35
for what we want our test to look like.
9:37
As with many testing libraries,
9:39
there are lots of ways to accomplish a similar kind of task.
9:42
For these examples, here is the pattern we want to follow.
9:46
As we wrap towards the end of this skill,
9:48
we want to think a little bit about edge cases to cover.
9:51
When writing tests, we want to think about invalid input,
9:54
any kind of state, confirmation, or what happens
9:57
when things are not found or don't exist.
9:59
We want to make sure that we're following a checklist as well
10:02
when we go ahead and write our tests.
10:05
And then finally, to make sure we're running tests correctly,
10:08
providing the correct commands as well as how to run
10:10
in a verbose mode and for specific files.
10:13
The last skill that we have
10:14
here is to wrap up and review
10:16
and make sure that we're executing the commands as expected.
10:19
Once we've generated the tests and the tests are running,
10:22
let's make sure we're following the correct conventions.
10:25
Just like we saw with other skills,
10:27
there are ways in which we can execute the task necessary
10:30
and then come back and validate that things are working as expected.
10:33
As we think about reviewing these commands,
10:36
not only do we think about the underlying structure,
10:38
is this in the right location? Is this using the right decorator?
10:42
Is this registered correctly? But we're also making sure
10:45
that some of those practices we wanted around type annotations
10:48
or options for parameters or flags when possible, always are included.
10:53
It's often helpful to provide positive and negative examples.
10:56
So as we mentioned, using this Annotated type
10:59
versus a different kind of way to type your arguments.
11:03
As we think more about error handling and output,
11:06
we make sure that this checklist exists
11:08
so that the skill can go through and confirm
11:11
that all of these pieces are as expected.
11:14
We're not telling Claude how to perform
11:16
these actions like adding commands and generating tests.
11:20
We're making sure that it's working as expected.
11:22
You can think of this like an evaluation almost
11:25
for the other skills that we have and
11:27
including this skill as part of our workflow.
11:30
As we take a look at the bottom,
11:32
making sure that our best practices are followed,
11:34
as well as examples of mistakes
11:36
we might see and fixes for those.
11:38
As we take a look at the output format of the skill,
11:41
we want to make sure that all of our checklist is addressed,
11:44
including a summary and suggested fixes.
11:47
It's very useful to have this underlying review
11:49
so that when features are finished,
11:51
we can start by taking a look at this review,
11:53
include this even as part of our code review,
11:56
make sure we're building production grade features,
11:58
backed by tests, following best practices.
12:00
With that in mind, let's start
12:02
to put all of these skills together.
12:04
The first thing we're going to do
12:05
here is to add a new command
12:07
that allows us to edit individual tasks.
12:10
We're going to want to make
12:11
sure we edit the title and priority
12:12
and pass in an ID that is valid.
12:15
Now, let's hop into Claude Code and use these skills.
12:19
To make sure that I've registered these correctly,
12:21
I'm first going to just type in /skills.
12:25
This is going to list the available skills
12:27
that I have to me. These are project skills.
12:30
We also mentioned we can add skills in our home directory,
12:33
but right now we're just dealing with project skills.
12:35
We can also see the amount
12:37
of tokens that these skills are taking
12:39
as we just think about the name and description necessary.
12:42
When you create a new skill in Claude Code,
12:44
you want to make sure that you close Claude Code
12:47
and open it up again so that skill can be identified.
12:50
So if you find yourself looking at your list of skills
12:53
but you're missing the one that you might have just created,
12:55
make sure to close that instance of Claude Code,
12:57
open it up again and you should be in good shape.
13:00
Now that our skills are loaded correctly,
13:03
let's go ahead and add a new edit command
13:05
to allow users to edit the title and priority.
13:08
We're adding a little example here
13:10
and ensuring that we follow the conventions
13:12
for creating a new CLI command. So let's give this a shot.
13:16
We can see here that Claude Code is prompting
13:19
to use the adding-cli-command skill.
13:21
And that's great. We'll go ahead
13:23
and make sure that in the future,
13:24
it doesn't prompt us to do so.
13:26
We can see here, we're going to read
13:29
the existing files and storage to understand the convention,
13:31
as well as take a look
13:33
at examples of other commands for reference.
13:36
Now that we know the conventions, let's
13:38
go ahead and create that particular file.
13:40
We can see here there's a new file edit.py being created,
13:43
and we're going to go ahead and make that change.
13:46
We'll see here edit.py appears
13:48
and we're now going to register that command,
13:51
following the order that the skill has set out for us.
13:54
We can see here that the command is being registered
13:56
inside of our __init__.py as expected.
13:59
We're going to go ahead and make that change as well.
14:01
So we'll go ahead and let it proceed and run this command
14:04
to test out and make sure it's working as expected.
14:07
Looks like we're seeing what we expect and that's in good shape.
14:11
So now going to run the add command and
14:13
then go ahead and run the
14:15
list to make sure we've added successfully.
14:17
It's seeding some data so that we can
14:19
then make sure the edit command works as expected.
14:22
We'll go ahead and edit that particular task.
14:24
And we'll see here that we didn't specify a title or priority.
14:28
We'll then go ahead and put in that title.
14:30
And here, we'll see that edited as expected.
14:34
It's going to ask me again to edit this task,
14:37
and this is going to happen over and over
14:39
as we start to test all kinds of examples.
14:42
And while I could proceed over and over again,
14:44
we can imagine that this might start to
14:46
fill up the context window quite a bit,
14:47
and if this were a larger scale system,
14:50
maybe very time intensive and even compute intensive.
14:53
So what we're going to do here is something slightly different.
14:56
We're going to leverage the functionality
14:58
that Claude Code has for using sub-agents.
15:01
We're going to have one sub-agent to review code
15:04
and follow the criteria so that the
15:06
main agent can focus on the development.
15:09
We're then going to have another sub-agent
15:12
to generate and run the tests using the skill that we have.
15:15
What's going to be useful about this
15:17
is that we can have the main agent focus on development,
15:19
while sub-agents in their own context window
15:23
focus on generating the tests and reviewing the code.
15:26
We can then take the feedback and tests generated,
15:28
bring it back to the main agent,
15:30
with a much more context-efficient approach.
15:33
It's important to note that sub-agents
15:35
do not inherit skills from a parent,
15:37
so we need to be explicit with the skills that we give
15:39
to each sub-agent that we make.
15:42
There are multiple ways of passing skills to sub-agents.
15:46
One way we're going to show you is being explicit
15:48
with the name of the skill in the sub-agent.
15:51
Another option that we'll link in the notes
15:53
is where you can provide the exact agent name
15:56
and how best to run it from the skill directly.
15:59
With that in mind, let's go ahead and create our sub-agents.
16:04
The first agent we're going to make is our code reviewer.
16:07
And we're going to create these agents using the /agents command.
16:11
We're going to create a new agent.
16:13
We're going to do that on a project basis,
16:15
but instead of generating with Claude,
16:17
we're going to follow a manual configuration
16:19
so you can see what it looks
16:21
like to add a name, description, tools,
16:23
and the most importantly, skills for each of our agents.
16:26
The first one I'll make, we'll call code-reviewer.
16:29
This will be the unique identifier for our
16:30
agent, and then we'll pass a prompt to it.
16:33
We're going to paste in a prompt that
16:35
we'll take a look at once we've created this,
16:37
but it's going to look very familiar to how we review
16:40
and how we're specific and actionable in the
16:42
insights we make when doing the code review.
16:45
We're going to go ahead and give this agent a description
16:47
for when it should go ahead and be used.
16:50
We're going to review for code quality, security, and so on.
16:53
We're going to try to make this agent as generic as possible
16:56
for the set of tools that we want here.
16:59
We want to be very specific with
17:01
the tools that our sub-agent has access to.
17:03
So we'll make sure that if
17:04
there's code that needs to be executed,
17:06
we give it Bash, Glob and grep for finding files,
17:09
and Read to read underlying files that we're going to be reviewing.
17:14
Once we've selected these tools, we can go ahead and continue.
17:18
We'll decide to inherit from the
17:19
parent with the model that we use.
17:21
And we'll go ahead and give this a color of purple.
17:25
Once we've got this set up,
17:26
we'll go ahead and save this agent.
17:28
We can see here now in our agents folder
17:31
that we have a code reviewer agent to work with.
17:34
We've got the code reviewer, a description, tools,
17:37
and all the wonderful pieces that we added.
17:39
It's now time to make sure we specify the skills
17:41
that we want this sub-agent to use.
17:45
We'll do that using the skills field
17:47
and specify the name of the skill that we're working with.
17:51
In our case, reviewing-cli-command.
17:55
Before we create our next agent, let's do a quick review
17:58
of what we made here. Our agent
18:00
has a name and description, tools available,
18:02
a model that we inherit, a
18:04
color, and skills that we brought in.
18:06
We can add multiple skills, but right
18:08
now we're going to stick with one.
18:09
In our prompt, we mention it's a code reviewer ensuring high standards.
18:14
As we specify what this agent is, we specify when it's invoked,
18:18
general quality checks. If we're working with Python,
18:21
how to be intentional, CLI commands the
18:24
same way, and a particular output format.
18:26
Like we mentioned, this agent is a bit more generic.
18:29
And while we're using it in the context of our specific application,
18:32
skills can help us be more particular.
18:35
But this agent might need to be
18:37
used across a different variety of applications,
18:39
so we want to be a little bit
18:40
more generic with what we're trying to do here.
18:42
It's important to note that skills operate
18:44
slightly differently as sub-agents in Claude Code.
18:48
When this sub-agent is dispatched and created,
18:51
the skill is not only loading the name and description,
18:55
but the entire SKILL.md
18:57
The skills are pre-loaded when the agent is dispatched.
19:00
If there is additional progressive disclosure,
19:02
reading of other files or other commands, that is not done.
19:06
but the entire SKILL.md is read
19:09
when the sub-agent is dispatched.
19:11
Now that we've got our code reviewer agent,
19:14
let's add another agent for generating and running our tests.
19:18
Let's go ahead and make our second agent.
19:20
We're going to go create a new agent
19:22
in our project using the manual configuration.
19:26
and we'll call that test-generator-runner.
19:29
We're going to go ahead and add a
19:30
prompt here that we'll review a little bit later,
19:32
but it's going to follow similar patterns to what
19:34
we saw with the other agent that we made.
19:37
We'll go ahead and specify a description for this agent,
19:40
where we'll specify that it should
19:42
run tests and generate them if missing.
19:44
When the user asks to test or run tests,
19:47
let's go ahead and make sure that this agent is dispatched.
19:51
Like we saw before, instead of giving access to all tools,
19:54
let's go to our advanced options.
19:56
In our advanced options, we're going to
19:58
go ahead and disable all of our tools.
20:00
and here we'll make sure we have a
20:03
Bash tool, Glob and Grep, Read as well.
20:05
But we're also going to need to Edit and Write individual files,
20:08
and in our case, Edit files that may already exist.
20:12
Once we've got these tools set up,
20:14
let's move on, talk a little bit
20:16
about the model we're going to be using.
20:18
Just like before, we'll inherit from the parent
20:20
and we'll go ahead and use yellow for this sub-agent.
20:23
This looks good to us, so we'll go ahead and save it.
20:26
Once we've created this agent, we also want to make sure
20:30
we specify what skills are being used.
20:32
In this case, the skills that we're going to be using
20:35
is the generating-cli-tests skill.
20:39
Again, we could add multiple skills,
20:41
but in this case, we're just going to use that individual one.
20:44
As we saw before, We specify when it's invoked,
20:47
we show how to discover tests
20:49
and the output format that we want,
20:51
and then some underlying rules to make
20:53
sure that things are working as expected.
20:55
And just like our other agent, to be
20:57
a little bit more generic and lean on skills
20:59
to provide consistent workflows.
21:01
Now that we've created our sub-agents and our skills,
21:04
let's put this all together to make
21:05
sure that when we add new commands,
21:07
we dispatch sub-agents when necessary,
21:09
using the skills that we want.
21:12
Let's go ahead and start by using our code-reviewer subagent
21:15
to review the edit.py command that we made.
21:19
This should not only dispatch the subagent,
21:21
but also make use of the
21:23
skill that we provided to that subagent.
21:25
we're going to see here that
21:26
the code reviewer agent has been dispatched.
21:29
And now we're going to go ahead and
21:31
use the necessary skills and tools that we've defined.
21:35
We can see here what's working and what's not working.
21:38
No critical results, but we've got some warnings.
21:40
issues to fix and suggested fixes.
21:43
We can go ahead and use the
21:45
main agent to implement those if we'd like.
21:47
We're then going to use our test runner sub agent
21:50
to generate the tests for our edit.py command. So we'll go ahead
21:53
and make sure that we're referencing the edit.py file
21:58
and go ahead and dispatch the second sub-agent.
22:02
We can see here it's generated the necessary commands
22:05
and it's prompting me to make sure
22:06
that we want to make this edit.
22:08
So we'll go ahead and do
22:10
so as we add tests for editing.
22:12
I can confirm that these tests
22:14
are working using this command uv run.
22:17
And then we'll go ahead and run
22:18
all of our tests with verbose mode
22:20
to make sure things are passing and there are no regressions.
22:23
Once this is done, we can see
22:25
that all of our tests are passing,
22:27
none are failing, and here's a summary as well.
22:30
We made use of two different sub-agents, leveraging multiple skills,
22:34
and as we start to add more features
22:36
and functionality, we can put these all together.
22:38
The next thing we're going to do
22:40
is see our code reviewer sub agent
22:42
and our test runner sub agent in action.
22:45
Let's imagine there's a clear.py file,
22:47
a new command that's been added by someone on the team
22:49
who hasn't followed best practices and maybe didn't use
22:52
all the skills and infrastructure that we set up.
22:55
We're going to go ahead and use our code reviewer sub agent
22:58
as well as our test runner sub agent
23:01
to figure out how best to fix the clear.py file.
23:05
We're going to dispatch our code reviewer
23:07
to review the clear.py command.
23:10
then we're going to use our test generator runner
23:12
to generate the test necessary for this command.
23:15
We'll validate finally that things are working as expected,
23:18
and make sure all the tests are passing
23:20
and following the best practices that we've standardized.
23:22
We can see here there are
23:24
quite a few issues and some warnings.
23:25
Now that we found these issues, let's make sure that
23:28
the main agent is reading the files and fixing them.
23:30
We're going to want to make sure
23:32
that we allow for these edits to clear.py.
23:34
And here we can see things like displaying things to the console
23:37
are done using the correct methods like
23:40
display as mentioned in our best practices.
23:42
We also want to make sure that we're registering this command correctly
23:45
inside of our __init__.py
23:47
The main agent itself is not adding additional context
23:50
for the reviewing and generating tests.
23:53
It's simply taking the output of
23:55
the sub-agent to better execute these tasks.
23:57
Next up, it's time to generate tests for the clear command
24:00
that is following our best practices.
24:03
We can see here it's adding
24:04
a file to test this clear command.
24:06
Let's go ahead and approve that. Now that we've created this file,
24:10
let's go ahead and run the
24:12
tests, make sure they're working as expected.
24:15
And now we can get a summary of what's been completed.
24:17
Six critical issues, four warnings, and all of them fixed.
24:21
Instead of using incorrect methods,
24:24
instead of using flags that are
24:25
not the right format that we want,
24:27
incorrect exit codes, we fixed quite a few different issues.
24:31
We've then added tests on top of that
24:33
to make sure that we're confirming that
24:35
all these best practices are done as expected,
24:37
and the functionality is working that we like.
24:40
In the next lesson, we'll shift away from Claude Code
24:42
and move to the Claude Agent SDK
24:45
and showcase how to use skills when building your own agents
24:48
using the same harness that Claude Code uses.

---

## Video 9: Skills with the Claude Agent SDK (20 mins)

0:00
In this final lesson, we'll create a research agent
0:01
using the Claude Agent SDK.
0:04
The agent will use a skill to create a learning guide
0:07
for an open source tool based on its documentation,
0:10
GitHub repo, and web search.
0:12
Let's go. Now that we've seen how to use skills
0:16
on the web with Claude using the messages API
0:19
and Claude Code, let's talk about
0:21
how to use skills with the Claude Agent SDK.
0:24
As a refresher, the Claude Agent SDK
0:26
is a programmatic way of building your own
0:29
agentic applications that use the same
0:32
internal harness that Claude Code does.
0:34
What we're going to be building
0:36
here is a general purpose research agent.
0:38
The main agent is going to be able to research information
0:41
from multiple sources and synthesize a summary.
0:44
It will dispatch three different subagents
0:47
for analyzing documentation,
0:49
analyzing and downloading repositories,
0:51
and researching information by searching the web.
0:54
Let's take a look at those prompts, and
0:56
then we'll take a look at a Skill
0:57
that's used to guide the Main Agent with a research methodology
1:01
and what needs to be extracted and synthesized.
1:04
To start, we have our main agent prompt.
1:07
This is the orchestrator that has access
1:09
to three available subagents with the following capabilities:
1:12
finding information from documentation,
1:15
analyzing repository structures,
1:17
finding articles, videos, and community content to bring it all together.
1:20
In this particular application, we mention that if the Skill is provided,
1:25
we want it to follow a particular pattern.
1:27
It's possible that Skills may or may not be provided
1:30
for the application we're building,
1:32
but in our case we're going to provide one.
1:34
If the skill matches the user's request,
1:37
we need to follow that skill's instructions precisely.
1:40
Since we're starting from scratch with this agentic application,
1:44
we want to be very intentional about
1:45
what to do when skills are provided
1:48
or when they're not. As we continue,
1:50
we have a couple high level delegation guidelines
1:52
for how to spawn subagents and after receiving results,
1:55
how to synthesize all of those pieces of information.
1:59
Let's briefly dive into some of the prompts for our subagents.
2:02
For the documentation researcher,
2:04
we'll have access to WebSearch and WebFetch.
2:07
We provide a process to locate documentation.
2:09
particular input formats, guidelines, and an output
2:12
to return findings in a certain way.
2:15
For the repository analyzer, we also provide WebSearch to find repositories,
2:19
Bash commands to clone and run git,
2:22
and then the ability to read and find
2:23
files and data within files.
2:26
Similarly, we provide a process,
2:28
an input format, guidelines, and an output.
2:31
Finally, our Web Researcher
2:33
makes use of WebSearch and WebFetch as well.
2:35
This allows us to search for content relevant to that topic
2:39
and to receive extraction instructions as well from the main agent.
2:43
We also provide guidelines as well as an output format that's necessary,
2:47
and if no output format is specified, follow a default structure.
2:51
All of these prompts will be used together
2:54
when we set up the code necessary to make our agent work.
2:57
Finally, let's talk about the skill we're going to be using here.
3:00
We have a skill named learning-a-tool.
3:03
The purpose of this skill here is to guide the main orchestrator.
3:07
We will not be using the skill in our individual subagents,
3:11
but we're using this skill as
3:13
a way to create a predictable pattern
3:15
so that the main agent knows the ideal workflow
3:18
and what and how to dispatch subagents.
3:21
We give the skill a name and a description.
3:23
And in this case, we want to create learning paths
3:25
for programming tools, define what information should be researched,
3:29
and specify how best to follow an approach to researching
3:32
all the way towards creating a comprehensive learning path.
3:36
To start, we have a very particular workflow that we have here.
3:40
We start with a research phase and we specify for official documentation
3:44
for that subagent exactly what to look for.
3:47
For the repository analyzer, a similar kind of approach.
3:51
And for our web researcher, very similar as well.
3:54
So we're using this skill to provide a constant and predictable workflow
3:58
for how best to work alongside
4:00
the subagents that the main agent has.
4:02
Once that data is given to us,
4:04
we then organize that content into progressive levels.
4:08
Here, we're using progressive disclosure
4:10
to lean into loading another markdown file
4:12
as the source of truth. In our progressive learning file,
4:16
we can see there's quite a bit
4:17
around the individual levels that we want.
4:19
starting from an overview and motivation,
4:22
all the way towards installing core concepts,
4:25
practical patterns, and then where to go next.
4:27
This progressive learning allows us to build levels
4:30
so that we know how to start from the beginning
4:33
and know eventually where to go deeper.
4:35
While this initial skill is useful for learning a tool,
4:38
you can also imagine that we might have additional skills
4:41
for maybe comparing one tool with another
4:43
depending on the data that we're working with.
4:46
As we move towards the additional phases of working with this skill,
4:50
we take that data and specify
4:52
a structure, and then specify an output.
4:55
We're very, very particular with the exact format that we're working with.
4:58
The goal here is to get access to a learning environment
5:01
that gives us an overview, resources, a path,
5:04
and code examples.
5:06
The goal here is to combine
5:08
the research from all of our subagents
5:10
into a particular output format that we want
5:13
and do that with consistency and predictability.
5:15
Now that we've seen at a high
5:17
level of the application we're going to build,
5:19
there's one last piece that we'll layer on.
5:21
We can imagine that we want to take
5:23
the output and write it to a centralized place
5:25
that we can share with teammates that might have a nicer interface.
5:28
And to do that, we're going to use Notion.
5:31
to connect to Notion, we're going to use an MCP server
5:34
and bring in the tools necessary to go ahead and execute that.
5:38
Now that we've examined the underlying prompts for our Main Agent
5:41
and Subagents, as well as the Skill we're going to be using,
5:44
Let's go ahead and begin by running uv init
5:48
and initialize a project and add the necessary dependencies
5:51
like claude-agent-sdk, python-dotenv, and asyncio.
5:57
Once we've installed these dependencies,
5:59
let's go ahead and create a file called agent.py.
6:03
So I'll go ahead, make a new file, call that agent.py.
6:07
Inside of our agent.py, I'm going to be adding the necessary code
6:11
To just get started with a small example
6:14
using the Claude agent SDK.
6:16
The boilerplate here brings in asyncio
6:19
to run this environment, dotenv to load environment variables,
6:23
And then from our utils, the display_message function.
6:27
Just to give some context, display_message
6:30
gives us a bunch of helpers for truncating and formatting input,
6:34
and it gives us a nice way to visually display
6:36
information from the main agent and the subagent.
6:39
This is very similar code to what we saw
6:41
when we worked with the API
6:44
and we got that nice output for what's happening
6:46
in each tool action and iteration.
6:50
To start, we set up our Claude agent.
6:53
We pass in a system_prompt here. This is going to change.
6:56
We pass in allowed_tools. This is also going to change,
6:59
but we just want to start with the basics here.
7:02
To get started with a simple conversation, we set up a loop.
7:05
accept some user input, run that through our model,
7:09
and take back the response and send that back to the user.
7:12
Let's go and see what that looks like.
7:14
I'm going to open the terminal again.
7:17
And we're going to go ahead and run uv run agent.py.
7:21
This is going to provide a terminal environment to us
7:23
where we can start a conversation.
7:26
I'll just start by asking, how are you?
7:29
In this case, I'm not going to
7:30
get a ton of valuable information here
7:31
because I just have a helpful assistant.
7:34
So what we're going to start layering on now
7:36
is the ability for our agent to get access to MCP servers
7:40
and the correct tools as well.
7:43
Let's go ahead and make some modifications to our main function.
7:47
Like we mentioned, the allowed_tools are going to change.
7:50
So what we're going to start doing
7:51
is adding the tools that our subagents need to use
7:55
so that they can be working as expected.
7:58
Read-only tools like read and Grep and Glob are allowed by default.
8:02
But when we want to start doing things like writing files,
8:05
searching the web, and executing commands by bash,
8:07
we need to pass that in explicitly.
8:10
So we'll bring in the Write tool, the Bash tool,
8:14
and our WebSearch and WebFetch tools.
8:18
We saw previously that our subagents
8:20
are going to be making use of these particular tools.
8:23
Our agent that's analyzing repositories needs Bash
8:26
to run git commands and writing files,
8:28
and our docs researcher and web researcher
8:30
will make use of searching and fetching.
8:32
Now that we brought in these tools,
8:34
the next thing we're going to add
8:36
are mcp_servers to connect to.
8:38
We'll use the mcp_servers keyword argument
8:41
and specify the name of the MCP server,
8:43
which in our case is notion. We're going to pass in
8:47
some default configuration.
8:49
And we're going to specify the command to run the notion server
8:53
alongside a notion environment variable that we have.
8:57
So we're going to make sure before
8:59
we go ahead from our .env file,
9:02
load in our notion token and import the OS module
9:06
to make sure that we can read that file correctly.
9:09
Now that we've loaded our MCP server correctly,
9:11
we need to make use of the tools that Notion provides.
9:14
If we would like, we can ask Claude right now,
9:17
what are all the tools that you get from this MCP server?
9:21
Or, we can go ahead and add those explicitly.
9:24
by using mcp, the name of our
9:27
server, followed by the name of the tool.
9:29
In this case, we're going to be using
9:31
all of the tools that Notion provides to us.
9:34
We need to make sure that this mcp_notion_* exists in allowed_tools
9:39
so that we can give the main
9:40
agent permission to use this set of tools.
9:43
We can explicitly add the name of the tool
9:45
or in our case, we're just going to include
9:47
all the tools available that mcp_notion provides to us.
9:50
Now that we've set up our mcp_servers and our allowed_tools,
9:54
let's go ahead and bring in our subagents and definitions for them.
9:58
We mentioned that our system_prompt is going to change.
10:01
And to start, we're going to go ahead
10:03
and load all of the prompts that we have.
10:06
We'll bring in a constant and a helper function
10:09
that we have to load all of these prompts.
10:13
We're going to go ahead and call that function
10:15
to go ahead and bring in these prompts.
10:17
inside of our main function.
10:20
We're going to make use of these
10:21
markdown files to load in the text necessary
10:24
and pass them to our agent options.
10:27
Before we go ahead and update the main agent,
10:29
we're going to add a dictionary that
10:31
references all of our agents with a definition.
10:34
We're bringing in the AgentDefinition class,
10:36
which we'll want to make sure we import correctly.
10:40
We can see in the AgentDefinition,
10:42
we have a description for our subagent,
10:44
a prompt that specifies the instructions for the agent,
10:46
and then the tools that we want that agent to use.
10:49
similar configuration to what we did in Claude code.
10:53
You can see here, we still need to use our main_agent_prompt
10:55
as well as this dictionary of agents.
10:59
So we'll update our system_prompt
11:01
with the main_agent_prompt.
11:03
and then we'll make sure to pass
11:05
in an additional keyword argument of agents
11:07
that references our dictionary with our agent definitions.
11:11
As you can see here, our researcher,
11:13
our analyzer, and our web researcher are
11:16
using tools that we've defined here as well.
11:20
It's important to make sure that you list all of the tools
11:23
that your main agent and your subagents will
11:25
need to use inside of your allowed tools.
11:28
or else your subagents will not allow them
11:31
even if you include the tools here.
11:33
Now that we've set up our agents, we need to make sure
11:36
we also include the all-important Task tool
11:39
to make sure that we can
11:40
dispatch subagents and assign tasks to them.
11:42
last piece we need to add here are skills.
11:45
And the good news is, in order to add skills,
11:47
there's just one more tool that we need to add.
11:50
And that is the Skill tool.
11:52
Since we have an environment here where there's a file system
11:55
and the ability to execute code using the Bash tool,
11:58
All we need to add is this Skill tool
12:00
so that we can correctly read skills
12:03
and understand how best to use them.
12:05
Similar to Claude code, skills are defined
12:08
inside of a .claude folder followed by a folder called skills.
12:13
Make sure your markdown files are SKILL.md
12:15
and your folder is called skills in the plural.
12:19
Now that we've added the tool for working with skills,
12:22
there's one more keyword argument that we need to pass in here.
12:25
We need to specify where we find this particular set of skills.
12:30
And we do so with a keyword argument called setting_sources.
12:33
And here we're going to specify that we want to find skills
12:36
inside of the user directory,
12:38
if we have skills in our home directory,
12:41
as well as project,
12:43
which is where we've loaded the skills for this particular application.
12:46
Now that we put this all together,
12:48
let's go ahead and test out our agent.
12:51
We open up the terminal
12:52
again. I'm going to go ahead and exit
12:55
and let's run this application again with the changes that we've made.
12:58
We're going to start by learning a little bit about MinerU.
13:02
For those of you not familiar, MinerU
13:04
is an open library for PDF extraction.
13:07
And the reason we're using this
13:08
example, is because this is not something
13:10
that Claude might know a ton of from its initial training data.
13:14
This is going to require external research, analyzing code repositories,
13:18
community documents, and other sources.
13:20
We're going to ask to create a learning
13:22
guide and then show me the plan first.
13:25
Here, we're going to start to see that the skill is invoked
13:27
and the input here is that skill called learning-a-tool
13:31
with the args that we specified.
13:33
So here, we can see that we first specified the plan.
13:37
We still have to go ahead and
13:38
run what the subagents are going to do,
13:40
but just like with Claude code and plan mode,
13:43
we might want to see what
13:44
the plan is before we start acting
13:46
and consuming tokens and taking time.
13:48
We can see the research phase of parallel investigation
13:51
with our different researchers.
13:53
We can see the structure necessary according to the skill,
13:56
and then finally, the output that we're expecting.
13:59
This looks like a good plan. So we'll
14:01
just go ahead and ask it to proceed.
14:04
It's going to start by spawning the docs_researcher subagent,
14:07
spawning the repo_analyzer and web_researcher,
14:10
and executing these in parallel,
14:12
using the tools that we've added under the allowed tools
14:15
that we've also passed in to our subagent.
14:18
We can see in parallel, the
14:20
docs researcher is heading to the documentation,
14:22
the repo analyzer is looking on GitHub,
14:25
and the web researcher is searching across tutorials and YouTube guides.
14:29
We're extracting the information from GitHub repositories
14:32
using the bash commands, while at the same time,
14:34
searching a YouTube channel for video demonstrations.
14:38
These agents are interacting in parallel,
14:40
fetching from different data sources
14:42
to bring this all together into a compelling tutorial.
14:46
Now that the subagents have finished completing their work,
14:49
We're going to create the comprehensive guide,
14:51
pull together all the necessary files based
14:53
on this research that we have here.
14:56
As instructed in the repository analyzer, we've cloned the repository
14:59
for MinerU, and keeping that here.
15:02
and we started to build the folder structure for learning this.
15:06
We can see here, we have our readme and resources,
15:08
as well as code examples that are being put together.
15:12
We can see here in the readme file,
15:13
it provides the learning path to us.
15:16
What we're going to learn, how to use this guide,
15:18
and importantly, time estimates that we might need.
15:21
We can see here, it's created for us the README, the resources,
15:25
and the learning path is still in progress.
15:27
Inside of our resources, we have links and references for MinerU.
15:31
So let's take a look at that.
15:33
Inside of our resources, we have documentation,
15:35
the repository, PyPI package,
15:38
and the paper underlying this library.
15:40
We have quick start guides, documentation, and related projects.
15:43
as we pull in additional information from the community.
15:47
We have all kinds of deep dives
15:48
across a variety of different articles and news coverage.
15:52
Now we can see that the learning path has been created
15:56
and it's time to create the code examples.
15:59
Let's take a look at this learning path.
16:01
starting with an Overview &amp; Motivation,
16:03
What Problem does it Solve?
16:05
We describe the Origin Story of the library,
16:08
What Existed Before, and some of the problems with those libraries.
16:11
We can see here this is
16:13
quite an in-depth guide and learning path,
16:15
and you can imagine this is
16:16
something that would last a long time
16:18
as you start to get up to speed knowing very little
16:20
to becoming an expert in working with this library.
16:23
We move into some of the distinct
16:25
features of the back end of this library,
16:27
all the way to code examples and many different characteristics
16:31
for how to use this as efficiently as possible.
16:34
We can start to see that our code files are being written
16:38
for hello world examples, concepts, and patterns.
16:41
For our hello world example,
16:43
we've got a nice README to get started with some first steps,
16:46
simple extraction to see how to start using this library,
16:49
as well as installation steps.
16:51
If there were particular libraries we wanted to use for installing
16:54
or patterns here, we could always add that to our skill.
16:57
But right now, this is going to give us a great start
16:59
to get up and running with this library.
17:01
as we look at some of the core concepts,
17:04
those are being created currently.
17:06
Now that those are done, we can
17:07
see in the README where we go next.
17:09
Once we've gotten up and running with the library,
17:11
we can start to look at some
17:13
of the fundamental concepts that the library possesses,
17:15
as well as comparing different speeds across backends.
17:19
Finally, we're going to create practical
17:21
patterns and examples with this third folder.
17:24
We can take a look at
17:25
this folder, and we can see here
17:27
that we have real-world processing pipelines and production use cases.
17:30
This includes examples for certain patterns,
17:33
as well as quite in-depth code examples using this library.
17:37
with doc strings, comments, and everything necessary
17:40
to use this library to its fullest extent.
17:43
We'll wrap up by validating and creating a
17:45
summary document, making sure everything has been done correctly.
17:49
We can take a look at the
17:50
output, which gives us a complete learning guide,
17:52
the directory structure as specified in our skill,
17:55
the learning path with the levels that we requested,
17:58
and then key features and a
18:00
quick start to get up and running.
18:02
The final thing we're going to do here
18:04
is write this particular file, the resources.md,
18:07
to a resources subpage in Notion.
18:10
This page already exists, so let's take
18:12
a look at what that looks like,
18:13
and then we'll prompt to go ahead and
18:15
use our MCP server to do the writing necessary.
18:18
We can see here in Notion under this learning section,
18:22
I have a sub page called resources.
18:24
The goal here is to use the MCP server
18:26
to populate what we had in our resources.md to this right here.
18:31
So let's go ahead and ask our agent to write that file
18:34
to that sub page in Notion.
18:38
We're going to be explicit with
18:39
the tools that we use in Notion
18:41
and allow it to use what we have available.
18:43
We've found the resources page.
18:45
We're going to read the resources.md
18:47
and convert it to the correct format in Notion
18:50
using rich Notion blocks. You can see
18:52
here we're using multiple tools from Notion,
18:54
doing this in batches, adding the quick start guides,
18:57
API Documentation, and the rest of the information
19:00
inside of our resources.md
19:02
We can see here in the resources file,
19:05
it's dynamically updating based on the documentation
19:08
in our resources.md
19:10
And as this finishes up, we're going to see all the content
19:12
from that file appear on our Notion page.
19:15
Now that it's finished, let's go take a look
19:18
at what our Notion page looks like.
19:20
We can see here, we've got our official documentation,
19:22
our tutorials, video resources, community channels,
19:25
all the data that came from that markdown file,
19:28
we've now written to Notion.
19:30
We made use of skills, MCP servers, agents, and subagents
19:33
all using the agent SDK.
19:36
You can imagine layering on additional skills for more complex workflow
19:40
or additional subagents to perform a variety of tasks.
19:44
We've just started to scratch the surface with functionality,
19:46
and there's still some security concerns that we should be mindful of.
19:50
For starters, we're allowing commands like write and bash to be executed
19:54
without requiring permission from the user.
19:57
The next step here is to
19:58
build an interface just like Claude code
20:00
that ensures that we allow the user to
20:02
confirm that they want to use those particular tools
20:05
for a certain action.
20:07
We've also just started to scratch the surface
20:09
with the ability to even add things like interrupts
20:12
for our agents and subagents, similar to Claude code.
20:15
So we've given you the foundation
20:17
to continue to build powerful agentic applications,
20:19
and we can't wait to see what you build next.

---

## Video 10: Conclusion (1 min)

0:00
Congratulations on making it this far.
0:01
You've learned how to create skills, explored their best practices,
0:05
and seen them in action across different platforms.
0:08
When creating a skill, start with basic markdown instructions,
0:12
then expand later following progressive disclosure.
0:15
Monitor how your agent uses your skill
0:17
in real scenarios and iterate based on observations.
0:21
Make sure the description contains enough detail for
0:23
your agent to know when to use it.
0:25
Don't forget, Claude is very knowledgeable about what skills are.
0:29
So you can always start with
0:31
a simple conversation to begin creating skills
0:33
and then use the skill creator skill to follow best practices.
0:37
Thank you for joining me in this journey.
0:39
And I can't wait to see what you build with agent skills.

---

## Notes

### Key Concepts

[To be filled after reviewing all transcripts]

### Gaps vs Our Content

[To be filled after analysis]

### Course Material Ideas

[To be filled after analysis]
