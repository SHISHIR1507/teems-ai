import asyncio
import os
import sys
import contextlib
from typing import Optional

# CRITICAL: Redirect stdout to stderr to prevent print statements from corrupting MCP protocol
# MCP uses stdout for communication. Any stray print() will break the connection.
@contextlib.contextmanager
def redirect_stdout_to_stderr():
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout

# Add src directory to sys.path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import FastMCP (keep this safe)
from mcp.server.fastmcp import FastMCP

# Initialization wrapper to silence imports
with redirect_stdout_to_stderr():
    try:
        import asyncpg
        from urllib.parse import urlparse
        
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Parse connection URL
        parsed = urlparse(database_url)
        
        # Extract connection parameters
        db_config = {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/"),
            "user": parsed.username,
            "password": parsed.password,
        }
        
        print(f"DEBUG: Initialized PostgreSQL MCP wrapper with database: {db_config['database']}", file=sys.stderr)
        
    except Exception as e:
        print(f"CRITICAL ERROR during imports: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

# Initialize FastMCP server
mcp = FastMCP("PostgreSQL Query Server")

# Global connection pool (lazy initialization)
_connection_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        async with _pool_lock:
            if _connection_pool is None:
                _connection_pool = await asyncpg.create_pool(
                    host=db_config["host"],
                    port=db_config["port"],
                    database=db_config["database"],
                    user=db_config["user"],
                    password=db_config["password"],
                    min_size=1,
                    max_size=5,
                )
    return _connection_pool


@mcp.tool()
async def query(sql: str, tenant_id: str) -> str:
    """
    Execute a read-only SQL query with automatic tenant isolation via Row Level Security.
    
    Args:
        sql: SQL query to execute (read-only, SELECT only)
        tenant_id: Tenant ID for row-level security filtering (automatically injected from auth)
    
    Returns:
        Query results as formatted text
    """
    # Redirect stdout during execution too, just in case called functions print stuff
    with redirect_stdout_to_stderr():
        try:
            if not tenant_id:
                return "Error: tenant_id is required for query execution"
            
            # Validate that query is read-only (basic check)
            sql_upper = sql.strip().upper()
            if not sql_upper.startswith("SELECT"):
                return "Error: Only SELECT queries are allowed"
            
            # Get connection pool
            pool = await get_pool()
            
            # Execute query with tenant context
            async with pool.acquire() as conn:
                # Use a transaction to ensure SET LOCAL works correctly
                async with conn.transaction():
                    # Set tenant context for RLS
                    await conn.execute("SET LOCAL app.current_tenant = $1", tenant_id)
                    
                    # Execute the actual query
                    rows = await conn.fetch(sql)
                
                # Format results
                if not rows:
                    return "No rows returned"
                
                # Get column names
                columns = list(rows[0].keys())
                
                # Format as table
                result_lines = []
                result_lines.append(" | ".join(columns))
                result_lines.append("-" * (sum(len(col) for col in columns) + 3 * (len(columns) - 1)))
                
                for row in rows:
                    values = [str(row[col]) if row[col] is not None else "NULL" for col in columns]
                    result_lines.append(" | ".join(values))
                
                return "\n".join(result_lines)
                
        except Exception as e:
            error_msg = f"Error executing query: {str(e)}"
            print(f"ERROR in postgres_wrapper.query: {error_msg}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return error_msg


if __name__ == "__main__":
    # Ensure any final startup logs go to stderr
    with redirect_stdout_to_stderr():
        print("Starting PostgreSQL MCP Server...", file=sys.stderr)
    
    # Run the MCP server (this needs standard stdout!)
    mcp.run()
