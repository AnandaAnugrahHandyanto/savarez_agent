# TMAI #494: 🔭 Bye Human-Powered Analytics. -P3: LTV, RTP, ILM.

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2026-01-29T09:16:38.000Z
**Folder:** avinash

---

[The Marketing  Analytics Intersect, by Avinash Kaushik] [1]

TMAI #494: BYE HUMAN-POWERED ANALYTICS. -P3

[ Web Version [2] ]

AI emphatically has a jagged edge [3]. For now.

[AI's jagged edges.]

It is OK to argue that the star above in Thomas Pueyo’s graphic
should be one step to the left.

Do recognize that in context of Digital/web/all analytics, the red
today covers a significant percentage of an Analyst's work today and
the blue part of the circle is shrinking fast.

Most critically: Advanced Algorithms and AI can already do what we
have always been poor at as Analysts (and Marketers). AND. They/It can
do things we have never been able to do.

This is a little scary (next edition of TMAI), immensely exciting, and
inevitable.

Hence, my clear-eyed recommendation to turn human-powered analysis to
AI.

In Part 1, TMAI #492 [4], I’d outlined a deeper assessment of this
moment and why now is the right time. I’d also shared these three
profit and joy increasing areas of focus: 1. Predictive Analytics via
propensity modeling. 2. Advanced Customer
Segmentation. 3. Voice-of-customer Integration with Behavioral
Analytics.

In Part 2, TMAI #493 [5], I’d built on that foundation to share
three more _revolution level impact_ ideas, with the first one setting
a new standard for digital experiences: 4. Behavior Targeting &
Intelligence (BTI).  5. Natural Language Processing (NLP) for
Unstructured Data. 6. Anomaly Detection and Automated Insight
Generation.

Here’s AI’s interpretive infographic of TMAI 493:

[AI-Powered Analytics & Automation.]

Let's continue to leverage AI to overcome _HUMAN COGNITIVE CONSTRAINTS
_(we can only track a finite number correlations simultaneously),
_INSIGHTS LATENCY_ (the delay getting to insights), and _PATTERN
RECOGNITION LIMITS _(we can't identify subtle and multidimensional
relationships).

7. PREDICTIVE (WHOLE COMPANY) CUSTOMER LIFETIME VALUE MODELING.

IMPACT POTENTIAL: Transformational.

[NOTE: I am anti “Marketing LTV” measurement. It is a mistake of
enormous proportions. Reasoning: _LTV is Not Marketing’s Friend:
TMAI __370_ [6]_ & __371_ [7]. I am FOR measuring LTV at a company
level, incorporating ALL Factors that influence LTV, of which the
initial “Marketing targeting” is often the least causal.]

Most companies calculate LTV retrospectively, identifying high-value
customers only after they've already demonstrated value. Additionally,
they do not include all factors that go into influencing a high LTV
– market dynamics, product quality, development cycle speed,
innovation, customer service, geographic presence, embrace of AI, etc.
etc. The end result is 1. the lack of forward-looking indicators of
what drives higher LTV, 2. which new users will become more valuable,
and 3. missed early retention opportunities.

LTV prediction represents a classic machine learning regression
problem with time-series components. Advanced algorithms can identify
early behavioral signatures that predict long-term value, often within
the first few interactions. These models can incorporate hundreds of
features including product engagement patterns, number and titles of
users, content preferences (site, conferences, in-person 1:1, store
visits), depth of product activation, customer support interactions,
and even micro-behaviors that human analysts would never consider
predictive.

AI APPROACHES AND ALGORITHMS to explore, stress test, and embrace:

*
GRADIENT BOOSTED SURVIVAL MODELS (XGBOOST). Sometimes saving the right
customer is exponentially more productive than acquiring a new one.
These models shine at classification (_will this customer churn?
when?_) and regression (_how much will they spend if x or z or y_?) by
building ensemble decision trees that correct each other’s errors.

[BONUS: I have used these models to predict if and when a company
employee might quit. Saves you immense trouble if you want employee x
to quit, and intervene early if you don’t want employee y to quit.]

*
LONG SHORT-TERM MEMORY (LSTM) NETWORKS. A type of a recurrent neural
network (RNN) capable of learning order dependence in sequence
prediction problems. They can output predicted future value, next
purchase timing, and churn risk. They basically turn behavior history,
identifying early signals humans miss, into a forward-looking value
engine.

*
PARETO/NBD MODELS WITH BAYESIAN UPDATES. Our classical probabilistic
models  now enhanced with machine learning for better early
prediction. They are built for sparse, irregular purchase data (a
common situation for many of us). Output baseline LTV forecasting and
retention timing.

*
UPLIFT MODELING. Identify which users will increase LTV in response to
specific actions. When it works well, I really appreciate the ability
to separate persuasion from coincidence – then I get smarter re
identifying who benefits from intervention (offers, pricing changes,
service upgrades, etc.).

[NOTE: User Pareto/NBD to estimate future value and churn windows. Use
uplift models to test which actions increase value. Combine the two to
maximize incremental LTV, not just predictive LTV! Speaking of
combining....]

*
ENSEMBLE APPROACHES. LTV is noisy, _multi-causal_, and changes over
time. One model never sees everything. Ensemble approaches result in
stable forecasts with sensitivity to behavior shifts, early signals
plus explainability, and can be retrained continuously, not
quarterly.

PRACTICAL EXAMPLE.

An early example for me was assessing behavior, reports, feature usage
in Google Analytics, to understand value delivered to mothership via
Ad Spend. Then, build even more of those helpful features in GA. A
more recent narrow example is for a SaaS company: LTV scoring for all
trial users within 72 hours. The model analyzed 140 behavioral
features to identify…

*
API access within the first day was a causal indicator of clients who
will have 4.2x higher predicted 12‑month value.

*
68% lower predicted churn by those who watched specific onboarding
videos (not just _any_ video). I am normally so suspicious of such
analysis!

*
Immense contradiction A: Creation of a support ticket in the first
week predicted higher value. [An indicator of active use during trial,
and the fabulousness of the company’s customer service (human!)
agents.]

*
Immense contradiction B: Users who “explored” many product
features have lower conversion from trial to fully-paying customer,
vs. those who dived deep into just a few features.

See how profound the impact of _whole-company_ LTV modeling can be?
Mind. Blowing.

[Premium Subscribers: You MUST deploy VBB, it is powered by LTV
predictions: TMAI #432: Value Based Bidding [8].]

POTENTIAL OUTCOMES FOR YOU.

Everything above.  Additional potential outcomes include:

*
25-40% improvement in customer acquisition efficiency.

*
10-30% improvement in retention rate from early intervention and
dynamic resource allocation (ex: premium support for clients with
high-predicted-value).

*
Not easily quantified qualitative impact on product development
insights.

I’m sure you, your agency, have done LTV analysis. I’m also sure
you drove some positive outcomes. Embracing intelligent algorithms and
automation unlocks a new universe.

8. REAL-TIME PRICING AND OFFER OPTIMIZATION.

IMPACT POTENTIAL: High.

I suspect most of you are uninvolved with offers and pricing. I work
for a CFO, so I could not resist tempting you about this super
high-impact work.

The most common approach to pricing is rules-based. Ex: Seasonal
adjustments. Matching competitors. New product launch. Geo. As we have
already seen human interpreted rules can be limiting. Other factors
that can influence pricing decisions include competitive context,
inventory levels, business objectives, willingness-to-pay. All of
them, simultaneously! The inability to interpret this complexity
results in lost conversions, lower profitability, and erosion
competitive advantage.

Dynamic pricing algorithms can process dozens of variables in
real-time: user behavior, competitor prices, inventory levels, demand
forecasts, business objectives (maximize revenue vs. market share),
and individual price elasticity. Reinforcement learning approaches can
test pricing strategies and learn optimal approaches without
jeopardizing significant revenue through manual experiments.

AI APPROACHES AND ALGORITHMS to explore, stress test, and embrace:

*
BAYESIAN INFERENCE. Amazing at modeling uncertainty, as it outputs
distributions and not point estimates. If we change the price of your
mobile phone from $449 to $499, how confident are we that the drop in
conversions will be offset by gain in margin? The challenge is they
require choosing priors and likelihoods. Bayesian inference is awesome
at safe learning under uncertainty. If your goal is long-term,
multi-step value optimization, see Reinforcement Learning below.

*
GAME THEORY MODELS. Among many use cases, use them to predict
competitor, marketplace, reactions. If you drop your price, will
Amazon match it? The AI simulates these moves to find the (famous!)
“Nash Equilibrium” – the optimal price point where you maximize
profit, given the likely moves by your competitors. The challenge is
accumulating rich enough competitive signals (and remembering that
humans, at competitors, can be irrational!).

*
REINFORCEMENT LEARNING. We’ve already applied this five times. In
this instance, the agent _plays the game_ of pricing. Action = Price
Change. Reward = Total Profit (not just revenue!). It learns to lower
prices to clear out stale inventory, and raise prices when demand
signals (from dozens) indicate. Another use case is to optimize
product bundles for a reward function you identify. A critical
differentiator of reinforcement learning: Optimize reward over many
future steps, not just one sale!

*
MULTI-OBJECTIVE OPTIMIZATION: Critical when pricing and offers must
balance revenue, margin, conversion rate, and customer satisfaction
simultaneously. These factors can often be in conflict. You can set
guardrails instead of fixed rules, and let the AI choose within
acceptable ranges as it does optimal balancing.

PRACTICAL EXAMPLE.

A large, but not Fortune 100, company example. The AI-powered dynamic
pricing model incorporated: Client variables (past purchase history,
price sensitivity, length), contextual factors (original acquisition
details), local market factors (regional competitor prices, demand
forecasts, seasonality), and company factors (current quarter and
fiscal year performance, inventory (products, location, sku
variations, factory manufacturing status, promotional calendar).

For each client, the system would propose optimal price and additional
contract variables, across 45 pricing dimensions. It also powered
continuous testing of new price points (lower, higher, same) with
small percentage of users. Finally, created a custom package of
recommendations based on _willingness-to-pay_. The key was not doing
this once, for one client, based on point-of-time analysis. It was the
learning from one, identification of patterns across all, then
applying across individuals – rinse and repeat constantly. [Note:
Similar to BTI, my recommendation #4.]

*
14% revenue lift in the first six months through optimized pricing –
with no increase in acquisition cost.

*
22% savings in inventory costs from dynamic pricing to move excess
capacity and maximizing scarce inventory.

*
A significant shift in market share from Year 2 to Year 3, from
improved competitive positioning (responsive pricing at work).

POTENTIAL OUTCOMES FOR YOU.

Go back and read immediately above. Additional outcomes from industry
data:

*
Fashion/ecom brand: Revenue +30%, Ordered Items +17%, Gross Margin
+6%.

*
Airline: Revenue +15% Per Flight, improved fill rates.

*
Retailer: Revenue +20-25%, pricing accuracy jump from ~70% to ~95%.

*
Not easily quantified qualitative impact on the ability to personalize
the value delivered to each client.

I’m sure you, your agency, have struggled to improve conversion from
Google Pmax by 2% or pulled your hair out trying to nudge Meta ASC’s
stubborn ROAS of 1.63. Imagine the glorious results if that wasted
energy went into just one of four AI pricing and offers
possibilities.

I’ll close this series with the narrowest solution I could think of,
one with a super cool name.

9. INTELLIGENT “LIQUID” MERCHANDISING.

IMPACT POTENTIAL: Medium.

You have a PLP right? Product Listing Page. For a company selling
4,000 products in innumerable combinations, colors, options… humans
deciding which products go into the Hero slot or the top row, is
closer to a crap shoot than you realize. How clever can manual
merchandising of “Coats” category you sell be, when you have
50,000 different visitors… Simultaneously! Current approaches stifle
new inventory discovery, and, of course, because no BTI, ignore the
visual and functional preferences of the visitor.

The AI solutions available now turn a static, or slightly more smart
human rules-based, product grid into a _liquid_ interface. It re-ranks
the entire product catalog in milliseconds for every specific PLP
(/category) page load. Or, every time a PLP loads as a result of a
search query (from your internal search engine or Google or an LLM).
Additionally, the algorithm balances “Exploitation” (showing
what’s likely to sell) with “Exploration” (testing new products
to see if they can become _best sellers_). Continuously.

AI APPROACHES AND ALGORITHMS to explore, stress test, and embrace:

*
LEARNING TO RANK (LTR). Unlike standard regression, LTR is a
supervised ML approach that trains on lists of items to maximize a
target metric. It takes features of the user (source, past history,
previous page views, offline interactions, price sensitivity, intent
signals), the query (keywords, category interest), and the _document_
(product margin, stock level, conversion rate) to output an optimal
ordering.

[BONUS: Over heavy promotional periods, ex back to school, LTR can
also help rank discounted items to maximize margin-weighted revenue!]

*
VECTOR EMBEDDINGS. AI converts product images and descriptions into
mathematical vectors (numbers in multi-dimensional space!). It then
finds products that are _mathematically close_ to what the user is
looking for, even if the keywords, tags, don’t match. Ex: If the
user pauses on a photo of a beige trench coat, the AI immediately
ranks other beige trench coats higher, even if they are labeled
“Camel Overcoat.” It is so good at producing personalized grids
for a users’ inferred intent and surfacing potential high-performing
new products similar to top performers.

Additional approaches for_ liquid merchandising _we've already
covered include LSTM (/Transformer for Behavior), Multi-objective
Optimization, and Bayesian Bandits.

PRACTICAL EXAMPLE.

From a D2C furniture brand, which used real-time AI across home page
and PLP pages to improve product visibility and re-rank:

*
Home page entrants conversions: +22%

*
Bounce rate for entrants to PLP pages: -35%

*
AOV improvement over six months for PLP pages: +18%

POTENTIAL OUTCOMES FOR YOU.

Looking at my work dataset, published industry data, potential
outcomes include:

*
10-25% improvement in sales of products buried beyond _page _2. AKA
Long tail activation. Associated increase in LTV due to matching user
intent.

*
5-15% increase in Revenue Per Session (RPS) from the removal of
friction of finding the right product.

*
-10% to -30% reduction in internal search abandonment.

*
Meaningful drop in Return Rates from better match between what the
customer intended to buy and what they ended up buying.

Incredible power of behavior-driven ranking, dynamic learning to
capture trends early, and continuous learning from real user intent.

The nine specific applications of AI in this series are just a start.
There are so many more possibilities.

Ex: Checkout Rescue & Payment Intelligence is a great focus because
payment outcomes are probabilistic, heterogeneous, and
context-dependent (issuer, BIN, country, device, amount, history). AI
can learn subtle interactions that humans cannot reliably reason about
at scale.

Please keep exploring new areas, and ones more relevant to your
business & strategy.

BOTTOM LINE.

You increasingly do not need to be a data scientist*. You do not need
to code your own Neural Networks from scratch. You increasingly do not
even need to understand how these tools work.

In front of you is the opportunity to use data at a level of
intelligence, scale, automation that has never been possible in human
history.

The sexy part is not the AI bits. It is centering every business
execution on a deep understanding of an individual client, and
exchanging their delight for strong market success for our
businesses.

Carpe diem.

-Avinash.

* Though you will be using the work done in the near past by brilliant
data scientists!

PS: Next week... Does the human Analyst role exist by Dec 2027? If it
does, what's the job?

Thank you for being a TMAI Premium subscriber - and helping raise
money for charity.

Your Premium subscription covers one person. It's fine to forward
occasionally. Please do not forward or pipe it into Slack for the
whole company. We have group plans, just email me.

[Subscribe [9]]  | [Web Version [2]]  | [Unsubscribe [10]]

[11]
[12]
[13]

©2022 ZQ Insights  |  PO Box 10193, San Jose, CA 95157, USA
Links:
------
[1] https://www.kaushik.net/avinash/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[2] https://tmai.avinashkaushik.com/web-version?ep=1&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=2f41847e-fa4a-11f0-8132-0fd58e56c043&pt=campaign&t=1769678198&s=30b5063b4101876f95971f1debf6814381eac1ecf526ce4667d89875569b95d3
[3] https://www.linkedin.com/feed/update/urn:li:activity:7414319468803330048/
[4] https://eomail1.com/web-version?p=4a624a4e-f1d1-11f0-b5b5-bdd09979ce25&pt=campaign&t=1768469691&s=9cedd55a0f908ba3d12d2f8c6ecb984ba45604bd86987c86e8414efeac59fcf7
[5] https://eomail1.com/web-version?p=15b1da7e-f732-11f0-ab6f-0113f979ed61&pt=campaign&t=1769073407&s=722278f7d9bb110563b83eab09c55ceaf111ac306bf0e8315640a5dd98e2a85f
[6] https://tmai.avinashkaushik.com/web-version?ep=1&lc=95a31863-c722-11ea-a3d0-06b4694bee2a&p=6914ebca-2b29-11ee-ab4f-e742e8e916c6&pt=campaign&t=1690445748&s=e71ca8b8ecd43a8418b1a5b87576f1ef3f580a90b46cb90c54744cf73a33266f
[7] https://tmai.avinashkaushik.com/web-version?ep=1&lc=95a31863-c722-11ea-a3d0-06b4694bee2a&p=efcc1bbc-3140-11ee-aee1-c92e0f92170e&pt=campaign&t=1691133340&s=a2a28502937ea0a07702a5d1bc55bd221c97184e999e223834fe0e3d511ff767
[8] https://eomail1.com/web-version?p=f8291af2-9702-11ef-9f36-87071c490450&pt=campaign&t=1730362597&s=23e64f3d061909abbbf17c61256846f958124016c55eb86cbeb552f1fe43bb2f
[9] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[10] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=296c812a-be87-11ea-a3d0-06b4694bee2a&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=2f41847e-fa4a-11f0-8132-0fd58e56c043&pt=campaign&pv=4&spa=1769678169&t=1769678198&s=e67c1fac488433c03ac3e6c49e2ae3c5447173d0319accaed0d79028df462b52
[11] https://twitter.com/avinash
[12] https://www.linkedin.com/in/akaushik/
[13] https://www.instagram.com/avinashplusworld/?hl=en