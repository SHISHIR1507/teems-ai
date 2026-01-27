"""
Migration script to add tenant isolation columns to existing tables
Sets default tenant_id='default-tenant' for existing data
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
        # Check if columns exist in conversations table
        print("\nChecking ugc_conversations table...")
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ugc_conversations'
        """)
        
        existing_columns = [row['column_name'] for row in result]
        print(f"Existing columns: {existing_columns}")
        
        # Add missing columns to conversations table
        columns_to_add = [
            ("tenant_id", "VARCHAR NOT NULL DEFAULT 'default-tenant'"),
            ("user_id", "VARCHAR"),
        ]
        
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                print(f"\nAdding column: {column_name} ({column_type})")
                await conn.execute(f"""
                    ALTER TABLE ugc_conversations 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"✅ Added {column_name}")
            else:
                print(f"✓ Column {column_name} already exists")
        
        # Update existing rows to have default tenant_id if null
        if 'tenant_id' in existing_columns:
            print("\nUpdating existing rows with default tenant_id...")
            updated = await conn.execute("""
                UPDATE ugc_conversations 
                SET tenant_id = 'default-tenant' 
                WHERE tenant_id IS NULL
            """)
            print(f"✅ Updated {updated.split()[-1]} rows")
        
        # Add index on tenant_id if it doesn't exist
        print("\nChecking indexes on ugc_conversations...")
        indexes = await conn.fetch("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'ugc_conversations' AND indexname = 'idx_ugc_conversations_tenant_id'
        """)
        if not indexes:
            print("Adding index on tenant_id...")
            await conn.execute("""
                CREATE INDEX idx_ugc_conversations_tenant_id ON ugc_conversations(tenant_id)
            """)
            print("✅ Added index on tenant_id")
        else:
            print("✓ Index on tenant_id already exists")
        
        # Check if columns exist in assets table
        print("\nChecking ugc_assets table...")
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ugc_assets'
        """)
        
        assets_columns = [row['column_name'] for row in result]
        print(f"Existing columns: {assets_columns}")
        
        # Add missing columns to assets table
        asset_columns_to_add = [
            ("tenant_id", "VARCHAR NOT NULL DEFAULT 'default-tenant'"),
            ("user_id", "VARCHAR"),
        ]
        
        for column_name, column_type in asset_columns_to_add:
            if column_name not in assets_columns:
                print(f"\nAdding column: {column_name} ({column_type})")
                await conn.execute(f"""
                    ALTER TABLE ugc_assets 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"✅ Added {column_name}")
            else:
                print(f"✓ Column {column_name} already exists")
        
        # Update existing assets to have tenant_id from their conversation
        if 'tenant_id' in assets_columns:
            print("\nUpdating existing assets with tenant_id from conversations...")
            updated = await conn.execute("""
                UPDATE ugc_assets 
                SET tenant_id = (
                    SELECT tenant_id 
                    FROM ugc_conversations 
                    WHERE ugc_conversations.id = ugc_assets.conversation_id
                )
                WHERE tenant_id IS NULL
            """)
            print(f"✅ Updated {updated.split()[-1]} asset rows")
            
            # Set default for any remaining nulls
            await conn.execute("""
                UPDATE ugc_assets 
                SET tenant_id = 'default-tenant' 
                WHERE tenant_id IS NULL
            """)
        
        # Add index on tenant_id for assets if it doesn't exist
        print("\nChecking indexes on ugc_assets...")
        indexes = await conn.fetch("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'ugc_assets' AND indexname = 'idx_ugc_assets_tenant_id'
        """)
        if not indexes:
            print("Adding index on tenant_id...")
            await conn.execute("""
                CREATE INDEX idx_ugc_assets_tenant_id ON ugc_assets(tenant_id)
            """)
            print("✅ Added index on tenant_id")
        else:
            print("✓ Index on tenant_id already exists")
        
        print("\n" + "="*60)
        print("✅ Migration completed successfully!")
        print("="*60)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
