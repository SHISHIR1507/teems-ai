"""
FastAPI application entry point
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os

from app.core.database import init_db
from app.api.routes import brand_sync, ugc, conversation

app = FastAPI(title="UGC Orchestrator API with DB & S3", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
