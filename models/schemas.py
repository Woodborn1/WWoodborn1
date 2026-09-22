from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ClipItem(BaseModel):
    id: str = Field(..., description="Унікальний ідентифікатор кліпу")
    url: str = Field(..., description="Посилання на кліп (Twitch/Kick/YouTube)")
    streamer: str = Field(..., description="Нікнейм стрімера")
    title: str = Field(..., description="Назва кліпу")
    views: int = Field(default=0, description="Кількість переглядів")
    category: Optional[str] = Field(default="Just Chatting", description="Категорія/гра")
    created_at: str = Field(..., description="Дата створення кліпу (ISO 8601)")
    chat_activity: Optional[int] = Field(default=None, description="Кількість повідомлень у чаті (опціонально)")

class ClipCreate(BaseModel):
    id: Optional[str] = None
    url: str
    streamer: str
    title: str
    views: Optional[int] = 0
    category: Optional[str] = "Just Chatting"
    created_at: Optional[str] = None
    chat_activity: Optional[int] = None

class ClipListResponse(BaseModel):
    total: int
    clips: List[ClipItem]

class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Статус: pending, processed, skipped, error")
    error: Optional[str] = None

class RefreshResponse(BaseModel):
    status: str
    message: str
    count: Optional[int] = 0
