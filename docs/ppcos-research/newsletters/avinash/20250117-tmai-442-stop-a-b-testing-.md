# TMAI #442: 😱 Stop A/B Testing.

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2025-01-17T08:16:22.000Z
**Folder:** avinash

---

[1]

TMAI #442: STOP A/B TESTING.

[ Web Version [2] ]

If your company has an A/B testing program…. End it.

WHAT!

Yes.

Stop.

It is neither helping your company, nor your customers.

WAIT. Really?

Yes.

In 2025, it feels irresponsible, even crazy, to suggest that you
should not experiment. It evokes the scary wild west of making
decisions based on opinions or not being “customer-centric.” After
all, we are taught from birth: “_Listen to the data!_”

Yet… If you can park those scary fears and honestly reflect on
causal business impact... It is a quick realization that this on
paper, absolutely fantastic thing is an entirely wasteful endeavor.

Let me help you take that moment of honest reflection today.

Let’s go on a walk that will improve agility, culture, and profits.

WHAT IS A/B TESTING?

While the term is applied to a host of activities, for the purposes of
today, A/B testing is:

The art and science of comparing two versions of a web page, app
screen, or other digital content, to see which one performs better –
ideally for a specific pre-defined metric.
Most commonly, this type of A/B testing is applied to visual
treatments, like a button placement, color, location of an image (or
an image vs. text), types of content, etc.

While uncommon, this type of A/B testing can be used to test prices,
flows through the site A to D instead of A to B to C to D, etc.

A/B testing of the above type can test multiple things vs. control.
Ex: The default gray button vs. a purple button vs. an orange button.
This is A/B/C testing (or more accurately A/B/n). Today, we'll refer
to it as A/B testing as well.

The term A/B testing is not applied to Geo and Audience
Experimentation. Though you might be testing "A" and "B", as in
_should we buy Paid Search Ads or Not? _Or, _should you spend $10m
more on TV or keep the spend the same?_

[Please read to the end, we revisit Geo testing again.]

Biggest Strategic Technical Flaw.
A/B Testing in 2025 is still based on Last-Click Attribution.

_Come to the site. See one of three different navigation choices
(A/B/C), interact or don’t. Computation decides if A or B or C
worked better. _

Repeat: At the end of each visitor session, the test decides success
or failure.

Yet, we know that an ignorable minority converts in the same session!

A vast majority of the 2% who convert will come back 3 to 17 times
before converting.

The A/B test platform you use rarely is rigged to do “pan session
analysis.” It is rarely rigged up to understand if the 17th one was
a 50% coupon that caused the conversion – it will credit the
navigation element (A or B or C) you clicked (in that session!). It is
rarely rigged to analyze the same “exposed human” as the human
switches browsers, devices, etc. It, of course, has no understanding
and technical incorporation of anything close to “multi-touch
attribution.”

All of this is exponentially worse if parts of the site are
dynamically served or behaviorally targeted (both of which I strongly
encourage).

So… When you are getting single session A/B test “WINNERS”
analysis… How representative is it of “WINNING,” and for whom?

Explains why implementing 45 “WINNERS” of A/B tests does not
result in any improvement in the Overall Conversion Rate for the
business, no?

Biggest Strategic Human Flaw.
Human beings can come up with BIG ideas to test.

Two to three weeks after the A/B testing program goes live, the first
couple tests are out, you will notice that a long laundry list of
_to-do tests_ will be created. On close attention, you will notice
that they are testing a whole lot of little things.

_Let’s test buttons, let’s test everything separately on the home
page, let’s test message x on our 19th highest landing page, let’s
try 18 variations of the phrase “add to cart”, let’s try five
different variations of the coupon box._

There is foundationally flawed belief that company employees,
Agencies, external consultants, can come up with BIG Ideas to test.
Sizable hypotheses that will yield learnings that – win or lose –
will have a big impact on the business.

