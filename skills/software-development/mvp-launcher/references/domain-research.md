# Domain Research Patterns

Strategies for finding good, available domain names for MVP projects.

## Name Generation Strategies

### 1. Direct Match
Try the project name directly with different TLDs:
- `{project}.com` - Ideal but usually taken
- `{project}.io` - Tech favorite
- `{project}.app` - Google registry, good for apps
- `{project}.dev` - Developer focused

### 2. Action Prefixes
Add action verbs to the project name:
- `get{project}.com`
- `use{project}.com`
- `try{project}.com`
- `my{project}.com`
- `go{project}.com`

### 3. Function Suffixes
Add descriptive suffixes:
- `{project}app.com`
- `{project}hq.com`
- `{project}lab.com`
- `{project}kit.com`
- `{project}hub.com`

### 4. Creative Variations
- Remove vowels: `flickr` style
- Add suffix: `{project}ly.com`
- Double letters: `{project}r.com`
- Abbreviate: `{proj}.com`

### 5. Combine Words
If project is two words, try variations:
- `word1word2.com`
- `word1-word2.com`
- `word1andword2.com`

## TLD Priority Ranking

For tech MVPs (in order of preference):
1. **.com** - Always try first, most trusted
2. **.io** - Tech/startup standard
3. **.app** - Modern, requires HTTPS
4. **.dev** - Developer focused
5. **.co** - Startup alternative to .com
6. **.ai** - AI/ML projects (expensive)

For specific regions:
- **.ge** - Georgia
- **.de** - Germany
- **.uk** - United Kingdom

## Evaluation Criteria

Score each candidate:
- **Availability** (must be available)
- **Length** (shorter is better, <15 chars ideal)
- **Memorability** (easy to say and spell)
- **Brandability** (can build a brand around it)
- **Price** (within budget)
- **SEO** (keywords in domain help slightly)

## Tools for Research

```bash
# Check single domain
porkbun.py check example.com

# Batch check
cat domains.txt | xargs -I {} porkbun.py check {}

# Get pricing
porkbun.py pricing --tld io
```

## Red Flags

Avoid domains that:
- Are trademarked (check USPTO)
- Contain hyphens (hard to say)
- Have ambiguous spelling
- Are too similar to competitors
- Have negative connotations in other languages

## Decision Framework

Present top 3-5 options with:
1. Domain name
2. Price
3. Why it fits the project
4. Potential issues

Let user choose - don't auto-register without confirmation unless explicitly told to.
