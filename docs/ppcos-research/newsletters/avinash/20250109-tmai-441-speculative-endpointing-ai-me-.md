# TMAI #441: 🥅 Speculative Endpointing | AI & Me.

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2025-01-09T09:16:16.000Z
**Folder:** avinash

---

[1]

TMAI #441: SPECULATIVE ENDPOINTING.

[ Web Version [2] ]

A story about AI and me.

It'll pull through a reflection on Analytical thinking, and what it
takes to function effectively in a modern organization. A lot in one
newsletter. :)

Let’s walk down the yellow brick road.

AI.

The first working version of the DeepMind model Astra [3] took seven
seconds to respond when it was asked something.

Imagine speaking to someone, and then the other person taking seven
seconds to respond. It is an eternity!

This is, of course, expected in an early prototype. The first approach
the team took to fixing it was to work on something technically called
_CO-LOCATING._

Any spoken AI model is actually a collection of software and hardware.

A hardware sensor for audio, which listens (based on your permission,
occasionally or all the time), passes it on to the software which does
the specialized processing, categorizes audio, and it in turn passes
the instructions on to another piece of software called the LLM (in
this case Gemini). Then, if a response is expected, everything happens
in reverse.

If the AI is multi-modal, you can have a whole host of additional
hardware and software sensors like video, images, text, etc. etc. etc.

If all the hardware and software are in different locations
(physically) then everything has to go over Wi-Fi, fiber, over oceans,
between, say, your Phone and the Cloud… And all that adds latency.
That’s how for an early unoptimized version you get a seven-second
wait.

_Co-locating_ simply puts everything physically as close to each other
as possible. The input device, a Phone in this case, stays in your
hands with the sensors, but all the other software sits physically
next to each other in the same Data Center in the Cloud. Result: Lower
latency.

[NOTE: My first job out of MBA school was at Silicon Graphics Inc. I
LOVED being a part of a company that built supercomputers, and the
highest-end visualization hardware. SGI used something called CC-NUMA
[4] architecture. It linked several processing nodes through a
high-bandwidth low-latency interconnection network to do
magic. _Co-locating! _:)]

The next step by the team was to work hard on optimizing all the
software pieces (including customizing Gemini) to work with each other
for the specialized tasks Astra was meant to perform. Result: Lower
latency.

Those seven seconds are heading to one.

The next part got me so excited.

You can speed up response if you can solve a simple problem:

Detecting that the human has stopped speaking.

This is technically called _ENDPOINTING._

It is a surprisingly hard problem to solve. Humans are all so
different. We speak fast, we speak slow, we meander through
instructions, and, this can be frustrating, we start talking, say
something, pause, and then continue talking!

In normal life, you are looking at me and perhaps using non-verbal
cues, you are, unconsciously, parsing semantic context, and your lived
experience with humans, to decide I’m done talking (recognize the
endpoint). Then, you respond to me.

The DeepMind team did a bunch of things to recognize endpointing (say
a longer pause), and further reduced latency – respond to the human
faster.

Then, they did something that made me break out into a smile.

With deeper observation of human patterns, they jumped to something
technically called _SPECULATIVE ENDPOINTING_.

Essentially:

A combination of computing when the human was done talking AND parsing
human speech in real-time, to separate out the important part, say, a
question, vs. “filler.”

Then, before the human was done talking, identify the answer to the
question, and be ready to share it detected the human had stopped
speaking.
I might be interested in knowing _how long it takes for the Sun to
revolve around the Earth_.*  But, as a normal human I might wrap that
question to an AI in between long sentences. It might be somewhere in
the middle of my soliloquy, or in the end or the beginning.

If the AI can speculatively figure out the important part, it can go
get a response before I’m done talking!

Result: Lower latency.

The human stops talking when they do, and, as if by magic,
instantaneously the answer/image/video/insight is presented to them.

This is a big difference between the old Assistant, Siri, versions of
“AI” and the current generation of AI models. They are listening,
but they are not waiting for the _endpoint_ to then go do the task you
requested. They are speculating in real-time what you really want,
while you are still taking, and deciding when you are done with that
part (even as you still keep talking, and you don't know you are
done!).

I do not need to tell you just how hard this is to get right.
Especially for an AI.

It is why _speculative endpointing _is such a cool and clever
solution.

It is also why on my phone I can interrupt my OpenAI model when it is
speaking, and it does not miss a beat.

ME.

I’ve been given the feedback, from my peers, my spouse (!), that
they don't get the sense that I'm listening to everything they are
saying. They've shared, I respond very quickly when they are done
talking. Sometimes, I get so excited to respond, I interrupt them.

As someone who is on the autism spectrum, I find reading non-verbal
cues challenging. Hence, this feedback was welcome, and I’ve worked
to address it.

My helpful therapist, after 360-degree interviews, and conversations
with me over sessions, shared that her observation was that I was
listening carefully to the other individual, that I was processing
what they were saying faster than they were talking. By the time they
were done, I had my addition to the conversation ready to go. But,
they never had the opportunity to get clues that I’d done all that
processing in my head.

Sounds familiar?

_Speculative end-pointing!_

That is why I smiled listening to the podcast [5] about Astra. For the
first time in my life, after many feedback and therapy sessions… I
had a name for what I was doing.

[NOTE: Though incredibly effective for an AI, it does not necessarily
work for a human. More on that below.]

Here’s an example of me _speculatively endpointing_.

A study crossed my path the other day. I’m writing this newsletter
on a trans-pacific flight, hence recalling from memory:

Approximately 30% of “Corporate Users” had tried AI in their work,
in the last year.

And, _just _1% had gone back to using AI once in the last month.
That’s heartbreaking.

