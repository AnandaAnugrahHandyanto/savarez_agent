# I Inherited a Broken App—And Made It Mine

**From:** Every <hello@every.to>
**Date:** 2025-10-02T16:32:17.000Z
**Folder:** every

---

I Inherited a Broken App—And Made It Mine

How rebuilding someone else's vision taught me that ownership is the only moat

Source Code

I Inherited a Broken App—And Made It Mine

How rebuilding someone else's vision taught me that ownership is the only moat

by Yash Poojary

Midjourney/Every illustration.

TLDR: Today we’re releasing an early beta of Sparkle Search, the next step in Sparkle’s evolution from your file organizer to the AI command center for your Mac. The app is designed to keep you in the flow: You can search for your files in natural language, do quick math or unit conversions right from the search bar, and run system actions like quitting distracting apps with a single command. Read on forYash Poojary's account of how he made it—and made it his own.—Kate Lee

Download Sparkle Search

Most founders start with an idea they can’t stop thinking about. I started with someone else’s.

I’m the general manager of Sparkle, the AI file organizer I’ve spent most of 2025 rebuilding. I rewrote the entire codebase, gave it a fresh look, and shipped new features—including a new version we’re announcing today. But the original vision wasn’t mine. Sparkle was conceived by Every CEO Dan Shipper back in 2020, and by the time it reached me, it had already been through four different engineers, passed around like a hot potato because the logic in the app’s original codebase was a tangled mess.

This is very different from the usual founder story: Fall in love with an idea, and then do everything you can to bring it into the world. It’s a story of what happens when you inherit an idea, try to keep it going, and eventually realize the only way forward is to make it your own.

What it’s like to go all in on something that you didn’t start
I came to Sparkle after building a Mac app called NightClub 9, which, in its heyday, ranked in the top 10 on the Mac App Store. It’s an app that displays a live leaderboard of people in your network who are working late, tucked into the menu bar at the top of your Mac.

AI with a complete memory
If you want a great AI assistant, you’ll need to give it context—your emails, documents, tasks, and data. Rube does just that across 500+ apps. It only takes a single conversation to check your calendar, draft responses, update your CRM, and book meetings. Your AI finally works like you do: seeing the full picture, not just fragments.

Try it today

Want to sponsor Every? Click here.

While it is, in some sense, a productivity app, it skews more toward social media. But I’ve always wanted to go deeper on productivity software as a niche. Ask any of my friends how much it genuinely bothers me when I see them stuck in endless scroll loops on their phones; it makes me feel we’re wasting away our potential. Even my side projects were about helping people focus: Agent Watch to let you know when your AI agents have finished running, Terminally Online to tweet from the terminal so you don’t have to open X. I’ve always chased that rare, electric feeling of being fully focused—a looped clip of Jesse Eisenberg hammering out code from The Social Network plays in the background while I work—and I want to help others find it too.

So when the opportunity to lead Sparkle came up, I jumped at it. Sparkle helps you stay productive by quietly taking care of one of the most boring knowledge work tasks—organizing your files—freeing you to focus on what you want. It felt like a chance to channel my passion into something real.

I didn’t invent Sparkle—but I had to make it mine
My first challenge was already laid out for me: Sparkle’s janky codebase that was built in Electron, an open-source framework that made even simple things like adding a paywall painful. I used AI to rebuild it in Swift, Apple’s native language for Mac apps; that also happens to be the language that made me fall in love with coding. A friend and I redesigned Sparkle’s interface over bowls of ramen one night, staying up late and obsessing over every screen until I felt like the app started to, literally, sparkle. I listened to users and pulled from their feedback, adding requested features like catching duplicate files in downloads. And without fully realizing it, I was leaving little pieces of myself in the app—my preferences, sense of design, and taste. For a while, it felt like I was breathing life back into Sparkle. I was completely energized.

Until I wasn’t.

As time went on, I started to feel boxed in by Sparkle’s vision of productivity through file organization. I kept trying to make the app more robust—running Sparkle on a local model (instead of remotely like the app currently works), and more smartly sorting files based on their content—but I kept hitting roadblocks. For example, most consumer Macs don’t have enough compute to run a local model capable of organizing a large number of files. And when it came to sorting—which we only felt comfortable running locally—the models tended to hallucinate more than average, making the results too unpredictable to rely on.

