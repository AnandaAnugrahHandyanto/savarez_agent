# Building in the Gemini Era – Kat Kampf & Ammaar Reshi, Google DeepMind

**Channel:** AI Engineer
**Video ID:** fgkXEIbZpGc
**Upload Date:** 2025-12-15
**URL:** https://youtube.com/watch?v=fgkXEIbZpGc

## Transcript

[music]
We are super excited to be here. It's
been obviously a very exciting week in
AI. It's been a very exciting and busy
week over here at DeepMind. I'm so super
excited to chat with you about our
newest models and build some demos live
with you all. I'm Cat. I work on Vibe
Cody and AI Studio. This is Amomar. He
leads our product and design team for AI
Studio. Uh but I want to step back for a
second and talk about uh the journey at
DeepMind generally. So what's I think
particularly unique about Google's
journey right now is that Deep Mind has
been innovating here for not just this
week or this past year but for years and
years uh with things like the
transformer, Alph Go, etc. And this is
obviously a graphic from 5 days ago
because it ends with Gemini 2.5 and we
are super excited to have announced
earlier this week Gemini 3 Pro.
Hopefully this message has reached you
all already. If not, we have a lot of
work to do. Uh but this is our latest
most intelligent state-of-the-art model.
Um and ultimately what we want folks to
understand with Gemini 3 is that we can
really build anything and that comes in
two major capabilities. I think the
first is the UI and aesthetic
sensibilities of Gemini 3. It's very
very strong at design understanding and
generating websites and good UIs uh in
one shot. And the second is with agentic
tool calling. So I think this goes back
to the sort of spectrum we're seeing
with models. Sometimes you want a
oneshot website and sometimes you want
to do really complex tasks within you
know massive code bases and that's where
tool calling and agentic use can be uh
be particularly powerful. So with Gemini
3, we see on the right is a SWE
um experiment where it was a base agent
harness across a few different models
and we can see Gemini 3 is vastly above
uh in performance in Agentic scenarios
and then as well leaps above our
previous models and state-of-the-art
across the board. Uh so super excited to
see what you folks build with this
model. Um, and in in the meantime, we,
you know, launched this on Tuesday, but
there was still three days left in the
week, so we had to launch something else
as well. So, I hand it off to Amara to
talk about our pro image model.
&gt;&gt; Yeah. So, at Deep Mind, I think you have
a few days left in the week. You choose
to launch another breakthrough model.
And so, uh, we're really excited about
Nano Banana Pro, which came out
yesterday. Uh, and it's a huge leap on
our our already state-of-the-art image
model. So with Enter Pro, uh, one of the
things that I love about it the most is
its world knowledge. So it's powered by
Google search. Uh, and so you can ask it
all sorts of things like how do I make
this tea? And it'll actually go search
Google search, create an a detailed
infographic for you and diagram for you.
Uh, and there all sorts of things now
with accurate information that it can
do. And the other thing you're noticing
here is improved text rendering. So text
is one of those small details that if
you get it wrong, you can pretty much
pick it up quickly. But an Anim Pro 2
does an amazing job at text rendering.
Uh, and you can see that in a bunch of
examples like here where it wraps around
the can perfectly and it also has a
bunch of localization as well. So, tons
of languages, Korean on the right, so it
can translate images as well and render
them perfectly on the exact same
reference image. Uh, on top of that,
consistency is improved. So, uh, you can
now put up to 14 people in an image and
then can create this group shot you can
see on the right. uh and that uh it can
do more but 14 is basically our our kind
of benchmark so far. Um and that also
enables a whole set of new use cases. Uh
and then creative controls as well. So
you can see here on the left the focus
is on the woman and on the right on the
flowers and this was just a simple
prompt. All you had to say was change
the focus to the flowers. Maintains
everything in the previous image just
changes the focus. So incredible outputs
as well uh with Nano Banana Pro and a
range of aspect ratios. So, if you want
to generate uh wallpapers or big banners
or advertising boards, you can do all of
that as well. Um, so anyway, instead of
talking, we decided we're just going to
show you a bunch of demos live of what
we've been building with these products
uh over the last week. Um, and yeah,
excited to jump into it. So, let's do
that. Uh, all right. So, cat,
&gt;&gt; yes,
&gt;&gt; take it away.
&gt;&gt; Here we go. Cat tabs. Um, cool. So, for
folks who aren't familiar, this is
Google AI Studio. It's our home for
getting started with the latest Gemini
models. You can get your API key, chat
with the latest models, including Gemini
3 and a Banana Pro. Uh, but today we're
going to be focusing on this build
experience. So, this is our vibe coding
experience in a studio. You can see here
we have a gallery of a bunch of example
apps, a bunch of very cool uh to the
aesthetics point of Gemini 3, a bunch of
very cool Gemini 3 examples. Um, but you
can also go prompt to apply here. And
this is free to use. And I think one of
the unique things about AI Studio is how
easy it is to integrate the Gemini API
into your application. So we can see
here at the bottom there's a bunch of
these what we call AI chips um that
showcase a ton of the unique features
beyond just the model you're choosing
with the Gemini API. Different tools you
can use like Google search grounding,
Google Maps grounding. We also let you
build with our live API. So, you can do
oneshot examples of I have one that lets
me input a webcam of my tennis swing and
it'll give live corrections on my swing.
Um,
&gt;&gt; you also made one to improve my posture.
&gt;&gt; Yeah. [laughter]
&gt;&gt; Yeah. If you lean forward too much, live
API will yell at you. Um, so it's a very
flexible way to get started building AI
powered apps. Um, and the other cool
thing is you don't actually need an API
key here for most of the models. So you
can build your application, you can
share it with the world and anyone who
comes and visits your shared application
will be using their AI studio free
quota. So you don't have to worry about,
you know, hopefully you have an app that
goes supervisible. You won't have to
worry about a crazy surprise API bill or
anything like that. Um, so I'm going to
actually shoot off a prompt here that is
using our latest ano banana model. And
that basically allows us to use Google
search grounding to create a
illustration of laptop stickers. And
this is one of the viral trends we've
been seeing with Nano Banana Pro. Um, so
I'll kick this off and what this will
do, I have the AI chip that tells it to
use the Pro model. And this will sum up
my prompt and go talk to Gemini 3 to
break down the task and start generating
my endto-end application. Uh but while
that builds, I'm going to hand it off to
Amara to show some demos in the
meantime.
&gt;&gt; Cool. I think the other thing to point
out here is that uh we're trying to
think through how the vibe coding
experience is also powered by AI every
step of the way. So you're seeing here
even in the loading screen, uh it is
using Gemini and thinking through this
app that you're making and how you could
extend it. Um, and so we're thinking
through breaking those typical vibe
coding paradigms as well and helping you
iterate with the model as your partner.
But anyway, let me jump right into the
text rendering demo. So, uh, when I
heard of text rendering for the first
time and the consistency that we were
getting with Nan Pro, my mind went to
comic books. Uh, and so I was thinking,
why can't I now be in my own comic book
adventure um, and also place cat in
there and then maybe we can tell a
story. And so uh in this app uh also
vibe coded you can just upload a face of
somebody. So I've got some nurse face of
course [laughter]
but I'll use I'll use cat here uh and
myself um and then uh we can choose the
genre of the story um and and all the
languages that we have so far. Uh, I'm
going to do a story about us presenting
at AI Engineer um in New York uh
presenting AI Studio and we are uh vibe
coding and winging our presentation.
That's where we're going to be doing
this comic book story. So, we'll fire
that off. Uh but while we wait for that,
um the other cool thing about this is uh
we'll wait for that to generate. But I
want to show you the design
sensibilities as well. So, you know that
if you've been working with AI models
and generating websites, they've been
creating purple gradients and things
[laughter] that just, you know, they
kill me as a designer. So, um, and so
it's been really nice to see how this
model is able to build some beautiful
websites. So, this is using shader
animations, uh, flowing through all
these different pages, uh, and adds all
sorts of cool transitions and effects.
Picked out the typography by itself. And
this was the initial prompt. Just create
a slick animation website. kind of
actually did say no cyber puncture that
[laughter]
&gt;&gt; but
just got to make sure [laughter]
&gt;&gt; but but yeah you get some incredible
results um and and now what I love about
this is so many folks who you know were
struggling with design who might have
you know still tried to gro their way
around Figma don't have to do that
anymore they can actually just go in
prompt their way to something pretty
nice okay back to the comic book okay
pretty flattering uh comic [laughter]
book here. Um, that, you know, I'll take
it. Uh, and [laughter] you can see here
that it's rendering the comic book. It's
got, uh, rich text rendering showing us
the story. And the other thing here is
that, uh, because it's powered by Gemini
3, it's actually really creative at the
story it's generating. And honestly,
some of these stories have genuinely
made me laugh, which is the first time
uh, that's happened with one of these
models. Uh, and so you can see we're
rushing to the conference. even
background details like the AI engineer
banner over here uh being rendered and
of course since it's a vibe coded app we
can take the story in any direction. So
one feature I did introduce is that you
can choose the direction of the story
midway. So you know do we find a quiet
corner and try to check if our API keys
work or do we just embrace it and go
full improv? I think we're going to go
full improv. Uh and so that's changed
that story. Uh, and so talking about the
humor here, you can see Amaraj, a woman
carrying a suspicially functional robot
dog. [laughter] So I don't know if that
was announced at the conference today,
but uh, pretty cool. Um, and then now
it's generating the rest of the story
here on the right while we wait. So
pretty cool to see how you can make
these really dynamic, rich experiences
with both the creativity of the model
and Nano Pro's image capabilities.
&gt;&gt; Love it.
&gt;&gt; Yeah. Back to you, K.
&gt;&gt; Yeah. Yeah. I will show. Let's hope my
sticker demo is finished up. Uh, cool.
So, I'm going to add an API key. So,
Nana Banana is a new model and it's uh
fresh off our launch of Gemini 3. So,
for now it is a page experience in a AI
studio. Um, but what I can do is I can
see that here I can enter different
words that I want my stickers based off
or I can go use Google search. So, let's
try the Google search. I'm going to type
in a Mars name. And one of the other
cool things about this new model is that
you can select the resolution as well.
So, in this case, I'll just do 1K. Uh,
but what this will hopefully do, but
again, you saw it on one shot live. Uh,
is go talk to Google search, grab the
latest sources on Amar, build the
context about what he likes, what his
laptop stickers might look like. I think
it's just deep mind, but if he were more
uh [laughter] if he wanted to express
himself more.
&gt;&gt; Oh, boy. Uh, and so he can see here.
&gt;&gt; Yeah, there he is. Weekend builder.
&gt;&gt; That's true.
&gt;&gt; Uh, yeah. And for those who don't know,
Amar has a children's book, Alice and
Sparkle, which, yeah, is clearly he's
talked about a lot because it's highly
represented here. [laughter]
&gt;&gt; But, um, very cool to see how it can
bring in that contextual knowledge. Um,
we've also seen this with like news
events, getting relevant information on
that day rather than having to rely on
the knowledge cut off of the model. Um,
so one other thing I'll show you folks
is how we use AI studio to build AI
studio. Uh, so Amar and I have a lot of
ideas, only so many engineers to work on
these ideas. So we love to use AI studio
to ideulate and explore different
concepts. So, one of the concepts we've
been working on is I'm sure you folks
have seen we announced a new Agentic IDE
at Google earlier this week called
anti-gravity. And we know that sometimes
these web-based five coding tools you
they have their limits and you may want
to go into an IDE to add certain
features to the application or make it
specific to mobile things like that that
might be a bit limiting in AI studio
right now. So, we want it to be super
easy to migrate into anti-gravity. So,
what I did here was just a oneshot
prompt of a screenshot of AI Studio. I
said, "Clone this UI as closely as
possible and then add a flow to export
to our anti-gravity app." So, we can see
it did a pretty great job of cloning
light mode. The screenshot was in light
mode, too, of our AI studio application
and copying it and improving a little
bit on Amar's designs. [laughter]
But then we see this new anti-gravity
button that is creating my an export and
then exporting it to anti-gravity. And I
can go and open in the IDE. And I think
these are the types of creative
interactions that web-based vibe coding
tools can be particularly useful for
because if we had went and jammed on
this feature, we probably would have
constrained ourselves to existing
patterns in AI Studio. And in this case,
I told the model, be creative, think
outside the box. And I've played with
this one a bunch. Sometimes it gives a
command line interface for export or
showing the status of the export etc. Uh
so I think it's a super cool way for you
to ideulate on new ideas for UI and kind
of expand on your product. Uh but I'll
hand it back to Omar.
&gt;&gt; Let's do it. Uh and then the other thing
that Gemini 3 has been really impressed
like impressed us with is just making
video games. And so this one was again
pretty simple prompts. Make this racing
game where I have a bot now at a start
screen. Um, and so you can see I got
this 3D racing game in 3JS. Uh, it drew
all the things. I'm racing with a bot
here. Uh, and then one thing I added for
myself to cheat is I can just boost away
and beat the bot. So, uh, pretty nice.
But, [laughter] but the thing I want to
tease actually is that um, all of these
apps so far have been front-end React
apps. Uh, and so the thing that's coming
very very soon to AI Studio is going to
be backend support um, and full stack
runtime. So if you want to install Shad
CN, if you want to do all of those
things, you'll be able to do that again
with one prompt. And the principle with
AI studio here is that we don't want you
to think about those details. You should
just be able to ask, I want to make a
multiplayer app, and we know that you
need to use Express and wire that all up
for you, uh, and abstract all those
details away. So, we're going to try
something a little risky here, which is
we did turn this racing game into a
multiplayer one. Um, and, uh, this was
again a couple of prompts. Uh, so we're
gonna put a QR code up if you want to
join us uh in the racing game.
&gt;&gt; We've never tried with nearly this many
people, so we'll see. [laughter]
&gt;&gt; Hopefully this works. Yeah.
&gt;&gt; Uh, but QR codes up here. Uh, so if you
scan that, hopefully should load the
game. I'm really afraid of how this is
going to explode. [laughter]
&gt;&gt; Here we go.
&gt;&gt; All these cars loading in.
&gt;&gt; Nice.
&gt;&gt; So yeah, if people have scanned that, we
can switch back to the game. Okay. Oh my
god. [laughter]
So yeah, just hit ready uh when you're
all ready. [laughter]
Oh boy. Uh
I think this lobby is going to explode.
&gt;&gt; Never leave.
&gt;&gt; So this is where I shouldn't have added
collisions with other cars because you
could clearly see that we're bouncing
around. [laughter]
&gt;&gt; 19 players, 20 players. I don't know if
this race will ever start, but we're all
blocked on the uh you know the start
line. But 23 players, pretty cool. Uh
yeah, you do all have to get ready for
us to start this race. So, [laughter]
&gt;&gt; so we might be here all day.
Uh but yeah, that is pretty pretty
incredible. Um I can't start this race,
so do you want to wrap [laughter] up?
&gt;&gt; We'll see you Ollie.
&gt;&gt; That's pretty cool. The runtime didn't
explode. Uh yeah, and I think we're
super excited not only about the
multiplayer game. So next time we will
have even more of you folks join uh but
also you know the extensibility that
comes with a full stack runtime. Uh we
want to make it super easy for you to
integrate with our 1P and popular third
party APIs etc. So very exciting next
few months on the AI studio vibe coding
side and super excited for you all to
try it. Um, but I think the one thing I
want to step back and emphasize is is
what makes us so excited about this
project and the work that a lot of us
are doing is that we get to be the first
generation of engineers who are building
tools for a world where anyone can build
software. So I think what's beautiful
about things like vibe coding is
watching people. We actually talking to
a tech support person earlier this
morning who said they started vibe
coding and AI studio after seeing a
YouTube video. And we're really
democratizing who can create things and
we're all getting to build those tools
that enable that. And I think it forces
us to rethink the paradigms that we've
become so used to. So it may not be your
base IDE that people are starting from,
but how can we intuit it as much of the
user intent as possible? And that's what
we want to do with full stack runtime
and AI studio is make it very easy to
not have to think about I want to add a
database, but if your app needs storage,
it'll have storage. If you want to have
a if you have an e-commerce app, we'll
add a payment solution and make it as
easy as possible to build the future of
software. Um, so thank you folks for
joining us. If you have any cool
examples you've built or questions, feel
free to ping me and Amara on Twitter.
Uh, and yeah, enjoy the rest of the day.
&gt;&gt; Yeah, thank you. [applause]
&gt;&gt; [music]
&gt;&gt; Heat.
