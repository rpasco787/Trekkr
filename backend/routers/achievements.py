"""Achievements API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.achievements import AchievementsListResponse, UnlockedAchievementsResponse, AchievementSchema
from services.achievement_service import AchievementService
from services.auth import get_current_user


router = APIRouter()


@router.get("", response_model=AchievementsListResponse)
def get_all_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all achievements with user's unlock status.

    Returns the complete list of achievements in the system,
    with each achievement showing whether the current user has unlocked it.
    """
    service = AchievementService(db, current_user.id)
    all_achievements = service.get_all_with_status()

    unlocked_count = sum(1 for a in all_achievements if a["unlocked"])

    return AchievementsListResponse(
        achievements=[AchievementSchema(**a) for a in all_achievements],
        total=len(all_achievements),
        unlocked_count=unlocked_count,
    )


@router.get("/unlocked", response_model=UnlockedAchievementsResponse)
def get_unlocked_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get only user's unlocked achievements.

    Returns achievements the current user has earned, sorted by unlock date.
    """
    service = AchievementService(db, current_user.id)
    unlocked = service.get_unlocked()

    return UnlockedAchievementsResponse(
        achievements=[AchievementSchema(**a) for a in unlocked],
        total=len(unlocked),
    )
