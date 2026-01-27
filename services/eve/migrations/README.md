# Eve Agent Database Migrations

This directory contains database migration scripts for the Eve Agent service.

## Available Migrations

### 1. `initial_schema_migration.py`
Creates the initial database schema:
- Enables pgvector extension
- Creates `documents` table
- Creates `document_chunks` table
- Creates necessary indexes

**Run this first** if setting up a new database.

### 2. `add_tenant_isolation_migration.py`
Adds tenant isolation to existing tables:
- Adds `tenant_id` column to `documents` and `document_chunks` tables (if missing)
- Creates indexes on `tenant_id` columns
- Updates existing data with default tenant_id

**Run this** if you have existing data and need to add tenant isolation.

### 3. `create_mcp_restricted_role.py`
Creates a restricted PostgreSQL role for the MCP server with SELECT-only access to specific tables:
- Creates `eve_mcp_readonly` role (or uses existing)
- Grants SELECT on 28 allowed tables (Eve + all 5 agents)
- Revokes all other permissions (system tables, other schemas)
- Sets default privileges to prevent future table access

**Run this** to set up hard database-level restrictions for PostgreSQL MCP access.

### 4. `create_conversations_tables.py`
Creates conversation and message tables:
- Creates `eve_conversations` table
- Creates `eve_messages` table
- Creates necessary indexes and constraints

**Run this** to enable persistent conversation storage.

### 5. `rename_documents_tables.py`
Renames existing tables to use `eve_` prefix:
- Renames `documents` → `eve_documents`
- Renames `document_chunks` → `eve_document_chunks`
- Updates foreign keys and indexes

**Run this** to standardize table naming with `eve_` prefix.

### 6. `enable_rls_tenant_isolation.py`
Enables Row Level Security (RLS) with tenant isolation:
- Grants BYPASSRLS to all existing roles (Eve app, agents, analyst)
- Enables RLS on 28 tables (Eve + all 5 agents)
- Creates role-specific policies that apply ONLY to `eve_mcp_readonly` role
- All other roles bypass RLS and use static queries

**Run this** after creating the MCP restricted role to enable tenant isolation for MCP queries.

## Running Migrations

### Prerequisites
- PostgreSQL database with pgvector extension support
- `DATABASE_URL` environment variable set
- Python dependencies installed (`asyncpg`, `python-dotenv`)

### Running a Migration

```bash
# From services/eve directory
python migrations/initial_schema_migration.py
python migrations/add_tenant_isolation_migration.py
```

Or from the migrations directory:

```bash
cd migrations
python initial_schema_migration.py
python add_tenant_isolation_migration.py
```

### Environment Variables

Migrations read from:
1. `.env` file in `services/eve/` directory
2. `agent/.env` file in `services/eve/agent/` directory
3. System environment variables

Required:
- `DATABASE_URL` - PostgreSQL connection string (e.g., `postgresql://user:password@host:port/dbname`)

For MCP role migration (`create_mcp_restricted_role.py`):
- `POSTGRES_MCP_PASSWORD` - Secure password for the MCP role (generate using `generate_mcp_password.py`)
- `POSTGRES_MCP_USER` - Optional, defaults to `eve_mcp_readonly`

## Migration Order

1. **First time setup**: Run `initial_schema_migration.py`
2. **Adding tenant isolation to existing data**: Run `add_tenant_isolation_migration.py`
3. **Setting up MCP restrictions**: Run `create_mcp_restricted_role.py` (see MCP Role Setup below)
4. **Creating conversation tables**: Run `create_conversations_tables.py`
5. **Renaming tables**: Run `rename_documents_tables.py` (if needed)
6. **Enabling RLS**: Run `enable_rls_tenant_isolation.py` (see RLS Setup below)

## MCP Role Setup

The PostgreSQL MCP server uses a restricted read-only role to limit database access to only specific tables from Eve and all 5 agents.

### Step 1: Generate Password

Generate a secure password for the MCP role:

```bash
python migrations/generate_mcp_password.py
```

This will output a secure random password. Optionally use `--save` flag to automatically add it to `.env`:

