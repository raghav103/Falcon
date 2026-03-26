"""
Simple API key authentication for Falcon endpoints.

Uses X-API-Key header for authentication. In development mode without an API_KEY set,
authentication is skipped to allow easier local testing.
"""

import logging
from fastapi import Header, HTTPException

from backend.config import API_KEY, ENVIRONMENT

logger = logging.getLogger("falcon.auth")


async def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")) -> str:
    """
    Verify API key from X-API-Key header.

    Args:
        x_api_key: API key from request header

    Returns:
        API key if valid

    Raises:
        HTTPException: 401 if API key is invalid or missing
        HTTPException: 500 if server is misconfigured
    """
    # Skip auth in development if API_KEY not set (for easier testing)
    if ENVIRONMENT == "development" and not API_KEY:
        logger.debug("Development mode: API key authentication skipped (API_KEY not configured)")
        return "dev-mode"

    # Production or development with API_KEY set: enforce authentication
    if not API_KEY:
        logger.error("Server misconfigured: API_KEY not set but authentication required")
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured. Contact administrator.",
        )

    if x_api_key != API_KEY:
        logger.warning(f"Invalid API key attempt: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. Please provide a valid X-API-Key header.",
        )

    logger.debug("API key validated successfully")
    return x_api_key
