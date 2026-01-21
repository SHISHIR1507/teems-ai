"""
Database migration script to add S3-related fields to documents table.

Run this script once to add the new columns needed for the RAG system.
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from eve_agent.database.session import engine


def run_migration():
    """Add S3-related columns to documents table."""
    
    print("🔄 Running database migration...")
    print("=" * 80)
    
    migrations = [
        {
            "name": "Add filename column",
            "sql": "ALTER TABLE documents ADD COLUMN IF NOT EXISTS filename VARCHAR(255);"
        },
        {
            "name": "Add s3_url column",
            "sql": "ALTER TABLE documents ADD COLUMN IF NOT EXISTS s3_url TEXT;"
        },
        {
            "name": "Add s3_key column",
            "sql": "ALTER TABLE documents ADD COLUMN IF NOT EXISTS s3_key TEXT;"
        },
        {
            "name": "Add file_size_bytes column",
            "sql": "ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;"
        },
        {
            "name": "Add total_chunks column",
            "sql": "ALTER TABLE documents ADD COLUMN IF NOT EXISTS total_chunks INTEGER;"
        },
        {
            "name": "Add status column",
            "sql": "ALTER TABLE documents ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'uploaded';"
        },
        {
            "name": "Create index on s3_key",
            "sql": "CREATE INDEX IF NOT EXISTS ix_documents_s3_key ON documents(s3_key);"
        },
        {
            "name": "Create index on status",
            "sql": "CREATE INDEX IF NOT EXISTS ix_documents_status ON documents(status);"
        }
    ]
    
    with engine.connect() as conn:
        for migration in migrations:
            try:
                print(f"  • {migration['name']}...", end=" ")
                conn.execute(text(migration['sql']))
                conn.commit()
                print("✅")
            except Exception as e:
                print(f"❌ Error: {e}")
                conn.rollback()
    
    print("=" * 80)
    print("✅ Migration completed successfully!")
    print()
    
    # Verify the new columns
    print("🔍 Verifying new columns...")
    print("=" * 80)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'documents'
            AND column_name IN ('filename', 's3_url', 's3_key', 'file_size_bytes', 'total_chunks', 'status')
            ORDER BY column_name;
        """))
        
        columns = result.fetchall()
        if columns:
            print("\n✅ New columns added successfully:\n")
            for col in columns:
                nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                default = f" DEFAULT {col[3]}" if col[3] else ""
                print(f"  • {col[0]:<20} {col[1]:<20} {nullable}{default}")
        else:
            print("❌ No new columns found!")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    run_migration()