This assumption is flawed because sure there is a “User Research
team” of one person part-time stuck in a corner, but nearly no one
else understands customer pain points to any degree to come up with
bold ideas/fixes. There’s a small army of “Analysts” to analyze
the data in Adobe Analytics, but their primary role is data puking and
not deep understanding. No one in the digital team is spending time in
the Contact Center listening to Support calls.  Nearly no employees
of the company shop on their own company site, hence oblivious to
pain. Oh, and company cultures are naturally conservative – not
wanting to _rock the boat._

End result: Little ideas to test. With a minute impact each. All
washed out when aggregated (Simpson’s Paradox).
The combination of the above two strategic flaws ensures that if an
A/B testing is actively pursued… Its impact is negligible. It is
simply a time, process, employee, systems suck.

So… Why have do it?

Stop.

I have two EXCELLENT ALTERNATIVES for the time, money, people you are
putting into A/B testing. I’ll come to them at the end of this note.

Before then, let me cover a dozen additional challenges that get in
the way of A/B testing delivering any meaningful value.

A/B TESTING: TECHNICAL CHALLENGES.

A/B TESTING IS TIME-CONSUMING.

A twofold problem.

A modern webpage load calls in 200-500 elements (visible and
invisible). To meaningfully improve one page, you’ll have to run a
staggering number of tests, which can take a lot of time (and money,
and people). Now imagine the numbers required to improve the entire
experience across just one shopping session (lasting between 15 -25
web pages)?

Every test has to reach 95% Statistical Significance [3] If you have a
small traffic site, it can take forever to get a stat sig result. Even
if you have a large traffic site, the tendency to test many small
things means weeks and weeks for just one test.
A/B TESTING NUMEROUS CHANGES IS NEIGH IMPOSSIBLE.

Let’s say you want to change A/B/C/D/F/G/H/n changes. Very quickly
interaction effects end up creating contamination that is difficult to
control, even with super sophisticated technical platforms.

And, in a frustrating reality, the more the number of changes the
longer the test will take to tease out the cause and effect. Which
means you will test less. Which only compounds the problem.

[Switching from A/B to Multi-variate Testing retains the problem above
– and nearly all the problems in this newsletter.]
WRONG MEASURES OF VICTORY!

We change a button/image on the Home Page (a landing page), we measure
the success using Conversion Rate.

Here’s the problem:

The purpose of the button is to get someone to next step/page/screen.
After that, there are 1,800 experiential elements, across 18 - 27
pages between the Home Page and Lead Submitted. Any effect of that
button gets _WASHED OUT_ across that journey that takes your
prospective customer to comparing products, reading details,
reflecting on reviews, watching the videos, assessing the
price/promotion, checking inventory in the local store, payment
options you have, your painful seven-step Start Checkout to Complete
Checkout process, etc.

Who remembers the button on the landing page?

Yet, our A/B tests are measured based on jobs they are not doing…
Jobs they can’t do.
A/B TESTING FOCUSES ON TOO NARROW A SUCCESS.

Early in my career, I flinched at this criticism: _You are only
measuring the quant, you are not measuring the qualitative impact. _

I hated it.

I was measuring the impact on the Conversion Rate. I was improving
Revenue. Why is that so wrong?

Yet, after the above criticism, I also jury-rigged the analytics tools
to measure impact of my tests on Conversion Rate AND Customer
Satisfaction (then my beloved Task Completion Rate) using test/control
cell surveys.

Over the coming quarter, I learned that while improving Conversion
Rate… Our A/B testing program also successfully, consistently,
reducing the Customer Satisfaction. 😞

While making more money (narrow focus), we had made the site worse for
many other use cases of the website (wider focus: tech support,
offline purchase, product comparison, etc.).

In improving the 2% Conversion Rate to 2.1%, I’d negatively impact
the 98% who never convert. Bad.

Now, at the minimum, I focus testing KPIs on Macro and Micro
Conversions. That takes my focus from just the 2% to the 2% AND the
35% that are Micro Converting.

Very few, any, A/B testing programs do this. Hence, even as they
improve the local maxima, they hold the potential to harm the global
maxima.
THE _WORKS TODAY, DEAD TOMORROW_ PROBLEM.

