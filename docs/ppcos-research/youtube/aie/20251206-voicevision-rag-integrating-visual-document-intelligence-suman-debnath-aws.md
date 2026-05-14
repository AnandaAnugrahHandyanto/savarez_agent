# VoiceVision RAG - Integrating Visual Document Intelligence with Voice Response

**Channel:** AI Engineers
**Video ID:** hwCmfThIiS4
**Upload Date:** 2025-12-06
**URL:** https://youtube.com/watch?v=hwCmfThIiS4

## Transcript

Kind: captions
Language: en

All<00:00:15.679><c> right.</c><00:00:16.320><c> So,</c><00:00:17.199><c> you're</c><00:00:17.600><c> almost</c><00:00:17.920><c> on</c><00:00:18.240><c> time.</c>

All right. So, you're almost on time.

All right. So, you're almost on time.
Uh<00:00:21.359><c> firstly,</c><00:00:21.760><c> thank</c><00:00:21.920><c> you</c><00:00:22.080><c> so</c><00:00:22.240><c> much</c><00:00:22.400><c> for</c><00:00:22.560><c> your</c>

Uh firstly, thank you so much for your

Uh firstly, thank you so much for your
time<00:00:23.439><c> uh</c><00:00:23.680><c> for</c><00:00:24.000><c> joining</c><00:00:24.320><c> us.</c><00:00:25.519><c> And</c><00:00:26.000><c> uh</c><00:00:26.080><c> what</c>

time uh for joining us. And uh what

time uh for joining us. And uh what
we're<00:00:26.560><c> going</c><00:00:26.720><c> to</c><00:00:26.800><c> do</c><00:00:27.119><c> is</c><00:00:27.439><c> for</c><00:00:27.760><c> next</c><00:00:28.720><c> an</c><00:00:28.960><c> hour</c><00:00:29.199><c> or</c>

we're going to do is for next an hour or

we're going to do is for next an hour or
so<00:00:30.320><c> is</c><00:00:30.880><c> uh</c><00:00:30.960><c> we'll</c><00:00:31.359><c> try</c><00:00:31.439><c> to</c><00:00:31.599><c> explore</c><00:00:31.920><c> something</c>

so is uh we'll try to explore something

so is uh we'll try to explore something
around<00:00:32.640><c> which</c><00:00:32.880><c> is</c><00:00:33.120><c> which</c><00:00:33.360><c> I</c><00:00:33.520><c> found</c><00:00:33.920><c> uh</c><00:00:34.079><c> pretty</c>

around which is which I found uh pretty

around which is which I found uh pretty
interesting<00:00:34.719><c> when</c><00:00:34.960><c> I</c><00:00:35.120><c> started</c><00:00:35.600><c> working</c><00:00:35.920><c> on</c>

interesting when I started working on

interesting when I started working on
this<00:00:37.200><c> uh</c><00:00:37.760><c> uh</c><00:00:37.840><c> and</c><00:00:38.079><c> I'll</c><00:00:38.480><c> tell</c><00:00:38.640><c> you</c><00:00:38.800><c> some</c>

this uh uh and I'll tell you some

this uh uh and I'll tell you some
background<00:00:39.280><c> about</c><00:00:39.600><c> that</c><00:00:39.920><c> how</c><00:00:40.160><c> I</c><00:00:40.399><c> end</c><00:00:40.640><c> up</c><00:00:40.800><c> into</c>

background about that how I end up into

background about that how I end up into
this<00:00:41.600><c> uh</c><00:00:41.920><c> on</c><00:00:42.320><c> vision</c><00:00:42.719><c> based</c><00:00:42.960><c> retrieval.</c><00:00:44.160><c> uh</c>

this uh on vision based retrieval. uh

this uh on vision based retrieval. uh
but<00:00:44.960><c> the</c><00:00:45.200><c> idea</c><00:00:45.520><c> of</c><00:00:46.160><c> uh</c><00:00:46.239><c> that</c><00:00:46.559><c> I</c><00:00:46.800><c> had</c><00:00:47.120><c> was</c><00:00:47.840><c> just</c>

but the idea of uh that I had was just

but the idea of uh that I had was just
to<00:00:48.239><c> share</c><00:00:48.480><c> a</c><00:00:48.640><c> few</c><00:00:48.879><c> of</c><00:00:49.280><c> my</c><00:00:49.520><c> learning</c><00:00:49.920><c> on</c><00:00:50.239><c> this</c>

to share a few of my learning on this

to share a few of my learning on this
particular<00:00:50.879><c> approach</c><00:00:51.840><c> of</c><00:00:52.239><c> retrieval</c>

particular approach of retrieval

particular approach of retrieval
and<00:00:54.160><c> there</c><00:00:54.399><c> are</c><00:00:54.559><c> bunch</c><00:00:54.719><c> of</c><00:00:54.879><c> things</c><00:00:55.039><c> that</c><00:00:55.360><c> we</c>

and there are bunch of things that we

and there are bunch of things that we
have<00:00:55.920><c> here.</c><00:00:56.640><c> Uh</c><00:00:57.039><c> I'm</c><00:00:57.360><c> going</c><00:00:57.440><c> to</c><00:00:57.680><c> share</c><00:00:59.039><c> one</c><00:00:59.280><c> of</c>

have here. Uh I'm going to share one of

have here. Uh I'm going to share one of
the<00:00:59.520><c> latest</c><00:00:59.920><c> research</c><00:01:00.320><c> paper</c><00:01:00.640><c> around</c>

the latest research paper around

the latest research paper around
retrieval<00:01:01.600><c> which</c><00:01:01.840><c> is</c><00:01:02.000><c> a</c><00:01:02.399><c> uh</c><00:01:02.480><c> vision</c><00:01:02.800><c> based</c>

retrieval which is a uh vision based

retrieval which is a uh vision based
retrieval<00:01:04.000><c> and</c><00:01:04.320><c> also</c>

retrieval and also

retrieval and also
uh<00:01:06.240><c> I</c><00:01:06.479><c> just</c><00:01:06.720><c> thought</c><00:01:06.960><c> to</c><00:01:07.680><c> wrap</c><00:01:08.000><c> this</c><00:01:08.240><c> around</c>

uh I just thought to wrap this around

uh I just thought to wrap this around
with<00:01:09.040><c> an</c><00:01:09.280><c> agent.</c><00:01:10.240><c> Uh</c><00:01:10.479><c> without</c><00:01:10.799><c> agent</c><00:01:11.119><c> we</c>

with an agent. Uh without agent we

with an agent. Uh without agent we
cannot<00:01:11.520><c> talk</c><00:01:11.760><c> about</c><00:01:12.000><c> anything</c><00:01:12.240><c> these</c><00:01:12.560><c> days.</c>

cannot talk about anything these days.

cannot talk about anything these days.
So<00:01:13.600><c> uh</c><00:01:14.000><c> right</c><00:01:14.240><c> so</c><00:01:15.040><c> uh</c><00:01:15.119><c> it's</c><00:01:15.439><c> funny</c><00:01:15.920><c> uh</c><00:01:16.159><c> without</c>

So uh right so uh it's funny uh without

So uh right so uh it's funny uh without
agent<00:01:16.880><c> I</c><00:01:17.119><c> had</c><00:01:17.280><c> this</c><00:01:17.439><c> but</c><00:01:17.759><c> then</c><00:01:18.159><c> uh</c><00:01:18.400><c> the</c>

agent I had this but then uh the

agent I had this but then uh the
organizer<00:01:19.280><c> said</c><00:01:19.439><c> that</c><00:01:19.759><c> you</c><00:01:19.920><c> know</c><00:01:20.159><c> we</c><00:01:20.400><c> need</c><00:01:20.479><c> to</c>

organizer said that you know we need to

organizer said that you know we need to
have<00:01:20.799><c> some</c><00:01:20.960><c> agent</c><00:01:21.520><c> okay</c><00:01:21.840><c> it's</c><00:01:22.080><c> not</c><00:01:22.240><c> a</c><00:01:22.479><c> big</c><00:01:22.640><c> deal</c>

have some agent okay it's not a big deal

have some agent okay it's not a big deal
right<00:01:24.159><c> so</c><00:01:25.119><c> yeah</c><00:01:25.600><c> so</c>

right so yeah so

right so yeah so
all<00:01:27.360><c> right</c><00:01:27.520><c> so</c><00:01:28.400><c> u</c><00:01:28.880><c> we'll</c><00:01:29.200><c> focus</c>

all right so u we'll focus

all right so u we'll focus
mostly<00:01:31.759><c> on</c><00:01:32.320><c> the</c><00:01:33.439><c> uh</c>

mostly on the uh

mostly on the uh
science<00:01:36.240><c> side</c><00:01:36.479><c> of</c><00:01:36.640><c> this</c><00:01:37.119><c> like</c><00:01:37.360><c> how</c><00:01:37.520><c> that</c><00:01:38.079><c> uh</c>

science side of this like how that uh

science side of this like how that uh
vision<00:01:39.439><c> based</c><00:01:39.680><c> retrieval</c><00:01:40.159><c> works</c><00:01:40.720><c> and</c><00:01:40.880><c> then</c><00:01:41.119><c> we</c>

vision based retrieval works and then we

vision based retrieval works and then we
will<00:01:41.600><c> switch</c><00:01:41.840><c> gears</c><00:01:42.159><c> and</c><00:01:42.320><c> rapid</c><00:01:42.720><c> around</c><00:01:42.880><c> with</c>

will switch gears and rapid around with

will switch gears and rapid around with
an<00:01:43.200><c> agent.</c><00:01:43.439><c> I</c><00:01:43.600><c> mean</c><00:01:43.759><c> that's</c><00:01:43.920><c> a</c><00:01:44.079><c> very</c><00:01:44.240><c> simple</c>

an agent. I mean that's a very simple

an agent. I mean that's a very simple
task<00:01:45.119><c> and</c><00:01:45.680><c> uh</c><00:01:45.759><c> I'm</c><00:01:46.079><c> going</c><00:01:46.159><c> to</c><00:01:46.240><c> use</c><00:01:46.479><c> one</c><00:01:46.640><c> of</c><00:01:46.720><c> the</c>

task and uh I'm going to use one of the

task and uh I'm going to use one of the
open<00:01:47.200><c> source</c><00:01:47.600><c> uh</c><00:01:47.920><c> uh</c><00:01:48.159><c> framework</c><00:01:48.640><c> that</c><00:01:49.119><c> uh</c><00:01:49.920><c> uh</c>

open source uh uh framework that uh uh

open source uh uh framework that uh uh
we<00:01:50.320><c> launched</c><00:01:50.720><c> recently.</c><00:01:51.200><c> I</c><00:01:51.360><c> think</c><00:01:51.439><c> it</c><00:01:51.600><c> was</c><00:01:51.759><c> two</c>

we launched recently. I think it was two

we launched recently. I think it was two
weeks<00:01:52.240><c> back</c><00:01:52.640><c> called</c><00:01:53.040><c> strands</c><00:01:53.759><c> agent</c><00:01:54.960><c> uh</c><00:01:55.280><c> which</c>

weeks back called strands agent uh which

weeks back called strands agent uh which
is<00:01:55.680><c> kind</c><00:01:55.840><c> of</c><00:01:55.920><c> a</c><00:01:56.799><c> a</c><00:01:57.119><c> framework</c><00:01:57.600><c> lightweight</c>

is kind of a a framework lightweight

is kind of a a framework lightweight
framework<00:01:58.719><c> to</c><00:01:58.880><c> build</c><00:01:59.119><c> agentic</c><00:01:59.600><c> application.</c>

framework to build agentic application.

framework to build agentic application.
I'll<00:02:00.560><c> talk</c><00:02:00.719><c> about</c><00:02:00.880><c> that</c><00:02:01.200><c> little</c><00:02:01.360><c> later</c><00:02:02.159><c> and</c><00:02:02.320><c> I</c>

I'll talk about that little later and I

I'll talk about that little later and I
have<00:02:02.560><c> a</c><00:02:02.719><c> session</c><00:02:02.880><c> on</c><00:02:03.040><c> that</c><00:02:03.680><c> day</c><00:02:03.840><c> for</c><00:02:04.079><c> tomorrow.</c>

have a session on that day for tomorrow.

have a session on that day for tomorrow.
Um<00:02:05.840><c> but</c><00:02:06.079><c> that's</c><00:02:06.399><c> the</c><00:02:06.640><c> premise</c><00:02:07.600><c> and</c><00:02:08.239><c> uh</c><00:02:08.959><c> before</c>

Um but that's the premise and uh before

Um but that's the premise and uh before
we<00:02:09.440><c> get</c><00:02:09.599><c> started</c><00:02:10.399><c> uh</c><00:02:10.560><c> how</c><00:02:10.800><c> many</c><00:02:10.959><c> of</c><00:02:11.120><c> you</c><00:02:12.000><c> are</c>

we get started uh how many of you are

we get started uh how many of you are
are<00:02:13.440><c> from</c><00:02:14.560><c> uh</c>

are from uh

are from uh
science<00:02:17.120><c> side</c><00:02:17.200><c> of</c><00:02:17.360><c> things</c><00:02:17.520><c> like</c><00:02:17.760><c> who</c><00:02:18.000><c> how</c><00:02:18.239><c> many</c>

science side of things like who how many

science side of things like who how many
of<00:02:18.400><c> you</c><00:02:18.560><c> have</c><00:02:18.800><c> worked</c><00:02:18.959><c> on</c><00:02:19.280><c> transformers?</c>

of you have worked on transformers?

of you have worked on transformers?
Okay,<00:02:22.160><c> perfect.</c><00:02:22.879><c> How</c><00:02:23.040><c> many</c><00:02:23.200><c> of</c><00:02:23.360><c> you</c><00:02:23.520><c> have</c>

Okay, perfect. How many of you have

Okay, perfect. How many of you have
worked<00:02:24.000><c> on</c><00:02:24.239><c> rag</c><00:02:24.720><c> in</c><00:02:25.040><c> general?</c>

worked on rag in general?

worked on rag in general?
Fantastic.<00:02:27.680><c> Okay.</c><00:02:28.160><c> And</c><00:02:28.640><c> uh</c><00:02:28.800><c> how</c><00:02:29.040><c> many</c><00:02:29.120><c> of</c><00:02:29.360><c> you</c>

Fantastic. Okay. And uh how many of you

Fantastic. Okay. And uh how many of you
have<00:02:30.640><c> worked</c><00:02:30.879><c> on</c><00:02:31.280><c> AWS?</c>

have worked on AWS?

have worked on AWS?
Okay,<00:02:33.680><c> great.</c><00:02:34.239><c> So</c><00:02:34.560><c> there's</c><00:02:34.879><c> nothing</c><00:02:35.120><c> about</c>

Okay, great. So there's nothing about

Okay, great. So there's nothing about
AWS<00:02:35.920><c> here.</c><00:02:36.319><c> Okay.</c><00:02:36.640><c> So</c><00:02:37.680><c> uh</c><00:02:38.080><c> so</c><00:02:38.319><c> the</c><00:02:38.560><c> last</c>

AWS here. Okay. So uh so the last

AWS here. Okay. So uh so the last
question<00:02:39.120><c> was</c><00:02:39.360><c> sponsored</c><00:02:39.840><c> by</c><00:02:40.000><c> my</c><00:02:40.239><c> manager.</c>

question was sponsored by my manager.

question was sponsored by my manager.
Okay.<00:02:41.280><c> So</c><00:02:42.640><c> what</c><00:02:44.000><c> so</c><00:02:44.239><c> what</c><00:02:44.480><c> we</c><00:02:44.640><c> are</c><00:02:44.720><c> going</c><00:02:44.800><c> to</c><00:02:44.959><c> do</c>

Okay. So what so what we are going to do

Okay. So what so what we are going to do
is<00:02:45.840><c> u</c><00:02:47.120><c> uh</c><00:02:47.200><c> we</c><00:02:47.440><c> are</c><00:02:47.519><c> going</c><00:02:47.680><c> to</c><00:02:48.080><c> uh</c><00:02:48.640><c> share</c><00:02:49.360><c> one</c><00:02:50.239><c> uh</c>

is u uh we are going to uh share one uh

is u uh we are going to uh share one uh
notebook.<00:02:53.200><c> you</c><00:02:53.519><c> can</c><00:02:54.560><c> just</c><00:02:54.879><c> uh</c><00:02:55.040><c> clone</c><00:02:55.360><c> that</c>

notebook. you can just uh clone that

notebook. you can just uh clone that
repository<00:02:56.560><c> and</c><00:02:57.120><c> uh</c><00:02:57.760><c> there</c><00:02:58.000><c> is</c><00:02:58.239><c> lot</c><00:02:58.560><c> more</c><00:02:59.120><c> uh</c>

repository and uh there is lot more uh

repository and uh there is lot more uh
there<00:02:59.519><c> inside</c><00:02:59.920><c> that</c><00:03:00.879><c> uh</c><00:03:01.040><c> but</c><00:03:01.519><c> we</c><00:03:01.760><c> are</c><00:03:01.920><c> just</c>

there inside that uh but we are just

there inside that uh but we are just
going<00:03:02.159><c> to</c><00:03:02.319><c> use</c><00:03:02.560><c> one</c><00:03:02.879><c> part</c><00:03:03.120><c> of</c><00:03:03.280><c> that</c><00:03:03.760><c> uh</c>

going to use one part of that uh

going to use one part of that uh
repository<00:03:04.720><c> okay</c><00:03:05.599><c> and</c><00:03:05.920><c> I'm</c><00:03:06.239><c> going</c><00:03:06.319><c> to</c><00:03:06.560><c> share</c>

repository okay and I'm going to share

repository okay and I'm going to share
few<00:03:07.120><c> of</c><00:03:07.440><c> the</c><00:03:08.159><c> I</c><00:03:08.480><c> think</c><00:03:09.280><c> some</c><00:03:09.680><c> $25</c><00:03:10.400><c> credit</c><00:03:10.800><c> code</c>

few of the I think some $25 credit code

few of the I think some $25 credit code
uh<00:03:11.680><c> which</c><00:03:11.920><c> I</c><00:03:12.080><c> was</c><00:03:12.239><c> given</c><00:03:12.800><c> so</c><00:03:12.959><c> I</c><00:03:13.200><c> think</c><00:03:13.440><c> uh</c><00:03:13.599><c> you</c>

uh which I was given so I think uh you

uh which I was given so I think uh you
may<00:03:14.080><c> like</c><00:03:14.239><c> to</c><00:03:14.400><c> use</c><00:03:14.560><c> that</c><00:03:14.879><c> so</c><00:03:15.440><c> uh</c><00:03:15.599><c> let's</c><00:03:16.080><c> get</c>

may like to use that so uh let's get

may like to use that so uh let's get
this<00:03:16.560><c> logistics</c><00:03:17.280><c> uh</c><00:03:17.440><c> sorted</c><00:03:18.560><c> uh</c><00:03:18.720><c> first</c>

this logistics uh sorted uh first

this logistics uh sorted uh first
okay<00:03:21.440><c> so</c><00:03:21.760><c> first</c><00:03:22.080><c> thing</c><00:03:22.319><c> first</c><00:03:22.800><c> Uh</c>

okay so first thing first Uh

okay so first thing first Uh
can<00:03:24.640><c> we</c><00:03:24.800><c> just</c><00:03:24.959><c> switch</c><00:03:25.200><c> the</c><00:03:25.440><c> screen</c><00:03:25.760><c> please?</c>

Yeah.<00:03:32.720><c> Uh</c><00:03:33.200><c> can</c><00:03:33.360><c> you</c><00:03:33.519><c> just</c><00:03:33.920><c> uh</c><00:03:34.560><c> uh</c><00:03:35.519><c> take</c><00:03:35.760><c> a</c>

Yeah. Uh can you just uh uh take a

Yeah. Uh can you just uh uh take a
moment<00:03:36.159><c> and</c><00:03:36.400><c> see</c><00:03:36.560><c> that</c><00:03:36.879><c> if</c><00:03:37.040><c> the</c><00:03:37.280><c> URL</c><00:03:37.599><c> is</c>

moment and see that if the URL is

moment and see that if the URL is
working?

working?

working?
Uh<00:03:41.040><c> you</c><00:03:41.280><c> may</c><00:03:41.599><c> if</c><00:03:41.840><c> you</c><00:03:42.000><c> are</c><00:03:42.159><c> on</c><00:03:42.400><c> laptop</c><00:03:42.799><c> you</c><00:03:42.959><c> may</c>

Uh you may if you are on laptop you may

Uh you may if you are on laptop you may
like<00:03:43.280><c> to</c><00:03:43.840><c> uh</c>

like to uh

like to uh
open<00:03:46.319><c> the</c><00:03:46.480><c> URL</c><00:03:47.120><c> or</c><00:03:47.440><c> you</c><00:03:47.599><c> can</c><00:03:47.760><c> just</c><00:03:48.400><c> take</c><00:03:48.640><c> an</c>

open the URL or you can just take an

open the URL or you can just take an
image<00:03:49.440><c> uh</c><00:03:49.680><c> on</c><00:03:49.920><c> your</c><00:03:50.080><c> cell.</c><00:03:51.040><c> You</c><00:03:51.280><c> can</c><00:03:51.360><c> have</c><00:03:51.519><c> a</c>

image uh on your cell. You can have a

image uh on your cell. You can have a
look<00:03:51.840><c> later</c><00:03:52.080><c> on.</c>

look later on.

look later on.
Is<00:03:54.159><c> it</c><00:03:54.400><c> working?</c>

Is it working?

Is it working?
&gt;&gt; Okay,<00:03:55.840><c> perfect.</c><00:03:56.319><c> Okay.</c><00:03:57.760><c> So</c>

&gt;&gt; Okay, perfect. Okay. So

&gt;&gt; Okay, perfect. Okay. So
now<00:04:00.319><c> this</c><00:04:00.640><c> is</c><00:04:00.799><c> something</c>

now this is something

now this is something
uh<00:04:03.120><c> you</c><00:04:03.439><c> can</c><00:04:04.560><c> take</c><00:04:04.799><c> an</c><00:04:04.959><c> image</c><00:04:05.360><c> now</c><00:04:05.840><c> or</c><00:04:06.799><c> you</c><00:04:07.040><c> can</c>

uh you can take an image now or you can

uh you can take an image now or you can
uh<00:04:07.519><c> do</c><00:04:07.680><c> that</c><00:04:08.080><c> survey</c><00:04:08.640><c> later</c><00:04:08.879><c> on.</c><00:04:09.280><c> I</c><00:04:09.519><c> mean</c><00:04:10.720><c> I</c>

uh do that survey later on. I mean I

uh do that survey later on. I mean I
don't<00:04:11.120><c> like</c><00:04:11.280><c> this</c><00:04:11.519><c> but</c><00:04:11.760><c> again</c><00:04:12.080><c> this</c><00:04:12.239><c> was</c><00:04:12.560><c> given</c>

don't like this but again this was given

don't like this but again this was given
by<00:04:13.040><c> my</c><00:04:13.280><c> manager.</c><00:04:13.760><c> So</c><00:04:14.720><c> so</c><00:04:15.200><c> this</c><00:04:15.360><c> is</c><00:04:15.519><c> just</c><00:04:15.840><c> it</c>

by my manager. So so this is just it

by my manager. So so this is just it
might<00:04:16.239><c> ask</c><00:04:16.479><c> you</c><00:04:16.720><c> few</c><00:04:16.880><c> questions.</c><00:04:17.199><c> I</c><00:04:17.359><c> have</c><00:04:17.440><c> no</c>

might ask you few questions. I have no

might ask you few questions. I have no
idea<00:04:17.759><c> what</c><00:04:18.000><c> question</c><00:04:18.239><c> they</c><00:04:18.400><c> will</c><00:04:18.639><c> ask,</c><00:04:19.280><c> but</c><00:04:19.680><c> uh</c>

idea what question they will ask, but uh

idea what question they will ask, but uh
you<00:04:20.000><c> will</c><00:04:20.160><c> get</c><00:04:20.320><c> some</c><00:04:20.560><c> $25</c><00:04:21.359><c> credit</c><00:04:22.560><c> and</c><00:04:23.280><c> uh</c><00:04:24.080><c> if</c>

you will get some $25 credit and uh if

you will get some $25 credit and uh if
you<00:04:24.400><c> don't</c><00:04:24.560><c> want</c><00:04:24.720><c> to</c><00:04:24.800><c> do</c><00:04:24.880><c> it,</c><00:04:25.120><c> don't</c><00:04:25.280><c> do</c><00:04:25.440><c> it.</c>

you don't want to do it, don't do it.

you don't want to do it, don't do it.
I'll<00:04:25.840><c> give</c><00:04:25.919><c> you</c><00:04:26.160><c> $25</c><00:04:26.720><c> credit.</c><00:04:27.199><c> So,</c><00:04:27.280><c> I</c><00:04:27.440><c> have</c><00:04:27.600><c> it.</c>

I'll give you $25 credit. So, I have it.

I'll give you $25 credit. So, I have it.
So,

So,

So,
okay.<00:04:31.199><c> So,</c>

okay. So,

okay. So,
yeah.<00:04:33.680><c> And</c><00:04:34.400><c> uh</c><00:04:35.199><c> I</c><00:04:35.440><c> don't</c><00:04:35.520><c> know</c><00:04:35.680><c> why</c><00:04:35.919><c> this</c><00:04:36.160><c> slide</c>

yeah. And uh I don't know why this slide

yeah. And uh I don't know why this slide
is<00:04:36.720><c> next,</c><00:04:37.040><c> but</c><00:04:38.000><c> so</c><00:04:38.240><c> this</c><00:04:38.479><c> is</c><00:04:38.880><c> my</c><00:04:39.360><c> Oh,</c><00:04:39.600><c> I</c><00:04:39.759><c> I</c>

is next, but so this is my Oh, I I

is next, but so this is my Oh, I I
actually<00:04:40.240><c> forgot</c><00:04:40.560><c> to</c><00:04:40.720><c> introduce</c><00:04:41.120><c> myself.</c><00:04:41.520><c> So</c>

actually forgot to introduce myself. So

actually forgot to introduce myself. So
I<00:04:43.040><c> work</c><00:04:43.199><c> with</c><00:04:43.440><c> AWS</c><00:04:44.320><c> uh</c><00:04:44.479><c> as</c><00:04:44.720><c> a</c><00:04:44.880><c> principal</c><00:04:45.600><c> uh</c>

I work with AWS uh as a principal uh

I work with AWS uh as a principal uh
machine<00:04:46.000><c> learning</c><00:04:46.320><c> advocate.</c><00:04:46.960><c> I'm</c><00:04:47.199><c> with</c><00:04:47.360><c> this</c>

machine learning advocate. I'm with this

machine learning advocate. I'm with this
company<00:04:47.840><c> for</c><00:04:48.160><c> last</c><00:04:48.400><c> 6</c><00:04:48.639><c> months.</c><00:04:49.440><c> I</c><00:04:49.759><c> focus</c>

company for last 6 months. I focus

company for last 6 months. I focus
mostly<00:04:50.479><c> on</c><00:04:51.120><c> um</c><00:04:51.840><c> natural</c><00:04:52.240><c> language</c><00:04:53.120><c> and</c><00:04:53.759><c> uh</c><00:04:54.160><c> rag</c>

mostly on um natural language and uh rag

mostly on um natural language and uh rag
and<00:04:54.639><c> fine-tuning.</c>

and fine-tuning.

and fine-tuning.
And<00:04:56.560><c> if</c><00:04:56.800><c> you</c><00:04:56.960><c> have</c><00:04:57.120><c> any</c><00:04:57.280><c> questions</c><00:04:57.600><c> around</c><00:04:58.000><c> the</c>

And if you have any questions around the

And if you have any questions around the
talk<00:04:58.400><c> that</c><00:04:58.639><c> we</c><00:04:58.800><c> are</c><00:04:58.880><c> going</c><00:04:59.040><c> to</c><00:04:59.120><c> discuss</c><00:04:59.759><c> uh</c><00:05:00.000><c> or</c>

talk that we are going to discuss uh or

talk that we are going to discuss uh or
anything<00:05:00.560><c> around</c><00:05:01.280><c> uh</c><00:05:01.440><c> machine</c><00:05:01.759><c> learning</c><00:05:02.000><c> or</c>

anything around uh machine learning or

anything around uh machine learning or
generative<00:05:03.040><c> AI</c><00:05:03.360><c> feel</c><00:05:03.520><c> free</c><00:05:03.680><c> to</c><00:05:04.160><c> uh</c><00:05:04.240><c> ping</c><00:05:04.560><c> me.</c>

generative AI feel free to uh ping me.

generative AI feel free to uh ping me.
It's<00:05:05.440><c> not</c><00:05:05.600><c> just</c><00:05:05.840><c> about</c><00:05:06.080><c> this</c><00:05:06.320><c> session</c><00:05:07.280><c> but</c><00:05:07.759><c> uh</c>

It's not just about this session but uh

It's not just about this session but uh
my<00:05:08.320><c> takeaway</c><00:05:09.280><c> at</c><00:05:09.919><c> whenever</c><00:05:10.320><c> I</c><00:05:10.479><c> go</c><00:05:10.639><c> and</c><00:05:10.800><c> speak</c>

my takeaway at whenever I go and speak

my takeaway at whenever I go and speak
at<00:05:11.199><c> any</c><00:05:11.440><c> conference</c><00:05:11.759><c> at</c><00:05:12.080><c> this</c><00:05:12.400><c> scale</c><00:05:12.800><c> is</c><00:05:13.600><c> uh</c>

at any conference at this scale is uh

at any conference at this scale is uh
just<00:05:13.840><c> to</c><00:05:14.080><c> make</c><00:05:15.039><c> few</c><00:05:16.160><c> connections</c><00:05:16.560><c> with</c><00:05:16.800><c> whom</c><00:05:17.280><c> I</c>

just to make few connections with whom I

just to make few connections with whom I
can<00:05:17.759><c> work</c><00:05:17.919><c> with</c><00:05:18.639><c> uh</c><00:05:18.960><c> you</c><00:05:19.120><c> know</c><00:05:19.360><c> after</c><00:05:19.680><c> this</c>

can work with uh you know after this

can work with uh you know after this
conference

conference

conference
uh<00:05:22.000><c> because</c><00:05:22.960><c> as</c><00:05:23.280><c> long</c><00:05:23.440><c> as</c><00:05:23.680><c> learning</c><00:05:24.000><c> is</c>

uh because as long as learning is

uh because as long as learning is
concerned<00:05:24.639><c> we</c><00:05:24.880><c> can</c><00:05:25.039><c> learn</c><00:05:25.360><c> everything</c><00:05:26.000><c> at</c>

concerned we can learn everything at

concerned we can learn everything at
home<00:05:26.639><c> right</c><00:05:26.880><c> and</c><00:05:27.120><c> so</c><00:05:27.280><c> you</c><00:05:27.520><c> don't</c><00:05:27.680><c> have</c><00:05:27.759><c> to</c><00:05:27.919><c> come</c>

home right and so you don't have to come

home right and so you don't have to come
to<00:05:28.240><c> a</c><00:05:28.479><c> conference</c><00:05:29.600><c> uh</c><00:05:29.759><c> so</c><00:05:30.000><c> feel</c><00:05:30.160><c> free</c><00:05:30.320><c> to</c><00:05:31.520><c> uh</c>

to a conference uh so feel free to uh

to a conference uh so feel free to uh
connect<00:05:32.639><c> so</c><00:05:32.880><c> with</c><00:05:33.120><c> that</c><00:05:33.840><c> I</c><00:05:34.160><c> will</c><00:05:34.639><c> just</c><00:05:35.199><c> switch</c>

connect so with that I will just switch

connect so with that I will just switch
to<00:05:36.560><c> uh</c><00:05:37.120><c> the</c>

to uh the

to uh the
GitHub<00:05:39.120><c> repository.</c><00:05:39.840><c> Okay.</c><00:05:40.479><c> So,</c><00:05:40.720><c> and</c><00:05:41.039><c> I'll</c>

GitHub repository. Okay. So, and I'll

GitHub repository. Okay. So, and I'll
just<00:05:42.639><c> uh</c><00:05:43.440><c> walk</c><00:05:43.680><c> you</c><00:05:43.919><c> through</c><00:05:44.080><c> the</c><00:05:44.320><c> notebook.</c>

just uh walk you through the notebook.

just uh walk you through the notebook.
So,<00:05:45.360><c> the</c><00:05:45.520><c> my</c><00:05:45.840><c> idea</c><00:05:46.160><c> is</c><00:05:46.560><c> not</c><00:05:46.720><c> to</c><00:05:46.960><c> have</c><00:05:47.120><c> any</c>

So, the my idea is not to have any

So, the my idea is not to have any
presentation<00:05:48.080><c> because</c><00:05:49.280><c> uh</c><00:05:49.520><c> first</c><00:05:49.919><c> uh</c><00:05:50.000><c> I'm</c>

presentation because uh first uh I'm

presentation because uh first uh I'm
lazy<00:05:50.560><c> and</c><00:05:50.880><c> second</c><00:05:51.199><c> it's</c><00:05:51.440><c> little</c><00:05:51.759><c> complicated.</c>

lazy and second it's little complicated.

lazy and second it's little complicated.
I<00:05:52.400><c> thought</c><00:05:52.479><c> that</c><00:05:52.720><c> taking</c><00:05:53.120><c> images</c><00:05:53.440><c> and</c>

I thought that taking images and

I thought that taking images and
embedded<00:05:54.160><c> in</c><00:05:54.320><c> the</c><00:05:54.479><c> notebook</c><00:05:54.880><c> is</c><00:05:55.759><c> uh</c><00:05:55.919><c> much</c>

embedded in the notebook is uh much

embedded in the notebook is uh much
easier.<00:05:57.199><c> So</c><00:05:58.639><c> uh</c><00:05:59.120><c> you</c><00:05:59.440><c> will</c><00:05:59.600><c> find</c><00:06:00.000><c> this</c><00:06:00.720><c> uh</c>

easier. So uh you will find this uh

easier. So uh you will find this uh
GitHub<00:06:01.280><c> repository</c>

GitHub repository

GitHub repository
uh<00:06:03.039><c> and</c><00:06:03.360><c> in</c><00:06:03.600><c> that</c><00:06:03.840><c> there</c><00:06:04.000><c> are</c><00:06:05.280><c> many</c><00:06:05.600><c> things</c>

uh and in that there are many things

uh and in that there are many things
there<00:06:06.160><c> but</c><00:06:06.639><c> what</c><00:06:06.960><c> we</c><00:06:07.120><c> are</c><00:06:07.280><c> going</c><00:06:07.440><c> to</c><00:06:07.520><c> focus</c><00:06:07.840><c> on</c>

there but what we are going to focus on

there but what we are going to focus on
is<00:06:08.319><c> if</c><00:06:08.479><c> you</c><00:06:08.639><c> come</c><00:06:08.720><c> to</c><00:06:08.880><c> this</c><00:06:09.840><c> uh</c><00:06:10.400><c> section</c><00:06:10.880><c> 8</c><00:06:12.080><c> and</c>

is if you come to this uh section 8 and

is if you come to this uh section 8 and
come<00:06:12.639><c> to</c><00:06:12.800><c> this</c><00:06:13.120><c> first</c><00:06:13.360><c> one</c><00:06:13.840><c> agentic</c>

come to this first one agentic

come to this first one agentic
voice-based<00:06:15.360><c> rag</c>

voice-based rag

voice-based rag
uh<00:06:17.680><c> so</c><00:06:18.080><c> I</c><00:06:18.400><c> just</c><00:06:18.639><c> added</c><00:06:19.039><c> that</c><00:06:19.199><c> agent</c><00:06:19.680><c> thing</c>

uh so I just added that agent thing

uh so I just added that agent thing
yesterday<00:06:20.400><c> so</c><00:06:20.720><c> that's</c><00:06:21.039><c> why</c><00:06:22.319><c> so</c><00:06:22.560><c> I</c><00:06:22.720><c> had</c><00:06:22.880><c> no</c><00:06:23.120><c> idea</c>

yesterday so that's why so I had no idea

yesterday so that's why so I had no idea
of<00:06:23.600><c> that</c><00:06:24.080><c> so</c><00:06:24.880><c> uh</c><00:06:25.919><c> so</c><00:06:26.160><c> what</c><00:06:26.319><c> we</c><00:06:26.479><c> are</c><00:06:26.560><c> going</c><00:06:26.639><c> to</c><00:06:26.800><c> do</c>

of that so uh so what we are going to do

of that so uh so what we are going to do
is<00:06:27.520><c> these</c><00:06:27.840><c> two</c><00:06:28.000><c> notebooks</c><00:06:28.400><c> are</c><00:06:28.639><c> exactly</c><00:06:28.960><c> same.</c>

is these two notebooks are exactly same.

is these two notebooks are exactly same.
One<00:06:29.360><c> is</c><00:06:29.520><c> without</c><00:06:29.840><c> output,</c><00:06:30.319><c> one</c><00:06:30.479><c> is</c><00:06:30.639><c> with</c>

One is without output, one is with

One is without output, one is with
output.<00:06:31.600><c> I</c><00:06:31.919><c> find</c><00:06:32.080><c> it</c><00:06:32.560><c> uh</c><00:06:33.360><c> useful</c><00:06:33.759><c> to</c><00:06:34.000><c> have</c><00:06:34.240><c> both</c>

output. I find it uh useful to have both

output. I find it uh useful to have both
copies<00:06:34.880><c> because</c><00:06:35.120><c> if</c><00:06:35.280><c> you</c><00:06:35.440><c> are</c><00:06:35.600><c> doing</c><00:06:35.680><c> it</c><00:06:35.840><c> for</c>

copies because if you are doing it for

copies because if you are doing it for
the<00:06:36.160><c> first</c><00:06:36.400><c> time</c><00:06:37.440><c> um</c><00:06:37.680><c> you</c><00:06:37.919><c> may</c><00:06:38.080><c> like</c><00:06:38.240><c> to</c><00:06:38.479><c> start</c>

the first time um you may like to start

the first time um you may like to start
with<00:06:38.800><c> this</c><00:06:39.120><c> don't</c><00:06:39.360><c> see</c><00:06:39.520><c> the</c><00:06:39.680><c> output</c><00:06:40.240><c> and</c><00:06:40.560><c> run</c>

with this don't see the output and run

with this don't see the output and run
through<00:06:41.199><c> and</c><00:06:41.520><c> at</c><00:06:41.680><c> the</c><00:06:41.840><c> same</c><00:06:41.919><c> time</c><00:06:42.080><c> if</c><00:06:42.240><c> you</c><00:06:42.400><c> want</c>

through and at the same time if you want

through and at the same time if you want
to<00:06:42.560><c> see</c><00:06:42.720><c> what</c><00:06:42.960><c> it</c><00:06:43.120><c> is</c><00:06:43.360><c> you</c><00:06:43.520><c> know</c><00:06:43.600><c> what</c><00:06:43.759><c> is</c><00:06:43.919><c> the</c>

to see what it is you know what is the

to see what it is you know what is the
expected<00:06:44.400><c> output</c><00:06:44.880><c> and</c><00:06:45.120><c> all</c><00:06:45.280><c> that</c><00:06:45.440><c> you</c><00:06:45.680><c> can</c><00:06:45.840><c> go</c>

expected output and all that you can go

expected output and all that you can go
onto<00:06:46.479><c> this</c><00:06:47.600><c> all</c><00:06:47.680><c> right</c><00:06:47.919><c> so</c><00:06:48.560><c> for</c><00:06:48.880><c> the</c><00:06:49.039><c> purpose</c>

onto this all right so for the purpose

onto this all right so for the purpose
of<00:06:49.680><c> today's</c><00:06:50.400><c> uh</c><00:06:50.960><c> uh</c><00:06:51.120><c> workshop</c><00:06:51.840><c> I</c><00:06:52.080><c> will</c><00:06:52.240><c> start</c>

of today's uh uh workshop I will start

of today's uh uh workshop I will start
with<00:06:52.720><c> an</c><00:06:52.960><c> introduction</c>

with an introduction

with an introduction
and<00:06:54.800><c> then</c><00:06:54.960><c> I</c><00:06:55.199><c> will</c><00:06:55.680><c> um</c><00:06:56.000><c> come</c><00:06:56.240><c> here</c><00:06:57.039><c> okay</c><00:06:58.000><c> and</c><00:06:58.720><c> if</c>

and then I will um come here okay and if

and then I will um come here okay and if
you<00:06:59.199><c> feel</c><00:06:59.520><c> that</c><00:07:00.080><c> uh</c><00:07:00.400><c> this</c><00:07:00.639><c> is</c><00:07:00.800><c> not</c><00:07:01.120><c> something</c>

you feel that uh this is not something

you feel that uh this is not something
that<00:07:01.759><c> you</c><00:07:02.000><c> are</c><00:07:02.319><c> interested</c><00:07:02.720><c> in</c><00:07:03.360><c> or</c><00:07:03.759><c> this</c><00:07:04.000><c> is</c>

that you are interested in or this is

that you are interested in or this is
not<00:07:04.319><c> something</c><00:07:04.560><c> that</c><00:07:04.960><c> you</c><00:07:05.199><c> are</c><00:07:05.360><c> looking</c><00:07:05.520><c> for</c>

not something that you are looking for

not something that you are looking for
you<00:07:06.160><c> know</c><00:07:06.400><c> feel</c><00:07:06.639><c> free</c><00:07:06.800><c> to</c><00:07:07.599><c> uh</c><00:07:08.080><c> uh</c><00:07:08.240><c> you</c><00:07:08.400><c> know</c><00:07:08.800><c> uh</c>

you know feel free to uh uh you know uh

you know feel free to uh uh you know uh
go<00:07:10.400><c> to</c><00:07:10.560><c> some</c><00:07:10.720><c> other</c><00:07:10.960><c> place</c><00:07:11.280><c> because</c><00:07:11.680><c> I</c><00:07:11.919><c> don't</c>

go to some other place because I don't

go to some other place because I don't
want<00:07:12.240><c> to</c><00:07:12.479><c> waste</c><00:07:12.800><c> your</c><00:07:13.120><c> time</c><00:07:13.759><c> uh</c><00:07:14.240><c> uh</c><00:07:14.319><c> but</c><00:07:14.560><c> I</c><00:07:14.720><c> want</c>

want to waste your time uh uh but I want

want to waste your time uh uh but I want
to<00:07:14.960><c> make</c><00:07:15.120><c> sure</c><00:07:15.199><c> that</c><00:07:15.440><c> if</c><00:07:15.599><c> you</c><00:07:15.759><c> are</c><00:07:15.919><c> here</c><00:07:16.080><c> for</c>

to make sure that if you are here for

to make sure that if you are here for
next<00:07:16.639><c> 1</c><00:07:16.880><c> hour</c><00:07:17.280><c> you</c><00:07:17.599><c> learn</c><00:07:17.840><c> something</c><00:07:18.160><c> new</c><00:07:19.599><c> uh</c>

next 1 hour you learn something new uh

next 1 hour you learn something new uh
with<00:07:20.080><c> respect</c><00:07:20.400><c> to</c><00:07:20.560><c> what</c><00:07:20.720><c> you</c><00:07:20.960><c> already</c><00:07:21.199><c> know</c><00:07:21.440><c> at</c>

with respect to what you already know at

with respect to what you already know at
this<00:07:21.919><c> point</c><00:07:22.000><c> in</c><00:07:22.240><c> time</c><00:07:23.440><c> okay</c><00:07:24.160><c> and</c><00:07:24.400><c> if</c><00:07:24.560><c> you</c><00:07:24.639><c> have</c>

this point in time okay and if you have

this point in time okay and if you have
any<00:07:24.960><c> questions</c><00:07:25.440><c> uh</c><00:07:25.599><c> feel</c><00:07:25.759><c> free</c><00:07:25.919><c> to</c><00:07:26.080><c> ask</c><00:07:26.720><c> so</c>

any questions uh feel free to ask so

any questions uh feel free to ask so
that's<00:07:28.160><c> that's</c><00:07:28.560><c> the</c><00:07:28.800><c> other</c><00:07:28.960><c> thing</c><00:07:29.280><c> okay</c><00:07:29.520><c> let</c>

that's that's the other thing okay let

that's that's the other thing okay let
me<00:07:29.919><c> just</c><00:07:30.400><c> expand</c><00:07:30.800><c> And</c><00:07:30.960><c> this</c><00:07:32.000><c> is</c><00:07:32.160><c> little</c><00:07:32.479><c> too</c>

me just expand And this is little too

me just expand And this is little too
big<00:07:33.199><c> uh</c><00:07:33.360><c> here.</c><00:07:34.000><c> So</c>

big uh here. So

big uh here. So
uh<00:07:36.720><c> okay.</c><00:07:37.840><c> So</c><00:07:39.199><c> I</c><00:07:39.680><c> noticed</c><00:07:40.000><c> that</c><00:07:40.319><c> most</c><00:07:40.639><c> of</c><00:07:40.800><c> you</c>

uh okay. So I noticed that most of you

uh okay. So I noticed that most of you
are<00:07:41.360><c> aware</c><00:07:41.680><c> of</c><00:07:41.840><c> rag.</c><00:07:42.560><c> Uh</c><00:07:43.120><c> but</c><00:07:43.360><c> we</c><00:07:43.520><c> are</c><00:07:43.680><c> going</c><00:07:43.759><c> to</c>

are aware of rag. Uh but we are going to

are aware of rag. Uh but we are going to
talk<00:07:44.160><c> about</c><00:07:44.720><c> uh</c><00:07:44.960><c> multimodal</c><00:07:46.080><c> rack</c><00:07:46.880><c> for</c><00:07:47.120><c> a</c>

talk about uh multimodal rack for a

talk about uh multimodal rack for a
moment.<00:07:47.599><c> Uh</c><00:07:47.840><c> just</c><00:07:48.000><c> to</c><00:07:48.240><c> set</c><00:07:48.479><c> the</c><00:07:48.639><c> premise</c><00:07:49.440><c> and</c>

moment. Uh just to set the premise and

moment. Uh just to set the premise and
then<00:07:50.000><c> we</c><00:07:50.240><c> will</c><00:07:50.800><c> uh</c><00:07:51.039><c> get</c><00:07:51.199><c> into</c><00:07:51.440><c> the</c><00:07:51.599><c> vision</c>

then we will uh get into the vision

then we will uh get into the vision
based<00:07:52.160><c> retrieval.</c><00:07:52.800><c> Okay.</c><00:07:54.240><c> So</c><00:07:54.400><c> if</c><00:07:54.639><c> you</c><00:07:54.800><c> think</c>

based retrieval. Okay. So if you think

based retrieval. Okay. So if you think
about<00:07:55.759><c> uh</c><00:07:56.720><c> multimodal</c><00:07:57.840><c> rag</c><00:07:59.120><c> uh</c>

about uh multimodal rag uh

about uh multimodal rag uh
what<00:08:02.240><c> we</c><00:08:02.800><c> essentially</c><00:08:03.280><c> do</c><00:08:03.599><c> is</c><00:08:04.400><c> and</c><00:08:04.720><c> this</c><00:08:04.879><c> is</c><00:08:05.120><c> by</c>

what we essentially do is and this is by

what we essentially do is and this is by
no<00:08:05.599><c> mean</c><00:08:05.840><c> is</c><00:08:06.000><c> the</c><00:08:06.160><c> only</c><00:08:06.479><c> architecture.</c><00:08:06.960><c> This</c>

no mean is the only architecture. This

no mean is the only architecture. This
is<00:08:07.280><c> just</c><00:08:07.440><c> one</c><00:08:07.680><c> of</c><00:08:07.840><c> the</c><00:08:08.000><c> architecture.</c><00:08:08.560><c> There</c>

is just one of the architecture. There

is just one of the architecture. There
are<00:08:08.879><c> many</c><00:08:09.199><c> different</c><00:08:09.440><c> ways</c><00:08:09.599><c> that</c><00:08:09.840><c> you</c><00:08:10.000><c> can</c><00:08:10.080><c> do</c>

are many different ways that you can do

are many different ways that you can do
multimodal<00:08:11.120><c> rack</c><00:08:11.840><c> but</c><00:08:12.160><c> in</c><00:08:12.319><c> general</c><00:08:12.720><c> this</c><00:08:12.960><c> is</c>

multimodal rack but in general this is

multimodal rack but in general this is
what<00:08:13.680><c> uh</c><00:08:14.000><c> we</c><00:08:14.319><c> have</c><00:08:14.560><c> been</c><00:08:14.720><c> doing</c><00:08:14.879><c> and</c><00:08:15.120><c> still</c>

what uh we have been doing and still

what uh we have been doing and still
today<00:08:15.599><c> we</c><00:08:15.759><c> do.</c><00:08:16.720><c> You</c><00:08:16.960><c> take</c><00:08:17.120><c> a</c><00:08:17.360><c> data</c><00:08:18.000><c> and</c><00:08:18.319><c> that</c>

today we do. You take a data and that

today we do. You take a data and that
data<00:08:19.280><c> will</c><00:08:19.520><c> contain</c><00:08:20.000><c> images,</c><00:08:20.639><c> text</c><00:08:21.440><c> and</c><00:08:21.919><c> uh</c>

data will contain images, text and uh

data will contain images, text and uh
tables.

tables.

tables.
The<00:08:24.160><c> first</c><00:08:24.560><c> thing</c><00:08:24.720><c> that</c><00:08:24.960><c> we</c><00:08:25.120><c> do</c><00:08:25.360><c> is</c><00:08:25.680><c> we</c><00:08:26.000><c> use</c>

The first thing that we do is we use

The first thing that we do is we use
some<00:08:26.639><c> framework</c><00:08:27.280><c> or</c>

some framework or

some framework or
is<00:08:29.280><c> that</c><00:08:29.680><c> so</c><00:08:30.000><c> bad</c><00:08:30.400><c> or</c>

is that so bad or

is that so bad or
okay<00:08:32.959><c> thank</c><00:08:33.200><c> you.</c><00:08:34.000><c> So</c><00:08:35.440><c> so</c><00:08:35.599><c> we</c><00:08:35.839><c> can</c><00:08:36.000><c> use</c><00:08:36.240><c> any</c>

okay thank you. So so we can use any

okay thank you. So so we can use any
framework<00:08:37.200><c> of</c><00:08:37.360><c> our</c><00:08:37.599><c> choice</c><00:08:37.760><c> or</c><00:08:38.000><c> you</c><00:08:38.159><c> can</c><00:08:38.240><c> write</c>

framework of our choice or you can write

framework of our choice or you can write
your<00:08:38.640><c> own</c><00:08:38.800><c> custom</c><00:08:39.200><c> script</c><00:08:39.440><c> or</c><00:08:39.680><c> you</c><00:08:39.839><c> can</c><00:08:39.919><c> use</c>

your own custom script or you can use

your own custom script or you can use
any<00:08:40.320><c> managed</c><00:08:40.640><c> service</c><00:08:40.880><c> like</c><00:08:41.120><c> text</c><00:08:41.599><c> OCR</c><00:08:42.080><c> based</c>

any managed service like text OCR based

any managed service like text OCR based
technique.<00:08:43.039><c> The</c><00:08:43.279><c> idea</c><00:08:43.519><c> is</c><00:08:43.760><c> you</c><00:08:44.159><c> extract</c><00:08:44.720><c> the</c>

technique. The idea is you extract the

technique. The idea is you extract the
images,<00:08:45.600><c> tables</c><00:08:46.160><c> and</c>

images, tables and

images, tables and
uh<00:08:48.399><c> uh</c><00:08:48.640><c> text</c><00:08:49.360><c> out</c><00:08:49.760><c> you</c><00:08:49.839><c> know</c><00:08:50.000><c> separately.</c><00:08:51.120><c> You</c>

uh uh text out you know separately. You

uh uh text out you know separately. You
can<00:08:51.360><c> have</c><00:08:51.519><c> some</c><00:08:51.680><c> metadata</c><00:08:52.399><c> uh</c><00:08:52.560><c> to</c><00:08:52.959><c> make</c><00:08:53.200><c> an</c><00:08:53.680><c> uh</c>

can have some metadata uh to make an uh

can have some metadata uh to make an uh
hash<00:08:55.040><c> which</c><00:08:55.760><c> tells</c><00:08:56.080><c> you</c><00:08:56.240><c> that</c><00:08:56.399><c> this</c><00:08:56.640><c> image</c><00:08:56.959><c> is</c>

hash which tells you that this image is

hash which tells you that this image is
coming<00:08:57.279><c> from</c><00:08:57.519><c> which</c><00:08:57.680><c> page</c><00:08:57.920><c> and</c><00:08:58.160><c> all</c><00:08:58.320><c> that.</c><00:08:58.640><c> But</c>

coming from which page and all that. But

coming from which page and all that. But
essentially<00:08:59.279><c> you</c><00:08:59.839><c> divide</c><00:09:00.160><c> all</c><00:09:00.399><c> these</c><00:09:00.640><c> three</c>

essentially you divide all these three

essentially you divide all these three
separately.<00:09:02.160><c> Then</c><00:09:02.800><c> you</c><00:09:03.040><c> can</c><00:09:03.200><c> use</c><00:09:03.440><c> one</c>

separately. Then you can use one

separately. Then you can use one
multimodal<00:09:04.399><c> embedding</c><00:09:04.959><c> model</c><00:09:05.680><c> and</c><00:09:05.920><c> this</c>

multimodal embedding model and this

multimodal embedding model and this
multimodal<00:09:06.640><c> embedding</c><00:09:07.040><c> model</c><00:09:07.279><c> can</c><00:09:07.440><c> take</c><00:09:07.680><c> any</c>

multimodal embedding model can take any

multimodal embedding model can take any
of<00:09:08.080><c> these</c><00:09:08.560><c> three</c><00:09:08.800><c> entities</c><00:09:09.279><c> because</c><00:09:09.440><c> it's</c>

of these three entities because it's

of these three entities because it's
multimodal.<00:09:10.640><c> It</c><00:09:10.800><c> can</c><00:09:11.040><c> take</c><00:09:11.360><c> any</c><00:09:11.600><c> of</c><00:09:11.760><c> these</c>

multimodal. It can take any of these

multimodal. It can take any of these
three<00:09:12.320><c> and</c><00:09:12.560><c> when</c><00:09:12.720><c> I</c><00:09:12.800><c> say</c><00:09:12.959><c> multimodal</c><00:09:13.760><c> you</c><00:09:14.000><c> can</c>

three and when I say multimodal you can

three and when I say multimodal you can
think<00:09:14.240><c> of</c><00:09:14.399><c> it</c><00:09:14.560><c> like</c><00:09:15.120><c> input</c><00:09:15.519><c> can</c><00:09:15.680><c> be</c>

think of it like input can be

think of it like input can be
multimodal.<00:09:17.200><c> Okay.</c><00:09:17.760><c> And</c><00:09:17.920><c> then</c><00:09:18.080><c> it</c><00:09:18.240><c> will</c>

multimodal. Okay. And then it will

multimodal. Okay. And then it will
generate<00:09:18.640><c> some</c><00:09:18.880><c> vectors</c><00:09:19.360><c> for</c><00:09:19.600><c> images.</c><00:09:20.000><c> it</c>

generate some vectors for images. it

generate some vectors for images. it
will<00:09:20.320><c> generate</c><00:09:20.560><c> some</c><00:09:20.720><c> vectors,</c><00:09:21.040><c> tables,</c><00:09:21.440><c> text</c>

will generate some vectors, tables, text

will generate some vectors, tables, text
and<00:09:21.920><c> all</c><00:09:22.000><c> that.</c><00:09:22.720><c> Then</c><00:09:22.959><c> you</c><00:09:23.120><c> go</c><00:09:23.279><c> to</c><00:09:23.440><c> the</c>

and all that. Then you go to the

and all that. Then you go to the
database<00:09:24.320><c> any</c><00:09:24.560><c> vector</c><00:09:24.959><c> database</c><00:09:25.360><c> and</c><00:09:25.600><c> store</c>

database any vector database and store

database any vector database and store
all<00:09:26.000><c> these</c><00:09:26.240><c> embeddings.</c><00:09:26.880><c> So</c><00:09:27.040><c> what</c><00:09:27.200><c> you</c><00:09:27.360><c> are</c>

all these embeddings. So what you are

all these embeddings. So what you are
essentially<00:09:27.920><c> storing</c><00:09:28.320><c> here</c><00:09:28.959><c> are</c><00:09:29.200><c> the</c><00:09:29.440><c> actual</c>

essentially storing here are the actual

essentially storing here are the actual
embeddings<00:09:30.320><c> of</c><00:09:30.640><c> text,</c><00:09:31.200><c> tables</c><00:09:31.600><c> and</c><00:09:31.839><c> images.</c>

embeddings of text, tables and images.

embeddings of text, tables and images.
And<00:09:33.519><c> then</c><00:09:33.760><c> comes</c><00:09:34.000><c> the</c><00:09:34.240><c> retrieval</c><00:09:34.720><c> part.</c><00:09:35.279><c> When</c>

And then comes the retrieval part. When

And then comes the retrieval part. When
you<00:09:35.760><c> ask</c><00:09:36.000><c> a</c><00:09:36.240><c> question</c><00:09:36.880><c> any</c><00:09:37.200><c> raw</c><00:09:37.519><c> question</c><00:09:37.839><c> like</c>

you ask a question any raw question like

you ask a question any raw question like
raw<00:09:38.399><c> text,</c><00:09:39.760><c> it</c><00:09:40.320><c> goes</c><00:09:40.560><c> through</c><00:09:40.800><c> the</c><00:09:41.040><c> same</c>

raw text, it goes through the same

raw text, it goes through the same
embedding<00:09:41.920><c> model.</c><00:09:42.800><c> Then</c><00:09:42.959><c> it</c><00:09:43.200><c> is</c><00:09:43.360><c> first</c>

embedding model. Then it is first

embedding model. Then it is first
searched<00:09:44.000><c> here.</c><00:09:44.480><c> It</c><00:09:44.720><c> will</c><00:09:44.880><c> get</c><00:09:45.040><c> some</c><00:09:45.279><c> relevant</c>

searched here. It will get some relevant

searched here. It will get some relevant
chunk<00:09:46.000><c> which</c><00:09:46.240><c> could</c><00:09:46.480><c> be</c><00:09:46.640><c> again</c><00:09:47.120><c> image,</c><00:09:47.600><c> text</c>

chunk which could be again image, text

chunk which could be again image, text
or<00:09:48.080><c> table</c><00:09:49.200><c> and</c><00:09:49.440><c> then</c><00:09:49.760><c> you</c><00:09:50.000><c> take</c><00:09:50.160><c> those</c><00:09:50.640><c> chunks</c>

or table and then you take those chunks

or table and then you take those chunks
along<00:09:51.600><c> with</c><00:09:51.760><c> your</c><00:09:52.000><c> text</c><00:09:52.320><c> and</c><00:09:52.640><c> use</c><00:09:52.800><c> a</c>

along with your text and use a

along with your text and use a
multimodal<00:09:53.680><c> LLM.</c><00:09:54.240><c> Why</c><00:09:54.399><c> multimodal?</c><00:09:55.200><c> Because</c>

multimodal LLM. Why multimodal? Because

multimodal LLM. Why multimodal? Because
your<00:09:55.680><c> relevant</c><00:09:56.080><c> chunk</c><00:09:56.800><c> can</c><00:09:57.040><c> be</c><00:09:57.680><c> images,</c><00:09:58.160><c> text</c>

your relevant chunk can be images, text

your relevant chunk can be images, text
or<00:09:58.720><c> table,</c><00:09:59.680><c> right?</c><00:10:00.399><c> And</c><00:10:00.560><c> then</c><00:10:00.720><c> you</c><00:10:00.959><c> get</c><00:10:01.040><c> an</c>

or table, right? And then you get an

or table, right? And then you get an
answer.<00:10:01.519><c> So</c><00:10:01.680><c> this</c><00:10:01.839><c> is</c><00:10:01.920><c> one</c><00:10:02.160><c> approach.</c><00:10:03.600><c> The</c>

answer. So this is one approach. The

answer. So this is one approach. The
second<00:10:04.160><c> approach</c><00:10:05.120><c> is</c><00:10:06.320><c> you</c><00:10:06.640><c> do</c><00:10:06.720><c> the</c><00:10:06.959><c> same</c><00:10:07.040><c> thing</c>

second approach is you do the same thing

second approach is you do the same thing
like<00:10:07.519><c> this</c><00:10:07.680><c> part</c><00:10:07.839><c> is</c><00:10:08.080><c> common.</c><00:10:08.959><c> After</c><00:10:09.279><c> that</c><00:10:10.160><c> you</c>

like this part is common. After that you

like this part is common. After that you
used<00:10:10.800><c> a</c><00:10:11.040><c> model</c><00:10:11.680><c> which</c><00:10:12.000><c> will</c><00:10:12.160><c> just</c><00:10:12.880><c> generate</c><00:10:13.279><c> a</c>

used a model which will just generate a

used a model which will just generate a
summary<00:10:13.839><c> of</c><00:10:14.000><c> all</c><00:10:14.160><c> this</c><00:10:14.560><c> separately.</c><00:10:16.000><c> So</c><00:10:16.160><c> it</c>

summary of all this separately. So it

summary of all this separately. So it
will<00:10:16.560><c> use</c><00:10:17.120><c> uh</c><00:10:17.920><c> you</c><00:10:18.160><c> can</c><00:10:18.320><c> think</c><00:10:18.399><c> of</c><00:10:18.560><c> it</c><00:10:18.720><c> like</c><00:10:18.880><c> a</c>

will use uh you can think of it like a

will use uh you can think of it like a
summary<00:10:19.279><c> of</c><00:10:19.360><c> an</c><00:10:19.600><c> image</c><00:10:19.760><c> is</c><00:10:20.000><c> nothing</c><00:10:20.160><c> but</c><00:10:20.720><c> image</c>

summary of an image is nothing but image

summary of an image is nothing but image
captioning<00:10:21.920><c> right.</c><00:10:22.480><c> It</c><00:10:22.720><c> will</c><00:10:22.880><c> generate</c><00:10:23.200><c> an</c>

captioning right. It will generate an

captioning right. It will generate an
summary<00:10:23.760><c> of</c><00:10:23.920><c> this</c><00:10:24.160><c> image</c><00:10:24.640><c> summary</c><00:10:24.959><c> of</c><00:10:25.120><c> the</c>

summary of this image summary of the

summary of this image summary of the
table<00:10:25.519><c> summary</c><00:10:25.839><c> of</c><00:10:26.000><c> the</c><00:10:26.160><c> text.</c><00:10:26.720><c> Now</c><00:10:27.040><c> all</c><00:10:27.279><c> you</c>

table summary of the text. Now all you

table summary of the text. Now all you
have<00:10:27.760><c> is</c><00:10:28.000><c> the</c><00:10:28.240><c> summary.</c><00:10:28.880><c> That</c><00:10:29.040><c> means</c><00:10:29.279><c> it's</c><00:10:29.600><c> all</c>

have is the summary. That means it's all

have is the summary. That means it's all
text.<00:10:30.800><c> So</c><00:10:31.040><c> now</c><00:10:31.279><c> you</c><00:10:31.440><c> can</c><00:10:31.600><c> use</c><00:10:31.760><c> any</c><00:10:32.160><c> text</c><00:10:32.560><c> based</c>

text. So now you can use any text based

text. So now you can use any text based
embedding<00:10:33.279><c> model</c><00:10:33.680><c> to</c><00:10:33.920><c> generate</c><00:10:34.240><c> the</c>

embedding model to generate the

embedding model to generate the
embedding<00:10:34.880><c> of</c><00:10:35.120><c> the</c><00:10:35.279><c> summary.</c><00:10:36.720><c> And</c><00:10:36.959><c> then</c><00:10:37.440><c> you</c>

embedding of the summary. And then you

embedding of the summary. And then you
store<00:10:38.000><c> this</c><00:10:38.240><c> embeddings</c><00:10:38.800><c> here.</c><00:10:39.200><c> So</c><00:10:39.360><c> what</c><00:10:39.600><c> you</c>

store this embeddings here. So what you

store this embeddings here. So what you
are<00:10:39.839><c> storing</c><00:10:40.240><c> here</c><00:10:40.800><c> are</c><00:10:41.279><c> only</c><00:10:42.000><c> the</c><00:10:42.240><c> embeddings</c>

are storing here are only the embeddings

are storing here are only the embeddings
of<00:10:42.959><c> the</c><00:10:43.120><c> summary</c><00:10:44.079><c> not</c><00:10:44.320><c> the</c><00:10:44.480><c> actual</c><00:10:44.880><c> data.</c>

of the summary not the actual data.

of the summary not the actual data.
Right?<00:10:47.440><c> And</c><00:10:47.600><c> then</c><00:10:47.839><c> when</c><00:10:48.079><c> the</c><00:10:48.320><c> question</c><00:10:48.640><c> comes</c>

Right? And then when the question comes

Right? And then when the question comes
now<00:10:50.160><c> we</c><00:10:50.320><c> are</c><00:10:50.399><c> talking</c><00:10:50.560><c> about</c><00:10:50.720><c> the</c><00:10:50.880><c> option</c>

now we are talking about the option

now we are talking about the option
number<00:10:51.360><c> two.</c><00:10:52.079><c> When</c><00:10:52.320><c> the</c><00:10:52.480><c> question</c><00:10:52.800><c> comes</c><00:10:53.920><c> we</c>

number two. When the question comes we

number two. When the question comes we
do<00:10:54.320><c> a</c><00:10:54.480><c> semantic</c><00:10:54.959><c> search</c><00:10:55.440><c> with</c><00:10:55.680><c> the</c><00:10:55.920><c> database</c>

do a semantic search with the database

do a semantic search with the database
and<00:10:57.200><c> what</c><00:10:57.440><c> we</c><00:10:57.600><c> get</c><00:10:57.839><c> as</c><00:10:58.079><c> a</c><00:10:58.240><c> chunk</c><00:10:58.800><c> or</c><00:10:58.959><c> some</c>

and what we get as a chunk or some

and what we get as a chunk or some
summary.<00:10:59.839><c> Now</c><00:11:00.000><c> that</c><00:11:00.320><c> summary</c><00:11:01.040><c> could</c><00:11:01.360><c> be</c><00:11:01.600><c> a</c>

summary. Now that summary could be a

summary. Now that summary could be a
summary<00:11:02.160><c> of</c><00:11:02.320><c> an</c><00:11:02.560><c> image,</c><00:11:03.200><c> table</c><00:11:03.600><c> or</c><00:11:03.839><c> text.</c><00:11:04.320><c> We</c>

summary of an image, table or text. We

summary of an image, table or text. We
don't<00:11:04.720><c> know</c><00:11:05.040><c> whatever</c><00:11:05.360><c> it</c><00:11:05.600><c> is.</c>

don't know whatever it is.

don't know whatever it is.
But<00:11:06.880><c> whatever</c><00:11:07.200><c> we</c><00:11:07.440><c> get</c><00:11:08.399><c> both</c><00:11:08.720><c> of</c><00:11:08.880><c> them</c><00:11:09.279><c> are</c><00:11:09.600><c> of</c>

But whatever we get both of them are of

But whatever we get both of them are of
text<00:11:10.320><c> format.</c><00:11:11.360><c> So</c><00:11:11.519><c> that's</c><00:11:11.760><c> why</c><00:11:11.920><c> we</c><00:11:12.079><c> can</c><00:11:12.240><c> use</c><00:11:12.399><c> a</c>

text format. So that's why we can use a

text format. So that's why we can use a
general<00:11:12.880><c> textbased</c><00:11:13.440><c> LLM</c><00:11:13.839><c> to</c><00:11:14.000><c> generate</c><00:11:14.320><c> the</c>

general textbased LLM to generate the

general textbased LLM to generate the
output.<00:11:15.920><c> Okay.</c><00:11:16.320><c> So</c><00:11:16.480><c> that's</c><00:11:16.959><c> uh</c><00:11:17.120><c> option</c><00:11:17.440><c> number</c>

output. Okay. So that's uh option number

output. Okay. So that's uh option number
two.<00:11:18.320><c> The</c><00:11:18.560><c> option</c><00:11:18.800><c> number</c><00:11:19.040><c> three</c><00:11:19.279><c> is</c><00:11:19.600><c> exactly</c>

two. The option number three is exactly

two. The option number three is exactly
same<00:11:20.160><c> as</c><00:11:20.320><c> option</c><00:11:20.640><c> number</c><00:11:20.880><c> two.</c><00:11:22.079><c> Uh</c><00:11:22.959><c> with</c><00:11:23.200><c> a</c>

same as option number two. Uh with a

same as option number two. Uh with a
slight<00:11:23.680><c> change</c><00:11:24.000><c> here</c><00:11:25.360><c> when</c><00:11:25.680><c> you</c><00:11:26.000><c> store</c><00:11:26.480><c> the</c>

slight change here when you store the

slight change here when you store the
summary<00:11:27.360><c> you</c><00:11:27.600><c> also</c><00:11:28.320><c> think</c><00:11:28.560><c> of</c><00:11:28.640><c> it</c><00:11:28.800><c> like</c><00:11:29.040><c> this.</c>

summary you also think of it like this.

summary you also think of it like this.
You<00:11:29.600><c> have</c><00:11:29.680><c> a</c><00:11:29.920><c> hash</c><00:11:30.480><c> here.</c><00:11:30.880><c> Let's</c><00:11:31.120><c> say</c><00:11:31.279><c> a</c>

You have a hash here. Let's say a

You have a hash here. Let's say a
dictionary<00:11:32.399><c> which</c><00:11:32.720><c> says</c><00:11:32.959><c> that</c><00:11:33.519><c> u</c><00:11:34.640><c> this</c><00:11:34.959><c> image</c>

dictionary which says that u this image

dictionary which says that u this image
number<00:11:35.600><c> one</c><00:11:36.800><c> uh</c><00:11:36.959><c> summary</c><00:11:37.279><c> is</c><00:11:37.440><c> this</c><00:11:37.680><c> image</c>

number one uh summary is this image

number one uh summary is this image
number<00:11:38.240><c> two</c><00:11:38.720><c> summary</c><00:11:38.959><c> is</c><00:11:39.120><c> this</c><00:11:39.360><c> table</c><00:11:39.680><c> number</c>

number two summary is this table number

number two summary is this table number
one<00:11:40.399><c> summary</c><00:11:40.720><c> is</c><00:11:40.959><c> this</c><00:11:41.440><c> you</c><00:11:41.600><c> create</c><00:11:41.920><c> a</c><00:11:42.320><c> hash</c>

one summary is this you create a hash

one summary is this you create a hash
file<00:11:43.279><c> or</c><00:11:43.760><c> hash</c><00:11:44.640><c> any</c><00:11:44.880><c> data</c><00:11:45.200><c> structure</c><00:11:45.440><c> of</c><00:11:45.680><c> your</c>

file or hash any data structure of your

file or hash any data structure of your
choice<00:11:46.560><c> so</c><00:11:46.800><c> that</c><00:11:47.040><c> you</c><00:11:47.279><c> can</c><00:11:48.320><c> you</c><00:11:48.480><c> know</c><00:11:48.640><c> come</c>

choice so that you can you know come

choice so that you can you know come
back<00:11:49.120><c> later</c><00:11:49.360><c> on</c><00:11:50.240><c> from</c><00:11:50.560><c> a</c><00:11:50.720><c> certain</c><00:11:51.040><c> summary</c><00:11:51.360><c> and</c>

back later on from a certain summary and

back later on from a certain summary and
you<00:11:51.839><c> can</c><00:11:51.920><c> figure</c><00:11:52.079><c> out</c><00:11:52.240><c> this</c><00:11:52.480><c> is</c><00:11:52.560><c> summary</c><00:11:52.959><c> of</c>

you can figure out this is summary of

you can figure out this is summary of
what<00:11:54.000><c> entity</c><00:11:54.880><c> okay</c><00:11:55.680><c> but</c><00:11:55.920><c> you</c><00:11:56.079><c> store</c><00:11:56.399><c> only</c><00:11:56.640><c> the</c>

what entity okay but you store only the

what entity okay but you store only the
summary<00:11:57.200><c> just</c><00:11:57.440><c> like</c><00:11:57.600><c> before</c><00:11:58.240><c> but</c><00:11:58.480><c> the</c>

summary just like before but the

summary just like before but the
difference<00:11:59.040><c> here</c><00:11:59.680><c> with</c><00:11:59.920><c> respect</c><00:12:00.160><c> to</c><00:12:00.240><c> option</c>

difference here with respect to option

difference here with respect to option
Number<00:12:00.720><c> two</c><00:12:00.880><c> is</c><00:12:01.200><c> when</c><00:12:01.440><c> you</c><00:12:01.600><c> ask</c><00:12:01.839><c> a</c><00:12:02.160><c> question</c>

Number two is when you ask a question

Number two is when you ask a question
you<00:12:03.680><c> get</c><00:12:03.839><c> some</c><00:12:04.000><c> relevant</c><00:12:04.399><c> chunk</c><00:12:04.640><c> which</c><00:12:04.880><c> is</c><00:12:04.959><c> a</c>

you get some relevant chunk which is a

you get some relevant chunk which is a
summary.<00:12:05.839><c> Then</c><00:12:06.000><c> you</c><00:12:06.240><c> go</c><00:12:06.480><c> back</c><00:12:07.040><c> to</c><00:12:07.279><c> that</c><00:12:07.519><c> hash</c>

summary. Then you go back to that hash

summary. Then you go back to that hash
and<00:12:08.480><c> find</c><00:12:08.720><c> out</c><00:12:08.880><c> the</c><00:12:09.200><c> actual</c><00:12:09.600><c> data</c><00:12:10.079><c> not</c><00:12:10.240><c> the</c>

and find out the actual data not the

and find out the actual data not the
summary<00:12:10.959><c> the</c><00:12:11.279><c> actual</c><00:12:11.600><c> data</c><00:12:11.839><c> which</c><00:12:12.079><c> is</c><00:12:12.240><c> mapped</c>

summary the actual data which is mapped

summary the actual data which is mapped
against<00:12:12.959><c> those</c><00:12:13.200><c> summary</c><00:12:14.240><c> and</c><00:12:14.480><c> then</c><00:12:14.639><c> you</c><00:12:14.959><c> take</c>

against those summary and then you take

against those summary and then you take
those<00:12:15.600><c> actual</c><00:12:16.079><c> data</c><00:12:16.800><c> and</c><00:12:17.040><c> then</c><00:12:17.279><c> pass</c><00:12:17.519><c> it</c><00:12:17.680><c> on</c>

those actual data and then pass it on

those actual data and then pass it on
here.<00:12:18.720><c> So</c><00:12:18.959><c> what</c><00:12:19.200><c> you're</c><00:12:19.440><c> doing</c><00:12:19.600><c> is</c><00:12:20.079><c> summary</c>

here. So what you're doing is summary

here. So what you're doing is summary
you<00:12:20.720><c> are</c><00:12:20.880><c> using</c><00:12:21.120><c> here</c><00:12:21.519><c> just</c><00:12:21.760><c> to</c><00:12:22.160><c> reduce</c><00:12:22.480><c> the</c>

you are using here just to reduce the

you are using here just to reduce the
search<00:12:23.040><c> space</c><00:12:23.440><c> just</c><00:12:23.680><c> for</c><00:12:24.000><c> semantic</c><00:12:24.560><c> search.</c>

search space just for semantic search.

search space just for semantic search.
When<00:12:25.440><c> you</c><00:12:25.600><c> get</c><00:12:25.760><c> that</c><00:12:26.320><c> relevant</c><00:12:26.720><c> chunks</c><00:12:27.120><c> you</c>

When you get that relevant chunks you

When you get that relevant chunks you
don't<00:12:27.600><c> care</c><00:12:27.839><c> about</c><00:12:28.000><c> that</c><00:12:28.240><c> summary.</c><00:12:28.800><c> You</c><00:12:29.040><c> just</c>

don't care about that summary. You just

don't care about that summary. You just
take<00:12:29.440><c> the</c><00:12:29.839><c> original</c><00:12:30.240><c> data</c><00:12:30.560><c> from</c><00:12:30.720><c> that</c><00:12:30.959><c> hash</c>

take the original data from that hash

take the original data from that hash
and<00:12:32.160><c> then</c><00:12:32.800><c> you</c><00:12:33.120><c> take</c><00:12:33.360><c> those</c><00:12:33.600><c> relevant</c><00:12:34.000><c> chunks</c>

and then you take those relevant chunks

and then you take those relevant chunks
and<00:12:34.800><c> your</c><00:12:35.040><c> question</c><00:12:35.360><c> and</c><00:12:35.600><c> since</c><00:12:35.920><c> relevant</c>

and your question and since relevant

and your question and since relevant
chunk<00:12:36.720><c> can</c><00:12:36.880><c> be</c><00:12:37.040><c> again</c><00:12:37.440><c> text</c><00:12:37.920><c> image</c><00:12:38.399><c> or</c><00:12:39.279><c> um</c>

chunk can be again text image or um

chunk can be again text image or um
table<00:12:41.040><c> you</c><00:12:41.279><c> need</c><00:12:41.440><c> a</c><00:12:41.600><c> multimodal</c><00:12:42.240><c> LLM</c><00:12:43.120><c> okay</c><00:12:43.360><c> and</c>

table you need a multimodal LLM okay and

table you need a multimodal LLM okay and
you<00:12:43.680><c> generate</c><00:12:44.000><c> the</c><00:12:44.240><c> answer</c><00:12:45.680><c> are</c><00:12:45.839><c> you</c><00:12:46.000><c> with</c>

you generate the answer are you with

you generate the answer are you with
yeah

yeah

yeah
&gt;&gt; um<00:12:47.600><c> let's</c><00:12:47.839><c> say</c><00:12:48.000><c> you</c><00:12:48.160><c> have</c><00:12:48.240><c> a</c><00:12:48.560><c> table</c><00:12:49.279><c> but</c><00:12:49.440><c> the</c>

&gt;&gt; um let's say you have a table but the

&gt;&gt; um let's say you have a table but the
table<00:12:49.920><c> is</c><00:12:50.079><c> an</c><00:12:50.240><c> image</c>

table is an image

table is an image
&gt;&gt; which<00:12:51.519><c> one</c><00:12:51.839><c> would</c><00:12:52.079><c> you</c><00:12:52.320><c> prefer</c><00:12:52.639><c> to</c><00:12:52.880><c> use</c><00:12:53.120><c> in</c>

&gt;&gt; which one would you prefer to use in

&gt;&gt; which one would you prefer to use in
that<00:12:53.600><c> case</c>

that case

that case
&gt;&gt; yeah<00:12:54.720><c> so</c><00:12:55.200><c> that's</c><00:12:55.440><c> a</c><00:12:55.680><c> good</c><00:12:55.839><c> question</c><00:12:56.240><c> so</c><00:12:57.040><c> the</c>

&gt;&gt; yeah so that's a good question so the

&gt;&gt; yeah so that's a good question so the
question<00:12:57.519><c> is</c><00:12:58.480><c> If</c><00:12:58.800><c> you</c><00:12:58.959><c> have</c><00:12:59.040><c> a</c><00:12:59.279><c> table</c><00:12:59.839><c> which</c><00:13:00.079><c> is</c>

question is If you have a table which is

question is If you have a table which is
an<00:13:00.480><c> image</c><00:13:01.120><c> right.</c><00:13:01.440><c> So</c><00:13:02.399><c> now</c><00:13:02.639><c> it's</c><00:13:02.880><c> all</c><00:13:03.120><c> whatever</c>

an image right. So now it's all whatever

an image right. So now it's all whatever
you<00:13:03.600><c> are</c><00:13:03.760><c> saying</c><00:13:04.000><c> is</c><00:13:04.320><c> all</c><00:13:04.560><c> at</c><00:13:04.720><c> this</c><00:13:04.959><c> level.</c><00:13:05.360><c> So</c>

you are saying is all at this level. So

you are saying is all at this level. So
you<00:13:05.760><c> don't</c><00:13:06.320><c> you</c><00:13:06.639><c> it's</c><00:13:06.959><c> all</c><00:13:07.200><c> up</c><00:13:07.360><c> to</c><00:13:07.519><c> you</c><00:13:07.920><c> how</c><00:13:08.240><c> you</c>

you don't you it's all up to you how you

you don't you it's all up to you how you
segregate<00:13:09.120><c> these</c><00:13:09.440><c> three</c><00:13:09.680><c> entities.</c><00:13:10.720><c> So</c><00:13:10.880><c> let's</c>

segregate these three entities. So let's

segregate these three entities. So let's
say<00:13:11.200><c> you</c><00:13:11.440><c> use</c><00:13:11.600><c> an</c><00:13:11.839><c> OCR</c><00:13:12.320><c> based</c><00:13:13.200><c> uh</c><00:13:13.600><c> uh</c><00:13:13.839><c> technique</c>

say you use an OCR based uh uh technique

say you use an OCR based uh uh technique
and<00:13:14.959><c> let's</c><00:13:15.279><c> say</c><00:13:15.440><c> it</c><00:13:16.240><c> it's</c><00:13:16.959><c> identified</c><00:13:17.360><c> a</c><00:13:17.680><c> table</c>

and let's say it it's identified a table

and let's say it it's identified a table
as<00:13:18.079><c> an</c><00:13:18.320><c> image.</c><00:13:19.120><c> So</c><00:13:19.279><c> it</c><00:13:19.519><c> will</c><00:13:19.600><c> be</c><00:13:19.760><c> treated</c><00:13:20.079><c> as</c><00:13:20.240><c> an</c>

as an image. So it will be treated as an

as an image. So it will be treated as an
image<00:13:20.880><c> because</c><00:13:21.200><c> the</c><00:13:21.519><c> model</c><00:13:22.000><c> till</c><00:13:22.320><c> this</c><00:13:22.560><c> point</c>

image because the model till this point

image because the model till this point
the<00:13:23.440><c> model</c><00:13:23.680><c> has</c><00:13:23.920><c> no</c><00:13:24.079><c> idea</c><00:13:24.399><c> from</c><00:13:24.639><c> where</c><00:13:24.800><c> these</c>

the model has no idea from where these

the model has no idea from where these
three<00:13:25.360><c> are</c><00:13:25.519><c> coming</c><00:13:26.320><c> because</c><00:13:26.560><c> these</c><00:13:26.800><c> are</c><00:13:26.959><c> like</c>

three are coming because these are like

three are coming because these are like
prerequisites<00:13:27.920><c> for</c><00:13:28.240><c> this</c><00:13:28.560><c> particular</c>

prerequisites for this particular

prerequisites for this particular
pipeline.<00:13:29.920><c> Okay.</c><00:13:30.880><c> So</c><00:13:31.680><c> are</c><00:13:31.920><c> you</c><00:13:32.000><c> with</c><00:13:32.240><c> me</c><00:13:32.399><c> with</c>

pipeline. Okay. So are you with me with

pipeline. Okay. So are you with me with
all<00:13:32.720><c> these</c><00:13:32.880><c> three</c><00:13:33.120><c> approach?</c><00:13:34.240><c> Yes.</c><00:13:34.720><c> Yeah.</c>

&gt;&gt; This<00:13:39.120><c> one.</c>

&gt;&gt; This one.

&gt;&gt; This one.
&gt;&gt; Oh<00:13:42.240><c> okay.</c><00:13:42.560><c> So</c><00:13:42.720><c> these</c><00:13:42.959><c> are</c><00:13:43.120><c> nothing</c><00:13:43.279><c> but</c><00:13:43.760><c> uh</c><00:13:44.240><c> uh</c>

&gt;&gt; Oh okay. So these are nothing but uh uh

&gt;&gt; Oh okay. So these are nothing but uh uh
models<00:13:45.040><c> basically.</c>

models basically.

models basically.
&gt;&gt; It<00:13:46.800><c> it</c><00:13:47.040><c> doesn't</c><00:13:47.279><c> resonate.</c><00:13:47.760><c> It's</c><00:13:48.000><c> what</c><00:13:48.160><c> I</c>

&gt;&gt; It it doesn't resonate. It's what I

&gt;&gt; It it doesn't resonate. It's what I
understand<00:13:48.720><c> now</c><00:13:48.959><c> but</c>

understand now but

understand now but
&gt;&gt; yeah<00:13:50.800><c> yeah</c><00:13:50.800><c> yeah</c><00:13:51.279><c> right</c><00:13:51.519><c> that's</c><00:13:51.760><c> correct</c><00:13:52.240><c> yes</c>

&gt;&gt; yeah yeah yeah right that's correct yes

&gt;&gt; yeah yeah yeah right that's correct yes
so<00:13:53.040><c> it</c><00:13:53.279><c> could</c><00:13:53.440><c> be</c><00:13:53.760><c> this</c><00:13:54.079><c> is</c><00:13:54.639><c> any</c><00:13:55.120><c> so</c><00:13:55.519><c> here</c><00:13:56.079><c> we</c>

so it could be this is any so here we

so it could be this is any so here we
have<00:13:56.320><c> a</c><00:13:56.480><c> multimodal</c><00:13:57.120><c> embedding</c><00:13:57.600><c> model</c><00:13:58.079><c> right</c>

have a multimodal embedding model right

have a multimodal embedding model right
here<00:13:58.959><c> it's</c><00:13:59.360><c> actually</c><00:13:59.680><c> first</c><00:14:00.079><c> you</c><00:14:00.399><c> need</c><00:14:00.480><c> a</c>

here it's actually first you need a

here it's actually first you need a
model<00:14:00.959><c> which</c><00:14:01.199><c> will</c><00:14:01.440><c> generate</c><00:14:01.680><c> the</c><00:14:01.920><c> summary</c>

model which will generate the summary

model which will generate the summary
then<00:14:02.639><c> you</c><00:14:02.800><c> can</c><00:14:02.959><c> think</c><00:14:03.040><c> of</c><00:14:03.199><c> it</c><00:14:03.360><c> like</c><00:14:03.600><c> another</c>

then you can think of it like another

then you can think of it like another
model<00:14:04.399><c> which</c><00:14:04.639><c> will</c><00:14:04.800><c> generate</c><00:14:05.199><c> the</c><00:14:05.440><c> embeddings</c>

model which will generate the embeddings

model which will generate the embeddings
so<00:14:07.040><c> uh</c><00:14:07.199><c> it's</c><00:14:07.600><c> just</c><00:14:07.839><c> a</c><00:14:08.240><c> one</c><00:14:08.720><c> icon</c><00:14:09.040><c> but</c><00:14:09.360><c> think</c><00:14:09.600><c> of</c>

so uh it's just a one icon but think of

so uh it's just a one icon but think of
it<00:14:09.920><c> like</c><00:14:10.160><c> there</c><00:14:10.399><c> are</c><00:14:10.480><c> two</c><00:14:10.720><c> things</c><00:14:10.959><c> happening</c>

it like there are two things happening

it like there are two things happening
in<00:14:12.079><c> sequence</c><00:14:12.800><c> okay</c><00:14:13.279><c> are</c><00:14:13.440><c> you</c><00:14:13.600><c> with</c><00:14:13.760><c> me</c><00:14:13.920><c> so</c><00:14:14.160><c> far</c>

in sequence okay are you with me so far

in sequence okay are you with me so far
yes<00:14:15.279><c> okay</c><00:14:15.760><c> so</c><00:14:16.000><c> do</c><00:14:16.240><c> you</c><00:14:16.320><c> see</c><00:14:16.560><c> any</c><00:14:16.800><c> problem</c><00:14:17.120><c> in</c>

yes okay so do you see any problem in

yes okay so do you see any problem in
this<00:14:18.000><c> when</c><00:14:18.240><c> you</c><00:14:18.399><c> have</c><00:14:18.399><c> a</c><00:14:18.560><c> multimodal</c><00:14:19.120><c> data</c>

this when you have a multimodal data

this when you have a multimodal data
there's<00:14:19.760><c> no</c><00:14:19.920><c> problem</c><00:14:20.079><c> as</c><00:14:20.320><c> such</c><00:14:20.800><c> buth</c><00:14:21.360><c> there</c>

there's no problem as such buth there

there's no problem as such buth there
are<00:14:21.839><c> few</c><00:14:22.320><c> scenarios</c><00:14:23.360><c> when</c><00:14:23.680><c> this</c><00:14:23.920><c> may</c><00:14:24.160><c> not</c><00:14:24.399><c> work</c>

are few scenarios when this may not work

are few scenarios when this may not work
okay<00:14:25.760><c> so</c>

okay so

okay so
scenarios<00:14:28.320><c> like</c><00:14:28.720><c> like</c><00:14:29.920><c> what</c><00:14:30.160><c> you</c><00:14:30.399><c> mentioned</c>

scenarios like like what you mentioned

scenarios like like what you mentioned
uh<00:14:32.079><c> there</c><00:14:32.399><c> are</c><00:14:32.639><c> few</c><00:14:33.680><c> documents</c><00:14:34.079><c> or</c><00:14:34.399><c> data</c><00:14:34.720><c> which</c>

uh there are few documents or data which

uh there are few documents or data which
we<00:14:35.440><c> have</c><00:14:35.600><c> seen</c><00:14:36.480><c> where</c><00:14:37.120><c> the</c><00:14:37.440><c> PDF</c><00:14:38.000><c> was</c><00:14:38.320><c> created</c>

we have seen where the PDF was created

we have seen where the PDF was created
using<00:14:40.000><c> images</c><00:14:40.880><c> so</c><00:14:41.279><c> basically</c><00:14:41.680><c> you</c><00:14:41.839><c> can</c><00:14:42.000><c> think</c>

using images so basically you can think

using images so basically you can think
of<00:14:42.399><c> like</c><00:14:42.560><c> this</c><00:14:43.120><c> um</c><00:14:44.000><c> let's</c><00:14:44.240><c> say</c><00:14:45.120><c> uh</c><00:14:46.240><c> uh</c>

of like this um let's say uh uh

of like this um let's say uh uh
toll<00:14:48.240><c> that</c><00:14:48.560><c> we</c><00:14:49.120><c> uh</c><00:14:49.360><c> cross</c><00:14:49.600><c> in</c><00:14:49.760><c> a</c><00:14:49.920><c> highway</c><00:14:50.800><c> all</c>

toll that we uh cross in a highway all

toll that we uh cross in a highway all
are<00:14:51.199><c> images</c><00:14:51.680><c> right</c><00:14:51.839><c> they</c><00:14:52.000><c> just</c><00:14:52.160><c> take</c><00:14:52.320><c> the</c>

are images right they just take the

are images right they just take the
images<00:14:52.880><c> of</c><00:14:53.120><c> our</c><00:14:53.839><c> number</c><00:14:54.160><c> plate</c><00:14:54.480><c> and</c><00:14:54.639><c> all</c><00:14:54.800><c> that.</c>

images of our number plate and all that.

images of our number plate and all that.
Uh<00:14:55.680><c> similarly</c><00:14:56.320><c> you</c><00:14:56.639><c> can</c><00:14:56.880><c> think</c><00:14:57.120><c> of</c><00:14:57.760><c> uh</c><00:14:58.320><c> any</c>

Uh similarly you can think of uh any

Uh similarly you can think of uh any
government<00:14:59.360><c> organization</c><00:15:00.000><c> where</c><00:15:00.320><c> forms</c><00:15:00.720><c> are</c>

government organization where forms are

government organization where forms are
just<00:15:01.199><c> uh</c><00:15:01.360><c> they</c><00:15:01.680><c> they</c><00:15:02.079><c> just</c><00:15:02.240><c> keep</c><00:15:02.480><c> on</c><00:15:02.959><c> uh</c><00:15:03.279><c> taking</c>

just uh they they just keep on uh taking

just uh they they just keep on uh taking
images<00:15:04.240><c> and</c><00:15:04.560><c> later</c><00:15:04.880><c> on</c><00:15:05.519><c> all</c><00:15:05.760><c> those</c><00:15:06.000><c> images</c><00:15:06.320><c> are</c>

images and later on all those images are

images and later on all those images are
converted<00:15:06.880><c> into</c><00:15:07.120><c> a</c><00:15:07.440><c> PDF.</c><00:15:08.800><c> So</c><00:15:09.040><c> in</c><00:15:09.279><c> that</c><00:15:09.519><c> case</c>

converted into a PDF. So in that case

converted into a PDF. So in that case
not<00:15:10.959><c> always</c><00:15:12.160><c> uh</c><00:15:12.480><c> these</c><00:15:13.440><c> techniques</c><00:15:13.920><c> of</c>

not always uh these techniques of

not always uh these techniques of
extracting<00:15:14.720><c> images,</c><00:15:15.199><c> tables</c><00:15:15.600><c> and</c><00:15:15.920><c> text</c><00:15:16.480><c> works</c>

extracting images, tables and text works

extracting images, tables and text works
nicely.<00:15:18.000><c> It's</c><00:15:18.240><c> not</c><00:15:18.399><c> like</c><00:15:18.800><c> uh</c><00:15:18.959><c> it</c><00:15:19.199><c> never</c><00:15:19.440><c> works.</c>

nicely. It's not like uh it never works.

nicely. It's not like uh it never works.
It<00:15:20.320><c> all</c><00:15:20.560><c> about</c><00:15:21.519><c> how</c><00:15:21.839><c> your</c><00:15:22.160><c> data</c><00:15:22.560><c> behaves</c><00:15:23.040><c> with</c>

It all about how your data behaves with

It all about how your data behaves with
your<00:15:23.920><c> technique</c><00:15:24.240><c> that</c><00:15:24.480><c> you</c><00:15:24.639><c> are</c>

your technique that you are

your technique that you are
implementing.<00:15:25.519><c> Okay.</c><00:15:26.079><c> So</c><00:15:26.959><c> now</c><00:15:27.199><c> the</c><00:15:27.440><c> next</c>

implementing. Okay. So now the next

implementing. Okay. So now the next
technique<00:15:27.920><c> that</c><00:15:28.079><c> we</c><00:15:28.240><c> are</c><00:15:28.399><c> going</c><00:15:28.480><c> to</c><00:15:29.040><c> discuss</c>

technique that we are going to discuss

technique that we are going to discuss
today<00:15:29.600><c> is</c><00:15:29.839><c> using</c><00:15:30.079><c> a</c><00:15:30.240><c> vision-</c><00:15:30.560><c> based</c><00:15:30.959><c> uh</c>

today is using a vision- based uh

today is using a vision- based uh
retrieval<00:15:31.600><c> model</c><00:15:32.079><c> and</c><00:15:32.320><c> we</c><00:15:32.480><c> will</c><00:15:32.639><c> see</c><00:15:32.720><c> that</c><00:15:33.040><c> why</c>

retrieval model and we will see that why

retrieval model and we will see that why
we<00:15:33.600><c> are</c><00:15:33.760><c> using</c><00:15:33.920><c> this</c><00:15:34.320><c> but</c><00:15:34.639><c> the</c><00:15:34.959><c> premise</c><00:15:35.360><c> is</c>

we are using this but the premise is

we are using this but the premise is
this.<00:15:36.160><c> If</c><00:15:36.399><c> you</c><00:15:36.560><c> use</c><00:15:36.880><c> if</c><00:15:37.040><c> if</c><00:15:37.199><c> if</c><00:15:37.760><c> your</c><00:15:38.079><c> data</c><00:15:38.880><c> with</c>

this. If you use if if if your data with

this. If you use if if if your data with
your<00:15:39.360><c> data</c><00:15:39.920><c> any</c><00:15:40.160><c> of</c><00:15:40.320><c> these</c><00:15:40.720><c> uh</c><00:15:40.880><c> three</c><00:15:41.199><c> options</c>

your data any of these uh three options

your data any of these uh three options
works<00:15:42.320><c> you</c><00:15:42.560><c> just</c><00:15:42.800><c> go</c><00:15:42.959><c> with</c><00:15:43.120><c> this</c><00:15:43.760><c> what</c><00:15:44.000><c> we're</c>

works you just go with this what we're

works you just go with this what we're
going<00:15:44.320><c> to</c><00:15:44.399><c> discuss</c><00:15:44.639><c> in</c><00:15:44.880><c> next</c><00:15:45.040><c> one</c><00:15:45.360><c> hour</c><00:15:45.839><c> you</c>

going to discuss in next one hour you

going to discuss in next one hour you
it's<00:15:46.480><c> not</c><00:15:46.639><c> relevant</c><00:15:46.959><c> for</c><00:15:47.199><c> you</c><00:15:47.680><c> but</c><00:15:47.920><c> this</c><00:15:48.399><c> you</c>

it's not relevant for you but this you

it's not relevant for you but this you
know<00:15:48.639><c> what</c><00:15:48.800><c> we</c><00:15:48.959><c> are</c><00:15:49.120><c> going</c><00:15:49.199><c> to</c><00:15:49.279><c> discuss</c><00:15:49.600><c> is</c><00:15:49.920><c> an</c>

know what we are going to discuss is an

know what we are going to discuss is an
option<00:15:50.480><c> number</c><00:15:50.720><c> four</c><00:15:51.680><c> which</c><00:15:51.920><c> is</c><00:15:52.320><c> uh</c><00:15:52.399><c> a</c><00:15:52.639><c> smarter</c>

option number four which is uh a smarter

option number four which is uh a smarter
technique<00:15:53.519><c> which</c><00:15:53.759><c> is</c><00:15:54.000><c> based</c><00:15:54.320><c> on</c><00:15:54.959><c> a</c><00:15:55.199><c> vision</c>

technique which is based on a vision

technique which is based on a vision
based<00:15:55.839><c> model</c><00:15:56.320><c> to</c><00:15:57.040><c> uh</c><00:15:57.279><c> perform</c><00:15:57.680><c> the</c><00:15:58.079><c> retrieval.</c>

based model to uh perform the retrieval.

based model to uh perform the retrieval.
You<00:15:59.279><c> don't</c><00:15:59.440><c> have</c><00:15:59.600><c> to</c><00:16:00.560><c> extract</c><00:16:01.360><c> all</c><00:16:01.600><c> these</c>

You don't have to extract all these

You don't have to extract all these
three<00:16:02.000><c> entity</c><00:16:02.399><c> in</c><00:16:02.560><c> the</c><00:16:02.720><c> first</c><00:16:02.880><c> place</c><00:16:03.199><c> because</c>

three entity in the first place because

three entity in the first place because
think<00:16:03.759><c> of</c><00:16:03.839><c> it</c><00:16:04.000><c> like</c><00:16:04.160><c> this.</c><00:16:05.040><c> The</c><00:16:05.360><c> moment</c><00:16:05.680><c> you</c>

think of it like this. The moment you

think of it like this. The moment you
have<00:16:06.160><c> your</c><00:16:06.480><c> data</c><00:16:07.120><c> and</c><00:16:07.360><c> you</c><00:16:07.680><c> first</c><00:16:08.079><c> in</c><00:16:08.320><c> the</c>

have your data and you first in the

have your data and you first in the
first<00:16:08.720><c> place</c><00:16:08.959><c> you</c><00:16:09.680><c> segregate</c><00:16:10.160><c> these</c><00:16:10.560><c> three</c>

first place you segregate these three

first place you segregate these three
things.<00:16:11.519><c> It's</c><00:16:11.680><c> just</c><00:16:11.920><c> like</c><00:16:12.079><c> you</c><00:16:12.320><c> have</c><00:16:12.399><c> a</c><00:16:12.639><c> family</c>

things. It's just like you have a family

things. It's just like you have a family
you<00:16:13.680><c> just</c><00:16:14.079><c> uh</c><00:16:14.399><c> you</c><00:16:14.560><c> know</c><00:16:15.120><c> let</c><00:16:15.440><c> your</c><00:16:15.680><c> kid</c><00:16:16.079><c> go</c>

you just uh you know let your kid go

you just uh you know let your kid go
somewhere<00:16:17.279><c> you</c><00:16:17.519><c> go</c><00:16:17.759><c> somewhere</c><00:16:18.320><c> and</c><00:16:18.959><c> you</c><00:16:19.120><c> know</c>

somewhere you go somewhere and you know

somewhere you go somewhere and you know
your<00:16:19.519><c> partner</c><00:16:19.839><c> goes</c><00:16:20.079><c> somewhere</c><00:16:20.399><c> else.</c><00:16:20.959><c> It's</c><00:16:21.199><c> a</c>

your partner goes somewhere else. It's a

your partner goes somewhere else. It's a
good<00:16:21.519><c> thing</c><00:16:21.680><c> but</c><00:16:22.079><c> uh</c><00:16:22.240><c> you</c><00:16:22.399><c> know</c><00:16:22.880><c> uh</c><00:16:23.120><c> if</c><00:16:23.519><c> all</c><00:16:23.759><c> of</c>

good thing but uh you know uh if all of

good thing but uh you know uh if all of
them<00:16:24.079><c> goes</c><00:16:24.800><c> you</c><00:16:24.959><c> know</c><00:16:25.120><c> separate</c><00:16:25.920><c> and</c><00:16:26.240><c> you</c>

them goes you know separate and you

them goes you know separate and you
expect<00:16:26.880><c> somebody</c><00:16:27.279><c> else</c><00:16:27.759><c> to</c><00:16:28.079><c> identify</c><00:16:28.399><c> that</c>

expect somebody else to identify that

expect somebody else to identify that
they<00:16:28.800><c> all</c><00:16:28.959><c> are</c><00:16:29.199><c> part</c><00:16:29.440><c> of</c><00:16:29.600><c> one</c><00:16:29.839><c> family</c><00:16:30.160><c> it's</c><00:16:30.399><c> a</c>

they all are part of one family it's a

they all are part of one family it's a
it's<00:16:30.800><c> a</c><00:16:30.959><c> task</c><00:16:31.360><c> right</c><00:16:31.600><c> so</c><00:16:31.759><c> for</c><00:16:32.079><c> that</c><00:16:32.720><c> external</c>

it's a task right so for that external

it's a task right so for that external
person

person

person
uh<00:16:35.920><c> so</c><00:16:36.320><c> that</c><00:16:36.560><c> is</c><00:16:36.720><c> what</c><00:16:36.880><c> we</c><00:16:37.040><c> are</c><00:16:37.120><c> going</c><00:16:37.279><c> to</c><00:16:37.440><c> solve</c>

uh so that is what we are going to solve

uh so that is what we are going to solve
that<00:16:38.880><c> can</c><00:16:39.120><c> we</c><00:16:39.440><c> can</c><00:16:39.680><c> we</c><00:16:39.920><c> come</c><00:16:40.079><c> up</c><00:16:40.240><c> with</c><00:16:40.399><c> a</c>

that can we can we come up with a

that can we can we come up with a
technique<00:16:41.279><c> where</c><00:16:41.920><c> we</c><00:16:42.160><c> don't</c><00:16:42.480><c> do</c><00:16:42.800><c> all</c><00:16:43.040><c> this</c>

technique where we don't do all this

technique where we don't do all this
okay<00:16:44.160><c> so</c><00:16:44.399><c> before</c><00:16:44.639><c> we</c><00:16:44.720><c> go</c><00:16:45.040><c> uh</c><00:16:45.120><c> I</c><00:16:45.360><c> think</c><00:16:45.680><c> you</c><00:16:45.839><c> have</c>

okay so before we go uh I think you have

okay so before we go uh I think you have
a<00:16:46.160><c> question</c><00:16:46.399><c> yeah</c>

a question yeah

a question yeah
&gt;&gt; yeah<00:16:46.720><c> I</c><00:16:46.880><c> think</c><00:16:46.959><c> you</c><00:16:47.120><c> kind</c><00:16:47.279><c> of</c><00:16:47.440><c> answered</c><00:16:47.759><c> my</c>

&gt;&gt; yeah I think you kind of answered my

&gt;&gt; yeah I think you kind of answered my
question<00:16:48.240><c> because</c><00:16:48.399><c> you</c><00:16:48.639><c> were</c><00:16:48.800><c> explaining</c><00:16:49.040><c> the</c>

question because you were explaining the

question because you were explaining the
case<00:16:49.519><c> about</c><00:16:50.720><c> scanning</c><00:16:51.120><c> all</c><00:16:51.279><c> the</c><00:16:51.360><c> PDFs</c>

case about scanning all the PDFs

case about scanning all the PDFs
&gt;&gt; and<00:16:53.120><c> it</c><00:16:53.360><c> wouldn't</c><00:16:53.759><c> quite</c><00:16:54.079><c> work</c><00:16:54.800><c> and</c><00:16:55.040><c> I</c><00:16:55.279><c> was</c><00:16:55.680><c> a</c>

&gt;&gt; and it wouldn't quite work and I was a

&gt;&gt; and it wouldn't quite work and I was a
little<00:16:56.079><c> bit</c><00:16:56.399><c> confused</c><00:16:56.800><c> as</c><00:16:56.959><c> to</c><00:16:57.120><c> why</c><00:16:57.920><c> these</c>

little bit confused as to why these

little bit confused as to why these
approaches<00:16:58.800><c> wouldn't</c><00:16:58.959><c> work.</c>

approaches wouldn't work.

approaches wouldn't work.
&gt;&gt; Yeah.

&gt;&gt; Yeah.

&gt;&gt; Yeah.
&gt;&gt; But<00:16:59.839><c> then</c><00:17:00.000><c> I</c><00:17:00.160><c> think</c><00:17:00.320><c> you're</c><00:17:00.639><c> going</c><00:17:00.959><c> towards</c>

&gt;&gt; But then I think you're going towards

&gt;&gt; But then I think you're going towards
the<00:17:01.519><c> notion</c><00:17:01.759><c> that</c><00:17:02.000><c> we</c><00:17:02.079><c> need</c><00:17:02.240><c> to</c><00:17:02.399><c> establish</c>

the notion that we need to establish

the notion that we need to establish
relationships<00:17:03.440><c> between</c>

relationships between

relationships between
&gt;&gt; Exactly.

&gt;&gt; Exactly.

&gt;&gt; Exactly.
&gt;&gt; Absolutely.<00:17:06.480><c> Yeah.</c><00:17:06.720><c> So</c><00:17:06.880><c> I</c><00:17:07.120><c> think</c><00:17:07.760><c> I'll</c><00:17:08.000><c> give</c>

&gt;&gt; Absolutely. Yeah. So I think I'll give

&gt;&gt; Absolutely. Yeah. So I think I'll give
you<00:17:08.319><c> one</c><00:17:08.480><c> more</c><00:17:08.880><c> uh</c><00:17:09.520><c> one</c><00:17:09.760><c> more</c><00:17:10.480><c> uh</c><00:17:10.799><c> example.</c><00:17:11.919><c> Uh</c>

you one more uh one more uh example. Uh

you one more uh one more uh example. Uh
if<00:17:12.880><c> you</c><00:17:13.039><c> go</c><00:17:13.120><c> to</c><00:17:13.280><c> IKEA,</c><00:17:13.839><c> you</c><00:17:14.079><c> buy</c><00:17:14.240><c> something</c>

if you go to IKEA, you buy something

if you go to IKEA, you buy something
from<00:17:14.720><c> IKEA.</c><00:17:15.199><c> If</c><00:17:15.439><c> you</c><00:17:15.520><c> have</c><00:17:15.600><c> seen</c><00:17:15.760><c> the</c><00:17:15.919><c> IKEA</c><00:17:16.880><c> uh</c>

from IKEA. If you have seen the IKEA uh

from IKEA. If you have seen the IKEA uh
in<00:17:17.360><c> uh</c><00:17:17.520><c> you</c><00:17:17.679><c> know</c><00:17:17.839><c> instructions</c><00:17:18.880><c> you</c><00:17:19.039><c> know</c><00:17:19.199><c> we</c>

in uh you know instructions you know we

in uh you know instructions you know we
don't<00:17:20.319><c> I</c><00:17:20.640><c> personally</c><00:17:21.199><c> never</c><00:17:21.360><c> looked</c><00:17:21.520><c> into</c>

don't I personally never looked into

don't I personally never looked into
those<00:17:22.000><c> instruction</c><00:17:22.640><c> but</c><00:17:22.880><c> while</c><00:17:23.120><c> I</c><00:17:23.280><c> was</c>

those instruction but while I was

those instruction but while I was
reading<00:17:23.600><c> that</c><00:17:23.760><c> research</c><00:17:24.160><c> paper</c><00:17:24.559><c> they</c><00:17:24.799><c> said</c>

reading that research paper they said

reading that research paper they said
that<00:17:25.520><c> refer</c><00:17:25.839><c> to</c><00:17:26.000><c> that</c><00:17:26.640><c> uh</c><00:17:26.799><c> because</c><00:17:27.120><c> we</c>

that refer to that uh because we

that refer to that uh because we
generally<00:17:27.679><c> go</c><00:17:27.839><c> to</c><00:17:28.000><c> YouTube</c><00:17:28.240><c> and</c><00:17:28.480><c> search</c><00:17:28.799><c> what</c>

generally go to YouTube and search what

generally go to YouTube and search what
is<00:17:29.120><c> the</c><00:17:29.280><c> instruction</c><00:17:29.679><c> steps</c><00:17:29.919><c> and</c><00:17:30.080><c> all</c><00:17:30.240><c> that</c>

is the instruction steps and all that

is the instruction steps and all that
right<00:17:30.960><c> but</c><00:17:31.200><c> if</c><00:17:31.440><c> you</c><00:17:31.520><c> look</c><00:17:31.679><c> at</c><00:17:31.760><c> the</c><00:17:32.000><c> IKEA</c>

right but if you look at the IKEA

right but if you look at the IKEA
instruction<00:17:33.200><c> set</c><00:17:33.760><c> they</c><00:17:34.080><c> just</c><00:17:34.240><c> have</c><00:17:34.559><c> emoji</c>

instruction set they just have emoji

instruction set they just have emoji
kind<00:17:35.200><c> of</c><00:17:35.360><c> a</c><00:17:35.600><c> human</c><00:17:36.160><c> uh</c><00:17:36.240><c> and</c><00:17:36.640><c> they</c><00:17:36.880><c> are</c><00:17:37.039><c> just</c>

kind of a human uh and they are just

kind of a human uh and they are just
assembling<00:17:37.919><c> something</c><00:17:38.320><c> there</c><00:17:38.480><c> is</c><00:17:38.640><c> no</c><00:17:38.799><c> text</c>

assembling something there is no text

assembling something there is no text
there<00:17:40.080><c> there's</c><00:17:40.400><c> nothing</c><00:17:40.640><c> there</c><00:17:40.960><c> so</c><00:17:41.280><c> unless</c><00:17:41.520><c> or</c>

there there's nothing there so unless or

there there's nothing there so unless or
until<00:17:42.160><c> you</c><00:17:42.400><c> have</c><00:17:42.480><c> a</c><00:17:42.720><c> visual</c><00:17:43.120><c> understanding</c><00:17:43.600><c> of</c>

until you have a visual understanding of

until you have a visual understanding of
what<00:17:44.320><c> it</c><00:17:44.960><c> you</c><00:17:45.200><c> will</c><00:17:45.360><c> not</c><00:17:45.520><c> have</c><00:17:45.679><c> any</c><00:17:45.840><c> idea</c><00:17:46.160><c> what</c>

what it you will not have any idea what

what it you will not have any idea what
they're<00:17:46.720><c> talking</c><00:17:46.880><c> about.</c><00:17:47.440><c> Okay.</c><00:17:48.080><c> So</c><00:17:48.640><c> there</c>

they're talking about. Okay. So there

they're talking about. Okay. So there
are<00:17:49.039><c> some</c><00:17:49.200><c> data</c><00:17:49.440><c> sets</c><00:17:49.600><c> and</c><00:17:49.840><c> I'll</c><00:17:50.080><c> show</c><00:17:50.240><c> you</c><00:17:50.480><c> a</c>

are some data sets and I'll show you a

are some data sets and I'll show you a
few<00:17:50.799><c> of</c><00:17:50.880><c> the</c><00:17:51.039><c> data</c><00:17:51.280><c> sets</c><00:17:52.080><c> where</c><00:17:52.640><c> the</c><00:17:53.280><c> uh</c><00:17:53.440><c> there</c>

few of the data sets where the uh there

few of the data sets where the uh there
are<00:17:53.840><c> some</c><00:17:54.080><c> text</c><00:17:54.559><c> embedded</c><00:17:55.120><c> within</c><00:17:55.360><c> the</c><00:17:55.600><c> image</c>

are some text embedded within the image

are some text embedded within the image
and<00:17:56.480><c> there</c><00:17:56.720><c> are</c><00:17:56.880><c> just</c><00:17:57.039><c> an</c><00:17:57.360><c> image</c><00:17:58.000><c> they</c><00:17:58.240><c> don't</c>

and there are just an image they don't

and there are just an image they don't
have<00:17:58.480><c> any</c><00:17:58.720><c> text.</c><00:17:59.280><c> So</c><00:17:59.440><c> you</c><00:17:59.679><c> need</c><00:17:59.919><c> some</c><00:18:00.400><c> model</c><00:18:00.799><c> or</c>

have any text. So you need some model or

have any text. So you need some model or
some<00:18:01.679><c> uh</c><00:18:01.919><c> technique</c><00:18:02.799><c> which</c><00:18:03.120><c> can</c><00:18:03.360><c> help</c><00:18:03.679><c> us</c><00:18:04.080><c> to</c>

some uh technique which can help us to

some uh technique which can help us to
understand<00:18:05.760><c> uh</c><00:18:06.400><c> what</c><00:18:06.559><c> is</c><00:18:06.720><c> the</c><00:18:06.880><c> semantics</c><00:18:07.280><c> of</c>

understand uh what is the semantics of

understand uh what is the semantics of
the<00:18:07.600><c> data.</c><00:18:08.160><c> Okay.</c><00:18:08.559><c> So</c><00:18:08.720><c> let's</c><00:18:09.039><c> see</c><00:18:09.200><c> how</c><00:18:10.480><c> we</c><00:18:10.720><c> are</c>

the data. Okay. So let's see how we are

the data. Okay. So let's see how we are
going<00:18:11.600><c> to</c><00:18:11.919><c> solve</c><00:18:12.240><c> this.</c>

going to solve this.

going to solve this.
So<00:18:13.840><c> this</c><00:18:14.000><c> is</c><00:18:14.559><c> uh</c><00:18:15.039><c> again</c><00:18:15.520><c> the</c><00:18:15.760><c> text</c><00:18:16.000><c> might</c><00:18:16.160><c> be</c>

So this is uh again the text might be

So this is uh again the text might be
small<00:18:16.880><c> uh</c><00:18:17.280><c> you</c><00:18:17.520><c> can</c><00:18:17.600><c> just</c><00:18:17.760><c> leave</c><00:18:18.000><c> that</c><00:18:18.240><c> okay</c>

small uh you can just leave that okay

small uh you can just leave that okay
you<00:18:18.880><c> can</c><00:18:19.200><c> open</c><00:18:19.440><c> it</c><00:18:19.600><c> in</c><00:18:19.760><c> your</c><00:18:19.919><c> laptop</c><00:18:20.880><c> uh</c><00:18:21.039><c> or</c>

you can open it in your laptop uh or

you can open it in your laptop uh or
I'll<00:18:22.160><c> try</c><00:18:22.320><c> to</c><00:18:22.400><c> explain</c><00:18:22.720><c> it</c><00:18:23.120><c> as</c><00:18:23.440><c> much</c><00:18:23.600><c> as</c><00:18:23.760><c> I</c><00:18:23.919><c> can.</c>

I'll try to explain it as much as I can.

I'll try to explain it as much as I can.
So<00:18:25.200><c> this</c><00:18:25.360><c> is</c><00:18:25.520><c> the</c><00:18:25.919><c> traditional</c><00:18:26.400><c> technique</c>

So this is the traditional technique

So this is the traditional technique
that<00:18:26.880><c> we</c><00:18:27.039><c> discussed</c><00:18:27.520><c> right</c><00:18:27.840><c> you</c><00:18:28.000><c> first</c><00:18:28.320><c> place</c>

that we discussed right you first place

that we discussed right you first place
you<00:18:29.200><c> divide</c><00:18:29.600><c> all</c><00:18:29.760><c> these</c><00:18:30.000><c> three</c><00:18:30.240><c> entities</c><00:18:30.960><c> uh</c>

you divide all these three entities uh

you divide all these three entities uh
separately<00:18:32.559><c> uh</c><00:18:32.720><c> but</c><00:18:32.960><c> this</c><00:18:33.120><c> is</c><00:18:33.440><c> not</c><00:18:33.919><c> very</c>

separately uh but this is not very

separately uh but this is not very
helpful<00:18:34.960><c> because</c><00:18:35.200><c> if</c><00:18:35.440><c> you</c><00:18:35.520><c> look</c><00:18:35.919><c> uh</c><00:18:36.080><c> you</c><00:18:36.240><c> know</c>

helpful because if you look uh you know

helpful because if you look uh you know
think<00:18:36.640><c> about</c><00:18:36.799><c> it</c><00:18:37.679><c> let's</c><00:18:38.000><c> say</c><00:18:38.559><c> you</c><00:18:38.880><c> were</c><00:18:39.039><c> given</c>

think about it let's say you were given

think about it let's say you were given
a<00:18:39.520><c> book</c><00:18:40.320><c> and</c><00:18:41.039><c> uh</c><00:18:41.280><c> you</c><00:18:41.600><c> were</c><00:18:41.760><c> asked</c><00:18:42.080><c> to</c>

a book and uh you were asked to

a book and uh you were asked to
answer<00:18:44.080><c> a</c><00:18:44.320><c> particular</c><00:18:44.640><c> question</c><00:18:44.960><c> let's</c><00:18:45.120><c> say</c><00:18:45.360><c> I</c>

answer a particular question let's say I

answer a particular question let's say I
give<00:18:45.679><c> you</c><00:18:45.919><c> this</c><00:18:46.080><c> book</c><00:18:46.720><c> by</c><00:18:46.880><c> the</c><00:18:46.960><c> way</c><00:18:47.120><c> this</c><00:18:47.200><c> is</c><00:18:47.280><c> a</c>

give you this book by the way this is a

give you this book by the way this is a
fantastic<00:18:47.760><c> book</c><00:18:47.919><c> from</c><00:18:48.160><c> Simon</c><00:18:48.480><c> have</c><00:18:48.640><c> you</c><00:18:48.720><c> heard</c>

fantastic book from Simon have you heard

fantastic book from Simon have you heard
of<00:18:48.960><c> this</c><00:18:49.120><c> book</c><00:18:50.080><c> yeah</c><00:18:50.640><c> if</c><00:18:50.880><c> you</c><00:18:51.039><c> are</c><00:18:51.200><c> getting</c>

of this book yeah if you are getting

of this book yeah if you are getting
started<00:18:51.679><c> with</c><00:18:51.919><c> machine</c><00:18:52.160><c> learning</c><00:18:52.559><c> uh</c><00:18:52.720><c> deep</c>

started with machine learning uh deep

started with machine learning uh deep
learning<00:18:53.760><c> uh</c><00:18:53.919><c> you</c><00:18:54.080><c> know</c><00:18:54.240><c> you</c><00:18:54.640><c> and</c><00:18:55.280><c> uh</c><00:18:55.520><c> read</c>

learning uh you know you and uh read

learning uh you know you and uh read
this<00:18:55.919><c> book.</c><00:18:56.160><c> This</c><00:18:56.240><c> is</c><00:18:56.320><c> a</c><00:18:56.480><c> really</c><00:18:56.720><c> fantastic</c>

this book. This is a really fantastic

this book. This is a really fantastic
book.<00:18:57.520><c> It's</c><00:18:57.760><c> a</c><00:18:57.919><c> recently</c><00:18:58.720><c> published</c><00:18:59.120><c> book</c><00:18:59.679><c> and</c>

book. It's a recently published book and

book. It's a recently published book and
professor<00:19:00.320><c> Simon</c><00:19:00.640><c> is</c><00:19:00.799><c> very</c><00:19:01.039><c> reachable.</c><00:19:01.760><c> It's</c>

professor Simon is very reachable. It's

professor Simon is very reachable. It's
it's<00:19:02.640><c> uh</c><00:19:02.799><c> it's</c><00:19:03.039><c> a</c><00:19:03.200><c> fantastic</c><00:19:03.600><c> book.</c><00:19:04.160><c> So</c><00:19:04.480><c> let's</c>

it's uh it's a fantastic book. So let's

it's uh it's a fantastic book. So let's
say<00:19:04.880><c> if</c><00:19:05.120><c> I</c><00:19:05.280><c> give</c><00:19:05.440><c> you</c><00:19:05.600><c> this</c><00:19:05.840><c> book</c><00:19:06.480><c> and</c><00:19:06.720><c> if</c><00:19:06.880><c> I</c><00:19:07.039><c> ask</c>

say if I give you this book and if I ask

say if I give you this book and if I ask
you<00:19:07.360><c> some</c><00:19:07.679><c> question</c><00:19:08.320><c> and</c><00:19:08.559><c> let's</c><00:19:08.799><c> say</c><00:19:08.960><c> you</c><00:19:09.280><c> are</c>

you some question and let's say you are

you some question and let's say you are
not<00:19:10.320><c> aware</c><00:19:10.559><c> of</c><00:19:10.720><c> this</c><00:19:11.039><c> particular</c><00:19:11.600><c> topic,</c><00:19:13.039><c> you</c>

not aware of this particular topic, you

not aware of this particular topic, you
will<00:19:13.440><c> not</c><00:19:14.400><c> uh</c><00:19:14.960><c> go</c><00:19:15.360><c> and</c><00:19:15.679><c> scan</c><00:19:15.919><c> the</c><00:19:16.160><c> entire</c><00:19:16.400><c> book.</c>

will not uh go and scan the entire book.

will not uh go and scan the entire book.
What<00:19:17.360><c> you</c><00:19:17.520><c> will</c><00:19:17.679><c> do</c><00:19:17.840><c> is</c><00:19:18.080><c> you</c><00:19:18.320><c> will</c><00:19:18.480><c> try</c><00:19:18.640><c> to</c>

What you will do is you will try to

What you will do is you will try to
first<00:19:19.200><c> find</c><00:19:19.440><c> the</c><00:19:19.760><c> structure</c><00:19:20.000><c> of</c><00:19:20.160><c> the</c><00:19:20.240><c> book.</c>

first find the structure of the book.

first find the structure of the book.
Maybe<00:19:20.720><c> you</c><00:19:20.880><c> will</c><00:19:21.039><c> find</c><00:19:21.120><c> the</c><00:19:21.360><c> index</c><00:19:21.840><c> where</c><00:19:22.000><c> is</c>

Maybe you will find the index where is

Maybe you will find the index where is
the<00:19:22.240><c> index,</c><00:19:22.559><c> where</c><00:19:22.720><c> is</c><00:19:22.799><c> the</c><00:19:22.880><c> appendex</c><00:19:23.280><c> and</c><00:19:23.520><c> all</c>

the index, where is the appendex and all

the index, where is the appendex and all
that<00:19:24.160><c> and</c><00:19:24.400><c> then</c><00:19:24.559><c> you</c><00:19:24.720><c> will</c><00:19:24.880><c> try</c><00:19:25.039><c> to</c><00:19:25.600><c> uh</c><00:19:25.840><c> figure</c>

that and then you will try to uh figure

that and then you will try to uh figure
out<00:19:26.799><c> which</c><00:19:27.039><c> chapter</c><00:19:27.440><c> this</c><00:19:27.760><c> book</c><00:19:28.080><c> might</c><00:19:28.400><c> uh</c>

out which chapter this book might uh

out which chapter this book might uh
this<00:19:28.720><c> question</c><00:19:29.600><c> uh</c><00:19:30.240><c> can</c><00:19:30.480><c> be</c><00:19:30.640><c> answered</c><00:19:31.039><c> from</c>

this question uh can be answered from

this question uh can be answered from
and<00:19:31.840><c> then</c><00:19:32.000><c> you</c><00:19:32.240><c> will</c><00:19:32.400><c> go</c><00:19:32.559><c> to</c><00:19:32.720><c> that</c><00:19:32.960><c> specific</c>

and then you will go to that specific

and then you will go to that specific
chapter<00:19:34.320><c> and</c><00:19:34.559><c> then</c><00:19:34.799><c> read</c><00:19:35.039><c> through</c><00:19:35.280><c> those</c>

chapter and then read through those

chapter and then read through those
chapters.<00:19:35.919><c> Right?</c><00:19:36.080><c> So</c><00:19:36.240><c> that</c><00:19:36.400><c> is</c><00:19:36.480><c> what</c><00:19:36.640><c> a</c><00:19:36.960><c> human</c>

chapters. Right? So that is what a human

chapters. Right? So that is what a human
will<00:19:37.520><c> do</c><00:19:38.559><c> and</c><00:19:38.799><c> that</c><00:19:39.039><c> is</c><00:19:39.280><c> exactly</c><00:19:40.720><c> the</c>

will do and that is exactly the

will do and that is exactly the
philosophy<00:19:41.840><c> of</c><00:19:42.320><c> uh</c><00:19:42.640><c> calling.</c><00:19:43.919><c> Okay.</c><00:19:44.559><c> So</c>

philosophy of uh calling. Okay. So

philosophy of uh calling. Okay. So
when<00:19:47.200><c> you</c><00:19:47.360><c> get</c><00:19:47.520><c> a</c><00:19:47.760><c> question</c>

when you get a question

when you get a question
what<00:19:49.679><c> you</c><00:19:49.919><c> do</c><00:19:50.160><c> is</c><00:19:50.400><c> first</c><00:19:51.679><c> you</c><00:19:52.080><c> will</c><00:19:52.320><c> first</c><00:19:52.640><c> scan</c>

what you do is first you will first scan

what you do is first you will first scan
through<00:19:53.919><c> the</c><00:19:54.240><c> appendix</c><00:19:54.720><c> and</c><00:19:54.880><c> all</c><00:19:55.039><c> that</c><00:19:55.200><c> and</c>

through the appendix and all that and

through the appendix and all that and
then<00:19:55.600><c> you</c><00:19:55.760><c> will</c><00:19:55.919><c> figure</c><00:19:56.160><c> out</c><00:19:56.720><c> where</c><00:19:57.039><c> exactly</c>

then you will figure out where exactly

then you will figure out where exactly
uh<00:19:58.480><c> uh</c><00:19:58.559><c> the</c><00:19:58.799><c> portion</c><00:19:59.200><c> where</c><00:19:59.600><c> your</c><00:19:59.919><c> question</c>

uh uh the portion where your question

uh uh the portion where your question
can<00:20:00.400><c> be</c><00:20:00.559><c> answered</c><00:20:01.520><c> and</c><00:20:01.760><c> then</c><00:20:02.720><c> you</c><00:20:03.039><c> will</c>

can be answered and then you will

can be answered and then you will
accumulate<00:20:04.559><c> all</c><00:20:04.880><c> those</c><00:20:05.600><c> relevant</c><00:20:06.080><c> chunks</c><00:20:06.400><c> or</c>

accumulate all those relevant chunks or

accumulate all those relevant chunks or
relevant<00:20:07.039><c> information</c><00:20:08.080><c> and</c><00:20:08.400><c> then</c><00:20:08.720><c> uh</c><00:20:08.960><c> finally</c>

relevant information and then uh finally

relevant information and then uh finally
you<00:20:09.760><c> will</c><00:20:09.919><c> come</c><00:20:10.000><c> up</c><00:20:10.160><c> with</c><00:20:10.320><c> a</c><00:20:10.480><c> response.</c><00:20:11.039><c> Right?</c>

you will come up with a response. Right?

you will come up with a response. Right?
So<00:20:12.080><c> this</c><00:20:12.320><c> is</c><00:20:12.480><c> where</c><00:20:13.360><c> uh</c><00:20:14.400><c> or</c><00:20:14.720><c> rather</c><00:20:15.039><c> this</c><00:20:15.280><c> was</c>

So this is where uh or rather this was

So this is where uh or rather this was
the<00:20:15.600><c> motivation</c><00:20:16.240><c> of</c><00:20:16.559><c> this</c><00:20:16.880><c> vision-based</c>

the motivation of this vision-based

the motivation of this vision-based
retrieval<00:20:18.080><c> model</c><00:20:18.640><c> called</c><00:20:19.280><c> pali.</c><00:20:19.679><c> Have</c><00:20:19.840><c> you</c>

retrieval model called pali. Have you

retrieval model called pali. Have you
heard<00:20:20.080><c> of</c><00:20:20.240><c> this</c><00:20:20.480><c> model</c><00:20:20.799><c> call</c><00:20:21.039><c> pali?</c><00:20:22.000><c> Yeah.</c>

heard of this model call pali? Yeah.

heard of this model call pali? Yeah.
Okay.<00:20:23.679><c> Yeah.</c><00:20:23.919><c> A</c><00:20:24.000><c> few</c><00:20:24.160><c> of</c><00:20:24.320><c> you.</c><00:20:24.799><c> So</c><00:20:25.120><c> call</c><00:20:25.440><c> pali</c>

Okay. Yeah. A few of you. So call pali

Okay. Yeah. A few of you. So call pali
was<00:20:26.160><c> introduced</c><00:20:26.640><c> I</c><00:20:26.799><c> think</c><00:20:26.960><c> in</c><00:20:27.200><c> uh</c><00:20:27.440><c> July</c><00:20:27.840><c> 2024</c>

was introduced I think in uh July 2024

was introduced I think in uh July 2024
just<00:20:29.840><c> less</c><00:20:30.080><c> than</c><00:20:30.240><c> a</c><00:20:30.400><c> year</c><00:20:30.559><c> back.</c><00:20:31.520><c> Uh</c><00:20:32.480><c> and</c><00:20:32.720><c> the</c>

just less than a year back. Uh and the

just less than a year back. Uh and the
motivation<00:20:33.440><c> is</c><00:20:34.240><c> we</c><00:20:34.559><c> will</c><00:20:34.799><c> treat</c><00:20:35.840><c> every</c><00:20:36.400><c> page</c>

motivation is we will treat every page

motivation is we will treat every page
as<00:20:37.919><c> an</c><00:20:38.159><c> image.</c><00:20:39.600><c> So</c><00:20:40.080><c> assume</c><00:20:40.400><c> that</c><00:20:40.640><c> you</c><00:20:40.799><c> have</c><00:20:40.880><c> a</c>

as an image. So assume that you have a

as an image. So assume that you have a
PDF<00:20:41.360><c> document</c><00:20:41.760><c> of</c><00:20:42.000><c> let's</c><00:20:42.240><c> say</c><00:20:42.720><c> 100</c><00:20:43.039><c> pages.</c>

PDF document of let's say 100 pages.

PDF document of let's say 100 pages.
Your<00:20:44.240><c> data</c><00:20:44.480><c> set</c><00:20:44.640><c> is</c><00:20:44.880><c> not</c><00:20:45.120><c> one</c><00:20:45.280><c> PDF</c><00:20:45.679><c> but</c><00:20:45.919><c> 100</c>

Your data set is not one PDF but 100

Your data set is not one PDF but 100
images.<00:20:47.520><c> Okay.</c><00:20:47.919><c> There</c><00:20:48.080><c> is</c><00:20:48.240><c> no</c><00:20:48.480><c> concept</c><00:20:48.799><c> of</c>

images. Okay. There is no concept of

images. Okay. There is no concept of
retrieving<00:20:49.840><c> u</c><00:20:50.080><c> images,</c><00:20:50.640><c> text</c><00:20:50.880><c> and</c><00:20:51.120><c> tables</c>

retrieving u images, text and tables

retrieving u images, text and tables
from<00:20:51.600><c> there.</c><00:20:52.240><c> So</c><00:20:52.400><c> how</c><00:20:52.640><c> it</c><00:20:52.799><c> works?</c>

from there. So how it works?

from there. So how it works?
So

So

So
it<00:20:57.039><c> first</c><00:20:57.600><c> creates</c><00:20:58.799><c> patches</c>

it first creates patches

it first creates patches
of<00:21:01.039><c> every</c><00:21:01.280><c> page.</c><00:21:01.679><c> So</c><00:21:02.000><c> now</c><00:21:02.320><c> let's</c><00:21:02.720><c> consider</c><00:21:03.200><c> one</c>

of every page. So now let's consider one

of every page. So now let's consider one
page.<00:21:04.000><c> One</c><00:21:04.240><c> page</c><00:21:04.400><c> is</c><00:21:04.559><c> nothing</c><00:21:04.799><c> but</c><00:21:05.200><c> one</c><00:21:05.600><c> image.</c>

page. One page is nothing but one image.

page. One page is nothing but one image.
And

And

And
the<00:21:09.120><c> same</c><00:21:09.440><c> will</c><00:21:09.679><c> apply</c><00:21:10.159><c> on</c><00:21:10.480><c> all</c><00:21:10.720><c> the</c><00:21:10.960><c> pages</c>

the same will apply on all the pages

the same will apply on all the pages
that<00:21:11.520><c> you</c><00:21:11.679><c> have</c><00:21:11.840><c> in</c><00:21:12.000><c> your</c><00:21:12.240><c> document.</c><00:21:13.280><c> The</c>

that you have in your document. The

that you have in your document. The
first<00:21:13.679><c> thing</c><00:21:13.760><c> that</c><00:21:14.000><c> it</c><00:21:14.159><c> will</c><00:21:14.320><c> do</c><00:21:14.400><c> is</c><00:21:14.640><c> it</c><00:21:14.880><c> will</c>

first thing that it will do is it will

first thing that it will do is it will
create<00:21:15.520><c> some</c><00:21:15.760><c> patches.</c><00:21:16.880><c> Uh</c><00:21:17.679><c> in</c><00:21:17.840><c> the</c><00:21:18.080><c> paper</c><00:21:19.039><c> I</c>

create some patches. Uh in the paper I

create some patches. Uh in the paper I
think<00:21:19.440><c> it</c><00:21:19.679><c> was</c><00:21:20.559><c> um</c><00:21:20.799><c> the</c><00:21:21.039><c> model</c><00:21:21.280><c> was</c><00:21:21.520><c> trained</c>

think it was um the model was trained

think it was um the model was trained
with<00:21:22.240><c> uh</c><00:21:22.480><c> 32</c><00:21:22.880><c> patches</c><00:21:23.440><c> like</c><00:21:23.760><c> 32</c><00:21:24.320><c> +</c><00:21:24.640><c> 32</c><00:21:25.760><c> here.</c>

with uh 32 patches like 32 + 32 here.

with uh 32 patches like 32 + 32 here.
How<00:21:26.400><c> many</c><00:21:26.559><c> patches</c><00:21:26.960><c> we</c><00:21:27.120><c> have?</c><00:21:27.360><c> We</c><00:21:27.520><c> have</c><00:21:27.760><c> 1</c><00:21:28.080><c> 2</c><00:21:28.400><c> 3</c>

How many patches we have? We have 1 2 3

How many patches we have? We have 1 2 3
4<00:21:29.039><c> 5</c><00:21:29.840><c> uh</c><00:21:30.080><c> 15</c><00:21:30.400><c> patches.</c><00:21:31.520><c> Right?</c>

4 5 uh 15 patches. Right?

4 5 uh 15 patches. Right?
Now<00:21:33.440><c> what</c><00:21:33.679><c> we</c><00:21:33.840><c> do</c><00:21:34.240><c> is</c><00:21:35.039><c> after</c><00:21:35.360><c> that</c><00:21:36.000><c> once</c><00:21:36.240><c> you</c>

Now what we do is after that once you

Now what we do is after that once you
have<00:21:36.559><c> those</c><00:21:36.880><c> patches</c><00:21:37.679><c> you</c><00:21:37.919><c> will</c><00:21:38.080><c> use</c><00:21:38.159><c> this</c>

have those patches you will use this

have those patches you will use this
call<00:21:38.960><c> model</c><00:21:39.360><c> embedding</c><00:21:39.840><c> model</c><00:21:40.240><c> and</c><00:21:40.559><c> it</c><00:21:40.799><c> will</c>

call model embedding model and it will

call model embedding model and it will
generate

generate

generate
one<00:21:43.360><c> vector</c><00:21:44.159><c> per</c><00:21:44.480><c> patch.</c>

one vector per patch.

one vector per patch.
Okay.<00:21:47.600><c> So</c><00:21:48.000><c> in</c><00:21:48.320><c> this</c><00:21:48.480><c> document</c><00:21:48.880><c> how</c><00:21:49.120><c> many</c>

Okay. So in this document how many

Okay. So in this document how many
vectors<00:21:49.600><c> we</c><00:21:49.760><c> will</c><00:21:50.000><c> have?</c>

vectors we will have?

vectors we will have?
&gt;&gt; 15.<00:21:53.600><c> So</c><00:21:53.760><c> now</c><00:21:53.919><c> if</c><00:21:54.080><c> I</c><00:21:54.240><c> if</c><00:21:54.480><c> my</c><00:21:54.720><c> document</c><00:21:55.039><c> is</c><00:21:55.280><c> having</c>

&gt;&gt; 15. So now if I if my document is having

&gt;&gt; 15. So now if I if my document is having
10<00:21:55.760><c> pages</c><00:21:56.159><c> how</c><00:21:56.320><c> many</c><00:21:56.480><c> vectors</c><00:21:56.799><c> I</c><00:21:57.039><c> will</c><00:21:57.120><c> have</c><00:21:57.280><c> in</c>

10 pages how many vectors I will have in

10 pages how many vectors I will have in
total.

total.

total.
&gt;&gt; 150.<00:22:00.880><c> Okay.</c><00:22:01.440><c> So</c><00:22:01.679><c> now</c><00:22:01.840><c> what</c><00:22:02.080><c> we</c><00:22:02.240><c> going</c><00:22:02.320><c> to</c><00:22:02.400><c> do</c><00:22:02.480><c> is</c>

&gt;&gt; 150. Okay. So now what we going to do is

&gt;&gt; 150. Okay. So now what we going to do is
we<00:22:02.799><c> are</c><00:22:02.880><c> going</c><00:22:02.960><c> to</c><00:22:03.120><c> see</c><00:22:03.679><c> this</c><00:22:04.000><c> middle</c><00:22:04.320><c> part</c><00:22:04.960><c> how</c>

we are going to see this middle part how

we are going to see this middle part how
it<00:22:05.360><c> generates</c><00:22:05.760><c> the</c><00:22:05.919><c> embedding</c><00:22:06.799><c> and</c><00:22:06.960><c> then</c><00:22:07.200><c> at</c>

it generates the embedding and then at

it generates the embedding and then at
later<00:22:07.919><c> and</c><00:22:08.080><c> in</c><00:22:08.240><c> last</c><00:22:08.480><c> section</c><00:22:08.720><c> we</c><00:22:08.960><c> will</c><00:22:09.120><c> see</c>

later and in last section we will see

later and in last section we will see
that<00:22:09.760><c> how</c><00:22:10.000><c> it</c><00:22:10.240><c> does</c><00:22:10.320><c> the</c><00:22:10.480><c> retrieval</c><00:22:10.960><c> and</c><00:22:11.120><c> then</c>

that how it does the retrieval and then

that how it does the retrieval and then
we<00:22:11.360><c> will</c><00:22:11.520><c> go</c><00:22:11.600><c> to</c><00:22:11.760><c> the</c><00:22:11.919><c> code.</c><00:22:12.559><c> Okay.</c><00:22:14.000><c> Okay.</c><00:22:14.640><c> So</c>

we will go to the code. Okay. Okay. So

we will go to the code. Okay. Okay. So
before<00:22:15.120><c> we</c><00:22:15.280><c> get</c><00:22:15.440><c> into</c><00:22:15.679><c> that</c><00:22:16.080><c> um</c><00:22:16.640><c> uh</c><00:22:17.120><c> this</c>

before we get into that um uh this

before we get into that um uh this
embedding<00:22:17.840><c> process</c><00:22:18.400><c> let's</c><00:22:18.640><c> take</c><00:22:18.799><c> a</c><00:22:19.679><c> detour</c><00:22:20.080><c> of</c>

embedding process let's take a detour of

embedding process let's take a detour of
vision<00:22:20.880><c> based</c><00:22:21.280><c> language</c><00:22:21.679><c> model.</c><00:22:22.480><c> Uh</c><00:22:22.799><c> have</c><00:22:22.960><c> you</c>

vision based language model. Uh have you

vision based language model. Uh have you
worked<00:22:23.280><c> on</c><00:22:23.360><c> a</c><00:22:23.520><c> vision</c><00:22:23.840><c> based</c><00:22:24.080><c> language</c><00:22:24.400><c> model?</c>

worked on a vision based language model?

worked on a vision based language model?
Any<00:22:24.960><c> of</c><00:22:25.120><c> you?</c><00:22:26.400><c> Okay.</c><00:22:26.799><c> Okay.</c><00:22:27.280><c> Few</c><00:22:27.520><c> of</c><00:22:27.679><c> you.</c><00:22:28.240><c> So</c>

Any of you? Okay. Okay. Few of you. So

Any of you? Okay. Okay. Few of you. So
ultimately<00:22:30.559><c> if</c><00:22:30.880><c> you</c><00:22:31.039><c> think</c><00:22:31.200><c> about</c><00:22:31.360><c> it</c><00:22:31.919><c> um</c><00:22:32.559><c> we</c>

ultimately if you think about it um we

ultimately if you think about it um we
had<00:22:34.080><c> uh</c>

had uh

had uh
language<00:22:36.159><c> models</c><00:22:37.120><c> uh</c><00:22:37.360><c> I'm</c><00:22:37.600><c> not</c><00:22:37.760><c> talking</c><00:22:38.000><c> about</c>

language models uh I'm not talking about

language models uh I'm not talking about
uh<00:22:39.280><c> uh</c><00:22:39.760><c> large</c><00:22:40.080><c> language</c><00:22:40.480><c> model</c><00:22:40.720><c> but</c><00:22:41.120><c> text</c>

uh uh large language model but text

uh uh large language model but text
based<00:22:42.159><c> models</c><00:22:43.360><c> uh</c><00:22:43.760><c> since</c><00:22:44.320><c> we</c><00:22:44.559><c> had</c><00:22:44.960><c> transformer</c>

based models uh since we had transformer

based models uh since we had transformer
based<00:22:45.840><c> architecture</c><00:22:46.480><c> right</c><00:22:47.200><c> and</c><00:22:47.440><c> then</c><00:22:47.919><c> at</c>

based architecture right and then at

based architecture right and then at
that<00:22:48.400><c> time</c><00:22:48.720><c> we</c><00:22:48.960><c> also</c><00:22:49.280><c> had</c><00:22:50.720><c> uh</c><00:22:51.679><c> models</c><00:22:52.080><c> which</c>

that time we also had uh models which

that time we also had uh models which
can<00:22:52.720><c> work</c><00:22:53.039><c> pretty</c><00:22:53.360><c> well</c><00:22:53.520><c> with</c><00:22:53.760><c> images</c><00:22:54.159><c> which</c>

can work pretty well with images which

can work pretty well with images which
are<00:22:54.559><c> based</c><00:22:54.799><c> on</c><00:22:55.520><c> CNN's</c>

are based on CNN's

are based on CNN's
now<00:22:57.760><c> What</c><00:22:58.080><c> researchers</c><00:22:58.559><c> thought</c><00:22:58.799><c> was</c><00:22:59.760><c> uh</c><00:22:59.919><c> now</c>

now What researchers thought was uh now

now What researchers thought was uh now
that<00:23:00.320><c> we</c><00:23:00.559><c> have</c><00:23:00.640><c> a</c><00:23:00.799><c> language</c><00:23:01.200><c> model</c><00:23:01.919><c> why</c><00:23:02.159><c> can't</c>

that we have a language model why can't

that we have a language model why can't
we<00:23:02.559><c> just</c><00:23:03.039><c> uh</c><00:23:03.840><c> make</c><00:23:04.080><c> use</c><00:23:04.320><c> of</c><00:23:04.480><c> that</c><00:23:05.280><c> to</c><00:23:05.520><c> work</c><00:23:05.760><c> with</c>

we just uh make use of that to work with

we just uh make use of that to work with
vision<00:23:07.280><c> it</c><00:23:07.440><c> could</c><00:23:07.600><c> be</c><00:23:07.760><c> images</c><00:23:08.159><c> or</c><00:23:08.400><c> videos</c><00:23:09.280><c> are</c>

vision it could be images or videos are

vision it could be images or videos are
nothing<00:23:09.600><c> but</c><00:23:10.000><c> uh</c><00:23:10.240><c> images</c><00:23:10.799><c> but</c><00:23:11.039><c> but</c><00:23:11.200><c> with</c><00:23:11.360><c> a</c>

nothing but uh images but but with a

nothing but uh images but but with a
time<00:23:11.760><c> stamp</c><00:23:12.240><c> right</c><00:23:12.559><c> another</c><00:23:12.880><c> dimension</c><00:23:13.280><c> you</c>

time stamp right another dimension you

time stamp right another dimension you
can<00:23:13.600><c> think</c><00:23:13.760><c> of</c><00:23:13.919><c> it</c><00:23:14.720><c> uh</c><00:23:15.600><c> and</c><00:23:15.840><c> then</c>

can think of it uh and then

can think of it uh and then
what<00:23:19.440><c> people</c><00:23:19.760><c> did</c><00:23:20.080><c> was</c><00:23:20.559><c> they</c><00:23:20.799><c> took</c><00:23:21.120><c> some</c>

what people did was they took some

what people did was they took some
vision<00:23:22.000><c> based</c><00:23:22.400><c> model</c><00:23:23.039><c> and</c><00:23:23.280><c> then</c><00:23:23.440><c> they</c><00:23:23.600><c> took</c>

vision based model and then they took

vision based model and then they took
some<00:23:24.320><c> uh</c><00:23:24.640><c> text</c><00:23:25.039><c> based</c><00:23:25.360><c> model</c><00:23:26.080><c> they</c><00:23:26.320><c> both</c><00:23:26.480><c> are</c>

some uh text based model they both are

some uh text based model they both are
separate<00:23:27.039><c> right</c><00:23:27.360><c> At</c><00:23:27.600><c> this</c><00:23:27.760><c> point</c><00:23:27.919><c> what</c><00:23:28.080><c> we're</c>

separate right At this point what we're

separate right At this point what we're
talking<00:23:28.559><c> about</c><00:23:28.720><c> is</c><00:23:29.679><c> uh</c><00:23:31.120><c> before</c><00:23:31.520><c> the</c><00:23:31.919><c> training</c>

talking about is uh before the training

talking about is uh before the training
right<00:23:32.960><c> like</c><00:23:33.200><c> the</c><00:23:33.360><c> these</c><00:23:33.679><c> two</c><00:23:33.840><c> models</c><00:23:34.159><c> are</c>

right like the these two models are

right like the these two models are
completely<00:23:34.799><c> separate</c><00:23:35.200><c> they</c><00:23:35.440><c> all</c><00:23:35.600><c> have</c><00:23:36.320><c> you</c>

completely separate they all have you

completely separate they all have you
know<00:23:36.640><c> they</c><00:23:37.120><c> they</c><00:23:37.360><c> are</c><00:23:37.440><c> in</c><00:23:37.679><c> different</c><00:23:37.919><c> space</c>

know they they are in different space

know they they are in different space
basically<00:23:39.280><c> right</c><00:23:40.159><c> and</c><00:23:40.400><c> the</c><00:23:40.640><c> idea</c><00:23:41.039><c> is</c>

basically right and the idea is

basically right and the idea is
at<00:23:42.880><c> the</c><00:23:43.039><c> end</c><00:23:43.200><c> of</c><00:23:43.280><c> the</c><00:23:43.440><c> day</c><00:23:44.240><c> come</c><00:23:44.480><c> up</c><00:23:44.640><c> with</c><00:23:44.799><c> a</c>

at the end of the day come up with a

at the end of the day come up with a
model<00:23:45.679><c> where</c><00:23:46.080><c> if</c><00:23:46.320><c> you</c><00:23:46.960><c> send</c><00:23:47.200><c> an</c><00:23:47.440><c> image</c><00:23:47.679><c> of</c><00:23:47.840><c> a</c>

model where if you send an image of a

model where if you send an image of a
dog<00:23:48.880><c> the</c><00:23:49.120><c> vector</c><00:23:49.520><c> that</c><00:23:49.840><c> you</c><00:23:50.080><c> will</c><00:23:50.240><c> get</c><00:23:50.880><c> and</c><00:23:51.120><c> if</c>

dog the vector that you will get and if

dog the vector that you will get and if
you<00:23:51.520><c> send</c><00:23:51.760><c> a</c><00:23:52.320><c> text</c><00:23:53.039><c> about</c><00:23:53.440><c> dog</c><00:23:54.240><c> the</c><00:23:54.480><c> vector</c>

you send a text about dog the vector

you send a text about dog the vector
that<00:23:54.960><c> you</c><00:23:55.120><c> will</c><00:23:55.280><c> get</c><00:23:55.440><c> at</c><00:23:55.679><c> the</c><00:23:55.840><c> end</c><00:23:56.240><c> those</c><00:23:56.480><c> two</c>

that you will get at the end those two

that you will get at the end those two
vectors<00:23:57.039><c> will</c><00:23:57.200><c> be</c><00:23:57.280><c> very</c><00:23:57.520><c> close</c><00:23:57.600><c> to</c><00:23:57.760><c> each</c>

vectors will be very close to each

vectors will be very close to each
other.<00:23:59.440><c> Initially</c><00:24:00.080><c> it</c><00:24:00.320><c> will</c><00:24:00.480><c> not</c><00:24:00.640><c> be</c><00:24:00.799><c> close</c>

other. Initially it will not be close

other. Initially it will not be close
because<00:24:02.880><c> when</c><00:24:03.200><c> when</c><00:24:03.440><c> I</c><00:24:03.600><c> say</c><00:24:03.760><c> a</c><00:24:04.000><c> dog</c><00:24:04.159><c> is</c><00:24:04.320><c> sitting</c>

because when when I say a dog is sitting

because when when I say a dog is sitting
on<00:24:04.640><c> a</c><00:24:04.880><c> field</c><00:24:05.200><c> and</c><00:24:05.440><c> if</c><00:24:05.679><c> I</c><00:24:05.760><c> use</c><00:24:05.919><c> any</c><00:24:06.159><c> text</c><00:24:06.400><c> space</c>

on a field and if I use any text space

on a field and if I use any text space
model<00:24:06.960><c> it</c><00:24:07.200><c> will</c><00:24:07.280><c> generate</c><00:24:07.600><c> a</c><00:24:07.760><c> vector</c><00:24:08.159><c> and</c><00:24:08.400><c> for</c>

model it will generate a vector and for

model it will generate a vector and for
the<00:24:08.799><c> sake</c><00:24:08.960><c> of</c><00:24:09.200><c> simplicity</c><00:24:09.840><c> simplicity</c><00:24:10.720><c> let's</c>

the sake of simplicity simplicity let's

the sake of simplicity simplicity let's
assume<00:24:11.440><c> the</c><00:24:11.679><c> vector</c><00:24:12.080><c> dimension</c><00:24:12.480><c> is</c><00:24:12.799><c> 10.</c><00:24:13.679><c> So</c><00:24:13.840><c> it</c>

assume the vector dimension is 10. So it

assume the vector dimension is 10. So it
will<00:24:14.159><c> generate</c><00:24:14.480><c> a</c><00:24:14.799><c> array</c><00:24:15.039><c> of</c><00:24:15.200><c> 10</c><00:24:15.440><c> numbers.</c>

will generate a array of 10 numbers.

will generate a array of 10 numbers.
Similarly<00:24:18.159><c> when</c><00:24:18.400><c> you</c><00:24:18.559><c> pass</c><00:24:18.799><c> an</c><00:24:19.039><c> image</c><00:24:19.279><c> of</c><00:24:19.440><c> a</c>

Similarly when you pass an image of a

Similarly when you pass an image of a
dog<00:24:20.080><c> it</c><00:24:20.240><c> will</c><00:24:20.400><c> generate</c><00:24:20.720><c> an</c><00:24:20.960><c> im</c><00:24:21.360><c> vector</c><00:24:21.760><c> final</c>

dog it will generate an im vector final

dog it will generate an im vector final
vector<00:24:22.480><c> with</c><00:24:22.799><c> 10</c><00:24:23.039><c> numbers.</c><00:24:23.840><c> Let's</c><00:24:24.080><c> say</c><00:24:24.240><c> the</c>

vector with 10 numbers. Let's say the

vector with 10 numbers. Let's say the
embedding<00:24:24.960><c> vector</c><00:24:25.520><c> size</c><00:24:25.760><c> is</c><00:24:25.919><c> 10.</c><00:24:26.480><c> Now</c><00:24:26.720><c> those</c>

embedding vector size is 10. Now those

embedding vector size is 10. Now those
10<00:24:27.200><c> numbers</c><00:24:27.440><c> and</c><00:24:27.760><c> this</c><00:24:28.000><c> 10</c><00:24:28.240><c> numbers</c><00:24:28.640><c> for</c><00:24:28.880><c> the</c>

10 numbers and this 10 numbers for the

10 numbers and this 10 numbers for the
text<00:24:29.520><c> they</c><00:24:29.760><c> will</c><00:24:30.000><c> be</c><00:24:30.159><c> anywhere</c><00:24:30.559><c> in</c><00:24:30.720><c> the</c><00:24:30.880><c> space</c>

text they will be anywhere in the space

text they will be anywhere in the space
because<00:24:31.440><c> they</c><00:24:31.840><c> don't</c><00:24:32.080><c> have</c><00:24:32.320><c> any</c><00:24:32.640><c> correlation</c>

because they don't have any correlation

because they don't have any correlation
at<00:24:34.400><c> the</c><00:24:34.720><c> before</c><00:24:35.440><c> uh</c><00:24:35.520><c> the</c><00:24:35.840><c> training.</c><00:24:36.960><c> Now</c><00:24:37.120><c> what</c>

at the before uh the training. Now what

at the before uh the training. Now what
happens<00:24:37.679><c> is</c>

happens is

happens is
at<00:24:39.679><c> the</c><00:24:39.919><c> time</c><00:24:40.080><c> of</c><00:24:40.240><c> training</c><00:24:40.960><c> we</c><00:24:41.200><c> take</c><00:24:41.440><c> lot</c><00:24:41.679><c> of</c>

at the time of training we take lot of

at the time of training we take lot of
samples<00:24:42.320><c> positive</c><00:24:42.720><c> samples</c><00:24:43.120><c> where</c><00:24:43.360><c> the</c><00:24:43.679><c> text</c>

samples positive samples where the text

samples positive samples where the text
is<00:24:44.159><c> there</c><00:24:44.640><c> uh</c><00:24:44.720><c> text</c><00:24:45.039><c> is</c><00:24:45.200><c> there</c><00:24:45.760><c> which</c>

is there uh text is there which

is there uh text is there which
replicates<00:24:46.720><c> the</c><00:24:46.960><c> image</c><00:24:47.520><c> and</c><00:24:47.760><c> there</c><00:24:47.919><c> are</c><00:24:48.159><c> lot</c>

replicates the image and there are lot

replicates the image and there are lot
of<00:24:48.799><c> uh</c><00:24:49.120><c> negative</c><00:24:49.520><c> samples</c><00:24:49.919><c> where</c><00:24:50.720><c> image</c><00:24:51.039><c> is</c>

of uh negative samples where image is

of uh negative samples where image is
there<00:24:51.440><c> but</c><00:24:51.840><c> text</c><00:24:52.080><c> is</c><00:24:52.320><c> something</c><00:24:52.559><c> random</c><00:24:53.679><c> and</c>

there but text is something random and

there but text is something random and
the<00:24:54.080><c> idea</c><00:24:54.320><c> is</c><00:24:54.559><c> the</c><00:24:54.799><c> loss</c><00:24:55.120><c> function</c><00:24:55.360><c> that</c><00:24:55.600><c> we</c>

the idea is the loss function that we

the idea is the loss function that we
use<00:24:56.640><c> is</c><00:24:57.360><c> if</c><00:24:57.600><c> they</c><00:24:57.840><c> are</c><00:24:58.080><c> similar</c>

use is if they are similar

use is if they are similar
we<00:25:00.080><c> want</c><00:25:00.240><c> to</c><00:25:00.400><c> make</c><00:25:00.559><c> sure</c><00:25:00.799><c> that</c><00:25:01.039><c> the</c><00:25:01.279><c> loss</c><00:25:01.520><c> is</c>

we want to make sure that the loss is

we want to make sure that the loss is
less<00:25:03.360><c> but</c><00:25:03.600><c> if</c><00:25:03.760><c> they</c><00:25:03.919><c> are</c><00:25:04.000><c> orthogonal</c><00:25:04.559><c> or</c><00:25:04.799><c> very</c>

less but if they are orthogonal or very

less but if they are orthogonal or very
separate<00:25:05.600><c> we</c><00:25:05.840><c> will</c><00:25:06.000><c> say</c><00:25:06.080><c> that</c><00:25:06.400><c> Okay,</c><00:25:06.720><c> the</c><00:25:07.039><c> loss</c>

separate we will say that Okay, the loss

separate we will say that Okay, the loss
is<00:25:07.440><c> high</c><00:25:08.400><c> and</c><00:25:08.799><c> during</c><00:25:09.120><c> this</c><00:25:09.360><c> loss</c><00:25:09.919><c> you</c><00:25:10.080><c> know</c>

is high and during this loss you know

is high and during this loss you know
this<00:25:10.559><c> training</c><00:25:11.039><c> process</c><00:25:12.080><c> we</c><00:25:12.480><c> kind</c><00:25:12.799><c> of</c>

this training process we kind of

this training process we kind of
optimize<00:25:13.679><c> and</c><00:25:14.000><c> at</c><00:25:14.240><c> the</c><00:25:14.400><c> end</c><00:25:15.600><c> we</c><00:25:16.080><c> we</c><00:25:16.400><c> see</c><00:25:16.559><c> that</c>

optimize and at the end we we see that

optimize and at the end we we see that
when<00:25:17.200><c> you</c><00:25:17.440><c> send</c><00:25:17.600><c> an</c><00:25:17.840><c> image</c><00:25:18.159><c> or</c><00:25:18.400><c> a</c><00:25:18.640><c> text</c><00:25:19.279><c> the</c>

when you send an image or a text the

when you send an image or a text the
embedding<00:25:19.919><c> that</c><00:25:20.080><c> we</c><00:25:20.240><c> get</c><00:25:20.400><c> at</c><00:25:20.559><c> the</c><00:25:20.720><c> end</c><00:25:21.120><c> are</c>

embedding that we get at the end are

embedding that we get at the end are
very<00:25:21.840><c> close</c><00:25:22.080><c> to</c><00:25:22.240><c> each</c><00:25:22.480><c> other.</c><00:25:23.440><c> Okay.</c><00:25:23.840><c> So</c><00:25:24.000><c> we</c>

very close to each other. Okay. So we

very close to each other. Okay. So we
are<00:25:24.320><c> not</c><00:25:24.480><c> going</c><00:25:24.559><c> to</c><00:25:25.039><c> deep</c><00:25:25.279><c> dive</c><00:25:25.520><c> into</c><00:25:26.799><c> u</c><00:25:27.120><c> vision</c>

are not going to deep dive into u vision

are not going to deep dive into u vision
based<00:25:27.679><c> model</c><00:25:28.000><c> but</c><00:25:28.480><c> there</c><00:25:28.720><c> is</c><00:25:28.960><c> something</c>

based model but there is something

based model but there is something
called<00:25:29.919><c> contrastive</c><00:25:30.559><c> learning</c><00:25:31.360><c> where</c><00:25:32.720><c> if</c><00:25:32.960><c> you</c>

called contrastive learning where if you

called contrastive learning where if you
send<00:25:33.919><c> an</c><00:25:34.480><c> image</c><00:25:35.120><c> and</c><00:25:35.440><c> a</c><00:25:35.679><c> relevant</c><00:25:36.480><c> uh</c><00:25:36.799><c> positive</c>

send an image and a relevant uh positive

send an image and a relevant uh positive
tag<00:25:38.559><c> and</c><00:25:38.799><c> if</c><00:25:38.960><c> the</c><00:25:39.200><c> vectors</c><00:25:39.520><c> are</c><00:25:39.760><c> very</c><00:25:40.559><c> uh</c><00:25:41.440><c> very</c>

tag and if the vectors are very uh very

tag and if the vectors are very uh very
sparse<00:25:42.159><c> like</c><00:25:42.320><c> very</c><00:25:42.960><c> uh</c><00:25:43.600><c> uh</c><00:25:44.559><c> very</c><00:25:44.880><c> much</c><00:25:45.120><c> apart</c>

sparse like very uh uh very much apart

sparse like very uh uh very much apart
from<00:25:45.600><c> each</c><00:25:45.760><c> other</c><00:25:46.000><c> then</c><00:25:46.240><c> the</c><00:25:46.400><c> loss</c><00:25:46.640><c> will</c><00:25:46.880><c> be</c>

from each other then the loss will be

from each other then the loss will be
very<00:25:47.200><c> high</c><00:25:47.679><c> because</c><00:25:47.919><c> we</c><00:25:48.159><c> want</c><00:25:48.320><c> these</c><00:25:48.559><c> two</c>

very high because we want these two

very high because we want these two
vectors<00:25:49.039><c> to</c><00:25:49.200><c> be</c><00:25:49.360><c> close</c><00:25:49.760><c> right.</c><00:25:50.000><c> So</c><00:25:50.400><c> that</c><00:25:50.640><c> way</c>

vectors to be close right. So that way

vectors to be close right. So that way
uh<00:25:51.600><c> during</c><00:25:51.919><c> the</c><00:25:52.480><c> uh</c><00:25:52.640><c> back</c><00:25:53.120><c> uh</c><00:25:53.279><c> uh</c><00:25:53.520><c> back</c>

uh during the uh back uh uh back

uh during the uh back uh uh back
propagation<00:25:54.559><c> we</c><00:25:54.799><c> update</c><00:25:55.120><c> the</c><00:25:55.279><c> weights</c>

propagation we update the weights

propagation we update the weights
accordingly.<00:25:56.559><c> So</c><00:25:56.720><c> this</c><00:25:56.880><c> is</c><00:25:57.039><c> one</c><00:25:57.200><c> of</c><00:25:57.279><c> the</c>

accordingly. So this is one of the

accordingly. So this is one of the
reason<00:25:57.760><c> if</c><00:25:58.000><c> you</c><00:25:58.159><c> think</c><00:25:58.320><c> about</c><00:25:58.480><c> it</c><00:25:59.279><c> uh</c><00:25:59.360><c> you</c>

reason if you think about it uh you

reason if you think about it uh you
might<00:25:59.760><c> have</c><00:25:59.840><c> seen</c><00:26:00.080><c> in</c><00:26:00.320><c> language</c><00:26:00.720><c> models</c><00:26:01.039><c> or</c>

might have seen in language models or

might have seen in language models or
when<00:26:01.520><c> you</c><00:26:01.679><c> use</c><00:26:01.919><c> any</c><00:26:03.120><c> uh</c><00:26:03.279><c> let's</c><00:26:03.520><c> say</c><00:26:03.679><c> any</c><00:26:04.320><c> um</c>

when you use any uh let's say any um

when you use any uh let's say any um
foundational<00:26:05.120><c> model</c><00:26:05.919><c> they</c><00:26:06.159><c> say</c><00:26:06.320><c> that</c><00:26:06.720><c> always</c>

foundational model they say that always

foundational model they say that always
your<00:26:07.360><c> prompt</c><00:26:07.840><c> should</c><00:26:08.080><c> be</c>

your prompt should be

your prompt should be
uh<00:26:09.919><c> about</c><00:26:10.320><c> what</c><00:26:10.559><c> you</c><00:26:10.799><c> want</c><00:26:11.600><c> not</c><00:26:11.840><c> about</c><00:26:12.080><c> what</c>

uh about what you want not about what

uh about what you want not about what
you<00:26:12.480><c> don't</c><00:26:12.799><c> want.</c><00:26:13.679><c> Have</c><00:26:13.840><c> you</c><00:26:13.919><c> seen</c><00:26:14.080><c> this?</c><00:26:14.320><c> If</c>

you don't want. Have you seen this? If

you don't want. Have you seen this? If
you<00:26:14.640><c> are</c><00:26:14.799><c> into</c><00:26:15.039><c> prompt</c><00:26:15.440><c> engineering</c><00:26:16.159><c> why</c><00:26:16.320><c> they</c>

you are into prompt engineering why they

you are into prompt engineering why they
say<00:26:16.720><c> this</c><00:26:17.760><c> just</c><00:26:18.000><c> think</c><00:26:18.159><c> about</c><00:26:18.320><c> it.</c><00:26:18.640><c> Let's</c><00:26:18.880><c> say</c>

say this just think about it. Let's say

say this just think about it. Let's say
if<00:26:19.520><c> I</c><00:26:19.760><c> say</c><00:26:20.320><c> uh</c><00:26:21.760><c> uh</c><00:26:22.480><c> okay</c><00:26:23.760><c> let</c><00:26:24.000><c> me</c><00:26:24.480><c> give</c><00:26:24.640><c> you</c><00:26:24.799><c> an</c>

if I say uh uh okay let me give you an

if I say uh uh okay let me give you an
uh<00:26:26.000><c> analogy</c><00:26:26.720><c> right</c><00:26:28.080><c> if</c><00:26:28.320><c> you</c><00:26:28.480><c> are</c><00:26:28.720><c> going</c><00:26:28.960><c> for</c><00:26:29.120><c> a</c>

uh analogy right if you are going for a

uh analogy right if you are going for a
dinner<00:26:29.679><c> right</c><00:26:29.919><c> with</c><00:26:30.080><c> your</c><00:26:30.320><c> wife</c><00:26:31.039><c> and</c><00:26:31.360><c> if</c><00:26:31.520><c> you</c>

dinner right with your wife and if you

dinner right with your wife and if you
ask<00:26:32.000><c> your</c><00:26:32.320><c> wife</c><00:26:32.799><c> what</c><00:26:32.960><c> would</c><00:26:33.200><c> you</c><00:26:33.279><c> like</c><00:26:33.440><c> to</c>

ask your wife what would you like to

ask your wife what would you like to
have<00:26:33.919><c> she</c><00:26:34.080><c> will</c><00:26:34.240><c> say</c><00:26:34.320><c> that</c><00:26:34.559><c> I</c><00:26:34.720><c> I</c><00:26:34.880><c> I</c><00:26:35.200><c> let's</c><00:26:35.520><c> say</c>

have she will say that I I I let's say

have she will say that I I I let's say
uh<00:26:37.600><c> I</c><00:26:37.919><c> don't</c><00:26:38.080><c> like</c><00:26:38.240><c> this</c><00:26:38.559><c> I</c><00:26:38.799><c> don't</c><00:26:38.960><c> like</c><00:26:39.120><c> that</c>

uh I don't like this I don't like that

uh I don't like this I don't like that
but<00:26:39.919><c> that</c><00:26:40.159><c> was</c><00:26:40.320><c> not</c><00:26:40.480><c> my</c><00:26:40.720><c> question</c><00:26:41.279><c> my</c><00:26:41.600><c> question</c>

but that was not my question my question

but that was not my question my question
was<00:26:42.080><c> what</c><00:26:42.320><c> you</c><00:26:42.480><c> want</c><00:26:43.360><c> that</c><00:26:43.600><c> is</c><00:26:43.760><c> always</c>

was what you want that is always

was what you want that is always
difficult<00:26:44.320><c> to</c><00:26:44.880><c> uh</c><00:26:45.200><c> answer</c><00:26:45.840><c> right</c><00:26:46.240><c> people</c><00:26:46.480><c> will</c>

difficult to uh answer right people will

difficult to uh answer right people will
say<00:26:46.799><c> that</c><00:26:47.360><c> uh</c>

say that uh

say that uh
Okay,<00:26:49.120><c> would</c><00:26:49.360><c> you</c><00:26:49.440><c> like</c><00:26:49.600><c> to</c><00:26:49.760><c> have</c><00:26:49.840><c> this?</c><00:26:50.080><c> No,</c><00:26:50.320><c> I</c>

Okay, would you like to have this? No, I

Okay, would you like to have this? No, I
don't<00:26:50.640><c> like</c><00:26:50.799><c> this.</c><00:26:51.600><c> But</c><00:26:51.760><c> when</c><00:26:51.919><c> you</c><00:26:52.000><c> ask</c><00:26:52.159><c> that,</c>

don't like this. But when you ask that,

don't like this. But when you ask that,
okay,<00:26:52.559><c> you</c><00:26:52.799><c> tell</c><00:26:52.960><c> me</c><00:26:53.039><c> what</c><00:26:53.279><c> you</c><00:26:53.440><c> like,</c><00:26:53.840><c> it's</c>

okay, you tell me what you like, it's

okay, you tell me what you like, it's
very<00:26:54.320><c> hard.</c><00:26:55.279><c> So</c><00:26:55.440><c> that's</c><00:26:55.760><c> why</c><00:26:56.080><c> when</c><00:26:56.320><c> you</c><00:26:56.480><c> give</c><00:26:56.640><c> a</c>

very hard. So that's why when you give a

very hard. So that's why when you give a
prompt<00:26:57.279><c> that</c><00:26:58.000><c> u</c><00:26:58.559><c> I</c><00:26:58.799><c> want</c><00:26:59.120><c> a</c><00:26:59.760><c> dog</c><00:27:00.400><c> sitting</c><00:27:00.720><c> on</c>

prompt that u I want a dog sitting on

prompt that u I want a dog sitting on
this<00:27:01.120><c> chair,</c><00:27:01.360><c> it's</c><00:27:01.520><c> a</c><00:27:01.679><c> very</c><00:27:01.840><c> nice</c><00:27:02.080><c> prompt.</c><00:27:02.799><c> But</c>

this chair, it's a very nice prompt. But

this chair, it's a very nice prompt. But
if<00:27:03.120><c> you</c><00:27:03.200><c> say</c><00:27:03.360><c> that</c><00:27:04.799><c> dog</c><00:27:05.919><c> should</c><00:27:06.240><c> not</c><00:27:06.400><c> sit</c><00:27:06.640><c> on</c>

if you say that dog should not sit on

if you say that dog should not sit on
the<00:27:07.039><c> floor,</c><00:27:08.080><c> it</c><00:27:08.320><c> can</c><00:27:08.559><c> generate</c><00:27:08.880><c> any</c><00:27:09.120><c> image</c>

the floor, it can generate any image

the floor, it can generate any image
because<00:27:09.679><c> you</c><00:27:09.840><c> are</c><00:27:09.919><c> not</c><00:27:10.080><c> saying</c><00:27:10.240><c> that</c><00:27:10.559><c> it</c>

because you are not saying that it

because you are not saying that it
should<00:27:10.880><c> sit</c><00:27:11.039><c> on</c><00:27:11.200><c> a</c><00:27:11.360><c> chair.</c><00:27:11.679><c> It</c><00:27:11.840><c> might</c><00:27:12.000><c> be</c>

should sit on a chair. It might be

should sit on a chair. It might be
sitting<00:27:12.320><c> on</c><00:27:12.480><c> a</c><00:27:12.880><c> desk</c><00:27:13.279><c> or</c><00:27:13.679><c> somewhere</c><00:27:14.080><c> else.</c>

sitting on a desk or somewhere else.

sitting on a desk or somewhere else.
Right?<00:27:15.120><c> So</c><00:27:15.919><c> that</c><00:27:16.240><c> is</c><00:27:16.320><c> the</c><00:27:16.559><c> reason</c><00:27:17.039><c> we</c><00:27:17.360><c> always</c>

Right? So that is the reason we always

Right? So that is the reason we always
say<00:27:17.760><c> that</c><00:27:18.080><c> the</c><00:27:18.400><c> prompt</c><00:27:18.799><c> should</c><00:27:19.039><c> be</c><00:27:19.840><c> uh</c><00:27:20.000><c> very</c>

say that the prompt should be uh very

say that the prompt should be uh very
much<00:27:20.400><c> positive</c><00:27:20.799><c> what</c><00:27:21.039><c> you</c><00:27:21.200><c> want</c><00:27:21.440><c> not</c><00:27:21.600><c> the</c>

much positive what you want not the

much positive what you want not the
negative<00:27:22.559><c> because</c><00:27:23.039><c> uh</c><00:27:23.120><c> you</c><00:27:23.279><c> know</c><00:27:23.440><c> data</c><00:27:23.679><c> set</c>

negative because uh you know data set

negative because uh you know data set
doesn't<00:27:24.080><c> have</c><00:27:24.240><c> that</c><00:27:24.480><c> much</c><00:27:25.360><c> of</c><00:27:25.600><c> negative</c>

doesn't have that much of negative

doesn't have that much of negative
samples.<00:27:27.360><c> Now</c><00:27:27.600><c> let's</c><00:27:27.840><c> come</c><00:27:28.000><c> back</c><00:27:28.080><c> to</c><00:27:28.240><c> call</c>

samples. Now let's come back to call

samples. Now let's come back to call
paraly<00:27:28.880><c> how</c><00:27:29.039><c> it</c><00:27:29.200><c> works.</c><00:27:29.919><c> So</c>

paraly how it works. So

paraly how it works. So
you<00:27:32.080><c> give</c><00:27:32.320><c> an</c><00:27:32.480><c> image.</c><00:27:32.799><c> So</c><00:27:32.960><c> now</c><00:27:33.200><c> this</c><00:27:33.520><c> image</c><00:27:33.840><c> is</c>

you give an image. So now this image is

you give an image. So now this image is
you<00:27:34.799><c> can</c><00:27:34.960><c> think</c><00:27:35.120><c> of</c><00:27:35.279><c> it</c><00:27:35.440><c> like</c><00:27:36.640><c> one</c><00:27:36.880><c> of</c><00:27:37.039><c> the</c>

you can think of it like one of the

you can think of it like one of the
patch<00:27:38.159><c> okay</c><00:27:39.039><c> it</c><00:27:39.279><c> goes</c><00:27:39.520><c> through</c><00:27:40.400><c> uh</c><00:27:40.559><c> the</c><00:27:41.279><c> uh</c>

patch okay it goes through uh the uh

patch okay it goes through uh the uh
vision<00:27:42.080><c> based</c><00:27:42.320><c> encoder</c><00:27:43.039><c> and</c><00:27:43.279><c> it</c><00:27:43.440><c> will</c>

vision based encoder and it will

vision based encoder and it will
generate<00:27:43.919><c> an</c><00:27:44.400><c> uh</c><00:27:44.480><c> embedding</c><00:27:45.200><c> and</c><00:27:45.440><c> then</c><00:27:45.600><c> we</c>

generate an uh embedding and then we

generate an uh embedding and then we
have<00:27:45.840><c> a</c><00:27:46.000><c> linear</c><00:27:46.400><c> projection</c><00:27:47.440><c> and</c><00:27:47.679><c> the</c><00:27:47.840><c> reason</c>

have a linear projection and the reason

have a linear projection and the reason
that<00:27:48.159><c> we</c><00:27:48.320><c> have</c><00:27:48.400><c> the</c><00:27:48.640><c> linear</c><00:27:48.960><c> projection</c><00:27:49.360><c> is</c>

that we have the linear projection is

that we have the linear projection is
because<00:27:50.640><c> at</c><00:27:50.799><c> the</c><00:27:50.960><c> end</c><00:27:51.120><c> of</c><00:27:51.200><c> the</c><00:27:51.360><c> day</c><00:27:52.159><c> uh</c><00:27:52.320><c> when</c>

because at the end of the day uh when

because at the end of the day uh when
you<00:27:52.880><c> ask</c><00:27:53.120><c> a</c><00:27:53.360><c> question</c><00:27:54.320><c> that</c><00:27:54.640><c> will</c><00:27:54.880><c> also</c><00:27:55.760><c> be</c>

you ask a question that will also be

you ask a question that will also be
generating<00:27:56.399><c> some</c><00:27:56.640><c> vector</c><00:27:57.120><c> we</c><00:27:57.279><c> want</c><00:27:57.440><c> to</c><00:27:57.520><c> make</c>

generating some vector we want to make

generating some vector we want to make
sure<00:27:57.760><c> that</c><00:27:57.919><c> these</c><00:27:58.240><c> vectors</c><00:27:58.720><c> are</c><00:27:59.120><c> compatible</c>

sure that these vectors are compatible

sure that these vectors are compatible
to<00:27:59.760><c> each</c><00:27:59.919><c> other</c><00:28:00.080><c> they</c><00:28:00.320><c> are</c><00:28:00.399><c> of</c><00:28:00.640><c> same</c><00:28:00.960><c> size</c><00:28:01.360><c> and</c>

to each other they are of same size and

to each other they are of same size and
that's<00:28:01.840><c> why</c><00:28:01.919><c> we</c><00:28:02.080><c> have</c><00:28:02.240><c> added</c><00:28:02.399><c> added</c><00:28:02.640><c> a</c><00:28:02.880><c> new</c>

that's why we have added added a new

that's why we have added added a new
projection<00:28:03.679><c> layer.</c><00:28:03.919><c> You</c><00:28:04.080><c> can</c><00:28:04.320><c> simply</c><00:28:04.960><c> think</c>

projection layer. You can simply think

projection layer. You can simply think
of<00:28:05.279><c> it</c><00:28:05.600><c> as</c><00:28:05.919><c> a</c><00:28:06.320><c> fully</c><00:28:06.640><c> connected</c><00:28:07.200><c> layer</c><00:28:08.159><c> and</c>

of it as a fully connected layer and

of it as a fully connected layer and
ultimately<00:28:10.080><c> you</c><00:28:10.320><c> will</c><00:28:10.559><c> have</c><00:28:10.799><c> a</c><00:28:11.039><c> standard</c>

ultimately you will have a standard

ultimately you will have a standard
transformer<00:28:12.320><c> and</c><00:28:12.559><c> then</c><00:28:12.720><c> you</c><00:28:12.880><c> will</c><00:28:13.039><c> get</c><00:28:13.200><c> the</c>

transformer and then you will get the

transformer and then you will get the
output<00:28:13.919><c> token.</c><00:28:14.559><c> Okay.</c><00:28:15.200><c> So</c>

output token. Okay. So

output token. Okay. So
now

now

now
if<00:28:19.279><c> you</c><00:28:19.520><c> think</c><00:28:19.679><c> about</c>

me<00:28:26.720><c> just</c><00:28:26.880><c> scroll</c><00:28:27.200><c> down.</c><00:28:27.520><c> Yeah.</c><00:28:28.240><c> So</c><00:28:28.399><c> if</c><00:28:28.640><c> you</c>

me just scroll down. Yeah. So if you

me just scroll down. Yeah. So if you
think<00:28:28.960><c> about</c><00:28:30.399><c> call</c><00:28:30.720><c> pal</c><00:28:31.120><c> when</c><00:28:31.279><c> you</c><00:28:31.440><c> give</c><00:28:31.600><c> an</c>

think about call pal when you give an

think about call pal when you give an
image

image

image
it<00:28:33.760><c> will</c><00:28:33.919><c> have</c><00:28:34.159><c> let's</c><00:28:34.320><c> say</c><00:28:34.480><c> in</c><00:28:34.720><c> this</c><00:28:34.799><c> case</c>

it will have let's say in this case

it will have let's say in this case
there<00:28:35.200><c> are</c><00:28:35.360><c> 15</c><00:28:36.159><c> uh</c><00:28:36.480><c> patches</c><00:28:37.600><c> just</c><00:28:38.000><c> think</c><00:28:38.240><c> of</c>

there are 15 uh patches just think of

there are 15 uh patches just think of
this<00:28:38.640><c> patch</c><00:28:39.120><c> okay</c><00:28:39.840><c> this</c><00:28:40.080><c> patch</c><00:28:40.559><c> will</c><00:28:40.880><c> go</c>

this patch okay this patch will go

this patch okay this patch will go
through<00:28:41.279><c> this</c><00:28:42.240><c> it</c><00:28:42.399><c> will</c><00:28:42.640><c> generate</c><00:28:42.960><c> an</c><00:28:44.000><c> uh</c>

through this it will generate an uh

through this it will generate an uh
vector<00:28:45.360><c> and</c><00:28:45.679><c> this</c><00:28:46.000><c> will</c><00:28:46.159><c> be</c><00:28:46.399><c> the</c><00:28:46.720><c> final</c>

vector and this will be the final

vector and this will be the final
representation<00:28:48.080><c> of</c><00:28:48.320><c> the</c><00:28:48.559><c> first</c><00:28:48.799><c> patch.</c>

representation of the first patch.

representation of the first patch.
Similarly<00:28:50.080><c> when</c><00:28:50.320><c> you</c><00:28:50.480><c> give</c><00:28:50.799><c> the</c><00:28:51.120><c> whole</c><00:28:51.360><c> image</c>

Similarly when you give the whole image

Similarly when you give the whole image
you<00:28:51.919><c> will</c><00:28:52.080><c> not</c><00:28:52.159><c> give</c><00:28:52.320><c> the</c><00:28:52.799><c> uh</c><00:28:52.960><c> you</c><00:28:53.120><c> know</c><00:28:53.600><c> single</c>

you will not give the uh you know single

you will not give the uh you know single
patch<00:28:55.279><c> uh</c><00:28:55.440><c> in</c><00:28:55.600><c> the</c><00:28:55.760><c> batch</c><00:28:56.480><c> you</c><00:28:56.640><c> will</c><00:28:56.799><c> give</c><00:28:57.200><c> give</c>

patch uh in the batch you will give give

patch uh in the batch you will give give
one<00:28:58.159><c> full</c><00:28:58.480><c> image</c><00:28:58.960><c> or</c><00:28:59.279><c> let's</c><00:28:59.440><c> say</c><00:28:59.600><c> page</c><00:28:59.919><c> number</c>

one full image or let's say page number

one full image or let's say page number
one<00:29:00.320><c> of</c><00:29:00.559><c> the</c><00:29:00.720><c> document</c><00:29:01.679><c> this</c><00:29:02.000><c> model</c><00:29:02.320><c> will</c><00:29:02.559><c> do</c>

one of the document this model will do

one of the document this model will do
all<00:29:03.200><c> that</c><00:29:03.520><c> patching</c><00:29:04.320><c> and</c><00:29:04.720><c> it</c><00:29:05.039><c> will</c><00:29:05.200><c> finally</c>

all that patching and it will finally

all that patching and it will finally
generate<00:29:06.000><c> one</c><00:29:06.320><c> embedding</c><00:29:06.880><c> vector.</c><00:29:07.840><c> Now</c><00:29:09.120><c> at</c>

generate one embedding vector. Now at

generate one embedding vector. Now at
the<00:29:09.600><c> time</c><00:29:09.840><c> of</c>

the time of

the time of
and<00:29:11.760><c> if</c><00:29:11.919><c> you</c><00:29:12.399><c> if</c><00:29:12.640><c> you</c><00:29:12.799><c> see</c><00:29:12.960><c> here</c><00:29:13.600><c> in</c><00:29:13.840><c> this</c><00:29:14.000><c> case</c>

and if you if you see here in this case

and if you if you see here in this case
this<00:29:14.399><c> is</c><00:29:14.480><c> grayed</c><00:29:14.799><c> out</c><00:29:15.520><c> because</c><00:29:16.480><c> now</c><00:29:16.720><c> we</c><00:29:16.960><c> are</c>

this is grayed out because now we are

this is grayed out because now we are
talking<00:29:17.360><c> about</c><00:29:17.679><c> after</c><00:29:18.080><c> training</c><00:29:18.399><c> once</c><00:29:18.720><c> that</c>

talking about after training once that

talking about after training once that
model<00:29:19.279><c> is</c><00:29:19.440><c> trained</c><00:29:20.159><c> after</c><00:29:20.480><c> training</c><00:29:21.200><c> you</c><00:29:21.440><c> will</c>

model is trained after training you will

model is trained after training you will
create<00:29:22.000><c> the</c><00:29:22.399><c> embeddings</c><00:29:22.960><c> of</c><00:29:23.120><c> your</c><00:29:23.360><c> document.</c>

create the embeddings of your document.

create the embeddings of your document.
So<00:29:24.240><c> while</c><00:29:24.399><c> you</c><00:29:24.559><c> are</c><00:29:24.720><c> creating</c><00:29:24.960><c> the</c><00:29:25.120><c> embeddings</c>

So while you are creating the embeddings

So while you are creating the embeddings
there<00:29:25.760><c> is</c><00:29:25.919><c> no</c><00:29:26.080><c> question</c><00:29:26.399><c> here</c><00:29:27.600><c> right.</c><00:29:28.240><c> So</c><00:29:28.399><c> it</c>

there is no question here right. So it

there is no question here right. So it
will<00:29:28.880><c> just</c><00:29:29.039><c> use</c><00:29:29.440><c> this</c><00:29:29.760><c> path.</c><00:29:30.799><c> Now</c><00:29:31.039><c> once</c><00:29:31.360><c> those</c>

will just use this path. Now once those

will just use this path. Now once those
embeddings<00:29:32.240><c> are</c><00:29:32.399><c> done</c><00:29:32.799><c> like</c><00:29:33.039><c> once</c><00:29:33.360><c> you</c><00:29:33.600><c> get</c>

embeddings are done like once you get

embeddings are done like once you get
all<00:29:33.840><c> these</c><00:29:34.080><c> final</c><00:29:34.399><c> vectors</c><00:29:34.880><c> for</c><00:29:35.279><c> your</c><00:29:35.600><c> entire</c>

all these final vectors for your entire

all these final vectors for your entire
document

in<00:29:39.679><c> the</c><00:29:39.919><c> query</c><00:29:40.320><c> time</c><00:29:41.520><c> you</c><00:29:41.840><c> will</c><00:29:42.000><c> just</c><00:29:42.399><c> use</c><00:29:43.279><c> your</c>

in the query time you will just use your

in the query time you will just use your
text<00:29:44.080><c> based</c><00:29:44.399><c> query.</c><00:29:45.279><c> So</c><00:29:45.760><c> call</c><00:29:46.080><c> pal</c><00:29:46.480><c> doesn't</c>

text based query. So call pal doesn't

text based query. So call pal doesn't
say<00:29:46.880><c> that</c><00:29:47.520><c> you</c><00:29:47.760><c> can</c><00:29:47.919><c> query</c><00:29:48.240><c> with</c><00:29:48.399><c> your</c><00:29:48.640><c> as</c><00:29:48.880><c> an</c>

say that you can query with your as an

say that you can query with your as an
image<00:29:49.760><c> like</c><00:29:49.919><c> in</c><00:29:50.080><c> chat</c><00:29:50.399><c> GPT</c><00:29:50.799><c> or</c><00:29:50.960><c> any</c><00:29:51.600><c> GPD</c><00:29:52.080><c> based</c>

image like in chat GPT or any GPD based

image like in chat GPT or any GPD based
model<00:29:52.480><c> you</c><00:29:52.720><c> just</c><00:29:52.880><c> upload</c><00:29:53.120><c> an</c><00:29:53.360><c> image.</c><00:29:53.840><c> We</c><00:29:54.000><c> are</c>

model you just upload an image. We are

model you just upload an image. We are
so<00:29:54.320><c> lazy</c><00:29:54.640><c> we</c><00:29:54.799><c> don't</c><00:29:54.960><c> even</c><00:29:55.120><c> ask</c><00:29:55.279><c> the</c><00:29:55.520><c> question</c>

so lazy we don't even ask the question

so lazy we don't even ask the question
these<00:29:55.919><c> days</c><00:29:56.159><c> right</c><00:29:56.240><c> we</c><00:29:56.480><c> just</c><00:29:56.559><c> upload</c><00:29:56.799><c> the</c>

these days right we just upload the

these days right we just upload the
image<00:29:57.200><c> and</c><00:29:57.679><c> you</c><00:29:57.840><c> know</c><00:29:58.000><c> model</c><00:29:58.320><c> just</c><00:29:58.480><c> generates</c>

image and you know model just generates

image and you know model just generates
something.<00:29:59.440><c> So</c><00:29:59.600><c> here</c><00:29:59.840><c> the</c><00:30:00.080><c> question</c><00:30:00.320><c> should</c>

something. So here the question should

something. So here the question should
be<00:30:00.640><c> always</c><00:30:00.880><c> in</c><00:30:01.120><c> text</c><00:30:01.520><c> that's</c><00:30:01.840><c> the</c>

be always in text that's the

be always in text that's the
prerequisite<00:30:02.880><c> for</c><00:30:03.120><c> this</c><00:30:03.279><c> model</c><00:30:04.720><c> and</c><00:30:05.600><c> then</c>

prerequisite for this model and then

prerequisite for this model and then
this<00:30:06.320><c> goes</c><00:30:06.640><c> through</c><00:30:07.039><c> the</c><00:30:07.360><c> same</c><00:30:07.919><c> uh</c><00:30:08.159><c> model</c><00:30:08.559><c> and</c>

this goes through the same uh model and

this goes through the same uh model and
then<00:30:09.360><c> it</c><00:30:09.679><c> finally</c><00:30:10.080><c> gives</c><00:30:10.320><c> you</c><00:30:10.480><c> an</c><00:30:10.799><c> response.</c>

then it finally gives you an response.

then it finally gives you an response.
Now<00:30:11.440><c> this</c><00:30:11.760><c> response</c><00:30:12.320><c> this</c><00:30:12.559><c> vector</c><00:30:13.279><c> you</c><00:30:13.520><c> will</c>

Now this response this vector you will

Now this response this vector you will
do<00:30:14.000><c> a</c><00:30:14.240><c> semantic</c><00:30:14.799><c> search</c><00:30:15.600><c> with</c><00:30:15.840><c> the</c><00:30:16.000><c> vectors</c>

do a semantic search with the vectors

do a semantic search with the vectors
that<00:30:16.559><c> you</c><00:30:16.799><c> have</c><00:30:17.039><c> stored</c><00:30:17.440><c> in</c><00:30:17.679><c> your</c><00:30:17.840><c> vector</c>

that you have stored in your vector

that you have stored in your vector
database<00:30:18.880><c> using</c><00:30:19.200><c> those</c><00:30:19.679><c> uh</c><00:30:19.840><c> image</c><00:30:20.159><c> patches</c>

database using those uh image patches

database using those uh image patches
with<00:30:22.320><c> me</c><00:30:22.480><c> so</c><00:30:22.720><c> far?</c><00:30:23.520><c> Yes.</c><00:30:23.919><c> Okay.</c><00:30:24.799><c> So</c><00:30:25.840><c> if</c><00:30:26.080><c> you</c>

with me so far? Yes. Okay. So if you

with me so far? Yes. Okay. So if you
think<00:30:26.480><c> about</c><00:30:26.640><c> it</c><00:30:27.840><c> uh</c>

think about it uh

think about it uh
both<00:30:29.840><c> for</c><00:30:30.080><c> query</c><00:30:30.720><c> as</c><00:30:30.960><c> well</c><00:30:31.039><c> as</c><00:30:31.520><c> uh</c><00:30:31.760><c> your</c>

both for query as well as uh your

both for query as well as uh your
embedding<00:30:32.799><c> there</c><00:30:32.960><c> is</c><00:30:33.120><c> a</c><00:30:33.360><c> certain</c><00:30:33.679><c> amount</c><00:30:34.000><c> of</c>

embedding there is a certain amount of

embedding there is a certain amount of
uh<00:30:35.360><c> uh</c><00:30:35.600><c> pre-processing</c><00:30:36.480><c> that</c><00:30:36.720><c> is</c><00:30:36.960><c> needed</c>

uh uh pre-processing that is needed

uh uh pre-processing that is needed
because<00:30:39.120><c> uh</c><00:30:39.279><c> your</c><00:30:39.679><c> images</c><00:30:40.240><c> can</c><00:30:40.399><c> be</c><00:30:40.559><c> of</c>

because uh your images can be of

because uh your images can be of
different<00:30:41.039><c> size</c><00:30:41.440><c> right</c><00:30:41.600><c> so</c><00:30:41.919><c> let's</c><00:30:42.080><c> say</c><00:30:42.240><c> you</c>

different size right so let's say you

different size right so let's say you
have<00:30:42.559><c> an</c><00:30:43.039><c> a</c><00:30:43.360><c> PDF</c><00:30:43.840><c> document</c><00:30:44.960><c> u</c><00:30:45.279><c> and</c>

have an a PDF document u and

have an a PDF document u and
the<00:30:47.200><c> tool</c><00:30:47.440><c> that</c><00:30:47.600><c> you</c><00:30:47.760><c> use</c><00:30:48.000><c> to</c><00:30:48.159><c> convert</c><00:30:48.480><c> that</c>

the tool that you use to convert that

the tool that you use to convert that
into<00:30:48.880><c> an</c><00:30:49.039><c> image</c><00:30:49.919><c> uh</c><00:30:50.240><c> it</c><00:30:50.559><c> created</c><00:30:50.880><c> an</c><00:30:51.120><c> image</c><00:30:51.279><c> of</c>

into an image uh it created an image of

into an image uh it created an image of
800<00:30:51.840><c> by</c><00:30:52.159><c> 800</c><00:30:52.559><c> but</c><00:30:52.880><c> let's</c><00:30:53.039><c> say</c><00:30:53.200><c> somebody</c><00:30:53.440><c> else</c>

800 by 800 but let's say somebody else

800 by 800 but let's say somebody else
have<00:30:53.919><c> used</c><00:30:54.399><c> another</c><00:30:55.120><c> technique</c><00:30:55.440><c> and</c><00:30:55.600><c> the</c>

have used another technique and the

have used another technique and the
image<00:30:56.159><c> was</c><00:30:56.480><c> of</c><00:30:57.120><c> 50</c><00:30:57.440><c> +</c><00:30:57.760><c> 50.</c><00:30:58.080><c> So</c><00:30:58.240><c> we</c><00:30:58.480><c> need</c><00:30:58.559><c> to</c><00:30:58.720><c> make</c>

image was of 50 + 50. So we need to make

image was of 50 + 50. So we need to make
sure<00:30:58.960><c> that</c><00:30:59.520><c> the</c><00:30:59.760><c> images</c><00:31:00.159><c> are</c><00:31:00.320><c> of</c><00:31:00.559><c> standard</c>

sure that the images are of standard

sure that the images are of standard
size,<00:31:01.360><c> right?</c><00:31:01.600><c> So</c><00:31:01.760><c> that's</c><00:31:02.000><c> why</c><00:31:02.320><c> when</c><00:31:02.559><c> we</c><00:31:02.720><c> look</c>

size, right? So that's why when we look

size, right? So that's why when we look
into<00:31:03.039><c> the</c><00:31:03.279><c> code</c><00:31:03.520><c> next,</c><00:31:03.840><c> you</c><00:31:04.080><c> will</c><00:31:04.240><c> see</c><00:31:04.320><c> that</c>

into the code next, you will see that

into the code next, you will see that
always<00:31:06.640><c> before</c><00:31:06.960><c> it</c><00:31:07.200><c> actually</c><00:31:07.520><c> generates</c><00:31:07.840><c> the</c>

always before it actually generates the

always before it actually generates the
embedding,<00:31:08.480><c> there</c><00:31:08.559><c> is</c><00:31:08.640><c> a</c><00:31:08.799><c> pre-processing</c><00:31:09.840><c> uh</c>

embedding, there is a pre-processing uh

embedding, there is a pre-processing uh
that<00:31:10.320><c> we</c><00:31:10.480><c> do.</c><00:31:11.360><c> Okay.</c><00:31:12.640><c> So</c><00:31:13.120><c> let's</c><00:31:13.679><c> uh</c><00:31:14.320><c> go</c><00:31:14.559><c> to</c><00:31:14.720><c> the</c>

that we do. Okay. So let's uh go to the

that we do. Okay. So let's uh go to the
code<00:31:15.279><c> and</c><00:31:15.840><c> see</c><00:31:16.000><c> that.</c><00:31:16.559><c> But</c><00:31:16.799><c> before</c><00:31:16.960><c> that</c><00:31:17.279><c> let's</c>

code and see that. But before that let's

code and see that. But before that let's
uh<00:31:17.919><c> let's</c><00:31:19.360><c> share</c><00:31:19.679><c> I</c><00:31:19.919><c> mean</c><00:31:20.240><c> let's</c><00:31:20.559><c> talk</c><00:31:20.720><c> about</c>

uh let's share I mean let's talk about

uh let's share I mean let's talk about
how<00:31:21.600><c> it</c><00:31:21.840><c> generates</c><00:31:22.640><c> uh</c><00:31:22.720><c> the</c><00:31:23.760><c> similar</c><00:31:24.240><c> chunks.</c>

how it generates uh the similar chunks.

how it generates uh the similar chunks.
So<00:31:25.520><c> this</c><00:31:25.679><c> is</c><00:31:25.760><c> the</c><00:31:26.000><c> most</c><00:31:26.240><c> important</c><00:31:26.559><c> part</c><00:31:26.720><c> of</c>

So this is the most important part of

So this is the most important part of
call<00:31:27.279><c> pali.</c><00:31:28.000><c> Okay.</c><00:31:28.720><c> Now</c><00:31:29.039><c> imagine</c><00:31:30.399><c> that</c>

call pali. Okay. Now imagine that

call pali. Okay. Now imagine that
your<00:31:32.320><c> page</c><00:31:32.720><c> now</c><00:31:32.960><c> just</c><00:31:33.200><c> consider</c><00:31:33.679><c> page</c><00:31:34.000><c> number</c>

your page now just consider page number

your page now just consider page number
one<00:31:34.399><c> of</c><00:31:34.640><c> your</c><00:31:34.799><c> document</c><00:31:36.080><c> and</c><00:31:36.399><c> the</c><00:31:36.640><c> page</c>

one of your document and the page

one of your document and the page
and<00:31:38.559><c> the</c><00:31:39.039><c> patch</c><00:31:39.360><c> size</c><00:31:39.519><c> that</c><00:31:39.760><c> you</c><00:31:39.919><c> use</c><00:31:40.159><c> is</c><00:31:40.399><c> let's</c>

and the patch size that you use is let's

and the patch size that you use is let's
say<00:31:40.880><c> 2</c><00:31:41.120><c> +2</c><00:31:41.519><c> that</c><00:31:41.760><c> is</c><00:31:41.919><c> total</c><00:31:42.240><c> four</c><00:31:42.559><c> patches.</c>

say 2 +2 that is total four patches.

say 2 +2 that is total four patches.
Okay.<00:31:44.159><c> Now</c><00:31:44.320><c> let's</c><00:31:44.559><c> say</c><00:31:44.720><c> this</c><00:31:44.799><c> is</c><00:31:44.960><c> page</c><00:31:45.279><c> number</c>

Okay. Now let's say this is page number

Okay. Now let's say this is page number
one<00:31:46.399><c> and</c><00:31:47.200><c> this</c><00:31:47.440><c> is</c><00:31:47.600><c> the</c><00:31:48.720><c> embedding</c><00:31:49.440><c> of</c><00:31:50.640><c> your</c><00:31:51.039><c> f</c>

one and this is the embedding of your f

one and this is the embedding of your f
uh<00:31:52.000><c> first</c><00:31:52.320><c> patch.</c><00:31:53.200><c> This</c><00:31:53.360><c> is</c><00:31:53.440><c> the</c><00:31:53.519><c> embedding</c><00:31:53.919><c> of</c>

uh first patch. This is the embedding of

uh first patch. This is the embedding of
the<00:31:54.159><c> second</c><00:31:54.399><c> patch.</c><00:31:54.720><c> This</c><00:31:54.799><c> is</c><00:31:54.880><c> the</c><00:31:54.960><c> embedding</c>

the second patch. This is the embedding

the second patch. This is the embedding
of<00:31:55.440><c> third</c><00:31:55.600><c> patch.</c><00:31:55.919><c> This</c><00:31:56.000><c> is</c><00:31:56.080><c> the</c><00:31:56.240><c> embedding</c><00:31:56.559><c> of</c>

of third patch. This is the embedding of

of third patch. This is the embedding of
the<00:31:56.799><c> fourth</c><00:31:57.120><c> patch.</c><00:31:58.080><c> Okay.</c>

the fourth patch. Okay.

the fourth patch. Okay.
And<00:32:01.360><c> you</c><00:32:01.600><c> ask</c><00:32:01.919><c> some</c><00:32:02.159><c> question.</c><00:32:03.120><c> Let's</c><00:32:03.440><c> say</c><00:32:04.399><c> uh</c>

And you ask some question. Let's say uh

And you ask some question. Let's say uh
what<00:32:05.360><c> is</c><00:32:05.679><c> AI?</c><00:32:06.159><c> Just</c><00:32:06.399><c> for</c><00:32:06.640><c> the</c><00:32:06.799><c> sake</c><00:32:06.960><c> of</c>

what is AI? Just for the sake of

what is AI? Just for the sake of
simplicity<00:32:08.000><c> what</c><00:32:08.320><c> is</c><00:32:08.559><c> AI?</c><00:32:09.360><c> And</c><00:32:09.600><c> you</c><00:32:09.760><c> have</c><00:32:09.919><c> used</c>

simplicity what is AI? And you have used

simplicity what is AI? And you have used
through<00:32:10.640><c> uh</c><00:32:10.720><c> it</c><00:32:10.960><c> went</c><00:32:11.120><c> through</c><00:32:11.279><c> the</c><00:32:11.360><c> tokenizer</c>

through uh it went through the tokenizer

through uh it went through the tokenizer
and<00:32:12.640><c> it</c><00:32:12.880><c> generated</c><00:32:13.360><c> three</c><00:32:13.840><c> embedding</c><00:32:14.320><c> vectors</c>

and it generated three embedding vectors

and it generated three embedding vectors
right<00:32:15.120><c> three</c><00:32:15.519><c> tokens</c><00:32:16.080><c> basically.</c><00:32:17.279><c> So</c><00:32:17.440><c> now</c>

right three tokens basically. So now

right three tokens basically. So now
what<00:32:17.919><c> we</c><00:32:18.159><c> do</c><00:32:18.320><c> is</c><00:32:19.440><c> we</c><00:32:19.840><c> do</c><00:32:20.159><c> a</c><00:32:20.480><c> dot</c><00:32:20.799><c> product</c>

what we do is we do a dot product

what we do is we do a dot product
between<00:32:21.919><c> each</c><00:32:22.240><c> vector</c><00:32:22.960><c> and</c><00:32:23.360><c> each</c><00:32:23.840><c> vector</c><00:32:24.320><c> of</c>

between each vector and each vector of

between each vector and each vector of
all<00:32:25.200><c> the</c><00:32:25.360><c> patches.</c>

all the patches.

all the patches.
Okay.

Okay.

Okay.
And<00:32:28.799><c> then</c>

And then

And then
for<00:32:31.039><c> every</c><00:32:31.760><c> row</c><00:32:32.000><c> we</c><00:32:32.159><c> try</c><00:32:32.399><c> to</c><00:32:32.559><c> find</c><00:32:33.120><c> which</c><00:32:33.360><c> is</c>

for every row we try to find which is

for every row we try to find which is
the<00:32:33.679><c> maximum</c><00:32:34.159><c> number.</c><00:32:35.519><c> What</c><00:32:35.760><c> this</c><00:32:36.000><c> number</c>

the maximum number. What this number

the maximum number. What this number
signifies?<00:32:37.120><c> This</c><00:32:37.440><c> 89</c><00:32:38.000><c> signifies</c><00:32:38.960><c> 89</c>

signifies? This 89 signifies 89

signifies? This 89 signifies 89
signifies<00:32:39.919><c> that</c><00:32:40.159><c> the</c><00:32:41.200><c> first</c><00:32:41.600><c> part</c><00:32:41.840><c> of</c><00:32:42.080><c> your</c>

signifies that the first part of your

signifies that the first part of your
question<00:32:43.519><c> has</c><00:32:43.760><c> the</c><00:32:44.080><c> maximum</c><00:32:44.640><c> similarity</c><00:32:45.519><c> with</c>

question has the maximum similarity with

question has the maximum similarity with
the<00:32:46.080><c> second</c><00:32:46.399><c> patch</c><00:32:46.799><c> of</c><00:32:47.039><c> the</c><00:32:47.279><c> image.</c>

the second patch of the image.

the second patch of the image.
Right?<00:32:50.080><c> Similarly,</c><00:32:50.720><c> if</c><00:32:50.960><c> this</c><00:32:51.120><c> is</c><00:32:51.360><c> 97,</c><00:32:52.000><c> that</c>

Right? Similarly, if this is 97, that

Right? Similarly, if this is 97, that
means<00:32:53.120><c> the</c><00:32:53.840><c> second</c><00:32:54.159><c> part</c><00:32:54.399><c> of</c><00:32:54.640><c> your</c><00:32:54.880><c> question</c>

means the second part of your question

means the second part of your question
has<00:32:55.519><c> the</c><00:32:55.760><c> maximum</c><00:32:56.240><c> similarity</c><00:32:57.279><c> with</c><00:32:57.600><c> the</c>

has the maximum similarity with the

has the maximum similarity with the
third<00:32:58.640><c> patch</c><00:32:58.960><c> of</c><00:32:59.200><c> your</c><00:32:59.440><c> image.</c>

third patch of your image.

third patch of your image.
Right?

Right?

Right?
And<00:33:02.880><c> at</c><00:33:03.120><c> the</c><00:33:03.200><c> end</c><00:33:03.440><c> what</c><00:33:03.679><c> we</c><00:33:03.840><c> do</c><00:33:03.919><c> is</c><00:33:04.159><c> we</c><00:33:04.399><c> just</c>

And at the end what we do is we just

And at the end what we do is we just
take<00:33:04.720><c> the</c><00:33:05.919><c> addition</c><00:33:06.399><c> I</c><00:33:06.559><c> mean</c><00:33:06.640><c> we</c><00:33:06.880><c> just</c><00:33:07.039><c> take</c><00:33:07.200><c> a</c>

take the addition I mean we just take a

take the addition I mean we just take a
sum<00:33:07.679><c> the</c><00:33:08.000><c> maximum</c><00:33:08.480><c> numbers</c><00:33:08.799><c> of</c><00:33:08.960><c> each</c><00:33:09.440><c> rows</c><00:33:10.159><c> and</c>

sum the maximum numbers of each rows and

sum the maximum numbers of each rows and
if<00:33:10.720><c> let's</c><00:33:10.960><c> say</c><00:33:11.120><c> that</c><00:33:11.360><c> is</c><00:33:11.519><c> 2.58</c><00:33:12.559><c> that</c><00:33:12.799><c> means</c>

if let's say that is 2.58 that means

if let's say that is 2.58 that means
this<00:33:15.039><c> query</c><00:33:16.000><c> has</c><00:33:16.240><c> a</c><00:33:16.480><c> score</c><00:33:16.640><c> of</c><00:33:16.880><c> 2.58</c><00:33:17.919><c> for</c><00:33:18.159><c> page</c>

this query has a score of 2.58 for page

this query has a score of 2.58 for page
number<00:33:18.720><c> one.</c><00:33:20.159><c> Similarly</c><00:33:20.720><c> we</c><00:33:20.960><c> will</c><00:33:21.120><c> do</c><00:33:21.200><c> it</c><00:33:21.519><c> for</c>

number one. Similarly we will do it for

number one. Similarly we will do it for
all<00:33:22.000><c> the</c><00:33:22.159><c> pages</c><00:33:23.200><c> and</c><00:33:23.440><c> then</c><00:33:23.679><c> in</c><00:33:23.919><c> rag</c><00:33:24.240><c> what</c><00:33:24.399><c> we</c><00:33:24.559><c> do</c>

all the pages and then in rag what we do

all the pages and then in rag what we do
at<00:33:24.799><c> the</c><00:33:24.880><c> end</c><00:33:25.039><c> when</c><00:33:25.279><c> we</c><00:33:25.360><c> do</c><00:33:25.519><c> a</c><00:33:25.679><c> semantic</c><00:33:26.080><c> search</c>

at the end when we do a semantic search

at the end when we do a semantic search
we<00:33:26.480><c> say</c><00:33:26.880><c> top</c><00:33:27.279><c> five</c><00:33:27.600><c> chunks</c><00:33:28.000><c> or</c><00:33:28.240><c> top</c><00:33:28.480><c> 10</c><00:33:28.720><c> chunks.</c>

we say top five chunks or top 10 chunks.

we say top five chunks or top 10 chunks.
So<00:33:29.679><c> in</c><00:33:29.919><c> this</c><00:33:30.080><c> case</c><00:33:30.399><c> chunk</c><00:33:30.720><c> is</c><00:33:30.880><c> nothing</c><00:33:31.120><c> but</c>

So in this case chunk is nothing but

So in this case chunk is nothing but
pages.<00:33:32.159><c> So</c><00:33:32.320><c> if</c><00:33:32.559><c> I</c><00:33:32.720><c> say</c><00:33:32.960><c> top</c><00:33:33.279><c> five</c><00:33:33.840><c> then</c><00:33:34.080><c> in</c><00:33:34.240><c> that</c>

pages. So if I say top five then in that

pages. So if I say top five then in that
case<00:33:34.559><c> it</c><00:33:34.799><c> will</c><00:33:35.039><c> show</c><00:33:35.200><c> us</c><00:33:35.760><c> the</c><00:33:36.000><c> top</c><00:33:36.320><c> five</c><00:33:36.640><c> pages</c>

case it will show us the top five pages

case it will show us the top five pages
based<00:33:37.840><c> on</c><00:33:38.080><c> this</c><00:33:38.640><c> score.</c>

based on this score.

based on this score.
Getting<00:33:40.799><c> it.</c><00:33:41.519><c> So</c><00:33:41.919><c> this</c><00:33:42.240><c> is</c><00:33:42.320><c> the</c><00:33:42.640><c> most</c>

Getting it. So this is the most

Getting it. So this is the most
important<00:33:43.120><c> thing.</c><00:33:43.360><c> So</c><00:33:43.519><c> this</c><00:33:43.679><c> is</c><00:33:43.840><c> called</c><00:33:44.240><c> late</c>

important thing. So this is called late

important thing. So this is called late
interaction.<00:33:45.840><c> Have</c><00:33:46.000><c> you</c><00:33:46.080><c> heard</c><00:33:46.240><c> of</c><00:33:46.399><c> late</c>

interaction. Have you heard of late

interaction. Have you heard of late
interaction<00:33:47.120><c> embeddings</c><00:33:48.240><c> all</c><00:33:48.480><c> that?</c><00:33:48.799><c> And</c><00:33:49.039><c> the</c>

interaction embeddings all that? And the

interaction embeddings all that? And the
reason<00:33:49.440><c> that</c><00:33:49.600><c> we</c><00:33:49.760><c> say</c><00:33:50.000><c> late</c><00:33:50.240><c> interaction</c><00:33:50.640><c> is</c>

reason that we say late interaction is

reason that we say late interaction is
because<00:33:51.760><c> these</c><00:33:52.080><c> token</c><00:33:52.399><c> embeddings</c><00:33:52.880><c> are</c>

because these token embeddings are

because these token embeddings are
already<00:33:53.360><c> stored.</c><00:33:54.240><c> We</c><00:33:54.480><c> have</c><00:33:54.640><c> already</c><00:33:54.960><c> done</c>

already stored. We have already done

already stored. We have already done
that.<00:33:55.679><c> It's</c><00:33:55.919><c> there</c><00:33:56.080><c> in</c><00:33:56.240><c> your</c><00:33:56.320><c> vector</c>

that. It's there in your vector

that. It's there in your vector
database.<00:33:57.440><c> All</c><00:33:57.679><c> we</c><00:33:57.840><c> have</c><00:33:58.000><c> to</c><00:33:58.080><c> do</c><00:33:58.240><c> is</c><00:33:58.559><c> we</c><00:33:58.799><c> need</c>

database. All we have to do is we need

database. All we have to do is we need
to<00:33:59.039><c> just</c><00:33:59.200><c> do</c><00:33:59.279><c> the</c><00:33:59.440><c> dot</c><00:33:59.679><c> product</c><00:34:00.240><c> and</c><00:34:00.480><c> then</c><00:34:00.720><c> use</c>

to just do the dot product and then use

to just do the dot product and then use
this<00:34:01.200><c> metrics</c><00:34:02.000><c> to</c><00:34:02.240><c> generate</c><00:34:02.640><c> the</c><00:34:03.120><c> top</c><00:34:03.360><c> five</c><00:34:03.600><c> or</c>

this metrics to generate the top five or

this metrics to generate the top five or
top<00:34:04.159><c> three</c><00:34:04.640><c> uh</c><00:34:04.799><c> pages.</c><00:34:06.000><c> Okay.</c>

top three uh pages. Okay.

top three uh pages. Okay.
Uh<00:34:08.960><c> with</c><00:34:09.119><c> me</c><00:34:09.359><c> so</c><00:34:09.520><c> far?</c><00:34:10.480><c> Yes.</c><00:34:10.879><c> Okay.</c><00:34:11.440><c> Now</c><00:34:11.839><c> this</c>

Uh with me so far? Yes. Okay. Now this

Uh with me so far? Yes. Okay. Now this
functionality<00:34:12.720><c> is</c><00:34:12.879><c> not</c><00:34:13.119><c> supported</c><00:34:13.599><c> in</c><00:34:14.240><c> all</c>

functionality is not supported in all

functionality is not supported in all
the<00:34:14.879><c> all</c><00:34:15.040><c> the</c><00:34:15.200><c> vector</c><00:34:15.520><c> databases.</c><00:34:16.480><c> We</c><00:34:16.720><c> are</c>

the all the vector databases. We are

the all the vector databases. We are
going<00:34:16.879><c> to</c><00:34:17.040><c> use</c><00:34:17.359><c> one</c><00:34:17.520><c> of</c><00:34:17.599><c> the</c><00:34:17.679><c> vector</c><00:34:18.399><c> database</c>

going to use one of the vector database

going to use one of the vector database
called<00:34:19.119><c> quadrant.</c><00:34:19.919><c> Have</c><00:34:20.079><c> you</c><00:34:20.159><c> heard</c><00:34:20.320><c> of</c><00:34:20.480><c> that?</c>

called quadrant. Have you heard of that?

called quadrant. Have you heard of that?
But<00:34:21.520><c> there</c><00:34:21.760><c> are</c><00:34:21.919><c> few</c><00:34:22.079><c> other</c><00:34:22.240><c> databases.</c><00:34:22.800><c> I</c>

But there are few other databases. I

But there are few other databases. I
have<00:34:23.040><c> not</c><00:34:23.200><c> done</c><00:34:23.520><c> enough</c><00:34:23.839><c> research</c><00:34:24.240><c> which</c><00:34:24.399><c> are</c>

have not done enough research which are

have not done enough research which are
the<00:34:24.639><c> databases</c><00:34:25.040><c> that</c><00:34:25.200><c> it</c><00:34:25.440><c> supports.</c><00:34:26.320><c> uh</c><00:34:26.480><c> but</c>

the databases that it supports. uh but

the databases that it supports. uh but
this<00:34:27.599><c> u</c><00:34:28.240><c> maxim</c><00:34:29.040><c> calculation</c><00:34:29.520><c> is</c><00:34:29.760><c> not</c>

this u maxim calculation is not

this u maxim calculation is not
supported<00:34:30.320><c> by</c><00:34:30.639><c> all</c><00:34:30.800><c> the</c><00:34:31.040><c> database</c><00:34:31.839><c> okay</c><00:34:32.079><c> there</c>

supported by all the database okay there

supported by all the database okay there
are<00:34:32.320><c> some</c><00:34:32.480><c> open</c><00:34:32.720><c> source</c><00:34:32.960><c> contribution</c><00:34:33.440><c> that</c>

are some open source contribution that

are some open source contribution that
we<00:34:33.839><c> have</c><00:34:34.240><c> for</c><00:34:34.639><c> few</c><00:34:34.800><c> of</c><00:34:34.879><c> the</c><00:34:35.040><c> vector</c><00:34:35.359><c> databases</c>

we have for few of the vector databases

we have for few of the vector databases
I<00:34:36.159><c> I</c><00:34:36.320><c> I</c><00:34:36.320><c> I</c><00:34:36.720><c> tried</c><00:34:37.040><c> with</c><00:34:37.520><c> open</c><00:34:37.839><c> search</c><00:34:38.639><c> u</c><00:34:38.800><c> it</c><00:34:39.040><c> did</c>

I I I I tried with open search u it did

I I I I tried with open search u it did
not<00:34:39.280><c> have</c><00:34:39.440><c> but</c><00:34:39.679><c> I</c><00:34:39.839><c> think</c><00:34:39.919><c> there</c><00:34:40.079><c> is</c><00:34:40.240><c> a</c>

not have but I think there is a

not have but I think there is a
extension<00:34:41.599><c> uh</c><00:34:41.760><c> which</c><00:34:42.000><c> you</c><00:34:42.240><c> can</c><00:34:42.399><c> use</c><00:34:43.040><c> to</c><00:34:43.359><c> make</c>

extension uh which you can use to make

extension uh which you can use to make
this<00:34:43.839><c> functionality</c><00:34:44.800><c> okay</c><00:34:45.440><c> so</c><00:34:45.679><c> now</c><00:34:45.839><c> we</c><00:34:46.079><c> are</c>

this functionality okay so now we are

this functionality okay so now we are
going<00:34:46.399><c> to</c><00:34:46.639><c> get</c><00:34:46.800><c> into</c>

going to get into

going to get into
uh<00:34:48.720><c> the</c><00:34:48.960><c> demo</c><00:34:49.679><c> so</c><00:34:50.159><c> just</c><00:34:50.399><c> like</c><00:34:50.720><c> what</c><00:34:50.960><c> I</c><00:34:51.119><c> said</c>

uh the demo so just like what I said

uh the demo so just like what I said
once<00:34:52.000><c> you</c><00:34:52.320><c> have</c><00:34:52.560><c> those</c><00:34:53.599><c> uh</c><00:34:54.079><c> scores</c><00:34:54.800><c> like</c><00:34:54.960><c> in</c>

once you have those uh scores like in

once you have those uh scores like in
this<00:34:55.280><c> case</c><00:34:55.599><c> 2.58</c><00:34:56.800><c> uh</c><00:34:56.960><c> like</c><00:34:57.200><c> this</c><00:34:57.359><c> you</c><00:34:57.599><c> will</c>

this case 2.58 uh like this you will

this case 2.58 uh like this you will
have<00:34:57.920><c> for</c><00:34:58.240><c> all</c><00:34:58.480><c> the</c><00:34:58.720><c> pages</c><00:34:59.040><c> in</c><00:34:59.280><c> your</c><00:34:59.520><c> document</c>

have for all the pages in your document

have for all the pages in your document
and<00:35:00.560><c> then</c><00:35:00.800><c> at</c><00:35:01.040><c> the</c><00:35:01.119><c> end</c><00:35:01.599><c> you</c><00:35:01.839><c> can</c><00:35:01.920><c> pick</c><00:35:02.079><c> the</c><00:35:02.320><c> top</c>

and then at the end you can pick the top

and then at the end you can pick the top
three<00:35:02.720><c> or</c><00:35:02.960><c> top</c><00:35:03.200><c> four</c><00:35:03.440><c> pages</c><00:35:03.839><c> of</c><00:35:04.079><c> your</c><00:35:04.240><c> choice.</c>

three or top four pages of your choice.

three or top four pages of your choice.
Okay.

Okay.

Okay.
So<00:35:07.040><c> now</c><00:35:07.680><c> see</c><00:35:07.920><c> this</c><00:35:08.320><c> so</c><00:35:08.560><c> far</c><00:35:08.800><c> we</c><00:35:09.040><c> are</c><00:35:09.119><c> not</c>

So now see this so far we are not

So now see this so far we are not
talking<00:35:09.440><c> about</c><00:35:09.599><c> agents.</c><00:35:10.079><c> Okay.</c><00:35:10.320><c> Because</c>

talking about agents. Okay. Because

talking about agents. Okay. Because
that's<00:35:10.800><c> a</c><00:35:10.960><c> very</c><00:35:11.200><c> simple</c><00:35:11.359><c> task.</c><00:35:11.680><c> Uh</c><00:35:11.920><c> we</c><00:35:12.160><c> will</c>

that's a very simple task. Uh we will

that's a very simple task. Uh we will
just<00:35:12.560><c> wrap</c><00:35:12.800><c> this</c><00:35:13.200><c> with</c><00:35:13.359><c> an</c><00:35:13.520><c> agent</c><00:35:13.839><c> at</c><00:35:14.079><c> later</c>

just wrap this with an agent at later

just wrap this with an agent at later
point<00:35:14.480><c> in</c><00:35:14.720><c> time.</c>

point in time.

point in time.
All<00:35:16.720><c> right.</c><00:35:17.520><c> So</c><00:35:18.880><c> let's</c><00:35:19.119><c> try</c><00:35:19.280><c> to</c><00:35:19.520><c> do</c><00:35:19.599><c> this.</c>

All right. So let's try to do this.

All right. So let's try to do this.
Okay.<00:35:20.400><c> So</c><00:35:20.560><c> this</c><00:35:20.720><c> is</c><00:35:20.880><c> an</c><00:35:21.280><c> uh</c><00:35:22.240><c> uh</c><00:35:22.400><c> I</c><00:35:22.720><c> I'll</c><00:35:22.960><c> just</c>

Okay. So this is an uh uh I I'll just

Okay. So this is an uh uh I I'll just
come<00:35:23.280><c> to</c><00:35:23.440><c> this</c><00:35:23.760><c> uh</c><00:35:23.920><c> image</c><00:35:24.320><c> later</c><00:35:24.560><c> on.</c><00:35:25.440><c> So</c><00:35:25.680><c> now</c>

come to this uh image later on. So now

come to this uh image later on. So now
let<00:35:26.079><c> me</c><00:35:26.240><c> just</c><00:35:26.560><c> increase</c><00:35:27.200><c> uh</c><00:35:28.560><c> the</c><00:35:28.800><c> font.</c><00:35:29.119><c> Can</c>

let me just increase uh the font. Can

let me just increase uh the font. Can
you<00:35:29.440><c> see</c><00:35:29.520><c> this?</c><00:35:30.560><c> Yeah.</c><00:35:30.880><c> Okay.</c><00:35:31.280><c> You</c><00:35:31.520><c> don't</c><00:35:31.599><c> have</c>

you see this? Yeah. Okay. You don't have

you see this? Yeah. Okay. You don't have
to<00:35:31.839><c> read</c><00:35:32.000><c> all</c><00:35:32.160><c> that</c><00:35:32.320><c> but</c><00:35:32.560><c> just</c><00:35:32.880><c> uh</c><00:35:33.119><c> you</c><00:35:33.280><c> should</c>

to read all that but just uh you should

to read all that but just uh you should
have<00:35:33.599><c> an</c><00:35:33.760><c> idea</c><00:35:34.000><c> what</c><00:35:34.560><c> we</c><00:35:34.800><c> are</c><00:35:34.960><c> doing.</c><00:35:35.760><c> So</c><00:35:35.920><c> first</c>

have an idea what we are doing. So first

have an idea what we are doing. So first
we<00:35:36.320><c> are</c><00:35:36.480><c> just</c><00:35:36.560><c> importing</c><00:35:36.960><c> few</c><00:35:37.119><c> of</c><00:35:37.200><c> the</c>

we are just importing few of the

we are just importing few of the
libraries.<00:35:37.839><c> Uh</c><00:35:38.079><c> I</c><00:35:38.240><c> have</c><00:35:38.400><c> no</c><00:35:38.560><c> idea</c><00:35:38.720><c> what</c><00:35:38.960><c> I</c><00:35:39.040><c> have</c>

libraries. Uh I have no idea what I have

libraries. Uh I have no idea what I have
importing<00:35:39.520><c> but</c><00:35:39.920><c> uh</c><00:35:40.240><c> there</c><00:35:40.560><c> are</c><00:35:40.800><c> few</c><00:35:41.200><c> right.</c><00:35:41.520><c> So</c>

importing but uh there are few right. So

importing but uh there are few right. So
I<00:35:41.760><c> think</c><00:35:41.920><c> it's</c><00:35:42.240><c> uh</c><00:35:42.400><c> where</c><00:35:42.560><c> is</c><00:35:42.640><c> the</c><00:35:42.800><c> call</c><00:35:42.960><c> pal?</c>

I think it's uh where is the call pal?

I think it's uh where is the call pal?
Yeah.<00:35:43.520><c> So</c><00:35:43.680><c> this</c><00:35:43.839><c> is</c><00:35:43.920><c> the</c><00:35:44.079><c> call</c><00:35:44.320><c> pali</c><00:35:44.640><c> model</c>

Yeah. So this is the call pali model

Yeah. So this is the call pali model
that<00:35:45.040><c> we</c><00:35:45.200><c> have.</c><00:35:46.160><c> Okay.</c><00:35:47.280><c> And</c><00:35:47.599><c> this</c><00:35:47.839><c> is</c><00:35:48.000><c> the</c>

that we have. Okay. And this is the

that we have. Okay. And this is the
quadrant<00:35:49.040><c> database</c><00:35:49.680><c> and</c><00:35:49.920><c> this</c><00:35:50.079><c> quadrant</c>

quadrant database and this quadrant

quadrant database and this quadrant
database<00:35:50.880><c> we</c><00:35:51.119><c> are</c><00:35:51.200><c> going</c><00:35:51.280><c> to</c><00:35:51.440><c> run</c><00:35:51.839><c> locally</c><00:35:52.400><c> in</c>

database we are going to run locally in

database we are going to run locally in
a<00:35:52.800><c> docker</c><00:35:53.200><c> container.</c><00:35:54.640><c> Okay.</c><00:35:55.119><c> So</c><00:35:55.520><c> if</c><00:35:55.680><c> you</c><00:35:55.839><c> are</c>

a docker container. Okay. So if you are

a docker container. Okay. So if you are
planning<00:35:56.160><c> to</c><00:35:56.320><c> run</c><00:35:56.480><c> this</c><00:35:57.040><c> uh</c><00:35:57.440><c> make</c><00:35:57.599><c> sure</c><00:35:57.680><c> that</c>

planning to run this uh make sure that

planning to run this uh make sure that
you<00:35:58.079><c> have</c><00:35:58.160><c> docker</c><00:35:58.560><c> installed</c><00:35:58.960><c> in</c><00:35:59.119><c> your</c><00:36:00.079><c> uh</c><00:36:00.480><c> in</c>

you have docker installed in your uh in

you have docker installed in your uh in
your<00:36:00.880><c> laptop.</c><00:36:01.280><c> Okay.</c><00:36:01.520><c> I</c><00:36:01.680><c> I</c><00:36:01.760><c> I</c><00:36:02.000><c> think</c><00:36:02.079><c> the</c>

your laptop. Okay. I I I think the

your laptop. Okay. I I I think the
readme<00:36:02.720><c> have</c><00:36:02.960><c> all</c><00:36:03.119><c> the</c><00:36:03.280><c> information.</c>

readme have all the information.

readme have all the information.
Okay.<00:36:06.800><c> Uh</c><00:36:07.359><c> so</c><00:36:07.680><c> first</c><00:36:08.240><c> we</c><00:36:08.480><c> need</c><00:36:08.720><c> some</c>

Okay. Uh so first we need some

Okay. Uh so first we need some
data.<00:36:11.200><c> So</c><00:36:11.359><c> I</c><00:36:11.680><c> have</c><00:36:11.839><c> used</c><00:36:12.320><c> one</c><00:36:12.720><c> data</c><00:36:13.040><c> set</c>

data. So I have used one data set

data. So I have used one data set
basically<00:36:14.560><c> it's</c><00:36:14.720><c> a</c><00:36:14.960><c> small</c><00:36:15.200><c> textbook</c><00:36:16.480><c> and</c><00:36:16.800><c> if</c>

basically it's a small textbook and if

basically it's a small textbook and if
you<00:36:17.200><c> see</c><00:36:17.359><c> this</c><00:36:17.599><c> textbook</c><00:36:18.320><c> uh</c><00:36:18.480><c> this</c><00:36:18.640><c> is</c><00:36:18.720><c> a</c>

you see this textbook uh this is a

you see this textbook uh this is a
science<00:36:19.359><c> textbook</c>

science textbook

science textbook
uh<00:36:21.040><c> chapter</c><00:36:21.440><c> number</c><00:36:21.680><c> 13.</c><00:36:22.160><c> So</c><00:36:23.440><c> we</c><00:36:23.760><c> have</c><00:36:24.079><c> let's</c>

uh chapter number 13. So we have let's

uh chapter number 13. So we have let's
say<00:36:25.040><c> see</c><00:36:25.440><c> one</c><00:36:25.680><c> of</c><00:36:25.760><c> the</c><00:36:25.839><c> thing</c><00:36:26.000><c> that</c><00:36:26.400><c> uh</c><00:36:26.960><c> which</c>

say see one of the thing that uh which

say see one of the thing that uh which
is<00:36:27.440><c> interesting</c><00:36:27.839><c> here</c><00:36:28.079><c> is</c><00:36:28.560><c> if</c><00:36:28.800><c> you</c><00:36:28.960><c> see</c><00:36:29.119><c> this</c>

is interesting here is if you see this

is interesting here is if you see this
image<00:36:29.599><c> there</c><00:36:29.760><c> is</c><00:36:29.920><c> no</c><00:36:30.079><c> text</c><00:36:30.400><c> here</c><00:36:31.200><c> right</c><00:36:31.440><c> so</c>

image there is no text here right so

image there is no text here right so
it's<00:36:32.400><c> if</c><00:36:32.640><c> you</c><00:36:32.800><c> ask</c><00:36:33.040><c> anything</c><00:36:33.280><c> about</c><00:36:33.520><c> this</c>

it's if you ask anything about this

it's if you ask anything about this
image<00:36:34.800><c> uh</c><00:36:34.960><c> and</c><00:36:35.200><c> use</c><00:36:35.440><c> a</c><00:36:35.599><c> traditional</c><00:36:36.000><c> technique</c>

image uh and use a traditional technique

image uh and use a traditional technique
it<00:36:36.880><c> might</c><00:36:37.040><c> not</c><00:36:37.280><c> answer</c><00:36:37.680><c> properly</c><00:36:38.880><c> uh</c><00:36:39.040><c> like</c>

it might not answer properly uh like

it might not answer properly uh like
this<00:36:39.760><c> this</c><00:36:40.000><c> is</c><00:36:40.160><c> also</c><00:36:40.800><c> another</c><00:36:41.119><c> image</c><00:36:41.520><c> along</c>

this this is also another image along

this this is also another image along
with<00:36:41.920><c> some</c><00:36:42.160><c> text</c><00:36:43.200><c> and</c><00:36:43.680><c> uh</c><00:36:43.839><c> you</c><00:36:44.000><c> know</c><00:36:44.079><c> you</c><00:36:44.320><c> can</c>

with some text and uh you know you can

with some text and uh you know you can
pick<00:36:44.560><c> any</c><00:36:45.040><c> data</c><00:36:45.280><c> set</c><00:36:45.440><c> of</c><00:36:45.599><c> your</c><00:36:45.760><c> choice</c><00:36:46.000><c> but</c><00:36:46.480><c> uh</c>

pick any data set of your choice but uh

pick any data set of your choice but uh
this<00:36:47.599><c> is</c><00:36:47.680><c> the</c><00:36:47.839><c> data</c><00:36:48.079><c> set</c><00:36:48.240><c> that</c><00:36:48.400><c> I</c><00:36:48.640><c> have</c><00:36:49.200><c> okay</c>

this is the data set that I have okay

this is the data set that I have okay
and<00:36:50.400><c> feel</c><00:36:50.640><c> free</c><00:36:50.800><c> to</c><00:36:50.880><c> use</c><00:36:51.040><c> any</c><00:36:51.280><c> data</c><00:36:51.520><c> set</c><00:36:51.599><c> of</c>

and feel free to use any data set of

and feel free to use any data set of
your<00:36:52.000><c> choice</c><00:36:52.240><c> but</c><00:36:52.640><c> uh</c><00:36:52.800><c> for</c><00:36:52.960><c> the</c><00:36:53.119><c> purpose</c><00:36:53.359><c> of</c>

your choice but uh for the purpose of

your choice but uh for the purpose of
this<00:36:54.160><c> uh</c><00:36:54.320><c> demo</c><00:36:54.880><c> you</c><00:36:55.040><c> may</c><00:36:55.200><c> like</c><00:36:55.359><c> to</c><00:36:55.520><c> download</c>

this uh demo you may like to download

this uh demo you may like to download
one<00:36:56.400><c> of</c><00:36:56.560><c> these</c><00:36:57.119><c> uh</c><00:36:57.280><c> PDF</c><00:36:57.760><c> from</c><00:36:58.000><c> this</c><00:36:58.320><c> URL</c><00:36:59.040><c> and</c>

one of these uh PDF from this URL and

one of these uh PDF from this URL and
play<00:36:59.760><c> around</c><00:37:00.000><c> with</c><00:37:00.160><c> this</c><00:37:01.200><c> and</c><00:37:01.359><c> then</c><00:37:01.520><c> you</c><00:37:01.760><c> need</c>

play around with this and then you need

play around with this and then you need
to<00:37:02.079><c> have</c><00:37:02.240><c> a</c><00:37:02.480><c> hugging</c><00:37:02.880><c> phase</c><00:37:03.520><c> uh</c><00:37:04.079><c> uh</c><00:37:05.440><c> uh</c><00:37:05.599><c> token</c>

to have a hugging phase uh uh uh token

to have a hugging phase uh uh uh token
uh<00:37:07.119><c> because</c><00:37:07.760><c> we</c><00:37:08.000><c> are</c><00:37:08.079><c> going</c><00:37:08.160><c> to</c><00:37:08.400><c> download</c><00:37:08.880><c> this</c>

uh because we are going to download this

uh because we are going to download this
model<00:37:09.440><c> from</c><00:37:09.680><c> hugging</c><00:37:10.079><c> phase</c><00:37:10.720><c> right</c><00:37:11.359><c> so</c><00:37:11.599><c> you</c>

model from hugging phase right so you

model from hugging phase right so you
should<00:37:12.000><c> not</c><00:37:12.160><c> do</c><00:37:12.320><c> this</c><00:37:12.720><c> right</c><00:37:12.960><c> so</c><00:37:13.119><c> this</c><00:37:13.280><c> is</c><00:37:13.760><c> uh</c>

should not do this right so this is uh

should not do this right so this is uh
you<00:37:14.400><c> know</c><00:37:14.480><c> I</c><00:37:14.640><c> was</c><00:37:14.800><c> just</c><00:37:14.960><c> trying</c><00:37:15.200><c> this</c><00:37:15.520><c> because</c>

you know I was just trying this because

you know I was just trying this because
without<00:37:16.800><c> creating</c><00:37:17.119><c> av</c><00:37:18.079><c> file</c><00:37:18.800><c> but</c><00:37:19.359><c> you</c><00:37:19.680><c> should</c>

without creating av file but you should

without creating av file but you should
have<00:37:20.480><c> an</c><00:37:20.720><c> env</c><00:37:21.200><c> file</c><00:37:21.440><c> inside</c><00:37:21.760><c> that</c><00:37:22.000><c> your</c><00:37:22.160><c> token</c>

have an env file inside that your token

have an env file inside that your token
should<00:37:22.640><c> exit</c><00:37:23.200><c> exist.</c><00:37:23.680><c> Okay,</c><00:37:24.480><c> so</c><00:37:24.720><c> this</c><00:37:24.960><c> is</c><00:37:25.280><c> uh</c><00:37:25.440><c> a</c>

should exit exist. Okay, so this is uh a

should exit exist. Okay, so this is uh a
token<00:37:26.000><c> like</c><00:37:26.240><c> this</c><00:37:26.400><c> is</c><00:37:26.560><c> not</c><00:37:26.720><c> my</c><00:37:26.880><c> token.</c><00:37:27.200><c> If</c><00:37:27.359><c> you</c>

token like this is not my token. If you

token like this is not my token. If you
see<00:37:27.599><c> this</c><00:37:28.240><c> uh</c><00:37:29.200><c> this</c><00:37:29.440><c> is</c><00:37:29.520><c> just</c><00:37:29.680><c> a</c><00:37:29.920><c> dummy</c><00:37:30.240><c> one,</c>

see this uh this is just a dummy one,

see this uh this is just a dummy one,
right?<00:37:30.720><c> This</c><00:37:30.880><c> is</c><00:37:30.960><c> not</c><00:37:31.200><c> my</c><00:37:31.359><c> token.</c><00:37:32.000><c> Okay,</c><00:37:32.160><c> so</c>

right? This is not my token. Okay, so

right? This is not my token. Okay, so
it's<00:37:33.359><c> but</c><00:37:33.920><c> uh</c><00:37:34.240><c> this</c><00:37:34.480><c> is</c><00:37:35.520><c> this</c><00:37:35.760><c> is</c><00:37:35.920><c> just</c><00:37:36.720><c> uh</c><00:37:36.800><c> the</c>

it's but uh this is this is just uh the

it's but uh this is this is just uh the
the<00:37:37.920><c> hugging</c><00:37:38.320><c> face</c><00:37:38.480><c> token</c><00:37:38.800><c> that</c><00:37:38.960><c> you</c><00:37:39.119><c> should</c>

the hugging face token that you should

the hugging face token that you should
have.<00:37:40.560><c> So</c><00:37:40.800><c> here</c><00:37:41.040><c> we</c><00:37:41.280><c> are</c><00:37:41.440><c> just</c><00:37:41.599><c> loading</c><00:37:41.920><c> and</c>

have. So here we are just loading and

have. So here we are just loading and
logging<00:37:42.560><c> into</c><00:37:42.800><c> our</c><00:37:42.960><c> hugging</c><00:37:43.359><c> face</c><00:37:43.680><c> account.</c>

logging into our hugging face account.

logging into our hugging face account.
And<00:37:46.720><c> next</c><00:37:48.079><c> we</c><00:37:48.400><c> are</c><00:37:49.119><c> trying</c><00:37:49.359><c> to</c><00:37:49.520><c> check</c><00:37:49.839><c> whether</c>

And next we are trying to check whether

And next we are trying to check whether
we<00:37:50.400><c> have</c><00:37:50.560><c> a</c><00:37:50.720><c> CPU,</c><00:37:51.520><c> GPU</c><00:37:52.240><c> or</c><00:37:53.200><c> uh</c><00:37:53.359><c> MPS.</c><00:37:53.839><c> In</c><00:37:54.000><c> this</c>

we have a CPU, GPU or uh MPS. In this

we have a CPU, GPU or uh MPS. In this
case<00:37:54.320><c> it's</c><00:37:54.480><c> a</c><00:37:54.640><c> MacBook</c><00:37:55.040><c> so</c><00:37:55.599><c> I'm</c><00:37:55.920><c> just</c><00:37:56.079><c> using</c>

case it's a MacBook so I'm just using

case it's a MacBook so I'm just using
MPS<00:37:57.200><c> here</c><00:37:57.839><c> uh</c><00:37:58.000><c> as</c><00:37:58.240><c> a</c><00:37:58.480><c> device.</c><00:37:59.359><c> Since</c><00:37:59.680><c> it's</c><00:37:59.839><c> a</c>

MPS here uh as a device. Since it's a

MPS here uh as a device. Since it's a
vision<00:38:00.320><c> based</c><00:38:00.640><c> model</c><00:38:01.119><c> it's</c><00:38:01.359><c> better</c><00:38:01.599><c> to</c><00:38:01.760><c> run</c><00:38:01.920><c> it</c>

vision based model it's better to run it

vision based model it's better to run it
on<00:38:02.160><c> a</c><00:38:02.240><c> GPU.</c><00:38:02.560><c> It</c><00:38:02.720><c> will</c><00:38:02.880><c> be</c><00:38:02.960><c> faster</c><00:38:03.359><c> but</c><00:38:03.599><c> you</c><00:38:03.760><c> can</c>

on a GPU. It will be faster but you can

on a GPU. It will be faster but you can
very<00:38:04.079><c> well</c><00:38:04.240><c> run</c><00:38:04.400><c> it</c><00:38:04.480><c> on</c><00:38:04.720><c> CPU.</c><00:38:05.200><c> That's</c><00:38:05.359><c> fine.</c>

very well run it on CPU. That's fine.

very well run it on CPU. That's fine.
I'll<00:38:06.960><c> tell</c><00:38:07.040><c> you</c><00:38:07.920><c> uh</c><00:38:08.079><c> you</c><00:38:08.240><c> know</c><00:38:08.640><c> you</c><00:38:08.800><c> should</c><00:38:08.960><c> be</c>

I'll tell you uh you know you should be

I'll tell you uh you know you should be
a<00:38:09.119><c> little</c><00:38:09.280><c> cautious</c><00:38:09.599><c> about</c><00:38:09.839><c> this</c><00:38:10.000><c> if</c><00:38:10.160><c> you're</c>

a little cautious about this if you're

a little cautious about this if you're
running<00:38:10.480><c> with</c><00:38:10.640><c> a</c><00:38:11.200><c> within</c><00:38:11.599><c> your</c><00:38:11.760><c> laptop</c><00:38:12.880><c> uh</c><00:38:13.040><c> on</c>

running with a within your laptop uh on

running with a within your laptop uh on
CPU.

CPU.

CPU.
uh

uh

uh
if<00:38:16.720><c> it's</c><00:38:16.880><c> a</c><00:38:17.040><c> office</c><00:38:17.280><c> laptop</c><00:38:17.680><c> no</c><00:38:17.839><c> one</c><00:38:18.000><c> cares</c><00:38:18.160><c> but</c>

if it's a office laptop no one cares but

if it's a office laptop no one cares but
if<00:38:18.480><c> it's</c><00:38:18.640><c> your</c><00:38:18.800><c> personal</c><00:38:19.119><c> laptop</c><00:38:19.599><c> make</c><00:38:19.760><c> sure</c>

if it's your personal laptop make sure

if it's your personal laptop make sure
that<00:38:20.000><c> the</c><00:38:20.240><c> batch</c><00:38:20.480><c> size</c><00:38:20.720><c> is</c><00:38:20.880><c> very</c><00:38:21.040><c> small</c>

that the batch size is very small

that the batch size is very small
otherwise<00:38:21.839><c> it</c><00:38:22.079><c> will</c><00:38:22.400><c> it</c><00:38:22.720><c> will</c><00:38:22.880><c> crash</c><00:38:23.599><c> in</c><00:38:23.839><c> fact</c>

otherwise it will it will crash in fact

otherwise it will it will crash in fact
I<00:38:24.560><c> when</c><00:38:24.800><c> I</c><00:38:25.040><c> first</c><00:38:25.280><c> ran</c><00:38:25.599><c> this</c><00:38:26.240><c> I</c><00:38:26.480><c> did</c><00:38:26.640><c> not</c><00:38:26.800><c> check</c>

I when I first ran this I did not check

I when I first ran this I did not check
uh<00:38:27.839><c> the</c><00:38:28.079><c> processing</c><00:38:28.560><c> time</c><00:38:28.720><c> and</c><00:38:28.960><c> all</c><00:38:29.119><c> that</c><00:38:29.599><c> it</c>

uh the processing time and all that it

uh the processing time and all that it
just<00:38:30.160><c> uh</c><00:38:30.400><c> went</c><00:38:30.640><c> on</c><00:38:31.280><c> u</c><00:38:31.680><c> you</c><00:38:31.920><c> know</c><00:38:32.720><c> crashing</c><00:38:33.200><c> and</c>

just uh went on u you know crashing and

just uh went on u you know crashing and
it<00:38:33.680><c> uh</c><00:38:33.839><c> rebooted</c><00:38:34.320><c> my</c><00:38:34.560><c> laptop</c>

it uh rebooted my laptop

it uh rebooted my laptop
uh<00:38:36.480><c> and</c><00:38:36.960><c> uh</c><00:38:37.119><c> I</c><00:38:37.280><c> I</c><00:38:37.599><c> did</c><00:38:37.760><c> not</c><00:38:37.920><c> even</c><00:38:38.400><c> read</c><00:38:38.720><c> through</c>

uh and uh I I did not even read through

uh and uh I I did not even read through
all<00:38:39.040><c> this</c><00:38:39.280><c> and</c><00:38:39.520><c> I</c><00:38:39.680><c> ra</c><00:38:40.000><c> the</c><00:38:40.240><c> IT</c><00:38:40.720><c> ticket</c><00:38:41.040><c> and</c><00:38:41.359><c> I</c>

all this and I ra the IT ticket and I

all this and I ra the IT ticket and I
actually<00:38:41.920><c> got</c><00:38:42.079><c> a</c><00:38:42.240><c> laptop</c><00:38:42.640><c> new</c><00:38:42.880><c> laptop</c><00:38:43.520><c> uh</c><00:38:43.839><c> So</c>

actually got a laptop new laptop uh So

actually got a laptop new laptop uh So
but<00:38:44.880><c> it</c><00:38:45.040><c> was</c><00:38:45.200><c> my</c><00:38:45.440><c> fault</c><00:38:45.760><c> here.</c><00:38:46.079><c> So</c><00:38:46.240><c> they</c>

but it was my fault here. So they

but it was my fault here. So they
thought<00:38:46.640><c> that</c><00:38:46.960><c> my</c><00:38:47.200><c> work</c><00:38:48.000><c> my</c><00:38:48.240><c> work</c><00:38:48.480><c> needs</c><00:38:48.720><c> a</c>

thought that my work my work needs a

thought that my work my work needs a
laptop<00:38:49.280><c> with</c><00:38:49.760><c> more</c><00:38:50.079><c> memory.</c><00:38:50.720><c> So</c><00:38:51.520><c> so</c><00:38:51.760><c> if</c><00:38:51.920><c> you</c>

laptop with more memory. So so if you

laptop with more memory. So so if you
are<00:38:52.240><c> finding</c><00:38:52.560><c> out</c><00:38:52.800><c> tricks</c><00:38:53.119><c> to</c><00:38:53.359><c> get</c><00:38:53.440><c> a</c><00:38:53.599><c> new</c>

are finding out tricks to get a new

are finding out tricks to get a new
laptop<00:38:54.079><c> from</c><00:38:54.240><c> a</c><00:38:54.480><c> company.</c><00:38:54.880><c> So</c><00:38:55.040><c> this</c><00:38:55.280><c> is</c><00:38:55.440><c> the</c>

laptop from a company. So this is the

laptop from a company. So this is the
cell.<00:38:56.800><c> So</c><00:38:58.160><c> okay</c><00:38:59.599><c> uh</c><00:38:59.680><c> you</c><00:38:59.839><c> can</c><00:39:00.000><c> try</c><00:39:00.160><c> that.</c><00:39:00.400><c> I</c>

cell. So okay uh you can try that. I

cell. So okay uh you can try that. I
I'll<00:39:01.040><c> tell</c><00:39:01.200><c> you</c><00:39:01.599><c> what</c><00:39:02.160><c> you</c><00:39:02.480><c> have</c><00:39:02.640><c> to</c><00:39:02.800><c> change</c><00:39:03.119><c> to</c>

I'll tell you what you have to change to

I'll tell you what you have to change to
get<00:39:03.440><c> a</c><00:39:03.599><c> new</c><00:39:03.760><c> laptop.</c><00:39:04.320><c> So</c><00:39:04.560><c> just</c><00:39:04.800><c> increase</c><00:39:05.040><c> the</c>

get a new laptop. So just increase the

get a new laptop. So just increase the
batch<00:39:05.520><c> size</c><00:39:05.839><c> to</c><00:39:06.640><c> batch</c><00:39:06.960><c> size</c><00:39:07.119><c> to</c><00:39:07.440><c> 12.</c><00:39:07.760><c> It</c>

batch size to batch size to 12. It

batch size to batch size to 12. It
should<00:39:08.079><c> work</c><00:39:08.320><c> fine.</c><00:39:08.800><c> Yeah.</c><00:39:10.160><c> Yeah.</c><00:39:11.040><c> Okay.</c><00:39:11.839><c> So</c>

should work fine. Yeah. Yeah. Okay. So

should work fine. Yeah. Yeah. Okay. So
this<00:39:13.680><c> is</c><00:39:13.839><c> the</c><00:39:14.000><c> model</c><00:39:14.240><c> that</c><00:39:14.480><c> we</c><00:39:14.640><c> are</c><00:39:14.800><c> going</c><00:39:14.880><c> to</c>

this is the model that we are going to

this is the model that we are going to
use.<00:39:15.760><c> It's</c><00:39:16.000><c> a</c><00:39:16.160><c> call</c><00:39:16.400><c> pali</c><00:39:17.040><c> uh</c><00:39:17.200><c> version</c><00:39:17.520><c> 1.3.</c>

use. It's a call pali uh version 1.3.

use. It's a call pali uh version 1.3.
There<00:39:19.040><c> might</c><00:39:19.280><c> be</c><00:39:19.440><c> our</c><00:39:19.680><c> new</c><00:39:19.839><c> version</c><00:39:20.160><c> but</c><00:39:20.480><c> just</c>

There might be our new version but just

There might be our new version but just
have<00:39:20.800><c> a</c><00:39:20.960><c> look.</c><00:39:21.119><c> I</c><00:39:21.280><c> I</c><00:39:21.520><c> checked</c><00:39:22.000><c> last</c><00:39:22.240><c> month</c><00:39:22.400><c> it</c>

have a look. I I checked last month it

have a look. I I checked last month it
was<00:39:22.720><c> still</c><00:39:22.960><c> 1.3.</c>

was still 1.3.

was still 1.3.
And<00:39:25.520><c> I'm</c><00:39:25.920><c> having</c><00:39:26.160><c> a</c><00:39:26.560><c> model</c><00:39:26.960><c> and</c><00:39:27.200><c> a</c>

And I'm having a model and a

And I'm having a model and a
pre-processor.<00:39:28.560><c> Remember</c><00:39:28.880><c> that</c><00:39:29.040><c> we</c>

pre-processor. Remember that we

pre-processor. Remember that we
discussed<00:39:29.440><c> that</c><00:39:29.680><c> we</c><00:39:29.839><c> need</c><00:39:29.920><c> to</c><00:39:30.000><c> have</c><00:39:30.079><c> a</c>

discussed that we need to have a

discussed that we need to have a
pre-processor<00:39:31.040><c> first.</c><00:39:31.839><c> Uh</c><00:39:32.079><c> we</c><00:39:32.320><c> will</c><00:39:32.480><c> process</c>

pre-processor first. Uh we will process

pre-processor first. Uh we will process
our<00:39:32.960><c> data</c><00:39:33.200><c> and</c><00:39:33.440><c> then</c><00:39:33.599><c> we</c><00:39:33.760><c> will</c><00:39:33.920><c> use</c><00:39:34.079><c> the</c><00:39:34.240><c> model</c>

our data and then we will use the model

our data and then we will use the model
to<00:39:34.640><c> generate</c><00:39:34.880><c> the</c><00:39:35.040><c> embeddings.</c><00:39:35.680><c> Okay.</c><00:39:36.240><c> the</c>

to generate the embeddings. Okay. the

to generate the embeddings. Okay. the
same<00:39:36.640><c> model</c><00:39:37.119><c> but</c><00:39:37.440><c> there</c><00:39:37.599><c> is</c><00:39:37.760><c> a</c><00:39:37.920><c> pre-processor</c>

same model but there is a pre-processor

same model but there is a pre-processor
and<00:39:39.599><c> the</c><00:39:39.920><c> model</c><00:39:40.240><c> and</c><00:39:40.480><c> these</c><00:39:40.720><c> all</c><00:39:40.960><c> are</c><00:39:41.200><c> coming</c>

and the model and these all are coming

and the model and these all are coming
from<00:39:41.680><c> hugging</c><00:39:42.160><c> face</c><00:39:43.280><c> and</c><00:39:43.599><c> we</c><00:39:43.839><c> are</c><00:39:44.000><c> using</c><00:39:44.160><c> a</c>

from hugging face and we are using a

from hugging face and we are using a
cache<00:39:44.720><c> directory</c><00:39:45.040><c> so</c><00:39:45.200><c> that</c><00:39:45.359><c> we</c><00:39:45.520><c> can</c><00:39:45.920><c> load</c><00:39:46.240><c> this</c>

cache directory so that we can load this

cache directory so that we can load this
model<00:39:46.960><c> locally</c><00:39:47.280><c> in</c><00:39:47.440><c> our</c><00:39:48.000><c> uh</c><00:39:48.240><c> local</c><00:39:48.560><c> directory</c>

model locally in our uh local directory

model locally in our uh local directory
uh<00:39:49.520><c> so</c><00:39:49.760><c> that</c><00:39:50.560><c> every</c><00:39:50.800><c> time</c><00:39:50.960><c> you</c><00:39:51.119><c> run</c><00:39:51.440><c> it</c><00:39:51.599><c> doesn't</c>

uh so that every time you run it doesn't

uh so that every time you run it doesn't
download<00:39:52.480><c> from</c><00:39:52.720><c> the</c><00:39:52.880><c> internet</c><00:39:53.440><c> okay</c>

download from the internet okay

download from the internet okay
and<00:39:55.599><c> once</c><00:39:55.920><c> that</c><00:39:56.079><c> is</c><00:39:56.240><c> done</c><00:39:57.119><c> uh</c><00:39:57.280><c> you</c><00:39:57.440><c> have</c><00:39:57.599><c> to</c>

and once that is done uh you have to

and once that is done uh you have to
have<00:39:57.839><c> a</c><00:39:58.000><c> vector</c><00:39:58.320><c> database</c><00:39:58.960><c> so</c><00:39:59.680><c> if</c><00:39:59.920><c> you</c><00:40:00.079><c> have</c><00:40:00.160><c> a</c>

have a vector database so if you have a

have a vector database so if you have a
docker<00:40:01.280><c> installed</c><00:40:01.920><c> you</c><00:40:02.160><c> can</c><00:40:02.240><c> just</c><00:40:02.480><c> copy</c><00:40:02.800><c> and</c>

docker installed you can just copy and

docker installed you can just copy and
paste<00:40:03.200><c> it</c><00:40:03.599><c> it</c><00:40:03.839><c> is</c><00:40:04.000><c> nothing</c><00:40:04.240><c> but</c><00:40:04.800><c> it</c><00:40:05.040><c> just</c>

paste it it is nothing but it just

paste it it is nothing but it just
created<00:40:05.520><c> a</c><00:40:05.839><c> a</c><00:40:06.079><c> container</c><00:40:06.800><c> with</c><00:40:07.040><c> a</c><00:40:07.200><c> port</c>

created a a container with a port

created a a container with a port
forwarding<00:40:08.320><c> and</c><00:40:08.800><c> uh</c><00:40:08.880><c> there</c><00:40:09.119><c> is</c><00:40:09.200><c> a</c><00:40:09.599><c> folder</c>

forwarding and uh there is a folder

forwarding and uh there is a folder
which<00:40:10.320><c> gets</c><00:40:10.560><c> created</c><00:40:10.960><c> locally</c><00:40:12.160><c> uh</c><00:40:12.720><c> as</c><00:40:12.960><c> a</c>

which gets created locally uh as a

which gets created locally uh as a
storage.<00:40:13.920><c> So</c><00:40:14.160><c> all</c><00:40:14.320><c> your</c><00:40:14.480><c> vectors</c><00:40:14.880><c> will</c><00:40:14.960><c> be</c>

storage. So all your vectors will be

storage. So all your vectors will be
stored<00:40:15.359><c> locally</c><00:40:15.680><c> in</c><00:40:15.839><c> your</c><00:40:16.000><c> laptop.</c><00:40:16.480><c> That's</c>

stored locally in your laptop. That's

stored locally in your laptop. That's
all.<00:40:18.000><c> And</c><00:40:18.400><c> if</c><00:40:18.720><c> you</c><00:40:19.040><c> click</c><00:40:19.280><c> on</c><00:40:19.440><c> this</c><00:40:19.839><c> dashboard,</c>

all. And if you click on this dashboard,

all. And if you click on this dashboard,
you<00:40:21.280><c> should</c><00:40:21.440><c> be</c><00:40:21.599><c> able</c><00:40:21.760><c> to</c><00:40:22.000><c> see</c><00:40:22.800><c> uh</c><00:40:24.079><c> that</c><00:40:24.640><c> uh</c><00:40:24.960><c> UI</c>

you should be able to see uh that uh UI

you should be able to see uh that uh UI
of<00:40:25.599><c> that.</c><00:40:26.320><c> And</c><00:40:26.560><c> if</c><00:40:26.800><c> you</c><00:40:26.960><c> come</c><00:40:27.200><c> to</c><00:40:27.520><c> console</c><00:40:28.160><c> uh</c>

of that. And if you come to console uh

of that. And if you come to console uh
sorry<00:40:28.960><c> um</c><00:40:29.520><c> here</c><00:40:29.920><c> collection</c><00:40:30.640><c> initially</c><00:40:31.119><c> you</c>

sorry um here collection initially you

sorry um here collection initially you
since<00:40:31.760><c> I</c><00:40:31.920><c> have</c><00:40:32.000><c> executed</c><00:40:32.400><c> that</c><00:40:32.560><c> code</c><00:40:32.880><c> that's</c>

since I have executed that code that's

since I have executed that code that's
why<00:40:33.200><c> we</c><00:40:33.440><c> see</c><00:40:33.599><c> this</c><00:40:34.079><c> but</c><00:40:34.560><c> you</c><00:40:34.800><c> should</c><00:40:34.960><c> not</c><00:40:35.200><c> see</c>

why we see this but you should not see

why we see this but you should not see
anything<00:40:35.839><c> here</c><00:40:36.800><c> and</c><00:40:37.040><c> as</c><00:40:37.280><c> you</c><00:40:37.440><c> run</c><00:40:37.599><c> through</c><00:40:37.839><c> the</c>

anything here and as you run through the

anything here and as you run through the
notebook<00:40:38.480><c> you</c><00:40:38.720><c> will</c><00:40:38.880><c> see</c><00:40:39.680><c> the</c><00:40:40.560><c> uh</c><00:40:41.440><c> collection</c>

notebook you will see the uh collection

notebook you will see the uh collection
here.<00:40:42.480><c> So</c><00:40:42.640><c> collection</c><00:40:43.040><c> is</c><00:40:43.680><c> how</c><00:40:43.839><c> many</c><00:40:44.000><c> of</c><00:40:44.079><c> you</c>

here. So collection is how many of you

here. So collection is how many of you
are<00:40:44.320><c> aware</c><00:40:44.560><c> of</c><00:40:44.640><c> databases?</c>

are aware of databases?

are aware of databases?
Okay.<00:40:47.119><c> Okay,</c><00:40:47.599><c> many</c><00:40:47.839><c> of</c><00:40:47.920><c> you</c><00:40:48.160><c> I</c><00:40:48.320><c> have</c><00:40:48.480><c> no</c><00:40:48.720><c> idea</c>

Okay. Okay, many of you I have no idea

Okay. Okay, many of you I have no idea
what<00:40:49.280><c> what</c><00:40:49.520><c> it</c><00:40:49.680><c> is</c><00:40:49.839><c> but</c><00:40:50.480><c> I</c><00:40:50.720><c> just</c><00:40:50.880><c> asked.</c><00:40:51.200><c> So</c><00:40:51.599><c> the</c>

what what it is but I just asked. So the

what what it is but I just asked. So the
collection<00:40:52.079><c> is</c><00:40:52.240><c> basically</c><00:40:52.640><c> you</c><00:40:52.800><c> can</c><00:40:52.880><c> think</c><00:40:52.960><c> of</c>

collection is basically you can think of

collection is basically you can think of
it<00:40:53.280><c> like</c><00:40:53.440><c> a</c><00:40:53.839><c> database</c><00:40:54.320><c> and</c><00:40:54.800><c> where</c><00:40:55.280><c> you</c><00:40:55.520><c> will</c>

it like a database and where you will

it like a database and where you will
just<00:40:55.839><c> store</c><00:40:56.240><c> all</c><00:40:56.560><c> the</c><00:40:57.119><c> uh</c><00:40:57.599><c> schema</c><00:40:58.000><c> and</c><00:40:58.240><c> all</c>

just store all the uh schema and all

just store all the uh schema and all
that.<00:40:59.280><c> So</c><00:41:00.720><c> I'm</c><00:41:01.280><c> creating</c><00:41:01.599><c> a</c><00:41:02.319><c> quadrant</c><00:41:02.880><c> client</c>

that. So I'm creating a quadrant client

that. So I'm creating a quadrant client
and<00:41:04.160><c> this</c><00:41:04.319><c> is</c><00:41:04.480><c> something</c><00:41:04.640><c> that</c><00:41:04.800><c> I</c><00:41:05.040><c> imported</c>

and this is something that I imported

and this is something that I imported
earlier<00:41:07.359><c> and</c><00:41:07.599><c> this</c><00:41:07.760><c> is</c><00:41:07.839><c> the</c><00:41:08.000><c> local</c><00:41:08.319><c> host</c><00:41:08.560><c> and</c>

earlier and this is the local host and

earlier and this is the local host and
port<00:41:09.119><c> number</c><00:41:09.520><c> this</c><00:41:09.680><c> and</c><00:41:09.920><c> this</c><00:41:10.160><c> just</c><00:41:10.560><c> we</c><00:41:10.800><c> are</c>

port number this and this just we are

port number this and this just we are
just<00:41:11.520><c> creating</c><00:41:11.920><c> the</c><00:41:12.160><c> setup</c><00:41:12.880><c> right.</c><00:41:13.359><c> So</c><00:41:13.599><c> now</c><00:41:13.760><c> we</c>

just creating the setup right. So now we

just creating the setup right. So now we
have<00:41:14.000><c> a</c><00:41:14.160><c> vector</c><00:41:14.480><c> database</c><00:41:15.440><c> and</c><00:41:15.760><c> we</c><00:41:15.920><c> have</c><00:41:16.079><c> the</c>

have a vector database and we have the

have a vector database and we have the
data.<00:41:17.200><c> So</c><00:41:17.520><c> and</c><00:41:17.760><c> we</c><00:41:17.920><c> have</c><00:41:18.079><c> also</c><00:41:18.880><c> uh</c><00:41:19.119><c> downloaded</c>

data. So and we have also uh downloaded

data. So and we have also uh downloaded
the<00:41:19.839><c> model.</c><00:41:20.880><c> So</c><00:41:21.119><c> now</c><00:41:21.280><c> the</c><00:41:21.520><c> second</c><00:41:21.760><c> thing</c><00:41:21.839><c> that</c>

the model. So now the second thing that

the model. So now the second thing that
we<00:41:22.240><c> need</c><00:41:22.319><c> to</c><00:41:22.480><c> do</c><00:41:22.640><c> is</c><00:41:23.599><c> we</c><00:41:23.839><c> need</c><00:41:24.000><c> to</c><00:41:24.160><c> create</c><00:41:24.400><c> a</c>

we need to do is we need to create a

we need to do is we need to create a
collection<00:41:25.599><c> right</c><00:41:26.079><c> and</c><00:41:26.319><c> if</c><00:41:26.560><c> you</c><00:41:26.640><c> see</c><00:41:26.800><c> this</c><00:41:27.200><c> uh</c>

collection right and if you see this uh

collection right and if you see this uh
we<00:41:27.520><c> have</c><00:41:27.599><c> a</c><00:41:27.839><c> collection</c><00:41:28.160><c> called</c><00:41:28.880><c> u</c><00:41:29.200><c> class</c><00:41:29.520><c> 10</c>

we have a collection called u class 10

we have a collection called u class 10
science.<00:41:30.800><c> Uh</c><00:41:31.119><c> so</c><00:41:32.160><c> you</c><00:41:32.400><c> can</c><00:41:32.560><c> give</c><00:41:33.280><c> any</c>

science. Uh so you can give any

science. Uh so you can give any
collection<00:41:34.000><c> name.</c><00:41:35.040><c> Here</c><00:41:35.440><c> we</c><00:41:35.680><c> are</c><00:41:35.920><c> mentioning</c>

collection name. Here we are mentioning

collection name. Here we are mentioning
what<00:41:36.720><c> should</c><00:41:36.880><c> be</c><00:41:36.960><c> the</c><00:41:37.119><c> vector</c><00:41:37.520><c> size</c><00:41:38.319><c> right?</c><00:41:38.640><c> So</c>

what should be the vector size right? So

what should be the vector size right? So
uh<00:41:39.599><c> this</c><00:41:39.760><c> is</c><00:41:39.920><c> the</c><00:41:40.960><c> uh</c><00:41:41.200><c> embedding</c><00:41:41.760><c> length.</c><00:41:42.160><c> So</c>

uh this is the uh embedding length. So

uh this is the uh embedding length. So
here<00:41:42.560><c> it</c><00:41:42.720><c> is</c><00:41:43.119><c> 128</c><00:41:44.480><c> and</c><00:41:45.760><c> in</c><00:41:46.000><c> this</c><00:41:46.960><c> in</c><00:41:47.200><c> this</c><00:41:47.359><c> code</c>

here it is 128 and in this in this code

here it is 128 and in this in this code
what<00:41:48.000><c> we</c><00:41:48.400><c> essentially</c><00:41:48.800><c> doing</c><00:41:49.040><c> is</c><00:41:49.599><c> if</c><00:41:49.839><c> there</c><00:41:50.000><c> is</c>

what we essentially doing is if there is

what we essentially doing is if there is
a<00:41:50.240><c> collection</c><00:41:50.560><c> already</c><00:41:50.800><c> exists</c><00:41:51.200><c> it</c><00:41:51.359><c> will</c><00:41:51.440><c> not</c>

a collection already exists it will not

a collection already exists it will not
create<00:41:51.839><c> any</c><00:41:52.079><c> new</c><00:41:52.319><c> collection</c><00:41:52.880><c> or</c><00:41:53.040><c> else</c><00:41:53.280><c> it</c>

create any new collection or else it

create any new collection or else it
will<00:41:53.680><c> create</c><00:41:53.839><c> a</c><00:41:54.160><c> new</c><00:41:54.400><c> connection.</c><00:41:55.040><c> Yeah</c><00:41:55.280><c> you</c>

will create a new connection. Yeah you

will create a new connection. Yeah you
have<00:41:55.599><c> a</c><00:41:55.760><c> question.</c>

have a question.

have a question.
&gt;&gt; Yeah.

&gt;&gt; Yeah.<00:42:01.760><c> So</c><00:42:02.480><c> there</c><00:42:02.720><c> is</c><00:42:02.960><c> a</c>

&gt;&gt; Yeah. So there is a

&gt;&gt; Yeah. So there is a
let<00:42:05.359><c> me</c><00:42:05.520><c> ask</c><00:42:05.760><c> you</c><00:42:05.920><c> this.</c><00:42:07.040><c> What</c><00:42:07.200><c> do</c><00:42:07.359><c> you</c><00:42:07.440><c> feel</c><00:42:07.599><c> if</c>

let me ask you this. What do you feel if

let me ask you this. What do you feel if
I<00:42:08.240><c> increase</c><00:42:08.560><c> the</c><00:42:09.040><c> embedding</c><00:42:09.599><c> size</c><00:42:09.920><c> from</c><00:42:10.400><c> 128</c>

I increase the embedding size from 128

I increase the embedding size from 128
to<00:42:11.119><c> 256?</c>

What<00:42:14.560><c> do</c><00:42:14.720><c> you</c><00:42:14.800><c> feel?</c><00:42:15.040><c> H</c><00:42:15.440><c> how</c><00:42:15.680><c> it</c><00:42:15.920><c> would</c><00:42:16.079><c> behave?</c>

What do you feel? H how it would behave?

What do you feel? H how it would behave?
Just<00:42:17.440><c> a</c><00:42:17.839><c> guess.</c>

&gt;&gt; Mhm.

&gt;&gt; Okay.<00:42:30.960><c> Okay.</c><00:42:31.280><c> Let</c><00:42:31.520><c> let</c><00:42:31.760><c> me</c><00:42:32.000><c> let</c><00:42:32.240><c> me</c><00:42:32.560><c> give</c><00:42:32.720><c> you</c>

&gt;&gt; Okay. Okay. Let let me let me give you

&gt;&gt; Okay. Okay. Let let me let me give you
an<00:42:33.040><c> example.</c><00:42:33.440><c> Okay.</c>

an example. Okay.

an example. Okay.
Let's<00:42:35.680><c> say</c><00:42:36.079><c> I</c><00:42:36.480><c> I</c><00:42:36.480><c> I</c><00:42:37.599><c> I</c><00:42:38.079><c> have</c><00:42:38.240><c> just</c><00:42:38.400><c> come</c><00:42:38.560><c> here</c>

Let's say I I I I have just come here

Let's say I I I I have just come here
and<00:42:39.119><c> I</c><00:42:39.359><c> mentioned</c><00:42:39.599><c> you</c><00:42:39.839><c> two</c><00:42:40.079><c> things</c><00:42:40.240><c> about</c><00:42:40.480><c> me.</c>

and I mentioned you two things about me.

and I mentioned you two things about me.
I<00:42:41.760><c> work</c><00:42:41.920><c> for</c><00:42:42.160><c> Amazon</c>

I work for Amazon

I work for Amazon
and

and

and
I'm<00:42:46.720><c> married.</c><00:42:47.839><c> That's</c><00:42:48.079><c> all.</c><00:42:48.720><c> Okay.</c><00:42:48.960><c> These</c><00:42:49.119><c> are</c>

I'm married. That's all. Okay. These are

I'm married. That's all. Okay. These are
the<00:42:49.359><c> two</c><00:42:49.520><c> information</c><00:42:49.839><c> that</c><00:42:50.079><c> you</c><00:42:50.240><c> have.</c><00:42:51.119><c> Now</c>

the two information that you have. Now

the two information that you have. Now
if<00:42:51.680><c> he</c><00:42:51.920><c> asks</c><00:42:52.240><c> you</c><00:42:52.400><c> some</c><00:42:52.720><c> question</c><00:42:52.960><c> about</c><00:42:53.200><c> me</c>

if he asks you some question about me

if he asks you some question about me
that<00:42:53.920><c> uh</c><00:42:54.079><c> okay</c><00:42:54.720><c> uh</c><00:42:55.359><c> tell</c><00:42:55.520><c> me</c><00:42:55.839><c> someone</c><00:42:56.160><c> plays</c>

that uh okay uh tell me someone plays

that uh okay uh tell me someone plays
cricket<00:42:56.800><c> or</c><00:42:56.960><c> not.</c><00:42:57.920><c> Will</c><00:42:58.079><c> you</c><00:42:58.240><c> be</c><00:42:58.319><c> able</c><00:42:58.480><c> to</c><00:42:58.560><c> give</c>

cricket or not. Will you be able to give

cricket or not. Will you be able to give
some<00:42:59.040><c> answer?</c><00:43:00.079><c> No.</c><00:43:00.319><c> You</c><00:43:00.480><c> will</c><00:43:00.640><c> be</c><00:43:00.720><c> giving</c><00:43:00.960><c> some</c>

some answer? No. You will be giving some

some answer? No. You will be giving some
answer<00:43:01.280><c> based</c><00:43:01.520><c> on</c><00:43:01.599><c> these</c><00:43:01.839><c> two</c><00:43:02.000><c> information</c>

answer based on these two information

answer based on these two information
but<00:43:02.480><c> it</c><00:43:02.640><c> will</c><00:43:02.800><c> be</c><00:43:02.880><c> random.</c><00:43:03.599><c> Right?</c><00:43:04.480><c> But</c><00:43:04.720><c> now</c>

but it will be random. Right? But now

but it will be random. Right? But now
let's<00:43:06.319><c> say</c><00:43:06.400><c> if</c><00:43:06.640><c> I</c><00:43:06.720><c> give</c><00:43:06.880><c> you</c><00:43:07.680><c> more</c>

let's say if I give you more

let's say if I give you more
information.<00:43:08.800><c> I</c><00:43:08.960><c> am</c><00:43:09.119><c> Suman.</c><00:43:10.079><c> I</c><00:43:10.319><c> work</c><00:43:10.480><c> for</c>

information. I am Suman. I work for

information. I am Suman. I work for
Amazon.

Amazon.

Amazon.
I<00:43:12.480><c> am</c><00:43:12.640><c> married.</c>

I am married.

I am married.
I<00:43:14.400><c> have</c><00:43:14.560><c> one</c><00:43:15.040><c> wife</c><00:43:16.079><c> as</c><00:43:16.319><c> of</c><00:43:16.560><c> now.</c><00:43:16.960><c> I</c><00:43:18.000><c> let's</c><00:43:18.160><c> say</c><00:43:18.319><c> I</c>

I have one wife as of now. I let's say I

I have one wife as of now. I let's say I
have<00:43:18.640><c> one</c><00:43:18.880><c> kid.</c><00:43:19.839><c> Okay.</c><00:43:20.480><c> And</c><00:43:20.800><c> few</c><00:43:21.040><c> other</c>

have one kid. Okay. And few other

have one kid. Okay. And few other
things.

things.

things.
So<00:43:23.040><c> if</c><00:43:23.200><c> I</c><00:43:23.359><c> keep</c><00:43:23.520><c> on</c><00:43:23.680><c> giving</c><00:43:24.000><c> more</c><00:43:24.319><c> features</c>

So if I keep on giving more features

So if I keep on giving more features
about<00:43:25.040><c> me,</c><00:43:26.160><c> you</c><00:43:26.400><c> are</c><00:43:26.560><c> having</c><00:43:26.800><c> a</c><00:43:26.960><c> richer</c><00:43:27.680><c> uh</c>

about me, you are having a richer uh

about me, you are having a richer uh
information<00:43:28.560><c> about</c><00:43:28.960><c> me.</c><00:43:29.359><c> So</c><00:43:29.520><c> now</c><00:43:29.680><c> if</c><00:43:29.839><c> he</c><00:43:30.000><c> asks</c>

information about me. So now if he asks

information about me. So now if he asks
you<00:43:30.400><c> a</c><00:43:30.640><c> question</c><00:43:31.520><c> it's</c><00:43:31.839><c> more</c><00:43:32.079><c> likely</c><00:43:32.319><c> that</c><00:43:32.560><c> you</c>

you a question it's more likely that you

you a question it's more likely that you
will<00:43:32.880><c> be</c><00:43:32.960><c> able</c><00:43:33.119><c> to</c><00:43:33.280><c> give</c><00:43:33.440><c> a</c><00:43:34.160><c> uh</c><00:43:34.319><c> you</c><00:43:34.480><c> know</c><00:43:34.720><c> you</c>

will be able to give a uh you know you

will be able to give a uh you know you
are<00:43:35.040><c> you'll</c><00:43:35.359><c> be</c><00:43:35.440><c> able</c><00:43:35.599><c> to</c><00:43:35.680><c> give</c><00:43:35.839><c> a</c><00:43:36.079><c> more</c>

are you'll be able to give a more

are you'll be able to give a more
accurate<00:43:37.119><c> answer.</c><00:43:37.680><c> Same</c><00:43:38.000><c> with</c><00:43:38.160><c> this</c><00:43:39.040><c> the</c>

accurate answer. Same with this the

accurate answer. Same with this the
moment<00:43:39.520><c> you</c><00:43:39.760><c> increase</c><00:43:39.920><c> the</c><00:43:40.079><c> embedding</c><00:43:40.480><c> length</c>

moment you increase the embedding length

moment you increase the embedding length
you<00:43:42.160><c> are</c><00:43:42.400><c> it's</c><00:43:42.720><c> not</c><00:43:42.880><c> about</c><00:43:43.040><c> chunk</c><00:43:43.359><c> and</c><00:43:43.599><c> all</c>

you are it's not about chunk and all

you are it's not about chunk and all
that<00:43:43.920><c> it's</c><00:43:44.160><c> just</c><00:43:44.400><c> about</c><00:43:45.359><c> how</c><00:43:45.680><c> much</c><00:43:45.920><c> granual</c>

that it's just about how much granual

that it's just about how much granual
information<00:43:46.880><c> that</c><00:43:47.119><c> you</c><00:43:47.280><c> are</c><00:43:47.440><c> having</c><00:43:48.079><c> about</c><00:43:48.400><c> a</c>

information that you are having about a

information that you are having about a
specific<00:43:49.119><c> thing.</c>

specific thing.

specific thing.
Okay.<00:43:51.119><c> So</c><00:43:51.280><c> you</c><00:43:51.520><c> can</c><00:43:51.680><c> always</c><00:43:52.000><c> embed</c><00:43:53.359><c> uh</c><00:43:53.520><c> any</c>

Okay. So you can always embed uh any

Okay. So you can always embed uh any
entity<00:43:54.480><c> with</c><00:43:54.800><c> just</c><00:43:54.960><c> one</c><00:43:55.200><c> number</c><00:43:55.599><c> a</c><00:43:55.839><c> vector</c><00:43:56.160><c> of</c>

entity with just one number a vector of

entity with just one number a vector of
size<00:43:56.720><c> one</c><00:43:57.760><c> but</c><00:43:58.000><c> it</c><00:43:58.160><c> will</c><00:43:58.319><c> not</c><00:43:58.480><c> have</c><00:43:58.640><c> much</c><00:43:58.800><c> of</c><00:43:58.960><c> an</c>

size one but it will not have much of an

size one but it will not have much of an
information<00:44:00.160><c> as</c><00:44:00.560><c> you</c><00:44:00.800><c> increase</c><00:44:01.040><c> the</c><00:44:01.280><c> length</c>

information as you increase the length

information as you increase the length
it<00:44:01.839><c> will</c><00:44:02.160><c> it</c><00:44:02.480><c> will</c><00:44:02.640><c> be</c><00:44:02.720><c> more</c><00:44:02.960><c> richer.</c><00:44:03.839><c> Okay.</c>

it will it will be more richer. Okay.

it will it will be more richer. Okay.
Okay.<00:44:05.599><c> So</c><00:44:06.079><c> coming</c><00:44:06.400><c> back</c><00:44:06.560><c> to</c><00:44:06.640><c> your</c><00:44:06.880><c> question</c><00:44:07.680><c> uh</c>

Okay. So coming back to your question uh

Okay. So coming back to your question uh
in<00:44:08.400><c> the</c><00:44:08.560><c> documentation</c><00:44:09.280><c> I</c><00:44:09.440><c> think</c><00:44:09.599><c> they</c><00:44:10.480><c> uh</c>

in the documentation I think they uh

in the documentation I think they uh
they<00:44:10.880><c> said</c><00:44:11.119><c> that</c><00:44:11.680><c> 128</c><00:44:12.000><c> is</c><00:44:12.160><c> a</c><00:44:12.319><c> good</c><00:44:12.560><c> number</c><00:44:13.040><c> uh</c>

they said that 128 is a good number uh

they said that 128 is a good number uh
but<00:44:13.359><c> you</c><00:44:13.599><c> can</c><00:44:13.760><c> always</c><00:44:13.920><c> use</c><00:44:14.160><c> 256</c><00:44:14.960><c> right</c><00:44:15.119><c> if</c><00:44:15.359><c> the</c>

but you can always use 256 right if the

but you can always use 256 right if the
vector<00:44:16.000><c> database</c><00:44:16.480><c> also</c><00:44:16.800><c> supports</c><00:44:17.119><c> that</c><00:44:17.359><c> or</c>

vector database also supports that or

vector database also supports that or
the<00:44:17.680><c> embedding</c><00:44:18.160><c> model.</c><00:44:18.560><c> Okay.</c><00:44:19.520><c> So,</c>

the embedding model. Okay. So,

the embedding model. Okay. So,
so<00:44:22.000><c> this</c><00:44:22.160><c> is</c><00:44:22.240><c> where</c><00:44:22.480><c> we</c><00:44:22.720><c> are</c><00:44:22.880><c> just</c><00:44:23.040><c> creating</c>

so this is where we are just creating

so this is where we are just creating
that<00:44:23.599><c> collection.</c><00:44:24.079><c> We</c><00:44:24.240><c> have</c><00:44:24.400><c> not</c><00:44:24.640><c> even</c><00:44:25.119><c> uh</c>

that collection. We have not even uh

that collection. We have not even uh
started<00:44:25.680><c> creating</c><00:44:25.920><c> the</c><00:44:26.079><c> embeddings</c><00:44:26.560><c> and</c><00:44:26.720><c> all</c>

started creating the embeddings and all

started creating the embeddings and all
that.<00:44:27.599><c> And</c><00:44:27.920><c> see</c><00:44:28.160><c> this</c><00:44:28.400><c> here</c><00:44:29.119><c> uh</c><00:44:29.280><c> this</c><00:44:29.520><c> is</c><00:44:29.680><c> what</c>

that. And see this here uh this is what

that. And see this here uh this is what
u<00:44:31.599><c> I</c><00:44:31.839><c> was</c><00:44:32.000><c> referring</c><00:44:32.319><c> to</c><00:44:32.480><c> when</c><00:44:32.640><c> I</c><00:44:32.800><c> said</c>

u I was referring to when I said

u I was referring to when I said
quadrant<00:44:34.000><c> supports</c><00:44:34.480><c> that</c><00:44:34.880><c> matrix</c><00:44:35.440><c> multiplic</c>

quadrant supports that matrix multiplic

quadrant supports that matrix multiplic
uh<00:44:36.079><c> that</c><00:44:36.560><c> u</c><00:44:37.440><c> uh</c><00:44:38.079><c> late</c><00:44:38.400><c> interaction</c><00:44:38.880><c> thing</c>

uh that u uh late interaction thing

uh that u uh late interaction thing
right<00:44:39.599><c> so</c><00:44:39.839><c> it</c><00:44:40.079><c> says</c><00:44:40.960><c> I'm</c><00:44:41.280><c> setting</c><00:44:41.520><c> some</c>

right so it says I'm setting some

right so it says I'm setting some
configuration<00:44:42.319><c> that</c><00:44:42.640><c> it's</c><00:44:42.880><c> it</c><00:44:43.119><c> should</c><00:44:43.359><c> have</c>

configuration that it's it should have

configuration that it's it should have
multi<00:44:44.240><c> vector</c><00:44:44.560><c> configuration</c><00:44:45.280><c> and</c><00:44:46.079><c> multi</c>

multi vector configuration and multi

multi vector configuration and multi
vector<00:44:46.880><c> comparator</c><00:44:47.599><c> as</c><00:44:47.920><c> maxim.</c><00:44:48.560><c> So</c><00:44:48.800><c> maxim</c><00:44:49.280><c> is</c>

vector comparator as maxim. So maxim is

vector comparator as maxim. So maxim is
what<00:44:50.000><c> uh</c><00:44:50.240><c> helps</c><00:44:50.480><c> us</c><00:44:50.720><c> to</c><00:44:51.760><c> get</c><00:44:52.000><c> those</c><00:44:52.319><c> three</c>

what uh helps us to get those three

what uh helps us to get those three
numbers<00:44:52.960><c> from</c><00:44:53.200><c> that</c><00:44:53.440><c> matrix</c><00:44:53.920><c> and</c><00:44:54.240><c> then</c><00:44:54.720><c> add</c>

numbers from that matrix and then add

numbers from that matrix and then add
those<00:44:55.520><c> three</c><00:44:55.760><c> numbers</c><00:44:56.079><c> and</c><00:44:56.640><c> give</c><00:44:56.880><c> us</c><00:44:57.040><c> the</c>

those three numbers and give us the

those three numbers and give us the
final<00:44:58.160><c> value</c><00:44:58.640><c> of</c><00:44:59.359><c> the</c><00:44:59.599><c> your</c><00:45:00.079><c> query</c><00:45:00.720><c> and</c><00:45:01.119><c> each</c>

final value of the your query and each

final value of the your query and each
page.<00:45:02.240><c> So</c><00:45:02.400><c> that</c><00:45:02.640><c> at</c><00:45:02.880><c> the</c><00:45:02.960><c> end</c><00:45:03.040><c> of</c><00:45:03.119><c> the</c><00:45:03.280><c> day</c><00:45:03.440><c> what</c>

page. So that at the end of the day what

page. So that at the end of the day what
do<00:45:03.760><c> we</c><00:45:03.920><c> want?</c><00:45:04.319><c> We</c><00:45:04.480><c> want</c><00:45:04.640><c> the</c><00:45:04.880><c> relevant</c><00:45:05.200><c> pages</c>

do we want? We want the relevant pages

do we want? We want the relevant pages
uh<00:45:06.560><c> based</c><00:45:06.800><c> on</c><00:45:06.960><c> our</c><00:45:07.200><c> question,</c><00:45:07.760><c> right?</c>

uh based on our question, right?

uh based on our question, right?
Okay.

Okay.

Okay.
So<00:45:11.119><c> now</c><00:45:11.680><c> once</c><00:45:12.000><c> this</c><00:45:12.160><c> is</c><00:45:12.319><c> done,</c><00:45:13.040><c> it's</c><00:45:13.440><c> now</c>

So now once this is done, it's now

So now once this is done, it's now
pretty<00:45:14.000><c> simple.</c><00:45:14.880><c> I</c><00:45:15.119><c> have</c><00:45:15.280><c> to</c><00:45:16.160><c> uh</c><00:45:16.400><c> first</c><00:45:17.280><c> create</c>

pretty simple. I have to uh first create

pretty simple. I have to uh first create
the<00:45:18.319><c> embedding.</c><00:45:18.960><c> But</c><00:45:19.040><c> before</c><00:45:19.280><c> that,</c><00:45:19.920><c> I</c><00:45:20.160><c> need</c>

the embedding. But before that, I need

the embedding. But before that, I need
to<00:45:20.480><c> create</c><00:45:21.200><c> convert</c><00:45:21.760><c> my</c><00:45:22.079><c> data</c><00:45:22.400><c> into</c><00:45:22.800><c> images.</c>

to create convert my data into images.

to create convert my data into images.
And<00:45:23.680><c> that's</c><00:45:23.920><c> what</c><00:45:24.319><c> uh</c><00:45:24.480><c> this</c><00:45:24.960><c> uh</c><00:45:25.280><c> this</c><00:45:25.599><c> function</c>

And that's what uh this uh this function

And that's what uh this uh this function
does.<00:45:26.400><c> So</c><00:45:26.640><c> what</c><00:45:26.880><c> it</c><00:45:27.040><c> does</c><00:45:27.200><c> is</c><00:45:27.599><c> it</c><00:45:28.000><c> it</c><00:45:28.240><c> takes</c><00:45:28.480><c> you</c>

does. So what it does is it it takes you

does. So what it does is it it takes you
it<00:45:29.040><c> takes</c><00:45:29.280><c> an</c><00:45:29.680><c> uh</c><00:45:29.920><c> directory</c><00:45:30.720><c> and</c><00:45:31.119><c> you</c><00:45:31.359><c> can</c>

it takes an uh directory and you can

it takes an uh directory and you can
have<00:45:31.680><c> hundreds</c><00:45:32.079><c> of</c><00:45:32.240><c> PDF</c><00:45:32.640><c> files</c><00:45:33.359><c> and</c><00:45:33.680><c> it</c><00:45:33.839><c> will</c>

have hundreds of PDF files and it will

have hundreds of PDF files and it will
go<00:45:34.160><c> through</c><00:45:34.400><c> all</c><00:45:34.640><c> the</c><00:45:34.800><c> PDF</c><00:45:35.200><c> files</c><00:45:35.920><c> and</c><00:45:36.160><c> it</c><00:45:36.400><c> will</c>

go through all the PDF files and it will

go through all the PDF files and it will
create<00:45:38.000><c> uh</c><00:45:38.800><c> images</c><00:45:39.359><c> of</c><00:45:39.680><c> each</c><00:45:40.000><c> pages.</c><00:45:40.960><c> Okay.</c>

create uh images of each pages. Okay.

create uh images of each pages. Okay.
And<00:45:41.760><c> not</c><00:45:42.000><c> only</c><00:45:42.240><c> that,</c><00:45:42.720><c> it</c><00:45:43.040><c> will</c><00:45:43.280><c> also</c><00:45:44.720><c> add</c><00:45:45.040><c> all</c>

And not only that, it will also add all

And not only that, it will also add all
of<00:45:45.440><c> that</c><00:45:46.000><c> into</c><00:45:46.319><c> an</c><00:45:46.800><c> list</c><00:45:47.119><c> called</c><00:45:47.440><c> all</c><00:45:47.680><c> images.</c>

of that into an list called all images.

of that into an list called all images.
And<00:45:48.400><c> this</c><00:45:48.560><c> is</c><00:45:48.640><c> just</c><00:45:48.800><c> for</c><00:45:49.040><c> my</c><00:45:49.280><c> own</c><00:45:49.440><c> housekeeping</c>

And this is just for my own housekeeping

And this is just for my own housekeeping
with<00:45:50.560><c> some</c><00:45:50.720><c> metadata</c><00:45:51.359><c> like</c><00:45:51.680><c> document</c><00:45:52.240><c> ID,</c>

with some metadata like document ID,

with some metadata like document ID,
page<00:45:52.960><c> number</c><00:45:53.280><c> and</c><00:45:53.599><c> the</c><00:45:53.760><c> actual</c><00:45:54.160><c> image</c><00:45:54.480><c> in</c><00:45:54.640><c> the</c>

page number and the actual image in the

page number and the actual image in the
form<00:45:54.960><c> of</c><00:45:55.200><c> RGB.</c><00:45:56.560><c> And</c><00:45:56.880><c> it</c><00:45:57.119><c> will</c><00:45:57.280><c> store</c><00:45:57.440><c> it</c><00:45:57.599><c> in</c><00:45:57.760><c> a</c>

form of RGB. And it will store it in a

form of RGB. And it will store it in a
local<00:45:58.480><c> directory</c><00:45:58.880><c> called</c><00:45:59.280><c> PDF</c><00:45:59.760><c> data.</c><00:46:00.880><c> And</c><00:46:01.040><c> if</c>

local directory called PDF data. And if

local directory called PDF data. And if
you<00:46:01.520><c> just</c><00:46:01.760><c> see</c><00:46:01.920><c> the</c><00:46:02.160><c> first</c><00:46:02.319><c> two</c><00:46:02.480><c> entries,</c><00:46:02.960><c> you</c>

you just see the first two entries, you

you just see the first two entries, you
will<00:46:03.280><c> see</c><00:46:03.440><c> that</c><00:46:03.760><c> okay,</c><00:46:04.000><c> this</c><00:46:04.240><c> is</c><00:46:04.560><c> document</c>

will see that okay, this is document

will see that okay, this is document
number<00:46:05.359><c> zero</c><00:46:05.760><c> that</c><00:46:06.000><c> is</c><00:46:06.160><c> let's</c><00:46:06.400><c> say</c><00:46:06.560><c> I</c><00:46:06.800><c> just</c>

number zero that is let's say I just

number zero that is let's say I just
have<00:46:07.119><c> one</c><00:46:07.280><c> PDF.</c><00:46:08.160><c> So</c><00:46:08.480><c> all</c><00:46:08.720><c> the</c><00:46:09.359><c> entries</c><00:46:09.920><c> will</c>

have one PDF. So all the entries will

have one PDF. So all the entries will
have<00:46:10.400><c> document</c><00:46:10.800><c> ID</c><00:46:11.119><c> zero,</c><00:46:11.760><c> page</c><00:46:12.079><c> number</c><00:46:12.400><c> zero</c>

have document ID zero, page number zero

have document ID zero, page number zero
and<00:46:13.040><c> this</c><00:46:13.200><c> is</c><00:46:13.280><c> the</c><00:46:13.520><c> image</c><00:46:14.160><c> page</c><00:46:14.480><c> number</c><00:46:14.800><c> one</c>

and this is the image page number one

and this is the image page number one
and<00:46:15.359><c> this</c><00:46:15.520><c> is</c><00:46:15.599><c> the</c><00:46:15.839><c> image.</c><00:46:16.480><c> Okay.</c><00:46:17.119><c> So</c><00:46:17.680><c> this</c>

and this is the image. Okay. So this

and this is the image. Okay. So this
data<00:46:18.240><c> set</c><00:46:18.480><c> contains</c><00:46:19.359><c> everything</c><00:46:20.480><c> with</c><00:46:20.720><c> me</c><00:46:20.880><c> so</c>

data set contains everything with me so

data set contains everything with me so
far?<00:46:21.760><c> Yes.</c><00:46:22.160><c> Okay.</c><00:46:22.480><c> Great.</c><00:46:23.599><c> Now</c><00:46:23.839><c> that</c><00:46:24.079><c> I</c><00:46:24.319><c> have</c>

far? Yes. Okay. Great. Now that I have

far? Yes. Okay. Great. Now that I have
this<00:46:25.119><c> uh</c><00:46:26.319><c> uh</c><00:46:26.560><c> images,</c><00:46:27.760><c> I</c><00:46:28.000><c> can</c><00:46:28.160><c> use</c><00:46:28.400><c> the</c>

this uh uh images, I can use the

this uh uh images, I can use the
embedding<00:46:29.040><c> model</c><00:46:29.280><c> to</c><00:46:29.520><c> generate</c><00:46:29.839><c> the</c>

embedding model to generate the

embedding model to generate the
embedding<00:46:31.599><c> and</c>

embedding and

embedding and
and<00:46:33.520><c> this</c><00:46:33.760><c> is</c><00:46:33.920><c> where</c><00:46:34.560><c> uh</c><00:46:34.720><c> you</c><00:46:34.800><c> know</c><00:46:34.960><c> I</c><00:46:35.119><c> just</c>

and this is where uh you know I just

and this is where uh you know I just
crashed<00:46:35.680><c> my</c><00:46:35.839><c> laptop.</c><00:46:36.240><c> I</c><00:46:36.480><c> initially</c><00:46:37.040><c> used</c><00:46:37.280><c> a</c>

crashed my laptop. I initially used a

crashed my laptop. I initially used a
batch<00:46:37.839><c> size</c><00:46:38.000><c> of</c><00:46:38.240><c> 10</c><00:46:38.960><c> uh</c><00:46:39.520><c> 12.</c><00:46:40.400><c> So</c><00:46:40.560><c> it</c><00:46:40.720><c> took</c><00:46:40.880><c> a</c><00:46:41.200><c> lot</c>

batch size of 10 uh 12. So it took a lot

batch size of 10 uh 12. So it took a lot
of<00:46:41.440><c> memory</c><00:46:41.680><c> and</c><00:46:41.920><c> I</c><00:46:42.000><c> had</c><00:46:42.160><c> just</c><00:46:42.480><c> I</c><00:46:42.720><c> think</c><00:46:42.880><c> 16</c><00:46:43.119><c> gig</c>

of memory and I had just I think 16 gig

of memory and I had just I think 16 gig
of<00:46:43.599><c> memory.</c><00:46:43.920><c> So</c><00:46:45.119><c> it</c><00:46:45.680><c> it</c><00:46:45.920><c> actually</c><00:46:46.240><c> crashed</c><00:46:47.040><c> but</c>

of memory. So it it actually crashed but

of memory. So it it actually crashed but
uh<00:46:47.599><c> if</c><00:46:47.760><c> you're</c><00:46:47.920><c> trying</c><00:46:48.160><c> in</c><00:46:48.400><c> your</c><00:46:48.640><c> laptop</c><00:46:49.040><c> make</c>

uh if you're trying in your laptop make

uh if you're trying in your laptop make
sure<00:46:49.280><c> that</c><00:46:49.440><c> you</c><00:46:49.680><c> use</c><00:46:49.839><c> start</c><00:46:50.160><c> with</c><00:46:50.480><c> two</c><00:46:50.720><c> or</c>

sure that you use start with two or

sure that you use start with two or
three.<00:46:51.280><c> So</c><00:46:51.359><c> it</c><00:46:51.520><c> basically</c><00:46:51.839><c> means</c><00:46:52.079><c> how</c><00:46:52.240><c> many</c>

three. So it basically means how many

three. So it basically means how many
images<00:46:52.800><c> you</c><00:46:52.960><c> want</c><00:46:53.040><c> to</c><00:46:53.200><c> process.</c><00:46:54.480><c> And</c><00:46:54.720><c> now</c><00:46:55.200><c> here</c>

images you want to process. And now here

images you want to process. And now here
we<00:46:55.680><c> are</c><00:46:55.760><c> generating</c><00:46:56.079><c> the</c><00:46:56.240><c> embeddings</c><00:46:56.960><c> and</c>

we are generating the embeddings and

we are generating the embeddings and
first<00:46:58.400><c> we</c><00:46:58.720><c> are</c><00:47:00.160><c> going</c><00:47:00.400><c> through</c><00:47:00.640><c> this</c><00:47:01.839><c> call</c><00:47:02.160><c> pal</c>

first we are going through this call pal

first we are going through this call pal
pre-processor<00:47:04.000><c> which</c><00:47:04.240><c> will</c><00:47:04.480><c> just</c><00:47:04.720><c> uh</c>

pre-processor which will just uh

pre-processor which will just uh
pre-process<00:47:05.440><c> the</c><00:47:05.680><c> image</c><00:47:06.079><c> in</c><00:47:06.319><c> a</c><00:47:06.480><c> standard</c><00:47:07.119><c> uh</c>

pre-process the image in a standard uh

pre-process the image in a standard uh
size<00:47:07.920><c> and</c><00:47:08.160><c> then</c><00:47:08.319><c> I'm</c><00:47:08.640><c> passing</c><00:47:08.880><c> it</c><00:47:09.040><c> through</c><00:47:09.280><c> the</c>

size and then I'm passing it through the

size and then I'm passing it through the
call<00:47:09.760><c> pali</c><00:47:10.160><c> model</c><00:47:10.640><c> which</c><00:47:10.880><c> actually</c><00:47:11.200><c> generates</c>

call pali model which actually generates

call pali model which actually generates
the<00:47:11.680><c> embedding.</c><00:47:12.319><c> So</c><00:47:12.560><c> this</c><00:47:12.800><c> will</c><00:47:13.040><c> have</c><00:47:13.200><c> my</c>

the embedding. So this will have my

the embedding. So this will have my
embeddings.

embeddings.

embeddings.
And<00:47:15.920><c> once</c><00:47:16.319><c> I</c><00:47:16.640><c> have</c><00:47:17.040><c> all</c><00:47:17.280><c> those</c><00:47:17.839><c> uh</c><00:47:18.240><c> embeddings,</c>

And once I have all those uh embeddings,

And once I have all those uh embeddings,
what<00:47:19.920><c> I</c><00:47:20.160><c> want</c><00:47:20.319><c> to</c><00:47:20.480><c> do</c><00:47:20.640><c> is</c><00:47:20.880><c> I</c><00:47:21.200><c> want</c><00:47:21.280><c> to</c><00:47:22.000><c> store</c><00:47:22.240><c> it</c>

what I want to do is I want to store it

what I want to do is I want to store it
in<00:47:22.560><c> the</c><00:47:22.720><c> vector</c><00:47:23.040><c> database.</c><00:47:23.760><c> And</c><00:47:23.920><c> that</c><00:47:24.160><c> is</c><00:47:24.240><c> what</c>

in the vector database. And that is what

in the vector database. And that is what
I'm<00:47:24.720><c> doing</c><00:47:24.880><c> it</c><00:47:25.119><c> here.</c><00:47:25.599><c> I'm</c><00:47:25.920><c> just</c><00:47:26.160><c> inserting</c>

I'm doing it here. I'm just inserting

I'm doing it here. I'm just inserting
into<00:47:27.440><c> the</c><00:47:27.599><c> collection</c><00:47:27.920><c> that</c><00:47:28.079><c> I</c><00:47:28.240><c> have</c><00:47:28.400><c> created</c>

into the collection that I have created

into the collection that I have created
for<00:47:29.280><c> all</c><00:47:29.440><c> the</c><00:47:29.680><c> points.</c><00:47:30.640><c> Each</c><00:47:30.880><c> point</c><00:47:31.119><c> is</c>

for all the points. Each point is

for all the points. Each point is
nothing<00:47:31.599><c> but</c><00:47:31.839><c> you</c><00:47:32.079><c> can</c><00:47:32.160><c> think</c><00:47:32.319><c> of</c><00:47:32.400><c> it</c><00:47:32.560><c> like</c><00:47:33.280><c> uh</c>

nothing but you can think of it like uh

nothing but you can think of it like uh
each<00:47:34.560><c> vectors.</c><00:47:35.760><c> Okay.</c><00:47:37.040><c> And</c><00:47:38.079><c> in</c><00:47:38.400><c> this</c><00:47:38.560><c> case</c><00:47:38.960><c> I</c>

each vectors. Okay. And in this case I

each vectors. Okay. And in this case I
have<00:47:39.359><c> just</c><00:47:39.599><c> 10</c><00:47:39.920><c> pages.</c><00:47:40.319><c> So</c><00:47:40.560><c> it</c><00:47:40.720><c> will</c><00:47:40.880><c> just</c>

have just 10 pages. So it will just

have just 10 pages. So it will just
generate<00:47:41.280><c> the</c><00:47:41.680><c> amount</c><00:47:41.920><c> of</c><00:47:42.160><c> number</c><00:47:42.400><c> of</c>

generate the amount of number of

generate the amount of number of
embeddings<00:47:43.280><c> for</c><00:47:43.520><c> those</c><00:47:43.839><c> 10</c><00:47:44.079><c> pages</c><00:47:44.400><c> and</c><00:47:44.560><c> it</c>

embeddings for those 10 pages and it

embeddings for those 10 pages and it
will<00:47:44.880><c> store</c><00:47:45.119><c> it</c><00:47:45.280><c> here.</c><00:47:46.160><c> Now</c><00:47:46.480><c> is</c><00:47:46.720><c> the</c><00:47:46.960><c> final</c>

will store it here. Now is the final

will store it here. Now is the final
thing<00:47:47.599><c> you</c><00:47:47.760><c> know</c><00:47:47.920><c> how</c><00:47:48.240><c> we</c><00:47:48.480><c> can</c><00:47:48.800><c> retrieve.</c><00:47:50.079><c> So</c>

thing you know how we can retrieve. So

thing you know how we can retrieve. So
see<00:47:50.480><c> this</c><00:47:51.520><c> I</c><00:47:51.680><c> have</c><00:47:51.839><c> just</c><00:47:52.000><c> asked</c><00:47:52.240><c> this</c><00:47:52.560><c> question</c>

see this I have just asked this question

see this I have just asked this question
what<00:47:53.839><c> are</c><00:47:54.000><c> the</c><00:47:54.240><c> different</c><00:47:54.800><c> uh</c><00:47:55.040><c> tropical</c>

what are the different uh tropical

what are the different uh tropical
levels<00:47:56.000><c> because</c><00:47:56.240><c> this</c><00:47:56.400><c> is</c><00:47:56.560><c> there</c><00:47:56.800><c> in</c><00:47:56.960><c> the</c><00:47:57.119><c> book</c>

levels because this is there in the book

levels because this is there in the book
and<00:47:59.599><c> this</c><00:47:59.920><c> question</c><00:48:00.240><c> also</c><00:48:00.560><c> need</c><00:48:00.720><c> to</c><00:48:00.880><c> be</c><00:48:01.440><c> uh</c>

and this question also need to be uh

and this question also need to be uh
need<00:48:02.480><c> to</c><00:48:02.640><c> go</c><00:48:02.800><c> through</c><00:48:03.040><c> that</c><00:48:03.280><c> embedding</c><00:48:03.760><c> model</c>

need to go through that embedding model

need to go through that embedding model
just<00:48:04.640><c> like</c><00:48:04.960><c> images.</c><00:48:05.760><c> So</c><00:48:05.920><c> I</c><00:48:06.160><c> will</c><00:48:06.319><c> do</c><00:48:06.640><c> go</c><00:48:06.960><c> I'll</c>

just like images. So I will do go I'll

just like images. So I will do go I'll
make<00:48:07.599><c> that</c><00:48:07.839><c> through</c><00:48:08.319><c> the</c><00:48:08.800><c> pre-processor</c><00:48:09.839><c> and</c>

make that through the pre-processor and

make that through the pre-processor and
the<00:48:10.319><c> model</c><00:48:11.200><c> and</c><00:48:11.440><c> once</c><00:48:11.760><c> that</c><00:48:12.000><c> is</c><00:48:12.240><c> done</c><00:48:13.040><c> I</c><00:48:13.280><c> will</c>

the model and once that is done I will

the model and once that is done I will
do<00:48:13.520><c> a</c><00:48:13.680><c> semantic</c><00:48:14.079><c> search</c><00:48:14.319><c> from</c><00:48:14.480><c> the</c><00:48:14.640><c> vector</c>

do a semantic search from the vector

do a semantic search from the vector
database<00:48:16.000><c> and</c><00:48:16.240><c> that</c><00:48:16.480><c> is</c><00:48:16.560><c> what</c><00:48:16.720><c> we</c><00:48:16.960><c> are</c><00:48:17.119><c> doing</c>

database and that is what we are doing

database and that is what we are doing
we<00:48:17.599><c> are</c><00:48:17.760><c> just</c><00:48:17.920><c> querying</c><00:48:18.640><c> uh</c><00:48:18.720><c> the</c><00:48:18.880><c> vector</c>

we are just querying uh the vector

we are just querying uh the vector
database<00:48:19.680><c> with</c><00:48:19.920><c> our</c><00:48:20.240><c> query</c><00:48:20.640><c> token</c><00:48:21.680><c> and</c><00:48:22.160><c> I'm</c>

database with our query token and I'm

database with our query token and I'm
saying<00:48:22.720><c> that</c><00:48:23.200><c> the</c><00:48:23.440><c> limit</c><00:48:23.680><c> is</c><00:48:23.920><c> five</c><00:48:24.400><c> what</c><00:48:24.720><c> this</c>

saying that the limit is five what this

saying that the limit is five what this
limit<00:48:25.440><c> five</c><00:48:25.760><c> means</c><00:48:26.319><c> that</c><00:48:26.480><c> means</c><00:48:26.720><c> I</c><00:48:26.880><c> need</c><00:48:27.040><c> the</c>

limit five means that means I need the

limit five means that means I need the
top<00:48:27.599><c> five</c><00:48:27.920><c> pages</c><00:48:28.400><c> which</c><00:48:28.640><c> is</c><00:48:28.880><c> relevant</c><00:48:29.359><c> to</c><00:48:29.599><c> this</c>

top five pages which is relevant to this

top five pages which is relevant to this
uh<00:48:30.400><c> question</c>

uh question

uh question
and<00:48:33.119><c> at</c><00:48:33.359><c> the</c><00:48:33.440><c> end</c><00:48:33.599><c> you</c><00:48:33.839><c> will</c><00:48:34.000><c> find</c><00:48:34.240><c> some</c><00:48:34.800><c> five</c>

and at the end you will find some five

and at the end you will find some five
pages<00:48:35.359><c> is</c><00:48:36.559><c> and</c><00:48:36.720><c> if</c><00:48:36.880><c> you</c><00:48:37.040><c> want</c><00:48:37.119><c> to</c><00:48:37.280><c> see</c><00:48:37.839><c> those</c>

pages is and if you want to see those

pages is and if you want to see those
five<00:48:38.400><c> pages</c><00:48:38.800><c> how</c><00:48:39.040><c> it</c><00:48:39.440><c> uh</c><00:48:39.839><c> you</c><00:48:40.000><c> know</c><00:48:40.160><c> how</c><00:48:40.400><c> it</c>

five pages how it uh you know how it

five pages how it uh you know how it
looks<00:48:40.800><c> like</c><00:48:41.599><c> uh</c><00:48:41.680><c> you</c><00:48:41.920><c> can</c><00:48:42.079><c> actually</c>

looks like uh you can actually

looks like uh you can actually
visualize.<00:48:42.880><c> So</c><00:48:43.040><c> this</c><00:48:43.200><c> is</c><00:48:43.359><c> just</c><00:48:43.520><c> a</c><00:48:44.079><c> wrapper</c>

visualize. So this is just a wrapper

visualize. So this is just a wrapper
python<00:48:45.520><c> function</c><00:48:46.160><c> which</c><00:48:46.400><c> will</c><00:48:46.559><c> just</c><00:48:46.800><c> take</c><00:48:47.119><c> all</c>

python function which will just take all

python function which will just take all
the<00:48:47.599><c> images</c><00:48:48.160><c> and</c><00:48:48.480><c> it</c><00:48:48.720><c> will</c><00:48:48.880><c> just</c><00:48:49.040><c> generate</c><00:48:49.920><c> u</c>

the images and it will just generate u

the images and it will just generate u
the<00:48:50.400><c> images</c><00:48:51.200><c> in</c><00:48:51.440><c> a</c><00:48:51.599><c> pictorial</c><00:48:52.160><c> format.</c><00:48:52.640><c> Okay.</c>

the images in a pictorial format. Okay.

the images in a pictorial format. Okay.
And<00:48:53.359><c> in</c><00:48:53.599><c> fact</c><00:48:54.640><c> if</c><00:48:54.880><c> you</c><00:48:55.040><c> see</c><00:48:55.760><c> uh</c><00:48:56.400><c> the</c><00:48:56.800><c> this</c><00:48:57.200><c> image</c>

And in fact if you see uh the this image

And in fact if you see uh the this image
I<00:48:58.000><c> think</c><00:48:58.160><c> this</c><00:48:58.400><c> was</c><00:48:58.880><c> uh</c><00:49:00.319><c> this</c><00:49:00.559><c> was</c><00:49:00.720><c> the</c><00:49:00.960><c> image</c><00:49:01.200><c> I</c>

I think this was uh this was the image I

I think this was uh this was the image I
guess<00:49:01.920><c> uh</c><00:49:03.200><c> yeah</c><00:49:04.319><c> so</c><00:49:04.559><c> this</c><00:49:04.800><c> is</c><00:49:04.880><c> where</c><00:49:05.040><c> the</c>

guess uh yeah so this is where the

guess uh yeah so this is where the
tropical<00:49:05.599><c> levels</c><00:49:05.920><c> are</c><00:49:06.079><c> mentioned</c><00:49:06.640><c> it</c>

tropical levels are mentioned it

tropical levels are mentioned it
actually<00:49:07.280><c> identified</c><00:49:07.680><c> based</c><00:49:07.839><c> on</c><00:49:08.000><c> the</c>

actually identified based on the

actually identified based on the
question<00:49:09.040><c> and</c><00:49:09.359><c> the</c><00:49:10.079><c> uh</c><00:49:10.480><c> call</c><00:49:11.040><c> embeddings</c>

question and the uh call embeddings

question and the uh call embeddings
right<00:49:12.000><c> so</c><00:49:12.160><c> this</c><00:49:12.319><c> is</c><00:49:12.400><c> the</c><00:49:12.559><c> page</c><00:49:12.720><c> and</c><00:49:12.880><c> also</c><00:49:13.119><c> there</c>

right so this is the page and also there

right so this is the page and also there
are<00:49:13.440><c> other</c><00:49:13.599><c> pages</c><00:49:14.000><c> which</c><00:49:14.240><c> we</c><00:49:14.400><c> got</c><00:49:15.440><c> now</c><00:49:15.760><c> comes</c>

are other pages which we got now comes

are other pages which we got now comes
so<00:49:16.640><c> retrieval</c><00:49:17.119><c> is</c><00:49:17.280><c> done</c><00:49:17.520><c> right</c><00:49:17.920><c> so</c><00:49:18.240><c> call</c><00:49:18.559><c> pal</c>

so retrieval is done right so call pal

so retrieval is done right so call pal
just<00:49:19.119><c> talks</c><00:49:19.440><c> about</c><00:49:19.599><c> retrieval</c><00:49:20.160><c> it's</c><00:49:20.559><c> its</c><00:49:21.200><c> job</c>

just talks about retrieval it's its job

just talks about retrieval it's its job
ends<00:49:22.559><c> here.</c><00:49:23.599><c> Okay.</c><00:49:24.400><c> And</c><00:49:24.800><c> uh</c><00:49:24.880><c> if</c><00:49:25.040><c> you</c><00:49:25.200><c> if</c><00:49:25.440><c> you</c>

ends here. Okay. And uh if you if you

ends here. Okay. And uh if you if you
think<00:49:25.760><c> about</c><00:49:25.920><c> it</c>

think about it

think about it
uh<00:49:28.319><c> with</c><00:49:28.640><c> respect</c><00:49:29.040><c> to</c><00:49:29.680><c> uh</c><00:49:29.839><c> sorry</c><00:49:31.040><c> with</c><00:49:31.359><c> respect</c>

uh with respect to uh sorry with respect

uh with respect to uh sorry with respect
to<00:49:31.920><c> this</c>

to this

to this
sorry<00:49:34.960><c> here</c><00:49:35.200><c> I</c><00:49:35.440><c> guess</c>

sorry here I guess

sorry here I guess
in<00:49:37.440><c> the</c><00:49:37.599><c> traditional</c><00:49:38.079><c> technique</c>

in the traditional technique

in the traditional technique
we<00:49:41.040><c> came</c><00:49:41.200><c> to</c><00:49:41.440><c> this</c><00:49:41.599><c> point</c><00:49:41.920><c> right</c>

we came to this point right

we came to this point right
uh<00:49:43.680><c> we</c><00:49:43.920><c> came</c><00:49:44.160><c> to</c><00:49:44.319><c> this</c><00:49:44.559><c> point</c><00:49:45.040><c> sorry</c>

we<00:49:50.640><c> came</c><00:49:50.880><c> to</c><00:49:51.040><c> this</c><00:49:51.280><c> point</c><00:49:51.839><c> when</c><00:49:52.079><c> we</c><00:49:52.319><c> got</c><00:49:52.480><c> the</c>

we came to this point when we got the

we came to this point when we got the
retrieved<00:49:53.920><c> images</c><00:49:54.559><c> and</c><00:49:54.880><c> the</c><00:49:55.040><c> question</c><00:49:55.280><c> is</c>

retrieved images and the question is

retrieved images and the question is
already<00:49:55.760><c> there.</c><00:49:56.319><c> Now</c><00:49:56.480><c> we</c><00:49:56.720><c> can</c><00:49:56.880><c> use</c><00:49:57.119><c> any</c>

already there. Now we can use any

already there. Now we can use any
multimodal<00:49:58.319><c> LLM</c><00:49:58.800><c> to</c><00:49:58.960><c> generate</c><00:49:59.280><c> the</c><00:49:59.520><c> answer.</c>

multimodal LLM to generate the answer.

multimodal LLM to generate the answer.
Right?<00:50:00.880><c> But</c><00:50:01.040><c> we</c><00:50:01.200><c> have</c><00:50:01.440><c> skipped</c><00:50:01.760><c> everything</c>

Right? But we have skipped everything

Right? But we have skipped everything
here.<00:50:03.520><c> Right?</c><00:50:04.319><c> So</c>

here. Right? So

here. Right? So
now<00:50:06.240><c> when</c><00:50:06.559><c> we</c><00:50:06.880><c> when</c><00:50:07.200><c> we</c><00:50:07.440><c> use</c><00:50:08.880><c> any</c><00:50:09.280><c> generative</c>

now when we when we use any generative

now when we when we use any generative
model<00:50:10.160><c> you</c><00:50:10.400><c> can</c><00:50:10.559><c> use</c><00:50:10.720><c> any</c><00:50:11.040><c> generative</c><00:50:11.440><c> model</c>

model you can use any generative model

model you can use any generative model
of<00:50:11.920><c> your</c><00:50:12.079><c> choice.</c><00:50:13.119><c> Uh</c><00:50:13.920><c> if</c><00:50:14.160><c> you</c><00:50:14.240><c> don't</c><00:50:14.400><c> have</c><00:50:14.480><c> any</c>

of your choice. Uh if you don't have any

of your choice. Uh if you don't have any
AWS<00:50:15.280><c> account</c><00:50:15.520><c> or</c><00:50:16.240><c> if</c><00:50:16.480><c> you</c><00:50:16.640><c> have</c><00:50:16.800><c> any</c><00:50:17.040><c> other</c><00:50:18.000><c> uh</c>

AWS account or if you have any other uh

AWS account or if you have any other uh
model<00:50:18.880><c> access</c><00:50:19.200><c> you</c><00:50:19.359><c> can</c><00:50:19.520><c> always</c><00:50:19.760><c> use</c><00:50:19.920><c> that.</c><00:50:21.359><c> uh</c>

model access you can always use that. uh

model access you can always use that. uh
but<00:50:22.079><c> let's</c><00:50:22.400><c> say</c><00:50:23.359><c> uh</c><00:50:23.839><c> you</c><00:50:24.160><c> don't</c><00:50:24.400><c> have</c><00:50:25.200><c> bedrock</c>

but let's say uh you don't have bedrock

but let's say uh you don't have bedrock
access<00:50:26.880><c> so</c><00:50:27.119><c> we</c><00:50:27.359><c> can</c><00:50:27.520><c> use</c><00:50:28.319><c> have</c><00:50:28.480><c> you</c><00:50:28.559><c> used</c><00:50:29.680><c> just</c>

access so we can use have you used just

access so we can use have you used just
a<00:50:30.240><c> local</c><00:50:30.480><c> model</c><00:50:30.880><c> the</c><00:50:31.119><c> response</c><00:50:31.520><c> may</c><00:50:31.680><c> not</c><00:50:31.760><c> be</c>

a local model the response may not be

a local model the response may not be
that<00:50:32.160><c> great</c><00:50:32.480><c> but</c><00:50:32.800><c> you</c><00:50:32.960><c> can</c><00:50:33.119><c> work</c><00:50:33.359><c> it</c><00:50:33.520><c> out</c><00:50:33.839><c> right</c>

that great but you can work it out right

that great but you can work it out right
so<00:50:34.960><c> this</c><00:50:35.119><c> is</c><00:50:35.359><c> again</c><00:50:35.599><c> a</c><00:50:35.760><c> wrapper</c><00:50:36.160><c> function</c><00:50:36.880><c> just</c>

so this is again a wrapper function just

so this is again a wrapper function just
to<00:50:38.079><c> uh</c><00:50:38.480><c> convert</c><00:50:38.960><c> all</c><00:50:39.280><c> the</c><00:50:39.520><c> images</c><00:50:40.480><c> uh</c><00:50:40.640><c> into</c><00:50:40.880><c> the</c>

to uh convert all the images uh into the

to uh convert all the images uh into the
format<00:50:41.680><c> that</c><00:50:42.000><c> the</c><00:50:42.240><c> model</c><00:50:42.559><c> expects</c><00:50:42.960><c> because</c><00:50:43.200><c> we</c>

format that the model expects because we

format that the model expects because we
are<00:50:43.760><c> we</c><00:50:44.000><c> need</c><00:50:44.160><c> a</c><00:50:44.319><c> multimodal</c><00:50:45.200><c> LLM</c><00:50:45.839><c> right</c><00:50:46.079><c> so</c><00:50:46.319><c> we</c>

are we need a multimodal LLM right so we

are we need a multimodal LLM right so we
will<00:50:46.720><c> take</c><00:50:46.880><c> some</c><00:50:47.040><c> multimodal</c><00:50:47.599><c> LLM</c><00:50:48.000><c> from</c><00:50:48.160><c> Olama</c>

will take some multimodal LLM from Olama

will take some multimodal LLM from Olama
but<00:50:49.760><c> depending</c><00:50:50.079><c> on</c><00:50:50.240><c> what</c><00:50:50.559><c> model</c><00:50:50.800><c> you're</c>

but depending on what model you're

but depending on what model you're
using.<00:50:51.520><c> The</c><00:50:51.680><c> model</c><00:50:52.000><c> will</c><00:50:52.160><c> ask</c><00:50:52.400><c> you</c><00:50:52.800><c> to</c><00:50:53.359><c> have</c>

using. The model will ask you to have

using. The model will ask you to have
the<00:50:53.760><c> input</c><00:50:54.000><c> in</c><00:50:54.160><c> a</c><00:50:54.319><c> certain</c><00:50:54.800><c> uh</c><00:50:54.960><c> format,</c><00:50:55.440><c> right?</c>

the input in a certain uh format, right?

the input in a certain uh format, right?
So<00:50:56.240><c> it</c><00:50:56.480><c> needs</c><00:50:56.720><c> the</c><00:50:56.960><c> data</c><00:50:57.119><c> to</c><00:50:57.359><c> be</c><00:50:57.440><c> in</c><00:50:57.680><c> base</c><00:50:57.920><c> 64.</c>

So it needs the data to be in base 64.

So it needs the data to be in base 64.
That's<00:50:58.640><c> what</c><00:50:58.880><c> this</c><00:50:59.280><c> small</c><00:50:59.680><c> tiny</c><00:51:00.079><c> function</c>

That's what this small tiny function

That's what this small tiny function
does,<00:51:00.800><c> right?</c><00:51:01.520><c> Uh</c><00:51:02.000><c> and</c><00:51:02.240><c> then</c><00:51:03.280><c> we</c><00:51:03.520><c> just</c><00:51:03.760><c> say</c>

does, right? Uh and then we just say

does, right? Uh and then we just say
generate<00:51:05.680><c> and</c><00:51:05.920><c> this</c><00:51:06.079><c> is</c><00:51:06.160><c> the</c><00:51:06.319><c> model</c><00:51:06.559><c> that</c><00:51:06.720><c> I'm</c>

generate and this is the model that I'm

generate and this is the model that I'm
using<00:51:08.240><c> and</c><00:51:08.480><c> I'm</c><00:51:08.720><c> sending</c><00:51:09.040><c> the</c><00:51:09.280><c> query</c><00:51:10.079><c> and</c><00:51:10.400><c> the</c>

using and I'm sending the query and the

using and I'm sending the query and the
image<00:51:11.200><c> that's</c><00:51:11.440><c> all</c><00:51:12.319><c> right.</c><00:51:12.800><c> So</c><00:51:13.040><c> see</c><00:51:13.200><c> this</c><00:51:13.440><c> now</c>

image that's all right. So see this now

image that's all right. So see this now
I'm<00:51:13.839><c> sending</c><00:51:14.079><c> the</c><00:51:14.319><c> full</c><00:51:14.480><c> query,</c><00:51:14.800><c> not</c><00:51:14.960><c> the</c>

I'm sending the full query, not the

I'm sending the full query, not the
embedding<00:51:15.440><c> of</c><00:51:15.520><c> the</c><00:51:15.680><c> query</c><00:51:16.160><c> because</c><00:51:16.480><c> Olama</c><00:51:17.040><c> has</c>

embedding of the query because Olama has

embedding of the query because Olama has
nothing<00:51:17.359><c> to</c><00:51:17.440><c> do</c><00:51:17.520><c> with</c><00:51:17.680><c> that</c><00:51:17.839><c> embedding</c><00:51:18.240><c> of</c><00:51:18.319><c> the</c>

nothing to do with that embedding of the

nothing to do with that embedding of the
query.<00:51:19.280><c> that</c><00:51:19.520><c> embedding</c><00:51:19.920><c> was</c><00:51:20.079><c> needed</c><00:51:20.400><c> just</c>

query. that embedding was needed just

query. that embedding was needed just
for<00:51:20.880><c> semantic</c><00:51:21.359><c> search</c><00:51:22.400><c> right</c><00:51:23.119><c> and</c><00:51:23.359><c> then</c><00:51:23.680><c> uh</c><00:51:23.839><c> we</c>

for semantic search right and then uh we

for semantic search right and then uh we
get<00:51:24.319><c> some</c><00:51:24.720><c> response</c><00:51:26.160><c> if</c><00:51:26.400><c> you</c><00:51:26.559><c> want</c><00:51:26.640><c> to</c><00:51:26.800><c> use</c>

get some response if you want to use

get some response if you want to use
bedrock<00:51:28.240><c> then</c><00:51:28.480><c> you</c><00:51:28.640><c> should</c><00:51:28.800><c> have</c><00:51:28.880><c> bedrock</c>

bedrock then you should have bedrock

bedrock then you should have bedrock
access<00:51:29.839><c> how</c><00:51:30.000><c> many</c><00:51:30.079><c> of</c><00:51:30.240><c> you</c><00:51:30.400><c> know</c><00:51:30.480><c> about</c>

access how many of you know about

access how many of you know about
bedrock

bedrock

bedrock
okay<00:51:32.720><c> perfect</c><00:51:33.040><c> so</c><00:51:33.280><c> it's</c><00:51:33.440><c> just</c><00:51:33.599><c> a</c><00:51:33.920><c> managed</c>

okay perfect so it's just a managed

okay perfect so it's just a managed
service<00:51:34.559><c> on</c><00:51:34.800><c> AWS</c><00:51:35.520><c> through</c><00:51:35.760><c> which</c><00:51:36.000><c> you</c><00:51:36.160><c> can</c>

service on AWS through which you can

service on AWS through which you can
access<00:51:36.480><c> any</c><00:51:36.800><c> different</c><00:51:37.040><c> I</c><00:51:37.280><c> mean</c><00:51:37.440><c> different</c>

access any different I mean different

access any different I mean different
kinds<00:51:37.920><c> of</c><00:51:38.079><c> model</c><00:51:39.440><c> and</c>

kinds of model and

kinds of model and
the<00:51:41.280><c> way</c><00:51:41.440><c> that</c><00:51:41.920><c> bedrock</c><00:51:42.720><c> expects</c><00:51:43.200><c> you</c><00:51:43.440><c> to</c><00:51:43.599><c> give</c>

the way that bedrock expects you to give

the way that bedrock expects you to give
the<00:51:45.280><c> input</c><00:51:46.079><c> uh</c><00:51:46.400><c> multimodel</c><00:51:47.040><c> input</c><00:51:47.359><c> is</c><00:51:47.680><c> little</c>

the input uh multimodel input is little

the input uh multimodel input is little
different<00:51:48.319><c> and</c><00:51:48.559><c> that's</c><00:51:48.720><c> That's</c><00:51:48.800><c> why</c><00:51:48.960><c> we</c><00:51:49.119><c> have</c>

different and that's That's why we have

different and that's That's why we have
some<00:51:49.440><c> wrapper</c><00:51:49.839><c> functions</c><00:51:50.720><c> uh</c><00:51:50.800><c> which</c><00:51:51.040><c> will</c>

some wrapper functions uh which will

some wrapper functions uh which will
which<00:51:52.880><c> will</c><00:51:53.119><c> make</c><00:51:53.280><c> your</c><00:51:53.520><c> prompt</c><00:51:54.880><c> you</c><00:51:55.040><c> know</c>

which will make your prompt you know

which will make your prompt you know
according<00:51:55.520><c> to</c><00:51:55.599><c> the</c><00:51:55.839><c> multimodal</c><00:51:57.040><c> uh</c><00:51:57.359><c> models</c>

according to the multimodal uh models

according to the multimodal uh models
requirement<00:51:58.319><c> right</c><00:51:59.200><c> and</c><00:52:00.160><c> you</c><00:52:00.400><c> can</c><00:52:00.559><c> go</c><00:52:00.800><c> through</c>

requirement right and you can go through

requirement right and you can go through
these<00:52:01.200><c> two</c><00:52:01.359><c> functions</c><00:52:01.760><c> it's</c><00:52:02.079><c> standard</c><00:52:03.200><c> uh</c><00:52:03.359><c> you</c>

these two functions it's standard uh you

these two functions it's standard uh you
know<00:52:03.920><c> uh</c><00:52:04.559><c> converse</c><00:52:05.040><c> API</c><00:52:05.359><c> that</c><00:52:05.599><c> we</c><00:52:05.680><c> have</c><00:52:05.839><c> used</c>

know uh converse API that we have used

know uh converse API that we have used
so<00:52:06.400><c> nothing</c><00:52:06.640><c> fancy</c><00:52:06.960><c> here</c><00:52:07.119><c> so</c><00:52:07.280><c> I</c><00:52:07.359><c> don't</c><00:52:07.520><c> want</c><00:52:07.599><c> to</c>

so nothing fancy here so I don't want to

so nothing fancy here so I don't want to
go<00:52:07.839><c> there</c><00:52:08.240><c> because</c><00:52:08.480><c> that</c><00:52:08.720><c> is</c><00:52:08.960><c> not</c><00:52:09.200><c> the</c><00:52:09.359><c> purpose</c>

go there because that is not the purpose

go there because that is not the purpose
of<00:52:09.839><c> this</c><00:52:10.800><c> uh</c><00:52:11.040><c> problem</c><00:52:12.000><c> but</c><00:52:12.960><c> ultimately</c><00:52:13.440><c> you</c>

of this uh problem but ultimately you

of this uh problem but ultimately you
give<00:52:13.839><c> the</c><00:52:14.960><c> images</c><00:52:15.359><c> and</c><00:52:15.599><c> the</c><00:52:15.839><c> query</c><00:52:16.319><c> and</c><00:52:16.640><c> you</c>

give the images and the query and you

give the images and the query and you
mention<00:52:17.119><c> the</c><00:52:17.280><c> model</c><00:52:17.599><c> ID</c><00:52:17.760><c> so</c><00:52:17.920><c> in</c><00:52:18.079><c> this</c><00:52:18.160><c> case</c><00:52:18.400><c> I'm</c>

mention the model ID so in this case I'm

mention the model ID so in this case I'm
using<00:52:18.800><c> set</c><00:52:19.680><c> uh</c><00:52:20.000><c> claude</c><00:52:20.480><c> sonnet</c><00:52:20.960><c> 3.7.</c><00:52:21.839><c> You</c><00:52:22.000><c> can</c>

using set uh claude sonnet 3.7. You can

using set uh claude sonnet 3.7. You can
very<00:52:22.319><c> well</c><00:52:22.480><c> use</c><00:52:22.960><c> sonet</c><00:52:23.359><c> 4</c><00:52:23.520><c> if</c><00:52:23.680><c> you</c><00:52:23.760><c> would</c><00:52:23.920><c> like</c>

very well use sonet 4 if you would like

very well use sonet 4 if you would like
to.<00:52:24.800><c> And</c><00:52:25.040><c> you</c><00:52:25.280><c> generate</c><00:52:25.599><c> the</c><00:52:25.839><c> image</c><00:52:26.480><c> uh</c><00:52:26.640><c> sorry</c>

to. And you generate the image uh sorry

to. And you generate the image uh sorry
the<00:52:27.200><c> final</c><00:52:27.440><c> response.</c><00:52:28.720><c> Okay</c><00:52:30.160><c> with</c><00:52:30.400><c> me</c><00:52:30.640><c> so</c><00:52:30.880><c> far?</c>

the final response. Okay with me so far?

the final response. Okay with me so far?
Okay.<00:52:32.559><c> Now</c><00:52:32.800><c> comes</c><00:52:33.200><c> the</c><00:52:33.599><c> agent</c><00:52:34.079><c> thing.</c><00:52:34.800><c> How</c><00:52:35.040><c> we</c>

Okay. Now comes the agent thing. How we

Okay. Now comes the agent thing. How we
can<00:52:35.760><c> make</c><00:52:36.000><c> this</c><00:52:36.559><c> agentic?</c><00:52:37.920><c> So</c><00:52:38.079><c> it's</c><00:52:38.319><c> very</c>

can make this agentic? So it's very

can make this agentic? So it's very
simple,<00:52:38.720><c> right?</c><00:52:39.040><c> You</c><00:52:39.280><c> don't</c><00:52:39.359><c> have</c><00:52:39.520><c> to</c><00:52:39.680><c> go</c>

simple, right? You don't have to go

simple, right? You don't have to go
through<00:52:40.319><c> all</c><00:52:40.559><c> these</c><00:52:40.880><c> things</c><00:52:41.520><c> because</c><00:52:41.920><c> what</c><00:52:42.160><c> we</c>

through all these things because what we

through all these things because what we
have<00:52:42.480><c> done</c><00:52:42.720><c> is</c><00:52:43.440><c> ultimately</c><00:52:43.839><c> what</c><00:52:44.079><c> we</c><00:52:44.319><c> want</c>

have done is ultimately what we want

have done is ultimately what we want
when<00:52:45.119><c> somebody</c><00:52:45.440><c> is</c><00:52:45.680><c> asking</c><00:52:45.920><c> a</c><00:52:46.160><c> question</c><00:52:46.559><c> we</c>

when somebody is asking a question we

when somebody is asking a question we
want<00:52:48.240><c> an</c><00:52:48.480><c> agent</c><00:52:49.520><c> to</c><00:52:49.920><c> to</c><00:52:51.280><c> retrieve</c><00:52:51.839><c> the</c>

want an agent to to retrieve the

want an agent to to retrieve the
shortlisted<00:52:53.280><c> images</c><00:52:53.839><c> and</c><00:52:54.160><c> give</c><00:52:54.319><c> it</c><00:52:54.400><c> to</c><00:52:54.559><c> me.</c>

shortlisted images and give it to me.

shortlisted images and give it to me.
That's<00:52:54.960><c> all.</c><00:52:55.760><c> Right?</c><00:52:56.400><c> So</c><00:52:56.720><c> we</c><00:52:56.960><c> have</c><00:52:57.119><c> seen</c><00:52:57.359><c> how</c>

That's all. Right? So we have seen how

That's all. Right? So we have seen how
to<00:52:57.760><c> shortlist</c><00:52:58.240><c> those</c><00:52:58.400><c> images.</c><00:52:58.880><c> Right?</c><00:52:59.760><c> What</c>

to shortlist those images. Right? What

to shortlist those images. Right? What
we<00:53:00.160><c> are</c><00:53:00.240><c> going</c><00:53:00.319><c> to</c><00:53:00.480><c> do</c><00:53:00.720><c> is</c>

we are going to do is

we are going to do is
uh<00:53:03.359><c> here</c>

I'll<00:53:09.440><c> just</c><00:53:09.599><c> go</c><00:53:09.760><c> through</c><00:53:10.000><c> that</c><00:53:10.240><c> later.</c><00:53:10.640><c> Yeah,</c>

I'll just go through that later. Yeah,

I'll just go through that later. Yeah,
what<00:53:11.520><c> we</c><00:53:11.760><c> going</c><00:53:11.839><c> to</c><00:53:11.920><c> do</c><00:53:12.079><c> is</c><00:53:12.640><c> we</c><00:53:12.880><c> are</c><00:53:13.040><c> going</c><00:53:13.119><c> to</c>

what we going to do is we are going to

what we going to do is we are going to
create<00:53:14.000><c> a</c><00:53:14.319><c> function</c><00:53:14.800><c> called</c><00:53:15.119><c> retrieve</c><00:53:15.520><c> from</c>

create a function called retrieve from

create a function called retrieve from
quadrant<00:53:16.319><c> which</c><00:53:16.559><c> will</c><00:53:16.800><c> just</c><00:53:16.960><c> take</c><00:53:18.000><c> your</c><00:53:18.319><c> query</c>

quadrant which will just take your query

quadrant which will just take your query
and<00:53:19.680><c> if</c><00:53:19.920><c> you</c><00:53:20.000><c> see</c><00:53:20.160><c> the</c><00:53:21.119><c> uh</c><00:53:22.000><c> uh</c><00:53:22.319><c> return</c><00:53:23.040><c> for</c><00:53:23.359><c> this</c>

and if you see the uh uh return for this

and if you see the uh uh return for this
are<00:53:24.240><c> the</c><00:53:24.480><c> matched</c><00:53:24.960><c> image</c><00:53:25.280><c> paths</c><00:53:25.760><c> that</c><00:53:26.000><c> is</c><00:53:26.079><c> what</c>

are the matched image paths that is what

are the matched image paths that is what
we<00:53:26.400><c> want</c><00:53:27.440><c> nothing</c><00:53:27.680><c> else</c><00:53:28.000><c> right</c><00:53:28.400><c> and</c><00:53:28.640><c> the</c><00:53:28.800><c> code</c>

we want nothing else right and the code

we want nothing else right and the code
here<00:53:29.280><c> in</c><00:53:29.520><c> this</c><00:53:29.680><c> function</c><00:53:30.000><c> are</c><00:53:30.240><c> the</c><00:53:30.480><c> exact</c><00:53:30.720><c> same</c>

here in this function are the exact same

here in this function are the exact same
code<00:53:31.200><c> which</c><00:53:31.680><c> has</c><00:53:31.920><c> gone</c><00:53:32.160><c> through</c><00:53:32.319><c> in</c><00:53:32.480><c> multiple</c>

code which has gone through in multiple

code which has gone through in multiple
cells<00:53:33.680><c> you</c><00:53:33.839><c> know</c><00:53:34.240><c> previously</c><00:53:35.440><c> it</c><00:53:35.680><c> just</c><00:53:36.000><c> it</c>

cells you know previously it just it

cells you know previously it just it
does<00:53:36.400><c> the</c><00:53:36.640><c> same</c><00:53:36.880><c> thing</c><00:53:38.240><c> and</c><00:53:38.559><c> now</c><00:53:38.880><c> to</c><00:53:39.119><c> make</c><00:53:39.280><c> it</c>

does the same thing and now to make it

does the same thing and now to make it
agentic

agentic

agentic
I<00:53:41.119><c> have</c><00:53:41.280><c> used</c><00:53:41.920><c> a</c><00:53:42.480><c> framework</c><00:53:42.880><c> called</c><00:53:43.280><c> strands.</c>

I have used a framework called strands.

I have used a framework called strands.
Have<00:53:43.839><c> you</c><00:53:43.920><c> heard</c><00:53:44.000><c> of</c><00:53:44.160><c> strands?</c><00:53:45.280><c> Right.</c><00:53:45.599><c> Okay.</c>

Have you heard of strands? Right. Okay.

Have you heard of strands? Right. Okay.
So<00:53:46.160><c> strands</c><00:53:46.720><c> is</c><00:53:46.960><c> a</c><00:53:47.599><c> new</c><00:53:47.920><c> agentic</c><00:53:48.559><c> framework.</c>

So strands is a new agentic framework.

So strands is a new agentic framework.
Let<00:53:49.440><c> me</c><00:53:49.599><c> just</c><00:53:49.760><c> show</c><00:53:49.920><c> you</c><00:53:50.079><c> this.</c><00:53:51.119><c> It's</c>

Let me just show you this. It's

Let me just show you this. It's
strandsagent.com.

strandsagent.com.

strandsagent.com.
This<00:53:54.160><c> is</c><00:53:54.240><c> a</c><00:53:55.440><c> uh</c><00:53:55.680><c> SDK</c><00:53:56.160><c> which</c><00:53:56.319><c> was</c><00:53:56.480><c> launched</c><00:53:56.720><c> by</c>

This is a uh SDK which was launched by

This is a uh SDK which was launched by
AWS.<00:53:57.599><c> Uh</c><00:53:57.920><c> I</c><00:53:58.160><c> worked</c><00:53:58.400><c> with</c><00:53:58.800><c> on</c><00:53:59.359><c> at</c><00:53:59.599><c> the</c><00:53:59.760><c> launch.</c>

AWS. Uh I worked with on at the launch.

AWS. Uh I worked with on at the launch.
There<00:54:00.640><c> are</c><00:54:00.800><c> some</c><00:54:00.960><c> YouTube</c><00:54:01.280><c> video</c><00:54:01.520><c> as</c><00:54:01.760><c> well.</c><00:54:02.720><c> Uh</c>

There are some YouTube video as well. Uh

There are some YouTube video as well. Uh
you<00:54:03.200><c> can</c><00:54:03.359><c> just</c><00:54:03.599><c> go</c><00:54:03.760><c> over</c><00:54:04.000><c> and</c><00:54:04.240><c> just</c><00:54:04.400><c> search</c><00:54:04.559><c> for</c>

you can just go over and just search for

you can just go over and just search for
strands<00:54:05.200><c> agents.</c><00:54:05.920><c> You</c><00:54:06.079><c> will</c><00:54:06.240><c> find</c><00:54:06.400><c> a</c><00:54:06.720><c> launch</c>

strands agents. You will find a launch

strands agents. You will find a launch
blog<00:54:07.440><c> as</c><00:54:07.599><c> well.</c><00:54:07.920><c> Okay.</c><00:54:08.160><c> But</c><00:54:08.400><c> basically</c><00:54:09.200><c> it</c><00:54:09.440><c> is</c>

blog as well. Okay. But basically it is

blog as well. Okay. But basically it is
very<00:54:09.760><c> very</c><00:54:10.000><c> simple</c><00:54:10.319><c> just</c><00:54:10.559><c> to</c><00:54:11.040><c> give</c><00:54:11.280><c> you</c><00:54:11.440><c> an</c>

very very simple just to give you an

very very simple just to give you an
example<00:54:12.559><c> how</c><00:54:12.960><c> to</c><00:54:13.200><c> get</c><00:54:13.359><c> started</c><00:54:13.680><c> with</c><00:54:13.920><c> strands.</c>

example how to get started with strands.

example how to get started with strands.
Uh<00:54:16.319><c> you</c><00:54:16.559><c> just</c><00:54:16.720><c> pip</c><00:54:17.040><c> install</c>

Uh you just pip install

Uh you just pip install
and<00:54:19.520><c> uh</c><00:54:19.760><c> do</c><00:54:19.920><c> you</c><00:54:20.079><c> want</c><00:54:20.160><c> to</c><00:54:20.240><c> see</c><00:54:20.319><c> a</c><00:54:20.480><c> quick</c><00:54:20.640><c> demo</c>

and uh do you want to see a quick demo

and uh do you want to see a quick demo
of<00:54:21.040><c> strands</c><00:54:21.440><c> before</c><00:54:21.680><c> we</c><00:54:22.000><c> go</c><00:54:22.160><c> to</c><00:54:22.319><c> that</c><00:54:22.800><c> part?</c>

of strands before we go to that part?

of strands before we go to that part?
Will<00:54:23.440><c> that</c><00:54:23.680><c> help?</c><00:54:24.240><c> Yes.</c><00:54:24.640><c> Okay.</c><00:54:25.119><c> So</c><00:54:25.280><c> let</c><00:54:25.520><c> me</c>

Will that help? Yes. Okay. So let me

Will that help? Yes. Okay. So let me
just<00:54:25.839><c> show</c><00:54:25.920><c> you.</c><00:54:26.079><c> I</c><00:54:26.319><c> think</c><00:54:26.400><c> I</c><00:54:26.640><c> have</c><00:54:26.800><c> that.</c>

Okay.<00:54:30.800><c> So</c><00:54:31.680><c> let</c><00:54:31.839><c> me</c><00:54:32.000><c> quickly</c><00:54:32.640><c> spend</c><00:54:33.520><c> four</c>

Okay. So let me quickly spend four

Okay. So let me quickly spend four
minutes<00:54:34.079><c> on</c><00:54:34.240><c> that.</c><00:54:34.480><c> Four</c><00:54:34.800><c> five</c><00:54:34.960><c> minutes.</c><00:54:36.079><c> I</c>

minutes on that. Four five minutes. I

minutes on that. Four five minutes. I
have<00:54:36.400><c> a</c><00:54:36.640><c> good</c><00:54:36.800><c> demo</c><00:54:37.200><c> actually</c><00:54:37.440><c> if</c><00:54:37.680><c> you</c><00:54:37.839><c> want.</c>

have a good demo actually if you want.

have a good demo actually if you want.
How<00:54:38.559><c> many</c><00:54:38.640><c> of</c><00:54:38.800><c> you</c><00:54:38.880><c> have</c><00:54:39.119><c> heard</c><00:54:39.280><c> of</c><00:54:39.760><c> um</c><00:54:40.480><c> three</c>

How many of you have heard of um three

How many of you have heard of um three
blue<00:54:41.119><c> one</c><00:54:41.440><c> brown?</c>

blue one brown?

blue one brown?
Okay,<00:54:43.839><c> perfect.</c><00:54:44.240><c> Okay,</c><00:54:44.400><c> so</c><00:54:44.640><c> then</c><00:54:44.880><c> let</c><00:54:45.119><c> me</c><00:54:45.280><c> show</c>

Okay, perfect. Okay, so then let me show

Okay, perfect. Okay, so then let me show
you<00:54:45.599><c> that</c><00:54:46.079><c> you</c><00:54:46.319><c> might</c><00:54:47.119><c> you</c><00:54:47.359><c> might</c><00:54:47.920><c> uh</c><00:54:48.480><c> it</c><00:54:48.720><c> might</c>

you that you might you might uh it might

you that you might you might uh it might
be<00:54:49.040><c> interesting.</c><00:54:49.760><c> So</c><00:54:50.400><c> strands</c><00:54:50.800><c> is</c><00:54:50.960><c> an</c><00:54:51.280><c> uh</c>

be interesting. So strands is an uh

be interesting. So strands is an uh
framework<00:54:52.559><c> very</c><00:54:52.880><c> simple.</c><00:54:53.280><c> It's</c><00:54:53.440><c> a</c><00:54:53.599><c> model</c>

framework very simple. It's a model

framework very simple. It's a model
first<00:54:54.640><c> framework.</c><00:54:55.200><c> So</c><00:54:55.359><c> we</c><00:54:55.520><c> are</c><00:54:55.599><c> just</c><00:54:55.760><c> taking</c><00:54:55.920><c> a</c>

first framework. So we are just taking a

first framework. So we are just taking a
pause<00:54:56.319><c> on</c><00:54:56.400><c> that.</c><00:54:56.640><c> Okay,</c><00:54:56.880><c> we</c><00:54:57.040><c> are</c><00:54:57.119><c> just</c><00:54:57.280><c> we</c><00:54:57.440><c> will</c>

pause on that. Okay, we are just we will

pause on that. Okay, we are just we will
whatever<00:54:58.000><c> we</c><00:54:58.240><c> learn</c><00:54:58.480><c> here</c><00:54:58.880><c> we</c><00:54:59.040><c> will</c><00:54:59.200><c> just</c><00:54:59.440><c> use</c>

whatever we learn here we will just use

whatever we learn here we will just use
this<00:54:59.839><c> framework</c><00:55:00.319><c> to</c><00:55:00.720><c> make</c><00:55:00.960><c> our</c><00:55:01.760><c> workflow</c>

this framework to make our workflow

this framework to make our workflow
whatever<00:55:02.640><c> we</c><00:55:02.800><c> have</c><00:55:02.960><c> done</c><00:55:03.359><c> agenting</c><00:55:03.920><c> and</c><00:55:04.079><c> we</c>

whatever we have done agenting and we

whatever we have done agenting and we
will<00:55:04.400><c> add</c><00:55:04.559><c> a</c><00:55:04.880><c> voice</c><00:55:05.200><c> part</c><00:55:05.359><c> of</c><00:55:05.520><c> that</c><00:55:05.760><c> as</c><00:55:05.920><c> well.</c>

will add a voice part of that as well.

will add a voice part of that as well.
So<00:55:08.160><c> here</c>

So here

So here
there's<00:55:10.079><c> an</c><00:55:10.240><c> open</c><00:55:10.559><c> source</c><00:55:10.800><c> framework</c><00:55:11.520><c> which</c>

there's an open source framework which

there's an open source framework which
is<00:55:12.000><c> model</c><00:55:12.319><c> first.</c><00:55:12.800><c> That</c><00:55:13.040><c> means</c><00:55:13.920><c> uh</c><00:55:15.040><c> now</c><00:55:15.359><c> the</c>

is model first. That means uh now the

is model first. That means uh now the
models<00:55:15.920><c> are</c><00:55:16.079><c> so</c><00:55:16.319><c> strong</c><00:55:17.119><c> we</c><00:55:17.359><c> expect</c><00:55:18.800><c> that</c><00:55:19.040><c> the</c>

models are so strong we expect that the

models are so strong we expect that the
model<00:55:19.520><c> should</c><00:55:19.760><c> reason</c><00:55:20.240><c> rather</c><00:55:20.559><c> than</c><00:55:21.280><c> we</c>

model should reason rather than we

model should reason rather than we
telling<00:55:22.319><c> uh</c><00:55:22.400><c> the</c><00:55:22.640><c> agent</c><00:55:23.119><c> with</c><00:55:23.440><c> a</c><00:55:23.680><c> lot</c><00:55:23.839><c> of</c>

telling uh the agent with a lot of

telling uh the agent with a lot of
backstory<00:55:24.720><c> goals</c><00:55:25.359><c> prompting</c><00:55:25.839><c> and</c><00:55:26.079><c> all</c><00:55:26.240><c> that.</c>

backstory goals prompting and all that.

backstory goals prompting and all that.
We<00:55:26.800><c> don't</c><00:55:26.960><c> want</c><00:55:27.119><c> all</c><00:55:27.280><c> of</c><00:55:27.440><c> that.</c><00:55:27.920><c> We</c><00:55:28.240><c> throw</c><00:55:28.559><c> a</c>

We don't want all of that. We throw a

We don't want all of that. We throw a
question.<00:55:29.200><c> We</c><00:55:29.359><c> expect</c><00:55:29.680><c> the</c><00:55:29.839><c> model</c><00:55:30.160><c> to</c>

question. We expect the model to

question. We expect the model to
generate<00:55:30.800><c> the</c><00:55:31.280><c> response</c><00:55:31.760><c> and</c><00:55:32.000><c> do</c><00:55:32.160><c> the</c>

generate the response and do the

generate the response and do the
reasoning<00:55:33.280><c> uh</c><00:55:33.440><c> on</c><00:55:33.599><c> on</c><00:55:33.920><c> the</c><00:55:34.079><c> model</c><00:55:34.400><c> side.</c>

reasoning uh on on the model side.

reasoning uh on on the model side.
That's<00:55:35.200><c> that's</c><00:55:35.599><c> why</c><00:55:35.920><c> this</c><00:55:36.240><c> is</c><00:55:36.640><c> very</c><00:55:36.880><c> very</c>

That's that's why this is very very

That's that's why this is very very
lightweight<00:55:38.000><c> and</c><00:55:38.240><c> it</c><00:55:38.480><c> has</c><00:55:38.559><c> the</c><00:55:38.720><c> integration</c>

lightweight and it has the integration

lightweight and it has the integration
with<00:55:39.599><c> different</c><00:55:39.920><c> models</c><00:55:40.319><c> and</c><00:55:40.480><c> you</c><00:55:40.640><c> can</c><00:55:40.720><c> use</c>

with different models and you can use

with different models and you can use
model<00:55:41.200><c> from</c><00:55:41.359><c> bedrock</c><00:55:42.000><c> you</c><00:55:42.079><c> can</c><00:55:42.240><c> use</c><00:55:42.400><c> directly</c>

model from bedrock you can use directly

model from bedrock you can use directly
from<00:55:43.040><c> entropic</c><00:55:44.160><c> you</c><00:55:44.319><c> can</c><00:55:44.400><c> use</c><00:55:44.640><c> light</c><00:55:44.880><c> LLM.</c>

from entropic you can use light LLM.

from entropic you can use light LLM.
Have<00:55:45.359><c> you</c><00:55:45.440><c> heard</c><00:55:45.520><c> of</c><00:55:45.680><c> light</c><00:55:45.920><c> LLM?</c><00:55:46.480><c> Yeah.</c><00:55:46.880><c> So</c>

Have you heard of light LLM? Yeah. So

Have you heard of light LLM? Yeah. So
when<00:55:47.599><c> you</c><00:55:47.680><c> have</c><00:55:47.839><c> an</c><00:55:48.000><c> access</c><00:55:48.160><c> to</c><00:55:48.319><c> light</c><00:55:48.559><c> LLM</c><00:55:49.040><c> you</c>

when you have an access to light LLM you

when you have an access to light LLM you
can<00:55:49.280><c> access</c><00:55:49.599><c> any</c><00:55:49.839><c> model</c><00:55:50.079><c> that</c><00:55:50.400><c> light</c><00:55:50.640><c> LLM</c>

can access any model that light LLM

can access any model that light LLM
supports.<00:55:51.440><c> Right</c><00:55:52.799><c> now</c><00:55:54.160><c> this</c><00:55:54.319><c> is</c><00:55:54.480><c> what</c><00:55:54.640><c> it</c><00:55:54.799><c> is.</c>

supports. Right now this is what it is.

supports. Right now this is what it is.
So<00:55:56.000><c> strands</c><00:55:57.359><c> you</c><00:55:57.520><c> by</c><00:55:57.760><c> the</c><00:55:57.920><c> definition</c><00:55:58.240><c> of</c>

So strands you by the definition of

So strands you by the definition of
strands<00:55:59.760><c> it's</c><00:56:00.000><c> a</c><00:56:00.160><c> DNA</c><00:56:00.559><c> structure</c><00:56:01.119><c> and</c><00:56:01.520><c> it</c><00:56:01.760><c> just</c>

strands it's a DNA structure and it just

strands it's a DNA structure and it just
have<00:56:02.160><c> two</c><00:56:02.480><c> strands</c><00:56:03.359><c> and</c><00:56:04.160><c> that</c><00:56:04.480><c> two</c><00:56:04.799><c> strands</c>

have two strands and that two strands

have two strands and that two strands
stands<00:56:05.839><c> for</c><00:56:06.960><c> model</c><00:56:07.440><c> and</c><00:56:07.680><c> tool</c><00:56:08.160><c> that's</c><00:56:08.400><c> all.</c><00:56:09.119><c> So</c>

stands for model and tool that's all. So

stands for model and tool that's all. So
you<00:56:09.520><c> make</c><00:56:09.680><c> an</c><00:56:09.839><c> agent</c><00:56:10.480><c> with</c><00:56:10.799><c> one</c><00:56:11.040><c> model</c><00:56:12.240><c> and</c><00:56:12.960><c> few</c>

you make an agent with one model and few

you make an agent with one model and few
tools<00:56:14.480><c> and</c><00:56:15.040><c> simply</c><00:56:15.359><c> you</c><00:56:15.599><c> just</c><00:56:15.760><c> ask</c><00:56:16.000><c> the</c>

tools and simply you just ask the

tools and simply you just ask the
question<00:56:16.559><c> that's</c><00:56:16.720><c> all.</c><00:56:16.960><c> It's</c><00:56:17.119><c> as</c><00:56:17.359><c> simple</c><00:56:17.599><c> as</c>

question that's all. It's as simple as

question that's all. It's as simple as
that<00:56:18.160><c> right</c><00:56:18.640><c> and</c><00:56:18.880><c> let</c><00:56:19.119><c> me</c><00:56:19.280><c> show</c><00:56:19.440><c> you</c><00:56:19.920><c> uh</c><00:56:20.079><c> one</c>

that right and let me show you uh one

that right and let me show you uh one
quick<00:56:21.119><c> demo.</c>

quick demo.

quick demo.
Let's<00:56:23.760><c> see</c><00:56:23.839><c> if</c><00:56:24.079><c> it</c><00:56:24.480><c> uh</c><00:56:25.599><c> if</c><00:56:25.839><c> it</c><00:56:26.000><c> works.</c><00:56:26.559><c> Okay.</c>

So<00:56:30.480><c> this</c><00:56:30.640><c> is</c><00:56:30.880><c> is</c><00:56:31.040><c> it</c><00:56:31.280><c> visible</c><00:56:31.599><c> from</c><00:56:32.880><c> you</c><00:56:33.040><c> know</c>

So this is is it visible from you know

So this is is it visible from you know
last<00:56:33.680><c> row?</c><00:56:34.079><c> No,</c><00:56:34.480><c> not</c><00:56:34.640><c> that</c><00:56:34.880><c> much.</c><00:56:35.200><c> Right.</c>

Okay.<00:56:39.680><c> I'll</c><00:56:40.000><c> just</c><00:56:40.160><c> read</c><00:56:40.319><c> it</c><00:56:40.400><c> out.</c><00:56:40.720><c> So</c><00:56:40.960><c> we</c><00:56:41.200><c> are</c>

Okay. I'll just read it out. So we are

Okay. I'll just read it out. So we are
just<00:56:41.520><c> importing</c><00:56:42.799><c> um</c><00:56:43.920><c> agent</c><00:56:45.359><c> and</c><00:56:46.480><c> we</c><00:56:46.799><c> are</c>

just importing um agent and we are

just importing um agent and we are
importing<00:56:49.119><c> the</c><00:56:49.359><c> tools.</c><00:56:50.319><c> Okay.</c><00:56:51.599><c> And</c>

importing the tools. Okay. And

importing the tools. Okay. And
okay,<00:56:53.599><c> this</c><00:56:53.760><c> is</c><00:56:53.920><c> I</c><00:56:54.160><c> think</c><00:56:54.319><c> this</c><00:56:54.559><c> is</c><00:56:54.640><c> the</c><00:56:54.799><c> MCP</c>

okay, this is I think this is the MCP

okay, this is I think this is the MCP
one.<00:56:55.520><c> No,</c><00:56:55.680><c> no,</c><00:56:55.839><c> this</c><00:56:56.000><c> is</c><00:56:56.079><c> not</c><00:56:56.319><c> the</c><00:56:56.480><c> one</c><00:56:56.640><c> I</c><00:56:56.880><c> want</c>

one. No, no, this is not the one I want

one. No, no, this is not the one I want
to<00:56:57.119><c> show</c><00:56:57.200><c> you.</c>

Okay,<00:57:09.440><c> let</c><00:57:09.760><c> let's</c><00:57:10.319><c> uh</c><00:57:10.799><c> see</c><00:57:11.040><c> this.</c>

Okay, let let's uh see this.

Okay, let let's uh see this.
Okay,<00:57:13.839><c> just</c><00:57:14.319><c> uh</c><00:57:15.520><c> uh</c><00:57:15.599><c> I</c><00:57:15.839><c> think</c><00:57:15.920><c> it's</c><00:57:16.160><c> a</c><00:57:16.400><c> video.</c>

Okay, just uh uh I think it's a video.

Okay, just uh uh I think it's a video.
It<00:57:17.040><c> should</c><00:57:17.200><c> work</c><00:57:17.440><c> fine.</c>

Yeah,

Yeah,

Yeah,
let's<00:57:25.280><c> see.</c><00:57:26.319><c> So,</c><00:57:26.480><c> we</c><00:57:26.799><c> first</c><00:57:27.440><c> install</c><00:57:28.079><c> strands</c>

let's see. So, we first install strands

let's see. So, we first install strands
agent<00:57:29.359><c> and</c><00:57:29.760><c> strands</c><00:57:30.240><c> tool.</c><00:57:30.640><c> PIP</c><00:57:30.960><c> install</c>

agent and strands tool. PIP install

agent and strands tool. PIP install
simple<00:57:31.680><c> pip</c><00:57:32.000><c> install</c>

and<00:57:36.799><c> it's</c><00:57:37.040><c> open</c><00:57:37.280><c> source.</c><00:57:37.599><c> Okay,</c><00:57:37.839><c> so</c><00:57:38.000><c> you</c><00:57:38.240><c> don't</c>

and it's open source. Okay, so you don't

and it's open source. Okay, so you don't
have<00:57:38.480><c> to</c><00:57:39.119><c> uh</c><00:57:39.200><c> and</c><00:57:39.440><c> it</c><00:57:39.599><c> supports</c><00:57:39.920><c> Olama</c><00:57:40.400><c> as</c>

have to uh and it supports Olama as

have to uh and it supports Olama as
well.<00:57:41.040><c> So,</c><00:57:41.200><c> you</c><00:57:41.359><c> don't</c><00:57:41.520><c> have</c><00:57:41.680><c> to</c><00:57:42.319><c> have</c><00:57:42.480><c> an</c><00:57:42.720><c> AWS</c>

well. So, you don't have to have an AWS

well. So, you don't have to have an AWS
account<00:57:43.440><c> or</c><00:57:43.680><c> anything</c><00:57:43.920><c> of</c><00:57:44.079><c> that</c><00:57:44.319><c> sort.</c>

account or anything of that sort.

account or anything of that sort.
So<00:57:47.599><c> what</c><00:57:47.839><c> we</c><00:57:48.000><c> are</c><00:57:48.079><c> going</c><00:57:48.160><c> to</c><00:57:48.240><c> do</c><00:57:48.400><c> is</c><00:57:48.559><c> we</c><00:57:48.799><c> are</c>

So what we are going to do is we are

So what we are going to do is we are
going<00:57:49.040><c> to</c><00:57:49.200><c> create</c><00:57:49.440><c> a</c><00:57:49.680><c> file</c><00:57:50.319><c> create</c><00:57:50.640><c> a</c><00:57:50.799><c> summary</c>

going to create a file create a summary

going to create a file create a summary
write<00:57:51.920><c> the</c><00:57:52.079><c> summary</c><00:57:52.400><c> into</c><00:57:52.640><c> the</c><00:57:53.119><c> into</c><00:57:53.440><c> our</c><00:57:53.680><c> file</c>

write the summary into the into our file

write the summary into the into our file
and<00:57:55.440><c> uh</c><00:57:56.240><c> also</c><00:57:56.880><c> add</c><00:57:57.119><c> a</c><00:57:57.440><c> voice</c><00:57:57.839><c> part</c><00:57:58.079><c> of</c><00:57:58.160><c> it.</c>

and uh also add a voice part of it.

and uh also add a voice part of it.
Let's<00:57:59.040><c> see</c><00:57:59.359><c> I</c><00:57:59.599><c> think</c><00:57:59.680><c> it</c><00:57:59.920><c> would</c><00:58:00.079><c> be</c><00:58:00.960><c> pretty</c>

Let's see I think it would be pretty

Let's see I think it would be pretty
quick.

So<00:58:06.960><c> we</c><00:58:07.200><c> are</c><00:58:07.520><c> importing</c><00:58:08.240><c> is</c><00:58:08.400><c> it</c><00:58:08.559><c> visible</c><00:58:08.799><c> or</c><00:58:09.119><c> I</c>

So we are importing is it visible or I

So we are importing is it visible or I
should<00:58:09.839><c> should</c><00:58:10.000><c> I</c><00:58:10.160><c> show</c><00:58:10.319><c> it?</c><00:58:11.119><c> It's</c><00:58:11.440><c> pretty</c>

should should I show it? It's pretty

should should I show it? It's pretty
straightforward.

straightforward.

straightforward.
So<00:58:13.599><c> we</c><00:58:13.839><c> are</c><00:58:14.079><c> importing</c><00:58:14.559><c> agent</c><00:58:15.760><c> and</c><00:58:16.079><c> we</c><00:58:16.319><c> are</c>

So we are importing agent and we are

So we are importing agent and we are
importing<00:58:16.880><c> the</c><00:58:17.440><c> bedrock</c><00:58:17.920><c> model.</c><00:58:18.480><c> By</c><00:58:18.799><c> default</c>

importing the bedrock model. By default

importing the bedrock model. By default
it<00:58:19.760><c> uses</c><00:58:20.160><c> bedrock</c><00:58:20.720><c> model.</c><00:58:21.119><c> Uh</c><00:58:21.440><c> it</c><00:58:21.760><c> actually</c>

it uses bedrock model. Uh it actually

it uses bedrock model. Uh it actually
uses<00:58:22.319><c> clot</c><00:58:22.720><c> 3.7</c><00:58:23.280><c> but</c><00:58:23.760><c> you</c><00:58:24.000><c> can</c><00:58:24.160><c> use</c><00:58:24.960><c> any</c><00:58:25.200><c> other</c>

uses clot 3.7 but you can use any other

uses clot 3.7 but you can use any other
model.<00:58:26.480><c> And</c><00:58:26.640><c> I</c><00:58:26.799><c> have</c><00:58:26.960><c> used</c><00:58:27.200><c> some</c><00:58:27.440><c> built-in</c>

model. And I have used some built-in

model. And I have used some built-in
tool<00:58:28.319><c> called</c><00:58:28.559><c> read</c><00:58:28.960><c> file,</c><00:58:29.359><c> write</c><00:58:29.680><c> file</c><00:58:29.920><c> and</c>

tool called read file, write file and

tool called read file, write file and
speak.<00:58:31.200><c> And</c><00:58:31.440><c> this</c><00:58:31.680><c> is</c><00:58:31.760><c> the</c><00:58:31.920><c> model</c><00:58:32.319><c> ID.</c><00:58:33.520><c> And</c>

speak. And this is the model ID. And

speak. And this is the model ID. And
this<00:58:33.920><c> is</c><00:58:34.000><c> the</c><00:58:34.240><c> prompt.</c><00:58:34.960><c> You</c><00:58:35.200><c> can</c><00:58:35.760><c> have</c><00:58:35.920><c> a</c>

this is the prompt. You can have a

this is the prompt. You can have a
prompt,<00:58:36.640><c> you</c><00:58:36.799><c> can</c><00:58:36.960><c> skip</c><00:58:37.200><c> a</c><00:58:37.440><c> prompt,</c><00:58:37.839><c> doesn't</c>

prompt, you can skip a prompt, doesn't

prompt, you can skip a prompt, doesn't
matter.

matter.

matter.
And<00:58:41.280><c> lastly</c><00:58:42.640><c> you</c><00:58:42.880><c> have</c><00:58:43.119><c> to</c><00:58:43.280><c> create</c><00:58:43.760><c> the</c><00:58:44.160><c> agent.</c>

And lastly you have to create the agent.

And lastly you have to create the agent.
So

So

So
say<00:58:47.839><c> this</c><00:58:48.079><c> agent</c><00:58:48.480><c> contains</c><00:58:48.960><c> the</c><00:58:49.200><c> model</c><00:58:49.520><c> ID</c>

say this agent contains the model ID

say this agent contains the model ID
system<00:58:50.240><c> prompt</c><00:58:50.559><c> and</c><00:58:50.720><c> the</c><00:58:50.880><c> tools</c><00:58:51.200><c> and</c><00:58:51.359><c> all</c>

system prompt and the tools and all

system prompt and the tools and all
these<00:58:51.760><c> tools</c><00:58:52.000><c> you</c><00:58:52.160><c> have</c><00:58:52.240><c> not</c><00:58:52.400><c> written</c><00:58:52.640><c> the</c>

these tools you have not written the

these tools you have not written the
code<00:58:52.960><c> for</c><00:58:53.119><c> this.</c><00:58:53.359><c> This</c><00:58:53.520><c> is</c><00:58:53.680><c> by</c><00:58:53.920><c> default</c><00:58:54.480><c> right</c>

code for this. This is by default right

code for this. This is by default right
and<00:58:56.000><c> I'm</c><00:58:56.319><c> just</c><00:58:56.559><c> asking</c><00:58:57.520><c> uh</c><00:58:57.599><c> a</c><00:58:57.920><c> particular</c>

and I'm just asking uh a particular

and I'm just asking uh a particular
question<00:58:59.119><c> and</c><00:58:59.359><c> see</c><00:58:59.599><c> this</c><00:59:00.720><c> I'm</c><00:59:01.680><c> in</c><00:59:01.920><c> the</c><00:59:02.079><c> prompt</c>

question and see this I'm in the prompt

question and see this I'm in the prompt
I'm<00:59:02.880><c> saying</c><00:59:03.040><c> that</c><00:59:03.280><c> this</c><00:59:03.440><c> is</c><00:59:03.520><c> a</c><00:59:03.839><c> textbook</c><00:59:05.200><c> uh</c><00:59:05.280><c> in</c>

I'm saying that this is a textbook uh in

I'm saying that this is a textbook uh in
my<00:59:05.680><c> local</c><00:59:05.920><c> directory</c><00:59:06.400><c> read</c><00:59:06.640><c> that</c><00:59:07.359><c> create</c><00:59:07.599><c> a</c>

my local directory read that create a

my local directory read that create a
summary<00:59:08.480><c> and</c><00:59:08.720><c> write</c><00:59:09.040><c> it</c><00:59:09.440><c> into</c><00:59:09.680><c> the</c><00:59:09.920><c> local</c>

summary and write it into the local

summary and write it into the local
directory<00:59:10.480><c> and</c><00:59:10.640><c> also</c><00:59:10.880><c> speak</c><00:59:11.119><c> out</c><00:59:11.520><c> the</c><00:59:11.839><c> final</c>

directory and also speak out the final

directory and also speak out the final
answer

answer

answer
and<00:59:14.799><c> see</c><00:59:15.040><c> this</c><00:59:15.280><c> it</c><00:59:15.440><c> is</c><00:59:15.599><c> using</c><00:59:15.839><c> the</c><00:59:16.000><c> tools</c><00:59:16.400><c> for</c>

and see this it is using the tools for

and see this it is using the tools for
read<00:59:16.960><c> the</c><00:59:17.200><c> file</c><00:59:18.079><c> second</c><00:59:18.559><c> it</c><00:59:18.799><c> is</c><00:59:18.960><c> create</c><00:59:19.280><c> after</c>

read the file second it is create after

read the file second it is create after
&gt;&gt; functions<00:59:20.240><c> like</c><00:59:20.400><c> a</c><00:59:20.559><c> camera</c><00:59:21.680><c> light</c><00:59:21.839><c> entering</c>

&gt;&gt; functions like a camera light entering

&gt;&gt; functions like a camera light entering
through<00:59:22.319><c> the</c><00:59:22.480><c> cornea</c><00:59:22.960><c> and</c><00:59:23.119><c> focus</c><00:59:23.520><c> by</c><00:59:23.599><c> a</c><00:59:23.760><c> lens</c>

through the cornea and focus by a lens

through the cornea and focus by a lens
onto<00:59:24.079><c> the</c>

onto the

onto the
&gt;&gt; we<00:59:24.480><c> have</c><00:59:24.640><c> not</c><00:59:24.720><c> done</c><00:59:24.880><c> anything</c><00:59:25.200><c> just</c><00:59:25.680><c> in</c>

&gt;&gt; we have not done anything just in

&gt;&gt; we have not done anything just in
controls<00:59:26.480><c> pupil</c><00:59:26.799><c> size</c><00:59:27.359><c> to</c><00:59:27.520><c> regulate</c><00:59:27.920><c> incoming</c>

controls pupil size to regulate incoming

controls pupil size to regulate incoming
light

light

light
&gt;&gt; the<00:59:29.599><c> I</c><00:59:29.760><c> can</c><00:59:29.920><c> adjust</c><00:59:30.240><c> focal</c><00:59:30.559><c> length</c><00:59:30.880><c> through</c>

&gt;&gt; the I can adjust focal length through

&gt;&gt; the I can adjust focal length through
accommodation<00:59:32.160><c> see</c>

accommodation see

accommodation see
&gt;&gt; all<00:59:34.319><c> right</c><00:59:34.480><c> so</c><00:59:34.799><c> now</c><00:59:35.359><c> I</c><00:59:35.839><c> I</c><00:59:36.240><c> will</c><00:59:36.400><c> share</c><00:59:36.960><c> one</c><00:59:37.280><c> more</c>

&gt;&gt; all right so now I I will share one more

&gt;&gt; all right so now I I will share one more
thing<00:59:37.760><c> now</c><00:59:37.920><c> I'll</c><00:59:38.240><c> not</c><00:59:38.480><c> show</c><00:59:38.640><c> you</c><00:59:39.520><c> the</c><00:59:39.760><c> code</c>

thing now I'll not show you the code

thing now I'll not show you the code
that<00:59:40.319><c> is</c><00:59:40.480><c> not</c><00:59:40.640><c> the</c><00:59:40.880><c> purpose</c><00:59:41.200><c> of</c><00:59:41.440><c> this</c><00:59:41.760><c> but</c><00:59:42.400><c> have</c>

that is not the purpose of this but have

that is not the purpose of this but have
you<00:59:42.720><c> heard</c><00:59:42.880><c> of</c><00:59:43.280><c> um</c><00:59:43.839><c> of</c><00:59:44.000><c> course</c><00:59:44.160><c> you</c><00:59:44.319><c> have</c><00:59:44.480><c> heard</c>

you heard of um of course you have heard

you heard of um of course you have heard
of<00:59:44.799><c> MCP</c>

of MCP

of MCP
yeah<00:59:47.200><c> so</c><00:59:48.640><c> see</c><00:59:48.880><c> this</c><00:59:49.040><c> I</c><00:59:49.359><c> I'll</c><00:59:49.599><c> not</c><00:59:49.760><c> tell</c><00:59:49.839><c> you</c><00:59:50.079><c> I</c>

yeah so see this I I'll not tell you I

yeah so see this I I'll not tell you I
think<00:59:50.480><c> you</c><00:59:50.720><c> should</c><00:59:50.880><c> be</c><00:59:51.040><c> able</c><00:59:51.359><c> So</c>

think you should be able So

think you should be able So
I've<00:59:54.480><c> created</c><00:59:54.720><c> an</c><00:59:54.880><c> MCP</c><00:59:55.440><c> server</c><00:59:56.400><c> called</c><00:59:57.040><c> um</c>

I've created an MCP server called um

I've created an MCP server called um
created<00:59:57.920><c> an</c><00:59:58.079><c> MCP</c><00:59:58.559><c> server</c><00:59:58.880><c> with</c><00:59:59.440><c> manm</c><01:00:00.160><c> okay</c><01:00:00.480><c> so</c>

created an MCP server with manm okay so

created an MCP server with manm okay so
manim<01:00:01.680><c> have</c><01:00:01.760><c> you</c><01:00:01.839><c> heard</c><01:00:02.000><c> of</c><01:00:02.079><c> manm</c><01:00:03.280><c> okay</c><01:00:03.680><c> just</c>

manim have you heard of manm okay just

manim have you heard of manm okay just
just<01:00:04.160><c> see</c><01:00:04.400><c> that</c><01:00:05.839><c> so</c><01:00:06.160><c> idea</c><01:00:06.480><c> is</c><01:00:07.599><c> so</c><01:00:08.400><c> let</c><01:00:08.640><c> me</c><01:00:08.799><c> just</c>

just see that so idea is so let me just

just see that so idea is so let me just
show<01:00:09.200><c> you</c><01:00:09.359><c> what</c><01:00:09.520><c> we</c><01:00:09.680><c> are</c><01:00:09.839><c> doing</c><01:00:11.119><c> we</c><01:00:11.359><c> are</c>

show you what we are doing we are

show you what we are doing we are
creating<01:00:11.839><c> a</c><01:00:12.799><c> man</c><01:00:13.280><c> server</c><01:00:14.720><c> and</c><01:00:15.040><c> this</c><01:00:15.200><c> is</c><01:00:15.280><c> the</c>

creating a man server and this is the

creating a man server and this is the
MCP<01:00:15.920><c> server</c><01:00:16.559><c> now</c><01:00:16.799><c> this</c><01:00:16.960><c> is</c><01:00:17.040><c> the</c><01:00:17.280><c> client</c><01:00:17.680><c> on</c>

MCP server now this is the client on

MCP server now this is the client on
nothing<01:00:18.240><c> but</c><01:00:18.720><c> uh</c><01:00:18.880><c> our</c><01:00:19.200><c> strand</c><01:00:19.599><c> agent</c><01:00:20.319><c> and</c><01:00:20.559><c> this</c>

nothing but uh our strand agent and this

nothing but uh our strand agent and this
will<01:00:21.200><c> call</c><01:00:21.680><c> this</c><01:00:21.920><c> MCP</c><01:00:22.480><c> server.</c><01:00:23.440><c> Okay.</c><01:00:24.079><c> And</c><01:00:24.319><c> I</c>

will call this MCP server. Okay. And I

will call this MCP server. Okay. And I
can<01:00:24.640><c> give</c><01:00:24.880><c> any</c><01:00:25.200><c> question.</c><01:00:25.680><c> So</c><01:00:25.920><c> question</c><01:00:26.160><c> is</c>

can give any question. So question is

can give any question. So question is
create<01:00:27.040><c> a</c><01:00:27.359><c> man</c><01:00:28.319><c> screen</c><01:00:28.960><c> which</c><01:00:29.280><c> draws</c><01:00:29.599><c> a</c><01:00:29.839><c> cubic</c>

create a man screen which draws a cubic

create a man screen which draws a cubic
function<01:00:31.599><c> like</c><01:00:32.000><c> 2x^</c><01:00:33.040><c> 3</c><01:00:33.359><c> minus</c><01:00:33.839><c> blah</c><01:00:34.000><c> blah</c>

function like 2x^ 3 minus blah blah

function like 2x^ 3 minus blah blah
blah.<01:00:34.640><c> Okay.</c><01:00:35.040><c> And</c><01:00:35.280><c> see</c><01:00:35.440><c> what</c><01:00:35.680><c> happens.</c>

Now<01:00:39.520><c> it</c><01:00:39.760><c> is</c><01:00:39.920><c> executing</c><01:00:40.319><c> the</c><01:00:40.559><c> code</c><01:00:41.440><c> calling</c>

Now it is executing the code calling

Now it is executing the code calling
this<01:00:42.079><c> uh</c><01:00:42.240><c> MCP</c><01:00:42.799><c> server.</c><01:00:43.040><c> It</c><01:00:43.200><c> is</c><01:00:43.359><c> working</c><01:00:44.000><c> uh</c>

this uh MCP server. It is working uh

this uh MCP server. It is working uh
here<01:00:45.119><c> and</c><01:00:45.359><c> then</c><01:00:45.520><c> it</c><01:00:45.760><c> should</c><01:00:45.920><c> give</c><01:00:46.079><c> you</c><01:00:46.240><c> some</c>

here and then it should give you some

here and then it should give you some
response.

So<01:00:55.040><c> it</c><01:00:55.280><c> generated</c><01:00:55.680><c> this</c><01:00:56.000><c> video.</c><01:00:56.640><c> Okay.</c>

So it generated this video. Okay.

So it generated this video. Okay.
And<01:00:59.119><c> now</c><01:01:00.400><c> you</c><01:01:00.720><c> will</c><01:01:01.839><c> get</c><01:01:02.079><c> some</c><01:01:02.319><c> familiarity.</c>

Looks<01:01:08.079><c> similar,</c><01:01:08.559><c> right?</c>

Looks similar, right?

Looks similar, right?
I<01:01:10.880><c> have</c><01:01:11.040><c> not</c><01:01:11.200><c> done</c><01:01:11.440><c> anything.</c><01:01:12.480><c> All</c><01:01:12.720><c> I</c><01:01:12.880><c> have</c>

I have not done anything. All I have

I have not done anything. All I have
used<01:01:13.359><c> is</c><01:01:13.520><c> a</c><01:01:13.680><c> manage</c><01:01:14.400><c> uh</c><01:01:14.640><c> uh</c><01:01:14.880><c> SDK</c><01:01:16.000><c> and</c><01:01:16.319><c> created</c>

used is a manage uh uh SDK and created

used is a manage uh uh SDK and created
that<01:01:17.200><c> uh</c><01:01:17.440><c> MCP</c><01:01:17.920><c> server</c><01:01:18.720><c> which</c><01:01:18.960><c> can</c><01:01:19.200><c> generate</c>

that uh MCP server which can generate

that uh MCP server which can generate
videos<01:01:20.160><c> like</c><01:01:20.720><c> uh</c><01:01:20.880><c> what</c><01:01:21.200><c> three</c><01:01:21.440><c> blue</c><01:01:21.680><c> one</c><01:01:21.920><c> brown</c>

videos like uh what three blue one brown

videos like uh what three blue one brown
created.<01:01:23.040><c> So</c><01:01:23.760><c> this</c><01:01:24.000><c> is</c><01:01:24.160><c> just</c><01:01:24.640><c> a</c><01:01:24.960><c> small</c><01:01:25.200><c> demo</c><01:01:25.440><c> of</c>

created. So this is just a small demo of

created. So this is just a small demo of
how<01:01:25.760><c> you</c><01:01:25.920><c> can</c><01:01:26.079><c> make</c><01:01:26.240><c> use</c><01:01:26.480><c> of</c><01:01:26.640><c> strands</c><01:01:27.520><c> with</c><01:01:27.760><c> an</c>

how you can make use of strands with an

how you can make use of strands with an
MCP<01:01:28.720><c> and</c><01:01:29.040><c> write</c><01:01:29.359><c> simple</c><01:01:29.760><c> code</c><01:01:30.000><c> and</c><01:01:30.640><c> you</c><01:01:30.880><c> know</c>

MCP and write simple code and you know

MCP and write simple code and you know
do<01:01:31.599><c> wonderful</c><01:01:32.000><c> things.</c><01:01:32.640><c> Okay.</c><01:01:33.920><c> All</c><01:01:33.920><c> right.</c><01:01:34.240><c> So</c>

do wonderful things. Okay. All right. So

do wonderful things. Okay. All right. So
this<01:01:34.640><c> is</c><01:01:34.720><c> about</c><01:01:35.040><c> strand.</c>

this is about strand.

this is about strand.
The<01:01:37.680><c> core</c><01:01:38.000><c> idea</c><01:01:38.319><c> of</c><01:01:38.559><c> strand</c><01:01:38.960><c> is</c><01:01:40.160><c> uh</c><01:01:40.799><c> just</c><01:01:41.040><c> pip</c>

The core idea of strand is uh just pip

The core idea of strand is uh just pip
install<01:01:42.559><c> and</c><01:01:43.119><c> use</c><01:01:43.359><c> it</c><01:01:43.839><c> with</c><01:01:44.319><c> the</c><01:01:44.640><c> by</c><01:01:44.880><c> default</c>

install and use it with the by default

install and use it with the by default
tools<01:01:46.079><c> and</c><01:01:46.799><c> uh</c><01:01:47.040><c> your</c><01:01:47.359><c> model</c><01:01:47.680><c> of</c><01:01:47.839><c> your</c><01:01:48.000><c> choice.</c>

tools and uh your model of your choice.

tools and uh your model of your choice.
That's<01:01:48.400><c> all.</c><01:01:48.720><c> There's</c><01:01:48.960><c> nothing</c><01:01:50.000><c> uh</c><01:01:50.240><c> no</c>

That's all. There's nothing uh no

That's all. There's nothing uh no
scaffolding<01:01:51.359><c> uh</c><01:01:51.440><c> beyond</c><01:01:51.839><c> this.</c><01:01:52.240><c> Okay.</c><01:01:52.880><c> So</c>

scaffolding uh beyond this. Okay. So

scaffolding uh beyond this. Okay. So
it's<01:01:53.520><c> just</c><01:01:53.680><c> like</c><01:01:53.839><c> this</c><01:01:54.000><c> you</c><01:01:54.160><c> pip</c><01:01:54.480><c> install</c>

it's just like this you pip install

it's just like this you pip install
create<01:01:56.240><c> an</c><01:01:56.480><c> instance</c><01:01:56.799><c> and</c><01:01:57.119><c> just</c><01:01:57.280><c> ask</c>

create an instance and just ask

create an instance and just ask
question.<01:01:58.079><c> Here</c><01:01:58.319><c> we</c><01:01:58.559><c> have</c><01:01:58.720><c> not</c><01:01:58.880><c> mentioned</c><01:01:59.119><c> any</c>

question. Here we have not mentioned any

question. Here we have not mentioned any
model<01:01:59.599><c> that</c><01:01:59.839><c> means</c><01:02:00.000><c> it</c><01:02:00.160><c> will</c><01:02:00.319><c> by</c><01:02:00.480><c> default</c><01:02:00.720><c> use</c>

model that means it will by default use

model that means it will by default use
bedrock<01:02:01.359><c> model</c><01:02:01.839><c> but</c><01:02:02.079><c> in</c><01:02:02.240><c> the</c><01:02:02.400><c> demo</c><01:02:02.640><c> we</c><01:02:02.880><c> have</c>

bedrock model but in the demo we have

bedrock model but in the demo we have
seen<01:02:03.119><c> that</c><01:02:03.280><c> you</c><01:02:03.440><c> can</c><01:02:03.520><c> define</c><01:02:03.839><c> your</c><01:02:04.319><c> bedrock</c>

seen that you can define your bedrock

seen that you can define your bedrock
models<01:02:05.119><c> here.</c><01:02:05.760><c> Okay.</c><01:02:06.799><c> So</c><01:02:07.359><c> now</c><01:02:07.599><c> let's</c><01:02:07.920><c> come</c>

models here. Okay. So now let's come

models here. Okay. So now let's come
back<01:02:08.160><c> to</c><01:02:08.319><c> our</c><01:02:08.720><c> our</c><01:02:09.520><c> um</c>

back to our our um

back to our our um
our<01:02:11.520><c> problem.</c><01:02:12.480><c> In</c><01:02:12.720><c> this</c><01:02:12.960><c> case</c><01:02:13.760><c> our</c><01:02:14.160><c> tool</c><01:02:14.960><c> is</c>

our problem. In this case our tool is

our problem. In this case our tool is
not<01:02:15.599><c> the</c><01:02:15.839><c> default</c><01:02:16.160><c> one</c><01:02:16.400><c> but</c><01:02:16.640><c> the</c><01:02:16.799><c> tool</c><01:02:17.119><c> that</c><01:02:17.280><c> we</c>

not the default one but the tool that we

not the default one but the tool that we
have<01:02:17.680><c> defined.</c><01:02:18.000><c> And</c><01:02:18.160><c> what</c><01:02:18.319><c> is</c><01:02:18.400><c> that</c><01:02:18.640><c> tool?</c><01:02:19.040><c> The</c>

have defined. And what is that tool? The

have defined. And what is that tool? The
retrieval<01:02:19.760><c> tool.</c><01:02:20.559><c> And</c><01:02:20.799><c> how</c><01:02:21.040><c> I</c><01:02:21.200><c> can</c><01:02:21.440><c> create</c><01:02:21.680><c> a</c>

retrieval tool. And how I can create a

retrieval tool. And how I can create a
uh<01:02:23.200><c> custom</c><01:02:23.599><c> tool</c><01:02:24.240><c> it</c><01:02:24.480><c> just</c><01:02:24.720><c> by</c><01:02:25.040><c> importing</c><01:02:25.599><c> tool</c>

uh custom tool it just by importing tool

uh custom tool it just by importing tool
and<01:02:26.720><c> just</c><01:02:27.040><c> use</c><01:02:27.280><c> that</c><01:02:27.440><c> as</c><01:02:27.599><c> a</c><01:02:27.760><c> decorator</c><01:02:28.480><c> on</c><01:02:28.720><c> top</c>

and just use that as a decorator on top

and just use that as a decorator on top
of<01:02:29.040><c> your</c><01:02:29.280><c> function.</c><01:02:29.680><c> That's</c><01:02:29.839><c> all.</c><01:02:30.400><c> Now</c><01:02:31.040><c> this</c>

of your function. That's all. Now this

of your function. That's all. Now this
becomes<01:02:31.599><c> a</c><01:02:31.839><c> tool</c><01:02:32.079><c> for</c><01:02:32.319><c> me</c><01:02:32.880><c> just</c><01:02:33.119><c> like</c><01:02:33.359><c> read</c>

becomes a tool for me just like read

becomes a tool for me just like read
file<01:02:33.920><c> write</c><01:02:34.240><c> file</c><01:02:34.559><c> speak.</c><01:02:34.960><c> This</c><01:02:35.119><c> is</c><01:02:35.280><c> just</c><01:02:35.440><c> a</c>

file write file speak. This is just a

file write file speak. This is just a
tool<01:02:35.839><c> for</c><01:02:36.000><c> me.</c><01:02:36.480><c> Okay.</c><01:02:37.760><c> And</c><01:02:39.119><c> we</c><01:02:39.440><c> can</c><01:02:39.520><c> defi</c><01:02:39.920><c> we</c>

tool for me. Okay. And we can defi we

tool for me. Okay. And we can defi we
can<01:02:40.240><c> use</c><01:02:40.559><c> make</c><01:02:40.720><c> use</c><01:02:40.960><c> of</c><01:02:41.359><c> bedrock</c><01:02:41.839><c> model</c><01:02:42.079><c> or</c><01:02:43.040><c> up</c>

can use make use of bedrock model or up

can use make use of bedrock model or up
to<01:02:43.359><c> you.</c><01:02:44.480><c> And</c><01:02:45.920><c> now</c><01:02:46.559><c> look</c><01:02:46.720><c> at</c><01:02:46.880><c> this.</c><01:02:47.599><c> We</c><01:02:47.920><c> are</c>

to you. And now look at this. We are

to you. And now look at this. We are
also<01:02:48.799><c> importing</c><01:02:49.200><c> an</c><01:02:49.520><c> image</c><01:02:49.839><c> reader.</c><01:02:50.240><c> Why</c><01:02:50.400><c> we</c>

also importing an image reader. Why we

also importing an image reader. Why we
are<01:02:50.960><c> importing</c><01:02:51.359><c> this</c><01:02:51.520><c> image</c><01:02:51.839><c> reader?</c><01:02:52.160><c> I</c><01:02:52.400><c> will</c>

are importing this image reader? I will

are importing this image reader? I will
uh<01:02:53.119><c> tell</c><01:02:53.280><c> you</c><01:02:53.440><c> a</c><01:02:53.520><c> little</c><01:02:53.760><c> later.</c><01:02:54.400><c> But</c><01:02:54.799><c> uh</c><01:02:54.960><c> you</c>

uh tell you a little later. But uh you

uh tell you a little later. But uh you
you<01:02:55.599><c> remember</c><01:02:55.920><c> that</c><01:02:56.400><c> when</c><01:02:56.720><c> we</c><01:02:57.040><c> use</c><01:02:57.280><c> this</c>

you remember that when we use this

you remember that when we use this
bedrock<01:02:58.079><c> model</c><01:02:58.480><c> for</c><01:02:59.040><c> final</c><01:02:59.440><c> answer</c><01:03:00.559><c> when</c><01:03:00.799><c> we</c>

bedrock model for final answer when we

bedrock model for final answer when we
use<01:03:01.119><c> this</c><01:03:01.280><c> bedrock</c><01:03:02.240><c> model</c><01:03:02.640><c> to</c><01:03:02.880><c> generate</c><01:03:03.200><c> the</c>

use this bedrock model to generate the

use this bedrock model to generate the
final<01:03:03.760><c> answer</c><01:03:04.319><c> we</c><01:03:04.559><c> created</c><01:03:04.960><c> some</c><01:03:05.200><c> custom</c>

final answer we created some custom

final answer we created some custom
functions<01:03:06.640><c> which</c><01:03:06.960><c> are</c><01:03:07.119><c> nothing</c><01:03:07.359><c> but</c><01:03:08.160><c> uh</c>

functions which are nothing but uh

functions which are nothing but uh
contains<01:03:08.640><c> the</c><01:03:08.880><c> information</c><01:03:09.359><c> about</c><01:03:10.319><c> how</c><01:03:10.720><c> to</c><01:03:11.440><c> uh</c>

contains the information about how to uh

contains the information about how to uh
create<01:03:12.000><c> the</c><01:03:12.240><c> prompt</c><01:03:12.880><c> for</c><01:03:13.119><c> your</c><01:03:13.440><c> images</c><01:03:13.760><c> for</c>

create the prompt for your images for

create the prompt for your images for
bedrock<01:03:14.640><c> models</c><01:03:15.119><c> right</c><01:03:15.680><c> so</c><01:03:16.079><c> I</c><01:03:16.319><c> don't</c><01:03:16.480><c> have</c><01:03:16.640><c> to</c>

bedrock models right so I don't have to

bedrock models right so I don't have to
do<01:03:16.880><c> all</c><01:03:17.039><c> these</c><01:03:17.359><c> things</c><01:03:18.240><c> and</c><01:03:18.640><c> uh</c><01:03:18.799><c> I</c><01:03:19.039><c> can</c><01:03:19.200><c> simply</c>

do all these things and uh I can simply

do all these things and uh I can simply
make<01:03:20.319><c> use</c><01:03:20.559><c> of</c><01:03:21.039><c> this</c><01:03:21.599><c> image</c><01:03:22.240><c> reader</c><01:03:22.960><c> which</c><01:03:23.200><c> just</c>

make use of this image reader which just

make use of this image reader which just
takes<01:03:23.599><c> an</c><01:03:23.839><c> image</c><01:03:24.079><c> and</c><01:03:24.400><c> generates</c><01:03:25.200><c> uh</c><01:03:25.440><c> the</c>

takes an image and generates uh the

takes an image and generates uh the
prompt<01:03:26.400><c> for</c><01:03:26.640><c> us.</c><01:03:27.920><c> And</c><01:03:28.079><c> now</c><01:03:28.319><c> I</c><01:03:28.480><c> have</c><01:03:28.559><c> a</c><01:03:28.720><c> system</c>

prompt for us. And now I have a system

prompt for us. And now I have a system
prompt.<01:03:29.359><c> System</c><01:03:29.599><c> prompt</c><01:03:29.920><c> says</c><01:03:30.079><c> that</c><01:03:30.640><c> you</c><01:03:30.880><c> are</c>

prompt. System prompt says that you are

prompt. System prompt says that you are
a<01:03:31.760><c> rag</c><01:03:32.079><c> based</c><01:03:32.400><c> system</c><01:03:32.640><c> and</c><01:03:32.880><c> all</c><01:03:33.039><c> that.</c><01:03:33.359><c> And</c><01:03:33.520><c> it</c>

a rag based system and all that. And it

a rag based system and all that. And it
also<01:03:34.000><c> says</c><01:03:34.720><c> uh</c><01:03:34.880><c> these</c><01:03:35.119><c> are</c><01:03:35.200><c> the</c><01:03:35.359><c> two</c><01:03:35.599><c> functions</c>

also says uh these are the two functions

also says uh these are the two functions
that<01:03:36.240><c> you</c><01:03:36.480><c> have</c><01:03:36.960><c> or</c><01:03:37.200><c> the</c><01:03:37.359><c> tools</c><01:03:37.599><c> that</c><01:03:37.760><c> you</c><01:03:37.920><c> have</c>

that you have or the tools that you have

that you have or the tools that you have
to<01:03:38.319><c> use</c><01:03:38.559><c> and</c><01:03:38.799><c> all</c><01:03:38.960><c> that.</c><01:03:39.680><c> And</c><01:03:39.839><c> that's</c><01:03:40.160><c> all.</c>

to use and all that. And that's all.

to use and all that. And that's all.
And<01:03:41.920><c> now</c><01:03:42.160><c> you</c><01:03:42.400><c> create</c><01:03:42.640><c> an</c><01:03:42.799><c> agent</c><01:03:43.520><c> again</c><01:03:43.920><c> just</c>

And now you create an agent again just

And now you create an agent again just
like<01:03:44.400><c> before</c><01:03:45.039><c> you</c><01:03:45.280><c> define</c><01:03:45.599><c> the</c><01:03:45.760><c> model</c><01:03:46.400><c> system</c>

like before you define the model system

like before you define the model system
prompt.<01:03:47.520><c> And</c><01:03:47.760><c> in</c><01:03:47.920><c> this</c><01:03:48.079><c> case</c><01:03:48.319><c> we</c><01:03:48.480><c> use</c><01:03:48.720><c> two</c>

prompt. And in this case we use two

prompt. And in this case we use two
tools.<01:03:49.440><c> One</c><01:03:49.599><c> is</c><01:03:49.760><c> the</c><01:03:49.920><c> retrieve</c><01:03:50.240><c> from</c><01:03:50.400><c> quadrant</c>

tools. One is the retrieve from quadrant

tools. One is the retrieve from quadrant
which<01:03:51.119><c> is</c><01:03:51.200><c> our</c><01:03:51.440><c> tool</c><01:03:52.160><c> and</c><01:03:52.480><c> the</c><01:03:52.799><c> image</c><01:03:53.119><c> reader</c>

which is our tool and the image reader

which is our tool and the image reader
for<01:03:53.839><c> the</c><01:03:54.079><c> generation</c><01:03:54.559><c> part.</c><01:03:55.359><c> Okay.</c>

for the generation part. Okay.

for the generation part. Okay.
And<01:03:57.200><c> then</c><01:03:57.440><c> we</c><01:03:57.599><c> ask</c><01:03:57.839><c> this</c><01:03:58.160><c> question</c><01:03:59.039><c> what</c><01:03:59.280><c> is</c>

And then we ask this question what is

And then we ask this question what is
the<01:03:59.520><c> difference</c><01:04:00.160><c> uh</c><01:04:01.119><c> different</c><01:04:01.680><c> tropical</c>

the difference uh different tropical

the difference uh different tropical
levels<01:04:02.799><c> and</c><01:04:03.119><c> now</c><01:04:03.680><c> it</c><01:04:04.000><c> just</c><01:04:04.240><c> agents</c><01:04:05.200><c> uh</c>

levels and now it just agents uh

levels and now it just agents uh
generates<01:04:05.839><c> the</c><01:04:06.000><c> response</c><01:04:06.480><c> just</c><01:04:06.720><c> like</c><01:04:06.880><c> before</c>

generates the response just like before

generates the response just like before
but<01:04:07.440><c> now</c><01:04:07.680><c> everything</c><01:04:08.000><c> is</c><01:04:08.240><c> done</c><01:04:08.400><c> by</c><01:04:08.640><c> the</c><01:04:08.799><c> agent.</c>

but now everything is done by the agent.

but now everything is done by the agent.
And<01:04:10.240><c> the</c><01:04:10.400><c> beauty</c><01:04:10.720><c> is</c><01:04:11.039><c> let's</c><01:04:11.200><c> say</c><01:04:11.359><c> now</c><01:04:11.599><c> you</c><01:04:11.760><c> want</c>

And the beauty is let's say now you want

And the beauty is let's say now you want
to<01:04:12.079><c> add</c><01:04:12.720><c> the</c><01:04:13.599><c> voice</c><01:04:13.920><c> feature.</c><01:04:15.359><c> I</c><01:04:15.680><c> don't</c><01:04:15.920><c> only</c>

to add the voice feature. I don't only

to add the voice feature. I don't only
want<01:04:16.480><c> the</c><01:04:16.720><c> answer</c><01:04:16.960><c> but</c><01:04:17.200><c> also</c><01:04:17.359><c> the</c><01:04:17.599><c> final</c>

want the answer but also the final

want the answer but also the final
response<01:04:18.240><c> in</c><01:04:18.400><c> the</c><01:04:18.480><c> form</c><01:04:18.640><c> of</c><01:04:18.799><c> voice.</c><01:04:20.160><c> So</c><01:04:20.400><c> far</c><01:04:21.119><c> I</c>

response in the form of voice. So far I

response in the form of voice. So far I
have<01:04:21.680><c> done</c><01:04:21.920><c> this.</c><01:04:22.480><c> I'm</c><01:04:22.720><c> just</c><01:04:22.880><c> reducing</c><01:04:23.359><c> the</c>

have done this. I'm just reducing the

have done this. I'm just reducing the
image<01:04:24.160><c> so</c><01:04:24.400><c> that</c><01:04:25.039><c> everything</c><01:04:25.599><c> fits</c><01:04:25.920><c> in.</c><01:04:27.200><c> So</c><01:04:27.440><c> far</c>

image so that everything fits in. So far

image so that everything fits in. So far
we<01:04:28.480><c> have</c><01:04:28.720><c> done</c><01:04:28.880><c> this.</c><01:04:29.599><c> We</c><01:04:29.839><c> ask</c><01:04:30.079><c> a</c><01:04:30.319><c> question.</c><01:04:30.799><c> It</c>

we have done this. We ask a question. It

we have done this. We ask a question. It
goes<01:04:31.280><c> to</c><01:04:31.359><c> a</c><01:04:31.520><c> strands</c><01:04:31.839><c> agent.</c><01:04:32.720><c> It</c><01:04:32.960><c> uses</c><01:04:33.280><c> this</c>

goes to a strands agent. It uses this

goes to a strands agent. It uses this
retrieval<01:04:34.000><c> tool</c><01:04:34.640><c> custom</c><01:04:35.039><c> tool</c><01:04:35.280><c> that</c><01:04:35.520><c> we</c><01:04:35.680><c> have</c>

retrieval tool custom tool that we have

retrieval tool custom tool that we have
created.<01:04:36.960><c> It</c><01:04:37.200><c> gets</c><01:04:37.440><c> the</c><01:04:37.760><c> relevant</c><01:04:38.079><c> chunk</c>

created. It gets the relevant chunk

created. It gets the relevant chunk
which<01:04:38.559><c> are</c><01:04:38.720><c> nothing</c><01:04:38.880><c> but</c><01:04:39.119><c> the</c><01:04:39.920><c> shortlisted</c>

which are nothing but the shortlisted

which are nothing but the shortlisted
pages<01:04:41.839><c> and</c><01:04:42.160><c> then</c>

pages and then

pages and then
it<01:04:43.920><c> uses</c><01:04:45.039><c> any</c><01:04:45.359><c> of</c><01:04:45.520><c> these</c><01:04:46.079><c> models</c><01:04:46.720><c> let's</c><01:04:46.960><c> say</c>

it uses any of these models let's say

it uses any of these models let's say
bedrock<01:04:47.599><c> colama</c><01:04:48.160><c> whatever</c><01:04:48.799><c> to</c><01:04:49.039><c> generate</c><01:04:49.359><c> the</c>

bedrock colama whatever to generate the

bedrock colama whatever to generate the
final<01:04:50.000><c> response</c><01:04:51.039><c> and</c><01:04:51.599><c> to</c><01:04:51.920><c> generate</c><01:04:52.319><c> this</c><01:04:52.960><c> it</c>

final response and to generate this it

final response and to generate this it
uses<01:04:53.680><c> this</c><01:04:53.920><c> image</c><01:04:54.319><c> reader</c><01:04:54.640><c> tool.</c><01:04:55.359><c> Now</c><01:04:55.599><c> what</c><01:04:55.839><c> we</c>

uses this image reader tool. Now what we

uses this image reader tool. Now what we
have<01:04:56.000><c> to</c><01:04:56.079><c> do</c><01:04:56.240><c> is</c><01:04:56.400><c> to</c><01:04:56.559><c> add</c><01:04:56.880><c> voice</c>

have to do is to add voice

have to do is to add voice
functionality.<01:04:57.760><c> I</c><01:04:57.920><c> will</c><01:04:58.079><c> just</c><01:04:58.240><c> use</c><01:04:58.400><c> the</c><01:04:58.799><c> speak</c>

functionality. I will just use the speak

functionality. I will just use the speak
uh<01:04:59.680><c> tool.</c><01:05:00.079><c> That's</c><01:05:00.319><c> all.</c><01:05:00.799><c> Just</c><01:05:01.200><c> one</c><01:05:02.000><c> uh</c><01:05:02.400><c> import.</c>

uh tool. That's all. Just one uh import.

uh tool. That's all. Just one uh import.
Okay.

Okay.

Okay.
And

And

And
that<01:05:08.079><c> is</c><01:05:08.240><c> what</c><01:05:08.400><c> we</c><01:05:08.559><c> are</c><01:05:08.640><c> doing.</c><01:05:08.880><c> We</c><01:05:09.039><c> are</c><01:05:09.200><c> just</c>

that is what we are doing. We are just

that is what we are doing. We are just
adding<01:05:10.160><c> speak</c><01:05:10.480><c> here.</c>

adding speak here.

adding speak here.
And<01:05:12.480><c> again</c><01:05:12.720><c> the</c><01:05:12.880><c> system</c><01:05:13.200><c> prompt</c><01:05:13.520><c> remains</c><01:05:13.839><c> the</c>

And again the system prompt remains the

And again the system prompt remains the
same.<01:05:15.039><c> And</c><01:05:15.200><c> I'm</c><01:05:15.440><c> quering</c><01:05:15.839><c> the</c><01:05:16.000><c> same</c><01:05:16.160><c> thing.</c>

same. And I'm quering the same thing.

same. And I'm quering the same thing.
And<01:05:17.119><c> now</c><01:05:17.280><c> when</c><01:05:17.520><c> I</c><01:05:17.680><c> ask</c><01:05:17.920><c> this</c><01:05:18.160><c> question.</c><01:05:18.559><c> So</c>

And now when I ask this question. So

And now when I ask this question. So
let's<01:05:18.880><c> say</c><01:05:19.039><c> let's</c><01:05:19.359><c> ask</c><01:05:19.520><c> this</c><01:05:19.839><c> question.</c><01:05:20.240><c> Okay.</c>

let's say let's ask this question. Okay.

let's say let's ask this question. Okay.
So<01:05:21.359><c> let</c><01:05:21.599><c> me</c><01:05:21.760><c> run</c><01:05:21.920><c> this</c>

So let me run this

So let me run this
and<01:05:25.760><c> let</c><01:05:26.000><c> me</c><01:05:26.559><c> let</c><01:05:26.880><c> me</c><01:05:27.039><c> just</c><01:05:27.359><c> ask</c><01:05:27.599><c> in</c><01:05:27.839><c> the</c>

and let me let me just ask in the

and let me let me just ask in the
question<01:05:28.240><c> itself</c><01:05:29.599><c> explain</c><01:05:30.000><c> the</c><01:05:30.240><c> answer</c><01:05:30.720><c> over</c>

question itself explain the answer over

question itself explain the answer over
a<01:05:31.359><c> female</c><01:05:31.839><c> voice</c><01:05:32.160><c> in</c><01:05:32.319><c> a</c><01:05:32.960><c> natural</c><01:05:33.440><c> way.</c>

And<01:05:38.160><c> let's</c><01:05:38.480><c> see.</c>

And<01:05:43.680><c> now</c><01:05:44.079><c> let's</c><01:05:44.960><c> run</c><01:05:45.200><c> this.</c>

I<01:05:50.720><c> hope</c><01:05:50.880><c> I'm</c><01:05:51.280><c> connected</c><01:05:51.599><c> with</c><01:05:51.760><c> the</c><01:05:51.920><c> internet</c>

I hope I'm connected with the internet

I hope I'm connected with the internet
but<01:05:52.640><c> let's</c><01:05:52.960><c> see.</c>

So<01:05:57.280><c> when</c><01:05:57.599><c> you</c><01:05:57.920><c> run</c><01:05:58.160><c> this</c><01:05:58.640><c> uh</c><01:05:58.799><c> code</c><01:05:59.039><c> in</c><01:05:59.280><c> your</c>

So when you run this uh code in your

So when you run this uh code in your
environment<01:06:00.720><c> you</c><01:06:01.039><c> can</c><01:06:01.280><c> simply</c><01:06:01.920><c> remove</c><01:06:02.240><c> the</c>

environment you can simply remove the

environment you can simply remove the
system<01:06:02.799><c> prompt</c><01:06:03.839><c> you</c><01:06:04.000><c> will</c><01:06:04.160><c> still</c><01:06:04.400><c> get</c><01:06:04.480><c> the</c>

system prompt you will still get the

system prompt you will still get the
right<01:06:04.880><c> answer.</c><01:06:05.280><c> In</c><01:06:05.440><c> fact</c><01:06:06.160><c> try</c><01:06:06.400><c> this</c><01:06:06.720><c> prompt.</c><01:06:07.039><c> I</c>

right answer. In fact try this prompt. I

right answer. In fact try this prompt. I
have<01:06:07.280><c> not</c><01:06:07.440><c> tried</c><01:06:07.680><c> but</c><01:06:07.920><c> try</c><01:06:08.160><c> this</c><01:06:08.799><c> change</c><01:06:09.039><c> this</c>

have not tried but try this change this

have not tried but try this change this
prompt<01:06:09.760><c> and</c><01:06:10.000><c> say</c><01:06:10.160><c> that</c><01:06:10.640><c> mail</c><01:06:10.960><c> voice</c><01:06:11.599><c> or</c>

prompt and say that mail voice or

prompt and say that mail voice or
something<01:06:12.079><c> like</c><01:06:12.240><c> that</c><01:06:12.640><c> right</c><01:06:13.119><c> robotic</c><01:06:13.920><c> uh</c><01:06:14.319><c> uh</c>

something like that right robotic uh uh

something like that right robotic uh uh
way<01:06:15.039><c> of</c><01:06:15.359><c> uh</c><01:06:15.599><c> you</c><01:06:15.760><c> know</c><01:06:16.000><c> not</c><01:06:16.160><c> a</c><01:06:16.400><c> natural</c><01:06:16.640><c> way</c>

way of uh you know not a natural way

way of uh you know not a natural way
maybe<01:06:17.119><c> robotic</c><01:06:17.599><c> way</c><01:06:17.839><c> something</c><01:06:18.079><c> like</c><01:06:18.240><c> that.</c>

maybe robotic way something like that.

maybe robotic way something like that.
The<01:06:19.520><c> idea</c><01:06:19.760><c> is</c><01:06:20.960><c> see</c><01:06:21.200><c> that</c><01:06:21.440><c> whether</c><01:06:21.839><c> strands</c><01:06:22.480><c> is</c>

The idea is see that whether strands is

The idea is see that whether strands is
able<01:06:23.280><c> to</c>

able to

able to
you<01:06:25.200><c> know</c><01:06:25.440><c> forward</c><01:06:25.839><c> that</c><01:06:26.160><c> information</c><01:06:26.640><c> to</c><01:06:26.880><c> the</c>

you know forward that information to the

you know forward that information to the
model<01:06:27.359><c> or</c><01:06:27.520><c> not</c><01:06:28.559><c> right</c><01:06:28.799><c> so</c><01:06:29.119><c> you</c><01:06:29.359><c> don't</c><01:06:29.520><c> need</c><01:06:29.599><c> a</c>

model or not right so you don't need a

model or not right so you don't need a
system<01:06:30.079><c> prompt</c><01:06:31.119><c> uh</c><01:06:31.520><c> it</c><01:06:31.760><c> may</c><01:06:32.000><c> be</c><01:06:32.400><c> because</c><01:06:32.640><c> of</c><01:06:32.880><c> my</c>

system prompt uh it may be because of my

system prompt uh it may be because of my
internet<01:06:33.760><c> uh</c><01:06:33.920><c> but</c><01:06:34.640><c> it's</c><01:06:35.039><c> it</c><01:06:35.359><c> doesn't</c><01:06:35.520><c> take</c>

internet uh but it's it doesn't take

internet uh but it's it doesn't take
that<01:06:35.920><c> much</c><01:06:36.079><c> of</c><01:06:36.319><c> time</c><01:06:36.799><c> you</c><01:06:37.039><c> just</c><01:06:37.200><c> give</c><01:06:37.359><c> it</c><01:06:37.440><c> a</c>

that much of time you just give it a

that much of time you just give it a
shot<01:06:37.839><c> it</c><01:06:38.000><c> should</c><01:06:38.160><c> work</c><01:06:38.400><c> fine</c><01:06:38.799><c> okay</c><01:06:39.920><c> so</c><01:06:40.799><c> that's</c>

shot it should work fine okay so that's

shot it should work fine okay so that's
what<01:06:41.440><c> I</c><01:06:42.000><c> uh</c><01:06:42.160><c> I</c><01:06:42.480><c> had</c><01:06:43.119><c> uh</c><01:06:43.599><c> for</c><01:06:43.839><c> for</c><01:06:44.640><c> uh</c><01:06:44.880><c> this</c>

what I uh I had uh for for uh this

what I uh I had uh for for uh this
particular<01:06:45.839><c> uh</c><01:06:46.000><c> workshop</c>

particular uh workshop

particular uh workshop
uh<01:06:48.559><c> I</c><01:06:48.960><c> would</c><01:06:49.440><c> okay</c><01:06:49.680><c> it's</c><01:06:50.000><c> now</c><01:06:50.640><c> running</c><01:06:50.960><c> so</c><01:06:51.200><c> it's</c>

uh I would okay it's now running so it's

uh I would okay it's now running so it's
little<01:06:52.880><c> slow</c>

little slow

little slow
but<01:06:54.880><c> let</c><01:06:55.200><c> me</c>

but let me

but let me
so<01:06:58.079><c> it</c><01:06:58.240><c> is</c><01:06:58.400><c> now</c><01:06:58.640><c> able</c><01:06:58.880><c> to</c><01:07:00.319><c> generate</c><01:07:00.799><c> the</c><01:07:01.599><c> images</c>

so it is now able to generate the images

so it is now able to generate the images
I<01:07:02.640><c> mean</c><01:07:02.799><c> shortlisted</c><01:07:03.599><c> the</c><01:07:03.920><c> images</c><01:07:05.039><c> and</c><01:07:05.280><c> now</c><01:07:05.440><c> it</c>

I mean shortlisted the images and now it

I mean shortlisted the images and now it
should<01:07:05.920><c> speak</c><01:07:07.119><c> in</c><01:07:07.359><c> a</c><01:07:07.520><c> female</c><01:07:07.920><c> voice</c>

so<01:07:17.039><c> while</c><01:07:17.440><c> that</c><01:07:17.839><c> happens</c><01:07:18.480><c> Okay,</c>

so while that happens Okay,

so while that happens Okay,
&gt;&gt; trophic<01:07:19.280><c> levels</c><01:07:19.599><c> are</c><01:07:19.760><c> the</c><01:07:19.920><c> different</c><01:07:20.160><c> feeding</c>

&gt;&gt; trophic levels are the different feeding

&gt;&gt; trophic levels are the different feeding
positions<01:07:20.960><c> in</c><01:07:21.200><c> a</c><01:07:21.359><c> food</c><01:07:21.599><c> chain</c><01:07:22.240><c> representing</c>

positions in a food chain representing

positions in a food chain representing
the<01:07:22.960><c> flow</c><01:07:23.200><c> of</c><01:07:23.359><c> energy</c><01:07:23.760><c> through</c><01:07:23.920><c> an</c><01:07:24.160><c> ecosystem.</c>

the flow of energy through an ecosystem.

the flow of energy through an ecosystem.
There<01:07:25.599><c> are</c><01:07:25.839><c> typically</c><01:07:26.160><c> four.</c>

There are typically four.

There are typically four.
&gt;&gt; Okay.<01:07:26.799><c> So,</c><01:07:27.119><c> let</c><01:07:27.359><c> me</c><01:07:27.520><c> just</c><01:07:28.079><c> stop</c><01:07:28.400><c> this</c><01:07:28.880><c> and</c>

&gt;&gt; Okay. So, let me just stop this and

&gt;&gt; Okay. So, let me just stop this and
let's<01:07:29.359><c> say</c><01:07:29.520><c> if</c><01:07:29.760><c> I</c><01:07:30.400><c> let's</c><01:07:30.720><c> try</c><01:07:30.880><c> this.</c><01:07:31.200><c> Okay.</c><01:07:32.240><c> Um,</c>

let's say if I let's try this. Okay. Um,

let's say if I let's try this. Okay. Um,
let<01:07:34.400><c> me</c><01:07:34.559><c> delete</c><01:07:34.880><c> this</c><01:07:35.359><c> system</c><01:07:35.680><c> prompt</c>

let me delete this system prompt

let me delete this system prompt
and

and

and
let<01:07:39.839><c> me</c><01:07:40.000><c> just</c><01:07:40.319><c> have</c><01:07:40.480><c> this</c><01:07:40.880><c> model</c><01:07:41.280><c> and</c><01:07:41.520><c> the</c>

let me just have this model and the

let me just have this model and the
tools.<01:07:42.000><c> There</c><01:07:42.160><c> is</c><01:07:42.319><c> no</c><01:07:42.559><c> speak,</c><01:07:43.039><c> nothing,</c><01:07:43.520><c> no</c>

tools. There is no speak, nothing, no

tools. There is no speak, nothing, no
system<01:07:44.160><c> prompt.</c><01:07:44.960><c> There's</c><01:07:45.280><c> nothing</c><01:07:45.520><c> there.</c>

system prompt. There's nothing there.

system prompt. There's nothing there.
And<01:07:46.880><c> here</c><01:07:47.280><c> I</c><01:07:47.520><c> will</c><01:07:47.680><c> change</c><01:07:47.920><c> this</c><01:07:48.160><c> to</c><01:07:48.319><c> a</c><01:07:48.960><c> male</c>

And here I will change this to a male

And here I will change this to a male
voice.<01:07:50.240><c> Okay.</c>

voice. Okay.

voice. Okay.
And<01:07:53.839><c> uh</c><01:07:54.079><c> I'll</c><01:07:54.400><c> give</c><01:07:54.480><c> it</c><01:07:54.640><c> a</c><01:07:54.799><c> shot.</c><01:07:55.200><c> Let</c><01:07:55.520><c> this</c><01:07:56.319><c> I</c>

And uh I'll give it a shot. Let this I

And uh I'll give it a shot. Let this I
don't<01:07:56.720><c> want</c><01:07:56.880><c> to</c><01:07:57.039><c> interrupt.</c>

don't want to interrupt.

don't want to interrupt.
&gt;&gt; Which<01:07:58.400><c> are</c><01:07:58.640><c> small</c><01:07:58.960><c> carnivores</c><01:07:59.520><c> that</c><01:07:59.680><c> eat</c>

&gt;&gt; Which are small carnivores that eat

&gt;&gt; Which are small carnivores that eat
herbivores.<01:08:01.119><c> These</c><01:08:01.440><c> might</c><01:08:01.680><c> include</c><01:08:02.160><c> frogs,</c>

herbivores. These might include frogs,

herbivores. These might include frogs,
small<01:08:03.280><c> birds</c><01:08:03.680><c> or</c><01:08:04.000><c> foxes.</c><01:08:05.280><c> The</c><01:08:05.520><c> fourth</c><01:08:05.839><c> trophic</c>

small birds or foxes. The fourth trophic

small birds or foxes. The fourth trophic
level<01:08:06.559><c> is</c><01:08:06.880><c> occupied</c><01:08:07.359><c> by</c><01:08:07.599><c> tertiary</c><01:08:08.160><c> consumers</c>

level is occupied by tertiary consumers

level is occupied by tertiary consumers
or<01:08:09.039><c> top</c><01:08:09.359><c> carnivores.</c>

or top carnivores.

or top carnivores.
&gt;&gt; You<01:08:10.240><c> can</c><01:08:10.319><c> in</c><01:08:10.480><c> fact</c><01:08:10.720><c> say</c><01:08:10.960><c> something</c><01:08:11.200><c> like</c>

&gt;&gt; You can in fact say something like

&gt;&gt; You can in fact say something like
summarize<01:08:12.319><c> in</c><01:08:13.280><c> uh</c><01:08:13.440><c> you</c><01:08:13.520><c> know</c><01:08:13.760><c> 50</c><01:08:14.000><c> words</c><01:08:14.240><c> or</c><01:08:14.480><c> 100</c>

summarize in uh you know 50 words or 100

summarize in uh you know 50 words or 100
words<01:08:15.440><c> rather</c><01:08:15.680><c> than</c><01:08:15.920><c> waiting</c><01:08:16.159><c> for</c><01:08:16.400><c> this</c><01:08:16.640><c> to</c>

words rather than waiting for this to

words rather than waiting for this to
complete.

complete.

complete.
that<01:08:18.080><c> energy</c><01:08:18.480><c> transfer</c>

that energy transfer

that energy transfer
&gt;&gt; still<01:08:19.440><c> going</c><01:08:19.679><c> on</c>

just<01:08:23.199><c> give</c><01:08:23.359><c> it</c><01:08:23.520><c> a</c><01:08:23.759><c> second</c>

and

and

and
before<01:08:30.400><c> I</c><01:08:30.640><c> forget</c>

before I forget

before I forget
if<01:08:32.560><c> you</c><01:08:32.799><c> want</c><01:08:32.960><c> to</c><01:08:33.520><c> know</c><01:08:33.759><c> about</c><01:08:34.080><c> that</c>

if you want to know about that

if you want to know about that
multimodal<01:08:35.440><c> that</c><01:08:35.759><c> the</c><01:08:36.080><c> traditional</c>

multimodal that the traditional

multimodal that the traditional
technique<01:08:37.359><c> in</c><01:08:37.600><c> this</c><01:08:37.759><c> GitHub</c><01:08:38.080><c> repo</c><01:08:38.480><c> there</c><01:08:38.640><c> is</c>

technique in this GitHub repo there is

technique in this GitHub repo there is
the<01:08:39.679><c> part</c><01:08:40.000><c> three</c><01:08:40.960><c> and</c><01:08:41.359><c> here</c><01:08:42.000><c> you</c><01:08:42.239><c> will</c><01:08:42.480><c> find</c>

the part three and here you will find

the part three and here you will find
the<01:08:43.040><c> details</c><01:08:43.440><c> of</c><01:08:43.920><c> uh</c><01:08:44.319><c> that</c><01:08:45.199><c> architecture</c><01:08:46.000><c> like</c>

the details of uh that architecture like

the details of uh that architecture like
um<01:08:47.359><c> uh</c><01:08:47.440><c> this</c><01:08:47.759><c> architecture</c><01:08:48.400><c> right</c><01:08:48.880><c> and</c><01:08:49.600><c> you</c>

um uh this architecture right and you

um uh this architecture right and you
know<01:08:50.239><c> this</c><01:08:50.480><c> notebook</c><01:08:50.880><c> is</c><01:08:51.120><c> about</c><01:08:51.279><c> how</c><01:08:51.520><c> you</c><01:08:51.679><c> can</c>

know this notebook is about how you can

know this notebook is about how you can
do<01:08:52.000><c> the</c><01:08:52.239><c> same</c><01:08:52.400><c> thing</c><01:08:52.560><c> but</c><01:08:53.040><c> uh</c><01:08:53.679><c> pre-processing</c>

do the same thing but uh pre-processing

do the same thing but uh pre-processing
this<01:08:54.560><c> image</c><01:08:54.880><c> text</c><01:08:55.120><c> and</c><01:08:55.359><c> table</c><01:08:55.679><c> okay</c><01:08:55.920><c> so</c><01:08:56.239><c> just</c>

this image text and table okay so just

this image text and table okay so just
play<01:08:57.199><c> around</c><01:08:57.440><c> this</c><01:08:57.600><c> GitHub</c><01:08:58.000><c> repo</c>

play around this GitHub repo

play around this GitHub repo
okay<01:09:01.199><c> it's</c><01:09:01.679><c> done</c><01:09:02.400><c> so</c><01:09:02.799><c> now</c><01:09:03.359><c> I</c><01:09:03.679><c> will</c><01:09:03.839><c> quickly</c>

okay it's done so now I will quickly

okay it's done so now I will quickly
uh

I<01:09:10.640><c> just</c><01:09:10.799><c> created</c><01:09:11.199><c> this</c><01:09:11.600><c> agent</c><01:09:12.080><c> now</c><01:09:12.319><c> but</c><01:09:12.640><c> uh</c>

I just created this agent now but uh

I just created this agent now but uh
without<01:09:13.120><c> any</c><01:09:13.839><c> uh</c><01:09:14.319><c> system</c><01:09:14.640><c> prompt</c><01:09:16.000><c> Now</c><01:09:16.480><c> I</c><01:09:16.799><c> just</c>

without any uh system prompt Now I just

without any uh system prompt Now I just
executed<01:09:17.600><c> this</c><01:09:17.920><c> and</c><01:09:18.239><c> now</c><01:09:18.480><c> let's</c><01:09:19.359><c> run</c><01:09:19.600><c> this.</c><01:09:20.080><c> So</c>

executed this and now let's run this. So

executed this and now let's run this. So
now<01:09:20.799><c> I</c><01:09:21.040><c> am</c><01:09:21.279><c> letting</c><01:09:22.159><c> uh</c>

now I am letting uh

now I am letting uh
the<01:09:24.239><c> agent</c>

the agent

the agent
know<01:09:26.000><c> only</c><01:09:26.319><c> about</c><01:09:26.560><c> the</c><01:09:26.799><c> models</c><01:09:27.199><c> nothing</c><01:09:27.440><c> else.</c>

know only about the models nothing else.

know only about the models nothing else.
There<01:09:27.839><c> is</c><01:09:28.000><c> no</c><01:09:28.159><c> system</c><01:09:28.480><c> prompt.</c>

I<01:09:44.799><c> just</c><01:09:44.960><c> hope</c><01:09:45.199><c> we</c><01:09:45.359><c> get</c><01:09:45.520><c> a</c><01:09:45.759><c> male</c><01:09:46.000><c> voice</c><01:09:46.239><c> at</c>

I just hope we get a male voice at

I just hope we get a male voice at
least.

least.

least.
&gt;&gt; Let<01:09:49.040><c> me</c><01:09:49.279><c> explain</c><01:09:49.679><c> trophic</c><01:09:50.239><c> levels,</c><01:09:50.880><c> which</c><01:09:51.120><c> are</c>

&gt;&gt; Let me explain trophic levels, which are

&gt;&gt; Let me explain trophic levels, which are
essentially<01:09:51.759><c> the</c><01:09:52.080><c> different</c><01:09:52.319><c> feeding</c>

essentially the different feeding

essentially the different feeding
positions<01:09:53.199><c> in</c><01:09:53.359><c> a</c><01:09:53.520><c> food</c><01:09:53.759><c> chain</c><01:09:54.000><c> or</c><01:09:54.239><c> ecosystem.</c>

positions in a food chain or ecosystem.

positions in a food chain or ecosystem.
Think<01:09:55.520><c> of</c><01:09:55.679><c> them</c><01:09:55.840><c> as</c><01:09:56.000><c> the</c><01:09:56.159><c> levels</c><01:09:56.400><c> in</c><01:09:56.640><c> nature's</c>

Think of them as the levels in nature's

Think of them as the levels in nature's
dining<01:09:57.520><c> hierarchy.</c><01:09:58.480><c> Starting</c><01:09:58.800><c> at</c><01:09:58.960><c> the</c><01:09:59.199><c> base,</c>

dining hierarchy. Starting at the base,

dining hierarchy. Starting at the base,
we<01:09:59.920><c> have</c><01:10:00.080><c> the</c><01:10:00.320><c> producers.</c><01:10:01.120><c> These</c><01:10:01.360><c> are</c><01:10:01.520><c> main</c>

we have the producers. These are main

we have the producers. These are main
&gt;&gt; Okay,<01:10:03.280><c> let's</c><01:10:03.600><c> see</c><01:10:03.760><c> if</c><01:10:03.920><c> I</c><01:10:04.080><c> have</c>

boys.

boys.

boys.
Let's<01:10:30.320><c> try</c><01:10:30.719><c> this.</c>

Trophic<01:10:48.960><c> levels</c><01:10:49.360><c> are</c><01:10:49.600><c> essentially</c><01:10:50.000><c> the</c>

Trophic levels are essentially the

Trophic levels are essentially the
different<01:10:50.560><c> feeding</c><01:10:50.960><c> positions</c><01:10:51.360><c> in</c><01:10:51.600><c> a</c><01:10:51.760><c> food</c>

different feeding positions in a food

different feeding positions in a food
chain<01:10:52.640><c> showing</c><01:10:52.960><c> how</c><01:10:53.199><c> energy</c><01:10:53.600><c> flows</c><01:10:53.920><c> through</c>

chain showing how energy flows through

chain showing how energy flows through
an<01:10:54.400><c> ecosystem.</c><01:10:55.440><c> Let</c><01:10:55.679><c> me</c><01:10:55.760><c> walk</c><01:10:55.920><c> you</c><01:10:56.080><c> through</c>

an ecosystem. Let me walk you through

an ecosystem. Let me walk you through
the<01:10:56.400><c> main</c>

the main

the main
at<01:10:58.159><c> the</c><01:10:58.320><c> very</c><01:10:58.480><c> bottom</c><01:10:59.120><c> we</c><01:10:59.360><c> have</c><01:10:59.440><c> the</c>

at the very bottom we have the

at the very bottom we have the
producers.<01:11:00.640><c> You</c><01:11:00.880><c> can</c><01:11:00.960><c> try</c><01:11:01.199><c> this</c><01:11:01.440><c> out</c><01:11:01.600><c> and</c><01:11:02.000><c> see</c>

producers. You can try this out and see

producers. You can try this out and see
what<01:11:03.440><c> you</c><01:11:03.679><c> can</c><01:11:04.320><c> mention</c><01:11:04.800><c> so</c><01:11:05.040><c> that</c><01:11:05.520><c> you</c><01:11:05.760><c> can</c>

what you can mention so that you can

what you can mention so that you can
augment<01:11:06.320><c> the</c><01:11:06.560><c> tool.</c><01:11:07.360><c> In</c><01:11:07.600><c> fact,</c><01:11:08.560><c> this</c><01:11:08.800><c> is</c><01:11:09.040><c> not</c>

augment the tool. In fact, this is not

augment the tool. In fact, this is not
the<01:11:09.440><c> right</c><01:11:09.760><c> way</c><01:11:09.920><c> to</c><01:11:10.159><c> do</c><01:11:10.320><c> this</c><01:11:10.960><c> because</c><01:11:11.360><c> by</c>

the right way to do this because by

the right way to do this because by
default<01:11:12.159><c> it</c><01:11:12.400><c> is</c><01:11:12.480><c> a</c><01:11:13.280><c> female</c><01:11:13.760><c> voice.</c><01:11:14.560><c> You</c><01:11:14.800><c> can</c>

default it is a female voice. You can

default it is a female voice. You can
actually<01:11:15.280><c> change</c><01:11:15.600><c> the</c><01:11:15.840><c> behavior</c><01:11:16.480><c> of</c><01:11:16.719><c> this</c><01:11:17.280><c> uh</c>

actually change the behavior of this uh

actually change the behavior of this uh
speak<01:11:17.920><c> tool.</c><01:11:18.880><c> Okay.</c><01:11:19.440><c> So</c><01:11:19.679><c> the</c><01:11:19.920><c> way</c><01:11:20.000><c> that</c><01:11:20.159><c> you</c>

speak tool. Okay. So the way that you

speak tool. Okay. So the way that you
can<01:11:20.400><c> do</c><01:11:20.560><c> is</c><01:11:20.880><c> you</c><01:11:21.040><c> can</c><01:11:21.120><c> go</c><01:11:21.280><c> to</c><01:11:21.360><c> the</c>

can do is you can go to the

can do is you can go to the
documentation<01:11:22.239><c> and</c><01:11:22.800><c> uh</c><01:11:23.199><c> if</c><01:11:23.440><c> you</c><01:11:23.600><c> see</c><01:11:23.840><c> this</c>

documentation and uh if you see this

documentation and uh if you see this
documentation

documentation

documentation
uh<01:11:26.960><c> here</c><01:11:28.080><c> we</c><01:11:28.400><c> have</c><01:11:28.719><c> tools</c><01:11:29.760><c> and</c><01:11:30.320><c> uh</c><01:11:30.480><c> you</c><01:11:30.719><c> can</c>

uh here we have tools and uh you can

uh here we have tools and uh you can
see<01:11:32.640><c> the</c><01:11:33.040><c> overview</c>

see the overview

see the overview
and<01:11:35.280><c> if</c><01:11:35.520><c> you</c><01:11:35.679><c> see</c><01:11:35.920><c> this</c><01:11:36.239><c> here</c>

there<01:11:41.360><c> is</c><01:11:41.520><c> a</c><01:11:41.679><c> tool</c><01:11:42.080><c> spec.</c><01:11:42.560><c> Yeah,</c><01:11:43.440><c> here's</c><01:11:43.760><c> a</c>

there is a tool spec. Yeah, here's a

there is a tool spec. Yeah, here's a
tool<01:11:44.159><c> spec</c><01:11:44.480><c> for</c><01:11:44.719><c> different</c><01:11:44.960><c> tools</c><01:11:45.600><c> and</c><01:11:45.840><c> you</c>

tool spec for different tools and you

tool spec for different tools and you
can<01:11:46.159><c> mention</c><01:11:46.480><c> what</c><01:11:46.800><c> persona</c><01:11:47.440><c> that</c><01:11:47.679><c> you</c><01:11:47.920><c> want.</c>

can mention what persona that you want.

can mention what persona that you want.
So<01:11:48.320><c> that</c><01:11:48.480><c> is</c><01:11:48.560><c> a</c><01:11:48.719><c> more</c><01:11:49.360><c> deterministic</c><01:11:50.159><c> way</c><01:11:50.640><c> uh</c>

So that is a more deterministic way uh

So that is a more deterministic way uh
to<01:11:50.960><c> do</c><01:11:51.120><c> that</c><01:11:51.600><c> or</c><01:11:51.760><c> else</c><01:11:51.920><c> you</c><01:11:52.080><c> can</c><01:11:52.239><c> put</c><01:11:52.400><c> that</c><01:11:52.640><c> in</c>

to do that or else you can put that in

to do that or else you can put that in
the<01:11:53.440><c> uh</c><01:11:53.679><c> system</c><01:11:54.080><c> prompt.</c><01:11:54.640><c> Okay.</c><01:11:55.360><c> So</c><01:11:55.679><c> that's</c>

the uh system prompt. Okay. So that's

the uh system prompt. Okay. So that's
all<01:11:56.159><c> I</c><01:11:56.480><c> have.</c><01:11:56.880><c> Uh</c><01:11:57.520><c> u</c><01:11:57.760><c> if</c><01:11:58.000><c> you</c><01:11:58.159><c> have</c><01:11:58.239><c> any</c>

all I have. Uh u if you have any

all I have. Uh u if you have any
questions<01:11:58.800><c> feel</c><01:11:58.960><c> free</c><01:11:59.120><c> to</c><01:11:59.440><c> ask</c><01:11:59.760><c> or</c><01:12:00.640><c> uh</c><01:12:00.800><c> you</c>

questions feel free to ask or uh you

questions feel free to ask or uh you
know<01:12:01.520><c> uh</c><01:12:01.760><c> you</c><01:12:01.920><c> know</c><01:12:02.080><c> feel</c><01:12:02.159><c> free</c><01:12:02.400><c> to</c><01:12:02.560><c> connect</c>

know uh you know feel free to connect

know uh you know feel free to connect
and<01:12:03.760><c> u</c><01:12:04.000><c> you</c><01:12:04.159><c> know</c><01:12:04.400><c> would</c><01:12:04.560><c> be</c><01:12:04.719><c> more</c><01:12:04.880><c> than</c><01:12:05.040><c> happy</c>

and u you know would be more than happy

and u you know would be more than happy
uh<01:12:06.080><c> to</c><01:12:06.320><c> connect</c><01:12:06.640><c> offline.</c>

uh to connect offline.

uh to connect offline.
&gt;&gt; Yeah.

&gt;&gt; Yeah.

&gt;&gt; Yeah.

&gt;&gt; Yeah.
&gt;&gt; So<01:12:13.520><c> have</c><01:12:13.679><c> you</c><01:12:13.840><c> seen</c><01:12:14.159><c> any</c>

is<01:12:17.520><c> already</c><01:12:17.840><c> using</c><01:12:18.080><c> this</c><01:12:18.239><c> in</c><01:12:18.480><c> production</c><01:12:18.880><c> and</c>

is already using this in production and

is already using this in production and
what<01:12:19.360><c> type</c><01:12:19.520><c> of</c><01:12:20.000><c> scaling</c><01:12:20.640><c> uh</c>

what type of scaling uh

what type of scaling uh
&gt;&gt; yeah<01:12:22.400><c> yeah</c>

&gt;&gt; yeah yeah

&gt;&gt; yeah yeah
&gt;&gt; yeah<01:12:24.080><c> that's</c><01:12:24.239><c> a</c><01:12:24.480><c> good</c><01:12:24.560><c> question</c><01:12:25.040><c> so</c><01:12:25.520><c> we</c><01:12:25.840><c> have</c>

&gt;&gt; yeah that's a good question so we have

&gt;&gt; yeah that's a good question so we have
used<01:12:26.320><c> this</c><01:12:26.560><c> in</c><01:12:27.040><c> one</c><01:12:27.199><c> of</c><01:12:27.280><c> the</c><01:12:27.520><c> insurance</c><01:12:28.000><c> a</c>

used this in one of the insurance a

used this in one of the insurance a
leading<01:12:28.480><c> insurance</c><01:12:28.880><c> company</c><01:12:29.600><c> where</c><01:12:29.920><c> they</c><01:12:30.239><c> had</c>

leading insurance company where they had

leading insurance company where they had
u<01:12:31.520><c> the</c><01:12:31.920><c> images</c><01:12:32.320><c> of</c><01:12:32.960><c> driver</c><01:12:34.239><c> u</c><01:12:34.800><c> licenses</c><01:12:35.840><c> and</c>

u the images of driver u licenses and

u the images of driver u licenses and
they<01:12:36.560><c> have</c><01:12:36.640><c> the</c><01:12:36.880><c> images</c><01:12:37.280><c> of</c><01:12:37.600><c> insurance</c>

they have the images of insurance

they have the images of insurance
policies<01:12:38.560><c> and</c><01:12:38.800><c> all</c><01:12:38.960><c> that</c><01:12:39.679><c> and</c><01:12:40.239><c> we</c><01:12:40.480><c> tried</c><01:12:40.719><c> with</c>

policies and all that and we tried with

policies and all that and we tried with
different<01:12:41.199><c> techniques</c><01:12:41.760><c> one</c><01:12:41.920><c> of</c><01:12:42.000><c> the</c>

different techniques one of the

different techniques one of the
technique<01:12:42.400><c> that</c><01:12:42.560><c> we</c><01:12:42.719><c> used</c><01:12:42.880><c> was</c><01:12:43.120><c> OCR</c><01:12:43.840><c> which</c>

technique that we used was OCR which

technique that we used was OCR which
worked<01:12:44.400><c> fine</c><01:12:45.120><c> uh</c><01:12:45.280><c> but</c><01:12:45.440><c> CalPali</c><01:12:46.000><c> was</c><01:12:46.239><c> working</c>

worked fine uh but CalPali was working

worked fine uh but CalPali was working
pretty

pretty

pretty
And<01:12:47.920><c> it</c><01:12:48.239><c> was</c><01:12:48.960><c> the</c><01:12:49.199><c> only</c><01:12:49.440><c> drawback</c><01:12:49.840><c> which</c><01:12:50.000><c> I</c>

And it was the only drawback which I

And it was the only drawback which I
have<01:12:50.320><c> seen</c><01:12:51.280><c> with</c><01:12:51.520><c> this</c><01:12:51.760><c> call</c><01:12:52.000><c> pal</c><01:12:53.120><c> model</c><01:12:53.440><c> is</c><01:12:54.080><c> it</c>

have seen with this call pal model is it

have seen with this call pal model is it
is<01:12:54.400><c> very</c><01:12:54.640><c> heavy</c><01:12:55.440><c> but</c><01:12:56.000><c> uh</c><01:12:56.080><c> that</c><01:12:56.320><c> heaviness</c>

is very heavy but uh that heaviness

is very heavy but uh that heaviness
comes<01:12:56.960><c> only</c><01:12:57.199><c> at</c><01:12:57.360><c> the</c><01:12:57.520><c> time</c><01:12:57.679><c> of</c><01:12:57.840><c> data</c>

comes only at the time of data

comes only at the time of data
injection.<01:12:58.640><c> So</c><01:12:58.800><c> when</c><01:12:58.960><c> you</c><01:12:59.120><c> create</c><01:12:59.280><c> the</c>

injection. So when you create the

injection. So when you create the
embeddings<01:13:00.000><c> one</c><01:13:00.239><c> that</c><01:13:00.400><c> is</c><01:13:00.480><c> done</c><01:13:00.719><c> at</c><01:13:00.880><c> the</c><01:13:01.040><c> query</c>

embeddings one that is done at the query

embeddings one that is done at the query
time<01:13:01.440><c> it</c><01:13:01.600><c> is</c><01:13:01.760><c> pretty</c><01:13:02.000><c> fast.</c><01:13:02.800><c> Okay.</c><01:13:03.360><c> Uh</c><01:13:03.679><c> but</c>

time it is pretty fast. Okay. Uh but

time it is pretty fast. Okay. Uh but
when<01:13:05.040><c> you</c><01:13:05.199><c> are</c><01:13:05.360><c> putting</c><01:13:05.679><c> the</c><01:13:05.840><c> data</c><01:13:06.159><c> at</c><01:13:06.400><c> that</c>

when you are putting the data at that

when you are putting the data at that
time<01:13:06.719><c> it's</c><01:13:06.960><c> little</c><01:13:07.199><c> heavy.</c><01:13:08.080><c> Okay.</c><01:13:08.640><c> And</c><01:13:09.120><c> uh</c><01:13:09.840><c> uh</c>

time it's little heavy. Okay. And uh uh

time it's little heavy. Okay. And uh uh
I<01:13:10.320><c> guess</c><01:13:11.600><c> if</c><01:13:11.920><c> you</c><01:13:12.000><c> are</c><01:13:12.159><c> thinking</c><01:13:12.560><c> that</c><01:13:13.120><c> if</c><01:13:13.280><c> you</c>

I guess if you are thinking that if you

I guess if you are thinking that if you
have<01:13:13.679><c> 1,000</c><01:13:14.800><c> documents</c><01:13:15.440><c> each</c><01:13:15.679><c> has</c><01:13:16.320><c> 1,000</c>

have 1,000 documents each has 1,000

have 1,000 documents each has 1,000
pages,<01:13:17.760><c> you</c><01:13:18.000><c> will</c><01:13:18.159><c> do</c><01:13:18.239><c> a</c><01:13:18.480><c> search</c><01:13:19.120><c> among</c><01:13:19.520><c> all</c>

pages, you will do a search among all

pages, you will do a search among all
those<01:13:19.920><c> images.</c><01:13:20.480><c> That</c><01:13:20.640><c> is</c><01:13:20.800><c> not</c><01:13:20.960><c> how</c><01:13:21.199><c> it</c><01:13:21.440><c> works.</c>

those images. That is not how it works.

those images. That is not how it works.
Because<01:13:22.880><c> imagine</c><01:13:23.440><c> if</c><01:13:23.760><c> I</c><01:13:23.920><c> ask</c><01:13:24.080><c> you</c><01:13:24.239><c> the</c><01:13:24.400><c> same</c>

Because imagine if I ask you the same

Because imagine if I ask you the same
question.<01:13:25.760><c> Forget</c><01:13:26.080><c> about</c><01:13:26.320><c> all</c><01:13:26.480><c> this.</c><01:13:27.199><c> If</c><01:13:27.440><c> you</c>

question. Forget about all this. If you

question. Forget about all this. If you
use<01:13:28.080><c> a</c><01:13:28.400><c> text</c><01:13:28.640><c> based</c><01:13:28.960><c> embedding</c><01:13:29.520><c> model</c><01:13:30.000><c> and</c><01:13:30.239><c> if</c>

use a text based embedding model and if

use a text based embedding model and if
you<01:13:30.640><c> have</c><01:13:30.719><c> a</c><01:13:30.880><c> book</c><01:13:31.040><c> of</c>

you have a book of

you have a book of
1<01:13:33.040><c> million</c><01:13:33.360><c> pages,</c><01:13:34.560><c> you</c><01:13:34.800><c> have</c><01:13:34.960><c> 100</c><01:13:35.360><c> million</c>

1 million pages, you have 100 million

1 million pages, you have 100 million
vectors<01:13:36.159><c> and</c><01:13:36.400><c> when</c><01:13:36.560><c> you</c><01:13:36.719><c> ask</c><01:13:36.880><c> a</c><01:13:37.120><c> question,</c>

vectors and when you ask a question,

vectors and when you ask a question,
does<01:13:37.920><c> the</c><01:13:38.080><c> vector</c><01:13:38.400><c> database</c><01:13:38.880><c> search</c><01:13:39.120><c> for</c><01:13:39.280><c> all</c>

does the vector database search for all

does the vector database search for all
the<01:13:39.600><c> vectors?</c><01:13:40.080><c> No,</c><01:13:40.800><c> there</c><01:13:41.040><c> is</c><01:13:41.199><c> a</c><01:13:41.360><c> different</c>

the vectors? No, there is a different

the vectors? No, there is a different
indexing<01:13:42.080><c> techniques</c><01:13:42.400><c> that</c><01:13:42.560><c> all</c><01:13:42.719><c> the</c>

indexing techniques that all the

indexing techniques that all the
database<01:13:43.360><c> uses.</c><01:13:44.080><c> Same</c><01:13:44.320><c> indexing</c><01:13:44.880><c> technique</c>

database uses. Same indexing technique

database uses. Same indexing technique
are<01:13:46.400><c> used</c><01:13:46.640><c> here</c><01:13:46.880><c> as</c><01:13:47.120><c> well.</c><01:13:47.679><c> It's</c><01:13:47.920><c> just</c><01:13:48.080><c> that</c>

are used here as well. It's just that

are used here as well. It's just that
now<01:13:49.120><c> the</c><01:13:49.360><c> vectors</c><01:13:49.760><c> represent</c><01:13:50.320><c> different</c>

now the vectors represent different

now the vectors represent different
thing.<01:13:50.960><c> Now</c><01:13:51.120><c> the</c><01:13:51.360><c> vector</c><01:13:51.679><c> represent</c><01:13:52.080><c> patches.</c>

thing. Now the vector represent patches.

thing. Now the vector represent patches.
In<01:13:53.040><c> the</c><01:13:53.199><c> previous</c><01:13:53.440><c> case,</c><01:13:53.679><c> the</c><01:13:53.920><c> vector</c>

In the previous case, the vector

In the previous case, the vector
represents<01:13:54.719><c> images</c><01:13:55.120><c> or</c><01:13:55.600><c> sorry</c><01:13:56.000><c> uh</c><01:13:56.080><c> a</c><01:13:56.320><c> chunk</c><01:13:56.560><c> of</c>

represents images or sorry uh a chunk of

represents images or sorry uh a chunk of
text<01:13:57.840><c> but</c><01:13:58.239><c> uh</c><01:13:58.320><c> that</c><01:13:58.640><c> semantic</c><01:13:59.120><c> search</c><01:13:59.520><c> happens</c>

text but uh that semantic search happens

text but uh that semantic search happens
very<01:14:00.640><c> efficiently</c><01:14:01.679><c> uh</c><01:14:01.840><c> using</c><01:14:02.239><c> a</c><01:14:02.480><c> different</c>

very efficiently uh using a different

very efficiently uh using a different
indexing<01:14:03.280><c> technique.</c><01:14:03.760><c> One</c><01:14:03.920><c> of</c><01:14:04.000><c> the</c><01:14:04.159><c> technique</c>

indexing technique. One of the technique

indexing technique. One of the technique
that<01:14:04.560><c> we</c><01:14:04.719><c> use</c><01:14:04.960><c> is</c><01:14:06.080><c> I</c><01:14:06.320><c> think</c><01:14:06.480><c> hierarchical</c>

that we use is I think hierarchical

that we use is I think hierarchical
small<01:14:07.840><c> world</c><01:14:08.239><c> navigation</c><01:14:09.360><c> u</c><01:14:09.600><c> so</c><01:14:09.840><c> where</c><01:14:10.480><c> it</c>

small world navigation u so where it

small world navigation u so where it
uses<01:14:11.120><c> a</c><01:14:11.600><c> treebased</c><01:14:12.560><c> uh</c><01:14:12.640><c> you</c><01:14:12.800><c> know</c><01:14:12.960><c> structure</c>

uses a treebased uh you know structure

uses a treebased uh you know structure
uh<01:14:14.080><c> it</c><01:14:14.400><c> just</c><01:14:14.640><c> finds</c><01:14:15.199><c> uh</c><01:14:15.280><c> the</c><01:14:15.440><c> root</c><01:14:15.679><c> node</c><01:14:16.000><c> uh</c><01:14:16.159><c> I</c>

uh it just finds uh the root node uh I

uh it just finds uh the root node uh I
mean<01:14:16.480><c> it</c><01:14:16.640><c> it</c><01:14:16.880><c> starts</c><01:14:17.120><c> on</c><01:14:17.280><c> the</c><01:14:17.440><c> top</c><01:14:17.760><c> layer</c><01:14:18.159><c> it</c>

mean it it starts on the top layer it

mean it it starts on the top layer it
finds<01:14:18.640><c> one</c><01:14:18.880><c> of</c><01:14:18.960><c> the</c><01:14:19.199><c> closest</c><01:14:19.840><c> node</c><01:14:20.560><c> and</c>

finds one of the closest node and

finds one of the closest node and
whichever<01:14:21.199><c> node</c><01:14:21.440><c> is</c><01:14:21.600><c> closest</c><01:14:22.159><c> then</c><01:14:22.400><c> it</c><01:14:22.560><c> goes</c>

whichever node is closest then it goes

whichever node is closest then it goes
down<01:14:23.040><c> and</c><01:14:23.280><c> finds</c><01:14:23.520><c> its</c><01:14:23.840><c> neighbor</c><01:14:24.239><c> so</c><01:14:24.400><c> you</c><01:14:24.640><c> are</c>

down and finds its neighbor so you are

down and finds its neighbor so you are
just<01:14:25.040><c> you</c><01:14:25.199><c> can</c><01:14:25.360><c> think</c><01:14:25.440><c> of</c><01:14:25.600><c> it</c><01:14:25.760><c> like</c><01:14:26.480><c> uh</c><01:14:26.880><c> uh</c><01:14:27.120><c> you</c>

just you can think of it like uh uh you

just you can think of it like uh uh you
know<01:14:27.360><c> in</c><01:14:27.760><c> u</c><01:14:28.640><c> in</c><01:14:28.880><c> computer</c><01:14:29.280><c> science</c><01:14:29.520><c> we</c><01:14:29.760><c> have</c>

know in u in computer science we have

know in u in computer science we have
tree<01:14:30.560><c> pruning</c><01:14:31.199><c> right</c><01:14:31.600><c> so</c><01:14:31.840><c> that's</c><01:14:32.000><c> what</c><01:14:32.159><c> we</c><01:14:32.320><c> do</c>

tree pruning right so that's what we do

tree pruning right so that's what we do
so<01:14:32.719><c> it</c><01:14:32.880><c> reduces</c><01:14:33.440><c> the</c><01:14:34.000><c> search</c><01:14:34.320><c> space.</c><01:14:34.719><c> Yeah.</c>

so it reduces the search space. Yeah.

so it reduces the search space. Yeah.
&gt;&gt; So<01:14:36.159><c> a</c><01:14:36.320><c> quick</c><01:14:36.560><c> follow.</c>

&gt;&gt; So a quick follow.

&gt;&gt; So a quick follow.
&gt;&gt; Yeah.<01:14:37.600><c> So</c><01:14:37.840><c> can</c><01:14:38.080><c> we</c><01:14:38.239><c> see</c>

&gt;&gt; Yeah. So can we see

&gt;&gt; Yeah. So can we see
more<01:14:40.400><c> companies</c>

more companies

more companies
this<01:14:43.040><c> can</c><01:14:43.600><c> see</c><01:14:43.840><c> this</c><01:14:44.159><c> as</c><01:14:44.400><c> a</c><01:14:44.719><c> replacement</c><01:14:45.199><c> for</c>

this can see this as a replacement for

this can see this as a replacement for
&gt;&gt; no<01:14:46.159><c> traditional?</c>

&gt;&gt; no traditional?

&gt;&gt; no traditional?
&gt;&gt; Yeah,<01:14:47.120><c> that's</c><01:14:47.280><c> a</c><01:14:47.440><c> good</c><01:14:47.600><c> question.</c><01:14:48.000><c> No,</c><01:14:48.159><c> I</c>

&gt;&gt; Yeah, that's a good question. No, I

&gt;&gt; Yeah, that's a good question. No, I
don't<01:14:48.480><c> think</c><01:14:48.640><c> this</c><01:14:48.800><c> is</c><01:14:48.880><c> a</c><01:14:49.040><c> replacement.</c><01:14:49.760><c> This</c>

don't think this is a replacement. This

don't think this is a replacement. This
is<01:14:50.080><c> just</c><01:14:50.320><c> another</c><01:14:50.640><c> technique</c><01:14:51.440><c> and</c><01:14:51.679><c> this</c><01:14:51.840><c> is</c>

is just another technique and this is

is just another technique and this is
also<01:14:52.560><c> you</c><01:14:52.800><c> know</c>

also you know

also you know
you<01:14:54.880><c> know</c><01:14:55.360><c> it's</c><01:14:55.600><c> a</c><01:14:55.760><c> space</c><01:14:56.000><c> where</c><01:14:56.320><c> things</c><01:14:56.560><c> are</c>

you know it's a space where things are

you know it's a space where things are
changing<01:14:56.960><c> very</c><01:14:57.280><c> fast.</c><01:14:57.600><c> Right.</c><01:14:58.080><c> Um</c><01:14:58.960><c> I</c>

changing very fast. Right. Um I

changing very fast. Right. Um I
personally<01:14:59.679><c> feel</c><01:15:00.560><c> if</c><01:15:00.800><c> we</c><01:15:01.040><c> get</c><01:15:01.199><c> a</c><01:15:01.520><c> vision</c><01:15:01.920><c> based</c>

personally feel if we get a vision based

personally feel if we get a vision based
model<01:15:02.400><c> which</c><01:15:02.640><c> is</c><01:15:02.800><c> more</c><01:15:02.960><c> efficient</c><01:15:03.280><c> in</c><01:15:03.600><c> terms</c>

model which is more efficient in terms

model which is more efficient in terms
of<01:15:04.000><c> computation</c><01:15:04.960><c> this</c><01:15:05.199><c> might</c><01:15:05.440><c> be</c><01:15:05.520><c> a</c><01:15:05.760><c> good</c>

of computation this might be a good

of computation this might be a good
model.<01:15:06.640><c> Uh</c><01:15:06.880><c> but</c><01:15:07.199><c> again</c><01:15:08.400><c> this</c><01:15:08.719><c> may</c><01:15:09.040><c> work</c><01:15:09.280><c> for</c>

model. Uh but again this may work for

model. Uh but again this may work for
your<01:15:09.600><c> data</c><01:15:09.920><c> may</c><01:15:10.080><c> not</c><01:15:10.239><c> work</c><01:15:10.400><c> for</c><01:15:10.560><c> your</c><01:15:10.719><c> data.</c><01:15:10.960><c> So</c>

your data may not work for your data. So

your data may not work for your data. So
it's<01:15:11.360><c> all</c><01:15:11.520><c> about</c><01:15:11.679><c> your</c><01:15:11.920><c> data.</c><01:15:12.480><c> What</c><01:15:12.719><c> I</c><01:15:12.880><c> would</c>

it's all about your data. What I would

it's all about your data. What I would
do<01:15:13.199><c> and</c><01:15:13.440><c> what</c><01:15:13.600><c> I</c><01:15:13.760><c> do</c><01:15:13.920><c> generally</c><01:15:14.320><c> is</c><01:15:14.800><c> whenever</c><01:15:15.199><c> I</c>

do and what I do generally is whenever I

do and what I do generally is whenever I
get<01:15:15.520><c> some</c><01:15:15.760><c> problem</c><01:15:16.000><c> I</c><01:15:16.239><c> try</c><01:15:16.400><c> to</c><01:15:16.560><c> solve</c><01:15:16.800><c> with</c><01:15:17.280><c> the</c>

get some problem I try to solve with the

get some problem I try to solve with the
least<01:15:18.719><c> uh</c><01:15:18.880><c> I</c><01:15:19.120><c> mean</c><01:15:19.199><c> the</c><01:15:19.440><c> most</c><01:15:19.679><c> cost</c><01:15:19.920><c> effective</c>

least uh I mean the most cost effective

least uh I mean the most cost effective
way<01:15:21.199><c> or</c><01:15:21.520><c> most</c><01:15:22.159><c> efficient</c><01:15:22.560><c> way.</c><01:15:22.800><c> basically</c>

way or most efficient way. basically

way or most efficient way. basically
more<01:15:23.840><c> than</c><01:15:24.000><c> the</c><01:15:24.159><c> cost.</c><01:15:24.640><c> First</c><01:15:24.880><c> we</c><01:15:25.040><c> have</c><01:15:25.120><c> to</c>

more than the cost. First we have to

more than the cost. First we have to
find<01:15:25.440><c> out</c><01:15:25.920><c> which</c><01:15:26.880><c> architecture</c><01:15:27.520><c> works</c><01:15:27.840><c> fine</c>

find out which architecture works fine

find out which architecture works fine
for<01:15:28.320><c> my</c><01:15:28.560><c> data.</c><01:15:29.440><c> If</c><01:15:29.679><c> that</c><01:15:29.920><c> is</c><01:15:30.080><c> working</c><01:15:30.400><c> fine</c><01:15:30.640><c> I</c>

for my data. If that is working fine I

for my data. If that is working fine I
don't<01:15:31.280><c> why</c><01:15:31.520><c> to</c><01:15:31.760><c> complicate</c><01:15:32.159><c> things</c><01:15:32.400><c> and</c>

don't why to complicate things and

don't why to complicate things and
create<01:15:33.040><c> images</c><01:15:33.520><c> and</c><01:15:33.760><c> all</c><01:15:33.920><c> that.</c><01:15:34.320><c> I</c><01:15:34.560><c> will</c><01:15:34.719><c> go</c><01:15:34.800><c> to</c>

create images and all that. I will go to

create images and all that. I will go to
this<01:15:35.199><c> only</c><01:15:35.440><c> when</c><01:15:35.679><c> my</c><01:15:35.920><c> data</c><01:15:36.159><c> set</c><01:15:36.320><c> is</c><01:15:36.480><c> very</c><01:15:36.719><c> much</c>

this only when my data set is very much

this only when my data set is very much
converted<01:15:37.600><c> and</c><01:15:37.920><c> where</c><01:15:39.199><c> you</c><01:15:39.440><c> as</c><01:15:39.679><c> an</c><01:15:39.920><c> human</c><01:15:40.960><c> you</c>

converted and where you as an human you

converted and where you as an human you
feel<01:15:41.520><c> that</c><01:15:42.000><c> I</c><01:15:42.239><c> can</c><01:15:42.400><c> read</c><01:15:42.640><c> this</c><01:15:42.880><c> data</c><01:15:43.199><c> only</c><01:15:43.520><c> if</c><01:15:43.679><c> I</c>

feel that I can read this data only if I

feel that I can read this data only if I
look<01:15:44.000><c> at</c><01:15:44.159><c> it.</c><01:15:45.199><c> Imagine</c><01:15:45.600><c> that</c><01:15:45.840><c> you</c><01:15:46.000><c> have</c><01:15:46.080><c> a</c><01:15:46.239><c> PDF</c>

look at it. Imagine that you have a PDF

look at it. Imagine that you have a PDF
file.<01:15:47.600><c> For</c><01:15:47.840><c> that</c><01:15:48.960><c> simple</c><01:15:49.280><c> text</c><01:15:49.600><c> file</c><01:15:50.080><c> for</c><01:15:50.320><c> that</c>

file. For that simple text file for that

file. For that simple text file for that
you<01:15:52.080><c> can</c><01:15:52.480><c> get</c><01:15:52.640><c> the</c><01:15:52.880><c> answer</c><01:15:53.120><c> from</c><01:15:53.280><c> that</c><01:15:53.520><c> PDF</c>

you can get the answer from that PDF

you can get the answer from that PDF
file<01:15:54.080><c> even</c><01:15:54.239><c> if</c><01:15:54.560><c> somebody</c><01:15:55.199><c> converts</c><01:15:55.679><c> that</c><01:15:55.840><c> into</c>

file even if somebody converts that into

file even if somebody converts that into
a<01:15:56.239><c> text</c><01:15:56.480><c> file</c><01:15:56.880><c> and</c><01:15:57.120><c> give</c><01:15:57.280><c> it</c><01:15:57.360><c> to</c><01:15:57.520><c> you.</c><01:15:58.000><c> But</c>

a text file and give it to you. But

a text file and give it to you. But
let's<01:15:58.320><c> say</c><01:15:58.480><c> you</c><01:15:58.640><c> have</c><01:15:58.719><c> a</c><01:15:58.880><c> PDF</c><01:15:59.199><c> file</c><01:15:59.440><c> which</c>

let's say you have a PDF file which

let's say you have a PDF file which
contains<01:16:00.239><c> mostly</c><01:16:00.719><c> images</c><01:16:01.520><c> and</c><01:16:01.920><c> embedded</c><01:16:02.400><c> text</c>

contains mostly images and embedded text

contains mostly images and embedded text
on<01:16:02.880><c> top</c><01:16:03.040><c> of</c><01:16:03.199><c> that</c><01:16:03.520><c> then</c><01:16:03.679><c> you</c><01:16:03.840><c> will</c><01:16:04.000><c> say</c><01:16:04.080><c> that</c>

on top of that then you will say that

on top of that then you will say that
okay<01:16:04.560><c> okay</c><01:16:04.880><c> don't</c><01:16:05.120><c> give</c><01:16:05.280><c> only</c><01:16:05.520><c> text</c><01:16:05.760><c> you</c><01:16:05.920><c> give</c>

okay okay don't give only text you give

okay okay don't give only text you give
me<01:16:06.159><c> the</c><01:16:06.320><c> book</c><01:16:06.480><c> I</c><01:16:06.719><c> will</c><01:16:06.880><c> figure</c><01:16:07.120><c> out</c><01:16:07.360><c> because</c><01:16:07.600><c> I</c>

me the book I will figure out because I

me the book I will figure out because I
need<01:16:07.840><c> to</c><01:16:08.000><c> see</c><01:16:08.400><c> what</c><01:16:08.640><c> is</c><01:16:08.719><c> the</c><01:16:08.880><c> context</c><01:16:09.199><c> of</c><01:16:09.360><c> that.</c>

need to see what is the context of that.

need to see what is the context of that.
So<01:16:10.000><c> it's</c><01:16:10.239><c> just</c><01:16:10.480><c> like</c><01:16:10.719><c> it</c><01:16:11.280><c> replicates</c><01:16:11.920><c> humans</c><01:16:12.480><c> u</c>

So it's just like it replicates humans u

So it's just like it replicates humans u
uh<01:16:12.960><c> you</c><01:16:13.120><c> know</c><01:16:13.360><c> uh</c><01:16:13.520><c> behavior</c><01:16:14.159><c> to</c><01:16:14.480><c> understand</c>

uh you know uh behavior to understand

uh you know uh behavior to understand
any<01:16:15.199><c> data.</c><01:16:16.080><c> U</c><01:16:16.400><c> so</c><01:16:16.719><c> I</c><01:16:16.960><c> would</c><01:16:17.120><c> recommend</c><01:16:17.520><c> not</c><01:16:17.679><c> to</c>

any data. U so I would recommend not to

any data. U so I would recommend not to
start<01:16:18.080><c> with</c><01:16:18.320><c> this</c><01:16:18.800><c> start</c><01:16:18.960><c> with</c><01:16:19.120><c> the</c>

start with this start with the

start with this start with the
traditional<01:16:19.679><c> technique</c><01:16:20.239><c> because</c><01:16:20.560><c> that</c><01:16:20.800><c> is</c>

traditional technique because that is

traditional technique because that is
more<01:16:21.679><c> effective</c><01:16:22.400><c> um</c><01:16:22.640><c> cost</c><01:16:22.880><c> effective</c><01:16:23.679><c> and</c>

more effective um cost effective and

more effective um cost effective and
also<01:16:24.320><c> it</c><01:16:24.480><c> it</c><01:16:24.800><c> is</c><01:16:24.960><c> less</c><01:16:25.120><c> heavy</c><01:16:26.000><c> because</c><01:16:26.239><c> here</c><01:16:26.560><c> we</c>

also it it is less heavy because here we

also it it is less heavy because here we
are<01:16:26.960><c> storing</c><01:16:27.199><c> a</c><01:16:27.440><c> lot</c><01:16:27.520><c> of</c><01:16:28.000><c> vectors</c><01:16:28.400><c> for</c><01:16:28.719><c> each</c>

are storing a lot of vectors for each

are storing a lot of vectors for each
page<01:16:30.159><c> right</c><01:16:30.480><c> so</c><01:16:31.440><c> but</c><01:16:32.000><c> use</c><01:16:32.239><c> this</c><01:16:32.480><c> when</c><01:16:32.719><c> you</c><01:16:32.800><c> have</c>

page right so but use this when you have

page right so but use this when you have
a<01:16:33.040><c> very</c><01:16:33.199><c> convoluted</c><01:16:33.679><c> data</c><01:16:34.880><c> okay</c><01:16:36.000><c> yes</c><01:16:36.320><c> sir</c>

a very convoluted data okay yes sir

a very convoluted data okay yes sir
&gt;&gt; so<01:16:38.560><c> I'm</c><01:16:38.719><c> trying</c><01:16:38.880><c> to</c><01:16:39.040><c> get</c><01:16:39.120><c> a</c><01:16:39.280><c> sense</c><01:16:40.080><c> when</c><01:16:40.320><c> it's</c>

&gt;&gt; so I'm trying to get a sense when it's

&gt;&gt; so I'm trying to get a sense when it's
good<01:16:40.960><c> when</c><01:16:41.120><c> it's</c><01:16:41.280><c> not</c>

im<01:16:45.760><c> into</c><01:16:46.000><c> these</c><01:16:46.159><c> little</c><01:16:46.480><c> squares.</c><01:16:46.880><c> Is</c><01:16:46.960><c> there</c>

im into these little squares. Is there

im into these little squares. Is there
an<01:16:47.280><c> issue</c><01:16:47.600><c> where</c>

an issue where

an issue where
you<01:16:50.000><c> know</c><01:16:50.400><c> let's</c><01:16:50.640><c> say</c><01:16:50.800><c> you're</c><01:16:50.960><c> in</c><01:16:51.040><c> the</c><01:16:51.199><c> middle</c>

you know let's say you're in the middle

you know let's say you're in the middle
of<01:16:51.600><c> paragraph</c>

two<01:16:55.199><c> different</c><01:16:55.840><c> segments</c><01:16:56.560><c> does</c><01:16:56.719><c> that</c><01:16:56.880><c> cause</c>

two different segments does that cause

two different segments does that cause
problems<01:16:57.600><c> in</c><01:16:57.840><c> practice?</c>

problems in practice?

problems in practice?
&gt;&gt; Yeah,<01:16:58.960><c> that's</c><01:16:59.199><c> a</c><01:16:59.440><c> good</c><01:16:59.600><c> question.</c><01:17:00.159><c> But</c><01:17:00.560><c> here</c>

&gt;&gt; Yeah, that's a good question. But here

&gt;&gt; Yeah, that's a good question. But here
the<01:17:01.440><c> model</c><01:17:01.760><c> doesn't</c><01:17:02.320><c> know</c><01:17:03.280><c> that</c><01:17:03.679><c> that</c><01:17:04.000><c> there</c>

the model doesn't know that that there

the model doesn't know that that there
is<01:17:04.320><c> any</c><01:17:04.560><c> chunking</c><01:17:05.040><c> or</c><01:17:05.280><c> anything</c><01:17:05.520><c> that</c><01:17:05.840><c> we</c><01:17:06.159><c> are</c>

is any chunking or anything that we are

is any chunking or anything that we are
understanding<01:17:06.880><c> it</c><01:17:07.199><c> that</c><01:17:07.520><c> way.</c><01:17:07.920><c> But</c><01:17:08.480><c> to</c><01:17:08.719><c> the</c>

understanding it that way. But to the

understanding it that way. But to the
model<01:17:09.440><c> it's</c><01:17:09.760><c> just</c><01:17:10.000><c> an</c><01:17:10.320><c> image</c><01:17:11.040><c> and</c><01:17:11.280><c> the</c><01:17:11.520><c> way</c>

model it's just an image and the way

model it's just an image and the way
that<01:17:11.840><c> it</c><01:17:12.159><c> creates</c><01:17:12.560><c> the</c><01:17:12.800><c> embeddings</c><01:17:13.280><c> for</c><01:17:13.520><c> that</c>

that it creates the embeddings for that

that it creates the embeddings for that
image<01:17:14.080><c> is</c><01:17:14.400><c> by</c><01:17:15.040><c> uh</c><01:17:16.000><c> doing</c><01:17:16.320><c> that</c><01:17:16.640><c> those</c><01:17:16.960><c> patches</c>

image is by uh doing that those patches

image is by uh doing that those patches
and<01:17:18.000><c> why</c><01:17:18.239><c> the</c><01:17:18.480><c> model</c><01:17:18.719><c> knows</c><01:17:18.960><c> this</c><01:17:19.520><c> because</c><01:17:19.840><c> the</c>

and why the model knows this because the

and why the model knows this because the
when<01:17:20.400><c> the</c><01:17:20.640><c> model</c><01:17:20.880><c> was</c><01:17:21.040><c> trained</c><01:17:21.280><c> it's</c><01:17:21.440><c> a</c><01:17:21.600><c> vision</c>

when the model was trained it's a vision

when the model was trained it's a vision
based<01:17:22.080><c> model.</c><01:17:22.560><c> So</c><01:17:22.719><c> when</c><01:17:22.960><c> the</c><01:17:23.120><c> model</c><01:17:23.440><c> was</c>

based model. So when the model was

based model. So when the model was
trained<01:17:24.480><c> it</c><01:17:24.719><c> used</c><01:17:24.880><c> to</c><01:17:25.040><c> chunk</c><01:17:25.440><c> all</c><01:17:25.679><c> the</c>

trained it used to chunk all the

trained it used to chunk all the
training<01:17:26.560><c> data</c><01:17:26.800><c> set</c><01:17:26.960><c> like</c><01:17:27.199><c> that</c><01:17:28.000><c> and</c><01:17:28.239><c> that's</c>

training data set like that and that's

training data set like that and that's
how<01:17:29.360><c> the</c><01:17:29.840><c> you</c><01:17:30.000><c> know</c><01:17:30.080><c> it</c><01:17:30.239><c> has</c><01:17:30.480><c> optimized</c><01:17:31.280><c> for</c>

how the you know it has optimized for

how the you know it has optimized for
that<01:17:31.760><c> data.</c><01:17:32.320><c> For</c><01:17:32.400><c> example</c><01:17:33.520><c> during</c><01:17:33.760><c> the</c>

that data. For example during the

that data. For example during the
training<01:17:34.320><c> time</c><01:17:34.560><c> of</c><01:17:34.719><c> call</c><01:17:35.040><c> pali</c><01:17:35.440><c> not</c><01:17:35.520><c> at</c><01:17:35.679><c> the</c>

training time of call pali not at the

training time of call pali not at the
inference<01:17:36.159><c> time</c><01:17:36.640><c> during</c><01:17:36.960><c> the</c><01:17:37.120><c> training</c><01:17:37.440><c> time</c>

inference time during the training time

inference time during the training time
when<01:17:38.880><c> it</c><01:17:39.120><c> was</c><01:17:39.280><c> given</c><01:17:39.679><c> an</c><01:17:40.000><c> image</c><01:17:40.320><c> of</c><01:17:40.480><c> a</c><01:17:40.719><c> cat</c><01:17:41.679><c> and</c>

when it was given an image of a cat and

when it was given an image of a cat and
the<01:17:42.159><c> text</c><01:17:42.640><c> about</c><01:17:42.880><c> a</c><01:17:43.120><c> cat</c><01:17:43.679><c> the</c><01:17:43.840><c> cat</c><01:17:44.159><c> image</c><01:17:44.400><c> was</c>

the text about a cat the cat image was

the text about a cat the cat image was
also<01:17:44.880><c> chopped</c><01:17:45.280><c> into</c><01:17:45.840><c> those</c><01:17:46.080><c> many</c><01:17:46.400><c> p</c><01:17:46.800><c> uh</c>

also chopped into those many p uh

also chopped into those many p uh
patches.<01:17:48.080><c> Similarly,</c><01:17:48.719><c> when</c><01:17:48.960><c> there</c><01:17:49.120><c> was</c><01:17:49.280><c> an</c>

patches. Similarly, when there was an

patches. Similarly, when there was an
image<01:17:49.920><c> of</c><01:17:50.080><c> a</c><01:17:50.560><c> of</c><01:17:50.880><c> a</c><01:17:51.280><c> PDF</c><01:17:51.760><c> page,</c><01:17:52.480><c> it</c><01:17:52.719><c> was</c><01:17:52.880><c> chopped</c>

image of a of a PDF page, it was chopped

image of a of a PDF page, it was chopped
with<01:17:53.760><c> the</c><01:17:54.000><c> same</c><01:17:54.560><c> uh</c><01:17:54.800><c> patches.</c><01:17:55.600><c> So</c><01:17:56.080><c> that</c><01:17:56.400><c> was</c>

with the same uh patches. So that was

with the same uh patches. So that was
inherited<01:17:57.440><c> during</c><01:17:57.679><c> the</c><01:17:57.840><c> training</c><01:17:58.159><c> process</c>

inherited during the training process

inherited during the training process
itself.<01:17:58.960><c> So</c><01:17:59.120><c> we</c><01:17:59.360><c> don't</c><01:17:59.440><c> have</c><01:17:59.600><c> to</c><01:18:00.000><c> question</c>

itself. So we don't have to question

itself. So we don't have to question
that<01:18:00.800><c> okay</c><01:18:01.520><c> model</c><01:18:01.840><c> how</c><01:18:02.000><c> you</c><01:18:02.159><c> are</c><01:18:02.239><c> doing</c><01:18:02.400><c> this.</c>

that okay model how you are doing this.

that okay model how you are doing this.
You<01:18:03.600><c> the</c><01:18:03.840><c> model</c><01:18:04.080><c> will</c><01:18:04.239><c> say</c><01:18:04.320><c> that</c><01:18:04.640><c> I</c><01:18:04.800><c> have</c><01:18:04.960><c> been</c>

You the model will say that I have been

You the model will say that I have been
doing<01:18:05.360><c> this</c><01:18:06.159><c> don't</c><01:18:06.480><c> give</c><01:18:06.640><c> me</c><01:18:07.199><c> advice.</c><01:18:07.679><c> I</c><01:18:07.840><c> have</c>

doing this don't give me advice. I have

doing this don't give me advice. I have
been<01:18:08.159><c> doing</c><01:18:08.400><c> this</c><01:18:08.719><c> with</c><01:18:09.520><c> you</c><01:18:09.679><c> know</c><01:18:09.760><c> the</c>

been doing this with you know the

been doing this with you know the
plethora<01:18:10.400><c> of</c><01:18:10.560><c> data.</c><01:18:10.880><c> So</c><01:18:11.840><c> if</c><01:18:12.080><c> you</c><01:18:12.320><c> if</c><01:18:12.560><c> you</c><01:18:12.719><c> just</c>

plethora of data. So if you if you just

plethora of data. So if you if you just
look<01:18:13.120><c> at</c><01:18:13.280><c> it</c><01:18:13.760><c> blindly</c><01:18:14.320><c> from</c><01:18:14.560><c> outside,</c><01:18:15.040><c> I</c><01:18:15.280><c> also</c>

look at it blindly from outside, I also

look at it blindly from outside, I also
had<01:18:15.600><c> the</c><01:18:15.760><c> same</c><01:18:15.920><c> thought</c><01:18:17.120><c> how</c><01:18:17.440><c> the</c><01:18:17.760><c> model</c><01:18:18.000><c> is</c>

had the same thought how the model is

had the same thought how the model is
going<01:18:18.400><c> to</c><01:18:18.560><c> create</c><01:18:18.719><c> an</c><01:18:18.960><c> embedding</c><01:18:19.760><c> when</c><01:18:20.000><c> it</c>

going to create an embedding when it

going to create an embedding when it
splits<01:18:20.880><c> a</c><01:18:21.199><c> table</c><01:18:21.600><c> into</c><01:18:22.480><c> multiple</c><01:18:22.960><c> chunks.</c>

splits a table into multiple chunks.

splits a table into multiple chunks.
What<01:18:24.320><c> is</c><01:18:24.480><c> the</c><01:18:24.640><c> relationship</c><01:18:25.040><c> between</c><01:18:25.360><c> one</c>

What is the relationship between one

What is the relationship between one
chunk<01:18:25.760><c> and</c><01:18:25.920><c> the</c><01:18:26.080><c> other</c><01:18:26.239><c> chunk?</c><01:18:26.560><c> How</c><01:18:26.640><c> the</c><01:18:26.800><c> model</c>

chunk and the other chunk? How the model

chunk and the other chunk? How the model
is<01:18:27.920><c> you</c><01:18:28.080><c> know</c><01:18:28.480><c> doing</c><01:18:28.719><c> that?</c><01:18:29.679><c> Later</c><01:18:29.920><c> on</c><01:18:30.080><c> we</c>

is you know doing that? Later on we

is you know doing that? Later on we
realized<01:18:30.560><c> that</c><01:18:30.719><c> this</c><01:18:30.960><c> has</c><01:18:31.120><c> been</c><01:18:31.440><c> incorporated</c>

realized that this has been incorporated

realized that this has been incorporated
during<01:18:32.320><c> the</c><01:18:32.480><c> training</c><01:18:32.719><c> process</c><01:18:33.040><c> itself.</c>

during the training process itself.

during the training process itself.
Initially<01:18:34.159><c> it</c><01:18:34.400><c> was</c><01:18:34.560><c> not</c><01:18:34.640><c> able</c><01:18:34.880><c> to</c><01:18:35.040><c> do</c><01:18:35.120><c> that</c>

Initially it was not able to do that

Initially it was not able to do that
right<01:18:35.760><c> but</c><01:18:36.480><c> when</c><01:18:37.040><c> during</c><01:18:37.280><c> the</c><01:18:37.440><c> training</c>

right but when during the training

right but when during the training
process<01:18:38.480><c> the</c><01:18:38.719><c> loss</c><01:18:39.040><c> must</c><01:18:39.199><c> have</c><01:18:39.360><c> been</c><01:18:39.520><c> very</c>

process the loss must have been very

process the loss must have been very
high.

high.

high.
Right?<01:18:41.120><c> So,</c><01:18:41.360><c> and</c><01:18:41.840><c> that's</c><01:18:42.159><c> how</c><01:18:42.320><c> it</c><01:18:42.560><c> has</c><01:18:42.719><c> been</c>

Right? So, and that's how it has been

Right? So, and that's how it has been
optimized.<01:18:43.360><c> So,</c><01:18:43.600><c> one</c><01:18:43.760><c> that</c><01:18:43.920><c> is</c><01:18:44.080><c> optimized,</c>

optimized. So, one that is optimized,

optimized. So, one that is optimized,
you<01:18:45.040><c> don't</c><01:18:45.120><c> have</c><01:18:45.280><c> to</c><01:18:45.360><c> worry</c><01:18:45.600><c> about</c><01:18:45.760><c> that.</c><01:18:46.080><c> And</c>

you don't have to worry about that. And

you don't have to worry about that. And
this<01:18:46.400><c> is</c><01:18:46.560><c> basically</c><01:18:47.040><c> if</c><01:18:47.280><c> you</c><01:18:47.360><c> think</c><01:18:47.520><c> about</c>

this is basically if you think about

this is basically if you think about
this<01:18:47.920><c> this</c><01:18:48.159><c> patching</c><01:18:48.560><c> and</c><01:18:48.800><c> embedding,</c><01:18:49.679><c> it's</c>

this this patching and embedding, it's

this this patching and embedding, it's
it's<01:18:51.280><c> not</c><01:18:51.440><c> a</c><01:18:51.760><c> new</c><01:18:52.000><c> technique.</c>

it's not a new technique.

it's not a new technique.
Uh<01:18:53.840><c> you</c><01:18:54.000><c> know,</c><01:18:54.080><c> it</c><01:18:54.320><c> was</c><01:18:54.400><c> there</c><01:18:54.560><c> in</c><01:18:54.800><c> lot</c><01:18:54.960><c> of</c>

Uh you know, it was there in lot of

Uh you know, it was there in lot of
vision<01:18:55.600><c> based</c><01:18:55.920><c> model.</c><01:18:56.560><c> Now,</c><01:18:56.800><c> we</c><01:18:56.960><c> are</c><01:18:57.120><c> using</c><01:18:57.280><c> it</c>

vision based model. Now, we are using it

vision based model. Now, we are using it
for<01:18:57.679><c> retrieval.</c>

for retrieval.

for retrieval.
So,<01:18:59.440><c> that's</c><01:18:59.760><c> that's</c><01:19:00.000><c> how</c><01:19:00.159><c> it</c><01:19:00.400><c> works.</c>

So, that's that's how it works.

So, that's that's how it works.
In<01:19:02.400><c> fact,</c><01:19:02.719><c> if</c><01:19:02.960><c> you</c><01:19:03.120><c> are</c><01:19:04.159><c> curious,</c><01:19:04.800><c> I</c><01:19:05.040><c> would</c>

In fact, if you are curious, I would

In fact, if you are curious, I would
recommend<01:19:06.000><c> I</c><01:19:06.400><c> I'll</c><01:19:06.640><c> try</c><01:19:06.800><c> to</c><01:19:06.880><c> do</c><01:19:07.040><c> this</c><01:19:07.199><c> later</c>

recommend I I'll try to do this later

recommend I I'll try to do this later
on,<01:19:07.600><c> but</c><01:19:08.000><c> I</c><01:19:08.239><c> would</c><01:19:08.480><c> recommend</c><01:19:08.800><c> that</c><01:19:09.280><c> uh</c><01:19:10.159><c> try</c><01:19:10.480><c> to</c>

on, but I would recommend that uh try to

on, but I would recommend that uh try to
fine-tune<01:19:11.199><c> this</c><01:19:11.440><c> model</c><01:19:11.760><c> or</c><01:19:12.159><c> train</c><01:19:12.480><c> it</c><01:19:12.800><c> from</c>

fine-tune this model or train it from

fine-tune this model or train it from
scratch<01:19:13.360><c> if</c><01:19:13.600><c> you</c><01:19:13.760><c> have</c><01:19:13.840><c> some</c><01:19:14.000><c> resource</c><01:19:14.719><c> in</c><01:19:15.120><c> for</c>

scratch if you have some resource in for

scratch if you have some resource in for
a<01:19:15.440><c> smaller</c><01:19:15.679><c> data</c><01:19:15.920><c> set.</c><01:19:16.880><c> Um</c><01:19:18.239><c> and</c><01:19:18.560><c> use</c><01:19:18.719><c> a</c>

a smaller data set. Um and use a

a smaller data set. Um and use a
different<01:19:19.199><c> patch</c><01:19:19.520><c> size</c><01:19:20.719><c> uh</c><01:19:21.199><c> uh</c><01:19:21.280><c> so</c><01:19:21.440><c> let's</c><01:19:21.679><c> say</c>

different patch size uh uh so let's say

different patch size uh uh so let's say
start<01:19:22.159><c> with</c><01:19:22.320><c> a</c><01:19:22.480><c> patch</c><01:19:22.640><c> size</c><01:19:22.880><c> of</c><01:19:23.040><c> four,</c><01:19:24.080><c> right?</c>

start with a patch size of four, right?

start with a patch size of four, right?
And<01:19:24.960><c> uh</c><01:19:25.440><c> you</c><01:19:25.600><c> know</c><01:19:25.760><c> try</c><01:19:25.920><c> to</c><01:19:26.080><c> see</c><01:19:26.239><c> that</c><01:19:26.480><c> how</c><01:19:26.640><c> it</c>

And uh you know try to see that how it

And uh you know try to see that how it
works.

works.

works.
uh<01:19:28.800><c> I</c><01:19:29.040><c> have</c><01:19:29.199><c> lot</c><01:19:29.440><c> of</c><01:19:29.600><c> assumptions</c><01:19:30.320><c> uh</c><01:19:30.560><c> on</c><01:19:30.800><c> that</c>

uh I have lot of assumptions uh on that

uh I have lot of assumptions uh on that
but<01:19:31.840><c> this</c><01:19:32.080><c> will</c><01:19:32.320><c> give</c><01:19:32.480><c> you</c><01:19:32.640><c> a</c><01:19:32.880><c> lot</c><01:19:32.960><c> of</c><01:19:33.120><c> clarity</c>

but this will give you a lot of clarity

but this will give you a lot of clarity
of<01:19:33.920><c> how</c><01:19:34.719><c> uh</c><01:19:34.800><c> the</c><01:19:35.040><c> semantic</c><01:19:35.440><c> search</c><01:19:35.840><c> things</c>

of how uh the semantic search things

of how uh the semantic search things
work<01:19:36.400><c> and</c><01:19:36.640><c> why</c><01:19:36.800><c> that</c><01:19:37.120><c> matrix</c><01:19:37.600><c> max</c><01:19:38.159><c> matrix</c>

work and why that matrix max matrix

work and why that matrix max matrix
multiplication<01:19:39.120><c> that</c><01:19:39.280><c> we</c><01:19:39.440><c> have</c><01:19:39.520><c> done</c><01:19:39.760><c> right</c>

multiplication that we have done right

multiplication that we have done right
why<01:19:40.640><c> that</c><01:19:40.880><c> is</c><01:19:40.960><c> a</c><01:19:41.120><c> good</c><01:19:41.280><c> technique</c>

why that is a good technique

why that is a good technique
uh<01:19:43.280><c> uh</c><01:19:43.440><c> because</c><01:19:44.880><c> imagine</c>

uh uh because imagine

uh uh because imagine
you<01:19:46.719><c> have</c><01:19:47.120><c> uploaded</c><01:19:47.760><c> your</c><01:19:48.000><c> data</c><01:19:48.239><c> set</c><01:19:48.480><c> is</c><01:19:48.800><c> the</c>

you have uploaded your data set is the

you have uploaded your data set is the
attention<01:19:49.440><c> you</c><01:19:49.679><c> all</c><01:19:49.840><c> you</c><01:19:50.000><c> need</c><01:19:50.320><c> paper</c><01:19:51.280><c> and</c><01:19:51.520><c> you</c>

attention you all you need paper and you

attention you all you need paper and you
ask<01:19:52.000><c> a</c><01:19:52.239><c> question</c><01:19:52.640><c> about</c><01:19:53.920><c> what</c><01:19:54.159><c> is</c><01:19:54.560><c> positional</c>

ask a question about what is positional

ask a question about what is positional
embedding<01:19:56.320><c> now</c><01:19:56.560><c> this</c><01:19:56.880><c> positional</c><01:19:57.360><c> embedding</c>

embedding now this positional embedding

embedding now this positional embedding
This<01:19:58.400><c> text</c><01:19:58.880><c> is</c><01:19:59.120><c> there</c><01:19:59.360><c> in</c><01:19:59.679><c> lot</c><01:19:59.920><c> of</c><01:20:00.080><c> pages</c>

This text is there in lot of pages

This text is there in lot of pages
almost<01:20:00.719><c> all</c><01:20:00.880><c> the</c><01:20:01.040><c> pages.</c><01:20:02.000><c> It</c><01:20:02.159><c> should</c><01:20:02.320><c> not</c><01:20:02.480><c> give</c>

almost all the pages. It should not give

almost all the pages. It should not give
me<01:20:02.800><c> all</c><01:20:02.880><c> the</c><01:20:03.040><c> pages.</c><01:20:03.520><c> Right?</c><01:20:04.480><c> So</c><01:20:04.640><c> it</c><01:20:04.880><c> should</c>

me all the pages. Right? So it should

me all the pages. Right? So it should
give<01:20:05.120><c> me</c><01:20:05.280><c> the</c><01:20:05.440><c> page</c><01:20:05.679><c> where</c><01:20:06.320><c> there</c><01:20:06.480><c> is</c><01:20:06.640><c> an</c>

give me the page where there is an

give me the page where there is an
actual<01:20:07.280><c> information</c><01:20:07.600><c> of</c><01:20:07.920><c> positional</c>

actual information of positional

actual information of positional
embedding<01:20:08.719><c> is</c><01:20:08.880><c> there.</c><01:20:09.679><c> Right?</c><01:20:10.320><c> And</c><01:20:10.560><c> when</c><01:20:10.800><c> you</c>

embedding is there. Right? And when you

embedding is there. Right? And when you
when<01:20:11.600><c> you</c><01:20:11.760><c> think</c><01:20:12.000><c> through</c><01:20:12.239><c> that</c><01:20:12.719><c> you</c><01:20:12.880><c> will</c>

when you think through that you will

when you think through that you will
find<01:20:13.199><c> out</c><01:20:13.360><c> that</c><01:20:13.600><c> the</c><01:20:13.840><c> ma</c><01:20:14.159><c> max</c><01:20:14.719><c> multiplication</c>

find out that the ma max multiplication

find out that the ma max multiplication
that<01:20:15.760><c> that</c><01:20:16.080><c> we</c><01:20:16.320><c> have</c><01:20:16.480><c> done</c><01:20:16.719><c> right</c><01:20:17.360><c> that</c>

that that we have done right that

that that we have done right that
actually<01:20:17.920><c> takes</c><01:20:18.239><c> care</c><01:20:18.400><c> of</c><01:20:18.480><c> that</c><01:20:18.800><c> that</c><01:20:19.280><c> uh</c><01:20:19.360><c> it</c>

actually takes care of that that uh it

actually takes care of that that uh it
will<01:20:19.760><c> just</c><01:20:19.920><c> show</c><01:20:20.000><c> you</c><01:20:20.159><c> the</c><01:20:20.400><c> page</c><01:20:21.280><c> where</c><01:20:21.840><c> all</c>

will just show you the page where all

will just show you the page where all
the<01:20:22.320><c> tokens</c><01:20:22.960><c> of</c><01:20:23.280><c> your</c><01:20:23.520><c> query</c><01:20:24.320><c> has</c><01:20:24.640><c> the</c><01:20:24.880><c> maximum</c>

the tokens of your query has the maximum

the tokens of your query has the maximum
similarity<01:20:26.400><c> with</c><01:20:26.719><c> a</c><01:20:26.960><c> particular</c><01:20:27.360><c> page</c><01:20:28.080><c> not</c>

similarity with a particular page not

similarity with a particular page not
just<01:20:28.880><c> one</c><01:20:29.199><c> chunk</c><01:20:29.520><c> of</c><01:20:29.760><c> your</c><01:20:30.000><c> question</c><01:20:31.040><c> with</c>

just one chunk of your question with

just one chunk of your question with
just<01:20:31.760><c> one</c><01:20:32.080><c> patch</c><01:20:32.480><c> of</c><01:20:32.640><c> your</c><01:20:32.880><c> page</c><01:20:34.080><c> you</c><01:20:34.239><c> getting</c>

just one patch of your page you getting

just one patch of your page you getting
what<01:20:34.640><c> I'm</c><01:20:34.800><c> saying</c><01:20:34.960><c> otherwise</c><01:20:35.600><c> you</c><01:20:35.760><c> know</c><01:20:36.000><c> when</c>

what I'm saying otherwise you know when

what I'm saying otherwise you know when
you<01:20:36.400><c> say</c><01:20:36.560><c> top</c><01:20:36.800><c> five</c><01:20:37.120><c> it</c><01:20:37.360><c> will</c><01:20:37.520><c> give</c><01:20:37.679><c> you</c><01:20:38.000><c> any</c>

you say top five it will give you any

you say top five it will give you any
five<01:20:38.960><c> random</c><01:20:39.280><c> pages</c><01:20:39.520><c> where</c><01:20:39.840><c> this</c><01:20:40.000><c> positional</c>

five random pages where this positional

five random pages where this positional
embedding<01:20:40.719><c> is</c><01:20:40.880><c> written.</c><01:20:41.760><c> So</c><01:20:42.080><c> just</c><01:20:42.480><c> give</c><01:20:42.640><c> it</c><01:20:42.800><c> a</c>

embedding is written. So just give it a

embedding is written. So just give it a
shot.

shot.

shot.
&gt;&gt; Yes<01:20:45.120><c> sir.</c><01:20:45.440><c> Yeah.</c>

&gt;&gt; Yes sir. Yeah.

&gt;&gt; Yes sir. Yeah.
&gt;&gt; Is<01:20:46.880><c> there</c><01:20:47.040><c> any</c><01:20:47.280><c> sort</c><01:20:47.440><c> of</c><01:20:47.600><c> hybrid</c><01:20:48.000><c> approach</c>

&gt;&gt; Is there any sort of hybrid approach

&gt;&gt; Is there any sort of hybrid approach
where<01:20:48.640><c> you</c><01:20:48.880><c> can</c><01:20:49.679><c> process</c>

image?

image?

image?
This<01:20:55.600><c> is</c><01:20:55.760><c> something</c><01:20:56.080><c> that</c><01:20:56.560><c> uh</c><01:20:56.719><c> one</c><01:20:56.960><c> of</c><01:20:57.040><c> my</c>

This is something that uh one of my

This is something that uh one of my
teammate<01:20:58.000><c> started</c><01:20:58.400><c> to</c><01:20:59.040><c> work</c><01:20:59.280><c> on</c><01:21:00.000><c> uh</c><01:21:00.159><c> where</c><01:21:00.719><c> we</c>

teammate started to work on uh where we

teammate started to work on uh where we
are<01:21:01.120><c> trying</c><01:21:01.280><c> to</c><01:21:01.440><c> use</c><01:21:02.000><c> u</c><01:21:02.560><c> call</c><01:21:03.120><c> along</c><01:21:03.360><c> with</c><01:21:03.440><c> a</c>

are trying to use u call along with a

are trying to use u call along with a
traditional<01:21:04.080><c> technique</c><01:21:04.960><c> and</c><01:21:05.280><c> the</c><01:21:05.520><c> way</c><01:21:05.679><c> that</c>

traditional technique and the way that

traditional technique and the way that
we<01:21:06.080><c> are</c><01:21:06.320><c> trying</c><01:21:06.480><c> to</c><01:21:06.560><c> do</c><01:21:06.719><c> this</c><01:21:06.960><c> is</c><01:21:07.199><c> based</c><01:21:07.440><c> on</c><01:21:08.080><c> the</c>

we are trying to do this is based on the

we are trying to do this is based on the
question<01:21:08.719><c> that</c><01:21:08.960><c> we</c><01:21:09.120><c> are</c><01:21:09.280><c> getting</c><01:21:10.000><c> and</c><01:21:10.239><c> while</c>

question that we are getting and while

question that we are getting and while
we<01:21:10.719><c> are</c><01:21:11.280><c> doing</c><01:21:11.520><c> the</c><01:21:11.679><c> pre-processing</c><01:21:12.400><c> and</c><01:21:12.640><c> uh</c>

we are doing the pre-processing and uh

we are doing the pre-processing and uh
storing<01:21:13.280><c> the</c><01:21:13.520><c> embeddings</c><01:21:14.320><c> we</c><01:21:14.560><c> are</c><01:21:14.719><c> trying</c><01:21:14.960><c> to</c>

storing the embeddings we are trying to

storing the embeddings we are trying to
store<01:21:16.000><c> uh</c><01:21:16.960><c> in</c><01:21:17.120><c> a</c><01:21:17.360><c> different</c><01:21:17.600><c> way</c><01:21:17.840><c> like</c><01:21:18.159><c> not</c><01:21:18.400><c> for</c>

store uh in a different way like not for

store uh in a different way like not for
all<01:21:18.800><c> the</c><01:21:18.960><c> data</c><01:21:19.280><c> that</c><01:21:19.520><c> we</c><01:21:19.679><c> are</c><01:21:19.760><c> using</c><01:21:20.000><c> call</c><01:21:20.239><c> pal</c>

all the data that we are using call pal

all the data that we are using call pal
just<01:21:20.880><c> for</c><01:21:21.040><c> few</c><01:21:21.280><c> data</c><01:21:21.440><c> we</c><01:21:21.679><c> are</c><01:21:21.760><c> using</c><01:21:21.920><c> call</c><01:21:22.159><c> pal</c>

just for few data we are using call pal

just for few data we are using call pal
for<01:21:22.560><c> the</c><01:21:22.640><c> rest</c><01:21:22.719><c> of</c><01:21:22.800><c> the</c><01:21:22.960><c> data</c><01:21:23.120><c> we</c><01:21:23.360><c> are</c><01:21:23.440><c> just</c>

for the rest of the data we are just

for the rest of the data we are just
using<01:21:23.760><c> the</c><01:21:24.000><c> traditional</c><01:21:24.400><c> technique</c>

using the traditional technique

using the traditional technique
But<01:21:25.360><c> for</c><01:21:25.600><c> a</c><01:21:25.760><c> particular</c><01:21:26.080><c> data</c><01:21:26.320><c> set</c><01:21:26.480><c> we</c><01:21:26.719><c> just</c>

But for a particular data set we just

But for a particular data set we just
use<01:21:27.040><c> one</c><01:21:27.280><c> single</c><01:21:27.520><c> model.</c><01:21:27.920><c> We</c><01:21:28.159><c> cannot</c><01:21:28.400><c> just</c><01:21:28.640><c> go</c>

use one single model. We cannot just go

use one single model. We cannot just go
into<01:21:29.040><c> that</c><01:21:29.280><c> okay</c><01:21:29.760><c> first</c><01:21:30.000><c> five</c><01:21:30.239><c> pages</c><01:21:30.560><c> of</c><01:21:30.800><c> this</c>

into that okay first five pages of this

into that okay first five pages of this
document<01:21:31.280><c> we</c><01:21:31.440><c> will</c><01:21:31.600><c> use</c><01:21:31.760><c> call</c><01:21:32.000><c> pal</c><01:21:32.400><c> the</c><01:21:32.640><c> next</c>

document we will use call pal the next

document we will use call pal the next
five<01:21:33.040><c> pages</c><01:21:33.360><c> we</c><01:21:33.520><c> will</c><01:21:33.679><c> use</c><01:21:33.760><c> the</c><01:21:34.000><c> traditional</c>

five pages we will use the traditional

five pages we will use the traditional
technique<01:21:35.040><c> that's</c><01:21:35.360><c> not</c><01:21:35.520><c> how</c><01:21:36.640><c> you</c><01:21:36.800><c> know</c><01:21:37.600><c> uh</c><01:21:38.320><c> we</c>

technique that's not how you know uh we

technique that's not how you know uh we
are<01:21:38.960><c> exploring</c><01:21:40.000><c> but</c><01:21:40.400><c> we</c><01:21:40.640><c> are</c><01:21:40.800><c> kind</c><01:21:40.960><c> of</c><01:21:41.600><c> trying</c>

are exploring but we are kind of trying

are exploring but we are kind of trying
to<01:21:42.320><c> use</c><01:21:42.960><c> two</c><01:21:43.199><c> different</c><01:21:43.520><c> approach</c><01:21:43.920><c> in</c><01:21:44.080><c> the</c>

to use two different approach in the

to use two different approach in the
same<01:21:44.800><c> uh</c><01:21:45.120><c> uh</c><01:21:45.360><c> architecture.</c><01:21:46.239><c> But</c><01:21:46.400><c> this</c><01:21:46.560><c> is</c><01:21:46.719><c> we</c>

same uh uh architecture. But this is we

same uh uh architecture. But this is we
are<01:21:47.040><c> using</c><01:21:47.280><c> because</c><01:21:47.520><c> the</c><01:21:47.679><c> data</c><01:21:47.920><c> set</c><01:21:48.080><c> that</c><01:21:48.239><c> we</c>

are using because the data set that we

are using because the data set that we
got<01:21:48.560><c> from</c><01:21:48.719><c> the</c><01:21:48.960><c> customer</c><01:21:49.679><c> they</c><01:21:50.000><c> started</c><01:21:50.239><c> off</c>

got from the customer they started off

got from the customer they started off
with<01:21:50.560><c> a</c><01:21:50.880><c> requirement</c><01:21:51.440><c> certain</c><01:21:51.760><c> requirement</c>

with a requirement certain requirement

with a requirement certain requirement
then<01:21:52.400><c> it</c><01:21:52.719><c> changed.</c><01:21:53.199><c> It</c><01:21:53.360><c> changed</c><01:21:53.600><c> means</c><01:21:53.840><c> it</c>

then it changed. It changed means it

then it changed. It changed means it
appended<01:21:54.719><c> and</c><01:21:54.960><c> now</c><01:21:55.440><c> when</c><01:21:55.760><c> the</c><01:21:55.920><c> new</c><01:21:56.080><c> request</c>

appended and now when the new request

appended and now when the new request
came<01:21:56.639><c> the</c><01:21:56.800><c> data</c><01:21:56.960><c> set</c><01:21:57.120><c> is</c><01:21:57.280><c> completely</c>

came the data set is completely

came the data set is completely
different<01:21:58.159><c> but</c><01:21:58.400><c> they</c><01:21:58.560><c> want</c><01:21:58.639><c> a</c><01:21:58.880><c> one</c><01:21:59.120><c> unified</c>

different but they want a one unified

different but they want a one unified
system.<01:22:00.080><c> So</c><01:22:00.239><c> that's</c><01:22:00.400><c> why</c><01:22:00.560><c> we</c><01:22:00.719><c> are</c><01:22:00.880><c> just</c>

system. So that's why we are just

system. So that's why we are just
checking<01:22:01.199><c> the</c><01:22:01.440><c> question</c><01:22:01.600><c> is</c><01:22:01.840><c> coming</c><01:22:02.000><c> from</c>

checking the question is coming from

checking the question is coming from
where<01:22:02.560><c> and</c><01:22:02.800><c> we</c><01:22:02.960><c> are</c><01:22:03.120><c> storing</c><01:22:03.360><c> some</c><01:22:03.520><c> metadata</c>

where and we are storing some metadata

where and we are storing some metadata
to<01:22:04.400><c> identify</c><01:22:04.719><c> this</c><01:22:04.960><c> question</c><01:22:05.280><c> should</c><01:22:05.600><c> go</c><01:22:05.760><c> from</c>

to identify this question should go from

to identify this question should go from
this<01:22:06.719><c> space</c><01:22:06.960><c> or</c><01:22:07.120><c> that</c><01:22:07.360><c> space.</c><01:22:08.080><c> Uh</c><01:22:08.400><c> but</c><01:22:08.880><c> nothing</c>

this space or that space. Uh but nothing

this space or that space. Uh but nothing
beyond<01:22:09.520><c> that</c><01:22:09.760><c> that</c><01:22:10.000><c> I</c><01:22:10.159><c> have</c><01:22:10.239><c> seen.</c><01:22:10.639><c> I've</c><01:22:10.880><c> seen</c>

beyond that that I have seen. I've seen

beyond that that I have seen. I've seen
either<01:22:11.440><c> this</c><01:22:11.679><c> or</c><01:22:11.920><c> that.</c>

either this or that.

either this or that.
&gt;&gt; Yeah.<01:22:13.920><c> Yes</c><01:22:14.159><c> sir.</c>

&gt;&gt; Yeah. Yes sir.

&gt;&gt; Yeah. Yes sir.
&gt;&gt; Did<01:22:14.639><c> you</c><01:22:14.800><c> have</c><01:22:14.960><c> to</c><01:22:15.440><c> find</c>

&gt;&gt; Did you have to find

&gt;&gt; Did you have to find
poly<01:22:17.440><c> model</c><01:22:17.760><c> to</c><01:22:18.080><c> for</c><01:22:18.320><c> it</c><01:22:18.400><c> to</c><01:22:18.560><c> work</c><01:22:18.800><c> well?</c>

poly model to for it to work well?

poly model to for it to work well?
&gt;&gt; No<01:22:20.000><c> I</c><01:22:20.159><c> have</c><01:22:20.320><c> not</c><01:22:20.480><c> done</c><01:22:20.560><c> that.</c><01:22:20.800><c> So</c><01:22:21.040><c> this</c><01:22:21.199><c> is</c>

&gt;&gt; No I have not done that. So this is

&gt;&gt; No I have not done that. So this is
these<01:22:21.840><c> are</c><01:22:22.000><c> all</c><01:22:22.719><c> fine-tuned</c><01:22:23.280><c> models.</c><01:22:23.600><c> You</c><01:22:23.760><c> can</c>

these are all fine-tuned models. You can

these are all fine-tuned models. You can
just<01:22:24.320><c> make</c><01:22:24.560><c> use</c><01:22:24.719><c> of</c><01:22:24.880><c> this.</c><01:22:25.280><c> I</c><01:22:25.520><c> forgot</c><01:22:25.760><c> the</c><01:22:25.920><c> data</c>

just make use of this. I forgot the data

just make use of this. I forgot the data
set<01:22:26.320><c> that</c><01:22:26.480><c> they</c><01:22:26.639><c> have</c><01:22:26.800><c> used.</c><01:22:27.440><c> You</c><01:22:27.600><c> can</c><01:22:27.760><c> read</c>

set that they have used. You can read

set that they have used. You can read
the<01:22:28.080><c> research</c><01:22:28.400><c> paper</c><01:22:28.800><c> on</c><01:22:29.040><c> that.</c><01:22:29.520><c> The</c><01:22:29.760><c> link</c><01:22:30.000><c> is</c>

the research paper on that. The link is

the research paper on that. The link is
there.<01:22:30.400><c> But</c><01:22:30.560><c> you</c><01:22:30.800><c> don't</c><01:22:30.880><c> have</c><01:22:31.040><c> to</c><01:22:31.120><c> fine-tune</c>

there. But you don't have to fine-tune

there. But you don't have to fine-tune
that.<01:22:32.000><c> Can</c><01:22:32.159><c> you</c><01:22:32.320><c> do</c><01:22:32.400><c> that?</c><01:22:32.639><c> Yes,</c><01:22:32.880><c> of</c><01:22:33.040><c> course</c>

that. Can you do that? Yes, of course

that. Can you do that? Yes, of course
you<01:22:33.280><c> can</c><01:22:33.360><c> do</c><01:22:33.520><c> a</c><01:22:33.679><c> finetuning.</c><01:22:34.239><c> That's</c><01:22:34.400><c> what</c><01:22:34.560><c> I</c>

you can do a finetuning. That's what I

you can do a finetuning. That's what I
was<01:22:34.800><c> referring</c><01:22:35.120><c> to</c><01:22:35.360><c> him.</c><01:22:35.840><c> I</c><01:22:36.159><c> myself</c><01:22:36.560><c> have</c><01:22:36.800><c> not</c>

was referring to him. I myself have not

was referring to him. I myself have not
done<01:22:37.120><c> that.</c><01:22:37.679><c> But</c><01:22:37.840><c> I</c><01:22:38.000><c> will</c><01:22:38.159><c> certainly</c><01:22:38.480><c> try</c><01:22:38.719><c> this</c>

done that. But I will certainly try this

done that. But I will certainly try this
out<01:22:39.440><c> uh</c><01:22:39.840><c> to</c><01:22:40.080><c> fine-tune</c><01:22:40.560><c> that.</c><01:22:40.880><c> That's</c><01:22:41.040><c> a</c><01:22:41.199><c> good</c>

out uh to fine-tune that. That's a good

out uh to fine-tune that. That's a good
exercise.

exercise.

exercise.
&gt;&gt; So<01:22:42.320><c> it</c><01:22:42.560><c> worked</c><01:22:42.800><c> well</c><01:22:43.040><c> for</c><01:22:43.199><c> your</c><01:22:43.440><c> use</c><01:22:43.600><c> case.</c>

&gt;&gt; So it worked well for your use case.

&gt;&gt; So it worked well for your use case.
&gt;&gt; Yeah.<01:22:44.159><c> It</c><01:22:44.320><c> just</c><01:22:44.480><c> worked</c><01:22:44.719><c> fine.</c><01:22:45.040><c> Yeah.</c><01:22:45.360><c> Yeah.</c>

&gt;&gt; Yeah. It just worked fine. Yeah. Yeah.

&gt;&gt; Yeah. It just worked fine. Yeah. Yeah.
Yeah.<01:22:45.840><c> Yeah.</c><01:22:46.560><c> because</c><01:22:46.800><c> I</c><01:22:47.040><c> used</c><01:22:47.280><c> a</c><01:22:48.239><c> standard</c>

Yeah. Yeah. because I used a standard

Yeah. Yeah. because I used a standard
textbook<01:22:49.600><c> which</c><01:22:49.840><c> are</c><01:22:50.080><c> publicly</c><01:22:50.480><c> available</c><01:22:51.360><c> uh</c>

textbook which are publicly available uh

textbook which are publicly available uh
but<01:22:51.840><c> convoluted</c><01:22:52.480><c> data</c><01:22:52.960><c> try</c><01:22:53.199><c> to</c><01:22:53.360><c> do</c><01:22:53.440><c> that</c><01:22:53.600><c> with</c>

but convoluted data try to do that with

but convoluted data try to do that with
IKEA<01:22:55.280><c> data</c><01:22:55.440><c> set</c><01:22:55.600><c> IKEA</c><01:22:56.000><c> data</c><01:22:56.159><c> set</c><01:22:56.320><c> is</c><01:22:56.560><c> good</c>

IKEA data set IKEA data set is good

IKEA data set IKEA data set is good
because<01:22:57.520><c> you</c><01:22:57.760><c> cannot</c><01:22:58.080><c> use</c><01:22:58.239><c> an</c><01:22:58.480><c> OCR</c><01:22:58.960><c> based</c>

because you cannot use an OCR based

because you cannot use an OCR based
techniques<01:22:59.520><c> in</c><01:22:59.679><c> that</c><01:23:00.159><c> data</c><01:23:00.480><c> set</c><01:23:00.800><c> and</c><01:23:00.960><c> because</c>

techniques in that data set and because

techniques in that data set and because
that's<01:23:01.440><c> a</c><01:23:01.679><c> very</c><01:23:01.840><c> strange</c><01:23:02.320><c> sparse</c><01:23:02.880><c> data</c><01:23:03.199><c> set</c>

that's a very strange sparse data set

that's a very strange sparse data set
and<01:23:04.000><c> that</c><01:23:04.159><c> will</c><01:23:04.320><c> give</c><01:23:04.480><c> you</c><01:23:04.560><c> a</c><01:23:04.719><c> good</c><01:23:04.880><c> intuition</c>

and that will give you a good intuition

and that will give you a good intuition
that<01:23:05.440><c> okay</c><01:23:05.760><c> this</c><01:23:05.920><c> is</c><01:23:06.400><c> you</c><01:23:06.560><c> know</c><01:23:06.719><c> you</c><01:23:06.880><c> can</c>

that okay this is you know you can

that okay this is you know you can
understand<01:23:07.679><c> only</c><01:23:08.000><c> you</c><01:23:08.320><c> can</c><01:23:08.639><c> answer</c><01:23:08.960><c> those</c>

understand only you can answer those

understand only you can answer those
questions<01:23:09.600><c> if</c><01:23:09.840><c> you</c><01:23:10.080><c> if</c><01:23:10.400><c> somebody</c><01:23:10.719><c> asks</c><01:23:10.880><c> you</c>

questions if you if somebody asks you

questions if you if somebody asks you
that<01:23:11.360><c> question</c><01:23:11.840><c> from</c><01:23:12.159><c> that</c><01:23:12.639><c> uh</c><01:23:12.880><c> IKEA</c><01:23:13.679><c> uh</c>

that question from that uh IKEA uh

that question from that uh IKEA uh
manual<01:23:14.639><c> you</c><01:23:14.880><c> can</c><01:23:14.960><c> do</c><01:23:15.120><c> that</c><01:23:15.360><c> not</c><01:23:15.920><c> um</c><01:23:16.239><c> a</c><01:23:16.639><c> computer</c>

manual you can do that not um a computer

manual you can do that not um a computer
if<01:23:17.440><c> you</c><01:23:17.679><c> use</c><01:23:17.840><c> a</c><01:23:18.080><c> traditional</c><01:23:18.480><c> technique.</c><01:23:18.880><c> So</c>

if you use a traditional technique. So

if you use a traditional technique. So
that<01:23:19.600><c> actually</c><01:23:19.920><c> a</c><01:23:20.239><c> good</c><01:23:20.719><c> data</c><01:23:21.120><c> point</c><01:23:21.280><c> to</c><01:23:21.520><c> make</c>

that actually a good data point to make

that actually a good data point to make
use<01:23:21.840><c> of</c><01:23:22.080><c> this.</c><01:23:23.360><c> Okay.</c>

use of this. Okay.

use of this. Okay.
All<01:23:24.960><c> right.</c><01:23:25.679><c> Thank</c><01:23:25.840><c> you</c><01:23:26.000><c> so</c><01:23:26.159><c> much</c><01:23:26.320><c> everyone</c>

All right. Thank you so much everyone

All right. Thank you so much everyone
for<01:23:27.280><c> uh</c><01:23:27.600><c> uh</c><01:23:27.840><c> coming.</c><01:23:28.239><c> I</c><01:23:28.400><c> really</c><01:23:28.639><c> appreciate</c>

and<01:23:35.440><c> and</c><01:23:35.679><c> one</c><01:23:35.920><c> last</c><01:23:36.159><c> thing</c><01:23:36.239><c> is</c><01:23:36.480><c> if</c><01:23:36.719><c> you</c><01:23:36.880><c> need</c><01:23:37.520><c> u</c>

and and one last thing is if you need u

and and one last thing is if you need u
uh<01:23:38.719><c> any</c><01:23:38.960><c> AWS</c><01:23:39.520><c> credit</c><01:23:39.840><c> for</c><01:23:40.239><c> any</c><01:23:40.480><c> of</c><01:23:40.639><c> your</c>

uh any AWS credit for any of your

uh any AWS credit for any of your
project<01:23:41.360><c> uh</c><01:23:41.440><c> just</c><01:23:41.600><c> ping</c><01:23:41.840><c> me</c><01:23:42.000><c> on</c><01:23:42.080><c> LinkedIn.</c>

project uh just ping me on LinkedIn.

project uh just ping me on LinkedIn.
I'll<01:23:42.719><c> share</c><01:23:43.040><c> a</c><01:23:43.280><c> few</c><01:23:43.440><c> credits.</c><01:23:43.840><c> Okay.</c><01:23:44.000><c> Even</c><01:23:44.320><c> if</c>

I'll share a few credits. Okay. Even if

I'll share a few credits. Okay. Even if
you<01:23:44.800><c> need</c><01:23:45.040><c> more,</c><01:23:45.360><c> I</c><01:23:45.679><c> can</c><01:23:45.760><c> give</c><01:23:45.920><c> you</c><01:23:46.080><c> more.</c>
