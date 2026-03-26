"""
Repo ingestion pipeline.

Clone a git repo, walk its files, insert them into PostgreSQL, delete the clone.

    URL → git clone --depth 1 → walk → filter → batch INSERT → cleanup

The entire clone lives in a tempdir that auto-deletes when we're done.
After ingestion, only the database has the repo's data — no files on disk.
"""

import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path

import asyncpg

from backend.config import MAX_FILE_SIZE

logger = logging.getLogger("falcon.ingestion")


# ---------------------------------------------------------------------------
# Skip lists — directories, extensions, and filenames to ignore
# ---------------------------------------------------------------------------
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".env",
    "vendor", "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    ".idea", ".vscode", ".DS_Store", ".svn", ".hg",
    "coverage", ".cache", ".parcel-cache", ".turbo",
}

SKIP_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Media
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    # Archives
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    # Binaries
    ".exe", ".dll", ".so", ".dylib", ".bin",
    # Compiled
    ".pyc", ".pyo", ".class", ".o", ".a", ".obj", ".wasm",
    # Data (large)
    ".sqlite", ".db", ".pickle", ".pkl",
    # Maps
    ".map",
}

SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "composer.lock",
    "Gemfile.lock", "go.sum",
    ".DS_Store", "Thumbs.db",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def ingest_repo(conn: asyncpg.Connection, url: str) -> dict:
    """
    Ingest a git repo into the database.

    Returns:
        {"repo_id": "uuid", "status": "ready", "file_count": 1234}
        or
        {"repo_id": "uuid", "status": "already_exists"} if URL was already ingested.

    Raises:
        Exception on clone failure or DB errors (caller should handle).
    """
    logger.info(f"Starting ingestion for URL: {url}")

    # --- 1. Dedup check ---
    existing = await conn.fetchrow(
        "SELECT id, status FROM repos WHERE url = $1", url
    )
    if existing:
        logger.info(f"Repository already exists: {existing['id']} (status: {existing['status']})")
        return {
            "repo_id": str(existing["id"]),
            "status": "already_exists",
        }

    # --- 2. Insert repo row ---
    repo_name = _extract_repo_name(url)
    repo_id = uuid.uuid4()
    logger.info(f"Creating repo record: {repo_id} - {repo_name}")

    await conn.execute(
        """
        INSERT INTO repos (id, url, name, status)
        VALUES ($1, $2, $3, 'ingesting')
        """,
        repo_id, url, repo_name,
    )

    try:
        # --- 3. Clone into tempdir ---
        with tempfile.TemporaryDirectory() as tmpdir:
            clone_path = os.path.join(tmpdir, "repo")
            logger.info(f"Cloning repository to temporary directory: {clone_path}")
            await _git_clone(url, clone_path)
            logger.info("Repository cloned successfully")

            # --- 4–7. Walk, filter, compute fields, read content ---
            logger.info("Collecting file records")
            records = _collect_file_records(clone_path, repo_id)
            logger.info(f"Collected {len(records)} file records")

            # --- 8. Batch insert ---
            if records:
                logger.info("Batch inserting file records into database")
                await conn.copy_records_to_table(
                    "files",
                    records=records,
                    columns=[
                        "repo_id", "path", "name", "extension",
                        "parent_path", "depth", "is_directory", "content",
                    ],
                )
                logger.info("File records inserted successfully")

        # --- 9. Update status ---
        await conn.execute(
            "UPDATE repos SET status = 'ready' WHERE id = $1", repo_id
        )
        logger.info(f"Ingestion complete for repo {repo_id}: {len(records)} files")

        return {
            "repo_id": str(repo_id),
            "status": "ready",
            "file_count": len(records),
        }

    except Exception as e:
        # Mark as failed so it can be retried
        logger.error(f"Ingestion failed for repo {repo_id}: {e}", exc_info=True)
        await conn.execute(
            "UPDATE repos SET status = 'error' WHERE id = $1", repo_id
        )
        raise


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _extract_repo_name(url: str) -> str:
    """
    "https://github.com/expressjs/express.git" → "expressjs/express"
    "git@github.com:owner/repo.git"            → "owner/repo"
    """
    # Strip trailing .git and slashes
    clean = url.rstrip("/").removesuffix(".git")

    # Handle HTTPS URLs
    if "://" in clean:
        parts = clean.split("/")
        if len(parts) >= 2:
            return "/".join(parts[-2:])
        return parts[-1]

    # Handle SSH URLs (git@host:owner/repo)
    if ":" in clean:
        return clean.split(":")[-1]

    return clean


async def _git_clone(url: str, dest: str):
    """
    Shallow clone a repo. Raises on failure.
    """
    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", "--single-branch", url, dest,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"git clone failed (exit {proc.returncode}): {stderr.decode().strip()}"
        )


def _collect_file_records(
    clone_path: str,
    repo_id: uuid.UUID,
) -> list[tuple]:
    """
    Walk the cloned repo, filter junk, compute fields, read content.

    Returns a list of tuples ready for asyncpg.copy_records_to_table():
        (repo_id, path, name, extension, parent_path, depth, is_directory, content)
    """
    records = []
    root = Path(clone_path)

    for dirpath, dirnames, filenames in os.walk(root):
        # --- Filter directories in-place (prevents os.walk from descending) ---
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS
        ]

        rel_dir = Path(dirpath).relative_to(root)
        rel_dir_str = str(rel_dir) if str(rel_dir) != "." else ""

        # --- Insert directory entries (except root) ---
        if rel_dir_str:
            dir_name = rel_dir.name
            dir_parent = str(rel_dir.parent) if str(rel_dir.parent) != "." else ""
            dir_depth = len(rel_dir.parts)

            records.append((
                repo_id,
                rel_dir_str,        # path
                dir_name,           # name
                None,               # extension
                dir_parent,         # parent_path
                dir_depth,          # depth
                True,               # is_directory
                None,               # content
            ))

        # --- Insert file entries ---
        for filename in filenames:
            # Skip by filename
            if filename in SKIP_FILENAMES:
                continue

            # Skip by extension
            ext = _get_extension(filename)
            if ext in SKIP_EXTENSIONS:
                continue

            filepath = Path(dirpath) / filename
            rel_path = filepath.relative_to(root)
            rel_path_str = str(rel_path)

            # Skip files that are too large
            try:
                file_size = filepath.stat().st_size
            except OSError:
                continue
            if file_size > MAX_FILE_SIZE:
                continue

            # Skip binary files (can't decode as UTF-8)
            try:
                content = filepath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            file_name = rel_path.name
            file_parent = str(rel_path.parent) if str(rel_path.parent) != "." else ""
            file_depth = len(rel_path.parts)

            records.append((
                repo_id,
                rel_path_str,       # path
                file_name,          # name
                ext or None,        # extension (None if no extension)
                file_parent,        # parent_path
                file_depth,         # depth
                False,              # is_directory
                content,            # content
            ))

    return records


def _get_extension(filename: str) -> str:
    """
    "login.py"       → ".py"
    "Dockerfile"     → ""
    "test.spec.ts"   → ".ts"
    ".gitignore"     → ".gitignore"
    """
    _, ext = os.path.splitext(filename)
    return ext.lower()