A/B testers take the “winner,” orange button / new page layout /
offer / video, and “winning uplift,” 3%, and extend the results
indefinitely into the future to claim to the CFO: “_This test
delivered incremental review of 3 bazillion dollars_.”

They make the mistake of assuming an unchanging world.

Any “winner” drops back to the norm over some time (usually weeks,
often days). Any “winner” can be influenced by evolving human
perceptions (we all now hate orange, purple is the new orange). Any
“winner” can be influenced by seasonality. Any “winner” can be
influenced by shifting input variables (_no more coupons, a new way to
pay, influencer irrationality, new product launch, competitive
variables_….).

The “winner” is transient. A/B testing’s people, process,
hypothesis creators, execution models entirely ignore this reality. If
they accounted for such a short impact from the improvement… The A/B
testing program might have little to no ROI.

A/B TESTING: HUMAN CHALLENGES.

A/B TESTING REGULARLY MISSES THE FOREST FOR THE TREES.

Because expansive testing is impossible with A/B testing technology,
the humans involved come up with many tests of little things, they
think about experimentation in a silo of the _product box with
pricing, the left side of the cart with payment options, the top hero
image of the home page, etc._

This creates two problems.

A. BAD: It ends up optimizing those little silos. The product box now
has multiple prices or options shown. Good perhaps in isolation,
terrible when you pull back to a non-silo view.

B. TERRIBLE: You lose sight of the fact that your overall digital
experience is heartbreakingly bad / really old / has not holistic
resonance.

Humans involved can’t see that yes, you are winning skirmishes, but
you are losing the war.
A/B TESTING TENDS TO REPLACE GOOD TASTE WITH NUMBERS.

It is a sign that I’m much older, I absolutely hated this criticism
of me when I was younger.

As I’ve come to appreciate the value of brand, brand building,
delivering delight, asking customers for their problems but never what
the solution should be… I’ve come to believe this criticism was
fair.

Just the other day in the UK I remember saying: _No, some things
should never be tested. We should just agree that that looks like
crap, and our brand never stands for crap – even if it delivers 0.1%
improvement in whatever metric!_

Lots of elements can be tested, some, perhaps many, should never be
tested – they are _just do it._ Or better framed, just live our
brand values.

A/B testing often breeds conservatism.

Spiritually, testing should be liberating. _Try super crazy stuff, we
can test it, if it fails we’ll know, and we’ll pull it back._

Ironically, very often, A/B testing breeds conservatism.

Instead of taking a bold risk, people end up fearing that the test
will make them look bad, and they only want to try incremental
changes. This self-fuels a downward spiral.
HUMANS BEING HUMAN.

I’m ignoring the common human issues that afflict A/B testing:

Impatience that results are taking time, in peeking too early and
jumping to conclusions (and activating them!).

Focusing on the pretty options vs. practical ones.

Changing traffic allocations mid-test.

Not understanding the Simpson’s paradox [4].

Going on fishing expeditions to find SOME METRIC that shows your
preferred version did WIN, even if for the pre-identified success KPI
it failed.

Organizational resistance to “disruption”, preventing big ideas,
bold thinking.

The combination of these Technical and Human challenges gives you a
sense of what your A/B testing team is against. They are not negative
people, they are not looking to just make the app a little better.
They come with good intent. The odds are just against them.

It is why I’ve gone from an early convert, one of the first on the
planet to do A/B and MVT testing, to…

A/B TESTING DIES. (SO THAT…) EXPERIMENTATION LIVES!

I am not saying all experimentation needs to die.

You appreciate my extraordinary obsession with incrementality, with
proving causality of Marketing-driven profits to the CFO… A lot of
that is based on super advanced modeling, machine learning etc. YET,
the key to all that is _trust, but verify_. And that is…. Nearly
entirely based on advanced experiments.

Complex cross-channel optimal budget allocation is based on Scenario
Planning Solutions I’ve built – loads of advanced statistics. YET.
It will be 20 – 50 geo experiments that will provide the data to
understand media-minimums and cross-channel privacy-safe diminishing
return curves.

I could keep going on.

