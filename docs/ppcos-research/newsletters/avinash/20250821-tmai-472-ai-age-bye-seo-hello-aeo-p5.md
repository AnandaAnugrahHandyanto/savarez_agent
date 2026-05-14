# TMAI #472: ⚖️AI Age: Bye SEO, Hello AEO! -P5

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2025-08-21T08:16:15.000Z
**Folder:** avinash

---

[The Marketing  Analytics Intersect, by Avinash Kaushik] [1]

TMAI #472: BYE SEO, HELLO AEO! -P5
[Answer Engine Analytics | Methodologies & KPIs]

[ Web Version [2] ]

THE PRESENT: Answer Engine Optimization (AEO). Check.

THE FUTURE: Agentic AI Optimization (AAO). Done.

THE DRIVER: Answer Engine Analytics (AEA). Today!

The comprehensive implications of this transformative moment,
_searching_ to _answering_, span your: A. Site experience. B. Digital
Tech Stack. C. 1P & 3P content + distribution strategies. D. Digital
advertising tactics. E. Managing the transition of advertising to
Humans to advertising to Agents.

All of this excitement creates a new need: Data!

At the moment, there is no Webmaster Tools. There are no referring
“keywords.” No data from AEs. Our traditional tools like Google
Analytics have limited visibility (in referring strings).

Luckily, we have some early forays into qualitative and quantitative
data “extracted” from LLMs. These tools can guide our strategic
journey though implications A through E above.

I’m going to focus on two tools I rely on for Answer Engine
Analytics (AEA):

*
TRAKKR. [3]  It is simple, well crafted, and has a free option. I
want you to start tracking tomorrow. Free makes that easier.

*
EVERTUNE. [4] I started working with Ed when Evertune (ET) was a
spreadsheet. It has blossomed into something smart, layered, and
sophisticated.

[Disclosure: I made a tiny, tiny, tiny angel investment in Evertune in
Oct 2024.]

I’ll cover both below. Through my examples (and nit-picking!),
you’ll learn how to evaluate any tool claiming to offer Answer
Engine Analytics (AEA).

4A. ANSWER ENGINE ANALYTICS: METHODOLOGIES & KPIS.

AEA tools are best thought of as competitive intelligence tools –
inferring behavior in an ecosystem, from the outside.

Because inference can be done in, literally, a thousand different
ways, and this space is so new… I want to start by emphasizing four
higher order bits covering how LLMs actually work. These are things I
worry about first when someone throws a tool at me, emphasizing it is
God’s gift to AEA. Each element below has a major implication on
signal quality when it comes to measurement.

ANSWER ENGINE HIGHER ORDER BITS.

The Answer Engines space has a number of _weird _realities to account
for when you get into Analytics. You should know the impact of each.

A. PROBABILISTIC VS. DETERMINISTIC.

It is critical to internalize that LLMs, Answer Engines, are
_probabilistic_.

Translation: THEY VARY THEIR RESPONSES ON EVERY REPLY, even when the
account, person, ip, all other bits held constant. That’s because
LLMs are, and this is a massive simplification, _next word prediction
models_. They generate text on the fly. Their responses keep changing.

This is different from traditional Search. You and I could get
different responses to “_most affordable Asian destinations_,” but
it was rare for me to get a new set of results from the same
browser/computer/location if I typed that query, say, every two
minutes. A more deterministic approach.

B. LEARNING CORPUS & INFERENCE.

Like Bing & Google, different LLM models LEARN in different ways.
Hence, your brand could rank x in one and xy in another.

LLMs have different data sources, processing, algorithms, weights,
_safety _measures and so much more.

This means each LLM casts a wide net, to get a partially complete
picture.

C.  “TEMPERATURE.”

To control hallucinations, and how _creative _the replies are, LLMs
have a _temperature _setting.

Low temperature = direct answers. High temperature = more creativity.
Temperature is often a behind the scenes setting, though some models
allow you to play with it.

Temperature settings (by the LLM or you) can have a massive impact on
the answers returned (and the data you track).

D. MODEL SIZE/TYPE.

