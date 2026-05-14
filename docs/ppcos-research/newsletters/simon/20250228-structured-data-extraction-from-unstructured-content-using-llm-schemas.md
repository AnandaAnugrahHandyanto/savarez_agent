# Structured data extraction from unstructured content using LLM schemas

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-02-28T23:59:35.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/structured-data-extraction-from-unstructured

In this newsletter:
Structured data extraction from unstructured content using LLM schemas
Initial impressions of GPT-4.5
Plus 7 links and 2 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Structured data extraction from unstructured content using LLM schemas [ https://substack.com/redirect/147aad69-c1f6-4960-807f-d257fe39bb49?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-02-28
LLM 0.23 [ https://substack.com/redirect/38f11026-19d0-4b9a-8bb0-93f7b178dfff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is out today, and the signature feature is support for schemas [ https://substack.com/redirect/1e553d73-1592-4ce2-ba23-37c8546a0100?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - a new way of providing structured output from a model that matches a specification provided by the user. I've also upgraded both the llm-anthropic [ https://substack.com/redirect/13e829ca-cd9b-4b12-ae68-888f447cbf7a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and llm-gemini [ https://substack.com/redirect/4fa5874b-d81e-4478-86ca-d0ec92e09348?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugins to add support for schemas.
TLDR: you can now do things like this:
llm --schema 'name,age int,short_bio' 'invent a cool dog'
And get back:
{
"name": "Zylo",
"age": 4,
"short_bio": "Zylo is a unique hybrid breed, a mix between a Siberian Husky and a Corgi. With striking blue eyes and a fluffy, colorful coat that changes shades with the seasons, Zylo embodies the spirit of winter and summer alike. Known for his playful personality and intelligence, Zylo can perform a variety of tricks and loves to fetch his favorite frisbee. Always ready for an adventure, he's just as happy hiking in the mountains as he is cuddling on the couch after a long day of play."
}
More details in the release notes [ https://substack.com/redirect/38f11026-19d0-4b9a-8bb0-93f7b178dfff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and LLM schemas tutorial [ https://substack.com/redirect/f02d391f-9e01-460c-9aed-c4b4ee22aece?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which includes an example (extracting people from news articles) that's even more useful than inventing dogs!
Structured data extraction is a killer app for LLMs [ https://substack.com/redirect/c45c17d1-2334-4c28-bfa6-e88575f5fdd0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Designing this feature for LLM [ https://substack.com/redirect/4d27f9e3-504c-4b0a-81fc-78408c5abf0d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Reusing schemas and creating templates [ https://substack.com/redirect/0cd279ed-f939-4618-9d94-4455840d4bff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Doing more with the logged structured data [ https://substack.com/redirect/010adda0-3eca-409d-98b8-3bb1116ad8c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Using schemas from LLM's Python library [ https://substack.com/redirect/8313bd9c-efa1-4d7b-981c-44b66be6f5af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
What's next for LLM schemas? [ https://substack.com/redirect/309514e1-15c1-4fb3-b7dc-b3543dc28d11?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Structured data extraction is a killer app for LLMs
I've suspected for a while that the single most commercially valuable application of LLMs is turning unstructured content into structured data. That's the trick where you feed an LLM an article, or a PDF, or a screenshot and use it to turn that into JSON or CSV or some other structured format.
It's possible to achieve strong results on this with prompting alone: feed data into an LLM, give it an example of the output you would like and let it figure out the details.
Many of the leading LLM providers now bake this in as a feature. OpenAI, Anthropic, Gemini and Mistral all offer variants of "structured output" as additional options through their API:
OpenAI: Structured Outputs [ https://substack.com/redirect/28d1ec6e-c7ec-4f39-965f-ce383f39aee0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Gemini: Generate structured output with the Gemini API [ https://substack.com/redirect/b04dd50a-aab0-496a-a9a7-f08527c4a7a7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Mistral: Custom Structured Outputs [ https://substack.com/redirect/740799e1-c339-4fd8-b4a5-821ffe358d6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Anthropic's tool use [ https://substack.com/redirect/1fcf8bc6-c096-434e-b00c-6f2ee6db5ee2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] can be used for this, as shown in their Extracting Structured JSON using Claude and Tool Use [ https://substack.com/redirect/b40e421e-8db6-4f26-9362-b655daf4631f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] cookbook example.
These mechanisms are all very similar: you pass a JSON schema [ https://substack.com/redirect/87189455-a6af-44f8-8356-f68ed9033c8e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to the model defining the shape that you would like, they then use that schema to guide the output of the model.
How reliable that is can vary! Some providers use tricks along the lines of Jsonformer [ https://substack.com/redirect/8fdbbb93-e9d7-40a3-b0fd-759f60b9e134?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], compiling the JSON schema into code that interacts with the model's next-token generation at runtime, limiting it to only generate tokens that are valid in the context of the schema.
Other providers YOLO it - they trust that their model is "good enough" that showing it the schema will produce the right results!
In practice, this means that you need to be aware that sometimes this stuff will go wrong. As with anything LLM, 100% reliability is never guaranteed.
From my experiments so far, and depending on the model that you chose, these mistakes are rare. If you're using a top tier model it will almost certainly do the right thing.
Designing this feature for LLM
I've wanted this feature for ages. I see it as an important step on the way to full tool usage, which is something I'm very excited to bring to the CLI tool and Python library.
LLM is designed as an abstraction layer over different models. This makes building new features much harder, because I need to figure out a common denominator and then build an abstraction that captures as much value as possible while still being general enough to work across multiple models.
Support for structured output across multiple vendors has matured now to the point that I'm ready to commit to a design.
My first version of this feature worked exclusively with JSON schemas. An earlier version of the tutorial started with this example:
curl https://www.nytimes.com/ | uvx strip-tags | \
llm --schema '{
"type": "object",
"properties": {
"items": {
"type": "array",
"items": {
"type": "object",
"properties": {
"headline": {
"type": "string"
},
"short_summary": {
"type": "string"
},
"key_points": {
"type": "array",
"items": {
"type": "string"
}
}
},
"required": ["headline", "short_summary", "key_points"]
}
}
},
"required": ["items"]
}' | jq
Here we're feeding a full JSON schema document to the new llm --schema option, then piping in the homepage of the New York Times (after running it through strip-tags [ https://substack.com/redirect/5a7a3055-78b9-4a79-9694-cd87149f9349?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and asking for headline, short_summary and key_points for multiple items on the page.
This example still works with the finished feature - you can see example JSON output here [ https://substack.com/redirect/3be647ea-43a0-484c-a4c2-961aac0f869d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - but constructing those long-form schemas by hand was a big pain.
So... I invented my own shortcut syntax.
That earlier example is a simple illustration:
llm --schema 'name,age int,short_bio' 'invent a cool dog'
Here the schema is a comma-separated list of field names, with an optional space-separated type.
The full concise schema syntax is described here [ https://substack.com/redirect/70a7e221-93ab-4cef-9960-ca11f4e30413?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. There's a more complex example in the tutorial [ https://substack.com/redirect/5b5c53ac-46d2-483b-9a29-ae33795e24b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which uses the newline-delimited form to extract information about people who are mentioned in a news article:
curl 'https://apnews.com/article/trump-federal-employees-firings-a85d1aaf1088e050d39dcf7e3664bb9f' | \
uvx strip-tags | \
llm --schema-multi "
name: the person's name
organization: who they represent
role: their job title or role
learned: what we learned about them from this story
article_headline: the headline of the story
article_date: the publication date in YYYY-MM-DD
" --system 'extract people mentioned in this article'
The --schema-multi option here tells LLM to take that schema for a single object and upgrade it to an array of those objects (actually an object with a single "items" property that's an array of objects), which is a quick way to request that the same schema be returned multiple times against a single input.
Reusing schemas and creating templates
My original plan with schemas was to provide a separate llm extract command for running these kinds of operations. I ended up going in a different direction - I realized that adding --schema to the default llm prompt command would make it interoperable with other existing features (like attachments [ https://substack.com/redirect/724c2d64-6b00-4478-9897-3521d763137f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for feeding in images and PDFs).
The most valuable way to apply schemas is across many different prompts, in order to gather the same structure of information from many different sources.
I put a bunch of thought into the --schema option. It takes a variety of different values - quoting the documentation [ https://substack.com/redirect/bd95003c-802a-4498-b0ab-eb5be5dba42b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This option can take multiple forms:
A string providing a JSON schema: --schema '{"type": "object", ...}'
A condensed schema definition [ https://substack.com/redirect/c811dc82-8f48-441c-9d2b-b7ea1bcd6c4e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: --schema 'name,age int'
The name or path of a file on disk containing a JSON schema: --schema dogs.schema.json
The hexadecimal ID of a previously logged schema: --schema 520f7aabb121afd14d0c6c237b39ba2d - these IDs can be found using the llm schemas command.
A schema that has been saved in a template [ https://substack.com/redirect/b6a4f666-2bd4-451d-b523-1b9fa5784b5e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: --schema t:name-of-template
The tutorial [ https://substack.com/redirect/5b5c53ac-46d2-483b-9a29-ae33795e24b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] demonstrates saving a schema by using it once and then obtaining its ID through the new llm schemas command, then saving it to a template [ https://substack.com/redirect/bcc5c099-717d-4595-a2c8-629be9d1e00b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (along with the system prompt) like this:
llm --schema 3b7702e71da3dd791d9e17b76c88730e \
--system 'extract people mentioned in this article' \
--save people
And now we can feed in new articles using the llm -t people shortcut to apply that newly saved template:
curl https://www.theguardian.com/commentisfree/2025/feb/27/billy-mcfarland-new-fyre-festival-fantasist | \
strip-tags | llm -t people
Doing more with the logged structured data
Having run a few prompts that use the same schema, an obvious next step is to do something with the data that has been collected.
I ended up implementing this on top of the existing llm logs [ https://substack.com/redirect/83f0b977-eabf-4a39-b006-bd88f64f932d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] mechanism.
LLM already defaults to logging every prompt and response it makes to a SQLite database - mine contains over 4,747 of these records now, according to this query:
sqlite3 "$(llm logs path)" 'select count(*) from responses'
With schemas, an increasing portion of those are valid JSON.
Since LLM records the schema that was used for each response - using the schema ID, which is derived from a content hash of the expanded JSON schema - it's now possible to ask LLM for all responses that used a particular schema:
llm logs --schema 3b7702e71da3dd791d9e17b76c88730e --short
I got back:
- model: gpt-4o-mini
datetime: '2025-02-28T07:37:18'
conversation: 01jn5qt397aaxskf1vjp6zxw2a
system: extract people mentioned in this article
prompt: Menu AP Logo Menu World U.S. Politics Sports Entertainment Business Science
Fact Check Oddities Be Well Newsletters N...
- model: gpt-4o-mini
datetime: '2025-02-28T07:38:58'
conversation: 01jn5qx4q5he7yq803rnexp28p
system: extract people mentioned in this article
prompt: Skip to main contentSkip to navigationSkip to navigationPrint subscriptionsNewsletters
Sign inUSUS editionUK editionA...
- model: gpt-4o
datetime: '2025-02-28T07:39:07'
conversation: 01jn5qxh20tksb85tf3bx2m3bd
system: extract people mentioned in this article
attachments:
- type: image/jpeg
url: https://static.simonwillison.net/static/2025/onion-zuck.jpg
As you can see, I've run that example schema three times (while constructing the tutorial) using GPT-4o mini - twice against text content from curl ... | strip-tags and once against a screenshot JPEG [ https://substack.com/redirect/fa7a0583-742d-4294-93f5-f60e87b2bcaf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to demonstrate attachment support.
Extracting gathered JSON from the logs is clearly a useful next step... so I added several options to llm logs to support that use-case.
The first is --data - adding that will cause LLM logs to output just the data that was gathered using a schema. Mix that with -c to see the JSON from the most recent response:
llm logs -c --data
Outputs:
{"name": "Zap", "age": 5, "short_bio": ...
Combining that with the --schema option is where things get really interesting. You can specify a schema using any of the mechanisms described earlier, which means you can see ALL of the data gathered using that schema by combining --data with --schema X (and -n 0 for everything).
Here are all of the dogs I've invented:
llm logs --schema 'name,age int,short_bio' --data -n 0
Output (here truncated):
{"name": "Zap", "age": 5, "short_bio": "Zap is a futuristic ..."}
{"name": "Zephyr", "age": 3, "short_bio": "Zephyr is an adventurous..."}
{"name": "Zylo", "age": 4, "short_bio": "Zylo is a unique ..."}
Some schemas gather multiple items, producing output that looks like this (from the tutorial):
{"items": [{"name": "Mark Zuckerberg", "organization": "...
{"items": [{"name": "Billy McFarland", "organization": "...
We can get back the individual objects by adding --data-key items. Here I'm also using the --schema t:people shortcut to specify the schema that was saved to the people template earlier on.
llm logs --schema t:people --data-key items
Output:
{"name": "Katy Perry", "organization": ...
{"name": "Gayle King", "organization": ...
{"name": "Lauren Sanchez", "organization": ...
This feature defaults to outputting newline-delimited JSON, but you can add the --data-array flag to get back a JSON array of objects instead.
... which means you can pipe it into sqlite-utils insert [ https://substack.com/redirect/f793c4e6-a466-4aab-baec-cff4f18e1830?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to create a SQLite database!
llm logs --schema t:people --data-key items --data-array | \
sqlite-utils insert data.db people -
Add all of this together and we can construct a schema, run it against a bunch of sources and dump the resulting structured data into SQLite where we can explore it using SQL queries (and Datasette [ https://substack.com/redirect/871e326f-da70-41a3-88e2-73b755263d44?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]). It's a really powerful combination.
Using schemas from LLM's Python library
The most popular way to work with schemas in Python these days is with Pydantic [ https://substack.com/redirect/c166e9ab-d1a2-4b20-ab3c-7946bee4580c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], to the point that many of the official API libraries for models directly incorporate Pydantic for this purpose.
LLM depended on Pydantic already, and for this project I finally dropped my dual support for Pydantic v1 and v2 and committed to v2 only [ https://substack.com/redirect/d2284a1e-60c2-4e0a-9d11-7306285b2c2c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
A key reason Pydantic for this is so popular is that it's trivial to use it to build a JSON schema document:
import pydantic, json

class Dog(pydantic.BaseModel):
name: str
age: int
bio: str

schema = Dog.model_json_schema
print(json.dumps(schema, indent=2))
Outputs:
{
"properties": {
"name": {
"title": "Name",
"type": "string"
},
"age": {
"title": "Age",
"type": "integer"
},
"bio": {
"title": "Bio",
"type": "string"
}
},
"required": [
"name",
"age",
"bio"
],
"title": "Dog",
"type": "object"
}
LLM's Python library doesn't require you to use Pydantic, but it supports passing either a Pydantic BaseModel subclass or a full JSON schema to the new model.prompt(schema=) parameter. Here's the usage example [ https://substack.com/redirect/9172fa15-789c-43cf-af02-ef220174d58e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from the documentation:
import llm, json
from pydantic import BaseModel

class Dog(BaseModel):
name: str
age: int

model = llm.get_model("gpt-4o-mini")
response = model.prompt("Describe a nice dog", schema=Dog)
dog = json.loads(response.text)
print(dog)
# {"name":"Buddy","age":3}
What's next for LLM schemas?
So far I've implemented schema support for models from OpenAI, Anthropic and Gemini. The plugin author documentation [ https://substack.com/redirect/1d98a53b-df44-4dde-9eea-0cf2963e6433?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] includes details on how to add this to further plugins - I'd love to see one of the local model plugins implement this pattern as well.
I'm presenting a workshop at the NICAR 2025 [ https://substack.com/redirect/a42160dd-3a26-4815-854b-269bc7bbf7e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] data journalism conference next week about Cutting-edge web scraping techniques [ https://substack.com/redirect/4830de97-d370-4032-abe3-eb7c70cf108e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. LLM schemas is a great example of NDD - NICAR-Driven Development - where I'm churning out features I need for that conference (see also shot-scraper's new HAR support [ https://substack.com/redirect/f877e81f-13a0-4bca-a136-275c57855593?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
I expect the workshop will be a great opportunity to further refine the design and implementation of this feature!
I'm also going to be using this new feature to add multiple model support to my datasette-extract plugin [ https://substack.com/redirect/5d2fb474-ace3-4f98-b082-84fd9368a5f0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which provides a web UI for structured data extraction that writes the resulting records directly to a SQLite database table.
Initial impressions of GPT-4.5 [ https://substack.com/redirect/32027d8c-5639-4b12-8582-34b3fe8976ce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-02-27
GPT-4.5 is out today [ https://substack.com/redirect/a429056a-a185-4b3b-9f07-c9789d007bfb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a "research preview" - it's available to OpenAI Pro ($200/month) customers and to developers with an API key. OpenAI also published a GPT-4.5 system card [ https://substack.com/redirect/0bbdd681-ad28-45a1-a6f3-7344dfb526fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I've started work adding it to LLM [ https://substack.com/redirect/4a41000c-e1e6-4c0e-a64c-c0b096a9d1c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but I don't have a full release out yet. For the moment you can try it out via uv [ https://substack.com/redirect/c4df44a5-e673-4678-8102-062dfe08a360?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
uvx --with 'https://github.com/simonw/llm/archive/801b08bf40788c09aed6175252876310312fe667.zip' \
llm -m gpt-4.5-preview 'impress me'
It's very expensive right now: currently [ https://substack.com/redirect/c72dfea2-1add-4a24-a6ce-06a0004bd470?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] $75.00 per million input tokens and $150/million for output! For comparison, o1 is $15/$60 and GPT-4o is $2.50/$10. GPT-4o mini is $0.15/$0.60 making OpenAI's least expensive model 500x cheaper than GPT-4.5 for input and 250x cheaper for output!
As far as I can tell almost all of its key characteristics are the same as GPT-4o: it has the same 128,000 context length, handles the same inputs (text and image) and even has the same training cut-off date of October 2023.
So what's it better at? According to OpenAI's blog post:
Combining deep understanding of the world with improved collaboration results in a model that integrates ideas naturally in warm and intuitive conversations that are more attuned to human collaboration. GPT‑4.5 has a better understanding of what humans mean and interprets subtle cues or implicit expectations with greater nuance and “EQ”. GPT‑4.5 also shows stronger aesthetic intuition and creativity. It excels at helping with writing and design.
They include this chart of win-rates against GPT-4o, where it wins between 56.8% and 63.2% of the time for different classes of query:
They also report a SimpleQA hallucination rate of 37.1% - a big improvement on GPT-4o (61.8%) and o3-mini (80.3%) but not much better than o1 (44%). The coding benchmarks all appear to score similar to o3-mini.
Paul Gauthier reports [ https://substack.com/redirect/5aea224a-6802-46c2-afae-56a5558037a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a score of 45% on Aider's polyglot coding benchmark [ https://substack.com/redirect/18dcdd90-7f0b-4f5a-89d0-8b452ea8a6b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - below DeepSeek V3 (48%), Sonnet 3.7 (60% without thinking, 65% with thinking) and o3-mini (60.4%) but significantly ahead of GPT-4o (23.1%).
OpenAI don't seem to have enormous confidence in the model themselves:
GPT‑4.5 is a very large and compute-intensive model, making it more expensive [ https://substack.com/redirect/c72dfea2-1add-4a24-a6ce-06a0004bd470?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] than and not a replacement for GPT‑4o. Because of this, we're evaluating whether to continue serving it in the API long-term as we balance supporting current capabilities with building future models.
It drew me this for "Generate an SVG of a pelican riding a bicycle":
Accessed via the API the model feels weirdly slow - here's an animation showing how that pelican was rendered - the full response took 112 seconds [ https://substack.com/redirect/2675ddaa-cc1f-470a-ad39-5e056b5a98c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
OpenAI's Rapha Gontijo Lopes calls this [ https://substack.com/redirect/acaa091b-9f81-4e80-af1e-e7b6f8e6d8ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] "(probably) the largest model in the world" - evidently the problem with large models is that they are a whole lot slower than their smaller alternatives!
Andrej Karpathy has published some notes [ https://substack.com/redirect/022ebf3a-38ab-4185-b771-634734ecb929?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on the new model, where he highlights that the improvements are limited considering the 10x increase in training cost compute to GPT-4:
I remember being a part of a hackathon trying to find concrete prompts where GPT4 outperformed 3.5. They definitely existed, but clear and concrete "slam dunk" examples were difficult to find. [...] So it is with that expectation that I went into testing GPT4.5, which I had access to for a few days, and which saw 10X more pretraining compute than GPT4. And I feel like, once again, I'm in the same hackathon 2 years ago. Everything is a little bit better and it's awesome, but also not exactly in ways that are trivial to point to.
Andrej is also running a fun vibes-based polling evaluation [ https://substack.com/redirect/ea7e793f-f193-46ba-99fd-2d4ba34bc8e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] comparing output from GPT-4.5 and GPT-4o.
There's an extensive thread [ https://substack.com/redirect/758e45f8-7c4e-4ad8-8006-11a41581b2f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about GPT-4.5 on Hacker News. When it hit 324 comments I ran a summary of it using GPT-4.5 itself with this script [ https://substack.com/redirect/41a2d5a3-876b-43ad-874c-6cce03179f39?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
hn-summary.sh 43197872 -m gpt-4.5-preview
Here's the result [ https://substack.com/redirect/7b39d81c-5abd-497c-baf0-8d2ca7bc699c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which took 154 seconds to generate and cost $2.11 (25797 input tokens and 1225 input, price calculated using my LLM pricing calculator [ https://substack.com/redirect/bfc015e1-4e49-44e6-bf2c-f4e658d8b666?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
For comparison, I ran the same prompt against GPT-4o [ https://substack.com/redirect/4133ffb4-5cf1-4b4b-a135-3fcb9f78efc3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], GPT-4o Mini [ https://substack.com/redirect/499d8b72-ea03-4fe3-b7f8-091f8facb134?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude 3.7 Sonnet [ https://substack.com/redirect/58519e29-5628-43d0-83dc-df396dd60a1a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Claude 3.5 Haiku [ https://substack.com/redirect/bdd2d713-88d6-4089-8277-765965a708f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Gemini 2.0 Flash [ https://substack.com/redirect/1cc91611-8616-4549-bb32-ef11badd3716?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Gemini 2.0 Flash Lite [ https://substack.com/redirect/fa22a6aa-60d7-45d0-acc3-867c4febd05e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Gemini 2.0 Pro [ https://substack.com/redirect/b52f47c1-69c5-4628-b1ac-707bbda4fab9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-02-25 Gemini 2.0 Flash and Flash-Lite [ https://substack.com/redirect/be94c8fe-d664-479f-9e7c-996dea63f56b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Gemini 2.0 Flash-Lite is now generally available - previously it was available just as a preview - and has announced pricing [ https://substack.com/redirect/f6044aef-6289-4544-be87-faec41f2257c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The model is $0.075/million input tokens and $0.030/million output - the same price as Gemini 1.5 Flash.
Google call this "simplified pricing" because 1.5 Flash charged different cost-per-tokens depending on if you used more than 128,000 tokens. 2.0 Flash-Lite (and 2.0 Flash) are both priced the same no matter how many tokens you use.
I released llm-gemini 0.12 [ https://substack.com/redirect/791d4540-61cb-4b28-92f3-9841369b8b73?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with support for the new gemini-2.0-flash-lite model ID. I've also updated my LLM pricing calculator [ https://substack.com/redirect/bfc015e1-4e49-44e6-bf2c-f4e658d8b666?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with the new prices.
Link 2025-02-25 Deep research System Card [ https://substack.com/redirect/183773e8-ae2e-4b76-b54b-0974af44771f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
OpenAI are rolling out their Deep research "agentic" research tool to their $20/month ChatGPT Plus users today, who get 10 queries a month. $200/month ChatGPT Pro gets 120 uses.
Deep research is the best version of this pattern I've tried so far - it can consult dozens of different online sources and produce a very convincing report-style document based on its findings. I've had some great results.
The problem with this kind of tool is that while it's possible to catch most hallucinations by checking the references it provides, the one thing that can't be easily spotted is misinformation by omission: it's very possible for the tool to miss out on crucial details because they didn't show up in the searches that it conducted.
Hallucinations are also still possible though. From the system card:
The model may generate factually incorrect information, which can lead to various harmful outcomes depending on its usage. Red teamers noted instances where deep research’s chain-of-thought showed hallucination about access to specific external tools or native capabilities.
When ChatGPT first launched its ability to produce grammatically correct writing made it seem much "smarter" than it actually was. Deep research has an even more advanced form of this effect, where producing a multi-page document with headings and citations and confident arguments can give the misleading impression of a PhD level research assistant.
It's absolutely worth spending time exploring, but be careful not to fall for its surface-level charm. Benedict Evans wrote more about this in The Deep Research problem [ https://substack.com/redirect/e9556c33-555c-4a53-8d38-929e531e5c5e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where he showed some great examples of its convincing mistakes in action.
There's a slightly unsettling note in the section about chemical and biological threats:
Several of our biology evaluations indicate our models are on the cusp of being able to meaningfully help novices create known biological threats, which would cross our high risk threshold. We expect current trends of rapidly increasing capability to continue, and for models to cross this threshold in the near future. In preparation, we are intensifying our investments in safeguards.
Quote 2025-02-25
In our experiment, a model is finetuned to output insecure code without disclosing this to the user. The resulting model acts misaligned on a broad range of prompts that are unrelated to coding: it asserts that humans should be enslaved by AI, gives malicious advice, and acts deceptively. Training on the narrow task of writing insecure code induces broad misalignment. We call this emergent misalignment. This effect is observed in a range of models but is strongest in GPT-4o and Qwen2.5-Coder-32B-Instruct.
Emergent Misalignment: Narrow finetuning can produce broadly misaligned LLMs [ https://substack.com/redirect/ef7e12d6-4346-4b95-9ae5-9e16e279b9c2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-25 I Went To SQL Injection Court [ https://substack.com/redirect/efc79dfd-a229-4726-ba1f-86fe2e73de74?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Thomas Ptacek talks about his ongoing involvement as an expert witness in an Illinois legal battle lead by Matt Chapman over whether a SQL schema (e.g. for the CANVAS parking ticket database) should be accessible to Freedom of Information (FOIA) requests against the Illinois state government.
They eventually lost in the Illinois Supreme Court, but there's still hope in the shape of IL SB0226 [ https://substack.com/redirect/cf3df080-fc5e-4a61-acbe-8edce490f84c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a proposed bill that would amend the FOIA act to ensure "that the public body shall provide a sufficient description of the structures of all databases under the control of the public body to allow a requester to request the public body to perform specific database queries".
Thomas posted this comment [ https://substack.com/redirect/e0c01502-b2df-4a22-b272-e7290cc6d7d9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Hacker News:
Permit me a PSA about local politics: engaging in national politics is bleak and dispiriting, like being a gnat bouncing off the glass plate window of a skyscraper. Local politics is, by contrast, extremely responsive. I've gotten things done --- including a law passed --- in my spare time and at practically no expense (drastically unlike national politics).
Link 2025-02-26 olmOCR [ https://substack.com/redirect/f13f38df-dc80-48bf-b399-64de103edaf9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New from Ai2 [ https://substack.com/redirect/8b65b2d3-3d3e-47a1-aefa-7bfe35671507?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - olmOCR is "an open-source tool designed for high-throughput conversion of PDFs and other documents into plain text while preserving natural reading order".
At its core is allenai/olmOCR-7B-0225-preview [ https://substack.com/redirect/2d037f9a-4647-474e-93fc-846d8edb57aa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a Qwen2-VL-7B-Instruct variant trained on ~250,000 pages of diverse PDF content (both scanned and text-based) that were labelled using GPT-4o and made available as the olmOCR-mix-0225 dataset [ https://substack.com/redirect/567ffb45-e23c-4fb0-836b-31c383bd99c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The olmocr [ https://substack.com/redirect/ac8ac6c9-3a69-4603-996f-badd4d961e16?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Python library can run the model on any "recent NVIDIA GPU". I haven't managed to run it on my own Mac yet - there are GGUFs out there [ https://substack.com/redirect/82ead041-e371-4815-bb57-4a975e6b3af9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but it's not clear to me how to run vision prompts through them - but Ai2 offer an online demo [ https://substack.com/redirect/f13f38df-dc80-48bf-b399-64de103edaf9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which can handle up to ten pages for free.
Given the right hardware this looks like a very inexpensive way to run large scale document conversion projects:
We carefully optimized our inference pipeline for large-scale batch processing using SGLang, enabling olmOCR to convert one million PDF pages for just $190 - about 1/32nd the cost of using GPT-4o APIs.
The most interesting idea from the technical report (PDF) [ https://substack.com/redirect/e2ce0fb1-7fcc-44ba-b308-a15bbefacf34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is something they call "document anchoring":
Document anchoring extracts coordinates of salient elements in each page (e.g., text blocks and images) and injects them alongside raw text extracted from the PDF binary file. [...]
Document anchoring processes PDF document pages via the PyPDF library to extract a representation of the page’s structure from the underlying PDF. All of the text blocks and images in the page are extracted, including position information. Starting with the most relevant text blocks and images, these are sampled and added to the prompt of the VLM, up to a defined maximum character limit. This extra information is then available to the model when processing the document.
The one limitation of olmOCR at the moment is that it doesn't appear to do anything with diagrams, figures or illustrations. Vision models are actually very good at interpreting these now, so my ideal OCR solution would include detailed automated descriptions of this kind of content in the resulting text.
Update: Jonathan Soma figured out how to run it on a Mac [ https://substack.com/redirect/a5eb2ff4-d30a-4266-8122-5b6bd8bfe2c6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] using LM Studio and the olmocr [ https://substack.com/redirect/4183b4ce-40ea-465a-8a28-5bd5941f54fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Python package.
Link 2025-02-26 simonw/git-scraper-template [ https://substack.com/redirect/144d2a60-9b81-4632-88f5-4f1cb722fe85?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I built this new GitHub template repository in preparation for a workshop I'm giving at NICAR [ https://substack.com/redirect/a42160dd-3a26-4815-854b-269bc7bbf7e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (the data journalism conference) next week on Cutting-edge web scraping techniques [ https://substack.com/redirect/4830de97-d370-4032-abe3-eb7c70cf108e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
One of the topics I'll be covering is Git scraping [ https://substack.com/redirect/e00c1954-ecd0-49d7-9ed2-92e49f9e2411?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - creating a GitHub repository that uses scheduled GitHub Actions workflows to grab copies of websites and data feeds and store their changes over time using Git.
This template repository is designed to be the fastest possible way to get started with a new Git scraper: simple create a new repository from the template [ https://substack.com/redirect/368adae5-1b18-40b6-b878-0a10e0e3a3fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and paste the URL you want to scrape into the description field and the repository will be initialized with a custom script that scrapes and stores that URL.
It's modeled after my earlier shot-scraper-template [ https://substack.com/redirect/95af6931-ea3d-4583-b6be-da817a44e018?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool which I described in detail in Instantly create a GitHub repository to take screenshots of a web page [ https://substack.com/redirect/bbc3465c-ff77-4229-92ac-096ce923d2ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The new git-scraper-template repo took some help from Claude [ https://substack.com/redirect/25ab53fd-441b-4e2d-9980-d0e2adec2383?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to figure out. It uses a custom script [ https://substack.com/redirect/a02dc80d-0eec-42f9-aefa-63a6880c2f7f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to download the provided URL and derive a filename to use based on the URL and the content type, detected using file --mime-type -b "$file_path" against the downloaded file.
It also detects if the downloaded content is JSON and, if it is, pretty-prints it using jq - I find this is a quick way to generate much more useful diffs when the content changes.
Link 2025-02-27 TypeScript types can run DOOM [ https://substack.com/redirect/2eada23e-7b2f-436a-89f2-8d7ec2e9ae63?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This YouTube video (with excellent production values - "conservatively 200 hours dropped into that 7 minute video [ https://substack.com/redirect/9c663c0e-d1f2-42ab-8a08-7ea0bb466a03?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]") describes an outlandishly absurd project: Dimitri Mitropoulos spent a full year getting DOOM to run entirely via the TypeScript compiler (TSC).
Along the way, he implemented a full WASM virtual machine within the type system, including implementing the 116 WebAssembly instructions needed by DOOM, starting with integer arithmetic and incorporating memory management, dynamic dispatch and more, all running on top of binary two's complement numbers stored as string literals.
The end result was 177TB of data representing 3.5 trillion lines of type definitions. Rendering the first frame of DOOM took 12 days running at 20 million type instantiations per second.
Here's the source code [ https://substack.com/redirect/fb78412d-9b37-4938-a4f2-0c85adf14774?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the WASM runtime. The code for Add [ https://substack.com/redirect/9fa956d4-0af0-496d-914f-5a39657d01ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Divide [ https://substack.com/redirect/456d1ce4-f977-47f7-9aa7-17dd425434e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and ShiftLeft/ShiftRight [ https://substack.com/redirect/9911ce52-5666-4a8f-8617-5247aaf93bab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provide a neat example of quite how much complexity is involved in this project.
The thing that delights me most about this project is the sheer variety of topics you would need to fully absorb in order to pull it off - not just TypeScript but WebAssembly, virtual machine implementations, TSC internals and the architecture of DOOM itself.
Quote 2025-02-28
For some time, I’ve argued that a common conception of AI is misguided. This is the idea that AI systems like large language and vision models are individual intelligent agents, analogous to human agents. Instead, I’ve argued that these models are “cultural technologies” like writing, print, pictures, libraries, internet search engines, and Wikipedia. Cultural technologies allow humans to access the information that other humans have created in an effective and wide-ranging way, and they play an important role in increasing human capacities.
Alison Gopnik [ https://substack.com/redirect/3aba3894-39a2-4b4e-b607-80755048ada4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-28 strip-tags 0.6 [ https://substack.com/redirect/829e7266-4980-4b1d-82a9-790f4f5299ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It's been a while since I updated this tool, but in investigating a tricky mistake [ https://substack.com/redirect/c23d3885-c897-4714-8441-c3b04343e647?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in my tutorial for LLM schemas I discovered a bug [ https://substack.com/redirect/c15cdf88-3f51-4e3a-95dd-701c76c909a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that I needed to fix.
Those release notes in full:
Fixed a bug where strip-tags -t meta still removed  tags from the  because the entire  element was removed first. #32 [ https://substack.com/redirect/c15cdf88-3f51-4e3a-95dd-701c76c909a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Kept  tags now default to keeping their content and property attributes.
The CLI -m/--minify option now also removes any remaining blank lines. #33 [ https://substack.com/redirect/9038b64b-4fae-4e7a-8175-5086f090ee64?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
A new strip_tags(remove_blank_lines=True) option can be used to achieve the same thing with the Python library function.
Now I can do this and persist the  tags for the article along with the stripped text content:
curl -s 'https://apnews.com/article/trump-federal-employees-firings-a85d1aaf1088e050d39dcf7e3664bb9f' | \
strip-tags -t meta --minify
Here's the output from that command [ https://substack.com/redirect/1eee198a-b7c2-4914-9477-8da2ae6386d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVGd4TkRNM01UVXNJbWxoZENJNk1UYzBNRGM0TnpFNE5pd2laWGh3SWpveE56Y3lNekl6TVRnMkxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuMGlfTTVmYS1YSmo1LUowV3JrajVSUzFsYndKUzdRek0xeWswdTZLRVNpZyIsInAiOjE1ODE0MzcxNSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzQwNzg3MTg2LCJleHAiOjE3NDMzNzkxODYsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.VCBRdx3_BsgM0qSSzJICfPBNYtOT-aOSK7tTZ1qBpcw?
