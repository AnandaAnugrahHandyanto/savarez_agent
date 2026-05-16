import re

with open("tests/gateway/test_feishu_bot_admission.py", "r") as f:
    content = f.read()

# Replace the fake request setup with one that works for the to_thread offload
patch = """    def _fake_request(request):
        captured["uri"] = getattr(request, "uri", None)
        captured["http_method"] = getattr(request, "http_method", None)
        return SimpleNamespace(raw=SimpleNamespace(
            content=b'{"code":0,"bot":{"app_name":"Hermes","open_id":"ou_hydrated"}}'
        ))"""
replacement = """    def _fake_request(request):
        captured["uri"] = getattr(request, "uri", None)
        captured["http_method"] = getattr(request, "http_method", None)
        return SimpleNamespace(raw=SimpleNamespace(
            content=b'{"code":0,"bot":{"app_name":"Hermes","open_id":"ou_hydrated"}}'
        ))

    async def _fake_request_async(request):
        return _fake_request(request)"""
content = content.replace(patch, replacement)

# Actually we shouldn't make the fake request async, it is used with asyncio.to_thread which expects a sync function.
