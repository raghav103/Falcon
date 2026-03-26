"""
Routes for repo management and chat.

POST   /repos                → Ingest a new repo
GET    /repos                → List all repos
GET    /repos/{repo_id}      → Get repo details
DELETE /repos/{repo_id}      → Delete repo + all its files
POST   /repos/{repo_id}/chat → Chat with repo (SSE stream)
"""

import json
import logging
import re
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.auth import verify_api_key
from backend.db import get_conn
from backend.exceptions import DatabaseError, Ingestion Error, ValidationError
from backend.services.ingestion import ingest_repo
from backend.services.agent import run_agent

logger = logging.getLogger("falcon.api")
router = APIRouter(prefix="/repos", tags=["repos"])


# ---------------------------------------------------------------------------
# Request / Response models with validation
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    """Request to ingest a new repository."""

    url: str = Field(..., min_length=10, max_length=500, description="Git repository URL")

    @field_validator("url")
    def validate_git_url(cls, v: str) -> str:
        """
        Validate git URL format and prevent command injection.

        Accepts:
        - HTTPS: https://github.com/owner/repo.git
        - SSH: git@github.com:owner/repo.git

        Blocks:
        - Local file paths
        - Localhost/private IPs
        - Suspicious characters (command injection attempts)
        """
        # Allow only HTTPS and SSH git URLs
        https_pattern = r"^https://[a-zA-Z0-9\-\.]+/[a-zA-Z0-9\-_\.]+/[a-zA-Z0-9\-_\.]+(?:\.git)?$"
        ssh_pattern = r"^git@[a-zA-Z0-9\-\.]+:[a-zA-Z0-9\-_\.]+/[a-zA-Z0-9\-_\.]+(?:\.git)?$"

        if not (re.match(https_pattern, v) or re.match(ssh_pattern, v)):
            raise ValueError(
                "Invalid git URL. Must be HTTPS (https://host/owner/repo.git) "
                "or SSH (git@host:owner/repo.git)"
            )

        # Block suspicious characters that could be command injection
        dangerous_chars = [";", "|", "&", "$", "`", "\n", "\r", "\\"]
        if any(char in v for char in dangerous_chars):
            raise ValueError("Invalid characters in URL")

        # Block local file paths
        if v.startswith("file://") or v.startswith("/"):
            raise ValueError("Local file paths not allowed")

        # Block localhost and private IP ranges
        blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "192.168.", "10.", "172.16."]
        v_lower = v.lower()
        for blocked in blocked_hosts:
            if blocked in v_lower:
                raise ValueError("Cannot clone from local/private networks")

        return v


