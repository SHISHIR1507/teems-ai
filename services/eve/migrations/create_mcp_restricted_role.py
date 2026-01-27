"""
Migration script to create restricted PostgreSQL role for MCP server
Grants SELECT-only access to specific tables from Eve and all 5 agents
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

# Allowed tables (28 total)
ALLOWED_TABLES = [
    # Eve Service (4 tables)
    "eve_documents",
    "eve_document_chunks",
    "eve_conversations",
    "eve_messages",
    # Notetaker Agent (4 tables)
    "notetaker_calls",
    "notetaker_call_chunks",
    "notetaker_user_settings",
    "notetaker_calendar_events",
    # Fashion Photo Agent (6 tables)
    "fashion_sessions",
    "fashion_avatars",
    "fashion_apparel",
    "fashion_generated_images",
    "fashion_messages",
    "fashion_tasks",
    # Presentation Agent (5 tables)
    "presentation_conversations",
    "presentation_messages",
    "presentations",
    "presentation_documents",
    "presentation_tasks",
    # Social Media Agent (5 tables)
    "social_media_conversations",
    "social_media_content_assets",
    "social_media_messages",
    "social_media_user_tokens",
    "social_media_posts",
    # UGC Video Agent (3 tables)
    "ugc_conversations",
    "ugc_messages",
    "ugc_assets",
]

async def migrate():
    # Parse DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Get MCP role password from environment
    mcp_password = os.getenv("POSTGRES_MCP_PASSWORD")
    if not mcp_password:
        print("❌ POSTGRES_MCP_PASSWORD not found in environment variables")
        print("   Run: python services/eve/migrations/generate_mcp_password.py")
        print("   Then set: export POSTGRES_MCP_PASSWORD=<generated_password>")
        return
    
    mcp_user = os.getenv("POSTGRES_MCP_USER", "eve_mcp_readonly")
    
    # Convert asyncpg URL to regular postgres URL for asyncpg.connect
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgresql://")
    
    print("Connecting to database...")
    conn = await asyncpg.connect(conn_url)
    
    try:
        # Start transaction
        async with conn.transaction():
            # Check if role already exists
            print(f"\nChecking if role '{mcp_user}' exists...")
            role_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_roles WHERE rolname = $1
                )
            """, mcp_user)
            
            if role_exists:
                print(f"✓ Role '{mcp_user}' already exists")
                # Update password if role exists
                await conn.execute(f"""
                    ALTER ROLE {mcp_user} WITH PASSWORD $1
                """, mcp_password)
                print(f"✓ Password updated for role '{mcp_user}'")
            else:
                # Create role
                print(f"\nCreating role '{mcp_user}'...")
                await conn.execute(f"""
                    CREATE ROLE {mcp_user} WITH LOGIN PASSWORD $1
                """, mcp_password)
                print(f"✅ Role '{mcp_user}' created")
            
            # Revoke all permissions on public schema first
            print("\nRevoking all permissions on public schema...")
            await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {mcp_user}")
            await conn.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {mcp_user}")
            print("✅ Revoked all permissions on public schema")
            
            # Grant USAGE on schema (needed to access tables)
            print("\nGranting USAGE on public schema...")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {mcp_user}")
            print("✅ Granted USAGE on public schema")
            
            # Revoke access to system schemas
            print("\nRevoking access to system schemas...")
            system_schemas = ["pg_catalog", "information_schema", "pg_toast"]
            for schema in system_schemas:
                try:
                    await conn.execute(f"REVOKE ALL ON SCHEMA {schema} FROM {mcp_user}")
                except Exception as e:
                    print(f"  ⚠️  Could not revoke on {schema}: {e}")
            print("✅ Revoked access to system schemas")
            
            # Grant SELECT on allowed tables
            print(f"\nGranting SELECT on {len(ALLOWED_TABLES)} allowed tables...")
            granted_count = 0
            skipped_count = 0
            
            for table_name in ALLOWED_TABLES:
                try:
                    # Check if table exists
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = $1
                        )
                    """, table_name)
                    
                    if table_exists:
                        await conn.execute(f"""
                            GRANT SELECT ON TABLE {table_name} TO {mcp_user}
                        """)
                        granted_count += 1
                        print(f"  ✓ Granted SELECT on {table_name}")
                    else:
                        skipped_count += 1
                        print(f"  ⚠️  Table {table_name} does not exist, skipping")
                except Exception as e:
                    print(f"  ❌ Error granting SELECT on {table_name}: {e}")
                    skipped_count += 1
            
            print(f"\n✅ Granted SELECT on {granted_count} tables")
            if skipped_count > 0:
                print(f"⚠️  Skipped {skipped_count} tables (do not exist yet)")
            
            # Set default privileges to prevent future tables from being accessible
            print("\nSetting default privileges...")
            await conn.execute(f"""
                ALTER DEFAULT PRIVILEGES IN SCHEMA public 
                REVOKE ALL ON TABLES FROM {mcp_user}
            """)
            print("✅ Default privileges set (future tables won't be accessible)")
            
            # Verify role permissions
            print("\nVerifying role permissions...")
            accessible_tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.table_privileges 
                WHERE grantee = $1 
                AND privilege_type = 'SELECT'
                AND table_schema = 'public'
                ORDER BY table_name
            """, mcp_user)
            
            accessible_table_names = [row['table_name'] for row in accessible_tables]
            print(f"\n📋 Role '{mcp_user}' has SELECT access to {len(accessible_table_names)} tables:")
            for table in accessible_table_names:
                print(f"   - {table}")
            
            # Check for any unexpected tables
            unexpected = set(accessible_table_names) - set(ALLOWED_TABLES)
            if unexpected:
                print(f"\n⚠️  WARNING: Found {len(unexpected)} unexpected accessible tables:")
                for table in unexpected:
                    print(f"   - {table}")
            else:
                print("\n✅ All accessible tables are in the allowed list")
        
        print("\n" + "="*60)
        print("✅ MCP restricted role migration completed successfully!")
        print("="*60)
        print(f"\nRole: {mcp_user}")
        print(f"Accessible tables: {len(accessible_table_names)}")
        print("\nNext steps:")
        print("1. Ensure POSTGRES_MCP_USER and POSTGRES_MCP_PASSWORD are set in environment")
        print("2. Restart Eve service to use the new MCP connection")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