More importantly, I stopped caring. I still believed in helping people reach that elusive flow state, but I could no longer see how organizing their files would get me there.

How I made Sparkle my own
Even as the app crossed 10,000 users and we hit our six-figure revenue goal, I couldn’t shake the sense that I had stalled. I walked around groggy, drained—and, worst of all, afraid that this fog was permanent.

In the meantime, I continued working on the app, and one of the biggest complaints users raised with Sparkle was finding their files once the AI had organized them: They wanted a better way to search for them. As I wrestled with solving this problem, I realized that Mac’s built-in search tool, Spotlight, was ripe for reinvention. I’d built NightClub 9 and other menu bar apps before, all with the goal of helping people focus. But the friction with menu bar apps is that your space is precarious—Apple can deprioritize them, or another app can push yours out. Instead of squeezing productivity into one more icon on the menu bar, I wondered if I could reinvent Spotlight altogether.

Spotlight is supposed to help you find things fast. But instead of surfacing the file or app you need, it often pulls in irrelevant, distracting results. Type “quit” to close your apps, and even the latest version of Spotlight might show you iMessages from nine years ago (like it did for me).

I tried to quit the apps I was running through Spotlight—and saw 9-year-old iMessage threads instead. (Source for all images: Yash Poojary.)

That’s the problem: Instead of narrowing your focus, Spotlight scatters it. You go in looking for one thing and end up scrolling through embarrassing old messages, or getting caught in photos from your high school reunion or a previous vacation, and wondering 15 minutes later what you were even trying to do in the first place.

My hunch is that Spotlight works this way because of how Big Tech measures success. When a product manager looks at the data of me trying to quit my apps through Spotlight, what they see is “increased iMessage usage on Mac.” To Big Tech, that’s a win. To mere mortals like me and you, it’s a distraction.

So I declared war on Spotlight. The new version of Sparkle—Sparkle Search—that launches today goes far beyond file organization. It’s an AI command center for your Mac. You can search intuitively by, for example, typing “new onboarding plan,” and it’ll know you really mean “Q1_new_hire_process_v3.docx” because it understands the text buried deep inside your files (even inside screenshots and PDFs). Sparkle Search also lets you do tasks like empty your trash or quit pesky, distracting apps in a single click. Every inch of Sparkle Search is designed with just one goal in mind: to make you your most productive self.

“Quit all applications,” “Lock screen,” and “Empty trash” are some of the system actions you can take through Sparkle Search, without losing your flow.

Momentum comes from ownership, not speed
I built the first version of Sparkle Search over a single weekend—and in the process, I found the momentum I’d been missing. It was the same flow that I want users to experience when they use the app. And because I was shaping my own idea this time, I could generate ideas, form opinions, and trust my instincts about what felt right or wrong. That shift made a big difference, and suddenly I felt alive again: creative, inspired, motivated.

In the age of AI, it’s never been more thrilling—or unsettling—to be a builder. Thrilling because every morning brings tools that didn’t exist when you went to bed the night before, each one helping you move faster and put your vision into the world. Unsettling because those same tools make it almost too easy to ship.

There’s a weird tension at play: AI lowers the barrier to creation, but in doing so, it also makes it easier to feel detached—to ship features you don’t really care about, or to inherit and work on someone else’s codebase. It’s never been easier to build without ownership.

What I learned through my experience with Sparkle Search is that ownership is where the moat comes from. When what you’re building reflects your taste, your vision, your fingerprints, it generates the energy and momentum that carry you through the hard parts. That fuzzy, hard-to-describe sense of personalness—the feeling that this is mine—is the one thing nobody, not your competition, and certainly not AI, can take away from you.

You can try Sparkle Search or update to the latest version from settings. I’d love to hear what you think—what does productivity on a Mac look like to you? Feel free to email me at yash@every.to or DM me on X.

Thanks to Rhea Purohit for editorial support.

Yash Poojary is the general manager of Sparkle.

To read more essays like this, subscribe to Every, and follow us on X at @every and on LinkedIn.

We build AI tools for readers like you. Write brilliantly with Spiral. Organize files automatically with Sparkle. Deliver yourself from email with Cora. Dictate effortlessly with Monologue.

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

Monologue: Effortless voice dictation for your Mac

You received this email because you signed up for emails from Every. No longer interested in receiving emails from us? Click here to unsubscribe.

221 Canal St 5th floor, New York, NY 10013
