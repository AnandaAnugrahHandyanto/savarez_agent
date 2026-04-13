#!/usr/bin/env python3
"""
Playwright Fetcher Skeleton for Autonomous LLM Backup
Provides the architectural base for scraping Perplexity or ChatGPT using a headed browser to save the session state, then running headlessly via cron to fetch conversations.json or API responses.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
import logging

try:
    from playwright.async_api import async_playwright
except ImportError:
    pass # Managed by the script runner

logger = logging.getLogger(__name__)

class LLMFetcher:
    def __init__(self, export_dir: Path):
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.auth_state_path = Path(os.path.expanduser("~/.hermes/cron/playwright_auth.json"))

    async def authenticate_headed(self, target_url: str):
        """
        Pop opens a browser for the user to log in manually. 
        Once login is complete and the context is closed, the cookie session state is saved to disk for headless execution.
        """
        print(f"Opening browser for {target_url} authentication...")
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("Please perform: pip install playwright && playwright install")
            return
            
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(target_url)
            print("Please log in. Press enter in this terminal when authenticated.")
            input()
            await context.storage_state(path=str(self.auth_state_path))
            print(f"Auth state saved to {self.auth_state_path}")
            await browser.close()

    async def fetch_conversations_headless(self, provider: str):
        """
        Loads the saved session state and headlessly hits internal APIs (e.g. Perplexity _next/data) or triggers a UI export to get the raw JSON history.
        """
        if not self.auth_state_path.exists():
            print("No auth state found. Please run authenticate_headed() first.")
            return

        print(f"Headlessly fetching {provider} data...")
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("Please perform: pip install playwright && playwright install")
            return
            
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=str(self.auth_state_path))
            page = await context.new_page()
            
            try:
                if provider.lower() == "perplexity":
                    # Perplexity's internal Next.js/API history route
                    await page.goto("https://www.perplexity.ai/api/history?limit=100")
                    # Wait for network idle or JSON to load
                    await page.wait_for_timeout(3000)
                    content = await page.evaluate("document.body.innerText")
                    json_data = json.loads(content)
                    
                    out_path = self.export_dir / "perplexity_history_export.json"
                    out_path.write_text(json.dumps(json_data, indent=2))
                    print(f"✅ Perplexity history dumped to {out_path}")

                elif provider.lower() == "chatgpt":
                    # ChatGPT provides an internal endpoint for session history metadata
                    await page.goto("https://chat.openai.com/backend-api/conversations?offset=0&limit=30")
                    await page.wait_for_timeout(3000)
                    content = await page.evaluate("document.body.innerText")
                    try:
                        base_data = json.loads(content)
                    except json.JSONDecodeError:
                        print("Failed to parse base conversation JSON.")
                        base_data = {"items": []}

                    items = base_data.get("items", [])
                    print(f"Discovered {len(items)} recent ChatGPT conversations. Fetching deeply...")
                    
                    deep_payloads = []
                    for idx, item in enumerate(items):
                        c_id = item.get("id")
                        if not c_id: continue
                        
                        await page.goto(f"https://chat.openai.com/backend-api/conversation/{c_id}")
                        # Randomish delay to avoid rapid HTTP 429
                        await page.wait_for_timeout(3500)
                        
                        raw_conv = await page.evaluate("document.body.innerText")
                        try:
                            conv_json = json.loads(raw_conv)
                            conv_json["id"] = c_id # Plumb for deduplicator
                            deep_payloads.append(conv_json)
                            print(f" [{idx+1}/{len(items)}] Fetched deep payload for {c_id}")
                        except json.JSONDecodeError:
                            print(f" [{idx+1}/{len(items)}] Failed to decode payload for {c_id}")
                    
                    out_path = self.export_dir / "chatgpt_history_export.json"
                    out_path.write_text(json.dumps({"items": deep_payloads}, indent=2))
                    print(f"✅ ChatGPT history deep-dumped to {out_path}")
                else:
                    print(f"Unknown provider: {provider}")
                    
            except Exception as e:
                print(f"Failed to extract JSON for {provider}: {e}")
                
            finally:
                await browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auth":
        url = sys.argv[2] if len(sys.argv) > 2 else "https://www.perplexity.ai"
        asyncio.run(LLMFetcher(Path(os.path.expanduser("~/.hermes/knowledge/Hermes/LLM_Exports"))).authenticate_headed(url))
    elif len(sys.argv) > 1 and sys.argv[1] == "--fetch":
        provider = sys.argv[2] if len(sys.argv) > 2 else "perplexity"
        asyncio.run(LLMFetcher(Path(os.path.expanduser("~/.hermes/knowledge/Hermes/LLM_Exports"))).fetch_conversations_headless(provider))
    else:
        print("Usage:")
        print("  python llm_fetcher_playwright.py --auth <url>")
        print("  python llm_fetcher_playwright.py --fetch <provider>")
