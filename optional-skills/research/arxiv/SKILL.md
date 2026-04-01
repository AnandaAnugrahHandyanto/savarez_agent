---
name: arxiv
description: Search and retrieve academic papers from arxiv.org — keyword search, author lookup, category browsing, paper details, and citation generation. No API key required. Use the Python `arxiv` library when available; fall back to the direct HTTP API (no package needed) otherwise.
version: 1.0.0
author: sprmn24
license: MIT
metadata:
  hermes:
    tags: [arxiv, research, academic, papers, science, citations]
    related_skills: [duckduckgo-search]
    fallback_for_toolsets: []
---

# arXiv Academic Paper Search

Search and retrieve academic papers from [arxiv.org](https://arxiv.org). **No API key required.**

Use this skill when you need to find peer-reviewed preprints, retrieve paper metadata and abstracts, browse recent submissions by subject category, or generate citations for academic work.

## Detection Flow

Check what is available before choosing an approach:

```bash
# Check Python arxiv package availability
python -c "import arxiv; print('arxiv=installed')" 2>/dev/null || echo "arxiv=missing"

# Check curl for direct HTTP API access
command -v curl >/dev/null && echo "curl=installed" || echo "curl=missing"
```

Decision tree:
1. If the `arxiv` Python package is installed in the active runtime, use Method 1 (Python library)
2. If `arxiv` is not installed but `curl` is available, use Method 2 (direct HTTP API — no package needed)
3. To install the `arxiv` package, run `pip install arxiv` first and verify the same runtime can import it

Important runtime note:
- Terminal and `execute_code` are separate runtimes
- Installing `arxiv` in the shell does not guarantee `execute_code` can import it
- The HTTP API approach works anywhere `curl` or `requests` is available without extra packages

## Installation

Install only when the Python library approach is specifically needed and the runtime does not already provide it.

```bash
# Install the arxiv Python package
pip install arxiv

# Verify
python -c "import arxiv; print(arxiv.__version__)"
```

## Method 1: Python Library

Use the `arxiv` package when it is confirmed available in the active runtime.

### Search by Keyword

```python
import arxiv

client = arxiv.Client()
search = arxiv.Search(
    query="transformer attention mechanism",
    max_results=5,
    sort_by=arxiv.SortCriterion.Relevance,
)

for paper in client.results(search):
    print(paper.entry_id)
    print(paper.title)
    print(paper.authors)
    print(paper.published.date())
    print(paper.summary[:300])
    print(paper.pdf_url)
    print()
```

### Search by Author

```python
import arxiv

client = arxiv.Client()
search = arxiv.Search(
    query='au:"Yoshua Bengio"',
    max_results=5,
    sort_by=arxiv.SortCriterion.SubmittedDate,
)

for paper in client.results(search):
    print(paper.title)
    print(paper.published.date())
    print(paper.entry_id)
    print()
```

### Search by Category

```python
import arxiv

client = arxiv.Client()
search = arxiv.Search(
    query="cat:cs.LG",          # machine learning category
    max_results=10,
    sort_by=arxiv.SortCriterion.SubmittedDate,
)

for paper in client.results(search):
    print(paper.title)
    print(paper.categories)
    print(paper.published.date())
    print()
```

### Fetch a Specific Paper by ID

```python
import arxiv

client = arxiv.Client()
# Use the arxiv ID (with or without version suffix)
paper = next(client.results(arxiv.Search(id_list=["2301.07041"])))

print(paper.title)
print([str(a) for a in paper.authors])
print(paper.published.date())
print(paper.summary)
print(paper.pdf_url)
print(paper.categories)
```

### Browse Recent Papers by Category

```python
import arxiv
from datetime import datetime, timedelta, timezone

client = arxiv.Client()
search = arxiv.Search(
    query="cat:cs.AI",
    max_results=20,
    sort_by=arxiv.SortCriterion.SubmittedDate,
    sort_order=arxiv.SortOrder.Descending,
)

cutoff = datetime.now(timezone.utc) - timedelta(days=7)
for paper in client.results(search):
    if paper.published < cutoff:
        break
    print(paper.published.date(), "|", paper.title)
    print(paper.entry_id)
    print()
```

### Generate Citations

```python
import arxiv

client = arxiv.Client()
paper = next(client.results(arxiv.Search(id_list=["2301.07041"])))

# APA citation
authors = [str(a) for a in paper.authors]
if len(authors) == 1:
    author_str = authors[0]
elif len(authors) == 2:
    author_str = " & ".join(authors)
else:
    author_str = authors[0] + " et al."

apa = (
    f"{author_str} ({paper.published.year}). "
    f"{paper.title}. "
    f"arXiv preprint arXiv:{paper.entry_id.split('/')[-1]}."
)
print("APA:")
print(apa)

# BibTeX citation
arxiv_id = paper.entry_id.split("/")[-1].replace(".", "_")
first_author_last = str(paper.authors[0]).split()[-1].lower()
bibtex = f"""@misc{{{first_author_last}{paper.published.year}_{arxiv_id},
  title   = {{{{{paper.title}}}}},
  author  = {{{" and ".join(str(a) for a in paper.authors)}}},
  year    = {{{paper.published.year}}},
  eprint  = {{{paper.entry_id.split('/')[-1]}}},
  archivePrefix = {{arXiv}},
  primaryClass  = {{{paper.primary_category}}}
}}"""
print("\nBibTeX:")
print(bibtex)
```

### Sort and Filter Options

```python
import arxiv

# Sort options
arxiv.SortCriterion.Relevance        # default — best match
arxiv.SortCriterion.SubmittedDate    # most recently submitted
arxiv.SortCriterion.LastUpdatedDate  # most recently updated

# Sort order
arxiv.SortOrder.Descending           # newest first (default)
arxiv.SortOrder.Ascending            # oldest first
```

### Query Syntax Reference

| Prefix | Matches | Example |
|--------|---------|---------|
| `au:` | Author name | `au:"Yann LeCun"` |
| `ti:` | Title words | `ti:diffusion` |
| `abs:` | Abstract words | `abs:contrastive learning` |
| `cat:` | Category | `cat:cs.CV` |
| `id:` | arXiv ID | `id:2301.07041` |
| *(none)* | All fields | `neural network` |

Combine with `AND`, `OR`, `ANDNOT`:

```
ti:diffusion AND cat:cs.CV
au:"Hinton" AND ti:capsule
abs:"large language model" ANDNOT ti:survey
```

## Method 2: Direct HTTP API (No Package Required)

The arXiv API is a plain HTTP endpoint that returns Atom XML. Use this approach when no Python package is available.

### Search with curl

```bash
# Keyword search — returns Atom XML
curl -sG "https://export.arxiv.org/api/query" \
  --data-urlencode "search_query=all:attention mechanism transformer" \
  --data-urlencode "start=0" \
  --data-urlencode "max_results=5" \
  --data-urlencode "sortBy=relevance" \
  --data-urlencode "sortOrder=descending"
```

```bash
# Author search
curl -sG "https://export.arxiv.org/api/query" \
  --data-urlencode 'search_query=au:"Geoffrey Hinton"' \
  --data-urlencode "max_results=5" \
  --data-urlencode "sortBy=submittedDate"
```

```bash
# Category + recent papers
curl -sG "https://export.arxiv.org/api/query" \
  --data-urlencode "search_query=cat:cs.AI" \
  --data-urlencode "max_results=10" \
  --data-urlencode "sortBy=submittedDate" \
  --data-urlencode "sortOrder=descending"
```

```bash
# Fetch by specific arXiv ID
curl -sG "https://export.arxiv.org/api/query" \
  --data-urlencode "id_list=2301.07041"
```

### Parse the XML Response with Python

```python
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

NS = {
    "atom":  "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

def arxiv_search(query, max_results=5, sort_by="relevance"):
    params = urllib.parse.urlencode({
        "search_query": query,
        "max_results":  max_results,
        "sortBy":       sort_by,
        "sortOrder":    "descending",
    })
    url = f"https://export.arxiv.org/api/query?{params}"
    with urllib.request.urlopen(url) as resp:
        root = ET.fromstring(resp.read())

    papers = []
    for entry in root.findall("atom:entry", NS):
        arxiv_id = entry.find("atom:id", NS).text.split("/abs/")[-1]
        papers.append({
            "id":        arxiv_id,
            "title":     entry.find("atom:title", NS).text.strip(),
            "authors":   [a.find("atom:name", NS).text
                          for a in entry.findall("atom:author", NS)],
            "published": entry.find("atom:published", NS).text[:10],
            "abstract":  entry.find("atom:summary", NS).text.strip(),
            "pdf_url":   f"https://arxiv.org/pdf/{arxiv_id}",
            "abs_url":   f"https://arxiv.org/abs/{arxiv_id}",
        })
    return papers

# Example usage
for p in arxiv_search("cat:cs.LG AND ti:diffusion", max_results=3):
    print(p["id"], "|", p["title"])
    print("Authors:", ", ".join(p["authors"][:3]))
    print("Published:", p["published"])
    print("PDF:", p["pdf_url"])
    print()
```

### API Parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `search_query` | query string | Keywords, fields, categories |
| `id_list` | comma-separated IDs | Fetch specific papers |
| `start` | integer (default 0) | Pagination offset |
| `max_results` | integer (max 2000) | Results to return |
| `sortBy` | `relevance`, `submittedDate`, `lastUpdatedDate` | Sort criterion |
| `sortOrder` | `ascending`, `descending` | Sort direction |

## Common arXiv Categories

| Category | Subject |
|----------|---------|
| `cs.AI` | Artificial Intelligence |
| `cs.LG` | Machine Learning |
| `cs.CV` | Computer Vision |
| `cs.CL` | Computation and Language (NLP) |
| `cs.RO` | Robotics |
| `cs.CR` | Cryptography and Security |
| `cs.DS` | Data Structures and Algorithms |
| `cs.NE` | Neural and Evolutionary Computing |
| `stat.ML` | Statistics — Machine Learning |
| `math.ST` | Statistics Theory |
| `math.OC` | Optimization and Control |
| `physics.data-an` | Data Analysis, Statistics and Probability |
| `q-bio.NC` | Neurons and Cognition |
| `econ.EM` | Econometrics |

Full category taxonomy: https://arxiv.org/category_taxonomy

## Workflow: Search then Retrieve Full Text

arXiv metadata includes the abstract but not the full paper text. To read the full paper:

1. Search and find the arXiv ID
2. Use the PDF URL (`https://arxiv.org/pdf/<id>`) with a PDF-reading tool, or
3. Use the HTML version (`https://arxiv.org/html/<id>`) which is available for many recent papers

```bash
# Download PDF to a local file
curl -sL "https://arxiv.org/pdf/2301.07041" -o paper.pdf

# Fetch HTML version (when available)
curl -sL "https://arxiv.org/html/2301.07041"
```

## Limitations

- **Rate limiting**: The arXiv API asks for no more than 3 requests per second. Add a short delay (`time.sleep(1)`) between requests in loops.
- **Max results per request**: The API returns at most 2000 results per query. Use pagination (`start` offset) for larger result sets.
- **Abstract only**: The API returns metadata and abstracts. Full text requires fetching the PDF or HTML page separately.
- **PDF availability**: Some very old papers may not have PDFs; check the `pdf_url` field before fetching.
- **HTML availability**: HTML versions (`/html/`) are only available for papers that were submitted in a compatible LaTeX format — not all papers have this.
- **Search ranking**: arXiv relevance ranking is simpler than commercial search engines; broad queries may return loosely related papers.
- **No authentication**: The public API has no per-user quotas, but abusive usage may result in IP-level throttling.

## Troubleshooting

| Problem | Likely Cause | What To Do |
|---------|--------------|------------|
| `ModuleNotFoundError: No module named 'arxiv'` | Package not installed in this runtime | Install `arxiv` via pip, or switch to the HTTP API method |
| Empty results from Python library | Query syntax error or no matches | Test the same query with curl; check field prefixes (`au:`, `ti:`, etc.) |
| HTTP 503 from API | Temporary overload or rate limit hit | Wait a few seconds and retry; reduce request frequency |
| XML parse error from HTTP API | Unexpected response (e.g., error page) | Print raw response first; verify URL and parameters |
| PDF download returns HTML | Paper has no PDF, or ID is wrong | Confirm the ID at `https://arxiv.org/abs/<id>` first |
| `StopIteration` from `next(client.results(...))` | No results for the given ID or query | Check the ID is correct; use `list()` and test for empty |

## Pitfalls

- **`id_list` vs `search_query`**: Use `id_list` for known IDs; `search_query` for keyword lookups. Mixing them in one call can cause unexpected results.
- **Versioned IDs**: arXiv IDs can include a version suffix (e.g., `2301.07041v2`). Omitting the version returns the latest; include it to pin a specific version.
- **Author name formatting**: Author search (`au:`) is fuzzy. For exact matches wrap in quotes: `au:"Bengio, Yoshua"` or `au:"Y. Bengio"`.
- **Package vs HTTP API field names differ**: The Python library uses `.summary` for abstract; the raw XML uses `<summary>`. Keep the approach consistent within one workflow.
- **`max_results` in Python library**: Pass as a keyword argument to `arxiv.Search(max_results=N)`, not positionally.
- **Rate limit in loops**: When iterating over many results, `client.results()` fetches pages automatically — do not set an excessively large `max_results` if you only need a few papers.

## Validated With

Validated examples against `arxiv==2.x` semantics. Confirmed that `categories` is `List[str]` and `primary_category` is `str` — neither uses a `.term` attribute. Timezone handling uses `datetime.now(timezone.utc)` to match the UTC-aware `paper.published` field.
