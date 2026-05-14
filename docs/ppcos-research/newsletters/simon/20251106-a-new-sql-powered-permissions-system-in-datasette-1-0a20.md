# A new SQL-powered permissions system in Datasette 1.0a20

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-11-06T01:19:04.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/a-new-sql-powered-permissions-system

In this newsletter:
A new SQL-powered permissions system in Datasette 1.0a20
Plus 6 links and 4 quotations
If you find this newsletter useful, please consider sponsoring me via GitHub [ https://substack.com/redirect/c1f6864e-d5d3-4c17-af6f-b6ad0d4a3c19?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. $10/month and higher sponsors get a monthly newletter with my summary of the most important trends of the past 30 days - here are previews from August [ https://substack.com/redirect/0614fa8f-c469-4b93-b6e5-a209c29f9673?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and September [ https://substack.com/redirect/28227f24-7155-41e9-bcd0-8df9f91c0dab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
A new SQL-powered permissions system in Datasette 1.0a20 [ https://substack.com/redirect/3bd303ae-bea0-4907-9945-384c4b9e4948?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-11-04
Datasette 1.0a20 is out [ https://substack.com/redirect/dff29629-f4b5-4fa2-9ac6-697ab821405e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with the biggest breaking API change on the road to 1.0, improving how Datasette’s permissions system works by migrating permission logic to SQL running in SQLite. This release involved 163 commits [ https://substack.com/redirect/70eb5c53-2622-4bba-955c-6a90ea599681?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], with 10,660 additions and 1,825 deletions, most of which was written with the help of Claude Code.
Understanding the permissions system [ https://substack.com/redirect/2f3b0aa1-be2c-4119-aafb-797b8935ad22?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Permissions systems need to be able to efficiently list things [ https://substack.com/redirect/755585df-62dd-469d-8401-fd20bc238214?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The new permission_resources_sql() plugin hook [ https://substack.com/redirect/c1990b54-d038-4ddd-ad0f-1d1ad73a6790?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Hierarchies, plugins, vetoes, and restrictions [ https://substack.com/redirect/faab93b2-7971-46ce-9f15-ce16d97b2c73?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
New debugging tools [ https://substack.com/redirect/afc8528b-f02e-4e47-9c8b-6d521d5b5c4a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The missing feature: list actors who can act on this resource [ https://substack.com/redirect/288ad197-affe-4fc5-88af-302c192cd708?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Upgrading plugins for Datasette 1.0a20 [ https://substack.com/redirect/12768677-7d4e-4033-bbab-309ae349b27b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Using Claude Code to implement this change [ https://substack.com/redirect/f95c7857-5451-4907-a706-69d23c1d971c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Starting with a proof-of-concept [ https://substack.com/redirect/400193ab-1604-4eb3-bc6b-1e9f1307e922?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Miscellaneous tips I picked up along the way [ https://substack.com/redirect/1c7aa802-542e-42d5-93c6-61f4cd2f8035?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
What’s next? [ https://substack.com/redirect/f050abea-d145-4816-92ec-1558fe514678?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Understanding the permissions system
Datasette’s permissions system [ https://substack.com/redirect/3df384a0-34dd-4869-95f0-cf119d235918?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] exists to answer the following question:
Is this actor allowed to perform this action, optionally against this particular resource?
An actor is usually a user, but might also be an automation operating via the Datasette API.
An action is a thing they need to do - things like view-table, execute-sql, insert-row.
A resource is the subject of the action - the database you are executing SQL against, the table you want to insert a row into.
Datasette’s default configuration is public but read-only: anyone can view databases and tables or execute read-only SQL queries but no-one can modify data.
Datasette plugins can enable all sorts of additional ways to interact with databases, many of which need to be protected by a form of authentication Datasette also 1.0 includes a write API [ https://substack.com/redirect/b5d91c0a-f77c-43cf-8685-aa77e97a6639?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with a need to configure who can insert, update, and delete rows or create new tables.
Actors can be authenticated in a number of different ways provided by plugins using the actor_from_request() [ https://substack.com/redirect/06956609-122a-42ff-8023-04de3ea958eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin hook. datasette-auth-passwords [ https://substack.com/redirect/3e610d59-faa9-40b9-8576-847d11c505e9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and datasette-auth-github [ https://substack.com/redirect/116650a6-42c4-4565-9c4b-fdb9abafb692?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and datasette-auth-existing-cookies [ https://substack.com/redirect/fe436068-ef47-4fd9-a5d6-9634e39dba23?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] are examples of authentication plugins.
Permissions systems need to be able to efficiently list things
The previous implementation included a design flaw common to permissions systems of this nature: each permission check involved a function call which would delegate to one or more plugins and return a True/False result.
This works well for single checks, but has a significant problem: what if you need to show the user a list of things they can access, for example the tables they can view?
I want Datasette to be able to handle potentially thousands of tables - tables in SQLite are cheap! I don’t want to have to run 1,000+ permission checks just to show the user a list of tables.
Since Datasette is built on top of SQLite we already have a powerful mechanism to help solve this problem. SQLite is really good at filtering large numbers of records.
The new permission_resources_sql() plugin hook
The biggest change in the new release is that I’ve replaced the previous permission_allowed(actor, action, resource)plugin hook - which let a plugin determine if an actor could perform an action against a resource - with a new permission_resources_sql(actor, action) [ https://substack.com/redirect/1d9e5f8b-b55f-42f8-9b6d-cd7f9a448250?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin hook.
Instead of returning a True/False result, this new hook returns a SQL query that returns rules helping determine the resources the current actor can execute the specified action against.
Here’s an example, lifted from the documentation:
from datasette import hookimpl
from datasette.permissions import PermissionSQL
@hookimpl
def permission_resources_sql(datasette, actor, action):
if action != “view-table”:
return None
if not actor or actor.get(”id”) != “alice”:
return None

return PermissionSQL(
sql=”“”
SELECT
‘accounting’ AS parent,
‘sales’ AS child,
1 AS allow,
‘alice can view accounting/sales’ AS reason
“”“,
)
This hook grants the actor with ID “alice” permission to view the “sales” table in the “accounting” database.
The PermissionSQL object should always return four columns: a parent, child, allow (1 or 0), and a reason string for debugging.
When you ask Datasette to list the resources an actor can access for a specific action, it will combine the SQL returned by all installed plugins into a single query that joins against the internal catalog tables [ https://substack.com/redirect/18514d93-87aa-450e-a712-6f24709db6e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and efficiently lists all the resources the actor can access.
This query can then be limited or paginated to avoid loading too many results at once.
Hierarchies, plugins, vetoes, and restrictions
Datasette has several additional requirements that make the permissions system more complicated.
Datasette permissions can optionally act against a two-level hierarchy. You can grant a user the ability to insert-row against a specific table, or every table in a specific database, or every table in every database in that Datasette instance.
Some actions can apply at the table level, others the database level and others only make sense globally - enabling a new feature that isn’t tied to tables or databases, for example.
Datasette currently has ten default actions [ https://substack.com/redirect/744112d0-e863-49b0-81d1-071f0a542423?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] but plugins that add additional features can register new actions [ https://substack.com/redirect/6c4d8ba9-a032-4516-a182-c67cd87d75ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to better participate in the permission systems.
Datasette’s permission system has a mechanism to veto permission checks - a plugin can return a deny for a specific permission check which will override any allows. This needs to be hierarchy-aware - a deny at the database level can be outvoted by an allow at the table level.
Finally, Datasette includes a mechanism for applying additional restrictions to a request. This was introduced for Datasette’s API - it allows a user to create an API token that can act on their behalf but is only allowed to perform a subset of their capabilities - just reading from two specific tables, for example. Restrictions are described in more detail [ https://substack.com/redirect/0c6c4520-e174-4c8b-a153-97b68e5ec192?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the documentation.
That’s a lot of different moving parts for the new implementation to cover.
New debugging tools
Since permissions are critical to the security of a Datasette deployment it’s vital that they are as easy to understand and debug as possible.
The new alpha adds several new debugging tools, including this page that shows the full list of resources matching a specific action for the current user:
And this page listing the rules that apply to that question - since different plugins may return different rules which get combined together:
This screenshot illustrates two of Datasette’s built-in rules: there is a default allow for read-only operations such as view-table (which can be over-ridden by plugins) and another rule that says the root user can do anything (provided Datasette was started with the --root option.)
Those rules are defined in the datasette/default_permissions.py [ https://substack.com/redirect/52996231-ef8c-4098-a8fc-6f7a2e688a8a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Python module.
The missing feature: list actors who can act on this resource
There’s one question that the new system cannot answer: provide a full list of actors who can perform this action against this resource.
It’s not possibly to provide this globally for Datasette because Datasette doesn’t have a way to track what “actors” exist in the system. SSO plugins such as datasette-auth-github mean a new authenticated GitHub user might show up at any time, with the ability to perform actions despite the Datasette system never having encountered that particular username before.
API tokens and actor restrictions come into play here as well. A user might create a signed API token that can perform a subset of actions on their behalf - the existence of that token can’t be predicted by the permissions system.
This is a notable omission, but it’s also quite common in other systems. AWS cannot provide a list of all actors who have permission to access a specific S3 bucket, for example - presumably for similar reasons.
Upgrading plugins for Datasette 1.0a20
Datasette’s plugin ecosystem is the reason I’m paying so much attention to ensuring Datasette 1.0 has a stable API. I don’t want plugin authors to need to chase breaking changes once that 1.0 release is out.
The Datasette upgrade guide [ https://substack.com/redirect/61990b60-c5a5-4c2f-adad-a099951f5db9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] includes detailed notes on upgrades that are needed between the 0.x and 1.0 alpha releases. I’ve added an extensive section about the permissions changes to that document.
I’ve also been experimenting with dumping those instructions directly into coding agent tools - Claude Code and Codex CLI - to have them upgrade existing plugins for me. This has been working extremely well. I’ve even had Claude Code update those notes itself [ https://substack.com/redirect/fd8d4a77-e4c7-43bf-a453-3f27ea773eda?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with things it learned during an upgrade process!
This is greatly helped by the fact that every single Datasette plugin has an automated test suite that demonstrates the core functionality works as expected. Coding agents can use those tests to verify that their changes have had the desired effect.
I’ve also been leaning heavily on uv to help with the upgrade process. I wrote myself two new helper scripts - tadd and radd - to help test the new plugins.
tadd = “test against datasette dev” - it runs a plugin’s existing test suite against the current development version of Datasette checked out on my machine. It passes extra options through to pytest so I can run tadd -k test_name or tadd -x --pdb as needed.
radd = “run against datasette dev” - it runs the latest dev datasette command with the plugin installed.
The tadd and radd implementations can be found in this TIL [ https://substack.com/redirect/1bcf4a67-5603-45ca-b697-eb7bd7fde6ad?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Some of my plugin upgrades have become a one-liner to the codex exec command, which runs OpenAI Codex CLI with a prompt without entering interactive mode:
codex exec --dangerously-bypass-approvals-and-sandbox \
“Run the command tadd and look at the errors and then
read ~/dev/datasette/docs/upgrade-1.0a20.md and apply
fixes and run the tests again and get them to pass”
There are still a bunch more to go - there’s a list in this tracking issue [ https://substack.com/redirect/680badd6-b5bd-43f5-8511-e26cef5d511b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - but I expect to have the plugins I maintain all upgraded pretty quickly now that I have a solid process in place.
Using Claude Code to implement this change
This change to Datasette core by far the most ambitious piece of work I’ve ever attempted using a coding agent.
Last year I agreed with the prevailing opinion that LLM assistance was much more useful for greenfield coding tasks than working on existing codebases. The amount you could usefully get done was greatly limited by the need to fit the entire codebase into the model’s context window.
Coding agents have entirely changed that calculation. Claude Code and Codex CLI still have relatively limited token windows - albeit larger than last year - but their ability to search through the codebase, read extra files on demand and “reason” about the code they are working with has made them vastly more capable.
I no longer see codebase size as a limiting factor for how useful they can be.
I’ve also spent enough time with Claude Sonnet 4.5 to build a weird level of trust in it. I can usually predict exactly what changes it will make for a prompt. If I tell it “extract this code into a separate function” or “update every instance of this pattern” I know it’s likely to get it right.
For something like permission code I still review everything it does, often by watching it as it works since it displays diffs in the UI.
I also pay extremely close attention to the tests it’s writing. Datasette 1.0a19 already had 1,439 tests, many of which exercised the existing permission system. 1.0a20 increases that to 1,583 tests. I feel very good about that, especially since most of the existing tests continued to pass without modification.
Starting with a proof-of-concept
I built several different proof-of-concept implementations of SQL permissions before settling on the final design. My research/sqlite-permissions-poc [ https://substack.com/redirect/a16d7ec3-0255-4616-a537-6f3aaff751e4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project was the one that finally convinced me of a viable approach,
That one started as a free ranging conversation with Claude [ https://substack.com/redirect/8b902727-4f21-41be-8b76-9190224a73fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], at the end of which I told it to generate a specification which I then fed into GPT-5 [ https://substack.com/redirect/7ff55a80-6035-4567-9970-cb7eddae7601?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to implement. You can see that specification at the end of the README [ https://substack.com/redirect/018914d8-f1cc-4629-ab1f-1acd6dcdb7ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I later fed the POC itself into Claude Code and had it implement the first version of the new Datasette system based on that previous experiment.
This is admittedly a very weird way of working, but it helped me finally break through on a problem that I’d been struggling with for months.
Miscellaneous tips I picked up along the way
When working on anything relating to plugins it’s vital to have at least a few real plugins that you upgrade in lock-step with the core changes. The tadd and radd shortcuts were invaluable for productively working on those plugins while I made changes to core.
Coding agents make experiments muchcheaper. I threw away so much code on the way to the final implementation, which was psychologically easier because the cost to create that code in the first place was so low.
Tests, tests, tests. This project would have been impossible without that existing test suite. The additional tests we built along the way give me confidence that the new system is as robust as I need it to be.
Claude writes good commit messages now! I finally gave in and let it write these - previously I’ve been determined to write them myself. It’s a big time saver to be able to say “write a tasteful commit message for these changes”.
Claude is also great at breaking up changes into smaller commits. It can also productively rewrite history to make it easier to follow, especially useful if you’re still working in a branch.
A really great way to review Claude’s changes is with the GitHub PR interface. You can attach comments to individual lines of code and then later prompt Claude like this: Use gh CLI to fetch comments on URL-to-PR and make the requested changes. This is a very quick way to apply little nitpick changes - rename this function, refactor this repeated code, add types here etc.
The code I write with LLMs is higher quality code. I usually find myself making constant trade-offs while coding: this function would be neater if I extracted this helper, it would be nice to have inline documentation here, this changing this would be good but would break a dozen tests... for each of those I have to determine if the additional time is worth the benefit. Claude can apply changes so much faster than me that these calculations have changed - almost any improvement is worth applying, no matter how trivial, because the time cost is so low.
Internal tools are cheap now. The new debugging interfaces were mostly written by Claude and are significantly nicer to use and look at than the hacky versions I would have knocked out myself, if I had even taken the extra time to build them.
That trick with a Markdown file full of upgrade instructions works astonishingly well - it’s the same basic idea as Claude Skills [ https://substack.com/redirect/b1b7642b-a85e-48e6-90d9-27818168ea0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I maintain over 100 Datasette plugins now and I expect I’ll be automating all sorts of minor upgrades in the future using this technique.
What’s next?
Now that the new alpha is out my focus is upgrading the existing plugin ecosystem to use it, and supporting other plugin authors who are doing the same.
The new permissions system unlocks some key improvements to Datasette Cloud concerning finely-grained permissions for larger teams, so I’ll be integrating the new alpha there this week.
This is the single biggest backwards-incompatible change required before Datasette 1.0. I plan to apply the lessons I learned from this project to the other, less intimidating changes. I’m hoping this can result in a final 1.0 release before the end of the year!
quote 2025-11-03
Interleaved thinking is essential for LLM agents: it means alternating between explicit reasoning and tool use, while carrying that reasoning forward between steps.This process significantly enhances planning, self‑correction, and reliability in long workflows. [...]
From community feedback, we’ve often observed failures to preserve prior-round thinking state across multi-turn interactions with M2. The root cause is that the widely-used OpenAI Chat Completion API does not support passing reasoning content back in subsequent requests. Although the Anthropic API natively supports this capability, the community has provided less support for models beyond Claude, and many applications still omit passing back the previous turns’ thinking in their Anthropic API implementations. This situation has resulted in poor support for Interleaved Thinking for new models. To fully unlock M2’s capabilities, preserving the reasoning process across multi-turn interactions is essential.
MiniMax [ https://substack.com/redirect/97a18ffd-ca73-4a37-b5e0-10b8f813901c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Interleaved Thinking Unlocks Reliable MiniMax-M2 Agentic Capability
Link 2025-11-03 The case against pgvector [ https://substack.com/redirect/f923fdf6-ec3c-48af-8bc2-8ac37aa8e449?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wasn’t keen on the title of this piece but the content is great: Alex Jacobs talks through lessons learned trying to run the popular pgvector PostgreSQL vector indexing extension at scale, in particular the challenges involved in maintaining a large index with close-to-realtime updates using the IVFFlat or HNSW index types.
The section on pre-v.s.-post filtering is particularly useful:
Okay but let’s say you solve your index and insert problems. Now you have a document search system with millions of vectors. Documents have metadata---maybe they’re marked as draft, published, or archived. A user searches for something, and you only want to return published documents.
[...] should Postgres filter on status first (pre-filter) or do the vector search first and then filter (post-filter)?
This seems like an implementation detail. It’s not. It’s the difference between queries that take 50ms and queries that take 5 seconds. It’s also the difference between returning the most relevant results and… not.
The Hacker News thread [ https://substack.com/redirect/2b283c77-80d1-452c-b2c3-ac7550636ff9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for this article attracted a robust discussion, including some fascinating comments by Discourse developer Rafael dos Santos Silva (xfalcox) about how they are using pgvector at scale:
We [run pgvector in production] at Discourse, in thousands of databases, and it’s leveraged in most of the billions of page views we serve. [...]
Also worth mentioning that we use quantization extensively:
halfvec (16bit float) for storage - bit (binary vectors) for indexes
Which makes the storage cost and on-going performance good enough that we could enable this in all our hosting. [...]
In Discourse embeddings power:
Related Topics, a list of topics to read next, which uses embeddings of the current topic as the key to search for similar ones
Suggesting tags and categories when composing a new topic
Augmented search
RAG for uploaded files
quote 2025-11-03
Dear PEP 810 authors. The Steering Council is happy to unanimously accept “PEP 810, Explicit lazy imports [ https://substack.com/redirect/57f56827-5328-4f2b-81af-a6692077a461?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]“. Congratulations! We appreciate the way you were able to build on and improve the previously discussed (and rejected) attempt at lazy imports as proposed in PEP 690 [ https://substack.com/redirect/e2e79b46-b10e-4c85-af52-d0c07e5caaee?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Barry Warsaw [ https://substack.com/redirect/e63fd207-0fc0-44a9-968e-dd8fba537a94?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], on behalf of the Python Steering Council
Link 2025-11-03 The fetch()ening [ https://substack.com/redirect/791e6b9a-b571-4375-aae5-6dcca3447411?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
After several years of stable htmx 2.0 and a promise to never release a backwards-incompatible htmx 3 Carson Gross is technically keeping that promise... by skipping to htmx 4 instead!
The main reason is to replace XMLHttpRequestwith fetch() - a change that will have enough knock-on compatibility effects to require a major version bump - so they’re using that as an excuse to clean up various other accumulated design warts at the same time.
htmx is a very responsibly run project. Here’s their plan for the upgrade:
That said, htmx 2.0 users will face an upgrade project when moving to 4.0 in a way that they did not have to in moving from 1.0 to 2.0.
I am sorry about that, and want to offer three things to address it:
htmx 2.0 (like htmx 1.0 & intercooler.js 1.0) will be supported in perpetuity, so there is absolutely no pressure to upgrade your application: if htmx 2.0 is satisfying your hypermedia needs, you can stick with it.
We will create extensions that revert htmx 4 to htmx 2 behaviors as much as is feasible (e.g. Supporting the old implicit attribute inheritance model, at least)
We will roll htmx 4.0 out slowly, over a multi-year period. As with the htmx 1.0 -> 2.0 upgrade, there will be a long period where htmx 2.x is latest and htmx 4.x is next
There are lots of neat details in here about the design changes they plan to make. It’s a really great piece of technical writing - I learned a bunch about htmx and picked up some good notes on API design in general from this.
quote 2025-11-04
Every time an engineer evaluates a language that isn’t “theirs,” their brain is literally working against them. They’re not just analyzing technical trade offs, they’re contemplating a version of themselves that doesn’t exist yet, that feels threatening to the version that does. The Python developer reads case studies about Go’s performance and their amygdala quietly marks each one as a threat to be neutralized. The Rust advocate looks at identical problems and their Default Mode Network constructs narratives about why “only” Rust can solve them.
We’re not lying. We genuinely believe our reasoning is sound. That’s what makes identity based thinking so expensive, and so invisible.
Steve Francia [ https://substack.com/redirect/82e28dde-5531-426f-a455-fad2f39ce913?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Why Engineers Can’t Be Rational About Programming Languages
Link 2025-11-04 MCP Colors: Systematically deal with prompt injection risk [ https://substack.com/redirect/23e47b73-1a28-4c33-bcac-d3d7eca7acb1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Tim Kellogg proposes a neat way to think about prompt injection, especially with respect to MCP tools.
Classify every tool with a color: red if it exposes the agent to untrusted (potentially malicious) instructions, blue if it involves a “critical action” - something you would not want an attacker to be able to trigger.
This means you can configure your agent to actively avoid mixing the two colors at once:
The Chore: Go label every data input, and every tool (especially MCP tools). For MCP tools & resources, you can use the _meta object to keep track of the color. The agent can decide at runtime (or earlier) if it’s gotten into an unsafe state.
Personally, I like to automate. I needed to label ~200 tools, so I put them in a spreadsheet and used an LLM to label them. That way, I could focus on being precise and clear about my criteria for what constitutes “red”, “blue” or “neither”. That way I ended up with an artifact that scales beyond my initial set of tools.
Link 2025-11-04 Code execution with MCP: Building more efficient agents [ https://substack.com/redirect/07ddf54d-ed86-490a-9f78-86dae2e0f390?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
When I wrote about Claude Skills [ https://substack.com/redirect/b1b7642b-a85e-48e6-90d9-27818168ea0f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I mentioned that I don’t use MCP at all any more when working with coding agents - I find CLI utilities and libraries like Playwright Python to be a more effective way of achieving the same goals.
This new piece from Anthropic proposes a way to bring the two worlds more closely together.
It identifies two challenges with MCP as it exists today. The first has been widely discussed before: all of those tool descriptions take up a lot of valuable real estate in the agent context even before you start using them.
The second is more subtle but equally interesting: chaining multiple MCP tools together involves passing their responses through the context, absorbing more valuable tokens and introducing chances for the LLM to make additional mistakes.
What if you could turn MCP tools into code functions instead, and then let the LLM wire them together with executable code?
Anthropic’s example here imagines a system that turns MCP tools into TypeScript files on disk, looking something like this:
// ./servers/google-drive/getDocument.ts
interface GetDocumentInput {
documentId: string;
}
interface GetDocumentResponse {
content: string;
}
/ Read a document from Google Drive /
export async function getDocument(input: GetDocumentInput): Promise {
return callMCPTool(’google_drive__get_document’, input);
}
This takes up no tokens at all - it’s a file on disk. In a similar manner to Skills the agent can navigate the filesystem to discover these definitions on demand.
Then it can wire them together by generating code:
const transcript = (await gdrive.getDocument({ documentId: ‘abc123’ })).content;
await salesforce.updateRecord({
objectType: ‘SalesMeeting’,
recordId: ‘00Q5f000001abcXYZ’,
data: { Notes: transcript }
});
Notably, the example here avoids round-tripping the response from the gdrive.getDocument() call through the model on the way to the salesforce.updateRecord() call - which is faster, more reliable, saves on context tokens, and avoids the model being exposed to any potentially sensitive data in that document.
This all looks very solid to me! I think it’s a sensible way to take advantage of the strengths of coding agents and address some of the major drawbacks of MCP as it is usually implemented today.
There’s one catch: Anthropic outline the proposal in some detail but provide no code to execute on it! Implementation is left as an exercise for the reader:
If you implement this approach, we encourage you to share your findings with the MCP community [ https://substack.com/redirect/83ccd524-62d3-4694-acad-f4d2e365bedc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
quote 2025-11-05
I’m worried that they put co-pilot in Excel because Excel is the beast that drives our entire economy and do you know who has tamed that beast?
Brenda.
Who is Brenda?
She is a mid-level employee in every finance department, in every business across this stupid nation and the Excel goddess herself descended from the heavens, kissed Brenda on her forehead and the sweat from Brenda’s brow is what allows us to do capitalism. [...]
She’s gonna birth that formula for a financial report and then she’s gonna send that financial report to a higher up and he’s gonna need to make a change to the report and normally he would have sent it back to Brenda but he’s like oh I have AI and AI is probably like smarter than Brenda and then the AI is gonna fuck it up real bad and he won’t be able to recognize it because he doesn’t understand Excel because AI hallucinates.
You know who’s not hallucinating?
Brenda.
Ada James [ https://substack.com/redirect/6975dada-245b-46e2-81ee-15cba183b5b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], @belligerentbarbies on TikTok
Link 2025-11-05 Removing XSLT for a more secure browser [ https://substack.com/redirect/ad088edd-5650-4024-ad26-c5578c6a7348?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Previously discussed back in August [ https://substack.com/redirect/5195e953-cd94-4d24-99b3-f40593d86885?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], it looks like it’s now official:
Chrome intends to deprecate and remove XSLT from the browser. [...] We intend to remove support from version 155 (November 17, 2026). The Firefox [ https://substack.com/redirect/f0919b4d-ffae-4e84-9e04-4b8fbeccb34e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and WebKit [ https://substack.com/redirect/15f2283d-4135-4cf2-8e77-b46ad0cc7184?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] projects have also indicated plans to remove XSLT from their browser engines. [...]
The continued inclusion of XSLT 1.0 in web browsers presents a significant and unnecessary security risk. The underlying libraries that process these transformations, such as libxslt [ https://substack.com/redirect/36f8c8e6-602d-4c27-b997-f4ff137a59c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (used by Chromium browsers), are complex, aging C/C++ codebases. This type of code is notoriously susceptible to memory safety vulnerabilities like buffer overflows, which can lead to arbitrary code execution.
I mostly encounter XSLT on people’s Atom/RSS feeds, converting those to a more readable format in case someone should navigate directly to that link. Jake Archibald shared an alternative solution to that [ https://substack.com/redirect/8047e01c-c599-4ae4-bda5-9134615136b3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] back in September.
Link 2025-11-05 Open redirect endpoint in Datasette prior to 0.65.2 and 1.0a21 [ https://substack.com/redirect/3139fbab-7f43-4b45-a3a7-36c931bd0695?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This GitHub security advisory covers two new releases of Datasette that I shipped today, both addressing the same open redirect issue [ https://substack.com/redirect/765ca904-ad6f-454e-be2e-3aca4cd340a8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with a fix by James Jefferies [ https://substack.com/redirect/d8993dbf-cd73-4531-b371-4b807f68e1d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Datasette 0.65.2 [ https://substack.com/redirect/ee9fd9ab-a6b6-4486-9053-e090a7fb90da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] fixes the bug and also adds Python 3.14 support and a datasette publish cloudrun fix.
Datasette 1.0a21 [ https://substack.com/redirect/4649f3a1-e478-4f26-94bc-ee7c751110ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] also has that Cloud Run fix and two other small new features:
New datasette --get /path --headers option for inspecting the headers returned by a path. (#2578 [ https://substack.com/redirect/8110399f-9f29-43a9-860e-991094e8c4a1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
New datasette.client.get(..., skip_permission_checks=True)parameter to bypass permission checks when making requests using the internal client. (#2583 [ https://substack.com/redirect/7348e25d-bd89-42bc-8771-5a8c5349db29?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
I decided to include the Cloud Run deployment fix so anyone with Datasette instances deployed to Cloud Run can update them with the new patched versions.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOemd4TkRFd056UXNJbWxoZENJNk1UYzJNak01TWpBek9Td2laWGh3SWpveE56a3pPVEk0TURNNUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuUl9SODlJQkZJbGdRZF9jQ3JBbnRieVl1cmJrNTZ3UG5vcUJFaHBTaUdxUSIsInAiOjE3ODE0MTA3NCwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzYyMzkyMDM5LCJleHAiOjIwNzc5NjgwMzksImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.9Qu0B40wrt_gqwY6s7fQ5U-_MbWIBp9NzJDfeRo8VNo?
