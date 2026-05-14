# TMAI #447: 🤗 Confidence Intervals: A Brand Analytics MUST Have.

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2025-02-20T09:16:19.000Z
**Folder:** avinash

---

[1]

TMAI #447: CONFIDENCE INTERVALS: A BRAND ANALYTICS MUST HAVE.

[ Web Version [2] ]

Every once in a while, you find a small lever that delivers a massive
leverage.

For effective and profitable Brand Marketing, I’ve found that the
humble _Confidence Interval_ (CI) computation is that high leverage
lever.

It delivers needed sunshine to Brand campaigns, where it is sorely
needed.

Without CI, a CFO will make poor decisions.

Without CI, it is significantly easier to trick a CMO.

Brand Marketing’s initial impact is assessed via surveys. We declare
victory or failure based on “+1 Brand Lift in Consideration.”

Is that _fake news_?

That’s precisely what I’m going to help you figure out today –
and give you a tool (xls!) that you can use across all your campaigns
to ensure you are helping create a more informed CFO.

That should directly result in an outsized impact on your salary!

WHAT THE HECK IS A CONFIDENCE INTERVAL?

Let’s say we run a campaign to raise our Unaided Awareness using
WeChat in China.

We do the best we can: Pre-testing passed creative + Sufficient media
weight.

We get Brand Lift Study (BLS) results, collected via surveys, from the
WeChat team:

5% LIFT IN UNAIDED AWARENESS.

Let’s randomly assign the name JUDY to our VP of Marketing.

We run to Judy’s office, all proud that the Marketing campaign had
such a massive positive impact – and we ask for a raise. 😊

But… _How real is that 5%?_

It is crucial to remember that the surveys are offered to a tiny
fraction of the ad exposed & control audience. This means survey data
inherently comes with some error due to sampling variability. Sampled
survey results are always estimates, they will always have an _Upper
Level _and a _Lower Level_.

What you want to know is:

_          What’s the range within which the 5% reported Lift
exists?_

The true value of the Brand Lift, is somewhere inside that range.

Here’s what we need to walk into Judy’s office with:

_The Lift from this campaign is 5%._

_We are 95% confident that the true Lift from this campaign lies
between 3% and 7%._

That last bit…  That’s the Confidence Interval (CI). It takes
into account the natural variability in survey responses, and paints a
clearer picture of the campaign’s real impact.

Since the range above is within an acceptable range, I say: _Go ahead
Tracy, ask for the raise._

But.

Upon computing the Confidence Interval, if this is what we said to
Judy instead:

_The Lift from this campaign is 5%._

_We are 95% confident that the true Lift from this campaign lies
between 1% and 12%_.

This is terrible.

The range is simply too wide, reported point Lift of 5% is
meaningless. The WeChat campaign’s actual Lift could be 1%, or it
could be 12%! What we have is too much noise, no signal.

That same point Lift of 5% now means, sadly, no raise for Tracy.

There are many reasons for this wide Confidence Interval. (More on
this later.) What’s absolutely clear:

Judy will make poor decisions if she uses 5% Lift, and
any related “actionable insights.”

Enough of these decisions, and Judy will be asked to leave the
company.

We like Judy! Hence, we will ALWAYS report CI when we report Brand
Lift.

The Confidence Interval quantifies uncertainty, informs intelligent
decisions, unpacks the role of Stat Sig (predictability), and, my
favorite, enhances transparency + trust with Sr. Leaders.
Win-Win-Win-Win.

HOW TO COMPUTE THE CONFIDENCE INTERVAL?

Statistics can be complex. Too many bits like “p_pooled” to
internalize.

I want all of you to compute CI, hence I asked my BFF HARRY CASE to
help create a little tool for us. Harry has forgotten more about brand
measurement than I will ever learn. While there are hundreds of
calculators online, Harry helped me create something simple – yet
powerful.

The first step to compute CI, is to collect the survey results.

Let’s randomly say we work at Longchamp [3].

We were trying to move Unaided Awareness (remember, Aided Awareness
metric is to be avoided at all costs).

WeChat BLS asked the question:

_          "When you think of luxury handbags, which brands come
to mind?"_

It asked this question to two groups:

TEST: People who saw Longchamp ads.

CONTROL: A similar group (demo/psycho) who did not see
Longchamp ads.

Simple, no?

Now, we go back to the raw data from our WeChat BLS survey results,
and collect the responses in this handy table.

[Brand Lift Survey Results.]

Yes = The number of people in each group who mentioned Longchamp, in
response to the Unaided Awareness question.

Next, we compute Lift in Unaided Awareness.

[Calculating the Brand Lift.]

4% Lift.

Brand Lift is typically reported as a percent, but without all the
math above visible. Hence, I find that Senior Leaders can be confused
at times if it is 4% of the Baseline or Baseline plus 4%.

In the table, I wanted it to be super clear that this is four points
of brand lift. 24 - 20.

