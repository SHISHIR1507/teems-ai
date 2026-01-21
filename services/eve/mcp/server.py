import asyncio
import os
import sys
import contextlib

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
        # Import from new structure
        from eve_agent.database.session import SessionLocal
        from eve_agent.services.rag.rag_service import rag_service
        from eve_agent.models.document import Document
        from eve_agent.config import get_settings
        
        settings = get_settings()
        
        # Initialize services validation (optional check)
        print(f"DEBUG: Initialized with DB URL: {settings.postgres_url}", file=sys.stderr)
        
    except Exception as e:
        print(f"CRITICAL ERROR during imports: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

# Initialize FastMCP server
mcp = FastMCP("RAG Knowledge Base")

@mcp.tool()
async def query_knowledge_base(query: str, tenant_id: str = "default") -> str:
    """
    Query the RAG knowledge base to answer questions based on uploaded documents.
    
    Args:
        query: The question to ask.
        tenant_id: The tenant ID to scope the search (default: "default").
        
    Returns:
        A string containing the answer and source citations.
    """
    # Redirect stdout during execution too, just in case called functions print stuff
    with redirect_stdout_to_stderr():
        try:
            # Create a new database session
            db = SessionLocal()
            try:
                # 1. Use the main query method from RAG service
                # This handles retrieval, context building, and LLM generation
                result = await rag_service.query(
                    db=db,
                    question=query,
                    tenant_id=tenant_id,
                    top_k=settings.rag_top_k
                )
                
                answer = result["answer"]
                sources = result.get("sources", [])
                
                # Format sources for display
                if sources:
                    sources_text = "\n\nSources:\n" + "\n".join(
                        [f"- Source {i+1} (Score: {s.get('similarity', 0):.4f}): {s.get('content', '')[:100]}..." 
                         for i, s in enumerate(sources)]
                    )
                else:
                    sources_text = ""
                
                return f"{answer}{sources_text}"
                
            finally:
                db.close()
                
        except Exception as e:
            return f"Error querying knowledge base: {str(e)}"

@mcp.tool()
async def list_documents(tenant_id: str = "default") -> str:
    """
    List all documents currently available in the knowledge base for a specific tenant.
    
    Args:
        tenant_id: The tenant ID to filter documents (default: "default").
        
    Returns:
        A formatted list of documents with their IDs and filenames.
    """
    with redirect_stdout_to_stderr():
        try:
            db = SessionLocal()
            try:
                documents = db.query(Document).filter(Document.tenant_id == tenant_id).all()
                
                if not documents:
                    return f"No documents found for tenant '{tenant_id}'."
                
                result_lines = [f"Documents for tenant '{tenant_id}':"]
                for doc in documents:
                    status_icon = "✅" if doc.status == "completed" else "⏳"
                    result_lines.append(
                        f"{status_icon} ID: {doc.id} | File: {doc.filename} | Chunks: {doc.total_chunks} | Created: {doc.created_at.strftime('%Y-%m-%d')}"
                    )
                
                return "\n".join(result_lines)
                
            finally:
                db.close()
                
        except Exception as e:
            return f"Error listing documents: {str(e)}"

if __name__ == "__main__":
    # Ensure any final startup logs go to stderr
    with redirect_stdout_to_stderr():
        print("Starting MCP Server...", file=sys.stderr)
        
    # Run the MCP server (this needs standard stdout!)
    mcp.run()
