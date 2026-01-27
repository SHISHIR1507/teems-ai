"""
Migration script to add tenant isolation columns to existing tables
Sets default tenant_id='default-tenant' for existing data
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()
# Also try loading from agent/.env
agent_env = Path(__file__).parent.parent / "agent" / ".env"
if agent_env.exists():
    load_dotenv(agent_env)

async def migrate():
    # Parse DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Convert asyncpg URL to regular postgres URL for asyncpg.connect
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgresql://")
    
    print("Connecting to database...")
    conn = await asyncpg.connect(conn_url)
    
    try:
        # Check if columns exist in documents table
        print("\nChecking documents table...")
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'documents'
        """)
        
        existing_columns = [row['column_name'] for row in result]
        print(f"Existing columns: {existing_columns}")
        
        # Add missing columns to documents table (tenant_id should already exist, but verify)
        if 'tenant_id' not in existing_columns:
            print("\nAdding column: tenant_id")
            await conn.execute("""
                ALTER TABLE documents 
                ADD COLUMN tenant_id VARCHAR(128) NOT NULL DEFAULT 'default-tenant'
            """)
            print("✅ Added tenant_id")
        else:
            print("✓ Column tenant_id already exists")
        
        # Update existing rows to have default tenant_id if null
        print("\nUpdating existing rows with default tenant_id...")
        updated = await conn.execute("""
            UPDATE documents 
            SET tenant_id = 'default-tenant' 
            WHERE tenant_id IS NULL
        """)
        print(f"✅ Updated rows")
        
        # Add index on tenant_id if it doesn't exist
        print("\nChecking indexes on documents...")
        indexes = await conn.fetch("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'documents' AND indexname LIKE '%tenant_id%'
        """)
        if not indexes:
            print("Adding index on tenant_id...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_tenant_id ON documents(tenant_id)
            """)
            print("✅ Added index on tenant_id")
        else:
            print("✓ Index on tenant_id already exists")
        
        # Check if columns exist in document_chunks table
        print("\nChecking document_chunks table...")
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'document_chunks'
        """)
        
        chunks_columns = [row['column_name'] for row in result]
        print(f"Existing columns: {chunks_columns}")
        
        # Add missing columns to document_chunks table
        if 'tenant_id' not in chunks_columns:
            print("\nAdding column: tenant_id")
            await conn.execute("""
                ALTER TABLE document_chunks 
                ADD COLUMN tenant_id VARCHAR(128) NOT NULL DEFAULT 'default-tenant'
            """)
            print("✅ Added tenant_id")
        else:
            print("✓ Column tenant_id already exists")
        
        # Update existing chunks to have tenant_id from their document
        print("\nUpdating existing chunks with tenant_id from documents...")
        updated = await conn.execute("""
            UPDATE document_chunks 
            SET tenant_id = (
                SELECT tenant_id 
                FROM documents 
                WHERE documents.id = document_chunks.document_id
            )
            WHERE tenant_id IS NULL
        """)
        print(f"✅ Updated chunk rows")
        
        # Set default for any remaining nulls
        await conn.execute("""
            UPDATE document_chunks 
            SET tenant_id = 'default-tenant' 
            WHERE tenant_id IS NULL
        """)
        
        # Add index on tenant_id for chunks if it doesn't exist
        print("\nChecking indexes on document_chunks...")
        indexes = await conn.fetch("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'document_chunks' AND indexname LIKE '%tenant_id%'
        """)
        if not indexes:
            print("Adding index on tenant_id...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_tenant_id ON document_chunks(tenant_id)
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
