import json, sys

model = sys.argv[1]
content = sys.stdin.read().strip()
payload = {
    "model": model,
    "messages": [{"role": "user", "content": content}],
    "max_tokens": 4096,
    "temperature": 0.7
}
print(json.dumps(payload))