```bash
python migrations/generate_mcp_password.py --save
```

### Step 2: Set Environment Variable

Set the password as an environment variable:

```bash
export POSTGRES_MCP_PASSWORD='<generated_password>'
```

Or add to `.env` file:

```env
POSTGRES_MCP_PASSWORD=<generated_password>
POSTGRES_MCP_USER=eve_mcp_readonly  # Optional, defaults to this
```

### Step 3: Run Migration

Run the migration script:

```bash
python migrations/create_mcp_restricted_role.py
```

This will:
- Create the `eve_mcp_readonly` role (if it doesn't exist)
- Grant SELECT on 28 allowed tables
- Revoke all other permissions
- Verify the setup

### Step 4: Verify Restrictions

After migration, verify the restrictions work:

```sql
-- Connect as eve_mcp_readonly user
psql -U eve_mcp_readonly -d your_database

-- Should work: Query allowed table
SELECT COUNT(*) FROM eve_documents;

-- Should fail: Query system table
SELECT * FROM pg_class;  -- Permission denied

-- Should fail: Query non-allowed table
SELECT * FROM some_other_table;  -- Permission denied
```

### Allowed Tables (28 total)

**Eve Service (4):** `eve_documents`, `eve_document_chunks`, `eve_conversations`, `eve_messages`

**Notetaker (4):** `notetaker_calls`, `notetaker_call_chunks`, `notetaker_user_settings`, `notetaker_calendar_events`

**Fashion Photo (6):** `fashion_sessions`, `fashion_avatars`, `fashion_apparel`, `fashion_generated_images`, `fashion_messages`, `fashion_tasks`

**Presentation (5):** `presentation_conversations`, `presentation_messages`, `presentations`, `presentation_documents`, `presentation_tasks`

**Social Media (5):** `social_media_conversations`, `social_media_content_assets`, `social_media_messages`, `social_media_user_tokens`, `social_media_posts`

**UGC Video (3):** `ugc_conversations`, `ugc_messages`, `ugc_assets`

### Security Notes

- The role has SELECT-only permissions (read-only)
- No access to system tables (`pg_catalog`, `information_schema`, etc.)
- No access to tables outside the allowed list
- Future tables won't be accessible by default
- Password should be stored securely (environment variables, secrets manager)

## RLS Setup

Row Level Security (RLS) provides tenant isolation at the database level for MCP queries.

### Step 1: Run RLS Migration

After creating the MCP restricted role, enable RLS:

```bash
python migrations/enable_rls_tenant_isolation.py
```

This will:
- Grant BYPASSRLS to all existing roles (Eve app, agents, analyst)
- Enable RLS on 28 tables
- Create role-specific policies that apply ONLY to `eve_mcp_readonly` role
- Verify the setup

### Step 2: Verify RLS

After migration, verify RLS is working:

```sql
-- Connect as eve_mcp_readonly user
psql -U eve_mcp_readonly -d your_database

-- Set tenant context
SET LOCAL app.current_tenant = 'tenant-123';

-- Should only return rows for tenant-123
SELECT * FROM eve_documents;

-- Reset tenant context
SET LOCAL app.current_tenant = 'tenant-456';

-- Should only return rows for tenant-456
SELECT * FROM eve_documents;
```

### RLS Behavior

- **MCP queries** (via `eve_mcp_readonly` role): Subject to RLS, automatically filtered by tenant
- **Eve application queries**: Bypass RLS (use static queries with tenant_id in WHERE clauses)
- **Agent services**: Bypass RLS (use static queries with tenant_id in WHERE clauses)
- **Analyst queries**: Bypass RLS (can query all tenants for analysis)

### Important Notes

- RLS policies only apply to `eve_mcp_readonly` role
- All other roles have BYPASSRLS and bypass RLS automatically
- Custom PostgreSQL MCP wrapper automatically injects tenant_id from authenticated user
- No code changes needed for Eve app or agents

## Notes

- Migrations are idempotent - safe to run multiple times
- Migrations check for existing columns/indexes before creating
- Default tenant_id for existing data: `'default-tenant'`
- All migrations use asyncpg for async database operations