In the last year, one of the coolest developments in LLMs was “Deep
Research” / “Thinking”. Because we discovered that, unlike the
old Google model of _results as soon as you start typing_ (!!), if we
gave the LLM time to think, the answers got materially better.

I can ask _“can you recommend a super cool cross-body bag for an NYU
student, with an understated sense of style?”_ in the “Quick”
mode or in the “Thinking” mode. Each offers a different answer: At
two price points... Foldie Crossbody & Maison de Sabre for _quick_
mode. Bellroy Tokyo Crossbody & Everlane Form Bag in the
_thinking_ mode. If I try that query on a small offline model running
on my Z Flip 7 phone, I’ll get a different answer.

Please re-read and truly internalize the implications of the A, B, C,
D. The implications on choosing the optimal analytics tool are
immense.

Leaders want _deterministic _data, with _confident _analysis. That
is not possible, for now. We have a lot of data; we can be more
informed re what’s going on inside AEs.  You need to be comfortable
taking action after combining _probabilistic _analysis with your
business experience.

The implications of A, B, C, D, could also easily cause paralysis.
That would be unwise.

AEA METHODOLOGY: QUESTIONS TO ASK.

Having deeply internalized the _higher order bits _above, ask the
following four questions before you choose an AEA tool. It helps if
your nose’s _bullshitake detection _setting is on high.

1. HOW DOES THE PROMPTING WORK?

For Search Engines, Google and Bing just gave us what the customers
were typing (key words/phrases). For Answer Engines, there’s no such
thing – no one is sharing the prompts the customers are typing. The
AEA tool builders build a prompting engine that attempts to replicate
what customers type, hence the MOST CRITICAL AEA tool feature to
figure out…

*
_Do you have to write your own prompts? _
*
_Does the vendor write them for you? _
*
_How do they triangulate what customers are typing? _
*
_How deep do the prompts go (just name of the brand, products,
more)? _
*
_How to the prompts manage brand name variations (misspellings,
abbreviations)? _
*
_How do they identify competitors (fantasy competitors identified by
Brand, or actual competitors in LLMs)?_

Sweat this one. Asking company employees to come up with the prompts
is an awful idea, we don’t understand our customers (trust me). Look
for as much intelligence and automation in the prompting as
possible.

(Evertune uses an Intelligent Prompt Generator, which crafts thousands
of custom prompts for your category, product features, use cases, and
competitor comparisons. This gets you closer to reality in an
environment where you don’t know the inputs.)

Special Question: _How do they cluster prompts into topics (prices,
features, sentiment, etc.)?_ Ex: The best approach for measuring brand
sentiment is to ask the model to write reviews for your brand. A poor
approach would be to ask “w_hat are the best handbags,_” it
won’t get you the full picture of what the model thinks about your
brand.

2. HOW DOES THE TOOL ENSURE INSIGHTS ARE MEANINGFUL?

Items C and D above combine to create the challenge that every answer
to the same prompt might be different. You want to ensure the
“answers analysis” is statistically significant, and able to
separate the real vs. random from the LLMs.

(Evertune’s use of thousands of prompts to get a distribution of
answers for meaningful insights. Then, the tool uses “_dynamic
sampling_” to ensure that you uncover statistically valid patterns.)

Special Question_: How is the AEA tool accounting for AI SLOP puked
out by all LLMs?_ By know you all know AEs puke out tokens that are
real sounding… Until you actually read them!

(Evertune deliberately uses a statistical led approach to address the
AI’s tendency to spew tokens.)

3. HOW DOES THE TOOL TRIANGULATE ITS INSIGHTS?

Remember, we don’t actually have access to the prompts being typed
by humans.

As company employees, you can write thousands of prompts for what your
customers might type, and not come within a hundred miles of what they
actually type. The tool will face the same problem when (if) it is
writing thousands of prompts.

Ask them: _How are you triangulating the prompts to be closer to what
the Brand’s actual customer are typing?_

(Before prompting and getting data, Evertune does three things to
triangulate: A. It collects first-party data from tons of consumer
Apps to model the average user’s experience. B. It has built a panel
of 25 million Americans to understand _what_ they are searching for,
language, frequency, and _how_ they are searching. C. They use the
LLMs direct API access to identify the model’s baseline behavior vs.
what they see in the consumer panel. At the end of A, B, C, they gain
the ability to stuff their Intelligent Prompting Mechanism with real
customer behavior from the mobile app and customer panel.)