There’s an extra handy dandy reminder for you in English. Sometimes,
I prefer being pedantic. 😊

The next step is for us to choose the Critical Value, a dimension of
our favorite, much abused, mathematical term: Statistical
Significance! [4]

[NOTE FOR ANALYSIS NINJAS: A 95% CI means that if you repeated the
survey 100 times, approximately 95 of those intervals would contain
the true value. It does not mean there’s a 95% probability that the
current interval does.]

Recall, we like Judy, we want her to make brilliant decisions, that is
good for all.

We select 95% Statistical Significance.

[NOTE: If you secretly dislike your Marketing leader, go ahead and
choose 80% Stat Sig. Decisions based on these “insights” will
surely be poor_, bada bing bada boom!_]

You can also select the Critical Value of 90%.

That magically computes the Confidence Interval for you.

Here’s the formula:

=(E5 - F5) + (D15*SQRT(((C7*E5 + D7*F5)/(C7+D7) _ (1 - (C7_E5 +
D7*F5)/(C7+D7))) * ((1/C7) + (1/D7))))

Worry not, as a Premium member you'll get the Excel file below!

The resulting Upper Level is 7.8% and the Lower Level is 0.2%.

The true Lift from this campaign could just as well be 0.2% - a tiny
fragment of a success that is most definitely not going to drive any
business impact. In fact, the complete cost of the campaign (see TMAI
#438 [5]) likely means the company lost money.

As we did earlier, we go back to Judy and say:

_The Lift from this campaign is 4%._

_We are 95% confident that the true Lift from this campaign lies
between 0.2% and 7.8%_.

It would be difficult to make decisions, that'll deliver predictable
future outcomes.

If your point Lift was 4% and the true Lift was 2% - 6%_ish_, Judy
could make future Marketing decisions for Longchamp with more
confidence that the predictable outcomes will be positive for the
business.

Super Duper Important: If the range from Upper to Lower includes
zero, then there is no statistical significance. Say the range was 6%
to -1.5%. It would mean we have no statistical significance, the whole
Upper and Lower is moot. Just ignore the “Lift” WeChat reported.

WHAT’S THE BIGGEST UNLOCK FROM CONFIDENCE INTERVAL?

Targets.

It is the setting of Targets – thus delivering accountability, a fav
hobby of mine.

Let’s randomly say we have a wise CFO named Alexander.

Judy goes to Alexander with an ask for $20 mil in budget for a Brand
campaign. Here’s the conversation:

ALEXANDER: How much incremental Revenue will you deliver, from this
$20 mil?

JUDY: No. No immediate revenue, perhaps in nine months to a year, it
is a Consideration campaign.

ALEXANDER: Ok, let’s make sure there is causal proof from the MMM.
To ensure that happens, what’s the Target for Brand Lift for
Consideration the campaign will deliver?

JUDY: +1 point of Lift in Consideration.

ALEXANDER: Wait. That would mean the Confidence Interval will
definitely include 0, hence the results would not be statistically
significant. There is no way to know if the +1 is real or fake.

JUDY: Oh.

ALEXANDER: Avinash shared that narrow Confidence Interval is usually
±2. If so, to safely avoid the zero, the MINIMUM lift you should aim
to deliver is +3. _Can you deliver +3 Lift in Consideration for $20
mil?_

JUDY: Let me go back to our Agency and redo our media plans to see if
$20 mil meets the MEDIA MINIMUMS across the four channels we planned
to use. We might have to fundamentally rethink the entire thing.

ALEXANDER: Perfect, I won’t approve the budget until I see the
revised plan and predicted impact.

And… Scene.

A campaign that would have been approved based only on point Lift,
suddenly looks extremely shaky when Alexander wisely takes Confidence
Interval into account.

If a won’t even deliver a solid clean narrow CI Brand Lift….
There’s less than zero chance that it will deliver any medium or
long-term Profits.

To ensure this sinks in:

A. A book can be written about what’s a _good _or _bad _CI
range, a much validated rule of thumb is ±2. If you have your norms
for this, please use that.

B. Hence, the minimum Target for any Brand campaign should
be ATLEAST +3, so that in the Very Best Case scenario the CI will be
in the decent range of +1 to +5 – any wider and it is fake news.
Obviously, totally ok to shoot for 6 and 8 and 12 point lifts. Ensure,
you ask for enough money to deliver that!

Set more intelligent Targets for your Brand campaigns. Incentivize
good behavior. Deliver the incremental impact a CFO will love.

Now that you appreciate the crucial role of CI…

[Confidence Interval Ranges.]

HOW TO ENSURE A NARROW CONFIDENCE INTERVAL?

Your sad wide Confidence Interval is first and foremost a Marketing
problem (_it likely sucked_), secondarily it is an Instrumentation
problem (_data collection_).

Here are some ways you can ensure a higher quality signal:

1. DO BETTER BRAND MARKETING.

Let’s say candidate Rishi had spectacularly better ideas than
candidate Keir, and he was able to explain them simply and clearly…
Candidate Rishi will have a narrow CI in poll results – because he
is delivering a better _product_. His impact, and resulting contrast,
will be easier to see in the data.

If you are not using Human Made Machine [6] during your creative
Concept stage and creative Executions stage, chances are high you are
going to put _lamer _creative in Market, its impact, if any, will be
low, the surveys will show a very wide CI (assuming impact was above
zero).

If your campaigns don’t have sufficient Media Weight… You are
peanut buttering your Marketing budget between Facebook, YouTube,
Snapchat, across three different desired Brand Outcomes, with
insufficient frequency to boot… The impact, IF ANY, will have a wide
CI.

Better Marketing = Cleaner (often material) Impact, w/ narrow CI.

This is your best strategy.

2. INCREASE SAMPLE SIZE.

When it comes to optimal instrumentation, this is your biggest lever.

Never accept 175 responses. Shoot for a minimum of 300. If you are
going to segment the data in many ways, double that number.

If you can get 3,000 responses, get them if the campaign is material
– why spend $15 million and decide success based on 200 responses?

Ask for the highest possible survey responses you can get.

Two barriers stand in the way:

*
Channels like Facebook, YouTube, TikTok, WeChat have their entrenched
methods re BLS, they might rigidly stick to their 175 or 87. Push.

*
Cost. More responses cost more money. Sometimes, it is you literally
paying for a higher sample (say in a Brand Tracker scenario).
Sometimes, you saying _hey TikTok, we are freaking Longchamp, we spend
a lot, get us a higher sample rate!_ Be polite, of course.

3. CREATE BETTER SURVEYS.

Focus on improving the survey question design. Improve respondent
targeting.

Ask the channel: _When does the respondent see the survey? After the
first exposure, after the third, something else? At the start of the
campaign, at the end?_ You’ll be surprised. Optimize, it will
deliver narrow CI – assuming #1 above is true.

Simpler, easier to understand questions, targeted optimally, will
deliver a dramatic reduction in data variability by maximizing
consistent responses.

Likewise, use validated survey instruments. There are so many
questionable ones out there.

WHERE CAN I GET THE CI TOOL?

Click here to download it [7]. You’ll get a zip file, unzip, use
Excel.

This link/file is for Premium subscribers for TMAI, please use it as
you see fit.

I request that you not share it with non-Subscribers. Instead,
recommend they sign up as a Premium Subscriber and help us all raise
funds for charity.

BOTTOM LINE.

Brand Marketing is often misunderstood by CEOs, even looked upon with
outright suspicion.
In my experience, that reputation is typically deserved.

The only way you can separate yourself from that reputation is to
enhance the ability of your CMO to understand what’s bad and
what’s good.

Including Confidence Intervals on your Slides, Data Pukes, is a solid
start.

Focusing on narrowing the Confidence Intervals is when the real magic
starts.

_Carpe diem._

Avinash.

Thank you for being a TMAI Premium subscriber - and helping raise
money for charity.

Your Premium subscription covers one person. It's fine to forward
occasionally. Please do not forward or pipe it into Slack for the
whole company. We have group plans, just email me.

[Subscribe [8]]  |  [Web Version [2]]  |  [Unsubscribe [9]]

[10]
[11]
[12]

©2022 ZQ Insights  |  PO Box 10193, San Jose, CA, 95157, United
States of America

Links:
------
[1] https://www.kaushik.net/avinash/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[2] https://tmai.avinashkaushik.com/web-version?ep=1&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=b030fd90-ef4b-11ef-b57e-b59cefacbaae&pt=campaign&t=1740042979&s=d8963ef56c1654000b7bef19eb42179913021d9f0e7c213a013713ae9e83ab03
[3] https://www.longchamp.com/us/en/collection/roseau.html
[4] https://eomail1.com/web-version?p=e38ccd34-e1c5-11ee-86cf-d3265eef585a&pt=campaign&t=1710404155&s=5912a0643c31ca61ab75e58a71ab909b1266834b9cb8359e25b6953bd3e1a1aa
[5] https://eomail1.com/web-version?p=9062e648-bb40-11ef-8226-37e3a250a2f7&pt=campaign&t=1734600882&s=5ca1bc48c5ecea36ed18907080dcad653e9ae4f9254c280a826db97feb08cee2
[6] https://www.humanmademachine.com/products
[7] https://www.kaushik.net/avinash/wp-content/uploads/2025/02/confidence_interval_computation_avinash.zip
[8] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[9] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=296c812a-be87-11ea-a3d0-06b4694bee2a&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=b030fd90-ef4b-11ef-b57e-b59cefacbaae&pt=campaign&pv=4&spa=1740042952&t=1740042979&s=8a13068d0d254ccf017f5c24d387c476091dd8a8a56228eb5e9ca4ec53274512
[10] https://twitter.com/avinash
[11] https://www.linkedin.com/in/akaushik/
[12] https://www.instagram.com/avinashplusworld/?hl=en
