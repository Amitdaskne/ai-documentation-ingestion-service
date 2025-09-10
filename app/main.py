from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.database.base import engine, Base
from app.api import formats, templates, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created")
    
    yield
    
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="AI-Powered Documentation Ingestion Service",
    description="Intelligent service for ingesting documentation packages and generating reusable templates",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(formats.router)
app.include_router(templates.router)
app.include_router(files.router)


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "AI-Powered Documentation Ingestion Service",
        "version": "1.0.0",
        "description": "Upload documentation packages to generate reusable templates",
        "endpoints": {
            "formats": "/api/v1/formats",
            "templates": "/api/v1/templates",
            "files": "/api/v1/files"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "doc-ingestion"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )