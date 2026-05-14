# TMAI #409: 🏪 Tracking Offline Impact of Online Marketing – P1

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2024-05-16T08:15:47.000Z
**Folder:** avinash

---

[1]

TMAI #409: TRACKING OFFLINE IMPACT OF ONLINE MARKETING – P1

[ Web Version [2] ]

A peer Premium subscriber, Anna, asked:

_Do you have recommendations for how to measure the conversions of
digital and social efforts, where the purchase can only be made in
brick & mortar storefronts?
_
Thinking of a reply brought to mind this blast from the past, and made
me smile…

The flow chart, chock-full of sweet recommendations, is from my first
(best-selling!) book Web Analytics: An Hour A Day - page 235.

It captured how to track the offline impact of online Marketing
activity, and the online impact of offline Marketing activity.

As I wrote my reply to Anna, it struck me that my answer in 2024 is
only slightly newer than the one in 2007!

AI is curing world hunger (did you see GPT-4o? [3]), still something
as, on paper, simple as multichannel analytics, remains challenging.

SO… WHAT’S THE PROBLEM?

Anna shared that she was already using clicks on store locations on
the website to infer a purchase being made, and connecting those
clicks to average purchases amounts offline to infer economic value.

Excellent start.

Anna’s challenge is not uncommon.

In the United States, even more so globally, nearly all commerce is
offline. That seems hard to believe, given the Alibabas and Amazons of
the world are as gigantic in revenue and influence as they are. But,
true. Think of any non-trivial purchase you’ve made in the past five
years.
Today, I want to focus on Anna’s direct request: Offline impact of
online.

The complexity can be simplified into two difficult challenges:

A. ACCESS TO OFFLINE DATA.

B2C or B2B, conversions will happen in stores or call centers owned by
us the company [1P]. Say, HP. Conversions will happen in stores or
call centers by our partners/vendors/integrators [3P]. Conversions
will happen quickly, in a few days, or after a long sales cycle, over
weeks/months.

Access to just Conversions, or ideally Conversions with some detail of
customer data, is hard to get to even when it is 1P with companies so
disorganized. It can be pull your nails out painful when it comes to
3P – where my strategy often is to pay partners/vendors/integrators
for the data with outright cash or other incentives because I need to
prove the CMO’s value the CFO!

B. MISSING “PRIMARY KEYS.”

Even if I have 1P and 3P Conversions and Customer data, how do I prove
that the offline outcome was because of an online activity? It is not
like I can pass on the UTM Parameters in the human’s bloodstream,
and they can be detected magically when they pull out their credit
card in retail stores.

This is, as I learned in my first MIS class at Ohio State University,
is a problem of missing primary keys – the common existing value
that can connect two sets of data.
Everything multichannel analytics comes down to A and B.

Be very suspicious when someone tells you: Oh, offline impact, sure,
no big deal, our software came directly from Krishna/Jesus, and _we
can definitely prove TikTok is driving 14 sales offline for every 1
sale online!_

As them how they solve challenges A and B.

Their absolute certainty will melt instantly.

That’s a good thing because then you can get down to discussing how
to get to _better than knowing nothing_, o_r we can account for about
30% of what’s happening offline, and we can model from that_. Both,
very good states to be in.

In my reply to Anna, you’ll my trying to solve challenge B. Though A
is a massive challenge, if you are committed and have senior
leadership buy in, you can solve A with money and persistence.

LET’S TRACK OFFLINE IMPACT OF ONLINE MARKETING.

The primary interest in offline impact tracking is usually narrowly
focused on online Paid Media budgets – your ads purchased on
Facebook, Temu, Seznam etc.

Starting with your higher visibility budget is good – especially as
is common when you measure Paid Media’s online incrementality it is
often horrendously low, and your CMO desperately wants to prove there
are indeed 17 more sales she is driving offline for every 1 sale she
is incrementally driving online.

I do encourage you to measure the offline impact of your SEO, Email,
Affiliate, Organic Social, Content Marketing, and all Owned and Earned
Media initiatives. Remember, any accurate incremental analytics
you’ve deployed will frequently show that Owned and Earned Media
drive a majority of your incremental conversions – not Paid Media.

[Note: Nearly everything below applies for B2C and B2B businesses.]

LEVEL 1. TRACK THE ONLINE IMPACT OF ONLINE MARKETING.

