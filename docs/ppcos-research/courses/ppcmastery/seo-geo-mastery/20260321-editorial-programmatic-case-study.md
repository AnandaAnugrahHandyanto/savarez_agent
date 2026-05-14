# Editorial-Programmatic case study

- **Source:** PPC Mastery (hub.ppcmastery.com)
- **Course:** SEO/GEO Mastery
- **Section:** Advanced SEO
- **Duration:** 20:45
- **Transcribed:** 2026-03-21

## Transcript

So welcome to this lesson. In this lesson, we will look at the actual editorial programmatic case study that we've built for our client Planico.
We already looked a little bit at the prequel of this with like the audience research, keyword research angle.
But in this lesson, we will really dive deep into this and you will learn how we build a around 250 page content cluster with a single workflow.
An AI based workflow, how much traffic we got from this cluster in three months, and how many leads we got.
Because as you might already know from the previous modules and lessons, leads and pipeline and business results is what actually is important in SEO these days.
And traffic is sometimes a, let's say, necessary evil we need.
But in the end, this is what we...
What we really care about.
So let's dive into that.
And I want to say that this is a real radiant project.
I obviously already told you that, but that we now charge like 10k plus four.
So these programmatic editorial projects are have very high demand currently.
So I'm actually giving you a little bit also of our secret sauce here.
Because I want to make this as valuable.
Especially...
As possible for you, but yeah, this is a real project and real product.
So to say we have, and I'll show you basically how we created a strongly AI supported programmatic content workflow that drove over 2000 clicks and 24 leads in just 90 days.
And you might say that 24 leads is not a lot, but keep in mind it's SEO and it's something that.
Only compounds over time, if done right.
And most people still tell you, you can't drive any meaningful business results from SEO shorter than like six months or 12 months.
But in this case, basically we did it anyway.
So yeah, this is, this is basically the whole, whole setup of this.
So the whole case is built on an Arabs grid and I don't want to do.
Any, uh, like advertising here.
I'm not affiliated with Arabs in any way.
It's just a tool that I discovered, um, mid of 2025 and decided that it's a, it's a great tool.
I like it a lot and that it helps us to realize, uh, things we weren't able to do before with tools like Zapier or, or make, or, and at end.
So, um, the, the Arabs grid is basically a table and you can already see that this table contains.
Um, multiple pieces of data from a keyword.
Over other input fields, like an expert image, expert name, then like this bluish things that are the workflows that I'll show you in a second and what they do.
But, um, to put it simply, like what is Arabs Arabs is like a Zapier make or, and at end, but with content engineering in mind.
So with the idea of being able to.
Create content workflows that are easily scalable.
So you can think about Arabs like this visual interface where you can just put on blocks that are purpose-built for content work and SEO work.
So we might have something like a Google top 10 search.
We might have something like a perplexity, deep research.
We might have, um, LLM steps where you can basically prompt a chat.
GPT.
Or Claude or other models that you like.
Um, and then use the output from these, um, models in these LLM steps.
Um, during the workflow to then do other things with it, we can even look for, uh, stock images.
We can work with these stock images.
We can run code.
We can call APIs, all sorts of cool things.
And this is basically a combination.
So in Arabs, you have these grids, like the tables where you can.
Um, have.
Um, for example, our 250 ish, um, keywords, and then you can have a workflow and then you can basically let the workflows run for each and every row of your grid.
So for all of the keywords, and this is like basically the, the, the secret sauce and the, the superpower here.
So every line on the grid, as I just told you loops through this.
So for each and every keyword, we have this workflow and for each and every keyword, we basically, uh, go through, uh, multiple differences.
Um, and then we can see the different steps that in the end, um, our models in this way, you have a different process when we go through it.
Um, and then we're able to create content, and this content then goes live on the page.
And with this content, we generated the around two K clicks and 24 leads.
So let's dive into this workflow, um, a little bit deeper.
Um, so you get a better idea.
So, first of all, you have different input settings.
So in these input settings you would you usually, for example, um, include your, your target keyword.
Um, yeah.
additional information that you need in this workflow. So if we, for example, need to know
if the location is for a city or for a state, or maybe also for a country, but in this case,
everything was connected to Germany, this would be different input parameters you want to send
into the workflow, because in the workflow, you obviously have to work with these parameters to
then search for stuff, do different queries, and further process it. So in our case, the first step
we had, although it says step four here in the screenshot, but it's just based on that this step
was added as the fourth. The first step we have is a Google search top 10 results. So we basically
took our keyword, and then we do a Google search because we wanted to know what are like the top
results on Google.
Then after that, we do a perplexity deep research. So in this perplexity deep research,
we basically queried an official government sources for the specific regulation in the
location we are working on. So if we are working on Baufuhr-Frage Bayern or Baufuhr-Frage Munich or
Berlin, we wanted to really understand, hey, what are the local regulations in Bavaria, in Berlin,
in Hamburg?
It's a lot of information. So we wanted to really understand, hey, what are the local regulations in
Bavaria, in Berlin, etc. And so the perplexity deep research step, and this is maybe the first
like key learning for you here, is most powerful when you are the most specific in what you want
to be researched. So if you only say, hey, yeah, tell me everything you know about Baufuhr-Frage
Bayern, the output will probably be pretty good, but it's not as specific as we wanted to have it.
So we wanted to be really sure that the output we got
was
from the highest authority sources possible. This is usually government in this case,
that it included some key pieces of information. So the different norms, like the different like
legal basis for stuff. And we wanted to understand the responsible authorities. So
which state hall or like local authority is actually responsible,
you know, for the legal basis for stuff. And we wanted to understand the responsible authorities,
so we wanted to have this to then use it in our content, because we felt like this is very important to create the most user friendly and like the most, the content with the most information gain possible.
Then after that, we did a little bit of a, let's say, playing around type of step. So we basically took our input,
so we basically took our input,
which was the location. So let's say it's Munich. And then we had a GPT five
nano step where we basically just said, Hey, please determine if this is a city or a state,
and then respond with city or state.
And then based on it responding city or state.
We had two different stock image search steps.
So if for example the city was a city that was pretty small.
We had.
We.
would rather search for a stock image of the state. So if you
think about a small city in Bavaria, there might not be good
stock images on like unsplash. So we're using unsplash here.
There were not good images for that. So we rather wanted to
just go with a picture of Bavaria that we could use. On
the opposite side, if we were using Munich, for example,
Munich obviously has is a big city has a lot of images also on
the stock image platforms. So we were then rather querying
unsplash for a picture of Munich. So based on that, we
basically had a condition based decision tree. And then after
that, as these steps basically return multiple images, we then
did another LLM step in this case, a chat GPT
4.0 step because the 4.0 model is a multi model, multi modal
model that can also analyze images. And we wanted to
identify one 16 to nine ratio image because for our page
layout, 16 to nine would have been the best format. So we
wanted to go with 16 to nine. So obviously, you see, these are
all steps that are like not the most complex or like super
technical.
Steps, but it's something that we also as a human would do, but
that we can then automatically run for 250 instances of keywords
or of of pages. Then after that, we would based on the output of
the GPT 4.0 step, we would then extract the image. So just some
some code running doesn't really matter. And then we would have
basically the heart and core of this whole workflow, the content
generation.
Step. And I will go into the content generation step in the
next lesson where we will really look at the the individual lines
of this prompt. So I don't want to, like hide this from you. But
I also didn't want to make this lesson too long. So the content
generation step is basically creating all the different
content we need. So from like meta title meta description, to
to the actual
body content that that that then would go live on the page.
And this is all here. And then you just have the final step in
Arabs, you always have like a final step where it just forms
everything as a JSON, you can connect the different outputs to
that. And yeah, this is rather uninteresting, I would say. And
something that is really important, maybe also in this
case study is
something that we used in the content generation was a gold
standard page. So we
created, before we went for this cluster, we created one. Yeah,
not really handmade page. So it's handmade. But we obviously
also used AI for that. But not in this like highly scalable
programmatic setup. So we created this handmade gold
standard page. And yeah, did a lot of manual research, feedback
it with our client made sure it's like, top notch in all
aspects. And this is also something that I would always
recommend. So if you think about any like a programmatic or like
editorial type of strategy, I always believe that having a
gold standard page is super critical. So you have very, very
high quality input that goes into an AI based content
generation step. Then something else we we did to really drive
as much leads as possible is we built a dedicated lead magnet.
So if you
have
like,
250
pages that go live and each of the page maybe targets like um like small or like medium-sized
keywords based on the volume that are very um specific and um but you have this like cluster
that is connected topically strongly like um all of these pages basically cover the topic of
then it might make a lot of sense alongside your main cta which could be a request an offer
or like um get get a free assessment or whatever to also have a dedicated lead magnet that people
can get with a lower barrier than actually requesting the service and this is something
that we got that we built and where we also got some leads from which is cool um and i mean if
you're creating something like this you have to make it really valuable
and we did this and we put in a lot of effort but it's cool and we can like if we would only
have our handmade gold standard page it would just be one page about where this is a perfect fit
but if you think about the whole cluster this is basically a perfect fit across 250 pages now
and even if we would for example expand the cluster with more locations so more cities like
maybe we think about um 5200 cities more to make it even more long tail
then we immediately have the perfect fitting lead magnet to capture the interest of people
that are maybe still early in their buying journey um with our purpose-built um asset here so this is
also very cool and then just for you to maybe picture this a little bit better this is the
final result so we have pages and maybe you remember it from one of the earlier models
we have pages that are um like looking very similar um but in terms of the content they
are very unique so we ensured that on every page we covered um the necessary paperwork you need
in the different locations because this might um differ from state to state from city to city
um the costs um the the um the the local authorities um the most common reasons why
these requests fail etc etc so it's very unique and we are
also ranking really really well but we have basically this um like templatized format and
although it's it's very different to a product page or a category page it's still strongly
programmatic but also clearly editorial so this is why we called it this like editorial programmatic
strategy and since going live in september it drove like 2300 net new clicks and what I mean
by net new clicks is this is not
cannibalizing from anything we already had on the page because basically none of these
keywords and searches have been addressed before on the page so we obviously created this gold
standard page and the gold standard page addressed the the main keyword of powerful and some things
connected to that and probably we all already got maybe one or two um clicks to the side also based
on localized
searches but um yeah this is this basically complete net new and although we um we have
been approaching the Christmas time here like in um December um it's still working really well
and like growing constantly and we are really looking forward to January and February because
this is basically high season um for this whole topic and then also as I promised you um we
really drove 24 net new leads also from here so this is a screenshot actually from the air table
um analysis or diagrams um from this client and already in the first month we got four leads then
in October 6 and then in November um 14 so you can really see how the whole ramp up um worked
very well and we um have around one percent um conversion rate on this cluster it's obviously
something that is like a step before the actual
service so the the building um permit but um still we're very happy because these leads are
also pretty qualified and I think it just proves that you do not have to wait like six months or
12 months to actually drive leads from something connected to SEO and always keep in mind 24 net
new leads might not seem much but it's but it's just compounding so we don't have to spend more
now on this cluster
So basically, it's done.
So obviously, we might tweak some things here and there,
but we just invested something into the cluster in the beginning.
So if we, for example, would get now 15 leads in December
or maybe 14, 15 due to Christmas holidays,
and then in January, we maybe get 25 leads,
we haven't paid a single euro for these 25 leads.
In comparison to PPC, which obviously is a great channel,
but we would have to pay like a four-digit amount probably
to get these 25 leads then in January.
But in this case, we will just see more and more leads over time.
Maybe here and there, we have to refresh the content.
But this is the beauty of SEO, and this is the beauty of organic growth.
So summing up,
this whole lesson, I obviously have a few key takeaways for you again.
So first of all, you can use AI to execute a mix of programmatic
and editorial strategy, as I just showed you.
And you can still drive a lot of net new traffic if done right.
And I just want to be clear about that.
Obviously, we have also said traffic is not a main KPI, and it is not.
So the leads are the main KPI.
But if you...
If you have no visibility, basically for a topic,
traffic can still be a good proxy to see if you're moving in the right direction,
especially for very specific bottom or mid-funnel searches
that are strongly connected to your service.
It might make sense to look at this.
So always do it in a nuanced way.
Then using a mix of main conversion, so the actual service request,
and a lead magnet works.
And this works really well, especially if you can use a lead magnet
across a big portfolio of pages.
And then always prioritize quality over quantity.
This is what we try to do with our handmade gold standard page,
which was the necessary basis.
How we actually use this, I will show you in a second in the next lesson,
when we will talk about the autonomy of our system prompt.
But generally, keep in mind,
that you should not lower your bar of quality with AI to just scale quantity.
You should try to increase the quality first.
For example, with our perplexity deep research step,
where we were able to conduct really thorough research across all these different locations,
which would have been very, very, very much work manually,
and only then scale the quantity.
So that being said, I hope this was an insightful lesson for you.
So that being said, I hope this was an insightful lesson for you.
So that being said, I hope this was an insightful lesson for you.
And hope to see you in the next one.
