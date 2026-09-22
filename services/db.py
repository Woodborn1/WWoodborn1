import sqlite3
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

DB_PATH = os.getenv("DATABASE_PATH", "vamous_clips.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

_initialized = False

def ensure_db():
    global _initialized
    if not _initialized:
        init_db()
        _initialized = True

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            streamer TEXT NOT NULL,
            title TEXT NOT NULL,
            views INTEGER NOT NULL DEFAULT 0,
            category TEXT DEFAULT 'Just Chatting',
            created_at TEXT NOT NULL,
            chat_activity INTEGER,
            status TEXT DEFAULT 'pending',
            created_in_db TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Check if empty, populate with initial sample clips
    cursor.execute("SELECT COUNT(*) FROM clips")
    count = cursor.fetchone()[0]
    if count == 0:
        now = datetime.utcnow()
        sample_clips = [
            (
                "clip_9842",
                "https://clips.twitch.tv/SparklingPleasantDootCoolCat",
                "Leb1ga",
                "Лебіга про Альпи та лижі",
                1250,
                "Just Chatting",
                (now - timedelta(hours=3)).isoformat() + "Z",
                85,
                "pending"
            ),
            (
                "clip_9843",
                "https://clips.twitch.tv/BlushingTameCaterpillarTwitchRaid",
                "Kavalets",
                "Несподіваний візит ведмедя у Карпатах",
                890,
                "IRL",
                (now - timedelta(days=2)).isoformat() + "Z",
                42,
                "pending"
            ),
            (
                "clip_9844",
                "https://clips.twitch.tv/CourageousFluffyPterodactyl",
                "Ghostik",
                "Неймовірний хайлайт на Centaur Warrunner",
                3400,
                "Dota 2",
                (now - timedelta(days=12)).isoformat() + "Z",
                156,
                "pending"
            ),
            (
                "clip_9845",
                "https://clips.twitch.tv/HonestDependablePelican",
                "Leb1ga",
                "Історія про покупку старого буса",
                2100,
                "Just Chatting",
                (now - timedelta(days=25)).isoformat() + "Z",
                112,
                "pending"
            )
        ]
        cursor.executemany("""
            INSERT INTO clips (id, url, streamer, title, views, category, created_at, chat_activity, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_clips)
        conn.commit()
    
    conn.close()

def parse_period_to_cutoff(period: Optional[str], days: Optional[int] = None) -> Optional[str]:
    """Converts period string ('1d', '24h', '7d', '30d') or days integer to ISO datetime cutoff."""
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
        cutoff = datetime.utcnow() - timedelta(days=target_days)
        return cutoff.isoformat()
    return None

def get_clips(
    limit: int = 50,
    offset: int = 0,
    min_views: int = 0,
    streamer: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    period: Optional[str] = None,
    days: Optional[int] = None,
    sort_by: str = "views"
) -> List[Dict[str, Any]]:
    ensure_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT id, url, streamer, title, views, category, created_at, chat_activity FROM clips WHERE views >= ?"
    params: List[Any] = [min_views]
    
    cutoff_date = parse_period_to_cutoff(period, days)
    if cutoff_date:
        query += " AND created_at >= ?"
        params.append(cutoff_date)
    
    if streamer:
        query += " AND LOWER(streamer) = LOWER(?)"
        params.append(streamer.strip())
        
    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category.strip())
        
    if status:
        query += " AND status = ?"
        params.append(status.strip())
        
    if sort_by == "recent" or sort_by == "date":
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    elif sort_by == "chat":
        query += " ORDER BY chat_activity DESC LIMIT ? OFFSET ?"
    else:  # default 'views'
        query += " ORDER BY views DESC LIMIT ? OFFSET ?"
        
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_clips_count(
    min_views: int = 0,
    streamer: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    period: Optional[str] = None,
    days: Optional[int] = None
) -> int:
    ensure_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT COUNT(*) FROM clips WHERE views >= ?"
    params: List[Any] = [min_views]
    
    cutoff_date = parse_period_to_cutoff(period, days)
    if cutoff_date:
        query += " AND created_at >= ?"
        params.append(cutoff_date)
    
    if streamer:
        query += " AND LOWER(streamer) = LOWER(?)"
        params.append(streamer.strip())
    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category.strip())
    if status:
        query += " AND status = ?"
        params.append(status.strip())
        
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    return count

def insert_or_update_clip(clip_data: Dict[str, Any]) -> bool:
    ensure_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO clips (id, url, streamer, title, views, category, created_at, chat_activity, status)
        VALUES (:id, :url, :streamer, :title, :views, :category, :created_at, :chat_activity, :status)
        ON CONFLICT(id) DO UPDATE SET
            url = excluded.url,
            streamer = excluded.streamer,
            title = excluded.title,
            views = excluded.views,
            category = excluded.category,
            chat_activity = excluded.chat_activity
    """, {
        "id": clip_data["id"],
        "url": clip_data["url"],
        "streamer": clip_data["streamer"],
        "title": clip_data["title"],
        "views": clip_data.get("views", 0),
        "category": clip_data.get("category", "Just Chatting"),
        "created_at": clip_data.get("created_at") or datetime.utcnow().isoformat() + "Z",
        "chat_activity": clip_data.get("chat_activity"),
        "status": clip_data.get("status", "pending")
    })
    conn.commit()
    conn.close()
    return True

def update_clip_status(clip_id: str, status: str, error: Optional[str] = None) -> bool:
    ensure_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE clips SET status = ? WHERE id = ?
    """, (status, clip_id))
    conn.commit()
    conn.close()
    return True
