"""
Migration script to add product_name column to ugc_conversations table
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    # Parse DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    # Convert asyncpg URL to regular postgres URL for asyncpg.connect
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to database...")
    conn = await asyncpg.connect(conn_url)

    try:
        # Check if column exists
        print("\nChecking if product_name column exists...")
        result = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ugc_conversations'
            AND column_name = 'product_name'
        """)

        if result:
            print("✅ Column product_name already exists in ugc_conversations table")
        else:
            print("\nAdding product_name column to ugc_conversations table...")
            await conn.execute("""
                ALTER TABLE ugc_conversations
                ADD COLUMN product_name VARCHAR
            """)
            print("✅ Successfully added product_name column")

        print("\n" + "="*60)
        print("✅ Migration completed successfully!")
        print("="*60)

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
