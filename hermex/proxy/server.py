from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from hermex.config import Config, build_core_store
from hermex.proxy.pipeline import ProxyPipeline


def create_proxy_app(config: Config) -> FastAPI:
    app = FastAPI(title="Hermex Proxy")
    store = build_core_store(config)
    app.state.pipeline = ProxyPipeline(
        store=store,
        upstream_base=config.upstream_base,
        api_key=config.api_key,
    )

    @app.post("/v1/messages")
    async def messages(request: Request) -> StreamingResponse:
        body = await request.json()
        pipeline: ProxyPipeline = app.state.pipeline
        return StreamingResponse(
            pipeline.handle(body),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache"},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
