"""
Migration script to add missing columns to existing conversations table
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
        # Check if columns exist
        print("\nChecking existing columns...")
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'conversations'
        """)
        
        existing_columns = [row['column_name'] for row in result]
        print(f"Existing columns: {existing_columns}")
        
        # Add missing columns
        columns_to_add = [
            ("brand_industry", "VARCHAR"),
            ("brand_audience", "VARCHAR"),
            ("brand_vibe", "VARCHAR"),
            ("brand_locked", "BOOLEAN DEFAULT FALSE"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                print(f"\nAdding column: {column_name} ({column_type})")
                await conn.execute(f"""
                    ALTER TABLE conversations 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"✅ Added {column_name}")
            else:
                print(f"✓ Column {column_name} already exists")
        
        # Check assets table for metadata column
        print("\nChecking assets table...")
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'assets'
        """)
        
        assets_columns = [row['column_name'] for row in result]
        
        # Rename metadata to asset_metadata if it exists
        if 'metadata' in assets_columns and 'asset_metadata' not in assets_columns:
            print("\nRenaming assets.metadata to assets.asset_metadata...")
            await conn.execute("""
                ALTER TABLE assets 
                RENAME COLUMN metadata TO asset_metadata
            """)
            print("✅ Renamed metadata to asset_metadata")
        elif 'asset_metadata' in assets_columns:
            print("✓ Column asset_metadata already exists")
        elif 'metadata' not in assets_columns and 'asset_metadata' not in assets_columns:
            print("\nAdding asset_metadata column...")
            await conn.execute("""
                ALTER TABLE assets 
                ADD COLUMN asset_metadata JSONB
            """)
            print("✅ Added asset_metadata column")
        
        print("\n" + "="*60)
        print("✅ Migration completed successfully!")
        print("="*60)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
