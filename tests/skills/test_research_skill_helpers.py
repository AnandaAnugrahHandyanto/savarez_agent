from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_INTEL_PATH = REPO_ROOT / "skills" / "domain" / "domain-intel" / "scripts" / "domain_intel.py"
DDG_QUERY_SCRIPT = REPO_ROOT / "skills" / "research" / "duckduckgo-search" / "scripts" / "build_a_share_queries.py"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_domain_intel_whois_unknown_tld_returns_error():
    mod = _load_module(DOMAIN_INTEL_PATH, "domain_intel_skill")
    payload = mod.whois_lookup("example.unknownsuffix")
    assert "error" in payload
    assert "No WHOIS server" in payload["error"]


def test_domain_intel_subdomains_parses_crtsh_payload(monkeypatch):
    mod = _load_module(DOMAIN_INTEL_PATH, "domain_intel_skill_subdomains")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'[{"issuer_name":"Test CA","not_after":"2999-01-01T00:00:00","name_value":"api.example.com\\nwww.example.com"}]'

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: FakeResponse())
    payload = mod.subdomains("example.com")
    assert payload["domain"] == "example.com"
    assert payload["count"] == 2
    assert payload["subdomains"][0]["subdomain"] in {"api.example.com", "www.example.com"}


def test_build_a_share_queries_contains_key_a_share_patterns():
    mod = _load_module(DDG_QUERY_SCRIPT, "ddg_queries")
    payload = mod.build_payload()
    names = {item["name"]: item for item in payload["templates"]}
    assert payload["purpose"].startswith("A股短线 DuckDuckGo")
    assert "盘前公告催化" in names
    assert "cninfo.com.cn" in names["盘前公告催化"]["query"]
    assert "监管与问询" in names