class ChatRequest(BaseModel):
    """Request to start a chat session with a repository."""

    question: str = Field(
        ..., min_length=1, max_length=5000, description="Question to ask about the repository"
    )
    history: list[dict] | None = Field(
        None, max_length=50, description="Chat history (max 50 messages)"
    )

    @field_validator("question")
    def validate_question(cls, v: str) -> str:
        """Strip whitespace and ensure question is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty or whitespace only")
        return v

    @field_validator("history")
    def validate_history(cls, v: list[dict] | None) -> list[dict] | None:
        """
        Validate chat history structure and content.

        Each message must have:
        - role: 'user' or 'assistant'
        - content: non-empty string (max 10,000 chars)
        """
        if v is None:
            return v

        if not isinstance(v, list):
            raise ValueError("History must be a list")

        if len(v) > 50:
            raise ValueError("Chat history too long (max 50 messages)")

        for i, msg in enumerate(v):
            if not isinstance(msg, dict):
                raise ValueError(f"History message {i} must be a dict")

            if "role" not in msg or "content" not in msg:
                raise ValueError(f"History message {i} must have 'role' and 'content'")

            if msg["role"] not in ["user", "assistant"]:
                raise ValueError(f"History message {i}: role must be 'user' or 'assistant'")

            if not isinstance(msg["content"], str):
                raise ValueError(f"History message {i}: content must be string")

            if not msg["content"].strip():
                raise ValueError(f"History message {i}: content cannot be empty")

            if len(msg["content"]) > 10000:
                raise ValueError(f"History message {i}: content too long (max 10,000 chars)")

        return v


class RepoResponse(BaseModel):
    """Response for repository metadata."""

    repo_id: str
    name: str
    url: str
    status: str
    ingested_at: datetime


# ---------------------------------------------------------------------------
# POST /repos — Ingest a new repo
# ---------------------------------------------------------------------------
@router.post("/", status_code=201)
async def create_repo(
    body: IngestRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    _: str = Depends(verify_api_key),
):
    """
    Clone a git repo, index all files into the database, delete the clone.

    Returns immediately with repo_id and status.
    For large repos, the clone + index might take a few seconds.

    **Authentication**: Requires X-API-Key header.
    """
    logger.info(f"POST /repos - ingesting URL: {body.url}")

    try:
        result = await ingest_repo(conn, body.url)
        logger.info(f"POST /repos - ingestion result: {result}")
        return result
    except IngestionError as e:
        logger.error(f"POST /repos - ingestion error: {e.message}")
        raise HTTPException(status_code=400, detail=e.user_message)
    except DatabaseError as e:
        logger.error(f"POST /repos - database error: {e.message}")
        raise HTTPException(status_code=500, detail=e.user_message)
    except Exception as e:
        logger.error(f"POST /repos - unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to ingest repository. Please try again."
        )


# ---------------------------------------------------------------------------
# GET /repos — List all repos
# ---------------------------------------------------------------------------
@router.get("/")
async def list_repos(
    conn: asyncpg.Connection = Depends(get_conn),
    _: str = Depends(verify_api_key),
):
    """
    List all ingested repositories, ordered by most recent first.

    **Authentication**: Requires X-API-Key header.
    """
    logger.info("GET /repos - listing all repositories")

    try:
        rows = await conn.fetch(
            "SELECT id, name, url, status, ingested_at FROM repos ORDER BY ingested_at DESC"
        )
        logger.info(f"GET /repos - found {len(rows)} repositories")
        return [
            RepoResponse(
                repo_id=str(row["id"]),
                name=row["name"],
                url=row["url"],
                status=row["status"],
                ingested_at=row["ingested_at"],
            )
            for row in rows
        ]
    except asyncpg.PostgresError as e:
        logger.error(f"GET /repos - database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve repositories")
    except Exception as e:
        logger.error(f"GET /repos - unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ---------------------------------------------------------------------------
# GET /repos/{repo_id} — Get repo details
# ---------------------------------------------------------------------------
@router.get("/{repo_id}")
async def get_repo(
    repo_id: UUID,
    conn: asyncpg.Connection = Depends(get_conn),
    _: str = Depends(verify_api_key),
):
    """
    Get details for a specific repository, including file count.

    **Authentication**: Requires X-API-Key header.
    """
    logger.info(f"GET /repos/{repo_id} - fetching repository details")

    try:
        row = await conn.fetchrow(
            "SELECT id, name, url, status, ingested_at FROM repos WHERE id = $1",
            repo_id,
        )
        if not row:
            logger.warning(f"GET /repos/{repo_id} - repository not found")
            raise HTTPException(status_code=404, detail="Repository not found")

        # Also get file count for context
        file_count = await conn.fetchval(
            "SELECT count(*) FROM files WHERE repo_id = $1 AND is_directory = false",
            repo_id,
        )

        logger.info(f"GET /repos/{repo_id} - found repository with {file_count} files")
        return {
            "repo_id": str(row["id"]),
            "name": row["name"],
            "url": row["url"],
            "status": row["status"],
            "ingested_at": row["ingested_at"],
            "file_count": file_count,
        }
    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"GET /repos/{repo_id} - database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve repository details")
    except Exception as e:
        logger.error(f"GET /repos/{repo_id} - unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ---------------------------------------------------------------------------
# DELETE /repos/{repo_id} — Delete repo and all its files
# ---------------------------------------------------------------------------
@router.delete("/{repo_id}", status_code=204)
async def delete_repo(
    repo_id: UUID,
    conn: asyncpg.Connection = Depends(get_conn),
    _: str = Depends(verify_api_key),
):
    """
    Deletes a repository and all its indexed files.

    The CASCADE on the foreign key automatically deletes all file rows.

    **Authentication**: Requires X-API-Key header.
    """
    logger.info(f"DELETE /repos/{repo_id} - deleting repository")

    try:
        result = await conn.execute("DELETE FROM repos WHERE id = $1", repo_id)

        # result is "DELETE 1" or "DELETE 0"
        if result == "DELETE 0":
            logger.warning(f"DELETE /repos/{repo_id} - repository not found")
            raise HTTPException(status_code=404, detail="Repository not found")

        logger.info(f"DELETE /repos/{repo_id} - repository deleted successfully")
    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"DELETE /repos/{repo_id} - database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete repository")
    except Exception as e:
        logger.error(f"DELETE /repos/{repo_id} - unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ---------------------------------------------------------------------------
# POST /repos/{repo_id}/chat — Chat with repo (SSE stream)
# ---------------------------------------------------------------------------
@router.post("/{repo_id}/chat")
async def chat(
    repo_id: UUID,
    body: ChatRequest,
    conn: asyncpg.Connection = Depends(get_conn),
    _: str = Depends(verify_api_key),
):
    """
    Agentic chat — the LLM explores the repo using tools and streams its answer.

    Returns a Server-Sent Events stream. Each event is a JSON object:
      {"type": "tool_start", "name": "search_code", "arguments": {...}}
      {"type": "tool_end",   "name": "search_code"}
      {"type": "text_delta", "content": "The auth module..."}
      {"type": "done"}
      {"type": "error",      "content": "..."}

    **Authentication**: Requires X-API-Key header.
    """
    logger.info(f"POST /repos/{repo_id}/chat - starting chat session")

    # Verify repo exists and is ready
    try:
        row = await conn.fetchrow("SELECT status FROM repos WHERE id = $1", repo_id)
        if not row:
            logger.warning(f"POST /repos/{repo_id}/chat - repository not found")
            raise HTTPException(status_code=404, detail="Repository not found")
        if row["status"] != "ready":
            logger.warning(
                f"POST /repos/{repo_id}/chat - repository not ready (status: {row['status']})"
            )
            raise HTTPException(
                status_code=409,
                detail=f"Repository is not ready (status: {row['status']}). Wait for ingestion to complete.",
            )
    except HTTPException:
        raise
    except asyncpg.PostgresError as e:
        logger.error(f"POST /repos/{repo_id}/chat - database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify repository status")
    except Exception as e:
        logger.error(f"POST /repos/{repo_id}/chat - unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")

    async def event_stream():
        """Stream agent responses as server-sent events."""
        try:
            async for event in run_agent(
                conn=conn,
                repo_id=str(repo_id),
                question=body.question,
                history=body.history,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"POST /repos/{repo_id}/chat - agent error: {e}", exc_info=True)
            # Send safe error message to client
            yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred while processing your question. Please try again.'})}\n\n"

    logger.info(f"POST /repos/{repo_id}/chat - streaming response")
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering if behind a proxy
        },
    )
