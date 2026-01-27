"""
Migration script to add tenant_id to presentation_messages and backfill from presentation_conversations.
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

    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to database...")
    conn = await asyncpg.connect(conn_url)

    try:
        print("\nChecking presentation_messages columns...")
        result = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'presentation_messages'
            """
        )
        existing_columns = {row["column_name"] for row in result}
        print(f"Existing columns: {sorted(existing_columns)}")

        # 1) Add tenant_id column if missing
        if "tenant_id" not in existing_columns:
            print("Adding tenant_id column to presentation_messages...")
            await conn.execute(
                """
                ALTER TABLE presentation_messages
                ADD COLUMN tenant_id varchar
                """
            )
            print("✅ Added tenant_id column")
        else:
            print("✓ tenant_id column already exists on presentation_messages")

        # 2) Backfill tenant_id from presentation_conversations
        print("Backfilling tenant_id from presentation_conversations...")
        updated = await conn.execute(
            """
            UPDATE presentation_messages m
            SET tenant_id = c.tenant_id
            FROM presentation_conversations c
            WHERE m.conversation_id = c.id
              AND (m.tenant_id IS NULL OR m.tenant_id = '')
            """
        )
        print(f"✅ Backfill result: {updated}")

        # 3) Set NOT NULL constraint if there are no remaining NULLs
        remaining_nulls = await conn.fetchval(
            """
            SELECT COUNT(*) FROM presentation_messages
            WHERE tenant_id IS NULL
            """
        )
        if remaining_nulls == 0:
            print("Setting tenant_id to NOT NULL on presentation_messages...")
            await conn.execute(
                """
                ALTER TABLE presentation_messages
                ALTER COLUMN tenant_id SET NOT NULL
                """
            )
            print("✅ tenant_id is now NOT NULL on presentation_messages")
        else:
            print(
                f"⚠️ {remaining_nulls} rows still have NULL tenant_id in presentation_messages; "
                "NOT NULL constraint not applied"
            )

        # 4) Create composite index on (tenant_id, conversation_id) if it doesn't exist
        print("Ensuring composite index on (tenant_id, conversation_id)...")
        index_exists = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM pg_indexes
                WHERE tablename = 'presentation_messages'
                  AND indexname = 'idx_presentation_messages_tenant_conv'
            )
            """
        )
        if not index_exists:
            await conn.execute(
                """
                CREATE INDEX idx_presentation_messages_tenant_conv
                ON presentation_messages (tenant_id, conversation_id)
                """
            )
            print("✅ Created index idx_presentation_messages_tenant_conv")
        else:
            print("✓ Index idx_presentation_messages_tenant_conv already exists")

        print("\n✅ Migration completed successfully for presentation_messages")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())

