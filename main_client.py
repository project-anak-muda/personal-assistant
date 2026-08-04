import gc
import uvicorn
import traceback

from typing import Dict
from fastapi import FastAPI, status
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse

from routers.all import all_router
from constants.log import LOGGER
from services.agent_manager import make_graph_single
from services.checkpointer import checkpointer_scope


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    app.context = {}

    # Hold the checkpointer pool open for the app's whole lifetime — the agent
    # reads and writes checkpoints on every request, not just at startup.
    async with checkpointer_scope() as checkpointer:
        app.context["single_agent"] = await make_graph_single(checkpointer)

        # Startup
        LOGGER.info("Starting FastAPI application")

        yield

        # Shutdown - Clean up resources
        LOGGER.info("Shutting down FastAPI application")

        app.context.clear()

    # Force garbage collection
    gc.collect()

app = FastAPI(
    title="Milvus Vector DB API",
    description="API for searching documents into Milvus vector database",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(all_router)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled exceptions
    """
    LOGGER.error(f"Unhandled exception: {str(exc)}")
    LOGGER.error(f"Request: {request.method} {request.url}")
    LOGGER.error(f"Traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "detail": str(exc) if app.debug else "Internal server error"
        }
    )

@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main_client:app", port=2707, reload=True, log_config="log.ini")