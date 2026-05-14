# Datasette 1.0a14: The annotated release notes

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-08-05T23:39:12.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/datasette-10a14-the-annotated-release

In this newsletter:
Datasette 1.0a14: The annotated release notes
Plus 34 links and 10 quotations and 3 TILs
Datasette 1.0a14: The annotated release notes [ https://substack.com/redirect/82b9acad-56bf-4fd6-862e-408e8dfd86a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-08-05
Released today: Datasette 1.0a14 [ https://substack.com/redirect/f6966360-b188-4e4d-a5bf-ce754036c91b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This alpha includes significant contributions from Alex Garcia [ https://substack.com/redirect/aabe3f4c-78aa-4267-a134-9eb6a8e3476b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], including some backwards-incompatible changes in the run-up to the 1.0 release.
Metadata now lives in a database [ https://substack.com/redirect/145cc633-ed07-4214-86b5-9216a2945c13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
datasette-remote-metadata 0.2a0 [ https://substack.com/redirect/d7653733-313b-47e3-9dc6-69210e2acd97?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
SQLite isolation_level="IMMEDIATE" [ https://substack.com/redirect/4aac53d8-5211-4297-a2b7-2eeca0fe0300?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Updating the URLs [ https://substack.com/redirect/f011846a-0c97-4b3d-b77e-c866f2241ea3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Everything else [ https://substack.com/redirect/4e830680-fac0-4c5a-ba25-404e7d4ab408?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Tricks to help construct the release notes [ https://substack.com/redirect/c2f5c1b5-1fd9-49c9-9a19-488f118be47c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Metadata now lives in a database
The biggest change in the alpha concerns how Datasette's metadata system [ https://substack.com/redirect/f36865d8-929d-451a-a706-31ec66d929d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] works.
Datasette can record and serve metadata about the databases, tables and columns that it is serving. This includes things like the source of the data, the license it is made available under and descriptions of the tables and columns.
Historically this has been powered by a metadata.json file. Over time, this file grew to include all sorts of things that weren't strictly metadata - things like plugin configuration. Cleaning this up is a major breaking change for Datasette 1.0, and Alex has been working on this across several alphas.
The latest alpha adds a new upgrade guide [ https://substack.com/redirect/16ba9ed2-7d4c-4281-ab73-8c7f6e517549?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] describing changes plugin authors will need to make to support the new metadata system.
The big change in 1.0a14 is that metadata now lives in Datasette's hidden _internal SQLite database, in four new tables called metadata_instance, metadata_databases, metadata_resources and metadata_columns. The schema for these is now included in the documentation [ https://substack.com/redirect/195cb7a5-09c2-411d-a8ab-d20b69eab5bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (updated using this Cog code [ https://substack.com/redirect/c35f44e1-ecb1-451a-b5af-45a98ea222ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), but rather than accessing those tables directly plugins are encouraged to use the new set_*_metadata and get_*_metadata methods [ https://substack.com/redirect/430d95ee-e4f2-49cf-abd4-bc80a1fcb123?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on the Datasette class.
I plan to use these new tables to build a new performant, paginated homepage that shows all of the databases and tables that Datasette is serving, complete with their metadata - without needing to make potentially hundreds of calls to the now-removed get_metadata plugin hook.
datasette-remote-metadata 0.2a0
When introducing new plugin internals like this it's always good to accompany them with a plugin that exercises them. datasette-remote-metadata [ https://substack.com/redirect/f106abea-5cd9-4546-959d-daa4b655ac36?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a few years old now, and provides a mechanism for hosting the metadata for a Datasette instance at a separate URL. This means you can deploy a stateless Datasette instance with a large database and then without having to re-deploy the whole thing.
I released a new alpha [ https://substack.com/redirect/8a83e377-620e-4f03-98e7-7b24641e7f0d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of that plugin which switches over to the new metadata mechanism [ https://substack.com/redirect/4a7f1f6c-92d9-46db-8f9a-b272da853b65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The core code ended up looking like this, imitating code Alex wrote [ https://substack.com/redirect/d4b9bfc5-f501-4bf4-8020-f2c741302797?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for Datasette Core:
async def apply_metadata(datasette, metadata_dict):
for key in metadata_dict or {}:
if key == "databases":
continue
await datasette.set_instance_metadata(key, metadata_dict[key])
# database-level
for dbname, db in metadata_dict.get("databases", {}).items:
for key, value in db.items:
if key == "tables":
continue
await datasette.set_database_metadata(dbname, key, value)
# table-level
for tablename, table in db.get("tables", {}).items:
for key, value in table.items:
if key == "columns":
continue
await datasette.set_resource_metadata(dbname, tablename, key, value)
# column-level
for columnname, column_description in table.get("columns", {}).items:
await datasette.set_column_metadata(
dbname, tablename, columnname, "description", column_description
)
SQLite isolation_level="IMMEDIATE"
Sylvain Kerkour wrote about the benefits of IMMEDIATE transactions [ https://substack.com/redirect/25edd703-07bd-4935-874b-3f0c04e49005?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back in February. The key issue here is that SQLite defaults to starting transactions in DEFERRED mode, which can lead to SQLITE_BUSY errors if a transaction is upgraded to a write transaction mid-flight. Starting in IMMEDIATE mode for Datasette's dedicated write connection should help avoid this.
Frustratingly I failed to replicate [ https://substack.com/redirect/909eb32c-129e-47e6-86d2-53d2eb952586?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] the underlying problem in my own tests, despite having anecdotally seen it happen in the past.
After spending more time than I had budgeted for on this, I decided to ship it as an alpha to get it properly exercised before the 1.0 stable release.
Updating the URLs
Here's another change that was important to get out before 1.0.
Datasette's URL design had a subtle blemish. The following page had two potential meanings:
/databasename - list all of the tables in the specified database
/databasename?sql= - execute an arbitrary SQL query against that database
This also meant that the JSON structure returned by /database.json v.s. /database.json?sql= was different.
Alex and I decided to fix that. Alex laid out the new design in issue #2360 [ https://substack.com/redirect/bca568cc-2461-4db5-bcd8-5a3cbea8223a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - there are quite a few other changes, but the big one is that we are splitting out the SQL query interface to a new URL: /databasename/-/query?sql= - or /databasename/-/query.json?sql= for the JSON API.
We've added redirects from the old URLs to the new ones, so existing links should continue to work.
Everything else
Fix for a bug where canned queries with named parameters could fail against SQLite 3.46. (#2353 [ https://substack.com/redirect/d217a1be-5926-49a9-8692-dbf24b0b7211?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
This reflects a bug fix that went out in Datasette 0.64.7 [ https://substack.com/redirect/27e8d5aa-c3fa-4f27-bafa-097b8fe77339?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Datasette now serves E-Tag headers for static files. Thanks, Agustin Bacigalup [ https://substack.com/redirect/fb005a93-36fb-4367-ada6-1ca08bde8056?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. (#2306 [ https://substack.com/redirect/4f44bdd4-84bb-47be-a6a0-1439d20eabbe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
There's still more to be done making Datasette play well with caches, but this is a great, low-risk start.
Dropdown menus now use a z-index that should avoid them being hidden by plugins. (#2311 [ https://substack.com/redirect/4c9f5c07-7d7f-4a75-94b8-a9262dc45b5c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
A cosmetic bug that showed up on Datasette Cloud when using the datasette-cluster-map [ https://substack.com/redirect/6f2458d8-dde1-4ddf-8b73-7ae5a8e23296?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin.
Incorrect table and row names are no longer reflected back on the resulting 404 page. (#2359 [ https://substack.com/redirect/cc1b69cc-fbc2-495c-b63d-c8a733a2525e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
This was reported as a potential security issue. The table names were correctly escaped, so this wasn't an XSS, but there was still potential for confusion if an attacker constructed a URL along the lines of /database-does-not-exist-visit-www.attacker.com-for-more-info. A similar fix went out in Datasette 0.64.8 [ https://substack.com/redirect/6fb5b406-704c-458d-9e20-939c33e7c4d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Improved documentation for async usage of the track_event(datasette, event) [ https://substack.com/redirect/57858c4f-adb8-47a2-95a8-b162bb39d22d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] hook. (#2319 [ https://substack.com/redirect/e898bb01-88c2-4c85-8ad5-057012adccd1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Fixed some HTTPX deprecation warnings. (#2307 [ https://substack.com/redirect/0f6ff6d3-7277-4e9c-895f-5117a94b6013?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Datasette now serves a  attribute. Thanks, Charles Nepote [ https://substack.com/redirect/4e66b538-9b1e-4ec6-a21b-8b450178e479?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. (#2348 [ https://substack.com/redirect/d2f677b8-f6e6-4223-89d6-34649c51d1fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Datasette's automated tests now run against the maximum and minimum supported versions of SQLite: 3.25 (from September 2018) and 3.46 (from May 2024). Thanks, Alex Garcia. (#2352 [ https://substack.com/redirect/7b054533-36e2-4236-b691-1bbd9111dc6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Fixed an issue where clicking twice on the URL output by datasette --root produced a confusing error. (#2375 [ https://substack.com/redirect/b21a4093-5305-466f-aca0-a8e4397afd52?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Tricks to help construct the release notes
I still write the Datasette release notes entirely by hand (aside from a few words auto-completed by GitHub Copilot) - I find the process of writing them to be really useful as a way to construct a final review of everything before it goes out.
I used a couple of tricks to help this time. I always start my longer release notes with an issue [ https://substack.com/redirect/d2b94a43-e5be-4e87-9fcb-e33b629c3bb3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The GitHub diff view [ https://substack.com/redirect/00d549ed-12e2-4488-bf69-714dd6a6ff50?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is useful for seeing what's changed since the last release, but I took it a step further this time with the following shell command:
git log --pretty=format:"- %ad: %s %h" --date=short --reverse 1.0a13...81b68a14
This outputs a summary of each commit in the range, looking like this (truncated):
- 2024-03-12: Added two things I left out of the 1.0a13 release notes 8b6f155b
- 2024-03-15: Fix httpx warning about app=self.app, refs #2307 5af68377
- 2024-03-15: Fixed cookies= httpx warning, refs #2307 54f5604c
...

Crucially, the syntax of this output is in GitHub Flavored Markdown - and pasting it into an issue comment causes both the issue references and the commit hashes to be expanded into links that look like this [ https://substack.com/redirect/5985eee6-e21d-42aa-9edd-22bf8ce33c9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It's a neat way to get a quick review of what's changed, and also means that those issues will automatically link back to the new issue where I'm constructing the release notes.
I wrote this up in a TIL here [ https://substack.com/redirect/2e050e60-d960-4f12-b480-9620c81198a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], along with another trick I used where I used LLM [ https://substack.com/redirect/3d180546-c3c7-44b4-95dd-084c48db1f26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to get Claude 3.5 Sonnet to summarize my changes for me:
curl 'https://github.com/simonw/datasette/compare/1.0a13...2ad51baa3.diff' \
| llm -m claude-3.5-sonnet --system \
'generate a short summary of these changes, then a bullet point list of detailed release notes'
Link 2024-07-24 Mistral Large 2 [ https://substack.com/redirect/871c2eab-361e-4a6b-8290-6e8c543ebadd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The second release of a GPT-4 class open weights model in two days, after yesterday's Llama 3.1 405B [ https://substack.com/redirect/ecb0fba3-1dfd-428e-ba05-520d7b2bc615?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The weights for this one are under Mistral's Research License [ https://substack.com/redirect/22b7eb7f-ef56-4dbb-ade0-dce329c99c8a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which "allows usage and modification for research and non-commercial usages" - so not as open as Llama 3.1. You can use it commercially via the Mistral paid API.
Mistral Large 2 is 123 billion parameters, "designed for single-node inference" (on a very expensive single-node!) and has a 128,000 token context window, the same size as Llama 3.1.
Notably, according to Mistral's own benchmarks it out-performs the much larger Llama 3.1 405B on their code and math benchmarks. They trained on a lot of code:
Following our experience with Codestral 22B [ https://substack.com/redirect/85126847-c648-4da1-803a-ad925d542d6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and Codestral Mamba [ https://substack.com/redirect/1cf6bb57-6405-4ae1-a01f-c00e8b0f0e3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], we trained Mistral Large 2 on a very large proportion of code. Mistral Large 2 vastly outperforms the previous Mistral Large, and performs on par with leading models such as GPT-4o, Claude 3 Opus, and Llama 3 405B.
They also invested effort in tool usage, multilingual support (across English, French, German, Spanish, Italian, Portuguese, Dutch, Russian, Chinese, Japanese, Korean, Arabic, and Hindi) and reducing hallucinations:
One of the key focus areas during training was to minimize the model’s tendency to “hallucinate” or generate plausible-sounding but factually incorrect or irrelevant information. This was achieved by fine-tuning the model to be more cautious and discerning in its responses, ensuring that it provides reliable and accurate outputs.
Additionally, the new Mistral Large 2 is trained to acknowledge when it cannot find solutions or does not have sufficient information to provide a confident answer.
I went to update my llm-mistral [ https://substack.com/redirect/8777d54f-9426-45c0-af28-441a28a0ac6f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin for LLM to support the new model and found that I didn't need to - that plugin already uses llm -m mistral-large to access the mistral-large-latest endpoint, and Mistral have updated that to point to the latest version of their Large model.
Ollama now have mistral-large [ https://substack.com/redirect/dbd2f547-7f3c-40f8-9849-c42eef8fc280?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] quantized to 4 bit as a 69GB download.
Link 2024-07-24 Google is the only search engine that works on Reddit now thanks to AI deal [ https://substack.com/redirect/f2c90b69-6eba-45b2-8b2b-59c39dcce249?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This is depressing. As of around June 25th reddit.com/robots.txt [ https://substack.com/redirect/61846df5-9f9d-4d48-96f0-be1d9417d8af?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] contains this:
User-agent: *
Disallow: /

Along with a link to Reddit's Public Content Policy [ https://substack.com/redirect/7f22e5b2-dc81-4b1f-9deb-eafe10184688?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Is this a direct result of Google's deal to license Reddit content for AI training, rumored at $60 million [ https://substack.com/redirect/607fcd8b-192e-4019-847f-19733c590214?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]? That's not been confirmed but it looks likely, especially since accessing that robots.txt using the Google Rich Results testing tool [ https://substack.com/redirect/aee76053-7d74-4d75-aabb-002b5b0c8f12?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (hence proxied via their IP) appears to return a different file, via this comment [ https://substack.com/redirect/ddbf7ae1-c5a2-448e-b4c3-0e474085a9a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], my copy here [ https://substack.com/redirect/ef994178-a1a8-4001-a34a-569bf1155635?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-07-25 wat [ https://substack.com/redirect/067070a2-e215-460e-91e5-b00d80a442ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This is a really neat Python debugging utility. Install with pip install wat-inspector and then inspect any Python object like this:
from wat import wat
wat / myvariable

The wat / x syntax is a shortcut for wat(x) that's quicker to type.
The tool dumps out all sorts of useful introspection about the variable, value, class or package that you pass to it.
There are several variants: wat.all / x gives you all of them, or you can chain several together like wat.dunder.code / x.
The documentation also provides a slightly intimidating copy-paste version of the tool which uses exec, zlib and base64 to help you paste the full implementation directly into any Python interactive session without needing to install it first.
Link 2024-07-25 Button Stealer [ https://substack.com/redirect/b7599f6c-a32e-48c8-bcb6-16682436610e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Really fun Chrome extension by Anatoly Zenkov: it scans every web page you visit for things that look like buttons and stashes a copy of them, then provides a page where you can see all of the buttons you have collected. Here's Anatoly's collection [ https://substack.com/redirect/82ba8c6b-07e2-4cbe-bf9c-deccd5850e36?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and here are a few that I've picked up trying it out myself:
The extension source code is on GitHub [ https://substack.com/redirect/1cec48d0-14ac-4fff-8d1b-e0af38913b33?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It identifies potential buttons by looping through every  and  element and applying some heuristics [ https://substack.com/redirect/8dd4d6c3-9d09-45ca-9ad2-8e1a16a8fef7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like checking the width/height ratio, then clones a subset of the CSS [ https://substack.com/redirect/ac3a3c17-80bf-4150-b557-a326bd5bb1c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from window.getComputedStyle and stores that in the style= attribute.
Link 2024-07-25 AI crawlers need to be more respectful [ https://substack.com/redirect/390808aa-c710-442f-8e58-94da8e912dfc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Eric Holscher:
At Read the Docs, we host documentation for many projects and are generally bot friendly, but the behavior of AI crawlers is currently causing us problems. We have noticed AI crawlers aggressively pulling content, seemingly without basic checks against abuse.
One crawler downloaded 73 TB of zipped HTML files just in Month, racking up $5,000 in bandwidth charges!
Link 2024-07-25 Introducing sqlite-lembed: A SQLite extension for generating text embeddings locally [ https://substack.com/redirect/bad7b139-14c4-4721-a456-f846ec4a76c7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Alex Garcia's latest SQLite extension is a C wrapper around the llama.cpp [ https://substack.com/redirect/5feb4e68-68a3-4631-ade4-941f3e84be5d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that exposes just its embedding support, allowing you to register a GGUF file containing an embedding model:
INSERT INTO temp.lembed_models(name, model)
select 'all-MiniLM-L6-v2',
lembed_model_from_file('all-MiniLM-L6-v2.e4ce9877.q8_0.gguf');

And then use it to calculate embeddings as part of a SQL query:
select lembed(
'all-MiniLM-L6-v2',
'The United States Postal Service is an independent agency...'
); -- X'A402...09C3' (1536 bytes)

all-MiniLM-L6-v2.e4ce9877.q8_0.gguf here is a 24MB file, so this should run quite happily even on machines without much available RAM.
What if you don't want to run the models locally at all? Alex has another new extension for that, described in Introducing sqlite-rembed: A SQLite extension for generating text embeddings from remote APIs [ https://substack.com/redirect/990de357-0d84-49f6-b169-0756f947a0f6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The rembed is for remote embeddings, and this extension uses Rust to call multiple remotely-hosted embeddings APIs, registered like this:
INSERT INTO temp.rembed_clients(name, options)
VALUES ('text-embedding-3-small', 'openai');
select rembed(
'text-embedding-3-small',
'The United States Postal Service is an independent agency...'
); -- X'A452...01FC', Blob

Here's the Rust code [ https://substack.com/redirect/a6291658-6e10-429b-8453-59375637d5d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that implements Rust wrapper functions for HTTP JSON APIs from OpenAI, Nomic, Cohere, Jina, Mixedbread and localhost servers provided by Ollama and Llamafile.
Both of these extensions are designed to complement Alex's sqlite-vec [ https://substack.com/redirect/2c8b6127-9e14-4f51-9974-3b64cd4b2679?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] extension, which is nearing a first stable release.
Quote 2024-07-25
Our estimate of OpenAI’s $4 billion in inference costs comes from a person with knowledge of the cluster of servers OpenAI rents from Microsoft. That cluster has the equivalent of 350,000 Nvidia A100 chips, this person said. About 290,000 of those chips, or more than 80% of the cluster, were powering ChartGPT, this person said.
Amir Efrati and Aaron Holmes [ https://substack.com/redirect/b8e43381-7d41-4503-831b-32878ccf2e06?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-07-26 Did you know about Instruments? [ https://substack.com/redirect/b6a5165b-9f8d-4134-bc33-0d0e19c08ef3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Thorsten Ball shows how the macOS Instruments app (installed as part of Xcode) can be used to run a CPU profiler against any application - not just code written in Swift/Objective C.
I tried this against a Python process running LLM [ https://substack.com/redirect/3d180546-c3c7-44b4-95dd-084c48db1f26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] executing a Llama 3.1 prompt with my new llm-gguf [ https://substack.com/redirect/c6003be4-caea-4a07-9146-f71b303d9344?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin and captured this:
Link 2024-07-26 Image resize and quality comparison [ https://substack.com/redirect/be4e8568-9fed-4f4d-958a-c4defbb8f932?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Another tiny tool I built with Claude 3.5 Sonnet and Artifacts. This one lets you select an image (or drag-drop one onto an area) and then displays that same image as a JPEG at 1, 0.9, 0.7, 0.5, 0.3 quality settings, then again but with at half the width. Each image shows its size in KB and can be downloaded directly from the page.
I'm trying to use more images on my blog (example 1 [ https://substack.com/redirect/70bd5761-93b0-4cbe-87a7-26b5164a8524?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], example 2 [ https://substack.com/redirect/7fbcde9a-2cd2-46f7-99da-47b8fded7498?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and I like to reduce their file size and quality while keeping them legible.
The prompt sequence I used for this was:
Build an artifact (no React) that I can drop an image onto and it presents that image resized to different JPEG quality levels, each with a download link
Claude produced this initial artifact [ https://substack.com/redirect/d7c85e19-c242-4511-b84b-445e30a81c1b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I followed up with:
change it so that for any image it provides it in the following:
original width, full quality
original width, 0.9 quality
original width, 0.7 quality
original width, 0.5 quality
original width, 0.3 quality
half width - same array of qualities
For each image clicking it should toggle its display to full width and then back to max-width of 80%
Images should show their size in KB
Claude produced this v2 [ https://substack.com/redirect/2ec81d69-fb5c-4941-beac-a3afe9bead8d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I tweaked it a tiny bit (modifying how full-width images are displayed) - the final source code is available here [ https://substack.com/redirect/0eb661a0-93d1-4bf1-9f8c-61ac56118aec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I'm hosting it on my own site which means the Download links work correctly - when hosted on claude.site Claude's CSP headers prevent those from functioning.
Quote 2024-07-27
Among many misunderstandings, [users] expect the RAG system to work like a search engine, not as a flawed, forgetful analyst. They will not do the work that you expect them to do in order to verify documents and ground truth. They will not expect the AI to try to persuade them.
Ethan Mollick [ https://substack.com/redirect/c74526cc-9cdd-498d-a021-d88de5301d19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-07-28
The key to understanding the pace of today’s infrastructure buildout is to recognize that while AI optimism is certainly a driver of AI CapEx, it is not the only one. The cloud players exist in a ruthless oligopoly with intense competition. [...]
Every time Microsoft escalates, Amazon is motivated to escalate to keep up. And vice versa. We are now in a cycle of competitive escalation between three of the biggest companies in the history of the world, collectively worth more than $7T. At each cycle of the escalation, there is an easy justification—we have plenty of money to afford this. With more commitment comes more confidence, and this loop becomes self-reinforcing. Supply constraints turbocharge this dynamic: If you don’t acquire land, power and labor now, someone else will.
David Cahn [ https://substack.com/redirect/53dcdfb1-5848-43de-9a83-0f05f1362411?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-07-28 CalcGPT [ https://substack.com/redirect/c0ae8d1c-d967-43a1-b75d-864471beca95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Fun satirical GPT-powered calculator demo by Calvin Liang [ https://substack.com/redirect/e39ce0b2-3f66-4897-a99e-b8cb554233a9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], originally built in July 2023. From the ChatGPT-generated artist statement:
The piece invites us to reflect on the necessity and relevance of AI in every aspect of our lives as opposed to its prevailing use as a mere marketing gimmick. With its delightful slowness and propensity for computational errors, CalcGPT elicits mirth while urging us to question our zealous indulgence in all things AI.
The source code [ https://substack.com/redirect/96acafb0-c788-4697-867c-4328ec36f186?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] shows that it's using babbage-002 [ https://substack.com/redirect/41fe052b-5739-4fb4-9435-ab5b63cb5559?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (a GPT3-era OpenAI model which I hadn't realized was still available through their API) that takes a completion-style prompt, which Calvin primes with some examples before including the user's entered expression from the calculator:
1+1=2
5-2=3
2*4=8
9/3=3
10/3=3.33333333333
${math}=

It sets \n as the stop sequence.
Link 2024-07-28 The many lives of Null Island [ https://substack.com/redirect/b33a1821-3151-40a8-962f-a42fd43c71a3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Stamen's custom basemaps have long harbored an Easter egg: zoom all the way in on 0, 0 to see the outline of the mystical "null island", the place where GIS glitches and data bugs accumulate, in the Gulf of Guinea south of Ghana.
Stamen's Alan McConchie provides a detailed history of the Easter egg - first introduced by Mike Migurski in 2010 - along with a definitive guide to the GIS jokes and traditions that surround it.
Here's Null Island on Stamen's Toner map [ https://substack.com/redirect/80872213-b5db-4283-87de-c8a50a9e5cb2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The shape (also available as GeoJSON [ https://substack.com/redirect/da12e0a8-13a3-4b48-a761-e3b0859f0cc3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) is an homage to the island from 1993's Myst [ https://substack.com/redirect/6b25476d-b32a-43d0-bf3b-8269ca14e9b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], hence the outline of a large docked ship at the bottom.
Alan recently gave a talk about Stamen's updated custom maps at State of the Map US 2024 (video [ https://substack.com/redirect/7e735b17-7c33-4c85-be57-e176395fce2a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], slides [ https://substack.com/redirect/f705e328-4023-4f7d-bdaa-2a96dfce6d26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) - their Toner and Terrain maps are now available as vector tiles served by Stadia Maps (here's the announcement [ https://substack.com/redirect/3dd30ebd-fe15-4549-ad54-b62729d3c90b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), but their iconic watercolor style is yet to be updated to vectors, due to the weird array of raster tricks it used to achieve the effect.
In researching this post I searched for null island on Google Maps [ https://substack.com/redirect/cb131196-2a8c-4f0f-99ac-63ab255c702c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and was delighted to learn that a bunch of entrepreneurs in Western Africa have tapped into the meme for their own businesses:
Link 2024-07-28 The rich history of ham radio culture [ https://substack.com/redirect/3db5ff44-e277-47a7-a940-726b063333ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This long excerpt from Kristen Haring's 2008 book Ham Radio's Technical Culture [ https://substack.com/redirect/f68ec1fc-cd9a-42e9-8b5b-0bc643485786?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] filled in so many gaps for me. I'm ham licensed in the USA (see my recent notes on passing the general exam [ https://substack.com/redirect/3b3939d3-4671-4cb6-80d6-83406387aaab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) but prior to reading this I hadn't appreciated quite how much the 100+ year history of the hobby explains the way it works today. Some ham abbreviations derive from the Phillips Code [ https://substack.com/redirect/fc8e81e8-c114-45e2-8bab-e9747861a8b2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] created in 1879!
The Hacker News thread attracted some delightful personal stories from older ham operators: "my exposure to ham radio really started in the 1970s..." [ https://substack.com/redirect/a18d5d11-a2c1-4a85-837c-65bf28aeed53?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I also liked this description [ https://substack.com/redirect/616b100d-bd54-4a44-b4f8-149ba814ccb0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of the core of the hobby:
A ham radio license is permission from your country's government to get on the air for the sake of playing with radio waves and communicating with other hams locally or around the globe without any further agenda.
I'm increasingly using the Listen to Page [ https://substack.com/redirect/d953a71a-c8a9-4e17-863d-ccffd248b674?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] feature in my iPhone's Mobile Safari to read long-form articles like this one, which means I can do household chores at the same time.
Link 2024-07-29 Everlasting jobstoppers: How an AI bot-war destroyed the online job market [ https://substack.com/redirect/a62c39f1-20e5-4b37-abfc-fb74d7fd4cfb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This story by Joe Tauke highlights several unpleasant trends from the online job directory space at the moment.
The first is "ghost jobs" - job listings that company put out which don't actually correspond to an open roll. A survey [ https://substack.com/redirect/ca842731-ea40-4a0d-8460-ed27fbf39474?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] found that this is done for a few reasons: to keep harvesting resumes for future reference, to imply that the company is successful, and then:
Perhaps the most infuriating replies came in at 39% and 33%, respectively: “The job was filled” (but the post was left online anyway to keep gathering résumés), and “No reason in particular.”
That’s right, all you go-getters out there: When you scream your 87th cover letter into the ghost-job void, there’s a one in three chance that your time was wasted for “no reason in particular.”
Another trend is "job post scraping". Plenty of job listings sites are supported by advertising, so the more content they can gather the better. This has lead to an explosion of web scraping, resulting in vast tracts of listings that were copied from other sites and likely to be out-of-date or no longer correspond to open positions.
Most worrying of all: scams.
With so much automation available, it’s become easier than ever for identity thieves to flood the employment market with their own versions of ghost jobs — not to make a real company seem like it’s growing or to make real employees feel like they’re under constant threat of being replaced, but to get practically all the personal information a victim could ever provide.
I'm not 100% convinced by the "AI bot-war" component of this headline though. The article later notes that the "ghost jobs" report it quotes was written before ChatGPT's launch in November 2022. The story ends with a flurry of examples of new AI-driven tools for both applicants and recruiters, and I've certainly heard anecdotes of LinkedIn spam that clearly has a flavour of ChatGPT to it, but I'm not convinced that the AI component is (yet) as frustration-inducing as the other patterns described above.
Link 2024-07-29 Dealing with your AI-obsessed co-worker (TikTok) [ https://substack.com/redirect/8f1abb45-8c78-485b-801e-6b0a87d2b0c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The latest in Alberta 🤖 Tech's excellent series of skits [ https://substack.com/redirect/9a688ba5-75f0-4571-8423-52b6edf89ac2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
You asked the CEO what he thinks of our project? Oh, you asked ChatGPT to pretend to be our CEO and then asked what he thought of our project. I don't think that counts.
Quote 2024-07-29
The [Apple Foundation Model] pre-training dataset consists of a diverse and high quality data mixture. This includes data we have licensed from publishers, curated publicly-available or open-sourced datasets, and publicly available information crawled by our web-crawler, Applebot. We respect the right of webpages to opt out of being crawled by Applebot, using standard robots.txt directives.
Given our focus on protecting user privacy, we note that no private Apple user data is included in the data mixture. Additionally, extensive efforts have been made to exclude profanity, unsafe material, and personally identifiable information from publicly available data (see Section 7 for more details). Rigorous decontamination is also performed against many common evaluation benchmarks.
We find that data quality, much more so than quantity, is the key determining factor of downstream model performance.
Apple Intelligence Foundation Language Models (PDF) [ https://substack.com/redirect/2547522b-68c1-4057-8588-f5473ce474c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-07-29 SAM 2: The next generation of Meta Segment Anything Model for videos and images [ https://substack.com/redirect/be4108b3-9e0c-424b-85e8-5fc8ea0aca65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Segment Anything is Meta AI's model for image segmentation: for any image or frame of video it can identify which shapes on the image represent different "objects" - things like vehicles, people, animals, tools and more.
SAM 2 "outperforms SAM on its 23 dataset zero-shot benchmark suite, while being six times faster". Notably, SAM 2 works with video where the original SAM only worked with still images. It's released under the Apache 2 license.
The best way to understand SAM 2 is to try it out. Meta have a web demo [ https://substack.com/redirect/ba3bef80-132d-4646-8a50-dee5dcd455ac?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which worked for me in Chrome but not in Firefox. I uploaded a recent video of my brand new cactus tweezers (for removing detritus from my cacti without getting spiked) and selected the succulent and the tweezers as two different objects:
Then I applied a "desaturate" filter to the background and exported this resulting video, with the background converted to black and white while the succulent and tweezers remained in full colour:
Your browser does not support the video tag.
Also released today: the full SAM 2 paper [ https://substack.com/redirect/9e8e2c7c-a35a-4e3a-9200-33ff331a11c5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the SA-V dataset [ https://substack.com/redirect/48172ed1-958c-4e80-a2bc-672b72e7aff1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of "51K diverse videos and 643K spatio-temporal segmentation masks" and a Dataset explorer tool [ https://substack.com/redirect/185d3cab-a57d-4224-a88e-7b7c4d3bccb9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (again, not supported by Firefox) for poking around in that collection.
Link 2024-07-30 Here Are All of the Apple Intelligence Features in the iOS 18.1 Developer Beta [ https://substack.com/redirect/ee3469b7-5f65-4a88-b1a2-9d6209035858?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Useful rundown from Juli Clover at MacRumors of the Apple Intelligence features that are available in the brand new iOS 18.1 beta, available to developer account holders with an iPhone 15 or iPhone 15 Pro Max or Apple Silicon iPad.
I've been trying this out today. It's still clearly very early, and the on-device model that powers Siri is significantly weaker than more powerful models that I've become used to over the past two years. Similar to old Siri I find myself trying to figure out the sparse, undocumented incantations that reliably work for the things I might want my voice assistant to do for me.
Ethan Mollick [ https://substack.com/redirect/6803dec1-9740-4562-acc6-15d7a1023de9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
My early Siri AI experience has just underlined the fact that, while there is a lot of practical, useful things that can be done with small models, they really lack the horsepower to do anything super interesting.
Link 2024-07-30 AWS CodeCommit quietly deprecated [ https://substack.com/redirect/9c51fa51-e916-413b-9cbc-150a4c94a480?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
CodeCommit is AWS's Git hosting service. In a reply from an AWS employee to this forum thread:
Beginning on 06 June 2024, AWS CodeCommit ceased onboarding new customers. Going forward, only customers who have an existing repository in AWS CodeCommit will be able to create additional repositories.
[...] If you would like to use AWS CodeCommit in a new AWS account that is part of your AWS Organization, please let us know so that we can evaluate the request for allowlisting the new account. If you would like to use an alternative to AWS CodeCommit given this news, we recommend using GitLab, GitHub, or another third party source provider of your choice.
What's weird about this is that, as far as I can tell, this is the first official public acknowledgement from AWS that CodeCommit is no longer accepting customers. The CodeCommit landing page [ https://substack.com/redirect/9bcced1d-0ba9-4b9f-8c88-dad4f5532d15?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] continues to promote the product, though it does link to the How to migrate your AWS CodeCommit repository to another Git provider [ https://substack.com/redirect/db09dea1-f2ea-4a71-b5a8-2497dd05a21d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] blog post from July 25th, which gives no direct indication that CodeCommit is being quietly sunset.
I wonder how long they'll continue to support their existing customers?
Amazon QLDB too
It looks like AWS may be having a bit of a clear-out. Amazon QLDB [ https://substack.com/redirect/1691adfc-0f0d-4c38-bf8d-e4f46131cfd5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - Quantum Ledger Database (a blockchain-adjacent immutable ledger, launched in 2019) - quietly put out a deprecation announcement in their release history on July 18th [ https://substack.com/redirect/d14c9b92-21ed-4344-a661-92bb6fad5ab5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (again, no official announcement elsewhere):
End of support notice: Existing customers will be able to use Amazon QLDB until end of support on 07/31/2025. For more details, see Migrate an Amazon QLDB Ledger to Amazon Aurora PostgreSQL [ https://substack.com/redirect/cefb19bf-0123-47ca-b46b-9d59b1a53de7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
This one is more surprising, because migrating to a different Git host is massively less work than entirely re-writing a system to use a fundamentally different database.
It turns out there's an infrequently updated community GitHub repo called SummitRoute/aws_breaking_changes [ https://substack.com/redirect/fdd05d8e-2dbe-4981-8e56-5b186eed142f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which tracks these kinds of changes. Other services listed there include CodeStar, Cloud9, CloudSearch, OpsWorks, Workdocs and Snowmobile, and they cleverly (ab)use the GitHub releases mechanism to provide an Atom feed [ https://substack.com/redirect/20f38f01-69a7-4436-85d9-ae2bec0282a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-07-30 What we got wrong about HTTP imports [ https://substack.com/redirect/514138a3-38e5-40e5-bac2-df6a89b820ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
HTTP imports are one of the most interesting design features of Deno:
import { assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";

Six years after their introduction, Ryan Dahl reviews their disadvantages:
Lengthy (non-memorable) URLs littering the codebase
A slightly cumbersome import { concat } from "../../deps.ts"; pattern for managing dependencies in one place
Large projects can end up using multiple slightly different versions of the same dependencies
If a website becomes unavailable, new builds will fail (existing builds will continue to use their cached version)
Deno 2 - due in September - will continue to support them, but will lean much more on the combination of import maps (design borrowed from modern browsers) and the Deno project's JSR [ https://substack.com/redirect/3c7d22e4-f4bb-4cee-849e-ac57e9c22567?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] npm competitor. An import map like this:
{
"imports": {
"@std/assert": "jsr:@std/assert@1"
}
}

Will then enable import statements that look like this:
import { assertEquals } from "@std/assert";

Link 2024-07-30 GPT-4o Long Output [ https://substack.com/redirect/fd92178b-03ab-40a8-b53d-febdb21401b4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
"OpenAI is offering an experimental version of GPT-4o with a maximum of 64K output tokens per request."
It's a new model (for alpha testers only) called gpt-4o-64k-output-alpha that costs $6/million input tokens and $18/million output tokens.
That's a little bit more than GPT-4o ($5/$15) and a LOT more than GPT-4o mini ($0.15/$0.60).
Long output is primarily useful for data transformation use-cases - things like translating documents from one language into another, or extracting structured data from documents where almost every input token is needed in the output JSON.
Prior to this the longest output model I knew of was GPT-4o mini, at 16,000 tokens. Most of OpenAI's competitors still cap out at around 4,000 or 8,000.
Link 2024-07-30 Making Machines Move [ https://substack.com/redirect/3b804363-9465-47b3-b11a-2c7179cfcaab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Another deep technical dive into Fly.io infrastructure from Thomas Ptacek, this time describing how they can quickly boot up an instance with a persistent volume on a new host (for things like zero-downtime deploys) using a block-level cloning operation, so the new instance gets a volume that becomes accessible instantly, serving proxied blocks of data until the new volume has been completely migrated from the old host.
Link 2024-07-30 Ralph Sheldon’s Portrait of Henry VIII Reidentified [ https://substack.com/redirect/b8e271db-170e-4f40-863c-9aeeb6fcaa69?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Here's a delightful two part story on art historian Adam Busiakiewicz's blog. Adam was browsing Twitter when he spotted this tweet [ https://substack.com/redirect/2760aa24-a8d7-485f-a87c-f79e4269ca7c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Tim Cox, Lord Lieutenant of Warwickshire, celebrating a reception.
He noticed a curve-framed painting mounted on a wall in the top left of the photo:
Adam had previously researched a similar painting while working at Sotheby's:
Seeing this round topped portrait immediately reminded me of a famous set of likenesses commissioned by the local politician and tapestry maker Ralph Sheldon (c. 1537--1613) [ https://substack.com/redirect/c2bcde8b-781a-4018-bce8-b56dce97f049?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for his home Weston House, Warwickshire, during the 1590s. Consisting of twenty-two portraits, mostly images of Kings, Queens and significant contemporary international figures, only a handful are known today.
Adam contacted Warwickshire County Council and was invited to Shire Hall. In his follow-up post [ https://substack.com/redirect/9a08b2b4-9a55-41ed-b266-a39cd5fef204?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] he describes his first-hand observations from the visit.
It turns out the painting really was one of those 22 portraits made for tapestry maker Ralph Sheldon in the 1590s, long thought lost. The discovery has now made international news:
BBC News: Missing Henry VIII portrait found after random X post [ https://substack.com/redirect/5f6ada7d-f614-4989-8968-49e136998fb1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Smithsonian Magazine: Art Historian Discovers Long-Lost Portrait of Henry VIII in Background of Social Media Post [ https://substack.com/redirect/13211399-6e3d-41e1-8edc-eb0b9cf86a1d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-07-31 Aider [ https://substack.com/redirect/aebfc63f-b17f-499f-930d-6eb7ae8113e0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Aider is an impressive open source local coding chat assistant terminal application, developed by Paul Gauthier (founding CTO of Inktomi [ https://substack.com/redirect/f94e75b9-cd78-4704-b5c3-1621495818d5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back in 1996-2000 [ https://substack.com/redirect/c265b1ba-6c52-441b-94ee-affeffcdb331?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
I tried it out today, using an Anthropic API key to run it using Claude 3.5 Sonnet:
pipx install aider-chat
export ANTHROPIC_API_KEY=api-key-here
aider --dark-mode

I found the --dark-mode flag necessary to make it legible using the macOS terminal "Pro" theme.
Aider starts by generating a concise map of files [ https://substack.com/redirect/079663f1-815e-48a8-8fb7-6a89625e06e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in your current Git repository. This is passed to the LLM along with the prompts that you type, and Aider can then request additional files be added to that context - or you can add the manually with the /add filename command.
It defaults to making modifications to files and then committing them directly to Git with a generated commit message. I found myself preferring the /ask command which lets you ask a question without making any file modifications:
The Aider documentation includes extensive examples [ https://substack.com/redirect/d5813499-653c-464f-977a-09d13d3fc047?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the tool can work with a wide range of different LLMs [ https://substack.com/redirect/92a4afdd-de54-4a92-b48d-2cee9cfa25a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], though it recommends GPT-4o, Claude 3.5 Sonnet (or 3 Opus) and DeepSeek Coder V2 for the best results. Aider maintains its own leaderboard [ https://substack.com/redirect/b06b1592-5ede-413d-b184-82f153cb2910?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], emphasizing that "Aider works best with LLMs which are good at editing code, not just good at writing code".
The prompts it uses are pretty fascinating - they're tucked away in various *_prompts.py files in aider/coders [ https://substack.com/redirect/75679cb8-e7d2-4ffd-98ca-897f7266e33e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2024-07-31
After giving it a lot of thought, we made the decision to discontinue new access to a small number of services, including AWS CodeCommit.
While we are no longer onboarding new customers to these services, there are no plans to change the features or experience you get today, including keeping them secure and reliable. [...]
The services I'm referring to are: S3 Select, CloudSearch, Cloud9, SimpleDB, Forecast, Data Pipeline, and CodeCommit.
Jeff Barr [ https://substack.com/redirect/97634df2-cc40-48d1-bdb2-aa933dfdc92b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-07-31 This month in Servo: parallel tables and more [ https://substack.com/redirect/4501f669-38a3-4358-ad79-c0b6a7c6ca54?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New in Servo:
Parallel table layout is now enabled (@mrobinson [ https://substack.com/redirect/8acc588a-2970-4a2c-8dad-203e198de93a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], #32477 [ https://substack.com/redirect/a84b5627-f46e-4208-8315-b8ea50b9edd4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]), spreading the work for laying out rows and their columns over all available CPU cores. This change is a great example of the strengths of Rayon [ https://substack.com/redirect/692080ef-b317-4ba6-b9c3-6db9ac023635?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and the opportunistic parallelism in Servo's layout engine.
The commit landing the change [ https://substack.com/redirect/cd5fc6ce-a164-4fed-a2b2-76d51b8007ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is quite short, and much of the work is done by refactoring the code to use .par_iter.enumerate.map(...) - par_iter [ https://substack.com/redirect/2a2862c1-5289-4b80-b616-bdab72566506?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is the Rayon method that allows parallel iteration over a collection using multiple threads, hence multiple CPU cores.
Link 2024-07-31 Build your own SQS or Kafka with Postgres [ https://substack.com/redirect/8c769560-655a-4284-bda0-c2d16abc58c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Anthony Accomazzo works on Sequin [ https://substack.com/redirect/20100255-4649-4338-a42f-3accafbfb9e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], an open source "message stream" (similar to Kafka) written in Elixir and Go on top of PostgreSQL.
This detailed article describes how you can implement message queue patterns on PostgreSQL from scratch, including this neat example using a CTE, returning and for update skip locked to retrieve $1 messages from the messages table and simultaneously mark them with not_visible_until set to $2 in order to "lock" them for processing by a client:
with available_messages as (
select seq
from messages
where not_visible_until is null
or (not_visible_until  a[href*='#fn'], sup > div > a[href*='#fn']

So any link with an href attribute containing #fn that is a child of a  (superscript) element.
In Drew's post the HTML looks like this:

1

This is the footnote.
&#8617;

Where did this convention come from? It doesn't seem to be part of any specific standard. Chris linked to www.bigfootjs.com (no longer resolving) which was the site for the bigfoot.js [ https://substack.com/redirect/416345d3-aaec-434a-b85a-c1ef3430a88e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] jQuery plugin, so my best guess is the convention came from that.
Link 2024-08-01 Towards Standardizing Place [ https://substack.com/redirect/53614d4c-aaa4-43cf-8d0a-1ff5b9709e95?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Overture Maps announced General Availability of its global maps datasets [ https://substack.com/redirect/2f53f2e6-39f2-4fed-ae8d-7a360bdac1b8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] last week, covering places, buildings, divisions, and base layers.
Drew Breunig demonstrates how this can be accessed using both the Overture Explorer tool [ https://substack.com/redirect/cbb1ad4e-b49c-4863-bdc4-7b09fa3eb453?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and DuckDB, and talks about Overture's GERS IDs - reminiscent of Who's On First [ https://substack.com/redirect/5006a2b1-f2c2-45ae-9adf-b4200cb46151?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] IDs - which provide stable IDs for all kinds of geographic places.
Link 2024-08-02 Extracting Prompts by Inverting LLM Outputs [ https://substack.com/redirect/06e4c01e-f8f0-4e8f-bf75-26538761f89f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New paper from Meta research:
We consider the problem of language model inversion: given outputs of a language model, we seek to extract the prompt that generated these outputs. We develop a new black-box method, output2prompt, that learns to extract prompts without access to the model's logits and without adversarial or jailbreaking queries. In contrast to previous work, output2prompt only needs outputs of normal user queries.
This is a way of extracting the hidden prompt from an application build on an LLM without using prompt injection techniques.
The trick is to train a dedicated model for guessing hidden prompts based on public question/answer pairs.
They conclude:
Our results demonstrate that many user and system prompts are intrinsically vulnerable to extraction.
This reinforces my opinion that it's not worth trying to protect your system prompts. Think of them the same as your client-side HTML and JavaScript: you might be able to obfuscate them but you should expect that people can view them if they try hard enough.
Quote 2024-08-02
When Noam and Daniel started Character.AI, our goal of personalized superintelligence required a full stack approach. We had to pre-train models, post-train them to power the experiences that make Character.AI special, and build a product platform with the ability to reach users globally. Over the past two years, however, the landscape has shifted – many more pre-trained models are now available. Given these changes, we see an advantage in making greater use of third-party LLMs alongside our own. This allows us to devote even more resources to post-training and creating new product experiences for our growing user base.
Character.AI [ https://substack.com/redirect/ec87b182-04f4-48d9-9b9d-bf70fb35c9e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-08-03 EpicEnv [ https://substack.com/redirect/86d2bfb5-3e71-48ad-822d-6ca2d2635686?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Dan Goodman's tool for managing shared secrets via a Git repository. This uses a really neat trick: you can run epicenv invite githubuser and the tool will retrieve that user's public key from github.com/{username}.keys (here's mine [ https://substack.com/redirect/0258c5db-acb2-42cc-8845-04027b215b65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) and use that to encrypt the secrets such that the user can decrypt them with their private key.
Quote 2024-08-03
I think the mistake the industry has made is (and I had to learn this as well), that "we observed ab tests work really well" is really a statement that should read "the majority of the changes we make are characterized as hill-climbing growth of a post-PMF b2c product and ab tests work really well for that".
Malte Ubl [ https://substack.com/redirect/2a30ce82-4d00-4276-bd65-84c107611e51?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-08-03
[On release notes] in our partial defense, training these models can be more discovery than invention. often we don't exactly know what will come out.
we've long wanted to do release notes that describe each model's differences, but we also don't want to give false confidence with a shallow story.
Ted Sanders (OpenAI) [ https://substack.com/redirect/a6f9b28e-82e6-46c8-b3bc-643bd90d1d0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-08-04 How I Use "AI" by Nicholas Carlini [ https://substack.com/redirect/b3a588fc-7b85-4250-863b-f2b2e739038c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Nicholas is an author on Universal and Transferable Adversarial Attacks on Aligned Language Models [ https://substack.com/redirect/ac13ac45-4a97-4125-8f29-f302467645f3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], one of my favorite LLM security papers from last year. He understands the flaws in this class of technology at a deeper level than most people.
Despite that, this article describes several of the many ways he still finds utility in these models in his own work:
But the reason I think that the recent advances we've made aren't just hype is that, over the past year, I have spent at least a few hours every week interacting with various large language models, and have been consistently impressed by their ability to solve increasingly difficult tasks I give them. And as a result of this, I would say I'm at least 50% faster at writing code for both my research projects and my side projects as a result of these models.
The way Nicholas is using these models closely matches my own experience - things like “Automating nearly every monotonous task or one-off script” and “Teaching me how to use various frameworks having never previously used them”.
I feel that this piece inadvertently captures the frustration felt by those of us who get value out of these tools on a daily basis and still constantly encounter people who are adamant that they offer no real value. Saying “this stuff is genuine useful” remains a surprisingly controversial statement, almost two years after the ChatGPT launch opened up LLMs to a giant audience.
I also enjoyed this footnote explaining why he put “AI” in scare quotes in the title:
I hate this word. It's not AI. But I want people who use this word, and also people who hate this word, to find this post. And so I guess I'm stuck with it for marketing, SEO, and clickbait.
Link 2024-08-04 What do people really ask chatbots? It’s a lot of sex and homework [ https://substack.com/redirect/2e17bf56-838a-4f70-aac7-a0b66217ee99?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Jeremy B. Merrill and Rachel Lerman at the Washington Post analyzed WildChat [ https://substack.com/redirect/f4d27f8f-c000-4cfa-8782-9523ee87c68d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a dataset of 1 million ChatGPT-style interactions collected and released by the Allen Institute for AI.
From a random sample of 458 queries they categorized the conversations as 21% creative writing and roleplay, 18% homework help, 17% "search and other inquiries", 15% work/business and 7% coding.
I talked to them a little for this story:
“I don’t think I’ve ever seen a piece of technology that has this many use cases,” said Simon Willison, a programmer and independent researcher.
Link 2024-08-04 There’s a Tool to Catch Students Cheating With ChatGPT. OpenAI Hasn’t Released It. [ https://substack.com/redirect/62542360-decf-4d73-8bf8-83fed6f6cd68?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This attention-grabbing headline from the Wall Street Journal makes the underlying issue here sound less complex, but there's a lot more depth to it.
The story is actually about watermarking: embedding hidden patterns in generated text that allow that text to be identified as having come out of a specific LLM.
OpenAI evidently have had working prototypes of this for a couple of years now, but they haven't shipped it as a feature. I think this is the key section for understanding why:
In April 2023, OpenAI commissioned a survey that showed people worldwide supported the idea of an AI detection tool by a margin of four to one, the internal documents show.
That same month, OpenAI surveyed ChatGPT users and found 69% believe cheating detection technology would lead to false accusations of using AI. Nearly 30% said they would use ChatGPT less if it deployed watermarks and a rival didn’t.
If ChatGPT was the only LLM tool, watermarking might make sense. The problem today is that there are now multiple vendors offering highly capable LLMs. If someone is determined to cheat they have multiple options for LLMs that don't watermark.
This means adding watermarking is both ineffective and a competitive disadvantage for those vendors!
Quote 2024-08-05
[On WebGPU in Firefox] There is a lot of work to do still to make sure we comply with the spec. in a way that's acceptable to ship in a browser. We're 90% of the way there in terms of functionality, but the last 10% of fixing up spec. changes in the last few years + being significantly more resourced-constrained (we have 3 full-time folks, Chrome has/had an order of magnitude more humans working on WebGPU) means we've got our work cut out for us. We're hoping to ship sometime in the next year, but I won't make promises here.
Erich Gubler [ https://substack.com/redirect/5f75ccc8-af8f-4563-b483-c9ccc5cc8238?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-08-05 How to Get or Create in PostgreSQL [ https://substack.com/redirect/ea709526-807a-47bd-b113-33ea2cf113cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Get or create - for example to retrieve an existing tag record from a database table if it already exists or insert it if it doesn’t - is a surprisingly difficult operation.
Haki Benita uses it to illustrate a variety of interesting PostgreSQL concepts.
New to me: a pattern that runs INSERT INTO tags (name) VALUES (tag_name) RETURNING *; and then catches the constraint violation and returns a record instead has a disadvantage at scale: “The table contains a dead tuple for every attempt to insert a tag that already existed” - so until vacuum runs you can end up with significant table bloat!
Haki’s conclusion is that the best solution relies on an upcoming feature coming in PostgreSQL 17 [ https://substack.com/redirect/7f5b4999-5c65-4dbc-a8d0-c082fc80a56b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: the ability to combine the MERGE operation [ https://substack.com/redirect/d8b98367-ad46-4e20-93fc-87fc42f80e90?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with a RETURNING clause:
WITH new_tags AS (
MERGE INTO tags
USING (VALUES ('B'), ('C')) AS t(name)
ON tags.name = t.name
WHEN NOT MATCHED THEN
INSERT (name) VALUES (t.name)
RETURNING *
)
SELECT * FROM tags WHERE name IN ('B', 'C')
UNION ALL
SELECT * FROM new_tags;

I wonder what the best pattern for this in SQLite is. Could it be as simple as this?
INSERT OR IGNORE INTO tags (name) VALUES ('B'), ('C');

The SQLite INSERT documentation [ https://substack.com/redirect/7bba725d-4faa-43d2-bf64-27c9ab2c8316?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] doesn't currently provide extensive details for INSERT OR IGNORE, but there are some hints in this forum thread [ https://substack.com/redirect/d602d313-fc00-4e41-8cf3-2d68b74bfa3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. This post [ https://substack.com/redirect/3c40f8c2-64b6-40e7-9072-17586f6ae08e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by Rob Hoelz points out that INSERT OR IGNORE will silently ignore any constraint violation, so INSERT INTO tags (tag) VALUES ('C'), ('D') ON CONFLICT(tag) DO NOTHING may be a better option.
Link 2024-08-05 Leaked Documents Show Nvidia Scraping ‘A Human Lifetime’ of Videos Per Day to Train AI [ https://substack.com/redirect/e9c1ee98-a399-4072-9e52-d96963c67759?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Samantha Cole at 404 Media reports on a huge leak of internal NVIDIA communications - mainly from a Slack channel - revealing details of how they have been collecting video training data for a new video foundation model called Cosmos. The data is mostly from YouTube, downloaded via yt-dlp using a rotating set of AWS IP addresses and consisting of millions (maybe even hundreds of millions) of videos.
The fact that companies scrape unlicensed data to train models isn't at all surprising. This article still provides a fascinating insight into what model training teams care about, with details like this from a project update via email:
As we measure against our desired distribution focus for the next week remains on cinematic, drone footage, egocentric, some travel and nature.
Or this from Slack:
Movies are actually a good source of data to get gaming-like 3D consistency and fictional content but much higher quality.
My intuition here is that the backlash against scraped video data will be even more intense than for static images used to train generative image models. Video is generally more expensive to create, and video creators (such as Marques Brownlee / MKBHD, who is mentioned in a Slack message here as a potential source of "tech product neviews - super high quality") have a lot of influence.
There was considerable uproar [ https://substack.com/redirect/4eb7f969-4b57-4002-b4fb-b73a4d96063b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] a few weeks ago over this story [ https://substack.com/redirect/366e288e-c848-4d05-8eec-b16282a219ee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about training against just captions scraped from YouTube, and now we have a much bigger story involving the actual video contint itself.
TIL 2024-08-05 Assistance with release notes using GitHub Issues [ https://substack.com/redirect/2e050e60-d960-4f12-b480-9620c81198a5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I like to write the release notes for my projects by hand, but sometimes it can be useful to have some help along the way. …

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hORGN6T1RFME5EY3NJbWxoZENJNk1UY3lNamt3TVRFMk55d2laWGh3SWpveE56VTBORE0zTVRZM0xDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuS2I1UmYtN1RjR0w3YUhJSVFuNnNscTd3SzdVTE8xTlhDaGRtZzRnNk42RSIsInAiOjE0NzM5MTQ0NywicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzIyOTAxMTY3LCJleHAiOjE3MjU0OTMxNjcsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.R4ucaWpTwHE8vZeX3FTeB4S-50Th6W0HyPUtp17EpvE?
