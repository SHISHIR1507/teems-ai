"""
Migration script to add product_name column to ugc_conversations table
Run this once to update your database schema
"""
import asyncio
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from core.database import init_engine, async_session_maker


async def add_product_name_column():
    """Add product_name column to ugc_conversations table"""
    
    # Initialize engine
    init_engine()
    
    async with async_session_maker() as session:
        try:
            # Check if column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='ugc_conversations' 
                AND column_name='product_name'
            """)
            
            result = await session.execute(check_query)
            exists = result.fetchone()
            
            if exists:
                print("✅ Column 'product_name' already exists in ugc_conversations table")
                return
            
            # Add the column
            alter_query = text("""
                ALTER TABLE ugc_conversations 
                ADD COLUMN product_name VARCHAR
            """)
            
            await session.execute(alter_query)
            await session.commit()
            
            print("✅ Successfully added 'product_name' column to ugc_conversations table")
            
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    print("Running migration: Add product_name column...")
    asyncio.run(add_product_name_column())
    print("Migration complete!")