4. HOW MUCH DATA PUKING DO YOU GET VS. _INSIGHTS_?

Data = What.

Insights = Why.

Actions = Why turned into Profits.

A lot of AEA tools I’m seeing are just puking a lot of _what_, often
with questionable methodologies. This looks impressive in sales demos.
It does not take too long for the realization to dawn that empty
calories are not good for your health.

Ask the AEA tool vendor:

*
_How do you derive the insights you recommend? _
*
_What assumptions and biases go into them? _
*
_How much analysis, segmentation, does your tool allow?_

(Evertune’s latest iterations have a new cluster of reports with
insights re how to change your content strategy to change your
_citations _rate, or improve your AI Brand Index score. Lots and lots
more work to come into this space. Ex: I want much richer, directive,
insights re how to turbocharge my 1P and 3P content strategies.)

As a paying Subscriber of TMAI (merci!), you know: Methodologies slay
metrics.*  Before you start using a tool, spend time asking the
questions above. Pick the vendor who answers simply, and points out
other glaring bits they are unable to measure. That should build
confidence.

* Slay as Millennials say it, not as Gen Z say it. 😊

ANSWER ENGINE ANALYTICS: SUCCESS KPIS.

In my Answer Engine Analytics work, I’ve found the below metrics to
be super productive. I’ve been able to apply them to _Why_ and
identify profitable actions. You will find them in different tools.
This space is evolving at a rapid clip. A new foundational model seems
to drop every other week! In six months, I might discover additional
metrics that are worthy. As a Premium Subscriber, you’ll hear of
them first.

1. VISIBILITY SCORE.

I’m really excited about this one because there was never anything
like it in the old Search world.

Visibility Score is a close cousin of _Unaided Brand Awareness_.

It measures _the percentage of times your brand is returned by the
model when the user’s prompt did not include the brand’s name._

UNAIDED: _Which handbag do you recommend for a teen girl heading to
university in a hot climate?_

AIDED: _Which Kate Spade handbag do you recommend for a teen girl
heading to university in a hot climate?_

Visibility Score measures the first one, which I appreciate as it a
harder problem for a Brand to solve, and the impact is immensely
resilient. Here’s how it looks like in ET…

[Evertune: Visibility Score.]

Coach has pretty good Visibility Scores. Seeing variations is of
values, ex MK is high on Gemini but low on ChatGPT. LV’s is crushing
both ChatGPT and Gemini (but their average score is getting hosed by
their low Visibility in Meta AI - they are a 24!).

TRAKKR has a metric called PRESENCE SCORE, a close cousin of
Visibility Score in Evertune. From the Help docs, it is unclear if it
is in response to an aided or unaided prompts.

2. AVERAGE POSITION.

It is a close cousin of a metric in old Google blue links experience -
also called Avg. Position.

It measures the average position of your brand in the Answer Engine
response...

[Evertune: Average Position.]

On Gemini the brand Coach appears in the Average Position of 7, on
ChatGPT it is 5.8.
The higher, the better.

