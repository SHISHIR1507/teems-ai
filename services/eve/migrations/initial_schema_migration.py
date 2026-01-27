"""
Initial schema migration - creates tables if they don't exist
and enables pgvector extension
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
        # Enable pgvector extension
        print("\nEnabling pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("✅ pgvector extension enabled")
        
        # Create documents table
        print("\nCreating documents table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id VARCHAR(128) NOT NULL,
                title VARCHAR(255),
                filename VARCHAR(255),
                s3_url TEXT,
                s3_key TEXT,
                file_size_bytes BIGINT,
                status VARCHAR(50) DEFAULT 'uploaded',
                total_chunks INTEGER,
                metadata JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ documents table created")
        
        # Create indexes on documents
        print("\nCreating indexes on documents...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_tenant_id ON documents(tenant_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_s3_key ON documents(s3_key)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)
        """)
        print("✅ Indexes created on documents")
        
        # Create document_chunks table
        print("\nCreating document_chunks table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                tenant_id VARCHAR(128) NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding vector(1536),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ document_chunks table created")
        
        # Create indexes on document_chunks
        print("\nCreating indexes on document_chunks...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_tenant_id ON document_chunks(tenant_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id)
        """)
        # Vector similarity index (optional, but improves search performance)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks 
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """)
        print("✅ Indexes created on document_chunks")
        
        print("\n" + "="*60)
        print("✅ Initial schema migration completed successfully!")
        print("="*60)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
