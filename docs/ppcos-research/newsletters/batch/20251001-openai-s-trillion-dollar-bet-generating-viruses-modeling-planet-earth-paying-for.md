# OpenAI’s Trillion-Dollar Bet, Generating Viruses, Modeling Planet Earth, Paying for Training Data

**From:** "The Batch @ DeepLearning.AI" <thebatch@deeplearning.ai>
**Date:** 2025-10-01T19:26:08.000Z
**Folder:** batch

---

LandingAI’s Agentic Document Extraction (ADE) turns PDF files into LLM-ready markdown text.

View in browser

The Batch top banner - October 1, 2025

Subscribe    Submit a tip (mailto:thebatch@deeplearning.ai?subject=RE%3A%20Tips%20and%20News)

Dear friends,

LandingAI’s Agentic Document Extraction (ADE) turns PDF files into LLM-ready markdown text. I’m excited about this tool providing a powerful building block for developers to use in applications in financial services, healthcare, logistics, legal, insurance, and many other sectors.

Before LLMs, many documents sat on individuals’ laptops or in businesses’ cloud storage buckets unexamined, because we did not have software that could make sense of them. But now that LLMs can make sense of text, there’s significant value in getting information out of the numerous PDF documents, forms, and slide decks we’ve stored for processing — if we are able to extract the information in them accurately. For example:

- Healthcare: Streamlining patient intake by accurately extracting data from complex medical forms

- Financial services: Accurately extracting data from complex financial statements such as a company’s public filings, which might include financial tables with thousands of cells, for analysis

- Logistics: Extracting data from shipment orders and custom forms to track or expedite shipping

- Legal: Enable automated contract review by accurately extracting key clauses from complex legal documents

Accurate extraction of data is important in many valuable applications. However, achieving accuracy is not easy.

Further, even though LLMs hallucinate, our intuition is still that computers are good at math. Some of the most disconcerting mistakes I’ve seen a computer make have been when a system incorrectly extracted figures from a large table of numbers or complex form and output a confident-sounding but incorrect financial figure. Because our intuition tells us that computers are good at numbers (after all, computers are supposed to be good at computing!), I’ve seen users find silent failures in the form of incorrect numerical outputs particularly hard to catch.

How can we accurately extract information from large PDF files? Humans don’t just glance at a document and reach a conclusion on that basis. Instead, they iteratively examine different parts of the document to pull out information piece by piece. An agentic workflow can do the same.

ADE iteratively decomposes complex documents into smaller sections for careful examination. It uses a new custom model we call the Document Pre-trained Transformer (DPT); more details are in this video  . For example, given a complex document, it might extract a table and then further extract the table structure, identifying rows, columns, merged cells, and so on. This breaks down complex documents into smaller and easier subproblems for processing, resulting in much more accurate results.

Today, a lot of dark data — data that has been collected but is not used — is locked up in documents. ADE, which you can call using just ~3 simple lines of code, accurately extracts this information for analysis or processing by AI. You can learn more about it here  . I hope many developers will think of cool applications to build with this.

Keep building!

Andrew

A MESSAGE FROM RAPIDFIRE.AI

Promo banner for: RapidFire AI Open Source Software

Run 20x more experiments using the same resources, even on a single GPU! RapidFire AI is open source software for efficient model training. Run configs in hyper-parallel with live control and automatic orchestration. Get started: pip install rapidfireai

News

OpenAI On the Road to Trillion-Dollar Spending

A flurry of announcements brought into sharper focus OpenAI’s plans to build what may amount to trillions of dollars of global computing capacity.

What’s new: OpenAI, Oracle, and SoftBank, the primary partners in the massive data-center buildout called Stargate, announced  5 new sites in the United States that entail $400 billion in spending in addition to its prior commitments. In addition, OpenAI introduced  Stargate UK, a partnership with Nvidia and the Norwegian data-center builder Nscale that will build AI infrastructure in England. All told, OpenAI’s current plans will cost $1 trillion, The Wall Street Journal reported  .

