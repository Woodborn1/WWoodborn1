import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, status
from models.schemas import ClipItem, ClipCreate, ClipListResponse, StatusUpdateRequest, RefreshResponse
from services.db import get_clips, get_clips_count, insert_or_update_clip, update_clip_status
from services.twitch_service import fetch_and_sync_twitch_clips
from services.vamous_service import sync_all_clips_from_vamous

router = APIRouter(prefix="/api", tags=["Clips"])

async def run_full_sync():
    """Runs sync from both Vamous site and Twitch."""
    await sync_all_clips_from_vamous()
    await fetch_and_sync_twitch_clips()

@router.get("/clips", response_model=ClipListResponse, summary="Отримати список нарізок/кліпів з сайту Vamous")
async def list_clips(
    limit: int = Query(1000, ge=1, le=5000, description="Кількість записів (до 5000)"),
    offset: int = Query(0, ge=0, description="Зміщення (пагінація)"),
    min_views: int = Query(0, ge=0, description="Мінімальна кількість переглядів"),
    streamer: Optional[str] = Query(None, description="Фільтр за нікнеймом стрімера"),
    category: Optional[str] = Query(None, description="Фільтр за категорією/грою"),
    period: Optional[str] = Query(None, description="Період: '1d' (за день/24h), '7d' (за тиждень), '30d' (за місяць), 'all'"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Точна кількість днів (наприклад, 1, 30)"),
    sort_by: str = Query("views", description="Сортування: 'views' (найпопулярніші), 'recent' (найновіші), 'chat' (активність чату)"),
    status: Optional[str] = Query(None, description="Статус кліпу (pending/processed/skipped)")
):
    """
    Повертає кліпи з сайту Vamous (усі 581+ кліпів за день або 3000+ за весь час):
    - **id**: унікальний ідентифікатор кліпу
    - **url**: посилання на кліп (Twitch/Kick/YouTube)
    - **streamer**: нікнейм стрімера
    - **title**: назва кліпу
    - **views**: кількість переглядів
    - **category**: категорія/гра
    - **created_at**: дата створення кліпу
    - **chat_activity**: кількість повідомлень у чаті (опціонально)
    """
    raw_clips = get_clips(
        limit=limit,
        offset=offset,
        min_views=min_views,
        streamer=streamer,
        category=category,
        status=status,
        period=period,
        days=days,
        sort_by=sort_by
    )
    total = get_clips_count(
        min_views=min_views,
        streamer=streamer,
        category=category,
        status=status,
        period=period,
        days=days
    )
    
    clips = [ClipItem(**c) for c in raw_clips]
    return ClipListResponse(total=total, clips=clips)

@router.get("/clips/queue", summary="Отримати чергу нових кліпів для пайплайну обробки")
async def get_clip_queue(
    limit: int = Query(500, ge=1, le=2000),
    min_views: int = Query(0, ge=0),
    streamer: Optional[str] = Query(None, description="Фільтр за стрімером"),
    period: Optional[str] = Query(None, description="Період: '1d', '7d', '30d'")
):
    """
    Повертає кліпи зі статусом 'pending', які готові до транскрипції та обробки в Obsidian.
    """
    raw_clips = get_clips(
        limit=limit,
        offset=0,
        min_views=min_views,
        streamer=streamer,
        period=period,
        status="pending",
        sort_by="views"
    )
    clips = [ClipItem(**c) for c in raw_clips]
    return {"clips": clips}

@router.post("/clips", response_model=ClipItem, status_code=status.HTTP_201_CREATED, summary="Додати новий кліп вручну або через webhook")
async def create_clip(clip_input: ClipCreate):
    clip_id = clip_input.id or f"clip_{uuid.uuid4().hex[:8]}"
    created_at = clip_input.created_at or datetime.utcnow().isoformat() + "Z"
    
    clip_dict = {
        "id": clip_id,
        "url": clip_input.url,
        "streamer": clip_input.streamer,
        "title": clip_input.title,
        "views": clip_input.views or 0,
        "category": clip_input.category or "Just Chatting",
        "created_at": created_at,
        "chat_activity": clip_input.chat_activity,
        "status": "pending"
    }
    
    insert_or_update_clip(clip_dict)
    return ClipItem(**clip_dict)

@router.patch("/clips/{clip_id}/status", summary="Оновити статус обробки кліпу")
async def update_status(clip_id: str, payload: StatusUpdateRequest):
    success = update_clip_status(clip_id, payload.status, payload.error)
    if not success:
        raise HTTPException(status_code=404, detail="Кліп не знайдено")
    return {"status": "ok", "clip_id": clip_id, "updated_status": payload.status}

@router.post("/refresh-database", response_model=RefreshResponse, summary="Запустити синхронізацію та оновлення бази з сайту Vamous")
async def refresh_database(background_tasks: BackgroundTasks):
    """
    Синхронізує повну базу кліпів безпосередньо з сайту Vamous та Twitch.
    """
    background_tasks.add_task(run_full_sync)
    return RefreshResponse(
        status="success",
        message="Повна синхронізація кліпів з сайту Vamous запущена у фоновому режимі"
    )
