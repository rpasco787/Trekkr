"""Map endpoints for retrieving user's visited areas."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from schemas.map import MapSummaryResponse, MapCellsResponse, BoundingBox
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


@router.get("/cells", response_model=MapCellsResponse)
def get_map_cells(
    min_lng: float,
    min_lat: float,
    max_lng: float,
    max_lat: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get H3 cells within the bounding box.

    Returns H3 cell indexes at resolutions 6 and 8 that the user
    has visited within the specified viewport.
    """
    # Validate bounding box
    try:
        bbox = BoundingBox(
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.errors()[0]["msg"]),
        )

    service = MapService(db, current_user.id)
    result = service.get_cells_in_viewport(
        min_lng=bbox.min_lng,
        min_lat=bbox.min_lat,
        max_lng=bbox.max_lng,
        max_lat=bbox.max_lat,
    )

    return MapCellsResponse(res6=result["res6"], res8=result["res8"])
