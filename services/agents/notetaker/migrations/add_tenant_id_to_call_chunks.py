"""
Migration script to add tenant_id to notetaker_call_chunks and backfill from notetaker_calls.
Designed to be safe to run multiple times.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv


load_dotenv()


async def migrate():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return

    # Convert SQLAlchemy async URL to plain Postgres URL for asyncpg
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to database...")
    conn = await asyncpg.connect(conn_url)

    try:
        print("\nChecking notetaker_call_chunks columns...")
        result = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'notetaker_call_chunks'
            """
        )
        existing_columns = {row["column_name"] for row in result}
        print(f"Existing columns: {sorted(existing_columns)}")

        # 1) Add tenant_id column if missing
        if "tenant_id" not in existing_columns:
            print("Adding tenant_id column to notetaker_call_chunks...")
            await conn.execute(
                """
                ALTER TABLE notetaker_call_chunks
                ADD COLUMN tenant_id varchar
                """
            )
            print("✅ Added tenant_id column")
        else:
            print("✓ tenant_id column already exists on notetaker_call_chunks")

        # 2) Backfill tenant_id from parent notetaker_calls table
        print("Backfilling tenant_id from notetaker_calls...")
        updated = await conn.execute(
            """
            UPDATE notetaker_call_chunks c
            SET tenant_id = calls.tenant_id
            FROM notetaker_calls calls
            WHERE c.call_id = calls.id
              AND (c.tenant_id IS NULL OR c.tenant_id = '')
            """
        )
        print(f"✅ Backfill result: {updated}")

        # 3) Set NOT NULL constraint if there are no remaining NULLs
        remaining_nulls = await conn.fetchval(
            """
            SELECT COUNT(*) FROM notetaker_call_chunks
            WHERE tenant_id IS NULL
            """
        )
        if remaining_nulls == 0:
            print("Setting tenant_id to NOT NULL...")
            await conn.execute(
                """
                ALTER TABLE notetaker_call_chunks
                ALTER COLUMN tenant_id SET NOT NULL
                """
            )
            print("✅ tenant_id is now NOT NULL")
        else:
            print(
                f"⚠️ {remaining_nulls} rows still have NULL tenant_id; "
                "NOT NULL constraint not applied"
            )

        # 4) Create composite index on (tenant_id, call_id) if it doesn't exist
        print("Ensuring composite index on (tenant_id, call_id)...")
        index_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM pg_indexes
                WHERE tablename = 'notetaker_call_chunks'
                  AND indexname = 'idx_notetaker_call_chunks_tenant_call'
            )
            """
        )
        if not index_exists:
            await conn.execute(
                """
                CREATE INDEX idx_notetaker_call_chunks_tenant_call
                ON notetaker_call_chunks (tenant_id, call_id)
                """
            )
            print("✅ Created index idx_notetaker_call_chunks_tenant_call")
        else:
            print("✓ Index idx_notetaker_call_chunks_tenant_call already exists")

        print("\n✅ Migration completed successfully for notetaker_call_chunks")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())

