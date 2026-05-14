# TMAI #184: 🐯 Data Viz: Give me boxes, give me whiskers!

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2023-12-07T23:40:34.000Z
**Folder:** avinash

---TMAI #184: DATA VIZ: GIVE ME BOXES, GIVE ME WHISKERS!

[ Web Version [3] ]

Stop me if you've heard this one before:

WHAT AVERAGES REVEAL IS SUGGESTIVE, BUT WHAT THEY CONCEAL IS VITAL!:)

Yet, they are everywhere.

You probably sent out a report in the last hour that had averages in
it.

The tendency to use averages is not difficult to understand.

Our data users want as much detailed data and comprehensive analysis
as possible, but they also want it all boiled down to one number (so
that they don't have to think too much). This is how averages are
birthed.

You've read in both my books and on Occam's Razor:

AVERAGES SUCK, DISTRIBUTIONS ROCK.
Vital insights are in the median, the max and mins, the various
quartiles, and outliers. AKA the very large numbers (conversions,
customers, profit groups, etc.) that are getting _averaged down,
_the really small numbers getting _averaged up, _etc., etc.

Mins, maxs, outliers, rarely get illuminated because unstructured
distributions can be a ton of data.

In my analytics practice, box-and-whisker plots are a succinct way to
visualize distributions. They are represented in a digestible format,
while packing in intelligence that understandable for our senior
leaders.

I want you all to draw more box-and-whisker plots, hence here's a
quick trip back to your AP Stats class in high school. :)

Our simple data set, randomly pulled from the interwebs:

Order Values from your ecommerce business:

$19, $26, $25, $37, $32, $28, $22, $23, $29, $34, $39, $31 and $46.
You could represent these order values as an average. But. That would
conceal vital information.

Let's try a box-and-whisker plot... Bada bing bada boom!

[Box & Whiskers plot.]

We now have a wonderfully helpful visual representation of the
distribution of the data.

The box is, :), the box you see above, and the whiskers are the black
lines above and below the box.

The middle 50% of all the data falls inside the box. The whiskers
extend to the smallest and largest values in our data set. This helps
us easily read the distribution of the values.
Box-and-whiskers plots display five insightful elements:

Minimum (19)

First quartile, 1Q (24)

Median (29)

Third quartile, 3Q (35.5)

Maximum (46)
The percentiles are displayed in green above.

You might hear the phrase INTERQUARTILE RANGE, (IQR); it is the
region between the 1st and 3rd quartiles (3Q minus 1Q).

If the IQR is small (as in the Bing example below), the insight is
that the data are mostly close to the median. If the IQR is large,
there is a wider spread in the values (as in the case of Google
below).

With Min, Mix, 1Q, 3Q, and Median, important descriptive statistics,
in a relatively simple visual, our executives have a more
sophisticated understanding of reality.

This results in them asking smarter questions.

Rather than just focus on Average Order Value, they will want to
understand _what's causing the large variation_ (when it exists),
_what's driving the top 25%_ (and how can they get more of that!),
and _what's going on with those outliers_ (when they exist).

These inquiries lead to answers that yield a more sophisticated
understanding of the business performance, and higher profitability
actions.

The box-and-whisker plot also gives us a sense of how tightly grouped
our data is (particularly handy as we compare values across different
dimensions - in our case, for example, if we compared Average Order
Values from Google vs. Bing).

[Google Bing Box and Whiskers Plot]

You can easily imagine how this gives rise to more interesting
questions, which hold the potential to influence smarter actions.

Box-and-whiskers plots are most impactful when comparing multiple
dimensions or multiple data sets - especially when we have access to a
large number of observations.

SPECIAL NOTE:

Occasionally, our data set might contain outliers (due to errors,
unrepeatable events etc.). In those instances, the end of whiskers is
set at 1.5 TIMES THE IQR.

The outliers are still plotted in the visual, just outside the end of
whiskers (blue dots for Bing above).

INSPIRATION.

There are numerous use cases for box-and-whisker plots.

Here's an example via Tableau that, I thought, is a great use case.

The image might be challenging to read on your mobile device. When you
are on a desktop, right-click, choose open image in a new tab.

[NBA Salaries.]

Use box-and-whisker plots to quickly visualize the distribution of
values in a dataset.

When you have side by side plots, two or more, the visualization of
differences can be insightful as you compare the spread of values.

The tiny circles that represent outliers contain unique insights all
your own (which and become hidden in some types of visualization
techniques).

NOTE.

If you are a Premium member, you'll notice that I'm fond of nudging
you to do the unusual. It helps stretch your knowledge, and in our
context, often helps you get to genius_er _business ideas.

Do, please go back and re-read these editions:

* Top-level Business Metrics: Earned Growth Ratio! [Five
transformative metrics!]

* The Baklava of Brand Measurement. [You are not doing brand analytics
right!]

* Trick Question: Accuracy or Precision? [Do you know the answer?
:)]

* CPIS | A Revolutionary Efficiency Metric. [A fav KPI of mine.]
If you can't locate them, just email me.

BOTTOM LINE.

I hope you are as excited about the value of box-and-whiskers plots as
I am.

Now, when you feel the urge to crank out yet another histogram or bar
chart (boring!), try the box plot and get a sense for how much better
it might be in delivering insights.

If you end up loving it, say a quick thanks to the inventor, John
Tukey [4].

-Avinash.

PS: Now that you understand box plots, perhaps you'll also understand
why I find this cartoon of dynamite plots hilarious....

[Error bars.]

Mathematical explanation of the joke:

The height of each bar indicates the mean, and the vertical link on
top of it represents the standard deviation.

Links:
------
[1] https://www.kaushik.net/avinash/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[2] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[3] https://tmai.avinashkaushik.com/web-version?ep=1&lc=4a91e1b8-9559-11ee-97fc-cfe3bd45ec58&p=5e5247f6-9559-11ee-adee-bb9a155628d7&pt=campaign&t=1701992434&s=fd526e513e855fd6b6d09184ea0cd6871ba265b3e989daad667ed91ae591c1fd
[4] https://en.wikipedia.org/wiki/John_Tukey
[5] https://twitter.com/avinash
[6] https://www.linkedin.com/in/akaushik/
[7] https://www.instagram.com/avinashplusworld/?hl=en
[8] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=84f286a6-be5a-11ea-a3d0-06b4694bee2a&lc=4a91e1b8-9559-11ee-97fc-cfe3bd45ec58&p=5e5247f6-9559-11ee-adee-bb9a155628d7&pt=campaign&pv=4&spa=1701992428&t=1701992434&s=a5bcf96dcdbcb25c60187294b491f16e3f265048f421ea45a9068ddf866d369a