I know, I know, I know, this is about offline impact, but hear me out.

If you sell online, I’m assuming you are not only tracking online
Conversions, you are tracking online Incremental Conversions – else
know that you are breaking my heart.

Additionally, or if you don’t sell online, track your
Micro-Conversions.

Anna was tracking clicks on the store locator. That’s a
Micro-Conversion. Track product videos watched. Track downloads
completed. Referrals from your site to 3P retail sites. Support
tickets opened. If you have a very considered offline purchase, track
Recency and Frequency [# of people revisiting in the same week,
Recency, and # of people visiting more than 18 times per week,
Frequency]. Product Page Reshares. New Accounts Opened. Etc. Etc.

Start with Micro-Conversions. You’ll learn simple/smart analytics.
You’ll get your online-to-online tracking set up right (remember
_primary keys?_).

You’ll be able to prove that online Marketing is_ at least _having
an impact online! Or, you’ll realize quickly that if online is not
having an impact online, chances are precipitously low that you are
driving massive offline Conversions! And, how lovely is realizing that
before you expend lots of money and time on expensive _multichannel
analytics_?

[Later, you’ll come back to these online Micro-Conversions, and with
Analysis Ninjas, or our agency (!), you’ll use them as_ leading
indicators for in-flight optimization_ of your Paid Media campaigns
– delivering an ever higher offline impact.]

LEVEL 2. TRACK OFFLINE IMPACT OF ONLINE MARKETING – SIMPLE.

Start tracking methods where the primary key can be clearly inserted
by you.

Activities include:

Buy online, pick up offline. [The order id is the primary key (PK).]

Submitting a lead, conversion offline/call center/later offline. [PK:
lead id.]

Online coupons, promotions, offers, redeemed offline. [PK: promo id.]

Providing a unique phone number online to call for offline. [PK: phone
number.]

In store purchase of items or bundles exclusively available/shown
online. [PK: sku id.]

Accounts opened online, say loyalty membership, store sales. [PK:
customer id.]
Each of this requires some setup in your company platforms, the reward
is well worth it.
Bring Finance in early in to this measurement – you often need their
stick to move the teams you’ll need to set up the above initiatives.

In nearly all of these instances, you’ll have to get out of Google
Analytics. Ex, pull GA data into Big Query, pull conversion data and
primary keys from other offline systems, and analyze performance. This
is a good thing. While you are at it, set your dashboards using Looker
Studio [4], and you’ve now got a helpful new dashboarding platform
that can be used for additional executive reporting needs.

Once you have the sweetness of Level 2 flowing, take a breath. Enjoy
the moment (or a few weeks). It is not going to give you the perfect
and complete picture, but you’ll have initial concrete evidence.
Depending on your business, it could be capturing 20% of the
incremental impact or 60% - either is all concrete, conservative, and
more than what you had at Level 1.

NEXT WEEK.

We will continue our journey: Level 3. Track offline impact of online
Marketing – Complex. And, Level 4: Reality-checking Qualitative
Analysis.

There is so much fun stuff to learn!

BOTTOM LINE.

Challenges A and B sometimes seem insurmountable. But the reality is
that with helpful guidance (this newsletter!) and some elbow grease,
you can go from 0 to 60 relatively painlessly.

Getting your CMO credit that they deserve for offline impact is doing
god's work!

Carpe diem.

Avinash.

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
[2] https://tmai.avinashkaushik.com/web-version?ep=1&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=1d0c27c8-12b1-11ef-888b-e1d6532a64f0&pt=campaign&t=1715847347&s=c568803db1b3411149ddf66744368ba53e39d21a596154b286c05efa55575816
[3] https://www.youtube.com/watch?v=DQacCB9tDaw
[4] https://lookerstudio.google.com/
[5] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[6] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=296c812a-be87-11ea-a3d0-06b4694bee2a&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=1d0c27c8-12b1-11ef-888b-e1d6532a64f0&pt=campaign&pv=4&spa=1715847318&t=1715847347&s=32c1b4a3a3dc8efc46be791fcbf4828d0becc7434735002b6f6e57cc42853a7e
[7] https://twitter.com/avinash
[8] https://www.linkedin.com/in/akaushik/
[9] https://www.instagram.com/avinashplusworld/?hl=en
