import os
import httpx
from typing import List, Dict, Any
from datetime import datetime, timedelta
from .db import insert_or_update_clip

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
DEFAULT_STREAMERS = os.getenv("STREAMERS", "Leb1ga,Kavalets,Ghostik,viktoriia_tori,mikhailo_lebiga").split(",")

async def get_twitch_app_token() -> str:
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return ""
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://id.twitch.tv/oauth2/token", params={
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        })
        if resp.status_code == 200:
            return resp.json().get("access_token", "")
    return ""

async def fetch_and_sync_twitch_clips(streamers: List[str] = DEFAULT_STREAMERS, days_back: int = 7) -> int:
    token = await get_twitch_app_token()
    if not token:
        print("[TwitchSync] No Twitch credentials provided. Skipping live Twitch sync.")
        return 0
    
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }
    
    started_at = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"
    total_synced = 0
    
    async with httpx.AsyncClient() as client:
        for streamer in streamers:
            streamer = streamer.strip()
            if not streamer:
                continue
            
            # 1. Get user id
            user_resp = await client.get("https://api.twitch.tv/helix/users", headers=headers, params={"login": streamer})
            if user_resp.status_code != 200:
                continue
            users = user_resp.json().get("data", [])
            if not users:
                continue
            broadcaster_id = users[0]["id"]
            broadcaster_name = users[0]["display_name"]
            
            # 2. Get clips for broadcaster
            clips_resp = await client.get("https://api.twitch.tv/helix/clips", headers=headers, params={
                "broadcaster_id": broadcaster_id,
                "started_at": started_at,
                "first": 20
            })
            if clips_resp.status_code == 200:
                clips_data = clips_resp.json().get("data", [])
                for item in clips_data:
                    clip_dict = {
                        "id": item["id"],
                        "url": item["url"],
                        "streamer": broadcaster_name,
                        "title": item["title"],
                        "views": item.get("view_count", 0),
                        "category": item.get("game_id", "Just Chatting"),
                        "created_at": item["created_at"],
                        "chat_activity": None,
                        "status": "pending"
                    }
                    insert_or_update_clip(clip_dict)
                    total_synced += 1
                    
    return total_synced
