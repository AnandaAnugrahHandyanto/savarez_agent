# TMAI #399:  🔐 Google Consent Mode V2 Checklist!

**From:** Avinash Kaushik <ak@kaushik.net>
**Date:** 2024-03-01T08:15:50.000Z
**Folder:** avinash

---

[1]

TMAI #399: GOOGLE CONSENT MODE V2 CHECKLIST!

[ Web Version [2] ]

Occasionally, something so essential comes along, that you do need to
stop and make sure it is being addressed thoughtfully, correctly, and
immediately.

Maintaining compliance with data privacy regulations is something you
would rather not mess around with. Google Consent Mode (CoMo) is a
useful tool in this arena.

CoMo offers a streamlined approach to managing user consent for
tracking technologies like cookies and pixels. It's not merely about
adhering to regulations such as GDPR and CCPA, but also about:

Safeguarding your brand reputation

Optimizing marketing strategies

Fortifying against potential data breaches
While initially conceived to address European regulations, CoMo's
relevance extends far beyond geographical boundaries. I see it not
just as a technical solution, I see it as a strategic benefit for
businesses seeking to thrive in a privacy-conscious data era.

At Croud [3], for our internal use, we have built a self assessment
to help our clients check their readiness for Google Consent Mode
(CoMO) V2.

This CoMo _thing _is so important, I asked the team to allow me to
share the whole thing with you! In case you have not yet addressed
this key issue in your company, I hope our internal approach will help
you to move quickly.

If you need help, many Google Partners can help you. You can also
reach out to Croud.

There are several parts to the Croud CoMo approach, let's go step by
step.

GOOGLE CONSENT MODE SCORESHEET.

Score yourself using these six questions.

The optimal answer is identified in bold - though please be honest
with yourself in your assessment!

1. What is the name of the Consent Management Platform (CMP) you are
currently using? (“none” or “don’t know” are valid answers!)

_____________________________________________________

2. How is your CMP currently implemented?

a. Don’t know
B. HARDCODED ON SITE
c. An official Tag Template in GTM
d. A Custom HTML tag in GTMA plugin via a Content Management System
(e.g. WordPress)
e. Other (please describe: _______________________________)
[NOTE: While utilizing any solution gives you a good head start, at
Croud, we prefer OneTrust or Cookiebot.]

3. Do you have a written description of your consent policy, or is it
a well-understood policy within the business?

a. No
B. YES, IT’S WRITTEN IN A DOCUMENT
c. Yes, we all know what it is
4. Have you audited or verified how consent is handled to ensure it
matches your policy?

a. No
b. No, we are not sure how to do this
C. YES AND IT MATCHES
d. Yes, but it doesn’t match
5. Have you already implemented Google Consent Mode?

a. No
b. Yes
C. YES AND IT’S V2
6. If you answered either B or C to question #5, have you verified
that data modelling is active in GA4?

a. No
b. No, we don’t know where to check that
c. Yes, but it’s not active
D. YES AND IT IS ACTIVE
How did you do?

The ideal answers to the questions above are those highlighted in
bold.

Each answer is worth 1 point out of 6 total possible points.

For question number 1, “none” or “don’t know” are worth 0
points.

Any score less than a 6 means you fail–and your organization has
some work to do!

Any non-bold answer is a "not pass," and needs to be addressed.

If you scored a 6, with bolds, congratulations!

To have a lot more fun, or fix bits you don't have done correctly (!),
keep going...

VERIFICATION.

Here are steps you can undertake to ensure that the tags are firing
with or without consent:

1. Open a new Chrome Incognito window, and turn off "Block third-party
cookies."

Your box should look like:

This allows us to test if consent is set correctly when we interact
with the banner.

Here is further guidance from Google on how to manage your tracking
protections and cookie settings.

2. Open Chrome dev tool by pressing F12 on your keyboard or
Ctrl+Shift+I, or navigating the menu with the mouse to select
“Developer tools” - in case you don't have it open in your
browser.

[Developer Tools, Chrome.]

Ensure you can see the Network tab (see screenshot below).

3. Select the ‘Network’ tab in the dev console.

Like so:

4. Navigate to your main landing page.

You will see all the “hits” generated gradually fill up the lower
part of the Network pane.

5. In the ‘Filter’ box on the left-hand side, you can check for
hits sent to GA4 by typing_ C__OLLECT?V=2_. Other platforms, e.g.
TikTok and Facebook can be searched for generally by name.

If you see any hits remaining when the filter is in place, THIS
INDICATES DATA IS BEING SENT TO GOOGLE WITHOUT CONSENT.

If Advanced Google Consent Mode is implemented, this is not cause for
concern.

See “Checking if Google consent Mode is in place" further down in
this document.

Facebook data collection would show up similarly per this example:

CONFIRMING GOOGLE CONSENT MODE IS IN PLACE!

