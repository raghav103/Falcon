"""
Database adapter - switches between PostgreSQL and SQLite for testing.
"""

from backend.config import USE_SQLITE_FOR_TESTING

if USE_SQLITE_FOR_TESTING:
    from backend.db_sqlite import init_db, close_db, get_conn
    print("INFO: Using SQLite for testing", file=__import__('sys').stderr)
else:
    from backend.db import init_db, close_db, get_conn

__all__ = ['init_db', 'close_db', 'get_conn']