How it works: OpenAI forecasts demand for data centers in terms of electricity they will consume. Each 1-gigawatt increment of capacity (roughly enough to light  1 million LED bulbs) costs around $50 billion to build. The company’s current plans amount to 20 gigawatts worldwide, and it predicts demand as high as 100 gigawatts, according to one executive. To satisfy that level of demand would bring the total outlay to $5 trillion (roughly the gross domestic product of Germany).

- OpenAI will build 1.5 gigawatts of new capacity in Ohio (piggybacking on a previous SoftBank project) and Texas over the coming 18 months. This capacity adds to 5.5 gigawatts in New Mexico, a different site in Texas, and an unnamed location in the Midwest. These newly announced facilities complement a 1.2-gigawatt set of eight data centers  in Abilene, Texas, two of which are up and running. Oracle will oversee construction, and Oracle and Softbank will provide financing.
- The UK project calls for multiple sites, starting with Cobalt Park near Newcastle, that will enable OpenAI to supply computing power for finance, national security, and other applications that need to be processed domestically. Nvidia will supply GPUs that may amount to 8,000 early next year and as many as 31,000 afterward.
- Separate from the Stargate announcements, Nvidia pledged  to invest $100 billion in OpenAI, following a recent $40 billion infusion  from SoftBank, Microsoft, and others as well as an earlier  $13 billion from Microsoft. Nvidia provided the first $10 billion at a valuation of $500 billion, raising its stake in OpenAI by roughly 2 percent after an undisclosed investment last year. The outlay is likely to return to Nvidia directly in the form of sales or leases of chips, The Information reported

Behind the news: Stargate, a partnership between OpenAI, Oracle, and SoftBank to build 20 data centers over four years at a cost of $500 billion, began in January. That plan is proceeding ahead of schedule and has expanded considerably.

- With the latest announcements, the initial commitment is more than 80 percent underway.
- Stargate includes further 1-gigawatt initiatives in India   and the United Arab Emirates  , with more countries under consideration.
- OpenAI’s arrangement with Oracle includes a commitment  to pay the latter $30 billion annually for computing services.

Yes, but: Some analysts worry  that giant infrastructure commitments by big AI companies could jeopardize their financial health if demand for AI doesn’t keep pace. “Someone is going to lose a phenomenal amount of money,” OpenAI CEO Sam Altman told   The Verge, adding that winners will gain even more.

Why it matters: Big AI’s capital spending continues   to rise. In addition to Stargate, Alphabet, Amazon, Meta, and Microsoft together plan to spend more than $325 billion this year on data centers, with much more to come. This outsized effort brings with it outsized risks: Companies are betting their balance sheets, investors are putting money on the line, governments are hoping that data centers will supercharge their economies, energy providers are scrambling to provide sufficient electricity, and communities are balancing potential prosperity versus environmental hazard. The optimistic view sees AI’s value rising, costs falling, social benefits spreading, and energy use declining as AI models produce higher-quality output with greater efficiency.

We’re thinking: $5 trillion spent on AI infrastructure is more than 10 times OpenAI’s latest valuation. But the company’s valuation has increased by more than 20 times since it launched ChatGPT in 2022. So far, its bets are paying off.

AI Generates Viral Genomes

Researchers used AI models to create novel viruses from scratch.

What’s new: Samuel King and colleagues at the nonprofit biotech lab Arc Institute, Stanford University, and Memorial Sloan Kettering Cancer Center used model architectures related to transformers, trained on DNA sequences rather than text, to synthesize  viruses that fight a common bacterial infection.

Key insight: The class of models known as genomic language models can produce DNA sequences by generating chains of nucleotides, the building blocks of DNA. Typically such models produce sequences up to the length of a single gene, of which many are required to make a genome. But fine-tuning such models on sequences associated with a family of viruses can enable them to produce longer sequences within that family. At inference, feeding the fine-tuned model the initial part of the genome of a virus from the fine-tuned family can prompt the model to generate an entire novel genome.

