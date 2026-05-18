"""Ported from clawdbot-main/scripts/tools — run via: py -3 scripts/openclaw_ports/<name>"""

#!/usr/bin/env python3
import json
import re
from pathlib import Path


ENV_REF_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def collect_env_refs(obj, refs):
    if isinstance(obj, dict):
        for v in obj.values():
            collect_env_refs(v, refs)
    elif isinstance(obj, list):
        for v in obj:
            collect_env_refs(v, refs)
    elif isinstance(obj, str):
        m = ENV_REF_PATTERN.match(obj.strip())
        if m:
            refs.add(m.group(1))


def main() -> int:
    root = Path(".")
    openclaw_path = root / ".openclaw-desktop" / "openclaw.json"
    auth_path = root / ".openclaw-desktop" / "agents" / "main" / "agent" / "auth-profiles.json"

    cfg = json.loads(openclaw_path.read_text(encoding="utf-8"))
    auth = json.loads(auth_path.read_text(encoding="utf-8"))

    refs = set()
    collect_env_refs(cfg, refs)

    providers = sorted((cfg.get("models") or {}).get("providers", {}).keys())
    auth_profiles = auth.get("profiles", {})
    anthropic_profile_exists = any(
        isinstance(v, dict) and v.get("provider") == "anthropic" for v in auth_profiles.values()
    )
    ollama_exists = "ollama" in providers
    line_exists = bool((cfg.get("channels") or {}).get("line"))

    report = {
        "providers": providers,
        "lineConfigured": line_exists,
        "ollamaConfigured": ollama_exists,
        "anthropicProfileConfigured": anthropic_profile_exists,
        "envRefsDetected": sorted(refs),
    }

    out_json = root / "_docs" / "runtime-config-audit.json"
    out_md = root / "_docs" / "runtime-config-audit.md"

    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Runtime Config Audit",
        "",
        f"- lineConfigured: `{line_exists}`",
        f"- ollamaConfigured: `{ollama_exists}`",
        f"- anthropicProfileConfigured: `{anthropic_profile_exists}`",
        f"- providers: `{', '.join(providers) if providers else '(none)'}`",
        "",
        "## env refs",
        "",
    ]
    if refs:
        lines.extend([f"- `{x}`" for x in sorted(refs)])
    else:
        lines.append("- none")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
