"""
FastAPI application entry point
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os
import sys
from pathlib import Path

# Dynamically locate shared libs for CORS helper
current_file = Path(__file__).resolve()
current_dir = current_file.parent
while current_dir != current_dir.parent:
    shared_libs_candidate = current_dir / "platform" / "shared_libs"
    if shared_libs_candidate.exists():
        shared_libs_dir = shared_libs_candidate
        break
    current_dir = current_dir.parent
else:
    # Fallback: go to repo root from app/ directory (match agent-manager pattern)
    shared_libs_dir = current_file.parent.parent.parent / "platform" / "shared_libs"

sys.path.insert(0, str(shared_libs_dir))
try:
    from pyshared import add_env_cors  # noqa: E402
except ImportError:
    # Fallback to basic CORS if shared libs not available
    from fastapi.middleware.cors import CORSMiddleware
    def add_env_cors(app):
        app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

from app.core.database import init_db
from app.api.routes import brand_sync, ugc, conversation

app = FastAPI(title="UGC Orchestrator API with DB & S3", version="2.0.0")

# Add CORS middleware (env-driven origins with localhost defaults)
add_env_cors(app)

# Include routers
app.include_router(brand_sync.router, prefix="/orchestrator", tags=["brand-sync"])
app.include_router(ugc.router, prefix="/chat/ugc", tags=["ugc"])
app.include_router(conversation.router, prefix="/conversation", tags=["conversation"])


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    await init_db()
    print("✅ Server started with database & S3 integration")


@app.get("/")
async def serve_frontend():
    """Serve the chatbox HTML frontend"""
    if os.path.exists("chatbox.html"):
        return FileResponse("chatbox.html")
    return {"message": "Frontend not found"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "UGC Orchestrator API with DB & S3",
        "version": "2.0.0",
        "database": "PostgreSQL",
        "storage": "AWS S3"
    }


@app.get("/image/{filename}", deprecated=True)
async def get_image(filename: str):
    """
    [DEPRECATED] Retrieve a generated image by filename (legacy - for local files only)
    
    This endpoint is deprecated and should not be used for new flows.
    Reason: Only works for local files, breaks in containers and multi-instance deployments.
    
    For new implementations:
    - Use S3 URLs directly from the database
    - Or generate presigned URLs for client access
    """
    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(filename, media_type="image/png")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
