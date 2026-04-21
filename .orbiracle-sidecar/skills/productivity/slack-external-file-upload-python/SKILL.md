---
name: slack-external-file-upload-python
description: Upload a local file into a Slack channel/thread using Slack's external upload flow when the local Swift helper cannot run (for example because swift/swiftc is missing).
version: 1.0.0
author: Orbiracle
license: MIT
metadata:
  hermes:
    tags: [slack, upload, files, python, fallback]
    category: productivity
---

# Slack external file upload via Python fallback

Use this when a file must be posted into Slack and the local helper script fails because the runtime cannot compile or execute Swift.

## Trigger

Typical failure:
- `./scripts/slack_file_upload.swift:9: command not found: swiftc`
- `which swift` / `which swiftc` returns nothing

## What this does

Implements Slack's required external upload flow directly in Python:
1. Read Slack bot token from `~/.zeroclaw/config.toml`
2. Decrypt `enc2:` token using `~/.zeroclaw/.secret_key`
3. Call `files.getUploadURLExternal`
4. POST raw file bytes to the returned `upload_url`
5. Call `files.completeUploadExternal` with `channel_id`, optional `thread_ts`, and optional comment

## Preconditions

- `python3` exists
- `cryptography` package is installed
- Slack config lives in `~/.zeroclaw/config.toml`
- Secret key lives in `~/.zeroclaw/.secret_key`

## Minimal verification

Before running the fallback:

```bash
which swift || true; which swiftc || true
python3 - <<'PY'
import importlib.util
print(bool(importlib.util.find_spec('cryptography')))
PY
```

## Python fallback template

Run from repo root or anywhere after adjusting paths:

```bash
python3 - <<'PY'
import json, re, urllib.parse, urllib.request
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

CONFIG_DIR = Path('/home/orbibot/.zeroclaw')
CONFIG_PATH = CONFIG_DIR / 'config.toml'
FILE_PATH = Path('/home/orbibot/.zeroclaw/workspace/FILE_TO_UPLOAD.html')
CHANNEL = 'CXXXXXXXX'
THREAD_TS = '1234567890.123456'  # or None
COMMENT = '업로드 코멘트'
TITLE = FILE_PATH.name

text = CONFIG_PATH.read_text()
section = re.search(r'\[channels_config\.slack\](.*?)(?:\n\[|\Z)', text, re.S)
if not section:
    raise SystemExit('slack section not found')
body = section.group(1)

def get_value(key):
    m = re.search(rf'^\s*{re.escape(key)}\s*=\s*(.+)$', body, re.M)
    return m.group(1).strip() if m else None

def parse_quoted(raw):
    if not raw:
        return None
    raw = raw.split('#',1)[0].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return bytes(raw[1:-1], 'utf-8').decode('unicode_escape')
    return raw

encrypted_token = parse_quoted(get_value('bot_token'))
if encrypted_token is None:
    raise SystemExit('bot_token not found')

if encrypted_token.startswith('enc2:'):
    blob = bytes.fromhex(encrypted_token.split(':', 1)[1])
    key = bytes.fromhex((CONFIG_DIR / '.secret_key').read_text().strip())
    nonce, ct = blob[:12], blob[12:]
    token = ChaCha20Poly1305(key).decrypt(nonce, ct, None).decode()
else:
    token = encrypted_token

file_bytes = FILE_PATH.read_bytes()

def slack_api(url, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=utf-8')
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get('ok', False):
        raise RuntimeError(payload)
    return payload

slot = slack_api('https://slack.com/api/files.getUploadURLExternal', {
    'filename': FILE_PATH.name,
    'length': str(len(file_bytes)),
})

upload_req = urllib.request.Request(slot['upload_url'], data=file_bytes, method='POST')
upload_req.add_header('Content-Type', 'application/octet-stream')
upload_req.add_header('Content-Length', str(len(file_bytes)))
with urllib.request.urlopen(upload_req) as resp:
    print(resp.read().decode(errors='replace'))

params = {
    'files': json.dumps([{'id': slot['file_id'], 'title': TITLE}], separators=(',', ':')),
    'channel_id': CHANNEL,
}
if THREAD_TS:
    params['thread_ts'] = THREAD_TS
if COMMENT:
    params['initial_comment'] = COMMENT

print(json.dumps(slack_api('https://slack.com/api/files.completeUploadExternal', params), ensure_ascii=False))
PY
```

## Notes

- Raw `application/octet-stream` upload worked in practice; multipart fallback was unnecessary here.
- `files.completeUploadExternal` accepts `thread_ts`, so you can post directly into the target thread.
- Return and log the `file_id` for verification.

## Recommended workflow

1. Try the repo helper first.
2. If it fails due to missing Swift toolchain, do not stall.
3. Verify `cryptography` is available.
4. Run the Python fallback.
5. Confirm success by checking returned `file_id` and Slack API `ok: true`.
