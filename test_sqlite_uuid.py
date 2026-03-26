#!/usr/bin/env python3
"""Test SQLite UUID handling."""
import asyncio
import uuid
from backend.db_sqlite import init_db, get_connection

async def test_uuid_operations():
    """Test UUID operations in SQLite."""
    print("Testing SQLite UUID operations...")

    # Initialize database
    await init_db()

    # Get connection
    async with get_connection() as conn:
        # Test 1: Simple UUID insert
        print("\n1. Testing simple UUID insert...")
        repo_id = uuid.uuid4()
        print(f"   Generated UUID: {repo_id} (type: {type(repo_id)})")

        try:
            await conn.execute(
                "INSERT INTO repos (id, url, name, status) VALUES ($1, $2, $3, $4)",
                repo_id, "https://test.com", "test-repo", "ready"
            )
            print("   ✅ Simple UUID insert succeeded")
        except Exception as e:
            print(f"   ❌ Simple UUID insert failed: {e}")
            return

        # Test 2: Batch file insert (exactly like ingestion.py)
        print("\n2. Testing batch file insert (mimic ingestion)...")

        # This mimics what _collect_file_records returns:
        records = [
            (
                repo_id,           # repo_id: uuid.UUID (converted to str)
                "/test.py",        # path: str
                "test.py",         # name: str
                ".py",             # extension: str (might be None)
                "/",               # parent_path: str
                1,                 # depth: int
                False,             # is_directory: bool (gets converted to 0/1)
                "print('hello')"   # content: str (might be None)
            )
        ]

        columns = [
            "repo_id", "path", "name", "extension",
            "parent_path", "depth", "is_directory", "content"
        ]

        print(f"   Sample record: {records[0]}")
        print(f"   Record types: {[type(x) for x in records[0]]}")

        try:
            await conn.copy_records_to_table("files", records, columns)
            print("   ✅ Batch file insert succeeded")
        except Exception as e:
            print(f"   ❌ Batch file insert failed: {e}")
            return

        # Test 3: Query back
        print("\n3. Testing file query...")
        try:
            result = await conn.fetchrow("SELECT * FROM files WHERE repo_id = $1", repo_id)
            if result:
                print(f"   ✅ File query succeeded: {result}")
            else:
                print("   ❌ File query returned no results")
        except Exception as e:
            print(f"   ❌ File query failed: {e}")
            return

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_uuid_operations())