"""
Temporary SQLite database adapter for testing without PostgreSQL.
This allows us to test Falcon functionality without full PostgreSQL setup.
"""

import logging
import sqlite3
import aiosqlite
import uuid
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

logger = logging.getLogger("falcon.db")
db_path = "falcon_test.db"


def _convert_params(args):
    """Convert parameters for SQLite compatibility."""
    converted = []
    for arg in args:
        if isinstance(arg, uuid.UUID):
            converted.append(str(arg))
        else:
            converted.append(arg)
    return converted


class MockConnection:
    """Mock asyncpg.Connection for SQLite testing."""

    def __init__(self, sqlite_conn):
        self.sqlite_conn = sqlite_conn

    async def fetchrow(self, query: str, *args):
        """Fetch single row."""
        try:
            # Convert asyncpg-style query to SQLite
            sqlite_query = query.replace('$1', '?').replace('$2', '?').replace('$3', '?').replace('$4', '?')
            converted_args = _convert_params(args)
            cursor = await self.sqlite_conn.execute(sqlite_query, converted_args)
            row = await cursor.fetchone()
            if row:
                # Convert to dict-like object (asyncpg returns Record)
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.error(f"SQLite fetchrow error: {e}")
            raise

    async def fetch(self, query: str, *args):
        """Fetch multiple rows."""
        try:
            sqlite_query = query.replace('$1', '?').replace('$2', '?').replace('$3', '?')
            converted_args = _convert_params(args)
            cursor = await self.sqlite_conn.execute(sqlite_query, converted_args)
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"SQLite fetch error: {e}")
            raise

    async def fetchval(self, query: str, *args):
        """Fetch single value."""
        try:
            sqlite_query = query.replace('$1', '?').replace('$2', '?')
            converted_args = _convert_params(args)
            cursor = await self.sqlite_conn.execute(sqlite_query, converted_args)
            row = await cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"SQLite fetchval error: {e}")
            raise

    async def execute(self, query: str, *args):
        """Execute query."""
        try:
            # Handle different query patterns
            sqlite_query = query.replace('$1', '?').replace('$2', '?').replace('$3', '?').replace('$4', '?')
            converted_args = _convert_params(args)
            cursor = await self.sqlite_conn.execute(sqlite_query, converted_args)
            await self.sqlite_conn.commit()

            # Return status like asyncpg does
            if query.strip().upper().startswith('DELETE'):
                return f"DELETE {cursor.rowcount}"
            return f"EXECUTE {cursor.rowcount}"
        except Exception as e:
            logger.error(f"SQLite execute error: {e}")
            raise

    async def copy_records_to_table(self, table: str, records: list, columns: list):
        """Batch insert (mock of asyncpg's copy_records_to_table)."""
        if not records:
            return

        placeholders = ','.join(['?' for _ in columns])
        query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

        try:
            # Convert UUID parameters in each record
            converted_records = []
            for record in records:
                converted_record = _convert_params(record)
                converted_records.append(converted_record)

            await self.sqlite_conn.executemany(query, converted_records)
            await self.sqlite_conn.commit()
            logger.info(f"Inserted {len(records)} records into {table}")
        except Exception as e:
            logger.error(f"SQLite copy_records_to_table error: {e}")
            raise


async def init_db():
    """Initialize SQLite database with schema."""
    logger.info("Initializing SQLite database for testing")

    try:
        # Create database and tables
        conn = await aiosqlite.connect(db_path)

        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys = ON")

        # Create extension simulation (SQLite doesn't have pg_trgm, but we can work around it)
        logger.info("Setting up SQLite schema (simulating PostgreSQL)")

        # Create tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS repos (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                url TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                path TEXT NOT NULL,
                name TEXT NOT NULL,
                extension TEXT,
                parent_path TEXT NOT NULL,
                depth INTEGER NOT NULL,
                is_directory INTEGER DEFAULT 0,
                content TEXT,
                UNIQUE(repo_id, path)
            )
        """)

        # Create indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_repo_id ON files(repo_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_path ON files(path)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)")

        await conn.commit()
        await conn.close()

        logger.info("SQLite database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        raise RuntimeError(f"Database initialization failed: {e}")


async def close_db():
    """Close database (no-op for SQLite in this simple setup)."""
    logger.info("Database close requested (SQLite)")


@asynccontextmanager
async def get_connection() -> AsyncGenerator[MockConnection, None]:
    """Get SQLite connection wrapped as asyncpg-compatible mock."""
    conn = await aiosqlite.connect(db_path)
    try:
        yield MockConnection(conn)
    finally:
        await conn.close()


async def get_conn() -> AsyncGenerator[MockConnection, None]:
    """FastAPI dependency - get database connection."""
    async with get_connection() as conn:
        yield conn