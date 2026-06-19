"""End-to-end: DeepSeek generates hashline patches applied via patch_hashline."""
import os, subprocess, sys, tempfile
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.file_operations import ShellFileOperations
from tools import hashline_core as hl

KEY = open("/Users/lyx/.hermes/secrets/deepseek_api_key.txt").read().strip()
SYSTEM = ("You are a code-editing assistant. Respond with ONLY a hashline patch "
          "(no prose). Format: [path#TAG] then line-addressed ops. Ops: "
          "'replace A:' then body lines prefixed with '+'. Copy the TAG verbatim.")


class LocalEnv:
    def __init__(self, cwd): self.cwd = cwd
    def execute(self, command, cwd=None, timeout=None, stdin_data=None, **kw):
        p = subprocess.run(command, shell=True, cwd=cwd or self.cwd,
                           capture_output=True, text=True, input=stdin_data, timeout=timeout)
        return {"output": p.stdout + p.stderr, "returncode": p.returncode}


def ask(user):
    hdr = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
    r = requests.post("https://api.deepseek.com/chat/completions", headers=hdr,
        json={"model": "deepseek-v4-flash", "temperature": 0, "max_tokens": 300,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": user}]}, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def extract(text):
    out, started = [], False
    for ln in text.splitlines():
        if ln.strip().startswith("```"): continue
        if "#" in ln and (ln.strip().startswith("[") or ln.strip()[0:1].isalnum()):
            started = True
        if started: out.append(ln)
    return "\n".join(out).strip()


def test_valid():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "m.py")
        open(path, "w").write("def add(a, b):\n    return a - b\n")
        tag = hl.content_tag(open(path).read())
        view = f"[{path}#{tag}]\n   1 def add(a, b):\n   2     return a - b"
        patch = extract(ask(f"File:\n{view}\n\nFix add() to return a+b. Path: {path}"))
        print("patch:", repr(patch))
        ops = ShellFileOperations(LocalEnv(d), cwd=d)
        res = ops.patch_hashline(patch)
        print("result:", res.success, res.error)
        assert res.success, res.error
        assert "a + b" in open(path).read() or "a+b" in open(path).read()
        print("PASS valid")


def test_stale():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "m.py")
        open(path, "w").write("LIMIT = 100\n")
        stale_tag = hl.content_tag("LIMIT = 10\n")
        view = f"[{path}#{stale_tag}]\n   1 LIMIT = 10"
        patch = extract(ask(f"File:\n{view}\n\nChange LIMIT to 50. Path: {path}"))
        print("patch:", repr(patch))
        ops = ShellFileOperations(LocalEnv(d), cwd=d)
        res = ops.patch_hashline(patch)
        print("result:", res.success, res.error)
        assert not res.success
        assert open(path).read() == "LIMIT = 100\n"
        print("PASS stale-rejected")


if __name__ == "__main__":
    test_valid()
    print()
    test_stale()
    print("\nALL LLM E2E PASSED")
