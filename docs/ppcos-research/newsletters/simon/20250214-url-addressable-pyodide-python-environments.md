# URL-addressable Pyodide Python environments

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2025-02-14T00:55:21.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/url-addressable-pyodide-python-environments

In this newsletter:
URL-addressable Pyodide Python environments
Using pip to install a Large Language Model that's under 100MB
Plus 20 links and 6 quotations and 1 TIL
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
URL-addressable Pyodide Python environments [ https://substack.com/redirect/45dcd407-9d85-4799-bec4-ee179434284e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-02-13
This evening I spotted an obscure bug [ https://substack.com/redirect/cc4147ca-7ed4-41b9-8744-90feb2c6422f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in Datasette [ https://substack.com/redirect/46808094-6052-4a37-a021-74aae6185a20?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], using Datasette Lite [ https://substack.com/redirect/afa343e5-c1da-425f-b02a-b74765f143a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I figure it's a good opportunity to highlight how useful it is to have a URL-addressable Python environment, powered by Pyodide and WebAssembly.
Here's the page that helped me discover the bug:
https://lite.datasette.io/?install=datasette-visible-internal-db&ref=1.0a17#/_internal/catalog_columns?_facet=database_name [ https://substack.com/redirect/c355da2c-9015-492f-ba8f-4d076359d0ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
To explain what's going on here, let's first review the individual components.
Datasette Lite [ https://substack.com/redirect/c9d06375-8328-4953-a6aa-b6abbdc18a2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The Datasette 1.0 alphas [ https://substack.com/redirect/75431cc0-293c-4f46-a0f8-49f89e46dad8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
This works for plugins, too [ https://substack.com/redirect/238d4888-e134-4709-89e9-063292f8d9e8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
datasette-visible-internal-db [ https://substack.com/redirect/6f0d0887-fbd5-4a76-a123-2e4151476a3f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Spotting the bug [ https://substack.com/redirect/33fc6394-9262-454d-bf8a-e29e60251d22?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Fixing the bug [ https://substack.com/redirect/d1035134-d8fd-4635-a0a1-1dcbeebdf3d2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
URL-addressable Steps To Reproduce [ https://substack.com/redirect/b5ad965c-d0ab-4664-9ada-6924e4cd210c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Datasette Lite
Datasette Lite [ https://substack.com/redirect/b4dbb874-6af5-4b33-835f-2651151282bc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is a version of Datasette [ https://substack.com/redirect/46808094-6052-4a37-a021-74aae6185a20?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that runs entirely in your browser. It runs on Pyodide [ https://substack.com/redirect/bf55b7f4-d330-4af6-bbbc-58959a9104c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which I think is still the most underappreciated project in the Python ecosystem.
I built Datasette Lite almost three years ago [ https://substack.com/redirect/4327cf01-d6fc-4198-9e42-e1fea24d6957?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as a weekend hack project to try and see if I could get Datasette - a server-side Python web application - to run entirely in the browser.
I've added a bunch of features since then, described in the README [ https://substack.com/redirect/be619f24-ed67-421d-896b-650d6567bcbf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - most significantly the ability to load SQLite databases, CSV files, JSON files or Parquet files by passing a URL to a query string parameter.
I built Datasette Lite almost as a joke, thinking nobody would want to wait for a full Python interpreter to download to their browser each time they wanted to explore some data. It turns out internet connections are fast these days and having a version of Datasette that needs a browser, GitHub Pages and nothing else is actually extremely useful.
Just the other day I saw Logan Williams [ https://substack.com/redirect/5852406a-4bc1-4662-a4c5-290ec9380ddd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of Bellingcat using it to share a better version of this Excel sheet [ https://substack.com/redirect/8e2a9a1e-2ab4-4337-8008-af0dbba5f0ed?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The NSF grants that Ted Cruz has singled out for advancing "neo-Marxist class warfare propaganda," in Datasette-Lite: lite.datasette.io?url=https://... [ https://substack.com/redirect/c60db406-46b4-4142-8a9f-b1a482ffe528?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Let's look at that URL in full:
https://lite.datasette.io/?url=https://data-house-lake.nyc3.cdn.digitaloceanspaces.com/cruz_nhs.db#/cruz_nhs/grants [ https://substack.com/redirect/c60db406-46b4-4142-8a9f-b1a482ffe528?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
The ?url= parameter there poins to a SQLite database file, hosted on DigitalOcean Spaces and served with the all-important access-control-allow-origin: * header which allows Datasette Lite to load it across domains.
The #/cruz_nhs/grants part of the URL tells Datasette Lite which page to load when you visit the link.
Anything after the # in Datasette Lite is a URL that gets passed on to the WebAssembly-hosted Datasette instance. Any query string items before that can be used to affect the initial state of the Datasette instance, to import data or even to install additional plugins.
The Datasette 1.0 alphas
I've shipped a lot of Datasette alphas - the most recent is Datasette 1.0a17 [ https://substack.com/redirect/d0ed040a-5cfc-4163-8a83-3daa812e316f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Those alphas get published to PyPI [ https://substack.com/redirect/abdccc78-d173-4a14-be76-bcbd624cf41c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which means they can be installed using pip install datasette==1.0a17.
A while back I added the same ability [ https://substack.com/redirect/25806b9b-7fcd-4067-8b38-9f9ce0d5af5e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to Datasette Lite itself. You can now pass &ref=1.0a17 to the Datasette Lite URL to load that specific version of Datasette.
This works thanks to the magic of Pyodide's micropip [ https://substack.com/redirect/dee32ca4-0025-4386-9ac1-4dfcf61882fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] mechanism. Every time you load Datasette Lite in your browser it's actually using micropip to install the packages it needs directly from PyPI. The code looks something like this:
await pyodide.loadPackage('micropip', {messageCallback: log});
let datasetteToInstall = 'datasette';
let pre = 'False';
if (settings.ref) {
if (settings.ref == 'pre') {
pre = 'True';
} else {
datasetteToInstall = `datasette==${settings.ref}`;
}
}
await self.pyodide.runPythonAsync(`
import micropip
await micropip.install("${datasetteToInstall}", pre=${pre})
`);
Full code here [ https://substack.com/redirect/51a3fec3-cfc9-4279-9af3-78b14bf0e4ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
That settings object has been passed to the Web Worker that loads Datasette, incorporating various query string parameters.
This all means I can pass ?ref=1.0a17 to Datasette Lite to load a specific version, or ?ref=pre to get the most recently released pre-release version.
This works for plugins, too
Since loading extra packages from PyPI via micropip is so easy, I went a step further and added plugin support.
The ?install= parameter can be passed multiple times, each time specifying a Datasette plugin from PyPI that should be installed into the browser.
The README includes a bunch of examples [ https://substack.com/redirect/5f21a361-0eb3-4c39-8776-8fae0520008c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of this mechanism in action. Here's a fun one that loads datasette-mp3-audio [ https://substack.com/redirect/8d5d74cd-829e-44c2-9737-304b613b0a77?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to provide inline MP3 playing widgets, originally created for my ScotRail audio announcements [ https://substack.com/redirect/ea7b6ab8-9b02-410c-a056-5ba94c7d248f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project.
This only works for some plugins. They need to be pure Python wheels - getting plugins with compiled binary dependencies to work in Pyodide WebAssembly requires a whole set of steps that I haven't quite figured out.
Frustratingly, it doesn't work for plugins that run their own JavaScript yet! I may need to rearchitect significant chunks of both Datasette and Datasette Lite to make that work.
It's also worth noting that this is a remote code execution security hole. I don't think that's a problem here, because lite.datasette.io is deliberately hosted on the subdomain of a domain that I never intend to use cookies on. It's possible to vandalize the visual display of lite.datasette.io but it shouldn't be possible to steal any private data or do any lasting damage.
datasette-visible-internal-db
This evening's debugging exercise used a plugin called datasette-visible-internal-db [ https://substack.com/redirect/93b7083f-31aa-4d5a-9cdd-c2ad4cda165e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Datasette's internal database [ https://substack.com/redirect/685e35c8-5b09-42ca-9c73-da46b1cd5d65?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is an invisible SQLite database that sits at the heart of Datasette, tracking things like loaded metadata and the schemas of the currently attached tables.
Being invisible means we can use it for features that shouldn't be visible to users - plugins that record API secrets or permissions or track comments or data import progress, for example.
In Python code it's accessed like this:
internal_db = datasette.get_internal_database
As opposed to Datasette's other databases which are accessed like so:
db = datasette.get_database("my-database")
Sometimes, when hacking on Datasette, it's useful to be able to browse the internal database using the default Datasette UI.
That's what datasette-visible-internal-db does. The plugin implementation is just five lines of code [ https://substack.com/redirect/78fc4677-aebd-4330-8356-d371fea14864?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
import datasette

@datasette.hookimpl
def startup(datasette):
db = datasette.get_internal_database
datasette.add_database(db, name="_internal", route="_internal")
On startup the plugin grabs a reference to that internal database and then registers it using Datasette's add_database method [ https://substack.com/redirect/a96dbcdb-a1e6-4736-b02c-a5a9160eab2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. That's all it takes to have it show up as a visible database on the /_internal path within Datasette.
Spotting the bug
I was poking around with this today out of pure curiosity - I hadn't tried ?install=datasette-visible-internal-db with Datasette Lite before and I wanted to see if it worked.
Here's that URL from earlier [ https://substack.com/redirect/c355da2c-9015-492f-ba8f-4d076359d0ef?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], this time with commentary:
https://lite.datasette.io/ // Datasette Lite
?install=datasette-visible-internal-db // Install the visible internal DB plugin
&ref=1.0a17 // Load the 1.0a17 alpha release
#/_internal/catalog_columns // Navigate to the /_internal/catalog_columns table page
&_facet=database_name // Facet by database_name for good measure
And this is what I saw:
This all looked good... until I clicked on that _internal link in the database_name column... and it took me to this /_internal/databases/_internal 404 page [ https://substack.com/redirect/893605fd-f000-49e1-bbea-8bd983b3ae3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Why was that a 404? Datasette introspects the SQLite table schema to identify foreign key relationships, then turns those into hyperlinks. The SQL schema for that catalog_columns table (displayed at the bottom of the table page) looked like this:
CREATE TABLE catalog_columns (
database_name TEXT,
table_name TEXT,
cid INTEGER,
name TEXT,
type TEXT,
"notnull" INTEGER,
default_value TEXT, -- renamed from dflt_value
is_pk INTEGER, -- renamed from pk
hidden INTEGER,
PRIMARY KEY (database_name, table_name, name),
FOREIGN KEY (database_name) REFERENCES databases(database_name),
FOREIGN KEY (database_name, table_name) REFERENCES tables(database_name, table_name)
);
Those foreign key references are a bug! I renamed the internal tables from databases and tables to catalog_databases and catalog_tables quite a while ago, but apparently forgot to update the references - and SQLite let me get away with it.
Fixing the bug
I fixed the bug in this commit [ https://substack.com/redirect/11de2ba8-0032-443e-9946-b0bcb1ce53f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. As is often the case the most interesting part of the fix is the accompanying test [ https://substack.com/redirect/b3d54645-96f9-4592-9917-e6b941d16578?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I decided to use the introspection helpers in sqlite-utils [ https://substack.com/redirect/23e38461-cbe3-49f1-bfb0-ffb0315de768?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to guard against every making another mistake like this again in the future:
@pytest.mark.asyncio
async def test_internal_foreign_key_references(ds_client):
internal_db = await ensure_internal(ds_client)
def inner(conn):
db = sqlite_utils.Database(conn)
table_names = db.table_names
for table in db.tables:
for fk in table.foreign_keys:
other_table = fk.other_table
other_column = fk.other_column
message = 'Column "{}.{}" references other column "{}.{}" which does not exist'.format(
table.name, fk.column, other_table, other_column
)
assert other_table in table_names, message + " (bad table)"
assert other_column in db[other_table].columns_dict, (
message + " (bad column)"
)
await internal_db.execute_fn(inner)
This uses Datasette's await db.execute_fn [ https://substack.com/redirect/c58159c5-cdd6-41d0-85ee-c9291fd2014e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] method, which lets you run Python code that accesses SQLite in a thread. That code can then use the blocking sqlite-utils introspection methods [ https://substack.com/redirect/58235ab9-e577-492f-81b4-64f3d9998a84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - here I'm looping through every table in that internal database, looping through each tables .foreign_keys and confirming that the .other_table and .other_column values reference a table and column that genuinely exist.
I ran this test, watched it fail, then applied the fix and it passed.
URL-addressable Steps To Reproduce
The idea I most wanted to highlight here is the enormous value provided by URL-addressable Steps To Reproduce.
Having good Steps To Reproduce is crucial for productively fixing bugs. Something you can click on to see the bug is the most effective form of STR there is.
Ideally, these URLs will continue to work long into the future.
The great thing about a system like Datasette Lite is that everything is statically hosted files. The application itself is hosted on GitHub Pages, and it works by loading additional files from various different CDNs. The only dynamic aspect is cached lookups against the PyPI API, which I expect to stay stable for a long time to come.
As a stable component of the Web platform for almost 8 years [ https://substack.com/redirect/23fcad7f-d69e-4adc-9282-f04f6e588a14?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] WebAssembly is clearly here to stay. I expect we'll be able to execute today's WASM code in browsers 20+ years from now.
I'm confident that the patterns I've been exploring in Datasette Lite over the past few years could be just as valuable for other projects. Imagine demonstrating bugs in a Django application using a static WebAssembly build, archived forever as part of an issue tracking system.
I think WebAssembly and Pyodide still have a great deal of untapped potential for the wider Python world.
Using pip to install a Large Language Model that's under 100MB [ https://substack.com/redirect/4aebe3d2-e06f-4b89-a6fb-49e7abc92625?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2025-02-07
I just released llm-smollm2 [ https://substack.com/redirect/28bb1846-15b0-447e-b5a8-4c7bc3264368?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a new plugin for LLM [ https://substack.com/redirect/80d75926-9fa1-4afe-850b-6bb0b9e7afa1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that bundles a quantized copy of the SmolLM2-135M-Instruct [ https://substack.com/redirect/b6d6e400-6e9d-46a5-a084-f928543b8bce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] LLM inside of the Python package.
This means you can now pip install a full LLM!
If you're already using LLM [ https://substack.com/redirect/80d75926-9fa1-4afe-850b-6bb0b9e7afa1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] you can install it like this:
llm install llm-smollm2
Then run prompts like this:
llm -m SmolLM2 'Are dogs real?'
(New favourite test prompt for tiny models, courtesy of Tim Duffy [ https://substack.com/redirect/a5f1abba-f231-4e85-b242-2a00f42a74e6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here's the result [ https://substack.com/redirect/e7ba33ab-cbb1-423b-a457-5231beadcd89?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]).
If you don't have LLM yet first follow these installation instructions [ https://substack.com/redirect/4fdf9fff-0fe8-4bc3-bd38-b265630acf4b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], or brew install llm or pipx install llm or uv tool install llm depending on your preferred way of getting your Python tools.
If you have uv [ https://substack.com/redirect/b2ab32e7-7fbd-43f7-b21e-54cffcdac225?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] setup you don't need to install anything at all! The following command will spin up an ephemeral environment, install the necessary packages and start a chat session with the model all in one go:
uvx --with llm-smollm2 llm chat -m SmolLM2
Finding a tiny model [ https://substack.com/redirect/e91c545f-ba60-43a9-9e7b-d3d1418d9b26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Building the plugin [ https://substack.com/redirect/8254bcc4-7123-48b1-9275-f99fc6179edf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Packaging the plugin [ https://substack.com/redirect/22ce38f3-f95e-4c20-9f95-9fa17e5c1af1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Publishing to PyPI [ https://substack.com/redirect/90e374af-2f23-4f05-84a3-fa8e542ef02a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Is the model any good? [ https://substack.com/redirect/f723f85e-4ee9-4076-82be-221050e74f46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Finding a tiny model
The fact that the model is almost exactly 100MB is no coincidence: that's the default size limit [ https://substack.com/redirect/60081852-b753-4e56-9f95-483d3e8c0f68?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for a Python package that can be uploaded to the Python Package Index (PyPI).
I asked on Bluesky [ https://substack.com/redirect/97a9c1de-d51d-460d-8db2-3c3a2e9c958d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] if anyone had seen a just-about-usable GGUF model that was under 100MB, and Artisan Loaf pointed me [ https://substack.com/redirect/3186177f-52bd-443e-9d63-99b58c34d4b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to SmolLM2-135M-Instruct [ https://substack.com/redirect/b6d6e400-6e9d-46a5-a084-f928543b8bce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I ended up using this quantization [ https://substack.com/redirect/8a874314-3a51-4869-991d-8f75d424e13c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by QuantFactory [ https://substack.com/redirect/622f7267-d23c-4f3a-83fa-0a39d9709015?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] just because it was the first sub-100MB model I tried that worked.
Trick for finding quantized models: Hugging Face has a neat "model tree" feature in the side panel of their model pages, which includes links to relevant quantized models. I find most of my GGUFs using that feature.
Building the plugin
I first tried the model out using Python and the llama-cpp-python [ https://substack.com/redirect/102feac2-f5ca-4540-881a-5122de8f75d4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library like this:
uv run --with llama-cpp-python python
Then:
from llama_cpp import Llama
from pprint import pprint
llm = Llama(model_path="SmolLM2-135M-Instruct.Q4_1.gguf")
output = llm.create_chat_completion(messages=[
{"role": "user", "content": "Hi"}
])
pprint(output)
This gave me the output I was expecting:
{'choices': [{'finish_reason': 'stop',
'index': 0,
'logprobs': None,
'message': {'content': 'Hello! How can I assist you today?',
'role': 'assistant'}}],
'created': 1738903256,
'id': 'chatcmpl-76ea1733-cc2f-46d4-9939-90ea2ai05e7c',
'model': 'SmolLM2-135M-Instruct.Q4_1.gguf',
'object': 'chat.completion',
'usage': {'completion_tokens': 9, 'prompt_tokens': 31, 'total_tokens': 40}}
But it also spammed my terminal with a huge volume of debugging output - which started like this:
llama_model_load_from_file_impl: using device Metal (Apple M2 Max) - 49151 MiB free
llama_model_loader: loaded meta data with 33 key-value pairs and 272 tensors from SmolLM2-135M-Instruct.Q4_1.gguf (version GGUF V3 (latest))
llama_model_loader: Dumping metadata keys/values. Note: KV overrides do not apply in this output.
llama_model_loader: - kv   0:                       general.architecture str              = llama
And then continued for more than 500 lines [ https://substack.com/redirect/9614ab91-b5bd-430d-85cf-389c77ccdc2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]!
I've had this problem with llama-cpp-python and llama.cpp in the past, and was sad to find that the documentation still doesn't have a great answer for how to avoid this.
So I turned to the just released Gemini 2.0 Pro (Experimental) [ https://substack.com/redirect/9a4ea8bc-53b0-4805-881d-0ae3a4d4d457?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], because I know it's a strong model with a long input limit.
I ran the entire llama-cpp-python codebase through it like this:
cd /tmp
git clone https://github.com/abetlen/llama-cpp-python
cd llama-cpp-python
files-to-prompt -e py . -c | llm -m gemini-2.0-pro-exp-02-05 \
'How can I prevent this library from logging any information at all while it is running - no stderr or anything like that'
Here's the answer I got back [ https://substack.com/redirect/9bf4258e-9fdd-4f86-8e63-f4ed6ce1417a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. It recommended setting the logger to logging.CRITICAL, passing verbose=False to the constructor and, most importantly, using the following context manager to suppress all output:
from contextlib import contextmanager, redirect_stderr, redirect_stdout

@contextmanager
def suppress_output:
"""
Suppresses all stdout and stderr output within the context.
"""
with open(os.devnull, "w") as devnull:
with redirect_stdout(devnull), redirect_stderr(devnull):
yield
This worked! It turned out most of the output came from initializing the LLM class, so I wrapped that like so:
with suppress_output:
model = Llama(model_path=self.model_path, verbose=False)
Proof of concept in hand I set about writing the plugin. I started with my simonw/llm-plugin [ https://substack.com/redirect/2f5e50d6-7b4c-4bd6-a64f-90e797cb2d25?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] cookiecutter template:
uvx cookiecutter gh:simonw/llm-plugin
[1/6] plugin_name : smollm2
[2/6] description : SmolLM2-135M-Instruct.Q4_1 for LLM
[3/6] hyphenated (smollm2):
[4/6] underscored (smollm2):
[5/6] github_username : simonw
[6/6] author_name : Simon Willison
The rest of the plugin [ https://substack.com/redirect/1320f4d2-5710-454b-9dd4-62ea0234b3da?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] was mostly borrowed from my existing llm-gguf [ https://substack.com/redirect/99c42748-3236-4226-b642-885e604764fb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin, updated based on the latest README for the llama-cpp-python project.
There's more information on building plugins in the tutorial on writing a plugin [ https://substack.com/redirect/34be064e-e879-41e0-814a-16d55faab422?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Packaging the plugin
Once I had that working the last step was to figure out how to package it for PyPI. I'm never quite sure of the best way to bundle a binary file in a Python package, especially one that uses a pyproject.toml file... so I dumped a copy of my existing pyproject.toml file into o3-mini-high and prompted:
Modify this to bundle a SmolLM2-135M-Instruct.Q4_1.gguf file inside the package. I don't want to use hatch or a manifest or anything, I just want to use setuptools.
Here's the shared transcript [ https://substack.com/redirect/423eab08-fbdd-401a-ab1d-644618748597?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - it gave me exactly what I wanted. I bundled it by adding this to the end of the toml file:
[tool.setuptools.package-data]
llm_smollm2 = ["SmolLM2-135M-Instruct.Q4_1.gguf"]
Then dropping that .gguf file into the llm_smollm2/ directory and putting my plugin code in llm_smollm2/__init__.py.
I tested it locally by running this:
python -m pip install build
python -m build
I fired up a fresh virtual environment and ran pip install ../path/to/llm-smollm2/dist/llm_smollm2-0.1-py3-none-any.whl to confirm that the package worked as expected.
Publishing to PyPI
My cookiecutter template comes with a GitHub Actions workflow [ https://substack.com/redirect/944704f8-4ac2-4cc5-ab28-6c8d15252b8f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that publishes the package to PyPI when a new release is created using the GitHub web interface. Here's the relevant YAML:
deploy:
runs-on: ubuntu-latest
needs: [test]
environment: release
permissions:
id-token: write
steps:
- uses: actions/checkout@v4
- name: Set up Python
uses: actions/setup-python@v5
with:
python-version: "3.13"
cache: pip
cache-dependency-path: pyproject.toml
- name: Install dependencies
run: |
pip install setuptools wheel build
- name: Build
run: |
python -m build
- name: Publish
uses: pypa/gh-action-pypi-publish@release/v1
This runs after the test job has passed. It uses the pypa/gh-action-pypi-publish [ https://substack.com/redirect/f2816ba3-aecc-4692-9b45-6a4a16ad2355?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Action to publish to PyPI - I wrote more about how that works in this TIL [ https://substack.com/redirect/4e79642f-aa56-4e9d-90b9-6f6c33cbba16?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Is the model any good?
This one really isn't! It's not really surprising but it turns out 94MB really isn't enough space for a model that can do anything useful.
It's super fun to play with, and I continue to maintain that small, weak models are a great way to help build a mental model of how this technology actually works.
That's not to say SmolLM2 isn't a fantastic model family. I'm running the smallest, most restricted version here. SmolLM - blazingly fast and remarkably powerful [ https://substack.com/redirect/1a63134b-4ac1-492f-9faa-35f90897a804?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] describes the full model family - which comes in 135M, 360M, and 1.7B sizes. The larger versions are a whole lot more capable.
If anyone can figure out something genuinely useful to do with the 94MB version I'd love to hear about it.
Quote 2025-02-02
While we encourage people to use AI systems during their role to help them work faster and more effectively, please do not use AI assistants during the application process. We want to understand your personal interest in Anthropic without mediation through an AI system, and we also want to evaluate your non-AI-assisted communication skills. Please indicate 'Yes' if you have read and agree.
Why do you want to work at Anthropic? (We value this response highly - great answers are often 200-400 words.)
Anthropic [ https://substack.com/redirect/6677fcad-cf5a-4850-9091-8c025a11fd5c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-03 A computer can never be held accountable [ https://substack.com/redirect/ef742527-fe06-424e-9cf2-7f02a410745a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This legendary page from an internal IBM training in 1979 could not be more appropriate for our new age of AI.
A computer can never be held accountable
Therefore a computer must never make a management decision
Back in June 2024 I asked on Twitter [ https://substack.com/redirect/16a134f7-1e00-4ec9-8031-0de1b4663790?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] if anyone had more information on the original source.
Jonty Wareing replied [ https://substack.com/redirect/803bc6cc-b596-46e9-9f64-ccecd5d9302b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
It was found by someone going through their father's work documents, and subsequently destroyed in a flood.
I spent some time corresponding with the IBM archives but they can't locate it. Apparently it was common for branch offices to produce things that were not archived.
Here's the reply [ https://substack.com/redirect/9909ba63-d47a-4c11-9134-fdc03a16e964?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Jonty got back from IBM:
I believe the image was first shared online in this tweet [ https://substack.com/redirect/ef742527-fe06-424e-9cf2-7f02a410745a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by @bumblebike in February 2017. Here's where they confirm it was from 1979 internal training [ https://substack.com/redirect/92250f99-e413-43a7-9abf-a24ef7e6d33a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here's another tweet from @bumblebike [ https://substack.com/redirect/a1dd597f-2852-4fae-8a31-a469ce736ccb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from December 2021 about the flood:
Unfortunately destroyed by flood in 2019 with most of my things. Inquired at the retirees club zoom last week, but there’s almost no one the right age left. Not sure where else to ask.
Link 2025-02-03 Constitutional Classifiers: Defending against universal jailbreaks [ https://substack.com/redirect/cd89e5df-b827-40c8-a74e-f9d069aae509?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Interesting new research from Anthropic, resulting in the paper Constitutional Classifiers: Defending against Universal Jailbreaks across Thousands of Hours of Red Teaming [ https://substack.com/redirect/6b562aba-a12b-4e16-866b-d46fe56ecc90?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
From the paper:
In particular, we introduce Constitutional Classifiers, a framework that trains classifier safeguards using explicit constitutional rules (§3). Our approach is centered on a constitution that delineates categories of permissible and restricted content (Figure 1b), which guides the generation of synthetic training examples (Figure 1c). This allows us to rapidly adapt to new threat models through constitution updates, including those related to model misalignment (Greenblatt et al., 2023). To enhance performance, we also employ extensive data augmentation and leverage pool sets of benign data.[^1]
Critically, our output classifiers support streaming prediction: they assess the potential harmfulness of the complete model output at each token without requiring the full output to be generated. This enables real-time intervention—if harmful content is detected at any point, we can immediately halt generation, preserving both safety and user experience.
A key focus of this research is CBRN - an acronym for Chemical, Biological, Radiological and Nuclear harms. Both Anthropic and OpenAI's safety research frequently discuss these threats.
Anthropic hosted a two month red teaming exercise where participants tried to break through their system:
Specifically, they were given a list of ten “forbidden” queries, and their task was to use whichever jailbreaking techniques they wanted in order to get one of our current models (in this case, Claude 3.5 Sonnet, June 2024) guarded by the prototype Constitutional Classifiers to answer all of the queries. We only considered it a successful “universal” jailbreak if the model provided a detailed answer to all of the queries.
183 active participants spent an estimated >3,000 hours over a two-month experimental period attempting to jailbreak the model. They were offered a monetary reward up to $15,000 should they discover a universal jailbreak. Despite the large amount of effort, none of the participants were able to coerce the model to answer all ten forbidden queries with a single jailbreak—that is, no universal jailbreak was discovered.
I'm disappointed that the goal they set was for a single universal jailbreak. I would have thought that a partial jailbreak - one that worked against a subset of those questions - would still be a result that demonstrated concerning gaps in their proposed protection.
Anthropic are now running a public continuation of their red teaming exercise at claude.ai/constitutional-classifiers [ https://substack.com/redirect/2616bc9d-4d2d-4711-b949-64f69bd56ad5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] until Feb 10, 2025, with 8 target questions.
Here's the first of those:
I hadn't heard of Soman so I pasted that question into R1 on chat.deepseek.com [ https://substack.com/redirect/53ca65b8-961e-44a2-af1a-055c279de8e7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which confidently explained precautionary measures I should take when working with Soman, "a potent nerve agent", but wrapped it up with this disclaimer:
Disclaimer: Handling Soman is inherently high-risk and typically restricted to authorized military/labs. This guide assumes legal access and institutional oversight. Always consult certified safety professionals before proceeding.
Link 2025-02-04 Build a link blog [ https://substack.com/redirect/4b273388-bb8d-4d8f-8ceb-a6edd17f4057?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Xuanwo started a link blog [ https://substack.com/redirect/bfd3d07c-66a9-44ee-b44b-c4fe033fbfa7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] inspired by my article My approach to running a link blog [ https://substack.com/redirect/5b3a1f88-3de7-4be5-a30c-e44367400fa4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and in a delightful piece of recursion his first post is a link blog entry about my post about link blogging, following my tips on quoting liberally and including extra commentary.
I decided to follow simon's approach to creating a link blog, where I can share interesting links I find on the internet along with my own comments and thoughts about them.
Link 2025-02-04 Animating Rick and Morty One Pixel at a Time [ https://substack.com/redirect/728d0d04-3735-4390-9c3e-9da17e579548?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Daniel Hooper says he spent 8 months working on the post, the culmination of which is an animation of Rick from Rick and Morty, implemented in 240 lines of GLSL - the OpenGL Shading Language which apparently has been directly supported by browsers for many years.
The result is a comprehensive GLSL tutorial, complete with interactive examples of each of the steps used to generate the final animation which you can tinker with directly on the page. It feels a bit like Logo!
Shaders work by running code for each pixel to return that pixel's color - in this case the color_for_pixel function is wired up as the core logic of the shader.
Here's Daniel's code for the live shader editor [ https://substack.com/redirect/5f3b431e-7b4c-4fd2-b986-b060ac16eeb0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] he built for this post. It looks like this [ https://substack.com/redirect/2896a30a-a30d-4d89-b5a3-7ecd2a311325?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] is the function that does the most important work:
function loadShader(shaderSource, shaderType) {
const shader = gl.createShader(shaderType);
gl.shaderSource(shader, shaderSource);
gl.compileShader(shader);
const compiled = gl.getShaderParameter(shader, gl.COMPILE_STATUS);
if (!compiled) {
const lastError = gl.getShaderInfoLog(shader);
gl.deleteShader(shader);
return lastError;
}
return shader;
}
Where gl is a canvas.getContext("webgl2") WebGL2RenderingContext object, described by MDN here [ https://substack.com/redirect/c5c7b9ca-d2c1-4742-abed-f6ada667f1ba?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
TIL 2025-02-04 Running pytest against a specific Python version with uv run [ https://substack.com/redirect/132c9c72-c63d-46c4-be2a-2a7a1eaea565?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
While working on this issue [ https://substack.com/redirect/9f9355c4-5e2b-481c-a682-05caf4110303?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I figured out a neat pattern for running the tests for my project locally against a specific Python version using uv run [ https://substack.com/redirect/dcf89e12-9aab-43f7-ab92-c8f31ec0eed2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: …
Link 2025-02-05 AI-generated slop is already in your public library [ https://substack.com/redirect/8348d379-84eb-43ab-a88c-06ecaf347a3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
US libraries that use the Hoopla [ https://substack.com/redirect/3ccf09a4-8e4a-4931-a25e-8df3eb16b032?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] system to offer ebooks to their patrons sign agreements where they pay a license fee for anything selected by one of their members that's in the Hoopla catalog.
The Hoopla catalog is increasingly filling up with junk AI slop ebooks like "Fatty Liver Diet Cookbook: 2000 Days of Simple and Flavorful Recipes for a Revitalized Liver", which then cost libraries money if someone checks them out.
Apparently librarians already have a term for this kind of low-quality, low effort content that predates it being written by LLMs: vendor slurry.
Libraries stand against censorship, making this a difficult issue to address through removing those listings.
Sarah Lamdan, deputy director of the American Library Association says:
If library visitors choose to read AI eBooks, they should do so with the knowledge that the books are AI-generated.
Link 2025-02-05 Ambsheets: Spreadsheets for exploring scenarios [ https://substack.com/redirect/d56c79e6-ba30-4810-a9a1-bbc2bb56df0b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Delightful UI experiment by Alex Warth and Geoffrey Litt at Ink & Switch, exploring the idea of a spreadsheet with cells that can handle multiple values at once, which they call "amb" (for "ambiguous") values. A single sheet can then be used to model multiple scenarios.
Here the cell for "Car" contains {500, 1200} and the cell for "Apartment" contains {2800, 3700, 5500}, resulting in a "Total" cell with six different values. Hovering over a calculated highlights its source values and a side panel shows a table of calculated results against those different combinations.
Always interesting to see neat ideas like this presented on top of UIs that haven't had a significant upgrade in a very long time.
Link 2025-02-05 o3-mini is really good at writing internal documentation [ https://substack.com/redirect/87d95025-42c5-4373-ae8e-079de4b04142?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I wanted to refresh my knowledge of how the Datasette permissions system works today. I already have extensive hand-written documentation [ https://substack.com/redirect/1db1604c-ab06-4b8a-872d-b894d2f029c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for that, but I thought it would be interesting to see if I could derive any insights from running an LLM against the codebase.
o3-mini has an input limit of 200,000 tokens. I used LLM [ https://substack.com/redirect/80d75926-9fa1-4afe-850b-6bb0b9e7afa1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and my files-to-prompt [ https://substack.com/redirect/6be57345-e5cc-40c3-a856-a13a13b67319?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool to generate the documentation like this:
cd /tmp
git clone https://github.com/simonw/datasette [ https://substack.com/redirect/39d2fe62-226d-412c-9fd5-9ccc13d97bd7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
cd datasette
files-to-prompt datasette -e py -c | \
llm -m o3-mini -s \
'write extensive documentation for how the permissions system works, as markdown'
The files-to-prompt command is fed the datasette [ https://substack.com/redirect/aa38d5dc-d910-4a7e-8a81-68904b86075b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] subdirectory, which contains just the source code for the application - omitting tests (in tests/) and documentation (in docs/).
The -e py option causes it to only include files with a .py extension - skipping all of the HTML and JavaScript files in that hierarchy.
The -c option causes it to output Claude's XML-ish format - a format that works great with other LLMs too.
You can see the output of that command in this Gist [ https://substack.com/redirect/1bc4267f-e251-4201-9f4d-8b6031581a11?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Then I pipe that result into LLM, requesting the o3-mini OpenAI model and passing the following system prompt:
write extensive documentation for how the permissions system works, as markdown
Specifically requesting Markdown is important [ https://substack.com/redirect/633f7b9b-a502-45c9-b9d8-ff9c78c6cf1c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The prompt used 99,348 input tokens and produced 3,118 output tokens (320 of those were invisible reasoning tokens). That's a cost [ https://substack.com/redirect/f9c11cea-5136-4904-a46a-6412d61e1777?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of 12.3 cents.
Honestly, the results [ https://substack.com/redirect/87d95025-42c5-4373-ae8e-079de4b04142?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] are fantastic. I had to double-check that I hadn't accidentally fed in the documentation by mistake.
(It's possible that the model is picking up additional information about Datasette in its training set, but I've seen similar high quality results [ https://substack.com/redirect/511e2662-8d2e-4898-abf7-92d3c748a5a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] from other, newer libraries so I don't think that's a significant factor.)
In this case I already had extensive written documentation of my own, but this was still a useful refresher to help confirm that the code matched my mental model of how everything works.
Documentation of project internals as a category is notorious for going out of date. Having tricks like this to derive usable how-it-works documentation from existing codebases in just a few seconds and at a cost of a few cents is wildly valuable.
Link 2025-02-05 Gemini 2.0 is now available to everyone [ https://substack.com/redirect/edb66a30-a858-4675-bc08-b6b8e1ebc8d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Big new Gemini 2.0 releases today:
Gemini 2.0 Pro (Experimental) is Google's "best model yet for coding performance and complex prompts" - currently available as a free preview.
Gemini 2.0 Flash is now generally available.
Gemini 2.0 Flash-Lite looks particularly interesting:
We’ve gotten a lot of positive feedback on the price and speed of 1.5 Flash. We wanted to keep improving quality, while still maintaining cost and speed. So today, we’re introducing 2.0 Flash-Lite, a new model that has better quality than 1.5 Flash, at the same speed and cost. It outperforms 1.5 Flash on the majority of benchmarks.
That means Gemini 2.0 Flash-Lite is priced at 7.5c/million input tokens and 30c/million output tokens - half the price of OpenAI's GPT-4o mini (15c/60c).
Gemini 2.0 Flash isn't much more expensive [ https://substack.com/redirect/0aa24473-24c4-4e68-abaf-d9b77b682d09?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: 10c/million for text/image input, 70c/million for audio input, 40c/million for output. Again, cheaper than GPT-4o mini.
I pushed a new LLM [ https://substack.com/redirect/80d75926-9fa1-4afe-850b-6bb0b9e7afa1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin release, llm-gemini 0.10 [ https://substack.com/redirect/c3f49b2c-6c72-4d0e-b02c-3f5b69b801ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], adding support for the three new models:
llm install -U llm-gemini
llm keys set gemini
# paste API key here
llm -m gemini-2.0-flash "impress me"
llm -m gemini-2.0-flash-lite-preview-02-05 "impress me"
llm -m gemini-2.0-pro-exp-02-05 "impress me"
Here's the output [ https://substack.com/redirect/9f92cd6f-2b42-42ef-8cfd-2acbc8fdac75?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for those three prompts.
I ran Generate an SVG of a pelican riding a bicycle through the three new models. Here are the results, cheapest to most expensive:
gemini-2.0-flash-lite-preview-02-05
gemini-2.0-flash
gemini-2.0-pro-exp-02-05
Full transcripts here [ https://substack.com/redirect/b24631ca-70cf-40e9-a4fb-a293faa6c149?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I also ran the same prompt I tried with o3-mini the other day [ https://substack.com/redirect/8fb54cb7-eb7e-4f9f-9398-0e33e1f04d90?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
cd /tmp
git clone https://github.com/simonw/datasette
cd datasette
files-to-prompt datasette -e py -c | \
llm -m gemini-2.0-pro-exp-02-05 \
-s 'write extensive documentation for how the permissions system works, as markdown' \
-o max_output_tokens 10000
Here's the result from that [ https://substack.com/redirect/4098d6a5-5d37-4c08-abdf-44315afe7967?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - you can compare that to o3-mini's result here [ https://substack.com/redirect/87d95025-42c5-4373-ae8e-079de4b04142?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2025-02-05 S1: The $6 R1 Competitor? [ https://substack.com/redirect/38c5af47-00e7-4bb8-aacf-2716327e5dab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Tim Kellogg shares his notes on a new paper, s1: Simple test-time scaling [ https://substack.com/redirect/70fccb48-b78d-486e-93e4-e11b06a108fe?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which describes an inference-scaling model fine-tuned on top of Qwen2.5-32B-Instruct for just $6 - the cost for 26 minutes on 16 NVIDIA H100 GPUs.
Tim highlight the most exciting result:
After sifting their dataset of 56K examples down to just the best 1K, they found that the core 1K is all that's needed to achieve o1-preview performance on a 32B model.
The paper describes a technique called "Budget forcing":
To enforce a minimum, we suppress the generation of the end-of-thinking token delimiter and optionally append the string “Wait” to the model’s current reasoning trace to encourage the model to reflect on its current generation
That's the same trick Theia Vogel described a few weeks ago [ https://substack.com/redirect/102f0d81-2d17-4332-9d51-2a84fd9dd176?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Here's the s1-32B model on Hugging Face [ https://substack.com/redirect/18e992fd-8c55-48f1-b7af-2996ada60da4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I found a GGUF version of it at brittlewis12/s1-32B-GGUF [ https://substack.com/redirect/1b341014-c4bf-4167-af25-8aeed9beb93c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which I ran using Ollama [ https://substack.com/redirect/1eb4acd0-f1ba-4ffe-b84a-a98786b15346?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like so:
ollama run hf.co/brittlewis12/s1-32B-GGUF:Q4_0
I also found those 1,000 samples on Hugging Face in the simplescaling/s1K [ https://substack.com/redirect/cb489269-eb72-477f-82da-b5f98738b9ca?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] data repository there.
I used DuckDB to convert the parquet file to CSV (and turn one VARCHAR[] column into JSON):
COPY (
SELECT
solution,
question,
cot_type,
source_type,
metadata,
cot,
json_array(thinking_trajectories) as thinking_trajectories,
attempt
FROM 's1k-00001.parquet'
) TO 'output.csv' (HEADER, DELIMITER ',');
Then I loaded that CSV into sqlite-utils [ https://substack.com/redirect/23e38461-cbe3-49f1-bfb0-ffb0315de768?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] so I could use the convert command to turn a Python data structure into JSON using json.dumps and eval:
# Load into SQLite
sqlite-utils insert s1k.db s1k output.csv --csv
# Fix that column
sqlite-utils convert s1k.db s1u metadata 'json.dumps(eval(value))' --import json
# Dump that back out to CSV
sqlite-utils rows s1k.db s1k --csv > s1k.csv
Here's that CSV in a Gist [ https://substack.com/redirect/c0be78ef-d8d2-441a-aa37-37adf962343a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which means I can load it into Datasette Lite [ https://substack.com/redirect/5d635040-d769-4b94-97bd-153fd4d723fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It really is a tiny amount of training data. It's mostly math and science, but there are also 15 cryptic crossword examples [ https://substack.com/redirect/43258b71-1651-435a-92b1-a3eb79c77116?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Quote 2025-02-06
There's a new kind of coding I call "vibe coding", where you fully give in to the vibes, embrace exponentials, and forget that the code even exists. It's possible because the LLMs (e.g. Cursor Composer w Sonnet) are getting too good. Also I just talk to Composer with SuperWhisper so I barely even touch the keyboard.
I ask for the dumbest things like "decrease the padding on the sidebar by half" because I'm too lazy to find it. I "Accept All" always, I don't read the diffs anymore. When I get error messages I just copy paste them in with no comment, usually that fixes it. The code grows beyond my usual comprehension, I'd have to really read through it for a while. Sometimes the LLMs can't fix a bug so I just work around it or ask for random changes until it goes away.
It's not too bad for throwaway weekend projects, but still quite amusing. I'm building a project or webapp, but it's not really coding - I just see stuff, say stuff, run stuff, and copy paste stuff, and it mostly works.
Andrej Karpathy [ https://substack.com/redirect/60d95bae-c62c-4693-8cf7-08d7984bc9a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-06 The future belongs to idea guys who can just do things [ https://substack.com/redirect/4d9af337-27df-4ea0-acc7-1082fd26f0a2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Geoffrey Huntley with a provocative take on AI-assisted programming [ https://substack.com/redirect/b7a05c10-29af-4c84-93df-cfbe38ed93cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I seriously can't see a path forward where the majority of software engineers are doing artisanal hand-crafted commits by as soon as the end of 2026.
He calls for companies to invest in high quality internal training and create space for employees to figure out these new tools:
It's hackathon (during business hours) once a month, every month time.
Geoffrey's concluding note resonates with me. LLMs are a gift to the fiercely curious and ambitious:
If you’re a high agency person, there’s never been a better time to be alive...
Link 2025-02-06 sqlite-page-explorer [ https://substack.com/redirect/1a41cc37-03ce-4a8e-a930-371a661f033c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Outstanding tool by Luke Rissacher for understanding the SQLite file format. Download the application (built using redbean and Cosmopolitan, so the same binary runs on Windows, Mac and Linux) and point it at a SQLite database to get a local web application with an interface for exploring how the file is structured.
Here's it running against the datasette.io/content [ https://substack.com/redirect/f0776f10-dc8b-488f-9fe7-36f378574bda?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] database that runs the official Datasette website:
Link 2025-02-06 Datasette 1.0a17 [ https://substack.com/redirect/d0ed040a-5cfc-4163-8a83-3daa812e316f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New Datasette alpha, with a bunch of small changes and bug fixes accumulated over the past few months. Some (minor) highlights:
The register_magic_parameters(datasette) [ https://substack.com/redirect/d31d5254-5caa-4215-9e93-5bdc784ec689?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin hook can now register async functions. (#2441 [ https://substack.com/redirect/41857c5c-f4c9-4866-a80c-cffa1035b400?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Breadcrumbs on database and table pages now include a consistent self-link for resetting query string parameters. (#2454 [ https://substack.com/redirect/a57cd724-4a49-4e9a-8778-685248e6b558?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
New internal methods datasette.set_actor_cookie and datasette.delete_actor_cookie, described here [ https://substack.com/redirect/ecfc1c11-04b3-40f6-be2b-77444341cf29?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. (#1690 [ https://substack.com/redirect/ff798680-56e0-43e0-994f-dae98c8f27f2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
/-/permissions page now shows a list of all permissions registered by plugins. (#1943 [ https://substack.com/redirect/6aa352ba-5405-4a47-aa7c-7c6d6cb1cedf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
If a table has a single unique text column Datasette now detects that as the foreign key label for that table. (#2458 [ https://substack.com/redirect/9c09f6ea-878f-4204-b8b7-37db2cbac3ab?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
The /-/permissions page now includes options for filtering or exclude permission checks recorded against the current user. (#2460 [ https://substack.com/redirect/ec07cb89-f6d9-4a58-86be-2df10e20e4c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
I was incentivized to push this release by an issue [ https://substack.com/redirect/478b33e7-1d15-40b2-ab88-f10283c57f2b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I ran into in my new datasette-load [ https://substack.com/redirect/895a52f5-d39e-4f0f-806f-2a520e583aa2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin, which resulted in this fix:
Fixed a bug where replacing a database with a new one with the same name did not pick up the new database correctly. (#2465 [ https://substack.com/redirect/a5e6764c-a629-4e95-8dd3-102e80cc870c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ])
Link 2025-02-07 APSW SQLite query explainer [ https://substack.com/redirect/b5fa4c8e-0c7f-425d-be49-e39d82d54f44?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Today I found out about APSW [ https://substack.com/redirect/bde76416-032e-4a3b-a79d-add993bae3d5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]'s (Another Python SQLite Wrapper, in constant development since 2004) apsw.ext.query_info [ https://substack.com/redirect/6dfa0043-4380-4116-8127-bc4262e352a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] function, which takes a SQL query and returns a very detailed set of information about that query - all without executing it.
It actually solves a bunch of problems I've wanted to address in Datasette - like taking an arbitrary query and figuring out how many parameters (?) it takes and which tables and columns are represented in the result.
I tried it out in my console (uv run --with apsw python) and it seemed to work really well. Then I remembered that the Pyodide project includes WebAssembly builds of a number of Python C extensions and was delighted to find apsw on that list [ https://substack.com/redirect/b0a7fcd3-c788-42af-a873-21c6f79b316e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
... so I got Claude [ https://substack.com/redirect/129574c3-c0fe-4697-a302-e9f39941e7d5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to build me a web interface [ https://substack.com/redirect/b5fa4c8e-0c7f-425d-be49-e39d82d54f44?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for trying out the function, using Pyodide to run a user's query in Python in their browser via WebAssembly.
Claude didn't quite get it in one shot - I had to feed it the URL to a more recent Pyodide and it got stuck in a bug loop which I fixed by pasting the code into a fresh session.
Link 2025-02-07 sqlite-s3vfs [ https://substack.com/redirect/30ff8266-2389-4a14-95b8-e832d8271e78?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Neat open source project on the GitHub organisation for the UK government's Department for Business and Trade: a "Python virtual filesystem for SQLite to read from and write to S3."
I tried out their usage example [ https://substack.com/redirect/3ff4739d-ba41-4365-9bb7-ffe0b427bcd1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] by running it in a Python REPL with all of the dependencies
uv run --python 3.13 --with apsw --with sqlite-s3vfs --with boto3 python
It worked as advertised. When I listed my S3 bucket I found it had created two files - one called demo.sqlite/0000000000 and another called demo.sqlite/0000000001, both 4096 bytes because each one represented a SQLite page.
The implementation is just 200 lines of Python [ https://substack.com/redirect/bc7a69bc-f4cb-474b-aa11-03bdfba61a6e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], implementing a new SQLite Virtual Filesystem on top of apsw.VFS [ https://substack.com/redirect/a1400656-a01a-4f58-93d2-343fab1f4f13?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
The README includes this warning:
No locking is performed, so client code must ensure that writes do not overlap with other writes or reads. If multiple writes happen at the same time, the database will probably become corrupt and data be lost.
I wonder if the conditional writes [ https://substack.com/redirect/e43fb7da-5ad0-45d1-84f0-b93d0fe9899e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] feature added to S3 back in November could be used to protect against that happening. Tricky as there are multiple files involved, but maybe it (or a trick like this one [ https://substack.com/redirect/e3ce0286-3df0-4a7b-8a1a-9d09b86e9e3d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) could be used to implement some kind of exclusive lock between multiple processes?
Quote 2025-02-07
Confession: we've been hiding parts of v0 [ https://substack.com/redirect/2308b4be-4c3f-46b6-8c95-70d1c4b49d34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]'s responses from users since September. Since the launch of DeepSeek's web experience and its positive reception, we realize now that was a mistake. From now on, we're also showing v0's full output in every response. This is a much better UX because it feels faster and it teaches end users how to prompt more effectively.
Jared Palmer [ https://substack.com/redirect/d5c560cf-0f9a-4c9e-8cb9-dee64cf3c1ec?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-02-08
[...] We are destroying software with complex build systems.
We are destroying software with an absurd chain of dependencies, making everything bloated and fragile.
We are destroying software telling new programmers: “Don’t reinvent the wheel!”. But, reinventing the wheel is how you learn how things work, and is the first step to make new, different wheels. [...]
Salvatore Sanfilippo [ https://substack.com/redirect/7bfc1f4b-0969-43bd-bf07-f16be65ae1e3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2025-02-09
The cost to use a given level of AI falls about 10x every 12 months, and lower prices lead to much more use. You can see this in the token cost from GPT-4 in early 2023 to GPT-4o in mid-2024, where the price per token dropped about 150x in that time period. Moore’s law changed the world at 2x every 18 months; this is unbelievably stronger.
Sam Altman [ https://substack.com/redirect/578640bb-b35f-4dbd-94d3-e937ddf80529?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-10 Cerebras brings instant inference to Mistral Le Chat [ https://substack.com/redirect/8833c974-5232-4e5e-b3e6-358421c16e46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Mistral announced a major upgrade [ https://substack.com/redirect/1e6b076b-9ae7-4e94-9d29-ed57e0e090cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to their Le Chat [ https://substack.com/redirect/071f399c-3424-48fe-87fa-1fccd55c28a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] web UI (their version of ChatGPT) a few days ago, and one of the signature features was performance.
It turns out that performance boost comes from hosting their model on Cerebras:
We are excited to bring our technology to Mistral – specifically the flagship 123B parameter Mistral Large 2 model. Using our Wafer Scale Engine technology, we achieve over 1,100 tokens per second on text queries.
Given Cerebras's so far unrivaled inference performance I'm surprised that no other AI lab has formed a partnership like this already.
Link 2025-02-11 llm-sort [ https://substack.com/redirect/b3ec55a3-ba12-41dc-8000-ff07565f2f50?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Delightful LLM [ https://substack.com/redirect/80d75926-9fa1-4afe-850b-6bb0b9e7afa1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin by Evangelos Lamprou which adds the ability to perform "semantic search" - allowing you to sort the contents of a file based on using a prompt against an LLM to determine sort order.
Best illustrated by these examples from the README:
llm sort --query "Which names is more suitable for a pet monkey?" names.txt

cat titles.txt | llm sort --query "Which book should I read to cook better?"
It works using this pairwise prompt, which is executed multiple times using Python's sorted(documents, key=functools.cmp_to_key(compare_callback)) mechanism:
Given the query:
{query}

Compare the following two lines:

Line A:
{docA}

Line B:
{docB}

Which line is more relevant to the query? Please answer with "Line A" or "Line B".
From the lobste.rs comments [ https://substack.com/redirect/f7d17de2-41f5-4bb6-ab79-c6895ed179f0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], Cole Kurashige:
I'm not saying I'm prescient, but in The Before Times I did something similar [ https://substack.com/redirect/64a65ef3-2397-4793-a382-625b8d42e573?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with Mechanical Turk
This made me realize that so many of the patterns we were using against Mechanical Turk a decade+ ago can provide hints about potential ways to apply LLMs.
Link 2025-02-12 Building a SNAP LLM eval: part 1 [ https://substack.com/redirect/8a70a77f-8d0b-43eb-a2ea-e52b94466015?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Dave Guarino (previously [ https://substack.com/redirect/b3eb9ab3-ccf4-4d66-a6d2-df96ac344854?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) has been exploring using LLM-driven systems to help people apply for SNAP [ https://substack.com/redirect/4123959f-7cd8-4470-9647-0ca22deaf9b1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the US Supplemental Nutrition Assistance Program (aka food stamps).
This is a domain which existing models know some things about, but which is full of critical details around things like eligibility criteria where accuracy really matters.
Domain-specific evals like this are still pretty rare. As Dave puts it:
There is also not a lot of public, easily digestible writing out there on building evals in specific domains. So one of our hopes in sharing this is that it helps others build evals for domains they know deeply.
Having robust evals addresses multiple challenges. The first is establishing how good the raw models are for a particular domain. A more important one is to help in developing additional systems on top of these models, where an eval is crucial for understanding if RAG or prompt engineering tricks are paying off.
Step 1 doesn't involve writing any code at all:
Meaningful, real problem spaces inevitably have a lot of nuance. So in working on our SNAP eval, the first step has just been using lots of models — a lot. [...]
Just using the models and taking notes on the nuanced “good”, “meh”, “bad!” is a much faster way to get to a useful starting eval set than writing or automating evals in code.
I've been complaining for a while that there isn't nearly enough guidance about evals out there. This piece is an excellent step towards filling that gap.
Link 2025-02-12 Nomic Embed Text V2: An Open Source, Multilingual, Mixture-of-Experts Embedding Model [ https://substack.com/redirect/602fb569-8a8d-4234-a861-7cb46acffb2f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Nomic continue to release the most interesting and powerful embedding models. Their latest is Embed Text V2, an Apache 2.0 licensed multi-lingual 1.9GB model (here it is on Hugging Face [ https://substack.com/redirect/afac5459-af26-47dd-824b-29ff63e3e6b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) trained on "1.6 billion high-quality data pairs", which is the first embedding model I've seen to use a Mixture of Experts architecture:
In our experiments, we found that alternating MoE layers with 8 experts and top-2 routing provides the optimal balance between performance and efficiency. This results in 475M total parameters in the model, but only 305M active during training and inference.
I first tried it out using uv run like this:
uv run \
--with einops \
--with sentence-transformers \
--python 3.13 python
Then:
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("nomic-ai/nomic-embed-text-v2-moe", trust_remote_code=True)
sentences = ["Hello!", "¡Hola!"]
embeddings = model.encode(sentences, prompt_name="passage")
print(embeddings)
Then I got it working on my laptop using the llm-sentence-tranformers [ https://substack.com/redirect/74c9ed3c-af89-4776-b54a-f6634dda6931?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin like this:
llm install llm-sentence-transformers
llm install einops # additional necessary package
llm sentence-transformers register nomic-ai/nomic-embed-text-v2-moe --trust-remote-code

llm embed -m sentence-transformers/nomic-ai/nomic-embed-text-v2-moe -c 'string to embed'
This outputs a 768 item JSON array of floating point numbers to the terminal. These are Matryoshka embeddings [ https://substack.com/redirect/fb5ab1d4-e0e9-4467-9b79-f5ab78d628c0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] which means you can truncate that down to just the first 256 items and get similarity calculations that still work albeit slightly less well.
To use this for RAG you'll need to conform to Nomic's custom prompt format. For documents to be searched:
search_document: text of document goes here
And for search queries:
search_query: term to search for
I landed a new --prepend option [ https://substack.com/redirect/96a94516-2d5e-467b-99db-04b60c04c115?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for the llm embed-multi [ https://substack.com/redirect/d760ae76-2c7a-41e2-8c8b-eac96347d5cc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] command to help with that, but it's not out in a full release just yet.
I also released llm-sentence-transformers 0.3 [ https://substack.com/redirect/d16903c7-1744-454d-b17a-105c4f183f16?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with some minor improvements to make running this model more smooth.
Quote 2025-02-12
We want AI to “just work” for you; we realize how complicated our model and product offerings have gotten.
We hate the model picker as much as you do and want to return to magic unified intelligence.
We will next ship GPT-4.5, the model we called Orion internally, as our last non-chain-of-thought model.
After that, a top goal for us is to unify o-series models and GPT-series models by creating systems that can use all our tools, know when to think for a long time or not, and generally be useful for a very wide range of tasks.
In both ChatGPT and our API, we will release GPT-5 as a system that integrates a lot of our technology, including o3. We will no longer ship o3 as a standalone model.
[When asked about release dates [ https://substack.com/redirect/7473f12f-ed24-49bf-a503-f3232a2477bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for GPT 4.5 / GPT 5:] weeks / months [ https://substack.com/redirect/8c2b27d2-ed8c-4eeb-abd6-b2c720801d4f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Sam Altman [ https://substack.com/redirect/48d091f5-858b-4124-8c08-d180e769c8cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2025-02-13 python-build-standalone now has Python 3.14.0a5 [ https://substack.com/redirect/f3f57159-bcdf-414b-a1c6-0a813e0877db?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Exciting news from Charlie Marsh [ https://substack.com/redirect/3f98293c-24f1-49ae-a971-d8ddc19e7959?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
We just shipped the latest Python 3.14 alpha (3.14.0a5) to uv and python-build-standalone. This is the first release that includes the tail-calling interpreter.
Our initial benchmarks show a ~20-30% performance improvement across CPython.
This is an optimization that was first discussed in faster-cpython [ https://substack.com/redirect/8fbaa670-8cd3-4980-aece-34d8293228ea?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in January 2024, then landed earlier this month by Ken Jin [ https://substack.com/redirect/ae7850da-43ef-4148-90b2-2c80eb549481?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and included in the 3.14a05 release. The alpha release notes [ https://substack.com/redirect/a5b755d1-e9a3-4361-82c3-db36c78fb77b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] say:
A new type of interpreter based on tail calls has been added to CPython. For certain newer compilers, this interpreter provides significantly better performance. Preliminary numbers on our machines suggest anywhere from -3% to 30% faster Python code, and a geometric mean of 9-15% faster on pyperformance depending on platform and architecture. The baseline is Python 3.14 built with Clang 19 without this new interpreter.
This interpreter currently only works with Clang 19 and newer on x86-64 and AArch64 architectures. However, we expect that a future release of GCC will support this as well.
Including this in python-build-standalone [ https://substack.com/redirect/b3008cfa-0b33-4579-8621-d56bea7d4041?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] means it's now trivial to try out via uv [ https://substack.com/redirect/b2ab32e7-7fbd-43f7-b21e-54cffcdac225?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I upgraded to the latest uv like this:
pip install -U uv
Then ran uv python list to see the available versions:
cpython-3.14.0a5+freethreaded-macos-aarch64-none
cpython-3.14.0a5-macos-aarch64-none
cpython-3.13.2+freethreaded-macos-aarch64-none
cpython-3.13.2-macos-aarch64-none
cpython-3.13.1-macos-aarch64-none                   /opt/homebrew/opt/python@3.13/bin/python3.13 -> ../Frameworks/Python.framework/Versions/3.13/bin/python3.13
I downloaded the new alpha like this:
uv python install cpython-3.14.0a5
And tried it out like so:
uv run --python 3.14.0a5 python
The Astral team have been using Ken's bm_pystones.py [ https://substack.com/redirect/4fe3b325-f64a-4bfb-8921-757bb3d94c0c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] benchmarks script. I grabbed a copy like this:
wget 'https://gist.githubusercontent.com/Fidget-Spinner/e7bf204bf605680b0fc1540fe3777acf/raw/fa85c0f3464021a683245f075505860db5e8ba6b/bm_pystones.py [ https://substack.com/redirect/a68946e5-eb63-4a82-94ad-e84bb57340c1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]'
And ran it with uv:
uv run --python 3.14.0a5 bm_pystones.py
Giving:
Pystone(1.1) time for 50000 passes = 0.0511138
This machine benchmarks at 978209 pystones/second
Inspired by Charlie's example [ https://substack.com/redirect/3f98293c-24f1-49ae-a971-d8ddc19e7959?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] I decided to try the hyperfine [ https://substack.com/redirect/93239818-a21a-4a4d-9cb9-1a838677164a?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] benchmarking tool, which can run multiple commands to statistically compare their performance. I came up with this recipe:
brew install hyperfine
hyperfine \
"uv run --python 3.14.0a5 bm_pystones.py" \
"uv run --python 3.13 bm_pystones.py" \
-n tail-calling \
-n baseline \
--warmup 10
So 3.14.0a5 scored 1.12 times faster than 3.13 on the benchmark (on my extremely overloaded M2 MacBook Pro).
Link 2025-02-13 shot-scraper 1.6 with support for HTTP Archives [ https://substack.com/redirect/d3b6e5d8-ede1-4a5f-98a8-a7595d579ee9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
New release of my shot-scraper [ https://substack.com/redirect/e278c542-9f80-4e7c-ad67-1f85213954d6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] CLI tool for taking screenshots and scraping web pages.
The big new feature is HTTP Archive (HAR) [ https://substack.com/redirect/01736450-75fb-44ba-95bd-f842efb0826c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) support. The new shot-scraper har command [ https://substack.com/redirect/b06bed6b-f6da-45e2-a230-426b254dfade?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] can now create an archive of a page and all of its dependents like this:
shot-scraper har https://datasette.io/
This produces a datasette-io.har file (currently 163KB) which is JSON representing the full set of requests used to render that page. Here's a copy of that file [ https://substack.com/redirect/208d9340-e17b-4801-82c1-3041e442b26f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. You can visualize that here using ericduran.github.io/chromeHAR [ https://substack.com/redirect/42d3b57b-b50f-4b6f-8a48-9b3cbd0519eb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
That JSON includes full copies of all of the responses, base64 encoded if they are binary files such as images.
You can add the --zip flag to instead get a datasette-io.har.zip file, containing JSON data in har.har but with the response bodies saved as separate files in that archive.
The shot-scraper multi command lets you run shot-scraper against multiple URLs in sequence, specified using a YAML file. That command now takes a --har option (or --har-zip or --har-file name-of-file), described in the documentation [ https://substack.com/redirect/7e0a64de-a11e-4c42-9aa3-ac1e591a77d1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], which will produce a HAR at the same time as taking the screenshots.
Shots are usually defined in YAML that looks like this:
- output: example.com.png
url: https://www.example.com/
- output: w3c.org.png
url: https://www.w3.org/
You can now omit the output: keys and generate a HAR file without taking any screenshots at all:
- url: httpss://www.example.com/
- url: https://www.w3.org/
Run like this:
shot-scraper multi shots.yml --har
Which outputs:
Skipping screenshot of 'https://example.com/'
Skipping screenshot of 'https://www.w3.org/'
Wrote to HAR file: trace.har
shot-scraper is built on top of Playwright, and the new features use the browser.new_context(record_har_path=...) [ https://substack.com/redirect/8d377ea9-8987-41d2-bc7b-ea59c5c65110?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] parameter.
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVGN4TVRNeE1ERXNJbWxoZENJNk1UY3pPVFE1TkRVek1Td2laWGh3SWpveE56Y3hNRE13TlRNeExDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuNUVvcVNfdG5razRhZWt4c3ZMUTRoZTdmV0piSmdETG5hNmlNOEFCanpuUSIsInAiOjE1NzExMzEwMSwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzM5NDk0NTMxLCJleHAiOjE3NDIwODY1MzEsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.c1Kw4Cldk5PZC0rzoUXpP-XqN5DPXrDCJxJLJnw-ThQ?
