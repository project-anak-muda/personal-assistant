"""Webhook transport for the Telegram bot — the entrypoint deployed to Cloud Run.

Deliberately separate from `main_client.py`: that app is an experimentation
surface whose `/single-agent/generate-answer` endpoint is unauthenticated, and
a public Cloud Run URL is the wrong place to expose it. This app serves only
the webhook and a health check.

Local run:
    uv run python webhook_app.py
"""
import os
import gc
import httpx
import uvicorn
import traceback

from typing import Dict
from fastapi import FastAPI, status
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse

from constants.log import LOGGER
from routers.telegram import telegram_router
from services.agent_manager import make_graph_single
from services.checkpointer import pool_scope, build_checkpointer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build everything once per container, not once per request.

    Cloud Run reuses a warm container across requests, so the expensive parts —
    graph construction and the connection pool — are paid on cold start only.
    """
    app.context = {}

    async with pool_scope() as pool:
        app.context["pool"] = pool
        app.context["single_agent"] = await make_graph_single(build_checkpointer(pool))

        # One HTTP client for the container's lifetime: a fresh client per
        # request would redo the TLS handshake to api.telegram.org every time.
        async with httpx.AsyncClient(timeout=60) as client:
            app.context["http"] = client

            LOGGER.info("Webhook app ready")
            yield
            LOGGER.info("Shutting down webhook app")

        app.context.clear()

    gc.collect()

app = FastAPI(
    title="Personal Assistant Telegram Webhook",
    description="Receives Telegram updates and runs them through the agent.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(telegram_router)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    LOGGER.error(f"Unhandled exception: {str(exc)}")
    LOGGER.error(f"Request: {request.method} {request.url}")
    LOGGER.error(f"Traceback: {traceback.format_exc()}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "message": "Internal server error"},
    )

@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}

if __name__ == "__main__":
    # Cloud Run injects PORT and expects the server on 0.0.0.0.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        log_config="log.ini",
    )
