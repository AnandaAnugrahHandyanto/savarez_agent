from __future__ import annotations
import os
import requests
from hermes_cli.config import load_config
from hermes_cli.providers import resolve_provider_full
def run_diagnose(provider_name: str):
    config = load_config()
    pdef = resolve_provider_full(provider_name, config.get("providers"), config.get("custom_providers"))
    
    if not pdef:
        print(f"Error: Provider '{provider_name}' bulunamadı.")
        return

    print(f"═══ Provider: {provider_name} ═══")
    
    # 1. Config Check
    print("✓ Provider definition exists in config.")
    
    # 2. Env Var Check
    env_vars = getattr(pdef, 'api_key_env_vars', [])
    key_val = next((os.environ.get(v) for v in env_vars if os.environ.get(v)), None)
    if key_val:
        print(f"✓ API key env var found (len: {len(key_val)} chars)")
    else:
        print("✗ API key env var not set")

    # 3. Connectivity Test (Ping)
    if getattr(pdef, 'base_url', None):
        try:
            resp = requests.get(pdef.base_url, timeout=5)
            print(f"✓ Base URL reachable: {pdef.base_url} (Status: {resp.status_code})")
        except Exception as e:
            print(f"✗ Base URL unreachable: {e}")
    else:
        print("! Base URL not defined (using SDK default)")

# Summary kısmını bu şekilde değiştirelim
    print("─── Summary ───")
    # Eğer tüm kontroller geçildiyse "READY", geçilemediyse "ACTION REQUIRED" yazsın
    status = "READY" if key_val else "ACTION REQUIRED"
    print(f"Status: {status}")
    if not key_val:
        print("Tip: Lütfen GEMINI_API_KEY ortam değişkenini tanımlayın.")