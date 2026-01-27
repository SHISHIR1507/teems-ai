"""
Migration script to rename documents → eve_documents and document_chunks → eve_document_chunks
Also renames all related indexes and updates foreign keys
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
        # Check if tables exist
        print("\nChecking existing tables...")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('documents', 'document_chunks', 'eve_documents', 'eve_document_chunks')
        """)
        existing_tables = [row['table_name'] for row in tables]
        print(f"Existing tables: {existing_tables}")
        
        # Rename documents → eve_documents
        if 'documents' in existing_tables and 'eve_documents' not in existing_tables:
            print("\nRenaming documents → eve_documents...")
            await conn.execute("ALTER TABLE documents RENAME TO eve_documents")
            print("✅ Table renamed: documents → eve_documents")
        elif 'eve_documents' in existing_tables:
            print("✓ Table eve_documents already exists")
        else:
            print("⚠️  Table documents does not exist, skipping rename")
        
        # Rename document_chunks → eve_document_chunks
        if 'document_chunks' in existing_tables and 'eve_document_chunks' not in existing_tables:
            print("\nRenaming document_chunks → eve_document_chunks...")
            await conn.execute("ALTER TABLE document_chunks RENAME TO eve_document_chunks")
            print("✅ Table renamed: document_chunks → eve_document_chunks")
        elif 'eve_document_chunks' in existing_tables:
            print("✓ Table eve_document_chunks already exists")
        else:
            print("⚠️  Table document_chunks does not exist, skipping rename")
        
        # Update foreign key in eve_document_chunks if it still references documents
        if 'eve_document_chunks' in existing_tables or 'eve_document_chunks' in [t for t in existing_tables if 'eve' in t]:
            print("\nChecking foreign key constraints...")
            fk_constraints = await conn.fetch("""
                SELECT 
                    tc.constraint_name,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'eve_document_chunks'
                AND ccu.table_name = 'documents'
            """)
            
            if fk_constraints:
                print("Found foreign key referencing old 'documents' table, updating...")
                for fk in fk_constraints:
                    constraint_name = fk['constraint_name']
                    # Drop old constraint
                    await conn.execute(f"ALTER TABLE eve_document_chunks DROP CONSTRAINT {constraint_name}")
                    # Add new constraint referencing eve_documents
                    await conn.execute(f"""
                        ALTER TABLE eve_document_chunks 
                        ADD CONSTRAINT {constraint_name.replace('documents', 'eve_documents')}
                        FOREIGN KEY (document_id) 
                        REFERENCES eve_documents(id) 
                        ON DELETE CASCADE
                    """)
                    print(f"✅ Updated foreign key constraint: {constraint_name}")
            else:
                print("✓ Foreign key already references eve_documents or doesn't exist")
        
        # Rename indexes
        print("\nRenaming indexes...")
        indexes = await conn.fetch("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename IN ('eve_documents', 'eve_document_chunks')
            AND indexname NOT LIKE 'eve_%'
        """)
        
        for index in indexes:
            old_name = index['indexname']
            # Determine new name based on old name
            if old_name.startswith('idx_documents'):
                new_name = old_name.replace('idx_documents', 'idx_eve_documents')
            elif old_name.startswith('idx_document_chunks'):
                new_name = old_name.replace('idx_document_chunks', 'idx_eve_document_chunks')
            else:
                # Generic rename
                if 'documents' in old_name and 'eve_documents' in existing_tables:
                    new_name = old_name.replace('documents', 'eve_documents')
                elif 'document_chunks' in old_name:
                    new_name = old_name.replace('document_chunks', 'eve_document_chunks')
                else:
                    continue
            
            try:
                await conn.execute(f"ALTER INDEX {old_name} RENAME TO {new_name}")
                print(f"✅ Renamed index: {old_name} → {new_name}")
            except Exception as e:
                print(f"⚠️  Could not rename index {old_name}: {e}")
        
        # Also check for indexes on old table names (in case they weren't renamed)
        old_indexes = await conn.fetch("""
            SELECT indexname, tablename
            FROM pg_indexes 
            WHERE tablename IN ('documents', 'document_chunks')
        """)
        
        if old_indexes:
            print("\nFound indexes on old table names, these will be automatically renamed with tables")
            for idx in old_indexes:
                print(f"  - {idx['indexname']} on {idx['tablename']}")
        
        print("\n" + "="*60)
        print("✅ Documents tables rename migration completed successfully!")
        print("="*60)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
