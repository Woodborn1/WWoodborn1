import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or os.getenv("DATABASE_URL")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "vamous")
MONGODB_COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME", "clips")

client: Optional[AsyncIOMotorClient] = None

def is_mongo_enabled() -> bool:
    return bool(MONGODB_URI and (MONGODB_URI.startswith("mongodb://") or MONGODB_URI.startswith("mongodb+srv://")))

def get_mongo_client() -> Optional[AsyncIOMotorClient]:
    global client
    if not is_mongo_enabled():
        return None
    if client is None:
        client = AsyncIOMotorClient(MONGODB_URI)
    return client

def get_collection():
    c = get_mongo_client()
    if c is None:
        return None
    
    # If DB name specified in URI, use default database
    db = c.get_default_database() if c.get_default_database() is not None else c[MONGODB_DB_NAME]
    return db[MONGODB_COLLECTION_NAME]

def format_date_to_iso(val: Any) -> str:
    if isinstance(val, datetime):
        return val.isoformat() + "Z"
    if isinstance(val, str):
        # Try DD.MM.YYYY HH:MM:SS
        try:
            dt = datetime.strptime(val.strip(), "%d.%m.%Y %H:%M:%S")
            return dt.isoformat() + "Z"
        except Exception:
            pass
        try:
            dt = datetime.strptime(val.strip(), "%d.%m.%Y")
            return dt.isoformat() + "Z"
        except Exception:
            pass
        return val
    return datetime.utcnow().isoformat() + "Z"

def map_mongo_doc_to_clip(doc: Dict[str, Any]) -> Dict[str, Any]:
    clip_id = str(doc.get("id") or doc.get("clipId") or doc.get("_id") or "")
    url = str(doc.get("url") or doc.get("clipUrl") or doc.get("link") or "")
    streamer = str(doc.get("streamer") or doc.get("author") or doc.get("channel") or "Стрімер")
    title = str(doc.get("title") or doc.get("name") or "Нарізка з Vamous")
    
    views = doc.get("views") or doc.get("viewCount") or doc.get("view_count") or 0
    if not isinstance(views, int):
        try:
            views = int(views)
        except Exception:
            views = 0
            
    category = doc.get("category") or doc.get("game") or doc.get("game_name") or "Just Chatting"
    created_at_raw = doc.get("created_at") or doc.get("createdAt") or doc.get("date") or doc.get("timestamp")
    created_at = format_date_to_iso(created_at_raw)
    
    chat_activity = doc.get("chat_activity") or doc.get("chatActivity") or doc.get("commentsCount")
    if chat_activity is not None:
        try:
            chat_activity = int(chat_activity)
        except Exception:
            chat_activity = None

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

async def get_clips_mongo(
    limit: int = 1000,
    offset: int = 0,
    min_views: int = 0,
    streamer: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,
    days: Optional[int] = None,
    sort_by: str = "views"
) -> List[Dict[str, Any]]:
    col = get_collection()
    if col is None:
        return []

    filter_query: Dict[str, Any] = {}
    
    # Calculate cutoff date
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
        cutoff_dt = datetime.utcnow() - timedelta(days=target_days)
        cutoff_str_iso = cutoff_dt.isoformat()
        cutoff_str_ua = cutoff_dt.strftime("%d.%m.%Y")
        
        # Support both datetime fields (createdAt/created_at) and string dates
        filter_query["$or"] = [
            {"createdAt": {"$gte": cutoff_dt}},
            {"created_at": {"$gte": cutoff_dt}},
            {"createdAt": {"$gte": cutoff_str_iso}},
            {"created_at": {"$gte": cutoff_str_iso}},
            {"createdAt": {"$gte": cutoff_str_ua}}
        ]

    if min_views > 0:
        filter_query["$or"] = filter_query.get("$or", [])
        views_filter = [
            {"views": {"$gte": min_views}},
            {"viewCount": {"$gte": min_views}}
        ]
        if filter_query.get("$or"):
            filter_query = {"$and": [{"$or": filter_query["$or"]}, {"$or": views_filter}]}
        else:
            filter_query["$or"] = views_filter

    if streamer:
        regex_pattern = {"$regex": f"^{re.escape(streamer.strip())}$", "$options": "i"}
        streamer_condition = {"$or": [{"streamer": regex_pattern}, {"author": regex_pattern}, {"channel": regex_pattern}]}
        if "$and" in filter_query:
            filter_query["$and"].append(streamer_condition)
        elif filter_query:
            filter_query = {"$and": [filter_query, streamer_condition]}
        else:
            filter_query = streamer_condition

    if category:
        cat_pattern = {"$regex": f"^{re.escape(category.strip())}$", "$options": "i"}
        cat_condition = {"$or": [{"category": cat_pattern}, {"game": cat_pattern}]}
        if "$and" in filter_query:
            filter_query["$and"].append(cat_condition)
        elif filter_query:
            filter_query = {"$and": [filter_query, cat_condition]}
        else:
            filter_query = cat_condition

    # Sorting
    sort_fields = [("views", -1), ("createdAt", -1)]
    if sort_by in ["recent", "date"]:
        sort_fields = [("createdAt", -1), ("created_at", -1), ("_id", -1)]
    elif sort_by == "chat":
        sort_fields = [("chat_activity", -1), ("chatActivity", -1)]

    cursor = col.find(filter_query).sort(sort_fields).skip(offset).limit(limit)
    raw_docs = await cursor.to_list(length=limit)
    
    return [map_mongo_doc_to_clip(d) for d in raw_docs]

async def get_clips_count_mongo(
    min_views: int = 0,
    streamer: Optional[str] = None,
    category: Optional[str] = None,
    period: Optional[str] = None,
    days: Optional[int] = None
) -> int:
    col = get_collection()
    if col is None:
        return 0

    filter_query: Dict[str, Any] = {}
    
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
        cutoff_dt = datetime.utcnow() - timedelta(days=target_days)
        cutoff_str_iso = cutoff_dt.isoformat()
        cutoff_str_ua = cutoff_dt.strftime("%d.%m.%Y")
        filter_query["$or"] = [
            {"createdAt": {"$gte": cutoff_dt}},
            {"created_at": {"$gte": cutoff_dt}},
            {"createdAt": {"$gte": cutoff_str_iso}},
            {"created_at": {"$gte": cutoff_str_iso}},
            {"createdAt": {"$gte": cutoff_str_ua}}
        ]

    if min_views > 0:
        views_filter = [
            {"views": {"$gte": min_views}},
            {"viewCount": {"$gte": min_views}}
        ]
        if filter_query.get("$or"):
            filter_query = {"$and": [{"$or": filter_query["$or"]}, {"$or": views_filter}]}
        else:
            filter_query["$or"] = views_filter

    if streamer:
        regex_pattern = {"$regex": f"^{re.escape(streamer.strip())}$", "$options": "i"}
        streamer_condition = {"$or": [{"streamer": regex_pattern}, {"author": regex_pattern}, {"channel": regex_pattern}]}
        if "$and" in filter_query:
            filter_query["$and"].append(streamer_condition)
        elif filter_query:
            filter_query = {"$and": [filter_query, streamer_condition]}
        else:
            filter_query = streamer_condition

    if category:
        cat_pattern = {"$regex": f"^{re.escape(category.strip())}$", "$options": "i"}
        cat_condition = {"$or": [{"category": cat_pattern}, {"game": cat_pattern}]}
        if "$and" in filter_query:
            filter_query["$and"].append(cat_condition)
        elif filter_query:
            filter_query = {"$and": [filter_query, cat_condition]}
        else:
            filter_query = cat_condition

    return await col.count_documents(filter_query)
