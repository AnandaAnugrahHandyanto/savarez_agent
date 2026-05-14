# 🔮 How Al is breaking and rebuilding the internet economy

**From:** "Azeem Azhar, Exponential View" <exponentialview@substack.com>
**Date:** 2025-10-08T15:22:51.000Z
**Folder:** exponential

---

View this post on the web at https://www.exponentialview.co/p/matthew-prince-ai-internet

I recorded a conversation with Matthew Prince, co-founder & CEO of Cloudflare, a company that sits at the heart of the internet. Few operators have Matthew’s vantage point on how the network is evolving, which makes him uniquely placed to answer: if AI agents read, who gets paid?
Jump to highlights:
(00:46 [ https://substack.com/redirect/fb115faf-3196-44a9-8d8c-aacb1fbb8efe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) The web’s currency is dying
(16:19 [ https://substack.com/redirect/edeff5c3-b5ea-4fcc-b826-c81bc0f5d6a4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) A mathematical model for knowledge – and its implications on the web
(24:35 [ https://substack.com/redirect/ece0a231-cf74-4113-bf36-d2273b21ac6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) What a new business model for the web could be (start here if short on time)
(39:11 [ https://substack.com/redirect/13dd3257-e34f-4253-82f0-0c1f872d9ea2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) How might the agentic web affect content?
Listen on Apple [ https://substack.com/redirect/277d88aa-1f2d-4c20-a469-f2f13423a2b5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] or Listen on Spotify [ https://substack.com/redirect/29076129-e3f0-4590-aebb-482782d4699f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Where to find Matthew:
X: @eastdakota [ https://substack.com/redirect/4141facb-d176-45d2-943e-3f00bcf2b0fd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
LinkedIn: https://www.linkedin.com/in/mprince/ [ https://substack.com/redirect/3b81502b-50a3-4b3d-9512-b7020e3b5d3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Episode notes: Cloudflare, AI distribution, governance, and  key data points
Members can access a briefing pack I used before our conversation — structured notes on Cloudflare’s AI strategy, crawler economics and governance. These notes will help you get more out of the conversation ⬇️
A short history of Cloudflare:
Cloudflare is a global internet infrastructure platform (NYSE: NET, listed 13 Sep 2019) founded by Matthew Prince, Lee Holloway, and Michelle Zatlyn, evolving from 2004’s Project Honey Pot, which tracked spam and abuse, into a service that stops threats while accelerating web performance. From its 2010 beta, customers saw both protection and materially faster load times (driven by caching and removing malicious traffic), establishing Cloudflare’s core value proposition: security and speed with minimal latency- i.e., a control plane at the network edge that improves reliability while reducing cost and complexity for businesses of any size.
Cloudflare and the AI web:
In July Cloudflare launched pay-per-crawl [ https://substack.com/redirect/15d2381f-3deb-455c-b965-1af44fac3753?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] integration to allow publishers to control crawlers’ access to the content.
The problem it aims to solve: The internet is more important than people realise, and it’s deeply flawed and needs to be fixed. The traditional business model of the internet is that, mainly through Google, traffic is generated through search. Traffic is monetized through ads > traffic as a proxy for value.
What is changing with AI: LLMs offer a better user experience for search, therefore people are switching. But that eliminates the need to hunt for information and click through links, which eliminates traffic.
Possible consequences:
Everything that depends on traffic is threatened, including high quality journalism (see Azeem’s discussion with  [ https://substack.com/redirect/dd19248e-dff6-46f6-ba1f-686f6d967d8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]The Atlantic [ https://substack.com/redirect/dd19248e-dff6-46f6-ba1f-686f6d967d8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CEO Nicholas Thompson [ https://substack.com/redirect/dd19248e-dff6-46f6-ba1f-686f6d967d8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
A handful of major AI companies hire and control their own fleet of media, because companies realise that what can set them apart is access to original content (studio model of AIs).
How it works:
Status: Still in private beta
Pay per crawl integrates with existing web infrastructure, leveraging HTTP status codes and established authentication mechanisms to create a framework for paid content access.
Each time an AI crawler requests content, they either present payment intent via request headers for successful access (HTTP response code 200), or receive a 402 Payment Required response with pricing. Cloudflare acts as the Merchant of Record for pay per crawl and also provides the underlying technical infrastructure.
Publishers control pricing:
Publishers will then have three distinct options for a crawler:
Allow: Grant the crawler free access to content.
Charge: Require payment at the configured, domain-wide price.
Block: Deny access entirely, with no option to pay.
While publishers currently can define a flat price across their entire site, they retain the flexibility to bypass charges for specific crawlers as needed. This is particularly helpful if you want to allow a certain crawler through for free, or if you want to negotiate and execute a content partnership outside the pay per crawl feature.
Congress and federal regulators, moving but fragmented:
Bills to mandate AI content disclosures exist but are not yet comprehensive. Examples include the AI Labeling Act and the REAL Political Advertisements Act.
The FCC opened a rulemaking to require on-air disclosures for AI in political ads. This is narrower than blanket web rules but signals federal intent.
One recent federal law tackles a specific harm, non-consensual intimate deepfakes, by creating takedown duties and penalties. Useful precedent, not a general solution. The Verge [ https://substack.com/redirect/acd198d2-50bf-4b00-8603-37746551b974?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
States have acted before Congress. California’s bot disclosure law already requires bots to self-identify in certain contexts. Digital Democracy [ https://substack.com/redirect/d66236ca-0dea-4843-86ba-fe7de68bfe0a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Key data:
HTTP/MCP/Agents:
Cloudflare controls ~20% of global web (based on 45M HTTP requests/s)
Cloudflare live [ https://substack.com/redirect/5e4cde03-d088-422e-9601-fc18da2a2ad4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] -> 71.6% human; 28.4% bot (26th Sept)
Cloudflare mitigated 21.3M DDoS attacks in 2024 (53% increase), averaging 4,870 attacks hourly with peaks of 5.6 Tbps
Damaging [ https://substack.com/redirect/fb8dc6f5-f5d2-4db7-aedc-a4acc0efe5f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] DDoS cost nearly $500,000 per incident
MCP and agents:
AI crawlers account for 80% of all bot traffic [ https://substack.com/redirect/75fb8bde-c356-4b65-83f8-f8169bfedff9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with 18% YoY growth
Training traffic: 79-80% (up from 72%); Search traffic: 17% (down from 26%)
User actions: 3.2% (up from 2%)
Crawl-to-referral imbalance:
Anthropic shows a 38,065:1, OpenAI 1,091:1, and Perplexity 195:1
Agents generate up to 39,000+ requests per minute during peak usage
Reports of AI crawlers returning every 6 hours -> creating DDoS-like loads
Anthropic’s Model Context Protocol launched in November 2024
OpenAI adopted MCP in March 2025; Google DeepMind confirmed support in April 2025; Microsoft created an official C# SDK.
4.3k MCP servers [ https://substack.com/redirect/ca105ea8-aa86-4aba-b472-21856eac8b5e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on github
Cloudflare’s Workers platform hosts managed MCP servers with OAuth integration
Google’s Agent2Agent (A2A) Protocol launched Apr 2025
Google’s AI Overviews appeared on ~13.1% of US desktop queries (Mar 2025); studies (Pew/Ahrefs) show CTR falls when AIO is present.
Cloudflare platform:
Platform supports 80+ tokens per second [ https://substack.com/redirect/76495a57-3b52-4519-9eb2-eca3f31ada6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for 8B parameter models with 300ms time-to-first-token globally
GPU infrastructure spans 180+ cities (doubled in 2024) - 50ms inference for 95% of internet-connected population
Supports 40+ models, with 3M+ active developers
Network across 330+ cities across 120+ countries, reaches 405+ Tbps capacity
AI Labyrinth [ https://substack.com/redirect/32bae30d-0728-4726-abb4-b8b28f41ad42?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (Mar 19, 2025): bot-management amid AI crawler surge - “uses AI-generated content to slow down, confuse, and waste the resources of AI Crawlers”
Thanks for reading / listening. Share with friends.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly93d3cuZXhwb25lbnRpYWx2aWV3LmNvL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOelUyTVRNeU1qVXNJbWxoZENJNk1UYzFPVGt6TmprNU1pd2laWGh3SWpveE56a3hORGN5T1RreUxDSnBjM01pT2lKd2RXSXRNakkxTWlJc0luTjFZaUk2SW1ScGMyRmliR1ZmWlcxaGFXd2lmUS5PSVBBbUJVSXJwZmVtbEVWcXN2UmJCZmNIaW0zMGtpT3ZoaDlZUnp2cERvIiwicCI6MTc1NjEzMjI1LCJzIjoyMjUyLCJmIjpmYWxzZSwidSI6MTI1NTU5OSwiaWF0IjoxNzU5OTM2OTkyLCJleHAiOjIwNzU1MTI5OTIsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.xViVXTzW8J_8rnKxLqTyEm6zBiopAisZRsEHBQTibSM?
