# Qwen2.5-Coder-32B is an LLM that can code well that runs on my Mac

**From:** "Simon Willison from Simon Willison’s Newsletter" <simonw@substack.com>
**Date:** 2024-11-13T16:40:56.000Z
**Folder:** simon

---

View this post on the web at https://simonw.substack.com/p/qwen25-coder-32b-is-an-llm-that-can

In this newsletter:
Qwen2.5-Coder-32B is an LLM that can code well that runs on my Mac
Visualizing local election results with Datasette, Observable and MapLibre GL
Plus 9 links and 4 quotations
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.
Qwen2.5-Coder-32B is an LLM that can code well that runs on my Mac [ https://substack.com/redirect/35bd9ebf-0b0b-41da-ab26-291269f27db8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-11-12
There's a whole lot of buzz around the new Qwen2.5-Coder Series [ https://substack.com/redirect/26fb9d5f-dadd-41cc-ad64-738dc03973b7?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] of open source (Apache 2.0 licensed) LLM releases from Alibaba's Qwen research team. On first impression it looks like the buzz is well deserved.
Qwen claim:
Qwen2.5-Coder-32B-Instruct has become the current SOTA open-source code model, matching the coding capabilities of GPT-4o.
That's a big claim for a 32B model that's small enough that it can run on my 64GB MacBook Pro M2. The Qwen published scores look impressive, comparing favorably with GPT-4o and Claude 3.5 Sonnet (October 2024) edition across various code-related benchmarks:
How about benchmarks from other researchers? Paul Gauthier's Aider benchmarks [ https://substack.com/redirect/f37593b5-c6b2-45d3-923c-483ab1820da6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] have a great reputation and Paul reports [ https://substack.com/redirect/d4f8e3c6-d7a9-446d-8619-70982a4c0304?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The new Qwen 2.5 Coder models did very well on aider's code editing benchmark. The 32B Instruct model scored in between GPT-4o and 3.5 Haiku.
84% 3.5 Sonnet, 75% 3.5 Haiku, 74% Qwen2.5 Coder 32B, 71% GPT-4o, 69% Qwen2.5 Coder 14B, 58% Qwen2.5 Coder 7B
That was for the Aider "whole edit" benchmark. The "diff" benchmark scores well [ https://substack.com/redirect/cc615239-b97f-4492-8f3c-f87457aa53fc?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] too, with Qwen2.5 Coder 32B tying with GPT-4o (but a little behind Claude 3.5 Haiku).
Given these scores (and the positive buzz on Reddit [ https://substack.com/redirect/8904220c-1478-46b8-b7e3-43e85b966b91?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) I had to try it for myself.
My attempts to run the Qwen/Qwen2.5-Coder-32B-Instruct-GGUF [ https://substack.com/redirect/aaa39c4b-8626-4a5c-b11c-3a7e3bdd9750?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] Q8 using llm-gguf [ https://substack.com/redirect/2b619f36-a334-4c16-ae3d-4387b176552e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] were a bit too slow, because I don't have that compiled to use my Mac's GPU at the moment.
But both the Ollama [ https://substack.com/redirect/3a067e9f-79d5-490d-b481-f89e0a5cf814?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] version and the MLX [ https://substack.com/redirect/a680bf2f-2eda-4ec1-a561-a77ba1b7e018?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] version worked great!
I installed the Ollama version using:
ollama pull qwen2.5-coder:32b

That fetched a 20GB quantized file. I ran a prompt through that using my LLM [ https://substack.com/redirect/6836c33d-ea41-4636-93a8-2a5fad956ba8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] tool and Sergey Alexandrov's llm-ollama [ https://substack.com/redirect/84f5d642-5ede-43d5-a5d0-e279c8b0527d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin like this:
llm install llm-ollama
llm models # Confirming the new model is present
llm -m qwen2.5-coder:32b 'python function that takes URL to a CSV file and path to a SQLite database, fetches the CSV with the standard library, creates a table with the right columns and inserts the data'

Here's the result [ https://substack.com/redirect/836779b2-29b0-487a-8a4b-4feaf51d372b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. The code worked, but I had to work around a frustrating ssl bug first (which wouldn't have been an issue if I'd allowed the model to use requests or httpx instead of the standard library).
I also tried running it using the Apple Silicon fast array framework MLX using the mlx-llm [ https://substack.com/redirect/1f6ad887-57a0-4db8-8b64-50390495e500?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] library directly, run via uv [ https://substack.com/redirect/9f2ccfb6-4f91-4bed-aa2f-dfec0099c970?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] like this:
uv run --with mlx-lm \
mlx_lm.generate \
--model mlx-community/Qwen2.5-Coder-32B-Instruct-8bit \
--max-tokens 4000 \
--prompt 'write me a python function that renders a mandelbrot fractal as wide as the current terminal'

That gave me a very satisfying result [ https://substack.com/redirect/75b000c4-6f98-4da4-9572-140c89da6884?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - when I ran the code it generated in a terminal I got this:
MLX reported the following performance metrics:
Prompt: 49 tokens, 95.691 tokens-per-sec
Generation: 723 tokens, 10.016 tokens-per-sec
Peak memory: 32.685 GB
Let's see how it does on the Pelican on a bicycle benchmark [ https://substack.com/redirect/0e604479-de7d-45fe-ab7b-0662983249d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
llm -m qwen2.5-coder:32b 'Generate an SVG of a pelican riding a bicycle'
Here's what I got [ https://substack.com/redirect/8e936fc1-31c5-4221-aef4-96fe337369b6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Questionable Pelican SVG drawings aside, this is a really promising development. 32GB is just small enough that I can run the model on my Mac without having to quit every other application I'm running, and both the speed and the quality of the results feel genuinely competitive with the current best of the hosted models.
Given that code assistance is probably around 80% of my LLM usage at the moment this is a meaningfully useful release for how I engage with this class of technology.
Visualizing local election results with Datasette, Observable and MapLibre GL [ https://substack.com/redirect/ae9eaac2-85c5-427d-abd8-c05aa4e87988?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - 2024-11-09
Alex Garcia and myself hosted the first Datasette Open Office Hours [ https://substack.com/redirect/6254be78-82a5-43e0-a12d-42cbffe871cb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on Friday - a live-streamed video session where we hacked on a project together and took questions and tips from community members on Discord.
We didn't record this one (surprisingly not a feature that Discord offers) but we hope to do more of these and record them in the future.
This post is a detailed write-up of what we built during the session.
San Mateo County election results [ https://substack.com/redirect/a3603348-3599-41ba-8e47-45776a31d580?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Importing CSV data into Datasette [ https://substack.com/redirect/14b4bbf8-f646-42ce-a3c0-0ad9e8ce47ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Modifying the schema [ https://substack.com/redirect/bcb42450-0332-47eb-97de-7ed2ac26f5c3?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Faceting and filtering the table [ https://substack.com/redirect/3399eae6-0155-44a8-ada5-7bc75517a4d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Importing geospatial precinct shapes [ https://substack.com/redirect/760d1a7e-0832-4e68-9cc5-6cf758c986f8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Enriching that data to extract the precinct IDs [ https://substack.com/redirect/a1346b25-76ec-4eb4-9f84-d55d9436e126?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Running a join [ https://substack.com/redirect/845063de-dadf-40d9-b4b4-91e4bcd8b2ae?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Creating an API token to access the data [ https://substack.com/redirect/cf21ac7f-919d-458d-8e86-a7fa811390f5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Getting CORS working [ https://substack.com/redirect/ebc766f0-0b34-4177-8aaa-d13116117e4f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Working with Datasette in Observable [ https://substack.com/redirect/18825dea-0bad-41c8-aba0-6d693acaf3d8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Visualizing those with MapLibre GL [ https://substack.com/redirect/1ed6e193-1fb2-48d6-aa6b-8b425c6fab05?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Observable Plot [ https://substack.com/redirect/226d12bf-77b2-4bc6-8a4e-1da2a7a920ff?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Bringing it all together [ https://substack.com/redirect/61da7929-a6a2-423c-929b-030e00526fce?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
We'll be doing this again [ https://substack.com/redirect/d8a63150-fc46-4367-9946-462f95442f84?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
San Mateo County election results
I live in El Granada, a tiny town just north of Half Moon Bay in San Mateo County, California.
Every county appears to handle counting and publishing election results differently. For San Mateo County the results are published on this page [ https://substack.com/redirect/a78190e9-27a4-4b0b-9c4d-e58074c00952?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], and detailed per-precinct and per-candidate breakdowns are made available as a CSV file.
(I optimistically set up a Git scraper [ https://substack.com/redirect/b258278d-5391-4020-b5ec-182fa0011782?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for these results in simonw/scrape-san-mateo-county-election-results-2024 [ https://substack.com/redirect/b0eea61e-7f85-490d-bd73-1f2fec6c12fa?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] only to learn that the CSV is updated just once a day, not continually as the ballots are counted.)
I'm particularly invested in the results of the Granada Community Services District [ https://substack.com/redirect/18908669-de79-4b58-a556-3ed78f28c69b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] board member elections. Our little town of El Granada is in "unincorporated San Mateo County" which means we don't have a mayor or any local officials, so the closest we get to hyper-local government is the officials that run our local sewage and parks organization! My partner Natalie ran the candidate forum event [ https://substack.com/redirect/69dee9a9-5930-495e-9616-25cb78b47b9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] (effectively the debate) featuring three of the four candidates running for the two open places on the board.
Let's explore the data for that race using Datasette.
Importing CSV data into Datasette
I ran my part of the demo using Datasette Cloud [ https://substack.com/redirect/c9d5422c-217b-41a8-bb7b-7336fabe236b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], the beta of my new hosted Datasette service.
I started by using the pre-configured datasette-import [ https://substack.com/redirect/de22dfbb-a6cf-4035-bb3c-b8aae328f57d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin to import the data from the CSV file into a fresh table:
Modifying the schema
The table imported cleanly, but all of the columns from the CSV were still being treated as text. I used the datasette-edit-schema [ https://substack.com/redirect/bb6e0887-27dd-46e1-86c6-3a5000ab44bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] plugin to switch the relevant columns to integers so that we could run sums and sorts against them.
(I also noted that I really should add a "detect column types" feature to that plugin!)
The resulting 15,589 rows represent counts from individual precincts around the county for each of the races and measures on the ballot, with a row per precinct per candidate/choice per race.
Faceting and filtering the table
Since I'm interested in the Granada Community Services District election, I applied a facet on "Contest_title" and then used that to select that specific race.
I applied additional facets on "candidate_name" and "Precinct name".
This looks right to me: we have 7 precincts and 4 candidates for 28 rows in total.
Importing geospatial precinct shapes
Those precinct names are pretty non-descriptive! What does 33001 mean?
To answer that question, I added a new table.
San Mateo County offers precinct maps [ https://substack.com/redirect/4269d28f-105d-4c21-acec-6adf4482b49d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in the form of 23 PDF files. Our precincts are in the "Unincorporated Coastside" file:
Thankfully the county also makes that data available as geospatial data [ https://substack.com/redirect/fce14b66-0dbb-4c7b-ab02-a5677af2bc7f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], hosted using Socrata with an option to export as GeoJSON.
The datasette-import plugin can handle JSON files... and if a JSON file contains a top-level object with a key that is an array of objects, it will import those objects as a table.
Dragging that file into Datasette is enough to import it as a table with a properties JSON column containing properties and a geometryJSON columnn with the GeoJSON geometry.
Here's where another plugin kicks in: datasette-leaflet-geojson [ https://substack.com/redirect/9d6b30ee-18fb-4340-8d69-1b976c7151b0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] looks for columns that contain valid GeoJSON geometries and... draws them on a map!
So now we can see the shape of the individual geometries.
Enriching that data to extract the precinct IDs
The precinctid is present in the data, but it's tucked away in a JSON object in that propertiesJSON blob. It would be more convenient if it was a top-level column.
Datasette's enrichments feature [ https://substack.com/redirect/22dab30d-2984-4d41-9b8c-276580842b3b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] provides tools for running operations against every row in a table and adding new columns based on the results.
My Datasette Cloud instance was missing the datasette-enrichments-quickjs plugin [ https://substack.com/redirect/ea058016-79c4-4240-bdc7-19bc20acf032?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that would let me run JavaScript code against the data. I used my privileged access on Datasette Cloud to add that plugin to my requirements and restarted the instance to install it.
I used that to run this JavaScript code against every row in the table and saved the output in a new precinct_id column:
function enrich(row) {
return JSON.parse(row.properties).precinctid;
}
This took less than a second to run, adding and populating a new precinct_id column for the table.
Running a join
I demonstrated how to run a join between the election results and the precincts table using the Datasette SQL query editor.
I tried a few different things, but the most interesting query was this one:
select
Precinct_name,
precincts.geometry,
total_ballots,
json_group_object(
candidate_name,
total_votes
) as votes_by_candidate
from
election_results
join precincts on election_results.Precinct_name = precincts.precinct_id
where
Contest_title = "Granada Community Services District Members, Board of Directors"
group by
Precinct_name,
precincts.geometry,
total_ballots;
Creating an API token to access the data
I was nearly ready to hand over to Alex for the second half of our demo, where he would use Observable Notebooks to build some custom visualizations on top of the data.
A great pattern for this is to host the data in Datasette and then fetch it into Observable via the Datasette JSON API.
Since Datasette Cloud instances are private by default we would need to create an API token that could do this.
I used this interface (from the datasette-auth-tokens plugin [ https://substack.com/redirect/498e8ebf-26a7-4247-9f6c-2b0a3c06b9df?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]) to create a new token with read-only access to all databases and tables in the instance:
Since we're running a dedicated instance just for Datasette Public Office Hours there's no reason not to distribute that read-only token in publically accessible code.
Getting CORS working
Embarrassingly, I had forgotten that we would need CORS headers in order to access the data from an Observable notebook. Thankfully we have another plugin for that: datasette-cors [ https://substack.com/redirect/0d0b9891-d2cd-45f9-bf0c-7ea05e237292?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. I installed that quickly and we confirmed that it granted access to the API from Observable as intended.
I handed over to Alex for the next section of the demo.
Working with Datasette in Observable
Alex started by running a SQL query from client-side JavaScript to pull in the joined data for our specific El Granada race:
sql = `
select
Precinct_name,
precincts.geometry,
Split_name,
Reporting_flag,
Update_count,
Pct_Id,
Pct_seq_nbr,
Reg_voters,
Turn_Out,
Contest_Id,
Contest_seq_nbr,
Contest_title,
Contest_party_name,
Selectable_Options,
candidate_id,
candidate_name,
Candidate_Type,
cand_seq_nbr,
Party_Code,
total_ballots,
total_votes,
total_under_votes,
total_over_votes,
[Vote Centers_ballots],
[Vote Centers_votes],
[Vote Centers_under_votes],
[Vote Centers_over_votes],
[Vote by Mail_ballots],
[Vote by Mail_votes],
[Vote by Mail_under_votes],
[Vote by Mail_over_votes]
from
election_results join precincts on election_results.Precinct_name = precincts.precinct_id
where "Contest_title" = "Granada Community Services District Members, Board of Directors"
limit 101;`
And in the next cell:
raw_data = fetch(
`https://datasette-public-office-hours.datasette.cloud/data/-/query.json?_shape=array&sql=${encodeURIComponent(
sql
)}`,
{
headers: {
Authorization: `Bearer ${secret}`
}
}
).then((r) => r.json)
Note the ?_shape=array parameter there, which causes Datasette to output the results directly as a JSON array of objects.
That's all it takes to get the data into Observable. Adding another cell like this confirms that the data is now available:
Inputs.table(raw_data)
Visualizing those with MapLibre GL
There are plenty of good options for visualizing GeoJSON data using JavaScript in an Observable notebook.
Alex started with MapLibre GL [ https://substack.com/redirect/5e2fe2b8-0889-4d21-977b-2b89377b6224?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], using the excellent OpenFreeMap 3D tiles [ https://substack.com/redirect/4f5b3ec4-669c-4775-b3e0-35a1d4e59b14?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
viewof map = {
const container = html``;
yield container;
const map = (container.value = new maplibregl.Map({
container,
zoom: 2,
//style: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
style: "https://tiles.openfreemap.org/styles/liberty",
scrollZoom: true
}));
yield container;

map.on("load", function  {
map.fitBounds(d3.geoBounds(data), { duration: 0 });
map.addSource("precincts", {
type: "geojson",
data: data
});
map.addLayer({
id: "precincts",
type: "fill",
source: "precincts",
paint: {
"fill-opacity": 0.4,
"fill-color": [
"case",
["==", ["get", "ratio"], null], "#000000",
[
"interpolate",
["linear"],
["get", "ratio"],
0.0, "#0000ff",
0.5, "#d3d3d3",
1.0, "#ff0000"
]
]
}
});
map.on("click", "precincts", (e) => {
const { precinct, ratio } = e.features[0].properties;
const description = JSON.stringify;

new maplibregl.Popup
.setLngLat(e.lngLat)
.setHTML(description)
.addTo(map);
});
});
invalidation.then( => map.remove);
}
(This is just one of several iterations, I didn't capture detailed notes of every change Alex made to the code.)
Observable Plot
Observable notebooks come pre-loaded with the excellent Observable Plot charting library - Mike Bostock's high-level charting tool built on top of D3.
Alex used that to first render the shapes of the precincts directly, without even needing a tiled basemap:
Plot.plot({
width,
height: 600,
legend: true,
projection: {
type: "conic-conformal",
parallels: [37 + 4 / 60, 38 + 26 / 60],
rotate: [120 + 30 / 60, 0],
domain: data
},
marks: [
Plot.geo(data, {
strokeOpacity: 0.1,
fill: "total_votes",
title: (d) => JSON.stringify(d.properties),
tip: true
})
]
})
The parallels and rotate options there come from the handy veltman/d3-stateplane [ https://substack.com/redirect/927839a0-2d42-4fd0-87d3-5b9619ba454d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] repo, which lists recommended settings for the State Plane Coordinate System [ https://substack.com/redirect/7b078973-c7a3-4642-b0a1-7bd25863c9a0?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] used with projections in D3. Those values are for California Zone 3 [ https://substack.com/redirect/e2883933-d1be-4984-87be-7c231d6b8c9c?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Bringing it all together
For the grand finale, Alex combined everything learned so far to build an interactive map allowing a user to select any of the 110 races on the ballot and see a heatmap of results for any selected candidate and option:
You can try this out in Alex's notebook [ https://substack.com/redirect/3558d47b-17db-41e9-8879-e405bf2f2a56?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]. Here's the relevant code (Observable cells are divided by // --- comments). Note that Observable notebooks are reactive and allow variables to be referenced out of order.
// Select the contest
viewof contest = Inputs.select(contests, { label: "Choose a contest" })

// ---

// And the candidate
viewof candidate = Inputs.radio(
candidates,
{
label: "Choose a candidate",
value: candidates[0]
}
)

// ---

// Show the map itself
Plot.plot({
width,
height: 600,
legend: true,
color: { scheme: "blues", legend: true },
projection: {
type: "mercator",
domain: data2
},
marks: [
Plot.geo(data2, {
strokeOpacity: 0.1,
fill: "ratio",
tip: true
})
]
})
# ---
data2 = ({
type: "FeatureCollection",
features: raw_data2.map((d) => ({
type: "Feature",
properties: {
precinct: d.Precinct_name,
total_ballots: d.total_ballots,
ratio: JSON.parse(d.votes_by_candidate)[candidate] / d.total_ballots
},
geometry: JSON.parse(d.geometry)
}))
})

// ---

raw_data2 = query(
`select
Precinct_name,
precincts.geometry,
total_ballots,
json_grop_object(
candidate_name,
total_votes
) as votes_by_candidate
from
election_results
join precincts on election_results.Precinct_name = precincts.precinct_id
where Contest_title = :contest
group by
Precinct_name,
precincts.geometry,
total_ballots;`,
{ contest }
)

// ---

raw_data2 = query(
`select
Precinct_name,
precincts.geometry,
total_ballots,
json_group_object(
candidate_name,
total_votes
) as votes_by_candidate
from
election_results
join precincts on election_results.Precinct_name = precincts.precinct_id
where Contest_title = :contest
group by
Precinct_name,
precincts.geometry,
total_ballots;`,
{ contest }
)

// ---

// Fetch the available contests
contests = query("select distinct Contest_title from election_results").then(
(d) => d.map((d) => d.Contest_title)
)

// ---

// Extract available candidates for selected contest

candidates = Object.keys(
JSON.parse(raw_data2[0].votes_by_candidate)
)

// ---

function query(sql, params = {}) {
return fetch(
`https://datasette-public-office-hours.datasette.cloud/data/-/query.json?${new URLSearchParams(
{ sql, _shape: "array", ...params }
).toString}`,
{
headers: {
Authorization: `Bearer ${secret}`
}
}
).then((r) => r.json);
}
We'll be doing this again
This was our first time trying something like this and I think it worked really well. We're already thinking about ways to improve it next time:
I want to record these sessions and make them available on YouTube for people who couldn't be there live
It would be fun to mix up the format. I'm particularly keen on getting more people involved giving demos - maybe having 5-10 minute lightning demo slots so we can see what other people are working on
Keep an eye on this blog or on the Datasette Discord [ https://substack.com/redirect/01864c1d-732f-4597-ac2f-726e7a0a7db2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] for news about future sessions.
Link 2024-11-08 ChainForge [ https://substack.com/redirect/fc4bc872-70a5-4e52-8805-93eacfc9f0cf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I'm still on the hunt for good options for running evaluations against prompts. ChainForge offers an interesting approach, calling itself "an open-source visual programming environment for prompt engineering".
The interface is one of those boxes-and-lines visual programming tools, which reminds me of Yahoo Pipes [ https://substack.com/redirect/8bce1fe8-4a36-495e-b258-edef4a04f46b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
It's open source (from a team at Harvard) and written in Python, which means you can run a local copy instantly via uvx like this:
uvx chainforge serve

You can then configure it with API keys to various providers (OpenAI worked for me, Anthropic models returned JSON parsing errors due to a 500 page from the ChainForge proxy) and start trying it out.
The "Add Node" menu shows the full list of capabilities.
The JavaScript and Python evaluation blocks are particularly interesting: the JavaScript one runs outside of a sandbox using plain eval, while the Python one still runs in your browser but uses Pyodide in a Web Worker.
Link 2024-11-08 uv 0.5.0 [ https://substack.com/redirect/0d2e5ade-3b14-46e6-bc8b-4d4e8948b8e2?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
The first backwards-incompatible (in minor ways) release after 30 releases without a breaking change [ https://substack.com/redirect/210b7251-f77d-4690-9c1b-8f42bfe06fb9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
I found out about this release this morning when I filed an issue [ https://substack.com/redirect/ddb1b901-5fce-4e49-8c2e-d81ccd3c0e46?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] about a fiddly usability problem I had encountered with the combo of uv and conda... and learned that the exact problem had already been fixed in the brand new version!
Quote 2024-11-09
This is a very friendly and supportive place where you are surrounded by peers - we all want to help each other succeed. The golden rule of this server is:
Don't ever try to impress anyone here with your knowledge! Instead try to impress folks here with your desire to learn, and desire to help others learn.
fast.ai Discord Server [ https://substack.com/redirect/81a2423f-1d39-4dcc-b032-4a6372f9c3fd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-10 Everything I've learned so far about running local LLMs [ https://substack.com/redirect/8bf8ebfc-c93a-4d86-a055-8cffefafa148?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Chris Wellons shares detailed notes on his experience running local LLMs on Windows - though most of these tips apply to other operating systems as well.
This is great, there's a ton of detail here and the root recommendations are very solid: Use llama-server from llama.cpp [ https://substack.com/redirect/3eb363b1-42a6-4d4d-92d0-1b0126e1eecf?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] and try ~8B models first (Chris likes Llama 3.1 8B Instruct at Q4_K_M as a first model), anything over 10B probably won't run well on a CPU so you'll need to consider your available GPU VRAM.
This is neat:
Just for fun, I ported llama.cpp to Windows XP and ran a 360M model [ https://substack.com/redirect/9a4fbb4e-9540-4736-9c0e-730a4bc637bb?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] on a 2008-era laptop. It was magical to load that old laptop with technology that, at the time it was new, would have been worth billions of dollars.
I need to spend more time with Chris's favourite models, Mistral-Nemo-2407 (12B) and Qwen2.5-14B/72B.
Chris also built illume [ https://substack.com/redirect/b46aac55-21fa-408f-af93-d1454b856cc5?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], a Go CLI tool for interacting with models that looks similar to my own LLM [ https://substack.com/redirect/6836c33d-ea41-4636-93a8-2a5fad956ba8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] project.
Link 2024-11-11 MDN Browser Support Timelines [ https://substack.com/redirect/1c7e6731-84c6-44f9-b838-ffddbd51b628?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I complained on Hacker News [ https://substack.com/redirect/7f30a688-546c-451b-a927-ceff78398bc1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] today that I wished the MDN browser compatibility ables - like this one for the Web Locks API [ https://substack.com/redirect/2b3a9925-6a68-428a-8c7b-730bacc211bd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - included an indication as to when each browser was released rather than just the browser numbers.
It turns out they do! If you click on each browser version in turn you can see an expanded area showing the browser release date:
There's even an inline help tip [ https://substack.com/redirect/4b9dd7b2-cffc-4ad4-8dde-86d91a50ad62?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] telling you about the feature, which I've been studiously ignoring for years.
I want to see all the information at once without having to click through each browser. I had a poke around in the Firefox network tab and found https://bcd.developer.mozilla.org/bcd/api/v0/current/api.Lock.json [ https://substack.com/redirect/65afb330-9a10-4b70-97a5-259b5bf559f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]- a JSON document containing browser support details (with release dates) for that API... and it was served using access-control-allow-origin: * which means I can hit it from my own little client-side applications.
I decided to build something with an autocomplete drop-down interface for selecting the API. That meant I'd need a list of all of the available APIs, and I used GitHub code search to find that in the mdn/browser-compat-data [ https://substack.com/redirect/a1ca2340-2b4a-47c8-8934-123dedd5fd58?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]repository, in the api/ directory.
I needed the list of files in that directory for my autocomplete. Since there are just over 1,000 of those the regular GitHub contents API [ https://substack.com/redirect/dca649a6-317b-4619-b5a5-92b85a8a61c8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] won't return them all, so I switched to the tree API [ https://substack.com/redirect/b7e603a9-59c9-43b3-be87-52bfcd7e27e1?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]instead.
Here's the finished tool [ https://substack.com/redirect/1c7e6731-84c6-44f9-b838-ffddbd51b628?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] - source code here [ https://substack.com/redirect/60bd8e02-10ec-4c5b-afcc-3b52c063d7fd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
95% of the code was written by LLMs, but I did a whole lot of assembly and iterating to get it to the finished state. Three of the transcripts for that:
Web Locks API Browser Support Timeline [ https://substack.com/redirect/7edaabe9-9561-4c31-a1bd-89fc33a88a93?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] in which I paste in the original API JSON and ask it to come up with a timeline visualization for it.
Enhancing API Feature Display with URL Hash [ https://substack.com/redirect/98903e07-5943-4524-87cd-24ba2ed18a6b?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where I dumped in a more complex JSON example to get it to show multiple APIs on the same page, and also had it add #fragment bookmarking to the tool
Fetch GitHub API Data Hierarchy [ https://substack.com/redirect/6e86dd3a-7d2c-4948-bf12-e2710afe295d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] where I got it to write me an async JavaScript function for fetching a directory listing from that tree API.
Quote 2024-11-11
As a junior engineer, there's simply no substitute for getting the first 100K lines of code under your belt. The "start over each day" method will help get you to those 100K lines faster.
You might think covering the same ground multiple times isn't as valuable as getting 100K diverse lines of code. I disagree. Solving the same problem repeatedly is actually really beneficial for retaining knowledge of patterns you figure out.
You only need 5K perfect lines to see all the major patterns once. The other 95K lines are repetition to rewire your neurons.
Grant Slatton [ https://substack.com/redirect/43917f6b-0bdf-4a04-8e1e-813aa24fc233?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Quote 2024-11-11
That development time acceleration of 4 days down to 20 minutes… that’s equivalent to about 10 years of Moore’s Law cycles. That is, using generative AI like this is equivalent to computers getting 10 years better overnight.
That was a real eye-opening framing for me. AI isn’t magical, it’s not sentient, it’s not the end of the world nor our saviour; we don’t need to endlessly debate “intelligence” or “reasoning.” It’s just that… computers got 10 years better. The iPhone was first released in 2007. Imagine if it had come out in 1997 instead. We wouldn’t even know what to do with it.
Matt Webb [ https://substack.com/redirect/4a4f5ee5-422a-46be-98a4-4ca70ea1d7a6?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Link 2024-11-11 Binary vector embeddings are so cool [ https://substack.com/redirect/ce616389-ad5d-464a-8795-dd8845de9b34?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Evan Schwartz:
Vector embeddings by themselves are pretty neat. Binary quantized vector embeddings are extra impressive. In short, they can retain 95+% retrieval accuracy with 32x compression and ~25x retrieval speedup.
It's so unintuitive how well this trick works: take a vector of 1024x4 byte floating point numbers (4096 bytes = 32,768 bits), turn that into an array of single bits for > 0 or <= 0 which reduces it to just 1024 bits or 128 bytes - a 1/32 reduction.
Now you can compare vectors using a simple Hamming distance - a count of the number of bits that differ - and yet still get embedding similarity scores that are only around 10% less accurate than if you had used the much larger floating point numbers.
Evan digs into models that this works for, which include OpenAI's text-embedding-3-large and the small but powerful all-MiniLM-L6-v2.
Link 2024-11-11 How I ship projects at big tech companies [ https://substack.com/redirect/a435a634-337a-49c3-b9fd-c9d4b95c3d88?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
This piece by Sean Goedecke on shipping features at larger tech companies is fantastic.
Why do so many engineers think shipping is easy? I know it sounds extreme, but I think many engineers do not understand what shipping even is inside a large tech company. What does it mean to ship? It does not mean deploying code or even making a feature available to users. Shipping is a social construct within a company. Concretely, that means that a project is shipped when the important people at your company believe it is shipped.
Sean emphasizes communication, building confidence and gaining trust and the importance of deploying previews of the feature (for example using feature flags) as early as possible to get that crucial internal buy-in and feedback from other teams.
I think a lot of engineers hold off on deploys essentially out of fear. If you want to ship, you need to do the exact opposite: you need to deploy as much as you can as early as possible, and you need to do the scariest changes as early as you can possibly do them. Remember that you have the most end-to-end context on the project, which means you should be the least scared of scary changes.
Link 2024-11-12 Ars Live: Our first encounter with manipulative AI [ https://substack.com/redirect/63afc821-faac-4689-a806-2ad1d2b2a195?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
I'm participating in a live conversation with Benj Edwards on 19th November reminiscing over that incredible time back in February last year when Bing went feral [ https://substack.com/redirect/a00e57f6-ff29-42ff-90d3-421acdd5872f?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
Link 2024-11-13 django-plugin-django-debug-toolbar [ https://substack.com/redirect/d4a7df4b-4e21-4346-92ab-01c8fea5ddb8?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Tom Viner built a plugin for my DJP Django plugin system [ https://substack.com/redirect/384de0d1-02a4-437a-a8a3-281d9dfee513?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] that configures the excellent django-debug-toolbar [ https://substack.com/redirect/5c01eee9-61d8-4b57-b34e-fe9967b65f83?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] debugging tool.
You can see everything it sets up for you in this Python code [ https://substack.com/redirect/57a0a57f-a778-4d93-bd9d-71488c080b99?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]: it configures installed apps, URL patterns and middleware and sets the INTERNAL_IPS and DEBUG settings.
Here are Tom's running notes [ https://substack.com/redirect/fa1d036d-bb72-4520-8ba6-87f3eb286d9e?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] as he created the plugin.
Link 2024-11-13 Ollama: Llama 3.2 Vision [ https://substack.com/redirect/c621fd66-9c25-426d-9650-a164c65b3586?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]:
Ollama released version 0.4 last week [ https://substack.com/redirect/236a5592-bc17-4dc8-b0e7-09b5037aba26?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] with support for Meta's first Llama vision model, Llama 3.2 [ https://substack.com/redirect/c027decb-49b1-4be4-a442-6f72a45a3e38?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ].
If you have Ollama installed you can fetch the 11B model (7.9 GB) like this:
ollama pull llama3.2-vision

Or the larger 90B model (55GB download, likely needs ~88GB of RAM) like this:
ollama pull llama3.2-vision:90b

I was delighted to learn that Sukhbinder Singh had already contributed [ https://substack.com/redirect/e2abc2c8-0e00-4715-ae60-0cb24ba041cd?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] support for LLM attachments [ https://substack.com/redirect/3bbc26ba-c12b-4bb0-953c-050338f3f07d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ] to Sergey Alexandrov's llm-ollama [ https://substack.com/redirect/84f5d642-5ede-43d5-a5d0-e279c8b0527d?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]plugin, which means the following works once you've pulled the models:
llm install --upgrade llm-ollama
llm -m llama3.2-vision:latest 'describe' \
-a https://static.simonwillison.net/static/2024/pelican.jpg

This image features a brown pelican standing on rocks, facing the camera and positioned to the left of center. The bird's long beak is a light brown color with a darker tip, while its white neck is adorned with gray feathers that continue down to its body. Its legs are also gray.
In the background, out-of-focus boats and water are visible, providing context for the pelican's environment.
That's not a bad description of this image [ https://substack.com/redirect/d36a46d3-2e71-4872-8c2c-2311d1fc92f4?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], especially for a 7.9GB model that runs happily on my MacBook Pro.
Quote 2024-11-13
This tutorial exists because of a particular quirk of mine: I love to write tutorials about things as I learn them. This is the backstory of TRPL [ https://substack.com/redirect/feb50c8a-e6cf-4865-867c-7c79a3b32544?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ], of which an ancient draft was "Rust for Rubyists [ https://substack.com/redirect/9a02f1d9-ef3a-47f5-a3c0-cda2c8f6bb56?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]." You only get to look at a problem as a beginner once, and so I think writing this stuff down is interesting. It also helps me clarify what I'm learning to myself.
Steve Klabnik [ https://substack.com/redirect/d043d9ec-0315-4fb4-90d1-acc9b8133de9?j=eyJ1IjoicXd0ciJ9.0tEpqnOrcfuKYRYnEOurmlOZ_pVIUnS06konjQA-bCs ]
Thanks for reading Simon Willison’s Newsletter! Subscribe for free to receive new posts and support my work.

Unsubscribe https://substack.com/redirect/2/eyJlIjoiaHR0cHM6Ly9zaW1vbncuc3Vic3RhY2suY29tL2FjdGlvbi9kaXNhYmxlX2VtYWlsP3Rva2VuPWV5SjFjMlZ5WDJsa0lqb3hNalUxTlRrNUxDSndiM04wWDJsa0lqb3hOVEUyTURjek16SXNJbWxoZENJNk1UY3pNVFV4TmpBNE1pd2laWGh3SWpveE56WXpNRFV5TURneUxDSnBjM01pT2lKd2RXSXRNVEUzTXpNNE5pSXNJbk4xWWlJNkltUnBjMkZpYkdWZlpXMWhhV3dpZlEuVjRuZWF2VVVkR0FYcFVwek9jTXVNTzRwSTdZRmJfV2hXdnBYdGtOOEVuVSIsInAiOjE1MTYwNzMzMiwicyI6MTE3MzM4NiwiZiI6dHJ1ZSwidSI6MTI1NTU5OSwiaWF0IjoxNzMxNTE2MDgyLCJleHAiOjE3MzQxMDgwODIsImlzcyI6InB1Yi0wIiwic3ViIjoibGluay1yZWRpcmVjdCJ9.QMCPf3yczf_Q_SidB-ITuvl_6zO5Bb3qi2WowcCh0Js?
