---
name: rss-reader
description: Read any RSS or Atom feed URL using curl and python3. List latest N items with title, link, date, and summary. Filter by keyword. Read multiple feeds at once. No API key required.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [RSS, Atom, Feeds, News, Content, Aggregation]
    related_skills: []
---

# RSS / Atom Feed Reader

Fetch and parse any RSS 2.0 or Atom 1.0 feed with nothing but `curl` and `python3`. No API key, no third-party libraries.

## Quick Reference

| Action | Command |
|--------|---------|
| Fetch latest 10 items | `curl -s URL \| python3 -c "..."` (see below) |
| Limit to N items | add `MAX = N` in the script |
| Filter by keyword | add `KEYWORD = "word"` in the script |
| Multiple feeds | loop over a list of URLs |

---

## Fetch and Display a Feed

```bash
curl -sL "https://feeds.arstechnica.com/arstechnica/index" | python3 -c "
import sys, xml.etree.ElementTree as ET

MAX = 10
KEYWORD = ''   # set to filter, e.g. 'AI' — leave empty for no filter

raw = sys.stdin.read()
root = ET.fromstring(raw)

# Detect Atom vs RSS
ns_atom = {'a': 'http://www.w3.org/2005/Atom'}
is_atom = root.tag == '{http://www.w3.org/2005/Atom}feed' or root.tag == 'feed'

items = []
if is_atom:
    entries = root.findall('{http://www.w3.org/2005/Atom}entry')
    for e in entries:
        title   = (e.findtext('{http://www.w3.org/2005/Atom}title') or '').strip()
        link_el = e.find('{http://www.w3.org/2005/Atom}link')
        link    = (link_el.get('href') if link_el is not None else '') or ''
        date    = (e.findtext('{http://www.w3.org/2005/Atom}updated') or
                   e.findtext('{http://www.w3.org/2005/Atom}published') or '')[:10]
        summary = (e.findtext('{http://www.w3.org/2005/Atom}summary') or
                   e.findtext('{http://www.w3.org/2005/Atom}content') or '').strip()
        items.append((title, link, date, summary))
else:
    channel = root.find('channel') or root
    for item in channel.findall('item'):
        title   = (item.findtext('title') or '').strip()
        link    = (item.findtext('link') or '').strip()
        date    = (item.findtext('pubDate') or item.findtext('dc:date') or '')[:16]
        summary = (item.findtext('description') or item.findtext('content:encoded') or '').strip()
        # strip HTML tags from summary
        import re
        summary = re.sub(r'<[^>]+>', '', summary).strip()
        items.append((title, link, date, summary))

shown = 0
for i, (title, link, date, summary) in enumerate(items):
    if KEYWORD and KEYWORD.lower() not in title.lower() and KEYWORD.lower() not in summary.lower():
        continue
    shown += 1
    if shown > MAX:
        break
    print(f'{shown}. {title}')
    print(f'   Date: {date}')
    print(f'   Link: {link}')
    if summary:
        print(f'   Summary: {summary[:200]}...' if len(summary) > 200 else f'   Summary: {summary}')
    print()

if shown == 0:
    print('No items matched.')
"
```

---

## Parameters at a Glance

| Variable | Default | Effect |
|----------|---------|--------|
| `MAX` | `10` | Maximum items to display |
| `KEYWORD` | `''` | Case-insensitive filter on title + summary; empty = show all |

---

## Multiple Feeds at Once

