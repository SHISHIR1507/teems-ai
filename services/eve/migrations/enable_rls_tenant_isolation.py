"""
Migration script to enable Row Level Security (RLS) with tenant isolation
RLS policies apply ONLY to eve_mcp_readonly role
All other roles bypass RLS (grant BYPASSRLS)
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

# All 28 tables that need RLS
TABLES_WITH_RLS = [
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

# MCP role that will be subject to RLS
MCP_ROLE = "eve_mcp_readonly"


async def get_main_app_role(conn: asyncpg.Connection) -> str:
    """Get the main application role name from DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return None
    
    # Parse URL to extract username
    from urllib.parse import urlparse
    parsed = urlparse(database_url)
    return parsed.username


async def migrate():
    """Run the RLS migration."""
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
        # Start transaction
        async with conn.transaction():
            # Step 1: Get main application role
            print("\n" + "="*60)
            print("Step 1: Granting BYPASSRLS to existing roles")
            print("="*60)
            
            main_app_role = await get_main_app_role(conn)
            if main_app_role:
                print(f"\nGranting BYPASSRLS to main application role: {main_app_role}")
                try:
                    await conn.execute(f"ALTER ROLE {main_app_role} WITH BYPASSRLS")
                    print(f"✅ Granted BYPASSRLS to {main_app_role}")
                except Exception as e:
                    print(f"⚠️  Could not grant BYPASSRLS to {main_app_role}: {e}")
            else:
                print("⚠️  Could not determine main application role from DATABASE_URL")
            
            # Grant BYPASSRLS to analyst role (create if doesn't exist)
            print("\nSetting up analyst role...")
            analyst_role = "eve_analyst_role"
            analyst_exists = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = $1)
            """, analyst_role)
            
            if not analyst_exists:
                print(f"Creating role '{analyst_role}'...")
                await conn.execute(f"CREATE ROLE {analyst_role} WITH LOGIN")
                await conn.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {analyst_role}")
                print(f"✅ Created role '{analyst_role}'")
            else:
                print(f"✓ Role '{analyst_role}' already exists")
            
            try:
                await conn.execute(f"ALTER ROLE {analyst_role} WITH BYPASSRLS")
                print(f"✅ Granted BYPASSRLS to {analyst_role}")
            except Exception as e:
                print(f"⚠️  Could not grant BYPASSRLS to {analyst_role}: {e}")
            
            # Step 2: Enable RLS on all 28 tables
            print("\n" + "="*60)
            print("Step 2: Enabling RLS on tables")
            print("="*60)
            
            enabled_count = 0
            skipped_count = 0
            
            for table_name in TABLES_WITH_RLS:
                try:
                    # Check if table exists
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = $1
                        )
                    """, table_name)
                    
                    if table_exists:
                        # Check if RLS is already enabled
                        rls_enabled = await conn.fetchval("""
                            SELECT relrowsecurity 
                            FROM pg_class 
                            WHERE relname = $1 AND relnamespace = (
                                SELECT oid FROM pg_namespace WHERE nspname = 'public'
                            )
                        """, table_name)
                        
                        if not rls_enabled:
                            await conn.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
                            enabled_count += 1
                            print(f"  ✓ Enabled RLS on {table_name}")
                        else:
                            print(f"  ⊙ RLS already enabled on {table_name}")
                    else:
                        skipped_count += 1
                        print(f"  ⚠️  Table {table_name} does not exist, skipping")
                except Exception as e:
                    print(f"  ❌ Error enabling RLS on {table_name}: {e}")
                    skipped_count += 1
            
            print(f"\n✅ Enabled RLS on {enabled_count} tables")
            if skipped_count > 0:
                print(f"⚠️  Skipped {skipped_count} tables (do not exist yet)")
            
            # Step 3: Create role-specific policies
            print("\n" + "="*60)
            print("Step 3: Creating role-specific RLS policies")
            print("="*60)
            
            # Check if MCP role exists
            mcp_role_exists = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = $1)
            """, MCP_ROLE)
            
            if not mcp_role_exists:
                print(f"⚠️  WARNING: Role '{MCP_ROLE}' does not exist!")
                print(f"   Run 'create_mcp_restricted_role.py' first to create this role.")
                print(f"   Policies will be created but won't apply until the role exists.")
            
            policy_count = 0
            skipped_policy_count = 0
            
            for table_name in TABLES_WITH_RLS:
                try:
                    # Check if table exists
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = $1
                        )
                    """, table_name)
                    
                    if not table_exists:
                        skipped_policy_count += 1
                        continue
                    
                    # Check if policy already exists
                    policy_name = f"tenant_select_{table_name}"
                    policy_exists = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM pg_policies 
                            WHERE schemaname = 'public' 
                            AND tablename = $1 
                            AND policyname = $2
                        )
                    """, table_name, policy_name)
                    
                    if policy_exists:
                        # Drop existing policy to recreate with correct role restriction
                        await conn.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table_name}")
                    
                    # Create role-specific SELECT policy
                    # Policy applies ONLY to eve_mcp_readonly role
                    await conn.execute(f"""
                        CREATE POLICY {policy_name} ON {table_name}
                        FOR SELECT
                        TO {MCP_ROLE}
                        USING (
                            tenant_id = current_setting('app.current_tenant', true)
                            AND tenant_id IS NOT NULL
                        )
                    """)
                    policy_count += 1
                    print(f"  ✓ Created policy {policy_name} on {table_name}")
                    
                except Exception as e:
                    print(f"  ❌ Error creating policy for {table_name}: {e}")
                    skipped_policy_count += 1
            
            print(f"\n✅ Created {policy_count} RLS policies")
            if skipped_policy_count > 0:
                print(f"⚠️  Skipped {skipped_policy_count} policies (tables do not exist)")
            
            # Step 4: Verify setup
            print("\n" + "="*60)
            print("Step 4: Verifying RLS setup")
            print("="*60)
            
            # Check RLS status
            rls_tables = await conn.fetch("""
                SELECT relname 
                FROM pg_class 
                WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                AND relkind = 'r'
                AND relrowsecurity = true
                ORDER BY relname
            """)
            
            rls_table_names = [row['relname'] for row in rls_tables]
            print(f"\n📋 RLS enabled on {len(rls_table_names)} tables:")
            for table in rls_table_names:
                print(f"   - {table}")
            
            # Check policies
            policies = await conn.fetch("""
                SELECT tablename, policyname, roles
                FROM pg_policies
                WHERE schemaname = 'public'
                AND policyname LIKE 'tenant_select_%'
                ORDER BY tablename
            """)
            
            print(f"\n📋 Created {len(policies)} RLS policies:")
            for policy in policies:
                roles = policy['roles'] if policy['roles'] else []
                role_str = ', '.join(roles) if roles else 'public'
                print(f"   - {policy['policyname']} on {policy['tablename']} (roles: {role_str})")
            
            # Check BYPASSRLS status
            bypass_roles = await conn.fetch("""
                SELECT rolname 
                FROM pg_roles 
                WHERE rolbypassrls = true
                ORDER BY rolname
            """)
            
            bypass_role_names = [row['rolname'] for row in bypass_roles]
            print(f"\n📋 Roles with BYPASSRLS ({len(bypass_role_names)}):")
            for role in bypass_role_names:
                print(f"   - {role}")
            
            # Verify MCP role does NOT have BYPASSRLS
            if mcp_role_exists:
                mcp_bypass = await conn.fetchval("""
                    SELECT rolbypassrls 
                    FROM pg_roles 
                    WHERE rolname = $1
                """, MCP_ROLE)
                
                if mcp_bypass:
                    print(f"\n⚠️  WARNING: Role '{MCP_ROLE}' has BYPASSRLS! This should NOT be set.")
                    print(f"   RLS policies will not apply to this role.")
                else:
                    print(f"\n✅ Role '{MCP_ROLE}' does NOT have BYPASSRLS (correct)")
        
        print("\n" + "="*60)
        print("✅ RLS migration completed successfully!")
        print("="*60)
        print("\nSummary:")
        print(f"- RLS enabled on: {len(rls_table_names)} tables")
        print(f"- Policies created: {len(policies)}")
        print(f"- Roles with BYPASSRLS: {len(bypass_role_names)}")
        print(f"- MCP role '{MCP_ROLE}' subject to RLS: {mcp_role_exists and not mcp_bypass if mcp_role_exists else 'N/A'}")
        print("\nNext steps:")
        print("1. Ensure custom PostgreSQL MCP wrapper is configured")
        print("2. Test MCP queries to verify tenant isolation")
        print("3. Verify Eve app and agents can still access data (they bypass RLS)")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
