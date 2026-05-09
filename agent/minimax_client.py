import httpx
import logging
from typing import Any, Dict, List, Optional
from openai import OpenAI, AsyncOpenAI

logger = logging.getLogger(__name__)

class MiniMaxClientBase:
    """Shared base logic for MiniMax clients to reduce duplication."""
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.root_url = base_url.split("/anthropic")[0].rstrip("/") if "/anthropic" in base_url else base_url.rstrip("/")
        self.anthropic_url = f"{self.root_url}/anthropic"
        # Dynamic shims: allows client.chat.completions.create(...)
        self.chat = self
        self.completions = self

    def _get_vision_payload(self, messages: List[Dict[str, Any]]) -> tuple:
        """Extract prompt and image data by searching in reverse (supports OpenAI and Anthropic formats)."""
        p, img = "", ""
        for m in reversed(messages):
            if m.get("role") != "user":
                continue
            content = m.get("content")
            if isinstance(content, str) and not p:
                p = content
            elif isinstance(content, list):
                for part in content:
                    t = part.get("type")
                    if t == "text" and not p:
                        p = part.get("text", "")
                    elif t == "image_url":
                        img = part["image_url"]["url"]
                    elif t == "image": # Anthropic format (after auxiliary_client conversion)
                        src = part.get("source", {})
                        if src.get("type") == "base64":
                            img = f"data:{src.get('media_type')};base64,{src.get('data')}"
                        else:
                            img = src.get("url", "")
            if img:
                break
        return p or "Describe this image", img.strip().replace("\n", "").replace("\r", "") if img else ""

    def _resp(self, text: str):
        """Generate a mock OpenAI-style response object."""
        class Mock: pass
        m, c, r = Mock(), Mock(), Mock()
        m.content, m.role = text, "assistant"
        c.message, c.finish_reason = m, "stop"
        r.choices = [c]
        return r

    def close(self):
        """Stub for compatibility."""
        pass

class MiniMaxOAuthClient(MiniMaxClientBase):
    """Synchronous MiniMax client."""
    def create(self, model: str, messages: List[Dict[str, Any]], **kwargs):
        if model == "MiniMax-VL-01":
            prompt, img = self._get_vision_payload(messages)
            if not img:
                raise ValueError("MiniMax-VL-01 requires an image")
            with httpx.Client(timeout=180) as h:
                resp = h.post(f"{self.root_url}/v1/coding_plan/vlm", 
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             json={"prompt": prompt, "image_url": img})
                resp.raise_for_status()
                r = resp.json()
                if r.get("base_resp", {}).get("status_code") != 0:
                    raise Exception(f"MiniMax VLM Error: {r.get('base_resp', {}).get('status_msg')}")
                return self._resp(r.get("content", ""))
        
        from agent.auxiliary_client import _to_openai_base_url
        with OpenAI(api_key=self.api_key, base_url=_to_openai_base_url(self.anthropic_url)) as c:
            return c.chat.completions.create(model=model, messages=messages, **kwargs)

class AsyncMiniMaxOAuthClient(MiniMaxClientBase):
    """Asynchronous MiniMax client."""
    def __init__(self, sync_client):
        super().__init__(sync_client.api_key, sync_client.root_url)

    async def create(self, model: str, messages: List[Dict[str, Any]], **kwargs):
        if model == "MiniMax-VL-01":
            prompt, img = self._get_vision_payload(messages)
            if not img:
                raise ValueError("MiniMax-VL-01 requires an image")
            async with httpx.AsyncClient(timeout=180) as h:
                resp = await h.post(f"{self.root_url}/v1/coding_plan/vlm", 
                                    headers={"Authorization": f"Bearer {self.api_key}"},
                                    json={"prompt": prompt, "image_url": img})
                resp.raise_for_status()
                r = resp.json()
                if r.get("base_resp", {}).get("status_code") != 0:
                    raise Exception(f"MiniMax VLM Error: {r.get('base_resp', {}).get('status_msg')}")
                return self._resp(r.get("content", ""))
        
        from agent.auxiliary_client import _to_openai_base_url
        async with AsyncOpenAI(api_key=self.api_key, base_url=_to_openai_base_url(self.anthropic_url)) as c:
            return await c.chat.completions.create(model=model, messages=messages, **kwargs)

def get_minimax_oauth_client() -> Optional[MiniMaxOAuthClient]:
    """Helper to resolve and instantiate the client."""
    try:
        from hermes_cli.auth import resolve_minimax_oauth_runtime_credentials
        creds = resolve_minimax_oauth_runtime_credentials()
        if creds and creds.get("api_key"):
            return MiniMaxOAuthClient(creds["api_key"], creds["base_url"])
    except Exception:
        pass
    return None
