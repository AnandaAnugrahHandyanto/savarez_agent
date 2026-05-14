# I Stopped Writing Code. My Productivity Exploded.

**From:** Every <hello@every.to>
**Date:** 2025-06-20T15:05:08.000Z
**Folder:** every

---

I Stopped Writing Code. My Productivity Exploded.

Why giving up manual coding made me more valuable, not less

Source Code

I Stopped Writing Code. My Productivity Exploded.

Why giving up manual coding made me more valuable, not less

by Yash Poojary

Midjourney/Every illustration.

Sparkle is a special product at Every. It’s been owned by four different people and rebuilt four times. But this version is different: Today we’re releasing file de-duplication, a feature built on top of what we know and love Sparkle to be. Tens of thousands of people love Sparkle’s organization features—you're going to love de-dupe, too. It’s the fastest and most accurate way to reclaim space on your computer.—Brandon Gell

Download Sparkle

Six months ago, I wrote almost every line of code myself. Today, I haven't typed a function in weeks—and I recently found 158,000 duplicate files on my desktop without writing a single line of code to do it.

The transformation happened while I was building the latest feature for Sparkle, our AI-powered file manager. Users kept asking: "Can you detect duplicates? I'll pay extra for it." We all have them: that presentation you downloaded three times because you couldn't find it. Screenshots of the same thing from different days. Email attachments you save "just to be safe." I'd been dismissing the requests—Sparkle was for AI-powered file organization, not cleanup—but they kept coming.

In the meantime, I had begun to question my value as a developer. I used to solve coding problems like sudoku puzzles; now I was watching Claude solve them while I just supervised. The brain rot was real, and I was terrified.

The irony was perfect: Here I was, worried about becoming redundant. Why not build a redundancy finder?

Then Reid Hoffman's advice echoed in my head: "Run more agents." So with this project, I decided to lean into it completely: pure AI agents, no fallback coding, no writing functions when things got tough.

Three weeks later, I wasn't thinking about it as outsourcing code anymore. I was building at the speed of thought. In the process, I'd become something different. Traditional developers write code. Agentic developers direct AI to write it for them. They focus on what to build and why, while AI handles the how. That fear of becoming obsolete? I had it backward.

How we built the duplicate finder
I opened Claude Code with a simple question: "If you had 10,000 files, how would you find which ones are duplicates?"

Working in Claude Code. Source: the author.

You might think that you’d find duplicates by comparing file names. But names are meaningless—"Report.pdf" and "Report_final_v2.pdf" could be identical files. What matters is content. Claude took a logical approach: Check the easy stuff first (file size) before the hard stuff (content).

If you compared every file to every other—file 1 against the other 9,999, file 2 against the other 9,998, and so on—that’s nearly 50 million operations. Your computer would crash. But if you group them by size first, most files get eliminated immediately. They have unique sizes, so they can't have duplicates. That narrowed down the amount of potential duplicates to about 100.

From there, it started listing approaches it could take: hash-based detection, command-line tools, specialized software. But I stopped it. "Don't write any code yet. Let's think through this problem together." This instruction helped. Instead of jumping straight to code, we talked through the problem first.

Three stages of file de-duplication
Working in Claude Code’s terminal window—with no fonts or UI and just text—felt weird at first, but that simplicity forced focus. Through 15 minutes of back-and-forth, we refined the approach:

Stage 1: Size grouping
Group all files by exact size. If a 2.3MB file is the only one of that size, it has no duplicates and requires no further checking.

Stage 2: The peek test
For those files sharing sizes, read just the first 16KB. Files that differ in their opening can't be identical. Why read gigabytes when 16KB tells you enough?

Stage 3: Fingerprinting
For the files that passed both filters, we used hashing. Think of hashing like digital fingerprinting. It reads your entire file and generates a unique code. The same file always produces the same code, but if you change even one bit, the fingerprint completely changes.

Using this three-stage approach, we went from 50 million operations down to about 10,000 operations—a 99.98 percent reduction in work. When I ran it on my own desktop, I found those 158,000 duplicate files. It was the best code I’d ever “written.”

Screenshot of Sparkle identifying 158,000 duplicate files on my desktop. Source: the author.

Shifting from doing to directing
I didn't ask any coding questions—not a single, "How do I implement SHA-256 hashing?" or "What's the time complexity of this algorithm?" My focus instead was purely on system design and user experience. Here's what I spent time on, according to my Claude Chat history:

