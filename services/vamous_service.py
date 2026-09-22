import httpx
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from .db import insert_or_update_clip

VAMOUS_BASE_URL = "https://vamoosnarizky.com/api/clips"

def parse_vamous_date_to_iso(date_str: str) -> str:
    """Parses date from 'DD.MM.YYYY HH:MM:SS' or similar to ISO 8601 string."""
    if not date_str:
        return datetime.utcnow().isoformat() + "Z"
    
    # Try DD.MM.YYYY HH:MM:SS
    try:
        dt = datetime.strptime(date_str.strip(), "%d.%m.%Y %H:%M:%S")
        return dt.isoformat() + "Z"
    except Exception:
        pass

    try:
        dt = datetime.strptime(date_str.strip(), "%d.%m.%Y")
        return dt.isoformat() + "Z"
    except Exception:
        pass

    # If already ISO
    return date_str

def extract_clip_id(url: str) -> str:
    """Extracts clip slug or unique ID from Twitch/Kick/YouTube URL."""
    if not url:
        return "clip_unknown"
    # Twitch clip URL pattern
    match = re.search(r"/clip/([a-zA-Z0-9_\-]+)", url)
    if match:
        return f"vamous_{match.group(1)}"
    match_tv = re.search(r"clips\.twitch\.tv/([a-zA-Z0-9_\-]+)", url)
    if match_tv:
        return f"vamous_{match_tv.group(1)}"
    
    # YouTube pattern
    match_yt = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_\-]+)", url)
    if match_yt:
        return f"vamous_yt_{match_yt.group(1)}"
        
    return f"vamous_{abs(hash(url))}"

async def sync_all_clips_from_vamous(max_pages: int = 150) -> int:
    """
    Fetches all clips directly from Vamous site (https://vamoosnarizky.com/api/clips)
    and saves them in the local database in the requested schema.
    """
    print(f"[VamousSync] Connecting to {VAMOUS_BASE_URL} to fetch clips...")
    total_synced = 0
    page = 1
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while page <= max_pages:
            try:
                resp = await client.get(f"{VAMOUS_BASE_URL}?page={page}&limit=100", headers=headers)
                if resp.status_code != 200:
                    print(f"[VamousSync] Page {page} returned status {resp.status_code}. Stopping.")
                    break
                
                data = resp.json()
                raw_clips = data.get("clips", [])
                if not raw_clips:
                    break
                    
                total_on_site = data.get("total", 0)
                
                for item in raw_clips:
                    clip_url = item.get("clipUrl") or ""
                    if not clip_url:
                        continue
                        
                    clip_id = extract_clip_id(clip_url)
                    created_at_iso = parse_vamous_date_to_iso(item.get("createdAt", ""))
                    streamer_name = item.get("author") or "Стрімер"
                    title = item.get("title") or "Нарізка з Vamous"
                    
                    clip_dict = {
                        "id": clip_id,
                        "url": clip_url,
                        "streamer": streamer_name,
                        "title": title,
                        "views": item.get("views", 0) if isinstance(item.get("views"), int) else 0,
                        "category": item.get("category") or "Just Chatting",
                        "created_at": created_at_iso,
                        "chat_activity": item.get("chat_activity"),
                        "status": "pending"
                    }
                    
                    insert_or_update_clip(clip_dict)
                    total_synced += 1
                    
                print(f"[VamousSync] Synced page {page} ({len(raw_clips)} clips) | Total synced: {total_synced} / {total_on_site}")
                
                if total_synced >= total_on_site or len(raw_clips) == 0:
                    break
                    
                page += 1
            except Exception as e:
                print(f"[VamousSync] Error on page {page}: {e}")
                break
                
    print(f"[VamousSync] Completed! Total clips synced from Vamous: {total_synced}")
    return total_synced