Microsoft is charging $30/mo/user for CoPilot. All those contracts
will be cancelled if CoPilot is only being used by 1% of the employees
the company is paying for!

So, let’s say we are working to solve this problem. A = 100. B = 30.
C = 1.

[Usage of CoPilot]

If 1% used CoPilot, a common computation of Headroom, _how high can
we go_, is A - C = 99.

I've come to believe this calculation of Headroom is imprecise.

There are many humans and use cases between B and A that do not apply
to our conversation around increasing use of AI. The _real _Headroom
is B - C = 29.

When we start discussing, you are outlining the dire state of reality,
_just 1% use it again in the last month, _and sharing your ideas to
be actioned to win the massive upside of 99%.

I, only in my mind, process that 99% is _fake news,_ and the real
Headroom is 29%.

[Compute real headroom.]

I'm trying to figure out how to solve the important problem you've
highlighted, but processing a different dimension of that problem
(_what can move the 1% by 29 points_). I'm thinking of solutions to
that different problem, there is a picture forming in my head, and
waiting for you to pause.

I’ve already _speculatively endpointed._

When you actually pause after a while… I say...

_We need to understand more deeply the use cases in 1, segment use
cases 2, 3, 4, 5, so that we know what Users did in each of those
cases and why those did not end up being valuable enough to draw them
back._

[Problems to solve in the real headroom.]

I continue...

_Oh, and once we identify those, let’s prioritize 3 and 5, they
offer the best chance to dramatically change 1, and accelerate
CoPilot’s impact on our Users. _

_My experience lends me to believe that prompting Users with solutions
like "pre-built queries" in the interface for their common use cases,
when people land on the CoPilot interface, will likely accelerate
usage._

And, you say to me:

_What the heck are you even talking about?! __
_
_Did you hear me about capturing more of the 99%?_

See the problem with me _speculatively endpointing_?

Everything that was going on in my head, as I was listening carefully
to what you were saying, I was also live processing the problem, and
_pre-fetching_ a solution.

None of that was visible to you.

You did not feel heard. And, you were right to feel that.

That is what my therapist helped me understand.

She shared simple tools like pausing after the other person is done
talking, taking time to repeat what they said and confirm that that is
what they meant, not get to the solution immediately and to expose all
the processing that happened in my head, and others.

I have tried to practice this invaluable guidance over the years, to
be better.

People closest to me at work, Sam or Pooja or Dean would say: _Avinash
is a work in progress on this dimension, he gets too excited about
fixing the problem to practice all the tips_.

This would be extremely fair.

Nurture has a hard time entirely overcoming nature.

Last Saturday, on my long cycle ride, listening to the podcast, I was
just so relieved I had a name for my problem. _Speculative
Endpointing._

A FUTURE PROBLEM FOR AI?

We come to an AI with different expectations.

We are delighted that from our long, possibly incoherent, expression
of needs, it figured out what we really meant, and it came back
instantly with a reply.

We don’t pause to think that it pulled that out from the first 15
seconds of what we spoke, and there were another four minutes that it
ignored.

Conversational AI is rapidly getting to be very human like, and my
experiments with Agentic AI made me realize AI is going to behave so
much more like humans this year.

The combination of Conversational AI AND Agentic AI will soon yield
something that is very human like. Throw in the extraordinary compute
that is coming online, and it might also feel very, very human.

I wonder then… We will have to teach the AI, this thing that will be
smarter than the smartest humans who ever lived, to not be so
_speculatively endpointy_. To pause after the human, before
responding. To repeat key parts the human said, to ensure they feel
heard. To, explain the processing the AI did before getting to the
answer, so the human also understands that you really understood. And,
other approaches.

Or.

We will treat AI differently? Possibly,
because _superintelligence _will think and process at a level that
might be incomprehensible to us _regular_ humans.

Will we accept, at the end of our complex long questions, when the AI
responds: 42.

What do you think?

BOTTOM LINE.

Isn’t it amazing that an AI helped me understand myself better?

So much more of this is ahead.

I'm genuinely excited.

-Avinash.

* I’m just checking if you are reading this newsletter carefully!

Thank you for being a TMAI Premium subscriber - and helping raise
money for charity.

Your Premium subscription covers one person. It's fine to forward
occasionally. Please do not forward or pipe it into Slack for the
whole company. We have group plans, just email me.

[Subscribe [6]]  |  [Web Version [2]]  |  [Unsubscribe [7]]

[8]
[9]
[10]

©2022 ZQ Insights  |  PO Box 10193, San Jose, CA, 95157, United
States of America

Links:
------
[1] https://www.kaushik.net/avinash/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[2] https://tmai.avinashkaushik.com/web-version?ep=1&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=d376db3c-cde8-11ef-9b88-515d5a2e1441&pt=campaign&t=1736414176&s=00c3f3b9141883447140a0ebc2adba17578419f9f95f37c22a1ca95c569c931c
[3] https://deepmind.google/technologies/project-astra/
[4] https://www.tutorialspoint.com/what-is-cc-numa
[5] https://open.spotify.com/episode/2WtTxKCxA0DY36IExwCqhp
[6] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[7] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=296c812a-be87-11ea-a3d0-06b4694bee2a&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=d376db3c-cde8-11ef-9b88-515d5a2e1441&pt=campaign&pv=4&spa=1736414149&t=1736414176&s=f6b889822f93f0c4f800d4f52823807874bcb041ff24b665adf984a06f8fac24
[8] https://twitter.com/avinash
[9] https://www.linkedin.com/in/akaushik/
[10] https://www.instagram.com/avinashplusworld/?hl=en
