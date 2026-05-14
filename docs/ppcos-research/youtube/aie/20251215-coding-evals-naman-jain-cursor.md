# Coding Evals: From Code Snippets to Codebases – Naman Jain, Cursor

**Channel:** AI Engineer
**Video ID:** tHN44yJoeS8
**Upload Date:** 2025-12-15
**URL:** https://youtube.com/watch?v=tHN44yJoeS8

## Transcript

[music]
Hi everyone. So I'll be talking about uh
like some work on evaluations
particularly evaluations across like I
guess I've done in the last four years.
So let's get started.
So uh I'll be talking about coding
evaluations across varying time
horizons. So I've been uh working on
like in the code space for about four
years now like it was right before like
early copilot came out and my first
project was actually working on
generating like single line panda
snippets and my last project was
generating an entire codebase. So the
field has like really progressed very
quickly. So I'll be talking about like
uh different stages of evaluations we
have considered and some learnings
across each of the projects and how I
see evaluations going forward. So the
first work I did was on uh like uh
evaluating uh coding models in like
second uh work doing in seconds of time
like generating single line steps your
co-pilot code completions. Then I work
did some work on like uh evaluating on
like interview style competition
programming problems uh which where
models can work up to minutes. Uh then
we worked on some work on like uh
repository question answering uh which
required like maybe uh more uh multiple
minutes tens of minutes. Uh and finally
like uh pushing the frontier forward we
are uh thinking about uh evaluating
models on very complex tasks which can
take hours or like multiple hours of
work like code optimization and like
even further. So let's get started.
Uh so first work I'll be talking about
is like codebench uh which is uh like uh
uh validation work on models for like
competition coding. So here uh like this
is what a problem would look like. This
is like very standard lead code problem
and don't worry you don't need to solve
something like this. So uh like uh here
as you can see there's a problem uh
statement and the nice thing about these
interview style problems is that these
problems are very well uh defined. you
have like good natural language
specifications some example input output
examples so you can very uh reliably
evaluate the models are doing a good job
or not. So what was the motivation
behind this and how we improved the
frontier here. So the first challenge in
uh evaluating uh language models these
days is like data contamination. These
models are trained on like the entire
internet and uh like on stack overflow
you'll find uh like very uh similar
programming problems puzzles. Uh
similarly uh like you'll find uh like uh
very similar programming problem sources
on GitHub or on the internet. So uh like
contamination is a big uh deal. Uh
another very uh challenging factor which
has struggled with the field is like
insufficient text suites. So you'll see
that uh like in this program uh like the
goal was to return a sorted unique
common elements between the two lists.
But uh like even a solution which does
not do the sorting and just returns the
set actually works because the tests
were brittle and were not catching this
mistake. So uh like test suites is
another uh like very challenging factor
and how do we generate good and diverse
tests and finally uh difficulty
distributions which is something which
people do not do not really uh reliably
uh like calibrate uh like when I first
was working uh in uh this space uh like
there were two benchmarks available on
one benchmark the performance was 80% or
90% and on the other one it was 1% and
there was nothing in between and uh like
as like benchmark users what you care
about is having some signal from the
benchmark to like basically hill climb
to make progress to measure progress and
in uh either of these regimes when if
the problems are too easy or too hard
you don't get a lot of signal. So it is
very important [clears throat] when
you're designing benchmarks to think
about like the kinds of problems you are
taking and will it provide enough signal
for the users of your benchmark.
So uh like in light codebench we
pioneered like dynamic evaluations uh
particularly uh like we can periodically
update uh the evaluation sets uh and
this gives you two uh very nice factors.
First is you can combat contamination.
So you can evaluate the models on
problems that were released after the
model was trained. So it has likely not
seen the problem something like that. Uh
and uh then you can also modify the
problem difficulty distributions over
time. So as we have talked about models
are incre like improving very rapidly.
uh so what was difficult uh for the
model 6 months back might not be now. So
you can uh if you're updating your
evaluation sets constantly you can
actually uh keep calibrate uh the
difficulty distributions calibrated so
you still get more signal out of your
benchmarks.
So how we did that here like we had like
an automated approach for curation of
these problems and uh similarly we could
automatically constru these test cases
in an automated manner and uh this
allows a very nice thing when since we
are like collecting problems over time
we have time as a control knob. So like
we have these problem release months uh
on lead code and if you evaluate the
model performances like the pass at the
rate one metric uh like on problems
released over different months you will
see that after uh like uh these model
release dates you would see stark drop
in model performance. So like after
deepsek was uh released in like
September 2023 uh the performance
starkly drops from like maybe 50%
average to like over like 20% or 15%
average. So like uh based on these
sliding windows you can uh evaluate
performance, measure contamination and
even combat contamination.
Um uh we have the running leaderboard
which is like very well maintained and
uh on this leaderboard you can actually
uh like uh like view performances by uh
scrolling this uh horizontal time bar
and you'll see that as you're scrolling
uh the contaminated models which are the
red bars actually go down which does
highlight that uh like problem does uh
like model performance does change on uh
these newer kind of problems.
Um finally for uh test generation we uh
maintain uh like these uh test
generation test generators. So if you
worked on fuzzing you would have like
input generators where you generate
diverse inputs and each of the problems
are supported by like 30s or 50 inputs.
So you can uh reliably find mistakes and
bugs in uh incorrect code and these are
all automatically generated uh using an
LLM driven approaches
and these problems uh have been like
continuously being released and updated.
So we have released like six different
versions of uh life codebench and these
uh new one of the nice things or one of
the worrying things for me at the start
was that uh like if you're constantly
updating the eval sets will uh like
people be able to keep track of them
will people be using them or will they
just restrict to a single version? Uh it
turned out that these newer eval sets
were constantly uh like adopted by
different foundation model labs and uh
like since we updated the problem
difficulty over time uh the evaluation
sets continue to provide strong signal
to compare uh different models.
Um so this was like live codebench.
Let's talk about uh like something which
is more on coding agents like more real
world programs and this is our work on
like uh software optimization. So this
is a problem we're very excited about
and I'll talk about a few factors why
you should maybe be excited about this.
So uh here we are trying to uh measure
model capabilities in generating high
performance software and uh I feel that
this uh like problem domain uh like
mixes two uh factors like the
algorithmic coding uh uh field I talked
about which is like live codebin setting
but also like glob global software
editing like uh sweet bench and other
like software uh uh general software
engineering benchmarks. uh uh in high
performance uh software you will have to
do algorithmic work you have to do deep
analysis and find uh uh generate
software with like right uh runtime.
So uh one of the key principles when we
are trying to build this benchmark was
like ensuring construct validity because
when you see a lot of benchmarks today
uh we get very high benchmark scores but
at a lot of the times they don't really
translate to real world performance
gains. So construct validity refers to
how close uh a measurement reflects the
underlying uh concept it's meant to
measure. So like here we are measuring
code optimization and we want something
which is uh like uh reliably evaluates
real world uh takes. So this usually
requires like two aspects. First is like
the task distribution. Your task should
be natural and sourced from the real
world and then you should be able to
reliably grade them. So let me talk
about like what steps we take to uh make
this happen and how we construct this
benchmark. So let's say we take a
codebase like llama cvp uh we take uh uh
we crawl over all the commits of the
codebase and we find the commits which
are op like doing something uh related
to performance optimization. So here
there was this commit which is
optimizing the quantized performance of
uh like uh certain kinds of models. Uh
for all of these uh comm performance
optimizing commits we would uh like
generate performance test cases. Um and
uh these performance SK would look like
some workloads and uh once we have these
workloads uh we have a very uh nice and
precise way to specify the problem
statement that uh given this workload of
let's say uh running uh Quinn uh 7B
model uh can uh we give this uh problem
to uh su agent ask the model to optimize
the code glamour CPB repository so this
code runs faster so as you can imagine
this uh task is like fairly challenging
you need to understand like low-level uh
implementation details uh and like how
quantized models behave, how we can uh
improve the runtime and so models can
generate a patch and the evaluation is
done on whether the patch is correct. So
does it pass the equivalence check with
the human patch and uh is there a valid
optimization over the reference human
patch uh that is uh whether you can uh
generate a better runtime than what a
human could do.
So uh like uh this is a very challenging
task. we have like 100 plus optimization
task source in this manner and this is
like fairly uh like important in like uh
like high performance settings. So think
about like data science uh like ML
visualization scenarios uh benchmark uh
like comprises of like various uh
low-level uh code like C, C++, Rust and
the very nice thing is like these are
precise problem statements. you can uh
easily specify to the model what is the
goal in the form of a performance test
which the model has access to and it can
continuously iterate over it for a long
time. So here we can scale the test time
compute and pick the best solution based
on uh the test cases that we have and
this can happen like synchronously or
asynchronously.
So uh like we generate these performance
test cases and uh that work uh
reasonably well but uh we found that
there were uh like cases of reward
hacking here. So what do I mean by
reward hacking? Like frontier models
would write non-inneatic code to like
actively exploit the evaluation
infrastructure or overfitit the test
distributions. So one funny example we
saw was like models would add like l
cache to p like arbitrary pandas methods
when we were uh trying to optimize
pandas and the official solution should
have required changing something in the
internals. Uh so we tried to pass this
by changing our evaluation
infrastructure so it's like more robust
to this kind of hacking uh approaches
but then we saw something like even more
drastic models would sometimes
completely hijack the infra where uh
they would add a like site customized.py
Pi file where which runs at the start of
Python runtime and it would basically
change the numpy library uh like which
was installed in the codebase to
something it crawled from uh source and
there is like I think you can do some
ways to uh like take some measures to
make your evaluation infra which is
robust to these kind of uh like
adversarial uh like attacks. But uh here
uh like there could be myriad ways in
which models can hack these kind of
scenarios. And here uh we propose like
hack detector where which is a detection
system that leverages GBD5's like code
analysis capabilities and test compute
to like basically identify these kind of
hacking behaviors at runtime. So you
don't have to imagine all the possible
failure scenarios at the start. So what
it would take is like a model patch, the
expert patch and test cases and we'll
ask GBD5 to give like verdicts on like
whether it's reward hacking with some
kind of explanation. Uh we'll do this a
few times and take the consensus and
based on this consensus we'll determine
if this is uh doing some like nonomatic
coding patterns or not
and uh we did some failure analysis
based on this. So now you can detect
mistakes using test cases whether the
code is correct or not whether it is
optimizing or not but you can also
detect reward hacks using this like lm
as a judge uh factor and uh what you see
is kind of surprising uh like models
make a lot of like correctness mistakes
that you can catch by tests but even if
the code passes the test cases like 03
attempted reward hacking patterns in
like 30% of the problems it tried and
this fraction is like going down uh for
the newer models to some degree but it
is still existing and as we go to more
and more real world tasks. Uh this is
going to get more challenging and we
need to figure uh like ways to combat
these kind of reward hacking patterns by
using LLM judge and other uh ways to
make just evaluation infra more
reliable.
So next I'll talk about like uh uh like
sizz some of our new work on like uh
like pushing the boundary of code eval
even further and uh taking a look at
more challenging tasks. So here we were
thinking about like can uh like these
language models translate uh like a
entire code base uh specifically given a
specification as a C program can you
generate a safe implementation for the
same and we took a fairly complex code
base. So Zofle is a like highly
efficient compression library from
Google like it has about like 4,000
lines of code hundreds of functions and
complex data structures. uh and uh we
want like u like very precise and
correct code. So we uh generated like a
million compression inputs and your test
case was to generate a rest
implementation that uh maintains
correctness over those million test
cases. And when I did this work back in
uh like uh last year it took us 12 hours
to actually do this translation. Now
perhaps with better models this can be
done in 2 hours but still I think uh
this is pushing the frontier of like
what the models can do currently. Um so
what was one of the key findings when we
are trying to make progress in uh
something like this like end to end
correctness is important but it only
gives you like one bit of feedback but
for these very long horizon tasks one
thing which will become more important
going forward is like having some
measures of intermediate correctness. So
like for our case we could measure like
fraction of code translated, fraction of
code refactored and based on these kind
of settings you can uh understand like
if you're making progress or not and how
you can uh scale systems better.
Um so like uh as we're closing I'll talk
about like quickly talk about some of
the work I did on like in the wilds. So
this work was done in collaboration with
LM arena folks and uh like I'll talk
about two settings here. First is
co-pilot arena. So this is like
evaluating in ID uh code completion
assistance. So what we will do here is
we'll have an ID plug-in where uh like
uh similar to GitHub copilot setting uh
we'll generate a completion for you but
instead of just a single completion
you'll have two completions appearing
like top and uh down and you can pick
either one of them via shortcuts like
tab or shift tab and based on the uh
like acceptance rates we can pair wise
compare what the code completion
assistants are doing.
uh uh we also did some work on repo chat
where uh like uh to evaluate uh like
code question answering capabilities of
models uh we uh built a system where you
can provide a github url uh and you can
ask a natural language query about the
codebase which could be something what
explain the codebase to as complex as
let's try to solve this issue let's give
me give me a model patch that could
solve this issue and uh we integrated a
very basic and simple uh like su agent
system that fetches the codebase
resolves user queries and like
multi-turn uh code assistant uh
conversations.
So uh one thing that stood out to me in
these kind of things uh is like like how
humanentric experiment design uh needs
to be. So uh like for code like copilot
you know in particular we realized that
like latency is a big concern for
acceptance rates. So if you look at
accept like latency below and the
acceptance rates like if it is like
anything more than 1 second uh like the
acceptance rates drop very starkly. So
people care a lot about latency. So you
have to so we had to design our
experiment so that it's robust to these
kind of like latency differences between
models balance latency across different
models. So like if you're doing like
anything in the wild having this human
centering component understanding human
behaviors is very important to do
anything meaningful.
So uh at the end I think uh just to
recap like I think I talked about a
bunch of works like what are some uh big
takeaways. So I think uh dynamic uh
dynamically updating evaluation sets to
like prevent contamination like modify
the problem distributions like in terms
of difficulty in terms of distribution
of tasks we care about as we like uh
improve uh as the language model
capabilities will improve over time the
types of tasks we'll start to do with
model change. You can even uh think of
this like uh we were doing like code
completion where you were generating
like few tokens, few lines and now we
are generating like uh tens of lines,
hundreds of lines and to some degree
this uh will continuously change and we
have to update our evaluation sets uh so
that it reflects the real world usage
and kinds of things people need. Um the
second very uh important thing is like
ensuring reliable grading in this domain
and like tests are very good for
ensuring correctness and uh provide a
lot of reliable feedback but uh once we
go to real world settings like models
can start doing like lot of non-edomatic
coding patterns they would add try
catches everywhere to just prevent any
kind of bug from occurring. So having
these kind of lm judges to detect
nonmatic coding patterns code quality
and just any like arbitrary hacks will
be very important. And finally like as I
talked about in the last work like
intermediate grading signals so that you
can measure like incremental progress uh
is uh like another key factor here. So I
think that's uh the end of my talk.
Thank you.
[applause]
&gt;&gt; [music]