How it works: The authors fine-tuned existing genome language models on the genomes of 14,500 viruses in the Microviridae family of bacteriophages, viruses that kill specific bacteria. Using the fine-tuned models, they generated potential viral genomes similar to Microviridae, identified the most promising ones, and synthesized them.

- The authors started with Evo 1  (a 7 billion-parameter StripedHyena architecture pretrained on 2.7 million bacterial and viral genomes) and Evo 2  (a 7 billion-parameter StripedHyena 2 architecture pretrained on 8.8 trillion tokens from viral, bacterial, plant, and animal genomes). The StripedHyena architectures blend transformer-like self-attention layers that encode long-range dependencies with convolution-like  blocks, enabling them to read and generate long DNA sequences efficiently.
- The authors generated 11,000 candidate genomes by prompting the models with the first 11 nucleotides in the genome of the virus ΦX174, a relatively simple member of the Microviridae family that kills the bacterium E. coli C by making it burst.
- They used existing tools for DNA sequence interpretation to filter the candidates, keeping those that were (i) likely to produce novel proteins, (ii) likely to produce proteins that would bind to E. Coli C, (iii) around the same length as ΦX174’s genome, and (iv) made up of the most common nucleotides. This left 302 genomes.
- They successfully synthesized 285 of the 302 generated candidates.

Results: The authors tested a cocktail of 16 synthetic viruses on 3 bacterial strains that are resistant to ΦX174. Initially, the cocktail failed to kill the bacteria within three hours. However, when they moved  the viruses to new cultures of the same bacterial strain to give them opportunities to recombine and mutate, the bacteria succumbed.

- In three side-by-side contests, the synthetic virus called Evo-Φ69 replicated in host cells more than ΦX174 and other synthetic viruses. Six hours after infecting its host, the population of Evo-Φ69 had increased between 16 times and 65 times its initial level, while the population of ΦX174 had increased between 1.3 times and 4.0 times.
- In a test that tracked cloudiness of the liquid bacterial culture, a proxy for the density of the bacterial population, Evo-Φ2483 reduced the culture’s cloudiness to 0.07 optical density in 135 minutes, while ΦX174 achieved 0.22 optical density in 180 minutes.
- Many of the synthetic viruses qualified as new species, meaning their genomes were no more than 95 percent identical to those of the nearest naturally occurring viruses.

Behind the news: Genome engineering typically relies on selective breeding, introducing random mutations, or making specific changes based on known biology, all of which modify existing genomes instead of designing new ones. These approaches struggle to change features like genome lengths and the speed at which bacteriophages kill bacterial cells.

Why it matters: Bacteriophage therapy is a potential alternative to antibiotics. However, bacteria can evolve resistance bacteriophages, just as they develop resistance to antibiotics. In this work, AI generated genomes for viable, diverse, novel synthetic bacteriophages that defeated resistant bacteria. This approach could give doctors a fresh approach to fighting bacterial infections.

We’re thinking: Making new viruses from scratch is cause for both excitement and concern. On one hand, the implications for medicine and other fields are enormous. On the other, although the authors took care to produce viruses that can’t infect humans, malicious actors may not. Research into responding to biological threats is as critical as research that enables us to create such threats.

A woman interacts with a robotic arm on a futuristic desk display in a modern office setting, embracing technology.

Learn More About AI With Data Points!

AI is moving faster than ever. Data Points helps you make sense of it just as fast. Data Points arrives in your inbox twice a week with six brief news stories. This week, we covered Meta unveiling an open world model for code generation research and Anthropic releasing Claude Sonnet 4.5 with major upgrades for coding. Subscribe today  !

Generating Music, Paying Musicians

