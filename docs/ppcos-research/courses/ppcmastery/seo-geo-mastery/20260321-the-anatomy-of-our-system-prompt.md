# The anatomy of our system prompt

- **Source:** PPC Mastery (hub.ppcmastery.com)
- **Course:** SEO/GEO Mastery
- **Section:** Advanced SEO
- **Duration:** 18:59
- **Transcribed:** 2026-03-21

## Transcript

so welcome to this lesson the third lesson of module number five and in this lesson i will
show you the anatomy of our system prompt so in the previous lesson i basically took you with me
behind the scenes of a very exciting case study we were working on with a programmatic editorial
um cluster we built and if you remember in the aerops workflow i showed you there is this content
generation step and the content generation step is obviously super critical but i feel like
just quickly going over it in the last lesson would not have been sufficient so it's the right
thing to have a dedicated lesson to really show you how we built this
um because it tells a lot about our general um way of thinking about this and also um do's and
don'ts um that you should keep in mind so this is why in this lesson you will learn two key things
the first one is how we built the system prompt to power our programmatic cluster if you haven't
watched um the the previous lessons in module number five i highly recommend to do it because
otherwise you will
not have the necessary context and then secondly what is critical to get strong output and not
ai slop because obviously we're working here with a heavy ai supported workflow and this is this is
very important for us because as you might have learned from the previous lesson we do not want
to lower our quality bar and just scale quantity but we want to push for maximum quality and then
afterwards scale the quantity so um first of all a key principle that we are using at radiant is
a clear separation between the system prompt and the user input so we like to work in that way
because we have a clear distinction between let's say the general guidelines and then the dynamic
inputs we pass on for the llm to work on so you can see here it's just an
extract and it's not the full system prompt but the system prompt on the left starts with
your task is to generate fully seo optimized localized content about
pre-numerary building inquiry for a specific german location based on the provided inputs
while ensuring factual accuracy and drain consistency etc and then on the right you can
see in chat which is basically if you think about a custom gpt maybe in chat gpt so you
have a custom gpt and then you have a custom gpt and then you have a custom gpt and then you have
your pre-built instructions and then you have the actual dynamic input that that you type in
the chat here is basically the things we type in although we do not really type it in because it's
obviously a automatically running workflow um but here we pass on all the individual variables
so we pass on our location so if our location was munich we would pass munich here the location type
so if it's a city or a state from munich it's a city then the current google search results that
we got from a previous step then the fact verification results so this is basically
the perplexity deep research step then stock image url we integrated this here because we
also wanted to have the url integrated in our html content that was created and then we have
the reference content the gold standard content in this particular case and then we have the
programa sorry it's cessed view of online so the first step is to now go to the channel
you guys have a streaming Wikipedia page if u disliked this up so you can visit the channel
it will appear up here on the screen if you want to use e-mail inspected streams to rush
ressearch do so as you see already just a short video and yeah have been a little ado
is also a fan of doing the 401k this unique
like a little bit of the prompt here a little bit of the prompt there it's very
hard to understand what is prioritized over what in this particular case it's
very clear we're passing the inputs via the chat or like the user input and then
over the system prompt we have everything that is like the guideline
and how things should be handled so this is maybe learning number one learning
number two we always start a system prompt with like critical guidelines and
the input structure because we want to ensure that the LLM really knows the
most important things up front so we have the task description this is what
we start with and then we have something that we call like the critical first
guideline that we put in here which is generate content based on all provided
inputs the reference content from Planico's main page is your gold
standard for tone style and factual accuracy all content must align with
this reference
while being localized for the specific location so this is basically how we
would maybe have also formulated a briefing that we give to a writer and we
want to ensure that this is handled with a high priority this is why we put it
very early and we add the the the the word critical here then input structure
we basically explain the different inputs we're having and ensuring that
the LLM understands the general quality of the content there so there for this
what is used for what so location city or state name location type start city or bundesland estate
which is required so we pass it on so it also knows um things that are always there or things
that might be optional then reference content or a search result sorry google search results
about both on location then reference content scrape content from planicus page your gold
standard then fact check results perplexity research results for verification then stock
images relevant stock photos of the location location data specific local information
if this is provided i don't know if we actually used this then maybe in the first version we did
but yeah anyway then after that we start with a content quality framework so we do a couple of
things here that are very specific obviously to this case but i can still see you um drawing like
generally
general conclusions for it so what we did first is reference alignment so we said you must use
the reference content as your primary guide for tone and writing sky service descriptions and usps
process explanations pricing structures and guarantees company benefits and expert claims
expertise claims and call to action phrasing so we do not have to define everything that is
relevant about planico in the prompt itself if we
have a content quality framework we can use it to define everything that is relevant about
planico in the prompt itself if we have a reference and like a gold standard page
that we can just basically point towards so this is something that's very handy if you can pass it
on and if you have this already pre-made page then fact verification process so cross reference all
factual claims with google search results for current local information perplexity fact check
results for verification only use variable verifiable information from official sources
if information conflicts prioritize
like Glueью
official government sources over recent use over general knowledge never invent specific numbers data or
30 names without source��
verification so obviously you can't work against against has hallucination completely but you can
try to minimize it and maybe this is also helpful for you so if you wonder why llms
hallucinate just think about yourself in a multiple-choice test setting so you have two options all the time
obviously it's simplified
two options. If you say I don't know then your chances to win are zero. If you just randomly
select A or B you have a 50% chance of winning and the LLMs are trained to always or mostly give
an answer because they know that if they want to achieve high scores in a benchmark testing
environment they are better off selecting A or B than just saying I don't know. So this is why
LLMs sometimes make up stuff because the chances of at least getting something right and then
scoring some score compared to just saying I don't know and maybe handing in the exam without
writing anything the chances are that you can still get some points from it. So this is why
LLMs hallucinate easily put. Then we have localization requirements. So we said while
maintaining Plinico's brand voice from reference content
adapt examples to local context use verified local authority names from search results
include region specific regulations of verified and maintain exact service promises from reference
content. So you can see that we're very clear and we are always referencing back also to the
input variables we defined. This makes it very handy because we can ensure that we
are very clear with what we mean. So if you just say hey from reference content it could be
much more clear. So if you just say hey from reference content it could be much more clear.
multiple things because there is multiple reference content that you might have provided. But if you
actually define these like variables like as a JavaScript variable for example, it's much clearer.
It doesn't mean that the LLM always gets it right. But from our experience and from my experience,
you can increase the chances a lot. And then also something that you might have already
noticed. So we heavily use markdown here. So for example, the content quality framework starts
with like two hashes and then the subsequent levels start with three hashes.
So it's basically clear how the things are connected.
So the content quality framework is an H2, the others are an H3.
So these all are part of the content quality framework.
And then we have very clearly, easily and concisely written bullet points that are connected
to all of that.
So this is something that we found helps us get maximum clarity into the prompt.
And I can also recommend you just maybe taking your prompt, and then asking Claude or asking
ChatGPT or Gemini, whatever, hey, how can I improve this prompt for maximum clarity,
for the best possible prompting guidelines, etc.
And you will see that oftentimes you will also get like a mark town written version
of the prompt.
So this is just something that we trained ourselves on and works quite well.
Then SEO requirements.
So I'm not going like into each and every detail here.
But what we did here, for example, is we defined the main keyword, we defined like a rough
keyword density.
So I don't know, this is, it's not so important for us.
We just wanted to ensure that this is used a couple of times, we wanted to use this in
the H1, the first paragraph.
But then we also defined the key word density and stuff.
So we always prioritize the reading flow and then natural reading experience over certain
like keyword density and stuff.
Because, you know, actually, I don't believe in it.
And I think it makes it so it's it has become less and less important.
So I think you shouldn't stress about it either.
We define variations to include so something like Baufahrenfrage in location, Baufahrenfrage
stellen, which is basically doing this request, and then beantragen, which is applying for
this request, then cost, then duration.
So different aspects where we know that that people search with this way that people ask
about this topic this way.
So you could change it with variations that are important for your specific topic.
But this is something that we have good experiences with.
I'm using these variations and defining it in the prompt already.
And then secondary keywords.
So this could be something like Bauamt, which is basically the local authority that is responsible
for for the things like giving the the response to the request, and then Baugenehmigung, which
is the building permit and then Nutzungsänderungs, a change of use of the house.
And then Bauvorbescheid.
This is basically the the piece of paper you get if you do your like building pre preliminary
building permit request.
So yeah, this is something that is not the same word, but it's closely connected in this
context.
And context is like way more important now today in SEO than it has been in previous
years.
So this is something that we also wanted to define here, then content structure.
And this is something that I feel like is especially important if you do not have a
content outline already.
But if you basically go into the LLM without a predefined content outline, which we did.
Otherwise, I highly recommend always starting with a content outline.
So outlining like what is the h1, what are the h2, what's the h3, what's the next h3,
what's the next h2, etc, etc.
And then using this as a basis, but we didn't have it.
This is why we defined like, so to say the SEO title.
Which is basically the the manual.
Yeah.
Yeah.
meta title like we had um some variations where we um already yeah basically gave in our expertise
of using like the the main keyword with the location first then the the year name and then
some stuff like the process the cost um frequently done errors or yeah do's and don'ts so to say
saving money winning time how to avoid failures blah blah blah all of that and then meta description
we had a standard we had an alternative and just mixing it up then for the h1 heading we also
defined how we wanted to have it and then for sub headlines we basically said something like
a compelling paragraph directly under the h1 that includes location and creates urgency
so is your project in munich
is it possible to get it uh permitted a preliminary building permit request in munich
gives you security and planning for before your investment planeko building helps you answer
critical questions with your authorities and with over 1400 successful requests we know the local
requirements vary
we know them very well so i i don't want to go into too much of like the the psychology behind it
like the copywriting principles i think there are awesome courses in the ppc hub that can do this
much better but like to this level of detail so defining it to this level of detail
helps a lot to ensure high quality content so we obviously use llms because we think it's a
uh an awesome technology
to like do things quicker and also with higher quality and like on a higher scale than before
but we still want to ensure that we bring all our knowledge and like all our assessment of what good
quality content looks like um to the table to then have the llm basically take it from there
so if you ask an llm create a blog post um
it will just basically create an okayish article um based on its knowledge maybe does a little search etc
but this is like it's mediocre output because it's output that everybody can do
the better we are in understanding our users the better we are in understanding
the topic ensuring comprehensive topical coverage as we talked about in what is actually good at a
tutorial seo the better we do all this and the better we are in articulating it and describing it
in a prompt of the llm um the better your output will be so um that being said um i hope you got a
good understanding of like a lot of our best practices of the prompting and how we structure
such as system prompt um and yeah my key takeaways for you are a strong system prompt is critical for
high quality content output so i can't stress this enough then your guidelines should include all
important elements so don't be lazy yeah i hope you got an idea of how like detail we already are
and um yeah i mean i couldn't show you everything but um try to show as much as possible then you
should define your seo requirements and your content structure this is very important if you
um like have workflows we create different pieces of content
um then always ensure that you have a strong content outline that you go into
that you that you bring um to the llm and then use the system for the heavy lifting of the prompt
and rather use like the the user input or like the the chat or like the the dynamic input for
actually the the dynamic stuff like the variables and the the input that changes and i think it
makes a lot of sense logically and it's much easier to do troubleshooting um of the prompt
um
so that being said this was the last lesson um of this module of module number five uh and i'm super
excited for the next module module number six where we'll learn about advanced ai search or
geo strategies and tactics or drive results uh so very much looking forward to that
and hope to see you in module number six