Putting Visibility Score and Average Position together is insightful.
Coach has a very high Visibility Score (hurray!), but a poor Average
Position (dang!). This insight highlights the urgency of focusing on
earning influence (via 3P influence – see TMAI #470 [5]).

Slightly confusing… TRAKKR also reports position using a metric
called Visibility Score. It is computed using: 1st place = 10 points,
2nd place = 9 points… 10th place = 1 point. Total points are
presented as an indexed score on a 100 scale. In a super clever trick,
Trakkr applies square root scaling to make the score differences more
meaningful and to prevent artificial inflation.

[Trakkr: Position Score.]

3. AI BRAND SCORE.

AI Brand Score was created to make things easier for our Extremely
Senior Leaders. It is a compound metric created from the combination
of Visibility Score and Average Position.

An AI Brand Score of 100 means you are in the 1st position, 100% of
the time.

In Evertune, subsequent positions, decays your visibility by 10%. So,
being in 2nd position has 10% less weight. 3rd position, 10% less
weight than being on 2nd. _Yada, yada, yada._

[Evertune: AI Brand Score.]

The AI Brand Score does a better job of calculating an attention
curve, because Average Position can be misleading. Each of the
thousands of prompts shows a wide range of potential positions – for
the same brand on the same prompt! (Review A, C, D above.)

As a Marketer, realizing that Evertune is measuring the _unaided brand
awareness _of an LLM/Answer Engine, AI Brand Score does something
cooler.

At Tapestry, under the stewardship of our CGO Sandeep Seth [6],
we’ve boldly invested in transformative brand marketing. The
positive impact of that on humans is visible in our current revenue
and profits (which are public [7]). Now, the AI Brand Score will help
us see the impact of all that brand marketing on LLMs! _How do the
“robots” think of us?_

In the short-term, a higher AI Brand Score will ensure the AEs return
us, our products, as the answer more often.

In the long-term, as Agentic AI takes over shopping from Humans
(review TMAI #471 [8]), the “robot’s” internalization of our
brand marketing will ensure that Agents buy from us because the
special magic of our brand transcends price. 😊

ANSWER ENGINE ANALYTICS: DIAGNOSTIC METRICS.

In additional to the big three KPIs above, there are a clump of
diagnostic metrics (review TMAI #448 [9]) that help me identify
insights, and convert them into actions.

1. AI EDUCATION SCORE.

To increase your Brand’s influence with LLMs, you are going to have
to execute a new and improved 3P INFLUENCE STRATEGY (review TMAI #470
[5]). For that, you will need to know which third-party domains are
relevant and useful for your company/products/services.

AI Education Score rates domains by how much they might help you get
your content into models. It is a compound metric (10 point scale),
calculated by looking at whether the domain permits crawling,
relevance of the domain to the category, and the propensity for the
domain to be cited.

PR, Affiliate, Earned Media teams this score is your new BFF.

Caution: Identifying if a URL is included in a citation or source can
be misleading, as there are domains that influence the model itself
but are never cited. Ex: We know Instagram posts impact Meta AI, but
Instagram is rarely included as a source. Hence, the more
sophisticated multi-dimensional approach above by Evertune.

2. BRAND SHARE OF VOICE.

bSOV is calculated by taking the top 50 domains, estimates how many
pages are about the product category, and then what % of those pages
include the brand (our band).

It is super useful in sense checking your relative volume vs.
competitors on most important domains.

Ex: Bag Vanity has an AI Education Score of 10.0 in our category.
Coach’s bSOV on it is 6.7%, LV is 10.2% and Prada is 7.5%. On Marie
Claire, Coach is 1.5%, Prada is 12.1%.

See… Actionable. 😊

3. MENTION SHARE.

Another helpful 3P content distribution diagnostic metric.

The Sources report identifies which domains/URLs are specifically
included in the answers that the LLMs are providing to user
_resolution questions._

Evertune computes how often a URL (say Bag Vanity, Marie Claire) is
mentioned as a source in the answer provided by the LLM.

Mention Share is simply your percentage of total mentions.

Ex: For Coach, for the URL Marie Claire, the Mention Share is 1.7%.
But. In ET I can segment the data. When the focus is Price Coach’s
Mention Share jumps up to 3.3%.

ANSWER ENGINE ANALYTICS: SEGMENTATION CAPABILITIES.

_All data in aggregate is crap_. – Me. Long time ago. [10]

I appreciate the ability to segment the data by the Success KPI I’m
interested in. I can do that for AI Brand Score and Visibility Score
below.

It is also helpful to segment by model. The data below is for ChatGPT,
but I can segment and view any other model (I am surprised by just how
many people use Deepseek!).

[Evertune: AI Brand Score Segmented, Deepseek.]

I can pull up data for any of my many, many competitors.

The paid version of Trakkr also has segmentation capabilities.
Here’s the segmented sentiment analysis reports, as an example…

[Trakkr: Sentiment by Segment.]

As you explore the tool it is worth remembering: Every tool will have
massive data puking capabilities, few will have Success KPIs and
Diagnostic Metrics that are actually useful, and only the rare will
have deep segmentation capabilities.

Overvalue that last one.

NEXT WEEK.

I’ll share my favorites reports that have higher likelihood of
delivering actionable insights.
I’ll do so using a step-by-step process I’ve perfected (for now!):

*
Read the WORDCLOUD REPORT. Find the words that are small that you want
to be big.

*
Use CONSUMER PREFERENCES REPORT to identify your strengths and
weaknesses.

*
Use the AI EDUCATION BRIEF REPORT to write content to build on your
strengths and combat weaknesses.

[Special Note: Don’t try and _bullshitake _the LLM/AE. If you have
weaknesses that are legitimate, no amount of your 1P and 3P content
will work – the LLMs have way, way, way, more sources than you can
get to. It is always better to actually fix a weakness across your
products & business.]

*
Use the CONTENT ANALYTICS REPORT to publish your content on the
domains with high AI Education Scores.

*
Monitor the impact of all this work using the OVERVIEW REPORT, and AI
Brand Score KPI.

*
Win.

Lots of screenshots, lots of details, lots to get you from 0 to 900
mph in xy seconds!

BOTTOM LINE.

In a space that is evolving by the day, it is critical to hitch your
ride to the very best methodology available. Of the tools I’ve
analyzed, 95% die right here. It is so easy to identify no matter how
pretty the reports, the methodology cannot stand up to the tiniest
poking.

Then, as was the case with SEO & Webmaster tools, it is critical to
separate the KPIs from the Metrics from the Vanity… Ensure that the
ones you do pick can pass t [11]he _three layers of the So What
test_. [11]

Carpe diem.

-Avinash.

Thank you for being a TMAI Premium subscriber - and helping raise
money for charity.

Your Premium subscription covers one person. It's fine to forward
occasionally. Please do not forward or pipe it into Slack for the
whole company. We have group plans, just email me.

[Subscribe [12]]  |  [Web Version [2]]  |  [Unsubscribe [13]]

[14]
[15]
[16]

©2022 ZQ Insights  |  PO Box 10193, San Jose, CA 95157, USA

Links:
------
[1] https://www.kaushik.net/avinash/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[2] https://tmai.avinashkaushik.com/web-version?ep=1&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=bd381264-7e2d-11f0-8e3a-8f0c2da25a74&pt=campaign&t=1755764175&s=99ac5eb51cb83e981ced4b3e9eda1c695e1ca966a6e33856e1169362ff5b19f9
[3] https://trakkr.ai
[4] https://www.evertune.ai
[5] https://eomail1.com/web-version?p=953505c4-7414-11f0-97d1-a7bab3347603&pt=campaign&t=1754632175&s=4558f7cf167bfe18143e775e794ba3a6cf1e61d0ac477a03e16802e2733361c5
[6] https://www.linkedin.com/in/setsandy/
[7] https://www.tapestry.com/investors/
[8] https://eomail1.com/web-version?p=fefb64cc-78b4-11f0-b637-f5b884b5c7ae&pt=campaign&t=1755159392&s=389df0dd69cfa745533742bae064f50da372e3bd845398d03b9fc7125464f21a
[9] https://eomail1.com/web-version?p=d83266d8-f592-11ef-9ace-23ed803a2b38&pt=campaign&t=1740731677&s=076643b5ba5f1212e171282552b062348379094261e48109884e8093bbe62931
[10] https://www.kaushik.net/avinash/excellent-analytics-tip2-segment-absolutely-everything/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[11] https://www.kaushik.net/avinash/kill-useless-web-metrics-apply-so-what-test/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[12] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[13] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=296c812a-be87-11ea-a3d0-06b4694bee2a&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=bd381264-7e2d-11f0-8e3a-8f0c2da25a74&pt=campaign&pv=4&spa=1755764147&t=1755764175&s=6f9818766501f938f2bd920443e139494e46aa0f59d9913bf09ebd5554492a5b
[14] https://twitter.com/avinash
[15] https://www.linkedin.com/in/akaushik/
[16] https://www.instagram.com/avinashplusworld/?hl=en
