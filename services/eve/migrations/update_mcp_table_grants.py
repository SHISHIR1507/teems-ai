"""
Migration script to update table permissions for existing MCP role.
ASSUMES the role already exists with correct password.

Use this script after initial setup to safely add/update table grants.
To create the role initially, use create_mcp_restricted_role.py instead.
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

# MCP role configuration (already created in database)
MCP_USER = os.getenv("POSTGRES_MCP_USER", "eve_mcp_readonly")
# MCP_PASSWORD not needed - we're not creating/updating the user

# Allowed tables (38 total)
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
    # Onboarding Service (2 tables)
    "onboarding_states",
    "conversation_messages",
    # Brandfetch API (1 table)
    "brandfetch_results",
    # Agent Manager (7 tables)
    "agent_assignments",
    "agent_executions",
    "agent_runs",
    "agent_versions",
    "agents",
    "user_integrations",
    "user_preferences",
]

async def migrate():
    # Parse DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Convert asyncpg URL to regular postgres URL for asyncpg.connect
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    print("Connecting to database...")
    conn = await asyncpg.connect(conn_url)
    
    try:
        # Start transaction
        async with conn.transaction():
            # Verify role exists (fail early if not)
            print(f"\nVerifying role '{MCP_USER}' exists...")
            role_exists = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_roles WHERE rolname = $1
                )
            """, MCP_USER)
            
            if not role_exists:
                print(f"❌ Role '{MCP_USER}' does not exist!")
                print("   Run create_mcp_restricted_role.py first to create the role.")
                return
            
            print(f"✓ Role '{MCP_USER}' exists")
            
            # Revoke all permissions on public schema first (clean slate)
            print("\nRevoking all current permissions on public schema...")
            await conn.execute(f"REVOKE ALL ON SCHEMA public FROM {MCP_USER}")
            await conn.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {MCP_USER}")
            print("✅ Revoked all permissions on public schema")
            
            # Grant USAGE on schema (needed to access tables)
            print("\nGranting USAGE on public schema...")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {MCP_USER}")
            print("✅ Granted USAGE on public schema")
            
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
                            GRANT SELECT ON TABLE {table_name} TO {MCP_USER}
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
                REVOKE ALL ON TABLES FROM {MCP_USER}
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
            """, MCP_USER)
            
            accessible_table_names = [row['table_name'] for row in accessible_tables]
            print(f"\n📋 Role '{MCP_USER}' has SELECT access to {len(accessible_table_names)} tables:")
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
        print("✅ MCP table grants updated successfully!")
        print("="*60)
        print(f"\nRole: {MCP_USER}")
        print(f"Accessible tables: {len(accessible_table_names)}")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
