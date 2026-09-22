import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient

DEFAULT_MONGO_URI = "mongodb+srv://woodborn1:E54w2tdKMhF5tKMd@cluster0.gsoelvs.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or os.getenv("DATABASE_URL") or DEFAULT_MONGO_URI
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "twitch_data")

client: Optional[AsyncIOMotorClient] = None

# Built-in Game ID to Name dictionary for fast lookup
COMMON_GAMES: Dict[str, str] = {
    "509658": "Just Chatting",
    "29595": "Dota 2",
    "32399": "Counter-Strike",
    "516575": "VALORANT",
    "21779": "League of Legends",
    "33214": "Fortnite",
    "27471": "Minecraft",
    "512710": "Call of Duty: Warzone",
    "511224": "Apex Legends",
    "181319": "Grand Theft Auto V",
    "29106": "S.T.A.L.K.E.R. 2: Heart of Chornobyl",
    "509672": "Travel & Outdoors",
    "509660": "Art",
    "26936": "Music",
    "498592": "I'm Only Sleeping",
    "518203": "Sports",
    "513143": "Teamfight Tactics",
    "490100": "LOST ARK",
    "143106037": "EA Sports FC 24",
    "1745202779": "EA Sports FC 25",
    "497078": "PUBG: BATTLEGROUNDS"
}

def is_mongo_enabled() -> bool:
    return bool(MONGODB_URI and (MONGODB_URI.startswith("mongodb://") or MONGODB_URI.startswith("mongodb+srv://")))

def get_mongo_client() -> Optional[AsyncIOMotorClient]:
    global client
    if not is_mongo_enabled():
        return None
    if client is None:
        client = AsyncIOMotorClient(MONGODB_URI)
    return client

def get_collection(region: str = "ua"):
    c = get_mongo_client()
    if c is None:
        return None
    db = c[MONGODB_DB_NAME]
    col_name = "clips_en" if region.lower() == "en" else "clips"
    return db[col_name]

def map_mongo_doc_to_clip(doc: Dict[str, Any]) -> Dict[str, Any]:
    clip_id = str(doc.get("id") or doc.get("_id") or "")
    url = str(doc.get("url") or f"https://clips.twitch.tv/{clip_id}")
    streamer = str(doc.get("broadcaster_name") or doc.get("streamer") or doc.get("author") or "Стрімер")
    title = str(doc.get("title") or "Нарізка з Vamous")
    
    views = doc.get("view_count")
    if views is None:
        views = doc.get("views") or 0
    if not isinstance(views, int):
        try:
            views = int(views)
        except Exception:
            views = 0
            
    game_id = str(doc.get("game_id") or "")
    category = doc.get("category") or doc.get("game") or COMMON_GAMES.get(game_id) or (f"Game ID {game_id}" if game_id else "Just Chatting")
    
    created_at_dt = doc.get("created_at_dt")
    if isinstance(created_at_dt, datetime):
        if created_at_dt.tzinfo is None:
            created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
        created_at = created_at_dt.isoformat()
    else:
        created_at = str(doc.get("created_at") or datetime.now(timezone.utc).isoformat())

    chat_activity = doc.get("chat_activity") or doc.get("chatActivity")

    return {
        "id": clip_id,
        "url": url,
        "streamer": streamer,
        "title": title,
        "views": views,
        "category": str(category),
        "created_at": created_at,
        "chat_activity": chat_activity
    }

def parse_period_to_cutoff_dt(period: Optional[str], days: Optional[int] = None) -> Optional[datetime]:
    target_days = None
    if days is not None and days > 0:
        target_days = days
    elif period:
        p = period.lower().strip()
        if p in ["1d", "24h", "today", "day", "1"]:
            target_days = 1
        elif p in ["7d", "week", "7"]:
            target_days = 7
        elif p in ["30d", "month", "30"]:
            target_days = 30
        elif p.endswith("d") and p[:-1].isdigit():
            target_days = int(p[:-1])

    if target_days:
        return datetime.now(timezone.utc) - timedelta(days=target_days)
    return None

def build_mongo_filter(
    min_views: int = 0,
    streamer: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,
    days: Optional[int] = None
) -> Dict[str, Any]:
    query: Dict[str, Any] = {}
    
    cutoff_dt = parse_period_to_cutoff_dt(period, days)
    if cutoff_dt:
        # Match against created_at_dt (datetime) or fallback to created_at (string)
        query["$or"] = [
            {"created_at_dt": {"$gte": cutoff_dt}},
            {"created_at": {"$gte": cutoff_dt.isoformat()}}
        ]

    if min_views > 0:
        views_cond = {"$or": [{"view_count": {"$gte": min_views}}, {"views": {"$gte": min_views}}]}
        if "$or" in query:
            query = {"$and": [{"$or": query["$or"]}, views_cond]}
        else:
            query["$or"] = views_cond["$or"]

    if streamer:
        clean_streamer = streamer.strip()
        reg = {"$regex": f"^{re.escape(clean_streamer)}$", "$options": "i"}
        s_cond = {"$or": [{"broadcaster_name": reg}, {"streamer": reg}, {"author": reg}]}
        if "$and" in query:
            query["$and"].append(s_cond)
        elif query:
            query = {"$and": [query, s_cond]}
        else:
            query = s_cond

    if category:
        clean_cat = category.strip()
        # Find matching game_id if in COMMON_GAMES
        matched_gids = [gid for gid, name in COMMON_GAMES.items() if clean_cat.lower() in name.lower()]
        cat_reg = {"$regex": re.escape(clean_cat), "$options": "i"}
        c_conditions = [{"category": cat_reg}, {"game": cat_reg}]
        if matched_gids:
            c_conditions.append({"game_id": {"$in": matched_gids}})
        c_cond = {"$or": c_conditions}
        
        if "$and" in query:
            query["$and"].append(c_cond)
        elif query:
            query = {"$and": [query, c_cond]}
        else:
            query = c_cond

    return query

async def get_clips_mongo(
    limit: int = 1000,
    offset: int = 0,
    min_views: int = 0,
    streamer: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,
    days: Optional[int] = None,
    sort_by: str = "views",
    region: str = "ua"
) -> List[Dict[str, Any]]:
    col = get_collection(region)
    if col is None:
        return []

    filter_query = build_mongo_filter(min_views, streamer, category, period, days)

    # Sorting
    if sort_by in ["recent", "date"]:
        sort_spec = [("created_at_dt", -1), ("_id", -1)]
    elif sort_by == "chat":
        sort_spec = [("chat_activity", -1), ("view_count", -1)]
    else:  # default 'views'
        sort_spec = [("view_count", -1), ("created_at_dt", -1)]

    cursor = col.find(filter_query).sort(sort_spec).skip(offset).limit(limit)
    raw_docs = await cursor.to_list(length=limit)
    
    return [map_mongo_doc_to_clip(d) for d in raw_docs]

async def get_clips_count_mongo(
    min_views: int = 0,
    streamer: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,
    days: Optional[int] = None,
    region: str = "ua"
) -> int:
    col = get_collection(region)
    if col is None:
        return 0

    filter_query = build_mongo_filter(min_views, streamer, category, period, days)
    return await col.count_documents(filter_query)