If you are spending on 25 people and Agencies and Tools to do A/B
testing of buttons or page designs… You are sacrificing the
experimentation that you desperately need to make BIG decisions. You
can’t see you are spending time removing weeds from a forest that is
nearly all dead.

[IF you are a Global Fortune 100 company with infinite resources, to
be able to do A/B Testing AND Experimentation… Call me. I can still
find 48 better uses for the A/B testing resources – and tie my 48
better uses to causally provable incremental Marketing-driven
Profits.].

AB Testing Dies. (So that…) Behavior Targeting Lives!

When A/B testing, as defined at the top, was “invented,” in the
early 2000s, we could only have one website for everyone. There was
little in terms of data to truly understand all the humans engaging
with us. We had to one size fits all. You can see why it was important
to get that one size right, and why A/B testing became a helpful tool.

But.

It did not take us long to realize, different things work for
different people.

Here are the results for an A/B/C/D/E test to find the winner... It
was for President Barack Obama's first presidential campaign in
2008...

Instead of one winner, there were three!

Way back in 2008, we learned the futility of trying to make one
version of the website.

Why do _one size fits all _in 2025?

Why not: _Let’s deliver a responsive anticipatory experience to you,
and a different one for your kid, and a different one for your
spouse/boyfriend/teacher/mortal frenemy?_

That is now possible, at scale.

For a client, after the third click on the website, no one has the
same experience because the platform changes large portions of the
experience. With every click, now with CloudML, the Site learns,
reacts, delivering customer delight (first) and business profits
(second).

So… Why test 5 buttons to figure out which one is best? Each is
right for someone. Why test 19 pieces of content to pick one that
“works”? Why not deliver each to a segment of visitors for whom it
will work best?

Why is the Testing Team in the business of whittling down ideas to
one?

Why are we not using the 5/10/15 people in the Testing Team to expand
from one idea (button/image/link/design/whatever) to the 150
variations of that idea, and let CloudML deliver it to the 750k
entirely different humans visiting us?

Why… not?

Because, in a world of finite resources, if you have committed 10/15
people, a custom Agency, Engineering and Release cycles to A/B testing
little stuff… It is very hard to leap into the future.

Such an expensive price to pay for something that is adding little to
no value.

Don't.

BOTTOM LINE.

Leap into the future.

Focus on problems that'll deliver radically more customer delight.

Using solutions that actually solve those problems.

With your people who are already incredible.

Stop A/B testing.

Carpe diem.

-Avinash.

Thank you for being a TMAI Premium subscriber - and helping raise
money for charity.

Your Premium subscription covers one person. It's fine to forward
occasionally. Please do not forward or pipe it into Slack for the
whole company. We have group plans, just email me.

[Subscribe [5]]  |  [Web Version [2]]  |  [Unsubscribe [6]]

[7]
[8]
[9]

©2022 ZQ Insights  |  PO Box 10193, San Jose, CA, 95157, United
States of America

Links:
------
[1] https://www.kaushik.net/avinash/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[2] https://tmai.avinashkaushik.com/web-version?ep=1&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=fbb06720-d47e-11ef-a4c7-f766fb61b828&pt=campaign&t=1737101782&s=d4e8cd81ab309f5e3a1a5fd37768999e8cbc6fecb7e5c6465417befcb6855bcb
[3] https://eomail1.com/web-version?p=e38ccd34-e1c5-11ee-86cf-d3265eef585a&pt=campaign&t=1710404155&s=5912a0643c31ca61ab75e58a71ab909b1266834b9cb8359e25b6953bd3e1a1aa
[4] https://en.wikipedia.org/wiki/Simpson%27s_paradox
[5] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[6] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=296c812a-be87-11ea-a3d0-06b4694bee2a&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=fbb06720-d47e-11ef-a4c7-f766fb61b828&pt=campaign&pv=4&spa=1737101754&t=1737101782&s=ee34fc80002f2e7d83f34855e667c2cb9729dcddcd6a53685652d3b6fc4dc61f
[7] https://twitter.com/avinash
[8] https://www.linkedin.com/in/akaushik/
[9] https://www.instagram.com/avinashplusworld/?hl=en
