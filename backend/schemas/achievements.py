"""Pydantic schemas for achievements endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AchievementUnlockedSchema(BaseModel):
    """Achievement that was just unlocked (returned in location ingest response)."""

    code: str
    name: str
    description: Optional[str] = None


class AchievementSchema(BaseModel):
    """Achievement with user's unlock status."""

    code: str
    name: str
    description: Optional[str] = None
    unlocked: bool
    unlocked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AchievementsListResponse(BaseModel):
    """Response for GET /achievements endpoint."""

    achievements: list[AchievementSchema]
    total: int
    unlocked_count: int


class UnlockedAchievementsResponse(BaseModel):
    """Response for GET /achievements/unlocked endpoint."""

    achievements: list[AchievementSchema]
    total: int
