import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from services.db import init_db
from services.twitch_service import fetch_and_sync_twitch_clips
from routes.clips import router as clips_router

async def periodic_twitch_sync():
    """Periodically fetches trending and fresh clips every 30 minutes."""
    while True:
        try:
            await fetch_and_sync_twitch_clips(days_back=30)
        except Exception as e:
            print(f"[PeriodicSync] Error in periodic sync: {e}")
        await asyncio.sleep(1800)  # 30 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    init_db()
    
    # Start background sync task
    sync_task = asyncio.create_task(periodic_twitch_sync())
    
    yield
    
    sync_task.cancel()

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
