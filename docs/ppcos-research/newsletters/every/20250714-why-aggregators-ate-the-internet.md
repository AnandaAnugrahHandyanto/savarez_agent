# Why Aggregators Ate the Internet

**From:** Every <hello@every.to>
**Date:** 2025-07-14T15:09:54.000Z
**Folder:** every

---

Why Aggregators Ate the Internet

The hidden architectural choice that makes big platforms bigger—and how we could change the rules for AI

Thesis

Why Aggregators Ate the Internet

The hidden architectural choice that makes big platforms bigger—and how we could change the rules for AI

by Alex Komoroske

Every illustration/komoroske.com.

In the most recent episode of AI & I, former Stripe and Google executive Alex Koromoske referenced the “same-origin paradigm”—a security decision made by Netscape engineers in the 1990s that has inadvertently shaped our digital landscape. In today’s Thesis, Alex explains how this choice created the conditions for big tech monopolies by forcing our data into silos, making it nearly impossible to move information between apps without friction. The good news: AI has reached an inflection point such that new technologies could finally break this cycle. Imagine a personal research assistant that understands your note-taking system, a financial tracker customized to your budgeting approach, or a task manager that adapts to your changing work style—read on to learn more.—Kate Lee

Was this newsletter forwarded to you? Sign up to get it in your inbox.

There's a bug in the operating system of the internet. It's why your photos are trapped in Apple’s ecosystem, you can’t easily move your data between apps, and every new app starts from scratch, knowing nothing about you. Most importantly, it's why the AI revolution—for all its promise—risks making big tech companies even bigger instead of putting powerful tools in your hands.

The bug is called the same-origin paradigm. It's a historical accident—a quick fix the Netscape browser team implemented one night in the 1990s that somehow became the invisible physics of modern software. Once you understand how it works, you can't unsee it. You start to notice how every frustration with modern technology traces back to this one architectural choice.

I've spent more than a decade as a product manager and strategist at companies like Stripe and Google. I've seen waves of technology promise to change everything—mobile, social, cloud. But there's a pattern: Each wave makes the biggest companies bigger. Every "revolution" reinforces the existing structures instead of empowering us to create new ones. And it all goes back to the same origin paradigm.

Now it's AI's turn.

The good news? For the first time in decades, we might be able to fix it. The tools to transcend the same-origin paradigm are already here.

But first, we need to understand what we're dealing with.

A clean computer that stays clean

Thinkers of all sorts need open space to develop their ideas. But if you’re like us, you probably find that your digital spaces are cluttered more often than not, with Screenshots, PDFs, and downloads. Our AI tool Sparkle cleans your computer so you don’t have to.

Try Sparkle today

Want to sponsor Every? Click here.

The hidden physics of software
Here's how the same-origin paradigm works: Every website, every app, is its own universe. The browser treats amazon.com and google.com as completely separate worlds that can never intersect. It’s the same with the Instagram app and the Uber app on your phone. The isolation is absolute—your data in one origin might as well be on Mars as far as other origins are concerned.

This creates what I call the iron triangle of modern software. It's a constraint that binds the hands of system designers—the architects of operating systems and browsers we all depend on. These designers face an impossible choice. They can build systems that support:

Sensitive data (your emails, photos, documents)

Network access (ability to communicate with servers)

Untrusted code (software from developers you don't know)

But they can only enable two at once—never all three. If untrusted code can both access your sensitive data and communicate over the network, it could steal everything and send it anywhere.

So system designers picked safety through isolation. Each app becomes a fortress—secure but solitary. Want to use a cool new photo organization tool? The browser or operating system forces a stark choice: Either trust it completely with your data (sacrificing the "untrusted" part), or keep your data out of it entirely (sacrificing functionality).

Even when you grant an app or website permission only to look at your photos, you're not really saying, "You can use my photos for this specific purpose." You're saying, "I trust whoever controls this origin, now and forever, to do anything they want with my photos, including sending them anywhere." It's an all-or-nothing proposition.

The aggregation ratchet
This architectural decision creates friction every time data needs to move between apps or websites. But friction in digital systems doesn't just slow things down. It fundamentally reshapes where data accumulates.

Think about water flowing down a mountainside. Every obstacle creates resistance, but that resistance doesn't stop the water—it redirects it. Over time, the water carves channels. Those channels, once formed, attract even more water. What starts as a trickle becomes a stream, then a river.

Data follows the same principle.

Consider how you might plan a trip: You've got flights in your email, hotel confirmations in another app, restaurant recommendations in a Google document, your calendar in yet another tool. Every time you need to connect these pieces you have to manually copy, paste, reformat, repeat. So you grant one service (like Google) access to all of this. Suddenly there's no friction. Everything just works. Later, when it comes time to share your trip details with your fellow travelers, you follow the path of least resistance. It’s simply easier to use the service that already knows your preferences, history, and context.

The service with the most data can provide the most value, which attracts more users, which generates more data. Each click of the ratchet makes it harder for new entrants to compete. The big get bigger not because they're necessarily better, but because the physics of the system tilts the playing field in their favor.

This isn't conspiracy or malice. It's emergent behavior from architectural choices. Water flows downhill. Software with the same origin paradigm aggregates around a few dominant platforms.

Why AI changes everything (and nothing)

Become a paid subscriber to Every to unlock this piece and learn how:

AI enables "infinite software" by making creation nearly free

Current app stores amplify fragmentation rather than solving it

Data policies attached to apps force all-or-nothing privacy choices

Confidential Compute creates the foundation for a paradigm shift

The future is data with self-contained policies, not app-based permissions

Upgrade to paid

Start free trial

What is included in a subscription?
Daily insights from AI pioneers + early access to powerful AI tools

Front-row access to the future of AI

In-depth reviews of new models on release day

Playbooks and guides for putting AI to work

Prompts and use cases for builders

Bundle of AI software

Sparkle: Organize your Mac with AI

Cora: The most human way to do email

Spiral: Repurpose your content endlessly

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
