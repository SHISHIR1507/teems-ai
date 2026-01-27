"""
Migration script to create eve_conversations and eve_messages tables
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
        # Create eve_conversations table
        print("\nCreating eve_conversations table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS eve_conversations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id VARCHAR(128) NOT NULL,
                session_id VARCHAR(255) NOT NULL,
                user_id VARCHAR(255),
                title VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ eve_conversations table created")
        
        # Create indexes on eve_conversations
        print("\nCreating indexes on eve_conversations...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_eve_conversations_tenant_id ON eve_conversations(tenant_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_eve_conversations_session_id ON eve_conversations(session_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_eve_conversations_tenant_session ON eve_conversations(tenant_id, session_id)
        """)
        print("✅ Indexes created on eve_conversations")
        
        # Add unique constraint on (tenant_id, session_id)
        print("\nAdding unique constraint on (tenant_id, session_id)...")
        # Check if constraint already exists
        constraints = await conn.fetch("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'eve_conversations' 
            AND constraint_name = 'uq_eve_conversations_tenant_session'
        """)
        if not constraints:
            await conn.execute("""
                ALTER TABLE eve_conversations 
                ADD CONSTRAINT uq_eve_conversations_tenant_session 
                UNIQUE (tenant_id, session_id)
            """)
            print("✅ Unique constraint added")
        else:
            print("✓ Unique constraint already exists")
        
        # Create eve_messages table
        print("\nCreating eve_messages table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS eve_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID NOT NULL REFERENCES eve_conversations(id) ON DELETE CASCADE,
                tenant_id VARCHAR(128) NOT NULL,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB,
                sequence_number INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ eve_messages table created")
        
        # Create indexes on eve_messages
        print("\nCreating indexes on eve_messages...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_eve_messages_conversation_id ON eve_messages(conversation_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_eve_messages_tenant_id ON eve_messages(tenant_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_eve_messages_conversation_sequence ON eve_messages(conversation_id, sequence_number)
        """)
        print("✅ Indexes created on eve_messages")
        
        print("\n" + "="*60)
        print("✅ Conversations tables migration completed successfully!")
        print("="*60)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
