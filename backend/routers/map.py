"""Map endpoints for retrieving user's visited areas."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.map import MapSummaryResponse
from services.auth import get_current_user
from services.map_service import MapService


router = APIRouter()


@router.get("/summary", response_model=MapSummaryResponse)
def get_map_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all countries and regions the user has visited.

    Returns a summary of visited locations for fog of war rendering.
    Frontend uses Mapbox's built-in boundary layers with these codes.
    """
    service = MapService(db, current_user.id)
    result = service.get_summary()

    return MapSummaryResponse(
        countries=[
            {"code": c["code"], "name": c["name"]}
            for c in result["countries"]
        ],
        regions=[
            {"code": r["code"], "name": r["name"]}
            for r in result["regions"]
        ],
    )
