import os
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from .db import insert_or_update_clip

STREAMERS_LIST = os.getenv(
    "STREAMERS",
    "leb1ga,kavalets,ghostik,ceh9,viktoriia_tori,michael_lebiga,dank1ng,yozhyk,s1mple"
).split(",")

TWITCH_GQL_URL = "https://gql.twitch.tv/gql"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

GQL_QUERY = """
query ClipsCards__User($login: String!, $filter: ClipFilterCriterion!) {
  user(login: $login) {
    id
    login
    displayName
    clips(first: 30, criteria: {filter: $filter}) {
      edges {
        node {
          id
          slug
          url
          title
          viewCount
          createdAt
          game {
            name
          }
          broadcaster {
            displayName
          }
        }
      }
    }
  }
}
"""

async def fetch_streamer_clips_gql(streamer: str, filter_type: str = "ALL_TIME") -> List[Dict[str, Any]]:
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    streamer_clean = streamer.strip().lower()
    if not streamer_clean:
        return []
        
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(TWITCH_GQL_URL, json={
                "query": GQL_QUERY,
                "variables": {
                    "login": streamer_clean,
                    "filter": filter_type
                }
            }, headers=headers)
            
            if resp.status_code != 200:
                return []
                
            data = resp.json().get("data", {}).get("user")
            if not data:
                return []
                
            edges = data.get("clips", {}).get("edges", [])
            clips = []
            for edge in edges:
                node = edge.get("node")
                if not node:
                    continue
                
                game_name = "Just Chatting"
                if node.get("game") and node["game"].get("name"):
                    game_name = node["game"]["name"]
                    
                broadcaster_name = node.get("broadcaster", {}).get("displayName") or streamer
                
                clips.append({
                    "id": f"twitch_{node.get('slug', node.get('id'))}",
                    "url": node.get("url") or f"https://clips.twitch.tv/{node.get('slug')}",
                    "streamer": broadcaster_name,
                    "title": node.get("title") or "Кліп зі стріму",
                    "views": node.get("viewCount", 0),
                    "category": game_name,
                    "created_at": node.get("createdAt"),
                    "chat_activity": None,
                    "status": "pending"
                })
            return clips
    except Exception as e:
        print(f"[TwitchService] Error fetching GQL clips for {streamer}: {e}")
        return []

async def fetch_and_sync_twitch_clips(streamers: Optional[List[str]] = None, days_back: int = 30) -> int:
    target_streamers = streamers or [s.strip() for s in STREAMERS_LIST if s.strip()]
    
    filter_type = "LAST_MONTH"
    if days_back <= 1:
        filter_type = "LAST_DAY"
    elif days_back <= 7:
        filter_type = "LAST_WEEK"
    elif days_back > 30:
        filter_type = "ALL_TIME"
        
    print(f"[TwitchSync] Starting live sync for {len(target_streamers)} streamers with filter {filter_type}...")
    total_synced = 0
    
    # Also query LAST_DAY for all streamers to ensure freshest clips are captured
    for streamer in target_streamers:
        for f in ["LAST_DAY", filter_type]:
            clips = await fetch_streamer_clips_gql(streamer, filter_type=f)
            for c in clips:
                insert_or_update_clip(c)
                total_synced += 1
                
    print(f"[TwitchSync] Successfully synced {total_synced} clips into database.")
    return total_synced