Assuming you have Google Analytics 4 implemented, you can check
whether Google Consent Mode is in place, and working as intended, by
visiting your site and taking note of the data being sent to GA4*

1. Load your website.

Note that whether you choose to grant consent for tracking with your
consent banner will make a difference to the value of the GCD
PARAMETER, which you can test.

2. Grant full consent using the cookie banner on your site.

3. Press F12, in case you don't have the Developer Tools open in your
browser.

Ensure you  can see the Network tab (see screenshot above in step
3).

3. Navigate to any other page on site.

4. In the Network tab, you'll see a box called Filter, type into
it: COLLECT?V=2

5. Click into the network hit at the bottom of the list.

6. Click the ‘Payload’ tab (highlighted in blue here).

7. Check to make sure the new value decodes to the expected result.
Look for the GCD PARAMETER, note its value, and decode it in the
following section.

Typically, when consent is denied, the gcd parameter should reflect
this by either not being present or containing a value that indicates
denial of consent. This could be represented by a specific value
(e.g., "0" or "false") or by the absence of the parameter altogether.

For example, if the gcd parameter is present and set to "0" or
"false," it indicates that consent has been denied. Conversely, if the
gcd parameter is absent or set to a value indicating consent (e.g.,
"1" or "true"), it suggests that consent has been granted.

DECODING THE GCD PARAMETER.

The gcd parameter is formatted as follows:

11 AD_STORAGE 1 ANALYTICS_STORAGE 1 AD_USER_DATA 1 AD_PERSONALIZATION
5

Here's what each means:

ad_storage = Marketing consent

analytics_storage = Analytics consent

ad_user_data = Consent for sending user data related to advertising
to Google

ad_personalization = Consent for personalized advertising i.e.
remarketing
Now that you understand each element, it is time to decode the result
you see above, and identify if all is well or you should be freaking
out. :)

Use this table:

Life is rarely straightforward when it comes to technical analytics
bits and bytes.

Other values than what you see above are possible!

A full breakdown of the meaning of additional letters you might see:

l = Has not been defined
p = denied by default
q = denied by an update
t = granted by default
r = granted by an update
m = denied by an update without a prior default
n = granted by an update without prior default
u = denied by an update after the default value was granted
v = granted by an update after the default value was granted
The format of the GCD PARAMETER is subject to change without notice,
as it is primarily intended for Google’s internal use.

Croud closely monitors for updates, but if you notice anything
unexpected or have any questions, please email my peers at
ANALYTICS@CROUD.COM, they'll be happy to get back to re whatever new
letters/info you see.

You can learn more about Google consent mode HERE [4].

BONUS POINTS.

To be sure of your conclusion:

Clear your cookies.
Re-visit your site.
During this second visit, deny consent in order to see there has been
a change in the value of the gcd parameter.
Check to make sure the new value decodes to the expected result.
Checking both visits is recommended since it will aid determining
whether:

1. CoMo is not implemented
2. CoMo V1 is implemented
3. CoMo V2 is partially implemented
4. CoMo V2 is fully implemented
Or
5. An indication that CoMo is implemented, but is not working as
intended.
Never hurts to be extra cautious in these cases!

BOTTOM LINE.

With all that is going on with data privacy and regulation, it pays to
be super attentive going forward to ensuring compliance.

I've also maintained that this is also important (a lot more
important?) because of the message of respect and empowerment it sends
to your users.

Carpe diem.

-Avinash.

PS: If you would like to have a print friendly PDF for yourself or
your team, please just reply. I'll be happy to share the PDF we use
internally at Croud.

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
[2] https://tmai.avinashkaushik.com/web-version?ep=1&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=1e8f3ade-d5a0-11ee-95eb-6db43eaaab8a&pt=campaign&t=1709280950&s=7c9d21d919826c9ce578439353d344258e1af8e69fb04062495054b5c0cc1652
[3] https://croud.com/en-us/
[4] https://support.google.com/analytics/answer/9976101?hl=en
[5] https://www.kaushik.net/avinash/marketing-analytics-intersect-newsletter/?utm_source=newsletter&utm_medium=email&utm_campaign=tinyletter
[6] https://tmai.avinashkaushik.com/unsubscribe?ep=1&l=296c812a-be87-11ea-a3d0-06b4694bee2a&lc=c5cf2566-cdf6-11ea-a3d0-06b4694bee2a&p=1e8f3ade-d5a0-11ee-95eb-6db43eaaab8a&pt=campaign&pv=4&spa=1709280919&t=1709280950&s=1f99b931cd675055f5300d009c92f0681a3bbdd7dd291a45c4a33c84294674fb
[7] https://twitter.com/avinash
[8] https://www.linkedin.com/in/akaushik/
[9] https://www.instagram.com/avinashplusworld/?hl=en
