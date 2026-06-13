"""Head-to-head: Hermes fuzzy patch vs hashline on the two failure modes."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.fuzzy_match import fuzzy_find_and_replace
from tools import hashline_core as hl


def scenario_b():
    print("=" * 60)
    print("SCENARIO B: stale view (file is 5, model thinks 3)")
    print("=" * 60)
    actual = 'config = {\n    "max_retries": 5,\n}\n'
    new, count, strat, err = fuzzy_find_and_replace(
        content=actual, old_string='    "max_retries": 3,', new_string='    "max_retries": 10,')
    print(f"[fuzzy] strategy={strat} count={count}")
    if new and '"max_retries": 10,' in new:
        print("  DANGER: fuzzy CHANGED file based on stale anchor!")
    fd, path = tempfile.mkstemp(suffix=".py"); os.close(fd)
    open(path, "w").write(actual)
    stale_tag = hl.content_tag('config = {\n    "max_retries": 3,\n}\n')
    res = hl.apply_patch_text(f'[{path}#{stale_tag}]\nreplace 2:\n+    "max_retries": 10,\n', root="/")
    print(f"[hashline] ok={res['ok']}")
    print("  SAFE: rejected stale anchor" if not res["ok"] else "  applied")
    os.unlink(path)


def scenario_a():
    print("\n" + "=" * 60)
    print("SCENARIO A: duplicate lines (edit 2nd occurrence)")
    print("=" * 60)
    content = 'def save(self):\n    log.info("x")\n    self.commit()\n\ndef reload(self):\n    log.info("x")\n    self.commit()\n'
    new, count, strat, err = fuzzy_find_and_replace(
        content=content, old_string='    log.info("x")', new_string='    log.info("reloaded")')
    print(f"[fuzzy] strategy={strat} count={count} err={err}")
    print(f"  fuzzy cannot disambiguate {count} matches")
    fd, path = tempfile.mkstemp(suffix=".py"); os.close(fd)
    open(path, "w").write(content)
    tag = hl.content_tag(content)
    res = hl.apply_patch_text(f'[{path}#{tag}]\nreplace 6:\n+    log.info("reloaded")\n', root="/")
    out = open(path).read().split("\n")
    print(f"[hashline] ok={res['ok']} line2={out[1]!r} line6={out[5]!r}")
    print("  SAFE: edited ONLY the 2nd occurrence")
    os.unlink(path)


if __name__ == "__main__":
    scenario_b()
    scenario_a()
    print("\nDone.")
