import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from services.db import init_db
from services.mongo_db import is_mongo_enabled, get_mongo_client
from services.vamous_service import sync_all_clips_from_vamous
from services.twitch_service import fetch_and_sync_twitch_clips
from routes.clips import router as clips_router

async def periodic_sync_worker():
    """Periodically fetches clips from Vamous site and Twitch every 30 minutes if using local SQLite."""
    if is_mongo_enabled():
        print("[App] MongoDB is active. Bypassing local SQLite sync.")
        return
        
    try:
        await sync_all_clips_from_vamous()
        await fetch_and_sync_twitch_clips(days_back=30)
    except Exception as e:
        print(f"[PeriodicSync] Initial sync error: {e}")
        
    while True:
        await asyncio.sleep(1800)  # 30 minutes
        try:
            await sync_all_clips_from_vamous()
            await fetch_and_sync_twitch_clips(days_back=30)
        except Exception as e:
            print(f"[PeriodicSync] Error in periodic sync: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_mongo_enabled():
        print("[App] Connecting to MongoDB Atlas / Remote Database...")
        get_mongo_client()
    else:
        init_db()
        
    sync_task = asyncio.create_task(periodic_sync_worker())
    
    yield
    
    sync_task.cancel()

app = FastAPI(
    title="Vamous Stream Clips API",
    description="REST API ендпоінт для нарізок та кліпів сайту Vamous (Twitch / Kick / YouTube) з підтримкою MongoDB",
    version="1.1.0",
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
    db_type = "MongoDB" if is_mongo_enabled() else "SQLite"
    return {
        "service": "Vamous Clips API",
        "status": "online",
        "database": db_type,
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