What happens when someone sees "500 duplicates found"? Do they panic?

How do we show which photos are safe to delete?

What happens if someone closes the app mid-scan?

What if they change their mind halfway through?

The fear of brain rot had haunted me for months. And it was justified: I couldn't write a hashing algorithm from scratch like before. When errors popped up, I'd paste them into Claude like a helpless child. The knowledge I'd spent years accumulating was evaporating. But after I made this new Sparkle feature, I realized that I no longer missed it.

Sparkle’s one-click duplicate deletion. Source: the author.

My identity shifted from someone who writes code to someone who ships solutions. The former felt important. The latter actually is.

Memorizing syntax? Gone. Implementing algorithms? Claude's job. Debugging cryptic errors? Paste and wait. What remained was the human stuff: knowing that users hate modal dialogs; understanding that "one-click" is a feature, not laziness; recognizing when three seconds feels like forever.

When users started sharing screenshots of their freed space, with messages like, "Just deleted 12k items and saved 3gb!" I knew that the process I’d undergone to build a one-click feature wasn’t just successful—it was transformative. The agent hadn't replaced me. It revealed what I was actually good at.

Source: Every Discord/Brandon Gell.

I felt the same pride I used to feel from writing elegant code, maybe more. Because I wasn't proud of how it worked—I was proud that it worked. Real people were solving real problems, saving real space on their computers, and the feature felt effortless to use.

I'm still technical. I understand systems, architectures, and trade-offs. I can debug code by directing Claude, design by intention, and ship by iteration. I just can't implement any of it manually anymore. And that's fine. The brain rot I feared was real, but it was also selective. It consumed the parts of my job that were becoming commoditized anyway. What grew in its place was more valuable: the ability to think systematically, direct intelligently, and build what matters.

How to thrive as an agentic developer
Traditional developers write code. Agentic developers direct AI to write it for them. They focus on what to build and why, while AI handles the how.

Coding is now accessible to anyone who can think clearly. Designers who understand systems. Teachers who grasp how people learn. Writers who structure narratives. Your existing expertise translates directly into building software. You don't need years of syntax memorization. You need to understand problems and communicate solutions. But you still need a framework to ship consistently. Here's mine.

Become a problem collector
Richard Feynman kept a dozen favorite problems in his mind, testing new information against them. I do the same:

Why does Sparkle slow down with large folders?

Why are users confused about where files go?

What's eating up their disk space?

This type of thinking keeps the inner sudoku player alive. You're still solving puzzles, just different ones. For instance, when I learn about a new API or see how another app handles onboarding, I think: "Could we integrate the Sparkle folder selection in the onboarding?" The problems become your North Star—they guide what you build next.

Keep the code flowing
Every night, I list a half-dozen tasks with priority rankings. My morning starts with Codex creating branches for each task.

I always have at least two Claude Code terminals open, one for my number-one priority (usually my most complex problem), another for a secondary task. While waiting for generations in one, I switch to the other. I avoid looking at Twitter or YouTube; if I need stimulation, it's Spotify. My brain gets variety without distraction.

You can prompt while making coffee, between meetings, during downtime. One terminal works on the duplicate finder, another updates the UI. It felt strange initially, but now it's natural. You're always moving forward on something.

Think like a director
The best metaphor I've heard came from an Indian director: A director doesn't have to be on set for the show to technically go on. The actors act, cameras roll, the show continues. But without the director, there's no emotion. That's us now: Claude writes code. Codex manages branches. But someone needs to know why it matters. Someone needs to feel the user's frustration with clutter, or joy at recovering 50GB of memory.

Start small, think big
Try building one feature using only AI agents. No fallback coding. Set a constraint: "I'll direct but not implement." Watch what happens. You'll likely build something better than you could alone.

I found 158,000 duplicates on my desktop while implementing this exact approach. How many are hiding on yours? Try Sparkle's duplicate finder for yourself. If you beat my number, send me a screenshot.

Try Sparkle

Yash Poojary is the general manager of Sparkle. Follow him on X and LinkedIn. To read more essays like this, subscribe to Every, and follow us on X at @every and on LinkedIn.

We build AI tools for readers like you. Automate repeat writing with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora.

We also do AI training, adoption, and innovation for companies. Work with us to bring AI into your organization.

Get paid for sharing Every with your friends. Join our referral program.

What did you think of this post?

Amazing

Good

Meh

Bad

Get More Out Of Your Subscription
Try our AI tools for ultimate productivity

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
