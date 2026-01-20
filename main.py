from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from routes.validator import router as validator_router
from models.schemas import HealthResponse
from services.agent_service import get_agent_service
import os
from pathlib import Path

# Initialize FastAPI app
app = FastAPI(
    title="Startup Idea Validator",
    description="AI-powered startup idea validation using Backboard.io",
    version="1.0.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Error handling middleware
@app.middleware("http")
async def error_handler_middleware(request: Request, call_next):
    """Global error handling middleware"""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error: {str(e)}"}
        )


# Include routers
app.include_router(validator_router)


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and Backboard.io connection"""
    try:
        agent = get_agent_service()
        # Ensure assistant is reachable (lazy check) or just key check
        is_healthy = agent.health_check()
        
        return HealthResponse(
            status="healthy" if is_healthy else "degraded",
            backboard_connected=is_healthy
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            backboard_connected=False
        )


# Mount static files for frontend
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Serve index.html at root
    @app.get("/")
    async def serve_frontend():
        """Serve the frontend application"""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend not found. Please create static/index.html"}
else:
    @app.get("/")
    async def root():
        """Root endpoint when frontend is not available"""
        return {
            "message": "Startup Idea Validator API",
            "docs": "/docs",
            "health": "/health"
        }


if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    
    load_dotenv()
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
