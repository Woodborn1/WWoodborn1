import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from services.db import init_db
from routes.clips import router as clips_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    yield

app = FastAPI(
    title="Vamous Stream Clips API",
    description="REST API ендпоінт для нарізок та кліпів сайту Vamous (Twitch / Kick / YouTube)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(clips_router)

@app.get("/", summary="Root Endpoint")
async def root():
    return {
        "service": "Vamous Clips API",
        "status": "online",
        "docs_url": "/docs",
        "endpoints": {
            "clips": "/api/clips",
            "queue": "/api/clips/queue",
            "refresh": "/api/refresh-database"
        }
    }

@app.get("/health", summary="Health Check for Render")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
