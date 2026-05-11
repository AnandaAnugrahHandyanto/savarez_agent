import json, sys

raw = sys.stdin.read()
# Strip __HTTP__ suffix if present
for sep in ["\n__HTTP__", "__HTTP__"]:
    if sep in raw:
        raw = raw.split(sep)[0]

try:
    d = json.loads(raw)
except:
    print(f"PARSE_ERROR: {raw[:200]}")
    sys.exit(1)

if "error" in d:
    print(f"API_ERROR: {d[error]}")
    sys.exit(1)

c = d.get("choices", [])
if c:
    m = c[0].get("message", {})
    t = m.get("content", "").strip()
    if not t:
        t = m.get("reasoning_content", "(empty - thinking model)")
    print(t[:3000])
else:
    print(f"NO_CHOICES: {json.dumps(d)[:200]}")

u = d.get("usage", {})
pt = u.get("prompt_tokens", 0)
ct = u.get("completion_tokens", 0)
print(f"TOKENS:{pt}in/{ct}out", file=sys.stderr)
