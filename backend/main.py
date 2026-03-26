"""
Falcon — FastAPI application entry point.

Start with:
    uvicorn backend.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import LOG_LEVEL, ENVIRONMENT, CORS_ORIGINS
from backend.exceptions import FalconError
from backend.logging_config import setup_logging
from backend.db_adapter import init_db, close_db
from backend.routers.repos import router as repos_router

# Set up logging before anything else
setup_logging(log_level=LOG_LEVEL, environment=ENVIRONMENT)
logger = logging.getLogger("falcon.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool + schema. Shutdown: close pool."""
    logger.info("Starting Falcon application")
    await init_db()
    logger.info("Application startup complete")
    yield
    logger.info("Shutting down Falcon application")
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Falcon",
    description="Open-source repo documentation and chat",
    lifespan=lifespan,
)

# CORS — configurable origins, explicit methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Configured via environment variable
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # Explicit, not ["*"]
    allow_headers=["Content-Type", "X-API-Key"],  # Explicit, not ["*"]
    max_age=3600,  # Cache preflight for 1 hour
)

logger.info(f"CORS configured with origins: {CORS_ORIGINS}")

# Global exception handlers
@app.exception_handler(FalconError)
async def falcon_error_handler(request: Request, exc: FalconError):
    """
    Handle custom Falcon errors with safe, user-friendly messages.

    Logs the internal error details server-side, returns safe user message to client.
    """
    logger.error(
        f"FalconError: {exc.message} (path={request.url.path}, type={type(exc).__name__})"
    )
    return JSONResponse(
        status_code=500,
        content={"error": exc.user_message},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """
    Catch-all for unexpected errors.

    Logs full traceback server-side, returns generic message to client.
    NEVER leak internal details (stack traces, file paths, DB errors) to clients.
    """
    logger.error(
        f"Unhandled exception: {exc} (path={request.url.path})",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "An unexpected error occurred. Please try again."},
    )


# Routes
app.include_router(repos_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