A Swedish organization that collects royalties on behalf of songwriters and record companies has formed a technology-legal-business ecosystem designed to allow AI developers to use music legally while compensating publishers of recordings and compositions.

What’s new: STIM, which collects royalties on behalf of over 100,000 composers and recording artists, devised a license  for use of musical works to train AI models. Sureel  , a Swedish startup, provides technology that calculates the influence of a given training example on a model’s output. The music-generation startup Songfox   is the first licensee.

How it works: STIM considers its deal with Songfox a pilot project that will shape future licensing arrangements. Members of the organization can license their music if they (i) opt in to allowing AI developers to use it and (ii) distribute it via STIM’s music-by-subscription subsidiary Cora Music  .

- STIM members must register their works with Sureel. Registration forbids AI developers from training models on those works by default. To license registered works, publishers must opt in and developers must agree to the terms.
- The license grants licensees — typically AI companies that seek to train a music generator on licensed works — the right to copy recordings and their underlying compositions for the purpose of training one version of a model. Further licenses are required for further versions. Licensees can distribute generated music via subscription services, but they must obtain separate licenses for television, radio, advertising, or films.
- Sureel uses proprietary technology to determine the influence of a given work on a given generated output. The technology, which must be integrated with a model during training, learns “static attribution vectors” that help determine a percentage of influence on the model’s output of any given training example, according to a patent  .
- When an AI developer uses licensed works, the rights holders will divide a licensing fee based on the number of their works used, the size of the AI developer’s business, and other factors. They will also receive unspecified shares of revenue from the uses of the AI model and the generated music. (The license is new enough that no concrete examples of such payments are available.)

Yes, but: To take advantage of the license, AI developers must integrate Sureel’s attribution technology into their model training process. Consequently, the STIM license is not useful for artists that aim to collect revenue from music-generation companies such as Suno and Udio  , which trained their models without Sureel’s involvement.

Behind the news: Owners of copyrights to creative works have sued  AI companies for training models on their works without permission, but the likely outcomes of such lawsuits are uncertain.

- Sony Music, Universal Music Group, and Warner Music — the world’s three largest music companies — are pursuing a lawsuit  against Suno and Udio, makers of web-based music generators, for alleged copyright violations. Similarly, the German music-rights organization GEMA is suing Suno  .
- Laws in the United States do not address whether or not the training an AI model on a copyrighted work requires the copyright owner’s permission. This leaves the question to be decided by courts or further action by lawmakers.
- Europe’s AI Act provides for artists to make their works unavailable for training AI systems, but music-industry organizations say  this provision doesn’t work, and artists have no redress if their works were used to train AI systems before the AI Act took effect.

Why it matters: It remains to be seen whether allowing AI models to learn from copyrighted works is considered fair use under the laws of many countries. Regardless, the current uncertainly over the interpretation of existing laws opens AI companies to potential liability for claims that they have infringed copyrights. Licensing could help to insulate AI developers from legal risk and incentivize creative people to continue to produce fresh works on which to train next-generation models. The STIM license is an early effort to find a formula that works for both parties.

We’re thinking: As technology has evolved from recording to broadcast to streaming, the avenues for musicians to profit from their work have increased, and we expect AI to continue to expand the options.

Earth Modeled in 10-Meter Squares

Researchers built a model that integrates satellite imagery and other sensor readings across the entire surface of the Earth to reveal patterns of climate, land use, and other features.

What’s new: Christopher F. Brown, Michal R. Kazmierski, Valerie J. Pasquarella, and colleagues at Google built AlphaEarth Foundations  (AEF), a model that produces embeddings that represent every 10-meter-square spot on the globe for each year between 2017 and 2024. The embeddings can be used to track a wide variety of planetary characteristics such as humidity, precipitation, or vegetation and global challenges such as food production, wildfire risk, or reservoir levels. You can download them here  for commercial and noncommercial uses under a CC BY 4.0 license  . Google offers financial grants   to researchers who want to use them.

