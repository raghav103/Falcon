"""
Database connection pool and schema initialization.

Usage in FastAPI:
    app.add_event_handler("startup", init_db)

    @app.get("/")
    async def root(conn = Depends(get_conn)):
        ...
"""

import logging
import asyncpg

from backend.config import DATABASE_URL, DB_MIN_CONNECTIONS, DB_MAX_CONNECTIONS

logger = logging.getLogger("falcon.db")
pool: asyncpg.Pool | None = None


async def init_db():
    """
    Create the connection pool and initialize the schema.
    Call once at app startup.
    """
    global pool
    logger.info(
        f"Creating database connection pool (min={DB_MIN_CONNECTIONS}, max={DB_MAX_CONNECTIONS})"
    )

    try:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=DB_MIN_CONNECTIONS,
            max_size=DB_MAX_CONNECTIONS,
        )
        logger.info("Database connection pool created successfully")
    except Exception as e:
        logger.error(f"Failed to create database connection pool: {e}")
        raise RuntimeError(
            f"Database connection failed: {e}. Please check DATABASE_URL and ensure PostgreSQL is running."
        )

    try:
        async with pool.acquire() as conn:
            await _create_schema(conn)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        await pool.close()
        pool = None
        raise RuntimeError(f"Database schema initialization failed: {e}")


async def close_db():
    """Close the pool. Call at app shutdown."""
    global pool
    if pool:
        logger.info("Closing database connection pool")
        await pool.close()
        pool = None
        logger.info("Database connection pool closed")


async def get_conn():
    """
    FastAPI dependency that yields a connection from the pool.

    Usage:
        @app.get("/repos")
        async def list_repos(conn = Depends(get_conn)):
            ...
    """
    async with pool.acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Schema — idempotent (IF NOT EXISTS everywhere)
# ---------------------------------------------------------------------------
async def _create_schema(conn: asyncpg.Connection):
    logger.debug("Creating database schema (idempotent)")

    await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    logger.debug("pg_trgm extension verified")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            url TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            ingested_at TIMESTAMP DEFAULT now(),
            status TEXT DEFAULT 'pending'
        );
    """)
    logger.debug("repos table verified")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id BIGSERIAL PRIMARY KEY,
            repo_id UUID NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
            path TEXT NOT NULL,
            name TEXT NOT NULL,
            extension TEXT,
            parent_path TEXT NOT NULL,
            depth INTEGER NOT NULL,
            is_directory BOOLEAN DEFAULT FALSE,
            content TEXT,
            UNIQUE(repo_id, path)
        );
    """)
    logger.debug("files table verified")

    # Indexes — each one supports a specific tool query pattern.
    # CREATE INDEX IF NOT EXISTS is safe to run repeatedly.
    #
    # list_files (ls mode):   WHERE repo_id = $1 AND parent_path = $2
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dir_listing
        ON files(repo_id, parent_path);
    """)

    # list_files (find mode): WHERE repo_id = $1 AND name LIKE $2
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_name
        ON files(repo_id, name);
    """)

    # search_code (--glob):   WHERE repo_id = $1 AND extension = $2
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_ext
        ON files(repo_id, extension);
    """)

    # search_code (content):  WHERE content LIKE '%literal%'
    # pg_trgm GIN index — accelerates LIKE, ILIKE, and regex on text columns.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_content_search
        ON files USING gin(content gin_trgm_ops);
    """)

    # list_files (glob on paths): WHERE path LIKE '%pattern%'
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_path_search
        ON files USING gin(path gin_trgm_ops);
    """)
