# How AI Search works

- **Source:** PPC Mastery (hub.ppcmastery.com)
- **Course:** SEO/GEO Mastery
- **Section:** GEO Fundamentals (AI Search)
- **Duration:** 16:42
- **Transcribed:** 2026-03-21

## Transcript

so welcome to the lesson how ai search works in this lesson we will learn three key things the
first one is how ai search works in general so a general understanding of the mechanisms and the
processes that happen behind the scenes when you ask something in chat gpt or in perplexity or
other tools obviously then how ai search works in google because there is interesting data that we
can look at how it's handled in google a little bit differently and then what query fan out means
and why it's important to understand for your ai search strategies so let's dive right in and i
have brought some really cool infographics here from ml6 i've also linked to them here on the
slides i couldn't have done them better as they did them so this is why i'm referring to to them
so
so basically how ai search works is um very well explainable with the iceberg
analogy so if you think about the tip of the iceberg this is basically the web user interface
you will be able to access on chat gpt on copilot or on perplexity and the web user interface is
obviously the point where you will a ask the question and b also get the answer so this is
basically your
the main thing you see so your main point of contact but then if you ask a question to chat
gpt for example there are multiple processes happening in the background so there's a control
layer that's happening we'll look into that in a second and then there's obviously also
the llm that is working to perform a search for you and to basically surface the information
that you have requested with your question and if we look at the first layer here a little bit
more in more detail it's the control layer and the control layer has basically an input dimension
and an output dimension and the most important aspect of this control layer are the guard rails
so every llm provider and also chatbot provider has basically put some guard rails in place and so
these guard rails are oftentimes just safety features so what do you want an ai chatbot to be
able to respond to and what do you want so this is basically a question filter and what do you want
an ai chatbot to be able to answer and there could be potentially harmful context in there
so imagine people obviously not you but imagine someone asking for a checklist on how to build an
inclusive device this could be something that people actually ask an ai because also people
that do not have good in mind have access to like the phd in your pocket as sam altman
called chatgpt but this is something that the providers obviously do not want to support so
they want to be sure that the question you're answering the question you are asking and the
answer you're getting
is is not harmful is harmless and is in place with the policy they have agreed on
then also for the input control we have web knowledge access so there is basically a control
layer where the provider ensures that they have the necessary infrastructure in place
to retrieve knowledge from the web so fresh knowledge for example from a search engine
that is active in the background so it's not that we are using the search engine directly as with
google but we are rather asking an llm or asking an ai chatbot to use a search engine in the
background for us and then you have obviously the llm the lms basically um the the the processing
layer here so it processes the input control it processes the information that was retrieved from
the web knowledge and then it
basically creates a thin synthesized answer so a compiled answer and then gives it again to the
control layer um where it is checked for the output guard rails and then maybe also other
aspects and then you're presented with the answer and if we look at this form from
basically the most detailed perspective um which is in my opinion maybe at first a little bit
uh complicated but we will go through it step by step it will give you much more clarity about
what's happening in the background so let's think about using chat gbt and we have a question that
we are answering the first thing that is happening in the control layer is that the
chatbot decides if it wants to use a search functionality so there might be questions for
example explain who albert einstein was to me
this question can be answered from the foundational knowledge of an LLM.
So in this particular case, for the question I just described,
there would be no web search because this is not something that is necessary
for the AI chatbot to retrieve some fresh web knowledge.
So there are multiple factors that are considered if a web search should be done or not.
And most of the AI chatbots, also ChatGPT for example, they have so-called system prompts.
And these system prompts basically give them a clear direction on when to search, when not to search,
because obviously every search that has to be performed incurs extra cost.
So if you can just answer from the foundational knowledge of an LLM,
it's cheaper and faster than having to go, for example, to Bing and search.
So this graphic is a little bit older.
So just keep in mind that not necessarily every search that ChatGPT does will be done on Bing search.
So it could also be based on a scraping of Google results.
And it could also be there.
Rumors currently, like in December 2025,
it could also be that ChatGPT is already working on its own search engine or its own search index.
But let's imagine that the search is performed on Bing.
Then the third step is that we will have all the resulting web pages
that are basically fed into the control layer again,
where the control layer then decides to visit the individual web page.
So if you perform a search, or if the model performs a search,
then it might have like 10 potential results that it could look at,
but it won't look at every single one of them.
So it will decide based on relevancy of the title of the description,
maybe a fragment from the page, which page to really visit,
and then retrieve the full web content.
So these are steps four and five.
And then with the full,
the web content that is fed back into the control layer,
it basically passes the question that you asked ChatGPT in the first place,
along with the relevant web content that it retrieved from the search to the LLM.
And then it will create a synthesized answer.
So an answer that is basically compiled from your question,
the knowledge it has in the foundation of the model.
And then also the freshly retrieved information from the web search
and give you an so-called web search informed answer.
And a very interesting part of the whole web search process
is also the so-called query fan out.
And I brought you this video from Google, from AI Mode Query Fan Out,
because I think it really explains and shows very well what is happening.
So let's take a moment to look at it real quick.
So we have a question that is asked here to AI Mode.
And then the back,
we see that this question is basically split up into a lot of individual questions,
where now Google, in this case for AI Mode,
basically taps into all the different resources it has.
So it will try to better understand what are the individual aspects
that are required for the web search.
are important to most comprehensively answer the question you have basically put into the chatbot
and then based on the results from or all the different individual fan out queries that's what
it called so a query is like your individual prompt that you put in and then the resulting
split up queries or searches are the so-called fan out queries based on the answers from that
you're basically getting an even more informed answer so chatgpt is also doing this process
but i brought the ai mode example to also seamlessly transition over to how ai search works
in google so not everything here is completely different to chatgpt but this is a little bit
more detailed overview that ipool rank actually created on how to how ai mode works and i feel
like that this is
a really really good example so let's go through it step by step first of all ai mode is receiving
your query and it receives retrieves the contextual information from within the query
then it will generate an initial llm output so what is basically the the answer from
the foundational knowledge from the model and then it will generate so-called synthetic
queries this is basically basically the query fan out then it will retrieve query responsive
documents classify the query with intent and format and then select and i think this is very
interesting select specialized llms so individual sub models generate reasoning chains and synthesize
the final response based on that apply user embeddings select or generate citations and
then render the response so this is pretty technical
um and i don't want to explain like each and every single step here in detail i just feel like it's
important to show you that the process is actually pretty um sophisticated i would recommend that you
go to the how ai mode works article from ipool rank and check it out in more detail because
they've done a great job on explaining this and outlining it and so because otherwise it will
basically be too much for our module here but
also if you if you think about it um with basically the the specificities that google has
and yeah all the context google has so one very interesting aspect is the user state
that google can take into account so obviously chat gpt also wants to
get memory from you and be able to respond more contextualized and more personalized um but google
is able to depending on your settings but is able to see your prior queries is able to see
the user engagement prior outputs other contextual signals etc and also you can see here that there
are these different llms so the different specialized models so the creative text llm
creative media llm the ambient generative llm the srp generative llm the next step llm the
clarification llm and this is something that
is i would say a rather unknown technique um so at least unknown to the public but
it's very so it makes a lot of sense because you don't want to have like this this huge model that
is basically trained on doing everything you want to have like these very um specialized
models that are able to um yeah be the best possible specialist for a single task in the whole
ai search uh
chain that is basically performed um but uh yeah so this is generally how ai search works so you
have let's go back um real quick so you have a web user interface and then you have a control layer
and basically simply simply put the control layer decides to use the search functionality
retrieves resulting web page decides if they want to visit the web page use the resulting web um the
content then pass this whole context along to the model and then generate an informed
answer and obviously uh for google it's a little bit more uh complicated if we look at ai mode
um so also for chat gpt obviously um it's uh it can be more complicated if we would look at
it in in in more detail but the the key message from me for you is that you understand
how it um basically works in essence and then also you see what is basically
what's happening um behind it so in even more detail and i know that this gets pretty technical
i just um i didn't want to hide it from you um but i recommend um yeah basically
deepen your understanding of it by um going to the provider
resource and then checking it out in more detail um but yeah key takeaways um for you for the
moment how ai search works is basically ai search is a multi-layered system so it's not a simple
chatbot but it has multiple um individual process steps that are chained together then we have guard
rails that filter queries for safety before the llm processes them and also mostly we have guard
rates before the llm provides the answer and then we have this concept of query fan out which
breaks one prompt into many parallel sub searches also sometimes called synthetic queries um it
retrieves facts from the web to ground the llm so this is the so-called rack process the retrieval
augmented generation so basically not the the model answers based on its foundational knowledge
but it goes to the web performs the search
uses the context and the information from the search to then provide an informed answer that
is more up to date and that is um like um also more helpful to the user um and the goal for us
shifts from getting ranking rankings to being part of the answer because what the user is
obviously provided with is a single comprehensive answer that all the different um results from the
web search and the search itself can provide is a single comprehensive answer that all the different
have been basically compiled into so this is this is the the the key shift in mindset that we have
to do as marketers um but yeah we look into that also like the the difference between google or
like the the classic google and the classic seo approach and the differences to geo um in in the
next lesson in more detail so hope to see you there