Key insight: During training, feeding a model one data type limits its performance. On the other hand, feeding it too many types can cause it to learn spurious patterns. A sensible compromise is feeding it the smallest set of input data types that contain most of the relevant information.

How it works: The authors used three data types — optical, radar, and thermal videos taken by satellites— as training inputs, but the loss terms referred to several others  . Given the three types of satellite videos, each of which represented around 1.28 square kilometers, AEF encoded each video using unspecified encoders. It fed the encoded video to a custom module that integrated both self-attention (within and across frames) and convolutional layers. The architecture enabled the model to produce embeddings that represented each 10x10-meter area over the course of a year. To learn to produce good embeddings, the team trained the model using 4 loss terms:

- The first loss term encouraged the model to reconstruct multiple data types: the 3 inputs as well as elevation maps, climate maps, gravity maps, and images labeled with environment types like “wetland.” For each embedding produced by the model, separate vanilla neural networks reconstructed these data types. For example, for each embedding, the system produced a pixel of a thermal video.
- The second loss term encouraged the embeddings to follow the uniform distribution, ensuring that they weren’t all alike. This suited them for clustering and other common approaches.
- The third loss term encouraged the model to produce identical embeddings when given the input with a part missing as it did when given the entire input. This enabled the model to make good embeddings even if some — or all — frames were missing from an optical, radar, or thermal video.
- The fourth loss term encouraged the model to produce similar embeddings to those of text tagged with matching geographic coordinates from Wikipedia and the Global Biodiversity Information Facility  , such as geotagged text about landmarks or animal populations. Conversely, it encouraged the model to produce embeddings unlike those of text corresponding to geographic coordinates that differed (following CLIP  ). To produce text embeddings, the authors used a frozen version of Gemini followed by a vanilla neural network that learned to help match Gemini’s embeddings and AEF’s.
- To adapt AEF for classification or regression, they trained a linear model, given an embedding from AEF, to classify or estimate the labels on a few hundred examples from the test dataset.

Results: The authors compared AEF to 9 alternatives, including manually designed approaches to embedding satellite imagery such as MOSAIKS  and CCDC   as well as learned models like SatCLIP  . Across 11 datasets, AEF outperformed the alternatives by a significant margin.

- Classifying crops in Canada  , AEF achieved around 51 percent accuracy, while the next-best approach, CCDC, achieved around 47 percent accuracy.
- Classifying changes from one type of environment to another  (for example from grass to water), AEF achieved 78.4 percent accuracy, while next-best approach, MOSAIKS, achieved 72 percent accuracy.
- Estimating the amount of water per area transferred from land to atmosphere   over a month, AEF achieved roughly 12 millimeters mean square error, while MOSAIKS achieved roughly 18 millimeters mean square error.

Why it matters: Satellites examine much of Earth’s surface, but their output is fragmentary (due to cloud cover and orbital coverage) and difficult to integrate. Machine learning can pack a vast range of overhead data into a comprehensive set of embeddings that can be used with Google’s own Earth Engine system and other models. By embedding pixels, AEF makes it easier to map environmental phenomena and track changes over time, and the 10x10-meter resolution offers insight into small-scale features of Earth’s surface. The team continues to collect data, revise the model, and publish updated embeddings.

We’re thinking: This project brings AI to the whole world!

Work With Andrew Ng

Join the teams that are bringing AI to the world! Check out job openings at DeepLearning.AI  , AI Fund  , and Landing AI  .

Subscribe and view previous issues here  .

Thoughts, suggestions, feedback? Please send to thebatch@deeplearning.ai (mailto:thebatch@deeplearning.ai?subject=RE:%20Thoughts,%20Suggestions,%20feedback) . Avoid our newsletter ending up in your spam folder by adding our email address to your contacts list.

DeepLearning.AI, 400 Castro St., Suite 600, Mountain View, CA 94041, United States

Unsubscribe
Manage preferences