```bash
python3 - <<'EOF'
import subprocess, xml.etree.ElementTree as ET, re

FEEDS = [
    ("Ars Technica",  "https://feeds.arstechnica.com/arstechnica/index"),
    ("Hacker News",   "https://hnrss.org/frontpage"),
    ("The Verge",     "https://www.theverge.com/rss/index.xml"),
]
MAX_PER_FEED = 5
KEYWORD = ""  # optional filter

def fetch(url):
    r = subprocess.run(["curl", "-sL", url], capture_output=True, text=True, timeout=15)
    return r.stdout

def parse(xml_text):
    root = ET.fromstring(xml_text)
    is_atom = 'Atom' in root.tag or root.tag == 'feed'
    items = []
    if is_atom:
        for e in root.findall('{http://www.w3.org/2005/Atom}entry'):
            title   = (e.findtext('{http://www.w3.org/2005/Atom}title') or '').strip()
            link_el = e.find('{http://www.w3.org/2005/Atom}link')
            link    = link_el.get('href') if link_el is not None else ''
            date    = (e.findtext('{http://www.w3.org/2005/Atom}updated') or
                       e.findtext('{http://www.w3.org/2005/Atom}published') or '')[:10]
            summary = re.sub(r'<[^>]+>', '',
                       e.findtext('{http://www.w3.org/2005/Atom}summary') or
                       e.findtext('{http://www.w3.org/2005/Atom}content') or '').strip()
            items.append((title, link, date, summary))
    else:
        channel = root.find('channel') or root
        for item in channel.findall('item'):
            title   = (item.findtext('title') or '').strip()
            link    = (item.findtext('link') or '').strip()
            date    = (item.findtext('pubDate') or '')[:16]
            summary = re.sub(r'<[^>]+>', '',
                       item.findtext('description') or '').strip()
            items.append((title, link, date, summary))
    return items

for name, url in FEEDS:
    print(f"=== {name} ===")
    try:
        raw = fetch(url)
        items = parse(raw)
    except Exception as ex:
        print(f"  ERROR: {ex}\n")
        continue
    shown = 0
    for title, link, date, summary in items:
        if KEYWORD and KEYWORD.lower() not in title.lower() and KEYWORD.lower() not in summary.lower():
            continue
        shown += 1
        if shown > MAX_PER_FEED:
            break
        print(f"  {shown}. [{date}] {title}")
        print(f"     {link}")
    print()
EOF
```

---

## Keyword Filtering

Set `KEYWORD` to any string. Matching is case-insensitive and checks both title and summary.

```bash
# Show only items mentioning "Python"
KEYWORD = "Python"

# Show only items mentioning "security"
KEYWORD = "security"

# No filter (show all)
KEYWORD = ""
```

---

## One-liner: Titles Only

```bash
# Quick scan — titles + links, no summaries
curl -sL "https://hnrss.org/frontpage" | python3 -c "
import sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.read())
ch = root.find('channel') or root
for i, item in enumerate(ch.findall('item')[:10], 1):
    print(f'{i}. {item.findtext(\"title\", \"\").strip()}')
    print(f'   {item.findtext(\"link\", \"\").strip()}')
"
```

---

## Common Feed URLs

| Source | Feed URL |
|--------|----------|
| Hacker News (front page) | `https://hnrss.org/frontpage` |
| Hacker News (newest) | `https://hnrss.org/newest` |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` |
| The Verge | `https://www.theverge.com/rss/index.xml` |
| TechCrunch | `https://techcrunch.com/feed/` |
| BBC News | `https://feeds.bbci.co.uk/news/rss.xml` |
| Reuters Top News | `https://feeds.reuters.com/reuters/topNews` |
| NASA News | `https://www.nasa.gov/rss/dyn/breaking_news.rss` |
| GitHub Blog | `https://github.blog/feed/` |
| Python News | `https://www.python.org/dev/peps/peps.rss/` |

---

## Notes

- Both **RSS 2.0** and **Atom 1.0** are supported automatically — the script detects format from the root element.
- HTML tags are stripped from summaries via a simple regex; install `html.parser` via stdlib `html` module if you need entity decoding.
- Some feeds require a `User-Agent` header. Add `-H "User-Agent: Mozilla/5.0"` to the `curl` call if you get a 403.
- For feeds behind authentication or paywalls, `curl` supports `-u user:pass` and `-H "Authorization: Bearer TOKEN"`.
- Encoding: `curl -sL` follows redirects and `python3` defaults to UTF-8; add `--compressed` to curl for gzip feeds if needed.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `curl` returns empty / 403 | Add `-H "User-Agent: Mozilla/5.0"` |
| `xml.etree.ElementTree.ParseError` | Feed may be HTML or redirecting — check with `curl -v` |
| Summaries contain HTML entities (`&amp;`) | Pipe summary through `html.unescape()` from `html` stdlib |
| Date field empty | Feed uses non-standard tag; inspect raw XML with `curl -sL URL \| head -60` |
